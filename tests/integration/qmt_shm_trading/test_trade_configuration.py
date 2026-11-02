# -*- coding: utf-8 -*-
"""R15 纯配置及真实 ControlPeer 内存状态测试；没有 SDK、线程启动或 I/O。"""
import base64
import copy
from datetime import datetime, timezone
import unittest
from unittest.mock import patch

from guanheng_qmt_shm_agent import read_configuration, builtin_shm
from guanheng_qmt_shm_agent.control_peer import ControlPeer
from guanheng_qmt_shm_agent.control_profile import ControlProfile
from guanheng_qmt_shm_agent.protocol import canonical, TransportBudget
from guanheng_qmt_shm_agent.read_capabilities import ACCOUNT, FULL_TICK, HISTORY
from guanheng_qmt_shm_agent.read_configuration import validate_read_configuration
from guanheng_qmt_shm_agent.trading_configuration import validate_trade_configuration
from test_trade_capabilities import binding, trade_profile, read_entries, request


SECRET = b'synthetic-trade-configuration-secret-0001'


def settings():
    private = binding()
    descriptor = trade_profile(private)
    descriptor['limits'].update(max_command_bytes=4096, max_command_ttl_ms=5000,
        max_call_result_bytes=4096, max_events=8, max_event_bytes=1024,
        max_total_event_bytes=8192, max_event_page_bytes=4096)
    return {'route': {'route_id': 'trade-config', 'executor_id': 'synthetic', 'route_epoch': 1},
        'secret': SECRET, 'allowed_operations': [ACCOUNT, FULL_TICK, HISTORY],
        'execution_timeout_ms': 1000, 'max_frame': 262144, 'max_pending': 1,
        'max_result_bytes': 16384, 'connect_seconds': 5, 'io_seconds': 2,
        'control_profile': {'schema_version': '2.0', 'max_pending_calls': 4,
            'max_call_bytes': 8192, 'max_reply_bytes': 32768, 'max_retained_bytes': 300000,
            'max_cycle_messages': 8, 'max_cycle_bytes': 65536,
            'poll_seconds': .005, 'max_call_seconds': 10},
        'transport': {'kind': 'shm', 'name': 'qmt-broker-trade-config', 'key_id': 'synthetic',
            'windows_session_id': 0, 'slot_counts': {'command': 2, 'reliable': 2, 'quote': 1},
            'control_packet_max_bytes': 8192, 'max_mapped_bytes': 4194304,
            'max_recent_frames': 64, 'poll_seconds': .005},
        'read_profile_version': 'qmt.read-profile.v4',
        'operation_profiles': read_entries([ACCOUNT, FULL_TICK, HISTORY]),
        'trade_profile': descriptor, 'trade_binding': private, 'writes_enabled': False}


def legacy(operations):
    value = settings()
    for key in ('trade_profile', 'trade_binding', 'writes_enabled'):
        del value[key]
    value['allowed_operations'] = list(operations)
    value['control_profile']['schema_version'] = '1.0'
    value['operation_profiles'] = read_entries(operations)
    if operations == [FULL_TICK]:
        del value['read_profile_version']
        del value['operation_profiles']
    else:
        value['read_profile_version'] = ('qmt.read-profile.v3' if ACCOUNT in operations
                                         else 'qmt.read-profile.v2')
    return value


class Clock(object):
    def __init__(self):
        self.now = 0

    def mono(self):
        return self.now

    def utc(self):
        return 1800000000 + self.now

    def expires(self):
        return datetime.fromtimestamp(self.utc() + 5, timezone.utc).isoformat()


def send(sender, receiver):
    batch = sender.prepare()
    # 本测试用内存传送替身代表成功的Session.send，再交真实peer解析。
    receiver.receive(batch.packet)
    sender.sent(batch)
    return batch.packet


def insert_body():
    return base64.b64encode(canonical({
        'schema_version': 'qmt.trade-command.v1',
        'command_id': '00000000-0000-4000-8000-000000000003',
        'operation': 'order.insert', 'binding_id': 'synthetic-only',
        'account_id': 'SYNTHETIC', 'account_type': 'stock', 'entrust_id': 'native.1',
        'user_tag': 'synthetic.1', 'symbol': '000001.SZ', 'side': 'buy',
        'order_type': 'limit', 'limit_price': '10.01', 'quantity': 100,
        'sdk_user_order_id': 'synthetic.1'})).decode('ascii')


