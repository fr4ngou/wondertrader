# -*- coding: utf-8 -*-
"""QST-R14 纯字段/身份回归；测试不构造 SDK、运行线程或获得真实写许可。"""
import copy
from datetime import date
import hashlib
import unittest

from guanheng_qmt_shm_agent.protocol import ProtocolError, canonical
from guanheng_qmt_shm_agent.read_capabilities import (
    ACCOUNT, FULL_TICK, HISTORY, build_read_profile, build_trade_read_profile,
    explicit_profile_version, operation_descriptor, validate_read_profile,
    validate_read_request,
)
from guanheng_qmt_shm_agent.trade_capabilities import (
    validate_trade_profile, validate_trade_profile_binding,
)


CAP = 262144
CONTROL = {'schema_version': '1.0', 'max_pending_calls': 1,
           'max_call_bytes': 8192, 'max_reply_bytes': 327680,
           'max_retained_bytes': 1048576, 'max_cycle_messages': 4,
           'max_cycle_bytes': 524288, 'poll_seconds': 0.01,
           'max_call_seconds': 3}
# 三份旧 envelope 的独立规范文本，不从 builder 输出反推 golden。
CONTROL_BYTES = (b'{"max_call_bytes":8192,"max_call_seconds":3,'
    b'"max_cycle_bytes":524288,"max_cycle_messages":4,"max_pending_calls":1,'
    b'"max_reply_bytes":327680,"max_retained_bytes":1048576,"poll_seconds":0.01,'
    b'"schema_version":"1.0"}')
HISTORY_BYTES = (b'{"execution_timeout_ms":1000,"limits":{"max_calendar_days":5,'
    b'"max_data_bytes":8192,"max_rows":2000,"schema_version":"qmt.history-1m.v1"},'
    b'"policy_id":"qmt.history-read.v1","policy_version":"1.0"}')
ACCOUNT_BYTES = (b'{"execution_timeout_ms":1000,"limits":{"account_binding":'
    b'{"account_environment":"live","account_id":"SYNTHETIC","currency":"CNY",'
    b'"financial_profile":"cny_cash_shsz_v1"},"max_data_bytes":8192,"max_nodes":65536,'
    b'"max_rows":4096,"max_scalar_chars":262144,"schema_version":"qmt.account-read.v1"},'
    b'"policy_id":"qmt.account-read.v1","policy_version":"1.0"}')


def binding():
    return {'schema_version': 'qmt.trade-binding.v1', 'binding_id': 'synthetic-only',
            'account_id': 'SYNTHETIC', 'account_type': 'stock',
            'account_environment': 'live', 'strategy_name': 'synthetic',
            'max_commands': 16, 'symbol_rules': {'000001.SZ': {
                'price_tick': '0.01', 'buy_min': 100, 'buy_step': 100,
                'sell_min': 1, 'sell_step': 1}}}


def trade_profile(private=None):
    private = binding() if private is None else private
    return {'schema_version': 'qmt.trade-profile.v1',
            'binding_sha256': hashlib.sha256(canonical(private)).hexdigest(),
            'clock_schema': 'qmt.win-uptime-ms.v1',
            'operations': ['order.cancel', 'order.insert'],
            'limits': {'max_commands': private['max_commands'], 'max_command_bytes': 65536,
                       'max_command_ttl_ms': 300000, 'max_call_result_bytes': 2097152,
                       'max_events': 4096, 'max_event_bytes': 1048576,
                       'max_total_event_bytes': 16777216, 'max_event_page_bytes': 4190208}}


