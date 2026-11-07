"""真实ASA原事务→CTA发布→观衡双策略读取；共同证券用不同数量识别混账。"""
import json
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal as D
from time import monotonic
from types import SimpleNamespace
from uuid import uuid4

from guanheng_wt_runtime.account_allocation import (
    AccountAllocation, AccountSnapshot, BookIdentity, StrategySeed, OwnedPosition,
    TargetIntent, Target, GroupBinding, WTChild, PreparedCommand, FillFact, FeeFact,
)
from guanheng_wt_runtime.profile_facts import allocation_projection
from guanheng_app.strategy_runtime_projection import project_strategy, project_strategies
from guanheng_app.live_strategy_performance import LiveStrategyPerformanceOwner

OLD = 'resonance-regime-v1'
NEW = 'resonance-original-wt-351f9d5-stable'
CODES = ('SSE.ETF.510300', 'SSE.ETF.510050', 'SSE.ETF.510500', 'SSE.ETF.512100',
         'SSE.ETF.515080', 'SSE.ETF.588000', 'SSE.ETF.589680', 'SZSE.ETF.159780', 'SZSE.ETF.159352')
OLD_CODES = tuple(s for s in CODES if s not in ('SSE.ETF.589680','SZSE.ETF.159352')) + ('SSE.ETF.588030',)
SHA = 'a' * 64
STAMP = '2026-11-06T06:31:00+00:00'


def uid(): return str(uuid4())
def deadline(): return monotonic() + 30


def make_book(root):
    root.mkdir()
    store = AccountAllocation(root, BookIdentity(SHA, uid(), 'b'*64), owner_check=lambda: None)
    store.initialize((StrategySeed(OLD, '1.2.2', D('10000'), (OwnedPosition(CODES[0], 100, 100),), 0, OLD_CODES),
        StrategySeed(NEW, '0.2.0a1', D('1000000'), (), 1, CODES)), D('0'),
        AccountSnapshot(1, '2026-11-06', D('2000000'), (OwnedPosition(CODES[0], 100, 100),), SHA), deadline=deadline())
    for sid, codes, quantity in ((OLD, OLD_CODES, 200), (NEW, CODES, 200)):
        store.record_targets(TargetIntent(uid(), sid, 1,
            tuple(Target(s, quantity if s == CODES[0] else 0) for s in codes), SHA, STAMP), deadline=deadline())
    plan, group = uid(), uid()
    store.plan(plan, (), deadline=deadline())
    store.bind_group(plan, GroupBinding(group, CODES[0], 'buy', 300, D('2'), D('5')), deadline=deadline())
    child, command = uid(), uid()
    store.record_wt_child(WTChild(group, child, 300, D('2'), SHA), deadline=deadline())
    store.bind_prepared(PreparedCommand(group, child, command, SHA, 300, D('2')), deadline=deadline())
    store.apply_fill(FillFact('actual-shared-fill', command, 300, D('2'), D('600'), None,
        '2026-11-06', '2026-11-09', SHA, CODES[0], 'buy', STAMP), deadline=deadline())
    return store


def reports(store):
    return {sid: dict(strategy_id=sid, strategy_version=version, sequence=2,
        status='waiting_market_input' if sid == OLD else 'holding',
        allocation_observation=json.loads(json.dumps(allocation_projection(store.strategy_observation(sid, deadline=deadline()),include_read_projection=True))))
        for sid, version in ((OLD, '1.2.2'), (NEW, '0.2.0a1'))}


def wrapper(rows): return dict(schema='guanheng.configured-cta-observation.v1', strategies=rows)


def snapshot(rows):
    return dict(configuration=SimpleNamespace(instance_id='synthetic', control_id='control', configuration_sha256=SHA),
        runtime=dict(pid=20, state='ready', ready=True, components={'execution':dict(state='ready', ready=True)}),
        reference=dict(pid=21), strategies={s['strategy_id']:s for s in project_strategies(wrapper(rows))},
        strategy=None, account=None, lifecycle=dict(execution_started_at=STAMP))


