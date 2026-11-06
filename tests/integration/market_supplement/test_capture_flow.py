"""采集→持久恢复→原件→标准查询；故障按业务条件注入。"""
import json
from decimal import Decimal
from pathlib import Path
import sys
import time

sys.path.insert(0,str(Path(__file__).parent))
from msf_fixture import ContentStore,DAYS,FrozenFetch,QmtTransport,plan,query
import pytest

from integrations.guanheng import market_supplement_capture as capture
from integrations.guanheng.market_supplement_store import MarketSupplementStore
from integrations.guanheng_market_client import MarketProtocolError
from guanheng_qmt_shm.read_retention_client import RetainedReadPending
from guanheng_app.observation.source_fetch import SourceFailure


def collect(root,targets,fetch,transport,**kwargs):
    return capture.collect_supplement(targets,DAYS[-1],DAYS,root/'work',objects=ContentStore(root/'raw'),
        fetch=fetch,qmt_transport=transport,calendar_coverage=(DAYS[0],DAYS[-1]),deadline=time.monotonic()+20,**kwargs)


def test_required_pending_recovers_only_missing_and_cache_extends(tmp_path):
    targets=plan(('etf_total_shares','SSE.510300'))
    fetch,transport=FrozenFetch(bad_day=DAYS[-1]),QmtTransport()
    with pytest.raises(capture.SupplementPending):collect(tmp_path,targets,fetch,transport)
    assert not (tmp_path/'work/catalog.json').exists()
    before=json.loads((tmp_path/'work/STATE.json').read_bytes())['rows']
    assert len(before)==1
    fetch.bad_day=None
    descriptor=collect(tmp_path,targets,fetch,transport)
    store=MarketSupplementStore(descriptor)
    try:
        rows=store.query(query())['rows'];assert len(rows)==2
        assert rows[0]==next(iter(before.values()))
        assert {r['value'] for r in rows}=={'1750001250'}
        assert all(r['unit']=='share' and r['available_at'] is None for r in rows)
        store.verify_sources()
    finally:store.close()
    assert len(fetch.calls)==3  # 第一天没有重抓；错日第二天原件没有成为永久负缓存。
    counts=len(fetch.calls)
    assert collect(tmp_path,targets,fetch,transport)==descriptor
    assert len(fetch.calls)==counts
    # 同对象库的新任务复用完整旧行，连原received_at也保持。
    next_root=tmp_path/'next';next_root.mkdir()
    result=capture.collect_supplement(targets,DAYS[-1],DAYS,next_root,objects=ContentStore(tmp_path/'raw'),
        fetch=fetch,qmt_transport=transport,previous=descriptor,calendar_coverage=(DAYS[0],DAYS[-1]),deadline=time.monotonic()+20)
    reused=json.loads(Path(result['path']).read_bytes())['rows']
    assert reused==rows and len(fetch.calls)==counts


def test_binding_unknown_never_enters_external_fallback(tmp_path):
    fetch,transport=FrozenFetch(),QmtTransport(binding_pending=True)
    with pytest.raises(RetainedReadPending):collect(tmp_path,plan(('etf_total_shares','SSE.510300')),fetch,transport)
    assert fetch.calls==[]
    assert not (tmp_path/'work/catalog.json').exists()
    assert transport.sdk_calls==[]


def test_proxy_unknown_looks_up_original_slot_and_keeps_unit_unknown(tmp_path):
    fetch,transport=FrozenFetch(),QmtTransport(lose_first=True)
    targets=plan(('market_turnover_proxy','CN.SH_SZ'))
    with pytest.raises(RetainedReadPending):collect(tmp_path,targets,fetch,transport)
    slot=tmp_path/'work/qmt-slots/000001.SH.json'
    original=json.loads(slot.read_bytes())['request']['request_id']
    descriptor=collect(tmp_path,targets,fetch,transport)
    assert len(transport.sdk_calls)==2
    assert transport.sdk_calls[0]['request_id']==original
    assert any(path.endswith('/'+original+'/lookup') for _,path in transport.calls)
    assert fetch.calls==[]
    with_store=MarketSupplementStore(descriptor)
    try:
        rows=with_store.query(query(metric='market_turnover_proxy',symbols=['CN.SH_SZ']))['rows']
        assert [Decimal(r['value']) for r in rows]==[Decimal('301'),Decimal('301')]
        assert {r['unit'] for r in rows}=={'unknown'}
        assert all(json.loads(with_store._objects.get(r['source_sha256']))['parents'] for r in rows)
    finally:with_store.close()


