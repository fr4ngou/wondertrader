"""WT已发布事实到固定原版特征/当前日信号；来源读取和金融执行由调用者所有。

本模块只校验、冻结和隔离计算。输入、临时源码和输出均在显式D/E目录内，
没有默认TEMP、网络、账户或服务副作用。协议字段及资格沿ORR-07。
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from .reference import DEFAULT_CODES, MAX_BYTES, MAX_ROWS, UPSTREAM_COMMIT, canonical, digest

FACTS_SCHEMA = "guanheng.original-current-facts.v1"
SIGNAL_SCHEMA = "guanheng.original-current-signal.v1"
_SHA = re.compile(r"[0-9a-f]{64}")


def _day(value: object) -> str:
    if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
        raise ValueError("事实日期须为YYYY-MM-DD")
    return value


def _instant(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("事实时刻须含时区")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("事实时刻须含时区")
    return parsed.astimezone(timezone.utc)


def _number(value: object, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError("事实数值须为有限非负数")
    try:
        decimal = Decimal(str(value))
        result = float(decimal)
    except (ValueError, InvalidOperation, OverflowError) as exc:
        raise ValueError("事实数值须为有限非负数") from exc
    if not decimal.is_finite() or not math.isfinite(result) or result < 0 or (positive and result <= 0):
        raise ValueError("事实数值须为有限非负数")
    return result


def _identity(item: dict) -> None:
    if not isinstance(item, dict) or not isinstance(item.get("source_sha256"), str) or not _SHA.fullmatch(item["source_sha256"]):
        raise ValueError("事实缺少原件SHA256")
    _instant(item.get("received_at"))
    if item.get("available_at") is not None:
        _instant(item["available_at"])


def normalize_facts(facts: dict) -> dict:
    """验证并复制调用方事实；未来/晚到事实留排除计数，原输入保持不变。

    available_at是供应商首次可知时刻，received_at是本地取得证明时刻；当前日模式
    两者都须不晚于decision_at，available_at未知仍可计算诊断，但PIT资格保持false。
    """
    if not isinstance(facts, dict) or facts.get("schema") != FACTS_SCHEMA:
        raise ValueError("当前日事实schema不匹配")
    raw = canonical(facts)
    if len(raw) > MAX_BYTES:
        raise ValueError("当前日事实超过容量")
    if facts.get("profile") not in ("causal-current", "historical-final-oracle"):
        raise ValueError("须显式选择当前日或历史对照profile")
    if facts.get("feature_stage") not in ("seed", "recalc"):
        raise ValueError("须显式选择seed/recalc口径")
    decision = _day(facts.get("decision_date"))
    cutoff = _instant(facts.get("decision_at"))
    if not isinstance(facts.get("snapshot_id"), str) or not _SHA.fullmatch(facts["snapshot_id"]):
        raise ValueError("发布快照身份不匹配")
    if not isinstance(facts.get("description"), str) or not facts["description"].strip():
        raise ValueError("缺少事实来源描述")
    codes = facts.get("codes")
    if not isinstance(codes, list) or not codes or any(not isinstance(c, str) or c not in DEFAULT_CODES for c in codes) or len(codes) != len(set(codes)):
        raise ValueError("当前日代码须为原九ETF的唯一子集")
    calendar = facts.get("calendar")
    if not isinstance(calendar, list) or any(_day(d) != d for d in calendar) or calendar != sorted(set(calendar)):
        raise ValueError("交易日历须升序唯一")
    calendar_set = set(calendar)
    if decision not in calendar_set:
        raise ValueError("决策日不在交易日历")
    result = {k: facts[k] for k in ("schema", "profile", "feature_stage", "decision_date", "decision_at", "snapshot_id", "description")}
    result.update(codes=list(codes), calendar=[d for d in calendar if d <= decision])
    # 排除只作用于计算，不覆写调用者原件；完整输入SHA仍绑定全部收到的事实。
    excluded = {
        "future_date": 0,  # 超过决策交易日而排除的事实行数，按输入行计数。
        "after_cutoff": 0,  # 已发布/收到时刻晚于decision_at而排除的事实行数。
    }
    total = 0

    def visible(day: str, item: dict) -> bool:
        if day > decision:
            excluded["future_date"] += 1
            return False
        if facts["profile"] == "causal-current" and (
            _instant(item["received_at"]) > cutoff or
            (item.get("available_at") is not None and _instant(item["available_at"]) > cutoff)
        ):
            excluded["after_cutoff"] += 1
            return False
        return True

    for name in ("analysis", "raw"):
        group = facts.get(name)
        if not isinstance(group, dict) or any(c not in (*DEFAULT_CODES, "000300") for c in group):
            raise ValueError("行情集合代码不匹配")
        result[name] = {}
        for code, packet in group.items():
            _identity(packet)
            if packet.get("price_unit") not in ("CNY/share", "index-point", "unknown") or packet.get("volume_unit") not in ("share", "lot", "upstream-source-unit", "unknown"):
                raise ValueError("行情单位声明不匹配")
            if packet.get("price_basis") != ("front_ratio" if name == "analysis" else "none"):
                raise ValueError("行情价格基准不匹配")
            if name == "analysis" and (not isinstance(packet.get("factor_version"), str) or not packet["factor_version"]):
                raise ValueError("前复权缺少基准版本")
            bars = packet.get("bars")
            if not isinstance(bars, list):
                raise ValueError("行情行须为列表")
            total += len(bars)
            previous = ""
            selected = []
            for bar in bars:
                if not isinstance(bar, dict):
                    raise ValueError("行情行须为对象")
                day = _day(bar.get("date"))
                if day <= previous or day not in calendar_set:
                    raise ValueError("行情日期须升序唯一且属于日历")
                previous = day
                numbers = {k: _number(bar.get(k), positive=k != "volume") for k in ("open", "high", "low", "close", "volume")}
                if numbers["high"] < max(numbers["open"], numbers["close"], numbers["low"]) or numbers["low"] > min(numbers["open"], numbers["close"]):
                    raise ValueError("行情高低价包络不匹配")
                if visible(day, packet):
                    selected.append({"date": day, **numbers})
            fields = {k: v for k, v in packet.items() if k != "bars"}
            if "qualified_price_dates" in fields:
                dates = fields["qualified_price_dates"]
                if (type(dates) is not list or any(_day(d) != d for d in dates)
                        or dates != sorted(set(dates)) or not set(dates) <= {bar["date"] for bar in bars}):
                    raise ValueError("来源区段单位日期不匹配")
                visible_dates = {bar["date"] for bar in selected}
                fields["qualified_price_dates"] = [day for day in dates if day in visible_dates]
            result[name][code] = {**fields, "bars": selected}
    required = set(codes) | ({"510300"} if "159352" in codes else set())
    if not required.issubset(result["analysis"]) or "000300" not in result["analysis"]:
        raise ValueError("分析行情或跨证券基准缺失")
    for name in ("shares", "turnover", "margin"):
        rows = facts.get(name)
        if not isinstance(rows, list):
            raise ValueError("辅助事实须为列表")
        total += len(rows)
        previous = {}
        result[name] = []
        kinds = set()
        for row in rows:
            _identity(row)
            day = _day(row.get("date"))
            code = row.get("code") if name == "shares" else name
            if (name == "shares" and code not in DEFAULT_CODES) or day <= previous.get(code, ""):
                raise ValueError("辅助事实日期/代码须升序唯一")
            previous[code] = day
            if row.get("unit") not in (("share", "unknown") if name == "shares" else ("CNY", "unknown")):
                raise ValueError("辅助事实单位声明不匹配")
            if name == "turnover":
                if row.get("kind") not in ("official", "proxy"):
                    raise ValueError("成交额须声明official/proxy")
                kinds.add(row["kind"])
            value = None if row.get("value") is None else _number(row["value"])
            if visible(day, row):
                result[name].append({**row, "value": value})
        if len(kinds) > 1:
            raise ValueError("成交额official/proxy须保持独立模型")
    if total > MAX_ROWS:
        raise ValueError("当前日事实行数超过容量")
    result["excluded"] = excluded
    return result


def build_current_signal(source: Path, facts: dict, *, work_directory: Path, timeout_seconds: float = 120, confirmation: bool = False) -> dict:
    """有界计算原日特征及当前日候选，返回ORR-07结果；无来源/金融副作用。

    source为用户提供的固定上游根；work_directory须为已存在D/E绝对目录，调用方
    所有，内部独占子目录退出时回收。子进程超时后终止/join，返回TimeoutError。
    ValueError表示事实/来源/输出身份失败，错误只暴露固定分类，不带外部原文。
    """
    if type(confirmation) is not bool:
        raise ValueError("收复确认策略选择无效")
    normalized = normalize_facts(facts)
    if confirmation:
        from .kc50_confirmation import CODES
        if set(normalized["codes"]) != set(CODES):
            raise ValueError("收复确认策略需要固定七只 ETF")
    if type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 600:
        raise ValueError("运行期限须大于0且不超过600秒")
    root = Path(source).resolve(strict=True)
    base = Path(work_directory)
    if not base.is_absolute() or base.drive.upper() not in ("D:", "E:"):
        raise ValueError("工作目录须为D/E盘显式绝对路径")
    base = base.resolve(strict=True)
    if base.drive.upper() not in ("D:", "E:") or not base.is_dir():
        raise ValueError("工作目录须为D/E盘实际目录")
    package = Path(__file__).parent
    original = json.loads((package / "source_manifest.json").read_text(encoding="utf-8"))
    feature = json.loads((package / "feature_source_manifest.json").read_text(encoding="utf-8"))
    if original["commit"] != UPSTREAM_COMMIT or feature["commit"] != UPSTREAM_COMMIT:
        raise ValueError("固定原源码清单身份不匹配")
    with tempfile.TemporaryDirectory(prefix="original-current-", dir=base) as temporary:
        work = Path(temporary)
        for name, expected in {**original["files"], **feature["files"]}.items():
            raw = (root / name).read_bytes()
            checked = raw.replace(b"\r\n", b"\n") if name in feature["files"] else raw
            if hashlib.sha256(checked).hexdigest() != expected:
                raise ValueError("固定原源码内容身份不匹配")
            target = work / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        inp, out = work / "facts.json", work / "signal.json"
        payload = {"facts": normalized, "facts_sha256": digest(facts), "manifest_sha256": digest({"original": original, "feature": feature})}
        if confirmation:
            payload["confirmation"] = True
        inp.write_bytes(canonical(payload))
        command = [sys.executable, "-I", "-S", "-B", str(package / "current_signal_worker.py"), str(work / "backend"), str(inp), str(out)]
        try:
            process = subprocess.run(command, cwd=work, capture_output=True, timeout=timeout_seconds, check=False)
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError("当前日原计算超时，子进程已终止") from exc
        if process.returncode != 0:
            raise ValueError("当前日原计算失败")
        if out.stat().st_size > MAX_BYTES:
            raise ValueError("当前日原输出超过容量")
        result = json.loads(out.read_bytes())
        if result.get("schema") != SIGNAL_SCHEMA or result.get("facts_sha256") != digest(facts) or result.get("prepared_sha256") != digest(result.get("prepared_snapshot")) or result.get("manifest_sha256") != payload["manifest_sha256"]:
            raise ValueError("当前日原输出身份不匹配")
        return result
