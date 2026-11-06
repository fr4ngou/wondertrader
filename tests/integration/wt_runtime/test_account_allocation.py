"""ASA实际主调用链人工oracle；纯归属事实，不创建Host/Native或金融请求。"""
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal as D, ROUND_HALF_UP, localcontext
import sqlite3
import json
from concurrent.futures import ThreadPoolExecutor
from time import monotonic
from uuid import uuid4

import pytest
import guanheng_wt_runtime.account_allocation as allocation_module

from guanheng_wt_runtime.account_allocation import (
    AccountAllocation, AccountSnapshot, AllocationError, BookIdentity, CommonPrice,
    FeeFact, FillFact, GroupBinding, OwnedPosition, PreparedCommand, StrategySeed,
    Target, TargetIntent, TerminalFact, WTChild, SellReservation, OpeningCycle,
)

CODE = 'SSE.ETF.510500'
SHA = 'a'*64
DAY, NEXT = '2026-11-06', '2026-11-09'
STAMP = '2026-11-06T07:00:00Z'


def bind(store, command, *, deadline, end=True):
    store.record_wt_child(WTChild(command.group_id, command.wt_order_id, command.quantity,
                                 command.limit_price_cny, SHA), deadline=deadline)
    result = store.bind_prepared(command, deadline=deadline)
    if end: store.record_group_end(command.group_id, 1, SHA, deadline=deadline)
    return result


def uid(): return str(uuid4())
def deadline(): return monotonic()+10


def book(root, *, old=10000, sellable=10000, old_cash='10000', new_cash='1000000', available='2000000', old_cycles=()):
    identity = BookIdentity(SHA, uid(), 'b'*64)
    store = AccountAllocation(root, identity, owner_check=lambda: None)
    snapshot = AccountSnapshot(1, DAY, D(available), (OwnedPosition(CODE, old, sellable),), SHA)
    seeds = (StrategySeed('old', '1.2.2', D(old_cash), (OwnedPosition(CODE, old, sellable),), 0, (CODE,), old_cycles),
             StrategySeed('new', '0.1.0a2', D(new_cash), (), 1, (CODE,)))
    store.initialize(seeds, D('0'), snapshot, deadline=deadline())
    return store, identity


def target(store, sid, quantity, revision=1, cap=None):
    store.record_targets(TargetIntent(uid(), sid, revision, (Target(CODE, quantity, cap),), SHA, STAMP), deadline=deadline())


def prepare(store, old, new, quantity, *, price='2', fee='5'):
    target(store, 'old', old); target(store, 'new', new)
    plan = uid(); store.plan(plan, (), deadline=deadline())
    group = uid(); store.bind_group(plan, GroupBinding(group, CODE, 'buy', quantity, D(price), D(fee)), deadline=deadline())
    command = PreparedCommand(group, uid(), uid(), SHA, quantity, D(price))
    bind(store, command, deadline=deadline())
    return plan, group, command


def fill(command, quantity, *, price='2', fee='5', fill_id=None):
    return FillFact(fill_id or uid(), command.command_id, quantity, D(price),
                    (D(price)*quantity).quantize(D('.01'), rounding=ROUND_HALF_UP), None if fee is None else D(fee), DAY, NEXT, SHA, CODE, 'buy')


def view(store, sid): return store.view(sid, deadline=deadline())
def pos(store, sid): return next(p for p in view(store, sid).positions if p.symbol == CODE)


def close(store, group, command, state, filled=None):
    if filled is None: filled = command.quantity
    store.apply_terminal(TerminalFact(uid(), group, command.command_id, state, SHA, filled), deadline=deadline())
    store.apply_terminal(TerminalFact(uid(), group, None, 'group_closed', SHA), deadline=deadline())


def test_initial_old_inventory_new_zero_and_restart(tmp_path):
    store, identity = book(tmp_path)
    assert pos(store, 'old').quantity == 10000
    assert view(store, 'new').positions == ()
    assert view(store, 'new').cash_cny == D('1000000')
    reopened = AccountAllocation(tmp_path, identity, owner_check=lambda: None)
    assert view(reopened, 'old') == view(store, 'old')


def test_same_direction_partial_fill_fifo_and_one_fee(tmp_path):
    store, _ = book(tmp_path)
    _, _, command = prepare(store, 11000, 3000, 4000)
    store.apply_fill(fill(command, 1500), deadline=deadline())
    assert pos(store, 'old').quantity == 11000
    assert pos(store, 'new').quantity == 500
    assert view(store, 'old').cash_cny == D('7996.67')
    assert view(store, 'new').cash_cny == D('998998.33')
    assert view(store, 'old').ledger_cash_cny+view(store, 'new').ledger_cash_cny == D('1006995')


def test_opposed_targets_transfer_then_native_residual(tmp_path):
    store, _ = book(tmp_path)
    target(store, 'old', 9000); target(store, 'new', 1500)
    plan = uid()
    result = store.plan(plan, (CommonPrice(CODE, D('2'), STAMP, SHA, ('old', 'new'), True),), deadline=deadline())
    assert result.orders[0].quantity == 500
    assert result.internal_transfers[0]['quantity'] == 1000
    group = uid(); store.bind_group(plan, GroupBinding(group, CODE, 'buy', 500, D('2.02'), D('5')), deadline=deadline())
    command = PreparedCommand(group, uid(), uid(), SHA, 500, D('2.02'))
    bind(store, command, deadline=deadline()); store.apply_fill(fill(command, 500, price='2.02'), deadline=deadline())
    close(store, group, command, 'filled')
    assert pos(store, 'old').quantity == 9000 and pos(store, 'new').quantity == 1500
    assert view(store, 'old').cash_cny == D('12000')
    assert view(store, 'new').cash_cny == D('996985')
    assert view(store, 'old').ledger_cash_cny+view(store, 'new').ledger_cash_cny == D('1008985')


