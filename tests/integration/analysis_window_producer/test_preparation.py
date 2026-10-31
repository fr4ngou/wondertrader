"""HPR 编排必要回归；正式 SDK 缓存副作用由独立完整主链证明。"""
from contextlib import contextmanager
from datetime import datetime,timedelta,timezone
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import guanheng_analysis_window_producer.preparation as preparation_module
from uuid import uuid4

from guanheng_analysis_window_producer.preparation import DailyHistoryPreparation
from guanheng_analysis_window_producer.runtime import create_producer
from guanheng_analysis_window_producer.source import SourcePending
from integrations.guanheng.source_history_transport import SourcePending as TransportPending
from integrations.guanheng.qmt_native_adjustment import SYMBOLS

ROOT=Path('E:/workspace/wondertrader')


class Transport:
    def __init__(self,*,lose=False,unknown=False,calendar=3660):
        self.lose,self.unknown=lose,unknown
        self.hold=False
        self.calendar=calendar
        self.executions=[]
        self.observations=[]
        self.uptime=type('Clock',(),dict(seconds=lambda self:time.monotonic()))()

    @contextmanager
    def rpc_budget(self,seconds):
        assert .1<=seconds<=30
        yield

    def binding(self,deadline):
        return dict(binding=dict(generation='original'),profile=dict(operation_profiles={
            'market.history_prepare':dict(limits=dict(periods=['1d'],total_timeout_ms=30000,
                max_calendar_days={'1d':self.calendar}))}))

    def plan(self,operation,args,metadata,deadline):
        assert operation=='market.history_prepare'
        return dict(request=dict(request_id=str(uuid4()),operation_id=operation,arguments=args),
            binding=metadata['binding'],result=None,attempted=False)

    def observe(self,record,save,deadline):
        request=record['request']
        self.observations.append(request['request_id'])
        if not record['attempted']:
            self.executions.append(request)
            record['attempted']=True
            save()
            if self.lose:
                self.lose=False
                raise TransportPending('injected lost reply')
        if self.hold: raise TransportPending('injected unavailable original reply')
        if record['result'] is None:
            record['result']=dict(ok=not self.unknown,error_code='preparation_unknown' if self.unknown else None,
                data=dict(schema='qmt.history-preparation-result.v1',symbol=request['arguments']['symbol'],
                    period='1d',start_time=request['arguments']['start_time'],end_time=request['arguments']['end_time'],
                    effect='call_returned',coverage='unknown'))
            save()
        return record['result']


