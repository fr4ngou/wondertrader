"""原融资表目标日空结果与结构损坏区分；不补造余额、不联网。"""
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0,str(Path(__file__).parent))
from msf_fixture import ContentStore,DAYS,FrozenFetch,QmtTransport,plan
from test_capture_flow import collect
from integrations.guanheng.market_supplement_sources import (
    MARGIN_REGIONAL_HOST, collect_external, margin_summary_regional, SourceUnavailable,
)
from integrations.guanheng.market_supplement_store import MarketSupplementStore
from integrations.guanheng_market_client.supplement_facts import MARGIN_DAILY_SUMMARY, MARGIN_SUMMARY_FIELDS, SIGNED_MARGIN_SUMMARY
from guanheng_app.observation.wt_margin_summary import TABLE, history as read_margin_summary


def get_response(value):
    raw=json.dumps(value).encode()
    def get(url,params,referer):
        assert params['reportName']=='RPTA_WEB_MARGIN_DAILYTRADE'
        assert params['filter']=="(STATISTICS_DATE='2026-11-06')"
        return dict(body=raw,sha256=hashlib.sha256(raw).hexdigest(),received_at='2026-11-06T14:57:30+00:00')
    return get


def test_official_empty_date_result_is_missing_record_not_schema_failure():
    empty=dict(success=False,code=9201,result=None,message='empty')
    with pytest.raises(SourceUnavailable)as failure:
        collect_external('margin_balance','CN.MARGIN_REPORT','2026-11-06',get_response(empty))
    assert failure.value.code=='source_record_missing'


@pytest.mark.parametrize('value',[
    dict(success=False,code=9202,result=None),
    dict(success=False,code=9201),
    dict(success=True,code=9201,result=None),
    dict(success=False,code='9201',result=None),
    dict(success=False,code=9201,result={}),
])
def test_other_vendor_errors_or_malformed_empty_envelopes_remain_schema_failure(value):
    with pytest.raises(SourceUnavailable)as failure:
        collect_external('margin_balance','CN.MARGIN_REPORT','2026-11-06',get_response(value))
    assert failure.value.code=='source_schema_invalid'


def test_empty_latest_date_preserves_previous_fact_and_publishes_explicit_gap(tmp_path):
    class MissingLatest(FrozenFetch):
        def get(self,url,params=None,referer=None):
            raw=super().get(url,params,referer)
            if (params.get('reportName')=='RPTA_WEB_MARGIN_DAILYTRADE'
                    and DAYS[-1]in params.get('filter','')):
                return json.dumps(dict(success=False,code=9201,result=None)).encode()
            return raw
    descriptor=collect(tmp_path,plan(('margin_balance','CN.MARGIN_REPORT'),required=False),MissingLatest(),QmtTransport())
    catalog=json.loads(Path(descriptor['path']).read_bytes())
    assert [row['date']for row in catalog['rows']]==[DAYS[0]]
    assert catalog['rows'][0]['value']=='12345678900'
    assert catalog['gaps']==[dict(date=DAYS[-1],metric='margin_balance',symbol='CN.MARGIN_REPORT',reason='source_record_missing')]
    assert catalog['complete'] is False


def regional_response(market, day):
    identities = {'sh':('007','沪证',2), 'sz':('001','深证',3), 'bj':('002','京证',1)}
    code, label, multiplier = identities[market]
    row = dict(DIM_DATE=day+' 00:00:00', SCDM=code, XOB_MARKET_0001='融资融券_'+label,
               RZYE=8*multiplier, RZMRE=2*multiplier, RZCHE=3*multiplier,
               RZJME=-multiplier, RQYE=multiplier, RZRQYE=9*multiplier)
    return dict(success=True, code=0, result=dict(count=1,pages=1,data=[row]))


