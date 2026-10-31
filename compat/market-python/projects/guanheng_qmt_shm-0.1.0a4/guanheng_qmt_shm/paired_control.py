"""QMT外的正式pair运行/私密停止控制；不引入HTTP管理权限或终端文件读取。"""
from __future__ import annotations

import math
import os
from pathlib import Path
import re
import stat
from threading import Event, Lock, Thread, current_thread
import time
from uuid import UUID, uuid4

from guanheng_qmt_shm_agent.protocol import canonical, decode
from .pair import build_paired_runtime
from .private_files import create_private_directory, write_private_new
from .server import create_server

MAX_CONTROL_BYTES = 4096
POLL_SECONDS = .02
_PENDING = set()
_PENDING_LOCK = Lock()


class PairedControlError(RuntimeError):
    """只公开固定分类；未知owner保留在本模块，不将原异常正文放到调用链。"""
    def __init__(self, error_code, result):
        self.error_code, self.result = error_code, dict(result)
        super().__init__(error_code)


def _require(value):
    if not value:
        raise ValueError('paired control contract')


def _file_identity(info):
    return info.st_dev, info.st_ino


def _ordinary(info, *, directory=False, bounded=True):
    _require(not getattr(info, 'st_file_attributes', 0) & 0x400)
    _require(stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode))
    if not directory:
        _require(info.st_nlink == 1)
        if bounded:
            _require(0 < info.st_size <= MAX_CONTROL_BYTES)


