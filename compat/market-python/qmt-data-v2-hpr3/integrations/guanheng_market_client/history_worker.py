"""显式作业的独立受管执行入口；Operations 持有持久状态与控制面授权。"""
from __future__ import annotations

import argparse
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from dataclasses import dataclass
import importlib
import json
import math
import os
from pathlib import Path
import re
import signal
import stat
import sys
import threading
import time
from uuid import UUID

from .history_runner import HistoryRunner

__all__ = ["WorkerLimits", "run_worker", "main"]

_RETRYABLE = frozenset({"Pending", "Backpressure", "Unavailable", "Timeout", "StaleSession"})
_CODES = _RETRYABLE | {"Ok", "Conflict", "InvalidInput", "NotSupported", "IoError", "InternalError"}
_FACTORY = re.compile(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*:[A-Za-z_]\w*", re.ASCII)


@dataclass(frozen=True)
class WorkerLimits:
    """秒数是总准入预算；不可抢占的依赖由外部进程监督负责硬截止。"""
    max_steps: int = 100
    max_seconds: float = 300
    wait_seconds: float = 1
    max_segments: int = 1
    drain_attempts: int = 3
    drain_seconds: float = 35

    def __post_init__(self):
        for name, maximum in (("max_steps", 10000), ("max_segments", 64), ("drain_attempts", 16)):
            value = getattr(self, name)
            if type(value) is not int or not 1 <= value <= maximum:
                raise ValueError("history worker limit invalid")
        for name, lower, upper in (("max_seconds", 0.001, 86400), ("wait_seconds", 0.05, 60), ("drain_seconds", 0.001, 60)):
            value = getattr(self, name)
            if type(value) not in (int, float) or not math.isfinite(value) or not lower <= value <= upper:
                raise ValueError("history worker limit invalid")


def _uuid(value):
    return str(UUID(str(value)))


def _event(phase, job_id="", status="InvalidInput", *, steps=0, confirmed=0, exit_code=None,
           pending_task=None, recovery_required=None):
    # 固定结构防止远端 reason、result_ref 或异常文本进入运行日志。
    result = {"schema_version": "guanheng.history.worker.v1", "phase": phase, "job_id": job_id,
              "status": status if status in _CODES else "InternalError", "steps": steps,
              "confirmed_segments": confirmed}
    if exit_code is not None:
        result["exit_code"] = exit_code
    if pending_task is not None:
        result.update(pending_task=pending_task, recovery_required=recovery_required)
    return result


def _write(event):
    print(json.dumps(event, sort_keys=True, separators=(",", ":")), flush=True)


@contextmanager
def _quiet_dependencies():
    # 部署工厂与注入依赖可能打印异常；仅 CLI 的结构化事件进入标准输出。
    with open(os.devnull, "w", encoding="utf-8") as sink, redirect_stdout(sink), redirect_stderr(sink):
        yield


@contextmanager
def _job_lock(directory, job_id):
    directory = Path(directory)
    if not directory.is_absolute() or not directory.is_dir():
        raise ValueError("history worker lock directory invalid")
    path = directory.resolve() / (job_id + ".lock")
    if path.is_symlink():
        raise ValueError("history worker lock path invalid")
    fd = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    locked = False
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError("history worker lock file invalid")
        if os.fstat(fd).st_size == 0:
            os.write(fd, b"0")
        os.lseek(fd, 0, os.SEEK_SET)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        locked = True
        yield
    finally:
        try:
            if locked:
                os.lseek(fd, 0, os.SEEK_SET)
                if os.name == "nt":
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def run_worker(runner, job_id, limits, stop_event, *, emit=_write, deadline=None):
    """当前线程有界执行并排空；本地暂停保持 Operations 作业原有状态。

    仅接受可信部署构造的 HistoryRunner。调用者持有实例排他锁，负责信号和
    外部硬截止；emit 接收固定结构事件，未知依赖异常仅映射固定状态。
    """
    job_id = _uuid(job_id)
    if not isinstance(runner, HistoryRunner) or not isinstance(limits, WorkerLimits):
        raise ValueError("history worker configuration invalid")
    if runner.owner != threading.get_ident() or runner.running:
        raise ValueError("history worker requires runner owner thread")
    if not isinstance(stop_event, threading.Event):
        raise ValueError("history worker stop event invalid")
    if limits.drain_seconds <= runner.budget_ms / 1000:
        # 总关闭窗口须给完整单次预算留出准入/调度余量；相等必然无法准入。
        raise ValueError("history worker drain window must exceed runner budget")
    if deadline is None:
        deadline = time.monotonic() + limits.max_seconds
    if type(deadline) not in (int, float) or not math.isfinite(deadline):
        raise ValueError("history worker deadline invalid")
    budget = runner.budget_ms / 1000
    steps, exit_code, status = 0, 3, "Pending"
    emit(_event("started", job_id, status))
    try:
        while steps < limits.max_steps and not stop_event.is_set():
            if deadline - time.monotonic() < budget:
                break
            with _quiet_dependencies():
                result = runner.step(job_id, limits.max_segments)
            steps += 1
            status = result.status
            emit(_event("step", job_id, status, steps=steps, confirmed=result.confirmed_segments))
            if status == "Ok":
                exit_code = 0
                break
            if status not in _RETRYABLE:
                exit_code = 5
                break
            remaining = deadline - time.monotonic()
            if steps < limits.max_steps and remaining > budget:
                stop_event.wait(min(limits.wait_seconds, remaining - budget))
    except KeyboardInterrupt:
        exit_code, status = 3, "Pending"
    except (Exception, SystemExit):
        # 源状态与异常未知时保留原 job；排空结果优先决定退出码。
        exit_code, status = 5, "InternalError"
    finally:
        drain_deadline = time.monotonic() + limits.drain_seconds
        drained = False
        for attempt in range(limits.drain_attempts):
            if drain_deadline - time.monotonic() < budget:
                break
            try:
                with _quiet_dependencies():
                    closed = runner.close()
                emit(_event("drain", job_id, closed.status, steps=steps,
                            pending_task=closed.pending_task, recovery_required=closed.recovery_required))
                drained = closed.status in ("Ok", "StaleSession") and not closed.pending_task and not closed.recovery_required
                if drained or closed.recovery_required:
                    break
            except (Exception, SystemExit, KeyboardInterrupt):
                break
            remaining = drain_deadline - time.monotonic()
            if attempt + 1 < limits.drain_attempts and remaining > budget:
                # 本地停止标志已置位也要节流排空；使用独立等待保留关闭预算。
                threading.Event().wait(min(limits.wait_seconds, remaining - budget))
        if not drained:
            exit_code, status = 4, "Unavailable"
    emit(_event("exited", job_id, status, steps=steps, exit_code=exit_code))
    return exit_code


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        # argparse 默认会回显 argv 中的未知参数和其值。
        raise ValueError("history worker arguments invalid")


def main(argv=None):
    """受管 CLI；凭据、部署工厂行为和跨主机单副本由部署 owner 提供。"""
    parser = _Parser(description=__doc__)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--factory", required=True)
    parser.add_argument("--lock-dir", required=True)
    parser.add_argument("--max-steps", type=int, default=100)
    parser.add_argument("--max-seconds", type=float, default=300)
    parser.add_argument("--wait-seconds", type=float, default=1)
    parser.add_argument("--max-segments", type=int, default=1)
    parser.add_argument("--drain-attempts", type=int, default=3)
    parser.add_argument("--drain-seconds", type=float, default=35)
    job_id = ""
    try:
        args = parser.parse_args(argv)
        job_id = _uuid(args.job_id)
        if not _FACTORY.fullmatch(args.factory) or len(args.factory) > 256:
            raise ValueError("history worker factory invalid")
        limits = WorkerLimits(args.max_steps, args.max_seconds, args.wait_seconds, args.max_segments,
                              args.drain_attempts, args.drain_seconds)
    except (ValueError, TypeError, AttributeError):
        _write(_event("configuration", job_id, exit_code=2))
        return 2
    stop_event = threading.Event()
    previous = {}
    runner = None
    try:
        # 锁先于加载部署工厂，竞争进程不能先行接触远端或凭据。
        with _job_lock(args.lock_dir, job_id):
            for sig in (signal.SIGINT, signal.SIGTERM):
                previous[sig] = signal.signal(sig, lambda *_: stop_event.set())
            deadline = time.monotonic() + limits.max_seconds
            try:
                with _quiet_dependencies():
                    module, name = args.factory.split(":")
                    runner = getattr(importlib.import_module(module), name)()
                if not isinstance(runner, HistoryRunner):
                    raise ValueError("history worker factory contract invalid")
            except (Exception, SystemExit, KeyboardInterrupt):
                _write(_event("configuration", job_id, exit_code=2))
                return 2
            return run_worker(runner, job_id, limits, stop_event, deadline=deadline)
    except (OSError, ValueError, RuntimeError):
        _write(_event("startup", job_id, "Conflict", exit_code=2))
        return 2
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


if __name__ == "__main__":
    sys.exit(main())
