# -*- coding: utf-8 -*-
"""QST-R9 纯替身回归；所有 SDK 调用均为本文件明确构造的内存函数。

测试不启动子进程、终端、网络或真实 SDK。线程用例只核原线程入口拒绝，
独立调用记录区分未进入、返回、实际已进入后异常和迟到。
"""
from decimal import getcontext, setcontext, Inexact, Rounded
import hashlib
from pathlib import Path
import sys
import threading
import unittest
from uuid import UUID

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'connectors/qmt_shm/agent'))
from guanheng_qmt_shm_agent.protocol import canonical
from guanheng_qmt_shm_agent.trading_kernel import (
    TradingKernel, TradingKernelError, snapshot_order, snapshot_deal, snapshot_error)


RESULT_KEYS = {'schema_version', 'command_id', 'command_sha256', 'operation',
               'stage', 'sdk_entered', 'signal_sent', 'error_code'}


def binding(**changes):
    value = {'schema_version': 'qmt.trade-binding.v1', 'binding_id': 'synthetic-binding',
        'account_id': 'SYNTHETIC-ONLY', 'account_type': 'stock',
        'account_environment': 'live', 'strategy_name': 'synthetic-strategy',
        'max_commands': 8, 'symbol_rules': {'000001.SZ': {
            'price_tick': '0.01', 'buy_min': 100, 'buy_step': 100,
            'sell_min': 1, 'sell_step': 1}}}
    value.update(changes)
    return value


def command(number=1, **changes):
    value = {'schema_version': 'qmt.trade-command.v1', 'command_id': str(UUID(int=number)),
        'operation': 'order.insert', 'binding_id': 'synthetic-binding',
        'account_id': 'SYNTHETIC-ONLY', 'account_type': 'stock',
        'entrust_id': 'GH-1-1', 'user_tag': 'otp.synthetic.1',
        'symbol': '000001.SZ', 'side': 'buy', 'order_type': 'limit',
        'limit_price': '7.15', 'quantity': 100, 'sdk_user_order_id': 'synthetic-token'}
    value.update(changes)
    return value


def cancel_command(number=2, **changes):
    value = command(number)
    for key in ('symbol', 'side', 'order_type', 'limit_price', 'quantity', 'sdk_user_order_id'):
        del value[key]
    value.update(operation='order.cancel', original_command_id=str(UUID(int=1)),
                 broker_order_id='synthetic-broker-id')
    value.update(changes)
    return value


class Calls(object):
    def __init__(self):
        self.calls = []
        self.context = object()
        self.now = 10.0
        self.cancel_value = True
        self.insert_value = None
        self.after_insert = None
        self.after_cancel = None

    def clock(self):
        return self.now

    def insert(self, *args):
        self.calls.append(('insert', args, threading.get_ident()))
        if self.after_insert:
            self.after_insert()
        return self.insert_value

    def cancel(self, *args):
        self.calls.append(('cancel', args, threading.get_ident()))
        if self.after_cancel:
            self.after_cancel()
        return self.cancel_value

    def kernel(self, **changes):
        options = {'binding': binding(), 'passorder': self.insert, 'cancel': self.cancel,
                   'writes_enabled': True, 'clock': self.clock}
        options.update(changes)
        return TradingKernel(self.context, **options)


def run(kernel, value=None, **changes):
    options = {'deadline': 20.0, 'phase': 'live_drain'}
    options.update(changes)
    return kernel.execute(command() if value is None else value, **options)


