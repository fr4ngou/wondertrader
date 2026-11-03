"""机构原报告单位、表列和游标的回归；完整PDF及HTTP主链另由冻结隔离验收证明。"""
from copy import deepcopy
from pathlib import Path
import json
import time

import pytest

from guanheng_app.observation import institution_reports as reports
from guanheng_app.observation.collection_config import validate_configuration
from guanheng_app.observation.contracts import ObservationError
from guanheng_app.observation.source_fetch import CollectionBudget,SourceFailure
from test_collection_config import configuration

FIXTURES=Path(__file__).resolve().parents[2]/'fixtures/observation/institutions'


def budget():return CollectionBudget(time.monotonic()+20)


class Pages:
    def __init__(self,mapping):
        self.mapping=mapping  # 明确的公开URL到原件字节映射；不连接真实来源。
        self.calls=[]  # 实际请求URL，用于证明按报告期读到数字正文或附件。
        self.records=[]  # 本次来源记录的替身容器；供正式适配器登记解析元数据。
        self.budget=budget()  # 所有读取与解析共用同一绝对截止。

    def get(self,url):
        self.budget.request();self.calls.append(url);self.records.append({})
        return self.mapping[url]


def custody_pages():
    return Pages({reports.PBC_URL:(FIXTURES/'pbc-market-directory.html').read_bytes(),
        'https://www.pbc.gov.cn/jinrongshichangsi/147160/147173/2026102618103714639/index.html':
        (FIXTURES/'pbc-market-september.html').read_bytes()})


def test_official_custody_whole_market_value_and_publication_are_separate():
    fetch=custody_pages();value=reports.pbc_custody(fetch,{'url':reports.PBC_URL},'2026-08-31','2026-11-03')
    assert value=={'bond.custody':[dict(date='2026-09-30',custody=210.8,available_at='2026-10-26')]}
    assert len(fetch.calls)==2 and fetch.records[-1]['parsed_document']['unit']=='CNY_trillion'


def test_custody_same_period_repeat_only_checks_directory_and_does_not_relabel_old_row():
    fetch=custody_pages();assert reports.pbc_custody(fetch,{'url':reports.PBC_URL},'2026-09-30','2026-11-03')=={'bond.custody':[]}
    assert fetch.calls==[reports.PBC_URL]


@pytest.mark.parametrize('old,new',[
    ('债券市场托管余额210.8万亿元','债券市场托管余额210.8亿元'),
    ('债券市场托管余额210.8万亿元','债券市场托管余额-210.8万亿元'),
    ('2026年9月末','2026年8月末'),
])
def test_custody_rejects_wrong_unit_negative_value_and_mismatched_month(old,new):
    fetch=custody_pages();url=next(k for k in fetch.mapping if k!=reports.PBC_URL)
    text=fetch.mapping[url].decode('utf8');assert old in text;fetch.mapping[url]=text.replace(old,new).encode()
    with pytest.raises(SourceFailure):reports.pbc_custody(fetch,{'url':reports.PBC_URL},'2026-08-31','2026-11-03')


def test_future_report_publication_is_not_admitted():
    fetch=custody_pages();assert reports.pbc_custody(fetch,{'url':reports.PBC_URL},'2026-08-31','2026-10-25')=={'bond.custody':[]}


def wealth_text(monkeypatch,text=None):
    text=text or (FIXTURES/'wealth-q3-report.txt').read_text(encoding='utf8')
    monkeypatch.setattr(reports,'pdf_pages',lambda body,budget,**kw:[text])


def test_real_wealth_q3_keeps_reported_components_and_rounded_sum(monkeypatch):
    wealth_text(monkeypatch)
    row=reports.wealth_pdf(b'%PDF-real-excerpt','2026-09-30','2026-10-21',budget())
    assert row==dict(date='2026-09-30',direct_pct=41.0,cd_pct=9.3,broad_pct=50.3,
                    broad_status='rounded_components_sum',available_at='2026-10-21')
    assert row['direct_pct']!=15.37/37.50*100


@pytest.mark.parametrize('old,new',[
    ('15.37','150.37'),('41.0%','99.0%'),('37.50','3.75'),('万亿元','亿元'),
])
def test_wealth_value_unit_denominator_and_ratio_changes_fail(monkeypatch,old,new):
    text=(FIXTURES/'wealth-q3-report.txt').read_text(encoding='utf8');assert old in text
    wealth_text(monkeypatch,text.replace(old,new))
    with pytest.raises(SourceFailure):reports.wealth_pdf(b'%PDF-real-excerpt','2026-09-30','2026-10-21',budget())


