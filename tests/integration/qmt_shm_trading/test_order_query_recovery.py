"""R21Q：原SQLite查询事务到恢复撤单；仅定义替身测试，SDK/运输启动为零。"""
from contextlib import closing
from concurrent.futures import Future
import copy
import sqlite3
import time
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace
from uuid import uuid4

from guanheng_qmt_shm_agent.account_query import AccountQueryAdapter
from guanheng_qmt_shm_agent.protocol import canonical, decode
from guanheng_qmt_shm_agent.results import finalize_result
from guanheng_qmt_shm.journal import JournalConflict
from guanheng_qmt_shm.control import HostControlLoop
from guanheng_qmt_shm.trade_bound import encode_trade_order_reference
import test_host_trade_runtime as runtime
import test_trade_order_links as link_fixtures
from test_trade_account_projection import query, NOW
from test_trading_journal import commit_failure


class OrderQueryRecoveryTests(runtime.RuntimeFixture):
    deadline = link_fixtures.TradeOrderLinkTests.deadline
    insert = link_fixtures.TradeOrderLinkTests.insert
    finish = link_fixtures.TradeOrderLinkTests.finish
    lookup = link_fixtures.TradeOrderLinkTests.lookup
    event_page = link_fixtures.TradeOrderLinkTests.event_page
    observe = link_fixtures.TradeOrderLinkTests.observe
    cancel = link_fixtures.TradeOrderLinkTests.cancel
    request_command = link_fixtures.TradeOrderLinkTests.request_command
    reopen = link_fixtures.TradeOrderLinkTests.reopen

    def setUp(self):
        original = runtime.agent_config
        def config():
            value = original()
            value['operation_profiles']['account.trade_detail']['policy_version'] = '2.0'
            return value
        with patch.object(runtime, 'agent_config', config):
            super().setUp()
        self.actual = self.ready()

    def new_source(self):
        self.owner = self.make_owner()
        self.service = self.make_service(session='query-recovered-source')
        self.actual = self.ready(self.owner, self.service)

    def order_row(self, value, **changes):
        row = dict(m_strAccountID='SYNTHETIC', m_strInstrumentID='000001',
            m_strExchangeID='SZ', m_strRemark=value['sdk_user_order_id'],
            m_strOrderSysID='broker-1', m_strOrderRef='ref-1',
            m_strInsertDate='20261023', m_strInsertTime='09:30:00',
            m_nVolumeTotalOriginal=100, m_nVolumeTraded=20, m_nVolumeTotal=80,
            m_nOrderStatus=55, m_nOffsetFlag=48, m_dLimitPrice=10.01)
        row.update(changes)
        return row

    def prepare_query(self, rows, datatype='order', actual=None):
        actual = self.actual if actual is None else actual
        request = query(datatype); request['request_id'] = str(uuid4())
        limits = self.admitted.profile['operation_profiles']['account.trade_detail']['limits']
        source = AccountQueryAdapter(lambda *unused: rows, limits, 16384,
            clock=lambda: 0, utc_now=lambda: NOW, projection_version=2)
        data = source.execute(request['arguments'], 10)
        result = finalize_result(dict(request_id=request['request_id'],
            operation_id='account.trade_detail', ok=True,
            completed_at=NOW.isoformat().replace('+00:00', 'Z'), data=data), 16384)
        rid = self.journal.submit_bound(canonical(request), actual, queue_timeout_ms=5000)
        self.assertEqual(self.journal.claim_bound(actual)[0], rid)
        return rid, result, actual

    def observe_query(self, rows, datatype='order'):
        rid, result, actual = self.prepare_query(rows, datatype)
        self.journal.finish_bound(rid, result, actual)
        return rid, result

    def test_new_source_query_refreshes_cancel_without_callback_and_keeps_old_event(self):
        value, unused = self.insert(); self.finish(value); self.observe(value)
        old = self.lookup(value)
        self.new_source()
        denied = self.owner.request(self.request_command(self.cancel(value)))
        self.assertEqual(denied.status_code, 503)
        rid, result = self.observe_query([self.order_row(value)])
        actual = self.lookup(value)
        self.assertEqual(actual['source'], old['source'])
        self.assertEqual(actual['source_sequence'], old['source_sequence'])
        self.assertEqual(actual['query_observation'], dict(request_id=rid,
            result_sha256=result['result_sha256'], row_index=0, host_binding=self.actual))
        self.assertEqual(actual['schema_version'], 'qmt.trade-order-reference.v2')
        wire = decode(encode_trade_order_reference(actual, max_command_bytes=4096, max_result_bytes=1024))
        self.assertEqual(wire['query_observation'], actual['query_observation'])
        accepted = self.owner.request(self.request_command(self.cancel(value)))
        self.assertEqual(accepted.status_code, 202)
        self.assertIsNone(self.journal.get_trade(self.cancel(value)['command_id'], deadline=self.deadline())['dispatch_binding'])

    def test_query_alone_proves_dispatched_insert_and_source_row_index_survives_reopen(self):
        value, unused = self.insert(); self.finish(value)
        rid, result = self.observe_query([self.order_row(value, m_strRemark='external'), self.order_row(value)])
        before = self.lookup(value)
        self.assertIsNone(before['source']); self.assertIsNone(before['source_sequence'])
        self.assertEqual(before['query_observation']['row_index'], 1)
        self.reopen()
        self.assertEqual(self.lookup(value), before)
        self.assertEqual(self.journal.get_bound(rid)['state'], 'terminal')

    def test_old_get_cannot_refresh_new_source(self):
        value, unused = self.insert(); self.finish(value)
        rid, unused = self.observe_query([self.order_row(value)])
        before = self.lookup(value); self.new_source()
        self.journal.get_bound(rid)
        self.assertEqual(self.lookup(value), before)
        self.assertEqual(self.owner.request(self.request_command(self.cancel(value))).status_code, 503)

    def test_undispatched_and_unknown_tokens_never_acquire_broker(self):
        value, unused = self.insert()
        self.observe_query([self.order_row(value), self.order_row(value, m_strRemark='unregistered')])
        actual = self.lookup(value)
        self.assertEqual(actual['schema_version'], 'qmt.trade-order-reference.v1')
        self.assertIsNone(actual['broker_order_id'])

    def test_broker_conflict_is_sticky_and_proved_by_retained_query_after_reopen(self):
        value, unused = self.insert(); self.finish(value); self.observe(value)
        self.observe_query([self.order_row(value, m_strOrderSysID='other-broker')])
        actual = self.lookup(value)
        self.assertEqual(actual['association_error'], 'broker_identity_conflict')
        self.assertEqual(actual['broker_order_id'], 'broker-1')
        self.reopen(); self.assertEqual(self.lookup(value), actual)

    def test_same_token_conflicting_rows_and_symbol_are_rejected(self):
        value, unused = self.insert(); self.finish(value)
        self.observe_query([self.order_row(value), self.order_row(value, m_strOrderSysID='other')])
        self.assertEqual(self.lookup(value)['association_error'], 'broker_identity_conflict')

    def test_exact_token_wrong_symbol_latches_real_query_conflict(self):
        value, unused = self.insert(); self.finish(value)
        self.observe_query([self.order_row(value, m_strInstrumentID='000002')])
        before = self.lookup(value)
        self.assertEqual(before['association_error'], 'symbol_mismatch')
        self.assertIsNone(before['broker_order_id'])
        self.reopen(); self.assertEqual(self.lookup(value), before)

    def test_reused_broker_on_other_date_does_not_merge_complete_tokens(self):
        first, unused = self.insert(1); self.finish(first)
        second, unused = self.insert(2); self.finish(second)
        self.observe_query([self.order_row(first,m_strInsertDate='20261022'),
                            self.order_row(second,m_strInsertDate='20261023')])
        a, b = self.lookup(first), self.lookup(second)
        self.assertEqual(a['broker_order_id'],b['broker_order_id'])
        self.assertNotEqual(a['insert']['command_id'],b['insert']['command_id'])
        self.assertEqual((a['query_observation']['row_index'],b['query_observation']['row_index']),(0,1))

    def test_query_account_mismatch_rolls_back_result_and_proof(self):
        value, unused = self.insert(); self.finish(value)
        rid, result, actual = self.prepare_query([self.order_row(value)])
        # 源adapter本身已拒绝错账户；此项显式篡改有限运输结果后重新封摘要，核Host边界。
        result['data']['rows'][0]['m_strAccountID']='OTHER'
        result=finalize_result(result,16384)
        with self.assertRaises(JournalConflict): self.journal.finish_bound(rid, result, actual)
        self.assertEqual(self.journal.get_bound(rid)['state'], 'executing')
        self.assertIsNone(self.lookup(value)['broker_order_id'])

    def test_failed_query_and_deal_query_do_not_publish_order_proof(self):
        value, unused = self.insert(); self.finish(value)
        rid, result, actual = self.prepare_query([self.order_row(value)])
        failed = finalize_result(dict(result, ok=False, data=None,
            error_code='operation_failed', error_message='synthetic failure'), 16384)
        self.journal.finish_bound(rid, failed, actual)
        self.observe_query([self.order_row(value)], datatype='deal')
        self.assertIsNone(self.lookup(value)['broker_order_id'])

    def test_commit_failure_publishes_neither_result_nor_proof(self):
        value, unused = self.insert(); self.finish(value)
        rid, result, actual = self.prepare_query([self.order_row(value)])
        with commit_failure(False), self.assertRaises(sqlite3.OperationalError):
            self.journal.finish_bound(rid, result, actual)
        self.assertEqual(self.journal.get_bound(rid)['state'], 'executing')
        self.assertIsNone(self.lookup(value)['broker_order_id'])

    def test_expired_persistence_deadline_never_publishes_result_or_proof(self):
        value, unused = self.insert(); self.finish(value)
        rid, result, actual = self.prepare_query([self.order_row(value)])
        with self.assertRaises(TimeoutError):
            self.journal.finish_bound(rid,result,actual,deadline=time.monotonic()-1)
        self.assertEqual(self.journal.get_bound(rid)['state'],'executing')
        self.assertIsNone(self.lookup(value)['broker_order_id'])

    def test_deadline_after_association_before_commit_rolls_back_both_facts(self):
        value, unused = self.insert(); self.finish(value)
        rid, result, actual = self.prepare_query([self.order_row(value)])
        clock = [100.0]
        saved = self.journal._bound_result_saved
        def cross_deadline(*args):
            saved(*args)
            clock[0] = 102.0
        with patch('guanheng_qmt_shm.bound_journal.time.monotonic',side_effect=lambda:clock[0]), \
                patch.object(self.journal,'_bound_result_saved',side_effect=cross_deadline), \
                self.assertRaises(TimeoutError):
            self.journal.finish_bound(rid,result,actual,deadline=101.0)
        self.assertEqual(self.journal.get_bound(rid)['state'],'executing')
        self.assertIsNone(self.lookup(value)['broker_order_id'])

    def test_commit_return_after_deadline_retains_actual_atomic_facts(self):
        value, unused = self.insert(); self.finish(value)
        rid, result, actual = self.prepare_query([self.order_row(value)])
        clock = [100.0]
        class Connection:
            def __init__(self,db): self.db=db
            def __getattr__(self,name): return getattr(self.db,name)
            def commit(self):
                self.db.commit()
                clock[0]=102.0
        with patch('guanheng_qmt_shm.bound_journal.time.monotonic',side_effect=lambda:clock[0]), \
                patch.object(self.journal, '_database', Connection(self.journal._database)), \
                self.assertRaises(TimeoutError):
            self.journal.finish_bound(rid,result,actual,deadline=101.0)
        self.assertEqual(self.journal.get_bound(rid)['state'],'terminal')
        self.assertEqual(self.lookup(value)['query_observation']['request_id'],rid)

    def test_tampered_or_missing_original_query_prevents_lookup(self):
        value, unused = self.insert(); self.finish(value)
        rid, unused = self.observe_query([self.order_row(value)])
        with closing(sqlite3.connect(self.journal.path)) as db, db:
            db.execute("UPDATE read_operations SET result=? WHERE request_id=?", (b'{}', rid))
        with self.assertRaises(JournalConflict): self.lookup(value)

    def test_uc_unknown_insert_new_source_order_query_allows_cancel_without_new_callback(self):
        value,unused=self.insert()
        self.journal.claim_trade(self.actual,deadline=self.deadline())
        original=self.journal.interrupt_trade(value['command_id'],deadline=self.deadline())
        self.new_source()
        self.assertFalse(self.owner.accepting_commands)
        self.assertTrue(self.owner.accepting_cancels)
        denied=self.owner.request(self.request_command(self.cancel(value)))
        self.assertEqual(denied.status_code,503)
        rid,result=self.observe_query([self.order_row(value)])
        proof=self.lookup(value)
        self.assertIsNone(proof['source'])
        self.assertEqual(proof['query_observation']['request_id'],rid)
        cancel=self.cancel(value)
        self.assertEqual(self.owner.request(self.request_command(cancel)).status_code,202)
        claimed=self.owner.claim_trade(self.actual,deadline=self.deadline())
        self.assertEqual(claimed['command_id'],cancel['command_id'])
        self.assertEqual(self.journal.get_trade(value['command_id'],deadline=self.deadline()),original)
        self.assertEqual(decode(runtime.bound.unb64(self.journal.get_bound(rid)['result_body_b64'],16384)),result)
        self.assertFalse(self.owner.accepting_commands)

    def test_uc_old_query_get_does_not_refresh_unknown_target_or_allow_cancel(self):
        value,unused=self.insert()
        self.journal.claim_trade(self.actual,deadline=self.deadline())
        self.journal.interrupt_trade(value['command_id'],deadline=self.deadline())
        rid,unused=self.observe_query([self.order_row(value)])
        before=self.lookup(value);self.new_source()
        self.journal.get_bound(rid)
        response=self.owner.request(self.request_command(self.cancel(value)))
        self.assertEqual(response.status_code,503)
        self.assertEqual(self.lookup(value),before)
        self.assertIsNone(self.journal.get_trade(self.cancel(value)['command_id'],deadline=self.deadline()))

    def query_metadata_corruption(self,column,bad,operation):
        self.assertIn(column,('query_request_id','query_result_sha256','query_row_index'))
        other,unused=self.insert(2);self.finish(other)
        self.observe_query([self.order_row(other,m_strOrderSysID='broker-2')])
        value,unused=self.insert()
        self.journal.claim_trade(self.actual,deadline=self.deadline())
        original=self.journal.interrupt_trade(value['command_id'],deadline=self.deadline())
        self.owner.note_trade_record(original)
        rid,result=self.observe_query([self.order_row(value)])
        self.assertIsNone(self.lookup(value)['source'])
        self.assertTrue(self.owner.accepting_cancels)
        with self.journal._trade_transaction(self.deadline()) as db:
            self.journal._order_links.validate_cancel(db,self.cancel(other,broker='broker-2'),self.source)
            db.execute('UPDATE trade_order_links SET '+column+'=? WHERE command_id=?',(bad,value['command_id']))
        if operation=='cancel_lookup':
            request=runtime.HostTradeRequest('trade.cancel_lookup',canonical({
                'schema_version':'qmt.trade-cancel-lookup.v1','original_command_id':value['command_id'],
                'original_command_sha256':runtime.bound.digest(canonical(value))}))
        else:
            identity=({'sdk_user_order_id':value['sdk_user_order_id']} if operation=='token_lookup'
                      else {key:value[key] for key in ('entrust_id','user_tag')})
            request=runtime.HostTradeRequest('trade.lookup',canonical({
                'schema_version':'qmt.trade-order-lookup.v1','identity':identity}))
        response=self.owner.request(request)
        self.assertEqual((response.status_code,decode(response.content)['error_code']),(409,'identity_conflict'))
        self.assertNotIn(b'private-query-metadata',response.content)
        facts=self.journal.trade_admission(deadline=self.deadline())
        self.assertEqual(facts,{'unknown_fenced':True,'hard_fault':{'code':'order_proof_invalid'}})
        self.owner.observe_source(self.service.status(),None,{'unknown_fenced':False,'hard_fault':None})
        status=decode(self.owner.request(runtime.HostTradeRequest('trade.status')).content)
        self.assertEqual(status['hard_fault'],{'code':'order_proof_invalid'})
        self.assertFalse(status['accepting_commands'] or status['cancel_admission'])
        self.assertEqual(self.owner.request(self.request_command(link_fixtures.command(33))).status_code,503)
        cancel=self.cancel(other,broker='broker-2')
        self.assertEqual(self.owner.request(self.request_command(cancel)).status_code,503)
        self.assertIsNone(self.journal.get_trade(cancel['command_id'],deadline=self.deadline()))
        self.assertEqual(self.journal.get_trade(value['command_id'],deadline=self.deadline()),original)
        self.assertEqual(self.owner.request(runtime.HostTradeRequest('trade.result',command_id=value['command_id'])).status_code,200)
        self.assertEqual(self.owner.request(self.request_command(value)).status_code,200)
        self.assertEqual(decode(runtime.bound.unb64(self.journal.get_bound(rid)['result_body_b64'],16384)),result)

    def test_uc_incomplete_query_tuple_cancel_lookup_latches_hard_fault(self):
        self.query_metadata_corruption('query_result_sha256',None,'cancel_lookup')

    def test_uc_non_json_query_metadata_token_lookup_latches_hard_fault(self):
        self.query_metadata_corruption('query_row_index',sqlite3.Binary(b'private-query-metadata'),'token_lookup')

    def test_uc_invalid_complete_query_metadata_WT_lookup_latches_hard_fault(self):
        self.query_metadata_corruption('query_row_index',-1,'WT_lookup')


