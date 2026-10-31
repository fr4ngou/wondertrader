"""AWP 捕获前的可选原 HPR 日线缓存准备；实际覆盖仍由 v7 回读负责。"""
from datetime import datetime,timedelta
import math
from pathlib import Path
import time

from integrations.guanheng import qmt_native_adjustment as qna
from integrations.guanheng.source_history_transport import SourcePending as TransportPending
from .source import SourcePending, SourceUnavailable, utc_now, write_json


def need(value, reason):
    if not value:
        raise ValueError(reason)


def load(path):
    import json
    need(path.stat().st_size <= 4*1024*1024, 'analysis_preparation_capacity')
    return json.loads(path.read_bytes())


def windows(start,end,maximum):
    """沿原来源的含首尾日额度拆窗；原接口负责证券及日期准入。"""
    need(type(maximum) is int and maximum>=1,'analysis_preparation_calendar_budget')
    cursor,last=datetime.strptime(start,'%Y%m%d'),datetime.strptime(end,'%Y%m%d')
    while cursor<=last:
        stop=min(last,cursor+timedelta(days=maximum-1))
        yield cursor.strftime('%Y%m%d'),stop.strftime('%Y%m%d')
        cursor=stop+timedelta(days=1)


class DailyHistoryPreparation:
    """原请求先落盘；未知只观察原 UUID，完成记录只用于合并准备频率。

    来源权威配置归 AWP 工作根 CONFIGURATION；本对象仅在原 capture 线程调用。
    它复用 BoundHistorySource 的签名、原 profile、GetTickCount64、plan/observe。
    """

    def __init__(self, configuration, *, checkpoint, clock=utc_now):
        need(type(configuration) is dict and set(configuration)=={'connection','refresh_interval_seconds'},
            'analysis_preparation_configuration')
        interval=configuration['refresh_interval_seconds']
        need(type(interval) in (int,float) and math.isfinite(interval) and 1 <= interval <= 86400,
            'analysis_preparation_interval')
        from .retained import transport
        self.source,self.retention,self.retained=transport(configuration['connection'])
        self.checkpoint=Path(checkpoint)
        self.interval,self.clock=float(interval),clock

    def request_close(self, *, deadline):
        self.source.request_close(deadline)

    def prepare(self, request, directory, closure, *, deadline):
        directory=Path(directory)
        directory.mkdir(parents=True,exist_ok=True)
        plan_path=directory/'PLAN.json'
        end=closure['closed_through'].replace('-','')
        if plan_path.exists():
            plan=load(plan_path)
            need(plan['capture_id']==request['capture_id'] and plan['symbols']==request['symbols']
                and plan['end_date']==end, 'analysis_preparation_identity')
        else:
            previous=load(self.checkpoint) if self.checkpoint.exists() else None
            start=end
            coalesced=False
            if previous is not None:
                need(previous['schema']=='guanheng.analysis-preparation-returned.v1',
                    'analysis_preparation_checkpoint')
                prior=previous['end_date']
                datetime.strptime(prior,'%Y%m%d')
                returned=datetime.fromisoformat(previous['returned_at'])
                need(returned.tzinfo is not None,'analysis_preparation_clock')
                age=(self.clock()-returned).total_seconds()
                coalesced=prior==end and 0 <= age < self.interval
                if prior <= end: start=prior
            plan=dict(schema='guanheng.analysis-preparation-plan.v1',capture_id=request['capture_id'],
                symbols=request['symbols'],start_date=start,end_date=end,coalesced=coalesced,
                checkpoint_sha256=qna.file_sha(self.checkpoint) if previous is not None else None)
            write_json(plan_path,plan)
        if plan['coalesced']:
            return
        try:
            with self.source.rpc_budget(min(30.,max(.1,deadline-time.monotonic()))):
                binding_path=directory/'BINDING.json'
                if binding_path.exists(): metadata=load(binding_path)
                else:
                    metadata=self.source.binding(deadline)
                    scope=metadata['profile']['operation_profiles']['market.history_prepare']['limits']
                    need('1d' in scope['periods'],'analysis_preparation_period')
                    write_json(binding_path,metadata)
                scope=metadata['profile']['operation_profiles']['market.history_prepare']['limits']
                if self.retained is not None:
                    from .retained import check_capability
                    check_capability(metadata,self.retention)
                records={}
                returned=[]
                for symbol in request['symbols']:
                    for start,stop in windows(plan['start_date'],end,scope['max_calendar_days']['1d']):
                        from .lifecycle import admit_read
                        admit_read(self.source, deadline)
                        # 第一片保持原文件名，已持久的请求身份可由同根后继继续观察。
                        suffix='' if start==plan['start_date'] else '-'+start
                        slot=directory/(symbol+suffix+'.json')
                        if slot.exists(): record=load(slot)
                        else:
                            remaining=min(scope['total_timeout_ms'],int((deadline-time.monotonic())*1000))
                            if remaining < 100: raise SourcePending('analysis_preparation_pending')
                            arguments=dict(symbol=symbol,period='1d',start_time=start,end_time=stop,
                                clock_schema='qmt.win-uptime-ms.v1',
                                deadline_ms=int(self.source.uptime.seconds()*1000)+remaining)
                            record=None
                            if self.retained is None:
                                record=self.source.plan('market.history_prepare',arguments,metadata,deadline)
                                record.update(requested_at=utc_now().isoformat(),received_at=None)
                                write_json(slot,record)
                        if record is not None:
                            arguments=record['request']['arguments']
                            need(record['binding']==metadata['binding'] and arguments['symbol']==symbol
                                and arguments['period']=='1d' and arguments['start_time']==start
                                and arguments['end_time']==stop,'analysis_preparation_original_request')
                        def save():
                            if record['result'] is not None and record['received_at'] is None:
                                record['received_at']=utc_now().isoformat()
                            write_json(slot,record)
                        if self.retained is not None:
                            from guanheng_qmt_shm.read_retention_client import RetainedReadPending,RetainedReadFailure
                            try:
                                receipt=self.retained.prepare('market.history_prepare',arguments,slot,deadline=deadline,
                                    expected_binding=metadata['binding'])
                            except RetainedReadPending:
                                # 缺原结果、通信未知及404/410继续核原ID，避免重派可能已执行的准备。
                                raise SourcePending('analysis_preparation_unconfirmed') from None
                            except RetainedReadFailure:
                                # 公共客户端已持久确认受理拒绝或调用前拒绝；旧slot保持，
                                # 业务owner下一轮可开始新capture，原过期截止不会永久阻断来源恢复。
                                raise SourceUnavailable('analysis_source_terminal_failure') from None
                            result=receipt['reply']
                            record=load(slot)
                            need(record['binding']==metadata['binding'],'analysis_preparation_original_request')
                        else:
                            while True:
                                try:
                                    result=self.source.observe(record,save,deadline)
                                    break
                                except TransportPending:
                                    remaining=deadline-time.monotonic()
                                    if remaining<=.1: raise SourcePending('analysis_preparation_pending') from None
                                    # 原 observe 的单段观察用尽后，沿同 UUID GET 续核；不重建 D 或 POST。
                                    time.sleep(min(.1,remaining))
                        # 原 HPR 的结果未知不准创建新 capture 重派；继续观察此原 UUID。
                        if result['ok'] is not True:
                            raise SourcePending('analysis_preparation_unconfirmed')
                        need(result['data']==dict(schema='qmt.history-preparation-result.v1',symbol=symbol,
                            period='1d',start_time=start,end_time=stop,effect='call_returned',coverage='unknown'),
                            'analysis_preparation_result')
                        records[symbol+suffix]=qna.file_sha(slot)
                        returned.append(record['received_at'])
                write_json(self.checkpoint,dict(schema='guanheng.analysis-preparation-returned.v1',
                    capture_id=request['capture_id'],end_date=end,returned_at=max(returned),
                    effect='call_returned',coverage='unknown',plan=str(plan_path),plan_sha256=qna.file_sha(plan_path),
                    records_sha256=records))
        except TransportPending:
            raise SourcePending('analysis_preparation_pending') from None
