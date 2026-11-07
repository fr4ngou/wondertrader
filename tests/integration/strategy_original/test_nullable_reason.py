"""固定原SH50可空份额原因；实际原函数红控、经济输出与文件身份核同。"""
from datetime import date,timedelta
from copy import deepcopy
import hashlib,importlib.util,json,os
from pathlib import Path
import subprocess,sys

import pytest

ROOT=Path(__file__).resolve().parents[3]


@pytest.mark.parametrize('bounce',[True,False])
def test_nullable_reason_keeps_original_buy_and_known_value_results(tmp_path,bounce):
    source=Path(os.environ.get('RESONANCE_ORIGINAL_SOURCE',str(ROOT/'research/resonance-20261105/upstream-resonance')))
    if not(source/'backend/base/analysis/strategy/sh50.py').is_file():pytest.skip('用户固定原源码未提供')
    probe=tmp_path/'probe.py'
    probe.write_text('''
from pathlib import Path
from datetime import date,timedelta
from copy import deepcopy
import hashlib,importlib.util,json,sys
sys.path.insert(0,sys.argv[1]);sys.path.insert(0,str(Path(sys.argv[2])/'backend'))
from guanheng_strategy_original.reference_labels import prepare_nullable_reason_labels
path=Path(sys.argv[2])/'backend/base/analysis/strategy/sh50.py'
raw=path.read_bytes();before=hashlib.sha256(raw).hexdigest()
spec=importlib.util.spec_from_file_location('raw_fixed_sh50',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
rows=[dict(date=(date(2026,1,1)+timedelta(days=i)).isoformat(),close_price=10.,volume_ratio=1.,
    price_position=30.,shares_delta_yi=None,change_pct=0.,trade_direction='NEUTRAL')for i in range(30)]
for i in (26,27):rows[i]['trade_direction']='ACCUMULATE'
if sys.argv[3]=='true':rows[28].update(close_price=10.3,change_pct=3.,volume_ratio=1.5)
else:
    rows[27]['change_pct']=1.
    rows[28].update(close_price=10.1,change_pct=1.,volume_ratio=1.1)
try:module.run_sh50_strategy(rows)
except TypeError:pass
else:raise AssertionError('Original missing-share formatting failure was not reproduced')
known=deepcopy(rows)
for row in known:row['shares_delta_yi']=2.
original=module.run_sh50_strategy(known)
prepare_nullable_reason_labels(Path(sys.argv[2])/'backend')
from base.analysis.strategy.sh50 import run_sh50_strategy
assert run_sh50_strategy(known)==original
actual=run_sh50_strategy(rows)
assert actual['trades'] and actual['trades'][0]['action']=='BUY'
assert '未知'in actual['trades'][0]['reason']
def economics(value):
    value=deepcopy(value)
    for trade in value['trades']:trade.pop('reason',None)
    return value
assert economics(actual)==economics(original)
assert hashlib.sha256(path.read_bytes()).hexdigest()==before
prepare_nullable_reason_labels(Path(sys.argv[2])/'backend')
assert run_sh50_strategy(rows)==actual
print(json.dumps(dict(original_red=True,economics_equal=True,file_unchanged=True)))
''',encoding='utf8')
    result=subprocess.run([sys.executable,'-I','-S','-B',str(probe),str(ROOT/'apps/guanheng/strategy_original'),str(source),
                           'true'if bounce else'false'],capture_output=True,timeout=20)
    assert result.returncode==0,result.stderr.decode('utf8',errors='replace')
    assert json.loads(result.stdout)==dict(original_red=True,economics_equal=True,file_unchanged=True)
