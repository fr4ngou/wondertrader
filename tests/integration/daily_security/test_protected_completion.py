"""已确认返回的旧HPR留证且允许新任务补缺；未知原结果继续阻止重复执行。"""
from pathlib import Path
from types import SimpleNamespace
import json
import tempfile
import time
import unittest
from unittest.mock import patch
from uuid import uuid4

from guanheng_qmt_shm import bound
from guanheng_qmt_shm_agent.protocol import canonical
from guanheng_qmt_shm_agent.control_messages import host_binding
from guanheng_qmt_shm_agent.read_capabilities import build_read_profile
from guanheng_qmt_shm_agent.read_retention import TICKET, content_id
from guanheng_qmt_shm_agent.history_preparation import OPERATION, POLICY, returned
from guanheng_qmt_shm_agent.results import finalize_result
from integrations.guanheng.daily_data_update import _descriptor
from integrations.guanheng.daily_gap_update import prepare_gap_plan


def receipt():
    """仅合成已认证原件形状；所有route/UUID/时钟都属于本测试。"""
    control = dict(schema_version='1.0', max_call_bytes=8192, max_reply_bytes=16384,
        max_pending_calls=4, max_cycle_messages=8, max_cycle_bytes=32768,
        max_retained_bytes=262144, max_call_seconds=40, poll_seconds=.005)
    scope = dict(schema_version='qmt.history-preparation-limits.v3', periods=['1d'],
        max_calendar_days=dict(**{'1d':3660,'1m':3660}), max_tasks=4, max_queued=2,
        total_timeout_ms=30000)
    operations = {
        'market.full_tick':dict(policy_id='qmt.standard-read.v1',policy_version='1.0',execution_timeout_ms=1000,limits={}),
        OPERATION:dict(policy_id=POLICY,policy_version='1.0',execution_timeout_ms=1000,limits=scope)}
    profile = build_read_profile(sorted(operations),1000,control,operations,max_result_bytes=8192,
        read_retention=dict(schema='qmt.read-retention.v1',max_lifetime_ms=5000))
    binding = host_binding(route=dict(route_id='synthetic-route',executor_id='synthetic-executor',route_epoch=1),
        generation='a'*32,host_instance_id='b'*32,journal_generation=None,observation_identity=None,
        capability_sha256=bound.digest(canonical(profile)))
    arguments = dict(symbol='510300.SH',period='1d',start_time='20261103',end_time='20261103',
        clock_schema='qmt.win-uptime-ms.v1',deadline_ms=1004000)
    request = dict(request_id=str(uuid4()),correlation_id=str(uuid4()),operation_id=OPERATION,
        arguments=arguments,timeout_ms=1000,policy_id=POLICY,policy_version='1.0',priority_class='normal')
    ticket = dict(schema=TICKET,epoch=binding['host_instance_id'],expires_ms=arguments['deadline_ms'])
    request['request_id'] = content_id(request,ticket)
    request_sha = bound.digest(canonical(request))
    reply = finalize_result(dict(request_id=request['request_id'],operation_id=OPERATION,ok=True,
        data=returned(arguments),completed_at='2026-11-04T01:00:00Z'),8192)
    body = canonical(reply)
    envelope = dict(schema_version=bound.SCHEMA,request_id=request['request_id'],operation_id=OPERATION,
        request_sha256=request_sha,request_body_sha256=request_sha,binding_status='recorded',
        admitted_binding=binding,dispatch_binding=binding,result_binding=binding,state='terminal',
        result_body_b64=bound.b64(body),result_body_sha256=bound.digest(body))
    return dict(request=request,request_body_sha256=request_sha,profile=profile,binding=binding,
        limits=dict(max_result_bytes=8192),ticket=ticket,result=envelope,attempted=True,consumed=True)


