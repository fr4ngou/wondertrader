"""原Native JSON形态→真实ASA SQLite；仅隔离归属，不声称实际WT/账户派发资格。"""
import ctypes as C
from datetime import datetime, timezone
from decimal import Decimal as D
import json
from time import monotonic
from uuid import uuid4
from types import SimpleNamespace
from dataclasses import replace
from hashlib import sha256

import pytest

from guanheng_wt_runtime.account_allocation import AccountAllocation, AccountSnapshot, BookIdentity, OwnedPosition, StrategySeed
from guanheng_wt_runtime.account_attribution import AttributionBridge, AttributionCoordinator, NativeEvent, NativeReply
from guanheng_wt_runtime.strategy_state import StrategyStateWrite

CODE, SHA = 'SSE.ETF.510500', 'a'*64
DAY, NEXT = '2026-11-06', '2026-11-09'
STAMP = '2026-11-06T07:00:00+00:00'


def end(): return monotonic()+10


def setup(root, *, day=DAY, following=NEXT, now=STAMP, include_third=False):
    identity = BookIdentity(SHA, str(uuid4()), 'b'*64)
    book = AccountAllocation(root, identity, owner_check=lambda: None)
    seeds = [StrategySeed('old', '1.2.2', D('10000'), (OwnedPosition(CODE, 10000, 10000),), 0, (CODE,)),
             StrategySeed('new', '0.2.0a1', D('1050'), (), 1, (CODE,))]
    if include_third:
        seeds.append(StrategySeed('third', '0.2.0a1', D('250000.05'), (), 2, (CODE,)))
    book.initialize(tuple(seeds), D('0'),
                    AccountSnapshot(1, day, D('2000000'), (OwnedPosition(CODE, 10000, 10000),), SHA), deadline=end())
    coordinator = AttributionCoordinator(book, control_id=str(uuid4()), account_scope_sha256=SHA,
        strategy_ids=tuple(seed.strategy_id for seed in seeds), fee_bound=lambda *args: D('5'), settlement_day=lambda day: following,
        utcnow=lambda: datetime.fromisoformat(now))
    return book, coordinator, AttributionBridge(coordinator, callback_seconds=5)


def send(bridge, kind, body, *, epoch=0, remaining_ms=5000):
    raw = json.dumps(body).encode();buffer = C.create_string_buffer(raw)
    role = 1 if kind == 1 else 3 if kind == 7 else 2
    event = NativeEvent(C.sizeof(NativeEvent), 1, kind, role, epoch, remaining_ms if kind in (7,8,9,12) else 0,
                        len(raw), 0, C.cast(buffer, C.c_void_p))
    reply = NativeReply(C.sizeof(NativeReply), 1, -1, 0, 0)
    result = bridge._callback(C.byref(event), C.byref(reply), None)
    return result, reply


def targets(coordinator, bridge, *, known_at=STAMP, buyer='new'):
    for epoch, sid in enumerate(coordinator.strategy_ids, start=1):
        quantity = {'old': 10000, buyer: 1000}.get(sid, 0)
        coordinator.prepare_intent(sid, epoch, source_sha256=SHA, known_at=known_at,
            buy_price_caps={}, common_prices=(), deadline=end())
        result, reply = send(bridge, 1, dict(strategy_id=sid, targets=[dict(symbol=CODE, quantity=quantity)]), epoch=epoch)
        assert result == 0, bridge.failure
    result, reply = send(bridge, 2, dict(execution_id='one-native-owner', targets=[dict(symbol=CODE, quantity=11000)]))
    assert result == 0, bridge.failure


def prepared(coordinator, bridge, *, known_at=STAMP, buyer='new'):
    targets(coordinator, bridge, known_at=known_at, buyer=buyer)
    auth = dict(execution_id='one-native-owner', instance_id='qmt', symbol=CODE, side='buy',
                requested_quantity=200 if buyer == 'new' else 100, limit_price_cny='10.01',
                account_known=True, account_available_cny=2000000)
    result, reply = send(bridge, 4, auth)
    assert result == 0 and reply.authorized_quantity == 100, bridge.failure
    group = dict(instance_id='qmt', native_generation=1, group_id=1, symbol=CODE,
                 side='buy', quantity=100, limit_price_cny='10.01')
    assert send(bridge, 5, group)[0] == 0, bridge.failure
    child = dict(group, user_tag='otp.original-runtime.1', entrust_id='qmt.original.1')
    assert send(bridge, 6, child)[0] == 0, bridge.failure
    # 原delegate已结束，worker仍未取得UUID；ASA须保留该原WTchild。
    assert send(bridge, 10, dict(group, accepted_children=1))[0] == 0, bridge.failure
    command = dict(child, command_id=str(uuid4()), command_sha256='c'*64)
    assert send(bridge, 7, command)[0] == 0, bridge.failure
    return command


