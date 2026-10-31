"""默认disabled的HPR产品进程适配；父端只读安全身份，不导入Host。"""
from dataclasses import dataclass
import hashlib
from pathlib import Path
import threading
import time
from .managed_local_process import (ManagedLocalProcess, _require, _sha, _path, _inspect, _read, _json)
from .qmt_host_process import HostProcessConfig

_FIELDS = {'schema', 'pythonw', 'pythonw_sha256', 'pair_directory', 'pair_manifest_sha256',
    'installed_agent', 'control_root', 'startup_seconds', 'stop_seconds', 'max_output_bytes'}
_IDENTITY = {'schema', 'control_id', 'pid', 'pair_manifest_sha256', 'pair_config_sha256'}


@dataclass(frozen=True)
class HistoryPreparationProcessConfig(HostProcessConfig):
    """只含路径、SHA和预算；复用原部署值验证，空配置不启动。"""
    @classmethod
    def from_path(cls, path, expected_sha256=None):
        if path is None or path == '':
            _require(expected_sha256 in (None, ''))
            return None
        raw = _read(_path(path), 65536)
        _require(hashlib.sha256(raw).hexdigest() == _sha(expected_sha256))
        value = _json(raw)
        _require(set(value) == _FIELDS and value.pop('schema') == 'qmt.history-preparation-process.v1')
        return cls(**value)


class HistoryPreparationProcess(ManagedLocalProcess):
    """原隐藏Job和资源owner；ready只授监听，数据/来源资格由认证查询给出。"""
    _status_schema = 'qmt.history-preparation-process-status.v1'
    _stop_schema = 'qmt.history-preparation-stop.v1'
    _thread_name = 'history-preparation-process'

    def __init__(self, config=None, *, job_factory=None, thread_factory=threading.Thread, clock=time.monotonic):
        _require(config is None or type(config) is HistoryPreparationProcessConfig)
        super().__init__(config, job_factory=job_factory, thread_factory=thread_factory, clock=clock)
        self._pair_config_sha = None

    def _command(self):
        cfg = self.config
        return (cfg.pythonw, '-I', '-B', '-m', 'guanheng_qmt_shm.history_preparation_cli', 'run',
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
        _require(value.get('schema_version') == 'qmt.history-preparation-product-pair.v1'
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
            ('qmt.history-preparation-ready.v1' if ready else 'qmt.history-preparation-closed.v1')
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