def test_actual_book_to_two_profiles_and_daily_read(tmp_path):
    store = make_book(tmp_path/'asa'); rows = reports(store)
    a=store.strategy_observation(OLD,deadline=deadline());b=store.strategy_observation(OLD,deadline=deadline())
    assert allocation_projection(a)==allocation_projection(b)
    assert set(allocation_projection(a))=={'strategy','account_revision','account_source_sha256','trading_day','opening_cycles'}
    assert len(project_strategies(wrapper(rows))) == 2
    assert project_strategy(wrapper(rows))['strategy_id'] == OLD
    assert project_strategy(wrapper(rows), strategy_id='absent') is None
    old = project_strategy(wrapper(rows), strategy_id=OLD)
    new = project_strategy(wrapper(rows), strategy_id=NEW)
    assert len(old['positions']) == 8 and len(new['positions']) == 9
    assert len({p['symbol']for p in old['positions']} & {p['symbol']for p in new['positions']}) == 7
    # 一个账户300份D按原FIFO分配为100/200；原账户400份P不可写进两个策略。
    assert next(p for p in old['positions']if p['symbol']=='510300.SH')['broker_quantity'] == 200
    assert next(p for p in new['positions']if p['symbol']=='510300.SH')['broker_quantity'] == 200
    assert old['ownership']['fills'][0]['quantity'] == 100
    assert new['ownership']['fills'][0]['quantity'] == 200
    assert old['ownership']['fills'][0]['amount_cny'] == '200.00'
    assert new['ownership']['fills'][0]['amount_cny'] == '400.00'
    assert new['ownership']['fills'][0]['fee_cny'] is None
    owner = LiveStrategyPerformanceOwner(None, history_root=str(tmp_path/'display'),
        snapshot_reader=lambda _:snapshot(rows), process_probe=lambda *_:True)
    (tmp_path/'display').mkdir()
    try:
        owner.capture_current(deadline())
        a = owner.read(OLD, '1.2.2', deadline=deadline())
        b = owner.read(NEW, '0.2.0a1', deadline=deadline())
        assert a['current']['is_current'] and b['current']['is_current']
        assert a['coverage']['history_scope_id'] != b['coverage']['history_scope_id']
        assert a['summary'] is b['summary'] is None
        assert a['coverage']['point_count'] == b['coverage']['point_count'] == 0
        assert [d['quantity'] for d in a['markers']] == [100]
        assert [d['quantity'] for d in b['markers']] == [200]
        assert b['markers'][0]['attribution'] == 'strategy-allocated'
        assert b['daily'][-1]['cash_cny'] is None  # 费用未知不冒充确定净现金。
        store.apply_fee(FeeFact(uid(), 'actual-shared-fill', D('5'), 'c'*64), deadline=deadline())
        rows.update(reports(store))
        known = owner.read(NEW, '0.2.0a1', deadline=deadline())
        assert known['daily'][-1]['cash_cny'] == '999596.67'
        assert known['daily'][0]['deals'][0]['fee_cny'] == '3.33'
        assert known['summary'] is None and known['coverage']['point_count'] == 0
        assert owner.read(NEW, 'wrong', deadline=deadline())['state'] == 'not_current'
        assert owner.read('missing', '1', deadline=deadline())['daily'] == []
    finally: owner.close()


def test_legacy_allocation_no_fill_clock_does_not_borrow_account_deals(tmp_path):
    rows = reports(make_book(tmp_path/'asa'))
    for row in rows.values():
        for key in ('fills','fills_truncated','observed_at','book_scope_sha256','targets'):
            row['allocation_observation'].pop(key)
    def read(_):
        value = snapshot(rows)
        # 同码NAP确有另一笔99900份账户成交；旧ASA缺D不能用它填本策略。
        def present(v): return dict(availability='present',value=v)
        value['account'] = dict(groups=dict(deal=dict(status='complete',received_at='2026-11-06T07:00:00Z',rows=[dict(
            identity=dict(m_strInstrumentID='510300',m_strExchangeID='SH',m_strTradeID='foreign-account-fill'),
            fields={k:present(v)for k,v in dict(date='20261106',time='143100',quantity=99900,price=2,amount=199800,side=48).items()})])))
        return value
    owner = LiveStrategyPerformanceOwner(None, snapshot_reader=read, process_probe=lambda *_:True)
    try:
        value = owner.read(NEW, '0.2.0a1', deadline=deadline())
        assert value['state'] == 'available' and value['markers'] == [] and value['summary'] is None
        assert value['coverage']['attribution'] == 'strategy-allocated'
    finally: owner.close()


def test_fill_missing_actual_clock_and_wrong_scope(tmp_path):
    import pytest
    rows = reports(make_book(tmp_path/'asa'))
    rows[NEW]['allocation_observation']['fills'][0]['executed_at'] = None
    owner = LiveStrategyPerformanceOwner(None, snapshot_reader=lambda _:snapshot(rows), process_probe=lambda *_:True)
    try:
        value = owner.read(NEW, '0.2.0a1', deadline=deadline())
        assert value['markers'] == [] and value['daily'][-1]['deals_state'] == 'partial'
    finally: owner.close()
    rows[NEW]['allocation_observation']['strategy']['strategy_id'] = OLD
    with pytest.raises(ValueError): project_strategy(wrapper(rows), strategy_id=NEW)


def test_published_version_must_match_allocation_version(tmp_path):
    import pytest
    rows = reports(make_book(tmp_path/'asa'))
    rows[NEW]['strategy_version'] = 'foreign-version'
    with pytest.raises(ValueError): project_strategy(wrapper(rows), strategy_id=NEW)


