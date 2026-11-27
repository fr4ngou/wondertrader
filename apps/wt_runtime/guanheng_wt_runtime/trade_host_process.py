"""默认disabled的交易通信产品进程适配；父端只读安全身份，不导入Host。"""
from dataclasses import dataclass
import hashlib
from pathlib import Path
import threading
import time
from .managed_local_process import (ManagedLocalProcess, _require, _sha, _path, _inspect, _read, _json,
                                    runtime_control_path)
from .qmt_host_process import HostProcessConfig

_FIELDS = {'schema', 'pythonw', 'pythonw_sha256', 'pair_directory', 'pair_manifest_sha256',
    'installed_agent', 'control_root', 'startup_seconds', 'stop_seconds', 'max_output_bytes'}
_IDENTITY = {'schema', 'control_id', 'pid', 'pair_manifest_sha256', 'pair_config_sha256'}


def _analysis_identity(value, key, version, operations):
    """父端只核公开能力身份；源码及私有设置由原 Host 完整验证。"""
    analysis = value.get(key)
    _require(type(analysis) is dict and set(analysis) == {'profile', 'settings_sha256'})
    _sha(analysis['settings_sha256'])
    profile = analysis['profile']
    _require(type(profile) is dict and profile.get('read_profile_version') == version
        and profile.get('read_operations') == operations)


@dataclass(frozen=True)
class TradeHostProcessConfig(HostProcessConfig):
    """只含路径、SHA和预算；复用原部署值验证，空配置不启动。"""
    def _validate_control_root(self):
        runtime_control_path(self.control_root)

    @classmethod
    def from_path(cls, path, expected_sha256=None):
        if path is None or path == '':
            _require(expected_sha256 in (None, ''))
            return None
        raw = _read(_path(path), 65536)
        _require(hashlib.sha256(raw).hexdigest() == _sha(expected_sha256))
        value = _json(raw)
        _require(set(value) == _FIELDS and value.pop('schema') == 'qmt.trade-host-process.v1')
        return cls(**value)


def validate_standalone_trade_host(components, control_root):
    """独立只读入口只托管同卷 Host，由 Host 核实际配对权限。"""
    _require(tuple(name for name, _ in components) == ('trade_host',))
    role = components[0][1]
    drive = control_root.drive.casefold()
    _require(runtime_control_path(role.descriptor).drive.casefold() == drive)
    host = TradeHostProcessConfig.from_path(role.descriptor, role.sha256)
    _require(all(runtime_control_path(path).drive.casefold() == drive for path in
                 (host.pythonw, host.pair_directory, host.installed_agent, host.control_root)))


