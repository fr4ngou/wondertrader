"""本机操作员回测入口；冻结值交给唯一NSH owner，终端及柜台不参与。

信号只通知父owner取消。CLI与宿主共享总预算，回执只投影收口事实；完整
历史仍归原运行目录，避免在stdout再次复制多年的逐日结果。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import signal
import sys
from threading import Event
from time import monotonic

from .strategy_host import (
    HostBudgets, HostError, InstallationBinding, StrategyHost, _bytes,
)
from .strategy_porter import AdmissionError, validate_backtest_window

_SCHEMA = "guanheng.backtest-cli.v1"
_MAX_RECEIPT = 8192
_RESULT_FIELDS = (
    "run_id", "status", "reason", "request_sha256", "installation_sha256",
    "directory", "pid", "exit_code", "forced", "pid_reaped", "pipes_joined",
    "elapsed_ms", "scope",
)
_UNQUALIFIED = "isolated-raw-BT; real-source/RT/broker/production-unqualified"


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        # argparse的默认诊断包含原argv；仅将固定原因交给统一回执边界。
        raise HostError("命令参数缺失、未知或类型不合格；请使用--help查看固定说明")

    def print_help(self, file=None):
        # 固定说明不包含调用者的argv、程序路径或本机受管配置。
        print("WT独立隔离回测：--binding PATH --binding-sha256 SHA256 --work-root PATH "
              "--session PATH --start YYYYMMDDHHMM --end YYYYMMDDHHMM "
              "[--name NAME] [--seconds 0.1..1800]", file=file)


def _parser():
    parser = _Parser(allow_abbrev=False)
    parser.add_argument("--binding", required=True, type=Path)
    parser.add_argument("--binding-sha256", required=True)
    parser.add_argument("--work-root", required=True, type=Path)
    parser.add_argument("--session", required=True, type=Path)
    parser.add_argument("--start", required=True, type=int, help="上海回放时刻YYYYMMDDHHMM")
    parser.add_argument("--end", required=True, type=int, help="上海回放时刻YYYYMMDDHHMM")
    parser.add_argument("--name", default="resonance")
    parser.add_argument("--seconds", default=1800.0, type=float)
    return parser


def _write_receipt(value):
    # ASCII JSON跨控制台代码页保持中文值，单个回执有明确上界。
    envelope = {name: value.get(name) for name in _RESULT_FIELDS}
    data = json.dumps({"schema": _SCHEMA, **envelope}, ensure_ascii=True, allow_nan=False,
                      separators=(",", ":"))
    if len(data.encode("ascii")) > _MAX_RECEIPT:
        # 保留能装入固定逐字段预算的已知事实；未知字段保持null，保持同版信封。
        envelope = {name: item if len(json.dumps(item, ensure_ascii=True).encode("ascii")) <= 512
                    else None for name, item in envelope.items()}
        envelope.update(status="incomplete", reason="运行回执超过容量，原运行目录保持供核查")
        data = json.dumps({"schema": _SCHEMA, **envelope}, ensure_ascii=True, allow_nan=False,
                          separators=(",", ":"))
        print(data)
        return False
    print(data)
    return True


def main(argv=None):
    """返回CLI退出码；本机主线程调用，临时信号处理器始终恢复。"""
    began = monotonic()
    cancel = Event()
    handlers = {}
    owner_entered = False
    try:
        args = _parser().parse_args(argv)
        budgets = HostBudgets(max_seconds=args.seconds)
        if args.seconds > 1800 or not re.fullmatch(r"[0-9a-f]{64}", args.binding_sha256):
            raise HostError("需要小写SHA256安装摘要，期限只能收紧至0.1..1800秒")
        validate_backtest_window(args.start, args.end)
        for name in ("SIGINT", "SIGBREAK", "SIGTERM"):
            number = getattr(signal, name, None)
            if number is not None:
                handlers[number] = signal.signal(number, lambda _signum, _frame: cancel.set())
        deadline = began + budgets.max_seconds
        payload = _bytes(args.session, budgets.input_bytes, deadline)
        if cancel.is_set():
            raise HostError("输入读取期间已取消，未启动原生回测")
        host = StrategyHost(InstallationBinding(args.binding, args.binding_sha256), args.work_root,
                            budgets=budgets)
        remaining = deadline - monotonic()
        if remaining < .1:
            raise HostError("输入准入已耗尽总期限，未启动原生回测")
        # 只收紧预算；已消耗的读取/准入时间不能在宿主run时重获。
        host.budgets = HostBudgets(max_seconds=remaining)
        owner_entered = True
        result = host.run(payload, start=args.start, end=args.end, name=args.name, cancel=cancel)
        value = {name: getattr(result, name) for name in _RESULT_FIELDS}
        complete = (result.status == "completed" and not result.forced and result.exit_code == 0
                    and result.pid_reaped and result.pipes_joined)
        if result.status == "completed" and not complete:
            value.update(status="incomplete", reason="宿主成功状态缺少完整进程回收证据")
        if not _write_receipt(value):
            return 2
        return 0 if complete else 3 if result.status == "busy" else 130 if cancel.is_set() else 2
    except (HostError, AdmissionError, OSError, ValueError) as exc:
        reason = str(exc)[:512] if isinstance(exc, (HostError, AdmissionError)) else "无法读取受管输入或建立回测宿主"
        _write_receipt({"status": "incomplete", "reason": reason,
                        "elapsed_ms": round((monotonic() - began) * 1000),
                        "scope": ("owner-result-unknown; " if owner_entered else "not-started; ") + _UNQUALIFIED})
        return 130 if cancel.is_set() else 2
    finally:
        for number, handler in handlers.items():
            signal.signal(number, handler)


if __name__ == "__main__":
    sys.exit(main())
