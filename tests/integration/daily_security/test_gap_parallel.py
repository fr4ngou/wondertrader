"""原SDK executor的小批通信并发；合成Source证明原槽恢复和已完成任务不重发。"""
import json
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from uuid import uuid4

from integrations.guanheng.daily_data_update import _save
from integrations.guanheng.daily_gap_update import advance_gap_plan
from guanheng_qmt_shm.market_daily_preparation import MarketDailyPreparation
from guanheng_qmt_shm.read_retention_client import RetainedReadPending,RetainedReadBindingChanged
from guanheng_qmt_shm_agent.history_preparation import OPERATION,returned
from daily_gap_fixture import synthetic_gap_plan


class GapParallelTests(unittest.TestCase):
    def fixture(self,root,*,concurrency=4,count=8,unknown=None):
        metadata=dict(binding=dict(host_instance_id='synthetic-original',transport_generation='synthetic-generation'),binding_sha256='a'*64,limits={},
            profile=dict(operation_profiles={OPERATION:dict(limits=dict(total_timeout_ms=5000))}))
        plan=synthetic_gap_plan(root/'plan',['%06d.SH'%(510000+i)for i in range(count)],'20261105')
        state=SimpleNamespace(submissions={},active=0,peak=0,unknown=unknown,lock=threading.Lock())
        class Client:
            def __init__(self,transport,**kwargs):
                self.transport=transport;self.clock=SimpleNamespace(seconds=lambda:1000.);self.poll_seconds=.001
            def wait_capacity(self,deadline):pass
            def prepare(self,operation,args,slot,**kwargs):
                if slot.exists():record=json.loads(slot.read_bytes())
                else:
                    record=dict(binding=metadata['binding'],profile=metadata['profile'],limits={},
                        request=dict(request_id=str(uuid4()),arguments=args))
                    slot.parent.mkdir(exist_ok=True);_save(slot,record)
                    with state.lock:state.submissions[args['symbol']]=state.submissions.get(args['symbol'],0)+1
                with state.lock:state.active+=1;state.peak=max(state.peak,state.active)
                try:
                    time.sleep(.05)
                    if args['symbol']==state.unknown:raise RetainedReadPending('synthetic_original_unknown')
                    return dict(request_id=record['request']['request_id'],received_at='2026-11-05T08:00:00+00:00',
                        reply=dict(data=returned(args)))
                finally:
                    with state.lock:state.active-=1
        context=patch('guanheng_qmt_shm.market_daily_preparation.RetainedReadClient',Client)
        self.addCleanup(context.stop);context.start()
        metadata_patch=patch('integrations.guanheng.daily_gap_update._gap_hpr_metadata',
            return_value=(metadata,metadata,root/'generations'))
        self.addCleanup(metadata_patch.stop);metadata_patch.start()
        transport=SimpleNamespace(exchange=lambda *a:None,plan=lambda *a:None,rpc_budget=lambda *a:nullcontext())
        owner=MarketDailyPreparation(lambda:object(),transport,concurrency=concurrency)
        return plan,owner,state

    def run_plan(self,plan,owner,root,**kwargs):
        return advance_gap_plan(plan,root/'work',owner,deadline=time.monotonic()+90,max_tasks=100,**kwargs)

    def test_original_executor_bounds_concurrency_and_improves_main_path(self):
        elapsed=[]
        for workers in(1,4):
            with tempfile.TemporaryDirectory()as directory:
                root=Path(directory);plan,owner,state=self.fixture(root,concurrency=workers)
                start=time.monotonic();result=self.run_plan(plan,owner,root);elapsed.append(time.monotonic()-start)
                self.assertEqual(len(result['rows']),8)
                self.assertEqual(state.peak,workers)
                self.assertEqual(set(state.submissions.values()),{1})
        self.assertLess(elapsed[1],elapsed[0]*.7)

    def test_unknown_slot_resumes_same_identity_and_completed_items_are_not_resubmitted(self):
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory);plan,owner,state=self.fixture(root,count=4,unknown='510002.SH')
            result=self.run_plan(plan,owner,root)
            self.assertEqual([r['state']for r in result['rows']].count('pending'),1)
            slot=root/'work/preparation/000002.json';identity=json.loads(slot.read_bytes())['request']['request_id']
            state.unknown=None
            result=self.run_plan(plan,owner,root)
            self.assertEqual([r['index']for r in result['rows']],[2])
            self.assertEqual(json.loads(slot.read_bytes())['request']['request_id'],identity)
            self.assertEqual(set(state.submissions.values()),{1})

    def test_interrupted_observation_commit_retains_parallel_sdk_slots(self):
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory);plan,owner,state=self.fixture(root,count=4)
            def stop(row):raise InterruptedError('synthetic after first observation')
            with self.assertRaises(InterruptedError):self.run_plan(plan,owner,root,on_progress=stop)
            self.assertEqual(len(state.submissions),4)
            slots={p.name:json.loads(p.read_bytes())['request']['request_id']for p in(root/'work/preparation').glob('*.json')}
            result=self.run_plan(plan,owner,root)
            self.assertEqual(len(result['rows']),3)
            self.assertEqual(set(state.submissions.values()),{1})
            self.assertEqual(slots,{p.name:json.loads(p.read_bytes())['request']['request_id']for p in(root/'work/preparation').glob('*.json')})

    def test_cancel_during_binding_change_stops_before_another_authentication(self):
        # 观察返回换代拒绝时已停止：worker收束后不再新增一次网络认证。
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory);plan,owner,state=self.fixture(root,count=1)
            stopped=threading.Event()
            def changed(*args,**kwargs):
                stopped.set()
                raise RetainedReadBindingChanged('synthetic_source_changed')
            with patch('integrations.guanheng.daily_gap_update._gap_hpr_metadata',return_value=(
                    dict(profile=dict(operation_profiles={OPERATION:dict(limits={})})),{},root/'generations'))as auth,\
                    patch.object(MarketDailyPreparation,'_prepare_items',side_effect=changed):
                with self.assertRaises(InterruptedError):
                    self.run_plan(plan,owner,root,cancelled=stopped.is_set)
            self.assertEqual(auth.call_count,1)
            self.assertEqual(state.submissions,{})


if __name__=='__main__':unittest.main()
