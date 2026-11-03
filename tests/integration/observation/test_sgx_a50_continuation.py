"""SGX真实官方月表、独立日/月游标及后继期次；合成未来记录只作自动接续回归。"""
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
import json
import time

import pytest

from guanheng_app.observation.providers import sgx
from guanheng_app.observation.sgx_reports import monthly, report_pdf, table_value, TABLES
from guanheng_app.observation.source_fetch import CollectionBudget, SourceFailure
from guanheng_app.observation.refresh_models import source_window


FIXTURES = Path(__file__).resolve().parents[2] / 'fixtures/observation/sgx'
SOURCE = dict(url='https://www.sgx.com/config/appconfig.json', datasets=['sgx_a50_monthly'],
              window_mode='report_latest', max_pages=4)
TITLE = 'September 2026'


class OfficialCapture:
    """官网原件回放；保持原JSON嵌套与原完整PDF，用调用记录核真实读取对象。"""
    def __init__(self):
        self.budget = CollectionBudget(time.monotonic()+30)  # 整次采集唯一总截止。
        self.config = json.loads((FIXTURES/'appconfig.json').read_bytes())  # 公开配置的必要字段投影。
        self.listing = json.loads((FIXTURES/'monthly-list.json').read_bytes())  # 原官网月报目录。
        self.calls = []  # 本轮URL与查询，用于核日/月来源隔离及分页。

    def get(self, url, params=None):
        self.calls.append((url, params))
        if 'appconfig.json' in url: return json.dumps(self.config).encode()
        if 'content-api' in url: return json.dumps(self.listing).encode()
        if url.endswith('.pdf'): return (FIXTURES/'sgx-202609.pdf').read_bytes()
        if '/history/cc/CN' in url: return (FIXTURES/'daily-latest.json').read_bytes()
        raise AssertionError(url)


def test_official_monthly_pdf_preserves_original_whole_month_and_month_end_values():
    fetch = OfficialCapture()
    result = sgx(fetch, SOURCE, '2026-09-23', '2026-11-03')
    assert result == {'sgx_a50_monthly': [dict(date='2026-09-30', oi=836157, volume=8917354,
        report_file='sgx_202609.pdf', oi_page=28, volume_page=14, basis_points=None, available_at=None)]}
    assert len(fetch.calls)==3 and fetch.calls[-1][0].endswith('.pdf')
    query=json.loads(fetch.calls[1][1]['variables'])
    assert query['lang']=='EN' and query['offset']==0 and query['limit']==24


def test_original_daily_product_aggregation_is_kept_separate():
    fetch = OfficialCapture()
    daily = sgx(fetch, dict(url='https://api.sgx.com/derivatives/v1.0/history/cc/CN',
                           datasets=['sgx_a50_daily']), '2026-10-23', '2026-11-03')
    assert daily == {'sgx_a50_daily': [dict(date='2026-10-30', oi=1043060, volume=496725,
                                          basis_points=None, available_at=None)]}
    assert len(fetch.calls)==1 and fetch.calls[0][1]['category']=='futures'


def test_noninteger_daily_source_value_keeps_original_unknown_unit_rule():
    data=dict(meta=dict(code='200'), data=[{'base-date':'20210827', 'total-volume':123.5,
                                         'open-interest':1000.}])
    fetch=SimpleNamespace(get=lambda *args: json.dumps(data).encode())
    row=sgx(fetch,dict(url='https://api.sgx.com/derivatives/v1.0/history/cc/CN'),
            '2021-08-27','2021-08-27')['sgx_a50_daily'][0]
    assert row['oi']==1000 and row['volume'] is None and row['source_volume_raw']==123.5
    assert row['source_volume_status']=='官方源非整手值，单位待核'


def test_independent_monthly_report_cursor_keeps_september_reachable():
    config=dict(max_days_per_batch=40)
    assert source_window('2026-09-30','2026-11-03',SOURCE,config)==('2026-09-23','2026-11-03')
    assert source_window('2026-10-30','2026-11-03',{},config)[0]=='2026-10-23'


def test_continuation_page_without_a50_does_not_duplicate_or_fail_table():
    text=(FIXTURES/'volume-continuation.txt').read_text(encoding='utf8')
    assert table_value(text,TABLES['volume'],TITLE) is None


def test_current_month_column_is_selected_before_ytd_or_previous_year():
    text=(FIXTURES/'volume-page.txt').read_text(encoding='utf8')
    assert table_value(text,TABLES['volume'],TITLE)==8917354
    assert '91,886,267' in text and '11,298,690' in text