def test_strategy_recovery_state_and_target_share_commit(tmp_path, monkeypatch):
    book, coordinator, bridge = setup(tmp_path)
    key = 'strategy-decision'
    before = '{"schema":"strategy.v1","line":9}'
    after = '{"schema":"strategy.v1","line":10}'
    initial = StrategyStateWrite(key, None, before)
    book.commit_strategy_state('new', initial, deadline=end())
    first = StrategyStateWrite(key, sha256(before.encode('ascii')).hexdigest(), after)
    body = dict(strategy_id='new', targets=[dict(symbol=CODE, quantity=100)])

    def submit(bridge, coordinator, epoch, update):
        coordinator.prepare_intent('new', epoch, source_sha256=SHA, known_at=STAMP,
            buy_price_caps={}, common_prices=(), strategy_state=update, deadline=end())
        return send(bridge, 1, body, epoch=epoch)[0]

    assert submit(bridge, coordinator, 1, first) == 0, bridge.failure
    original = book.current_targets(deadline=end())['new']
    assert submit(bridge, coordinator, 1, first) == 0, bridge.failure
    assert book.current_targets(deadline=end())['new'] == original
    assert book.load_strategy_state('old', key, deadline=end()) is None

    # 策略状态已进入事务时出错，目标、状态和去重事件都应回滚。
    body['targets'][0]['quantity'] = 200
    next_state = StrategyStateWrite(key, sha256(after.encode('ascii')).hexdigest(), before)
    with monkeypatch.context() as patch:
        def interrupt(*_):
            raise RuntimeError('simulated pre-commit interruption')

        patch.setattr(book, '_save', interrupt)
        assert submit(bridge, coordinator, 2, next_state) != 0
    assert book.load_strategy_state('new', key, deadline=end()) == after
    assert book.current_targets(deadline=end())['new'] == original
    # 以前的状态版本尝试提交新目标，两项均不能写入。
    assert submit(bridge, coordinator, 3, StrategyStateWrite(key, first.expected_revision, before)) != 0
    identity = book.identity
    book.close(end())
    recovered = AccountAllocation(tmp_path, identity, owner_check=lambda: None, require_existing=True)
    try:
        assert recovered.load_strategy_state('new', key, deadline=end()) == after
        assert recovered.current_targets(deadline=end())['new'] == original
        assert original.targets[0].quantity == 100
        successor = AttributionCoordinator(recovered, control_id=str(uuid4()), account_scope_sha256=SHA,
            strategy_ids=('old', 'new'), fee_bound=lambda *args: D('5'), settlement_day=lambda day: NEXT)
        resume_bridge = AttributionBridge(successor, callback_seconds=5)
        restored = successor.restore_strategy_target('new', key, deadline=end())
        assert restored == original
        successor.prepare_intent('new', 1, source_sha256=SHA, known_at=STAMP, buy_price_caps={},
            common_prices=(), recovery_target=restored.intent_id, deadline=end())
        body['targets'][0]['quantity'] = 100
        assert send(resume_bridge, 1, body, epoch=1)[0] == 0, resume_bridge.failure
        assert recovered.current_targets(deadline=end())['new'] == original
        body['targets'][0]['quantity'] = 200
        assert send(resume_bridge, 1, body, epoch=1)[0] != 0
        assert recovered.current_targets(deadline=end())['new'] == original
    finally:
        recovered.close(end())


@pytest.mark.parametrize('kind', [8, 12])
@pytest.mark.parametrize('committed', [False, True])
def test_durable_broker_timeout_retries_original_receipt(tmp_path, monkeypatch, kind, committed):
    book, coordinator, bridge = setup(tmp_path)
    command = prepared(coordinator, bridge)
    fill = dict(command, source_kind='query-result', source_sha256='d'*64, trading_date=20261106,
                trade_id='nqh1.timeout-retry', quantity=20, price_cny='10.01',
                amount_cny='200.20', trade_time=93102000, fee_cny=None)
    project = book.project_broker_batch

    def timeout(work, *, deadline):
        if committed:
            project(work, deadline=deadline)
        raise TimeoutError('allocation_deadline')

    body = fill if kind == 8 else {'kind': 8, 'rows': [json.dumps(fill)]}
    monkeypatch.setattr(book, 'project_broker_batch', timeout)
    result, reply = send(bridge, kind, body)
    assert result == reply.decision == 0, bridge.failure
    assert bridge.failure is None
    assert len(book.pending_events(deadline=end())) == (0 if committed else 1)
    original = book.lookup_prepared(command['user_tag'], deadline=end())

    auth = dict(instance_id='qmt', symbol=CODE, side='buy', requested_quantity=100, limit_price_cny='10.01')
    assert send(bridge, 4, auth)[1].authorized_quantity == 0
    coordinator.replay_pending(deadline=end())
    assert len(book.pending_events(deadline=end())) == (0 if committed else 1)
    monkeypatch.setattr(book, 'project_broker_batch', project)
    coordinator.replay_pending(deadline=end())
    assert book.pending_events(deadline=end()) == ()
    assert send(bridge, kind, body)[0] == 0, bridge.failure
    view = book.view('new', deadline=end())
    assert view.positions[0].quantity == 20
    assert view.ledger_cash_cny == D('849.80')
    assert book.lookup_prepared(command['user_tag'], deadline=end()) == original
    assert send(bridge, 4, auth)[1].authorized_quantity == 0
    from guanheng_wt_runtime.execution_strategy import BrokerObservationValue, BrokerPositionValue
    stamp = int(datetime.fromisoformat(STAMP).timestamp()*1000)
    broker = BrokerObservationValue(True, True, 9, stamp, 10, stamp, stamp,
        2000000, 1999799.8, (BrokerPositionValue(CODE, True, 10020, 10000),))
    context = SimpleNamespace(broker_observation=lambda: broker)
    assert coordinator.observe_context(context, deadline=end(), max_age_seconds=30) is None
    assert not coordinator._broker_projection_needs_account


@pytest.mark.parametrize('remaining_ms, expected', [(5000, -1), (10000, 0)])
def test_deferred_receipt_respects_native_deadline(tmp_path, monkeypatch, remaining_ms, expected):
    book, coordinator, bridge = setup(tmp_path)
    command = prepared(coordinator, bridge)
    clock = [monotonic()]
    bridge._clock = lambda: clock[0]

    def timeout(*args, **kwargs):
        clock[0] += 5.1
        raise TimeoutError('allocation_deadline')

    monkeypatch.setattr(book, 'project_broker_batch', timeout)
    fill = dict(command, source_kind='query-result', source_sha256='d'*64, trading_date=20261106,
                trade_id='nqh1.timeout-budget', quantity=20, price_cny='10.01',
                amount_cny='200.20', trade_time=93102000, fee_cny=None)
    assert send(bridge, 12, {'kind': 8, 'rows': [json.dumps(fill)]}, remaining_ms=remaining_ms)[0] == expected
    assert len(book.pending_events(deadline=end())) == 1


