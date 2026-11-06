"""原版已发布事实的后台准备者；Native只读小型不可变投影。"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date,datetime,timedelta,timezone
import hashlib,json,math,os,re,time
from pathlib import Path
from threading import Event,Lock
from types import MappingProxyType
from zoneinfo import ZoneInfo
from .managed_local_process import _read,_json
from .thread_owner import ThreadOwner


def _need(ok,reason):
    if not ok:raise ValueError(reason)

def _sha(value):
    _need(type(value)is str and re.fullmatch('[0-9a-f]{64}',value) is not None,'original_source_identity')
    return value

def _encode(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode('ascii')

def _path(value):
    p=Path(value);_need(type(value)is str and p.is_absolute() and p.drive.upper() in ('D:','E:') and '..' not in p.parts,'original_source_path')
    return p

@dataclass(frozen=True)
class OriginalSignalConfig:
    source_root:Path  # 固定351源码根，原纯模块按manifest逐文件核对。
    current_file:Path  # Data owner原CURRENT.json，只读且不跟踪金融CURRENT。
    work_directory:Path  # E/D已声明工作根，所有纯计算临时文件在其下。
    market:dict  # 原SDK端点及token_env；配置不含令牌正文。
    history_from:str  # 历史自然日起点，原路由自身处理预热。
    feature_stage:str  # 明确seed/recalc数学口径。
    turnover_kind:str  # 明确official/proxy模型，不混接事实。
    poll_seconds:float  # 一次后台轮询间隔，资源调度参数。
    query_seconds:float  # 单轮已发布事实查询原总D。
    compute_seconds:float  # 隔离纯计算原总D。
    unit_evidence:dict|None=None  # 可选固定{path,sha256}原件；默认不提升unknown，DTO仅由后台持有。

    @classmethod
    def from_dict(cls,v):
        fields=set(cls.__dataclass_fields__)
        _need(type(v)is dict and fields-{'unit_evidence'}<=set(v)<=fields,'original_signal_configuration')
        d=dict(v);descriptor=d.get('unit_evidence')
        if descriptor is not None:
            _need(type(descriptor)is dict and set(descriptor)=={'path','sha256'},'original_unit_evidence_descriptor')
            _path(descriptor['path']);_sha(descriptor['sha256']);descriptor=MappingProxyType(dict(descriptor))
        d['unit_evidence']=descriptor
        for k in ('source_root','current_file','work_directory'):d[k]=_path(d[k])
        _need(date.fromisoformat(d['history_from']).isoformat()==d['history_from'],'original_history_from')
        _need(d['feature_stage'] in ('seed','recalc') and d['turnover_kind'] in ('official','proxy'),'original_signal_model')
        for k,maximum in (('poll_seconds',3600),('query_seconds',600),('compute_seconds',600)):
            x=d[k];_need(type(x)in(int,float) and math.isfinite(x) and 0<x<=maximum,'original_worker_budget')
        m=d['market'];_need(type(m)is dict and set(m)=={'base_url','token_env','timeout_seconds','max_response_bytes'},'original_market_binding')
        _need(type(m['token_env'])is str and re.fullmatch('[A-Za-z_][A-Za-z0-9_]{0,127}',m['token_env'])is not None,'original_market_binding')
        # 原SDK仍拥有URL/HTTP预算准入；此处仅构造，不进行网络访问。
        from guanheng_market_client import MarketClient
        MarketClient(m['base_url'],'configuration-only',timeout=m['timeout_seconds'],max_response_bytes=m['max_response_bytes'])
        d['market']=MappingProxyType(dict(m));return cls(**d)

@dataclass(frozen=True)
class OriginalPublication:
    observation_date:str  # 已发布闭合决策日；不是机器今天日期。
    snapshot_id:str  # 磁盘完整快照ID，与SDK首尾响应核同。
    pointer_sha256:str  # 本次完整CURRENT原件SHA。
    eligible_date:str|None  # 同快照官方日历证明的下一交易日；未知保持None。
    calendar_sha256:str|None  # 原官方日历字节身份。

@dataclass(frozen=True)
class PreparedOriginalSignal:
    publication:OriginalPublication  # 原发布及下一会话资格证明。
    projection_json:bytes  # 完整小型投影的不可变编码；没有行情大数组或可变借用。
    completed_at:str  # 本机准备完成UTC时刻，不冒充首次发布时间。

    def projection(self):return json.loads(self.projection_json)

@dataclass(frozen=True)
class OriginalSignalRead:
    value:PreparedOriginalSignal|None  # 最后完整成功值，错误仍保留用于展示。
    ready:bool  # 本轮来源/计算成功；qualified仍单独按原输出核。
    reason:str|None  # 固定错误分类或等待，不带外部原文/配置。


def read_original_publication(config,*,deadline):
    """仅白名单消费原指针及冻结日历；不构造Data writer或执行其配置。"""
    raw=_read(config.current_file,65536,clock=time.monotonic,deadline=deadline);v=_json(raw)
    _need(v.get('schema')=='guanheng.market-current.v1','original_current_schema')
    day=v.get('observation_date');_need(type(day)is str and date.fromisoformat(day).isoformat()==day,'original_current_date')
    identity=_sha(v.get('snapshot_id'));descriptor=v.get('configuration')
    _need(type(descriptor)is dict and set(descriptor)=={'path','sha256'},'original_current_configuration')
    cfgraw=_read(_path(descriptor['path']),1048576,clock=time.monotonic,deadline=deadline)
    _need(hashlib.sha256(cfgraw).hexdigest()==_sha(descriptor['sha256']),'original_current_configuration')
    frozen=_json(cfgraw);_need(frozen.get('mode')=='source-market-snapshot','original_current_configuration')
    snap=frozen['snapshot'];snapraw=_read(_path(snap['path']),16*1024*1024,clock=time.monotonic,deadline=deadline)
    _need(hashlib.sha256(snapraw).hexdigest()==_sha(snap['sha256']),'original_current_snapshot')
    from guanheng_market_client.market_snapshot import validate_market_snapshot
    snapshot=validate_market_snapshot(_json(snapraw));_need(snapshot['snapshot_id']==identity and snapshot['observation_date']==day,'original_current_snapshot')
    eligible,calendar_sha=None,None;calendar=frozen.get('calendar')
    if calendar is not None:
        calendar_sha=_sha(calendar['sha256']);_need(snapshot['provenance'].get('calendar_sha256')==calendar_sha,'original_calendar_identity')
        body=_read(_path(calendar['path']),1048576,clock=time.monotonic,deadline=deadline)
        _need(hashlib.sha256(body).hexdigest()==calendar_sha,'original_calendar_identity');cal=_json(body)
        _need(cal.get('kind')=='official-exchange-calendar/v1' and type(cal.get('closed_dates'))is list,'original_calendar_schema')
        from guanheng_market_client.exchange_calendar import official_calendar
        def check():
            _need(time.monotonic()<deadline,'original_calendar_deadline')
        rows,metadata=official_calendar(cal,check=check)
        if metadata['coverage_start']<=day<=metadata['coverage_end']:
            eligible=next((row['date'] for row in rows if row['date']>day and row['is_open']),None)
    return OriginalPublication(day,identity,hashlib.sha256(raw).hexdigest(),eligible,calendar_sha)


def route_qualification(facts,result):
    """逐原路由必要证据；可选因子None、宏观缺口与270日诊断不升级成全池门槛。"""
    rows={};coverage=result['diagnostics']['coverage']
    for code in facts['codes']:
        dependencies=(code,'510300') if code=='159352' else (code,)
        reasons=[]
        if facts['profile']!='causal-current':reasons.append('causal_profile_required')
        benchmark=facts['analysis'].get('000300',{})
        if benchmark.get('price_unit')!='index-point':reasons.append('benchmark_price_units_unqualified')
        for dependency in dependencies:
            packet=facts['analysis'].get(dependency,{})
            if packet.get('price_unit')!='CNY/share' or packet.get('volume_unit','unknown')=='unknown':reasons.append('quote_units_unqualified:'+dependency)
            if facts['raw'].get(dependency,{}).get('price_unit')!='CNY/share':reasons.append('raw_price_units_unqualified:'+dependency)
            detail=coverage.get(dependency,{})
            if detail.get('today_present')is not True:reasons.append('today_features_missing:'+dependency)
            if detail.get('missing_benchmark_dates'):reasons.append('benchmark_dates_missing:'+dependency)
            if detail.get('unresolved_split_dates'):reasons.append('split_unresolved:'+dependency)
        if result['model_state'].get(code,{}).get('held')is None:reasons.append('route_report_unavailable')
        rows[code]=dict(
            qualified=not reasons,  # 此路由必要数据证据齐备，仍不授金融执行资格。
            reasons=reasons,  # 本证券及引用证券的必要证据缺口。
            dependencies=list(dependencies),  # 固定原路由依赖代码；A500明确引用510300。
            optional_diagnostics=[r for r in result['diagnostics']['reasons'] if r.startswith(('today_shares_missing','today_turnover_missing','today_margin_missing','shares_units_unknown','turnover_units_unknown','margin_units_unknown'))])  # None由原guards处理，不增全池停交易门槛。
    return rows


class OriginalSignalWorker:
    """一次ThreadOwner、一个Client、一个最后成功投影；没有Native引用或Source写入。"""
    def __init__(self,config,*,client_factory=None,publication_reader=read_original_publication,collector=None,computer=None,utcnow=lambda:datetime.now(timezone.utc)):
        _need(type(config)is OriginalSignalConfig,'original_worker_config');self.config=config
        self._client_factory=client_factory;self._publication_reader=publication_reader;self._collector=collector;self._computer=computer;self._utcnow=utcnow
        self._stop=Event();self._lock=Lock();self._read=OriginalSignalRead(None,False,'not_started');self._owner=None

    def latest(self):
        with self._lock:return self._read

    def _publish(self,value):
        with self._lock:
            if self._stop.is_set():value=OriginalSignalRead(value.value,False,'stopping')
            self._read=value

    def _client(self):
        if self._client_factory is not None:return self._client_factory()
        from guanheng_market_client import MarketClient
        m=self.config.market;return MarketClient(m['base_url'],os.environ[m['token_env']],timeout=m['timeout_seconds'],max_response_bytes=m['max_response_bytes'])

    def _run(self):
        client=None
        try:
            evidence=None
            if self.config.unit_evidence is not None:
                from .profile_facts import read_unit_evidence
                evidence=read_unit_evidence(self.config.unit_evidence,deadline=time.monotonic()+self.config.query_seconds)
            client=self._client()
            from .original_market_facts import collect_current_facts
            from guanheng_strategy_original.current_signal import build_current_signal
            collector=self._collector or collect_current_facts;computer=self._computer or build_current_signal
            while not self._stop.is_set():
                try:
                    query_deadline=time.monotonic()+self.config.query_seconds
                    publication=self._publication_reader(self.config,deadline=query_deadline)
                    local=self._utcnow().astimezone(ZoneInfo('Asia/Shanghai'))
                    closed=date.fromisoformat(publication.observation_date)
                    _need(closed<local.date() or (closed==local.date() and local.hour>=15),'original_market_not_closed')
                    prior=self.latest().value
                    if prior is not None and prior.publication==publication:
                        self._publish(OriginalSignalRead(prior,True,None))
                    else:
                        options={} if evidence is None else {'unit_evidence':evidence}
                        source=collector(client,observation_date=publication.observation_date,history_from=self.config.history_from,
                            feature_stage=self.config.feature_stage,turnover_kind=self.config.turnover_kind,seconds=max(.001,query_deadline-time.monotonic()),**options)
                        _need(time.monotonic()<query_deadline,'original_query_deadline')
                        _need(source.facts['snapshot_id']==publication.snapshot_id,'original_publication_changed')
                        result=computer(self.config.source_root,source.facts,work_directory=self.config.work_directory,timeout_seconds=self.config.compute_seconds)
                        # 计算完成后的重新确认属于单独只读发布核验阶段，不延长查询或计算本身的原D。
                        final=self._publication_reader(self.config,deadline=time.monotonic()+self.config.query_seconds)
                        _need(final==publication,'original_publication_changed')
                        _need(result.get('profile')=='causal-current' and result.get('decision_date')==publication.observation_date,'original_causal_profile')
                        prices={}
                        for code,p in source.facts['raw'].items():
                            rows=p['bars']
                            if p.get('price_unit')=='CNY/share' and rows and rows[-1]['date']==publication.observation_date:prices[code]=rows[-1]['close']
                        small={k:result[k] for k in ('schema','algorithm_id','upstream_commit','facts_sha256','prepared_sha256','decision_date','decision_at','signals_today','model_state','signal_qualified')}
                        small.update(
                            signal_sha256=hashlib.sha256(_encode(result)).hexdigest(),  # 完整原纯结果身份，非仅BUY/SELL摘要。
                            diagnostic_reasons=result['diagnostics']['reasons'],  # 全输入诊断，不能直接作为全池停交易开关。
                            signal_close_prices=prices,  # 原决策日已证明CNY/share的未复权收盘价；缺项保持缺失。
                            snapshot_id=publication.snapshot_id,  # 原Data完整发布身份，不是投影或CURRENT文件SHA。
                            eligible_date=publication.eligible_date,  # 同发布官方日历证明的下一会话，未知为None。
                            route_qualification=route_qualification(source.facts,result))  # 每证券必要证据及可选缺口分别标识。
                        value=PreparedOriginalSignal(publication,_encode(small),self._utcnow().isoformat())
                        if not self._stop.is_set():self._publish(OriginalSignalRead(value,True,None))
                except Exception as error:
                    self._publish(OriginalSignalRead(self.latest().value,False,'prepare_'+type(error).__name__))
                if self._stop.wait(self.config.poll_seconds):break
        except Exception as error:self._publish(OriginalSignalRead(self.latest().value,False,'worker_'+type(error).__name__))
        finally:
            close=getattr(client,'close',None)
            if close is not None:close()

    def start(self):
        _need(self._owner is None,'original_worker_started');self.config.work_directory.mkdir(parents=True,exist_ok=True)
        self._owner=ThreadOwner(target=self._run,name='original-current-signal');self._owner.start()

    def request_close(self):
        self._stop.set();self._publish(OriginalSignalRead(self.latest().value,False,'stopping'))

    def close(self,deadline):
        self.request_close();return self._owner is None or self._owner.join_until(deadline)

    @property
    def pending(self):return self._owner is not None and self._owner.pending
