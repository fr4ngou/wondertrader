"""官方HTTP导出→份额事实→原采集owner；合成OOXML，不联网且不依赖pandas。"""
import hashlib
import io
import json
from pathlib import Path
import sys
import struct
import time
import zipfile

sys.path.insert(0,str(Path(__file__).parent))
from msf_fixture import ContentStore,DAYS,QmtTransport,plan,query,szse_xlsx
import httpx
import pytest

from integrations.guanheng.market_supplement_sources import collect_external,SourceUnavailable
from integrations.guanheng.market_supplement_capture import collect_supplement,SupplementPending
from integrations.guanheng.market_supplement_store import MarketSupplementStore
from guanheng_app.observation.source_fetch import CollectionBudget,Fetcher

RECEIVED='2026-11-06T09:37:57.219933+00:00'


def receipt(raw):
    return dict(body=raw,sha256=hashlib.sha256(raw).hexdigest(),received_at=RECEIVED)


def test_szse_verified_http_export_preserves_shares_without_ten_thousand_scaling():
    raw=szse_xlsx(DAYS[-1]);calls=[]
    def get(url,params,referer):
        calls.append((url,params,referer))
        assert url=='http://www.szse.cn/api/report/ShowReport'
        assert params['SHOWTYPE']=='xlsx' and params['CATALOGID']=='scsj_fund_jjgm'
        assert params['txtStart']==DAYS[-1] and params['txtEnd']==DAYS[-1]
        return receipt(raw)
    first=collect_external('etf_total_shares','SZSE.159352',DAYS[-1],get)
    second=collect_external('etf_total_shares','SZSE.159780',DAYS[-1],get)
    assert first==dict(value='32469101746',unit='share',source='SZSE',parents=[hashlib.sha256(raw).hexdigest()],received_at=RECEIVED)
    assert second['value']=='4037248583'  # 表头是份，人工原值直接进入标准事实。
    assert len(calls)==2


@pytest.mark.parametrize('mode',['inline','shared'])
def test_valid_xml_cell_encodings_keep_small_and_fractional_share_precision(mode):
    raw=szse_xlsx(DAYS[-1],mode=mode,rows=[[DAYS[-1],'159352','合成ETF', '123.125']])
    result=collect_external('etf_total_shares','SZSE.159352',DAYS[-1],lambda *a:receipt(raw))
    assert result['value']=='123.125' and result['unit']=='share'


@pytest.mark.parametrize('case,expected',[
    ('wrong_day','source_date_mismatch'),
    ('invalid_code','source_symbol_mismatch'),
    ('duplicate','source_duplicate_record'),
    ('missing','source_record_missing'),
    ('ten_thousand_header','source_unit_unverified'),
    ('wrong_header','source_unit_unverified'),
    ('negative','source_value_invalid'),
])
def test_invalid_table_never_becomes_a_share_fact(case,expected):
    rows=[[DAYS[-1],'159352','合成ETF',123]];header=None
    if case=='wrong_day':rows[0][0]=DAYS[0]
    elif case=='invalid_code':rows[0][1]='15935A'
    elif case=='duplicate':rows*=2
    elif case=='missing':rows[0][1]='159780'
    elif case=='ten_thousand_header':header=['日期','基金代码','基金简称','基金规模(万份)']
    elif case=='wrong_header':header=['日期','基金代码','基金简称','基金净值(元)']
    elif case=='negative':rows[0][3]=-123
    raw=szse_xlsx(DAYS[-1],rows=rows,header=header)
    with pytest.raises(SourceUnavailable) as failure:
        collect_external('etf_total_shares','SZSE.159352',DAYS[-1],lambda *a:receipt(raw))
    assert failure.value.code==expected


def replace_member(raw,name,change):
    output=io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(raw)) as original,zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as result:
        for member in original.infolist():
            data=original.read(member)
            result.writestr(member.filename,change(data) if member.filename==name else data)
    return output.getvalue()


