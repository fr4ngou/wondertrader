"""原事实→固定特征→当天信号的实际子进程及因果边界；样本完全合成。"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
import json
import os
from pathlib import Path
import shutil
import sys

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "apps/guanheng/strategy_original"))
from guanheng_strategy_original.current_signal import build_current_signal, normalize_facts
from guanheng_strategy_original.reference import DAILY_FIELDS, digest


@pytest.fixture
def source():
    path = Path(os.environ.get("RESONANCE_ORIGINAL_SOURCE", str(ROOT / "research/resonance-20261105/upstream-resonance")))
    if not (path / "backend/base/analysis/strategy/router.py").is_file():
        pytest.skip("原源码由用户显式提供，不随测试再发行")
    return path


@pytest.fixture
def facts():
    days, current = [], date(2026, 9, 1)
    while len(days) < 40:
        if current.weekday() < 5:
            days.append(current.isoformat())
        current += timedelta(days=1)
    identity = {"source_sha256": "a" * 64, "received_at": "2026-10-26T09:00:00+00:00", "available_at": None}
    result = {"schema": "guanheng.original-current-facts.v1", "profile": "causal-current", "feature_stage": "recalc",
              "decision_date": days[-1], "decision_at": "2026-10-26T10:00:00+00:00", "snapshot_id": "b" * 64,
              "description": "合成常价递增成交量和份额，非真实市场数据", "codes": ["510300"], "calendar": days,
              "analysis": {}, "raw": {}, "shares": [], "turnover": [], "margin": []}
    for kind in ("analysis", "raw"):
        for code in ("510300", "000300"):
            result[kind][code] = {**identity, "price_unit": "index-point" if code == "000300" else "CNY/share",
                                  "volume_unit": "share", "price_basis": "front_ratio" if kind == "analysis" else "none",
                                  "factor_version": "synthetic-same-reference" if kind == "analysis" else "",
                                  "bars": [{"date": day, "open": 1., "close": 1., "high": 1.2, "low": .8, "volume": 100 + i} for i, day in enumerate(days)]}
    for i, day in enumerate(days):
        result["shares"].append({**identity, "date": day, "code": "510300", "value": 100000000 + i * 1000000, "unit": "share"})
        result["turnover"].append({**identity, "date": day, "value": "456000000000", "unit": "CNY", "kind": "official"})
        result["margin"].append({**identity, "date": day, "value": "789000000000", "unit": "CNY"})
    return result


def test_actual_feature_signal_chain_and_manual_values(source, facts, tmp_path):
    before = deepcopy(facts)
    result = build_current_signal(source, facts, work_directory=tmp_path)
    assert facts == before
    assert result["facts_sha256"] == digest(facts)
    assert result["prepared_sha256"] == digest(result["prepared_snapshot"])
    rows = result["prepared_snapshot"]["daily"]["510300"]
    assert len(rows) == 21 and set(rows[0]) == set(DAILY_FIELDS)
    # 首个派生日对应第20条源行；首19条份额实际参与均值，未被价格暖机裁掉。
    assert rows[0]["volume_ma20"] == 109.5
    assert rows[0]["volume_ratio"] == round(119 / 109.5, 3)
    assert rows[0]["price_position"] == 50
    assert rows[0]["shares_yi"] == 1.19
    assert rows[0]["shares_delta_yi"] == .01
    assert rows[0]["shares_delta_pct"] == round(.01 / 1.18 * 100, 3)
    assert result["prepared_snapshot"]["turnover"][-1]["total_amount_yi"] == 4560
    assert result["signals_today"]["510300"] == [r for r in result["reference_report"]["trades_by_code"]["510300"] if r["date"] == facts["decision_date"]]
    assert result["signal_qualified"] is True
    assert result["execution_qualified"] is False and result["point_in_time_qualified"] is False
    assert list(tmp_path.iterdir()) == []


def test_late_and_future_facts_cannot_enter_decision(source, facts, tmp_path):
    packet = facts["analysis"]["510300"]
    packet["received_at"] = "2026-10-27T00:00:00+00:00"
    facts["shares"][-1]["available_at"] = "2026-10-27T00:00:00+00:00"
    normal = normalize_facts(facts)
    assert normal["analysis"]["510300"]["bars"] == []
    result = build_current_signal(source, facts, work_directory=tmp_path)
    assert result["reference_report"] is None and result["signal_qualified"] is False
    assert result["model_state"]["510300"]["held"] is None
    assert result["diagnostics"]["excluded"]["after_cutoff"] == 41


def test_future_price_ignored_and_historical_profile_clock_explicit(source, facts, tmp_path):
    facts["decision_date"] = facts["calendar"][-2]
    result = build_current_signal(source, facts, work_directory=tmp_path)
    assert result["prepared_snapshot"]["daily"]["510300"][-1]["date"] == facts["decision_date"]
    assert result["diagnostics"]["excluded"]["future_date"] == 7
    facts["profile"] = "historical-final-oracle"
    facts["decision_at"] = "2026-10-01T00:00:00+00:00"
    oracle = build_current_signal(source, facts, work_directory=tmp_path)
    assert oracle["profile"] == "historical-final-oracle" and oracle["signal_qualified"] is False
    assert len(oracle["prepared_snapshot"]["daily"]["510300"]) == 20


def test_missing_share_and_unknown_units_remain_missing(source, facts, tmp_path):
    facts["shares"][-2]["value"] = None
    facts["turnover"][-1]["unit"] = "unknown"
    facts["analysis"]["510300"]["price_unit"] = "unknown"
    result = build_current_signal(source, facts, work_directory=tmp_path)
    row = result["prepared_snapshot"]["daily"]["510300"][-1]
    assert row["shares_delta_yi"] is None and row["share_prob"] is None
    assert result["prepared_snapshot"]["turnover"][-1]["total_amount_yi"] is None
    assert result["signal_qualified"] is False
    assert "quote_units_unknown:510300" in result["diagnostics"]["reasons"]


def test_causal_split_cannot_borrow_future_jump(source, facts, tmp_path):
    # 第30条份额翻倍，第31条才出现价格因子跳变：当前因果口径保留真实发生日期。
    for i in range(29, 40):
        facts["shares"][i]["value"] = 2 * (100000000 + i * 1000000)
    for i in range(30, 40):
        facts["raw"]["510300"]["bars"][i].update(open=.5, close=.5, high=.6, low=.4)
    causal = build_current_signal(source, facts, work_directory=tmp_path)
    assert causal["diagnostics"]["coverage"]["510300"]["split_events"] == []
    facts["profile"] = "historical-final-oracle"
    historical = build_current_signal(source, facts, work_directory=tmp_path)
    assert historical["diagnostics"]["coverage"]["510300"]["split_events"][0]["date"] == facts["calendar"][29]
    assert historical["signal_qualified"] is False


def test_exact_day_split_uses_paired_factors(source, facts, tmp_path):
    for i in range(29, 40):
        facts["shares"][i]["value"] = 2 * (100000000 + i * 1000000)
        facts["raw"]["510300"]["bars"][i].update(open=.5, close=.5, high=.6, low=.4)
    result = build_current_signal(source, facts, work_directory=tmp_path)
    row = result["prepared_snapshot"]["daily"]["510300"][10]
    assert row["share_adjust"] == 2
    assert row["shares_delta_yi"] == pytest.approx(.02)
    assert row["shares_delta_pct"] == pytest.approx(.02 / 2.56 * 100)


def test_missing_benchmark_has_no_zero_return_substitution(source, facts, tmp_path):
    missing = facts["analysis"]["000300"]["bars"].pop(20)["date"]
    result = build_current_signal(source, facts, work_directory=tmp_path)
    assert result["prepared_snapshot"]["daily"]["510300"] == []
    assert result["reference_report"] is None
    assert result["diagnostics"]["coverage"]["510300"]["missing_benchmark_dates"] == [missing]


def test_reference_mismatch_and_missing_split_pair_remain_diagnostic(source, facts, tmp_path):
    facts["analysis"]["510300"]["factor_version"] = "other-reference"
    facts["raw"]["510300"]["bars"] = []
    facts["shares"][-1]["value"] *= 2
    result = build_current_signal(source, facts, work_directory=tmp_path)
    assert "front_reference_mismatch" in result["diagnostics"]["reasons"]
    assert result["prepared_snapshot"]["daily"]["510300"][-1]["share_prob"] is None
    assert result["diagnostics"]["coverage"]["510300"]["unresolved_split_dates"] == [facts["decision_date"]]
    assert result["signal_qualified"] is False


def test_index_unit_has_no_currency_dimension(facts):
    assert normalize_facts(facts)["analysis"]["000300"]["price_unit"] == "index-point"
    facts["analysis"]["000300"]["price_unit"] = "CNY/index-point"
    with pytest.raises(ValueError, match="单位"):
        normalize_facts(facts)


@pytest.mark.parametrize("raw_unit", ["unknown", "index-point"])
def test_unqualified_raw_units_cannot_confirm_causal_split(source, facts, tmp_path, raw_unit):
    # 原反例：输入ETF原价却声明未知或指数点，数值恰能构成2:1时曾错误授资格。
    facts["raw"]["510300"]["price_unit"] = raw_unit
    for i in range(29, 40):
        facts["shares"][i]["value"] = 2 * (100000000 + i * 1000000)
        facts["raw"]["510300"]["bars"][i].update(open=.5, close=.5, high=.6, low=.4)
    result = build_current_signal(source, facts, work_directory=tmp_path)
    coverage = result["diagnostics"]["coverage"]["510300"]
    event = result["prepared_snapshot"]["daily"]["510300"][10]
    assert result["signal_qualified"] is False
    assert "split_price_units_unqualified:510300" in result["diagnostics"]["reasons"]
    assert coverage["split_events"] == [] and coverage["factor_pair"]["units_qualified"] is False
    assert coverage["factor_pair"]["historical_unit_assumption"] is False
    assert event["share_adjust"] is None and event["share_prob"] is None
    # 同数值历史对照允许明确的研究假设，始终不授当前日资格，不称已核折算。
    facts["profile"] = "historical-final-oracle"
    historical = build_current_signal(source, facts, work_directory=tmp_path)
    assert historical["signal_qualified"] is False
    assert historical["diagnostics"]["coverage"]["510300"]["split_events"][0]["basis"] == "historical-unit-assumption"
    assert historical["prepared_snapshot"]["source"]["split_unit_assumptions"] == ["510300"]


@pytest.mark.parametrize("fault", ["duplicate", "nan", "bad_ohlc", "sha", "mixed_model", "bad_code", "naive_time", "negative", "wrong_basis"])
def test_invalid_fact_contract_rejected(facts, fault):
    if fault == "duplicate": facts["analysis"]["510300"]["bars"].insert(1, deepcopy(facts["analysis"]["510300"]["bars"][0]))
    elif fault == "nan": facts["shares"][0]["value"] = "NaN"
    elif fault == "bad_ohlc": facts["analysis"]["510300"]["bars"][0]["high"] = .5
    elif fault == "sha": facts["shares"][0]["source_sha256"] = "bad"
    elif fault == "mixed_model": facts["turnover"][-1]["kind"] = "proxy"
    elif fault == "bad_code": facts["codes"] = [[]]
    elif fault == "naive_time": facts["decision_at"] = "2026-10-26T10:00:00"
    elif fault == "negative": facts["shares"][0]["value"] = -1
    elif fault == "wrong_basis": facts["analysis"]["510300"]["price_basis"] = "none"
    with pytest.raises(ValueError): normalize_facts(facts)


def test_source_tamper_and_explicit_work_directory(source, facts, tmp_path):
    package = ROOT / "apps/guanheng/strategy_original/guanheng_strategy_original"
    copy = tmp_path / "source"
    for manifest in ("source_manifest.json", "feature_source_manifest.json"):
        for name in json.loads((package / manifest).read_bytes())["files"]:
            target = copy / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / name, target)
    target = copy / "backend/base/analysis/shares_adjust.py"
    target.write_bytes(target.read_bytes() + b"\n# changed\n")
    with pytest.raises(ValueError, match="源码内容身份"):
        build_current_signal(copy, facts, work_directory=tmp_path)
    with pytest.raises(ValueError, match="D/E"):
        build_current_signal(source, facts, work_directory=Path("relative-work"))
    with pytest.raises(TimeoutError):
        build_current_signal(source, facts, work_directory=tmp_path, timeout_seconds=1e-9)
    assert not list(tmp_path.glob("original-current-*"))