def test_proxy_resume_after_first_fact_keeps_original_request_range(tmp_path,monkeypatch):
    fetch,transport=FrozenFetch(),QmtTransport()
    targets=plan(('market_turnover_proxy','CN.SH_SZ'))
    original_save=capture._save
    interrupted=False
    def fail_after_first(path,value):
        nonlocal interrupted
        original_save(path,value)
        if path.name=='STATE.json' and len(value.get('rows',{}))==1 and not interrupted:
            interrupted=True;raise InterruptedError('crash after one committed proxy fact')
    with monkeypatch.context() as scoped:
        scoped.setattr(capture,'_save',fail_after_first)
        with pytest.raises(InterruptedError):collect(tmp_path,targets,fetch,transport)
    assert len(transport.sdk_calls)==2
    identities=[r['request_id'] for r in transport.sdk_calls]
    descriptor=collect(tmp_path,targets,fetch,transport)
    assert len(transport.sdk_calls)==2
    assert [r['request_id'] for r in transport.sdk_calls]==identities
    assert len(json.loads(Path(descriptor['path']).read_bytes())['rows'])==2


def test_official_combination_and_financing_preserve_actual_fields(tmp_path):
    fetch,transport=FrozenFetch(),QmtTransport()
    descriptor=collect(tmp_path,plan(('market_turnover','CN.SH_SZ'),('margin_balance','CN.MARGIN_REPORT')),fetch,transport)
    store=MarketSupplementStore(descriptor)
    try:
        market=store.query(query(metric='market_turnover',symbols=['CN.SH_SZ']))['rows']
        assert {r['value'] for r in market}=={'2120874000000'}
        assert {r['source'] for r in market}=={'SSE+SZSE'}
        assert all(len(json.loads(store._objects.get(r['source_sha256']))['parents'])==2 for r in market)
        financing=store.query(query(metric='margin_balance',symbols=['CN.MARGIN_REPORT']))['rows']
        assert {r['value'] for r in financing}=={'12345678900'}
        assert all(r['unit']=='CNY' and r['available_at'] is None for r in financing)
    finally:store.close()


def test_optional_gaps_and_committed_source_damage_are_explicit(tmp_path):
    targets=plan(('etf_total_shares','SSE.510300'),required=False)
    targets['external_fallback']=[]
    fetch,transport=FrozenFetch(),QmtTransport()
    descriptor=collect(tmp_path,targets,fetch,transport)
    catalog=json.loads(Path(descriptor['path']).read_bytes())
    assert catalog['complete'] is False and len(catalog['gaps'])==2 and catalog['rows']==[]
    assert fetch.calls==[]
    objects=ContentStore(tmp_path/'raw');objects.path(catalog['qmt_evidence']['source_sha256']).write_bytes(b'corrupt')
    with pytest.raises(ValueError):collect(tmp_path,targets,fetch,transport)


def test_cancel_preserves_successful_facts_and_no_final_catalog(tmp_path):
    fetch,transport=FrozenFetch(),QmtTransport()
    checks=0
    def cancelled():
        nonlocal checks
        checks+=1
        return (tmp_path/'work/STATE.json').exists() and len(json.loads((tmp_path/'work/STATE.json').read_bytes()).get('rows',{}))==1
    with pytest.raises(InterruptedError):collect(tmp_path,plan(('etf_total_shares','SSE.510300')),fetch,transport,cancelled=cancelled)
    assert checks>0 and not (tmp_path/'work/catalog.json').exists()
    assert len(json.loads((tmp_path/'work/STATE.json').read_bytes())['rows'])==1


