"""账户四查询丢失消费确认后，原期限结束应释放已确认结果的额度。"""
from datetime import datetime, timezone
from pathlib import Path
import tempfile
from types import SimpleNamespace
import time
import unittest
from uuid import uuid4

from guanheng_qmt_shm_agent.account_query import AccountQueryAdapter
from guanheng_qmt_shm_agent.control_messages import host_binding
from guanheng_qmt_shm_agent.protocol import canonical
from guanheng_qmt_shm_agent.read_capabilities import build_read_profile
from guanheng_qmt_shm_agent.read_retention import content_id, ReadTicketEnded
from guanheng_qmt_shm_agent.results import finalize_result
from guanheng_qmt_shm.bound import digest
from guanheng_qmt_shm.journal import JournalFull
from guanheng_qmt_shm.read_retention_journal import RetainedAccountJournal, RetainedTradingJournal


class AccountExpiryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / 'account.sqlite'
        self.uptime = 10.0
        self.clock = SimpleNamespace(seconds=lambda: self.uptime)
        self.route = dict(route_id='account-expiry', executor_id='synthetic', route_epoch=1)
        self.limits = dict(schema_version='qmt.account-read.v1', account_binding=dict(
            account_id='SYNTHETIC', account_environment='live', currency='CNY',
            financial_profile='cny_cash_shsz_v1'), max_rows=4096, max_nodes=65536,
            max_scalar_chars=262144, max_data_bytes=8192)
        control = dict(schema_version='1.0', max_pending_calls=1, max_call_bytes=8192,
            max_reply_bytes=327680, max_retained_bytes=1048576, max_cycle_messages=4,
            max_cycle_bytes=524288, poll_seconds=0.01, max_call_seconds=3)
        self.profile = build_read_profile(['account.trade_detail', 'market.full_tick'], 1000, control,
            {'account.trade_detail': dict(policy_id='qmt.account-read.v1', policy_version='1.0',
                execution_timeout_ms=1000, limits=self.limits),
             'market.full_tick': dict(policy_id='qmt.standard-read.v1', policy_version='1.0',
                execution_timeout_ms=1000, limits={})}, max_result_bytes=16384,
            read_retention=dict(schema='qmt.read-retention.v1', max_lifetime_ms=5000))
        self.binding = host_binding(route=self.route, generation='c'*32,
            host_instance_id='a'*32, journal_generation=None, observation_identity=None,
            capability_sha256=digest(canonical(self.profile)))
        self.journal = self.open()
        self.addCleanup(lambda: self.journal.close())
        self.submitted = {}

    def open(self):
        return RetainedAccountJournal(self.path, self.route, max_records=2,
            max_result_bytes=16384, max_request_bytes=4096,
            max_journal_bytes=2*(4096+16384+16384), read_profile=self.profile, clock=self.clock)

    def submit(self, datatype='position', outcome='success'):
        ticket = dict(schema='qmt.read-ticket.v1', epoch='a'*32,
            expires_ms=int(self.uptime*1000)+1000)
        request = dict(correlation_id=str(uuid4()), operation_id='account.trade_detail',
            arguments=dict(account_type='stock', datatype=datatype, scope='account'),
            timeout_ms=1000, policy_id='qmt.account-read.v1', policy_version='1.0',
            priority_class='normal')
        request['request_id'] = content_id(request, ticket)
        rid = self.journal.submit_ticket(canonical(request), self.binding, ticket, queue_timeout_ms=5000)
        self.submitted[rid] = (canonical(request), ticket)
        self.assertEqual(self.journal.claim_bound(self.binding)[0], rid)
        if outcome == 'unknown':
            self.journal.interrupt_bound(rid, 'account.trade_detail')
        elif outcome == 'success':
            rows = [SimpleNamespace(m_dBalance=1000000, m_dAvailable=1000000)] if datatype == 'account' else []
            adapter = AccountQueryAdapter(lambda *args: rows, self.limits, 16384,
                utc_now=lambda: datetime(2026, 11, 20, tzinfo=timezone.utc))
            result = finalize_result(dict(request_id=rid, operation_id='account.trade_detail',
                ok=True, data=adapter.execute(request['arguments'], time.monotonic()+2),
                completed_at='2026-11-20T00:00:00Z'), 16384)
            self.journal.finish_bound(rid, result, self.binding)
        return rid

    def test_expired_confirmed_results_without_ack_allow_next_four_queries_after_reopen(self):
        originals = [self.submit(), self.submit('order')]
        with self.assertRaises(JournalFull):
            self.submit('deal')
        self.journal.close()
        self.journal = self.open()
        self.uptime += 2
        for datatype in ('position', 'order', 'deal', 'account'):
            rid = self.submit(datatype)
            self.assertEqual(self.journal.get_bound(rid)['state'], 'terminal')
            self.uptime += 2
        self.assertTrue(all(self.journal.get_bound(rid) is None for rid in originals))
        self.assertEqual(self.journal.retention_status('a'*32)['retained'], 0)
        for rid in originals:
            body, ticket = self.submitted[rid]
            with self.assertRaises(ReadTicketEnded):
                self.journal.submit_ticket(body, self.binding, ticket, queue_timeout_ms=5000)
        self.assertEqual(self.journal.retention_status('a'*32)['retained'], 0)

    def test_expired_unknown_and_executing_requests_keep_original_identity(self):
        unknown = self.submit(outcome='unknown')
        executing = self.submit(outcome='executing')
        before = {rid: self.journal.get_bound(rid) for rid in (unknown, executing)}
        self.uptime += 2
        status = self.journal.retention_status('a'*32)
        self.assertEqual(status['held_unknown'], 1)
        self.assertEqual(status['queued_or_running'], 1)
        with self.assertRaises(JournalFull):
            self.submit('deal')
        self.assertEqual({rid: self.journal.get_bound(rid) for rid in before}, before)

    def test_financial_query_proof_survives_expiry_until_its_owner_releases_reference(self):
        # 直接复用交易 owner 的查询证明判定，核对实际 SQL 引用闭包。
        self.journal._read_held_by_financial_proof = lambda db, rid: (
            RetainedTradingJournal._read_held_by_financial_proof(self.journal, db, rid))
        self.journal._retention_extra_counts = lambda: RetainedTradingJournal._retention_extra_counts(self.journal)
        with self.journal._transaction() as db:
            db.execute('CREATE TABLE trade_order_links(query_request_id TEXT)')
        rid = self.submit('order')
        original = self.journal.get_bound(rid)
        with self.journal._transaction() as db:
            db.execute('INSERT INTO trade_order_links VALUES(?)', (rid,))
        self.uptime += 2
        self.assertEqual(self.journal.retention_status('a'*32)['retained'], 1)
        self.assertEqual(self.journal.get_bound(rid), original)
        with self.journal._transaction() as db:
            db.execute('DELETE FROM trade_order_links WHERE query_request_id=?', (rid,))
        self.assertEqual(self.journal.retention_status('a'*32)['retained'], 0)

    def test_confirmed_unconsumed_result_stays_available_before_original_deadline(self):
        rid = self.submit()
        original = self.journal.get_bound(rid)
        self.uptime += .5
        self.assertEqual(self.journal.retention_status('a'*32)['awaiting_consumer'], 1)
        self.assertEqual(self.journal.get_bound(rid), original)

    def test_other_operations_still_require_consumer_ack_after_expiry(self):
        ticket = dict(schema='qmt.read-ticket.v1', epoch='a'*32, expires_ms=11000)
        request = dict(correlation_id=str(uuid4()), operation_id='market.full_tick',
            arguments=dict(stocks=['510300.SH']), timeout_ms=1000,
            policy_id='qmt.standard-read.v1', policy_version='1.0', priority_class='normal')
        request['request_id'] = content_id(request, ticket)
        rid = self.journal.submit_ticket(canonical(request), self.binding, ticket, queue_timeout_ms=5000)
        self.assertEqual(self.journal.claim_bound(self.binding)[0], rid)
        result = finalize_result(dict(request_id=rid, operation_id='market.full_tick',
            ok=False, error_code='capability_unavailable', error_message='synthetic unavailable',
            completed_at='2026-11-20T00:00:00Z'), 16384)
        self.journal.finish_bound(rid, result, self.binding)
        original = self.journal.get_bound(rid)
        self.uptime += 2
        self.assertEqual(self.journal.retention_status('a'*32)['awaiting_consumer'], 1)
        self.assertEqual(self.journal.get_bound(rid), original)


if __name__ == '__main__':
    unittest.main()
