"""可搬迁开发包冒烟；只使用合成历史、包内 DLL 和可选只读外部策略。"""
from __future__ import annotations

import ctypes as C
from datetime import date, timedelta
import os
from pathlib import Path
import socket
import tempfile
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID

from .dependencies import ExternalQmt, digest
from .models import MarketBar, SourceSession
from .native_history import HistoryMetadata, LOG_CALLBACK, NativeHistory, WTSBar
from .shadow import ResonanceShadow
from .business_flow import RetainedBusinessFlow
from .market_compat import ChartReadInterface, RetainedMarketData


def synthetic_dsb(reader: NativeHistory, path: Path, *, helper_library: Path, count: int = 140, period: str = "1d"):
    """通过真实 store_bars 生成有区别的确定性样本；仅用于隔离验证。"""
    if type(count) is not int or not 1 <= count <= reader.max_bars or period not in ("1d", "1m"):
        raise ValueError("合成历史参数不合格")
    rows = (WTSBar * count)()
    current = date(2024, 1, 2)
    for index, row in enumerate(rows):
        if period == "1d":
            while current.weekday() >= 5:
                current += timedelta(days=1)
            row.date = int(current.strftime("%Y%m%d"))
            current += timedelta(days=1)
        else:
            row.date = 20240102
            minute = 9 * 60 + 31 + index
            row.time = (row.date - 19900000) * 10000 + (minute // 60) * 100 + minute % 60
        close = 3.8 - index * 0.003
        row.open, row.high, row.low, row.close = close + 0.005, close + 0.02, close - 0.01, close
        row.vol, row.money, row.settle = 12000 + index * 7, (12000 + index * 7) * close, close
    # 合成写入显式使用原 Helper；读侧自有 ABI 不伪造上游导出。
    helper_library = Path(helper_library).resolve(strict=True)
    helper = C.CDLL(str(helper_library))
    store = helper.store_bars
    store.argtypes = [C.c_char_p, C.POINTER(WTSBar), C.c_int, C.c_char_p, LOG_CALLBACK]
    store.restype = C.c_bool
    logger = LOG_CALLBACK(lambda unused: None)
    if not store(str(path).encode("utf-8"), rows, count, b"d" if period == "1d" else b"m1", logger) or not path.is_file():
        raise ValueError("原生合成历史写入失败")
    return HistoryMetadata(SourceSession("Qmt", "synthetic", "offline-development", 1),
        "DevelopmentVerified", "synthetic-v1", digest(path), "synthetic-test-only", period,
        count, 1.0, 1.0)


def package_smoke(library, work, qmt_source=None, native_fixture=None, *, helper_library):
    """包内真实 WtDtHelper→DSB→MarketBar；显式外部核心存在时延伸到真实影子目标。"""
    library, work = Path(library).resolve(strict=True), Path(work).resolve()
    work.mkdir(parents=True, exist_ok=True)
    reader = NativeHistory(library, digest(library), max_bars=1000, max_file_bytes=4 * 1024 * 1024)
    try:
        with tempfile.TemporaryDirectory(prefix="guanheng-business-", dir=work) as folder:
            path = Path(folder) / "synthetic.dsb"
            metadata = synthetic_dsb(reader, path, helper_library=helper_library)
            modules, unavailable = None, "未配置外部 QMT 纯策略源；发布打包方式待决策"
            external = None
            if qmt_source:
                # 明确要求该资格的包验收不能把缺依赖静默降级为成功。
                external = ExternalQmt(Path(qmt_source))
                modules = external.retained()
            bar_type = modules["contracts"].MarketBar if modules else MarketBar
            history = reader.read(path, "510300.SH", metadata, bar_type)
            result = {"history": "DevelopmentVerified", "bars": len(history.bars), "coverage": history.coverage,
                      "library_sha256": digest(library), "dataset_sha256": metadata.content_id,
                      "core": "unavailable", "reason": unavailable, "qualification": "DevelopmentVerified"}
            result.update(retained_business="unavailable", console_contract="unavailable",
                          retained_reason="未配置外部原业务依赖")
            result.update(cross_module="unavailable", cross_module_reason="未提供 C++ LC1 原生导入样本")
            if native_fixture:
                cross = reader.read_store(Path(native_fixture), "SSE", "510300", bar_type)
                if (cross.metadata.dataset_version != "fixture-lc1-units-v1" or len(cross.bars) != 3
                        or cross.metadata.source_license != "synthetic-no-market-data"
                        or [b.volume for b in cross.bars] != [300., 400., 500.]
                        or [b.amount for b in cross.bars] != [255., 265., 275.]):
                    raise ValueError("C++ LC1 导入与 Python MarketBar 的量额或来源不一致")
                result.update(cross_module="passed", cross_module_bars=len(cross.bars),
                              cross_module_reason="C++ LC1→原生 DSB→Python 股/元一致")
            if modules:
                shadow = ResonanceShadow(modules, config_id=UUID("00000000-0000-4000-8000-000000000001"),
                    config_version="synthetic-v1", budget_weight=0.25, symbol_cap_weight=0.25,
                    intent_lifetime=timedelta(hours=1))
                auxiliary = {bar.occurred_at.date(): dict(share_probability=80.0, turnover_percentile=10.0,
                    margin_percentile=10.0, auxiliary_available_at=bar.occurred_at,
                    auxiliary_source_dates=(bar.occurred_at.date(),), evidence_refs=("synthetic-input-v1",))
                    for bar in history.bars}
                whole, incremental = shadow.compare(shadow.observations(history.bars, auxiliary=auxiliary))
                if not whole.intents:
                    raise ValueError("真实策略样本没有触发目标，影子链未获覆盖")
                result.update(core="DevelopmentVerified", reason="同一上游纯核心整段/增量信号及目标一致",
                              decisions=len(whole.decisions), targets=len(incremental.intents))
                result.update(retained_package_contract(external, modules, history, whole.intents))
            return result
    finally:
        reader.close()


def synthetic_portfolio_request(modules, intents):
    """固定合成账户；复用原 PortfolioRequest/AccountSnapshot，不实现风险规则。"""
    now = intents[-1].valid_until - timedelta(minutes=5)
    account = modules["contracts"].AccountSnapshot(agent_id="synthetic-agent", account_id="synthetic-account",
        captured_at=now, total_asset=100000., cash=100000., market_value=0., day_start_asset=100000.)
    return modules["risk"].PortfolioRequest(account=account, intents=list(intents), prices={"510300.SH": 3.5},
        allowed_symbols={"510300.SH"}, heartbeat_at=now, reconciled=True, execution_mode="shadow", now=now)


def retained_package_contract(external, modules, history, intents):
    """包内兼容层→原 Console callable，及包内业务层→原 Portfolio shadow 拒绝。"""
    market = RetainedMarketData(modules)
    client = ChartReadInterface(market, lambda security, period, limit, before: history,
        other_reads=SimpleNamespace(get=lambda *args, **kwargs: []))
    with patch.dict(os.environ, {"QMT_OPERATIONAL_STDOUT_ENABLED": "false", "OTEL_EXPORTER_OTLP_LOGS_ENDPOINT": ""}), \
            patch.object(socket.socket, "connect", side_effect=AssertionError("隔离包冒烟禁止实际网络")):
        console = external.console_consumer()
        chart = console.ui_market_chart("510300.SH", period="1d", limit=5, benchmark_symbol=None, client=client)
        if not chart.data_available or len(chart.candles) != 5:
            raise ValueError("包内原生历史→原图表 DTO→原 Console 消费链未通过")
        evaluation = RetainedBusinessFlow(modules).evaluate(synthetic_portfolio_request(modules, intents))
        if (evaluation.signing_allowed or evaluation.result.orders
                or "phase 3 shadow evaluation blocks automatic execution" not in evaluation.result.rejected_reasons):
            raise ValueError("包内原 Portfolio shadow 必须保持零委托/零签名")
    return {"retained_business": "passed", "console_contract": "passed", "portfolio_orders": 0,
            "portfolio_decisions": len(evaluation.result.decisions),
            "retained_reason": "包内兼容模块消费原接口；原 shadow 拒绝保持，运行服务未切换"}
