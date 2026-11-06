"""冻结原库和运行固定纯算法；原交易算法保持上游唯一正文。

每次调用独占临时目录和子进程，原通用包名 base/resonance 不进入调用方解释器。
输入为历史最终行，原库没有保存的逐时点事实始终保持未知。
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from contextlib import closing
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile

UPSTREAM_COMMIT = "351f9d58152e10efd2447c997b8ee4db66b5ac6a"
ALGORITHM_ID = "resonance-original-351f9d5-stable"
SCHEMA = "guanheng.resonance-original-input.v1"
MAX_BYTES = 32 * 1024 * 1024
MAX_ROWS = 60000
DEFAULT_CODES = ("510300", "510050", "510500", "512100", "515080", "588000", "589680", "159780", "159352")
DAILY_FIELDS = (
    "date",  # 原事实交易日，YYYY-MM-DD；历史首次发布时间由来源说明另列。
    "code",  # 原六位证券代码，不替换为跟踪相同指数的其他ETF。
    "open_price",  # 来源开盘价，CNY/份，复权基准按source声明，null为缺失。
    "high_price",  # 同基准最高价，CNY/份；null为缺失。
    "low_price",  # 同基准最低价，CNY/份；null为缺失。
    "close_price",  # 同基准收盘价，CNY/份；原组合使用此价。
    "change_pct",  # 存库收盘对前收盘涨幅，百分数；与seed日内涨幅分别表达。
    "volume",  # 原来源成交量，沿同一来源单位；null为未知，零为已知零。
    "volume_ma20",  # 含当日20条均量，与volume同单位。
    "volume_ratio",  # 含当日均量的量比，无量纲，原存库通常三位小数。
    "shares_yi",  # ETF份额存量，亿份；null为未取得。
    "shares_delta_yi",  # 原处理后的份额增量，亿份；null不代表零流入。
    "shares_delta_pct",  # 原处理后的份额增幅，百分数；折算依原数据版本。
    "share_adjust",  # 原折算比例标记；null为无记录，非1需要单独核对。
    "vol_prob",  # 原量能评分，0..100；名称沿原库，尚非校准事件概率。
    "dir_prob",  # 原方向评分，0..100；seed/recalc阶段由来源说明。
    "share_prob",  # 原份额评分，0..100；null为缺少份额依据。
    "composite_prob",  # 原综合评分，0..100；回放保持已存值。
    "idx_chg",  # 原基准指数日内开收到收盘涨幅，百分数；null为缺失。
    "signal_level",  # HIGH/MID/LOW或null，沿原综合评分阈值。
    "price_position",  # 60条高低区间位置，百分数；窗口不全时沿原算法。
    "trade_direction",  # 原量价标签ACCUMULATE/DISTRIBUTE/NEUTRAL或null。
)


def canonical(value: object) -> bytes:
    """有限JSON的稳定UTF-8编码，用于冻结输入身份。"""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def _day(value: object) -> str:
    if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
        raise ValueError("日期须为YYYY-MM-DD")
    return value


def _ordered(rows: list, field: str = "date") -> None:
    if any(isinstance(r, dict) and field not in r for r in rows):
        raise ValueError("序列行缺少日期")
    dates = [_day(r[field]) if isinstance(r, dict) else _day(r) for r in rows]
    if dates != sorted(set(dates)):
        raise ValueError("日期须严格升序且唯一")


def validate_snapshot(value: object) -> dict:
    """校验独立原版快照；允许空辅助事实，并在结果中逐项披露。"""
    if not isinstance(value, dict) or value.get("schema") != SCHEMA:
        raise ValueError("原版冻结输入schema不匹配")
    if value.get("upstream_commit") != UPSTREAM_COMMIT:
        raise ValueError("原版输入提交身份不匹配")
    if value.get("data_kind") not in ("synthetic", "historical-final"):
        raise ValueError("须声明synthetic或historical-final数据性质")
    if value.get("units") != {"price": "CNY/share", "volume": "upstream-source-unit", "shares": "1e8-share", "market": "1e8-CNY"}:
        raise ValueError("输入单位声明不匹配")
    if not isinstance(value.get("source"), dict) or not value["source"].get("description"):
        raise ValueError("缺少输入来源说明")
    codes = value.get("codes")
    if not isinstance(codes, list) or not 1 <= len(codes) <= 17:
        raise ValueError("证券集合须为1..17项且唯一")
    if any(not isinstance(c, str) or len(c) != 6 or not c.isascii() or not c.isdigit() for c in codes):
        raise ValueError("证券须用上游六位代码")
    if len(set(codes)) != len(codes):
        raise ValueError("证券集合须唯一")
    daily = value.get("daily")
    if not isinstance(daily, dict) or not set(codes).issubset(daily) or len(daily) > 17:
        raise ValueError("缺少证券日线")
    total = 0
    for code, rows in daily.items():
        if not isinstance(code, str) or not isinstance(rows, list):
            raise ValueError("证券日线结构错误")
        if any(not isinstance(row, dict) for row in rows):
            raise ValueError("证券日线每行须为对象")
        total += len(rows)
        _ordered(rows)
        for row in rows:
            if set(DAILY_FIELDS) - set(row) or row["code"] != code:
                raise ValueError("原版日线字段或证券身份不完整")
            for field in DAILY_FIELDS[2:]:
                item = row[field]
                if field in ("signal_level", "trade_direction"):
                    continue
                if item is not None and (type(item) not in (int, float) or not math.isfinite(item)):
                    raise ValueError("日线数值须有限或为null")
            for field in ("open_price", "high_price", "low_price", "close_price"):
                if row[field] is not None and row[field] <= 0:
                    raise ValueError("价格须为正数或null")
            for field in ("volume", "volume_ma20", "shares_yi", "share_adjust"):
                if row[field] is not None and row[field] < 0:
                    raise ValueError("数量须非负或null")
            for field in ("price_position", "vol_prob", "dir_prob", "share_prob", "composite_prob"):
                if row[field] is not None and not 0 <= row[field] <= 100:
                    raise ValueError("位置与分数须为0..100或null")
            if row["trade_direction"] not in (None, "ACCUMULATE", "DISTRIBUTE", "NEUTRAL"):
                raise ValueError("交易方向枚举错误")
            if row["signal_level"] not in (None, "HIGH", "MID", "LOW"):
                raise ValueError("信号等级枚举错误")
            o, h, low, close = (row[k] for k in ("open_price", "high_price", "low_price", "close_price"))
            if all(x is not None for x in (o, h, low, close)) and not low <= min(o, close) <= max(o, close) <= h:
                raise ValueError("OHLC价格关系错误")
    for key, fields in (("turnover", ("total_amount_yi",)), ("margin", ("fin_balance_yi",))):
        rows = value.get(key)
        if not isinstance(rows, list):
            raise ValueError("缺少市场辅助序列")
        if any(not isinstance(row, dict) for row in rows):
            raise ValueError("市场辅助序列每行须为对象")
        _ordered(rows)
        total += len(rows)
        for row in rows:
            for field in fields:
                item = row.get(field)
                if item is not None and (type(item) not in (int, float) or not math.isfinite(item) or item < 0):
                    raise ValueError("市场金额须为非负有限数或null")
    calendar = value.get("calendar")
    if not isinstance(calendar, list) or any(not isinstance(item, str) for item in calendar):
        raise ValueError("缺少显式交易日历")
    _ordered(calendar)
    start = _day(value.get("evaluation_start"))
    if start < "2021-01-01":
        raise ValueError("原组合回测起点须不早于2021-01-01")
    if total + len(calendar) > MAX_ROWS or len(canonical(value)) > MAX_BYTES:
        raise ValueError("原版输入超过容量")
    return value


def export_database(database: Path, codes: tuple[str, ...] = DEFAULT_CODES) -> dict:
    """在只读事务内冻结原SQLite业务数据；不迁移、不写库、不触发采集。

    SQLite事务包含已提交WAL，最终身份使用导出正文摘要，文件SHA不能替代该身份。
    """
    path = Path(database).resolve(strict=True)
    selected_codes = set(codes)
    for code in codes:
        reference = {"159352": "510300", "588200": "588000"}.get(code)
        if reference:
            selected_codes.add(reference)
    if not 1 <= len(selected_codes) <= 17 or any(not isinstance(c, str) or len(c) != 6 or not c.isascii() or not c.isdigit() for c in selected_codes):
        raise ValueError("导出证券集合错误")
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=5)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        conn.execute("BEGIN")
        columns = {r[1] for r in conn.execute("PRAGMA table_info(etf_daily)")}
        missing = set(DAILY_FIELDS) - columns
        if missing - {"share_adjust"}:
            raise ValueError("原库缺少必要日线列")
        selected = [f if f in columns else "NULL AS " + f for f in DAILY_FIELDS]
        placeholders = ",".join("?" for _ in selected_codes)
        rows = conn.execute("SELECT " + ",".join(selected) + " FROM etf_daily WHERE code IN (" + placeholders + ") ORDER BY code,date LIMIT ?", (*sorted(selected_codes), MAX_ROWS + 1)).fetchall()
        if len(rows) > MAX_ROWS:
            raise ValueError("原库导出超过容量")
        daily: dict[str, list] = {}
        for row in rows:
            daily.setdefault(row["code"], []).append(dict(row))
        # 跨标的引用随交易集合导出；已退市或从监控删除的其他行保持原库所有权。
        turnover = [dict(r) for r in conn.execute("SELECT date,total_amount_yi FROM market_turnover ORDER BY date LIMIT ?", (MAX_ROWS + 1,))]
        margin = [dict(r) for r in conn.execute("SELECT date,fin_balance_yi FROM margin_trading ORDER BY date LIMIT ?", (MAX_ROWS + 1,))]
        calendar = [r[0] for r in conn.execute("SELECT date FROM trade_calendar ORDER BY date LIMIT ?", (MAX_ROWS + 1,))]
    snapshot = {
        "schema": SCHEMA,  # 独立原版输入协议。
        "upstream_commit": UPSTREAM_COMMIT,  # 固定算法提交，与输入处理版本分别标识。
        "data_kind": "historical-final",  # 当前取得的历史最终行，历史逐时点资格未知。
        "source": {"description": "readonly-original-sqlite", "captured_at": datetime.now(timezone.utc).isoformat(),
                   "historical_available_at": None, "price_basis": "not-recorded-by-original-schema"},
        "units": {"price": "CNY/share", "volume": "upstream-source-unit", "shares": "1e8-share", "market": "1e8-CNY"},
        "codes": list(codes),  # 原监控集合内显式选择的交易证券。
        "daily": daily,  # 每个证券的完整升序预热及回放行，含必要参考证券。
        "turnover": turnover,  # 两市成交额日期序列，total_amount_yi单位亿元。
        "margin": margin,  # 融资余额日期序列，fin_balance_yi单位亿元。
        "calendar": calendar,  # 原交易日历，升序且唯一。
        "evaluation_start": "2021-01-01",  # 原组合信号筛选起点，不裁掉策略预热历史。
    }
    return validate_snapshot(snapshot)


def run_reference(source: Path, snapshot: dict, timeout_seconds: float = 120) -> dict:
    """有界运行固定上游纯计算，返回信号、五灯、原组合与数据诊断。

    source是用户指定的上游检出根；按随包清单逐字校验并复制后运行，避免通用包名冲突。
    """
    validate_snapshot(snapshot)
    if type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 600:
        raise ValueError("运行期限须大于0且不超过600秒")
    package = Path(__file__).parent
    manifest = json.loads((package / "source_manifest.json").read_text(encoding="utf-8"))
    root = Path(source).resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix="resonance-original-") as temporary:
        work = Path(temporary)
        for name, expected in manifest["files"].items():
            raw = (root / name).read_bytes()
            if hashlib.sha256(raw).hexdigest() != expected:
                raise ValueError("上游源码内容身份不匹配: " + name)
            target = work / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        inp, out = work / "input.json", work / "output.json"
        inp.write_bytes(canonical(snapshot))
        command = [sys.executable, "-I", "-S", "-B", str(package / "worker.py"), str(work / "backend"), str(inp), str(out)]
        try:
            process = subprocess.run(command, cwd=work, capture_output=True, timeout=timeout_seconds, check=False)
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError("原版参考计算超时，子进程已终止") from exc
        if process.returncode != 0:
            # 上游异常可能带输入值，完整traceback保留在子进程内，仅返回限定错误分类。
            try:
                detail = json.loads(out.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                detail = {}
            raise ValueError("原版参考计算失败: " + detail.get("error_type", "worker-failed"))
        if out.stat().st_size > MAX_BYTES:
            raise ValueError("原版参考输出超过容量")
        report = json.loads(out.read_text(encoding="utf-8"))
        if report.get("input_sha256") != digest(snapshot) or report.get("algorithm_id") != ALGORITHM_ID:
            raise ValueError("原版参考输出身份不匹配")
        report["source_manifest_sha256"] = digest(manifest)
        return report
