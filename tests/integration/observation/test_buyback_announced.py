"""公告金额的来源日期、空日、金额及凭证归档回归。"""
from datetime import date,timedelta
import json
from time import monotonic

import httpx
import pytest

from guanheng_app.observation import buyback_announced as source,ipo_supply
from guanheng_app.observation.source_fetch import CollectionBudget,Fetcher,SourceFailure
from guanheng_app.observation.storage import ContentStore


def test_local_history_never_needs_network():
    class Offline:
        def __getattr__(self,name):raise AssertionError('local reuse must not request network')
    prior=[dict(date='2026-11-20',amount_cny=100,announcement_count=1)]
    assert source.history(Offline(),['2026-11-20'],existing=prior)==prior


def public_packet(days,rows,total=None):
    key='DIM{'+days[0]+'|'+days[-1]+'|5|天}已回购金额求和'
    data=[]
    for code,amount in rows:
        data.append(dict(SECURITY_CODE=code,**{'MTM_EXTRA|'+key:json.dumps([dict(
            colHeads=[dict(colProp='DIM_REPURAMOUNT',unit='元'),dict(colProp='DIM_UPDATEDATE',unit='')],
            data=[dict(DIM_UPDATEDATE=days[-1],DIM_REPURAMOUNT=amount,SUM=str(source._money(amount)))])])}))
    return dict(code='100'if rows else '201',data=dict(result=dict(
        columns=[dict(title='回购',key=key)],dataList=data,total=len(rows)if total is None else total)))


def test_public_query_pagination_uses_no_key_and_checks_complete_range(tmp_path):
    days=['2026-11-16','2026-11-17','2026-11-18','2026-11-19','2026-11-20'];calls=[]
    def handle(request):
        payload=json.loads(request.content);calls.append(payload)
        assert 'em_api_key'not in request.headers and 'token'not in payload
        import re
        requested=['-'.join(parts)for parts in re.findall(r'(\d{4})年(\d{2})月(\d{2})日',payload['keyWord'])]
        body=public_packet(requested,[('60000'+str(payload['pageNo']),'1亿')],total=2)
        return httpx.Response(200,stream=httpx.ByteStream(json.dumps(body).encode()))
    fetch=Fetcher(ContentStore(tmp_path),['np-tjxg-g.eastmoney.com'],budget=CollectionBudget(monotonic()+10),
        client=httpx.Client(transport=httpx.MockTransport(handle)))
    rows=source.public_window(fetch,days)
    assert rows[-1]['amount_cny']==200000000 and rows[-1]['announcement_count']==2
    assert calls[0]['fingerprint']==calls[1]['fingerprint'] and [c['pageNo']for c in calls[:2]]==[1,2]
    assert fetch.records[-1]['kind']=='choice_window'
    proof=json.loads(fetch.objects.get(rows[-1]['source_sha256']))
    assert len(proof['parents'])==2
    fetch.close()


def test_public_preview_cannot_be_used_as_complete_amount():
    days=['2026-11-16','2026-11-17','2026-11-18','2026-11-19','2026-11-20']
    packet=public_packet(days,[('600001','1亿')]);r=packet['data']['result'];key='MTM_EXTRA|'+r['columns'][0]['key']
    groups=json.loads(r['dataList'][0][key]);groups[0]['data'][0]['SUM']='300000000';r['dataList'][0][key]=json.dumps(groups)
    with pytest.raises(SourceFailure,match='choice_public_query_incomplete'):
        source.parse_public(r['columns'],r['dataList'],r['total'],days)
    empty=public_packet(days,[])['data']['result']
    assert all(r['amount_cny']==0 for r in source.parse_public(empty['columns'],[],0,days))


def test_definition_switch_clears_old_ratio_before_any_new_window_is_published():
    old=dict(date='2026-11-20',close=100,ratio=9,buyback=6,ipo=1,reduction=2)
    row,=ipo_supply.versioned_history([old])
    assert row['close']==100 and row['ipo']==1 and row['reduction']==2
    assert row['ratio'] is None and row['buyback'] is None and row['buyback_window_missing']==20
    assert old['ratio']==9
    assert ipo_supply.versioned_history([dict(row,ratio=3)])[0]['ratio']==3

@pytest.mark.parametrize('amount,expected',[('7230.59万',72305900),('2.35亿',235000000),('0.00',0)])
def test_public_amount_units(amount,expected):
    days=['2026-11-20']
    value=public_packet(days,[('600001',amount)])['data']['result']
    assert source.parse_public(value['columns'],value['dataList'],value['total'],days)[-1]['amount_cny']==expected


@pytest.mark.parametrize('mutation',[
    lambda r:r.update(total=2),
    lambda r:r['columns'][0].update(key='DIM{2025-11-16|2025-11-20|5|天}已回购金额求和'),
    lambda r:r['dataList'].append(r['dataList'][0]),
])
def test_public_incomplete_queries_keep_gaps(mutation):
    days=['2026-11-16','2026-11-17','2026-11-18','2026-11-19','2026-11-20']
    value=public_packet(days,[('600001','1亿')])['data']['result'];mutation(value)
    with pytest.raises(SourceFailure):source.parse_public(value['columns'],value['dataList'],value['total'],days)


def test_multiday_rounding_cannot_certify_omitted_dates_as_zero():
    days=['2026-11-16','2026-11-17','2026-11-18','2026-11-19','2026-11-20']
    value=public_packet(days,[('600001','1.00亿')])['data']['result'];key='MTM_EXTRA|'+value['columns'][0]['key']
    groups=json.loads(value['dataList'][0][key]);groups[0]['data'][0]['SUM']='100010000';value['dataList'][0][key]=json.dumps(groups)
    rows=source.parse_public(value['columns'],value['dataList'],value['total'],days)
    assert [row['date']for row in rows]==['2026-11-20']
    # 单日查询的独立SUM可以保留预览外的小额方案，金额无需猜测。
    value['columns'][0]['key']='DIM{2026-11-20}已回购金额求和'
    value['dataList'][0]['MTM_EXTRA|'+value['columns'][0]['key']]=value['dataList'][0].pop(key)
    assert source.parse_public(value['columns'],value['dataList'],value['total'],['2026-11-20'])[0]['amount_cny']==100010000