def test_qmt_metadata_and_proxy_share_original_public_budget(tmp_path):
    fetch,transport=FrozenFetch(),QmtTransport()
    fetch.budget.max_requests=1
    with pytest.raises(capture.SupplementPending):
        collect(tmp_path,plan(('market_turnover_proxy','CN.SH_SZ')),fetch,transport)
    assert transport.sdk_calls==[]  # 首次metadata已用额度，不能再偷偷产生SDK读取。
    assert fetch.budget.sdk_requests==1
    assert not (tmp_path/'work/catalog.json').exists()
    assert {r['reason'] for r in json.loads((tmp_path/'work/COVERAGE.json').read_bytes())['gaps']}=={'request_budget_exceeded'}


def test_profile_row_limit_partitions_history_without_truncation(tmp_path):
    fetch,transport=FrozenFetch(),QmtTransport(max_rows=1)
    targets=plan(('market_turnover_proxy','CN.SH_SZ'))
    descriptor=collect(tmp_path,targets,fetch,transport)
    assert len(transport.sdk_calls)==4
    state=json.loads((tmp_path/'work/STATE.json').read_bytes())
    assert len(state['rows'])==2
    assert all(r['arguments']['max_rows']==1 for r in transport.sdk_calls)
    assert all(r['arguments']['start_date']==r['arguments']['end_date'] for r in transport.sdk_calls)
    identities=[r['request_id'] for r in transport.sdk_calls]
    assert collect(tmp_path,targets,fetch,transport)==descriptor
    assert [r['request_id'] for r in transport.sdk_calls]==identities


def test_requested_history_outside_calendar_is_rejected_before_source(tmp_path):
    targets=plan(('etf_total_shares','SSE.510300'))
    targets['targets'][0]['from']='2026-11-03'
    fetch,transport=FrozenFetch(),QmtTransport()
    with pytest.raises(ValueError):collect(tmp_path,targets,fetch,transport)
    assert fetch.calls==[] and transport.calls==[]
    assert not (tmp_path/'work/catalog.json').exists()


def test_nontrading_start_inside_official_coverage_is_admitted(tmp_path):
    targets=plan(('etf_total_shares','SSE.510300'))
    targets['targets'][0]['from']='2026-11-01'  # Sunday，真实覆盖从休市日开始。
    fetch,transport=FrozenFetch(),QmtTransport()
    descriptor=capture.collect_supplement(targets,'2026-11-03',['2026-11-02','2026-11-03'],tmp_path/'work',
        objects=ContentStore(tmp_path/'raw'),fetch=fetch,qmt_transport=transport,
        calendar_coverage=('2026-11-01','2026-11-03'),deadline=time.monotonic()+20)
    value=json.loads(Path(descriptor['path']).read_bytes())
    assert value['complete'] and [r['date'] for r in value['rows']]==['2026-11-02','2026-11-03']


def test_scaled_source_overflow_is_gap_then_recovers_without_poisoned_state(tmp_path):
    class OversizedMargin(FrozenFetch):
        oversized=True
        def get(self,url,params=None,referer=None):
            raw=super().get(url,params,referer)
            if self.oversized and params.get('reportName')=='RPTA_WEB_MARGIN_DAILYTRADE':
                value=json.loads(raw);value['result']['data'][0]['FIN_BALANCE']='1e128'
                return json.dumps(value).encode('utf8')
            return raw
    fetch,transport=OversizedMargin(),QmtTransport()
    targets=plan(('margin_balance','CN.MARGIN_REPORT'))
    with pytest.raises(capture.SupplementPending):collect(tmp_path,targets,fetch,transport)
    assert json.loads((tmp_path/'work/STATE.json').read_bytes())['rows']=={}
    assert not (tmp_path/'work/catalog.json').exists()
    fetch.oversized=False
    descriptor=collect(tmp_path,targets,fetch,transport)
    assert {r['value'] for r in json.loads(Path(descriptor['path']).read_bytes())['rows']}=={'12345678900'}


def test_invalid_qmt_value_never_enters_persistent_fact_rows(tmp_path):
    fetch,transport=FrozenFetch(),QmtTransport(amounts={'000001.SH':1e128,'399106.SZ':200.75})
    with pytest.raises(MarketProtocolError):
        collect(tmp_path,plan(('market_turnover_proxy','CN.SH_SZ')),fetch,transport)
    assert len(transport.sdk_calls)==2
    assert json.loads((tmp_path/'work/STATE.json').read_bytes())['rows']=={}
    assert not (tmp_path/'work/catalog.json').exists()