class TradingKernelTests(unittest.TestCase):
    def assert_code(self, code, function, *args, **kwargs):
        with self.assertRaises(TradingKernelError) as caught:
            function(*args, **kwargs)
        self.assertEqual(str(caught.exception), code)

    def test_exact_insert_and_original_identity(self):
        calls = Calls()
        kernel = calls.kernel()
        value = command()
        result = run(kernel, value)
        self.assertEqual(set(result), RESULT_KEYS)
        self.assertEqual(result['stage'], 'sdk_returned')
        self.assertTrue(result['sdk_entered'])
        self.assertIsNone(result['signal_sent'])
        self.assertIsNone(result['error_code'])
        self.assertEqual(result['command_sha256'], hashlib.sha256(canonical(value)).hexdigest())
        self.assertEqual(calls.calls, [('insert', (23, 1101, 'SYNTHETIC-ONLY', '000001.SZ',
            11, 7.15, 100, 'synthetic-strategy', 2, 'synthetic-token', calls.context),
            threading.get_ident())])
        self.assertEqual(value['entrust_id'], 'GH-1-1')
        self.assertEqual(value['user_tag'], 'otp.synthetic.1')
        run(kernel, command(2, side='sell', quantity=3))
        self.assertEqual(calls.calls[1][1][0], 24)
        self.assertEqual(calls.calls[1][1][6], 3)

    def test_default_off_and_no_implicit_account(self):
        calls = Calls()
        kernel = TradingKernel(calls.context, binding=binding(), passorder=calls.insert,
                               cancel=calls.cancel, clock=calls.clock)
        result = run(kernel)
        self.assertEqual((result['stage'], result['sdk_entered'], result['error_code']),
                         ('definitely_not_called', False, 'writes_disabled'))
        self.assertEqual(calls.calls, [])
        self.assert_code('invalid_binding', calls.kernel, binding=binding(account_id=''))
        self.assert_code('invalid_command', run, calls.kernel(), command(account_id=''))

    def test_cancel_preserves_signal_and_official_account_type(self):
        for signal in (True, False):
            calls = Calls()
            calls.cancel_value = signal
            result = run(calls.kernel(), cancel_command())
            self.assertEqual(result['stage'], 'sdk_returned')
            self.assertIs(result['signal_sent'], signal)
            self.assertEqual(calls.calls[0][1], ('synthetic-broker-id', 'SYNTHETIC-ONLY',
                                               'STOCK', calls.context))
            self.assertNotIn('cancelled', result)

    def test_exact_shapes_uuid_and_types(self):
        bad = [command(extra=True), command(quantity=True), command(quantity=100.0),
            command(quantity=0), command(quantity=2 ** 53), command(order_type='market'),
            command(command_id='not-uuid'), command(command_id=str(UUID(int=255)).upper()),
            command(limit_price='NaN'), command(limit_price='Infinity'),
            command(limit_price='0'), command(limit_price='-1'), command(limit_price='1e999'),
            command(limit_price=' 1.0'), command(limit_price=7.15),
            command(symbol='０００００１.SZ'), command(side='BUY'),
            command(sdk_user_order_id='bad token'), command(sdk_user_order_id='中'),
            command(user_tag='bad\x00tag'), command(entrust_id='x' * 64),
            command(account_type='STOCK'), cancel_command(original_command_id='latest'),
            cancel_command(broker_order_id=''), cancel_command(broker_order_id='x' * 129)]
        missing = command()
        del missing['entrust_id']
        bad.append(missing)
        calls = Calls()
        kernel = calls.kernel()
        for value in bad:
            self.assert_code('invalid_command', run, kernel, value)
        self.assertEqual(calls.calls, [])

    def test_binding_deep_copy_and_resource_limits(self):
        original = binding()
        calls = Calls()
        kernel = calls.kernel(binding=original)
        original['account_id'] = 'CHANGED'
        original['strategy_name'] = 'changed'
        original['symbol_rules']['000001.SZ']['price_tick'] = '5'
        original['symbol_rules'].clear()
        self.assertEqual(run(kernel)['stage'], 'sdk_returned')
        self.assertEqual(calls.calls[0][1][2], 'SYNTHETIC-ONLY')
        self.assertEqual(calls.calls[0][1][7], 'synthetic-strategy')
        for item in (binding(account_environment='simulation'), binding(account_type='STOCK'),
                     binding(max_commands=True), binding(max_commands=0),
                     binding(max_commands=4097), binding(symbol_rules={}),
                     binding(account_id='账' * 22)):
            self.assert_code('invalid_binding', calls.kernel, binding=item)
        changed = binding()
        changed['symbol_rules']['000001.SZ']['buy_step'] = False
        self.assert_code('invalid_binding', calls.kernel, binding=changed)
        self.assert_code('invalid_configuration', calls.kernel, writes_enabled=1)
        self.assert_code('invalid_configuration', calls.kernel, passorder=None)

    def test_utf8_63_byte_account_and_wt_capacity(self):
        calls = Calls()
        kernel = calls.kernel(binding=binding(account_id='账' * 21))
        result = run(kernel, command(account_id='账' * 21, entrust_id='账' * 21,
                                     user_tag='账' * 21))
        self.assertEqual(result['stage'], 'sdk_returned')
        self.assertEqual(calls.calls[0][1][2], '账' * 21)
        self.assert_code('invalid_command', run, kernel, command(entrust_id='账' * 22))

    def test_contract_price_grid_independent_of_decimal_context(self):
        saved = getcontext().copy()
        try:
            getcontext().prec = 1
            getcontext().traps[Inexact] = True
            getcontext().traps[Rounded] = True
            facts = binding()
            facts['symbol_rules']['000001.SZ'].update(price_tick='0.0001', buy_min=3, buy_step=2)
            calls = Calls()
            kernel = calls.kernel(binding=facts)
            result = run(kernel, command(quantity=5, limit_price='123.4567'))
            self.assertEqual(result['stage'], 'sdk_returned')
            self.assertEqual(run(kernel, command(2, quantity=4))['error_code'], 'quantity_off_grid')
            self.assertEqual(run(kernel, command(3, quantity=1))['error_code'], 'quantity_off_grid')
            self.assertEqual(run(kernel, command(4, quantity=3, limit_price='1.00001'))['error_code'],
                             'price_off_grid')
            self.assertEqual(len(calls.calls), 1)
        finally:
            setcontext(saved)

    def test_double_underflow_overflow_are_not_called(self):
        for price, tick in (('0.' + '0' * 20 + '1e-308', '0.' + '0' * 20 + '1e-308'),
                            ('99999999999999999999e308', '1')):
            calls = Calls()
            facts = binding()
            facts['symbol_rules']['000001.SZ']['price_tick'] = tick
            kernel = calls.kernel(binding=facts)
            # 超长字面值在形状校验直接拒绝；有限协议内的溢出在 SDK 前拒绝。
            if len(price) > 64:
                self.assert_code('invalid_command', run, kernel, command(limit_price=price))
            else:
                self.assertEqual(run(kernel, command(limit_price=price))['stage'],
                                 'definitely_not_called')
            self.assertEqual(calls.calls, [])

    def test_binding_symbol_and_quantity_rejections(self):
        calls = Calls()
        kernel = calls.kernel()
        for number, changes, code in ((1, {'account_id': 'OTHER'}, 'binding_mismatch'),
            (2, {'binding_id': 'OTHER'}, 'binding_mismatch'),
            (3, {'symbol': '600000.SH'}, 'symbol_not_allowed'),
            (4, {'quantity': 101}, 'quantity_off_grid'),
            (5, {'limit_price': '7.151'}, 'price_off_grid')):
            self.assertEqual(run(kernel, command(number, **changes))['error_code'], code)
        self.assertEqual(calls.calls, [])

    def test_duplicate_conflict_result_copy_close_capacity_and_expiry(self):
        calls = Calls()
        kernel = calls.kernel(binding=binding(max_commands=1))
        value = command()
        first = run(kernel, value)
        result_copy = dict(first)
        first['stage'] = 'FORGED'
        self.assert_code('command_conflict', run, kernel, command(quantity=200))
        self.assertEqual(run(kernel, command(2))['error_code'], 'capacity_exhausted')
        kernel.request_close()
        calls.now = 99
        self.assertEqual(run(kernel, value, deadline=1), result_copy)
        self.assertEqual(len(calls.calls), 1)

    def test_deadline_is_not_refreshed_after_pre_call_rejection(self):
        calls = Calls()
        kernel = calls.kernel()
        first = run(kernel, deadline=10)
        self.assertEqual(first['error_code'], 'deadline_expired')
        self.assertEqual(run(kernel, deadline=200), first)
        self.assertEqual(calls.calls, [])
        for deadline in (True, None, float('nan'), float('inf'), 10 ** 1000):
            self.assert_code('invalid_deadline', run, kernel, deadline=deadline)

    def test_invalid_phase_original_thread_and_reentrancy(self):
        calls = Calls()
        kernel = calls.kernel()
        for phase in ('init', 'handlebar', 'callback', 'history', None):
            self.assert_code('invalid_phase', run, kernel, phase=phase)
        observed = []
        def other_thread():
            try:
                run(kernel)
            except TradingKernelError as error:
                observed.append(str(error))
        thread = threading.Thread(target=other_thread)
        thread.start()
        thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(observed, ['wrong_thread'])
        def callback():
            self.assert_code('reentrant_call', run, kernel)
            self.assert_code('reentrant_call', run, kernel, command(2))
        calls.after_insert = callback
        self.assertEqual(run(kernel)['stage'], 'sdk_returned')
        self.assertEqual(len(calls.calls), 1)

    def test_insert_normal_return_has_no_broker_semantics(self):
        # 当前终端原生签名返回int；None、整数及其他返回对象均不提供柜台身份。
        for returned in (None, 0, 1, -1, True, 'not-a-broker-id', object()):
            with self.subTest(return_type=type(returned).__name__):
                calls = Calls()
                calls.insert_value = returned
                kernel = calls.kernel()
                result = run(kernel)
                self.assertEqual(result['stage'], 'sdk_returned')
                self.assertTrue(result['sdk_entered'])
                self.assertIsNone(result['signal_sent'])
                self.assertIsNone(result['error_code'])
                self.assertEqual(set(result), RESULT_KEYS)
                self.assertEqual(run(kernel), result)
                self.assertEqual(len(calls.calls), 1)

    def test_sdk_exception_and_late_return_close_new_writes(self):
        def raises():
            raise RuntimeError('secret should never appear')
        for scenario in ('exception', 'late'):
            calls = Calls()
            if scenario == 'exception':
                calls.after_insert = raises
            else:
                calls.after_insert = lambda: setattr(calls, 'now', 20.0)
            kernel = calls.kernel()
            first = run(kernel)
            self.assertEqual(first['stage'], 'unknown')
            self.assertTrue(first['sdk_entered'])
            self.assertNotIn('secret', repr(first))
            self.assertEqual(run(kernel), first)
            self.assertEqual(run(kernel, command(2), deadline=200)['error_code'], 'admission_closed')
            self.assertEqual(len(calls.calls), 1)
        calls = Calls()
        calls.cancel_value = 1
        result = run(calls.kernel(), cancel_command())
        self.assertEqual(result['error_code'], 'invalid_sdk_return')
        self.assertEqual(result['stage'], 'unknown')
        self.assertIsNone(result['signal_sent'])

    def test_close_pre_call_and_clock_stop_do_not_cancel(self):
        calls = Calls()
        kernel = calls.kernel()
        kernel.request_close()
        self.assertEqual(run(kernel)['error_code'], 'admission_closed')
        self.assertEqual(calls.calls, [])
        holder = []
        def stopping_clock():
            holder[0].request_close()
            return 10.0
        kernel = calls.kernel(clock=stopping_clock)
        holder.append(kernel)
        self.assertEqual(run(kernel)['error_code'], 'admission_closed')
        self.assertEqual(calls.calls, [])

    def test_unknown_is_insert_fence_cancel_keeps_original_four_arguments(self):
        calls = Calls()
        def entered_then_raises():
            raise RuntimeError('synthetic-sdk-exception')
        calls.after_insert = entered_then_raises
        kernel = calls.kernel()
        original = run(kernel)
        self.assertEqual(original['stage'], 'unknown')
        self.assertEqual(run(kernel, cancel_command())['stage'], 'sdk_returned')
        self.assertEqual(calls.calls[-1][1],
                         ('synthetic-broker-id', 'SYNTHETIC-ONLY', 'STOCK', calls.context))
        self.assertEqual(run(kernel), original)
        self.assertEqual(run(kernel, command(3))['error_code'], 'admission_closed')
        self.assertEqual(len(calls.calls), 2)
        kernel.request_fault('handoff_failed')
        self.assertEqual(run(kernel, cancel_command(4))['error_code'], 'admission_closed')
        self.assertEqual(run(kernel, cancel_command())['stage'], 'sdk_returned')
        self.assertEqual(len(calls.calls), 2)

    def test_post_call_clock_failure_is_hard_even_after_unknown(self):
        calls = Calls()
        samples = [10, float('nan')]
        kernel = calls.kernel(clock=lambda: samples.pop(0) if samples else 10)
        self.assertEqual(run(kernel)['stage'], 'unknown')
        self.assertEqual(run(kernel, cancel_command())['error_code'], 'admission_closed')
        self.assertEqual(len(calls.calls), 1)

    def test_clock_failures_keep_before_and_after_sdk_distinct(self):
        calls = Calls()
        def bad_clock():
            raise RuntimeError('clock internal text')
        self.assertEqual(run(calls.kernel(clock=bad_clock))['error_code'], 'clock_failed')
        self.assertEqual(calls.calls, [])
        state = [0]
        def later_bad_clock():
            state[0] += 1
            if state[0] == 1:
                return 10
            raise RuntimeError('secret clock detail')
        kernel = calls.kernel(clock=later_bad_clock)
        result = run(kernel)
        self.assertEqual(result['stage'], 'unknown')
        self.assertTrue(result['sdk_entered'])
        self.assertEqual(len(calls.calls), 1)
        self.assertNotIn('secret', repr(result))


    def test_command_copy_and_concurrent_close_during_sdk(self):
        calls = Calls()
        value = command()
        expected_digest = hashlib.sha256(canonical(value)).hexdigest()
        kernel = calls.kernel()
        observed = []
        def while_sdk():
            # SDK 替身改变调用者原 dict；已冻结身份和已准备参数保持原值。
            value['account_id'] = 'MUTATED'
            def concurrent():
                try:
                    run(kernel, command(2))
                except TradingKernelError as error:
                    observed.append(str(error))
                kernel.request_close()
            worker = threading.Thread(target=concurrent)
            worker.start()
            worker.join(2)
            self.assertFalse(worker.is_alive())
        calls.after_insert = while_sdk
        first = run(kernel, value)
        self.assertEqual(first['stage'], 'sdk_returned')
        self.assertEqual(first['command_sha256'], expected_digest)
        self.assertEqual(observed, ['wrong_thread'])
        self.assertEqual(run(kernel, command(2))['error_code'], 'admission_closed')
        self.assertEqual(len(calls.calls), 1)
        self.assertEqual(calls.calls[0][1][2], 'SYNTHETIC-ONLY')

    def test_clock_reentry_and_scalar_failures_before_sdk(self):
        calls = Calls()
        owner = []
        def reentrant_clock():
            self.assert_code('reentrant_call', run, owner[0])
            return 10
        kernel = calls.kernel(clock=reentrant_clock)
        owner.append(kernel)
        self.assertEqual(run(kernel)['stage'], 'sdk_returned')
        self.assertEqual(len(calls.calls), 1)
        for value in (True, None, float('nan'), float('inf'), 10 ** 1000):
            fake = Calls()
            result = run(fake.kernel(clock=lambda: value))
            self.assertEqual(result['error_code'], 'clock_failed')
            self.assertFalse(result['sdk_entered'])
            self.assertEqual(fake.calls, [])


