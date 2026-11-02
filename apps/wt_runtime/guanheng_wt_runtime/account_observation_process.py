"""独立WT持有原生账户单轮；发布原帧，不计算金融投影或策略归属。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from threading import Condition, Event
import time
from uuid import uuid4

from guanheng_market_client.runtime_status import replace_status

from .account_protocol import AccountScanConfig, FRAME_BYTES
from .account_scan_runtime import ManagedAccountScan
from .managed_local_process import _duration, _inspect, _json, _path, _read, _require, _sha
from .thread_owner import ThreadOwner

_NATIVE_FILES = ('GuanhengAccountScan.exe', 'traders/TraderQMTReadOnly.dll')
PUBLICATION_BYTES = FRAME_BYTES + 65536


def _utc():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')


@dataclass(frozen=True)
class AccountObservationConfig:
    """descriptor只选择原生材料、刷新和预算；凭据沿原Scan环境变量。"""
    installation: Path  # 固定账户组件安装绝对目录；来自部署描述，原生映像由本owner验证，必填。
    scan: AccountScanConfig  # 原四查询配置值对象；绑定账户/环境、来源和总截止，不在此复制凭据或账户金融事实。
    control_root: Path  # E盘控制根绝对路径；由账户owner租约保护，保存分代观察及current引用，必填。
    refresh_seconds: float  # 两轮扫描之间的等待秒数，范围(0,3600]；来自部署描述，不代表来源有效期。
    startup_seconds: float  # 本组件启动共享预算，单位秒、范围(0,60]；来自部署描述，必填。
    stop_seconds: float  # 本组件关闭预算，单位秒、上限120；至少覆盖Scan总预算加2秒，来源为部署描述。
    native_sha256: tuple[tuple[str, str], ...]  # 安装清单的(相对文件名,SHA256)不可变对；逐一核固定Scan/Trader字节，必填。

    @classmethod
    def from_path(cls, path, expected_sha256):
        raw = _read(_path(path, e_drive=True), 65536)
        _require(hashlib.sha256(raw).hexdigest() == _sha(expected_sha256))
        value = _json(raw)
        _require(set(value) == {'schema', 'installation', 'configuration', 'configuration_sha256',
                 'control_root', 'refresh_seconds', 'startup_seconds', 'stop_seconds'}
                 and value['schema'] == 'guanheng.account-observation-deployment.v1')
        installation = _path(value['installation'], e_drive=True)
        root = _path(value['control_root'], e_drive=True)
        _inspect(installation, directory=True)
        _inspect(root, directory=True)
        configuration = _path(value['configuration'], e_drive=True)
        _inspect(configuration)
        scan = AccountScanConfig.from_paths(str(installation / _NATIVE_FILES[0]), str(configuration))
        _require(scan.schema_version == 2 and scan.configuration_sha256 == _sha(value['configuration_sha256'])
                 and Path(scan.configuration['installation_root']) == installation
                 and Path(scan.configuration['library']['path']) == installation / _NATIVE_FILES[1])
        manifest = _json(_read(installation / 'account-observation-installation.json', 65536))
        _require(set(manifest) == {'schema', 'files'}
                 and manifest['schema'] == 'guanheng.account-observation-install.v1'
                 and type(manifest['files']) is dict and set(manifest['files']) == set(_NATIVE_FILES))
        digests = tuple((name, _sha(manifest['files'][name])) for name in _NATIVE_FILES)
        _require(manifest['files'][_NATIVE_FILES[1]] == scan.configuration['library']['sha256'])
        refresh = _duration(value['refresh_seconds'], 3600)
        startup = _duration(value['startup_seconds'], 60)
        stop = _duration(value['stop_seconds'], 120)
        _require(stop >= scan.total_seconds + 2)
        return cls(installation, scan, root, refresh, startup, stop, digests)


class AccountObservationProcess:
    """单线程顺序运行原Scan；首个停止截止及未回收资源始终归同一owner。

    start/close由原Runtime串行调用，request_close可跨线程。初次ready只授发布
    入口就绪；四查询成功、来源新鲜度和金融资格分别由原帧及消费者表达。
    """
    def __init__(self, config, *, scanner=None, clock=time.monotonic):
        self.config = config
        self._clock = clock
        self._scanner = scanner or ManagedAccountScan(clock=clock)
        self._condition = Condition()
        self._stop, self._round_stop, self._ready = Event(), Event(), Event()
        self._thread = self._lease = None
        self._attempted = self._closed = False
        self._stop_deadline = None
        self._state, self._error = 'new', None
        self._control_id = str(uuid4())
        self._directory = config.control_root / self._control_id
        self._revision, self._success, self._attempt = 0, None, None
        self._observation_state = 'waiting'

    @property
    def startup_seconds(self):
        return self.config.startup_seconds

    @property
    def shutdown_seconds(self):
        return self.config.stop_seconds

    def status(self):
        with self._condition:
            reference = None
            if self._ready.is_set() and self._state != 'new':
                reference = dict(schema='guanheng.account-observation-reference.v1',
                    control_id=self._control_id, config_sha256=self.config.scan.configuration_sha256,
                    pid=os.getpid(), path=str(self._directory / 'observation.json'),
                    ready_path=str(self._directory / 'ready.json'))
            return dict(schema='guanheng.account-observation-process.v1', state=self._state,
                ready=self._state == 'ready' and not self._stop.is_set(),
                pending=bool(self._thread and self._thread.pending) or self._scanner.pending,
                forced=self._round_stop.is_set(), error_code=self._error, pid=os.getpid(),
                observation_state=self._observation_state, account_observation=reference)

    def _publish(self, state, error_code=None):
        self._revision += 1
        scan = self.config.scan
        binding = {name: getattr(scan, name) for name in ('account', 'environment', 'max_rows',
            'ipc_schema', 'inspection_version', 'source', 'read_profile_version')}
        value = dict(schema='guanheng.account-observation.v1', control_id=self._control_id,
            config_sha256=scan.configuration_sha256, pid=os.getpid(), revision=self._revision,
            updated_at=_utc(), state=state, error_code=error_code, binding=binding,
            last_success_at=None, scan_id=None, observation=None, completion=None, close=None,
            attempt=self._attempt)
        if self._success:
            value.update(self._success)
        raw = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode('utf8')
        _require(len(raw) <= PUBLICATION_BYTES)
        # 唯一写者始终另写完整文件再原子换名；消费者可继续持有完整旧句柄。
        temporary = self._directory / ('.observation.' + str(uuid4()))
        with temporary.open('xb') as stream:
            stream.write(raw)
            stream.flush()
        replace_status(temporary, self._directory / 'observation.json')
        # 固定定位只发布当前owner引用；金融正文和各批原时间仍归原observation文件。
        reference = dict(
            schema='guanheng.account-observation-reference.v1',  # 固定定位协议版本；仅引用原观察正文。
            control_id=self._control_id,  # 本代owner的UUID文本；由启动入口分配，必填，与分代目录同名。
            config_sha256=scan.configuration_sha256,  # 原Scan配置SHA256；核同一账户来源，必填，不代表观测时点。
            pid=os.getpid(),  # 本代发布owner的Windows进程ID；必填正整数，不能单独证明当前存活。
            path=str(self._directory/'observation.json'),  # 本代原始观察帧绝对路径；正文/原时间归账户owner，消费者只读。
            ready_path=str(self._directory/'ready.json'))  # 同代ready收据绝对路径；由同owner拥有，必填，不授金融新鲜度。
        pointer = self.config.control_root / ('.current.'+str(uuid4()))
        with pointer.open('xb') as stream:
            stream.write(json.dumps(reference, separators=(',', ':')).encode('utf8')); stream.flush()
        replace_status(pointer, self.config.control_root/'current.json')
        with self._condition:
            self._observation_state = state

    def _verify_native(self, deadline):
        for name, digest in self.config.native_sha256:
            _require(self._clock() < deadline)
            raw = _read(self.config.installation / name, 64 * 1024 * 1024)
            _require(hashlib.sha256(raw).hexdigest() == digest and self._clock() < deadline)

    def _run(self):
        try:
            while not self._stop.is_set():
                deadline = self._clock() + self.config.scan.total_seconds
                self._publish('refreshing')
                self._verify_native(deadline)
                result = self._scanner.run(self.config.scan, str(uuid4()), deadline, self._round_stop)
                self._attempt = dict(scan_id=result.scan_id, completion=result.completion, close=result.close)
                if result.complete:
                    self._success = dict(scan_id=result.scan_id, observation=result.observation,
                        completion=result.completion, close=result.close, last_success_at=_utc())
                self._publish('ready' if result.complete else 'degraded',
                              None if result.complete else result.close['error_code'])
                # 原轮资源未知时保留同owner并退出，不启动第二轮。
                if self._scanner.pending:
                    raise RuntimeError('account_round_reclaim_pending')
                self._stop.wait(self.config.refresh_seconds)
            self._publish('stopped')
        except BaseException:
            with self._condition:
                self._state, self._error = 'faulted', 'observation_runtime'
            self.request_close()
            try:
                self._publish('degraded', 'observation_runtime')
            except BaseException:
                pass

    def start(self, deadline):
        from .__main__ import _InstanceLease
        with self._condition:
            _require(not self._attempted)
            self._attempted = True
        try:
            _require(self._clock() < deadline and not self._stop.is_set())
            _inspect(self.config.control_root, directory=True)
            # 使用原WT OS租约实现；同一输出根只授一个观察owner。
            self._lease = _InstanceLease(self.config.control_root, '00000000-0000-0000-0000-000000000001')
            self._lease.__enter__()
            self._directory.mkdir()
            _inspect(self._directory, directory=True)
            self._verify_native(deadline)
            self._publish('waiting')
            ready = dict(schema='guanheng.account-observation.ready.v1', control_id=self._control_id,
                config_sha256=self.config.scan.configuration_sha256, pid=os.getpid())
            (self._directory / 'ready.json').write_text(json.dumps(ready), encoding='utf8')
            _require(self._clock() < deadline and not self._stop.is_set())
            with self._condition:
                self._state = 'ready'
                self._ready.set()
                self._thread = ThreadOwner(target=self._run, daemon=True, name='wt-account-observation')
                self._thread.start()
            return True
        except BaseException:
            with self._condition:
                self._state, self._error = 'faulted', 'observation_startup'
            self.request_close()
            return False

    def request_close(self):
        with self._condition:
            if self._stop_deadline is None:
                self._stop_deadline = self._clock() + self.shutdown_seconds
            self._stop.set()
            if self._state not in ('faulted', 'closed'):
                self._state = 'stopping'

    def close(self, seconds):
        _require(type(seconds) in (int, float) and 0 <= seconds <= 120)
        self.request_close()
        with self._condition:
            # 第一次较短调用的停止期限属于owner；后续close只能续核原资源。
            self._stop_deadline = min(self._stop_deadline, self._clock() + seconds)
            deadline = self._stop_deadline
        if self._thread and not self._thread.join_until(deadline, clock=self._clock):
            self._round_stop.set()
            return False
        if not self._scanner.reap(deadline):
            return False
        if self._lease and self._lease.stream is not None:
            self._lease.__exit__()
        with self._condition:
            self._closed = True
            if self._state != 'faulted':
                self._state = 'closed'
        return True


def write_installation_manifest(installation):
    """显式普通安装后记录两个原生制品；此函数不启动来源或授运行资格。"""
    root = _path(str(installation), e_drive=True)
    files = {name: hashlib.sha256(_read(root / name, 64 * 1024 * 1024)).hexdigest() for name in _NATIVE_FILES}
    value = dict(schema='guanheng.account-observation-install.v1', files=files)
    with (root / 'account-observation-installation.json').open('x', encoding='utf8') as stream:
        json.dump(value, stream, sort_keys=True)
    return value


def create_process(descriptor_path, expected_sha256):
    return AccountObservationProcess(AccountObservationConfig.from_path(descriptor_path, expected_sha256))
