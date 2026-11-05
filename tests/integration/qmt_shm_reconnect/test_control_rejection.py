"""同一Host控制owner的拒绝→后继成功→关闭；真实peer、域线程和SQLite，零QMT/网络。"""
import base64
from concurrent.futures import Future
from datetime import datetime,timezone
from pathlib import Path
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'connectors/qmt_shm/host'),str(ROOT/'connectors/qmt_shm/agent')]

from guanheng_qmt_shm_agent.control_agent import AgentControlLoop
from guanheng_qmt_shm_agent.control_messages import host_binding
from guanheng_qmt_shm_agent.control_peer import ControlPeer,ControlFuture
from guanheng_qmt_shm_agent.control_profile import ControlProfile
from guanheng_qmt_shm_agent.history_preparation import OPERATION,returned
from guanheng_qmt_shm_agent.protocol import ProtocolError,TransportBudget,canonical,decode
from guanheng_qmt_shm_agent.read_capabilities import build_read_profile
from guanheng_qmt_shm_agent.results import finalize_result
from guanheng_qmt_shm.control import HostControlLoop
from guanheng_qmt_shm.bulk_host_control import BulkHostControlLoop
from guanheng_qmt_shm.history_preparation_journal import HistoryPreparationJournal
from guanheng_qmt_shm.read_service import _diagnostic_read_rejection,ReconnectingReadService
from guanheng_qmt_shm.runtime import HostReadRuntime


CONTROL=dict(schema_version='1.0',max_pending_calls=4,max_call_bytes=8192,max_reply_bytes=16384,
    max_retained_bytes=262144,max_cycle_messages=4,max_cycle_bytes=32768,poll_seconds=.001,max_call_seconds=10)
SCOPE=dict(schema_version='qmt.history-preparation-limits.v2',periods=['1d'],
    max_calendar_days={'1m':5,'1d':366},max_tasks=8,max_queued=8,total_timeout_ms=10000)


class Source:
    """只替代原SDK任务队列；真实AgentControlLoop按原grammar产生回复。"""
    def __init__(self,rejected_id):
        self.rejected_id=rejected_id  # 本例第一请求，只有此ID在队列准入前拒绝。
        self.seen=[]  # 测试计数，验证原请求没有重发。

    def _enqueue_read(self,message):
        request=decode(base64.b64decode(message['body'],validate=True));self.seen.append(request['request_id'])
        if request['request_id']==self.rejected_id:
            raise ProtocolError('isolated expired preparation admission')
        result=finalize_result(dict(request_id=request['request_id'],operation_id=OPERATION,ok=True,
            completed_at=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),data=returned(request['arguments']),
            execution_ms=0,queue_wait_ms=0),8192)
        return request,SimpleNamespace(poll=lambda:result)


class Session:
    """只交换真实peer的内存packet；不建立HTTP/SHM，也不导入运行中的配对配置。"""
    def __init__(self,profile,source,runtime,finished,error_code=None,corrupt=False):
        self.generation='1'*32  # 合成Session固定代，沿原nonce验证。
        self.framer=SimpleNamespace()  # 显式使用原同步Session.receive分支。
        self.loop=AgentControlLoop.__new__(AgentControlLoop)
        self.loop.agent=source;self.loop.pending={};self.loop.peer=ControlPeer('agent',self.generation,profile)
        self.runtime=runtime;self.finished=finished;self.host=None;self.batch=None
        self.error_code=error_code  # 显式合成其它合法控制失败码；主链缺省沿真实AgentControlLoop准入。
        self.corrupt=corrupt  # 真正wire损坏在Host原peer准入处失败，不进入单次拒绝分支。
        self.end=time.monotonic()+5  # 仅测试等待预算，不改原业务/持久化截止。

    def send(self,packet,deadline):
        if time.monotonic()>=self.end:raise TimeoutError('isolated peer chain did not finish')
        self.loop.peer.receive(packet)
        if self.error_code is None:self.loop._dispatch_available()
        else:
            while True:
                call=self.loop.peer.take_call()
                if call is None:break
                request=decode(base64.b64decode(call['payload']['body']))
                if request['request_id']==self.loop.agent.rejected_id:
                    self.loop.peer.reply(call['call_seq'],error=dict(code=self.error_code,message=self.error_code))
                else:self.loop._dispatch(call)
        self.loop._complete_pending()
        self.batch=self.loop.peer.prepare()

    def receive(self,deadline):
        value=self.batch.packet;self.loop.peer.sent(self.batch);self.batch=None
        if self.corrupt:
            for message in value['messages']:
                if message['kind']=='REPLY':message['error']['code']='invalid-private-code'
        if self.finished()and self.host.peer._out_floor==2:self.runtime._stop.set()
        return value


