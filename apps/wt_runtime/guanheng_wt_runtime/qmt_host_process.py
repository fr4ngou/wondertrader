"""WT独占只读Host进程；Host包仅由受管子进程导入，父端只读公开身份收据。"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
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
from .managed_local_process import (ManagedLocalProcess, _require, _duration, _sha, _path,
                                    _inspect, _identity, _read as _managed_read, _json, _job)


_SHA = re.compile(r'[0-9a-f]{64}')
_FIELDS = {'schema', 'pythonw', 'pythonw_sha256', 'pair_directory', 'pair_manifest_sha256',
           'installed_agent', 'control_root', 'startup_seconds', 'stop_seconds', 'max_output_bytes'}
_MANIFEST = {'schema_version', 'config_sha256', 'host_python', 'host_package', 'host_sources',
             'agent_package', 'agent_sources', 'qualified_in_qmt', 'capabilities', 'order_ready',
             'files', 'memory_runtime', 'connection_lifecycle'}
_READY = {'schema', 'control_id', 'pid', 'pair_manifest_sha256', 'pair_config_sha256',
          'listen_host', 'listen_port'}
_CLOSED = {'schema', 'control_id', 'pid', 'pair_manifest_sha256', 'pair_config_sha256',
           'status', 'runtime_closed', 'monitor_joined', 'error_code'}
# v9证券资料沿原只读Host准入；资格、manifest与原Host完整核验继续保持。
_READS = {'market.full_tick', 'market.history_1m', 'account.trade_detail',
          'market.market_data', 'market.divid_factors',
          'market.security_details', 'market.security_universe'}


def _read(path, maximum, *, clock=None, deadline=None):
    # 保留Host原有读取注入接缝，底层身份/容量检查仍只有通用实现。
    return _managed_read(path, maximum, clock=clock, deadline=deadline, inspector=_inspect)


@dataclass(frozen=True)
class HostProcessConfig:
    """部署身份/路径/预算的纯值快照；不含IPC或HTTP凭证。"""
    pythonw: str
    pythonw_sha256: str
    pair_directory: str
    pair_manifest_sha256: str
    installed_agent: str
    control_root: str
    startup_seconds: float
    stop_seconds: float
    max_output_bytes: int

    def _validate_control_root(self):
        _path(self.control_root, e_drive=True)

    def __post_init__(self):
        _path(self.pythonw); _sha(self.pythonw_sha256)
        _require(PureWindowsPath(self.pythonw).name.lower() == 'pythonw.exe')
        _path(self.pair_directory); _sha(self.pair_manifest_sha256)
        _path(self.installed_agent)
        self._validate_control_root()
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
        _require(set(value) == _FIELDS and value.pop('schema') == 'qmt.host-process.v1')
        return cls(**value)


class QmtHostProcess(ManagedLocalProcess):
    """原只读Host配置和收据适配；进程/线程/Job生命周期统一由基类持有。"""
    _status_schema = 'qmt.host-process-status.v1'
    _stop_schema = 'qmt.host-stop.v1'
    _thread_name = 'qmt-host-process'

    def __init__(self, config=None, *, job_factory=None, thread_factory=threading.Thread, clock=time.monotonic):
        _require(config is None or type(config) is HostProcessConfig)
        super().__init__(config, job_factory=job_factory or _job, thread_factory=thread_factory, clock=clock)
        self._pair_config_sha = None

    def _command(self):
        cfg = self.config
        return (cfg.pythonw, '-I', '-B', '-m', 'guanheng_qmt_shm', 'run-pair',
                '--directory', cfg.pair_directory, '--installed-agent', cfg.installed_agent,
                '--control-directory', str(self._directory), '--control-id', self._control_id)

    def _validate_inputs(self, deadline):
        cfg = self.config
        for path in (cfg.pair_directory, cfg.installed_agent, cfg.control_root):
            _inspect(Path(path), directory=True)
        self._verify_file(Path(cfg.pythonw), cfg.pythonw_sha256, 64 * 1024 * 1024, deadline)
        raw = _read(Path(cfg.pair_directory) / 'manifest.json', 1048576, clock=self._clock, deadline=deadline)
        _require(hashlib.sha256(raw).hexdigest() == cfg.pair_manifest_sha256)
        value = _json(raw)
        _require(set(value) == _MANIFEST and value['schema_version'] == 'qmt.shm-pair.v3'
                 and value['qualified_in_qmt'] is False and value['order_ready'] is False)
        capabilities = value['capabilities']
        _require(type(capabilities) is list and 1 <= len(capabilities) <= len(_READS)
                 and all(type(x) is str and x in _READS for x in capabilities)
                 and capabilities == sorted(set(capabilities)))
        _require(_path(value['agent_package']) == Path(cfg.installed_agent))
        lifecycle = value['connection_lifecycle']
        _require(type(lifecycle) is dict and set(lifecycle) == {'schema_version', 'mode', 'reconnect_seconds'}
                 and lifecycle['schema_version'] == 'qmt.read-resident.v1' and lifecycle['mode'] == 'resident-read')
        _duration(lifecycle['reconnect_seconds'], 60)
        self._pair_config_sha = _sha(value['config_sha256'])
        _require(not self._directory.exists())
        self._check(deadline)

    def _receipt(self, name, deadline):
        _inspect(self._directory, directory=True)
        value = _json(_read(self._directory / name, 4096, clock=self._clock, deadline=deadline))
        keys = _READY if name == 'ready.json' else _CLOSED
        _require(set(value) == keys and value['schema'] == ('qmt.host-ready.v1' if name == 'ready.json' else 'qmt.host-closed.v1')
                 and value['control_id'] == self._control_id
                 and value['pair_manifest_sha256'] == self.config.pair_manifest_sha256
                 and value['pair_config_sha256'] == self._pair_config_sha
                 and type(value['pid']) is int and 0 < value['pid'] < 2**32)
        if name == 'ready.json':
            _require(type(value['listen_host']) is str and 1 <= len(value['listen_host']) <= 255
                     and type(value['listen_port']) is int and 1024 <= value['listen_port'] <= 65535)
        else:
            _require(value['pid'] == self._host_pid and value['status'] == 'stopped'
                     and value['runtime_closed'] is True and value['monitor_joined'] is True
                     and value['error_code'] is None)
        return value

