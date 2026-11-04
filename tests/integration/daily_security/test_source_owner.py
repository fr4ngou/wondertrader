"""SMP显式数据组合、启动期原D关闭与旧来源责任隔离；来源调用由替身拒绝。"""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from integrations.guanheng import market_daily_owner as owners
from integrations.guanheng.daily_data_inputs import observe_prior_plans
from integrations.guanheng.market_generation import encode
from integrations.guanheng.source_market_service import _configuration
from guanheng_qmt_shm.read_retention_client import RetainedReadBindingChanged


class SourceOwnerTests(unittest.TestCase):
    def test_changed_original_binding_keeps_identity_and_other_plans_continue(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);slot=root/'original.json';slot.write_bytes(encode(dict(request_id='fixed-test-UUID')))
            before=slot.read_bytes();calls=[]
            plans=[(dict(path=str(root/'a.json'),sha256='a'*64),root/'a',[3]),
                   (dict(path=str(root/'b.json'),sha256='b'*64),root/'b',[7])]

            def advance(plan,work,owner,**kwargs):
                calls.append((plan['sha256'],kwargs['task_indices']))
                if plan['sha256']=='a'*64:raise RetainedReadBindingChanged('original source changed')
                return dict(state='observed', rows=[])

            with patch('integrations.guanheng.daily_gap_update.advance_gap_plan',advance):
                result=observe_prior_plans(plans,object(),deadline=time.monotonic()+5,cancelled=lambda:False)
            self.assertEqual(calls,[('a'*64,[3]),('b'*64,[7])])
            self.assertEqual(len(result),1)
            self.assertEqual(result[0]['state'],'original_responsibility_unavailable')
            self.assertEqual(slot.read_bytes(),before)

    def test_original_pending_rows_are_recorded_and_other_plans_continue(self):
        calls=[]
        plans=[(dict(sha256='a'*64),Path('first'),[3,4]),
               (dict(sha256='b'*64),Path('second'),[7])]
        rows=[dict(index=3,state='pending',reason_code='original_pending',
                   slot='original-slot3',request_id='original-request3',coverage='unknown'),
              dict(index=4,state='source_unavailable',reason_code='original_failure',
                   slot='original-slot4',request_id='original-request4',coverage='unknown')]

        def advance(plan,work,owner,**kwargs):
            calls.append(plan['sha256'])
            return dict(state='observed',rows=rows if plan['sha256']=='a'*64 else
                        [dict(index=7,state='call_returned',coverage='unknown')])

        with patch('integrations.guanheng.daily_gap_update.advance_gap_plan',advance):
            result=observe_prior_plans(plans,object(),deadline=time.monotonic()+5,cancelled=lambda:False)
        self.assertEqual(calls,['a'*64,'b'*64])
        self.assertEqual(result,[dict(plan_sha256='a'*64,state=row['state'],task_indices=[row['index']],
            reason_code=row['reason_code'],slot=row['slot'],request_id=row['request_id'],coverage='unknown')
            for row in rows])

    def test_stop_before_control_directory_is_created_uses_original_deadline(self):
        with tempfile.TemporaryDirectory() as directory:
            parent=Path(directory);release=threading.Event();observed=[]

            def delayed_serve(configuration,output,control_id):
                release.wait(1);output.mkdir()
                end=time.monotonic()+2
                while not(output/'stop.json').exists():
                    if time.monotonic()>=end:raise TimeoutError('test stop not delivered')
                    time.sleep(.01)
                value=json.loads((output/'stop.json').read_bytes());observed.append(value['deadline'])
                (output/'closed.json').write_bytes(encode(dict(control_id=control_id,pid=os.getpid(),
                    owner_closed=True,error_type=None,close_deadline_exceeded=False)))

            with patch.object(owners,'serve',delayed_serve):
                owner=owners.MarketDailyOwner(dict(path='test-config',sha256='a'*64),parent)
                original=time.monotonic()+2
                try:
                    with self.assertRaises(InterruptedError):owner.start(original,stop_request=lambda:original)
                    self.assertFalse(owner.directory.exists())
                    release.set();owner.close(original+5)
                    self.assertFalse(owner.thread.is_alive())
                    self.assertEqual(observed,[original])
                finally:
                    release.set()
                    if owner.thread is not None:owner.thread.join(3)

    def test_configuration_rejects_separate_read_and_production_current(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            def save(name,value):
                path=root/name;path.write_bytes(encode(value))
                return dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            source=save('read.json',dict(mode='source-market-current',current_file=str(root/'wrong/CURRENT.json')))
            update=save('daily.json',dict(schema='guanheng.daily-data-service.v1',directory=str(root/'tasks'),
                raw_store=str(root/'raw'),template=dict(schema='guanheng.daily-data-update.v1',publication_directory=str(root/'publication')),
                inputs=dict(connections=dict(batch={},hpr={}),cache_from='20260701',max_rows=100,source_kind='actual-qmt',
                    public_facts=dict(source={},allowed_hosts=[],seconds=30,max_requests=1,max_bytes=1,response_bytes=1,timeout_seconds=1)),
                schedule=dict(timezone='Asia/Shanghai',at='09:00',poll_seconds=1),cycle_seconds=60,retry_seconds=1))
            service=save('service.json',dict(schema='guanheng.source-market-service.v1',source_configuration=source,
                daily_update=update,listen=dict(host='127.0.0.1',port=18100),token_env='TEST_TOKEN',socket_timeout=6))
            with self.assertRaises(ValueError):_configuration(Path(service['path']),service['sha256'])


if __name__=='__main__':unittest.main()
