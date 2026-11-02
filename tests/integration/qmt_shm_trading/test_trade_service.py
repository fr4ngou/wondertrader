# -*- coding: utf-8 -*-
"""R16 服务完整替身链；真实交易SDK、文件、网络和进程均不参与。"""
import base64
import hashlib
import threading
import unittest
from unittest.mock import patch

from guanheng_qmt_shm_agent import builtin_shm
from guanheng_qmt_shm_agent.protocol import canonical, decode
from guanheng_qmt_shm_agent.trade_service import SourceTradingService, SourceTradingError
from guanheng_qmt_shm_agent.trading_configuration import validate_trade_configuration
from test_trade_configuration import settings


def entered_then_raises(*args):
    # 明确SDK进入后异常，保持unknown/hard-fault回归的原触发语义。
    raise RuntimeError('synthetic SDK entered before exception')


class Context(object):
    def __init__(self, mode=False):
        self.mode, self.reads = mode, 0

    @property
    def do_back_test(self):
        self.reads += 1
        return self.mode


class Clocks(object):
    def __init__(self):
        self.business, self.local, self.reads = 10.0, 100.0, []

    def clock(self):
        self.reads.append('business')
        return self.business

    def mono(self):
        self.reads.append('local')
        return self.local


def admitted(enabled=True, count=16, pending=1):
    value = settings()
    value['writes_enabled'] = enabled
    value['max_pending'] = pending
    value['trade_binding']['max_commands'] = count
    value['trade_profile']['limits'].update(max_commands=count,
        max_event_bytes=4096, max_total_event_bytes=32768, max_event_page_bytes=8192)
    value['trade_profile']['binding_sha256'] = hashlib.sha256(canonical(value['trade_binding'])).hexdigest()
    value['transport'] = {'kind': 'builtin-shm', 'schema_version': 'qmt.builtin-shm.v1',
        'name': 'qmt-broker-service-test', 'max_mapped_bytes': 1048576,
        'poll_seconds': .005, 'windows_session_id': 0}
    with patch.object(builtin_shm.sys, 'platform', 'win32'), \
            patch.object(builtin_shm.sys, 'version', '3.6.8 AMD64'), \
            patch.object(builtin_shm.struct, 'calcsize', return_value=8):
        return validate_trade_configuration(value)


def command(number=1):
    return {'schema_version': 'qmt.trade-command.v1',
        'command_id': '00000000-0000-4000-8000-%012d' % number,
        'operation': 'order.insert', 'binding_id': 'synthetic-only',
        'account_id': 'SYNTHETIC', 'account_type': 'stock', 'entrust_id': 'native.%d' % number,
        'user_tag': 'synthetic.%d' % number, 'symbol': '000001.SZ', 'side': 'buy',
        'order_type': 'limit', 'limit_price': '10.01', 'quantity': 100,
        'sdk_user_order_id': 'synthetic.%d' % number}


def payload(original=None, deadline_ms=15000):
    return {'kind': 'trade', 'body': base64.b64encode(canonical(
        command() if original is None else original)).decode('ascii'),
        'clock_schema': 'qmt.win-uptime-ms.v1', 'deadline_ms': deadline_ms}


def cancel_command(number=2):
    value = command(number)
    for key in ('symbol', 'side', 'order_type', 'limit_price', 'quantity', 'sdk_user_order_id'):
        del value[key]
    value.update(operation='order.cancel', original_command_id=command()['command_id'],
                 broker_order_id='synthetic-broker')
    return value


def service(context=None, enabled=True, clock=None, **kwargs):
    context = Context() if context is None else context
    clock = Clocks() if clock is None else clock
    calls = []
    def buy(*args):
        calls.append(('insert', args, threading.get_ident()))
    def cancel(*args):
        calls.append(('cancel', args, threading.get_ident()))
        return True
    value = SourceTradingService(context, admitted(enabled=enabled,
        count=kwargs.pop('count', 16), pending=kwargs.pop('pending', 1)),
        passorder=kwargs.pop('passorder', buy), cancel=kwargs.pop('cancel', cancel),
        clock=clock.clock, monotonic=clock.mono, session_id='synthetic-session', **kwargs)
    return value, context, clock, calls


def other_thread(function):
    values, errors = [], []
    def run():
        try:
            values.append(function())
        except BaseException as error:
            errors.append(error)
    worker = threading.Thread(target=run, daemon=True)
    worker.start(); worker.join(2)
    if worker.is_alive():
        raise AssertionError('bounded fixture thread did not return')
    return values, errors


def page_request(value, after=0):
    return {'session_id': value.session_id, 'after_seq': after, 'limit': 8, 'max_bytes': 8192}