def test_shared_waiting_without_allocation_never_uses_account_inventory():
    from guanheng_wt_runtime.original_live import OriginalLiveStrategy
    definition = OriginalLiveStrategy._definition(SimpleNamespace(id=NEW, codes=tuple(s.rsplit('.',1)[1] for s in CODES),
        mapping={s.rsplit('.',1)[1]:s for s in CODES}))
    original = dict(strategy_id=NEW,strategy_version='0.2.0a1',definition=definition,
        status='waiting',allocation_observation=None)
    old = dict(status='waiting_allocation',definition=dict(strategy_id=OLD,strategy_version='1.2.2',symbols=definition['symbols'][:8]),
        broker_observation=dict(positions_known=True,positions=[dict(symbol=CODES[0],quantity=999900,sellable=999900)]))
    a = project_strategy(wrapper({NEW:original}),strategy_id=NEW)
    b = project_strategy(wrapper({OLD:old}),strategy_id=OLD)
    assert len(a['positions']) == 9 and a['ownership'] is None
    assert len(b['positions']) == 8 and b['ownership'] is None
    assert all(p['broker_quantity'] is None for p in a['positions']+b['positions'])


def test_published_files_to_catalog_selected_details_and_live_http(tmp_path, monkeypatch):
    """真实只读文件边界及App原读池，不启动金融角色或发来源请求。"""
    from fastapi.testclient import TestClient
    from guanheng_app.app import create_app
    from guanheng_app.settings import ConsoleSettings
    rows = reports(make_book(tmp_path/'asa'))
    control, instance, execution = uid(), uid(), uid()
    directory = tmp_path/execution; directory.mkdir()
    reference = dict(schema='guanheng.execution-observation-reference.v1', control_id=execution,
        config_sha256='b'*64, pid=777, path=str(directory/'strategies.json'), ready_path=str(directory/'ready.json'))
    runtime = dict(schema='guanheng.wt-runtime-status.v1', control_id=control, instance_id=instance,
        configuration_sha256=SHA, pid=555, state='ready', error_code=None, ready=True,
        components=dict(execution=dict(state='ready', ready=True, pending=True, forced=False, pid=777, business_observation=reference)))
    (tmp_path/'status.json').write_text(json.dumps(runtime))
    (directory/'ready.json').write_text(json.dumps(dict(schema='guanheng.execution.ready.v1',
        control_id=execution, config_sha256='b'*64, pid=777, closed=False)))
    (directory/'strategies.json').write_text(json.dumps(dict(schema='guanheng.configured-cta-observation.v2',
        control_id=execution, config_sha256='b'*64, pid=777, strategies=rows)))
    settings = ConsoleSettings(wt_status_file=str(tmp_path/'status.json'), wt_control_id=control,
        wt_instance_id=instance, wt_configuration_sha256=SHA, account_source='wt_account_publication')
    # ASA专属读取不等待无关账户NAP；详情账户分组仍沿其独立错误语义。
    import guanheng_app.live_strategy_performance as live_module
    monkeypatch.setattr(live_module,'observe_published_account',lambda *_args,**_kwargs: (_ for _ in ()).throw(AssertionError('NAP must not feed allocated strategies')))
    app = create_app(settings)
    with TestClient(app) as client:
        catalog = client.get('/v1/ui/strategy-catalog')
        assert catalog.status_code == 200
        keys = {(s['strategy_id'],s['strategy_version']) for s in catalog.json()['strategies']}
        assert (OLD,'1.2.2') in keys and (NEW,'0.2.0a1') in keys
        detail = client.get('/v1/ui/strategy-details', params={'strategy_id':NEW})
        assert detail.status_code == 200
        assert detail.json()['calculation']['strategy_id'] == NEW
        assert detail.json()['assignment']['scope'] == 'strategy-allocated'
        assert len(detail.json()['calculation']['positions']) == 9
        selected = client.get('/v1/ui/strategy-runtime', params={'strategy_id':NEW})
        assert selected.status_code == 200 and selected.json()['strategy']['strategy_id'] == NEW
        for sid, version, quantity in ((OLD,'1.2.2',100),(NEW,'0.2.0a1',200)):
            value = client.get('/v1/ui/live-strategy-performance', params={'strategy_id':sid,'strategy_version':version})
            assert value.status_code == 200
            body = value.json()
            assert body['state'] == 'available' and body['markers'][0]['quantity'] == quantity
            assert body['summary'] is None and body['current']['is_current'] is False
        assert client.get('/v1/ui/strategy-details?strategy_id=a&strategy_id=b').status_code == 422
        assert client.post('/v1/ui/strategy-details').status_code == 405
    assert app.state.shutdown_complete