def read_entries(operations):
    entries = {
        FULL_TICK: {'policy_id': 'qmt.standard-read.v1', 'policy_version': '1.0',
                    'execution_timeout_ms': 1000, 'limits': {}},
        HISTORY: {'policy_id': 'qmt.history-read.v1', 'policy_version': '1.0',
                  'execution_timeout_ms': 1000, 'limits': {
                      'schema_version': 'qmt.history-1m.v1', 'max_calendar_days': 5,
                      'max_rows': 2000, 'max_data_bytes': 8192}},
        ACCOUNT: {'policy_id': 'qmt.account-read.v1', 'policy_version': '1.0',
                  'execution_timeout_ms': 1000, 'limits': {
                      'schema_version': 'qmt.account-read.v1', 'account_binding': {
                          'account_id': 'SYNTHETIC', 'account_environment': 'live',
                          'currency': 'CNY', 'financial_profile': 'cny_cash_shsz_v1'},
                      'max_rows': 4096, 'max_nodes': 65536,
                      'max_scalar_chars': 262144, 'max_data_bytes': 8192}}}
    return {operation: entries[operation] for operation in operations}


def profile(operations=None, descriptor=None):
    operations = [ACCOUNT] if operations is None else operations
    control = dict(CONTROL, schema_version='2.0')
    return {'read_profile_version': 'qmt.read-profile.v4',
            'read_operations': operations, 'execution_timeout_ms': 1000,
            'control_profile': control, 'operation_profiles': read_entries(operations),
            'trade_profile': trade_profile() if descriptor is None else descriptor}


def request(operation):
    values = {
        FULL_TICK: {'symbols': ['000001.SZ']},
        HISTORY: {'symbol': '000001.SZ', 'start_time': '20261022093000',
                  'end_time': '20261022100000', 'max_rows': 100},
        ACCOUNT: {'account_type': 'stock', 'datatype': 'account', 'scope': 'account'}}
    return {'request_id': '00000000-0000-4000-8000-000000000001',
            'correlation_id': '00000000-0000-4000-8000-000000000002',
            'operation_id': operation, 'arguments': values[operation],
            'timeout_ms': 1000, 'policy_id': read_entries([operation])[operation]['policy_id'],
            'policy_version': '1.0', 'priority_class': 'normal'}


