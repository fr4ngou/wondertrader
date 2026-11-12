"""已准入隔离BT的有限展示派生；WT资金事实与报告准入继续归原owner。"""
from __future__ import annotations

from decimal import Decimal
from fractions import Fraction
from hashlib import sha256
import json
import math
import re

from .strategy_session import _decimal, _unpack_record, MAX_EXPANDED_REPORT_BYTES
from .backtest_reports import project_session_record, RETAINED_REPORT_SCHEMAS, PER_DATE_REPORT_SCHEMA


SCHEMA = "nbw-performance-v1"
COMPARISON_SCHEMA = "nbw-comparison-v1"
MAX_POINTS = 4096
MAX_RESPONSE = 512 * 1024
_NUMBER = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE]([+-]?[0-9]+))?\Z")
_ERROR = "归档绩效超出有限展示范围，请保留原报告并核查"


def _require(value):
    if not value:
        raise ValueError(_ERROR)


def _fraction(value):
    """仅解析有限有界十进制；不通过浮点参与金融计算。"""
    if type(value) in (int, float):
        _require(value.bit_length() <= 4096 if type(value) is int else math.isfinite(value))
        value = repr(value)
    _require(type(value) is str and 0 < len(value) <= 512)
    matched = _NUMBER.fullmatch(value)
    _require(matched is not None and (matched.group(1) is None or abs(int(matched.group(1))) <= 512))
    result = Fraction(Decimal(value))
    _require(max(result.numerator.bit_length(), result.denominator.bit_length()) <= 4096)
    return result


def _money(value):
    result = _decimal(value)
    _require(len(result) <= 512)
    number = float(result)
    _require(math.isfinite(number) and (not value or number != 0))
    return result


def _percentage(value):
    try:
        number = float(value)
        return number if math.isfinite(number) and (not value or number != 0) else None
    except (ValueError, OverflowError):
        return None


def _hash(value, check):
    check()
    raw = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("ascii")
    check()
    return sha256(raw).hexdigest()


def _position_point(day, nav, cash_value):
    """同日原估值的持仓占比、市值及现金；缺值或无可用长仓估值时保留空点。"""
    if nav > 0 and cash_value is not None:
        cash = _fraction(cash_value)
        market = nav - cash
        if market >= 0:
            ratio = _percentage(market / nav * 100)
            if ratio is not None:
                return [day, ratio, _money(market), _money(cash)]
    return [day, None, None, None]


def _nav_metrics(initial, navs):
    """从原日末净值精确计算，首个峰值为初始本金，缺值不参与运算。"""
    peak, drawdown, last = initial, Fraction(0), None
    for nav in navs:
        if nav is not None:
            peak = max(peak, nav)
            drawdown = max(drawdown, (peak - nav) / peak * 100)
            last = nav
    return {
        "total_return_pct": None if last is None else _percentage((last / initial - 1) * 100),
        "observed_max_drawdown_pct": None if last is None else _percentage(drawdown),
    }