class TradeHostProcess(ManagedLocalProcess):
    """原隐藏Job和资源owner；ready只授监听，数据/来源资格由认证查询给出。"""
    _status_schema = 'qmt.trade-host-process-status.v1'
    _stop_schema = 'qmt.trade-host-stop.v1'
    _thread_name = 'trade-host-process'

    def __init__(self, config=None, *, job_factory=None, thread_factory=threading.Thread, clock=time.monotonic):
        _require(config is None or type(config) is TradeHostProcessConfig)
        super().__init__(config, job_factory=job_factory, thread_factory=thread_factory, clock=clock)
        self._pair_config_sha = None

    def _command(self):
        cfg = self.config
        return (cfg.pythonw, '-I', '-B', '-m', 'guanheng_qmt_shm.trade_cli', 'run',
            '--directory', cfg.pair_directory, '--installed-agent', cfg.installed_agent,
            '--control-directory', str(self._directory), '--control-id', self._control_id)

    def _validate_inputs(self, deadline):
        cfg = self.config
        for path in (cfg.pair_directory, cfg.installed_agent, cfg.control_root):
            _inspect(Path(path), directory=True)
        self._verify_file(Path(cfg.pythonw), cfg.pythonw_sha256, 67108864, deadline)
        raw = _read(Path(cfg.pair_directory)/'manifest.json', 2097152, clock=self._clock, deadline=deadline)
        _require(hashlib.sha256(raw).hexdigest() == cfg.pair_manifest_sha256)
        value = _json(raw)
        source_runtime = value.get('source_runtime')
        pair_schema = value.get('schema_version')
        # 证券资料连接只由显式v5声明；旧版本保持原连接形状。
        if 'security_reference_read' in value:
            _require(pair_schema == 'qmt.trade-product-pair.v5')
        if pair_schema in ('qmt.trade-product-pair.v2', 'qmt.trade-product-pair.v3',
                           'qmt.trade-product-pair.v4', 'qmt.trade-product-pair.v5'):
            _require(type(source_runtime) is dict and set(source_runtime) == {'schema_version', 'mode'}
                and source_runtime['schema_version'] == 'qmt.source-runtime.v1'
                and source_runtime['mode'] in ('thread', 'strategy_tick'))
            if pair_schema in ('qmt.trade-product-pair.v3', 'qmt.trade-product-pair.v4', 'qmt.trade-product-pair.v5'):
                _require(source_runtime['mode'] == 'strategy_tick')
                if pair_schema == 'qmt.trade-product-pair.v3' or 'analysis_read' in value:
                    _analysis_identity(value, 'analysis_read', 'qmt.read-profile.v7',
                        ['market.divid_factors', 'market.market_data'])
                if pair_schema == 'qmt.trade-product-pair.v4' or (
                        pair_schema == 'qmt.trade-product-pair.v5' and 'analysis_batch_read' in value):
                    # v4固定选用批量通道，v5按字段存在性选用；两者复用原owner和QMT策略线程。
                    _analysis_identity(value, 'analysis_batch_read', 'qmt.read-profile.v8', ['market.market_data'])
                if pair_schema == 'qmt.trade-product-pair.v5':
                    # v5只在原策略线程增加独立v9只读连接；v7/v8各按存在性核身份。
                    _analysis_identity(value, 'security_reference_read', 'qmt.read-profile.v9',
                        ['market.security_details', 'market.security_universe'])
        else:
            _require(value.get('schema_version') == 'qmt.trade-product-pair.v1' and 'source_runtime' not in value)
        _require(pair_schema in ('qmt.trade-product-pair.v1', 'qmt.trade-product-pair.v2',
                'qmt.trade-product-pair.v3', 'qmt.trade-product-pair.v4', 'qmt.trade-product-pair.v5')
            and value.get('qualified_in_qmt') is False and value.get('order_ready') is False
            and value.get('strategy_name') == 'GH_WT_MEMORY_VERIFY'
            and _path(value.get('agent_package')) == Path(cfg.installed_agent)
            and _path(value.get('host_python')) == Path(cfg.pythonw)
            and value.get('host_python_sha256') == cfg.pythonw_sha256)
        self._pair_config_sha = _sha(value['config_sha256'])
        _require(not self._directory.exists())
        self._check(deadline)

    def _receipt(self, name, deadline):
        _inspect(self._directory, directory=True)
        value = _json(_read(self._directory/name, 4096, clock=self._clock, deadline=deadline))
        ready = name == 'ready.json'
        fields = _IDENTITY | ({'listen_host', 'listen_port'} if ready else
            {'status', 'runtime_closed', 'monitor_joined', 'error_code'})
        _require(set(value) == fields and value['schema'] ==
            ('qmt.trade-host-ready.v1' if ready else 'qmt.trade-host-closed.v1')
            and value['control_id'] == self._control_id and type(value['pid']) is int and 0 < value['pid'] < 2**32
            and value['pair_manifest_sha256'] == self.config.pair_manifest_sha256
            and value['pair_config_sha256'] == self._pair_config_sha)
        if ready:
            _require(type(value['listen_host']) is str and 0 < len(value['listen_host']) <= 255
                and type(value['listen_port']) is int and 1024 <= value['listen_port'] <= 65535)
        else:
            _require(value['pid'] == self._host_pid and value['status'] == 'stopped'
                and value['runtime_closed'] is True and value['monitor_joined'] is True and value['error_code'] is None)
        return value


def create_process(descriptor_path, expected_sha256):
    """WT固定工厂接缝；构造只核部署身份，start才取得进程与Job。"""
    return TradeHostProcess(TradeHostProcessConfig.from_path(descriptor_path, expected_sha256))