def test_broker_timeout_before_durable_receipt_preserves_failure(tmp_path, monkeypatch):
    book, coordinator, bridge = setup(tmp_path)
    command = prepared(coordinator, bridge)
    fill = dict(command, source_kind='query-result', source_sha256='d'*64, trading_date=20261106,
                trade_id='nqh1.receipt-not-committed', quantity=20, price_cny='10.01',
                amount_cny='200.20', trade_time=93102000, fee_cny=None)

    def timeout(*args, **kwargs):
        raise TimeoutError('allocation_deadline')

    monkeypatch.setattr(book, 'receive_broker_events', timeout)
    assert send(bridge, 12, {'kind': 8, 'rows': [json.dumps(fill)]})[0] == -1
    assert isinstance(bridge.failure, TimeoutError)
    assert book.pending_events(deadline=end()) == ()


def test_broker_query_persists_original_rows_with_one_commit_and_keeps_replay_identity(tmp_path, monkeypatch):
    from contextlib import contextmanager
    from guanheng_wt_runtime.runtime_diagnostics import ProcessEventLog
    book, coordinator, bridge = setup(tmp_path)
    diagnostics = ProcessEventLog(tmp_path, str(uuid4()), 'cta-broker-query')
    monkeypatch.setattr(coordinator, '_broker_query_observation', diagnostics.broker_query)
    ticks = iter((1.0, 1.00125, 1.00175))
    monkeypatch.setattr('guanheng_wt_runtime.account_attribution.perf_counter', lambda: next(ticks))
    transactions = []
    transaction = book._transaction

    @contextmanager
    def counted(deadline):
        transactions.append(deadline)
        with transaction(deadline) as db:
            yield db

    monkeypatch.setattr(book, '_transaction', counted)
    rows = [json.dumps(dict(source_kind='query-result', source_sha256=SHA, output_index=i,
                            user_tag=f'otp.history.{i}')) for i in range(44)]
    assert send(bridge, 12, dict(kind=9, rows=rows))[0] == 0, bridge.failure
    assert len(transactions) == 1
    assert diagnostics.drain()
    [sample] = map(json.loads, (tmp_path / 'process-events.jsonl').read_bytes().splitlines())
    assert (sample['event'], sample['kind'], sample['rows'], sample['unbound']) == ('broker_query_batch', 9, 44, 44)
    assert sample['receive_ms'] == 1.25 and sample['projection_ms'] == .5 and sample['deferred'] is False
    assert 'otp.history' not in json.dumps(sample)
    inbox = book.pending_events(deadline=end())
    assert [row.raw_json for row in inbox] == [row.encode() for row in rows]
    assert all(row.reason == 'attribution_command_unmapped' and not row.applied for row in inbox)
    assert send(bridge, 9, json.loads(rows[0]))[0] == 0, bridge.failure
    assert book.pending_events(deadline=end()) == inbox
    assert send(bridge, 12, dict(kind=9, rows=[rows[0], '{}']))[0] == -1
    assert book.pending_events(deadline=end()) == inbox


def test_owned_broker_query_uses_one_projection_commit(tmp_path, monkeypatch):
    from contextlib import contextmanager
    book, coordinator, bridge = setup(tmp_path)
    command = prepared(coordinator, bridge)
    transaction = book._transaction
    commits = []

    @contextmanager
    def counted(deadline):
        if getattr(getattr(book, '_projection', None), 'db', None) is None:
            commits.append(deadline)
        with transaction(deadline) as db:
            yield db

    monkeypatch.setattr(book, '_transaction', counted)
    fill = dict(command, source_kind='query-result', source_sha256='d'*64, trading_date=20261106,
                trade_id='nqh1.batch', quantity=20, price_cny='10.01', amount_cny='200.20',
                trade_time=93102000, fee_cny=None)
    rows = [json.dumps(dict(fill, output_index=i)) for i in range(44)]
    assert send(bridge, 12, dict(kind=8, rows=rows))[0] == 0, bridge.failure
    assert len(commits) == 2
    assert book.view('new', deadline=end()).positions[0].quantity == 20
    assert book.pending_events(deadline=end()) == ()

    conflict = dict(fill, source_sha256='e'*64, quantity=21, amount_cny='210.21')
    result, _ = send(bridge, 12, dict(kind=8, rows=[json.dumps(conflict)]))
    assert result == -1 and bridge.failure.reason == 'fill_economic_conflict'
    assert book.view('new', deadline=end()).positions[0].quantity == 20
    assert book.pending_events(deadline=end())[0].reason == 'fill_economic_conflict'
    with book._transaction(end()) as db:
        assert db.execute("SELECT COUNT(*) FROM asa_conflicts WHERE kind='fill_economic_conflict'").fetchone()[0] == 1