def test_frozen_old_stock_does_not_become_internal_sellable(tmp_path):
    store, _ = book(tmp_path, sellable=0)
    target(store, 'old', 9000); target(store, 'new', 1000)
    blocked = store.plan(uid(), (CommonPrice(CODE, D('2'), STAMP, SHA, ('old', 'new'), True),), deadline=deadline())
    assert blocked.blocked_reasons == {CODE: 'internal_sellable_insufficient'}
    assert pos(store, 'old').quantity == 10000 and pos(store, 'old').sellable == 0
    assert view(store, 'new').cash_cny == D('1000000')


def test_target_change_late_fill_stays_original_plan_then_restart_idempotency(tmp_path):
    store, identity = book(tmp_path)
    _, group, command = prepare(store, 11000, 3000, 4000, fee='10')
    first = fill(command, 1500); store.apply_fill(first, deadline=deadline())
    target(store, 'new', 0, revision=2)
    assert store.plan(uid(), (), deadline=deadline()).blocked_symbols == (CODE,)
    late = fill(command, 300)
    store.apply_fill(late, deadline=deadline())
    close(store, group, command, 'cancelled', filled=1800)
    assert pos(store, 'new').quantity == 800
    reopened = AccountAllocation(tmp_path, identity, owner_check=lambda: None)
    before = view(reopened, 'new'); reopened.apply_fill(late, deadline=deadline())
    assert view(reopened, 'new') == before


def test_unknown_fee_stays_unknown_until_original_fee_fact(tmp_path):
    store, _ = book(tmp_path)
    _, group, command = prepare(store, 10000, 100, 100)
    actual = fill(command, 100, fee=None)
    store.apply_fill(actual, deadline=deadline()); close(store, group, command, 'filled')
    assert view(store, 'new').cash_cny is None
    assert view(store, 'new').reserved_cash_cny == D('5')
    event = FeeFact(uid(), actual.fill_id, D('5'), SHA)
    store.apply_fee(event, deadline=deadline()); store.apply_fee(event, deadline=deadline())
    assert view(store, 'new').cash_cny == D('999795')
    assert view(store, 'new').reserved_cash_cny == 0


def test_principal_and_fee_precede_dispatch_and_failed_group_rolls_back(tmp_path):
    store, _ = book(tmp_path, new_cash='200')
    target(store, 'old', 10000); target(store, 'new', 100)
    plan = uid(); store.plan(plan, (), deadline=deadline())
    assert store.preview_group(plan, CODE, 'buy', 100, D('2'), D('5'), deadline=deadline()).quantity == 0
    with pytest.raises(AllocationError, match='authorization_changed'):
        store.bind_group(plan, GroupBinding(uid(), CODE, 'buy', 100, D('2'), D('5')), deadline=deadline())
    assert view(store, 'new').reserved_cash_cny == 0
    with pytest.raises(AllocationError, match='command_unknown'):
        store.apply_fill(fill(PreparedCommand(uid(), uid(), uid(), SHA, 100, D('2')), 100), deadline=deadline())
    assert pos(store, 'new').quantity == 0


def test_original_prepared_identity_first_binding_then_lookup_only(tmp_path):
    store, _ = book(tmp_path)
    _, _, command = prepare(store, 10000, 100, 100)
    assert bind(store, command, deadline=deadline()).first_binding is False
    with pytest.raises(AllocationError, match='event_identity_conflict'):
        bind(store, replace(command, command_sha256='c'*64), deadline=deadline())
    assert view(store, 'new').reserved_cash_cny == D('205')


def test_child_allocations_are_fixed_before_out_of_order_fills(tmp_path):
    store, _ = book(tmp_path)
    target(store, 'old', 11000); target(store, 'new', 3000)
    plan = uid(); store.plan(plan, (), deadline=deadline()); group = uid()
    store.bind_group(plan, GroupBinding(group, CODE, 'buy', 4000, D('2'), D('10')), deadline=deadline())
    old_child = PreparedCommand(group, uid(), uid(), SHA, 1000, D('2'))
    new_child = PreparedCommand(group, uid(), uid(), SHA, 3000, D('2'))
    assert bind(store, old_child, deadline=deadline(), end=False).first_binding
    assert bind(store, new_child, deadline=deadline(), end=False).first_binding
    store.record_group_end(group, 2, SHA, deadline=deadline())
    store.apply_fill(fill(new_child, 500), deadline=deadline())
    assert pos(store, 'old').quantity == 10000 and pos(store, 'new').quantity == 500
    store.apply_fill(fill(old_child, 1000), deadline=deadline())
    assert pos(store, 'old').quantity == 11000 and pos(store, 'new').quantity == 500


def test_unknown_original_command_can_receive_actual_fill_without_releasing_reserve(tmp_path):
    store, _ = book(tmp_path)
    _, group, command = prepare(store, 10000, 100, 100)
    store.apply_terminal(TerminalFact(uid(), group, command.command_id, 'unknown', SHA), deadline=deadline())
    assert group in view(store, 'new').pending_groups
    assert view(store, 'new').reserved_cash_cny == D('205')
    store.apply_fill(fill(command, 100), deadline=deadline())
    close(store, group, command, 'filled')
    assert pos(store, 'new').quantity == 100 and view(store, 'new').reserved_cash_cny == 0


def test_order_terminal_arriving_before_trade_does_not_release_child(tmp_path):
    store, _ = book(tmp_path)
    _, group, command = prepare(store, 10000, 100, 100)
    terminal = TerminalFact(uid(), group, command.command_id, 'filled', SHA, 100)
    with pytest.raises(AllocationError, match='terminal_missing_fills'):
        store.apply_terminal(terminal, deadline=deadline())
    assert view(store, 'new').reserved_cash_cny == D('205')
    store.apply_fill(fill(command, 100), deadline=deadline())
    store.apply_terminal(terminal, deadline=deadline())
    store.apply_terminal(TerminalFact(uid(), group, None, 'group_closed', SHA), deadline=deadline())
    assert view(store, 'new').reserved_cash_cny == 0


