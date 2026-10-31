"""受管本地进程的唯一监督实现；业务契约通过子类受保护hook提供。"""
from __future__ import annotations
import ctypes
from ctypes import wintypes
import hashlib
import json
import math
import os
from pathlib import Path, PureWindowsPath
import re
import stat
import threading
import time
from uuid import uuid4
from .thread_owner import ThreadOwner

_SHA = re.compile(r'[0-9a-f]{64}')

def _require(value):
    if not value:
        raise ValueError('invalid managed Host deployment')


def _duration(value, maximum):
    # JSON整数可任意大；先用整数安全比较收窄范围，再调用需要浮点转换的isfinite。
    _require(type(value) in (int, float) and .1 <= value <= maximum and math.isfinite(value))
    return float(value)


def _sha(value):
    _require(type(value) is str and _SHA.fullmatch(value) is not None)
    return value


def _path(value, *, e_drive=False):
    _require(type(value) is str and 1 <= len(value) <= 1024 and chr(0) not in value)
    win = PureWindowsPath(value)
    _require(win.is_absolute() and re.fullmatch(r'[A-Za-z]:', win.drive) is not None
             and '..' not in win.parts and all(':' not in p for p in win.parts[1:]))
    if e_drive:
        _require(win.drive.lower() == 'e:')
    return Path(value)


def _inspect(path, *, directory=False):
    # 每个祖先与叶子均先lstat；不resolve跟随重解析点，不接受链接到其它身份。
    for item in reversed((path, *path.parents)):
        info = item.lstat()
        _require(not stat.S_ISLNK(info.st_mode) and not (getattr(info, 'st_file_attributes', 0) & 0x400))
        if item != path:
            _require(stat.S_ISDIR(info.st_mode))
    _require(stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode) and info.st_nlink == 1)
    return info


def _identity(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def _open_read(path):
    """Windows保留真实共享/拒绝码；fd接管后只由stream关闭句柄。"""
    if os.name != 'nt':
        return path.open('rb')
    import msvcrt
    api = ctypes.WinDLL('kernel32', use_last_error=True)
    api.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                               ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    api.CreateFileW.restype = wintypes.HANDLE
    api.CloseHandle.argtypes, api.CloseHandle.restype = [wintypes.HANDLE], wintypes.BOOL
    handle = api.CreateFileW(str(path), 0x80000000, 1 | 4, None, 3, 0x00200000, None)
    if handle == ctypes.c_void_p(-1).value:
        code = ctypes.get_last_error()
        raise ctypes.WinError(code)
    try:
        fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
    except BaseException:
        api.CloseHandle(handle)
        raise
    try:
        return os.fdopen(fd, 'rb')
    except BaseException:
        os.close(fd)
        raise


def _read(path, maximum, *, clock=None, deadline=None, inspector=None):
    inspect = inspector or _inspect
    before = inspect(path)
    _require(0 <= before.st_size <= maximum)
    if clock is not None and clock() >= deadline:
        raise TimeoutError('managed metadata deadline')
    with _open_read(path) as stream:
        opened = os.fstat(stream.fileno())
        # share=0发布者写入期间open报32/33；打开成功后才判断正文非空，避免创建瞬间0B误判。
        _require((opened.st_dev, opened.st_ino) == (before.st_dev, before.st_ino)
                 and stat.S_ISREG(opened.st_mode) and opened.st_nlink == 1 and 0 < opened.st_size <= maximum)
        raw = stream.read(maximum + 1)
        _require(_identity(os.fstat(stream.fileno())) == _identity(opened))
    _require(len(raw) == opened.st_size and _identity(inspect(path)) == _identity(opened))
    if clock is not None and clock() >= deadline:
        raise TimeoutError('managed metadata deadline')
    return raw


def _json(raw):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            _require(key not in value)
            value[key] = item
        return value
    def reject(unused):
        raise ValueError('nonfinite control number')
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=unique, parse_constant=reject)
    except (ValueError, UnicodeError, RecursionError):
        raise ValueError('invalid bounded control document') from None
    _require(type(value) is dict)
    return value


def _job():
    # App导入不加载Host或Windows进程后端；实际启动时才构造原ProcessJob。
    from .strategy_job import ProcessJob
    return ProcessJob()


