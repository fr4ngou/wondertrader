"""确定未执行保留原拒绝记录，并由业务owner开始下一捕获；未知保持原ID。"""
from contextlib import contextmanager
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from uuid import uuid4

from guanheng_analysis_window_producer.preparation import DailyHistoryPreparation
from guanheng_analysis_window_producer.runtime import AnalysisWindowProducer
from guanheng_analysis_window_producer.source import SourcePending,SourceUnavailable
from guanheng_qmt_shm.read_retention_client import RetainedReadPending,RetainedReadFailure
from integrations.guanheng.qmt_native_adjustment import SYMBOLS

ROOT=Path('E:/workspace/wondertrader')
ARTIFACTS=json.loads((ROOT/'build/root-analysis-restart-001/normal005/ANALYSIS.json').read_bytes())['configuration']['producer']['artifacts']
CAP=dict(schema='qmt.read-retention.v1',max_lifetime_ms=300000)

class Transport:
    uptime=type('Clock',(),dict(seconds=lambda self:time.monotonic()))()
    @contextmanager
    def rpc_budget(self,seconds):yield
    def binding(self,deadline):
        return dict(binding=dict(generation='synthetic-original'),profile=dict(read_retention=CAP,
            operation_profiles={'market.history_prepare':dict(limits=dict(periods=['1d'],
                max_calendar_days={'1d':3660},total_timeout_ms=30000))}))

class RejectedThenAvailable:
    def __init__(self):self.rejected=None;self.sdk=0;self.calls=[]
    def prepare(self,operation,arguments,slot,*,deadline,expected_binding=None):
        if not slot.exists():
            record=dict(request=dict(request_id=str(uuid4()),arguments=arguments),
                binding=dict(generation='synthetic-original'),result=None,received_at=None)
            if self.rejected is None:
                record['admission_rejection']=dict(status=400,error_code='read_ticket_ended')
                self.rejected=slot
            slot.write_text(json.dumps(record),encoding='utf8')
        record=json.loads(slot.read_bytes());self.calls.append((str(slot),record['request']['request_id']))
        if record.get('admission_rejection'):raise RetainedReadFailure('read_admission_rejected')
        self.sdk+=1
        reply=dict(ok=True,data=dict(schema='qmt.history-preparation-result.v1',symbol=arguments['symbol'],
            period='1d',start_time=arguments['start_time'],end_time=arguments['end_time'],
            effect='call_returned',coverage='unknown'))
        record.update(result=reply,received_at=datetime.now(timezone.utc).isoformat())
        slot.write_text(json.dumps(record),encoding='utf8')
        return dict(reply=reply)

def preparation(root,client):
    os.environ['AWP_REJECTION_TEST_SECRET']='synthetic-rejection-contract-secret-0001'
    value=DailyHistoryPreparation(dict(connection=dict(base_url='http://127.0.0.1:1',key_id='test',
        secret_env='AWP_REJECTION_TEST_SECRET',timeout=1,read_retention=CAP),refresh_interval_seconds=1),
        checkpoint=root/'PREPARATION.json')
    value.source=Transport();value.retained=client
    return value

class PreparationRejectionContracts(unittest.TestCase):
    def test_confirmed_rejection_stays_in_original_slot_and_allows_next_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);client=RejectedThenAvailable();p=preparation(root,client)
            request=dict(capture_id=str(uuid4()),symbols=list(SYMBOLS))
            with self.assertRaises(SourceUnavailable):
                p.prepare(request,root/'first',dict(closed_through='2026-10-30'),deadline=time.monotonic()+30)
            raw=client.rejected.read_bytes()
            for unused in range(2):
                with self.assertRaises(SourceUnavailable):
                    p.prepare(request,root/'first',dict(closed_through='2026-10-30'),deadline=time.monotonic()+30)
            self.assertEqual(client.sdk,0);self.assertEqual(client.rejected.read_bytes(),raw)
            self.assertEqual(len(set(client.calls)),1)
            p.prepare(dict(capture_id=str(uuid4()),symbols=list(SYMBOLS)),root/'next',
                dict(closed_through='2026-10-30'),deadline=time.monotonic()+30)
            self.assertEqual(client.sdk,8);self.assertEqual(client.rejected.read_bytes(),raw)

    def test_original_owner_advances_capture_after_definite_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);client=RejectedThenAvailable();p=preparation(root,client)
            class Provider:
                def __init__(self):self.ids=[];self.ready=threading.Event()
                def capture(self,request,directory,*,deadline):
                    self.ids.append(request['capture_id'])
                    p.prepare(request,directory,dict(closed_through='2026-10-30'),deadline=deadline)
                    self.ready.set();raise SourcePending('isolated_stop_before_native')
            provider=Provider()
            owner=AnalysisWindowProducer(provider,directory=root/'owner',publication=root/'window.json',
                artifacts=ARTIFACTS,interval_seconds=.05,refresh_seconds=3,
                source_identity=dict(provider='isolated-confirmed-rejection-v1'))
            owner.start(deadline=time.monotonic()+3)
            try:
                # 观察使用该夹具原刷新预算；磁盘落盘可以合法消耗完整三秒。
                self.assertTrue(provider.ready.wait(owner.refresh_seconds),'source available but capture remains blocked')
                self.assertGreaterEqual(len(set(provider.ids)),2);self.assertEqual(client.sdk,8)
                self.assertTrue(client.rejected.exists())
            finally:self.assertTrue(owner.close(3))

if __name__=='__main__':unittest.main()
