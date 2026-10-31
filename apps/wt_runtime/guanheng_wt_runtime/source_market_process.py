"""原生来源历史服务的部署与收据适配；进程监督复用原公共owner。"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import ipaddress
from pathlib import Path, PureWindowsPath
import threading
import time

from .managed_local_process import (ManagedLocalProcess, _require, _duration, _sha,
                                    _path, _inspect, _read, _json)

_FIELDS = {'schema', 'pythonw', 'pythonw_sha256', 'entry', 'entry_sha256',
           'configuration', 'configuration_sha256', 'control_root',
           'startup_seconds', 'stop_seconds', 'max_output_bytes'}
_IDENTITY = {'schema', 'control_id', 'pid', 'configuration_sha256'}
_READY = _IDENTITY | {'listen_host', 'listen_port'}
_CLOSED = _IDENTITY | {'status', 'server_closed', 'native_closed', 'error_code'}


def _listen(value):
    """仅验证父端所需监听身份；完整子配置仍由SMP服务唯一解释。"""
    _require(type(value) is dict and set(value) == {'host', 'port'})
    host, port = value['host'], value['port']
    _require(type(host) is str and len(host) <= 64
             and ipaddress.ip_address(host).is_loopback)
    _require(type(port) is int and 1 <= port <= 65535)
    return host, port


@dataclass(frozen=True)
class SourceMarketProcessConfig:
    """SMA固定部署身份；凭据留在子进程环境，构造不创建进程或读取数据。"""
    pythonw: str
    pythonw_sha256: str
    entry: str
    entry_sha256: str
    configuration: str
    configuration_sha256: str
    control_root: str
    startup_seconds: float
    stop_seconds: float
    max_output_bytes: int

    def __post_init__(self):
        _path(self.pythonw); _sha(self.pythonw_sha256)
        _require(PureWindowsPath(self.pythonw).name.lower() == 'pythonw.exe')
        _path(self.entry); _sha(self.entry_sha256)
        _path(self.configuration); _sha(self.configuration_sha256)
        _path(self.control_root, e_drive=True)
        _duration(self.startup_seconds, 120); _duration(self.stop_seconds, 60)
        _require(type(self.max_output_bytes) is int and 1024 <= self.max_output_bytes <= 1048576)

    @classmethod
    def from_path(cls, path, expected_sha256=None):
        """核64KiB以内父部署原字节；空配置关闭，坏输入抛ValueError/OSError。"""
        if path is None or path == '':
            _require(expected_sha256 in (None, ''))
            return None
        expected = _sha(expected_sha256)
        raw = _read(_path(path), 65536)
        _require(hashlib.sha256(raw).hexdigest() == expected)
        value = _json(raw)
        _require(set(value) == _FIELDS and value.pop('schema') == 'guanheng.source-market-process.v1')
        return cls(**value)


class SourceMarketProcess(ManagedLocalProcess):
    """单次历史查询进程；ready绑定监听与实例，数据资格由查询结果说明。"""
    _status_schema = 'guanheng.source-market-process-status.v1'
    _stop_schema = 'guanheng.source-market-stop.v1'
    _thread_name = 'source-market-process'

    def __init__(self, config=None, *, job_factory=None, thread_factory=threading.Thread, clock=time.monotonic):
        _require(config is None or type(config) is SourceMarketProcessConfig)
        super().__init__(config, job_factory=job_factory, thread_factory=thread_factory, clock=clock)
        self._expected_listen = None

    def _validate_inputs(self, deadline):
        cfg = self.config
        _inspect(Path(cfg.control_root), directory=True)
        self._verify_file(Path(cfg.pythonw), cfg.pythonw_sha256, 64 * 1024 * 1024, deadline)
        self._verify_file(Path(cfg.entry), cfg.entry_sha256, 4 * 1024 * 1024, deadline)
        raw = _read(Path(cfg.configuration), 65536, clock=self._clock, deadline=deadline)
        _require(hashlib.sha256(raw).hexdigest() == cfg.configuration_sha256)
        value = _json(raw)
        _require(value.get('schema') == 'guanheng.source-market-service.v1')
        self._expected_listen = _listen(value.get('listen'))
        _require(not self._directory.exists())
        self._check(deadline)

    def _command(self):
        cfg = self.config
        return (cfg.pythonw, '-I', '-B', cfg.entry, '--config', cfg.configuration,
                '--config-sha256', cfg.configuration_sha256,
                '--control-directory', str(self._directory), '--control-id', self._control_id)

    def _receipt(self, name, deadline):
        _inspect(self._directory, directory=True)
        value = _json(_read(self._directory / name, 4096, clock=self._clock, deadline=deadline))
        ready = name == 'ready.json'
        _require(set(value) == (_READY if ready else _CLOSED)
                 and value['schema'] == ('guanheng.source-market-ready.v1' if ready else 'guanheng.source-market-closed.v1')
                 and value['control_id'] == self._control_id
                 and value['configuration_sha256'] == self.config.configuration_sha256
                 and type(value['pid']) is int and 0 < value['pid'] < 2**32)
        if ready:
            _require(_listen({'host': value['listen_host'], 'port': value['listen_port']}) == self._expected_listen)
        else:
            _require(value['pid'] == self._host_pid and value['status'] == 'stopped'
                     and value['server_closed'] is True and value['native_closed'] is True
                     and value['error_code'] is None)
        return value
