"""有界补跑只选择计划窗口；采集/尝试/发布仍由唯一refresh拥有。"""
from datetime import datetime,timezone
from time import monotonic
from .collection import refresh
from .schedule_policy import due_windows,window_as_of
from .source_fetch import SourceFailure
from .contracts import ObservationError
from .ashare_public import capture_due
from .data_repair import repair

CONTROL_BUDGET_ERRORS={'collection_stopped','collection_timeout','observation_stopped','observation_timeout'}


def tick(reader,config,now,*,deadline,cancelled=None,fetcher_factory=None,market_client_factory=None):
    results=[]
    for key,_when in due_windows(now,config['schedule']):
        if monotonic()>=deadline or cancelled is not None and cancelled():break
        arguments=dict(as_of=window_as_of(key,now,config['schedule'],config['models']),deadline=deadline,window_key=key,now=now,
            cancelled=cancelled,market_client_factory=market_client_factory)
        if fetcher_factory is not None:arguments['fetcher_factory']=fetcher_factory
        try:result=refresh(reader,config,**arguments)
        except (SourceFailure,ObservationError) as exc:
            if exc.code in CONTROL_BUDGET_ERRORS:break
            raise
        results.append(result)
    return dict(status='checked',windows=sum(r.get('status') in ('success','partial') for r in results),results=results)


def run(reader,config,stop,*,now=lambda:datetime.now(timezone.utc),clock=monotonic,
        fetcher_factory=None,market_client_factory=None,on_ready=None):
    """一个进程主线程拥有调度循环；stop提供is_set/wait，批次仍沿原有限D。

    心跳为最近检查记录，来源调用/完成版本分别观察。阻塞SDK的硬停止
    仍由父ManagedLocalProcess的原Job负责，不生成另一套监督线程。
    """
    reader.repository.initialize()
    with reader.repository.scheduler_lease() as lease:
        if lease is None:
            raise ObservationError('scheduler_already_running','该数据根已有观察调度实例',409)
        return _run(reader,config,stop,lease,now,clock,fetcher_factory,market_client_factory,on_ready)


def _run(reader,config,stop,lease,now,clock,fetcher_factory,market_client_factory,on_ready):
    reader.snapshot()
    def observe(phase):
        reader.repository.record_scheduler(dict(enabled=phase!='stopped',state='running' if phase!='stopped' else 'stopped',
            phase=phase,last_heartbeat=now().isoformat(),heartbeat_max_age_seconds=config['budget']['seconds']+config['schedule']['poll_seconds'],
            schedule={key:config['schedule'][key] for key in ('timezone','times')},error_code=None),lease=lease)
    observe('waiting')
    try:
        if on_ready is not None:on_ready()
        startup = True
        while not stop.is_set():
            observed=now();observe('collecting')
            tick(reader,config,observed,deadline=clock()+config['budget']['seconds'],cancelled=stop.is_set,
                fetcher_factory=fetcher_factory,market_client_factory=market_client_factory)
            if stop.is_set():break
            # 兼容无权威日历的历史配置。补齐入口以正式配置的官方日历为准。
            if config.get('models', {}).get('calendars', {}).get('cn', {}).get('kind') == 'official-exchange-calendar/v1':
                observed=now();observe('collecting')
                try:
                    windows = due_windows(observed, config['schedule'])
                    window = windows[-1][0] if windows else None
                    job = reader.repository.data_repair()
                    if startup:
                        job = reader.repository.request_data_repair('startup')
                    elif window and (not job or not job.get('window') or job['window'] < window):
                        job = reader.repository.request_data_repair('scheduled')
                    startup = False
                    if job and job['state'] in ('queued', 'running'):
                        repair(reader, config, job, observed, lease=lease, deadline=clock()+config['budget']['seconds'],
                               cancelled=stop.is_set, refresh=refresh, market_client_factory=market_client_factory, window=window)
                except ObservationError as error:
                    if error.code not in ('catalog_unavailable', 'write_outcome_unknown'):
                        raise
            if stop.is_set():break
            if any(source['kind']=='ashare_public' for source in config['sources']):
                observe('archiving')
                arguments=dict(deadline=clock()+config['budget']['seconds'],cancelled=stop.is_set)
                if fetcher_factory is not None:arguments['fetcher_factory']=fetcher_factory
                try:capture_due(reader,config,now(),**arguments)
                except (SourceFailure,ObservationError) as error:
                    if error.code not in CONTROL_BUDGET_ERRORS:raise
            if stop.is_set():break
            observe('waiting')
            stop.wait(config['schedule']['poll_seconds'])
    finally:observe('stopped')