def test_wealth_future_period_is_discovered_without_a_hardcoded_file(monkeypatch):
    # 期次及链接为明确合成后继；数字形态沿真实季度报告，证明自动发现合同。
    directory='<a href="202701/new.html">中国银行业理财市场季度报告（2026年四季度）</a>'
    detail='<span>2027-01-21 </span><li data-recurl="new.pdf"></li>'
    fetch=Pages({reports.WEALTH_URL:directory.encode(),
        reports.WEALTH_URL+'202701/new.html':detail.encode(),reports.WEALTH_URL+'202701/new.pdf':b'%PDF-next'})
    text=(FIXTURES/'wealth-q3-report.txt').read_text(encoding='utf8').replace('三季度末','四季度末')
    wealth_text(monkeypatch,text)
    result=reports.wealth_allocation(fetch,{'url':reports.WEALTH_URL},'2026-09-30','2027-02-01')
    assert result['holdings_wealth'][0]['date']=='2026-12-31'
    assert fetch.calls[-1].endswith('/202701/new.pdf')


@pytest.mark.parametrize('name,expected',[
    ('citic-h1-report',{'2026-06-30':336803374744.06,'2025-12-31':316445911608.65}),
    ('citic-last',{'2025-06-30':400312389025.07,'2024-12-31':338997747988.89}),
    ('citic-annual-2025',{'2025-12-31':316445911608.65,'2024-12-31':338997747988.89}),
    ('citic-annual-2024',{'2024-12-31':338997747988.89,'2023-12-31':218365346534.60}),
])
def test_actual_citic_note8_headers_fair_value_total_and_comparison_dates(monkeypatch,name,expected):
    data=json.loads((FIXTURES/(name+'-excerpts.json')).read_bytes())
    monkeypatch.setattr(reports,'pdf_pages',lambda body,budget,**kw:data['pages'])
    result=reports.citic_pdf(b'%PDF-text-excerpts',data['year'],data['published'],budget(),annual=data['annual'])
    assert {row['date']:row['trading_bonds_cny'] for row in result}==expected
    for row in result:
        assert row['bond_pct']==pytest.approx(100*row['trading_bonds_cny']/row['trading_assets_cny'])
        assert row['within_pct']==pytest.approx(100*row['trading_bonds_cny']/(row['trading_bonds_cny']+row['trading_stocks_cny']))


@pytest.mark.parametrize('old,new',[
    ('金额单位均为人民币元','金额单位均为美元'),('合并资产负债表','母公司资产负债表'),
    ('公允价值合计','摊余成本合计'),('336,803,374,744.06','336,803,374,740.06'),
    ('2026 年 6 月 30 日','2027 年 6 月 30 日'),
])
def test_citic_wrong_scope_unit_column_sum_and_period_fail(monkeypatch,old,new):
    data=json.loads((FIXTURES/'citic-h1-report-excerpts.json').read_bytes());pages=data['pages']
    # 单位说明在PDF中含空白；先固定原文本形态再作语义变更。
    import re
    if old in ['金额单位均为人民币元','合并资产负债表']:
        pages=[re.sub(r'\s+','',p) if i==1 else p for i,p in enumerate(pages)]
    assert any(old in p for p in pages)
    monkeypatch.setattr(reports,'pdf_pages',lambda body,budget,**kw:[p.replace(old,new) for p in pages])
    with pytest.raises(SourceFailure):reports.citic_pdf(b'%PDF-text-excerpts',2026,'2026-08-21',budget())


def test_pdf_invalid_format_and_expired_budget_fail_before_decode():
    with pytest.raises(SourceFailure,match='institution_pdf_format_or_budget'):
        reports.pdf_pages(b'<html>not a PDF</html>',budget(),max_pages=10,max_bytes=1024)
    with pytest.raises(SourceFailure,match='collection_timeout'):
        reports.pdf_pages(b'%PDF-',CollectionBudget(time.monotonic()-1),max_pages=10,max_bytes=1024)


@pytest.mark.parametrize('kind,url,metrics,tables,derived',[
    ('pbc_custody',reports.PBC_URL,['bond.custody'],[],[]),
    ('wealth_allocation',reports.WEALTH_URL,['holdings_wealth'],[],[]),
    ('citic_broker',reports.CITIC_URL,['holdings_broker'],[],[]),
    ('chinabond_wealth','https://yield.chinabond.com.cn/cbweb-mn/indices/singleIndexQuery',[],['source.chinabond_wealth'],['bond.mtm45']),
])
def test_numeric_source_configuration_is_scoped_and_rejects_extra_owners(kind,url,metrics,tables,derived):
    from urllib.parse import urlsplit
    c=configuration();c['allowed_hosts']=[urlsplit(url).hostname]
    source=dict(id='institution.test',kind=kind,url=url,window_mode='report_latest',overlap_days=0)
    if metrics:source['datasets']=metrics
    if tables:source['tables']=tables
    if derived:source['derived_metrics']=derived
    if kind=='citic_broker':source['max_pages']=4
    c['sources']=[source];validate_configuration(c)
    wrong=deepcopy(c);wrong['sources'][0]['datasets']=['holdings_bank']
    with pytest.raises(ObservationError):validate_configuration(wrong)
    wrong=deepcopy(c);wrong['sources'][0]['overlap_days']=7
    with pytest.raises(ObservationError):validate_configuration(wrong)