class TradeCapabilityTests(unittest.TestCase):
    def test_descriptor_copy_and_binding_match(self):
        private = binding()
        source = trade_profile(private)
        actual = validate_trade_profile_binding(source, private)
        self.assertEqual(actual, source)
        self.assertEqual(set(actual), {'schema_version', 'binding_sha256',
                                      'clock_schema', 'operations', 'limits'})
        source['operations'].clear()
        source['limits']['max_commands'] = 1
        self.assertEqual(actual['operations'], ['order.cancel', 'order.insert'])
        self.assertEqual(actual['limits']['max_commands'], 16)
        actual['limits']['max_events'] = 1
        self.assertEqual(private['max_commands'], 16)

    def test_binding_checks_full_private_rules_and_capacity(self):
        original = binding()
        descriptor = trade_profile(original)
        variants = []
        for key, value in (('account_id', 'ANOTHER'), ('binding_id', 'other'),
                           ('strategy_name', 'other'), ('max_commands', 17)):
            changed = copy.deepcopy(original)
            changed[key] = value
            variants.append(changed)
        changed = copy.deepcopy(original)
        changed['symbol_rules']['000001.SZ']['price_tick'] = '0.02'
        variants.append(changed)
        changed = copy.deepcopy(original)
        changed['symbol_rules']['000001.SZ']['price_tick'] = '0'
        variants.append(changed)
        for changed in variants:
            with self.subTest(changed=changed), self.assertRaises(ProtocolError):
                validate_trade_profile_binding(descriptor, changed)
        # 单独改公开容量也拒绝，摘要相等不掩盖不一致的资源配置。
        descriptor['limits']['max_commands'] = 17
        with self.assertRaises(ProtocolError):
            validate_trade_profile_binding(descriptor, original)
        bad_private = dict(original, extra='ignored')
        with self.assertRaises(ProtocolError):
            validate_trade_profile_binding(trade_profile(bad_private), bad_private)

    def test_descriptor_exact_fields_versions_hash_and_operations(self):
        bad = []
        for name, item in (
                ('schema_version', 'qmt.trade-profile.v2'),
                ('clock_schema', 'monotonic'), ('clock_schema', None),
                ('binding_sha256', 'A' * 64), ('binding_sha256', 'a' * 63),
                ('binding_sha256', 'g' * 64), ('binding_sha256', 0),
                ('operations', ['order.insert', 'order.cancel']),
                ('operations', ['order.cancel', 'order.cancel']),
                ('operations', ['order.insert']),
                ('operations', ['order.cancel', 'order.insert', 'account.trade_detail']),
                ('operations', ('order.cancel', 'order.insert'))):
            value = trade_profile(); value[name] = item; bad.append(value)
        value = trade_profile(); value['writes_enabled'] = True; bad.append(value)
        value = trade_profile(); del value['binding_sha256']; bad.append(value)
        value = trade_profile(); value['limits']['unknown'] = 1; bad.append(value)
        value = trade_profile(); del value['limits']['max_commands']; bad.append(value)
        for value in bad:
            with self.subTest(value=value), self.assertRaises(ProtocolError):
                validate_trade_profile(value)

    def test_all_limit_boundaries_and_scalar_types(self):
        bounds = (('max_commands', 1, 4096), ('max_command_bytes', 1, 65536),
                  ('max_command_ttl_ms', 100, 300000),
                  ('max_call_result_bytes', 1024, 2097152), ('max_events', 1, 4096),
                  ('max_event_bytes', 256, 1048576),
                  ('max_total_event_bytes', 256, 16777216),
                  ('max_event_page_bytes', 1280, 4190208))
        for key, low, high in bounds:
            for number in (low - 1, high + 1, True, None, 1.5, '100'):
                value = trade_profile(); value['limits'][key] = number
                with self.subTest(key=key, number=number), self.assertRaises(ProtocolError):
                    validate_trade_profile(value)
        value = trade_profile()
        for key, low, high in bounds:
            value['limits'][key] = low
        self.assertEqual(validate_trade_profile(value), value)
        for key, low, high in bounds:
            value['limits'][key] = high
        self.assertEqual(validate_trade_profile(value), value)
        for key, number in (('max_total_event_bytes', 1048575),
                            ('max_event_page_bytes', 1049599)):
            value = trade_profile(); value['limits'][key] = number
            with self.subTest(key=key), self.assertRaises(ProtocolError):
                validate_trade_profile(value)

    def test_non_plain_values_do_not_run_user_comparison(self):
        class Trap(object):
            def __eq__(self, other):
                raise AssertionError('external comparison is not a protocol value')
        class DictSubclass(dict):
            pass
        for key in ('schema_version', 'clock_schema', 'binding_sha256', 'operations'):
            value = trade_profile(); value[key] = Trap()
            with self.subTest(key=key), self.assertRaises(ProtocolError):
                validate_trade_profile(value)
        value = trade_profile(); value['operations'][0] = Trap()
        with self.assertRaises(ProtocolError):
            validate_trade_profile(value)
        with self.assertRaises(ProtocolError):
            validate_trade_profile(DictSubclass(trade_profile()))

    def test_large_private_rule_set_stays_outside_profile_capacity(self):
        private = binding()
        rule = private['symbol_rules']['000001.SZ']
        private['symbol_rules'] = {
            '%06d.SZ' % number: dict(rule) for number in range(4096)}
        descriptor = trade_profile(private)
        self.assertEqual(validate_trade_profile_binding(descriptor, private), descriptor)
        combined = profile([ACCOUNT, FULL_TICK, HISTORY], descriptor)
        combined['operation_profiles'][ACCOUNT]['limits']['account_binding']['account_id'] = '账' * 21
        admitted = validate_read_profile(combined, max_result_bytes=CAP)
        self.assertLessEqual(len(canonical(admitted)), 4096)
        self.assertGreater(len(canonical(private)), 4096)
        self.assertNotIn(b'symbol_rules', canonical(admitted))
        combined['trade_profile']['symbol_rules'] = private['symbol_rules']
        with self.assertRaises(ProtocolError):
            validate_read_profile(combined, max_result_bytes=CAP)

    def test_v4_read_requests_keep_actual_version_and_original_bytes(self):
        for operations in ([ACCOUNT], [ACCOUNT, FULL_TICK], [ACCOUNT, HISTORY],
                           [ACCOUNT, FULL_TICK, HISTORY]):
            source = profile(list(operations))
            actual = build_trade_read_profile(source['read_operations'], 1000,
                source['control_profile'], source['operation_profiles'],
                source['trade_profile'], max_result_bytes=CAP)
            self.assertEqual(actual, source)
            self.assertEqual(actual['control_profile']['schema_version'], '2.0')
            for operation in operations:
                original = request(operation)
                raw = canonical(original)
                validate_read_request(original, actual, as_of_date=date(2026, 10, 23),
                                      max_result_bytes=CAP)
                self.assertEqual(canonical(original), raw)
                self.assertEqual(operation_descriptor(actual, operation, max_result_bytes=CAP),
                                 actual['operation_profiles'][operation])
                wrong = copy.deepcopy(actual)
                wrong['control_profile']['schema_version'] = '1.0'
                with self.assertRaises(ProtocolError):
                    validate_read_request(original, wrong, as_of_date=date(2026, 10, 23),
                                          max_result_bytes=CAP)
        for datatype in ('position', 'order', 'deal', 'account'):
            original = request(ACCOUNT); original['arguments']['datatype'] = datatype
            validate_read_request(original, profile(), max_result_bytes=CAP)

    def test_v4_request_and_read_descriptor_fail_closed(self):
        source = profile([ACCOUNT, FULL_TICK, HISTORY])
        variants = []
        original = request(ACCOUNT); original['arguments']['account_id'] = 'OTHER'; variants.append(original)
        original = request(ACCOUNT); original['policy_id'] = 'qmt.standard-read.v1'; variants.append(original)
        original = request(ACCOUNT); original['timeout_ms'] = 1001; variants.append(original)
        original = request(ACCOUNT); original['trade_profile'] = {}; variants.append(original)
        original = request(HISTORY); original['arguments']['max_rows'] = 2001; variants.append(original)
        original = request(HISTORY); original['arguments']['start_time'] = '20260230093000'; variants.append(original)
        for original in variants:
            with self.subTest(request=original), self.assertRaises(ProtocolError):
                validate_read_request(original, source, as_of_date=date(2026, 10, 23),
                                      max_result_bytes=CAP)
        with self.assertRaises(ProtocolError):
            validate_read_request(request(FULL_TICK), profile(), max_result_bytes=CAP)
        for key, value in (('policy_id', 'qmt.standard-read.v1'),
                           ('policy_version', '3.0'), ('execution_timeout_ms', 999)):
            bad = profile(); bad['operation_profiles'][ACCOUNT][key] = value
            with self.subTest(key=key), self.assertRaises(ProtocolError):
                validate_read_profile(bad, max_result_bytes=CAP)
        bad = profile(); bad['operation_profiles'][ACCOUNT]['limits']['max_data_bytes'] = CAP
        with self.assertRaises(ProtocolError):
            validate_read_profile(bad, max_result_bytes=CAP)

    def test_v4_closed_envelope_control_and_required_account(self):
        variants = []
        for name, item in (('read_profile_version', 'qmt.read-profile.v3'),
                           ('read_profile_version', 'qmt.read-profile.v5'),
                           ('execution_timeout_ms', 1001)):
            value = profile(); value[name] = item; variants.append(value)
        value = profile(); value['control_profile']['schema_version'] = '1.0'; variants.append(value)
        value = profile(); value['extra'] = True; variants.append(value)
        value = profile(); del value['trade_profile']; variants.append(value)
        value = profile([ACCOUNT, FULL_TICK]); value['read_operations'].reverse(); variants.append(value)
        value = profile(); value['read_operations'].append(ACCOUNT); variants.append(value)
        value = profile(); value['operation_profiles']['order.insert'] = {}; variants.append(value)
        variants.extend(profile(ops) for ops in ([FULL_TICK], [HISTORY], [FULL_TICK, HISTORY]))
        for value in variants:
            with self.subTest(profile=value), self.assertRaises(ProtocolError):
                validate_read_profile(value, max_result_bytes=CAP)
        for result_cap in (None, True, 8191, 2097153):
            with self.subTest(cap=result_cap), self.assertRaises(ProtocolError):
                validate_read_profile(profile(), max_result_bytes=result_cap)

    def test_v4_no_mutable_aliases(self):
        source = profile([ACCOUNT, HISTORY])
        actual = build_trade_read_profile(source['read_operations'], 1000,
            source['control_profile'], source['operation_profiles'], source['trade_profile'],
            max_result_bytes=CAP)
        source['read_operations'].clear()
        source['control_profile']['schema_version'] = '1.0'
        source['operation_profiles'][ACCOUNT]['limits']['account_binding']['account_id'] = 'OTHER'
        source['trade_profile']['limits']['max_commands'] = 1
        source['trade_profile']['operations'].clear()
        self.assertEqual(actual['read_operations'], [ACCOUNT, HISTORY])
        self.assertEqual(actual['control_profile']['schema_version'], '2.0')
        self.assertEqual(actual['operation_profiles'][ACCOUNT]['limits']['account_binding']['account_id'], 'SYNTHETIC')
        self.assertEqual(actual['trade_profile']['limits']['max_commands'], 16)
        self.assertEqual(actual['trade_profile']['operations'], ['order.cancel', 'order.insert'])
        descriptor = operation_descriptor(actual, ACCOUNT, max_result_bytes=CAP)
        descriptor['limits']['account_binding']['account_id'] = 'THIRD'
        self.assertEqual(actual['operation_profiles'][ACCOUNT]['limits']['account_binding']['account_id'], 'SYNTHETIC')

    def test_old_v1_v2_v3_builders_keep_exact_bytes_and_control1(self):
        expected = {
            FULL_TICK: b'{"control_profile":' + CONTROL_BYTES +
                b',"execution_timeout_ms":1000,"read_operations":["market.full_tick"]}',
            HISTORY: b'{"control_profile":' + CONTROL_BYTES +
                b',"execution_timeout_ms":1000,"operation_profiles":{"market.history_1m":' + HISTORY_BYTES +
                b'},"read_operations":["market.history_1m"],"read_profile_version":"qmt.read-profile.v2"}',
            ACCOUNT: b'{"control_profile":' + CONTROL_BYTES +
                b',"execution_timeout_ms":1000,"operation_profiles":{"account.trade_detail":' + ACCOUNT_BYTES +
                b'},"read_operations":["account.trade_detail"],"read_profile_version":"qmt.read-profile.v3"}'}
        for operation in (FULL_TICK, HISTORY, ACCOUNT):
            entries = None if operation == FULL_TICK else read_entries([operation])
            actual = build_read_profile([operation], 1000, copy.deepcopy(CONTROL),
                                        entries, max_result_bytes=CAP)
            self.assertEqual(canonical(actual), expected[operation])
            with self.assertRaises(ProtocolError):
                build_read_profile([operation], 1000, dict(CONTROL, schema_version='2.0'),
                                   entries, max_result_bytes=CAP)
        self.assertIsNone(explicit_profile_version([FULL_TICK]))
        self.assertEqual(explicit_profile_version([HISTORY]), 'qmt.read-profile.v2')
        self.assertEqual(explicit_profile_version([ACCOUNT]), 'qmt.read-profile.v3')


if __name__ == '__main__':
    unittest.main()
