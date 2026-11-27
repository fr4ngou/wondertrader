"""覆盖组合部署的读取额度回收与状态身份核验。"""
from pathlib import Path
from runpy import run_path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4

from guanheng_qmt_shm import bound
from guanheng_qmt_shm.auth import HMACVerifier
from guanheng_qmt_shm.read_retention_journal import RetainedPreparationJournal, RetainedReadJournal
from guanheng_qmt_shm_agent.control_messages import host_binding
from guanheng_qmt_shm_agent.history_preparation import CLOCK_SCHEMA, OPERATION, validate_configuration
from guanheng_qmt_shm_agent.protocol import canonical, decode
from guanheng_qmt_shm_agent.read_configuration import validate_read_configuration
from guanheng_qmt_shm_agent.read_retention import CONSUMED, TICKET, content_id, now_ms
from guanheng_qmt_shm_agent.results import finalize_result


REPO = Path(__file__).resolve().parents[3]
EXAMPLES = REPO / 'connectors' / 'qmt_shm' / 'examples'
MARKET = run_path(str(REPO / 'scripts' / 'qmt_readonly_market.py'))


def make_binding(route, profile):
    return host_binding(route=route, generation='c' * 32, host_instance_id='a' * 32,
                        journal_generation=None, observation_identity=None,
                        capability_sha256=bound.digest(canonical(profile)),
                        schema_version=profile['control_profile']['schema_version'])


class MarketOnboardingTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.profile = decode((EXAMPLES / 'qmt-readonly-market.example.json').read_bytes())
        self.account = decode((EXAMPLES / 'qmt-trade-config.example.json').read_bytes())
        self.policy, = decode((EXAMPLES / 'qmt-operation-policy.example.json').read_bytes())['policies']
        self.seconds = 1000.
        self.clock = SimpleNamespace(seconds=lambda: self.seconds)

    def configuration(self, role):
        contracts = MARKET['role_contracts'](self.profile)
        # 替换创建期 ACL 入口，保留生产策略原字节与 Host/Agent 配置准入。
        with patch('guanheng_qmt_shm.private_files.write_private_new', Path.write_bytes):
            return MARKET['build_configuration'](
                self.account, role, contracts[role], self.profile['ports'][role], self.root, self.policy)

    def submit(self, journal, binding, operation, arguments, expiry):
        descriptor = journal.admission_profile['operation_profiles'][operation]
        request = dict(request_id=str(uuid4()), correlation_id=str(uuid4()), operation_id=operation,
                       arguments=arguments, timeout_ms=descriptor['execution_timeout_ms'],
                       policy_id=descriptor['policy_id'], policy_version='1.0', priority_class='normal')
        ticket = dict(schema=TICKET, epoch=binding['host_instance_id'], expires_ms=expiry)
        request['request_id'] = content_id(request, ticket)
        rid = journal.submit_ticket(canonical(request), binding, ticket, queue_timeout_ms=2500)
        journal.claim_bound(binding)
        return rid, request

    def test_consumed_history_and_analysis_keep_serving_past_record_limit(self):
        cases = (
            ('history', RetainedPreparationJournal, validate_configuration, 'market.full_tick',
             {'stocks': ['510300.SH']}),
            ('analysis', RetainedReadJournal, validate_read_configuration, 'market.divid_factors',
             {'symbol': '510300.SH'}),
        )
        for role, journal_type, validate, operation, arguments in cases:
            with self.subTest(role=role):
                config, _, settings = self.configuration(role)
                profile = validate(settings).profile
                binding = make_binding(config['route'], profile)
                epoch = binding['host_instance_id']
                size = config['max_result_bytes']
                records = config['max_records']
                max_request = config['max_journal_bytes'] // records - size - bound.MAX_METADATA_BYTES
                journal = journal_type(Path(config['journal_path']), config['route'], max_records=records,
                    max_result_bytes=size, max_request_bytes=max_request, max_journal_bytes=config['max_journal_bytes'],
                    read_profile=profile, clock=self.clock)
                self.addCleanup(journal.close)
                if role == 'history':
                    expiry = now_ms(self.clock) + 1000
                    unknown, _ = self.submit(journal, binding, OPERATION, dict(
                        symbol='510300.SH', period='1m', start_time='20261126093100', end_time='20261126093600',
                        clock_schema=CLOCK_SCHEMA, deadline_ms=expiry), expiry)
                    journal.interrupt_bound(unknown, OPERATION)
                    self.seconds += 2.
                for index in range(records + 2):
                    expiry = now_ms(self.clock) + 1000
                    rid, request = self.submit(journal, binding, operation, arguments, expiry)
                    result = finalize_result(dict(request_id=rid, operation_id=operation, ok=True,
                                                  data={}, completed_at='2026-11-27T00:00:00Z'), size)
                    journal.finish_bound(rid, result, binding)
                    # 保留一期未确认消费的成功终态；票据结束后仍必须可回读。
                    if index == 0:
                        unconsumed = rid
                    else:
                        saved = journal.consumed(rid, dict(schema=CONSUMED,
                            request_body_sha256=bound.digest(canonical(request)),
                            result_body_sha256=bound.digest(canonical(result))), epoch)
                        self.assertTrue(saved['retained'])
                    self.seconds += 2.
                counts = journal.retention_status(epoch)
                self.assertEqual(counts['awaiting_consumer'], 1)
                self.assertIsNotNone(journal.get_bound(unconsumed))
                self.assertIsNone(journal.get_bound(rid))
                if role == 'history':
                    self.assertEqual(counts['held_unknown'], 1)
                    self.assertIsNotNone(journal.get_bound(unknown))
                else:
                    self.assertEqual(counts['held_unknown'], 0)

    def test_status_rejects_nonsuccess_or_unmatched_binding(self):
        config, credentials, settings = self.configuration('analysis')
        profile = validate_read_configuration(settings).profile
        keys = credentials['http_keys']
        verifier = HMACVerifier(keys.get)
        expected_binding = make_binding(config['route'], profile)

        def metadata(binding, actual_profile):
            body = canonical(actual_profile)
            return dict(schema_version=bound.SCHEMA, binding=binding, binding_sha256=bound.digest(canonical(binding)),
                        read_profile_body_b64=bound.b64(body), read_profile_body_sha256=bound.digest(body),
                        order_ready=False)

        wrong_route = dict(config['route'], route_epoch=config['route']['route_epoch'] + 1)
        wrong_profile = dict(profile, execution_timeout_ms=1000)
        checks = (
            (200, metadata(expected_binding, profile), True),
            (503, metadata(expected_binding, profile), False),
            (200, metadata(make_binding(wrong_route, profile), profile), False),
            (200, metadata(make_binding(config['route'], wrong_profile), wrong_profile), False),
            (200, dict(status='available', lifecycle='connected'), False),
        )
        for code, body, accepted in checks:
            with self.subTest(code=code, accepted=accepted), patch('http.client.HTTPConnection') as connection:
                def request(method, url, *, headers):
                    self.assertEqual(url, '/internal/v1/read-binding')
                    verifier.verify(method, url, headers)

                host = connection.return_value
                host.request.side_effect = request
                host.getresponse.return_value = SimpleNamespace(status=code, read=lambda _: canonical(body))
                status = MARKET['binding_status'](config, keys, profile)
                self.assertEqual(status['binding_verified'], accepted)
                self.assertEqual(status['status'], 'available' if accepted else 'reachable')


if __name__ == '__main__':
    unittest.main()
