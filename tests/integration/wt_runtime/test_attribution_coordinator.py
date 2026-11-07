"""原Native JSON形态→真实ASA SQLite；仅隔离归属，不声称实际WT/账户派发资格。"""
import ctypes as C
from datetime import datetime, timezone
from decimal import Decimal as D
import json
from time import monotonic
from uuid import uuid4
from types import SimpleNamespace
from dataclasses import replace

import pytest

from guanheng_wt_runtime.account_allocation import AccountAllocation, AccountSnapshot, BookIdentity, OwnedPosition, StrategySeed
from guanheng_wt_runtime.account_attribution import AttributionBridge, AttributionCoordinator, NativeEvent, NativeReply

CODE, SHA = 'SSE.ETF.510500', 'a'*64
DAY, NEXT = '2026-11-06', '2026-11-09'
STAMP = '2026-11-06T07:00:00+00:00'


def end(): return monotonic()+10


def setup(root, *, day=DAY, following=NEXT, now=STAMP):
    identity = BookIdentity(SHA, str(uuid4()), 'b'*64)
    book = AccountAllocation(root, identity, owner_check=lambda: None)
    book.initialize((StrategySeed('old', '1.2.2', D('10000'), (OwnedPosition(CODE, 10000, 10000),), 0, (CODE,)),
                     StrategySeed('new', '0.2.0a1', D('1050'), (), 1, (CODE,))), D('0'),
                    AccountSnapshot(1, day, D('2000000'), (OwnedPosition(CODE, 10000, 10000),), SHA), deadline=end())
    coordinator = AttributionCoordinator(book, control_id=str(uuid4()), account_scope_sha256=SHA,
        strategy_ids=('old', 'new'), fee_bound=lambda *args: D('5'), settlement_day=lambda day: following,
        utcnow=lambda: datetime.fromisoformat(now))
    return book, coordinator, AttributionBridge(coordinator, callback_seconds=5)


def send(bridge, kind, body, *, epoch=0):
    raw = json.dumps(body).encode();buffer = C.create_string_buffer(raw)
    role = 1 if kind == 1 else 3 if kind == 7 else 2
    event = NativeEvent(C.sizeof(NativeEvent), 1, kind, role, epoch, 5000 if kind in (7,8,9) else 0,
                        len(raw), 0, C.cast(buffer, C.c_void_p))
    reply = NativeReply(C.sizeof(NativeReply), 1, -1, 0, 0)
    result = bridge._callback(C.byref(event), C.byref(reply), None)
    return result, reply


def targets(coordinator, bridge, *, known_at=STAMP):
    for sid, quantity, epoch in [('old', 10000, 1), ('new', 1000, 2)]:
        coordinator.prepare_intent(sid, epoch, source_sha256=SHA, known_at=known_at,
            buy_price_caps={}, common_prices=(), deadline=end())
        result, reply = send(bridge, 1, dict(strategy_id=sid, targets=[dict(symbol=CODE, quantity=quantity)]), epoch=epoch)
        assert result == 0, bridge.failure
    result, reply = send(bridge, 2, dict(execution_id='one-native-owner', targets=[dict(symbol=CODE, quantity=11000)]))
    assert result == 0, bridge.failure


def prepared(coordinator, bridge, *, known_at=STAMP):
    targets(coordinator, bridge, known_at=known_at)
    auth = dict(execution_id='one-native-owner', instance_id='qmt', symbol=CODE, side='buy',
                requested_quantity=200, limit_price_cny='10.01', account_known=True, account_available_cny=2000000)
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


def test_prepared_binding_is_durable_before_native_ack_and_old_inventory_stays_old(tmp_path):
    book, coordinator, bridge = setup(tmp_path)
    command = prepared(coordinator, bridge)
    assert book.lookup_prepared(command['user_tag'], deadline=end()).command_id == command['command_id']
    assert book.view('old', deadline=end()).positions[0].quantity == 10000
    assert all(p.quantity == 0 for p in book.view('new', deadline=end()).positions)
    assert book.view('new', deadline=end()).spendable_cash_cny == D('44.00')


def test_terminal_before_fill_then_replay_and_cross_source_fill_idempotence(tmp_path):
    book, coordinator, bridge = setup(tmp_path)
    command = prepared(coordinator, bridge)
    source = dict(command, source_kind='query-result', source_sha256='d'*64, trading_date=20261106)
    order = dict(source, terminal=True, order_state=53, filled_quantity=20, remaining_quantity=0, price_cny='10.01')
    assert send(bridge, 9, order)[0] == 0, bridge.failure
    assert len(book.pending_events(deadline=end())) == 1
    fill = dict(source, trade_id='nqh1.synthetic-original-fill', quantity=20, price_cny='10.01',
                amount_cny='200.20', trade_time=93102000, fee_cny=None)
    assert send(bridge, 8, fill)[0] == 0, bridge.failure
    coordinator.replay_pending(deadline=end())
    assert book.pending_events(deadline=end()) == ()
    assert book.view('new', deadline=end()).positions[0].quantity == 20
    assert book.view('new', deadline=end()).ledger_cash_cny == D('849.80')
    assert book.view('new', deadline=end()).unknown_fee_count == 1
    assert book.view('old', deadline=end()).positions[0].quantity == 10000
    # 同一原成交在实时源及下一份查询中出现，数量/本金只入账一次，全部证明保留。
    assert send(bridge, 8, dict(fill, source_kind='derived-facts', source_sha256='e'*64))[0] == 0, bridge.failure
    assert book.view('new', deadline=end()).positions[0].quantity == 20
    # 已关闭原单同经济终态重观测仍可消费，不产生新命令或回退状态。
    assert send(bridge, 9, dict(order, source_sha256='f'*64))[0] == 0, bridge.failure
    assert book.pending_events(deadline=end()) == ()


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


def test_order_projection_keeps_only_live_owned_sell_and_ignores_late_active_after_terminal(tmp_path):
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
    order=dict(command,source_sha256='d'*64,terminal=False,order_state=49,filled_quantity=0,remaining_quantity=100)
    assert send(bridge,9,order)[0] == 0
    assert set(coordinator._order_sources) == {command['user_tag']}
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
