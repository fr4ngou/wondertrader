"""原SDK异常→真实完整ORDER投影→原Journal/Host准入→后继SDK；全部为显式替身。"""
import copy
import time
from uuid import uuid4

from guanheng_qmt_shm_agent.account_query import AccountQueryAdapter
from guanheng_qmt_shm_agent.protocol import canonical, decode
from guanheng_qmt_shm_agent.results import finalize_result
from guanheng_qmt_shm_agent.trade_service import SourceTradingService
from guanheng_qmt_shm.trade_bound import HostTradeRequest
from test_order_query_recovery import OrderQueryRecoveryTests
from test_trade_account_projection import query, NOW
from test_trade_service import command, payload


class UnknownOrderResolutionTests(OrderQueryRecoveryTests):
    def begin_unknown(self):
        self.calls = []

        def insert(*args):
            self.calls.append(args)
            if len(self.calls) == 1:
                raise RuntimeError('synthetic SDK accepted before exception')
            return None

        self.service = SourceTradingService(self.context, self.admitted, passorder=insert,
            cancel=lambda *unused: True, clock=self.clock, monotonic=time.monotonic,
            session_id='runtime-source')
        self.actual = self.ready(service=self.service)
        original = command()
        self.assertEqual(self.owner.request(self.request_command(original)).status_code, 202)
        self.execute_original(original)
        self.assertTrue(self.service.status()['unknown_fenced'])
        self.assertFalse(self.owner.accepting_commands)
        return original, self.journal.get_trade(original['command_id'], deadline=self.deadline())

    def execute_original(self, value):
        claimed = self.owner.claim_trade(self.actual, deadline=self.deadline())
        self.assertEqual(claimed['command_id'], value['command_id'])
        completed = self.service.enqueue(payload(value, deadline_ms=14000), self.deadline())
        self.assertTrue(self.service.tick())
        result = decode(completed.poll())
        saved = self.journal.finish_trade(value['command_id'], result, self.actual,
                                         deadline=self.deadline())
        self.owner.note_trade_record(saved, deadline=self.deadline())
        self.owner.observe_source(self.service.status(), None,
                                  self.journal.trade_admission(deadline=self.deadline()))
        return saved

    def actual_order_query(self, rows):
        request = query(); request['request_id'] = str(uuid4())
        limits = self.admitted.profile['operation_profiles']['account.trade_detail']['limits']
        adapter = AccountQueryAdapter(lambda *unused: rows, limits, 16384,
            utc_now=lambda: NOW, projection_version=2,
            observe_result=self.service.observe_account_result)
        rid = self.journal.submit_bound(canonical(request), self.actual, queue_timeout_ms=5000)
        self.assertEqual(self.journal.claim_bound(self.actual)[0], rid)
        data = adapter.execute(request['arguments'], self.deadline())
        result = finalize_result(dict(request_id=rid, operation_id='account.trade_detail', ok=True,
            completed_at=NOW.isoformat().replace('+00:00', 'Z'), data=data), 16384)
        self.journal.finish_bound(rid, result, self.actual)
        self.owner.observe_source(self.service.status(), None,
                                  self.journal.trade_admission(deadline=self.deadline()))
        return decode(self.owner.request(HostTradeRequest('trade.status')).content)

    def terminal_row(self, original):
        return self.order_row(original, m_nOrderStatus=56, m_nVolumeTraded=100, m_nVolumeTotal=0)

    def test_sdk_exception_terminal_query_keeps_original_and_executes_next_insert_once(self):
        original, unknown = self.begin_unknown()
        self.assertEqual(unknown['state'], 'unknown')
        self.assertTrue(unknown['source_result']['sdk_entered'])
        status = self.actual_order_query([self.terminal_row(original)])
        self.assertFalse(status['unknown_fenced'])
        self.assertTrue(status['accepting_commands'])
        self.assertFalse(self.service.status()['unknown_fenced'])
        self.assertEqual(self.journal.get_trade(original['command_id'], deadline=self.deadline()), unknown)
        self.owner.note_trade_record(unknown, deadline=self.deadline())
        self.assertTrue(self.owner.accepting_commands)
        # 相同原身份始终取原unknown结果，实际副作用保持一次。
        prior = self.service.enqueue(payload(original), self.deadline())
        self.assertEqual(decode(prior.poll()), unknown['source_result'])
        self.assertEqual(len(self.calls), 1)
        following = command(2); following['quantity'] = 200
        self.assertEqual(self.owner.request(self.request_command(following)).status_code, 202)
        self.assertEqual(self.execute_original(following)['state'], 'sdk_returned')
        self.assertEqual([args[6] for args in self.calls], [100, 200])
        self.reopen()
        self.assertFalse(self.journal.trade_admission(deadline=self.deadline())['unknown_fenced'])
        self.assertEqual(self.journal.get_trade(original['command_id'], deadline=self.deadline()), unknown)

    def test_absent_active_or_partial_order_stays_unknown(self):
        original, unknown = self.begin_unknown()
        self.check_unresolved(original, unknown, [[], [self.order_row(original)],
            [self.order_row(original, m_nVolumeTraded=0, m_nVolumeTotal=100, m_nOrderStatus=50)]])

    def test_duplicate_or_changed_order_stays_unknown(self):
        original, unknown = self.begin_unknown()
        terminal = self.terminal_row(original)
        changes = ({'m_nVolumeTotalOriginal': 200}, {'m_nOffsetFlag': 49},
                   {'m_dLimitPrice': 10.02})
        rows = [[terminal, copy.deepcopy(terminal)]]
        rows.extend([[dict(terminal, **change)] for change in changes])
        missing = dict(terminal); del missing['m_dLimitPrice']; rows.append([missing])
        self.check_unresolved(original, unknown, rows)

    def check_unresolved(self, original, unknown, rows):
        for index, current in enumerate(rows):
            with self.subTest(case=index):
                status = self.actual_order_query(current)
                self.assertTrue(status['unknown_fenced'])
                self.assertFalse(status['accepting_commands'])
                self.assertTrue(self.service.status()['unknown_fenced'])
                self.assertEqual(len(self.calls), 1)
                self.assertEqual(self.journal.get_trade(original['command_id'], deadline=self.deadline()), unknown)

    def test_later_hard_fault_survives_terminal_order_reconciliation(self):
        original, unknown = self.begin_unknown()
        self.service._stop_writes('handoff_failed')
        status = self.actual_order_query([self.terminal_row(original)])
        self.assertFalse(status['accepting_commands'])
        self.assertEqual(status['source_status']['hard_fault'], {'code': 'handoff_failed'})
        self.assertEqual(status['hard_fault'], {'code': 'handoff_failed'})
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.journal.get_trade(original['command_id'], deadline=self.deadline()), unknown)