def build_performance_preview(report, initial, *, check, packed):
    """只读完成证明绑定的日末值，保留分段极值和缺口；完整分析另行准入。"""
    records = report["records"]
    _require(len(records) <= MAX_POINTS)
    navs = []
    expanded = 0
    for record in records:
        check()
        if packed:
            expanded += record["payload_bytes"]
            _require(expanded <= MAX_EXPANDED_REPORT_BYTES)
            record = _unpack_record(record, check=check)
        capture = record["capture"]
        navs.append(None if capture is None else _fraction(capture["basis"]["nav_cny"]))

    metrics = _nav_metrics(initial, navs)
    returns = [_percentage((nav / initial - 1) * 100) if nav is not None else None for nav in navs]
    valid = [index for index, value in enumerate(returns) if value is not None]
    if not valid:
        return {**metrics, "points": []}

    samples = {valid[0], valid[-1]}
    # 每段最多两个极值，另保留首末；相邻样本间有缺值就增加一个断点。
    buckets = 11
    stride = max(1, (len(returns) + buckets - 1) // buckets)
    for start in range(0, len(returns), stride):
        observed = [index for index in range(start, min(start + stride, len(returns))) if returns[index] is not None]
        if observed:
            samples.add(min(observed, key=returns.__getitem__))
            samples.add(max(observed, key=returns.__getitem__))
    ordered = sorted(samples)
    for left, right in zip(ordered, ordered[1:]):
        missing = next((index for index in range(left + 1, right) if returns[index] is None), None)
        if missing is not None:
            samples.add(missing)
    return {**metrics, "points": [[index, returns[index]] for index in sorted(samples)]}


def build_performance(*, receipt, receipt_sha256, request, session, report, admitted, check, position_points=None):
    """从已准入记录读取绩效；visuals 同轮收集日末仓位，保持原绩效响应契约。"""
    check()
    _require(admitted.record_count <= MAX_POINTS)
    initial = _fraction(session["policy"]["initial_capital_cny"])
    _require(initial > 0)
    initial_text = _money(initial)
    last, fees, available, last_date = None, None, 0, None
    points, navs = [], []
    for index in range(admitted.record_count):
        check()
        record = project_session_record(admitted, index, check=check)["record"]
        day = record["trading_date"]
        capture = record["capture"]
        if capture is None:
            points.append([day, None])
            navs.append(None)
            if position_points is not None:
                position_points.append([day, None, None, None])
            continue
        basis = capture["basis"]
        nav = _fraction(basis["nav_cny"])
        fee = _fraction(capture["funds"]["fees"])
        _require(fee >= 0)
        points.append([day, _money(nav)])
        if position_points is not None:
            position_points.append(_position_point(day, nav, basis.get("cash_cny")))
        navs.append(nav)
        last, fees, last_date, available = nav, fee, day, available + 1
    retained = report['schema'] in RETAINED_REPORT_SCHEMAS
    algorithm=None
    if retained:
        # 算法身份优先复制该归档实际NSQ目标；全程预热尚无目标时保持未知。
        algorithm=next(((row.get('outcome')or{}).get('state',{}).get('target',{}).get('algorithm_id')
            for row in report['records']if (row.get('outcome')or{}).get('state')),None)
    strategy = ({'strategy_id':report['strategy_id'],'strategy_version':report['strategy_version'],
        'algorithm_id':algorithm,**session['request']['configuration']}if retained else session.get('strategy',session.get('config')))
    _require(type(strategy) is dict)
    response = {"schema": SCHEMA, "run_id": receipt["run_id"], "request_id": receipt["request_id"],
        "receipt_sha256": receipt_sha256, "request_sha256": receipt["request_sha256"],
        "report_sha256": receipt["report_sha256"], "installation_sha256": receipt["installation_sha256"],
        "session_sha256": request["session_sha256"], "session_id": report["session_id"], "report_schema": report["schema"],
        "configuration": dict(receipt["configuration"]),
        "strategy": {"id": strategy["strategy_id"], "version": strategy["strategy_version"], "algorithm_id": strategy.get("algorithm_id")},
        "input": {"history_sha256": _hash({'history': session['request']['history'],
            'analysis': session['request']['analysis'], 'current_view': session['request']['current_view'],
            'historical_model': session['model'],
            **({'per_date_source': report['per_date_source']} if report['schema'] == PER_DATE_REPORT_SCHEMA else {})
            } if retained else session["history"], check), "market_manifest_source": session["market_manifest_source"],
            "capital_source": session["policy"]["capital_source"], "fee_reserve_cny": session["fee_reserve_cny"],
            "fee_source": session["fee_source"], "policy_sha256": _hash(session["policy"], check),
            "configuration_sha256": _hash(strategy, check)},
        "metrics": {"initial_capital_cny": initial_text, "last_nav_cny": None if last is None else _money(last),
            **_nav_metrics(initial, navs),
            "native_cumulative_fees_cny": None if fees is None else _money(fees)},
        "observations": {"total": admitted.record_count, "available": available, "missing": admitted.record_count - available,
            "last_trading_date": last_date}, "points": points, "scope": report["scope"]}
    check()
    return response


def build_comparison(left, right, scope):
    """只比较可见输入身份和条件；收益差异本身不成为条件差异。"""
    differences = []
    if tuple(left["configuration"][key] for key in ("start", "end")) != tuple(right["configuration"][key] for key in ("start", "end")):
        differences.append("window")
    if _fraction(left["metrics"]["initial_capital_cny"]) != _fraction(right["metrics"]["initial_capital_cny"]):
        differences.append("initial_capital")
    if any(left["input"][key] != right["input"][key] for key in ("history_sha256", "market_manifest_source", "capital_source")):
        differences.append("input")
    if left["strategy"] != right["strategy"]:
        differences.append("strategy")
    if left["input"]["configuration_sha256"] != right["input"]["configuration_sha256"]:
        differences.append("configuration")
    if (left["report_schema"], left["strategy"]["algorithm_id"], left["input"]["policy_sha256"]) != (right["report_schema"], right["strategy"]["algorithm_id"], right["input"]["policy_sha256"]):
        differences.append("model")
    if any(left["input"][key] != right["input"][key] for key in ("fee_reserve_cny", "fee_source")):
        differences.append("fees")
    return {"schema": COMPARISON_SCHEMA, "left": left, "right": right, "differences": differences, "scope": scope}