def test_margin_regional_requires_every_market_and_retains_prior_exact_summary(tmp_path):
    from integrations.guanheng.market_supplement_capture import SupplementPending

    class MarginFetch(FrozenFetch):
        missing = True
        allowed_hosts = (MARGIN_REGIONAL_HOST,)

        def get(self, url, params=None, referer=None):
            self.budget.request()
            self.calls.append(params)
            value = dict(success=False,code=9201,result=None)
            if url.endswith('/details2'):
                if params['mkt'] != 'bj' or not self.missing:
                    value = regional_response(params['mkt'],params['fd'])
            elif DAYS[0] in params['filter']:
                value = regional_response('sh',DAYS[0])
            body = json.dumps(value).encode()
            self.budget.consume(len(body))
            return body

    fetch, qmt = MarginFetch(), QmtTransport()
    first = 'margin_summary_fin_buy'
    targets = plan((first,MARGIN_DAILY_SUMMARY),(SIGNED_MARGIN_SUMMARY,MARGIN_DAILY_SUMMARY))
    with pytest.raises(SupplementPending):
        collect(tmp_path,targets,fetch,qmt)
    state = json.loads((tmp_path/'work/STATE.json').read_bytes())
    rows = list(state['rows'].values())
    assert len(rows) == 2 and {r['date'] for r in rows} == {DAYS[0]}
    assert {r['reason'] for r in json.loads((tmp_path/'work/COVERAGE.json').read_bytes())['gaps']} == {
        'margin_regional_report_missing'}
    queried = len(fetch.calls)
    fetch.missing = False
    descriptor = collect(tmp_path,targets,fetch,qmt)
    assert [call['mkt'] for call in fetch.calls[queried:] if 'mkt' in call] == ['bj']
    store = MarketSupplementStore(descriptor)
    try:
        store.verify_sources()
    finally:
        store.close()
    catalog = json.loads(Path(descriptor['path']).read_bytes())
    assert {r['metric']:r for r in catalog['rows'] if r['date'] == DAYS[0]} == {r['metric']:r for r in rows}
    later = {r['metric']:r for r in catalog['rows'] if r['date'] == DAYS[-1]}
    assert later[first]['value'] == '12' and later[SIGNED_MARGIN_SUMMARY]['value'] == '-6'


def test_margin_regional_rate_limit_keeps_national_fields_and_skips_other_days(tmp_path):
    from guanheng_app.observation.source_fetch import SourceFailure

    class LimitedMarket(FrozenFetch):
        allowed_hosts = (MARGIN_REGIONAL_HOST,)

        def get(self,url,params=None,referer=None):
            self.budget.request()
            self.calls.append(params)
            if url.endswith('/details2'):
                state = json.loads((tmp_path/'work/STATE.json').read_bytes())
                assert any(row['date'] == DAYS[-1] and row['metric'] == 'margin_summary_fin_buy'
                           for row in state['rows'].values())
                raise SourceFailure('source_rate_limited')
            day = next(d for d in DAYS if d in params['filter'])
            value = regional_response('sh',day)
            del value['result']['data'][0]['RZJME']
            body = json.dumps(value).encode()
            self.budget.consume(len(body))
            return body

    fetch = LimitedMarket()
    targets = plan(('margin_summary_fin_buy',MARGIN_DAILY_SUMMARY),(SIGNED_MARGIN_SUMMARY,MARGIN_DAILY_SUMMARY),
                   required=False)
    descriptor = collect(tmp_path,targets,fetch,QmtTransport())
    result = json.loads(Path(descriptor['path']).read_bytes())
    assert [call['mkt'] for call in fetch.calls if 'mkt' in call] == ['sh']
    assert {row['date'] for row in result['rows']} == set(DAYS)
    assert {gap['date']:gap['reason'] for gap in result['gaps']} == {
        DAYS[-1]:'source_rate_limited', DAYS[0]:'source_record_missing'}


def test_margin_regional_rejects_a_wrong_market_in_the_date_bound_response():
    def get(url, params, referer):
        raw = json.dumps(regional_response('sh',params['fd'])).encode()
        return dict(body=raw, sha256=hashlib.sha256(raw).hexdigest(), received_at='2026-11-06T14:57:30+00:00')

    with pytest.raises(SourceUnavailable) as failure:
        margin_summary_regional(DAYS[-1],get)
    assert failure.value.code == 'margin_regional_identity_invalid'


