"""失败 RPC 回报落诊断，原命令仍交给既有 Journal 中断处理。"""
from contextlib import redirect_stderr
from concurrent.futures import Future
import base64
from hashlib import sha256
from io import StringIO
import sqlite3
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from uuid import uuid4

from guanheng_qmt_shm.control_trading import HostTradingControlLoop
from guanheng_qmt_shm.control import HostControlLoop
from guanheng_qmt_shm.journal import interrupted
from guanheng_qmt_shm_agent.protocol import canonical
from guanheng_qmt_shm_agent.results import finalize_result


class TradeReplyDiagnostic(unittest.TestCase):
    def test_failed_reply_logs_once_and_retries_only_the_original_journal_handoff(self):
        for code, delivery in (('binding_closed', 'unknown'), ('call_expired', 'not_sent'),
                               ('capability_unavailable', 'replied')):
            with self.subTest(code=code):
                owner = HostTradingControlLoop.__new__(HostTradingControlLoop)
                command = str(uuid4())
                owner._trade_active = {'command_id': command}
                owner._trade_future = Mock()
                owner._trade_future.take.return_value = {'ok': False, 'payload': None,
                    'error': {'code': code, 'message': 'PRIVATE'}, 'delivery': delivery}
                owner._jobs = {}
                owner._trade_received = owner._trade_result_deadline = None
                owner._result_deadline = Mock(return_value=100)
                owner._job = Mock()
                output = StringIO()
                with redirect_stderr(output):
                    owner._collect_trade()
                    owner._collect_trade()  # Journal 暂忙，第二次只尝试交接原值。
                owner._trade_future.take.assert_called_once_with()
                expected = f'GH_TRADE_REPLY_INTERRUPTED {code} {delivery} {sha256(command.encode()).hexdigest()}\n'
                self.assertEqual(output.getvalue(), expected)
                self.assertEqual(len(owner._job.call_args_list), 2)
                for call in owner._job.call_args_list:
                    self.assertEqual(call.args, ('trade', 'trade.interrupt', {'command_id': command}, 100))

    def test_account_read_finish_timeout_reconciles_original_before_ack(self):
        for original_committed in (False, True):
            with self.subTest(original_committed=original_committed):
                owner = HostControlLoop.__new__(HostControlLoop)
                owner._wake = threading.Event()
                owner._binding = canonical({'source_generation': 2})
                owner.domain_failed = owner._read_timeout_reported = False
                owner._read_scan = owner._read_reconcile = owner._read_rejection = None
                request_id = str(uuid4())
                operation = 'account.trade_detail'
                raw = canonical({'operation_id': operation})
                original = {'request_id': request_id, 'ok': True}
                record = {'state': 'terminal' if original_committed else 'executing',
                    'operation_id': operation, 'dispatch_binding': owner.binding,
                    'request_body_sha256': sha256(raw).hexdigest(), 'result_binding': owner.binding,
                    'result_body_b64': base64.b64encode(canonical(original)).decode('ascii')}
                journal = Mock(max_result_bytes=4096)
                journal.get_bound.return_value = record
                owner.runtime = SimpleNamespace(journal=journal, _stop=threading.Event(),
                                                budget=SimpleNamespace(io_seconds=2))
                owner._domain = owner._make_domain()
                owner.active = (request_id, raw, 10, 'unused')
                owner.read_future = Mock()
                owner._read_commit_payload = dict(request_id=request_id, result=original, deadline=10)
                owner._read_commit = Future()
                owner._read_commit.set_exception(TimeoutError('original Journal budget expired'))
                output = StringIO()
                try:
                    with redirect_stderr(output):
                        owner._progress_domain()
                        owner.read_future.ack.assert_not_called()
                        owner._read_reconcile.result(timeout=2)
                        owner._progress_domain()
                    owner.read_future.ack.assert_called_once_with()
                    journal.get_bound.assert_called_once()
                    self.assertEqual(journal.get_bound.call_args.args, (request_id,))
                    journal.finish_bound.assert_not_called()
                    self.assertEqual(journal.interrupt_bound.call_count, int(not original_committed))
                    self.assertIsNone(owner.active)
                    self.assertIn('commit_timeout', output.getvalue())
                    self.assertIn('original_result_already_terminal' if original_committed
                                  else 'original_request_interrupted', output.getvalue())
                finally:
                    owner._domain.close(2)

    def test_account_read_reconciliation_timeout_retains_original_until_next_attempt(self):
        locked = sqlite3.OperationalError('database locked')
        locked.sqlite_errorcode = sqlite3.SQLITE_BUSY
        for error in (TimeoutError('reconciliation'), locked):
            with self.subTest(error=type(error).__name__):
                owner = HostControlLoop.__new__(HostControlLoop)
                request = canonical({'operation_id': 'account.trade_detail'})
                original = {'request_id': str(uuid4()), 'result': {}, 'deadline': 10}
                owner.active = (original['request_id'], request, 10, 'unused')
                owner._read_scan = owner._read_rejection = None
                owner._read_timeout_reported = False
                owner._read_commit = Future()
                owner._read_commit.set_exception(TimeoutError('original persistence'))
                owner._read_commit_payload = original
                owner._read_reconcile = Future()
                owner._read_reconcile.set_exception(error)
                owner.runtime = SimpleNamespace(_stop=threading.Event(), budget=SimpleNamespace(io_seconds=2))
                owner._domain = Mock()
                owner.read_future = Mock()
                successor = Future()
                owner._domain.submit.return_value = successor
                with redirect_stderr(StringIO()) as output:
                    owner._progress_domain()
                    self.assertIs(owner._read_commit_payload, original)
                    owner.read_future.ack.assert_not_called()
                    owner._progress_domain()
                    successor.set_result('original_result_already_terminal')
                    owner._progress_domain()
                self.assertIsNone(owner.active)
                self.assertIs(owner._domain.submit.call_args.args[1]['finish'], original)
                owner.read_future.ack.assert_called_once_with()
                self.assertIn('reconcile_timeout', output.getvalue())
                self.assertIn('original_result_already_terminal', output.getvalue())

    def test_close_checks_interrupt_committed_before_reconciliation_timeout(self):
        owner = HostControlLoop.__new__(HostControlLoop)
        owner._binding = canonical({'source_generation': 2})
        request_id = str(uuid4())
        operation = 'account.trade_detail'
        request = canonical({'operation_id': operation})
        journal = Mock(max_result_bytes=4096)
        result = interrupted(request_id, operation, 'operation_interrupted')
        result['completed_at'] = '2026-11-12T06:27:16+00:00'
        closed = finalize_result(result, 4096)
        journal.get_bound.return_value = {'state': 'terminal', 'operation_id': operation,
            'dispatch_binding': owner.binding, 'request_body_sha256': sha256(request).hexdigest(),
            'result_binding': None, 'result_body_b64': base64.b64encode(canonical(closed)).decode('ascii')}
        owner.runtime = SimpleNamespace(journal=journal)
        owner.active = (request_id, request, 10, 'unused')
        reply = owner.read_future = Mock(retired=True)
        owner._read_commit_payload = dict(request_id=request_id, result={'ok': True}, deadline=10)
        owner._read_commit, owner._read_reconcile = Future(), Future()
        owner._read_commit.set_exception(TimeoutError('original deadline'))
        owner._read_reconcile.set_exception(TimeoutError('reconciliation after commit'))
        self.assertTrue(owner._reconcile_timed_out_read_finish(20))
        journal.get_bound.assert_called_once_with(request_id, deadline=20)
        journal.interrupt_bound.assert_not_called()
        reply.ack.assert_not_called()
        self.assertEqual(owner._abandoned_read_commit['outcome'], 'original_request_interrupted')