class TradeConfigurationTests(unittest.TestCase):
    def test_public_private_snapshot_and_explicit_gate(self):
        value = settings()
        public = {key: copy.deepcopy(item) for key, item in value.items()
                  if key not in ('secret', 'trade_binding', 'writes_enabled')}
        actual = validate_trade_configuration(value)
        self.assertEqual(actual.value, public)
        self.assertEqual(actual.secret, SECRET)
        self.assertIs(actual.writes_enabled, False)
        self.assertEqual(actual.profile['read_profile_version'], 'qmt.read-profile.v4')
        self.assertEqual(actual.profile['control_profile']['schema_version'], '2.0')
        self.assertNotIn('symbol_rules', canonical(actual.value).decode('utf-8'))
        for key in ('secret', 'trade_binding', 'writes_enabled'):
            self.assertNotIn(key, actual.value)
        value['secret'] = b'changed' * 8
        value['writes_enabled'] = True
        value['trade_binding']['symbol_rules']['000001.SZ']['price_tick'] = '99'
        value['route']['route_id'] = 'changed'
        value['trade_profile']['limits']['max_events'] = 1
        self.assertEqual(actual.secret, SECRET)
        self.assertIs(actual.writes_enabled, False)
        self.assertEqual(actual.route['route_id'], 'trade-config')
        self.assertEqual(actual.trade_binding['symbol_rules']['000001.SZ']['price_tick'], '0.01')
        copied = actual.trade_binding
        copied['symbol_rules'].clear()
        self.assertEqual(len(actual.trade_binding['symbol_rules']), 1)
        copied_profile = actual.profile
        copied_profile['trade_profile']['limits']['max_events'] = 1
        self.assertEqual(actual.profile['trade_profile']['limits']['max_events'], 8)
        requested = settings(); requested['writes_enabled'] = True
        self.assertIs(validate_trade_configuration(requested).writes_enabled, True)
        self.assertNotIn('order_ready', actual.value)

    def test_exact_fields_versions_gate_and_secret(self):
        source = settings()
        for missing in source:
            value = copy.deepcopy(source); del value[missing]
            with self.subTest(missing=missing), self.assertRaises(ValueError):
                validate_trade_configuration(value)
        values = []
        value = settings(); value['extra'] = None; values.append(value)
        for name, item in (('writes_enabled', 1), ('writes_enabled', 'false'),
                           ('writes_enabled', None), ('secret', b'short'),
                           ('secret', bytearray(SECRET)), ('read_profile_version', 'qmt.read-profile.v3')):
            value = settings(); value[name] = item; values.append(value)
        value = settings(); value['control_profile']['schema_version'] = '1.0'; values.append(value)
        for value in values:
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_trade_configuration(value)
        with self.assertRaises(ValueError):
            validate_read_configuration(settings())

    def test_old_read_configuration_values_and_profile_remain(self):
        for operations in ([FULL_TICK], [HISTORY], [ACCOUNT], [ACCOUNT, FULL_TICK, HISTORY]):
            value = legacy(list(operations))
            before = copy.deepcopy(value)
            actual = validate_read_configuration(value)
            self.assertEqual(actual.value, {key: item for key, item in before.items() if key != 'secret'})
            self.assertEqual(actual.secret, SECRET)
            self.assertEqual(value, before)
            self.assertEqual(actual.profile['control_profile']['schema_version'], '1.0')
            self.assertEqual(actual.profile['read_operations'], list(operations))
            if operations == [FULL_TICK]:
                self.assertEqual(set(actual.profile), {'read_operations', 'execution_timeout_ms', 'control_profile'})
            else:
                self.assertEqual(actual.profile['read_profile_version'], before['read_profile_version'])
            for new_key in ('writes_enabled', 'trade_binding', 'trade_profile'):
                altered = copy.deepcopy(value); altered[new_key] = settings()[new_key]
                with self.subTest(operations=operations, key=new_key), self.assertRaises(ValueError):
                    validate_read_configuration(altered)
            with self.assertRaises(ValueError):
                validate_trade_configuration(value)

    def test_account_and_private_digest_relations_reject_before_transport(self):
        values = []
        for name, item in (('account_id', 'OTHER'), ('account_environment', 'simulation')):
            value = settings()
            value['operation_profiles'][ACCOUNT]['limits']['account_binding'][name] = item
            values.append(value)
        value = settings(); value['trade_profile']['binding_sha256'] = '0' * 64; values.append(value)
        value = settings(); value['trade_profile']['limits']['max_commands'] += 1; values.append(value)
        value = settings(); value['trade_binding']['symbol_rules']['000001.SZ']['price_tick'] = '0'; values.append(value)
        for value in values:
            with patch.object(read_configuration, 'validate_transport_profile') as layout:
                with self.subTest(value=value), self.assertRaises(ValueError):
                    validate_trade_configuration(value)
                layout.assert_not_called()

    def test_base64_groups_fit_complete_call_exactly(self):
        for size in (3070, 3071, 3072, 3073):
            value = settings()
            value['trade_profile']['limits']['max_command_bytes'] = size
            capacity = 4 * ((size + 2) // 3) + 1024
            value['control_profile']['max_call_bytes'] = capacity
            self.assertEqual(validate_trade_configuration(value).control_profile.max_call_bytes, capacity)
            value['control_profile']['max_call_bytes'] = capacity - 1
            with self.subTest(size=size), self.assertRaises(ValueError):
                validate_trade_configuration(value)

    def test_result_and_page_need_complete_reply_overhead(self):
        for field, size in (('max_call_result_bytes', 17408), ('max_event_page_bytes', 18432)):
            value = settings()
            value['trade_profile']['limits'][field] = size
            value['control_profile']['max_reply_bytes'] = size + 1024
            self.assertEqual(validate_trade_configuration(value).profile['trade_profile']['limits'][field], size)
            value['control_profile']['max_reply_bytes'] -= 1
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_trade_configuration(value)
        value = settings()
        value['trade_profile']['limits']['max_event_page_bytes'] = 4190208
        with self.assertRaises(ValueError):
            validate_trade_configuration(value)

    def test_original_lifetime_and_fixed_role_reservations(self):
        value = settings(); value['control_profile']['max_call_seconds'] = 7
        validate_trade_configuration(value)
        value['control_profile']['max_call_seconds'] = 6.999
        with self.assertRaises(ValueError):
            validate_trade_configuration(value)
        value = settings(); value['control_profile']['max_pending_calls'] = 3
        with self.assertRaises(ValueError):
            validate_trade_configuration(value)
        value = settings()
        control = validate_trade_configuration(value).control_profile
        reservation = control.reservation(control.max_call_bytes)
        value['control_profile']['max_retained_bytes'] = control.base_bytes + 7 * reservation
        actual = validate_trade_configuration(value).control_profile
        self.assertEqual(actual.call_slots('host'), 4)
        self.assertEqual(actual.call_slots('agent'), 3)
        value['control_profile']['max_retained_bytes'] -= 1
        with self.assertRaises(ValueError):
            validate_trade_configuration(value)

    def test_common_scalar_and_transport_budgets_are_still_enforced(self):
        for name, item in (('max_frame', True), ('max_frame', 4194305),
                           ('max_pending', 0), ('max_result_bytes', 8191),
                           ('execution_timeout_ms', 99), ('io_seconds', float('nan')),
                           ('connect_seconds', True)):
            value = settings(); value[name] = item
            with self.subTest(name=name), self.assertRaises(ValueError):
                validate_trade_configuration(value)
        value = settings(); value['transport']['max_mapped_bytes'] = 1
        with self.assertRaises(ValueError):
            validate_trade_configuration(value)
        value = settings(); value['transport']['kind'] = 'unknown'
        with self.assertRaises(ValueError):
            validate_trade_configuration(value)

    def test_builtin_mapping_includes_both_slots_and_rendezvous(self):
        value = settings()
        frame = value['max_frame']
        required = 256 + 2 * (((64 + frame + 63) // 64) * 64) + 256
        value['transport'] = {'kind': 'builtin-shm', 'schema_version': 'qmt.builtin-shm.v1',
            'name': 'qmt-broker-trade-config', 'max_mapped_bytes': required,
            'poll_seconds': .005, 'windows_session_id': 0}
        # 仅声明布局环境，调用真实布局算法；不创建映射、文件或本机资源。
        with patch.object(builtin_shm.sys, 'platform', 'win32'), \
                patch.object(builtin_shm.sys, 'version', '3.6.8 AMD64'), \
                patch.object(builtin_shm.struct, 'calcsize', return_value=8):
            actual = validate_trade_configuration(value)
            self.assertEqual(actual.value['transport']['max_mapped_bytes'], required)
            value['transport']['max_mapped_bytes'] = required - 1
            with self.assertRaises(ValueError):
                validate_trade_configuration(value)

    def test_configuration_is_pure_and_transport_gets_actual_v4(self):
        layout = read_configuration.validate_transport_profile
        observed = []

        def checked(config, route, maximum, profile):
            observed.append(copy.deepcopy(profile))
            return layout(config, route, maximum, profile)

        with patch.object(read_configuration, 'validate_transport_profile', side_effect=checked), \
                patch('builtins.open', side_effect=AssertionError('file I/O')), \
                patch('threading.Thread', side_effect=AssertionError('thread owner')):
            actual = validate_trade_configuration(settings())
        self.assertEqual(observed, [actual.profile])
        self.assertEqual(observed[0]['control_profile']['schema_version'], '2.0')

    def test_real_peer_three_slots_block_ack_four_allow_one_then_gap_blocks(self):
        for host_slots in (3, 4):
            admitted = validate_trade_configuration(settings())
            profile = admitted.control_profile
            if host_slots == 3:
                # 三槽只作为失败对照，显式绕开完整配置准入构造原ControlProfile。
                config = profile.configuration
                config['max_pending_calls'] = 3
                profile = ControlProfile(config, 262144, TransportBudget(5, 2))
            self.assertEqual(profile.call_slots('host'), host_slots)
            clock = Clock()
            host = ControlPeer('host', '1' * 32, profile, clock.mono, clock.utc)
            agent = ControlPeer('agent', '1' * 32, profile, clock.mono, clock.utc)
            try:
                read = host.submit('agent.read', {'kind': 'read',
                    'body': base64.b64encode(canonical(request(FULL_TICK))).decode('ascii'),
                    'queue_timeout_ms': 1000, 'queue_expires_at': clock.utc() + 1}, clock.expires())
                trade = host.submit('agent.trade', {'kind': 'trade', 'body': insert_body(),
                    'clock_schema': 'qmt.win-uptime-ms.v1', 'deadline_ms': 5000}, clock.expires())
                page = host.submit('agent.trade.events', {'session_id': 'synthetic-session',
                    'after_seq': 0, 'limit': 1, 'max_bytes': 4096}, clock.expires())
                reverse = agent.submit('host.binding.read', {}, clock.expires())
                send(host, agent)
                calls = [agent.take_call(), agent.take_call(), agent.take_call()]
                self.assertEqual([item['call_seq'] for item in calls], [1, 2, 3])
                payload = {'schema_version': 'qmt.trade-event-page.v1',
                    'session_id': 'synthetic-session', 'binding_id': 'synthetic-only',
                    'acknowledged_through': 0, 'published_through': 0, 'gap': None, 'events': []}
                agent.reply(calls[2]['call_seq'], payload)
                send(agent, host)
                self.assertEqual(host.take_call()['operation'], 'host.binding.read')
                self.assertIsNone(read.take())
                self.assertIsNone(trade.take())
                # 这里仅用有限列表代表领域提交完成；不声称已验真实事件持久化。
                committed = [page.take()['payload']]
                self.assertEqual(committed, [payload])
                page.ack()
                self.assertFalse(page.retired)
                batch = host.prepare()
                self.assertFalse(page.retired)
                host.sent(batch)
                agent.receive(batch.packet)
                self.assertTrue(page.retired)
                send(agent, host)
                ack_payload = {'session_id': 'synthetic-session', 'through_seq': 0}
                if host_slots == 3:
                    self.assertFalse(host.can_submit())
                    with self.assertRaises(BufferError):
                        host.submit('agent.trade.ack', ack_payload, clock.expires())
                else:
                    self.assertTrue(host.can_submit())
                    ack = host.submit('agent.trade.ack', ack_payload, clock.expires())
                    send(host, agent)
                    incoming = agent.take_call()
                    self.assertEqual(incoming['operation'], 'agent.trade.ack')
                    self.assertEqual(incoming['call_seq'], 4)
                    self.assertEqual(incoming['payload'], ack_payload)
                    agent.reply(4, {'through_seq': 0})
                    send(agent, host)
                    self.assertEqual(ack.take()['payload'], {'through_seq': 0})
                    ack.ack()
                    send(host, agent)
                    self.assertTrue(ack.retired)
                    send(agent, host)
                    self.assertFalse(host.can_submit())
                    with self.assertRaises(BufferError):
                        host.submit('agent.trade.events', {'session_id': 'synthetic-session',
                            'after_seq': 0, 'limit': 1, 'max_bytes': 4096}, clock.expires())
                self.assertIsNone(reverse.take())
            finally:
                host.close()
                agent.close()


if __name__ == '__main__':
    unittest.main()