class ControlRejectionTests(unittest.TestCase):
    def fixture(self,directory):
        entries={
            'market.full_tick':dict(policy_id='qmt.standard-read.v1',policy_version='1.0',execution_timeout_ms=1000,limits={}),
            OPERATION:dict(policy_id='qmt.history-preparation.v1',policy_version='1.0',execution_timeout_ms=1000,limits=SCOPE)}
        profile=build_read_profile(sorted(entries),1000,CONTROL,entries,max_result_bytes=8192)
        route=dict(route_id='isolated',executor_id='source',route_epoch=1)
        journal=HistoryPreparationJournal(Path(directory)/'communication.sqlite',route,max_records=8,
            max_result_bytes=8192,max_request_bytes=4096,max_journal_bytes=8*(8192+4096+16384),
            read_profile=profile,clock=SimpleNamespace(seconds=time.monotonic))
        binding=host_binding(route=route,generation='1'*32,host_instance_id='2'*32,journal_generation=None,
            observation_identity=None,capability_sha256=__import__('hashlib').sha256(canonical(profile)).hexdigest())
        runtime=SimpleNamespace(journal=journal,budget=TransportBudget(1,2),_stop=threading.Event(),
            _wake=threading.Event(),last_tick=None,control_profile=ControlProfile(CONTROL,65536,TransportBudget(1,2)))
        runtime.claim_bound=journal.claim_bound
        requests=[]
        for unused in range(2):
            request=dict(request_id=str(uuid4()),correlation_id=str(uuid4()),operation_id=OPERATION,
                arguments=dict(symbol='510300.SH',period='1d',start_time='20261101',end_time='20261105',
                    clock_schema='qmt.win-uptime-ms.v1',deadline_ms=int((time.monotonic()+5)*1000)),
                timeout_ms=1000,policy_id='qmt.history-preparation.v1',policy_version='1.0',priority_class='normal')
            journal.submit_bound(canonical(request),binding,queue_timeout_ms=2000);requests.append(request)
        return journal,binding,runtime,requests

    def test_same_host_rejection_success_and_close(self):
        self.run_chain()

    def run_chain(self,error_code=None,backpressure=False):
        with tempfile.TemporaryDirectory()as directory:
            journal,binding,runtime,requests=self.fixture(directory)
            source=Source(requests[0]['request_id'])
            finished=lambda:all(journal.get_bound(r['request_id'])['state']=='terminal'for r in requests)
            session=Session(runtime.control_profile,source,runtime,finished,error_code=error_code)
            host=HostControlLoop(runtime,session,binding);session.host=host
            original_submit=host._domain.submit;original_take=ControlFuture.take
            payloads=[];deliveries=[]
            def submit(operation,payload=None,expires_at=None):
                if operation=='read.finish'and 'control_rejection'in payload:
                    payloads.append(dict(payload))
                    if backpressure and len(payloads)==1:raise BufferError('isolated domain backpressure')
                return original_submit(operation,payload,expires_at)
            def take(future):
                result=original_take(future)
                if result is not None:deliveries.append(future)
                return result
            try:
                with patch.object(host._domain,'submit',side_effect=submit),patch.object(ControlFuture,'take',new=take):
                    host.run()
                first=journal.get_bound(requests[0]['request_id']);second=journal.get_bound(requests[1]['request_id'])
                self.assertEqual(decode(base64.b64decode(first['result_body_b64']))['error_code'],'preparation_unknown')
                self.assertIsNone(first['result_binding'])
                self.assertTrue(decode(base64.b64decode(second['result_body_b64']))['ok'])
                self.assertEqual(second['result_binding'],binding)
                expected=[r['request_id']for r in requests]if error_code is None else[requests[1]['request_id']]
                self.assertEqual(source.seen,expected)
                self.assertEqual(host.read_rejection_diagnostic,dict(code=error_code or'invalid_arguments',delivery='replied',persistence='committed',count=1))
                self.assertEqual(len(deliveries),len(set(deliveries)))
                self.assertEqual(len(payloads),2 if backpressure else 1)
                self.assertTrue(all(p==payloads[0]for p in payloads))
                runtime._control=host
                self.assertEqual(HostReadRuntime.read_rejection_diagnostic.fget(runtime),host.read_rejection_diagnostic)
                runtime.read_rejection_diagnostic=host.read_rejection_diagnostic
                self.assertEqual(_diagnostic_read_rejection(runtime),host.read_rejection_diagnostic)
                self.assertIsNone(host.active);self.assertIsNone(host._read_finish)
            finally:
                try:host.close(time.monotonic()+2)
                finally:journal.close(time.monotonic()+2)
            self.assertFalse(host._domain._thread.is_alive())

    def test_every_existing_control_error_keeps_next_request_available(self):
        for code in ('queue_full','capability_unavailable','call_expired','reply_too_large','binding_closed'):
            with self.subTest(code=code):self.run_chain(error_code=code)

    def test_backpressure_keeps_one_reply_one_diagnostic_and_original_deadline(self):
        self.run_chain(backpressure=True)

    def test_pending_rejection_closes_and_reopens_without_resubmitting_original(self):
        with tempfile.TemporaryDirectory()as directory:
            journal,binding,runtime,requests=self.fixture(directory);source=Source(requests[0]['request_id'])
            session=Session(runtime.control_profile,source,runtime,lambda:False)
            host=HostControlLoop(runtime,session,binding);session.host=host
            original=host._domain.submit
            def blocked(operation,payload=None,expires_at=None):
                if operation=='read.finish':
                    runtime._stop.set();raise BufferError('isolated stop with retained rejection')
                return original(operation,payload,expires_at)
            try:
                with patch.object(host._domain,'submit',side_effect=blocked):host.run()
                self.assertIsNotNone(host._read_finish)
                # close直接消费已持有回复，不调用take或发送新CALL。
                host.close(time.monotonic()+2)
                record=journal.get_bound(requests[0]['request_id'])
                self.assertEqual(decode(base64.b64decode(record['result_body_b64']))['error_code'],'preparation_unknown')
                self.assertEqual(source.seen,[requests[0]['request_id']])
                args=dict(max_records=8,max_result_bytes=8192,max_request_bytes=4096,
                    max_journal_bytes=8*(8192+4096+16384),read_profile=journal.admission_profile,
                    clock=SimpleNamespace(seconds=time.monotonic))
                route=journal.route;journal.close(time.monotonic()+2)
                journal=HistoryPreparationJournal(Path(directory)/'communication.sqlite',route,**args)
                self.assertEqual(journal.get_bound(requests[0]['request_id'])['state'],'terminal')
                self.assertEqual(journal.claim_bound(binding)[0],requests[1]['request_id'])
            finally:
                try:host.close(time.monotonic()+2)
                finally:journal.close(time.monotonic()+2)

    def test_real_wire_damage_still_raises_and_retains_original_unknown(self):
        with tempfile.TemporaryDirectory()as directory:
            journal,binding,runtime,requests=self.fixture(directory)
            session=Session(runtime.control_profile,Source(requests[0]['request_id']),runtime,lambda:False,corrupt=True)
            host=HostControlLoop(runtime,session,binding);session.host=host
            try:
                with self.assertRaises(ProtocolError):host.run()
                self.assertIsNone(host.read_rejection_diagnostic)
                host.close(time.monotonic()+2)
                result=journal.get_bound(requests[0]['request_id'])
                self.assertEqual(decode(base64.b64decode(result['result_body_b64']))['error_code'],'preparation_unknown')
                self.assertEqual(session.loop.agent.seen,[requests[0]['request_id']])
            finally:
                try:host.close(time.monotonic()+2)
                finally:journal.close(time.monotonic()+2)

    def test_diagnostic_rejects_extra_fields_and_private_values(self):
        with tempfile.TemporaryDirectory()as directory:
            journal,binding,runtime,requests=self.fixture(directory)
            try:
                for value in [dict(code='private',delivery='replied',persistence='pending',count=1),
                        dict(code='queue_full',delivery='replied',persistence='pending',count=1,body='PRIVATE')]:
                    runtime.read_rejection_diagnostic=value
                    self.assertIsNone(_diagnostic_read_rejection(runtime))
            finally:journal.close(time.monotonic()+2)

    def test_local_not_sent_retirement_keeps_original_until_its_domain_commit(self):
        with tempfile.TemporaryDirectory()as directory:
            journal,binding,runtime,requests=self.fixture(directory)
            session=Session(runtime.control_profile,Source(requests[0]['request_id']),runtime,lambda:False)
            host=HostControlLoop(runtime,session,binding);session.host=host
            try:
                claimed=Future();claimed.set_result(host._journal_call('read.claim',None));host._read_scan=claimed
                host._admit();original=host.read_future
                host.peer._mono=lambda:time.monotonic()+20
                host.peer.prepare()  # 原peer在发送前超期，Future先退休并保留not_sent结果。
                self.assertTrue(original.retired)
                with patch.object(host._domain,'submit',side_effect=BufferError('isolated retained rejection')):
                    host._complete();host._admit()
                self.assertIs(host.read_future,original)
                self.assertEqual(host.read_rejection_diagnostic['delivery'],'not_sent')
                self.assertEqual(session.loop.agent.seen,[])
                host.close(time.monotonic()+2)
                record=journal.get_bound(requests[0]['request_id'])
                self.assertEqual(decode(base64.b64decode(record['result_body_b64']))['error_code'],'preparation_unknown')
            finally:
                try:host.close(time.monotonic()+2)
                finally:journal.close(time.monotonic()+2)

    def test_rejection_persistence_failure_keeps_original_and_close_does_not_ack(self):
        for after_commit in (False,True):
            with self.subTest(after_commit=after_commit),tempfile.TemporaryDirectory()as directory:
                journal,binding,runtime,requests=self.fixture(directory)
                session=Session(runtime.control_profile,Source(requests[0]['request_id']),runtime,lambda:False)
                host=HostControlLoop(runtime,session,binding);session.host=host
                original=journal.interrupt_bound;calls=[]
                def persist(rid,operation,*,deadline=None):
                    calls.append(rid)
                    if len(calls)==1:
                        if after_commit:original(rid,operation,deadline=deadline)
                        raise TimeoutError('isolated original commit deadline')
                    return original(rid,operation,deadline=deadline)
                try:
                    with patch.object(journal,'interrupt_bound',side_effect=persist):
                        with self.assertRaises(TimeoutError):host.run()
                        self.assertIsNotNone(host.active)
                        host.close(time.monotonic()+2)
                    record=journal.get_bound(requests[0]['request_id'])
                    self.assertEqual(record['state'],'terminal');self.assertIsNone(record['result_binding'])
                    self.assertEqual(len(calls),1 if after_commit else 2)
                    self.assertFalse(host._abandoned_read_commit['reply_future']._acknowledged)
                    self.assertEqual(session.loop.agent.seen,[requests[0]['request_id']])
                finally:
                    try:host.close(time.monotonic()+2)
                    finally:journal.close(time.monotonic()+2)

    def test_refused_commit_checks_original_body_and_preserves_existing_native_terminal(self):
        with tempfile.TemporaryDirectory()as directory:
            journal,binding,runtime,requests=self.fixture(directory)
            session=Session(runtime.control_profile,Source(requests[0]['request_id']),runtime,lambda:False)
            host=HostControlLoop(runtime,session,binding);session.host=host
            first=requests[0];journal.claim_bound(binding)
            payload=dict(request_id=first['request_id'],result=None,deadline=time.monotonic()+2,
                control_rejection=dict(code='queue_full',delivery='replied',operation_id=OPERATION,request_sha256='0'*64))
            try:
                with self.assertRaises(ProtocolError):host._persist_read_outcome(payload,payload['deadline'])
                self.assertEqual(journal.get_bound(first['request_id'])['state'],'executing')
                result=finalize_result(dict(request_id=first['request_id'],operation_id=OPERATION,ok=True,
                    completed_at=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
                    data=returned(first['arguments']),execution_ms=0,queue_wait_ms=0),8192)
                journal.finish_bound(first['request_id'],result,binding)
                before=journal.get_bound(first['request_id'])
                payload['control_rejection']['request_sha256']=__import__('hashlib').sha256(canonical(first)).hexdigest()
                host._persist_read_outcome(payload,payload['deadline'])
                self.assertEqual(journal.get_bound(first['request_id']),before)
            finally:
                try:host.close(time.monotonic()+2)
                finally:journal.close(time.monotonic()+2)

    def test_failure_snapshot_copies_nested_rejection_without_private_message(self):
        with tempfile.TemporaryDirectory()as directory:
            journal,binding,runtime,requests=self.fixture(directory)
            service=ReconnectingReadService.__new__(ReconnectingReadService)
            service._condition=threading.Condition();service._failure=service._cleanup_failure=None
            service._phase='connected';service._generation=1;service._runtime=runtime;service.connected=threading.Event()
            runtime.read_rejection_diagnostic=dict(code='queue_full',delivery='replied',persistence='pending',count=1)
            try:
                service._fault('runtime_journal');snapshot=service.failure_diagnostic_snapshot
                self.assertEqual(snapshot['first_failure']['read_rejection'],runtime.read_rejection_diagnostic)
                snapshot['first_failure']['read_rejection']['code']='PRIVATE'
                self.assertEqual(service.failure_diagnostic_snapshot['first_failure']['read_rejection']['code'],'queue_full')
                self.assertNotIn(b'PRIVATE',canonical(service.failure_diagnostic_snapshot))
            finally:journal.close(time.monotonic()+2)

    def test_bulk_close_uses_same_ordinary_read_rejection_persistence(self):
        with tempfile.TemporaryDirectory()as directory:
            journal,binding,runtime,requests=self.fixture(directory)
            loop=BulkHostControlLoop.__new__(BulkHostControlLoop);loop.runtime=runtime
            loop._binding=canonical(binding);loop._cleanup_scan=None
            closed=[];loop._file_owner=lambda:SimpleNamespace(close=lambda deadline,requests:closed.append(True))
            journal.claim_bound(binding);first=requests[0]
            pending=dict(request_id=first['request_id'],result=None,deadline=time.monotonic()+2,
                control_rejection=dict(code='queue_full',delivery='replied',operation_id=OPERATION,
                    request_sha256=__import__('hashlib').sha256(canonical(first)).hexdigest()))
            try:
                loop._journal_call('bulk.close',dict(requests=[],page=None,read_finish=pending,deadline=time.monotonic()+2))
                self.assertEqual(journal.get_bound(first['request_id'])['state'],'terminal')
                self.assertEqual(closed,[True])
            finally:journal.close(time.monotonic()+2)


if __name__=='__main__':unittest.main()
