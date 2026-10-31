"""受管分钟消费进程；唯一线程访问SDK，持久游标与接纳确认归MarketData。"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import timedelta
import importlib
import json
import math
import signal
import sys
import threading
import time
from uuid import NAMESPACE_URL, uuid5

from . import encode_json, strict_json
from .history_worker import _FACTORY, _job_lock, _quiet_dependencies
from .minute_owner import (MinuteOwnerConflict, MinuteOwnerProtocolError, MinuteOwnerRejected,
    MinuteOwnerUnavailable, admission_request, confirm_receipt, minute_time, sha_identity,
    stream_identity, validate_checkpoint)
from .strategy_market import StrategyMarket, _instant, _minute

_RETRYABLE = {"Ok", "Pending", "Unavailable", "Timeout", "Backpressure"}


def _bound(value, maximum):
    return type(value) in (int, float) and 0 < value <= maximum and math.isfinite(value)


@dataclass(frozen=True)
class MinuteStepResult:
    status: str
    committed_after: int | None = None
    accepted_bars: int = 0
    recovery_required: bool = False


class MinuteWorker:
    """同步有限步骤；pending请求保持原身份，先回查再重投，禁止本地推算游标。

    每步预留一次完整行情预算及四次owner交换，涵盖恢复回查、提交与CAS刷新。
    外部信号仅停止后续步骤；正在进行的有限调用结束后由本线程核查和关闭。
    """
    def __init__(self, market, owner_client, stream_id, policy_sha256, *, max_batch_minutes=240, budget_seconds=60):
        if (not isinstance(market, StrategyMarket) or market._owner != threading.get_ident() or market._closed
                or any(not callable(getattr(owner_client, name, None)) for name in ("checkpoint", "submit", "receipt"))
                or not _bound(getattr(owner_client, "timeout", None), 30)
                or type(max_batch_minutes) is not int or not 1 <= max_batch_minutes <= 1440
                or market.max_bars > 512 or not _bound(budget_seconds, 600)
                or budget_seconds <= market.timeout + 4 * owner_client.timeout):
            raise ValueError("minute worker configuration invalid")
        self.market, self.owner_client = market, owner_client
        self.stream_id, self.policy_sha256 = stream_identity(stream_id), sha_identity(policy_sha256)
        self.max_batch_minutes, self.budget_seconds = max_batch_minutes, budget_seconds
        self.owner_thread = threading.get_ident()
        self.checkpoint, self.subscription, self.pending = None, None, None
        self.closed, self.running = False, False

    def _guard(self):
        if self.owner_thread != threading.get_ident() or self.running:
            raise RuntimeError("minute worker requires its idle owner thread")

    def _call(self, method, *args):
        remaining = self.deadline - time.monotonic()
        if not _bound(getattr(self.owner_client, "timeout", None), 30):
            raise MinuteOwnerProtocolError()
        if remaining < self.owner_client.timeout:
            raise MinuteOwnerUnavailable()
        # 注入的传输不得改变保留的未知请求，否则重试身份失去稳定性。
        detached = tuple(strict_json(encode_json(item)) if isinstance(item, dict) else item for item in args)
        result = getattr(self.owner_client, method)(self.stream_id, *detached)
        if time.monotonic() >= self.deadline:
            raise MinuteOwnerUnavailable()
        return result

    def _refresh(self):
        checkpoint = validate_checkpoint(self._call("checkpoint"))
        if (checkpoint["stream_id"] != self.stream_id or checkpoint["policy_sha256"] != self.policy_sha256
                or checkpoint["calendar_version"] != self.market.calendar_version):
            raise MinuteOwnerProtocolError()
        old = self.checkpoint
        if old is not None and (any(checkpoint[key] != old[key] for key in
                ("symbol", "feature_version", "calendar_version", "bootstrap_after", "live_after", "max_batch_minutes"))
                or checkpoint["revision"] < old["revision"] or checkpoint["committed_after"] < old["committed_after"]):
            raise MinuteOwnerProtocolError()
        try:
            subscription = self.market.subscribe_minutes(checkpoint["symbol"], minute_time(checkpoint["committed_after"]))
        except (ValueError, RuntimeError):
            raise MinuteOwnerProtocolError() from None
        if self.subscription is not None:
            self.subscription.close()
        self.subscription, self.checkpoint = subscription, checkpoint

    def _result(self, status, accepted=0):
        return MinuteStepResult(status, None if self.checkpoint is None else self.checkpoint["committed_after"],
                                accepted, self.pending is not None)

    def _confirmed(self, value):
        receipt = confirm_receipt(value, self.stream_id, self.pending)
        accepted = receipt["stored_count"]
        try:
            acked = self.subscription.ack(self.pending["batch_id"])
        except Exception:
            acked = False
        if not acked:
            # ACK结果未知只影响内存；重新读取已提交owner再重建，无需本地账本。
            self._refresh()
            if self.checkpoint["revision"] < receipt["revision"] or self.checkpoint["committed_after"] < receipt["committed_after"]:
                raise MinuteOwnerProtocolError()
        else:
            self.checkpoint = dict(self.checkpoint, committed_after=receipt["committed_after"],
                revision=receipt["revision"], last_batch_id=receipt["batch_id"],
                phase="warmup" if receipt["committed_after"] < self.checkpoint["live_after"] else "subscription")
        self.pending = None
        return self._result("Ok", accepted)

    def _receipt(self):
        receipt = self._call("receipt", self.pending["batch_id"])
        return None if receipt is None else self._confirmed(receipt)

    def _submit(self):
        conflict = False
        try:
            return self._confirmed(self._call("submit", self.pending))
        except MinuteOwnerRejected:
            # 可信公开拒绝没有接纳效果；保留SDK未ACK，停止并由调用者修配置。
            self.pending = None
            return self._result("InvalidInput")
        except MinuteOwnerConflict:
            conflict = True
        except (Exception, KeyboardInterrupt):
            # 响应解析失败、超时及中断均可能发生在提交以后，先查询原身份。
            pass
        confirmed = self._receipt()
        if confirmed is not None:
            return confirmed
        if conflict:
            self._refresh()
            self.pending = None
            return self._result("Pending")
        return self._result("Pending")

    def step(self):
        self._guard()
        if self.closed:
            return self._result("Unavailable")
        self.running, self.deadline = True, time.monotonic() + self.budget_seconds
        try:
            if self.checkpoint is None:
                self._refresh()
                return self._result("Pending")
            if self.pending is not None:
                confirmed = self._receipt()
                return confirmed if confirmed is not None else self._submit()
            now = _instant(self.market.clock())
            limit = min(self.max_batch_minutes, self.checkpoint["max_batch_minutes"])
            through = min(now.replace(second=0, microsecond=0),
                          minute_time(self.checkpoint["committed_after"]) + timedelta(minutes=limit))
            if self.checkpoint["phase"] == "warmup":
                through = min(through, minute_time(self.checkpoint["live_after"]))
            if (not _bound(self.market.timeout, 300) or not _bound(self.owner_client.timeout, 30)):
                return self._result("Conflict")
            if self.deadline - time.monotonic() < self.market.timeout + 4 * self.owner_client.timeout:
                return self._result("Timeout")
            batch = self.subscription.poll(as_of=now, until=through)
            if batch.status != "Ok":
                return self._result(batch.status)
            if not batch.batch_id:
                return self._result("Pending")
            self.pending = admission_request(self.checkpoint, batch)
            return self._submit()
        except (MinuteOwnerConflict, MinuteOwnerProtocolError):
            return self._result("Conflict")
        except MinuteOwnerRejected:
            return self._result("InvalidInput")
        except (MinuteOwnerUnavailable, OSError, TimeoutError, KeyboardInterrupt):
            return self._result("Unavailable")
        except Exception:
            return self._result("InternalError")
        finally:
            self.running = False

    def close(self):
        """停止新扫描；待确认请求仅回查，不在关闭期间重新提交或读取行情。"""
        self._guard()
        if self.closed:
            return self._result("Pending" if self.pending else "Ok")
        self.running, self.deadline = True, time.monotonic() + self.budget_seconds
        status = "Ok"
        try:
            if self.pending is not None:
                result = self._receipt()
                status = result.status if result is not None else "Pending"
        except (MinuteOwnerProtocolError, MinuteOwnerConflict):
            status = "Conflict"
        except (Exception, KeyboardInterrupt):
            status = "Unavailable"
        finally:
            if self.subscription is not None:
                self.subscription.close()
            self.market.close()
            self.closed, self.running = True, False
        return self._result(status)


@dataclass(frozen=True)
class MinuteWorkerLimits:
    max_steps: int = 100
    max_seconds: float = 300
    wait_seconds: float = 1

    def __post_init__(self):
        if (type(self.max_steps) is not int or not 1 <= self.max_steps <= 100000
                or not _bound(self.max_seconds, 86400) or not _bound(self.wait_seconds, 60)):
            raise ValueError("minute worker limits invalid")


def _event(phase, status, *, steps=0, recovery_required=False):
    return dict(schema_version="guanheng.minute.worker.v1", phase=phase, status=status,
                steps=steps, recovery_required=recovery_required)


def _write(value):
    print(json.dumps(value, sort_keys=True, separators=(",", ":")), flush=True)


def run_worker(worker, limits, stop_event, *, emit=_write, deadline=None):
    if not isinstance(worker, MinuteWorker) or not isinstance(limits, MinuteWorkerLimits) or not isinstance(stop_event, threading.Event):
        raise ValueError("minute worker configuration invalid")
    worker._guard()
    deadline = time.monotonic() + limits.max_seconds if deadline is None else deadline
    if not _bound(deadline, float("inf")):
        raise ValueError("minute worker deadline invalid")
    steps, exit_code = 0, 0
    emit(_event("started", "Pending"))
    try:
        while not stop_event.is_set() and steps < limits.max_steps:
            if deadline - time.monotonic() < worker.budget_seconds:
                break
            with _quiet_dependencies():
                result = worker.step()
            steps += 1
            emit(_event("step", result.status, steps=steps, recovery_required=result.recovery_required))
            if result.status not in _RETRYABLE:
                exit_code = 5
                break
            remaining = deadline - time.monotonic() - worker.budget_seconds
            if steps < limits.max_steps and remaining > 0:
                stop_event.wait(min(limits.wait_seconds, remaining))
    except (Exception, KeyboardInterrupt, SystemExit):
        exit_code = 5
    finally:
        with _quiet_dependencies():
            result = worker.close()
        emit(_event("closed", result.status, steps=steps, recovery_required=result.recovery_required))
        if result.recovery_required or result.status != "Ok":
            exit_code = 4
    return exit_code


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run one bounded minute-stream consumer", exit_on_error=False)
    parser.add_argument("--stream-id", required=True)
    parser.add_argument("--factory", default="guanheng_market_client.minute_factory:create")
    parser.add_argument("--lock-dir", required=True)
    parser.add_argument("--max-steps", type=int, default=100)
    parser.add_argument("--max-seconds", type=float, default=300)
    parser.add_argument("--wait-seconds", type=float, default=1)
    try:
        with _quiet_dependencies():
            args = parser.parse_args(argv)
        stream = stream_identity(args.stream_id)
        if len(args.factory) > 256 or _FACTORY.fullmatch(args.factory) is None:
            raise ValueError
        limits = MinuteWorkerLimits(args.max_steps, args.max_seconds, args.wait_seconds)
    except (Exception, SystemExit):
        _write(_event("configuration", "InvalidInput"))
        return 2
    stop, previous = threading.Event(), {}
    try:
        # 同机锁在工厂加载前取得；跨主机并发由owner事务CAS处理。
        with _job_lock(args.lock_dir, str(uuid5(NAMESPACE_URL, "guanheng.minute:" + stream))):
            for sig in (signal.SIGINT, signal.SIGTERM):
                previous[sig] = signal.signal(sig, lambda *_: stop.set())
            deadline = time.monotonic() + limits.max_seconds
            try:
                with _quiet_dependencies():
                    module, name = args.factory.split(":")
                    worker = getattr(importlib.import_module(module), name)()
                if not isinstance(worker, MinuteWorker) or worker.stream_id != stream:
                    if isinstance(worker, MinuteWorker):
                        worker.close()
                    raise ValueError
            except (Exception, SystemExit, KeyboardInterrupt):
                _write(_event("configuration", "InvalidInput"))
                return 2
            return run_worker(worker, limits, stop, deadline=deadline)
    except (OSError, ValueError, RuntimeError):
        _write(_event("startup", "Conflict"))
        return 2
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


if __name__ == "__main__":
    # -m执行时工厂导入的是规范模块；统一类型身份，避免__main__产生第二套类型。
    from .minute_worker import main as entrypoint
    sys.exit(entrypoint())
