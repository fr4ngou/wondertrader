"""独立观衡 Web 本机维护：隐藏启动、查询、正常停止和重启。"""
import argparse
import asyncio
import contextlib
import ctypes
from ctypes import wintypes
import hashlib
import json
import logging
from logging.handlers import RotatingFileHandler
import math
import msvcrt
import os
from pathlib import Path
import subprocess
import sys
import time
from uuid import UUID, uuid4


def require(value, code):
    if not value:
        raise RuntimeError(code)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path, maximum=65536):
    with Path(path).open('rb') as stream:
        raw = stream.read(maximum + 1)
    require(len(raw) <= maximum, 'control_capacity')
    value = json.loads(raw)
    require(type(value) is dict, 'control_object')
    return value


def write(path, value):
    temporary = path.with_name(path.name + '.' + str(uuid4()) + '.tmp')
    with temporary.open('xb') as stream:
        stream.write(json.dumps(value, ensure_ascii=True, sort_keys=True).encode())
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


class _WebLogHandler(RotatingFileHandler):
    """沿标准库轮转，按UTF-8实际字节准入；写失败交回本Web日志owner。"""
    def __init__(self, path, maximum, backups, failed):
        self.failed = failed  # 仅更新本日志的有限故障计数，不递归写stderr。
        super().__init__(path, maxBytes=maximum, backupCount=backups,
                         encoding='utf-8', errors='backslashreplace', delay=True)
        self.terminator = ''  # stdout/stderr原有换行保持，不为每次write额外插行。
        self.setFormatter(logging.Formatter('%(message)s'))

    def _open(self):
        # 禁止Windows换行转换，使容量核算与实际文件字节一致。
        return open(self.baseFilename, self.mode, encoding=self.encoding,
                    errors=self.errors, newline='')

    def shouldRollover(self, record):
        if self.stream is None:
            self.stream = self._open()
        self.stream.seek(0, os.SEEK_END)
        size = len(self.format(record).encode('utf-8', 'backslashreplace'))
        return self.stream.tell() + size > self.maxBytes

    def handleError(self, record):
        self.failed(sys.exc_info()[1])  # logging默认错误处理会回写已重定向stderr。