@pytest.mark.parametrize('change,reason', [
    ({'side': 'sell'}, 'fill_scope_conflict'),
    ({'symbol': 'SZSE.ETF.159352'}, 'fill_scope_conflict'),
    ({'fee_cny': D('6')}, 'fee_bound_exceeded'),
    ({'amount_cny': D('199')}, 'fill_amount'),
])
def test_bad_source_fact_retains_binding_and_original_cash(tmp_path, change, reason):
    store, _ = book(tmp_path)
    _, _, command = prepare(store, 10000, 100, 100)
    before = view(store, 'new')
    with pytest.raises(AllocationError, match=reason):
        store.apply_fill(replace(fill(command, 100), **change), deadline=deadline())
    assert view(store, 'new') == before


def test_complete_account_snapshot_and_next_day_settlement(tmp_path, monkeypatch):
    class Monday(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 11, 9, 8, tzinfo=timezone.utc).astimezone(tz)
    monkeypatch.setattr(allocation_module, 'datetime', Monday)
    store, _ = book(tmp_path)
    _, group, command = prepare(store, 10000, 100, 100)
    store.apply_fill(fill(command, 100), deadline=deadline()); close(store, group, command, 'filled')
    friday = AccountSnapshot(2, DAY, D('1999795'), (OwnedPosition(CODE, 10100, 10000),), 'b'*64)
    store.observe_account(friday, deadline=deadline()); store.observe_account(friday, deadline=deadline())
    assert pos(store, 'new').sellable == 0
    monday = AccountSnapshot(3, NEXT, D('1999795'), (OwnedPosition(CODE, 10100, 10100),), 'c'*64)
    store.observe_account(monday, deadline=deadline())
    assert pos(store, 'new').sellable == 100
    with pytest.raises(AllocationError, match='account_position_mismatch'):
        store.observe_account(replace(monday, revision=4, positions=(OwnedPosition(CODE, 10200, 10100),)), deadline=deadline())
    assert pos(store, 'new').quantity == 100


def test_spent_account_available_is_not_reused_by_next_closed_plan(tmp_path):
    store, _ = book(tmp_path, old=0, sellable=0, old_cash='1000', new_cash='1000', available='1000')
    _, group, command = prepare(store, 500, 0, 500, fee='0')
    store.apply_fill(fill(command, 500, fee='0'), deadline=deadline()); close(store, group, command, 'filled')
    target(store, 'new', 500, revision=2)
    plan = uid(); store.plan(plan, (), deadline=deadline())
    with pytest.raises(AllocationError, match='authorization_changed'):
        store.bind_group(plan, GroupBinding(uid(), CODE, 'buy', 500, D('2'), D('0')), deadline=deadline())


def test_per_share_cent_ceiling_covers_many_small_actual_fills(tmp_path):
    store, _ = book(tmp_path)
    _, _, command = prepare(store, 10000, 100, 100, price='2.005', fee='0')
    assert view(store, 'new').reserved_cash_cny == D('201')
    store.apply_fill(fill(command, 1, price='2.005', fee='0'), deadline=deadline())
    assert view(store, 'new').cash_cny == D('999997.99')
    assert view(store, 'new').reserved_cash_cny == D('198.99')


def test_worker_duplicate_prepared_is_serialized_and_once_only(tmp_path):
    store, _ = book(tmp_path)
    target(store, 'old', 10000); target(store, 'new', 100)
    plan = uid(); store.plan(plan, (), deadline=deadline()); group = uid()
    store.bind_group(plan, GroupBinding(group, CODE, 'buy', 100, D('2'), D('5')), deadline=deadline())
    command = PreparedCommand(group, uid(), uid(), SHA, 100, D('2'))
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: bind(store, command, deadline=deadline()).first_binding, range(2)))
    assert sorted(results) == [False, True]
    assert view(store, 'new').reserved_cash_cny == D('205')


def test_original_lease_exception_and_deadline_survive_without_state_reset(tmp_path):
    store, _ = book(tmp_path)
    stop = RuntimeError('original lease cancelled')
    def check(): raise stop
    store.owner_check = check
    with pytest.raises(RuntimeError) as caught: view(store, 'new')
    assert caught.value is stop
    store.owner_check = lambda: None
    with pytest.raises(TimeoutError): store.view('new', deadline=monotonic()-1)
    assert view(store, 'new').cash_cny == D('1000000')


def test_private_state_digest_and_financial_identity_conflicts_reject(tmp_path):
    store, identity = book(tmp_path)
    with pytest.raises(AllocationError, match='book_identity_conflict'):
        view(AccountAllocation(tmp_path, replace(identity, baseline_sha256='c'*64), owner_check=lambda: None), 'new')
    with sqlite3.connect(store.path) as db:
        db.execute("UPDATE asa_book SET value='{}' WHERE id=1")
    with pytest.raises(AllocationError, match='storage_invalid'): view(store, 'new')


def test_native_odd_share_sell_keeps_original_quantity_and_fee(tmp_path):
    store, _ = book(tmp_path, old=10113, sellable=10113)
    target(store, 'old', 10000); target(store, 'new', 0)
    plan = uid(); assert store.plan(plan, (), deadline=deadline()).orders[0].quantity == 113
    group = uid(); store.bind_group(plan, GroupBinding(group, CODE, 'sell', 113, D('2'), D('5')), deadline=deadline())
    command = PreparedCommand(group, uid(), uid(), SHA, 113, D('2'))
    bind(store, command, deadline=deadline())
    actual = replace(fill(command, 113), side='sell', settlement_day=DAY)
    store.apply_fill(actual, deadline=deadline()); close(store, group, command, 'filled')
    assert pos(store, 'old').quantity == 10000 and pos(store, 'old').sellable == 10000
    assert view(store, 'old').cash_cny == D('10221')
    assert view(store, 'new').cash_cny == D('1000000')
    assert store.lookup_prepared(command.wt_order_id, deadline=deadline()) == command
    assert store.lookup_prepared(uid(), deadline=deadline()) is None