def test_compaction_keeps_original_receipts_and_replays_one_unbound_fact(tmp_path):
    from hashlib import sha256
    import sqlite3
    from contextlib import closing
    from guanheng_wt_runtime.allocation_compaction import compact

    book, _, _ = setup(tmp_path)
    tag = 'otp.future-binding'
    fill = dict(source_kind='query-result', source_sha256=SHA, trading_date=20261106,
                trade_id='nqh1.unbound', user_tag=tag, quantity=20, price_cny='10.01', amount_cny='200.20')
    originals = [json.dumps(dict(fill, request_id=str(i))).encode() for i in range(3)]
    with book._transaction(end()) as db:
        db.executemany(
            "INSERT INTO asa_inbox(event_id,kind,raw_json,payload_sha256,source_sha256,applied,reason)"
            " VALUES(?,'8',?,?,?,0,'attribution_command_unmapped')",
            ((str(uuid4()), raw, sha256(raw).hexdigest(), SHA) for raw in originals))
    output = tmp_path / 'rehearsal'
    report = compact(book.path, output)
    assert (report['original_receipts'], report['candidate_receipts'], report['mapped_duplicates']) == (3, 1, 2)
    with closing(sqlite3.connect(output / 'receipt-map.sqlite3')) as mapping:
        assert mapping.execute('SELECT original_sequence, retained_sequence FROM receipt ORDER BY original_sequence'
                               ).fetchall() == [(2, 1), (3, 1)]
    with closing(sqlite3.connect(output / 'original.sqlite3')) as archive:
        assert [row[0] for row in archive.execute('SELECT raw_json FROM asa_inbox ORDER BY sequence')] == originals
    resumed = AccountAllocation(output, book.identity, owner_check=lambda: None, require_existing=True)
    replay, command = resumed.receive_broker_event(str(uuid4()), '8', originals[-1], SHA, tag, deadline=end())
    assert command is None and replay.sequence == 1 and replay.raw_json == originals[0]
    assert resumed.pending_events(deadline=end()) == (replay,)


def test_query_receipt_deduplicates_on_business_state_across_restart(tmp_path):
    book, coordinator, bridge = setup(tmp_path)
    command = prepared(coordinator, bridge)
    fill = dict(command, source_kind='query-result', source_sha256='d'*64, trading_date=20261106,
                trade_id='nqh1.repeat', quantity=20, price_cny='10.01', amount_cny='200.20',
                trade_time=93102000, fee_cny=None, request_id='first', output_index=0)

    def accept(active_bridge, row):
        assert send(active_bridge, 12, dict(kind=8, rows=[json.dumps(row)]))[0] == 0, active_bridge.failure

    def counts(store):
        with store._transaction(end()) as db:
            return tuple(db.execute(sql).fetchone()[0] for sql in (
                "SELECT count(*) FROM asa_inbox WHERE kind='8'",
                "SELECT count(*) FROM asa_source_proof WHERE kind='fills'",
            ))

    accept(bridge, fill)
    for index in range(15):
        accept(bridge, dict(fill, request_id=f'query-{index}', output_index=index, source_sha256='e'*64))
    accept(bridge, dict(fill, request_id='equivalent-format', price_cny='10.0100', amount_cny='200.2', quantity=20.0))
    assert counts(book) == (1, 1)
    reopened = AccountAllocation(tmp_path, book.identity, owner_check=lambda: None, require_existing=True)
    resumed = AttributionCoordinator(reopened, control_id=str(uuid4()), account_scope_sha256=SHA,
        strategy_ids=coordinator.strategy_ids, fee_bound=lambda *args: D('5'), settlement_day=lambda _: NEXT)
    resumed_bridge = AttributionBridge(resumed, callback_seconds=5)
    accept(resumed_bridge, dict(fill, request_id='after-restart', native_generation=2, source_sha256='f'*64))
    assert counts(reopened) == (1, 1)
    accept(resumed_bridge, dict(fill, request_id='fee', source_sha256='1'*64, fee_cny='1.00'))
    assert counts(reopened) == (2, 2)
    accept(resumed_bridge, dict(fill, request_id='fee-again', source_sha256='2'*64, fee_cny='1.00'))
    assert counts(reopened) == (2, 2)
    assert reopened.view('new', deadline=end()).positions[0].quantity == 20


def test_source_processing_and_failure_recording_have_distinct_diagnostics(tmp_path, monkeypatch):
    book, coordinator, bridge = setup(tmp_path)
    command = prepared(coordinator, bridge)
    source = dict(command, source_kind='query-result', source_sha256='d'*64)
    order = dict(source, terminal=True, order_state=53, filled_quantity=20, remaining_quantity=0)

    def recording_timeout(*args, **kwargs):
        raise TimeoutError('allocation_deadline')

    monkeypatch.setattr(book, 'mark_event_failed', recording_timeout)
    assert send(bridge, 9, order)[0] == -1
    assert bridge.failure.reason == 'terminal_missing_fills'
    diagnostic = bridge.failure_diagnostic
    assert diagnostic['phase'] == 'handle_event' and diagnostic['event_kind'] == 9
    assert diagnostic['remaining_ms'] == 5000
    assert diagnostic['exception']['reason'] == 'terminal_missing_fills'
    assert diagnostic['recording_failure']['reason'] == 'allocation_deadline'
    assert len(book.pending_events(deadline=end())) == 1
    assert command['command_id'] not in json.dumps(diagnostic)


def test_prepared_binding_is_durable_before_native_ack_and_old_inventory_stays_old(tmp_path):
    book, coordinator, bridge = setup(tmp_path)
    command = prepared(coordinator, bridge)
    assert book.lookup_prepared(command['user_tag'], deadline=end()).command_id == command['command_id']
    assert book.view('old', deadline=end()).positions[0].quantity == 10000
    assert all(p.quantity == 0 for p in book.view('new', deadline=end()).positions)
    assert book.view('new', deadline=end()).spendable_cash_cny == D('44.00')