class WebLog:
    """本运行代的两条文本流共用有界磁盘系列，无队列、行缓冲或新线程。

    默认web.log及三个备份各4MiB。每次write切成有限片段，大段无换行
    和多字节字符同样守总预算。故障后本代停止日志写入并计数丢弃字符，
    Web继续自己的生命周期；原控制回执与WT均不受日志结果控制。
    """
    encoding = 'utf-8'  # 两条流统一使用UTF-8，原日志保持文本读取。
    errors = 'backslashreplace'  # 非法代理字符以有限ASCII转义留存。

    def __init__(self, path, *, maximum=4 * 1024 * 1024, backups=3):
        require(type(maximum) is int and maximum >= 64 and type(backups) is int and backups >= 1,
                'web_log_budget')
        self.path = Path(path)  # 原私有运行代web.log入口，仅管理该文件及数字备份。
        self.maximum, self.backups = maximum, backups  # 单份字节预算、备份份数；总量为maximum*(backups+1)。
        self.written_bytes = 0  # 本次owner实际成功追加的UTF-8字节数，不代表历史保留量。
        self.dropped_characters = 0  # 写失败后未持久化的Python字符数，无原文内存积累。
        self.write_failures = 0  # 文件打开、轮转、追加或flush首次失败次数。
        self.error_type = None  # 固定异常类别，不保存路径、异常正文或凭据。
        self.closed = False  # 本owner关闭后禁止新write，stdout/stderr由外层context恢复。
        self.handler = _WebLogHandler(self.path, maximum, backups, self._failed)  # 标准库锁覆盖轮转和追加。
        try:
            # 升级前的大文件保留最新UTF-8尾部；旧正文仍使用原文件名直接可读。
            for current in [self.path, *[self.path.with_name(self.path.name + '.' + str(i))
                                       for i in range(1, backups + 1)]]:
                if current.exists() and current.stat().st_size > maximum:
                    with current.open('r+b') as stream:
                        stream.seek(-maximum, os.SEEK_END)
                        tail = stream.read(maximum).decode('utf-8', 'ignore').encode('utf-8')
                        stream.seek(0)
                        stream.write(tail)
                        stream.truncate()
        except OSError as error:
            self._failed(error)
            self._save_status()

    def _failed(self, error):
        self.write_failures += 1
        self.error_type = ('OSError' if isinstance(error, OSError) else 'LogWriteError')

    def isatty(self):
        return False

    def write(self, value):
        if self.closed:
            raise ValueError('write to closed Web log')
        if not isinstance(value, str):
            raise TypeError('Web log expects text')
        # 非法Unicode代理字符的backslashreplace至多六字节，不突破单份预算。
        chunk = min(16384, self.maximum // 6)
        previous_error = self.error_type
        self.handler.acquire()
        try:
            for start in range(0, len(value), chunk):
                piece = value[start:start + chunk]
                if self.error_type is None:
                    self.handler.emit(logging.LogRecord('observer.web', logging.INFO, '', 0, piece, (), None))
                    if self.error_type is None:
                        self.written_bytes += len(piece.encode('utf-8', 'backslashreplace'))
                        continue
                self.dropped_characters += len(value) - start
                break
        finally:
            self.handler.release()
        if previous_error is None and self.error_type is not None:
            self._save_status()  # 首次失败的整次write已计入丢弃数；后续输出不反复访问故障磁盘。
        return len(value)

    def flush(self):
        if not self.closed and self.error_type is None:
            try:
                self.handler.flush()
            except OSError as error:
                self._failed(error)
                self._save_status()

    def close(self):
        if self.closed:
            return
        try:
            self.handler.close()
        except OSError as error:
            self._failed(error)
        self.closed = True
        self._save_status()

    def _save_status(self):
        # 状态为常量大小；磁盘整体不可写时允许缺失，原ready/closed不伪装日志成功。
        status = self.path.with_name('web-log-status.json')
        temporary = status.with_suffix('.tmp')
        try:
            temporary.write_text(json.dumps(dict(
                schema='guanheng.web-log-status.v1',  # 本Web日志owner的私有状态格式。
                closed=self.closed,  # 文件句柄生命周期已结束；与App的closed证明分别表达。
                state='degraded' if self.error_type else 'ok',  # 该日志owner是否观察到写故障。
                maximum_file_bytes=self.maximum,  # 每份日志的UTF-8字节上限。
                maximum_total_bytes=self.maximum * (self.backups + 1),  # 本代完整轮转系列的字节上限。
                written_bytes=self.written_bytes,  # 本次确认追加量，历史已轮转字节仍计入。
                dropped_characters=self.dropped_characters,  # 故障后丢弃字符累计，未保存正文。
                write_failures=self.write_failures,  # 本次文件打开、追加、轮转、flush及close故障次数。
                error_type=self.error_type)), encoding='utf-8')  # 固定OSError/LogWriteError；None表示未观察到。
            os.replace(temporary, status)
        except OSError:
            with contextlib.suppress(OSError):
                temporary.unlink(missing_ok=True)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class Process:
    """保留原进程对象，PID复用后也不会把另一实例当作本次退出。"""
    def __init__(self, pid):
        self.pid, self.handle = pid, None
        self.api = ctypes.WinDLL('kernel32', use_last_error=True)
        self.api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.api.OpenProcess.restype = wintypes.HANDLE
        self.api.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
        self.api.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        self.api.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self.api.WaitForSingleObject.restype = wintypes.DWORD
        self.api.CloseHandle.argtypes = [wintypes.HANDLE]

    def __enter__(self):
        self.handle = self.api.OpenProcess(0x1000 | 0x100000, False, self.pid)
        if not self.handle:
            require(ctypes.get_last_error() == 87, 'process_identity_unavailable')
        return self

    def snapshot(self):
        if not self.handle:
            return None
        times, code = [wintypes.FILETIME() for _ in range(4)], wintypes.DWORD()
        require(self.api.GetProcessTimes(self.handle, *[ctypes.byref(x) for x in times]), 'process_times')
        require(self.api.GetExitCodeProcess(self.handle, ctypes.byref(code)), 'process_exit')
        return dict(creation_time=(times[0].dwHighDateTime << 32) | times[0].dwLowDateTime,
                    exit_code=code.value)

    def __exit__(self, *_):
        if self.handle:
            self.api.CloseHandle(self.handle)


def profile(path):
    value = read(path)
    expected = {'schema', 'pythonw', 'pythonw_sha256', 'app_version', 'static_directory',
                'control_root', 'host', 'port', 'environment_file', 'environment_sha256',
                'startup_seconds', 'stop_seconds'}
    require(set(value) == expected and value['schema'] == 'guanheng.observer-web.v1', 'profile_schema')
    for key in ('pythonw', 'static_directory', 'control_root', 'environment_file'):
        require(type(value[key]) is str and Path(value[key]).is_absolute(), 'absolute_profile_path')
    require(value['host'] in ('127.0.0.1', '::1') and type(value['port']) is int
            and 1 <= value['port'] <= 65535, 'listen_address')
    for key in ('startup_seconds', 'stop_seconds'):
        require(type(value[key]) in (int, float) and math.isfinite(value[key]) and value[key] > 0, 'finite_deadline')
    require(Path(value['control_root']).is_dir(), 'control_root_missing')
    return value


@contextlib.contextmanager
def exclusive(root):
    with (root / 'web.lock').open('a+b') as stream:
        if stream.tell() == 0:
            stream.write(b'0')
            stream.flush()
        stream.seek(0)
        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            yield
        finally:
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


def state_for(root, expected):
    path = root / 'instance.json'
    if not path.exists():
        return None
    state = read(path)
    require(state['profile_sha256'] == expected, 'instance_configuration_differs_stop_old_profile_first')
    require(str(UUID(state['control_id'])) == state['control_id'], 'instance_uuid')
    require(state['directory'] == str(root / state['control_id']), 'instance_directory')
    return state


def receipt(state, name):
    path = Path(state['directory']) / (name + '.json')
    if not path.exists():
        return None
    value = read(path)
    require(value['control_id'] == state['control_id'] and value['profile_sha256'] == state['profile_sha256']
            and value['pid'] == state.get('pid'), 'receipt_identity')
    return value


def adopt_body(root, state):
    """启动等待超时后仍可按原代的署名回执取得本体身份，避免重复启动。"""
    if 'pid' in state or 'launcher_pid' not in state:
        return state
    for name in ('ready', 'failure'):
        path = Path(state['directory']) / (name + '.json')
        if path.exists():
            body = read(path)
            require(body['control_id'] == state['control_id']
                    and body['profile_sha256'] == state['profile_sha256'], 'launch_receipt_identity')
            require(body['pid'] == state['launcher_pid'] or body['parent_pid'] == state['launcher_pid'],
                    'Web_launcher_ancestry')
            state = dict(state, pid=body['pid'], creation_time=body['creation_time'])
            write(root / 'instance.json', state)
            break
    return state


def observe(root, expected):
    state = state_for(root, expected)
    if state is None:
        return dict(outcome='stopped', instance=None, alive=False)
    state = adopt_body(root, state)
    if 'pid' not in state:
        return dict(outcome='unknown', instance=state, alive=None, reason='launch_identity_unresolved')
    with Process(state['pid']) as process:
        identity = process.snapshot()
    if identity is not None:
        require(identity['creation_time'] == state['creation_time'], 'process_identity_changed')
    alive = identity is not None and identity['exit_code'] == 259
    ready, closed, failed, exited = [receipt(state, name) for name in ('ready', 'closed', 'failure', 'exit')]
    good_close = bool(closed and closed['shutdown_complete'] and closed['reader_threads'] == 0
                      and closed['backtest_reader_threads'] == 0 and exited and exited['exit_code'] == 0
                      and exited['launcher_exit_code'] == 0)
    outcome = 'ready' if alive and ready and not failed else 'failed' if failed else 'closed' if not alive and good_close else 'unknown'
    return dict(outcome=outcome, instance=state, alive=alive, ready=ready, closed=closed, failure=failed, OS_exit=exited)


def launch(command, remaining):
    """Windows原生CIM只创建Web本体；不增加常驻父进程或依赖包。

    新进程不继承短命维护命令的Job，维护命令退出后页面持续运行。
    凭据在Web内部从外部配置加载，命令行及CIM返回仅含路径和PID。
    """
    quoted = subprocess.list2cmdline(command).replace("'", "''")
    script = ("$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue';"
              "$s=New-CimInstance -ClassName Win32_ProcessStartup -ClientOnly -Property @{ShowWindow=[uint16]0};"
              "$r=Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine='"
              + quoted + "';ProcessStartupInformation=$s};$r|Select-Object ReturnValue,ProcessId|ConvertTo-Json -Compress")
    import base64
    response = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-EncodedCommand',
                               base64.b64encode(script.encode('utf-16le')).decode()],
                              capture_output=True, timeout=min(30, remaining), creationflags=subprocess.CREATE_NO_WINDOW)
    require(response.returncode == 0, 'native_launch_unavailable')
    result = json.loads(response.stdout.decode('utf-8-sig'))
    require(result['ReturnValue'] == 0 and result['ProcessId'] > 0, 'native_launch_failed')
    return result['ProcessId']


