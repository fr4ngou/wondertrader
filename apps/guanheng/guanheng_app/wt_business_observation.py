"""从WRI/NRT-R20公开定位读取原结果；消费者不持有执行进程或金融状态。"""
from datetime import datetime,timezone
import hashlib
import math
from pathlib import Path
import re
from time import monotonic
from uuid import UUID

from guanheng_market_client.runtime_status import read_status_snapshot
from .contracts.account import AccountOverviewV3,AccountGroupV3,NativeAccountSource,AccountRow,AccountField
from .account_projection import FIELD_MAP,unknown
from .wt_runtime_observation import RuntimeObservationConfig,read_runtime_snapshot,resolve_runtime_configuration
from .strategy_runtime_projection import project_strategy, project_strategies
from .managed_local_process import _read,_json,_inspect


def _need(value):
    if not value:raise ValueError('WT业务观察格式或身份无效')


def _check(deadline):
    if monotonic()>=deadline:raise TimeoutError('WT业务观察读取超过本次时间')


def read_business(configuration,deadline):
    """一次原截止内核WRI→原ready→v2结果→WRI身份，原文件均以SDK只读句柄取得。

    WRI快照沿SDK64KiB，结果沿原观察器4MiB共享删除读取；不扫描或改写运行文件。
    文件修改时间与原P/A接收/副本发布时刻分别拥有，停止后结果保留历史身份。
    """
    configuration=resolve_runtime_configuration(configuration,deadline)
    if configuration is None:return None,None,'unconfigured'
    before=read_runtime_snapshot(configuration,deadline).value
    execution=before['components'].get('execution')
    reference=execution.get('business_observation') if execution else None
    if reference is None:return None,None,before['state']
    _need(type(reference) is dict and set(reference)=={'schema','control_id','config_sha256','pid','path','ready_path'}
          and reference['schema']=='guanheng.execution-observation-reference.v1')
    control,digest,pid=reference['control_id'],reference['config_sha256'],reference['pid']
    _need(type(control) is str and str(UUID(control))==control and type(digest) is str
          and re.fullmatch('[a-f0-9]{64}',digest) is not None and type(pid) is int and 0<pid<2**32
          and execution.get('pid')==pid)
    _need(type(reference['path']) is str and type(reference['ready_path']) is str)
    path,ready_path=Path(reference['path']),Path(reference['ready_path'])
    _need(path.is_absolute() and ready_path.is_absolute() and path.name=='strategies.json'
          and ready_path.name=='ready.json' and path.parent==ready_path.parent and path.parent.name==control)
    _inspect(path.parent,directory=True)
    _check(deadline);ready=read_status_snapshot(ready_path,4096).value;_check(deadline)
    _need(set(ready)=={'schema','control_id','config_sha256','pid','closed'}
          and ready['schema']=='guanheng.execution.ready.v1' and ready['closed'] is False)
    value=_json(_read(path,4*1024*1024,clock=monotonic,deadline=deadline));_check(deadline)
    _need(set(value)=={'schema','control_id','config_sha256','pid','strategies'}
          and value['schema']=='guanheng.configured-cta-observation.v2')
    for item in (ready,value):
        _need(item.get('control_id')==control and item.get('config_sha256')==digest
              and type(item.get('pid')) is int and item['pid']==pid)
    strategies=value['strategies']
    _need(type(strategies) is dict and len(strategies)<=32 and all(type(s)is str and re.fullmatch(r'[A-Za-z0-9_.+@-]{1,64}',s) for s in strategies))
    after=read_runtime_snapshot(configuration,deadline).value
    _need(after['pid']==before['pid'] and after['components'].get('execution',{}).get('business_observation')==reference
          and after['components']['execution'].get('pid')==pid)
    _check(deadline)
    return strategies,reference,after['state']


def _stamp(value):
    _need(type(value) is int and 0<value<253402300800000)
    result=datetime.fromtimestamp(value/1000,timezone.utc)
    _need(result<=datetime.now(timezone.utc))
    return result.isoformat()