@pytest.mark.parametrize('change', ['missing_column','fractional','duplicate','missing_year'])
def test_changed_month_table_fails_without_guessing_columns(change):
    text=(FIXTURES/'volume-page.txt').read_text(encoding='utf8')
    if change=='missing_column': text=text.replace('Sep 2026','Oct 2026')
    elif change=='fractional': text=text.replace('8,917,354','8917354.5')
    elif change=='duplicate':
        line=next(l for l in text.splitlines() if l.startswith('SGX FTSE China A50 Index Futures '))
        text+='\n'+line
    else: text=text.replace('FYTD 2027','unknown aggregate')
    with pytest.raises(SourceFailure): table_value(text,TABLES['volume'],TITLE)


@pytest.mark.parametrize('change', ['outside_cms','external_pdf','duplicate_period','wrong_mime','unknown_title'])
def test_source_identity_changes_reject_whole_result(change):
    fetch=OfficialCapture()
    first=fetch.listing['data']['list']['results'][0]['data']
    if change=='outside_cms': fetch.config['endpoints']['CMS_API_URL']='https://example.invalid'
    elif change=='external_pdf': first['report']['data']['file']['data']['url']='https://example.invalid/a.pdf'
    elif change=='duplicate_period': fetch.listing['data']['list']['results'][1]=deepcopy(fetch.listing['data']['list']['results'][0])
    elif change=='wrong_mime': first['report']['data']['file']['data']['filemime']='text/plain'
    else: first['title']='Unknown quarter 2026'
    # 避免重复期次场景先解析原PDF，测试保持对目录完整性的观察。
    with pytest.raises(SourceFailure): monthly(fetch,SOURCE,'2026-09-23','2026-11-03')


def test_future_report_is_not_imported_and_no_pdf_requested():
    fetch=OfficialCapture()
    result=monthly(fetch,SOURCE,'2026-09-23','2026-10-01')
    assert result=={'sgx_a50_monthly': []}
    assert not any(url.endswith('.pdf') for url,_ in fetch.calls)


def test_original_deadline_applies_before_pdf_decoding():
    budget=CollectionBudget(time.monotonic()-1)
    with pytest.raises(SourceFailure) as caught:
        report_pdf((FIXTURES/'sgx-202609.pdf').read_bytes(),TITLE,budget)
    assert caught.value.code=='collection_timeout'


def test_source_listing_budget_does_not_silently_claim_coverage():
    fetch=OfficialCapture()
    with pytest.raises(SourceFailure) as caught:
        monthly(fetch,dict(SOURCE,max_pages=1),'2000-01-01','2020-10-01')
    assert caught.value.code=='sgx_monthly_listing_coverage_incomplete'


def test_new_month_and_moved_pdf_pages_are_discovered(monkeypatch):
    # 合成未来十月报告；目标值刻意与九月不同，避免复用旧金额或单日日值通过。
    import pypdf
    fetch=OfficialCapture()
    first=deepcopy(fetch.listing['data']['list']['results'][0])
    data=first['data'];data['title']='October 2026'
    data['reportDate']=data['report']['data']['date']=int(datetime.fromisoformat('2026-11-10T10:00:00+08:00').timestamp())
    fetch.listing['data']['list']=dict(count=1,results=[first])
    volume=(FIXTURES/'volume-page.txt').read_text(encoding='utf8').replace('September 2026','October 2026').replace('Sep 2026','Oct 2026').replace('8,917,354','9,123,456')
    oi=(FIXTURES/'oi-page.txt').read_text(encoding='utf8').replace('September 2026','October 2026').replace('Sep 2026','Oct 2026').replace('836,157','900,001')
    closed=[]
    pages=[SimpleNamespace(extract_text=lambda:'unrelated page'),SimpleNamespace(extract_text=lambda:volume),SimpleNamespace(extract_text=lambda:oi)]
    book=SimpleNamespace(is_encrypted=False,xref={},xref_objStm={},root_object={'/Pages':{'/Count':3}},pages=pages,close=lambda:closed.append(True))
    monkeypatch.setattr(pypdf,'PdfReader',lambda *args,**kwargs:book)
    result=monthly(fetch,SOURCE,'2026-09-23','2026-11-11')['sgx_a50_monthly'][0]
    assert result['date']=='2026-10-31' and result['volume']==9123456 and result['oi']==900001
    assert result['volume_page']==2 and result['oi_page']==3 and result['report_file']=='sgx_202610.pdf'
    assert closed==[True]
