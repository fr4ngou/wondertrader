"""运行边界的最小失败诊断；不复制异常正文、路径、参数或金融状态。"""
from __future__ import annotations

from datetime import datetime, timezone
import atexit
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import stat
import threading
import time


_PHASES = frozenset((
    'runtime_construct', 'signal_register', 'runtime_start',
    'initial_status_snapshot', 'initial_status_publish', 'ready_publish',
    'stop_poll', 'loop_status_snapshot', 'loop_status_publish',
    'stop_read', 'stop_validate', 'component_check', 'close_request', 'cycle_wait',
    'runtime_close', 'final_status_snapshot', 'final_status_publish',
    'signal_restore', 'receipt_publish',
))
_TYPES = (FileNotFoundError, PermissionError, FileExistsError, TimeoutError,
          BrokenPipeError, ConnectionError, OSError, ValueError, TypeError,
          KeyError, RuntimeError, AssertionError, OverflowError, MemoryError, Exception)


def _integer(value):
    return value if type(value) is int and -(2**31) <= value < 2**31 else None


def _event(phase, error):
    # 类型只取有限内置类别；自定义类名、args/filename/cause/traceback均可能携带秘密。
    return dict(phase=phase if phase in _PHASES else 'unknown',
        exception_type=next((kind.__name__ for kind in _TYPES if isinstance(error, kind)), 'Exception'),
        errno=_integer(getattr(error, 'errno', None)) if isinstance(error, OSError) else None,
        winerror=_integer(getattr(error, 'winerror', None)) if isinstance(error, OSError) else None)


class FailureDiagnostic:
    """先纯值记录，原收口结束后另写版本化旁证；诊断写失败保持原异常和退出结果。"""
    def __init__(self, directory, identity, publish):
        self.directory = directory  # 本代原控制目录；只发布固定diagnostic.json，不采集或输出目录正文。
        self.identity = identity  # 原control/instance/PID/config摘要；不含凭证、账户或业务结果。
        self.publish = publish  # 原严格发布接缝；旁证写入失败不改变原异常、清理及退出结果。
        self.phase = 'runtime_construct'  # 当前边界固定阶段，捕获时只认_PHASES白名单。
        self.failure = None  # 首次异常的纯值分类；None表示未观察异常，后续清理错误独立保存。

    def __enter__(self):
        return self

    def capture(self, error):
        if self.failure is None:
            try:
                self.failure = _event(self.phase, error)
            except Exception:
                pass

    def __exit__(self, kind, error, traceback):
        secondary = None
        if isinstance(error, Exception):
            if self.failure is None:
                self.capture(error)
            else:
                try:
                    secondary = _event(self.phase, error)
                except Exception:
                    pass
        if self.failure is not None:
            try:
                self.publish(self.directory, 'diagnostic.json', dict(
                    schema='guanheng.wt-runtime-diagnostic.v1', **self.identity,
                    failure=self.failure, cleanup_failure=secondary))
            except Exception:
                pass
        return False


_LOG_QUEUE = queue.Queue(maxsize=256)  # 整个宿主共用，最多256条、每条4096字节；原管道不等待磁盘。
_LOG_START = threading.Lock()  # 只保护本进程唯一写线程的创建，不与日志文件锁混用。
_LOG_THREAD = None  # daemon写线程仅一个；磁盘阻塞时不按运行代不断新增线程。


def _write_process_events():
    while True:
        owner, body = _LOG_QUEUE.get()
        try:
            owner._write(body)
        finally:
            with owner._lock:
                owner._queued -= 1
                if owner._queued == 0:
                    owner._drained.set()
            _LOG_QUEUE.task_done()


def _start_process_log_writer():
    global _LOG_THREAD
    with _LOG_START:
        if _LOG_THREAD is None:
            worker = threading.Thread(target=_write_process_events, name='process-event-log', daemon=True)
            worker.start()
            _LOG_THREAD = worker


