"""官方原XLS数值、后继季度识别与来源变化的根因回归；替身期次明确为合成。"""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import json
import time

import pytest
import xlrd

from guanheng_app.observation.nfra_source import history, parse_workbook
from guanheng_app.observation.source_fetch import CollectionBudget, SourceFailure
from guanheng_app.observation.collection_config import validate_configuration
from guanheng_app.observation.contracts import ObservationError
from test_collection_config import configuration


FIXTURES = Path(__file__).resolve().parents[2] / 'fixtures/observation/nfra'
TITLE = '2026年二季度保险公司资金运用情况表'
PUBLISHED = '2026-08-14 17:46:37'
RAW = (FIXTURES / 'funds-2026-q2.xls').read_bytes()


class OfficialCapture:
    """固定公开原件回放；所有请求均由所测正式适配器发起。"""
    def __init__(self):
        self.budget = CollectionBudget(time.monotonic() + 30)  # 本次回放的同一总截止。
        self.calls = []  # 本次访问路径，用于确认数字附件实际被消费。
        self.pages = [json.loads((FIXTURES / f'listing-{i}.json').read_bytes()) for i in (1, 2)]
        self.detail = json.loads((FIXTURES / 'detail.json').read_bytes())  # 同一官方文档身份。

    def get(self, url):
        self.calls.append(url)
        if 'SelectDocByItemIdAndChild' in url:
            page = int(url.split('pageIndex=')[1].split(',')[0])
            return json.dumps(self.pages[page-1]).encode()
        if 'SelectByDocId' in url:
            return json.dumps(self.detail).encode()
        if url.endswith('.xls'):
            return RAW
        raise AssertionError(url)


def test_original_official_two_groups_keep_full_precision_and_percentage():
    fetch = OfficialCapture()
    result = history(fetch, {'max_pages': 3}, '2026-06-23', '2026-11-03')
    assert len(fetch.calls) == 4 and fetch.calls[-1].endswith('.xls')
    assert result['holdings_life'] == [dict(date='2026-06-30', total=368690.956069265,
        bonds=188800.560366525, bond_pct=51.208351400693296, available_at=PUBLISHED)]
    assert result['holdings_property'] == [dict(date='2026-06-30', total=25349.9856317761,
        bonds=10268.5874149431, bond_pct=40.50727114445173, available_at=PUBLISHED)]


def test_publication_after_cutoff_keeps_unpublished_quarter_empty():
    fetch = OfficialCapture()
    result = history(fetch, {'max_pages': 3}, '2026-06-23', '2026-08-13')
    assert result == {'holdings_life': [], 'holdings_property': []}
    assert not any(url.endswith('.xls') for url in fetch.calls)


@pytest.mark.parametrize('mutation', ['detail', 'external', 'duplicate_attachment', 'changed_total', 'order'])
def test_document_and_listing_changes_fail_whole_source(mutation):
    fetch = OfficialCapture()
    if mutation == 'detail':
        fetch.detail['data']['docId'] += 1
    elif mutation == 'external':
        fetch.detail['data']['attachmentInfoVOList'][0]['urlOtherName'] = 'https://example.invalid/a.xls'
    elif mutation == 'duplicate_attachment':
        fetch.detail['data']['attachmentInfoVOList'] *= 2
    elif mutation == 'changed_total':
        fetch.pages[1]['data']['total'] += 1
    else:
        fetch.pages[0]['data']['rows'][1]['publishDate'] = '2026-11-01 10:00:00'
    with pytest.raises(SourceFailure) as caught:
        history(fetch, {'max_pages': 3}, '2026-06-23', '2026-11-03')
    assert caught.value.code == 'nfra_response_schema'


def test_pagination_budget_exhaustion_does_not_report_no_new_data():
    fetch = OfficialCapture()
    with pytest.raises(SourceFailure) as caught:
        history(fetch, {'max_pages': 1}, '2026-06-23', '2026-11-03')
    assert caught.value.code == 'nfra_listing_coverage_incomplete'


def workbook_rows():
    book = xlrd.open_workbook(file_contents=RAW)
    try:
        sheet = book.sheet_by_index(0)
        return [sheet.row_values(i) for i in range(sheet.nrows)]
    finally:
        book.release_resources()