class ProtectedCompletionTests(unittest.TestCase):
    def plan(self,root,record,*,cached=False):
        capture=root/'capture';capture.mkdir()
        manifest=dict(request=dict(symbols=['510300.SH'],start_date='20261103',end_date='20261103'),
            comparison={'510300.SH':dict(common_dates=['20261103']if cached else[])})
        (capture/'manifest.json').write_bytes(canonical(manifest))
        original=root/'original.json';original.write_bytes(canonical(record));before=original.read_bytes()
        reference=SimpleNamespace(_calendar=dict(coverage_start='2026-01-01',coverage_end='2026-12-31',closed_dates=[]),
            security=lambda *_:dict(listed_on=None,expires_on=None))
        with patch('guanheng_qmt_shm.analysis_batch_source.read_capture',return_value=manifest):
            result=prepare_gap_plan(dict(directory=str(capture),sha256=_descriptor(capture/'manifest.json')['sha256']),
                reference,dict(observation_date='2026-11-03',snapshot_id='c'*64),root/'plan',
                protected_slots=[str(original)],authorized_from='20261103',authorized_to='20261103',
                deadline=time.monotonic()+5)
        self.assertEqual(original.read_bytes(),before)
        return json.loads(Path(result['path']).read_bytes())

    def test_completed_original_retains_identity_and_allows_new_gap_task(self):
        with tempfile.TemporaryDirectory()as directory:
            record=receipt();plan=self.plan(Path(directory),record)
            self.assertEqual([r['dates']for r in plan['tasks']],[['20261103']])
            self.assertEqual(plan['protected_requests'][0]['request_id'],record['request']['request_id'])

    def test_unconsumed_return_still_blocks_original_interval(self):
        with tempfile.TemporaryDirectory()as directory:
            record=receipt();record['consumed']=False
            self.assertEqual(self.plan(Path(directory),record)['tasks'],[])

    def test_unknown_result_still_blocks_original_interval(self):
        with tempfile.TemporaryDirectory()as directory:
            record=receipt();record['result']=None;record['consumed']=False
            self.assertEqual(self.plan(Path(directory),record)['tasks'],[])

    def test_corrupt_unknown_original_is_rejected_before_planning(self):
        for field in ('symbol','digest','binding','result'):
            with self.subTest(field=field),tempfile.TemporaryDirectory()as directory:
                record=receipt();record['consumed']=False
                if field=='symbol':record['request']['arguments']['symbol']='510500.SH'
                elif field=='digest':record['request_body_sha256']='0'*64
                elif field=='binding':record['binding']['host_instance_id']='d'*32
                else:record['result']['result_body_sha256']='0'*64
                with self.assertRaises(ValueError):self.plan(Path(directory),record)

    def test_consumed_failure_remains_unknown_execution(self):
        with tempfile.TemporaryDirectory()as directory:
            record=receipt();request=record['request']
            reply=finalize_result(dict(request_id=request['request_id'],operation_id=OPERATION,ok=False,
                error_code='preparation_unknown',completed_at='2026-11-04T01:00:00Z'),8192)
            body=canonical(reply);record['result'].update(result_body_b64=bound.b64(body),result_body_sha256=bound.digest(body))
            self.assertEqual(self.plan(Path(directory),record)['tasks'],[])

    def test_success_without_original_dispatch_and_result_proof_stays_unknown(self):
        with tempfile.TemporaryDirectory()as directory:
            record=receipt();record['result'].update(dispatch_binding=None,result_binding=None)
            self.assertEqual(self.plan(Path(directory),record)['tasks'],[])

    def test_corrupt_completed_result_cannot_release_original_responsibility(self):
        with tempfile.TemporaryDirectory()as directory:
            record=receipt();record['result']['result_body_sha256']='0'*64
            with self.assertRaises(ValueError):self.plan(Path(directory),record)

    def test_completed_result_with_other_binding_cannot_release_original_responsibility(self):
        with tempfile.TemporaryDirectory()as directory:
            record=receipt();record['result']['result_binding']=dict(record['binding'],host_instance_id='d'*32)
            with self.assertRaises(ValueError):self.plan(Path(directory),record)

    def test_completed_result_with_other_business_symbol_is_rejected(self):
        with tempfile.TemporaryDirectory()as directory:
            record=receipt();request=record['request'];data=returned(request['arguments']);data['symbol']='510500.SH'
            reply=finalize_result(dict(request_id=request['request_id'],operation_id=OPERATION,ok=True,
                data=data,completed_at='2026-11-04T01:00:00Z'),8192)
            body=canonical(reply);record['result'].update(result_body_b64=bound.b64(body),result_body_sha256=bound.digest(body))
            with self.assertRaises(ValueError):self.plan(Path(directory),record)

    def test_complete_cache_does_not_create_another_preparation(self):
        with tempfile.TemporaryDirectory()as directory:
            self.assertEqual(self.plan(Path(directory),receipt(),cached=True)['tasks'],[])
