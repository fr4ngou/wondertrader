"""固定profile共用的原WT资料与共同报价读取；不拥有资金或执行状态。"""
from dataclasses import asdict
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from fractions import Fraction
import hashlib,json,time,math
from zoneinfo import ZoneInfo
from .managed_local_process import _read
from .execution_strategy import _need
from .execution_facts import admit_native_files,native_price_ticks,canonical_raw_price


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False,default=str).encode('ascii')).hexdigest()

def configured_native_facts(configuration,native,mapping,*,deadline):
    """同一已安装manifest与原admit_native_files，完整复用旧configured资料准入。"""
    root=configuration.installation/'app';expected=dict(configuration.artifacts)
    names={n:native['base_data'][n] for n in ('sessions','commodities','contracts','holidays')};names['fees']=native['environment'].get('fees');paths={}
    for name,relative in names.items():
        _need(type(relative)is str and relative,'native_cash_model');path=root/relative
        _need(path.is_relative_to(root) and '..' not in path.parts,'native_cash_model')
        raw=_read(path,1048576,clock=time.monotonic,deadline=deadline)
        _need(hashlib.sha256(raw).hexdigest()==expected.get('app/'+path.relative_to(root).as_posix()),'native_cash_model_identity');paths[name]=path
    identities,frozen=admit_native_files(mapping,SimpleNamespace(**paths))
    _need(all(hashlib.sha256(frozen[n]).hexdigest()==expected.get('app/'+paths[n].relative_to(root).as_posix()) for n,_ in identities)
          and time.monotonic()<deadline,'native_cash_model_identity')
    return identities,frozen,native_price_ticks(mapping,frozen)


def quote_value(context,symbol,tick,*,now,max_age):
    quote=context.quote(symbol)
    if quote is None:return None
    clock=quote.action_time
    stamp=datetime.strptime(str(quote.action_date), '%Y%m%d').replace(hour=clock//10000000,minute=clock//100000%100,
        second=clock//1000%100,microsecond=clock%1000*1000,tzinfo=ZoneInfo('Asia/Shanghai')).astimezone(timezone.utc)
    if not stamp<=now<stamp+timedelta(seconds=max_age):return None
    price=canonical_raw_price(quote.price_cny,tick)
    return price,quote


def common_prices(context,mapping,ticks,participants,*,now,max_age):
    """每证券独立验证原quote；观察时点与tick源时间分别绑定，缺项只跳过对应证券。"""
    from .account_allocation import CommonPrice
    rows=[]
    for symbol in mapping.values():
        accepted=tuple(participants.get(symbol,()))
        if len(accepted)<2:continue
        value=quote_value(context,symbol,ticks[symbol],now=now,max_age=max_age)
        if value is None:continue
        price,quote=value;observed=datetime.now(timezone.utc).isoformat()
        proof=digest(dict(schema='guanheng.common-native-quote.v1',symbol=symbol,quote=asdict(quote),observed_at=observed,max_age_seconds=max_age))
        rows.append(CommonPrice(symbol,Decimal(price.numerator)/Decimal(price.denominator),observed,proof,accepted,True))
    return tuple(rows)


def announce_shared_hold(context,strategy_id,symbols,observation,allocation,*,source_identity,deadline):
    """首次SCHEDULE宣布原ctx完整保持目标，使局部信号等待不会遮住另一ctx。"""
    rows={row.symbol:row.quantity for row in observation.strategy.positions}
    vector=[]
    for symbol in symbols:
        existing=context.position(symbol).enum_target
        quantity=rows.get(symbol,0) if existing is None else existing
        _need(type(quantity)in(int,float) and math.isfinite(quantity) and quantity>=0 and quantity==int(quantity) and quantity%100==0,'shared_hold_target_unrepresentable')
        vector.append((symbol,int(quantity)))
    source=digest(dict(schema='guanheng.shared-hold-target.v1',strategy_id=strategy_id,identity=source_identity,
        account_source_sha256=observation.account_source_sha256,targets=vector))
    allocation.prepare_intent(strategy_id,context.event.epoch,source_sha256=source,
        known_at=datetime.now(timezone.utc).isoformat(),buy_price_caps={},common_prices=(),deadline=deadline)
    _need(dict(context.set_targets(tuple(vector)))==dict(vector),'shared_hold_target_readback')
    return tuple(vector)


def allocation_projection(observation):
    """ASA精确Decimal以CNY十进制文本发布；数量及来源/周期字段沿唯一DTO。"""
    def encode(value):
        if isinstance(value,Decimal):return format(value,'f')
        if isinstance(value,dict):return {k:encode(v) for k,v in value.items()}
        if isinstance(value,tuple):return tuple(encode(v) for v in value)
        if isinstance(value,list):return [encode(v) for v in value]
        return value
    return encode(asdict(observation))


def read_unit_evidence(descriptor,*,deadline):
    """后台单次读取固定1MiB证据字节；只复用SDK DTO，不查映射或官方原件。"""
    from .original_signal_runtime import _path,_sha
    from guanheng_market_client.source_units import parse_unit_evidence
    raw=_read(_path(descriptor['path']),1048576,clock=time.monotonic,deadline=deadline)
    _need(hashlib.sha256(raw).hexdigest()==_sha(descriptor['sha256']),'original_unit_evidence_identity')
    return parse_unit_evidence(raw)
