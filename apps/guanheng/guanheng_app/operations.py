"""当前 App 所持进程与查询服务的只读投影；公开字段均为有限白名单。"""
from datetime import datetime, timezone

from fastapi import APIRouter
from .collection_observation import empty_observation, with_process_state

_STATES = {
    'disabled': '未配置', 'new': '待启动', 'starting': '启动中',
    'ready': '监听就绪', 'stopping': '停止中', 'closed': '已停止', 'faulted': '失败',
}
_ERRORS = {
    'configuration': '部署文件或内容身份校验失败',
    'process_start': '进程创建失败', 'pipe_start': '输出读取启动失败',
    'control_receipt': '实例就绪或关闭收据核验失败',
    'startup_timeout': '启动超过原截止时间', 'unexpected_exit': '进程意外退出',
    'host_exit': '进程异常退出', 'stop_timeout': '停止超过原截止时间',
    'output_limit': '进程输出超过限额', 'pipe_read': '进程输出读取失败',
    'job_stop': '进程树关闭失败', 'cleanup_unconfirmed': '资源回收尚未确认',
    'monitor_start': '进程监督线程启动失败',
}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def process_status(owner, *, invalid=False, startup_failed=False):
    """仅取当前持有owner的status；不访问历史文件、日志或进程控制接口。"""
    if invalid:
        state, error, raw = 'faulted', '部署配置与摘要未通过校验', {}
    else:
        try:
            raw = owner.status() if owner is not None else {'state': 'disabled'}
            state = raw.get('state')
            state = state if state in _STATES else 'unknown'
            code = raw.get('error_code')
            error = _ERRORS.get(code, '进程发生未分类故障') if code else None
        except Exception:
            state, error, raw = 'unknown', '当前进程状态读取失败', {}
    if startup_failed and error is None:
        error = '本轮启动尚未取得成功确认'
    reason = error or {
        'disabled': '当前应用未配置此受管进程',
        'ready': '当前进程已提交监听就绪收据，来源连接与数据活跃度另行核实',
        'closed': '当前应用持有的进程已停止',
    }.get(state, '当前应用持有的进程处于' + _STATES.get(state, '未知状态'))
    pid = raw.get('pid')
    return dict(state=state, label=_STATES.get(state, '未知'), reason=reason,
                pid=pid if type(pid) is int and 0 < pid < 2**32 else None,
                ready=raw.get('ready') if type(raw.get('ready')) is bool else None,
                pending=raw.get('pending') if type(raw.get('pending')) is bool else None,
                forced=raw.get('forced') if type(raw.get('forced')) is bool else None, error=error,
                action='请由维护人员核对部署配置和本实例受管收据；页面可重新读取状态。')


def query_status(settings, remaining, client_factory=None):
    """沿原 SDK 的有限响应/传输截止调用 capabilities；不查询或准备证券数据。"""
    if not (settings.wondertrader_market_url and settings.wondertrader_market_token.get_secret_value()):
        return dict(state='unconfigured', reason='尚未配置 WonderTrader 行情查询连接',
                    history_supported=None, snapshot_supported=None, source=None)
    try:
        from guanheng_market_client import MarketClient
        factory = client_factory or MarketClient
        kwargs = dict(timeout=min(remaining, settings.wondertrader_market_timeout_seconds))
        if settings.wondertrader_market_connect_ip:
            kwargs['connect_ip'] = settings.wondertrader_market_connect_ip
        client = factory(settings.wondertrader_market_url,
                         settings.wondertrader_market_token.get_secret_value(), **kwargs)
        response = client.capabilities()
        if response['status']['code'] != 'Ok':
            raise ValueError('query service unavailable')
        data = response['data']
        history, snapshot = data['history']['supported'], data['snapshot']['supported']
        if type(history) is not bool or type(snapshot) is not bool:
            raise ValueError('query service protocol')
        return dict(state='responding', reason='本次能力查询成功；历史与快照支持按服务声明展示，行情时效另验',
                    history_supported=history, snapshot_supported=snapshot,
                    source={'Qmt': 'QMT', 'Tdx': '通达信'}.get((data.get('source') or {}).get('provider')))
    except Exception:
        return dict(state='unavailable', reason='行情查询服务读取失败、超时或响应无效，请维护人员核对服务与连接',
                    history_supported=None, snapshot_supported=None, source=None)


def router(settings, *, collection_invalid=False, host_invalid=False, client_factory=None):
    """注册只读入口；SDK调用进入现有有界池，排队和执行共用一次绝对截止。"""
    import asyncio
    from time import monotonic
    from fastapi import Request
    from fastapi.responses import JSONResponse
    from .reading import ReadCapacityError

    routes = APIRouter()

    async def read_source(app, operation, deadline):
        # 各来源分别提交完成结果，排队/执行仍共用一次D；后续来源失败保留此前观察。
        future = app.state.reader.submit(operation, deadline)
        try:
            wrapped = asyncio.wrap_future(future)
            wrapped.add_done_callback(lambda done: None if done.cancelled() else done.exception())
            return await asyncio.wait_for(asyncio.shield(wrapped), max(0, deadline-monotonic()))
        finally:
            future.cancel()

    @routes.get('/v1/ui/operations/status')
    async def status(request: Request):
        app = request.app
        deadline = monotonic() + min(2.0, settings.wondertrader_market_timeout_seconds)
        if collection_invalid:
            telemetry = empty_observation('invalid_configuration')
        else:
            owner = app.state.qmt_collection_process
            try:
                telemetry = (await read_source(app, lambda _remaining: owner.observe(deadline), deadline)
                             if owner is not None else empty_observation('waiting'))
            except (ReadCapacityError, TimeoutError):
                telemetry = empty_observation('deadline')
            except Exception:
                telemetry = empty_observation('unavailable')
        try:
            query = await read_source(app, lambda remaining: query_status(settings, remaining, client_factory), deadline)
        except (ReadCapacityError, TimeoutError):
            query = dict(state='unavailable', reason='行情状态读取繁忙或超时，请稍后重新读取',
                         history_supported=None, snapshot_supported=None, source=None)
        collection = process_status(app.state.qmt_collection_process, invalid=collection_invalid,
                                    startup_failed=app.state.qmt_collection_start_error)
        telemetry = with_process_state(telemetry, collection)
        return JSONResponse(headers={'Cache-Control': 'no-store'}, content=dict(
            schema_version='guanheng.operations.v2', read_only=True, observed_at=utc_now(),
            collection=collection,
            host=process_status(app.state.qmt_host_process, invalid=host_invalid,
                                startup_failed=app.state.qmt_host_start_error),
            query=query, telemetry=telemetry))

    return routes