def flush_process_logs(timeout=.5):
    """业务收口完成后有限等候日志；未落盘仍为pending，不改变原关闭结果。"""
    end = time.monotonic() + timeout
    while _LOG_QUEUE.unfinished_tasks and time.monotonic() < end:
        time.sleep(min(.01, max(0., end-time.monotonic())))
    return _LOG_QUEUE.unfinished_tasks == 0


atexit.register(flush_process_logs)


class ProcessEventLog:
    """受管进程的有界事件留存；只接受固定类别和结构，不写入原始输出。

    管道/监督者只解析并投入全进程有界队列，磁盘由唯一写线程处理。
    同系列的跨进程写入通过非阻塞文件锁协调，容量判断、轮转和追加同锁。
    三份轮转加当前文件，默认总预算4MiB；另有固定1字节锁文件。
    """
    _exceptions = frozenset(kind.__name__ for kind in _TYPES) | {
        'ModuleNotFoundError', 'ImportError', 'SyntaxError', 'NameError', 'AttributeError',
        'UnicodeDecodeError', 'JSONDecodeError', 'KeyboardInterrupt', 'SystemExit',
        'RetainedValidationError', 'CtaBridgeError', 'SessionError', 'SourceUnavailable', 'SourcePending'}
    _files = frozenset(('host.py', '__main__.py', 'managed_local_process.py', 'qmt_host_process.py',
        'source_market_process.py', 'history_preparation_process.py', 'execution_process.py',
        'execution_configured.py', 'strategy_job.py', 'runtime.py', 'source.py', 'protocol.py',
        'source_runtime.py', 'threading.py', 'runpy.py'))
    _codes = frozenset(('configuration', 'process_start', 'pipe_start', 'control_receipt',
        'startup_timeout', 'unexpected_exit', 'stop_timeout', 'host_exit', 'job_stop',
        'cleanup_unconfirmed', 'output_limit', 'pipe_read', 'monitor_start'))
    _events = frozenset(('process_started', 'process_ready', 'process_failure',
        'process_closed', 'stream_exception', 'stream_summary'))
    _structured_stderr = (b'GH_TRADE_REPLY_INTERRUPTED ', b'GH_ACCOUNT_READ_FINISH ')

    def __init__(self, root, control_id, component, *, max_bytes=1024*1024, backups=3):
        if not 4096 <= max_bytes <= 16*1024*1024 or type(backups) is not int or not 1 <= backups <= 8:
            raise ValueError('process_log_budget')
        self.root = Path(root)  # 部署的稳定控制根；跨运行代复用，日志不放入金融状态目录。
        self.control_id = control_id  # 当前运行代UUID，仅用于关联原状态及进程。
        self.component = component  # 固定宿主组件名，不接受配置正文或账户标识。
        self.max_bytes, self.backups = max_bytes, backups  # 每文件字节上限和轮转份数，总占用有界。
        self._lock = threading.Lock()  # 只保护内存解析/计数；磁盘IO始终在锁外。
        self._pending = [bytearray(), bytearray()]  # 每流最多8192字节未换行片段，归本对象。
        self._oversize = [False, False]  # 超长行丢弃到下个换行，避免截断正文被当作异常。
        self._hashes = [hashlib.sha256(), hashlib.sha256()]  # 整条流摘要，不保留原文。
        self._sizes = [0, 0]  # 实际消费字节数，区别于受限内存前缀长度。
        self._structured_bytes = 0  # 本代交易Host严格准入的stderr诊断字节，独立走有界日志队列。
        self._frames = [[], []]  # 每条流最多八个已知模块的行位置，不保存路径、源码或局部变量。
        self._errors = 0  # 日志写入失败次数；不覆盖原业务失败或改变交易语义。
        self._written = 0  # 本代成功落盘事件数，供验真核查日志是否实际工作。
        self._queued = 0  # 本代尚未完成的日志数，包含正在磁盘写入的一条。
        self._dropped = 0  # 全进程队列已满/写线程启动失败导致的未受理数，不授落盘资格。
        self._drained = threading.Event()  # 只供独立诊断验真有限等待，监督关闭不等待此事件。
        self._drained.set()

    @staticmethod
    def _regular(path):
        try:
            info = path.lstat()
        except FileNotFoundError:
            return
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise OSError('process_log_path')

    @contextmanager
    def _series_lock(self):
        """固定锁文件留存以保持锁身份；竞争时即时报错，不阻塞监督或无限等待。"""
        path = self.root/'process-events.lock'
        self._regular(path)
        with path.open('a+b') as stream:
            stream.seek(0)
            def initialize():
                # 锁可覆盖EOF之外的字节；先取得锁再初始化，避免两个初代各追加一字节。
                if stream.seek(0, os.SEEK_END) == 0:
                    stream.write(b'\0')
                    stream.flush()
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                try:
                    initialize()
                    yield
                finally:
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                try:
                    initialize()
                    yield
                finally:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def _write(self, body):
        """唯一写线程消费完整脱敏字节；文件同步不持有内存/进程状态锁。"""
        try:
            info = self.root.lstat()
            if not stat.S_ISDIR(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                raise OSError('process_log_root')
            with self._series_lock():
                path = self.root/'process-events.jsonl'
                self._regular(path)
                if path.exists() and path.stat().st_size+len(body) > self.max_bytes:
                    oldest = self.root/('process-events.jsonl.'+str(self.backups))
                    self._regular(oldest)
                    oldest.unlink(missing_ok=True)
                    for index in range(self.backups-1, 0, -1):
                        source = self.root/('process-events.jsonl.'+str(index))
                        self._regular(source)
                        if source.exists():
                            os.replace(source, self.root/('process-events.jsonl.'+str(index+1)))
                    os.replace(path, self.root/'process-events.jsonl.1')
                with path.open('ab') as stream:
                    if stream.write(body) != len(body):
                        raise OSError('process_log_short_write')
                    stream.flush()
                    os.fsync(stream.fileno())
            with self._lock:
                self._written += 1
        except Exception:
            with self._lock:
                self._errors += 1

    def _append(self, event, data):
        # 调用方持有内存锁：先登记pending，再允许写线程消费；队满立即退回。
        try:
            row = dict(schema='guanheng.process-event.v1', occurred_at=datetime.now(timezone.utc).isoformat(),
                       component=self.component, control_id=self.control_id, event=event, **data)
            body = (json.dumps(row, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode('utf8')
            if len(body) > 4096:
                raise ValueError('process_log_record_capacity')
            _start_process_log_writer()
            self._queued += 1
            self._drained.clear()
            try:
                _LOG_QUEUE.put_nowait((self, body))
            except queue.Full:
                self._queued -= 1
                if self._queued == 0:
                    self._drained.set()
                raise
        except Exception:
            self._dropped += 1

    def event(self, event, *, code=None, error=None, exit_code=None):
        """固定生命周期事件；异常正文、参数、路径及自定义类型名不进入记录。"""
        if event not in self._events:
            raise ValueError('process_log_event')
        value = dict(code=code if code in self._codes else None, exit_code=_integer(exit_code))
        if error is not None:
            try:
                value['exception'] = _event('unknown', error)
            except Exception:
                value['exception'] = dict(phase='unknown', exception_type='Exception', errno=None, winerror=None)
        with self._lock:
            self._append(event, value)

    def _line(self, index, raw):
        # 只解析标准异常类别和Windows错误码；秘密出现在正文、普通输出或自定义
        # 异常类名时均丢弃。完整输出仅形成摘要，不写入日志或公开状态。
        line = raw.decode('utf8', errors='replace').strip()
        if index == 1 and self.component == 'trade-host-process' and len(raw) <= 160 and raw.endswith(b'\n'):
            wire = raw.removesuffix(b'\n').removesuffix(b'\r').decode('utf8', errors='replace')
            reply = re.fullmatch(r'GH_TRADE_REPLY_INTERRUPTED '
                r'(invalid_arguments|queue_full|capability_unavailable|call_expired|reply_too_large|binding_closed|unknown) '
                r'(replied|not_sent|unknown) ([a-f0-9]{64})', wire)
            if reply:
                self._append('trade_reply_interrupted', dict(level='ERROR', phase='collect_trade_reply',
                    rpc_error=reply[1], delivery=reply[2], command_sha256=reply[3], action='reconcile_original'))
                self._structured_bytes += len(raw)
                return
            finish = re.fullmatch(r'GH_ACCOUNT_READ_FINISH '
                r'(commit_timeout|identity_unconfirmed|original_rejection_already_terminal|'
                r'original_result_already_terminal|original_request_interrupted) ([a-f0-9]{64})', wire)
            if finish:
                level = 'ERROR' if finish[1] in ('commit_timeout', 'identity_unconfirmed') else 'INFO'
                self._append('account_read_finish_recovery', dict(level=level, phase='persist_original_read',
                    outcome=finish[1], request_sha256=finish[2]))
                self._structured_bytes += len(raw)
                return
        frame = re.fullmatch(r'File "(.*)", line ([0-9]{1,8}), in .*', line)
        if frame:
            filename = frame[1].replace('\\', '/').rsplit('/', 1)[-1]
            if filename in self._files:
                self._frames[index].append(dict(file=filename, line=int(frame[2])))
                self._frames[index] = self._frames[index][-8:]
            return
        kind = line.split(':', 1)[0]
        if kind not in self._exceptions:
            return
        code = re.search(r'\[WinError ([0-9]{1,5})\]', line)
        number = re.search(r'\[Errno ([0-9]{1,5})\]', line)
        self._append('stream_exception', dict(stream='stdout' if index == 0 else 'stderr',
            exception_type=kind, winerror=int(code[1]) if code else None,
            errno=int(number[1]) if number else None, frames=list(self._frames[index])))
        self._frames[index].clear()

    def feed(self, index, chunk):
        """同次消费管道，返回本流计入原普通输出限额的累计字节。"""
        with self._lock:
            self._sizes[index] += len(chunk)
            self._hashes[index].update(chunk)
            for part in chunk.splitlines(keepends=True):
                pending = self._pending[index]
                complete = part.endswith(b'\n')
                if len(pending)+len(part) > 8192:
                    self._oversize[index] = True
                    pending.clear()
                elif not self._oversize[index]:
                    pending.extend(part)
                if complete:
                    if not self._oversize[index]:
                        self._line(index, bytes(pending))
                    pending.clear()
                    self._oversize[index] = False
            if index != 1 or self.component != 'trade-host-process':
                return self._sizes[index]
            pending = self._pending[index]
            # 仅暂缓可能的固定诊断帧；无效整行或超长仍回到原输出预算。
            provisional = len(pending) if len(pending) <= 160 and any(
                prefix.startswith(pending) or pending.startswith(prefix) for prefix in self._structured_stderr) else 0
            return self._sizes[index] - self._structured_bytes - provisional

    def finish(self, index):
        """EOF时落盘尾行和整流摘要；原内存前缀稍后清空也保留诊断。"""
        with self._lock:
            if self._pending[index] and not self._oversize[index]:
                self._line(index, bytes(self._pending[index]))
            self._pending[index].clear()
            self._append('stream_summary', dict(stream='stdout' if index == 0 else 'stderr',
                bytes=self._sizes[index], sha256=self._hashes[index].hexdigest()))
            return self._sizes[index] - (self._structured_bytes if index == 1 else 0)

    def snapshot(self):
        """独立诊断纯值；日志故障与原进程状态各自留证。"""
        with self._lock:
            return dict(schema='guanheng.process-log-status.v1', records_written=self._written,
                        write_failures=self._errors, records_pending=self._queued, records_dropped=self._dropped,
                        max_series_bytes=self.max_bytes*(self.backups+1), queue_capacity=256)

    def drain(self, timeout=1.):
        """独立验真在既定预算内等候本代落盘；原进程start/close从不调用。"""
        return self._drained.wait(timeout)