class PreparationContracts(unittest.TestCase):
    def make(self,root,transport,clock=None):
        os.environ['AWP_PREPARATION_TEST_SECRET']='synthetic-history-preparation-test-secret'
        owner=DailyHistoryPreparation(dict(connection=dict(base_url='http://127.0.0.1:1',key_id='test',
            secret_env='AWP_PREPARATION_TEST_SECRET',timeout=1),refresh_interval_seconds=10),
            checkpoint=root/'PREPARATION.json',**(dict(clock=clock) if clock else {}))
        owner.source=transport
        return owner

    def request(self): return dict(capture_id=str(uuid4()),symbols=list(SYMBOLS))

    def test_lost_reply_keeps_original_request_and_return_clock(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);transport=Transport(lose=True);owner=self.make(root,transport)
            request=self.request();capture=root/'capture';closure=dict(closed_through='2026-10-30')
            owner.prepare(request,capture,closure,deadline=time.monotonic()+30)
            first=transport.executions[0]
            self.assertEqual(len(transport.executions),8)
            self.assertEqual(transport.observations[:2],[first['request_id']]*2)
            self.assertEqual(json.loads((capture/(SYMBOLS[0]+'.json')).read_bytes())['request'],first)
            before=(root/'PREPARATION.json').read_bytes()
            owner.prepare(request,capture,closure,deadline=time.monotonic()+30)
            self.assertEqual(len(transport.executions),8)
            self.assertEqual((root/'PREPARATION.json').read_bytes(),before)

    def test_absolute_deadline_then_resume_preserves_request(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);transport=Transport();transport.hold=True
            owner=self.make(root,transport);request=self.request()
            # 确定的业务时钟让同一 .25 秒截止覆盖已受理请求；磁盘fsync耗时
            # 不决定夹具能否进入其声明的失回执窗口。
            now=[100.]
            def advance(seconds):now[0]+=seconds
            clock=SimpleNamespace(monotonic=lambda:now[0],sleep=advance)
            with patch.object(preparation_module,'time',clock), self.assertRaises(SourcePending):
                owner.prepare(request,root/'capture',dict(closed_through='2026-10-30'),deadline=100.25)
            self.assertEqual(len(transport.executions),1)
            first=transport.executions[0]
            transport.hold=False
            owner.prepare(request,root/'capture',dict(closed_through='2026-10-30'),deadline=time.monotonic()+30)
            self.assertEqual(len(transport.executions),8)
            self.assertEqual(transport.executions[0],first)

    def test_unknown_completion_does_not_execute_again(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);transport=Transport(unknown=True);owner=self.make(root,transport)
            request=self.request()
            for unused in range(2):
                with self.assertRaises(SourcePending):
                    owner.prepare(request,root/'capture',dict(closed_through='2026-10-30'),deadline=time.monotonic()+30)
            self.assertEqual(len(transport.executions),1)
            self.assertFalse((root/'PREPARATION.json').exists())

    def test_coalescing_same_day_revision_and_new_day_range(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);transport=Transport();now=[datetime.now(timezone.utc)]
            owner=self.make(root,transport,lambda:now[0])
            def run(number,end):
                owner.prepare(self.request(),root/str(number),dict(closed_through=end),deadline=time.monotonic()+30)
            run(1,'2026-10-29')
            self.assertTrue(all(r['arguments']['start_time']==r['arguments']['end_time']=='20261029' for r in transport.executions))
            # 合并间隔相对已保存的实收时刻；本地I/O耗时不能使注入时钟落到实收之前。
            now[0]=datetime.fromisoformat(json.loads((root/'PREPARATION.json').read_bytes())['returned_at'])+timedelta(seconds=1)
            run(2,'2026-10-29')
            self.assertEqual(len(transport.executions),8)
            self.assertTrue(json.loads((root/'2/PLAN.json').read_bytes())['coalesced'])
            now[0]+=timedelta(seconds=11)
            run(3,'2026-10-29')
            self.assertEqual(len(transport.executions),16)
            run(4,'2026-10-30')
            self.assertEqual(len(transport.executions),24)
            self.assertTrue(all(r['arguments']['start_time']=='20261029' and r['arguments']['end_time']=='20261030'
                for r in transport.executions[-8:]))

    def test_omitted_preparation_preserves_a5_configuration_identity(self):
        base=ROOT/'build/root-analysis-restart-002/normal001'
        configuration=json.loads((base/'ANALYSIS.json').read_bytes())['configuration']
        os.environ['QAB_TEST_HTTP']='synthetic-analysis-main-http-secret-00002'
        owner=create_producer(configuration)
        self.assertIsNone(owner.provider.preparation)
        self.assertEqual(owner._configuration,json.loads((base/'owner/CONFIGURATION.json').read_bytes())['configuration'])

    def test_one_day_source_budget_still_crosses_days(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);transport=Transport(calendar=1);owner=self.make(root,transport)
            owner.prepare(self.request(),root/'first',dict(closed_through='2026-10-29'),deadline=time.monotonic()+30)
            owner.prepare(self.request(),root/'second',dict(closed_through='2026-10-30'),deadline=time.monotonic()+30)
            self.assertEqual(len(transport.executions),24)
            self.assertTrue(all(row['arguments']['start_time']==row['arguments']['end_time']
                for row in transport.executions))


if __name__=='__main__':unittest.main()
