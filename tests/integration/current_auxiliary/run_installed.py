"""Installed AWP -> atomic publication -> Runtime -> unique V1/NSQ target.
Actual frozen market/6743 auxiliary facts; explicit flat-cycle/million-capital model,
no account access, source operation, trading or service process.
"""
from argparse import ArgumentParser
from dataclasses import asdict,replace
from datetime import date,datetime,timedelta,timezone
import hashlib,json,socket,time
from pathlib import Path
from unittest.mock import patch
from importlib import metadata


def main():
    parser=ArgumentParser(description=__doc__)
    parser.add_argument('--frozen',type=Path,required=True)
    parser.add_argument('--work',type=Path,required=True)
    args=parser.parse_args();args.work.mkdir(parents=True,exist_ok=False)
    def save(name,value):
        (args.work/name).write_text(json.dumps(value,indent=2,ensure_ascii=False,default=str),encoding='utf8')
    def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
    def deny(*a,**kw):raise AssertionError('network/source forbidden in installed replay')
    socket.socket.connect=deny
    from guanheng_analysis_window_producer.official_auxiliary import enrich_window
    from guanheng_analysis_window_producer.source import write_json
    from guanheng_strategy_v1.auxiliary import AuxiliaryPublication
    from guanheng_strategy_v1 import RetainedInput,SYMBOLS
    from guanheng_strategy_core.contracts import EvaluationBudget
    from guanheng_strategy_native import QuantityPolicy,generation_id
    from guanheng_wt_runtime.execution_market_window import MarketWindowFile
    from guanheng_wt_runtime.retained_evaluation import evaluate_retained,target_for_result
    publications=[]
    for raw in json.loads((args.frozen/'publications-frozen.json').read_bytes()):
        item=dict(raw);item['statistic_date']=date.fromisoformat(item['statistic_date'])
        item['received_at']=datetime.fromisoformat(item['received_at'])
        if item.get('available_at'):item['available_at']=datetime.fromisoformat(item['available_at'])
        publications.append(AuxiliaryPublication(**item))
    original=json.loads((args.frozen/'publication-frozen.json').read_bytes())
    original_history=json.dumps(original['history'],sort_keys=True,separators=(',',':'))
    original_analysis=json.dumps(original['analysis'],sort_keys=True,separators=(',',':'))
    with patch('guanheng_analysis_window_producer.official_auxiliary.observed_publications',return_value=tuple(publications)) as read_facts:
        publication,report=enrich_window(original,args.work/'frozen-fact-boundary')
    assert read_facts.call_count==1 and len(publications)==6743
    assert json.dumps(publication['history'],sort_keys=True,separators=(',',':'))==original_history
    assert json.dumps(publication['analysis'],sort_keys=True,separators=(',',':'))==original_analysis
    assert report['enriched_rows']==0 and len(publication['current_auxiliary']['values'])==16
    path=args.work/'current-window.json';write_json(path,publication)
    cutoff=datetime.fromisoformat(json.loads((args.frozen/'RESULT.json').read_bytes())['captured_at'])
    # 周期/资金为显式隔离模型；行情/辅助日期、价格和接收时间均来自完整真实原件。
    seed=dict(schema='guanheng.retained-resonance-input.v1',
        configuration=dict(config_revision='isolated-current-auxiliary-real-data-v1',budget_fraction=.95),
        history=original['history'],analysis=original['analysis'],current_view=original['current_view'],
        cycles=[dict(symbol=s,status='flat',quantity=0,source_sha256='9'*64) for s in SYMBOLS],
        cycles_captured_at=cutoff.isoformat(),cycles_valid_until=(cutoff+timedelta(minutes=10)).isoformat(),
        decision_cutoff=cutoff.isoformat())
    request=RetainedInput.from_dict(seed)
    reader=MarketWindowFile(path,600)
    read=reader.read(request,deadline=time.monotonic()+10)
    assert read.request is not None and read.reason is None
    policy=QuantityPolicy('1000000','isolated-fixed-million-inclusive-inventory-policy')
    baseline=evaluate_retained(request,policy,budget=EvaluationBudget(max_seconds=5))
    # 观察真实信号机对当前事实属性的读取；包装后仍调用同一原方法和公式。
    from guanheng_strategy_v1.current_auxiliary import CurrentDecisionObservation,FIELDS
    from guanheng_strategy_v1.role_profile import ROLE_SYMBOLS
    accesses={}
    original_getattr=CurrentDecisionObservation.__getattr__
    def trace(observation,name):
        value=original_getattr(observation,name)
        if name in FIELDS:
            accesses[(observation.market.symbol,name)]=value
        return value
    with patch.object(CurrentDecisionObservation,'__getattr__',trace):
        actual=evaluate_retained(read.request,policy,budget=EvaluationBudget(max_seconds=5))
    supplied={(item['symbol'],item['field']):item['value'] for item in publication['current_auxiliary']['values']}
    required={(ROLE_SYMBOLS['csi300'],field) for field in ('share_probability','turnover_percentile','margin_percentile')}
    required|={(ROLE_SYMBOLS[role],'shares_delta_yi') for role in ('sh50','kc50','kc_composite','zz500')}
    assert all(key in accesses and accesses[key]==supplied[key] for key in required)
    save('ACTUAL-MATH-CONSUMPTION.json',[dict(symbol=key[0],field=key[1],value=accesses[key]) for key in sorted(required)])
    result=actual.result.to_dict()
    assert result.get('current_auxiliary') is not None
    save('AWP-REPORT.json',report);save('PUBLICATION-REFERENCE.json',read.publication)
    save('CORE-RESULT.json',result);save('LEGACY-CORE-RESULT.json',baseline.result.to_dict())
    save('TARGET.json',asdict(actual.target));save('MODEL-POLICY.json',asdict(policy))
    # 旧发布移除请求中的可选当前视图；旧输入不被残留事实污染。
    old_path=args.work/'legacy-window.json';write_json(old_path,original)
    old_read=MarketWindowFile(old_path,600).read(read.request,deadline=time.monotonic()+10)
    assert old_read.request.current_auxiliary is None
    old_result=evaluate_retained(old_read.request,policy,budget=EvaluationBudget(max_seconds=5))
    assert old_result.result.to_dict()==baseline.result.to_dict()
    # 相同事实/行情的后续决策仅改变观察时间，原NSQ经济代际保持。
    later_request=replace(read.request,decision_cutoff=cutoff+timedelta(minutes=1))
    later=evaluate_retained(later_request,policy,previous_target=actual.target,budget=EvaluationBudget(max_seconds=5))
    assert generation_id(actual.target,policy)==generation_id(later.target,policy)
    assert actual.target==later.target
    save('PUBLIC-DIAGNOSTIC.json',dict(schema='guanheng.current-auxiliary-consumption-replay.v1',
        current_auxiliary=result['current_auxiliary'],historical_diagnostics=result['diagnostics'],
        market_basis_date=publication['analysis']['basis_date'],decision_cutoff=result['decision_cutoff'],
        publication=read.publication,cycle_source='isolated-flat-cycle-model',capital_cny=policy.initial_capital_cny))
    report=dict(passed=True,versions={name:metadata.version(name) for name in ('guanheng-analysis-window-producer','guanheng-strategy-v1','guanheng-strategy-core','guanheng-wt-runtime','guanheng-strategy-native')},
        auxiliary_facts=len(publications),current_values=16,required_fields_read_by_original_math=len(required),historical_rows_unchanged=True,
        historical_analysis_unchanged=True,old_publication_exact_result=True,
        current_view_sha256=publication['current_auxiliary']['sha256'],
        repeated_economic_generation=generation_id(actual.target,policy),
        actual_target=asdict(actual.target),legacy_target=asdict(baseline.target),
        source_sdk_calls=0,network_calls=0,services_started=0,production_writes=0,
        account_cycles='explicit-isolated-flat-model',capital_model='fixed-one-million',
        frozen_inputs={name:sha(args.frozen/name) for name in ('publication-frozen.json','publications-frozen.json','RESULT.json')})
    save('RESULT.json',report)
    print(json.dumps({k:v for k,v in report.items() if k not in ('actual_target','legacy_target')},indent=2))
if __name__=='__main__':main()