class SourceTradingServiceTests(unittest.TestCase):
    def test_io_enqueue_owner_tick_sync_callbacks_page_ack_close(self):
        calls = []
        context, clock = Context(), Clocks()
        def buy(*args):
            calls.append((args, threading.get_ident()))
            self.assertTrue(value.status()['executing'])
            value.on_order(context, {'m_strAccountID': 'SYNTHETIC', 'm_strRemark': args[9]})
            value.on_deal(context, {'m_strAccountID': 'SYNTHETIC', 'm_strTradeID': 'deal-1'})
            value.on_error(context, {'accountID': 'SYNTHETIC'}, 'unparsed original')
        value, unused, unused_clock, unused_calls = service(context=context, clock=clock, passorder=buy)
        queued, errors = other_thread(lambda: value.enqueue(payload(), 105))
        self.assertEqual(errors, [])
        future = queued[0]
        self.assertIsNone(future.poll())
        self.assertEqual(calls, [])
        self.assertTrue(value.tick())
        self.assertFalse(value.tick())
        result = decode(future.poll())
        self.assertEqual(result['stage'], 'sdk_returned')
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1], threading.get_ident())
        self.assertEqual(calls[0][0], (23, 1101, 'SYNTHETIC', '000001.SZ', 11,
            10.01, 100, 'synthetic', 2, 'synthetic.1', context))
        value.request_close()
        self.assertFalse(value.local_drained)
        events = value.events(page_request(value))
        self.assertEqual([item['kind'] for item in events['events']], ['order', 'deal', 'error'])
        self.assertEqual(value.acknowledge({'session_id': value.session_id, 'through_seq': 3}),
                         {'session_id': value.session_id, 'through_seq': 3})
        self.assertTrue(value.local_drained)
        self.assertEqual(context.reads, 1)

    def test_write_switch_and_terminal_mode_attribute_once(self):
        for mode, requested, expected in ((False, True, True), (False, False, False),
                (True, True, False), (0, True, False), (None, True, False)):
            value, context, clock, calls = service(context=Context(mode), enabled=requested)
            state = value.status()
            self.assertEqual(state['write_admission'], expected)
            self.assertEqual(state['writes_enabled'], requested)
            self.assertIs(state['source_mode_live'], mode is False)
            self.assertEqual(set(state), {'schema_version', 'session_id', 'binding_id',
                'binding_sha256', 'writes_enabled', 'source_mode_live', 'write_admission',
                'closing', 'gap', 'queued', 'executing', 'commands', 'completed', 'events',
                'unknown_fenced', 'hard_fault', 'cancel_admission'})
            self.assertEqual(state['schema_version'], 'qmt.trade-source-status.v2')
            self.assertEqual(state['cancel_admission'], expected)
            self.assertEqual(context.reads, 1)
            future = value.enqueue(payload(), 105)
            value.tick()
            self.assertEqual(len(calls), int(expected))
            self.assertEqual(decode(future.poll())['error_code'], None if expected else 'writes_disabled')
            self.assertEqual(context.reads, 1)
        value = SourceTradingService(Context(), admitted(enabled=False), passorder=lambda *args: None,
            cancel=lambda *args: True, clock=lambda: 10, monotonic=lambda: 100,
            session_id='default-off')
        self.assertFalse(value.status()['write_admission'])
        class Broken(object):
            @property
            def do_back_test(self):
                raise RuntimeError('private source detail')
        value, unused, unused_clock, calls = service(context=Broken())
        future = value.enqueue(payload(), 105); value.tick()
        self.assertEqual(decode(future.poll())['error_code'], 'writes_disabled')
        self.assertEqual(calls, [])

    def test_duplicate_original_body_keeps_completion_and_deadlines(self):
        value, context, clock, calls = service()
        first = value.enqueue(payload(), 102)
        self.assertEqual(clock.reads, ['business', 'local'])
        clock.business, clock.local = 11, 101
        same = value.enqueue(payload(deadline_ms=16000), 110)
        self.assertIs(same, first)
        self.assertEqual(clock.reads, ['business', 'local'])
        altered = command(); altered['quantity'] = 200
        with self.assertRaises(SourceTradingError):
            value.enqueue(payload(altered), 110)
        clock.local = 102
        value.tick()
        self.assertEqual(decode(first.poll())['error_code'], 'deadline_expired')
        self.assertEqual(calls, [])
        value.request_close()
        self.assertIs(value.enqueue(payload(deadline_ms=17000), 120), first)
        self.assertEqual(value.status()['commands'], 1)

    def test_queue_and_identity_capacity_preserve_rejected_completion(self):
        value, context, clock, calls = service(count=2, pending=1)
        first = value.enqueue(payload(), 105)
        rejected = value.enqueue(payload(command(2)), 105)
        self.assertEqual(decode(rejected.poll())['error_code'], 'capacity_exhausted')
        self.assertIs(value.enqueue(payload(command(2)), 106), rejected)
        with self.assertRaises(SourceTradingError):
            value.enqueue(payload(command(3)), 105)
        value.request_close()
        self.assertEqual(decode(first.poll())['error_code'], 'admission_closed')
        self.assertTrue(value.local_drained)
        self.assertEqual(calls, [])
        value, context, clock, calls = service()
        value.request_close()
        refused = value.enqueue(payload(), 105)
        self.assertEqual(decode(refused.poll())['error_code'], 'admission_closed')
        self.assertIs(value.enqueue(payload(), 106), refused)

    def test_payload_body_identity_and_deadline_rejections_do_not_call_sdk(self):
        value, context, clock, calls = service()
        variants = []
        for key, item in (('kind', 'read'), ('clock_schema', 'UTC'), ('deadline_ms', True),
                           ('deadline_ms', 0), ('body', '%%%'), ('body', 'A' * 10000)):
            item_payload = payload(); item_payload[key] = item; variants.append(item_payload)
        item_payload = payload(); item_payload['extra'] = 1; variants.append(item_payload)
        item_payload = payload(); item_payload['body'] = base64.b64encode(b' '+canonical(command())).decode('ascii'); variants.append(item_payload)
        wrong = command(); wrong['account_id'] = 'OTHER'; variants.append(payload(wrong))
        for item_payload in variants:
            with self.subTest(payload=item_payload), self.assertRaises(SourceTradingError):
                value.enqueue(item_payload, 105)
        for local in (True, 0, float('nan'), float('inf')):
            with self.subTest(local=local), self.assertRaises(SourceTradingError):
                value.enqueue(payload(), local)
        self.assertEqual(value.status()['commands'], 0)
        self.assertEqual(calls, [])
        refused = value.enqueue(payload(deadline_ms=16000), 105)
        self.assertEqual(decode(refused.poll())['error_code'], 'not_admitted')

    def test_original_business_and_local_deadlines_cover_sdk_late_return(self):
        for clock_kind in ('business', 'local'):
            clock = Clocks()
            def buy(*args):
                if clock_kind == 'business':
                    clock.business = 15
                else:
                    clock.local = 105
            value, unused, unused_clock, calls = service(clock=clock, passorder=buy)
            future = value.enqueue(payload(), 105)
            value.tick()
            result = decode(future.poll())
            self.assertEqual(result['stage'], 'unknown')
            self.assertTrue(result['sdk_entered'])
            self.assertEqual(result['error_code'], 'deadline_expired_after_call')
            self.assertFalse(value.status()['write_admission'])
            self.assertFalse(value.local_drained)
        value, context, clock, calls = service()
        future = value.enqueue(payload(), 105)
        clock.business = 15
        value.tick()
        self.assertEqual(decode(future.poll())['error_code'], 'deadline_expired')
        self.assertEqual(calls, [])

    def test_bad_clock_stops_new_writes_and_safe_result_is_retained(self):
        value, context, clock, calls = service()
        clock.business = float('nan')
        future = value.enqueue(payload(), 105)
        self.assertEqual(decode(future.poll())['error_code'], 'clock_failed')
        self.assertFalse(value.status()['write_admission'])
        clock.business = 10
        another = value.enqueue(payload(command(2)), 105)
        self.assertEqual(decode(another.poll())['error_code'], 'admission_closed')
        self.assertEqual(calls, [])

    def test_wrong_thread_phase_and_synchronous_reentry(self):
        value, context, clock, calls = service()
        future = value.enqueue(payload(), 105)
        unused, errors = other_thread(value.tick)
        self.assertEqual([str(error) for error in errors], ['wrong_thread'])
        for phase in ('init', 'handlebar', None):
            with self.assertRaises(SourceTradingError):
                value.tick(phase)
        value.tick()
        self.assertEqual(len(calls), 1)
        self.assertEqual(decode(future.poll())['stage'], 'sdk_returned')
        reentered = []
        def buy(*args):
            try:
                nested.tick()
            except SourceTradingError as error:
                reentered.append(str(error))
        nested, unused, unused_clock, unused_calls = service(passorder=buy)
        done = nested.enqueue(payload(), 105)
        nested.tick()
        self.assertEqual(reentered, ['reentrant_call'])
        self.assertEqual(decode(done.poll())['stage'], 'sdk_returned')

    def test_cancel_preserves_official_account_type_and_signal(self):
        value, context, clock, calls = service()
        original = command(2)
        original = {key: original[key] for key in ('schema_version', 'command_id', 'binding_id',
            'account_id', 'account_type', 'entrust_id', 'user_tag')}
        original.update(operation='order.cancel', original_command_id=command()['command_id'], broker_order_id='broker-1')
        done = value.enqueue(payload(original), 105)
        value.tick()
        self.assertEqual(calls[0][1], ('broker-1', 'SYNTHETIC', 'STOCK', context))
        self.assertIs(decode(done.poll())['signal_sent'], True)

    def test_wrong_context_never_reads_source_and_account_gap_stops_write(self):
        value, context, clock, calls = service()
        class Source(object):
            @property
            def m_strAccountID(self):
                raise AssertionError('must not inspect wrong-context source')
        with self.assertRaises(SourceTradingError) as caught:
            value.on_order(Context(), Source())
        self.assertEqual(str(caught.exception), 'context_mismatch')
        self.assertFalse(value.status()['write_admission'])
        for kind in ('order', 'deal', 'error'):
            value, context, clock, calls = service()
            with self.assertRaises(SourceTradingError):
                if kind == 'error':
                    value.on_error(context, {'accountID': 'OTHER'}, 'source details')
                else:
                    getattr(value, 'on_' + kind)(context, {'m_strAccountID': 'OTHER'})
            self.assertEqual(value.status()['gap']['code'], 'account_mismatch')
            self.assertFalse(value.status()['write_admission'])

    def test_callback_other_thread_page_session_bounds_and_snapshot(self):
        value, context, clock, calls = service()
        result, errors = other_thread(lambda: value.on_order(context, {'m_strAccountID': 'SYNTHETIC'}))
        self.assertEqual(errors, []); self.assertEqual(result, [1])
        for change in ({'session_id': 'old'}, {'limit': 9}, {'max_bytes': 8193}, {'extra': 1}):
            query = page_request(value); query.update(change)
            with self.assertRaises(SourceTradingError):
                value.events(query)
        with self.assertRaises(SourceTradingError):
            value.acknowledge({'session_id': 'old', 'through_seq': 1})
        with self.assertRaises(SourceTradingError):
            value.acknowledge({'session_id': value.session_id, 'through_seq': 1})
        before = value.status()
        before['events']['retained'] = 0
        self.assertEqual(value.status()['events']['retained'], 1)
        self.assertNotIn('SYNTHETIC', canonical(value.status()).decode('utf-8'))
        value.events(page_request(value))
        value.acknowledge({'session_id': value.session_id, 'through_seq': 1})
        value.request_close()
        self.assertTrue(value.local_drained)

    def test_publication_failure_or_cancel_keeps_identity_without_sdk_retry(self):
        for cancelled in (False, True):
            value, context, clock, calls = service()
            done = value.enqueue(payload(), 105)
            if cancelled:
                done.cancel()
                with self.assertRaises(SourceTradingError):
                    value.tick()
            else:
                with patch.object(done, 'publish', side_effect=RuntimeError('private detail')):
                    with self.assertRaises(SourceTradingError) as caught:
                        value.tick()
                self.assertEqual(str(caught.exception), 'result_publication_failed')
            self.assertEqual(len(calls), 1)
            self.assertIs(value.enqueue(payload(), 106), done)
            self.assertFalse(value.status()['write_admission'])
            value.request_close()
            self.assertFalse(value.local_drained)

    def test_close_during_clock_admission_and_sdk_does_not_cancel_entered(self):
        value, context, clock, calls = service()
        def close_now():
            value.request_close()
            return 10
        value._clock = close_now
        done = value.enqueue(payload(), 105)
        self.assertEqual(decode(done.poll())['error_code'], 'admission_closed')
        self.assertTrue(value.local_drained)
        self.assertEqual(calls, [])
        def buy(*args):
            entered.request_close()
            self.assertFalse(entered.local_drained)
        entered, context, clock, calls = service(passorder=buy)
        done = entered.enqueue(payload(), 105)
        entered.tick()
        self.assertEqual(decode(done.poll())['stage'], 'sdk_returned')
        self.assertTrue(entered.local_drained)

    def test_reserved_callback_survives_close_and_blocks_drain_until_ack(self):
        value, context, clock, calls = service()
        entered, release = threading.Event(), threading.Event()
        errors = []
        class Source(object):
            @property
            def m_strAccountID(self):
                entered.set()
                if not release.wait(2):
                    raise RuntimeError('fixture timeout')
                return 'SYNTHETIC'
        def capture():
            try:
                value.on_order(context, Source())
            except BaseException as error:
                errors.append(type(error))
        worker = threading.Thread(target=capture, daemon=True)
        worker.start()
        try:
            self.assertTrue(entered.wait(2))
            value.request_close()
            self.assertEqual(value.status()['events']['inflight'], 1)
            self.assertFalse(value.local_drained)
        finally:
            release.set(); worker.join(2)
        self.assertFalse(worker.is_alive())
        self.assertEqual(errors, [])
        self.assertFalse(value.local_drained)
        value.events(page_request(value))
        value.acknowledge({'session_id': value.session_id, 'through_seq': 1})
        self.assertTrue(value.local_drained)

    def test_sdk_exception_retains_unknown_and_closes_later_identity(self):
        calls = []
        def buy(*args):
            calls.append(args)
            raise RuntimeError('private account detail')
        value, context, clock, unused = service(passorder=buy)
        done = value.enqueue(payload(), 105)
        value.tick()
        result = decode(done.poll())
        self.assertEqual(result['stage'], 'unknown')
        self.assertTrue(result['sdk_entered'])
        self.assertEqual(result['error_code'], 'sdk_exception')
        self.assertNotIn('private account detail', done.poll().decode('utf-8'))
        self.assertIs(value.enqueue(payload(), 106), done)
        refused = value.enqueue(payload(command(2)), 105)
        self.assertEqual(decode(refused.poll())['error_code'], 'admission_closed')
        self.assertEqual(len(calls), 1)
        value.request_close()
        self.assertTrue(value.local_drained)
        self.assertTrue(value.status()['unknown_fenced'])
        self.assertEqual(done.poll(), canonical(result))

    def test_gap_publication_and_sdk_reservation_have_one_shared_order(self):
        for gap_first in (True, False):
            with self.subTest(gap_first=gap_first):
                value, context, clock, calls = service()
                ready, published, release = (threading.Event() for unused in range(3))
                errors = []
                original_notify = value._events._on_gap
                original_reserve = value._kernel._reserve_call
                def delayed_notify(gap):
                    published.set()
                    if not release.wait(2):
                        raise RuntimeError('fixture gap notification timeout')
                    original_notify(gap)
                def event_thread():
                    try:
                        if not ready.wait(2):
                            raise RuntimeError('fixture SDK admission timeout')
                        with self.assertRaises(SourceTradingError):
                            value.on_order(context, {'m_strAccountID': 'OTHER'})
                    except BaseException as error:
                        errors.append(error)
                def reserve(operation):
                    # Kernel字段/clock预检已完成，尚无物理SDK调用。
                    ticket = None if gap_first else original_reserve(operation)
                    if not gap_first:
                        self.assertIsNotNone(ticket)
                    ready.set()
                    if not published.wait(2):
                        raise RuntimeError('fixture gap publication timeout')
                    self.assertIsNotNone(value._events.status()['gap'])
                    self.assertIsNone(value.status()['hard_fault'])
                    return original_reserve(operation) if gap_first else ticket
                worker = threading.Thread(target=event_thread, daemon=True)
                with patch.object(value._events, '_on_gap', side_effect=delayed_notify), \
                        patch.object(value._kernel, '_reserve_call', side_effect=reserve):
                    worker.start()
                    try:
                        future = value.enqueue(payload(), 105)
                        value.tick()
                        result = decode(future.poll())
                        self.assertEqual(result['sdk_entered'], not gap_first)
                        self.assertEqual(result['stage'], 'definitely_not_called' if gap_first else 'sdk_returned')
                        self.assertEqual(len(calls), 0 if gap_first else 1)
                        self.assertIsNone(value._events._call_ticket)
                    finally:
                        ready.set(); release.set(); worker.join(2)
                self.assertFalse(worker.is_alive())
                self.assertEqual(errors, [])
                self.assertEqual(value.status()['hard_fault'], {'code': 'event_gap'})
                refused = value.enqueue(payload(cancel_command()), 105)
                self.assertEqual(decode(refused.poll())['error_code'], 'admission_closed')
                self.assertEqual(len(calls), 0 if gap_first else 1)
                value.request_close()
                self.assertFalse(value.try_local_drained())

    def test_reserved_call_close_and_original_deadline_retire_without_sdk(self):
        for reason in ('close', 'deadline'):
            with self.subTest(reason=reason):
                value, context, clock, calls = service()
                real_reserve = value._kernel._reserve_call
                seen = []
                def reserve(operation):
                    ticket = real_reserve(operation)
                    self.assertIsNotNone(ticket)
                    seen.append(ticket)
                    if reason == 'close':
                        value.request_close()
                    else:
                        clock.local = 105
                    self.assertFalse(value.try_local_drained())
                    return ticket
                future = value.enqueue(payload(), 105)
                with patch.object(value._kernel, '_reserve_call', side_effect=reserve):
                    value.tick()
                result = decode(future.poll())
                self.assertEqual(result['stage'], 'definitely_not_called')
                self.assertFalse(result['sdk_entered'])
                self.assertEqual(result['error_code'], 'admission_closed' if reason == 'close' else 'deadline_expired')
                self.assertEqual(len(seen), 1)
                self.assertIsNone(value._events._call_ticket)
                self.assertEqual(calls, [])
                value.request_close()
                self.assertTrue(value.try_local_drained())

    def test_sdk_reservation_failures_preserve_actual_call_and_borrow_facts(self):
        for phase in ('reserve', 'reserve_after_acquired', 'release'):
            with self.subTest(phase=phase):
                value, context, clock, calls = service()
                future = value.enqueue(payload(), 105)
                real_reserve = value._events.reserve_call
                def reserved_then_failed():
                    self.assertIsNotNone(real_reserve())
                    raise MemoryError()
                method = 'release_call' if phase == 'release' else 'reserve_call'
                failure = reserved_then_failed if phase == 'reserve_after_acquired' else MemoryError
                with patch.object(value._events, method, side_effect=failure):
                    value.tick()
                result = decode(future.poll())
                self.assertEqual(result['sdk_entered'], phase == 'release')
                self.assertEqual(result['stage'], 'sdk_returned' if phase == 'release' else 'definitely_not_called')
                self.assertEqual(len(calls), int(phase == 'release'))
                self.assertEqual(value.status()['hard_fault'],
                    {'code': 'sdk_release_failed' if phase == 'release' else 'sdk_admission_failed'})
                self.assertEqual(value._events._call_ticket is not None, phase != 'reserve')
                value.request_close()
                self.assertFalse(value.try_local_drained())
                # 已知SDK结果与原UUID保持；release异常绝不强清event owner票据。
                self.assertIs(value.enqueue(payload(), 106), future)
                self.assertEqual(future.poll(), canonical(result))

    def test_reserved_sdk_sync_callback_and_reentry_use_no_owner_lock(self):
        def buy(*args):
            self.assertIsNotNone(value._events._call_ticket)
            value.on_order(context, {'m_strAccountID': 'SYNTHETIC'})
            self.assertEqual(value.status()['events']['retained'], 1)
            with self.assertRaisesRegex(SourceTradingError, 'reentrant_call'):
                value.tick()
            value.request_close()
            self.assertFalse(value.try_local_drained())
        value, context, clock, calls = service(passorder=buy)
        future = value.enqueue(payload(), 105)
        value.tick()
        self.assertEqual(decode(future.poll())['stage'], 'sdk_returned')
        self.assertIsNone(value._events._call_ticket)
        self.assertFalse(value.try_local_drained())
        value.events(page_request(value))
        value.acknowledge({'session_id': value.session_id, 'through_seq': 1})
        self.assertTrue(value.try_local_drained())

    def test_unknown_allows_target_cancel_keeps_insert_fence_and_original_result(self):
        def buy(*args):
            raise RuntimeError('synthetic SDK unknown')
        value, context, clock, calls = service(passorder=buy)
        original = value.enqueue(payload(), 105)
        value.tick()
        original_bytes = original.poll()
        state = value.status()
        self.assertTrue(state['unknown_fenced'])
        self.assertFalse(state['write_admission'])
        self.assertTrue(state['cancel_admission'])
        self.assertIsNone(state['hard_fault'])
        self.assertIsNone(state['gap'])
        self.assertFalse(state['closing'])
        value.on_order(context, {'m_strAccountID': 'SYNTHETIC'})
        self.assertEqual(len(value.events(page_request(value))['events']), 1)
        cancelled = value.enqueue(payload(cancel_command()), 105)
        self.assertIsNone(cancelled.poll())
        self.assertTrue(value.tick())
        self.assertEqual(decode(cancelled.poll())['stage'], 'sdk_returned')
        self.assertEqual([call[0] for call in calls], ['cancel'])
        self.assertIs(value.enqueue(payload(cancel_command()), 106), cancelled)
        self.assertEqual(value.enqueue(payload(), 106).poll(), original_bytes)
        refused = value.enqueue(payload(command(3)), 105)
        self.assertEqual(decode(refused.poll())['error_code'], 'admission_closed')
        self.assertTrue(value.status()['unknown_fenced'])
        value.request_close()
        self.assertFalse(value.status()['cancel_admission'])
        self.assertEqual(decode(value.enqueue(payload(cancel_command(4)), 105).poll())['error_code'],
                         'admission_closed')
        self.assertFalse(value.local_drained)

    def test_queued_insert_is_retired_before_queued_cancel_after_unknown(self):
        def buy(*args):
            raise RuntimeError('synthetic')
        value, context, clock, calls = service(passorder=buy, pending=3)
        first = value.enqueue(payload(), 105)
        later_insert = value.enqueue(payload(command(3)), 105)
        later_cancel = value.enqueue(payload(cancel_command()), 105)
        value.tick(); value.tick(); value.tick()
        self.assertEqual(decode(first.poll())['stage'], 'unknown')
        self.assertEqual(decode(later_insert.poll())['error_code'], 'admission_closed')
        self.assertEqual(decode(later_cancel.poll())['stage'], 'sdk_returned')
        self.assertEqual([call[0] for call in calls], ['cancel'])

    def test_unknown_then_hard_fault_blocks_cancel_and_preserves_both_facts(self):
        for fault in ('clock', 'context', 'event', 'publication'):
            with self.subTest(fault=fault):
                value, context, clock, calls = service(passorder=entered_then_raises)
                original = value.enqueue(payload(), 105)
                value.tick()
                if fault == 'clock':
                    clock.business = float('nan')
                    value.enqueue(payload(cancel_command()), 105)
                    clock.business = 10
                    expected = 'clock_failed'
                elif fault == 'context':
                    with self.assertRaises(SourceTradingError):
                        value.on_order(object(), {})
                    expected = 'context_mismatch'
                elif fault == 'event':
                    with self.assertRaises(SourceTradingError):
                        value.on_order(context, {'m_strAccountID': 'OTHER'})
                    expected = 'event_gap'
                else:
                    with patch('guanheng_qmt_shm_agent.trade_service.MemoryCompletion',
                               side_effect=MemoryError):
                        with self.assertRaises(SourceTradingError):
                            value.enqueue(payload(cancel_command()), 105)
                    expected = 'result_publication_failed'
                state = value.status()
                self.assertTrue(state['unknown_fenced'])
                self.assertEqual(state['hard_fault'], {'code': expected})
                self.assertFalse(state['cancel_admission'])
                self.assertEqual(decode(original.poll())['stage'], 'unknown')
                refused = value.enqueue(payload(cancel_command(4)), 105)
                self.assertEqual(decode(refused.poll())['error_code'], 'admission_closed')
                self.assertEqual(calls, [])
                # 第一个硬错安全码保留，source_unknown不能占用或清除此槽。
                value._stop_writes('source_unknown')
                self.assertEqual(value.status()['hard_fault'], {'code': expected})

    def test_cancel_enqueued_inside_original_sdk_runs_only_on_next_owner_tick(self):
        nested = []
        def buy(*args):
            nested.append(value.enqueue(payload(cancel_command()), 105))
            self.assertTrue(value.status()['executing'])
            self.assertEqual(calls, [])
            raise RuntimeError('synthetic')
        value, context, clock, calls = service(passorder=buy)
        original = value.enqueue(payload(), 105)
        value.tick()
        self.assertEqual(decode(original.poll())['stage'], 'unknown')
        self.assertIsNone(nested[0].poll())
        value.tick()
        self.assertEqual(decode(nested[0].poll())['stage'], 'sdk_returned')
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][2], threading.get_ident())

    def test_unknown_cancel_retains_first_deadline_and_is_not_retried(self):
        value, context, clock, calls = service(passorder=entered_then_raises)
        value.enqueue(payload(), 105); value.tick()
        cancel = payload(cancel_command(), deadline_ms=12000)
        queued = value.enqueue(cancel, 102)
        self.assertIs(value.enqueue(payload(cancel_command()), 105), queued)
        clock.local = 102
        value.tick()
        original = queued.poll()
        self.assertEqual(decode(original)['error_code'], 'deadline_expired')
        self.assertIs(value.enqueue(payload(cancel_command()), 110), queued)
        self.assertEqual(queued.poll(), original)
        self.assertEqual(calls, [])

    def test_event_snapshot_failure_blocks_queued_cancel_and_latches_hard_fault(self):
        value, context, clock, calls = service(passorder=entered_then_raises)
        value.enqueue(payload(), 105); value.tick()
        pending = value.enqueue(payload(cancel_command()), 105)
        with patch.object(value._events, 'status', side_effect=MemoryError):
            self.assertTrue(value.tick())
        self.assertEqual(decode(pending.poll())['error_code'], 'admission_closed')
        state = value.status()
        self.assertTrue(state['unknown_fenced'])
        self.assertEqual(state['hard_fault'], {'code': 'event_status_failed'})
        self.assertFalse(state['cancel_admission'])
        self.assertFalse(state['executing'])
        self.assertEqual(calls, [])

    def test_cancel_rechecks_hard_fault_after_enqueue_clock_and_before_sdk(self):
        value, context, clock, calls = service(passorder=entered_then_raises)
        value.enqueue(payload(), 105); value.tick()
        def fail_from_clock():
            try:
                value.on_order(object(), {})
            except SourceTradingError:
                pass
            return 10
        value._clock = fail_from_clock
        result = value.enqueue(payload(cancel_command()), 105)
        self.assertEqual(decode(result.poll())['error_code'], 'admission_closed')
        self.assertEqual(calls, [])
        value, context, clock, calls = service(passorder=entered_then_raises)
        value.enqueue(payload(), 105); value.tick()
        result = value.enqueue(payload(cancel_command()), 105)
        value._clock = fail_from_clock
        value.tick()
        self.assertEqual(decode(result.poll())['error_code'], 'admission_closed')
        self.assertEqual(calls, [])

    def test_concurrent_duplicate_during_first_clock_keeps_original_owner(self):
        value, context, clock, calls = service()
        entered, release = threading.Event(), threading.Event()
        completed, errors = [], []
        def slow_clock():
            entered.set()
            if not release.wait(2):
                raise RuntimeError('fixture timeout')
            return 10
        value._clock = slow_clock
        def enqueue_first():
            try:
                completed.append(value.enqueue(payload(), 102))
            except BaseException as error:
                errors.append(type(error))
        worker = threading.Thread(target=enqueue_first, daemon=True)
        worker.start()
        try:
            self.assertTrue(entered.wait(2))
            duplicate = value.enqueue(payload(deadline_ms=16000), 110)
            self.assertIsNone(duplicate.poll())
            self.assertEqual(value.status()['commands'], 1)
            value.request_close()
            self.assertEqual(decode(duplicate.poll())['error_code'], 'admission_closed')
        finally:
            release.set(); worker.join(2)
        self.assertFalse(worker.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(len(completed), 1)
        self.assertIs(completed[0], duplicate)
        self.assertTrue(value.local_drained)
        self.assertEqual(calls, [])


    def test_close_during_sdk_retains_later_synchronous_callback_until_ack(self):
        observed = []
        def buy(*args):
            value.request_close()
            observed.append(value.status()['events']['closed'])
            self.assertFalse(value.local_drained)
            value.on_order(context, {'m_strAccountID': 'SYNTHETIC', 'm_strRemark': args[9]})
            self.assertEqual(value.status()['events']['retained'], 1)
        value, context, clock, calls = service(passorder=buy)
        done = value.enqueue(payload(), 105)
        seal = value._events.request_close
        sealing = []
        def checked_seal():
            sealing.append((value.status()['executing'], value.local_drained))
            seal()
        with patch.object(value._events, 'request_close', side_effect=checked_seal):
            value.tick()
        self.assertEqual(sealing, [(False, False)])
        self.assertEqual(observed, [False])
        self.assertEqual(decode(done.poll())['stage'], 'sdk_returned')
        self.assertTrue(value.status()['events']['closed'])
        self.assertIsNone(value.status()['gap'])
        self.assertFalse(value.local_drained)
        page = value.events(page_request(value))
        self.assertEqual(page['events'][0]['payload']['m_strRemark'], 'synthetic.1')
        value.acknowledge({'session_id': value.session_id, 'through_seq': 1})
        self.assertTrue(value.local_drained)
        # SDK返回后的晚异步回报已超出封口；保留gap，不把宿主回调生命周期判绿。
        with self.assertRaises(SourceTradingError):
            value.on_order(context, {'m_strAccountID': 'SYNTHETIC'})
        self.assertEqual(value.status()['gap']['code'], 'capture_closed')
        self.assertFalse(value.local_drained)


    def test_try_local_drained_busy_locks_are_nonblocking_and_release_service(self):
        value, context, clock, calls = service()
        value.request_close()
        for lock in (value._lock, value._events._lock):
            lock.acquire()
            try:
                observed, errors = other_thread(value.try_local_drained)
                self.assertEqual(errors, [])
                self.assertEqual(observed, [False])
            finally:
                lock.release()
            self.assertTrue(value.try_local_drained())
            self.assertTrue(value._lock.acquire(False))
            value._lock.release()
        self.assertEqual(calls, [])

    def test_normal_drain_query_waits_short_lock_while_try_remains_nonblocking(self):
        for layer in ('service', 'event'):
            with self.subTest(layer=layer):
                value, context, clock, calls = service()
                value.request_close()
                owner = value if layer == 'service' else value._events
                actual = owner._lock
                attempted, done = threading.Event(), threading.Event()
                modes, results, errors = [], [], []
                class ObservedLock(object):
                    def acquire(self, blocking=True):
                        modes.append(blocking)
                        attempted.set()
                        return actual.acquire(blocking)
                    def release(self):
                        actual.release()
                    def __enter__(self):
                        self.acquire(True)
                        return self
                    def __exit__(self, *unused):
                        self.release()
                def query():
                    try:
                        results.append(value.local_drained)
                    except BaseException as error:
                        errors.append(error)
                    finally:
                        done.set()
                worker = threading.Thread(target=query, daemon=True)
                with patch.object(owner, '_lock', new=ObservedLock()):
                    actual.acquire()
                    try:
                        self.assertFalse(value.try_local_drained())
                        self.assertEqual(modes, [False])
                        modes[:] = []; attempted.clear()
                        worker.start()
                        self.assertTrue(attempted.wait(2))
                        self.assertEqual(modes, [True])
                        self.assertFalse(done.is_set())
                    finally:
                        actual.release()
                        if worker.ident is not None:
                            worker.join(2)
                self.assertFalse(worker.is_alive())
                self.assertEqual(errors, [])
                self.assertEqual(results, [True])
                self.assertTrue(value.try_local_drained())
                self.assertIsNone(value.status()['hard_fault'])
                self.assertEqual(calls, [])

    def test_try_local_drained_checks_tickets_without_status_clock_or_mutation(self):
        value, context, clock, calls = service()
        self.assertFalse(value.try_local_drained())
        done = value.enqueue(payload(), 105)
        value.on_order(context, {'m_strAccountID': 'SYNTHETIC'})
        value.request_close()
        before = value.status()
        original_result = done.poll()
        with patch.object(value, 'status', side_effect=AssertionError('status copy')), \
                patch.object(value._events, 'status', side_effect=AssertionError('event copy')), \
                patch.object(value, '_clock', side_effect=AssertionError('clock')), \
                patch.object(value, '_mono', side_effect=AssertionError('local clock')):
            self.assertFalse(value.try_local_drained())
        self.assertEqual(value.status(), before)
        self.assertEqual(done.poll(), original_result)
        value.events(page_request(value))
        value.acknowledge({'session_id': value.session_id, 'through_seq': 1})
        self.assertTrue(value.try_local_drained())
        with self.assertRaises(SourceTradingError):
            value.on_order(context, {'m_strAccountID': 'SYNTHETIC'})
        gap = value.status()
        self.assertFalse(value.try_local_drained())
        self.assertEqual(value.status(), gap)
        self.assertEqual(calls, [])

    def test_try_local_drained_rejects_inflight_and_unpublished_completion(self):
        observed = []
        def buy(*args):
            value.request_close()
            observed.append(value.try_local_drained())
        value, context, clock, calls = service(passorder=buy)
        done = value.enqueue(payload(), 105)
        value.tick()
        self.assertEqual(observed, [False])
        self.assertTrue(value.try_local_drained())
        value, context, clock, calls = service()
        done = value.enqueue(payload(), 105)
        publish = done.publish
        def checked_publish(raw):
            observed.append(value.try_local_drained())
            publish(raw)
        with patch.object(done, 'publish', side_effect=checked_publish):
            value.request_close()
        self.assertEqual(observed, [False, False])
        self.assertTrue(value.try_local_drained())
        value, context, clock, calls = service()
        done = value.enqueue(payload(), 105)
        done.cancel()
        with self.assertRaises(SourceTradingError):
            value.request_close()
        self.assertFalse(value.try_local_drained())

    def test_try_local_drained_releases_service_lock_on_event_check_exception(self):
        value, context, clock, calls = service()
        value.request_close()
        with patch.object(value._events, 'try_drained', side_effect=MemoryError):
            with self.assertRaises(MemoryError):
                value.try_local_drained()
        self.assertTrue(value._lock.acquire(False))
        value._lock.release()
        self.assertTrue(value.try_local_drained())


if __name__ == '__main__':
    unittest.main()