@pytest.mark.parametrize(('buyer', 'initial_cash'), [('new', '1050'), ('third', '250000.05')])
def test_terminal_before_fill_then_replay_and_cross_source_fill_idempotence(tmp_path, buyer, initial_cash):
    book, coordinator, bridge = setup(tmp_path, include_third=buyer == 'third')
    command = prepared(coordinator, bridge, buyer=buyer)
    assert book.view(buyer, deadline=end()).spendable_cash_cny == D(initial_cash)-D('1006.00')
    source = dict(command, source_kind='query-result', source_sha256='d'*64, trading_date=20261106)
    order = dict(source, terminal=True, order_state=53, filled_quantity=20, remaining_quantity=0, price_cny='10.01')
    assert send(bridge, 9, order)[0] == 0, bridge.failure
    assert len(book.pending_events(deadline=end())) == 1
    fill = dict(source, trade_id='nqh1.synthetic-original-fill', quantity=20, price_cny='10.01',
                amount_cny='200.20', trade_time=93102000, fee_cny=None)
    assert send(bridge, 8, fill)[0] == 0, bridge.failure
    coordinator.replay_pending(deadline=end())
    assert book.pending_events(deadline=end()) == ()
    assert book.view(buyer, deadline=end()).positions[0].quantity == 20
    assert book.view(buyer, deadline=end()).ledger_cash_cny == D(initial_cash)-D('200.20')
    assert book.view(buyer, deadline=end()).unknown_fee_count == 1
    assert book.view('old', deadline=end()).positions[0].quantity == 10000
    if buyer == 'third':
        other = book.view('new', deadline=end())
        assert other.ledger_cash_cny == D('1050') and not other.positions
    # 同一原成交在实时源及下一份查询中出现，数量/本金只入账一次，全部证明保留。
    assert send(bridge, 8, dict(fill, source_kind='derived-facts', source_sha256='e'*64))[0] == 0, bridge.failure
    assert book.view(buyer, deadline=end()).positions[0].quantity == 20
    # 已关闭原单同经济终态重观测仍可消费，不产生新命令或回退状态。
    assert send(bridge, 9, dict(order, source_sha256='f'*64))[0] == 0, bridge.failure
    assert book.pending_events(deadline=end()) == ()


def test_broker_fill_clock_pending_keeps_original_event_and_replays(tmp_path, monkeypatch):
    from datetime import timedelta
    from zoneinfo import ZoneInfo
    from guanheng_wt_runtime import account_allocation, account_attribution

    book, coordinator, bridge = setup(tmp_path)
    command = prepared(coordinator, bridge)
    executed = datetime(2026, 11, 6, 9, 31, 2, tzinfo=ZoneInfo('Asia/Shanghai'))

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return current[0].astimezone(tz)

    current = [executed - timedelta(milliseconds=269)]
    monkeypatch.setattr(account_attribution, 'datetime', Clock)
    monkeypatch.setattr(account_allocation, 'datetime', Clock)
    fill = dict(command, source_kind='derived-facts', source_sha256='d'*64,
                trading_date=20261106, trade_id='nqh1.synthetic-broker-clock',
                quantity=20, price_cny='10.01', amount_cny='200.20',
                trade_time=93102000, fee_cny=None)
    assert send(bridge, 8, fill)[0] == 0, bridge.failure
    assert book.pending_events(deadline=end())[0].reason == 'fill_clock_pending'
    assert book.view('new', deadline=end()).positions == ()
    current[0] = executed + timedelta(milliseconds=100)
    coordinator.replay_pending(deadline=end())
    assert book.pending_events(deadline=end()) == ()
    assert book.view('new', deadline=end()).positions[0].quantity == 20


def test_wait_for_complete_targets_then_use_wt_risk_cut_and_filter(tmp_path):
    book, coordinator, bridge = setup(tmp_path)
    order = dict(instance_id='qmt', symbol=CODE, side='sell', requested_quantity=9000, limit_price_cny='2')
    assert send(bridge, 4, order)[1].decision == 1
    targets(coordinator, bridge)
    assert send(bridge, 2, dict(targets=[dict(symbol=CODE, quantity=5500)]))[0] == 0
    assert send(bridge, 4, order)[1].authorized_quantity == 4500
    assert send(bridge, 4, dict(order, side='buy'))[1].authorized_quantity == 0
    # 过滤省略与明确目标为零含义不同。旧缓存即使还发起执行也不能被当作当前许可。
    assert send(bridge, 2, dict(targets=[]))[0] == 0
    assert send(bridge, 4, order)[1].authorized_quantity == 0
    assert send(bridge, 2, dict(targets=[dict(symbol=CODE, quantity=0)]))[0] == 0
    assert send(bridge, 4, order)[1].authorized_quantity == 9000
    assert book.view('old', deadline=end()).positions[0].quantity == 10000


def test_return_to_previous_targets_rebuilds_active_plan(tmp_path):
    _, coordinator, bridge = setup(tmp_path)
    targets(coordinator, bridge)
    request = dict(instance_id='qmt', symbol=CODE, side='buy', requested_quantity=100,
                   limit_price_cny='10.01')
    assert send(bridge, 4, request)[1].authorized_quantity == 100
    assert send(bridge, 2, dict(targets=[dict(symbol=CODE, quantity=10000)]))[0] == 0
    assert send(bridge, 4, request)[1].authorized_quantity == 0
    assert send(bridge, 2, dict(targets=[dict(symbol=CODE, quantity=11000)]))[0] == 0
    result, reply = send(bridge, 4, request)
    assert result == 0, bridge.failure
    assert reply.authorized_quantity == 100


