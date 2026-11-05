"""原生DataKit公开组件的薄绑定；运输由独立QuoteStreamReceiver拥有。"""
from __future__ import annotations
import ctypes
import json
import os
from pathlib import Path
import threading
import time


class _CurrentDay(ctypes.Structure):
    """与GHCurrentDay默认C布局一致；原Writer字段值不在绑定层换算。"""
    _fields_ = [
        ('trading_date', ctypes.c_uint32),  # 来源交易日YYYYMMDD，0表示未知。
        ('action_date', ctypes.c_uint32),  # 来源自然日YYYYMMDD。
        ('action_time', ctypes.c_uint32),  # 来源上海HHMMSSmmm。
        ('open', ctypes.c_double),  # 当日开盘价，沿原profile单位。
        ('high', ctypes.c_double),  # 当日最高价。
        ('low', ctypes.c_double),  # 当日最低价。
        ('close', ctypes.c_double),  # 当日最新价，持续变化。
        ('volume', ctypes.c_double),  # 当日累计成交量，沿原profile单位。
        ('amount', ctypes.c_double),  # 当日累计成交额，沿原profile单位。
    ]

class NativeDataKitSession:
    """创建/关闭归管理线程；push归唯一SHM接收线程，分钟和存储全部归原Writer。"""
    def __init__(self, configuration, native_directory):
        self._owner=threading.get_ident()
        self._directory=Path(native_directory).resolve(strict=True)
        self._dll_path=self._directory/'GuanhengDataKitSession.dll'
        self._dll_directory=os.add_dll_directory(str(self._directory)) if hasattr(os,'add_dll_directory') else None
        self._library=ctypes.CDLL(str(self._dll_path))
        lib=self._library
        lib.gh_datakit_create.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.POINTER(ctypes.c_void_p)];lib.gh_datakit_create.restype=ctypes.c_int
        lib.gh_datakit_push_quotes.argtypes=[ctypes.c_void_p,ctypes.c_char_p,ctypes.c_uint32];lib.gh_datakit_push_quotes.restype=ctypes.c_int
        lib.gh_datakit_archive.argtypes=[ctypes.c_void_p,ctypes.c_char_p];lib.gh_datakit_archive.restype=ctypes.c_int
        lib.gh_datakit_archive_done.argtypes=[ctypes.c_void_p,ctypes.c_char_p];lib.gh_datakit_archive_done.restype=ctypes.c_int
        lib.gh_datakit_count.argtypes=[ctypes.c_void_p,ctypes.c_uint32];lib.gh_datakit_count.restype=ctypes.c_uint64
        lib.gh_datakit_close.argtypes=[ctypes.c_void_p];lib.gh_datakit_close.restype=ctypes.c_int
        self._session=ctypes.c_void_p()
        module=(self._directory.as_posix().rstrip('/')+'/').encode('utf8')
        code=lib.gh_datakit_create(str(Path(configuration).resolve(strict=True)).encode('utf8'),module,ctypes.byref(self._session))
        if code!=0 or not self._session.value:
            raise RuntimeError('native_datakit_initialization_failed')
        self._closed=False
        self._writer_failed=False
        # 模式由原生已准入的实例返回，Python不重新解释另一份配置。
        self._lifecycle_writer=lib.gh_datakit_count(self._session,3)==1

    def _check_writer_failure(self):
        # key4 为原 Writer sink 的真实 LL_ERROR 闩锁；并发读取只访问原子计数。
        # 失败保留到对象关闭以后，时段过滤/广播数差额不会触发此判断。
        if not self._closed and self._library.gh_datakit_count(self._session,4):
            self._writer_failed=True
        if self._writer_failed:
            raise RuntimeError('native_datakit_writer_failed')

    def check_health(self):
        """管理 owner 在稳态调用；与 push 并发安全，捕获没有后续批次的后台故障。

        仅检查错误闩锁，不读取行情或释放资源；调用方须停止 Receiver 并 join 后关闭。
        """
        if threading.get_ident()!=self._owner:
            raise RuntimeError('native_datakit_health_owner')
        self._check_writer_failure()
        if self._closed:
            raise RuntimeError('native_datakit_closed')
        return True

    def push(self,ticks,kind):
        if self._closed or kind not in ('snapshot','incremental'):
            raise RuntimeError('native_datakit_input_not_admitted')
        self._check_writer_failure()
        raw=json.dumps(ticks,ensure_ascii=True,allow_nan=False,separators=(',',':')).encode('ascii')
        result=self._library.gh_datakit_push_quotes(self._session,raw,len(raw))
        if result==-6:self._writer_failed=True
        self._check_writer_failure()
        if result!=len(ticks):
            raise RuntimeError('native_datakit_batch_failed_'+str(result))
        return result

    def counts(self):
        if self._closed:
            self._check_writer_failure()
            raise RuntimeError('native_datakit_closed')
        self._check_writer_failure()
        values=dict(subscribed=self._library.gh_datakit_count(self._session,0),
            delivered=self._library.gh_datakit_count(self._session,1),
            writer_processed=self._library.gh_datakit_count(self._session,2))
        self._check_writer_failure()
        return values

    def current_days(self, symbols):
        """管理线程按实际订阅读取原Writer；无数据证券不填0或猜测交易日。

        仅显式启用盘中日线投影的部署调用新增导出，旧DLL及原默认采集保持原路径。
        每次只持有一个证券副本，返回集合由调用方替换发布，不追加日志或历史。
        """
        if threading.get_ident()!=self._owner or self._closed:
            raise RuntimeError('native_datakit_current_day_owner')
        self._check_writer_failure()
        read=self._library.gh_datakit_current_day
        read.argtypes=[ctypes.c_void_p,ctypes.c_char_p,ctypes.c_char_p,ctypes.POINTER(_CurrentDay)]
        read.restype=ctypes.c_int
        result=[]
        for symbol in symbols:
            code,suffix=symbol.split('.')
            exchange={'SH':'SSE','SZ':'SZSE','BJ':'BSE'}[suffix]
            row=_CurrentDay()
            state=read(self._session,code.encode('ascii'),exchange.encode('ascii'),ctypes.byref(row))
            if state<0:
                raise RuntimeError('native_datakit_current_day_failed')
            if state:
                result.append(dict(symbol=exchange+'.'+code,
                    **{key:getattr(row,key) for key,unused in _CurrentDay._fields_}))
        return result

    def archive(self,session_id,deadline):
        """所有报价生产者先停止；原收盘任务完成与文件正确性分别确认。"""
        if threading.get_ident()!=self._owner or self._closed or time.monotonic()>=deadline:
            raise RuntimeError('native_datakit_archive_owner_or_deadline')
        if self._lifecycle_writer:
            raise RuntimeError('lifecycle_writer_requires_archive_and_close')
        sid=session_id.encode('ascii')
        self._check_writer_failure()
        result=self._library.gh_datakit_archive(self._session,sid)
        if result==-6:self._writer_failed=True
        self._check_writer_failure()
        if result!=0:
            raise RuntimeError('native_datakit_archive_failed')
        while True:
            if time.monotonic()>=deadline:raise TimeoutError('native_datakit_archive_deadline')
            state=self._library.gh_datakit_archive_done(self._session,sid)
            if state==-6:self._writer_failed=True
            self._check_writer_failure()
            if state==1:return
            if state<0:raise RuntimeError('native_datakit_archive_state_failed')
            time.sleep(min(.02,max(0,deadline-time.monotonic())))

    def archive_and_close(self,session_id):
        """生产者已停止并join后提交归档，再由适配Writer排空/join。

        返回只证明原生close成功；DSB是否完整由调用者使用Helper回读确认。
        磁盘或dumper可能阻塞，外层进程owner继续持有原截止和资源所有权。
        """
        if threading.get_ident()!=self._owner or self._closed or not self._lifecycle_writer:
            raise RuntimeError('native_datakit_lifecycle_owner_or_mode')
        sid=session_id.encode('ascii')
        if not sid or len(sid)>15:
            raise ValueError('native_datakit_session_id')
        # 无论归档准入还是后台写入失败，生产者已 join 的 owner 都继续真实 close。
        # 调用方不重提未知归档；close 的资源结果与 Writer 失败分别处理。
        result=self._library.gh_datakit_archive(self._session,sid)
        if result==-6:self._writer_failed=True
        self.close()
        if result!=0:
            raise RuntimeError('native_datakit_archive_failed')

    def close(self):
        """先 join Receiver。负返回保留句柄；+1 先标记已释放，再报告 Writer 失败。"""
        if self._closed:
            self._check_writer_failure()
            return
        if threading.get_ident()!=self._owner:raise RuntimeError('native_datakit_close_owner')
        if self._library.gh_datakit_count(self._session,4):self._writer_failed=True
        result=self._library.gh_datakit_close(self._session)
        if result not in (0,1):
            raise RuntimeError('native_datakit_close_failed')
        if result==1:self._writer_failed=True
        self._session=ctypes.c_void_p();self._closed=True
        if self._dll_directory is not None:self._dll_directory.close();self._dll_directory=None
        self._check_writer_failure()

    @property
    def supports_draining_archive(self):
        """实例选择的Writer能否在close时排空归档；事实来自原生准入结果。"""
        return self._lifecycle_writer

    @property
    def closed(self):return self._closed
