"""独立行情采集进程部署适配；默认关闭，ready仅表示listener就绪。"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
from pathlib import Path, PureWindowsPath
import threading
import time

from .managed_local_process import (ManagedLocalProcess, _require, _duration, _sha,
                                    _path, _inspect, _read, _json)

_FIELDS = {'schema', 'pythonw', 'pythonw_sha256', 'entry', 'entry_sha256',
           'configuration', 'configuration_sha256', 'control_root',
           'startup_seconds', 'stop_seconds', 'max_output_bytes'}
_READY = {'schema', 'control_id', 'pid', 'configuration_sha256', 'listener_ready'}
_CLOSED = {'schema', 'control_id', 'pid', 'configuration_sha256', 'status',
           'receiver_closed', 'native_closed', 'error_code'}


@dataclass(frozen=True)
class QuoteCollectionProcessConfig:
    """受管入口/子配置原字节身份；不包含连接凭证或原生业务配置正文。"""
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
        if path is None or path == '':
            _require(expected_sha256 in (None, ''))
            return None
        expected = _sha(expected_sha256)
        raw = _read(_path(path), 65536)
        _require(hashlib.sha256(raw).hexdigest() == expected)
        value = _json(raw)
        _require(set(value) == _FIELDS and value.pop('schema') == 'qmt.quote-collector-process.v1')
        return cls(**value)


class QuoteCollectionProcess(ManagedLocalProcess):
    """只托管单次采集进程；不自动重启，不把进程ready解释为行情或历史就绪。"""
    _status_schema = 'qmt.quote-collector-process-status.v1'
    _stop_schema = 'qmt.quote-collector-stop.v1'
    _thread_name = 'qmt-quote-collector-process'

    def __init__(self, config=None, *, job_factory=None, thread_factory=threading.Thread, clock=time.monotonic):
        _require(config is None or type(config) is QuoteCollectionProcessConfig)
        super().__init__(config, job_factory=job_factory, thread_factory=thread_factory, clock=clock)

    def _validate_inputs(self, deadline):
        cfg = self.config
        _inspect(Path(cfg.control_root), directory=True)
        self._verify_file(Path(cfg.pythonw), cfg.pythonw_sha256, 64 * 1024 * 1024, deadline)
        self._verify_file(Path(cfg.entry), cfg.entry_sha256, 4 * 1024 * 1024, deadline)
        self._verify_file(Path(cfg.configuration), cfg.configuration_sha256, 65536, deadline)
        # 子配置、连接与原生依赖的完整语义由子服务唯一校验；父只绑定受管身份。
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
                 and value['schema'] == ('qmt.quote-collector-ready.v1' if ready else 'qmt.quote-collector-closed.v1')
                 and value['control_id'] == self._control_id
                 and value['configuration_sha256'] == self.config.configuration_sha256
                 and type(value['pid']) is int and 0 < value['pid'] < 2**32)
        if ready:
            _require(value['listener_ready'] is True)
        else:
            _require(value['pid'] == self._host_pid and value['status'] == 'stopped'
                     and value['receiver_closed'] is True and value['native_closed'] is True
                     and value['error_code'] is None)
        return value

    def observe(self, deadline):
        """只读当前实例状态；目录与三重身份由本owner提供，原生命周期不变。

        在有界读池内调用，参数为原monotonic绝对截止；文件读取期间不持进程锁。
        读取后续核同一实例及当前进程状态，JSON不能单独证明当前运行或连接。
        """
        from .collection_observation import empty_observation, read_observation, with_process_state
        with self._condition:
            if self.config is None:
                return with_process_state(empty_observation('unconfigured'), self.status())
            identity = (self._control_id, self._host_pid, self.config.configuration_sha256)
            directory = self._directory
        if identity[1] is None:
            return with_process_state(empty_observation('waiting'), self.status())
        result = read_observation(directory, identity, deadline, clock=self._clock, wall_clock=time.time)
        with self._condition:
            if (identity != (self._control_id, self._host_pid, self.config.configuration_sha256)
                    or directory != self._directory):
                result = empty_observation('identity_changed')
            return with_process_state(result, self.status())