def start(path, cfg, root, expected):
    before = observe(root, expected)
    if before['alive'] or before['outcome'] == 'unknown':
        return before
    require(digest(cfg['pythonw']) == cfg['pythonw_sha256'], 'python_identity')
    require(digest(cfg['environment_file']) == cfg['environment_sha256'], 'environment_identity')
    deadline = time.monotonic() + cfg['startup_seconds']
    identifier = str(uuid4())
    directory = root / identifier
    directory.mkdir()
    state = dict(schema='guanheng.observer-web-instance.v1', control_id=identifier,
                 profile_sha256=expected, directory=str(directory))
    write(root / 'instance.json', state)  # launch有未知时保留本代，不自动创建第二个Web。
    pid = launch([cfg['pythonw'], '-I', '-B', str(Path(__file__).resolve()), '_serve',
                  '--profile', str(path.resolve()), '--control-id', identifier, '--profile-sha256', expected],
                 max(.001, deadline - time.monotonic()))
    with Process(pid) as process:
        identity = process.snapshot()
    state.update(launcher_pid=pid, launcher_creation_time=None if identity is None else identity['creation_time'])
    write(root / 'instance.json', state)
    # Windows venv pythonw可有短启动器和真正解释器两个PID；ready/failure由Web本体署名。
    while time.monotonic() < deadline:
        state = adopt_body(root, state)
        if 'pid' not in state:
            time.sleep(.05)
            continue
        current = observe(root, expected)
        if current['outcome'] in ('ready', 'failed') or not current['alive']:
            return current if time.monotonic() < deadline else dict(current, outcome='unknown', reason='startup_deadline')
        time.sleep(.05)
    return dict(outcome='unknown', instance=state, alive=None, reason='startup_deadline')


