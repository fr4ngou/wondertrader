"""仅供独立子进程使用的固定源码接缝；不导入上游API、store或scheduler。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _data_audit(snapshot: dict, factors, composite) -> dict:
    """检查足够预热后的可重建字段；历史原始价/首次可知信息保持未知。"""
    coverage = {}
    checks = {}

    def compare(field: str, actual, expected, tolerance: float = 1e-8) -> None:
        stat = checks.setdefault(field, {"checked": 0, "mismatches": 0})
        if actual is None or expected is None:
            return
        stat["checked"] += 1
        if isinstance(actual, str):
            stat["mismatches"] += actual != expected
        else:
            stat["mismatches"] += abs(actual - expected) > tolerance

    for code, rows in snapshot["daily"].items():
        fields = ("open_price", "high_price", "low_price", "close_price", "volume", "volume_ma20", "volume_ratio",
                  "price_position", "share_prob", "shares_yi", "shares_delta_yi", "shares_delta_pct",
                  "idx_chg", "vol_prob", "dir_prob", "composite_prob", "trade_direction", "signal_level")
        dates = {r["date"] for r in rows}
        gaps = [d for d in snapshot["calendar"] if rows and rows[0]["date"] <= d <= rows[-1]["date"] and d not in dates]
        coverage[code] = {
            "rows": len(rows), "first": rows[0]["date"] if rows else None, "last": rows[-1]["date"] if rows else None,
            "missing": {field: sum(r[field] is None for r in rows) for field in fields},
            "calendar_gap_count": len(gaps), "calendar_gap_sample": gaps[:10],
            "pre_evaluation_rows": sum(r["date"] < snapshot["evaluation_start"] for r in rows),
            "long_window_diagnostic": {"available_rows": len(rows), "ma250_full_rows": max(0, len(rows) - 249),
                                       "ma250_and_20_prior_full_rows": max(0, len(rows) - 269),
                                       "pre_evaluation_below_270": sum(r["date"] < snapshot["evaluation_start"] for r in rows) < 270,
                                       "rule": "原各策略预热规则仍按其源码，270仅为长均线及20条斜率的诊断参考"},
        }
        for i, row in enumerate(rows):
            if i >= 19:
                win = rows[i - 19:i + 1]
                if all(r["volume"] is not None for r in win):
                    mean = sum(r["volume"] for r in win) / 20
                    compare("volume_ma20", row["volume_ma20"], round(mean, 2))
                    if mean > 0:
                        ratio = row["volume"] / mean
                        compare("volume_ratio", row["volume_ratio"], round(ratio, 3))
                        compare("vol_prob", row["vol_prob"], round(factors.calc_volume_probability(ratio), 1))
                        compare("trade_direction", row["trade_direction"], factors.classify_trade_direction(row["price_position"], ratio))
            if i >= 59 and row["close_price"] is not None:
                win = rows[i - 59:i + 1]
                if all(r["high_price"] is not None and r["low_price"] is not None for r in win):
                    bars = [{"high": r["high_price"], "low": r["low_price"], "close": r["close_price"]} for r in win]
                    compare("price_position", row["price_position"], factors.calc_price_position(bars, 59))
            if row["vol_prob"] is not None and row["dir_prob"] is not None:
                cp = composite.calc_composite_probability(row["vol_prob"], row["dir_prob"], row["share_prob"], row["price_position"])
                compare("composite_from_stored_components", row["composite_prob"], cp)
            # 原recalc用收盘涨幅及idx_chg复合重建，和seed的日内涨幅口径分别呈现。
            if i >= 4 and row["change_pct"] is not None and all(r["close_price"] for r in rows[i - 4:i + 1]):
                recent = rows[i - 3:i + 1]
                if all(r["idx_chg"] is not None for r in recent):
                    index_factor = 1.0
                    for r in recent:
                        index_factor *= 1 + r["idx_chg"] / 100
                    dp = factors.calc_direction_probability(
                        row["change_pct"], (row["close_price"] / rows[i - 4]["close_price"] - 1) * 100,
                        (index_factor - 1) * 100, row["volume_ratio"] or 0, row["idx_chg"] or 0, row["price_position"],
                    )
                    compare("direction_recalc_profile", row["dir_prob"], dp)
            if i >= 10 and row["shares_delta_pct"] is not None:
                previous = rows[i - 10:i]
                if all(r["shares_yi"] is not None for r in previous) and not any(r["share_adjust"] not in (None, 1) for r in rows[i - 10:i + 1]):
                    sp = factors.calc_share_probability_dual(row["shares_delta_pct"], row["shares_yi"], [r["shares_yi"] for r in previous])
                    compare("share_probability_no_recent_split", row["share_prob"], sp)
    market = {}
    for name, field in (("turnover", "total_amount_yi"), ("margin", "fin_balance_yi")):
        series = snapshot[name]
        known = {r["date"] for r in series if r.get(field) is not None}
        selected_dates = {r["date"] for code in snapshot["codes"] for r in snapshot["daily"][code]}
        market[name] = {"rows": len(series), "nonnull": len(known),
                        "missing_selected_dates": len(selected_dates - known),
                        "first": series[0]["date"] if series else None, "last": series[-1]["date"] if series else None}
    return {
        "coverage": coverage, "derived_checks": checks,
        "market_coverage": market,
        "qualification": "diagnostic-only",
        "limits": ["原库缺少历史首次发布时刻", "存量行前部缺少原始预热K线时跳过相应计算",
                   "seed与recalc方向口径存在差异，recalc不匹配不自动修改存量行",
                   "seed用未舍入VP计算CP，使用存量舍入VP回算CP可能相差一个显示精度",
                   "折算附近份额概率待原始因子事件核对", "价格复权和来源真实性需要原件核对"],
    }


def evaluate(snapshot: dict, *, confirmation_backend: Path | None = None, confirmation_history=None) -> dict:
    """按照固定portfolio/API相同纯函数和日期约定回放，原结果完整保留。"""
    from base.analysis.sentiment.core import enrich_turnover, percentile_series, turnover_value
    from base.analysis.strategy.router import compute_trades
    from base.config import ETFS, SENTIMENT_ZONE_MIN_PTS, SENTIMENT_ZONE_WINDOW
    from portfolio.analysis.simulator import simulate
    from resonance.analysis import composite, factors
    from resonance.analysis.core import compute_resonance

    daily, codes = snapshot["daily"], snapshot["codes"]
    if confirmation_backend is not None:
        from guanheng_strategy_original import kc50_confirmation as confirmation
        from base.analysis.strategy.hs300 import run_hs300_strategy

        codes = confirmation.CODES
        daily = dict(confirmation.lagged_features(daily, snapshot["calendar"]))
        main_days = [r["date"] for r in daily["510300"]]
        start_day = snapshot["evaluation_start"]
        warmup = next(day for day in main_days if day >= start_day)
        history = {code: [row for row in confirmation_history[code] if row["date"] >= warmup] for code in codes}
        market = dict(confirmation.market_state(history, [day for day in snapshot["calendar"] if day >= warmup]))
    if any(code not in ETFS for code in daily):
        raise ValueError("上游监控集合中没有该证券")
    for code in codes:
        if not daily[code]:
            raise ValueError("选定证券日线为空")
        reference = {"159352": "510300", "588200": "588000"}.get(code)
        if reference and not daily.get(reference):
            raise ValueError("跨证券策略参考日线缺失")
    turnover = enrich_turnover(snapshot["turnover"])
    margin = snapshot["margin"]
    tp = percentile_series([r["date"] for r in turnover], [turnover_value(r) for r in turnover], SENTIMENT_ZONE_WINDOW, SENTIMENT_ZONE_MIN_PTS)
    mp = percentile_series([r["date"] for r in margin], [r["fin_balance_yi"] for r in margin], SENTIMENT_ZONE_WINDOW, SENTIMENT_ZONE_MIN_PTS)
    results, lights, trades = {}, {}, {}
    start = snapshot["evaluation_start"]
    for code in codes:
        if confirmation_backend is not None and code == "588000":
            results[code] = confirmation.evaluate_kc50(confirmation_backend, daily[code], market, tp, mp)
        elif confirmation_backend is not None and code == "159352":
            results[code] = dict(run_hs300_strategy(daily[code]), code=code)
        else:
            results[code] = compute_trades(code, daily[code], t_pct=tp, m_pct=mp,
                                          hs300_rows=daily.get("510300"), kc50_rows=daily.get("588000"), version="stable")
        trades[code] = [t for t in results[code]["trades"] if t["date"] >= start]
        lights[code] = compute_resonance(code, daily[code], turnover, margin)
    price_map = {code: {r["date"]: r["close_price"] for r in daily[code] if r["close_price"] is not None} for code in codes}
    for code in codes:
        for trade in trades[code]:
            price_map[code].setdefault(trade["date"], trade["price"])
    end = max((d for prices in price_map.values() for d in prices), default=None)
    dates = [d for d in snapshot["calendar"] if start <= d and (end is None or d <= end)]
    if confirmation_backend is not None:
        dates = dates[1:]  # 首个评价交易日用作 WT 原生日线暖机，不在该日生成目标。
        if not dates:
            raise ValueError("收复确认缺少暖机后评价日")
        trades = {code: [trade for trade in signals if trade["date"] >= dates[0]] for code, signals in trades.items()}
    fallback = not dates
    if fallback:
        dates = sorted({d for prices in price_map.values() for d in prices})
    portfolio = simulate(trades, price_map, dates)
    audit = _data_audit(snapshot, factors, composite)
    audit["market_percentile_coverage"] = {"turnover_dates": len(tp), "margin_dates": len(mp)}
    audit["signal_duplicates"] = {code: len(items) - len({(t["date"], t["action"]) for t in items}) for code, items in trades.items()}
    variant = ({confirmation.REFERENCE_FIELD: True} if confirmation_backend is not None else {})
    return {
        **variant,  # 显式独立策略模型，WT按此校验回放身份。
        "schema": "guanheng.resonance-original-report.v1",  # 独立报告协议，与原WT报告族分开。
        "algorithm_id": "resonance-original-351f9d5-stable",  # 唯一参考算法身份。
        "upstream_commit": "351f9d58152e10efd2447c997b8ee4db66b5ac6a",  # 上游固定提交。
        "input_sha256": hashlib.sha256(_canonical(snapshot)).hexdigest(),  # 完整冻结JSON内容摘要。
        "data_kind": snapshot["data_kind"],  # 合成/历史最终行声明，不提升来源资格。
        "source": snapshot["source"],  # 来源与采集、复权、未知可知时刻的原说明。
        "execution_qualified": False,  # 本入口不具备交易执行资格。
        "point_in_time_qualified": False,  # 原库没有证明完整历史首次可知时间。
        "strategy_results": results,  # 全预热历史的原算法结果，保留上游返回结构。
        "trades_by_code": trades,  # 裁剪到评价起点后的原信号；并非实际成交。
        "resonance": lights,  # 独立五灯结果，不把灯数当作专属买卖算法。
        "turnover_percentiles": tp,  # MA5优先成交额的原滚动分位数，百分数。
        "margin_percentiles": mp,  # 原融资余额的滚动分位数，百分数。
        "portfolio": portfolio,  # 原次日收盘浮点份额组合，归一化初值1.0。
        "data_audit": audit,  # 缺失、预热、日期及派生值核对，保留检查限制。
        "model": {"signal_version": "stable", "execution": "next-trading-day-close", "fees": 0,
                  "fractional_shares": True, "allocation": "new-buy-equal-weight-full-equity",
                  "sell_rebalance": False, "calendar_fallback": fallback,
                  "historical_features": "as-stored-final-rows", "initial_equity": 1.0,
                  "historical_availability": "unknown", "warmup": "original-function-behaviour",
                  "prefix_stability": "not-guaranteed-by-upstream-minimum-length-guards"},
    }


def main() -> int:
    source, input_path, output_path = map(Path, sys.argv[1:])
    sys.path.insert(0, str(source))
    try:
        report = evaluate(json.loads(input_path.read_text(encoding="utf-8")))
        output_path.write_bytes(_canonical(report))
    except Exception as exc:
        output_path.write_bytes(_canonical({"error_type": type(exc).__name__}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
