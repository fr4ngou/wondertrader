"""历史来源保留回归；使用合成资料核方法勘误、预热及版本升级边界。"""
import copy
from datetime import date,timedelta

import pytest
from guanheng_app.observation.breadth_provenance import retain_history_provenance
from guanheng_app.observation.breadth_models import admit_definition,definition
from guanheng_app.observation.breadth_trends import attach_trends,definition as trend_definition
from guanheng_app.observation.contracts import ObservationError


def previous(metric='breadth.ashare'):
    method=definition(metric)
    value=copy.deepcopy(method)
    value['limitations']=['old method note that needs correction']
    value['source']='old method source'
    value['history_extension']=dict(schema='observation-history-extension/1',recipe_sha256='a'*64,
        definition_version=method['definition_version'],interval=['2026-08-03','2026-10-30'],
        source='official frozen history',source_url='https://www.bse.cn/',point_in_time=False,
        limitations=['latest identity reconstruction; historical availability unknown'])
    return value


def test_same_method_updates_method_notes_and_keeps_history_independently():
    prior=previous();original=copy.deepcopy(prior)
    method=definition('breadth.ashare')
    value=admit_definition('breadth.ashare',prior,[],[])
    assert value['history_extension']==prior['history_extension']
    assert value['limitations']==method['limitations']+prior['history_extension']['limitations']
    assert 'old method note that needs correction' not in value['limitations']
    assert value['source']==method['source']+'；历史补齐：official frozen history'
    assert prior==original
    value['history_extension']['limitations'].append('consumer mutation')
    assert prior==original


def test_repeated_regeneration_never_duplicates_history_notes_or_source():
    prior=previous();method=definition('breadth.ashare')
    once=retain_history_provenance(method,prior,method)
    twice=retain_history_provenance(once,once,method)
    assert twice==once


@pytest.mark.parametrize('bad',[
    {'schema':'other'}, {'recipe_sha256':'not-a-sha'}, {'definition_version':'other/1'},
    {'interval':['2026-08-03','2026-02-30']}, {'interval':['2026-10-30','2026-08-03']},
    {'interval':['2026-08-03T00:00:00','2026-10-30']}, {'interval':['2026-08-03']},
    {'point_in_time':0}, {'source':''}, {'source_url':None}, {'limitations':'not-list'}, {'limitations':['']}
])
def test_invalid_producer_descriptor_is_rejected(bad):
    prior=previous();prior['history_extension'].update(bad)
    with pytest.raises(ObservationError) as caught:admit_definition('breadth.ashare',prior,[],[])
    assert caught.value.code=='invalid_history_provenance'


def test_method_change_does_not_inherit_old_history_claims():
    prior=previous();new_method=definition('breadth.ashare');new_method['definition_version']='breadth.ashare/3'
    # 调用方在新版本中误带旧来源及限制时，输出保留新方法的规范说明；
    # 新历史资格继续由生产者确认。
    changed=copy.deepcopy(prior);changed['definition_version']=new_method['definition_version']
    value=retain_history_provenance(changed,prior,new_method)
    assert 'history_extension' not in value
    assert value['source']==new_method['source'] and value['limitations']==new_method['limitations']


@pytest.mark.parametrize('metric',['breadth.ashare','turnover.gt5.shsz'])
def test_actual_complete_history_upgrade_drops_the_previous_method_claims(metric):
    method=definition(metric)
    prior=copy.deepcopy(method);prior['definition_version']=metric+'/1'
    prior['source']='legacy source';prior['limitations']=['legacy method claim']
    prior['history_extension']=dict(previous()['history_extension'],definition_version=prior['definition_version'])
    rows=[dict(date='2026-10-30')]
    upgraded=admit_definition(metric,prior,rows,rows)
    assert upgraded['definition_version']==metric+'/2'
    assert 'history_extension' not in upgraded
    assert upgraded['limitations']==method['limitations'] and upgraded['source']==method['source']
    with pytest.raises(ObservationError) as caught:
        admit_definition(metric,prior,rows,[])
    assert caught.value.code=='stock_method_mismatch'


def test_existing_no_history_snapshots_keep_the_original_behavior():
    method=definition('breadth.ashare')
    value=admit_definition('breadth.ashare',method,[],[])
    assert value==method


def test_both_derived_definitions_keep_history_and_original_warmup_values():
    # 合成涨跌家数固定为6和4，EMA及MSI期望值可以直接核算。
    days=[(date(2026,1,1)+timedelta(days=n)).isoformat() for n in range(59)]
    metrics={'breadth.ashare':[dict(date=day,advancing_count=6,declining_count=4,market_count=10,unclassified_count=0) for day in days],
             'rana.ashare':[dict(date=day,rana=200) for day in days]}
    datasets={key:metrics[key] for key in ('breadth.ashare','rana.ashare')};definitions={}
    for kind in ('msi','breadth.thrust'):
        metric=kind+'.ashare';method=trend_definition(kind,'ashare')
        method['history_extension']=dict(previous()['history_extension'],definition_version=method['definition_version'])
        definitions[metric]=method
    original=copy.deepcopy(definitions)
    days=[r['date'] for r in datasets['breadth.ashare']]
    attach_trends(datasets,definitions,{'source.cn_calendar':[dict(date=day,is_open=1) for day in days]})
    for kind,valid in (('msi',21),('breadth.thrust',50)):
        metric=kind+'.ashare';field='msi' if kind=='msi' else 'breadth_thrust'
        assert definitions[metric]['history_extension']==original[metric]['history_extension']
        assert original[metric]['history_extension']['limitations'][0] in definitions[metric]['limitations']
        assert sum(r[field] is not None for r in datasets[metric])==valid
        assert all(r[field]==pytest.approx(0 if kind=='msi' else .6) for r in datasets[metric] if r[field] is not None)
    attach_trends(datasets,definitions,{'source.cn_calendar':[dict(date=day,is_open=1) for day in days]})
    assert definitions['msi.ashare']['limitations'].count(original['msi.ashare']['history_extension']['limitations'][0])==1
