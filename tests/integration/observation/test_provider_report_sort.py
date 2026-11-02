"""报表供应商排序契约：方向数与列数一致，调用者提供唯一排序键。"""
import json
from time import monotonic

import pytest

from guanheng_app.observation.provider_reports import report_pages
from guanheng_app.observation.source_fetch import CollectionBudget,SourceFailure


class Vendor:
    def __init__(self):self.budget=CollectionBudget(monotonic()+5);self.requests=[]
    def get(self,url,params):
        self.budget.request('http');self.requests.append(dict(params))
        # 原真实9501：排序字段和顺序数量必须一致。
        if len(params['sortColumns'].split(','))!=len(str(params['sortTypes']).split(',')):
            return json.dumps(dict(success=False,result=None,code=9501))
        first=(params['pageNumber']-1)*500;end=min(first+500,501)
        return json.dumps(dict(success=True,result=dict(count=501,pages=2,
            data=[dict(TRADE_DATE='2026-10-30',SECURITY_CODE=str(index)) for index in range(first,end)])))


@pytest.mark.parametrize('sort,order',[('SECURITY_CODE',1),('TRADE_DATE,SECURITY_CODE','1,1'),('A,B,C','1,1,1')])
def test_unique_composite_sort_completes_all_pages_and_single_sort_keeps_original_protocol(sort,order):
    source=Vendor()
    rows=report_pages(source,'https://example.invalid',report='report',columns='ALL',filters='',sort=sort,max_pages=2)
    assert len(rows)==501 and len({row['SECURITY_CODE'] for row in rows})==501
    assert len(source.requests)==2 and all(params['sortTypes']==order for params in source.requests)


@pytest.mark.parametrize('sort',[None,1,[],True,'',' A','A,','A,,B','A,A','A;B','a.' ,'X'*129,'A'*1025])
def test_invalid_sort_is_rejected_before_vendor_request(sort):
    source=Vendor()
    with pytest.raises(SourceFailure,match='valuation_sort'):
        report_pages(source,'https://example.invalid',report='report',columns='ALL',filters='',sort=sort,
            max_pages=2,error_prefix='valuation')
    assert not source.requests