def stop(cfg, root, expected):
    before = observe(root, expected)
    if before['instance'] is None or before['outcome'] == 'closed':
        return before
    state = before['instance']
    require('pid' in state, 'unknown_launch_identity')
    deadline = time.monotonic() + cfg['stop_seconds']
    # 同时持有启动器与解释器句柄；退出后 PID 消失仍能取得各自的实际退出码。
    with Process(state['pid']) as process, Process(state['launcher_pid']) as launcher:
        identity = process.snapshot()
        require(identity is not None and identity['creation_time'] == state['creation_time'], 'stop_process_identity')
        launched = launcher.snapshot()
        require(launched is not None and launched['creation_time'] == state['launcher_creation_time'],
                'stop_launcher_identity')
        if identity['exit_code'] == 259:
            path = Path(state['directory']) / 'stop.json'
            if not path.exists():
                write(path, dict(control_id=state['control_id'], profile_sha256=expected))
            while time.monotonic() < deadline:
                identity = process.snapshot()
                if identity['exit_code'] != 259:
                    break
                time.sleep(.05)
        if identity['exit_code'] == 259:
            return dict(before, outcome='unknown', reason='stop_deadline')
        while launched['exit_code'] == 259 and time.monotonic() < deadline:
            time.sleep(.05)
            launched = launcher.snapshot()
        if launched['exit_code'] == 259:
            return dict(before, outcome='unknown', reason='launcher_stop_deadline')
        write(Path(state['directory']) / 'exit.json', dict(control_id=state['control_id'],
              profile_sha256=expected, pid=state['pid'], exit_code=identity['exit_code'],
              launcher_exit_code=launched['exit_code'] if launched is not None else None))
    return observe(root, expected)