def test_confirmed_cancel_allows_original_wt_replacement_without_reassigning_fills(tmp_path):
    store, _ = book(tmp_path)
    plan, group, first = prepare(store, 11000, 1000, 2000, fee='10')
    store.apply_fill(fill(first, 1000), deadline=deadline())
    store.apply_terminal(TerminalFact(uid(), group, first.command_id, 'cancelled', SHA, 1000), deadline=deadline())
    successor = uid()
    store.bind_group(plan, GroupBinding(successor, CODE, 'buy', 1000, D('2'), D('5')), deadline=deadline())
    second = PreparedCommand(successor, uid(), uid(), SHA, 1000, D('2'))
    assert bind(store, second, deadline=deadline()).first_binding
    store.apply_fill(fill(second, 1000), deadline=deadline()); close(store, successor, second, 'filled')
    assert pos(store, 'old').quantity == 11000 and pos(store, 'new').quantity == 1000
    assert view(store, 'old').cash_cny == D('7995') and view(store, 'new').cash_cny == D('997995')
    assert store.lookup_prepared(first.wt_order_id, deadline=deadline()) == first


def test_low_decimal_context_does_not_round_cash_or_fill_gross(tmp_path):
    store, _ = book(tmp_path)
    _, group, command = prepare(store, 10000, 100, 100, price='2.005', fee='0')
    actual = fill(command, 100, price='2.005', fee='0')
    with localcontext() as context:
        context.prec = 4
        store.apply_fill(actual, deadline=deadline())
        assert view(store, 'new').cash_cny == D('999799.50')
    close(store, group, command, 'filled')


def test_old_exact_account_snapshot_does_not_erase_local_fill_cash_adjustment(tmp_path):
    store, _ = book(tmp_path, old=0, sellable=0, old_cash='1000', new_cash='1000', available='1000')
    _, group, command = prepare(store, 500, 0, 500, fee='0')
    store.apply_fill(fill(command, 500, fee='0'), deadline=deadline()); close(store, group, command, 'filled')
    store.observe_account(AccountSnapshot(1, DAY, D('1000'), (OwnedPosition(CODE, 0, 0),), SHA), deadline=deadline())
    target(store, 'new', 500, revision=2)
    plan = uid(); store.plan(plan, (), deadline=deadline())
    with pytest.raises(AllocationError, match='authorization_changed'):
        store.bind_group(plan, GroupBinding(uid(), CODE, 'buy', 500, D('2'), D('0')), deadline=deadline())


def test_preview_skips_only_new_strategy_cap_and_keeps_old_fifo(tmp_path):
    store, _ = book(tmp_path)
    target(store, 'old', 10100); target(store, 'new', 200, cap=D('2'))
    plan = uid(); store.plan(plan, (), deadline=deadline())
    before = view(store, 'old')
    assert store.preview_group(plan, CODE, 'buy', 300, D('2.5'), D('5'), deadline=deadline()).quantity == 100
    assert store.preview_group(plan, CODE, 'buy', 300, D('2'), D('5'), deadline=deadline()).quantity == 300
    assert view(store, 'old') == before
    group = uid(); store.bind_group(plan, GroupBinding(group, CODE, 'buy', 100, D('2.5'), D('5')), deadline=deadline())
    command = PreparedCommand(group, uid(), uid(), SHA, 100, D('2.5'))
    bind(store, command, deadline=deadline()); store.apply_fill(fill(command, 100, price='2.5'), deadline=deadline())
    assert pos(store, 'old').quantity == 10100 and pos(store, 'new').quantity == 0
    assert store.preview_group(plan, CODE, 'buy', 200, D('2.5'), D('5'), deadline=deadline()).quantity == 0


def test_preview_partial_account_cash_is_same_authority_as_binding(tmp_path):
    store, _ = book(tmp_path, available='500')
    target(store, 'old', 10100); target(store, 'new', 300)
    plan = uid(); store.plan(plan, (), deadline=deadline())
    quote = store.preview_group(plan, CODE, 'buy', 400, D('2'), D('5'), deadline=deadline())
    assert quote.quantity == 200
    group = uid(); store.bind_group(plan, GroupBinding(group, CODE, 'buy', quote.quantity, D('2'), D('5')), deadline=deadline())
    assert view(store, 'old').reserved_cash_cny == D('205')
    assert view(store, 'new').reserved_cash_cny == D('205')
    assert store.preview_group(plan, CODE, 'buy', 200, D('2'), D('5'), deadline=deadline()).quantity == 0


def test_preview_price_changes_recheck_budget_before_dispatch(tmp_path):
    store, _ = book(tmp_path, new_cash='205')
    target(store, 'old', 10000); target(store, 'new', 100)
    plan = uid(); store.plan(plan, (), deadline=deadline())
    assert store.preview_group(plan, CODE, 'buy', 100, D('2'), D('5'), deadline=deadline()).quantity == 100
    assert store.preview_group(plan, CODE, 'buy', 100, D('2.005'), D('5'), deadline=deadline()).quantity == 0
    with pytest.raises(AllocationError, match='authorization_changed'):
        store.bind_group(plan, GroupBinding(uid(), CODE, 'buy', 100, D('2.005'), D('5')), deadline=deadline())
    assert view(store, 'new').reserved_cash_cny == 0