class ManagedLocalProcess:
    """一个App生命周期只启动一次本地服务；运行期监督线程是Job唯一操作owner。

    start接收绝对单调截止并等待ready；ready只证明子类收据声明的监听就绪。
    request_close只发布内存停止，监督者原子写stop。close(seconds)沿首停机D
    join监督者和管道；监督者join后close才能续核资源。失败保留未确认资源，kill只作故障收口。
    """
    _status_schema = 'managed.local-process-status.v1'
    _stop_schema = None
    _thread_name = 'managed-local-process'

    def __init__(self, config=None, *, job_factory=None, thread_factory=threading.Thread, clock=time.monotonic):
        self.config = config
        self._job_factory, self._thread_factory, self._clock = job_factory or _job, thread_factory, clock
        self._condition = threading.Condition()
        self._stop, self._ready, self._wake = threading.Event(), threading.Event(), threading.Event()
        self._stop_deadline = None
        self._monitor = self._job = self._host_handle = None
        self._readers, self._buffers = [], [bytearray(), bytearray()]
        self._eof = [False, False]
        self._attempted = self._constructing = self._reaping = False
        self._job_start_claimed = self._job_start_finished = False
        self._reaped = self._graceful = self._graceful_confirmed = self._forced = False
        self._state = 'disabled' if config is None else 'new'
        self._error = None
        self._control_id = str(uuid4())
        self._directory = Path(config.control_root) / self._control_id if config else None
        self._host_pid = self._exit_code = None
        self._stop_written = False

    @property
    def startup_seconds(self):
        return self.config.startup_seconds if self.config else 0.0

    @property
    def shutdown_seconds(self):
        return self.config.stop_seconds if self.config else 0.0

    def status(self):
        with self._condition:
            pending = self._constructing or (self._monitor is not None and self._monitor.pending)
            pending = pending or self._job is not None and not self._reaped or self._host_handle is not None
            return {'schema': self._status_schema, 'state': self._state,
                    'ready': self._state == 'ready' and not self._stop.is_set(),
                    'qmt_connection': 'not_checked', 'pending': bool(pending),
                    'error_code': self._error, 'forced': self._forced, 'pid': self._host_pid}

    def _failure(self, code):
        with self._condition:
            if self._error is None:
                self._error = code
            self._state = 'faulted'
        self.request_close()
        self._ready.set()

    def request_close(self):
        with self._condition:
            if self._stop_deadline is None:
                self._stop_deadline = self._clock() + self.shutdown_seconds
            if self._state not in ('disabled', 'closed', 'faulted'):
                self._state = 'stopping'
            self._stop.set()
        self._wake.set()

    def _check(self, deadline):
        if self._clock() >= deadline:
            raise TimeoutError('original Host process deadline')

    def _verify_file(self, path, expected_sha256, maximum, deadline):
        """原句柄前后身份与SHA校验；流式读取沿原启动截止。"""
        info = _inspect(path)
        _require(0 < info.st_size <= maximum)
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            _require(_identity(os.fstat(stream.fileno())) == _identity(info))
            while True:
                self._check(deadline)
                part = stream.read(131072)
                if not part:
                    break
                digest.update(part)
            _require(_identity(os.fstat(stream.fileno())) == _identity(info))
        _require(_identity(_inspect(path)) == _identity(info) and digest.hexdigest() == expected_sha256)
        self._check(deadline)

    def _validate_inputs(self, deadline):
        """子类核其部署输入；此hook在监督线程和原启动D内调用。"""
        raise NotImplementedError

    def _receipt(self, name, deadline):
        """子类校验有限收据及实例身份，返回含pid的独立值。"""
        raise NotImplementedError

    def _command(self):
        """子类返回固定argv；凭证不进入命令行。"""
        raise NotImplementedError

    def _claim_pid(self, pid):
        # venv launcher与实际Host PID可以不同；持有真实句柄并核本Job成员，拒绝PID快照推断。
        job = self._job
        handle = job.api.OpenProcess(0x1000, False, pid)
        if not handle:
            raise OSError('Host identity unavailable')
        self._host_handle = handle
        inside = wintypes.BOOL()
        if not job.api.IsProcessInJob(handle, job.handle, ctypes.byref(inside)) or not inside.value:
            raise OSError('Host identity outside owned Job')
        self._host_pid = pid

    def _reader(self, index, pipe):
        try:
            while True:
                chunk = pipe.read(4096)
                if not chunk:
                    self._eof[index] = True
                    self._wake.set()
                    return
                prefix = self._buffers[index]
                remaining = self.config.max_output_bytes - len(prefix)
                if remaining:
                    prefix.extend(chunk[:remaining])
                if len(chunk) > remaining:
                    self._failure('output_limit')
                # 超额后仍排空；原始字节只留有限私有内存，status从不暴露它。
        except BaseException:
            self._failure('pipe_read')

    def _start_readers(self):
        for index, pipe in enumerate((self._job.stdout, self._job.stderr)):
            if pipe is None:
                continue
            reader = ThreadOwner(target=self._reader, args=(index, pipe), name=self._thread_name + '-pipe-' + str(index),
                                 daemon=True, thread_factory=self._thread_factory)
            self._readers.append(reader)
            reader.start()

    def _retry_sharing(self, read, deadline):
        """只续读32/33，始终使用首个关闭D及调用者D的较早者。"""
        while True:
            effective = min(deadline, self._stop_deadline if self._stop_deadline is not None else deadline)
            self._check(effective)
            try:
                return read(effective)
            except OSError as error:
                if getattr(error, 'winerror', None) not in (32, 33):
                    raise
                self._check(effective)
                time.sleep(min(.01, max(0., effective - self._clock())))

    def _existing_stop(self, target):
        value = _json(self._retry_sharing(lambda end: _read(target, 4096, clock=self._clock, deadline=end), self._stop_deadline))
        _require(set(value) == {'schema', 'control_id', 'deadline'}
                 and value['schema'] == self._stop_schema and value['control_id'] == self._control_id
                 and type(value['deadline']) in (int, float) and math.isfinite(value['deadline'])
                 and value['deadline'] <= self._stop_deadline)
        with self._condition:
            self._stop_deadline = min(self._stop_deadline, value['deadline'])
        self._stop_written = True

    def _publish_stop(self):
        if self._stop_written or self._host_pid is None:
            return
        _inspect(self._directory, directory=True)
        target = self._directory / 'stop.json'
        try:
            self._existing_stop(target)
            return
        except FileNotFoundError:
            pass
        raw = json.dumps({'schema': self._stop_schema, 'control_id': self._control_id,
                          'deadline': self._stop_deadline}, separators=(',', ':'), allow_nan=False).encode('utf-8')
        _require(0 < len(raw) <= 4096)
        temporary = self._directory / ('stop-' + str(uuid4()) + '.tmp')
        # 同一私有目录先完整写临时文件，再Windows独占rename；失败临时文件保留，不删除证据。
        with temporary.open('xb') as stream:
            _require(stream.write(raw) == len(raw))
            stream.flush()
            os.fsync(stream.fileno())
        _inspect(temporary)
        try:
            os.rename(temporary, target)
        except FileExistsError:
            self._existing_stop(target)  # 只接受本control_id且不延长首D的已有命令。
            return
        self._stop_written = True

    def _reap(self, deadline):
        job = self._job
        if job is None:
            self._reaped = True
            return True
        try:
            if not self._job_start_claimed or (self._job_start_finished and job.process is None):
                # 原Job输出槽确认没有进程句柄；close_reaped仍核整树0并逐项关闭部分创建资源。
                job.close_reaped()
                self._reaped = True
                return True
            self._exit_code = job.wait(max(0, deadline - self._clock()))
            if job.poll() is None or job.active_processes() != 0:
                return False
            joined = [reader.join_until(deadline, clock=self._clock) for reader in self._readers]
            if not all(joined):
                return False
            if len(self._readers) != 2 or not all(self._eof):
                # start部分失败尚无两个pipe时，仍可回收；不会授优雅完成。
                if self._error is None:
                    return False
            if self._host_handle is not None:
                exit_code = wintypes.DWORD()
                if not job.api.GetExitCodeProcess(self._host_handle, ctypes.byref(exit_code)):
                    return False
                if exit_code.value != 0:
                    self._failure('host_exit')
                if not job.api.CloseHandle(self._host_handle):
                    return False
                self._host_handle = None
            job.close_reaped()
            self._reaped = True
            self._buffers = [bytearray(), bytearray()]
            return True
        except BaseException:
            return False

    def _run(self, startup_deadline):
        stage = 'configuration'
        try:
            if self._stop.is_set():
                return
            self._validate_inputs(startup_deadline)
            if self._stop.is_set():
                return
            # ProcessJob构造无OS资源；先存owner再start。stop期间晚返回也归本监督者。
            job = self._job_factory()
            self._job = job
            if self._stop.is_set():
                return
            cfg = self.config
            argv = self._command()
            stage = 'process_start'
            self._job_start_claimed = True
            try:
                job.start(argv, str(Path(cfg.pythonw).parent), deadline=startup_deadline, clock=self._clock)
            finally:
                self._job_start_finished = True
            stage = 'pipe_start'
            self._start_readers()
            stage = 'control_receipt'
            admitted = False
            while True:
                now = self._clock()
                if not admitted:
                    try:
                        ready = self._receipt('ready.json', startup_deadline)
                    except OSError as exc:
                        if isinstance(exc, FileNotFoundError) or getattr(exc, 'winerror', None) in (32, 33):
                            ready = None
                        else:
                            raise
                    if ready is not None:
                        self._claim_pid(ready['pid'])
                        stage = 'startup_timeout'
                        with self._condition:
                            # 句柄成员核验也消耗原启动D；锁内提交ready前重新取同一时钟。
                            self._check(startup_deadline)
                            admitted = True
                            if not self._stop.is_set():
                                self._state = 'ready'
                        stage = 'control_receipt'
                        self._ready.set()
                    elif now >= startup_deadline:
                        self._failure('startup_timeout')
                if self._stop.is_set():
                    self._publish_stop()
                exited = job.poll()
                if exited is not None and job.active_processes() == 0:
                    self._exit_code = exited
                    if not self._stop.is_set():
                        self._failure('unexpected_exit')
                    break
                if self._stop.is_set() and now >= self._stop_deadline:
                    self._forced = True
                    self._failure('stop_timeout')
                    job.close_job()
                    break
                self._wake.wait(.01)
                self._wake.clear()
            deadline = self._stop_deadline
            if not self._forced and self._error is None and self._exit_code == 0:
                self._retry_sharing(lambda end: self._receipt('closed.json', end), deadline)
                self._graceful = self._stop_written
            elif self._exit_code != 0:
                self._failure('host_exit')
        except BaseException:
            self._failure(stage)
        finally:
            if self._job is not None and self._error is not None:
                try:
                    if (self._job.process is not None and self._job.poll() is None) or self._job.active_processes():
                        self._forced = True
                        self._job.close_job()
                except BaseException:
                    self._failure('job_stop')
            deadline = self._stop_deadline if self._stop_deadline is not None else self._clock() + self.shutdown_seconds
            if not self._reap(deadline):
                self._failure('cleanup_unconfirmed')
            elif self._graceful:
                with self._condition:
                    # close可在资源核实期间收紧D；旧局部值不能授越过最早截止的成功。
                    expired = self._clock() >= min(deadline, self._stop_deadline)
                if expired:
                    self._failure('stop_timeout')
                    self._graceful = False
            self._ready.set()
            self._wake.set()

    def start(self, deadline):
        _require(type(deadline) in (int, float) and math.isfinite(deadline))
        if self.config is None:
            return True
        with self._condition:
            if self._attempted or self._stop.is_set():
                return False
            self._attempted, self._constructing, self._state = True, True, 'starting'
        end = min(deadline, self._clock() + self.startup_seconds)
        try:
            monitor = ThreadOwner(target=self._run, args=(end,), name=self._thread_name, daemon=True,
                                  thread_factory=self._thread_factory)
            with self._condition:
                self._monitor = monitor  # constructing保留到start尝试及ready等待退出，close不能越过未调用start的owner。
                claimed = not self._stop.is_set()
            if claimed:
                monitor.start()
            else:
                self._ready.set()
            if not self._ready.wait(max(0, end - self._clock())):
                self._failure('startup_timeout')
            with self._condition:
                expired = self._clock() >= end
                ready = self._state == 'ready' and not self._stop.is_set()
            if expired:
                self._failure('startup_timeout')
                return False
            return ready
        except BaseException:
            self._failure('monitor_start')
            return False
        finally:
            with self._condition:
                self._constructing = False
                self._condition.notify_all()

    def close(self, timeout=2.0):
        _require(type(timeout) in (int, float) and math.isfinite(timeout) and 0 <= timeout <= 120)
        if self.config is None:
            return True
        end = self._clock() + timeout
        with self._condition:
            if self._graceful_confirmed:
                return True  # 仅已取得实际join/句柄关闭且原D内确认过的资格允许幂等返回。
            self._stop_deadline = min(end, self._stop_deadline) if self._stop_deadline is not None else min(end, self._clock() + self.shutdown_seconds)
            self._stop.set()
            if self._state not in ('disabled', 'closed', 'faulted'):
                self._state = 'stopping'
            while self._constructing or self._reaping:
                remaining = end - self._clock()
                if remaining <= 0:
                    return False
                self._condition.wait(remaining)
            self._reaping = True
        self._wake.set()
        try:
            if self._monitor is not None and not self._monitor.join_until(end, clock=self._clock):
                return False
            # 原stop D不重写；晚close仅续核已停止资源，不重启/不授超期优雅资格。
            if not self._reaped and not self._reap(end):
                return False
            with self._condition:
                success = self._error is None and (self._graceful or not self._job_start_claimed)
                expired = self._job_start_claimed and self._clock() >= min(end, self._stop_deadline)
                if success and not expired:
                    self._state = 'closed'
                    self._graceful_confirmed = self._job_start_claimed
                    return True
                self._state = 'faulted'
            if success and expired:
                self._failure('stop_timeout')
                self._graceful = False
            return False
        finally:
            with self._condition:
                self._reaping = False
                self._condition.notify_all()