def test_replay_prioritizes_original_events_with_order_binding(tmp_path):
    book, coordinator, bridge = setup(tmp_path)
    command = prepared(coordinator, bridge)
    for i in range(5):
        historical = dict(source_kind='query-result', source_sha256=SHA,
                          user_tag=f'otp.external.{i}', output_index=i)
        assert send(bridge, 9, historical)[0] == 0
    source = dict(command, source_kind='query-result', source_sha256='d'*64, trading_date=20261106)
    order = dict(source, terminal=True, order_state=53, filled_quantity=20, remaining_quantity=0)
    assert send(bridge, 9, order)[0] == 0
    fill = dict(source, trade_id='nqh1.replay-bound', quantity=20, price_cny='10.01',
                amount_cny='200.20', trade_time=93102000, fee_cny=None)
    assert send(bridge, 8, fill)[0] == 0
    coordinator.replay_pending(limit=1, deadline=end())
    assert book.lookup_wt_child(command['user_tag'], deadline=end()).terminal_state == 'cancelled'
    assert len(book.pending_events(deadline=end())) == 5


def test_opposite_targets_never_transfer_without_broker_fill(tmp_path):
    from guanheng_wt_runtime.account_allocation import CommonPrice
    book, coordinator, bridge = setup(tmp_path)
    quote = CommonPrice(CODE, D('2'), STAMP, SHA, ('old', 'new'), True)
    for sid, quantity, epoch in [('old', 9000, 1), ('new', 1000, 2)]:
        coordinator.prepare_intent(sid, epoch, source_sha256=SHA, known_at=STAMP,
            buy_price_caps={}, common_prices=(quote,), deadline=end())
        assert send(bridge, 1, dict(strategy_id=sid, targets=[dict(symbol=CODE, quantity=quantity)]),
                    epoch=epoch)[0] == 0
    assert send(bridge, 2, dict(targets=[dict(symbol=CODE, quantity=10000)]))[0] == 0
    for side in ('buy', 'sell'):
        order = dict(instance_id='qmt', symbol=CODE, side=side, requested_quantity=1000, limit_price_cny='2')
        assert send(bridge, 4, order)[1].authorized_quantity == 0
    assert book.view('old', deadline=end()).positions[0].quantity == 10000
    assert book.view('new', deadline=end()).positions == ()


def test_source_binary_tail_is_normalized_but_material_precision_is_preserved_for_review():
    normalize = AttributionCoordinator._source_decimal
    assert normalize('2.01', '.001') == D('2.010')
    assert normalize('2.0100000000000002', '.001') == D('2.010')
    assert normalize('200.20000000000002', '.01') == D('200.20')
    for value, quantum in [('2.0101', '.001'), ('2.011', '.01'), ('1e309', '.01')]:
        with pytest.raises(RuntimeError, match='source_cash_precision_unproven'):
            normalize(value, quantum)


def test_duplicate_target_epoch_and_inbox_unknown_does_not_starve_later_terminal(tmp_path):
    book, coordinator, bridge = setup(tmp_path)
    targets(coordinator, bridge)
    same = dict(strategy_id='new', targets=[dict(symbol=CODE, quantity=1000)])
    before = book.current_targets(deadline=end())['new']
    assert send(bridge, 1, same, epoch=2)[0] == 0, bridge.failure
    assert book.current_targets(deadline=end())['new'] == before
    unknown = dict(user_tag='otp.foreign.1', command_id=None, terminal=False,
                   side='sell', remaining_quantity=100, filled_quantity=0, source_sha256='7'*64)
    assert send(bridge, 9, unknown)[0] == 0, bridge.failure
    # 不重新触发targets，沿当前原计划创建这次原child。
    assert send(bridge, 4, dict(instance_id='qmt', symbol=CODE, side='buy', requested_quantity=200, limit_price_cny='10.01'))[1].authorized_quantity == 100
    group = dict(instance_id='qmt', native_generation=1, group_id=1, symbol=CODE,
                 side='buy', quantity=100, limit_price_cny='10.01')
    assert send(bridge, 5, group)[0] == 0
    command = dict(group, user_tag='otp.owned.1', entrust_id='qmt.owned.1', command_id=str(uuid4()), command_sha256='c'*64)
    assert send(bridge, 6, command)[0] == 0
    assert send(bridge, 10, dict(group, accepted_children=1))[0] == 0
    assert send(bridge, 7, command)[0] == 0
    source = dict(command, source_kind='query-result', source_sha256='d'*64, trading_date=20261106)
    assert send(bridge, 9, dict(source, terminal=True, order_state=53, filled_quantity=20,
                              remaining_quantity=0, price_cny='10.01'))[0] == 0
    assert send(bridge, 8, dict(source, trade_id='nqh1.starvation-test', quantity=20, price_cny='10.01',
                              amount_cny='200.20', trade_time=93102000, fee_cny=None))[0] == 0
    coordinator.replay_pending(deadline=end(), limit=1)
    coordinator.replay_pending(deadline=end(), limit=1)
    pending = book.pending_events(deadline=end())
    assert len(pending) == 1 and pending[0].reason == 'attribution_command_unmapped'
    assert book.view('new', deadline=end()).pending_groups == ()


