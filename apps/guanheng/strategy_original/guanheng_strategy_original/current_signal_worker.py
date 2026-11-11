"""独立进程内构造日特征并调用原路由；只装载经过固定SHA核对的纯函数。"""

from __future__ import annotations

import ast
from datetime import date
import json
from pathlib import Path
import sys


def prepare(facts: dict, backend: Path) -> tuple[dict, dict]:
    """转换已验证的事实；返回原输入和来源/日期/折算诊断，不读取外部事实。"""
    from guanheng_strategy_original.reference import DAILY_FIELDS, SCHEMA, UPSTREAM_COMMIT
    from resonance.analysis.composite import analyze_single_etf, calc_composite_probability
    from resonance.analysis.factors import calc_direction_probability, calc_share_probability_dual, classify_signal
    from base.analysis.shares_adjust import detect_share_adjust, find_factor_jump, is_candidate

    # scheduler导入会连接store；只提取已核固定文件中的两个无外部依赖函数节点。
    tree = ast.parse((backend / "base/scheduler/recalc.py").read_text(encoding="utf-8"))
    pure = ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ("_t5_return", "_idx_t5_return")], type_ignores=[])
    if len(pure.body) != 2:
        raise ValueError("固定重算函数缺失")
    scope = {}
    exec(compile(pure, "fixed-original-recalc-functions", "exec"), scope)
    calendar = facts["calendar"]
    positions = {day: i for i, day in enumerate(calendar)}
    benchmark = {r["date"]: r for r in facts["analysis"]["000300"]["bars"]}
    share_map = {(r["code"], r["date"]): r["value"] / 1e8 if r["value"] is not None and r["unit"] == "share" else None for r in facts["shares"]}
    selected = set(facts["codes"]) | ({"510300"} if "159352" in facts["codes"] else set())
    daily, coverage, pair_unit_issues = {}, {}, []
    for code in sorted(selected):
        bars = facts["analysis"][code]["bars"]
        missing_index = [b["date"] for b in bars if b["date"] not in benchmark]
        # 缺基准时不填造0收益，原函数所需完整日期序列无法成立，独立保留该代码缺口。
        rows = []
        if not missing_index:
            index = [benchmark[b["date"]] for b in bars]
            for i in range(19, len(bars)):
                value = analyze_single_etf(bars[:i + 1], index[:i + 1], None, i)
                if value is None:
                    continue
                row = {field: value.get(field) for field in DAILY_FIELDS}
                row.update(code=code, **{field + "_price": value[field] for field in ("open", "high", "low", "close")})
                rows.append(row)
        share_rows = [{"date": b["date"], "shares_yi": share_map.get((code, b["date"])),
                       "shares_delta_yi": None, "shares_delta_pct": None, "share_prob": None,
                       "share_adjust": None} for b in bars]
        previous, previous_date, levels = None, None, []
        gaps = []
        for row in share_rows:
            current = row["shares_yi"]
            if current is None:
                continue
            if previous is not None and previous > 0:
                if positions[row["date"]] - positions[previous_date] == 1:
                    delta = round(current - previous, 4)
                    row["shares_delta_yi"] = delta
                    row["shares_delta_pct"] = round(delta / previous * 100, 3)
                    row["share_prob"] = calc_share_probability_dual(row["shares_delta_pct"], current, levels[-10:])
                else:
                    gaps.append([previous_date, row["date"]])
            previous, previous_date = current, row["date"]
            levels.append(current)
        raw_packet = facts["raw"].get(code, {})
        raw = {b["date"]: b for b in raw_packet.get("bars", [])}
        pair_units_qualified = (raw_packet.get("price_unit") == "CNY/share"
                                and facts["analysis"][code]["price_unit"] == "CNY/share")
        if not pair_units_qualified:
            pair_unit_issues.append("split_price_units_unqualified:" + code)
        historical = facts["profile"] == "historical-final-oracle"
        # 当前日因子必须同为已核ETF单价。历史对照显式保留研究单位假设，永不授信号资格。
        ratios = ([(b["date"], raw[b["date"]]["close"] / b["close"]) for b in bars if b["date"] in raw]
                  if pair_units_qualified or historical else [])
        ratio_map = dict(ratios)
        splits, unresolved = [], []
        for i in range(1, len(share_rows)):
            row = share_rows[i]
            if not is_candidate(row["shares_delta_pct"]):
                continue
            if facts["profile"] == "historical-final-oracle":
                pivot = date.fromisoformat(row["date"])
                window = [(d, value) for d, value in ratios if abs((date.fromisoformat(d) - pivot).days) <= 30]
            else:
                # 当前日事件仅使用当日及前交易日因子；未来条目已在父进程截止过滤。
                pair = [share_rows[i - 1]["date"], row["date"]]
                window = [(d, ratio_map[d]) for d in pair if d in ratio_map]
            jump = find_factor_jump(window)
            adjust = detect_share_adjust(share_rows[i - 1]["shares_yi"], row["shares_yi"], jump[0], jump[1]) if jump else None
            if len(window) < 2:
                unresolved.append(row["date"])
                if facts["profile"] == "causal-current":
                    row["share_prob"] = None
            if adjust is None:
                continue
            row["share_adjust"] = adjust.ratio
            row["shares_delta_yi"] = adjust.real_delta_yi
            row["shares_delta_pct"] = adjust.real_delta_pct
            splits.append({
                "date": row["date"],  # 模型识别的折算事件交易日，非公告首次可知时刻。
                "ratio": adjust.ratio,  # 折算后/前份额比例，无量纲。
                "basis": "validated-unit-pair" if pair_units_qualified else "historical-unit-assumption",  # 单位依据；假设不能称已核折算。
            })
            for j in range(i, min(len(share_rows), i + 11)):
                current = share_rows[j]
                if current["shares_yi"] is None:
                    continue
                rebased = []
                for k in range(max(0, j - 10), j):
                    value = share_rows[k]["shares_yi"]
                    if value is None:
                        continue
                    if facts["profile"] == "historical-final-oracle":
                        value *= adjust.ratio if k < i else 1
                    else:
                        # 连续折算将窗口归一到当前基准，实际份额存量保持原值。
                        for event in splits:
                            if share_rows[k]["date"] < event["date"] <= current["date"]:
                                value *= event["ratio"]
                    rebased.append(value)
                current["share_prob"] = calc_share_probability_dual(current["shares_delta_pct"], current["shares_yi"], rebased)
        share_dates = {r["date"]: r for r in share_rows}
        for row in rows:
            row.update({k: value for k, value in share_dates[row["date"]].items() if k != "date"})
        if facts["feature_stage"] == "recalc":
            for i, row in enumerate(rows):
                dp = calc_direction_probability(row["change_pct"] or 0, scope["_t5_return"](rows, i), scope["_idx_t5_return"](rows, i), row["volume_ratio"] or 0, row["idx_chg"] or 0, row["price_position"])
                row["dir_prob"] = dp
                row["composite_prob"] = calc_composite_probability(row["vol_prob"], dp, row["share_prob"], row["price_position"])
                row["signal_level"] = classify_signal(row["composite_prob"])
        daily[code] = rows
        coverage[code] = {
            "source_bars": len(bars),  # 截止过滤后输入行情条数，包含前19条价格预热。
            "derived_rows": len(rows),  # 实际生成原DAILY_FIELDS条数，零表示未能重建。
            "missing_benchmark_dates": missing_index,  # ETF日期中缺000300的交易日，不以零收益替代。
            "share_gap_intervals": gaps,  # 两个已知份额日之间跨越缺失交易日的区间，不视作单日流入。
            "split_events": splits,  # 模型折算判定及单位依据；历史假设单独标识。
            "unresolved_split_dates": unresolved,  # 大幅份额变动缺少可消费因子对的日期。
            "today_present": bool(rows and rows[-1]["date"] == facts["decision_date"]),  # 决策日是否确有派生行。
            "today_share_present": share_map.get((code, facts["decision_date"])) is not None,  # 决策日已知且单位可转换的份额是否存在。
            "ma250_full_rows": max(0, len(rows) - 249),  # 可完整形成MA250的派生行数，仅窗口诊断。
            "ma250_plus20_full_rows": max(0, len(rows) - 269),  # MA250与20行前MA250均完整的行数，非统一准入门槛。
            "factor_pair": {
                "raw_price_unit": raw_packet.get("price_unit"),  # 原价单位，null表示缺少该来源包。
                "analysis_price_unit": facts["analysis"][code]["price_unit"],  # 前复权价格单位，unknown不能证明同维度。
                "units_qualified": pair_units_qualified,  # 两价均已声明CNY/share才为true。
                "historical_unit_assumption": historical and not pair_units_qualified and bool(ratios),  # 仅历史对照实际使用的单位假设。
            },
        }
    turnover = [{"date": row["date"], "total_amount_yi": row["value"] / 1e8 if row["value"] is not None and row["unit"] == "CNY" else None} for row in facts["turnover"]]
    margin = [{"date": row["date"], "fin_balance_yi": row["value"] / 1e8 if row["value"] is not None and row["unit"] == "CNY" else None} for row in facts["margin"]]
    reasons = list(pair_unit_issues)
    versions = {facts["analysis"][c]["factor_version"] for c in selected | {"000300"}}
    if len(versions) != 1:
        reasons.append("front_reference_mismatch")
    for code in sorted(selected | {"000300"}):
        packet = facts["analysis"][code]
        expected = "index-point" if code == "000300" else "CNY/share"
        if packet["price_unit"] != expected or packet["volume_unit"] == "unknown":
            reasons.append("quote_units_unknown:" + code)
    for code in facts["codes"]:
        if not coverage[code]["today_present"]:
            reasons.append("today_features_missing:" + code)
        if not coverage[code]["today_share_present"]:
            reasons.append("today_shares_missing:" + code)
        if coverage[code]["unresolved_split_dates"]:
            reasons.append("split_unresolved:" + code)
    for name, rows, field in (("turnover", turnover, "total_amount_yi"), ("margin", margin, "fin_balance_yi")):
        if not any(r["date"] == facts["decision_date"] and r[field] is not None for r in rows):
            reasons.append("today_" + name + "_missing")
    for name in ("shares", "turnover", "margin"):
        if any(row["unit"] == "unknown" for row in facts[name]):
            reasons.append(name + "_units_unknown")
    snapshot = {
        "schema": SCHEMA,  # 原纯路由输入格式，既有接口保持。
        "upstream_commit": UPSTREAM_COMMIT,  # 唯一数学源码身份。
        "data_kind": "historical-final",  # 原协议仅含此类真实数据；PIT资格由新输出另列。
        "source": {
            "description": facts["description"],  # 调用方冻结的来源说明。
            "snapshot_id": facts["snapshot_id"],  # 本次WT发布快照SHA。
            "profile": facts["profile"],  # 当前因果或历史对照处理身份。
            "feature_stage": "aligned-seed-share-split-" + facts["feature_stage"],  # 方向评分seed/recalc口径。
            "units_qualified": not any("units_unknown" in r for r in reasons) and not pair_unit_issues,  # 来源单位证明与目标协议单位分别表达。
            "historical_available_at": None,  # 原事实历史首次可知时刻仍未知。
            "price_basis": "explicit-source-front-ratio",  # 价格基准沿显式供应商前复权包。
            "alignment": "exact-trade-date",  # ETF与000300按交易日关联。
            "market_turnover_model": next((r["kind"] for r in facts["turnover"]), "missing"),  # 官方/proxy/缺失单一模型身份。
            "split_policy": "event-adjacent-causal" if facts["profile"] == "causal-current" else "historical-final-plus-minus30-calendar-days",  # 折算窗口和因果约束。
            "split_unit_assumptions": [code for code in coverage if coverage[code]["factor_pair"]["historical_unit_assumption"]],  # 仅历史对照采用单位假设的证券，不能升级资格。
            "diagnostic_reasons": reasons,  # 未满足输入合同的有限原因码，不含外部原文。
        },
        "units": {"price": "CNY/share", "volume": "upstream-source-unit", "shares": "1e8-share", "market": "1e8-CNY"},  # 原目标协议；来源资格单独记录。
        "codes": list(facts["codes"]),  # 显式策略集合，参考证券可另在daily。
        "daily": daily,  # 所有可重建预热行，缺基准代码保持空序列。
        "turnover": turnover,  # 官方或proxy单一模型；未知单位不除以1e8假冒亿元。
        "margin": margin,  # 供应商原融资报表亿元，与账户融资分开。
        "calendar": calendar,  # 决策日之前的已提供交易日。
        "evaluation_start": max(calendar[0], "2021-01-01"),  # 原组合协议起点；路由仍使用更早完整前缀。
    }
    return snapshot, {
        "coverage": coverage,  # 每代码来源/派生/预热/折算诊断，非账户覆盖。
        "reasons": reasons,  # 阻止授予signal_qualified的输入合同原因。
        "excluded": facts["excluded"],  # 未来交易日及截止后收到事实的输入行数。
    }