def broken_deflate(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        info=archive.getinfo('xl/worksheets/sheet1.xml')
        name_size,extra_size=struct.unpack_from('<HH',raw,info.header_offset+26)
        start=info.header_offset+30+name_size+extra_size
    damaged=bytearray(raw);damaged[start]=(damaged[start]&0xF8)|7  # Deflate保留块类型11。
    return bytes(damaged)


@pytest.mark.parametrize('case',['html','truncated_zip','broken_deflate','invalid_xml','formula','members','expanded_bytes','rows'])
def test_non_xlsx_or_unbounded_documents_are_explicit_source_gaps(case):
    raw=szse_xlsx(DAYS[-1])
    if case=='html':raw=b'<html><body>synthetic edge challenge</body></html>'
    elif case=='truncated_zip':raw=raw[:100]
    elif case=='broken_deflate':raw=broken_deflate(raw)
    elif case=='invalid_xml':raw=replace_member(raw,'xl/worksheets/sheet1.xml',lambda b:b'<worksheet>')
    elif case=='formula':raw=replace_member(raw,'xl/worksheets/sheet1.xml',lambda b:b.replace(b'<v>32469101746</v>',b'<f>1+2</f><v>32469101746</v>'))
    elif case=='members':raw=szse_xlsx(DAYS[-1],extra_members=[(f'extra/{i}.xml','x') for i in range(65)])
    elif case=='expanded_bytes':raw=szse_xlsx(DAYS[-1],extra_members=[('padding.xml','x'*(16*1024*1024+1))])
    elif case=='rows':raw=szse_xlsx(DAYS[-1],rows=[[DAYS[-1],'159352','合成ETF',1]]*20001)
    with pytest.raises(SourceUnavailable) as failure:
        collect_external('etf_total_shares','SZSE.159352',DAYS[-1],lambda *a:receipt(raw))
    assert failure.value.code.startswith('source_')
    assert 'edge challenge' not in str(failure.value)


@pytest.mark.parametrize('damage',['sha','received'])
def test_original_bytes_receipt_identity_and_utc_are_required(damage):
    raw=szse_xlsx(DAYS[-1]);record=receipt(raw)
    record['sha256' if damage=='sha' else 'received_at']='0'*64 if damage=='sha' else '2026-11-05'
    with pytest.raises(SourceUnavailable) as failure:
        collect_external('etf_total_shares','SZSE.159352',DAYS[-1],lambda *a:record)
    assert failure.value.code=='source_receipt_invalid'


@pytest.mark.parametrize('bad_response',['html','broken_deflate'])
def test_fetcher_collector_retains_raw_parents_and_recovers_only_source_gaps(tmp_path,bad_response):
    calls=[];bad_last={'value':True};bodies={d:szse_xlsx(d,mode='shared') for d in DAYS}
    def handler(request):
        assert request.method=='GET' and request.url.scheme=='http'
        assert request.url.host=='www.szse.cn' and request.url.path=='/api/report/ShowReport'
        assert request.url.params['SHOWTYPE']=='xlsx'
        day=request.url.params['txtStart'];assert request.url.params['txtEnd']==day
        assert 'txtDm' not in request.url.params  # 已验证原版全表路径，目标筛选发生在解析后。
        calls.append(day)
        body=bodies[day]
        if day==DAYS[-1] and bad_last['value']:
            body=b'<html>synthetic gateway failure</html>' if bad_response=='html' else broken_deflate(body)
        return httpx.Response(200,stream=httpx.ByteStream(body))
    objects=ContentStore(tmp_path/'raw');qmt=QmtTransport()
    target=plan(('etf_total_shares','SZSE.159352'),('etf_total_shares','SZSE.159780'))
    def make_fetch():
        budget=CollectionBudget(time.monotonic()+10,max_requests=20,max_bytes=4*1024*1024,response_bytes=1024*1024)
        return Fetcher(objects,['www.szse.cn'],budget=budget,client=httpx.Client(transport=httpx.MockTransport(handler),trust_env=False))
    def collect(fetch):
        return collect_supplement(target,DAYS[-1],DAYS,tmp_path/'work',objects=objects,fetch=fetch,
            qmt_transport=qmt,calendar_coverage=(DAYS[0],DAYS[-1]),deadline=time.monotonic()+10)
    first=make_fetch()
    try:
        with pytest.raises(SupplementPending):collect(first)
        coverage=json.loads((tmp_path/'work/COVERAGE.json').read_bytes())
        assert coverage['expected']==4 and coverage['observed']==2 and len(coverage['gaps'])==2
        prior=list(json.loads((tmp_path/'work/STATE.json').read_bytes())['rows'].values())
        assert {r['date'] for r in prior}=={DAYS[0]}
        assert not (tmp_path/'work/catalog.json').exists()
    finally:first.close()
    bad_last['value']=False;second=make_fetch()
    try:descriptor=collect(second)
    finally:second.close();qmt.close()
    assert calls.count(DAYS[0])==1 and second.budget.http_requests==1
    store=MarketSupplementStore(descriptor)
    try:
        rows=store.query(query(symbols=['SZSE.159352','SZSE.159780']))['rows']
        assert len(rows)==4 and {r['value'] for r in rows}=={'4037248583','32469101746'}
        assert [r for r in rows if r['date']==DAYS[0]]==prior
        for row in rows:
            proof=json.loads(objects.get(row['source_sha256']))
            expected=hashlib.sha256(bodies[row['date']]).hexdigest()
            assert proof['parents']==[expected] and objects.get(expected)==bodies[row['date']]
            assert row['unit']=='share' and row['available_at'] is None
            assert row['received_at'].endswith('+00:00')
        store.verify_sources()
    finally:store.close()
    assert first.client.is_closed and second.client.is_closed