def test_preview_sell_preserves_legal_odd_shares(tmp_path):
    store, _ = book(tmp_path, old=10113, sellable=10113)
    target(store, 'old', 10000); target(store, 'new', 0)
    plan = uid(); store.plan(plan, (), deadline=deadline())
    assert store.preview_group(plan, CODE, 'sell', 113, D('2'), D('5'), deadline=deadline()).quantity == 113


def test_missing_original_fill_idempotency_record_cannot_apply_fill_twice(tmp_path):
    store, _ = book(tmp_path)
    _, _, command = prepare(store, 10000, 200, 200, fee='10')
    actual = fill(command, 100)
    store.apply_fill(actual, deadline=deadline())
    with sqlite3.connect(store.path) as db:
        db.execute('DELETE FROM asa_events WHERE identity=?', ('fill:'+actual.fill_id,))
    with pytest.raises(AllocationError, match='storage_invalid'):
        store.apply_fill(actual, deadline=deadline())
    assert pos(store, 'new').quantity == 100


def test_missing_plan_idempotency_record_cannot_rewrite_original_plan(tmp_path):
    store, _ = book(tmp_path)
    target(store, 'old', 10000); target(store, 'new', 100)
    plan = uid(); store.plan(plan, (), deadline=deadline())
    with sqlite3.connect(store.path) as db:
        db.execute('DELETE FROM asa_events WHERE identity=?', ('plan:'+plan,))
    with pytest.raises(AllocationError, match='storage_invalid'):
        store.plan(plan, (), deadline=deadline())


@pytest.mark.parametrize('result', [False, True])
def test_owner_callback_must_follow_original_success_or_raise_contract(tmp_path, result):
    store, _ = book(tmp_path)
    store.owner_check = lambda: result
    with pytest.raises(AllocationError, match='owner_required'):
        view(store, 'new')


def test_future_account_day_cannot_unlock_t_plus_one_shares(tmp_path):
    store, _ = book(tmp_path)
    with pytest.raises(AllocationError, match='account_future_day'):
        store.observe_account(AccountSnapshot(2, '2099-01-01', D('2000000'),
                                             (OwnedPosition(CODE, 10000, 10000),), SHA), deadline=deadline())
    assert pos(store, 'old').sellable == 10000


def sell_setup(store, quantity=100, price='2', fee='5'):
    target(store, 'old', 0); target(store, 'new', 0)
    plan = uid(); store.plan(plan, (), deadline=deadline())
    quote = store.preview_group(plan, CODE, 'sell', quantity, D(price), D(fee), deadline=deadline())
    assert quote.quantity == quantity
    group = uid(); store.bind_group(plan, GroupBinding(group, CODE, 'sell', quantity, D(price), D(fee)), deadline=deadline())
    command = PreparedCommand(group, uid(), uid(), SHA, quantity, D(price))
    bind(store, command, deadline=deadline())
    return plan, group, command


def sell_fill(command, quantity, *, price='2', fee=None):
    return replace(fill(command, quantity, price=price, fee=fee), side='sell', settlement_day=DAY)


@pytest.mark.parametrize('available', ['2000000', '0'])
def test_zero_cash_sell_uses_owned_inventory_not_commission_cash_gate(tmp_path, available):
    store, _ = book(tmp_path, old=100, sellable=100, old_cash='0', available=available)
    _, group, command = sell_setup(store)
    assert view(store, 'old').spendable_cash_cny == 0
    assert view(store, 'old').reserved_cash_cny == D('5')
    store.apply_fill(sell_fill(command, 100, fee='5'), deadline=deadline()); close(store, group, command, 'filled')
    assert pos(store, 'old').quantity == 0
    assert view(store, 'old').cash_cny == D('195')
    assert view(store, 'new').cash_cny == D('1000000')


def test_partial_sell_unknown_fee_then_actual_fee_signed_balance_and_later_proceeds(tmp_path):
    store, identity = book(tmp_path, old=100, sellable=100, old_cash='0')
    plan, group, command = sell_setup(store)
    actual = sell_fill(command, 1)
    store.apply_fill(actual, deadline=deadline())
    before = view(store, 'old')
    assert before.ledger_cash_cny == D('2') and before.cash_cny is None
    assert before.reserved_cash_cny == D('5') and before.spendable_cash_cny == 0
    assert pos(store, 'old').quantity == 99
    with pytest.raises(AllocationError, match='terminal_missing_fills'):
        store.apply_terminal(TerminalFact(uid(), group, command.command_id, 'cancelled', SHA, 100), deadline=deadline())
    close(store, group, command, 'cancelled', filled=1)
    fee = FeeFact(uid(), actual.fill_id, D('5'), SHA)
    store.apply_fee(fee, deadline=deadline()); store.apply_fee(fee, deadline=deadline())
    assert view(store, 'old').cash_cny == D('-3')
    assert view(store, 'old').ledger_cash_cny == D('-3') and view(store, 'old').spendable_cash_cny == 0
    assert view(store, 'new').cash_cny == D('1000000')
    reopened = AccountAllocation(tmp_path, identity, owner_check=lambda: None)
    assert view(reopened, 'old') == view(store, 'old')
    target(store, 'old', 200, revision=2)
    wait = uid(); store.plan(wait, (), deadline=deadline())
    assert store.preview_group(wait, CODE, 'buy', 100, D('2'), D('5'), deadline=deadline()).quantity == 0
    target(store, 'new', 100, revision=2)
    independent = uid(); store.plan(independent, (), deadline=deadline())
    assert store.preview_group(independent, CODE, 'buy', 300, D('2'), D('5'), deadline=deadline()).quantity == 100
    independent_group = uid()
    store.bind_group(independent, GroupBinding(independent_group, CODE, 'buy', 100, D('2'), D('5')), deadline=deadline())
    assert view(store, 'new').cash_cny == D('1000000')
    assert view(store, 'old').cash_cny == D('-3')
    store.record_group_end(independent_group, 0, SHA, deadline=deadline())
    store.apply_terminal(TerminalFact(uid(), independent_group, None, 'not_called', SHA), deadline=deadline())
    target(store, 'old', 0, revision=3); target(store, 'new', 0, revision=3)
    continuation = uid(); store.plan(continuation, (), deadline=deadline())
    second_group = uid(); store.bind_group(continuation, GroupBinding(second_group, CODE, 'sell', 99, D('2'), D('0')), deadline=deadline())
    second = PreparedCommand(second_group, uid(), uid(), SHA, 99, D('2'))
    bind(store, second, deadline=deadline()); store.apply_fill(sell_fill(second, 99, fee='0'), deadline=deadline())
    close(store, second_group, second, 'filled')
    assert view(store, 'old').cash_cny == D('195') and pos(store, 'old').quantity == 0
    assert view(store, 'new').cash_cny == D('1000000')