def compute(payload: dict, backend: Path) -> dict:
    from guanheng_strategy_original.reference import ALGORITHM_ID, UPSTREAM_COMMIT, digest, validate_snapshot
    from guanheng_strategy_original.worker import evaluate
    facts = payload["facts"]
    snapshot, diagnostics = prepare(facts, backend)
    validate_snapshot(snapshot)
    from guanheng_strategy_original.reference_labels import prepare_nullable_reason_labels
    prepare_nullable_reason_labels(backend)
    # 参考函数要求各code非空。数据不足返回完整缺口；不能静默缩成另一证券组合。
    confirmation_backend = backend if payload.get("confirmation") else None
    options = {}
    if confirmation_backend is not None:
        history = {code: facts["analysis"][code]["bars"] for code in snapshot["codes"]}
        options = dict(confirmation_backend=backend, confirmation_history=history)
    report = evaluate(snapshot, **options) if all(snapshot["daily"].get(c) for c in snapshot["codes"]) else None
    today, states = {}, {}
    for code in snapshot["codes"]:
        trades = report["strategy_results"][code]["trades"] if report is not None else []
        today[code] = [r for r in trades if r["date"] == facts["decision_date"]]
        last = trades[-1] if trades else None
        held = report["strategy_results"][code].get("holding", last["action"] == "BUY" if last else False) if report is not None else None
        states[code] = {
            "held": held,  # 原路由模型持仓bool；report=null时为null，未声明账户实际持仓。
            "last_signal": last,  # 原前缀最后信号；无信号或无报告时null，非券商成交。
            "through_date": snapshot["daily"][code][-1]["date"] if snapshot["daily"][code] else None,  # 最后特征交易日，非账户观察时刻；无行时null。
        }
    return {
        "schema": "guanheng.original-current-signal.v1",  # 当前日纯计算协议。
        "algorithm_id": ALGORITHM_ID,  # 固定原stable路由，非独立公开策略。
        "upstream_commit": UPSTREAM_COMMIT,  # 用户提供源码的核验身份。
        "facts_sha256": payload["facts_sha256"],  # 完整输入原件含被过滤事实的摘要。
        "manifest_sha256": payload["manifest_sha256"],  # 原路由与新特征纯函数清单绑定。
        "prepared_sha256": digest(snapshot),  # 全部派生日线和辅助序列的内容摘要。
        "decision_date": facts["decision_date"],  # 本次信号交易日。
        "decision_at": facts["decision_at"],  # 已收到/已发布事实的截止时刻，含时区。
        "profile": facts["profile"],  # 当前因果或历史最终对照。
        "source_provenance": {
            "quotes": {kind: {code: {k: v for k, v in packet.items() if k != "bars"} for code, packet in facts[kind].items()} for kind in ("analysis", "raw")},  # 行情原件/单位/收到时刻；字段沿输入行情包合同。
            "auxiliary_parents": {kind: sorted({row["source_sha256"] for row in facts[kind]}) for kind in ("shares", "turnover", "margin")},  # 辅助事实原件集合；每行日期/时刻沿facts_sha256绑定。
        },  # 源证明只绑定调用方已核原件，不重新读取ContentStore。
        "prepared_snapshot": snapshot,  # DAILY_FIELDS完整前缀，可独立差分原参考入口。
        "reference_report": report,  # 原路由完整报告；数据不足则null，不改算法默认值。
        "signals_today": today,  # 原信号记录，与真实委托/成交分开。
        "model_state": states,  # 最后原BUY/SELL所示模型持仓，未声明账户归属。
        "diagnostics": diagnostics,  # 缺失/排除/折算/窗口诊断，消费者据此决策。
        "signal_qualified": facts["profile"] == "causal-current" and not diagnostics["reasons"] and report is not None,  # 仅本输入合同，不代表执行/PIT通过。
        "execution_qualified": False,  # 纯计算没有金融执行资格。
        "point_in_time_qualified": False,  # 首次可知及历史修订完整性仍未证明。
    }


def main() -> int:
    backend, inp, out = map(Path, sys.argv[1:])
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    sys.path.insert(0, str(backend))
    try:
        payload = json.loads(inp.read_bytes())
        result = compute(payload, backend)
        out.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False), encoding="utf-8")
    except Exception:
        # 外部输入可能含受控事实；父进程只报告固定失败，子进程也不输出原文。
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
