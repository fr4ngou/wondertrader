"""固定安装的策略子入口。仅接受本轮冻结请求，不接受命令、loader或DLL参数。"""
from __future__ import annotations

import argparse
from dataclasses import fields
import math
import os
from pathlib import Path
import sys
import time

from .strategy_host import (SCHEMA, HostError, _BASES, _bytes, _digest, _encode, _json, _keys, _path, _tree,
                            verify_install)


def decode_session(value):
    """固定schema转领域DTO；映射/原生日线冻结tuple，业务校验归原owner。"""
    if type(value) is dict and value.get('schema') == 'guanheng.retained-replay-input.v1':
        from .retained_replay import RetainedReplayInput
        return RetainedReplayInput.from_dict(value)
    from guanheng_strategy_core import ConfiguredStrategyConfig, FrozenHistory, HistoricalEodModel
    from guanheng_strategy_native import QuantityPolicy
    from .strategy_porter import Bar
    from .strategy_session import FrozenSessionInput, NativeSeries
    from .strategy_evaluation import FrozenV2SessionInput,V2BacktestSpec
    from .strategy_host import StrategyHost
    StrategyHost._payload_shape(value)
    data = dict(value)
    v2=data.get('schema')=='nsb-v2-input-v1'
    if v2:data['strategy']=V2BacktestSpec.from_dict(data['strategy'])
    else:data["config"] = ConfiguredStrategyConfig.from_dict(data["config"])
    data["history"] = FrozenHistory.from_dict(data["history"])
    if "historical_model" in data:
        if v2:
            raise HostError("当前历史回测模型仅接configured回测")
        data["historical_model"] = HistoricalEodModel.from_dict(data["historical_model"])
    if type(data["policy"]) is not dict:
        raise HostError("需要显式理论资本与数量policy")
    _keys(data["policy"], ("initial_capital_cny", "capital_source"),
          tuple(f.name for f in fields(QuantityPolicy) if f.name not in ("initial_capital_cny", "capital_source")))
    data["policy"] = QuantityPolicy(**data["policy"])
    mapping = data["native_mapping"]
    if type(mapping) is not list or not 1 <= len(mapping) <= 16 or any(type(v) is not list or len(v) != 2 or any(type(x) is not str for x in v) for v in mapping):
        raise HostError("证券映射结构无效")
    data["native_mapping"] = tuple(tuple(v) for v in mapping)
    series = []
    for item in data["series"]:
        bars = []
        for row in item["bars"]:
            _keys(row, ("date", "time", "open", "high", "low", "close", "settle", "money", "vol"), ("hold", "add", "reserve"))
            bars.append(Bar(**row))
        series.append(NativeSeries(item["symbol"], tuple(bars)))
    data["series"] = tuple(series)
    return FrozenV2SessionInput(**data) if v2 else FrozenSessionInput(**data)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--request-sha", required=True)
    parser.add_argument("--binding-sha", required=True)
    parser.add_argument("--deadline", required=True, type=float)
    args = parser.parse_args(argv)
    # monotonic在本机进程间共用时钟；所有子端准入也沿父端同一次绝对截止。
    deadline = args.deadline
    if not math.isfinite(deadline) or not time.monotonic() < deadline <= time.monotonic() + 7200:
        raise HostError("子进程共用截止无效或已经耗尽")
    root = _path(Path.cwd())
    if not sys.flags.isolated or not sys.dont_write_bytecode or args.request != root / "request.json":
        raise HostError("runner需要隔离Python和固定本轮请求路径")
    if len(root.name) != 32 or any(c not in "0123456789abcdef" for c in root.name):
        raise HostError("runner目录身份无效")
    installation_bytes = _bytes(root / "installation.json", 2097152, deadline)
    install = verify_install(installation_bytes, args.binding_sha, deadline)
    if (Path(sys.executable) != Path(install["python"]["path"]) or Path(__file__).resolve() != Path(install["site_root"]) / "guanheng_app/strategy_runner.py"
            or not any(Path(item["path"]) == Path(sys._base_executable) for item in install["python_runtime"])):
        raise HostError("执行解释器或runner不属于受信安装")
    data = _bytes(args.request, 16777216, deadline)
    if _digest(data) != args.request_sha:
        raise HostError("请求冻结身份漂移")
    request = _json(data, 16777216, deadline)
    _keys(request, ("schema", "run_id", "installation_sha256", "session", "session_sha256", "backtest", "budgets", "deadline_monotonic", "report_schema"))
    if (request["schema"], request["run_id"], request["installation_sha256"]) != (SCHEMA, root.name, args.binding_sha):
        raise HostError("请求schema/run/安装身份失配")
    from .backtest_reports import report_schema_for_input
    if (request["deadline_monotonic"] != deadline or request["report_schema"] != install['report_schema']
            or request['report_schema']!=report_schema_for_input(request['session'])):
        raise HostError("父子绝对截止身份失配")
    if _digest(_encode(request["session"])) != request["session_sha256"]:
        raise HostError("完整会话输入身份失配")
    _keys(request["backtest"], ("start", "end", "name"))
    _keys(request["budgets"], ("input_bytes", "native_bytes", "result_bytes", "max_files"))
    budgets = request["budgets"]
    maxima = {"input_bytes": 16777216, "native_bytes": 536870912, "result_bytes": 67108864, "max_files": 65536}
    if any(type(budgets[k]) is not int or not 1 <= budgets[k] <= v for k, v in maxima.items()) or len(data) > budgets["input_bytes"]:
        raise HostError("子端预算无效")
    for name in _BASES:
        payload = _bytes(root / "basefiles" / (name + ".json"), 1048576, deadline)
        if _digest(payload) != install["basefiles"][name]["sha256"]:
            raise HostError("本轮基础资料副本身份失配")
    # 所有安装、请求、基础资料身份核完后才导入并创建业务session；没有动态loader。
    from .strategy_porter import BacktestConfig
    from .strategy_session import StrategyBacktestSession
    inputs = decode_session(request["session"])
    if request['report_schema'] == 'guanheng.retained-replay-report.v1':
        from .retained_replay import RetainedBacktestSession
        session = RetainedBacktestSession(inputs)
    else:
        session = StrategyBacktestSession(inputs)
    config = BacktestConfig(root, root / "outputs", root / "storage",
                            *(root / "basefiles" / (name + ".json") for name in _BASES),
                            **request["backtest"])
    report = session.run(Path(install["library"]["path"]), Path(install["abi_probe"]["path"]), config)
    files, _ = _tree(root / "outputs", budgets["native_bytes"], budgets["max_files"], deadline)
    outputs = {p.relative_to(root).as_posix(): _digest(_bytes(p, budgets["native_bytes"], deadline)) for p in files}
    result = {"schema": SCHEMA, "run_id": root.name, "request_sha256": args.request_sha,
              "installation_sha256": args.binding_sha, "report_schema": request['report_schema'],
              "report": report if type(report) is dict else report.to_dict(), "native_outputs": outputs}
    encoded = _encode(result)
    if len(encoded) > budgets["result_bytes"]:
        raise HostError("结构化结果超过预算")
    temporary = root / "result.pending"
    with temporary.open("xb") as stream:
        stream.write(encoded); stream.flush(); os.fsync(stream.fileno())
    if (root / "result.json").exists():
        raise HostError("结果目标已存在，拒绝采用旧结果")
    temporary.replace(root / "result.json")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyboardInterrupt, Exception) as exc:
        # stderr为有限诊断，不承担成功协议，也不输出输入/账户内容。
        from .strategy_host import _reason
        print("策略回测未完成：" + _reason(exc), file=sys.stderr, flush=True)
        raise SystemExit(2)
