"""将最终父端回收事实发布为原NBW完成证明；报告和原生输出保持原件。

调用者须仍持有本次原HostResult。入口不扫描旧运行、不创建进程；发布与回读
共用调用者的绝对monotonic截止。观衡沿原completed-archive.json只读消费。
"""
from __future__ import annotations

import math
import os
from pathlib import Path
import re
import stat
from uuid import uuid4

from .strategy_host import (
    HostBudgets, HostError, HostResult, InstallationBinding, StrategyHost,
    _check, _digest, _encode, _json, _path,
)
from .backtest_reports import validate_report_dict

RECEIPT = 'completed-archive.json'
SCHEMA = 'nbw-completed-archive-v1'
SCOPE = 'isolated-raw-BT; real-source/RT/broker/production-unqualified'
MAX_RECEIPT = 16384
MAX_ENTRIES = 8192
MAX_RUN_BYTES = 192 * 1048576


def _require(ok):
    if not ok:
        raise HostError('完成证明的父回收事实、原件身份或发布配置不合格')


def _same(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def _capacity(directory, deadline, *, reserve):
    """与原NBW累计同一整run目录项/字节；仅首次发布预留pending及证明。"""
    extra_entries, extra_bytes = (2, MAX_RECEIPT) if reserve else (0, 0)
    pending, entries, total = [directory], 0, 0
    while pending:
        folder = pending.pop()
        _check(deadline)
        with os.scandir(folder) as children:
            for child in children:
                _check(deadline)
                entries += 1
                if entries + extra_entries > MAX_ENTRIES:
                    raise HostError('完成归档目录项容量已满，请保留原件并核查')
                path = _path(Path(child.path))
                info = path.lstat()
                if stat.S_ISDIR(info.st_mode):
                    pending.append(path)
                else:
                    _require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1)
                    total += info.st_size
                    if total + extra_bytes > MAX_RUN_BYTES:
                        raise HostError('完成归档原件或首次发布预留容量不足')
    _check(deadline)


def _read(path, maximum, deadline):
    """沿原路径规则读取单链接普通文件，并核对打开前后的同一原件。"""
    _check(deadline)
    path = _path(path)
    before = path.lstat()
    _require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= maximum)
    data = bytearray()
    with path.open('rb') as stream:
        _require(_same(os.fstat(stream.fileno())) == _same(before))
        while True:
            _check(deadline)
            part = stream.read(min(65536, maximum + 1 - len(data)))
            if not part:
                break
            data.extend(part)
            _require(len(data) <= maximum)
        _require(_same(os.fstat(stream.fileno())) == _same(before))
    after = _path(path).lstat()
    _require(_same(after) == _same(before) and after.st_nlink == 1)
    _check(deadline)
    return bytes(data)


def publish_completed(result, work_root, *, label, session_sha256, max_seconds, deadline):
    """返回原NBW证明的SHA256；写失败抛错并保留原件，调用者保留执行状态。

    仅接受当前父责任层已完成的HostResult；deadline为原CLI总D，max_seconds
    为其原始秒数预算。label只用于展示，session_sha256绑定操作员输入原字节。
    CLI一次运行以原run_id标识owner/request；历史读取不授进程控制权。
    """
    _check(deadline)
    _require(type(result) is HostResult and result.status == 'completed' and result.forced is False
             and type(result.exit_code) is int and result.exit_code == 0
             and result.pid_reaped is True and result.pipes_joined is True
             and type(result.pid) is int and 0 < result.pid <= 0xffffffff
             and type(result.elapsed_ms) is int and 0 <= result.elapsed_ms <= 7200000
             and type(result.run_id) is str and re.fullmatch('[a-f0-9]{32}', result.run_id)
             and type(result.report_json) is str)
    _require(type(label) is str and 1 <= len(label) <= 100 and all(ord(c) >= 32 for c in label)
             and type(session_sha256) is str and re.fullmatch('[a-f0-9]{64}', session_sha256)
             and type(max_seconds) in (int, float) and math.isfinite(max_seconds)
             and .1 <= max_seconds <= 1800)
    directory = _path(Path(work_root) / result.run_id)
    _require(directory.is_dir() and _path(result.directory) == directory and os.name == 'nt')
    # 与原NBW容量一致；首次写预留pending和最终证明，现有文件全部保持。
    target = directory/RECEIPT
    _capacity(directory, deadline, reserve=not target.exists())
    request_raw = _read(directory/'request.json', 16 * 1048576, deadline)
    install_raw = _read(directory/'installation.json', 2 * 1048576, deadline)
    result_raw = _read(directory/'result.json', 32 * 1048576, deadline)
    _require(_digest(request_raw) == result.request_sha256
             and _digest(install_raw) == result.installation_sha256)
    request = _json(request_raw, 16 * 1048576, deadline)
    install = _json(install_raw, 2 * 1048576, deadline)
    returned = _json(result_raw, 32 * 1048576, deadline)
    _require(request['run_id'] == result.run_id
             and request['installation_sha256'] == result.installation_sha256
             and request['session_sha256'] == _digest(_encode(request['session'])))
    # 复用原父owner的唯一结果/金融身份与输出校验，不另写报告或成交计算。
    verifier = StrategyHost(InstallationBinding(directory/'installation.json', result.installation_sha256),
                            Path(work_root), budgets=HostBudgets())
    report_json = verifier._result(returned, directory, result.run_id, result.request_sha256,
                                   install, request, deadline)
    _require(report_json == result.report_json)
    for key, identity in install['basefiles'].items():
        for folder in ('basefiles', 'session-basefiles'):
            _require(_digest(_read(directory/folder/(key+'.json'), 1048576, deadline)) == identity['sha256'])
    admitted = validate_report_dict(returned['report'], check=lambda: _check(deadline))
    value = dict(schema=SCHEMA, run_id=result.run_id, owner_id=result.run_id, request_id=result.run_id,
        request_sha256=result.request_sha256, installation_sha256=result.installation_sha256,
        result_sha256=_digest(result_raw), report_sha256=_digest(report_json.encode('ascii')),
        record_count=admitted.record_count, pid=result.pid, exit_code=0, forced=False,
        pid_reaped=True, pipes_joined=True, elapsed_ms=result.elapsed_ms, scope=SCOPE,
        configuration=dict(label=label, **request['backtest'], session_sha256=session_sha256,
                           max_seconds=max_seconds))
    encoded = _encode(value)
    _require(len(encoded) <= MAX_RECEIPT)
    if target.exists():
        _require(_read(target, MAX_RECEIPT, deadline) == encoded)
        return _digest(encoded)
    temporary = directory/('.archive-'+uuid4().hex+'.pending')
    _check(deadline)
    with temporary.open('xb') as stream:
        identity = os.fstat(stream.fileno())
        stream.write(encoded)
        stream.flush()
        _check(deadline)
        os.fsync(stream.fileno())
    _require(_read(temporary, MAX_RECEIPT, deadline) == encoded)
    info = temporary.lstat()
    _require((info.st_dev, info.st_ino) == (identity.st_dev, identity.st_ino))
    _path(directory)
    _check(deadline)
    try:
        # Windows rename在目标已存在时失败；同身份竞争可确认，冲突保留两件原件。
        os.rename(temporary, target)
    except FileExistsError:
        _require(_read(target, MAX_RECEIPT, deadline) == encoded)
        info = temporary.lstat()
        _require((info.st_dev, info.st_ino) == (identity.st_dev, identity.st_ino))
        temporary.unlink()
    _require(_read(target, MAX_RECEIPT, deadline) == encoded)
    _check(deadline)
    return _digest(encoded)