def test_real_native_broker_value_refresh_has_stable_revision_and_unlocks_t1(tmp_path):
    from guanheng_wt_runtime.execution_strategy import BrokerObservationValue, BrokerPositionValue
    book, coordinator, bridge = setup(tmp_path, day='2026-11-04', following='2026-11-05', now='2026-11-04T01:32:00+00:00')
    command = prepared(coordinator, bridge, known_at='2026-11-03T07:00:00+00:00')
    source = dict(command, source_kind='query-result', source_sha256='d'*64, trading_date=20261104)
    assert send(bridge, 8, dict(source, trade_id='nqh1.settlement-test', quantity=20, price_cny='10.01',
                              amount_cny='200.20', trade_time=93102000, fee_cny=None))[0] == 0
    # 新完整P/A晚于实际D接收，次日Source明确20份可卖；原按交易日历的lot才成熟。
    now = datetime(2026, 11, 5, 1, 31, tzinfo=timezone.utc)
    coordinator._utcnow = lambda: now
    stamp = int(now.timestamp()*1000)
    broker = BrokerObservationValue(True, True, 9, stamp, 10, stamp, stamp,
        2000000, 1999799.8, (BrokerPositionValue(CODE, True, 10020, 10020),))
    context = SimpleNamespace(event=SimpleNamespace(tdate=20261105), broker_observation=lambda: broker)
    assert coordinator.observe_context(context, deadline=end(), max_age_seconds=30) is None
    revision = book.strategy_observation('new', deadline=end()).account_revision
    broker = replace(broker, published_epoch_ms=stamp+1)
    assert coordinator.observe_context(context, deadline=end(), max_age_seconds=30) is None
    assert book.strategy_observation('new', deadline=end()).account_revision == revision
    with pytest.MonkeyPatch.context() as patch:
        def unexpected_database_call(*args, **kwargs):
            pytest.fail('already reconciled observations must not access SQLite')
        patch.setattr(book, '_transaction', unexpected_database_call)
        assert coordinator.observe_context(context, deadline=end(), max_age_seconds=30) is None
        assert coordinator.strategy_state('new', deadline=end()).account_revision == revision
    assert book.view('new', deadline=end()).positions[0].sellable == 20


def test_new_intent_waits_for_native_commit_and_inflight_authorization_keeps_original_plan(tmp_path):
    book, coordinator, bridge = setup(tmp_path)
    targets(coordinator, bridge)
    auth = dict(instance_id='qmt', symbol=CODE, side='buy', requested_quantity=100, limit_price_cny='10.01')
    assert send(bridge, 4, auth)[1].authorized_quantity == 100
    # 在原Local authorize→group之间插入另一ctx首setter前的意图，WT仍执行旧commit。
    coordinator.prepare_intent('old',3,source_sha256=SHA,known_at=STAMP,buy_price_caps={},common_prices=(),deadline=end())
    assert send(bridge,1,dict(strategy_id='old',targets=[dict(symbol=CODE,quantity=11000)]),epoch=3)[0] == 0
    group = dict(instance_id='qmt', native_generation=1, group_id=1, symbol=CODE,
                 side='buy', quantity=100, limit_price_cny='10.01')
    assert send(bridge,5,group)[0] == 0,bridge.failure
    command=dict(group,user_tag='otp.commit-barrier.1',entrust_id='qmt.commit-barrier.1',
                 command_id=str(uuid4()),command_sha256='c'*64)
    assert send(bridge,6,command)[0] == 0
    assert send(bridge,10,dict(group,accepted_children=1))[0] == 0
    assert send(bridge,7,command)[0] == 0
    fill=dict(command,source_kind='query-result',source_sha256='d'*64,trading_date=20261106,
              trade_id='nqh1.commit-barrier',quantity=20,price_cny='10.01',amount_cny='200.20',trade_time=93102000,fee_cny=None)
    assert send(bridge,8,fill)[0] == 0,bridge.failure
    assert book.view('old',deadline=end()).positions[0].quantity == 10000
    assert book.view('new',deadline=end()).positions[0].quantity == 20
    # 后继新group必须等新Native合并，不借原已完成预览绕过barrier。
    result,reply=send(bridge,4,auth)
    assert result == 0 and reply.decision == 1 and reply.authorized_quantity == 0
    assert send(bridge,2,dict(targets=[dict(symbol=CODE,quantity=12000)]))[0] == 0


def test_denied_prepared_receipt_remains_until_original_no_call_then_replay_never_dispatches(tmp_path):
    book, coordinator, bridge = setup(tmp_path)
    targets(coordinator,bridge)
    assert send(bridge,4,dict(instance_id='qmt',symbol=CODE,side='buy',requested_quantity=100,limit_price_cny='10.01'))[1].authorized_quantity == 100
    group=dict(instance_id='qmt',native_generation=1,group_id=1,symbol=CODE,side='buy',quantity=100,limit_price_cny='10.01')
    assert send(bridge,5,group)[0] == 0
    child=dict(group,user_tag='otp.denied.1',entrust_id='qmt.denied.1')
    assert send(bridge,6,child)[0] == 0
    assert send(bridge,10,dict(group,accepted_children=1))[0] == 0
    # 原prepared被拒绝也必须先留下原UUID/SHA；此合成子价越界驱动真实拒绝入口。
    command=dict(child,command_id=str(uuid4()),command_sha256='c'*64,limit_price_cny='10.02')
    assert send(bridge,7,command)[0] == -1
    pending=book.pending_events(deadline=end())
    assert len(pending)==1 and pending[0].kind=='7' and command['command_id'].encode()in pending[0].raw_json
    assert book.lookup_prepared(child['user_tag'],deadline=end()) is None
    # Native明确未进入submit_once才可结束原child；本地证明没有Source SHA。
    result=dict(command,source_kind='native-insert-result',source_sha256=None,phase=0,
                dispatch_not_entered=True,filled_quantity=0,attribution_binding_failed=True)
    assert send(bridge,11,result)[0] == 0,bridge.failure
    coordinator.replay_pending(deadline=end())
    assert book.pending_events(deadline=end()) == ()
    assert book.lookup_prepared(child['user_tag'],deadline=end()) is None
    assert book.view('new',deadline=end()).pending_groups == ()


