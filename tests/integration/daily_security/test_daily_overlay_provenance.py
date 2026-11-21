"""上层日线合并保留下层逐段来源，汇总身份不充当原始捕获会话。"""
from copy import deepcopy
import threading

import pytest

from integrations.guanheng.daily_overlay import DailyOverlayMarket, _metadata, _select
from integrations.guanheng_market_client.source_history import validate_source_daily_data


def metadata(session):
    profile = dict(source_license='fixture',price_unit='CNY',volume_unit='lot',amount_unit='CNY')
    return _metadata(dict(provider='Qmt',instance_id='fixture',session_id=session,generation=1),
                     session*64,'fixture-daily',profile)


def bar(day, close):
    return dict(symbol='SSE.510300',date=day,open=close-.01,high=close+.02,
                low=close-.03,close=close,volume=123.,amount=456.)


class Source:
    """返回真实协议形态的多来源日线；不创建Reader或访问外部数据。"""
    def __init__(self):
        self.first = metadata('a')  # 前两日所属原始会话。
        self.last = metadata('b')  # 第三日所属另一原始会话。
        self.rows = {20261118:(bar(20261118,4.01),self.first),
                     20261119:(bar(20261119,4.06),self.first),
                     20261120:(bar(20261120,4.02),self.last)}  # 日期与原值绑定逐段来源。

    def call(self,request):
        data = _select(self.rows,request['request'],self.first)
        return dict(api_version='guanheng.market.v1',status=dict(code='Ok',reason=''),data=data)

    def close(self):
        pass


def overlay(base, *, shape='segments', tail=None):
    market = object.__new__(DailyOverlayMarket)
    market._owner = threading.get_ident()
    market._closed = False
    market._entries = {}
    market._base = base
    market._reader = None
    market._shape = shape
    market._maximum = 8388608
    market._tail = lambda security,after,query: deepcopy(tail or {})
    return market


def request(limit, *, end=20261120, view='current'):
    return dict(api_version='guanheng.market.v1',action='history.source-daily-query',
                request={'exchange':'SSE','code':'510300','from':20261118,'to':end,'limit':limit,'view':view})


@pytest.mark.parametrize('limit',[1,2,3])
@pytest.mark.parametrize('shape',['segments','dataset'])
def test_overlay_preserves_original_rows_and_metadata_from_composite_base(limit,shape):
    source = Source()
    market = overlay(source,shape=shape)
    query = request(limit)
    expected = source.call(query)['data']
    try:
        result = market.call(query)
        assert result['status']['code']=='Ok'
        data = validate_source_daily_data(result['data'],query['request'])
        assert data['bars']==expected['bars']
        if shape=='segments':
            assert data==expected
    finally:
        market.close()


def test_nested_overlay_and_writer_tail_keep_each_original_source():
    source = Source()
    tail_metadata = metadata('c')
    tail = {20261123:(bar(20261123,4.08),tail_metadata)}
    market = overlay(overlay(source),tail=tail)
    query = request(4,end=20261123)
    try:
        result = market.call(query)
        assert result['status']['code']=='Ok'
        data = validate_source_daily_data(result['data'],query['request'])
        assert [p['metadata'] for p in data['provenance']]==[source.first,source.last,tail_metadata]
        assert [p['count'] for p in data['provenance']]==[2,1,1]
        assert data['bars']==[v[0] for v in source.rows.values()]+[tail[20261123][0]]
    finally:
        market.close()


def test_archive_view_keeps_original_base_selection():
    source = Source()
    market = overlay(source)
    query = request(2,view='archive')
    try:
        assert market.call(query)==source.call(query)
    finally:
        market.close()