def _number(value,*,quantity=False):
    _need(type(value) in (int,float) and math.isfinite(value) and abs(value)<=9007199254740991
          and (not quantity or value>=0))
    return AccountField(availability='present',value=value)


def project_broker(strategies,configuration,reference,runtime_state):
    """原P/A逐组复制；不推导成本、成交、交易日、账号、环境或交易准入。"""
    source=None
    if configuration is not None:
        identity=(configuration.instance_id,configuration.control_id,configuration.configuration_sha256,
                  reference['control_id'] if reference else None)
        source=NativeAccountSource(scope_id=hashlib.sha256(repr(identity).encode('utf8')).hexdigest())
    groups={kind:AccountGroupV3(datatype=kind,status='unavailable',source=source,
        reason='WT现有观察未提供此类数据') for kind in ('position','order','deal','account')}
    report=(strategies or {}).get('resonance-regime-v1')
    broker=report.get('broker_observation') if type(report) is dict else None
    if broker is not None:
        _need(type(broker) is dict)
        for kind,flag,revision,received in (('position','positions_known','position_revision','position_received_ms'),
                                          ('account','account_known','account_revision','account_received_ms')):
            try:
                _need(type(broker.get(flag)) is bool)
                if not broker[flag]:continue
                rev=broker.get(revision);_need(type(rev) is int and 0<rev<=9007199254740991)
                stamp,published=_stamp(broker.get(received)),_stamp(broker.get('published_epoch_ms'))
                _need(broker[received]<=broker['published_epoch_ms'])
                rows=[]
                if kind=='account':
                    fields={key:unknown() for key in FIELD_MAP[kind]}
                    fields.update(total_asset=_number(broker.get('balance')),available=_number(broker.get('available')))
                    rows=[AccountRow(fields=fields)]
                else:
                    positions=broker.get('positions');_need(type(positions) is list and len(positions)<=4096)
                    seen=set()
                    for p in positions:
                        _need(type(p) is dict and type(p.get('symbol')) is str and 0<len(p['symbol'])<=64
                              and re.fullmatch(r'[A-Z][A-Z0-9_]{0,15}\.[A-Z0-9_]{1,16}\.[A-Za-z0-9_]{1,16}',p['symbol']) is not None
                              and type(p.get('is_long')) is bool)
                        key=p['symbol'],p['is_long'];_need(key not in seen);seen.add(key)
                        quantity,sellable=_number(p.get('quantity'),quantity=True),_number(p.get('sellable'),quantity=True)
                        _need(sellable.value<=quantity.value)
                        match=re.fullmatch(r'(SSE|SZSE)\.[A-Za-z0-9_]+\.([0-9]{6})',p['symbol'])
                        identity={'m_strInstrumentID':match[2],'m_strExchangeID':'SH' if match[1]=='SSE' else 'SZ'} if match else {'wt_symbol':p['symbol']}
                        fields={key:unknown() for key in FIELD_MAP[kind]}
                        fields.update(quantity=quantity,sellable=sellable,direction=AccountField(availability='present',value='多头' if p['is_long'] else '空头'))
                        rows.append(AccountRow(identity=identity,fields=fields))
                stale = kind=='position' and report.get('reason')=='broker_position_stale'
                groups[kind]=AccountGroupV3(datatype=kind,status='complete',rows=rows,source=source,
                    received_at=stamp,published_at=published,revision=rev,
                    reason='WT提示持仓观察已过期；下方保留原持仓和原接收时间。' if stale else None)
            except (ValueError,TypeError,KeyError,OverflowError,OSError):
                groups[kind].reason='此类WT观察格式或时间无效，本次保持缺失'
    available=any(g.status=='complete' for g in groups.values())
    reason='WT最近发布的券商观察；持仓和资金保留各自接收时间，委托与成交明细尚未提供。'
    if runtime_state not in ('ready','unconfigured'):
        label={'new':'待启动','starting':'启动中','stopping':'停止中','closed':'已停止','faulted':'失败'}[runtime_state]
        reason='WT最近发布状态为'+label+'；下方保留其最后完整观察及原时间。'
    return AccountOverviewV3(status='partial' if available else 'unavailable',trade_date=unknown('WT现有观察未提供券商交易日'),
        groups=groups,reason=reason,runtime_state=runtime_state,observed_at=datetime.now(timezone.utc).isoformat())