@pytest.mark.parametrize('unavailable, reason', [(None, 'source_record_missing'), ('bad', 'source_value_invalid')])
def test_margin_summary_keeps_signed_value_and_only_retries_missing_report_fields(tmp_path, unavailable, reason):
    class MarginFetch(FrozenFetch):
        missing_short = True

        def get(self, url, params=None, referer=None):
            self.budget.request()
            self.calls.append(params)
            assert params['reportName'] == 'RPTA_RZRQ_LSHJ'
            assert set(params['columns'].split(',')) == {'DIM_DATE','RZYE','RZMRE','RZJME','RZCHE','RQYE','RZRQYE'}
            day = next(d for d in DAYS if d in params['filter'])
            row = dict(DIM_DATE=day+' 00:00:00', RZYE=800_000_000, RZMRE=120_000_000, RZJME=-30_000_000,
                       RZCHE=150_000_000, RQYE=unavailable if self.missing_short and day == DAYS[-1] else 90_000_000,
                       RZRQYE=890_000_000)
            body = json.dumps(dict(success=True, result=dict(count=1, pages=1, data=[row]))).encode()
            self.budget.consume(len(body))
            return body

    from integrations.guanheng.market_supplement_capture import SupplementPending

    fetch, qmt = MarginFetch(), QmtTransport()
    targets = plan(*[(metric, MARGIN_DAILY_SUMMARY) for metric in MARGIN_SUMMARY_FIELDS])
    with pytest.raises(SupplementPending):
        collect(tmp_path, targets, fetch, qmt)
    state = json.loads((tmp_path/'work/STATE.json').read_bytes())
    coverage = json.loads((tmp_path/'work/COVERAGE.json').read_bytes())
    assert len(state['rows']) == 11
    assert coverage['gaps'] == [dict(date=DAYS[-1], symbol=MARGIN_DAILY_SUMMARY,
                                   metric='margin_summary_short_balance', reason=reason)]
    assert len(fetch.calls) == 2
    fetch.missing_short = False
    descriptor = collect(tmp_path, targets, fetch, qmt)
    assert len(fetch.calls) == 3 and DAYS[-1] in fetch.calls[-1]['filter']
    catalog = json.loads(Path(descriptor['path']).read_bytes())
    assert catalog['complete'] and len(catalog['rows']) == 12
    for row in catalog['rows']:
        key = '|'.join([row['date'], row['metric'], row['symbol']])
        if key in state['rows']:
            assert row == state['rows'][key]
    assert {row['value'] for row in catalog['rows'] if row['metric'] == SIGNED_MARGIN_SUMMARY} == {'-30000000'}

    store = MarketSupplementStore(descriptor)
    identity = '1' * 64

    class WTClient:
        def source_market_snapshot_query(self, day):
            return dict(status={'code':'Ok'}, data=dict(observation_date=day, snapshot_id=identity,
                provenance={'supplement_facts_sha256':descriptor['sha256']}))

        def source_supplement_query(self, request):
            assert request['snapshot_id'] == identity and request['symbols'] == [MARGIN_DAILY_SUMMARY]
            return dict(status={'code':'Ok'}, data=store.query(request))

    try:
        store.verify_sources()
        reader = SimpleNamespace(budget=fetch.budget, timeout=5, records=[], objects=ContentStore(tmp_path/'observer'))
        tables = read_margin_summary(reader, DAYS[0], DAYS[-1], lambda _: WTClient(), snapshot_dates=[DAYS[-1]])
        assert tables[TABLE] == [dict(date=d, available_at=None, fin_balance=8.0, fin_buy=1.2,
            fin_net_reported=-0.3, fin_repay=1.5, short_balance=0.9, total_balance=8.9) for d in DAYS]
    finally:
        store.close()