def test_known_partial_sell_fee_does_not_round_negative_fraction_incorrectly(tmp_path):
    store, _ = book(tmp_path, old=100, sellable=100, old_cash='0')
    _, _, command = sell_setup(store, price='1.99')
    store.apply_fill(sell_fill(command, 1, price='1.99', fee='5'), deadline=deadline())
    assert view(store, 'old').cash_cny == D('-3.01')
    assert view(store, 'old').ledger_cash_cny == D('-3.01')
    assert view(store, 'old').spendable_cash_cny == 0
    assert view(store, 'new').cash_cny == D('1000000')


@pytest.mark.parametrize('already_prepared', [False, True])
def test_late_real_sell_fee_rechecks_buy_dispatch_and_never_loses_actual_trade(tmp_path, already_prepared):
    other = 'SZSE.ETF.159780'
    identity = BookIdentity(SHA, uid(), 'b'*64)
    store = AccountAllocation(tmp_path, identity, owner_check=lambda: None)
    store.initialize((StrategySeed('old', '1.2.2', D('205'), (OwnedPosition(CODE, 100, 100),), 0, (CODE, other)),
                      StrategySeed('new', '0.1.0a2', D('1000000'), (), 1, (CODE, other))), D('0'),
                     AccountSnapshot(1, DAY, D('2000000'), (OwnedPosition(CODE, 100, 100),), SHA), deadline=deadline())
    store.record_targets(TargetIntent(uid(), 'old', 1, (Target(CODE, 0), Target(other, 100)), SHA, STAMP), deadline=deadline())
    plan = uid(); store.plan(plan, (), deadline=deadline())
    buy_group, sell_group = uid(), uid()
    store.bind_group(plan, GroupBinding(buy_group, other, 'buy', 100, D('2'), D('5')), deadline=deadline())
    buy = PreparedCommand(buy_group, uid(), uid(), SHA, 100, D('2'))
    if already_prepared: bind(store, buy, deadline=deadline())
    else:
        store.record_wt_child(WTChild(buy_group, buy.wt_order_id, 100, D('2'), SHA), deadline=deadline())
        store.record_group_end(buy_group, 1, SHA, deadline=deadline())
    store.bind_group(plan, GroupBinding(sell_group, CODE, 'sell', 100, D('2'), D('5')), deadline=deadline())
    sell = PreparedCommand(sell_group, uid(), uid(), SHA, 100, D('2'))
    bind(store, sell, deadline=deadline()); store.apply_fill(sell_fill(sell, 1, fee='5'), deadline=deadline())
    assert view(store, 'old').ledger_cash_cny == D('202')
    if already_prepared:
        store.apply_fill(replace(fill(buy, 100), symbol=other), deadline=deadline())
        assert view(store, 'old').cash_cny == D('-3')
        assert next(p for p in view(store, 'old').positions if p.symbol == other).quantity == 100
    else:
        with pytest.raises(AllocationError, match='strategy_cash_insufficient'):
            bind(store, buy, deadline=deadline())
        assert store.lookup_prepared(buy.wt_order_id, deadline=deadline()) is None
    assert view(store, 'new').cash_cny == D('1000000')


@pytest.mark.parametrize('accepted', [0, 1])
def test_delegate_end_waits_original_wt_child_without_prepared_until_proven_not_called(tmp_path, accepted):
    store, _ = book(tmp_path)
    target(store, 'old', 10000); target(store, 'new', 100)
    plan = uid(); store.plan(plan, (), deadline=deadline()); group = uid()
    store.bind_group(plan, GroupBinding(group, CODE, 'buy', 100, D('2'), D('5')), deadline=deadline())
    child = WTChild(group, uid(), 100, D('2'), SHA)
    store.record_wt_child(child, deadline=deadline()); store.record_group_end(group, accepted, SHA, deadline=deadline())
    assert group in view(store, 'new').pending_groups and view(store, 'new').reserved_cash_cny == D('205')
    with pytest.raises(AllocationError, match='group_unresolved'):
        store.apply_terminal(TerminalFact(uid(), group, None, 'group_closed', SHA), deadline=deadline())
    raw = b'{"dispatch_not_entered":true,"command_id":null}'
    event = store.receive_event('native-not-sent', '11', raw, None, deadline=deadline())
    assert event.source_sha256 is None and not event.applied
    store.record_child_not_called(group, child.wt_order_id, event.payload_sha256, deadline=deadline())
    store.mark_event_applied(event.event_id, deadline=deadline())
    assert not view(store, 'new').pending_groups and view(store, 'new').reserved_cash_cny == 0
    assert store.pending_events(deadline=deadline()) == ()


