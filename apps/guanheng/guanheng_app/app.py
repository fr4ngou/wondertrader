"""观衡只读HTTP入口；WT运行生命周期独立，个人观察偏好由本应用拥有。"""
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from time import monotonic

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .contracts.market import MarketChartBenchmark, MarketChartBenchmarkPoint, MarketChartBundle
from .native_chart import build_native_chart, normalize_chart_symbol, unavailable_native_chart
from .reading import BoundedReader, ReadCapacityError
from .settings import ConsoleSettings
from .watchlist import WatchlistOwner, WatchlistError, UNAVAILABLE, UNCONFIGURED
from .watchlist_routes import router as watchlist_router, watchlist_error, REQUEST_SECONDS
from .contracts.watchlist import MAX_ITEMS as WATCHLIST_MAX_ITEMS
from .contracts.strategy_configuration import MAX_VERSIONS as CONFIGURATION_MAX_VERSIONS
from .runtime_status_routes import router as status_router
from .wt_runtime_observation import router as wt_runtime_router
from .wt_business_observation import router as wt_business_router
from .backtest_readonly import router as backtest_router
from .strategy_catalog import strategy_catalog
from .observation.contracts import ObservationError
from .observation.runtime import build_reader as observation_reader
from .observation.routes import make_router as observation_router, observation_error, REQUEST_SECONDS as OBSERVATION_REQUEST_SECONDS

UNMIGRATED_REASON = "该观衡只读功能正在接入WonderTrader公开结果"


async def _initialize_document(reader, owner):
    """个人自选沿原读池初始化；在途文件操作由自选owner持续持有。"""
    deadline = monotonic() + REQUEST_SECONDS
    future = None
    try:
        future = reader.submit(lambda _remaining: owner.start(deadline), deadline)
        wrapped = asyncio.wrap_future(future)
        wrapped.add_done_callback(lambda done: None if done.cancelled() else done.exception())
        await asyncio.wait_for(asyncio.shield(wrapped), max(0, deadline-monotonic()))
    except (ReadCapacityError, TimeoutError):
        pass
    finally:
        if future is not None:
            future.cancel()