def observe_account(configuration,deadline):
    configuration=resolve_runtime_configuration(configuration,deadline)
    strategies,reference,state=read_business(configuration,deadline)
    result=project_broker(strategies,configuration,reference,state);_check(deadline)
    return result


def observe_strategy(configuration,deadline,strategy_id=None):
    configuration=resolve_runtime_configuration(configuration,deadline)
    strategies,_reference,state=read_business(configuration,deadline)
    projected=project_strategy(dict(schema='guanheng.configured-cta-observation.v1',strategies=strategies),runtime_state=state,strategy_id=strategy_id) if strategies is not None else None
    all_strategies=project_strategies(dict(schema='guanheng.configured-cta-observation.v1',strategies=strategies),runtime_state=state) if strategies is not None else []
    _check(deadline)
    result=dict(state='available' if projected else 'waiting' if configuration else 'unconfigured',
                strategy=projected,strategies=all_strategies,runtime_state=state)
    if configuration and strategies is None:
        runtime=read_runtime_snapshot(configuration,deadline).value
        if 'execution' not in runtime['components']:
            result['execution_state']='not_started'
    return result


def router(settings, securities=None):
    """两业务GET共用原App读池/2秒D；失败503由浏览器保留同查询成功结果。"""
    import asyncio
    from fastapi import APIRouter,HTTPException,Request
    from fastapi.responses import JSONResponse
    from .operations import utc_now
    configuration,invalid=None,False
    try:configuration=RuntimeObservationConfig.from_settings(settings)
    except (ValueError,TypeError):invalid=True
    routes=APIRouter()
    from .observer_strategy_details import router as details_router
    routes.include_router(details_router(settings,configuration,invalid,securities))
    @routes.get('/v1/ui/account/overview')
    @routes.get('/v1/ui/strategy-runtime')
    async def read(request:Request):
        strategy=request.url.path.endswith('strategy-runtime')
        params=list(request.query_params.multi_items());selected=request.query_params.get('strategy_id')
        if ((bool(params)if not strategy else len(params)>1 or any(k!='strategy_id'for k,v in params)
                or selected is not None and not re.fullmatch(r'[A-Za-z0-9_.+@-]{1,64}',selected))
                or request.headers.get('content-length','0')!='0' or request.headers.get('transfer-encoding')):
            raise HTTPException(422,'业务观察查询参数无效')
        future=None;deadline=monotonic()+2
        try:
            if invalid:raise ValueError('invalid WT reading configuration')
            strategy=request.url.path.endswith('strategy-runtime')
            if strategy:operation=lambda config,cutoff:observe_strategy(config,cutoff,selected)
            elif settings.account_source=='wt_account_publication':
                from .account_publication import observe_published_account
                operation=observe_published_account
            else:operation=observe_account
            future=request.app.state.reader.submit(lambda _remaining:operation(configuration,deadline),deadline)
            wrapped=asyncio.wrap_future(future)
            wrapped.add_done_callback(lambda done:None if done.cancelled() else done.exception())
            value=await asyncio.wait_for(asyncio.shield(wrapped),max(0,deadline-monotonic()))
            body=dict(schema_version='guanheng.strategy-runtime.v1',read_only=True,observed_at=utc_now(),**value) if strategy else value.model_dump(mode='json')
            return JSONResponse(body,headers={'Cache-Control':'no-store'})
        except Exception:
            raise HTTPException(503,'WT业务观察暂时无法更新，请核对来源后重新读取') from None
        finally:
            if future is not None:future.cancel()
    return routes
