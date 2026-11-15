"""申万原日报、WT 成品目录、观衡投影和旧曲线保留。"""

from hashlib import sha256
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from msf_fixture import ContentStore, DAYS, FrozenFetch, QmtTransport, plan
from test_capture_flow import collect

from guanheng_app.observation import wt_shenwan_source
from guanheng_app.observation.source_fetch import SourceFailure
from guanheng_app.observation import refresh_models
from guanheng_app.observation.refresh_models import spread_and_bond
from integrations.guanheng.market_supplement_capture import SupplementPending
from integrations.guanheng.market_supplement_sources import SourceUnavailable, shenwan_history
from integrations.guanheng.market_supplement_store import MarketSupplementStore
from integrations.guanheng_market_client.supplement_facts import SHENWAN_FIELDS, SHENWAN_SCOPE


def report(day, pb):
    return dict(code='200', data=dict(count=2, results=[
        dict(swindexcode='801003', bargaindate=day+'T08:00:00+08:00',
             pe='16.10', pb=pb, closeindex='3947.67', bargainamount='1031.17', turnoverrate='3.27'),
        dict(swindexcode='801001', bargaindate=day+'T08:00:00+08:00'),
    ]))


def test_shenwan_group_roundtrip_preserves_original_and_retries_only_missing(tmp_path):
    class ShenwanFetch(FrozenFetch):
        missing_pb = True

        def get(self, url, params=None, referer=None):
            self.budget.request()
            self.calls.append(params)
            assert url.endswith('/index_analysis_report/') and params['type'] == 'DAY'
            day = params['end_date']
            pb = None if day == DAYS[-1] and self.missing_pb else '1.78'
            body = json.dumps(report(day, pb)).encode()
            self.budget.consume(len(body))
            return body

    source = ShenwanFetch()
    targets = plan(*[(metric, SHENWAN_SCOPE) for metric in SHENWAN_FIELDS])
    targets['external_fallback'] = ['Shenwan']
    with pytest.raises(SupplementPending):
        collect(tmp_path, targets, source, QmtTransport())
    value = json.loads((tmp_path/'work/STATE.json').read_bytes())
    assert len(value['rows']) == 9
    coverage = json.loads((tmp_path/'work/COVERAGE.json').read_bytes())
    assert coverage['gaps'] == [dict(date=DAYS[-1], metric='shenwan_market_pb', symbol=SHENWAN_SCOPE,
                                    reason='source_record_missing')]
    source.missing_pb = False
    completed = collect(tmp_path, targets, source, QmtTransport())
    assert len(source.calls) == 3  # 后续只查询仍缺 PB 的日期，一次请求覆盖整张日表。
    assert source.calls[-1]['start_date'] == DAYS[-1]
    new_value = json.loads(Path(completed['path']).read_bytes())
    for old in value['rows'].values():
        assert old in new_value['rows']
    store = MarketSupplementStore(completed)
    identity = 'a' * 64

    class WTClient:
        def source_market_snapshot_query(self, day):
            return dict(status={'code':'Ok'}, data=dict(observation_date=day, snapshot_id=identity,
                provenance={'supplement_facts_sha256':completed['sha256']}))

        def source_supplement_query(self, query):
            return dict(status={'code':'Ok'}, data=store.query(query))

    try:
        store.verify_sources()
        fetch = SimpleNamespace(budget=source.budget, timeout=5, records=[],
                                objects=ContentStore(tmp_path/'observer'))
        tables = wt_shenwan_source.history(fetch, DAYS[0], DAYS[-1], lambda _: WTClient(),
                                           snapshot_dates=[DAYS[-1]])
        assert tables[wt_shenwan_source.TABLE] == [dict(date=day, pe=16.1, weighted_pb=1.78,
            reference=3947.67,bargainamount=1031.17,turnoverrate=3.27) for day in DAYS]
        datasets = {'spread_sw':[], 'pb_sw_daily':[]}
        old_day = '2026-11-02'
        tables['source.gov10y'] = [dict(date=day,gov10y_pct=1.6) for day in [old_day, *DAYS]]
        tables[wt_shenwan_source.LEGACY_TABLE] = [dict(date=old_day, pe=15.5, weighted_pb=1.7, reference=3900)]
        spread_and_bond(tables,datasets,{})
        assert [row['date'] for row in datasets['pb_sw_daily']] == [old_day, *DAYS]
        assert datasets['spread_sw'][-1]['spread'] == pytest.approx(100/16.1-1.6)
    finally:
        store.close()


@pytest.mark.parametrize('change,reason', [('duplicate','source_duplicate_record'), ('truncated','source_pagination_incomplete')])
def test_shenwan_rejects_duplicate_identity_or_truncated_page(change, reason):
    payload = report(DAYS[-1], '1.78')
    if change == 'duplicate':
        payload['data']['results'][1] = payload['data']['results'][0]
    else:
        payload['data']['count'] = 3
    body = json.dumps(payload).encode()
    with pytest.raises(SourceUnavailable) as error:
        shenwan_history(DAYS[-1], DAYS[-1], lambda *args: dict(body=body, sha256=sha256(body).hexdigest(),
            received_at='2026-11-06T10:00:00+00:00'))
    assert error.value.code == reason


def test_shenwan_transport_failure_leaves_history_for_next_cycle(tmp_path):
    class Limited(FrozenFetch):
        def get(self,url,params=None,referer=None):
            self.budget.request()
            self.calls.append(params)
            raise SourceFailure('source_rate_limited')

    fetch = Limited()
    targets = plan(('shenwan_market_pb', SHENWAN_SCOPE), required=False)
    targets['external_fallback'] = ['Shenwan']
    result = collect(tmp_path, targets, fetch, QmtTransport())
    catalog = json.loads(Path(result['path']).read_bytes())
    assert {gap['reason'] for gap in catalog['gaps']} == {'source_rate_limited'}
    assert len(fetch.calls) == 1 and len(catalog['gaps']) == 2


def test_partial_shenwan_projection_preserves_system_c_historical_turnover(monkeypatch):
    monkeypatch.setattr(refresh_models,'comparison_model',lambda *args:None)
    monkeypatch.setattr(refresh_models,'continue_weekly',lambda *args:None)
    day = DAYS[-1]
    tables = {'market.'+symbol:[dict(date=day,close=3,provider_volume=123)]
              for symbol in ('sh000001','hkHSTECH','hkHSI','hkHSCEI')}
    tables[wt_shenwan_source.TABLE] = [dict(date=day,weighted_pb=2)]
    datasets = {'system_c.research':[dict(date=day,a_all_volume_field=42)]}
    definitions = {'system_c.research':{}}
    refresh_models.market_models(tables,datasets,definitions,dict(base_date=day),day)
    assert datasets['system_c.research'][0]['a_all_volume_field'] == 42