def test_order_projection_keeps_only_live_owned_sell_and_ignores_late_active_after_terminal(tmp_path, monkeypatch):
    book, coordinator, bridge = setup(tmp_path)
    for sid, quantity, epoch in [('old', 9900, 1), ('new', 0, 2)]:
        coordinator.prepare_intent(sid, epoch, source_sha256=SHA, known_at=STAMP,
            buy_price_caps={}, common_prices=(), deadline=end())
        assert send(bridge, 1, dict(strategy_id=sid, targets=[dict(symbol=CODE, quantity=quantity)]), epoch=epoch)[0] == 0
    assert send(bridge, 2, dict(targets=[dict(symbol=CODE, quantity=9900)]))[0] == 0
    assert send(bridge, 4, dict(instance_id='qmt',symbol=CODE,side='sell',requested_quantity=100,limit_price_cny='10.01'))[1].authorized_quantity == 100
    group=dict(instance_id='qmt',native_generation=1,group_id=1,symbol=CODE,side='sell',quantity=100,limit_price_cny='10.01')
    assert send(bridge,5,group)[0] == 0
    command=dict(group,user_tag='otp.sell.1',entrust_id='qmt.sell.1',command_id=str(uuid4()),command_sha256='c'*64)
    assert send(bridge,6,command)[0] == 0
    assert send(bridge,10,dict(group,accepted_children=1))[0] == 0
    assert send(bridge,7,command)[0] == 0
    order=dict(command,source_kind='query-result',source_sha256='d'*64,terminal=False,order_state=49,
               filled_quantity=0,remaining_quantity=100,order_id='qmt.123',trading_date=20261106)
    assert send(bridge,9,order)[0] == 0
    assert set(coordinator._order_sources) == {command['user_tag']}
    coordinator._order_sources.clear()
    def timeout(*args, **kwargs):
        raise TimeoutError('allocation_deadline')

    with monkeypatch.context() as scoped:
        scoped.setattr(book, 'project_broker_batch', timeout)
        assert send(bridge,9,dict(order,request_id='new-query'))[0] == 0
        assert coordinator._order_sources == {}
        assert coordinator._broker_projection_needs_account
    coordinator.replay_pending(deadline=end())
    assert not coordinator._sell_restore_pending
    assert set(coordinator._order_sources) == {command['user_tag']}
    with book._transaction(end()) as db:
        assert db.execute("SELECT count(*) FROM asa_inbox WHERE kind='9'").fetchone()[0] == 1
    reduced = dict(order, remaining_quantity=90, source_sha256='1'*64)
    assert send(bridge,9,reduced)[0] == 0
    coordinator._order_sources.clear()
    assert send(bridge,9,dict(order,request_id='restart-old'))[0] == 0
    assert send(bridge,9,dict(reduced,request_id='restart-new'))[0] == 0
    assert coordinator._order_sources[command['user_tag']]['remaining_quantity'] == 90
    assert send(bridge,9,dict(order,request_id='late-old'))[0] == 0
    assert coordinator._order_sources[command['user_tag']]['remaining_quantity'] == 90
    assert book.lookup_wt_child(command['user_tag'],deadline=end()).terminal_state is None
    assert send(bridge,9,dict(order,terminal=True,order_state=53,remaining_quantity=0,source_sha256='e'*64))[0] == 0
    assert coordinator._order_sources == {}
    assert book.lookup_wt_child(command['user_tag'],deadline=end()).terminal_state == 'cancelled'
    # 重启后也借用持久终态，不靠无界内存墓碑判断迟到active原件。
    coordinator._order_sources.clear()
    assert send(bridge,9,dict(order,source_sha256='f'*64))[0] == 0
    assert coordinator._order_sources == {}
    foreign=dict(order,user_tag='otp.foreign.1',command_id=None,source_sha256='7'*64)
    assert send(bridge,9,foreign)[0] == 0
    assert coordinator._order_sources == {}
    assert len(book.pending_events(deadline=end())) == 1  # 外部原件保留，不能归入任一策略。


def test_weekend_native_planned_session_does_not_advance_actual_account_day(tmp_path):
    from guanheng_wt_runtime.execution_strategy import BrokerObservationValue, BrokerPositionValue
    book, coordinator, bridge = setup(tmp_path)
    command=prepared(coordinator,bridge)
    fill=dict(command,source_kind='query-result',source_sha256='d'*64,trading_date=20261106,
        trade_id='nqh1.weekend-t1',quantity=20,price_cny='10.01',amount_cny='200.20',trade_time=93102000,fee_cny=None)
    assert send(bridge,8,fill)[0] == 0
    now=datetime(2026,11,7,3,0,tzinfo=timezone.utc)
    coordinator._utcnow=lambda:now
    coordinator._trading_day_qualified=lambda day:day in (DAY,NEXT)
    coordinator._account_observation_day=lambda day:DAY if day=='2026-11-07' else None
    stamp=int(now.timestamp()*1000)
    broker=BrokerObservationValue(True,True,9,stamp,10,stamp,stamp,2000000,1999799.8,
        (BrokerPositionValue(CODE,True,10020,10000),))
    context=SimpleNamespace(event=SimpleNamespace(tdate=20261109),broker_observation=lambda:broker)
    assert coordinator.observe_context(context,deadline=end(),max_age_seconds=30) is None
    assert book.strategy_observation('old',deadline=end()).trading_day==DAY
    assert book.view('new',deadline=end()).positions[0].sellable==0
    # 官方范围之外没有可用归属日期，明确等待；原计划交易日仍不可代替。
    coordinator._account_observation_day=lambda day:None
    assert coordinator.observe_context(context,deadline=end(),max_age_seconds=30)=='account_observation_day_unqualified'