class SnapshotTests(unittest.TestCase):
    def test_missing_null_zero_raw_text_and_whitelist(self):
        raw = {'m_strAccountID': 'SYNTHETIC-ONLY', 'm_strRemark': None,
               'm_nVolumeTraded': 0, 'm_strInsertTime': '09:30:00', 'unknown': 'omit'}
        result = snapshot_order(raw)
        self.assertEqual(result, {key: raw[key] for key in raw if key != 'unknown'})
        self.assertNotIn('m_strOrderSysID', result)
        self.assertIsNone(result['m_strRemark'])
        self.assertEqual(snapshot_deal({'m_strTradeID': 'raw-id', 'm_nVolume': 0}),
                         {'m_strTradeID': 'raw-id', 'm_nVolume': 0})

    def test_real_getter_once_and_declared_attribute_error(self):
        class Source(object):
            def __init__(self):
                self.reads = 0
            @property
            def m_strRemark(self):
                self.reads += 1
                return 'original _ &&& _ token'
        source = Source()
        self.assertEqual(snapshot_order(source), {'m_strRemark': 'original _ &&& _ token'})
        self.assertEqual(source.reads, 1)
        class Broken(object):
            @property
            def m_strRemark(self):
                raise AttributeError('private SDK detail')
        with self.assertRaisesRegex(TradingKernelError, '^source_shape_invalid$'):
            snapshot_order(Broken())

    def test_error_has_no_guessed_order_identity(self):
        raw = {'opType': 23, 'accountID': 'SYNTHETIC-ONLY',
               'strategyName': 'strategy _ &&& _ token', 'userOrderId': 'not-documented'}
        result = snapshot_error(raw, '原错误\n详情')
        self.assertEqual(result['order_args'], {'opType': 23, 'accountID': 'SYNTHETIC-ONLY',
                         'strategyName': 'strategy _ &&& _ token'})
        self.assertEqual(result['err_msg'], '原错误\n详情')
        self.assertNotIn('command_id', result)
        self.assertEqual(snapshot_error({}, None), {'order_args': {}, 'err_msg': None})

    def test_source_value_bounds_and_no_implicit_conversion(self):
        for value in (float('nan'), float('inf'), 2 ** 53, object(), [], 'x' * 4097):
            with self.assertRaisesRegex(TradingKernelError, '^source_value_invalid$'):
                snapshot_deal({'m_strRemark': value})
        with self.assertRaisesRegex(TradingKernelError, '^source_value_invalid$'):
            snapshot_error({}, object())
        class Exploding(object):
            @property
            def m_strTradeID(self):
                raise RuntimeError('must not leak')
        with self.assertRaisesRegex(TradingKernelError, '^source_shape_invalid$'):
            snapshot_deal(Exploding())


if __name__ == '__main__':
    unittest.main()