async def serve(path, cfg, expected, identifier):
    require(digest(path) == expected, 'launch_profile_changed')
    with Process(os.getpid()) as process:
        identity = process.snapshot()
    state = dict(control_id=identifier, profile_sha256=expected, pid=os.getpid(),
                 creation_time=identity['creation_time'], parent_pid=os.getppid())
    directory = Path(cfg['control_root']) / identifier
    import importlib.metadata
    require(importlib.metadata.version('guanheng-app') == cfg['app_version'], 'App_version')
    require(digest(cfg['environment_file']) == cfg['environment_sha256'], 'environment_identity')
    environment = read(cfg['environment_file'])
    require(all(type(k) is str and k.startswith('GUANHENG_') and type(v) is str
                and '\x00' not in v for k, v in environment.items()), 'reading_environment')
    for key in list(os.environ):
        if key.upper().startswith('GUANHENG_'):
            del os.environ[key]
    os.environ.update(environment)
    import uvicorn
    from guanheng_app.app import create_app
    from guanheng_app.settings import ConsoleSettings
    from guanheng_app.__main__ import HTTP_LOOP
    require((Path(cfg['static_directory']) / 'index.html').is_file(), 'SPA_not_installed')
    app = create_app(settings=ConsoleSettings.from_environment(), static_directory=cfg['static_directory'])
    server = uvicorn.Server(uvicorn.Config(app, host=cfg['host'], port=cfg['port'], access_log=False,
                                         log_level='warning', loop=HTTP_LOOP))
    task = asyncio.create_task(server.serve())
    try:
        while not server.started and not task.done():
            await asyncio.sleep(.05)
        require(server.started, 'Web_not_started')
        write(directory / 'ready.json', dict(state, app_version=cfg['app_version'], host=cfg['host'], port=cfg['port']))
        while not task.done():
            path = directory / 'stop.json'
            if path.exists():
                require(read(path) == dict(control_id=identifier, profile_sha256=expected), 'stop_identity')
                server.should_exit = True
            await asyncio.sleep(.05)
        await task
    finally:
        if not task.done():
            server.should_exit = True
            await task
    closed = dict(state, shutdown_complete=bool(app.state.shutdown_complete),
                  reader_threads=app.state.reader.live_threads,
                  backtest_reader_threads=app.state.backtest_reader.live_threads)
    write(directory / 'closed.json', closed)
    require(closed['shutdown_complete'] and closed['reader_threads'] == 0
            and closed['backtest_reader_threads'] == 0, 'App_shutdown_incomplete')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('start', 'status', 'stop', 'restart', '_serve'))
    parser.add_argument('--profile', type=Path, required=True)
    parser.add_argument('--control-id')
    parser.add_argument('--profile-sha256')
    args = parser.parse_args()
    try:
        cfg = profile(args.profile)
        root, expected = Path(cfg['control_root']), digest(args.profile)
        if args.action == '_serve':
            require(args.profile_sha256 == expected, 'profile_identity')
            require(str(UUID(args.control_id)) == args.control_id, 'control_uuid')
            with WebLog(root / args.control_id / 'web.log') as log:
                with contextlib.redirect_stderr(log), contextlib.redirect_stdout(log):
                    try:
                        with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
                            runner.run(serve(args.profile, cfg, expected, args.control_id))
                    except BaseException as error:
                        print('Web_runtime_failure: ' + type(error).__name__, file=sys.stderr)
                        with Process(os.getpid()) as process:
                            identity = process.snapshot()
                        write(root / args.control_id / 'failure.json', dict(control_id=args.control_id,
                              profile_sha256=expected, pid=os.getpid(), parent_pid=os.getppid(),
                              creation_time=identity['creation_time'], error_type=type(error).__name__,
                              code=str(error) if type(error) is RuntimeError else 'Web_runtime_failure'))
                        return 2
            return 0
        with exclusive(root):
            result = observe(root, expected) if args.action == 'status' else stop(cfg, root, expected) if args.action == 'stop' else start(args.profile, cfg, root, expected) if args.action == 'start' else None
            if args.action == 'restart':
                result = stop(cfg, root, expected)
                if result['outcome'] in ('closed', 'stopped'):
                    result = start(args.profile, cfg, root, expected)
        print(json.dumps(result, ensure_ascii=True))
        return 0 if result['outcome'] in ('ready', 'closed', 'stopped') or args.action == 'status' else 1
    except subprocess.TimeoutExpired:
        print(json.dumps(dict(outcome='unknown', code='launch_deadline',
                              reason='inspect_original_control_receipts_before_retry')))
        return 1
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as error:
        print(json.dumps(dict(outcome='failed', error_type=type(error).__name__,
                             code=str(error) if type(error) is RuntimeError else 'local_control_failure')))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
