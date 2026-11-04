"""已准入隔离BT的有限展示派生；WT资金事实与报告准入继续归原owner。"""
from __future__ import annotations

from decimal import Decimal
from fractions import Fraction
from hashlib import sha256
import json
import math
import re

from .strategy_session import _decimal
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


def build_performance(*, receipt, receipt_sha256, request, session, report, admitted, check):
    """归档传入已准入的原内层；原请求身份和逐记录公开投影分别保持。"""
    check()
    _require(admitted.record_count <= MAX_POINTS)
    initial = _fraction(session["policy"]["initial_capital_cny"])
    _require(initial > 0)
    initial_text = _money(initial)
    peak, drawdown, last, fees, available, last_date = initial, Fraction(0), None, None, 0, None
    points = []
    for index in range(admitted.record_count):
        check()
        record = project_session_record(admitted, index, check=check)["record"]
        capture = record["capture"]
        if capture is None:
            points.append([record["trading_date"], None])
            continue
        nav = _fraction(capture["basis"]["nav_cny"])
        fee = _fraction(capture["funds"]["fees"])
        _require(fee >= 0)
        points.append([record["trading_date"], _money(nav)])
        peak = max(peak, nav)
        drawdown = max(drawdown, (peak - nav) / peak * 100)
        last, fees, last_date, available = nav, fee, record["trading_date"], available + 1
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
            "total_return_pct": None if last is None else _percentage((last / initial - 1) * 100),
            "observed_max_drawdown_pct": None if last is None else _percentage(drawdown),
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
