"""旧状态URL的只读投影；事实来自独立WT发布文件和原行情SDK。"""
import asyncio
from time import monotonic

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from .collection_observation import empty_observation
from .operations import query_status, utc_now
from .wt_runtime_observation import RuntimeObservationConfig, observe_runtime


def _process(snapshot, name):
    if name is None:
        return dict(state='unknown',label='待接入',ready=None,pending=None,forced=None,pid=None,error=None,
                    reason='WT历史补齐的独立观察尚未提供，历史数据范围请在行情页查看。',
                    action='请维护人员核对WT公开观察；页面不管理补齐进程。')
    runtime = snapshot['runtime']
    component = next((c for c in runtime['components'] if c['name'] == name), None) if runtime else None
    if component is None:
        unavailable = snapshot['state']=='unavailable'
        return dict(state='unknown' if unavailable else 'disabled', label='未知' if unavailable else '未配置', ready=None, pending=None, forced=None, pid=None, error=None,
                    reason='独立WT尚未提供此组件的发布状态', action='请维护人员核对WT运行装配与只读连接。')
    return dict(state=component['state'], label=component['label'], ready=component['ready'],
        pending=component['pending'], forced=component['forced'], pid=None,
        error='WT发布了组件失败状态，请由维护人员核查' if component['state']=='faulted' else None,
        reason='WT最近发布：'+component['label']+'；当前存活与业务可用需分别核实。',
        action='请维护人员在WT入口核查运行状态；观衡只读取已发布结果。')


def router(settings, client_factory=None):
    """兼容读取地址继续提供中文DTO；所有读取沿App读池及一次原2秒截止。"""
    configuration, invalid = None, False
    try:
        configuration = RuntimeObservationConfig.from_settings(settings)
    except (ValueError, TypeError):
        invalid = True
    routes = APIRouter()

    async def read(request, deadline, operation):
        future = None
        try:
            if invalid:
                raise ValueError('invalid WT observation')
            future = request.app.state.reader.submit(operation, deadline)
            wrapped = asyncio.wrap_future(future)
            wrapped.add_done_callback(lambda done: None if done.cancelled() else done.exception())
            return await asyncio.wait_for(asyncio.shield(wrapped), max(0,deadline-monotonic()))
        except Exception:
            raise HTTPException(503, '独立WT状态暂不可读取，请核对连接后重试') from None
        finally:
            if future is not None:
                future.cancel()

    @routes.get('/v1/ui/operations/status')
    async def operations(request: Request):
        if request.query_params or request.headers.get('content-length','0')!='0' or request.headers.get('transfer-encoding'):
            raise HTTPException(422,'状态读取不接受额外参数')
        deadline = monotonic() + min(2.0,settings.wondertrader_market_timeout_seconds)
        try:
            snapshot = await read(request,deadline,lambda _remaining:observe_runtime(configuration,deadline))
        except HTTPException:
            snapshot=dict(state='unavailable',runtime=None,published_at=None,reason='WT发布状态暂不可读取')
        try:
            query = await read(request,deadline,lambda remaining:query_status(settings,remaining,client_factory))
        except HTTPException:
            query=dict(state='unavailable',reason='行情查询状态暂不可读取，请重新读取',history_supported=None,snapshot_supported=None,source=None)
        telemetry=empty_observation('unavailable')
        telemetry['reason']='采集业务明细尚未接入WT公开观察；进程发布状态见上方。'
        return JSONResponse(headers={'Cache-Control':'no-store'},content=dict(
            schema_version='guanheng.operations.v2',read_only=True,observed_at=utc_now(),
            collection=_process(snapshot,'collection'),host=_process(snapshot,'host'),
            query=query,telemetry=telemetry,wt_runtime=snapshot))

    @routes.get('/v1/ui/source-market')
    @routes.get('/v1/ui/execution-process')
    @routes.get('/v1/ui/qmt-host')
    @routes.get('/v1/ui/qmt-collection')
    @routes.get('/v1/ui/qmt-history-preparation')
    async def component(request: Request):
        if request.query_params or request.headers.get('content-length','0')!='0' or request.headers.get('transfer-encoding'):
            raise HTTPException(422,'状态读取不接受额外参数')
        deadline=monotonic()+2
        snapshot=await read(request,deadline,lambda _remaining:observe_runtime(configuration,deadline))
        leaf=request.url.path.rsplit('/',1)[-1]
        name={'source-market':'history','execution-process':'execution','qmt-host':'host','qmt-collection':'collection'}.get(leaf)
        process=_process(snapshot,name)
        if leaf in ('qmt-host','qmt-collection'):
            return JSONResponse(headers={'Cache-Control':'no-store'},content={
                'host' if leaf=='qmt-host' else 'collection':process,'startup_failed':False,'qmt_connection':'not_checked'})
        schema={'source-market':'guanheng.source-market-app-status.v1','execution-process':'guanheng.execution-app-status.v1',
                'qmt-history-preparation':'guanheng.history-preparation-app-status.v1'}[leaf]
        value=dict(schema_version=schema,read_only=True,observed_at=utc_now(),process=process)
        if leaf=='execution-process':
            value.update(configuration_sha256=None,execution_qualification='not_checked',recovery_ready=False)
        else:
            value['data_qualification']='not_checked'
            if leaf=='qmt-history-preparation':value['qmt_connection']='not_checked'
        return JSONResponse(headers={'Cache-Control':'no-store'},content=value)
    return routes
