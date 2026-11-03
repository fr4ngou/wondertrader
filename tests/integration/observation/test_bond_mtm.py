"""原45自然日假定、季度基准、指数身份与不改旧模型数值的定向回归。"""
from copy import deepcopy
from urllib.parse import parse_qs,urlsplit
import json
import time

import pytest

from guanheng_app.observation import bond_mtm
from guanheng_app.observation.source_fetch import CollectionBudget,SourceFailure


def inputs():
    quarters=[dict(date='2026-06-30',fund_records=1200,bond_pct=60,stock_pct=20,cash_pct=10),
              dict(date='2026-09-30',fund_records=1400,bond_pct=50,stock_pct=30,cash_pct=10)]
    stocks={'2026-06-30':100,'2026-09-30':120,'2026-11-13':110,'2026-11-14':108}
    bonds={'2026-06-30':100,'2026-09-30':102,'2026-11-13':103,'2026-11-14':104}
    return quarters,stocks,bonds,sorted(stocks)


def test_day44_uses_old_quarter_and_day45_switches_to_new_quarter():
    q,s,b,c=inputs();old=bond_mtm.calculate('2026-11-13',q,s,b,c);new=bond_mtm.calculate('2026-11-14',q,s,b,c)
    assert old['anchor_period']=='2026-06-30' and old['model_eligible_date']=='2026-08-14'
    assert new['anchor_period']=='2026-09-30' and new['model_eligible_date']=='2026-11-14'
    assert old['estimate']==pytest.approx(100*(60*1.03)/(60*1.03+20*1.1+10+10))
    assert new['estimate']==pytest.approx(100*(50*104/102)/(50*104/102+30*108/120+10+10))


def test_common_source_base_is_last_real_date_not_later_than_quarter_end():
    q,s,b,c=inputs();s['2026-09-29']=s.pop('2026-09-30');b['2026-09-29']=b.pop('2026-09-30');c=sorted(s)
    value=bond_mtm.calculate('2026-11-14',q,s,b,c)
    assert value['anchor_date']=='2026-09-29'
    assert value['stock_index_base']==120 and value['bond_index_base']==102


def test_partial_fund_sample_is_not_used_as_a_complete_quarter():
    q,s,b,c=inputs();q[-1]['fund_records']=999
    assert bond_mtm.calculate('2026-11-14',q,s,b,c)['anchor_period']=='2026-06-30'


def test_missing_current_day_or_quarter_does_not_fill_an_estimate():
    q,s,b,c=inputs();assert bond_mtm.calculate('2026-11-12',q,s,b,c) is None
    assert bond_mtm.calculate('2026-11-14',[],s,b,c) is None


def test_append_keeps_old_values_and_adds_only_actual_common_dates():
    q,s,b,c=inputs();old=dict(date='2026-11-13',estimate=62.5,reference=3333,available_at=None,csi_all_reference=110)
    tables={'source.csi_all':[dict(date=d,close=v) for d,v in s.items()],bond_mtm.TABLE:[dict(date=d,close=v) for d,v in b.items()]}
    datasets={bond_mtm.METRIC:[deepcopy(old)],'holdings_fund':q}
    bond_mtm.extend(tables,datasets,check=lambda:None)
    assert datasets[bond_mtm.METRIC][0]==old
    assert [r['date'] for r in datasets[bond_mtm.METRIC]]==['2026-11-13','2026-11-14']
    assert datasets[bond_mtm.METRIC][-1]['reference'] is None
    saved=deepcopy(datasets);bond_mtm.extend(tables,datasets,check=lambda:None);assert datasets==saved


def test_expired_calculation_does_not_partly_append_rows():
    q,s,b,c=inputs();datasets={bond_mtm.METRIC:[],'holdings_fund':q};before=deepcopy(datasets)
    tables={'source.csi_all':[dict(date=d,close=v) for d,v in s.items()],bond_mtm.TABLE:[dict(date=d,close=v) for d,v in b.items()]}
    def expired():raise SourceFailure('collection_timeout')
    with pytest.raises(SourceFailure):bond_mtm.extend(tables,datasets,check=expired)
    assert datasets==before


class IndexCapture:
    """合成有限指数回包，明确CFZS/00；真实6209期原件另由主链存证。"""
    def __init__(self):
        self.budget=CollectionBudget(time.monotonic()+20)  # 全部请求沿同一总截止。
        self.records=[]  # 固定请求回执容器，正式适配器写入解析身份。
        self.calls=[]  # 原POST地址及公开表单，验证未改成GET或换指数。
        self.tree=[dict(id=bond_mtm.INDEX_ID,name='中债-新综合指数')]  # 官方身份合同的合成样本。
        self.data=dict(dqcName={'00':'总值'},dqcList=['00'],CFZS_00={'1793548800000':257.851,'1793635200000':258})  # 上海11/2、11/3零点原毫秒形态。

    def post_readonly(self,url,form):
        self.calls.append((url,form));self.records.append({});self.budget.request()
        return json.dumps(self.tree if 'queryTree' in url else self.data,ensure_ascii=False).encode()


def test_original_index_post_identity_timestamp_and_cutoff():
    fetch=IndexCapture();value=bond_mtm.history(fetch,dict(url=bond_mtm.URL),'2026-11-02','2026-11-02')
    assert value=={bond_mtm.TABLE:[dict(date='2026-11-02',close=257.851,available_at=None)]}
    params=parse_qs(urlsplit(fetch.calls[-1][0]).query)
    assert params['indexid']==[bond_mtm.INDEX_ID] and params['zslxt']==['CFZS'] and params['qxlxt']==['00']


@pytest.mark.parametrize('change',[
    lambda f:f.tree[0].update(name='中债-总指数'),
    lambda f:f.data.update(dqcName={'00':'1-3年'}),
    lambda f:f.data['CFZS_00'].update({'1793548800000':float('nan')}),
    lambda f:f.data['CFZS_00'].update({'1793548800001':250}),
    lambda f:f.data.update(CFZS_00={}),
])
def test_wrong_index_term_nonfinite_and_nonmidnight_data_rejected(change):
    fetch=IndexCapture();change(fetch)
    with pytest.raises(SourceFailure):bond_mtm.history(fetch,dict(url=bond_mtm.URL),'2026-11-02','2026-11-02')


def test_duplicate_json_keys_fail_in_original_shared_json_boundary():
    fetch=IndexCapture();original=fetch.post_readonly
    def repeated(url,form):
        body=original(url,form)
        return body if 'queryTree' in url else b'{"CFZS_00":{},"CFZS_00":{}}'
    fetch.post_readonly=repeated
    with pytest.raises(SourceFailure):bond_mtm.history(fetch,dict(url=bond_mtm.URL),'2026-11-02','2026-11-02')