def test_original_callback_chain_multi_proof_cycle_inbox_replay_and_terminal_reobservation(tmp_path):
    store, identity = book(tmp_path, new_cash='1006')
    assert store.current_targets(deadline=deadline()) == {'old': None, 'new': None}
    target(store, 'old', 10000); target(store, 'new', 200)
    plan = uid(); store.plan(plan, (), deadline=deadline())
    assert store.current_targets(deadline=deadline())['new'].targets == (Target(CODE, 200),)
    assert store.preview_group(plan, CODE, 'buy', 200, D('10.01'), D('5'), deadline=deadline()).quantity == 100
    group = uid(); store.bind_group(plan, GroupBinding(group, CODE, 'buy', 100, D('10.01'), D('5')), deadline=deadline())
    command = PreparedCommand(group, uid(), uid(), SHA, 100, D('10.01'))
    store.record_wt_child(WTChild(group, command.wt_order_id, 100, D('10.01'), SHA), deadline=deadline())
    store.record_group_end(group, 1, SHA, deadline=deadline())
    assert group in view(store, 'new').pending_groups
    store.bind_prepared(command, deadline=deadline())
    first = fill(command, 20, price='10.01', fee=None, fill_id='nqh1-original-trade')
    store.apply_fill(first, deadline=deadline())
    before = store.strategy_observation('new', deadline=deadline())
    assert before.strategy.ledger_cash_cny == D('805.80') and before.strategy.reserved_cash_cny == D('805.80')
    assert before.opening_cycles[CODE].opened_at is None and before.opening_cycles[CODE].status == 'unknown'
    richer = replace(first, source_sha256='b'*64, executed_at='2026-11-06T07:00:01Z')
    store.apply_fill(richer, deadline=deadline()); store.apply_fill(richer, deadline=deadline())
    after = store.strategy_observation('new', deadline=deadline())
    assert after.strategy.ledger_cash_cny == before.strategy.ledger_cash_cny and pos(store, 'new').quantity == 20
    assert after.opening_cycles[CODE].cycle_id == before.opening_cycles[CODE].cycle_id
    assert after.opening_cycles[CODE].opened_at == '2026-11-06T07:00:01+00:00'
    assert after.opening_cycles[CODE].source_sha256 == 'b'*64
    terminal = TerminalFact(uid(), group, command.command_id, 'filled', 'c'*64, 100)
    raw = json.dumps({'command_id':command.command_id,'filled_quantity':100}).encode()
    store.receive_event('source-order-first', '9', raw, 'c'*64, deadline=deadline())
    with pytest.raises(AllocationError, match='terminal_missing_fills'):
        store.apply_terminal(terminal, deadline=deadline())
    store.mark_event_failed('source-order-first', 'terminal_missing_fills', deadline=deadline())
    assert store.pending_events(deadline=deadline())[0].raw_json == raw
    second = replace(fill(command, 80, price='10.01', fee=None), executed_at='2026-11-06T07:00:02Z')
    store.apply_fill(second, deadline=deadline()); store.apply_terminal(terminal, deadline=deadline())
    store.mark_event_applied('source-order-first', deadline=deadline())
    assert not view(store, 'new').pending_groups and pos(store, 'new').quantity == 100
    store.apply_terminal(replace(terminal, event_id=uid(), source_sha256='d'*64), deadline=deadline())
    store.apply_terminal(TerminalFact(uid(), group, command.command_id, 'unknown', 'e'*64), deadline=deadline())
    store.apply_fill(replace(richer, source_sha256='f'*64), deadline=deadline())
    assert pos(store, 'new').quantity == 100
    store.apply_fee(FeeFact(uid(), first.fill_id, D('5'), SHA), deadline=deadline())
    store.apply_fee(FeeFact(uid(), second.fill_id, D('0'), SHA), deadline=deadline())
    assert view(store, 'new').cash_cny == 0 and view(store, 'old').cash_cny == D('10000')
    conflict = replace(richer, quantity=21, amount_cny=D('210.21'))
    for _ in range(2):
        with pytest.raises(AllocationError, match='fill_economic_conflict'):
            store.apply_fill(conflict, deadline=deadline())
    bad_terminal = replace(terminal, event_id=uid(), state='cancelled')
    for _ in range(2):
        with pytest.raises(AllocationError, match='terminal_economic_conflict'):
            store.apply_terminal(bad_terminal, deadline=deadline())
    with sqlite3.connect(store.path) as db:
        assert db.execute('SELECT COUNT(*) FROM asa_conflicts').fetchone()[0] == 2
        state = json.loads(db.execute('SELECT value FROM asa_book WHERE id=1').fetchone()[0])
    assert state['fills'][first.fill_id]['source_sha256'] == SHA
    assert state['fills'][first.fill_id]['source_proofs'] == [SHA,'b'*64,'f'*64]
    reopened = AccountAllocation(tmp_path, identity, owner_check=lambda: None)
    assert reopened.strategy_observation('new', deadline=deadline()) == store.strategy_observation('new', deadline=deadline())


def test_source_pending_sell_freeze_requires_original_order_proof(tmp_path):
    store, _ = book(tmp_path, old=100, sellable=100)
    _, group, command = sell_setup(store)
    snapshot = AccountSnapshot(2, DAY, D('2000000'), (OwnedPosition(CODE,100,0),), 'b'*64)
    with pytest.raises(AllocationError, match='account_sellable_mismatch'):
        store.observe_account(snapshot, deadline=deadline())
    qualified = replace(snapshot, sell_reservations=(SellReservation(command.command_id,100,'c'*64),))
    store.observe_account(qualified, deadline=deadline())
    assert pos(store, 'old').quantity == 100 and pos(store, 'old').sellable == 0
    assert store.strategy_observation('old', deadline=deadline()).account_revision == 2
    with pytest.raises(AllocationError, match='account_freeze_unbound'):
        store.observe_account(replace(qualified, revision=3, sell_reservations=(SellReservation(uid(),100,SHA),)), deadline=deadline())
    actual = sell_fill(command,20,fee='0'); store.apply_fill(actual, deadline=deadline())
    store.observe_account(AccountSnapshot(3,DAY,D('2000040'),(OwnedPosition(CODE,80,0),),'d'*64,
        (SellReservation(command.command_id,80,'e'*64),)),deadline=deadline())
    assert pos(store, 'old').quantity == 80 and pos(store,'old').sellable == 0
    close(store,group,command,'cancelled',filled=20)
    store.observe_account(AccountSnapshot(4,DAY,D('2000040'),(OwnedPosition(CODE,80,80),),'f'*64),deadline=deadline())
    assert pos(store,'old').sellable == 80