class ReadFinishDeadlineControlTests(unittest.TestCase):
    """无线程控制循环替身，核同一D/原结果与ACK边界。"""
    def loop(self):
        loop=object.__new__(HostControlLoop)
        loop.runtime=SimpleNamespace(budget=SimpleNamespace(io_seconds=2),journal=Mock())
        loop._binding=canonical({'synthetic':'binding'})
        loop.active=('original-query',b'{}',1,0)
        loop._read_scan=loop._read_commit=loop._read_finish=None
        loop.domain_failed=False
        loop.read_future=Mock()
        loop.read_future.take.return_value={'ok':True,'payload':{'original':'native'}}
        loop._domain=Mock()
        return loop

    def test_queue_backpressure_keeps_original_result_and_deadline(self):
        loop=self.loop(); commit=Future()
        loop._domain.submit.side_effect=[BufferError('full'),commit]
        with patch('guanheng_qmt_shm.control.time.monotonic',return_value=100):
            loop._complete()
        pending=loop._read_finish
        self.assertEqual(pending['payload']['deadline'],102)
        self.assertIs(pending['reply'],loop.read_future.take.return_value)
        with patch('guanheng_qmt_shm.control.time.monotonic',return_value=101):
            loop._complete()
        self.assertIs(loop._domain.submit.call_args.args[1],pending['payload'])
        self.assertEqual(loop.read_future.take.call_count,1)
        commit.set_result(None);loop._progress_domain()
        loop.read_future.ack.assert_called_once()
        self.assertIsNone(loop.active)

    def test_expired_pending_result_is_retained_without_new_submit_or_ack(self):
        loop=self.loop();loop._domain.submit.side_effect=BufferError('full')
        with patch('guanheng_qmt_shm.control.time.monotonic',return_value=100):
            loop._complete()
        pending=loop._read_finish
        with patch('guanheng_qmt_shm.control.time.monotonic',return_value=103), \
                self.assertRaises(TimeoutError):
            loop._complete()
        self.assertIs(loop._read_finish,pending)
        self.assertEqual(loop._domain.submit.call_count,1)
        self.assertEqual(loop.read_future.take.call_count,1)
        loop.read_future.ack.assert_not_called()

    def test_domain_passes_exact_deadline_and_failed_commit_never_acks(self):
        loop=self.loop()
        loop._journal_call('read.finish',dict(request_id='original-query',result={},deadline=102))
        loop.runtime.journal.finish_bound.assert_called_once_with(
            'original-query',{}, {'synthetic':'binding'},deadline=102)
        commit=Future();commit.set_exception(TimeoutError('commit returned late'))
        loop._read_commit=commit
        with self.assertRaises(TimeoutError):loop._progress_domain()
        self.assertTrue(loop.domain_failed)
        self.assertIs(loop._read_commit,commit)
        self.assertIsNotNone(loop.active)
        loop.read_future.ack.assert_not_called()

    def test_close_pending_uses_earlier_original_deadline_and_keeps_failure(self):
        loop=self.loop();loop.peer=Mock()
        pending={'reply':{'ok':True,'payload':{}},'ready':True,
                 'payload':dict(request_id='original-query',result={},deadline=102)}
        loop._read_finish=pending
        loop.runtime.journal.finish_bound.side_effect=TimeoutError('original deadline')
        with patch('guanheng_qmt_shm.control.time.monotonic',return_value=101), \
                self.assertRaises(TimeoutError):loop.close(110)
        loop.runtime.journal.finish_bound.assert_called_once_with(
            'original-query',{}, {'synthetic':'binding'},deadline=102)
        self.assertIs(loop._read_finish,pending)
        loop.read_future.ack.assert_not_called()

    def test_slot_allocation_or_clock_failure_precedes_take(self):
        for location,error in (('_new_read_finish',MemoryError('slot allocation')),
                               ('clock',RuntimeError('clock unavailable'))):
            with self.subTest(location=location):
                loop=self.loop()
                failure=(patch.object(loop,location,side_effect=error) if location!='clock'
                    else patch('guanheng_qmt_shm.control.time.monotonic',side_effect=error))
                with failure,self.assertRaises(type(error)):loop._complete()
                loop.read_future.take.assert_not_called()
                self.assertIsNone(loop._read_finish)
                loop._domain.submit.assert_not_called()

    def test_clock_failure_after_take_keeps_original_reply_and_conservative_deadline(self):
        loop=self.loop()
        with patch('guanheng_qmt_shm.control.time.monotonic',
                side_effect=[100,RuntimeError('clock after take')]),self.assertRaises(RuntimeError):
            loop._complete()
        self.assertIs(loop._read_finish['reply'],loop.read_future.take.return_value)
        self.assertEqual(loop._read_finish['payload']['deadline'],102)
        loop._domain.submit.assert_not_called()
        loop.read_future.ack.assert_not_called()

    def test_missing_or_failed_native_payload_stays_owned_through_interrupt_and_close(self):
        for reply in ({'ok':True},{'ok':True,'payload':None},{'ok':False,'payload':None}):
            with self.subTest(reply=reply):
                loop=self.loop();loop.peer=Mock();loop.read_future.take.return_value=reply
                with patch('guanheng_qmt_shm.control.time.monotonic',return_value=100), \
                        self.assertRaises((KeyError,ValueError)):
                    loop._complete()
                pending=loop._read_finish
                self.assertIs(pending['reply'],reply)
                self.assertEqual(pending['payload']['deadline'],102)
                with self.assertRaises((KeyError,ValueError)):loop.interrupt_read()
                with patch('guanheng_qmt_shm.control.time.monotonic',return_value=101), \
                        self.assertRaises((KeyError,ValueError)):loop.close(110)
                self.assertIs(loop._read_finish,pending)
                loop._domain.submit.assert_not_called()
                loop.runtime.journal.finish_bound.assert_not_called()
                loop.runtime.journal.interrupt_bound.assert_not_called()
                self.assertEqual(loop.read_future.take.call_count,1)
                loop.read_future.ack.assert_not_called()

    def test_empty_take_keeps_original_unclaimed_path(self):
        loop=self.loop();loop.read_future.take.return_value=None
        with patch('guanheng_qmt_shm.control.time.monotonic',return_value=100):loop._complete()
        self.assertIsNone(loop._read_finish)
        self.assertIsNotNone(loop.active)
        loop._domain.submit.assert_not_called()


if __name__ == '__main__':
    unittest.main()
