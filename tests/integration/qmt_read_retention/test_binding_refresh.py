"""原公开客户端新slot准入当前认证，旧slot原责任恢复；不运行Source/SDK。"""
from contextlib import nullcontext
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from guanheng_qmt_shm_agent.protocol import canonical,decode
from guanheng_qmt_shm_agent.control_messages import host_binding
from guanheng_qmt_shm_agent.history_preparation import validate_configuration,OPERATION,returned
from guanheng_qmt_shm_agent.read_retention import retention,require_live
from guanheng_qmt_shm_agent.results import finalize_result
from guanheng_qmt_shm.bound import digest,b64,unb64
from guanheng_qmt_shm.read_retention_journal import RetainedPreparationJournal
from guanheng_qmt_shm.read_retention_client import RetainedReadClient,RetainedReadPending,RetainedReadBindingChanged
from integrations.guanheng.source_history_transport import BoundHistorySource,SourcePending
from tests.integration.qmt_history_preparation.support import configuration,Clock,request

class BindingRefreshContracts(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);config,settings=configuration(self.root);self.clock=Clock()
        self.profile=dict(validate_configuration(settings).profile,read_retention=retention(dict(schema='qmt.read-retention.v1',max_lifetime_ms=5000)))
        def metadata(epoch):
            binding=host_binding(route=config['route'],generation='c'*32,host_instance_id=epoch,journal_generation=None,
                observation_identity=None,capability_sha256=digest(canonical(self.profile)))
            return dict(schema_version='qmt.bound-read.v1',binding=binding,binding_sha256=digest(canonical(binding)),
                read_profile_body_b64=b64(canonical(self.profile)),read_profile_body_sha256=digest(canonical(self.profile)),profile=self.profile,
                limits=dict(max_request_bytes=4096,max_result_bytes=8192,max_http_request_bytes=65536,max_http_response_bytes=65536),order_ready=False)
        self.old,self.current=metadata('a'*32),metadata('b'*32)
        self.active=self.current;self.calls=[];self.executions=0;self.lose=False
        self.journal=RetainedPreparationJournal(self.root/'retained.sqlite',config['route'],max_records=8,
            max_result_bytes=8192,max_request_bytes=4096,max_journal_bytes=8*(4096+8192+16384),read_profile=self.profile,clock=self.clock)
        self.addCleanup(self.journal.close)
        def exchange(method,path,body,deadline):
            self.calls.append((method,path))
            if path.endswith('/read-binding'):return 200,self.active
            if path.endswith('/read-retention-status'):return 200,self.journal.retention_status(self.active['binding']['host_instance_id'])
            if '/bound-operations/' in path:
                envelope=decode(body);value=decode(unb64(envelope['request_body_b64'],4096))
                require_live(value,envelope['ticket'],self.profile['read_retention'],self.active['binding']['host_instance_id'],self.clock)
                rid=self.journal.submit_ticket(canonical(value),self.active['binding'],envelope['ticket'],queue_timeout_ms=2000)
                self.journal.claim_bound(self.active['binding'])
                self.executions+=1
                if self.lose:raise SourcePending('synthetic_lost_reply')
                result=finalize_result(dict(request_id=rid,operation_id=OPERATION,ok=True,data=returned(value['arguments']),completed_at='2026-10-30T00:00:00Z'),8192)
                self.journal.finish_bound(rid,result,self.active['binding'])
                return 200,self.journal.get_bound(rid)
            if path.endswith('/consumed'):
                rid=path.split('/')[-2]
                value=self.journal.consumed(rid,decode(body),self.active['binding']['host_instance_id'])
                return 200,value
            if path.endswith('/lookup'):return 410,dict(error_code='read_ticket_ended_unretained')
            raise AssertionError('unexpected test transport path')
        self.transport=SimpleNamespace(exchange=exchange,clock=time.monotonic,rpc_budget=lambda unused:nullcontext())
        self.transport.plan=lambda *args:BoundHistorySource.plan(self.transport,*args)
        self.client=RetainedReadClient(self.transport,clock=self.clock)
        self.args=request(self.clock)['arguments']
        self.slots=self.root/'slots';self.slots.mkdir()
        (self.slots/'BINDING.json').write_bytes(canonical(self.old))

    def test_new_slot_gets_current_binding_and_preserves_owner_binding(self):
        parent=(self.slots/'BINDING.json').read_bytes();slot=self.slots/'new.json'
        self.client.prepare(OPERATION,self.args,slot,deadline=time.monotonic()+2)
        self.assertEqual(decode(slot.read_bytes())['binding'],self.current['binding'])
        self.assertEqual((self.slots/'BINDING.json').read_bytes(),parent)
        self.assertEqual(sum(p.endswith('/read-binding') for _,p in self.calls),1)
        self.assertEqual(self.executions,1)

    def test_expected_old_binding_rejects_new_slot_before_plan_or_post(self):
        slot=self.slots/'new.json'
        with self.assertRaises(RetainedReadBindingChanged):
            self.client.prepare(OPERATION,self.args,slot,deadline=time.monotonic()+2,expected_binding=self.old['binding'])
        self.assertFalse(slot.exists());self.assertEqual(self.executions,0)
        self.assertFalse(any('/bound-operations/' in p for _,p in self.calls))

    def test_completed_old_slot_keeps_original_result_and_received_clock(self):
        self.active=self.old;slot=self.slots/'old.json'
        receipt=self.client.prepare(OPERATION,self.args,slot,deadline=time.monotonic()+2)
        before=slot.read_bytes();self.active=self.current;self.calls.clear()
        self.assertEqual(self.client.prepare(OPERATION,self.args,slot,deadline=time.monotonic()+2,expected_binding=self.old['binding']),receipt)
        with self.assertRaises(RetainedReadBindingChanged):
            self.client.prepare(OPERATION,self.args,slot,deadline=time.monotonic()+2,expected_binding=self.current['binding'])
        self.assertEqual(slot.read_bytes(),before);self.assertEqual(self.calls,[]);self.assertEqual(self.executions,1)

    def test_unknown_old_slot_keeps_id_and_lookup_without_current_binding(self):
        self.active=self.old;self.lose=True;slot=self.slots/'unknown.json'
        with self.assertRaises(RetainedReadPending):self.client.prepare(OPERATION,self.args,slot,deadline=time.monotonic()+2)
        before=slot.read_bytes();self.active=self.current;self.calls.clear()
        for unused in range(2):
            with self.assertRaises(RetainedReadPending):
                self.client.prepare(OPERATION,self.args,slot,deadline=time.monotonic()+2,expected_binding=self.current['binding'])
        self.assertEqual(slot.read_bytes(),before);self.assertEqual(self.executions,1)
        self.assertEqual(len(self.calls),2);self.assertTrue(all(p.endswith('/lookup') for _,p in self.calls))

    def test_v2_new_slot_reserve_stops_before_identity(self):
        # 原600秒阶段尾部515ms根因：不足完整30秒时不得计划SDK正文、票据或新槽。
        slot=self.slots/'reserve.json'
        with self.assertRaisesRegex(RetainedReadPending,'read_new_request_budget_exhausted'):
            self.client.prepare(OPERATION,self.args,slot,deadline=time.monotonic()+.515,
                minimum_new_request_seconds=30)
        self.assertFalse(slot.exists());self.assertEqual(self.calls,[]);self.assertEqual(self.executions,0)

    def test_v2_reserve_rechecks_time_spent_getting_binding(self):
        # 准入初检足够，当前绑定GET消耗外部预算后再次检查，仍不得产生短正文或slot。
        slot=self.slots/'after-binding.json';now=[0.];original_exchange=self.transport.exchange
        def exchange(method,path,body,deadline):
            result=original_exchange(method,path,body,deadline)
            if path.endswith('/read-binding'):now[0]=80.
            return result
        self.transport.exchange=exchange
        with patch('guanheng_qmt_shm.read_retention_client.time.monotonic',lambda:now[0]):
            with self.assertRaisesRegex(RetainedReadPending,'read_new_request_budget_exhausted'):
                self.client.prepare(OPERATION,self.args,slot,deadline=100.,minimum_new_request_seconds=30)
        self.assertFalse(slot.exists());self.assertEqual(self.executions,0)
        self.assertEqual(sum(p.endswith('/read-binding')for _,p in self.calls),1)
        self.assertFalse(any('/bound-operations/'in p for _,p in self.calls))

    def test_existing_slot_short_observation_keeps_original_result(self):
        # 已有完整成功原件即使新观察不足30秒仍按原ID复用，SDK、实收与票据字节保持。
        slot=self.slots/'completed-reserve.json'
        receipt=self.client.prepare(OPERATION,self.args,slot,deadline=time.monotonic()+2)
        before=slot.read_bytes();self.calls.clear()
        repeated=self.client.prepare(OPERATION,self.args,slot,deadline=time.monotonic()+.515,
            minimum_new_request_seconds=30)
        self.assertEqual(repeated,receipt);self.assertEqual(slot.read_bytes(),before)
        self.assertEqual(self.calls,[]);self.assertEqual(self.executions,1)

    def test_hpr_reserve_uses_whole_observation_not_single_call_deadline(self):
        # HPR单次原call_deadline与外部整段D分别持有；余量检查不错误阻止正常短单次预算。
        slot=self.slots/'external-observation.json'
        self.client.prepare(OPERATION,self.args,slot,deadline=time.monotonic()+2,
            minimum_new_request_seconds=30,new_request_observation_deadline=time.monotonic()+60)
        self.assertTrue(slot.exists());self.assertEqual(self.executions,1)

if __name__=='__main__':unittest.main()