def two_symbol_book(root, *, new_cash='1000000', sellable=100):
    other='SZSE.ETF.159780'; identity=BookIdentity(SHA,uid(),'b'*64)
    store=AccountAllocation(root,identity,owner_check=lambda:None)
    store.initialize((StrategySeed('old','1',D('10000'),(OwnedPosition(CODE,100,sellable),),0,(CODE,other)),
        StrategySeed('new','2',D(new_cash),(),1,(CODE,other))),D('0'),
        AccountSnapshot(1,DAY,D('2000000'),(OwnedPosition(CODE,100,sellable),),SHA),deadline=deadline())
    return store,other


def complete_target(store,sid,other,first,second,revision=1,cap=None):
    store.record_targets(TargetIntent(uid(),sid,revision,(Target(CODE,first,cap),Target(other,second)),SHA,STAMP),deadline=deadline())


def test_pending_symbol_keeps_original_responsibility_without_blocking_other_symbol(tmp_path):
    store,other=two_symbol_book(tmp_path)
    complete_target(store,'old',other,100,0);complete_target(store,'new',other,100,0)
    first=uid();store.plan(first,(),deadline=deadline());group=uid()
    store.bind_group(first,GroupBinding(group,CODE,'buy',100,D('2'),D('5')),deadline=deadline())
    command=PreparedCommand(group,uid(),uid(),SHA,100,D('2'));bind(store,command,deadline=deadline())
    complete_target(store,'new',other,100,100,revision=2)
    later=uid();plan=store.plan(later,(),deadline=deadline())
    assert plan.blocked_reasons=={CODE:'pending_group'} and plan.orders[0].symbol==other
    assert store.preview_group(later,other,'buy',100,D('2'),D('5'),deadline=deadline()).quantity==100
    store.apply_fill(fill(command,20,fee='0'),deadline=deadline())
    assert pos(store,'new').quantity==20 and group in view(store,'new').pending_groups


@pytest.mark.parametrize('mode,reason',[('missing','common_price_unqualified'),('cash','strategy_cash_insufficient'),
    ('frozen','internal_sellable_insufficient'),('cap','internal_price_cap'),('future','clock_invalid')])
def test_unqualified_opposing_symbol_waits_while_independent_symbol_continues(tmp_path,mode,reason):
    store,other=two_symbol_book(tmp_path,new_cash='50' if mode=='cash' else '1000000',sellable=0 if mode=='frozen' else 100)
    complete_target(store,'old',other,0,100);complete_target(store,'new',other,100,0,cap=D('1') if mode=='cap' else None)
    prices=() if mode=='missing' else (CommonPrice(CODE,D('2'),'2099-01-01T00:00:00Z'if mode=='future'else STAMP,SHA,('old','new'),True),)
    plan_id=uid();result=store.plan(plan_id,prices,deadline=deadline())
    assert result.blocked_reasons=={CODE:reason} and result.internal_transfers==()
    assert result.orders[0].symbol==other and result.orders[0].quantity==100
    assert pos(store,'old').quantity==100 and pos(store,'new').quantity==0
    assert store.preview_group(plan_id,other,'buy',100,D('2'),D('5'),deadline=deadline()).quantity==100


def test_explicit_seed_cycle_internal_transfer_and_real_flat_clear(tmp_path):
    seed=OpeningCycle(CODE,'legacy-original-cycle','2026-10-30T07:00:00Z','b'*64,'initial_inventory')
    store,_=book(tmp_path,old=100,sellable=100,old_cash='0',old_cycles=(seed,))
    assert store.strategy_observation('old',deadline=deadline()).opening_cycles[CODE]==seed
    assert store.strategy_observation('new',deadline=deadline()).opening_cycles[CODE] is None
    target(store,'old',0);target(store,'new',100)
    plan=uid();store.plan(plan,(CommonPrice(CODE,D('2'),STAMP,SHA,('old','new'),True),),deadline=deadline())
    assert store.strategy_observation('old',deadline=deadline()).opening_cycles[CODE] is None
    cycle=store.strategy_observation('new',deadline=deadline()).opening_cycles[CODE]
    assert cycle.cycle_id!='legacy-original-cycle' and cycle.opened_at=='2026-11-06T07:00:00+00:00'
    target(store,'new',0,revision=2);plan2=uid();store.plan(plan2,(),deadline=deadline());group=uid()
    store.bind_group(plan2,GroupBinding(group,CODE,'sell',100,D('2'),D('5')),deadline=deadline())
    command=PreparedCommand(group,uid(),uid(),SHA,100,D('2'));bind(store,command,deadline=deadline())
    store.apply_fill(sell_fill(command,100,fee='5'),deadline=deadline())
    assert store.strategy_observation('new',deadline=deadline()).opening_cycles[CODE] is None


@pytest.mark.parametrize('raw',[b'{"a":1,"a":2}',b'{"a":NaN}',b'{"a":1e309}',b'\xff'])
def test_event_inbox_preserves_strict_original_json_boundary(tmp_path,raw):
    store,_=book(tmp_path)
    with pytest.raises(AllocationError,match='event_json_invalid'):
        store.receive_event('bad-source','8',raw,SHA,deadline=deadline())
    assert store.pending_events(deadline=deadline())==()
