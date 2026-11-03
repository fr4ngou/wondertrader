"""乐咕原页面快照、展示舍入与独立历史范围的根因回归。"""
from copy import deepcopy
from decimal import localcontext
from pathlib import Path
from types import SimpleNamespace
import time

import pytest

from guanheng_app.observation.legulegu_gdp import METRIC, URL, history, page_snapshot, update_definition
from guanheng_app.observation.source_fetch import CollectionBudget, SourceFailure
from guanheng_app.observation.refresh_models import merge
from guanheng_app.observation.collection_config import validate_configuration
from guanheng_app.observation.contracts import ObservationError
from test_collection_config import configuration


FIXTURES = Path(__file__).resolve().parents[2] / 'fixtures/observation/legu-gdp'
CURRENT = (FIXTURES/'page-20261102.html').read_bytes()
OLD = (FIXTURES/'page-20261016.html').read_bytes()
SOURCE = dict(id='legulegu.marketcap_gdp', kind='legulegu_gdp', url=URL,
              datasets=[METRIC], window_mode='report_latest')


def parse(body=CURRENT):
    return page_snapshot(body, CollectionBudget(time.monotonic()+10))


def test_actual_page_keeps_both_cny_trillion_values_and_page_percentage():
    row=parse()
    assert row==dict(date='2026-11-02',ratio=.8298,marketcap_trillion=116.32,
                    gdp_trillion=140.19,gdp_year=2025,available_at=None)
    assert row['ratio'] != row['marketcap_trillion']/row['gdp_trillion']
    assert 'csi300_reference' not in row and 'csi300_source_date' not in row


def test_actual_old_archive_reproduces_original_numbers_and_keeps_existing_reference():
    old=parse(OLD)
    assert old==dict(date='2026-10-16',ratio=.8562,marketcap_trillion=120.02,
                    gdp_trillion=140.19,gdp_year=2025,available_at=None)
    previous=dict(old,csi300_reference=4170.61,csi300_source_date='2026-10-16')
    merged,revisions=merge([previous],[old])
    assert merged==[previous] and revisions==[]


def test_append_actual_snapshots_does_not_fill_missing_days_or_join_monthly_model():
    calls=[]
    fetch=SimpleNamespace(budget=CollectionBudget(time.monotonic()+10),
                          get=lambda url:(calls.append(url),CURRENT)[1])
    result=history(fetch,SOURCE,'2026-10-09','2026-11-03')
    assert set(result)=={METRIC} and calls==[URL]
    merged,revisions=merge([parse(OLD)],result[METRIC])
    assert [row['date'] for row in merged]==['2026-10-16','2026-11-02'] and revisions==[]


@pytest.mark.parametrize('change', ['header_date','description_ratio','unit','denominator','scope','duplicate',
                                   'missing_gdp','negative','nonfinite','missing_description'])
def test_changed_page_identity_units_and_required_values_fail_whole_snapshot(change):
    text=CURRENT.decode('utf8')
    if change=='header_date': text=text.replace('>2026-11-02<','>2026-11-03<')
    elif change=='description_ratio': text=text.replace('值为：82.98%','值为：80.01%')
    elif change=='unit': text=text.replace('116.32万亿','116.32亿元')
    elif change=='denominator': text=text.replace('上一年度的全年GDP数值','滚动四季度GDP数值')
    elif change=='scope': text=text.replace('上交所、深交所、北交所已上市股票','上交所、深交所已上市股票')
    elif change=='duplicate': text=text.replace('class="metric-item metric-gdp"','class="metric-item metric-gdp metric-market-cap"')
    elif change=='missing_gdp': text=text.replace('140.19万亿','--')
    elif change=='negative': text=text.replace('116.32万亿','-116.32万亿')
    elif change=='nonfinite': text=text.replace('116.32万亿','NaN万亿')
    else: text=text.replace('id="data-description"','id="unknown-description"')
    with pytest.raises(SourceFailure):parse(text.encode())


def test_future_snapshot_date_is_not_admitted_to_earlier_window():
    body=CURRENT.replace(b'2026-11-02',b'2026-11-04').replace('2026年11月02日'.encode(),'2026年11月04日'.encode())
    fetch=SimpleNamespace(budget=CollectionBudget(time.monotonic()+10),get=lambda url:body)
    assert history(fetch,SOURCE,'2026-10-09','2026-11-03')=={METRIC:[]}


def test_next_actual_observation_uses_new_page_values_without_replaying_old_day():
    text=CURRENT.decode().replace('2026-11-02','2026-11-03').replace('2026年11月02日','2026年11月03日').replace('116.32万亿','117.43万亿').replace('82.98%','83.77%')
    row=parse(text.encode())
    assert row['date']=='2026-11-03' and row['marketcap_trillion']==117.43 and row['ratio']==.8377
    assert row['gdp_trillion']==140.19 and row['gdp_year']==2025


def test_original_deadline_and_page_capacity_are_enforced():
    with pytest.raises(SourceFailure) as caught:
        page_snapshot(CURRENT,CollectionBudget(time.monotonic()-1))
    assert caught.value.code=='collection_timeout'
    with pytest.raises(SourceFailure) as caught:parse(b'x'*(2*1024*1024+1))
    assert caught.value.code=='legu_gdp_page_capacity'


def test_external_decimal_context_does_not_change_published_percentage_conversion():
    with localcontext() as context:
        context.prec=2
        assert parse()['ratio']==.8298


def definition():
    return dict(definition_version='original-method',points=True,
        field_schema=dict(ratio=dict(formula='页面发布值85.62% / 100'),gdp_year={}),
        lines=[dict(key='ratio'),dict(key='csi300_reference')],how_to_read=dict(boundary='old'),
        frequency_audit=dict(daily_ready=False),history_audit=dict(old_count=1),
        reference_review=dict(status='旧403'),refresh_policy=dict(automatic_refresh_enabled=False))


def test_current_metadata_describes_observed_points_and_success_without_changing_method_or_rows():
    d=definition();rows=[parse(OLD),parse()];frozen=deepcopy(rows)
    update_definition(d,rows,[dict(status='success')],'2026-11-03T05:00:00+00:00')
    assert d['definition_version']=='original-method' and rows==frozen
    assert d['points'] is True and d['frequency_audit']['daily_ready'] is False
    assert d['history_audit']['current_count']==2 and d['history_audit']['old_count']==1
    assert d['refresh_policy']['automatic_refresh_enabled'] is True
    assert d['refresh_policy']['source_latest_period']=='2026-11-02'
    assert '85.62' not in d['field_schema']['ratio']['formula'] and '403' not in d['reference_review']['status']


def test_unselected_source_does_not_change_other_refresh_metadata():
    d=definition();before=deepcopy(d)
    update_definition(d,[parse()],[],'2026-11-03T05:00:00+00:00')
    assert d==before


def page_configuration():
    value=configuration();value['allowed_hosts']=['legulegu.com'];value['sources']=[deepcopy(SOURCE)]
    return value


def test_configuration_admits_only_this_original_page_metric():
    validate_configuration(page_configuration())


@pytest.mark.parametrize('change', [dict(datasets=['valuation_marketcap_gdp_monthly']),
    dict(datasets=['valuation_marketcap_gdp_observed']),dict(tables=['source.gdp_annual']),
    dict(url='https://legulegu.com/stockdata/other'),dict(window_mode='daily'),
    dict(derived_metrics=['valuation_marketcap_gdp_observed'])])
def test_configuration_keeps_monthly_observed_and_raw_tables_outside_this_owner(change):
    value=page_configuration();value['sources'][0].update(change)
    with pytest.raises(ObservationError):validate_configuration(value)