def substituted_book(monkeypatch, rows):
    closed = []
    sheet = SimpleNamespace(nrows=len(rows), ncols=4, row_values=lambda i: rows[i])
    book = SimpleNamespace(nsheets=1, sheet_by_index=lambda i: sheet,
                           release_resources=lambda: closed.append(True))
    monkeypatch.setattr(xlrd, 'open_workbook', lambda **kwargs: book)
    return closed


@pytest.mark.parametrize('mutation', ['unit', 'group', 'ratio', 'duplicate', 'nonfinite'])
def test_changed_table_contract_is_rejected_and_workbook_released(monkeypatch, mutation):
    rows = workbook_rows()
    if mutation == 'unit': rows[1][3] = '单位：万元，%'
    elif mutation == 'group': rows[11][0] = '其他公司'
    elif mutation == 'ratio': rows[13][3] = .9
    elif mutation == 'duplicate': rows.insert(14, deepcopy(rows[13]))
    else: rows[13][2] = float('nan')
    closed = substituted_book(monkeypatch, rows)
    with pytest.raises(SourceFailure) as caught:
        parse_workbook(RAW, TITLE, PUBLISHED, CollectionBudget(time.monotonic()+5))
    assert caught.value.code == 'nfra_workbook_schema' and closed == [True]


def test_next_quarter_is_discovered_and_new_numeric_values_are_used(monkeypatch):
    # 合成三季度披露，仅用于证明期次与金额没有硬编码为当前官方二季度。
    fetch = OfficialCapture()
    title, published = '2026年三季度保险公司资金运用情况表', '2026-11-13 17:46:37'
    row = next(row for row in fetch.pages[1]['data']['rows'] if row['docId'] == 1268117)
    row.update(docTitle=title, publishDate=published)
    fetch.pages[0]['data']['rows'] = [row]
    fetch.pages[0]['data']['total'] = 1
    fetch.detail['data'].update(docTitle=title, publishDate=published)
    fetch.detail['data']['attachmentInfoVOList'][0]['title'] = title+'.xls'
    rows = workbook_rows()
    rows[0][0] = title
    rows[11][2], rows[13][2], rows[13][3] = 400000., 200000., .5
    closed = substituted_book(monkeypatch, rows)
    result = history(fetch, {'max_pages': 3}, '2026-06-23', '2026-11-16')
    assert result['holdings_life'] == [dict(date='2026-09-30', total=400000., bonds=200000.,
                                           bond_pct=50., available_at=published)]
    assert result['holdings_property'][0]['date'] == '2026-09-30' and closed == [True]


def insurance_configuration():
    config = configuration()
    config['allowed_hosts'] = ['www.nfra.gov.cn']
    config['sources'] = [dict(id='nfra.disclosures', kind='nfra_insurance',
        url='https://www.nfra.gov.cn/', datasets=['holdings_life','holdings_property'],
        window_mode='report_latest', max_pages=8)]
    return config


def test_configuration_admits_original_two_outputs():
    validate_configuration(insurance_configuration())


@pytest.mark.parametrize('change', [dict(datasets=['holdings_life']), dict(max_pages=2),
    dict(max_pages=True), dict(window_mode='daily'), dict(url='https://example.invalid/')])
def test_configuration_rejects_scope_and_capacity_changes(change):
    config = insurance_configuration()
    config['sources'][0].update(change)
    with pytest.raises(ObservationError): validate_configuration(config)


def test_missing_xls_dependency_is_explicit(monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, 'xlrd', None)
    with pytest.raises(SourceFailure) as caught:
        parse_workbook(RAW, TITLE, PUBLISHED, CollectionBudget(time.monotonic()+5))
    assert caught.value.code == 'nfra_xls_dependency_missing'


def test_expired_original_deadline_stops_before_workbook_open(monkeypatch):
    calls = []
    monkeypatch.setattr(xlrd, 'open_workbook', lambda **kwargs: calls.append(kwargs))
    with pytest.raises(SourceFailure) as caught:
        parse_workbook(RAW, TITLE, PUBLISHED, CollectionBudget(time.monotonic()-1))
    assert caught.value.code == 'collection_timeout' and calls == []