class _Owner:
    def __init__(self, runtime, keys, identity, control_id, schemas=None):
        self.schemas = dict(ready='qmt.host-ready.v1', stop='qmt.host-stop.v1', closed='qmt.host-closed.v1') if schemas is None else dict(schemas)
        self.atomic_publication = schemas is not None
        self.runtime, self.keys, self._provided_identity = runtime, keys, identity
        self.identity = {'pair_manifest_sha256': None, 'pair_config_sha256': None}
        self.control_id, self.pid = control_id, os.getpid()
        self.directory = self.directory_identity = self.server = self.monitor = None
        self.done, self.entered = Event(), Event()
        self.lock = Lock()
        self.monitor_attempted = self.monitor_started = False
        self.monitor_joined = True
        self.ready_written = self.stop_seen = self.server_closed = False
        self.first = None
        self.deadline = None
        self.startup_deadline = time.monotonic() + runtime.budget.connect_seconds + runtime.budget.io_seconds + 1

    def fail(self, code):
        with self.lock:
            if self.first is None:
                self.first = code

    def validate_identity(self):
        identity = self._provided_identity
        _require(type(identity) is dict and set(identity) == {
            'pair_manifest_sha256', 'pair_config_sha256'})
        _require(all(type(value) is str and re.fullmatch('[0-9a-f]{64}', value)
                     for value in identity.values()))
        self.identity = dict(identity)
        _require(type(self.runtime.listen_host) is str and 0 < len(self.runtime.listen_host) <= 255)
        _require(type(self.runtime.listen_port) is int and 1024 <= self.runtime.listen_port <= 65535)

    def emit(self, name, value):
        raw = canonical(value)
        _require(0 < len(raw) <= MAX_CONTROL_BYTES)
        if self.atomic_publication:
            # 新产品父端严格核文件身份；完整关闭临时句柄后才发布固定收据名。
            temporary = self.directory / (name + '.' + uuid4().hex + '.tmp')
            write_private_new(temporary, raw)
            os.rename(temporary, self.directory / name)
        else:
            write_private_new(self.directory / name, raw)

    def read_stop(self):
        # 只访问本次新目录与固定stop.json；不遍历父目录或解释任意文件路径。
        info = self.directory.lstat()
        _ordinary(info, directory=True)
        _require(_file_identity(info) == self.directory_identity)
        path = self.directory / 'stop.json'
        try:
            before = path.lstat()
        except FileNotFoundError:
            return None
        # 独占CREATE_NEW写者可能暂时暴露0B；先试打开，32/33等待提交，
        # 获得可读句柄后才按同一opened快照核正文容量。
        _ordinary(before, bounded=False)
        try:
            stream = path.open('rb')
        except PermissionError as error:
            if getattr(error, 'winerror', None) in (32, 33):
                return None  # 父仍持独占写句柄；等待完整提交，不采用半正文。
            raise
        with stream:
            opened = os.fstat(stream.fileno())
            _ordinary(opened)
            _require(_file_identity(opened) == _file_identity(before))
            raw = stream.read(MAX_CONTROL_BYTES + 1)
            after_read = os.fstat(stream.fileno())
        after = path.lstat()
        _ordinary(after)
        _require(len(raw) == opened.st_size <= MAX_CONTROL_BYTES
                 and _file_identity(after) == _file_identity(opened)
                 and _file_identity(after_read) == _file_identity(opened)
                 and after.st_size == after_read.st_size == opened.st_size
                 and after.st_mtime_ns == after_read.st_mtime_ns == opened.st_mtime_ns)
        value = decode(raw)
        _require(type(value) is dict and set(value) == {'schema', 'control_id', 'deadline'})
        _require(value['schema'] == self.schemas['stop'] and value['control_id'] == self.control_id)
        deadline = value['deadline']
        _require(type(deadline) in (int, float) and math.isfinite(deadline))
        return deadline

    def stop(self, deadline=None):
        # 两次请求共用runtime的最早D；不把轮询间隔加到外部原截止。
        try:
            actual = self.runtime.begin_shutdown(deadline)
            with self.lock:
                self.deadline = min(actual, self.deadline) if self.deadline is not None else actual
            if self.server is not None:
                self.server.request_close()
            else:
                self.runtime.request_close()
        except BaseException:
            self.fail('stop_failed')
            if self.server is not None:
                self.server.should_exit = True

    def monitor_run(self):
        self.entered.set()
        try:
            while not self.done.is_set():
                try:
                    deadline = self.read_stop()
                except BaseException:
                    self.fail('invalid_stop')
                    self.stop()
                    return
                if deadline is not None:
                    self.stop_seen = True
                    self.stop(deadline)
                    return
                if self.runtime.shutdown_started:
                    return
                if getattr(self.runtime, 'failure', None) is not None:
                    self.fail('runtime_failed')
                    self.stop()
                    return
                if not self.ready_written:
                    if time.monotonic() >= self.startup_deadline:
                        self.fail('startup_timeout')
                        self.stop(self.startup_deadline)
                        return
                    if self.server.started:
                        # 启动轮询与ready之间再读stop，优先受理已提交停止；
                        # 同一monitor受理后绝不发布新ready。
                        try:
                            deadline = self.read_stop()
                        except BaseException:
                            self.fail('invalid_stop')
                            self.stop()
                            return
                        if deadline is not None:
                            self.stop_seen = True
                            self.stop(deadline)
                            return
                        if self.done.is_set() or self.runtime.shutdown_started:
                            return
                        if time.monotonic() >= self.startup_deadline:
                            self.fail('startup_timeout')
                            self.stop(self.startup_deadline)
                            return
                        self.emit('ready.json', dict(schema=self.schemas['ready'], control_id=self.control_id,
                            pid=self.pid, **self.identity, listen_host=self.runtime.listen_host,
                            listen_port=self.runtime.listen_port))
                        self.ready_written = True
                        # 文件写入晚返回也保留原超时事实；父仍须核
                        # closed/实际退出及原D，不能仅凭ready文件授成功。
                        if time.monotonic() >= self.startup_deadline:
                            self.fail('startup_timeout')
                            self.stop(self.startup_deadline)
                            return
                self.done.wait(POLL_SECONDS)
        except BaseException:
            self.fail('monitor_failed')
            self.stop()

    def join_monitor(self, deadline):
        if not self.monitor_attempted:
            self.monitor_joined = True
            return
        self.monitor_joined = False
        if self.monitor is current_thread():
            return
        if not self.monitor_started and not self.entered.wait(max(0, deadline - time.monotonic())):
            return
        try:
            self.monitor.join(max(0, deadline - time.monotonic()))
            self.monitor_joined = not self.monitor.is_alive()
        except BaseException:
            self.monitor_joined = False

    def _current_deadline(self, original):
        # monitor可能已进入read_stop；收束前后只取更早值，不重开预算。
        with self.lock:
            return min(original, self.deadline) if self.deadline is not None else original

    def finish(self):
        self.done.set()
        self.stop()
        deadline = self.deadline
        if deadline is None:
            # begin_shutdown自身失败只给一次有限清理窗口；不授其已正常启动/关闭。
            fallback = time.monotonic() + self.runtime.budget.io_seconds + 1
            with self.lock:
                if self.deadline is None:
                    self.deadline = fallback
                deadline = self.deadline
        try:
            if self.server is not None:
                self.server.close()
            else:
                self.runtime.close(deadline)
            self.server_closed = True
        except BaseException:
            self.fail('close_failed')
        deadline = self._current_deadline(deadline)
        self.join_monitor(deadline)
        deadline = self._current_deadline(deadline)
        if not self.monitor_joined:
            self.fail('monitor_join_unconfirmed')
        try:
            runtime_closed = (self.runtime.closed_complete is True
                              and self.runtime.io_resources_closed is True)
        except BaseException:
            runtime_closed = False
            self.fail('close_unconfirmed')
        deadline = self._current_deadline(deadline)
        complete = runtime_closed and self.monitor_joined and self.server_closed and time.monotonic() < deadline
        if not complete:
            self.fail('close_unconfirmed')
        status = 'incomplete' if not complete else 'failed' if self.first is not None else 'stopped'
        result = dict(schema=self.schemas['closed'], control_id=self.control_id, pid=self.pid,
            **self.identity, status=status, runtime_closed=runtime_closed,
            monitor_joined=self.monitor_joined, error_code=self.first)
        deadline = self._current_deadline(deadline)
        if time.monotonic() >= deadline:
            complete = False
            self.fail('receipt_deadline')
            result.update(status='incomplete', error_code=self.first)
        if self.directory is not None:
            try:
                self.emit('closed.json', result)
            except BaseException:
                self.fail('closed_receipt_failed')
                result.update(status='failed' if complete else 'incomplete', error_code=self.first)
        deadline = self._current_deadline(deadline)
        if time.monotonic() >= deadline:
            complete = False
            self.fail('receipt_deadline')
            result.update(status='incomplete', error_code=self.first)
        if complete:
            with _PENDING_LOCK:
                _PENDING.discard(self)
        return result