def create_app(settings=None, market_client_factory=None, static_directory=None, watchlist_owner_factory=None):
    """构造只读消费者；生命周期只拥有Web读池、个人自选和独立观察读取。"""
    configured = settings if settings is not None else ConsoleSettings.from_environment()

    @asynccontextmanager
    async def lifespan(application):
        application.state.reader = BoundedReader()
        application.state.backtest_reader = BoundedReader(workers=1, capacity=2)
        application.state.watchlist_owner = None
        application.state.observation_owner = None
        application.state.shutdown_complete = False
        application.state.shutdown_errors = ()
        lifecycle_error = None
        try:
            application.state.reader.start()
            application.state.backtest_reader.start()
            if configured.observation_root:
                try:
                    application.state.observation_owner = observation_reader(configured.observation_root)
                except ObservationError:
                    pass
            application.state.watchlist_owner = (watchlist_owner_factory or WatchlistOwner)(configured.watchlist_root)
            if configured.watchlist_root:
                await _initialize_document(application.state.reader, application.state.watchlist_owner)
            yield
        except BaseException as error:
            lifecycle_error = error
            raise
        finally:
            # 取消HTTP不会终止已运行worker；关闭预算覆盖观察、报告及行情的原D。
            deadline = monotonic() + max(configured.wondertrader_market_timeout_seconds,
                                         OBSERVATION_REQUEST_SECONDS, 5) + .25
            errors = []
            def close(owner, timeout):
                if owner is None:
                    return True
                try:
                    return owner.close(timeout)
                except BaseException as error:
                    errors.append(error)
                    return False
            close(application.state.watchlist_owner, 0)
            results = [close(owner, max(0,deadline-monotonic())) for owner in
                (application.state.reader, application.state.backtest_reader, application.state.watchlist_owner)]
            application.state.shutdown_errors = tuple(errors)
            application.state.shutdown_complete = all(results) and not errors
            if errors:
                if lifecycle_error is not None:
                    lifecycle_error.add_note("观衡自有读取资源关闭异常，详见应用私有状态")
                elif len(errors)==1:
                    raise errors[0]
                else:
                    raise BaseExceptionGroup("观衡自有读取资源关闭异常",errors)

    application = FastAPI(title="观衡量化交易系统", lifespan=lifespan)
    application.add_exception_handler(WatchlistError,watchlist_error)
    application.include_router(watchlist_router())
    application.include_router(backtest_router(configured.backtest_archive_root))
    application.include_router(status_router(configured,market_client_factory))
    application.include_router(wt_runtime_router(configured))
    application.include_router(wt_business_router(configured))
    application.add_exception_handler(ObservationError,observation_error)
    application.include_router(observation_router())

    @application.exception_handler(RequestValidationError)
    async def invalid_request(_request,_exception):
        return JSONResponse(status_code=422,content={"detail":"请求参数无效，请检查证券代码、周期、条数及带时区的时间"})

    @application.get("/health")
    async def health():
        return {"status":"ok","application":"guanheng","read_only":True}

    @application.get("/v1/ui/strategy-catalog")
    async def strategy_definitions(request: Request):
        if request.query_params or request.headers.get('content-length','0')!='0' or request.headers.get('transfer-encoding'):
            raise HTTPException(422,"策略目录不接受额外参数")
        return JSONResponse(content=strategy_catalog(),headers={'Cache-Control':'no-store'})

    @application.get("/v1/ui/capabilities")
    async def capabilities():
        available=bool(configured.wondertrader_market_url and configured.wondertrader_market_token.get_secret_value())
        business=all((configured.wt_status_file,configured.wt_control_id,configured.wt_instance_id,configured.wt_configuration_sha256))
        return {"read_only":True,"features":{
            "minute_chart":{"available":available,"periods":["1m","1d"] if configured.wondertrader_history_semantics=="source" else ["1m","5m"],"reason":None if available else "尚未配置WT行情读取连接"},
            "daily_chart":{"available":available and configured.wondertrader_history_semantics=="source","periods":["1d"],"read_only":True,"reason":None if available else "尚未配置WT日线读取连接"},
            "backtest":{"available":bool(configured.backtest_archive_root),"read_only":True,"reason":None if configured.backtest_archive_root else "尚未配置WT已保存的回测报告"},
            "personal_watchlist":application.state.watchlist_owner.capability() if application.state.watchlist_owner else {"available":False,"editable":False,"max_items":WATCHLIST_MAX_ITEMS,"scope":"personal-observation","affects_strategy":False,"reason":UNCONFIGURED},
            "account":{"available":business,"read_only":True,"scope":"account","datatypes":["position","order","deal","account"],"timeout_seconds":2,"reason":None if business else "尚未配置WT账户观察读取连接"},
            "operations":{"available":True,"read_only":True,"reason":None},
            "market_observation":{"available":application.state.observation_owner is not None,"read_only":True,"scope":"independent-observation","executable":False,"reason":None if application.state.observation_owner else "尚未配置独立市场观察数据"},
            "strategy_configuration":{"available":False,"editable":False,"max_versions":CONFIGURATION_MAX_VERSIONS,"scope":"wt-configuration-observation","runtime_effect":False,"reason":"实际配置由WT入口维护"},
            "strategy":{"available":True,"read_only":True,"reason":None},
            "execution":{"available":business,"read_only":True,"reason":None if business else "尚未配置WT策略观察读取连接"}}}

    async def read_chart(symbol, period, limit, before, deadline):
        remaining = deadline - monotonic()
        if remaining <= 0:
            return unavailable_native_chart(symbol, period, "WonderTrader 行情读取预算已耗尽")
        try:
            future = application.state.reader.submit(
                lambda budget: build_native_chart(
                    symbol=symbol, period=period, limit=limit, before=before,
                    settings=configured, client_factory=market_client_factory,
                    timeout_seconds=budget,
                ), deadline,
            )
            wrapped = asyncio.wrap_future(future)
            # HTTP已超时后worker仍可能按来源截止结束；消费晚到异常，避免事件环告警。
            wrapped.add_done_callback(lambda completed: None if completed.cancelled() else completed.exception())
            try:
                return await asyncio.wait_for(asyncio.shield(wrapped), max(0, deadline - monotonic()))
            except (TimeoutError, asyncio.CancelledError):
                # 已运行调用仍归worker拥有；排队调用取消后不会再访问来源。
                future.cancel()
                if asyncio.current_task().cancelling():
                    raise
                return unavailable_native_chart(symbol, period, "WonderTrader 行情读取超时，请稍后重试")
        except (ReadCapacityError, TimeoutError):
            return unavailable_native_chart(symbol, period, "WonderTrader 行情读取繁忙或已停止，请稍后重试")

    @application.get("/v1/ui/market/chart/{symbol}", response_model=MarketChartBundle)
    async def market_chart(
        symbol: str, period: str = Query(default="1m", pattern=r"^(1m|5m|1d)$"),
        limit: int = Query(default=240, ge=1, le=2000), before: datetime | None = None,
        benchmark_symbol: str | None = None, feature_version: str | None = None,
    ):
        try:
            symbol = normalize_chart_symbol(symbol)
            if benchmark_symbol:
                benchmark_symbol = normalize_chart_symbol(benchmark_symbol)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        if feature_version is not None or (before is not None and before.utcoffset() is None):
            raise HTTPException(422, "行情查询须使用带时区的时间，且不接受旧feature_version")
        # 主图与基准共享同一绝对截止；每个worker真正执行时再次扣除排队时间。
        deadline = monotonic() + configured.wondertrader_market_timeout_seconds
        chart = await read_chart(symbol, period, limit, before, deadline)
        unavailable = {"strategy", "bridge"}
        benchmark = None
        if benchmark_symbol and benchmark_symbol != symbol:
            # 主图空或失败时，附加读取没有对齐窗口；明确缺项并保留来源预算。
            source = (
                await read_chart(benchmark_symbol, period, limit, before, deadline)
                if chart.data_available else unavailable_native_chart(
                    benchmark_symbol, period, "主图无可用行情，基准暂不读取"
                )
            )
            benchmark = MarketChartBenchmark(
                symbol=benchmark_symbol,
                points=[MarketChartBenchmarkPoint(occurred_at=c.occurred_at, close=c.close) for c in source.candles],
                data_available=source.data_available, missing_reason=source.missing_reason,
            )
            if not source.data_available:
                unavailable.add("benchmark")
        return MarketChartBundle.model_validate({
            **chart.model_dump(), "benchmark": benchmark,
            "overlay_unavailable_sources": sorted(unavailable),
        })

    @application.api_route("/v1/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "TRACE", "CONNECT"])
    async def unmigrated(path: str, request: Request):
        parts = path.split("/")
        domain = parts[1] if len(parts) > 1 and parts[0] == "ui" else parts[0]
        # 退役产品不再使用“正在迁入”的承诺；旧链接只返回明确结束状态。
        retired = domain in {"news", "news-collector", "research", "research-reports", "grafana"}
        if domain == "research-data":
            offset = 2 if parts[0] == "ui" else 1
            retired = len(parts) <= offset or parts[offset] != "market-observation"
        if retired:
            raise HTTPException(410, "该功能已退出产品范围")
        if domain in {"strategy-configurations", "backtest", "account", "qmt-host", "qmt-collection", "qmt-history-preparation", "source-market", "execution-process", "strategy-runtime", "operations"}:
            if request.method != 'GET':
                raise HTTPException(405, "运行、配置和保存由WT入口负责；观衡仅查询已发布结果", headers={"Allow":"GET"})
            if domain in {"strategy-configurations", "backtest"}:
                raise HTTPException(503, "WT公开任务或配置观察尚未接入，请维护人员核对读取连接")
        if domain == "strategy-runtime":
            raise HTTPException(503, "WT策略业务观察尚未接入，请维护人员核对公开读取配置")
        raise HTTPException(501, UNMIGRATED_REASON)

    directory = Path(static_directory) if static_directory is not None else Path(__file__).parent / "static"
    if directory.is_dir() and (directory / "index.html").is_file():
        if (directory / "assets").is_dir():
            application.mount("/assets", StaticFiles(directory=directory / "assets"), name="assets")

        @application.get("/{path:path}", include_in_schema=False)
        async def frontend(path: str):
            return FileResponse(directory / "index.html")
    else:
        @application.get("/", include_in_schema=False)
        async def no_frontend():
            raise HTTPException(501, "观衡浏览器制品尚未安装，请先构建并配置静态目录")
    return application
