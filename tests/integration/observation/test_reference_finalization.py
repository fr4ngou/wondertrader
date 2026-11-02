"""期货与基差在同次最终化取得一致上证参考，重复更新保持数值。"""
import copy
import pytest
from guanheng_app.observation.refresh_models import market_models,attach_sse_reference

@pytest.mark.parametrize('product,spot',[('if','sh000300'),('ih','sh000016'),('ic','sh000905'),('im','sh000852')])
def test_futures_and_basis_share_benchmark_in_first_refresh(product,spot):
    day='2026-10-30'
    tables={'market.sh000001':[dict(date=day,close=3599.02)],
            'market.'+spot:[dict(date=day,close=4000.0)]}
    datasets={'cffex_'+product:[dict(date=day,front_close=4012.0,front_contract=product.upper()+'2611',sse_reference=None)]}
    definitions={'basis_'+product:dict(field_schema={})}
    def finalize():
        market_models(tables,datasets,definitions,{},'2026-11-01')
        attach_sse_reference(tables,datasets)
    finalize()
    assert datasets['cffex_'+product][0]['sse_reference']==3599.02
    assert datasets['basis_'+product][0]['sse_reference']==3599.02
    assert datasets['basis_'+product][0]['basis_points']==12
    once=copy.deepcopy(datasets);finalize()
    assert datasets==once
    tables['market.sh000001'][0]['close']=3601.5
    finalize()
    assert datasets['cffex_'+product][0]['sse_reference']==datasets['basis_'+product][0]['sse_reference']==3601.5

def test_reference_outside_current_source_coverage_retains_qualified_archive():
    legacy=dict(date='2014-01-02',sse_reference=2109.39)
    datasets={name:[dict(legacy)] for name in ('cffex_if','basis_if','pb_shsz_daily')}
    attach_sse_reference({'market.sh000001':[dict(date='2026-10-30',close=3599.02)]},datasets)
    assert all(rows==[legacy] for rows in datasets.values())