def serve_paired(directory, *, installed_agent, control_directory=None, control_id=None):
    """验证并运行正式v3只读pair；控制目录由Host新建，原始凭证不进回执。

    无控制模式不建monitor/控制文件。受控模式父只给新私有E路径和canonical UUID；
    ready只证明本Host的HTTP已绑定，金融/策略来源资格仍由原binding/query判断。
    本调用在主线程阻塞运行至服务退出；创建和停止各沿原有限预算。
    成功返回status/runtime_closed/monitor_joined/error_code安全摘要；失败抛
    PairedControlError并携带同类摘要，释放未知的owner由模块持续保留。
    """
    return _serve_factory(lambda: build_paired_runtime(directory, installed_agent=installed_agent),
        control_directory=control_directory, control_id=control_id)


def _serve_factory(factory, *, control_directory=None, control_id=None, schemas=None):
    """同一Server/监控/资源所有权；新产品只选择严格工厂及固定控制schema。"""
    controlled = control_directory is not None or control_id is not None
    if controlled:
        try:
            _require(control_directory is not None and type(control_id) is str and str(UUID(control_id)) == control_id)
        except (ValueError, TypeError, AttributeError):
            raise PairedControlError('invalid_control', {'status': 'failed', 'error_code': 'invalid_control'}) from None
    try:
        runtime, keys, identity = factory()
    except BaseException:
        raise PairedControlError('pair_admission_failed',
            {'status': 'failed', 'error_code': 'pair_admission_failed'}) from None
    owner = (_Owner(runtime, keys, identity, control_id) if schemas is None
        else _Owner(runtime, keys, identity, control_id, schemas=schemas))
    with _PENDING_LOCK:
        _PENDING.add(owner)
    try:
        owner.validate_identity()
        if controlled:
            owner.directory = create_private_directory(Path(control_directory))
            info = owner.directory.lstat()
            _ordinary(info, directory=True)
            owner.directory_identity = _file_identity(info)
        owner.server = create_server(runtime, http_keys=keys)
        if controlled:
            try:
                owner.monitor = Thread(target=owner.monitor_run, name='qmt-paired-control', daemon=True)
                owner.monitor_attempted, owner.monitor_joined = True, False
                owner.monitor.start()
                owner.monitor_started = True
            except BaseException:
                owner.fail('monitor_start_failed')
                raise
        if not runtime.shutdown_started:
            owner.server.run()
        if not owner.server.started and not owner.stop_seen:
            owner.fail('startup_failed')
        if (controlled and not owner.ready_written and not owner.stop_seen
                and time.monotonic() >= owner.startup_deadline):
            owner.fail('startup_timeout')
    except BaseException:
        owner.fail('run_failed')
    finally:
        result = owner.finish()
    # 调用者/CLI只拿固定安全摘要；不把私密控制回执整体回显到stdout。
    summary = {key: result[key] for key in ('status', 'runtime_closed', 'monitor_joined', 'error_code')}
    if result['status'] != 'stopped':
        raise PairedControlError(result['error_code'], summary) from None
    return summary
