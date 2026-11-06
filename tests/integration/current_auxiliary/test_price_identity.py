"""Actual frozen values; revision cases are explicit isolated test models."""
import json,sys,hashlib
from pathlib import Path
from unittest.mock import patch
from dataclasses import replace
from datetime import date,datetime,timedelta
from guanheng_analysis_window_producer.official_auxiliary import enrich_window
from guanheng_strategy_v1.auxiliary import AuxiliaryPublication
from guanheng_strategy_v1 import RetainedInput
from guanheng_strategy_core.contracts import EvaluationBudget
from guanheng_strategy_native import QuantityPolicy
from guanheng_wt_runtime.execution_market_window import bind_market_window
from guanheng_wt_runtime.retained_evaluation import evaluate_retained
q=Path(sys.argv[1]);base=json.loads((q/'CANDIDATE.json').read_bytes())
raw=json.loads((q/'consumer-frozen/publications-frozen.json').read_bytes());facts=[]
for v in raw:
 v=dict(v);v['statistic_date']=date.fromisoformat(v['statistic_date']);v['received_at']=datetime.fromisoformat(v['received_at']);facts.append(AuxiliaryPublication(**v))
def enrich(items):
 with patch('guanheng_analysis_window_producer.official_auxiliary.observed_publications',return_value=tuple(items)):
  return enrich_window(base,q/'unused-frozen-boundary')
original,_=enrich(facts)
assert original['input_sha256']==base['input_sha256']
# Isolated source revision: same true market, changed auxiliary value+source identity.
latest=max(x.statistic_date for x in facts if x.symbol=='588000.SH')
changed=[replace(x,value=x.value+1,source_sha256='a'*64) if x.symbol=='588000.SH' and x.statistic_date==latest else x for x in facts]
current,_=enrich(changed)
assert current['input_sha256']==base['input_sha256']
assert current['current_auxiliary']['sha256']!=original['current_auxiliary']['sha256']
# Historical merge test uses actual market rows with explicitly modelled earlier knowledge.
model=[replace(x,received_at=datetime.combine(x.statistic_date,datetime.min.time(),tzinfo=x.received_at.tzinfo)) for x in facts]
history,report=enrich(model)
assert report['enriched_rows']>0 and history['input_sha256']==base['input_sha256']
assert any('history_sha256' in x for x in history['references'])
assert hashlib.sha256(json.dumps(history,sort_keys=True).encode()).hexdigest()!=hashlib.sha256(json.dumps(original,sort_keys=True).encode()).hexdigest()
# Current-only real facts change the actual canonical core input, with original Reader price identity fixed.
from guanheng_strategy_v1.role_profile import SYMBOLS
cutoff=datetime.fromisoformat(json.loads((q/'consumer-frozen/RESULT.json').read_bytes())['captured_at'])
wire=dict(schema='guanheng.retained-resonance-input.v1',configuration=dict(config_revision='isolated-price-identity',budget_fraction=.95),history=base['history'],analysis=base['analysis'],current_view=base['current_view'],cycles=[dict(symbol=s,status='flat',quantity=0,source_sha256='9'*64) for s in SYMBOLS],cycles_captured_at=cutoff.isoformat(),cycles_valid_until=(cutoff+timedelta(minutes=10)).isoformat(),decision_cutoff=cutoff.isoformat())
request=RetainedInput.from_dict(wire);policy=QuantityPolicy('1000000','isolated-price-identity')
results=[]
for publication in [original,current,history]:
 bound=bind_market_window(wire,publication)
 results.append(evaluate_retained(bound,policy,budget=EvaluationBudget(max_seconds=5)).result.to_dict()['input_sha256'])
assert len(set(results))==3
out=dict(passed=True,current_revision_price_identity_preserved=True,historical_merge_price_identity_preserved=True,historical_enriched_rows=report['enriched_rows'],canonical_core_input_revisions=results,historical_reference_present=True,source_calls=0)
(q/'REGRESSION.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
