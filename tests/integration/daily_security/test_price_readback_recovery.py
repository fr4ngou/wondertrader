"""价格回读完成/结果提交前中断时，完整责任快照与原回读共同恢复。"""
from pathlib import Path
import json,time,uuid,tempfile,unittest
from contextlib import ExitStack
from unittest.mock import patch
from integrations.guanheng.daily_data_update import _save,_descriptor,_load
from integrations.guanheng.daily_price_inputs import prepare_price_inputs
from integrations.guanheng.daily_price_continuation import requires_price_continuation

class PriceReadbackRecoveryTests(unittest.TestCase):
    def test_completed_readback_and_interrupted_inputs_keep_original_pending_progress(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);root=Path(temporary.name)
        def write(path,value):
            path.parent.mkdir(parents=True,exist_ok=True);_save(path,value);return _descriptor(path)
        identity=dict(symbol='SSE.510300',name='synthetic ETF',market='SSE',security_type='etf',
                      listed_on=None,expires_on=None,observed_at=None)
        universe=write(root/'universe.json',dict(schema='guanheng.price-universe.v1',
            observation_date='2026-11-03',securities={identity['symbol']:identity}))
        base=write(root/'base.json',{})
        reference=write(root/'reference.json',dict(schema='guanheng.security-reference.v1',
            securities={identity['symbol']:identity},provenance=dict(catalog_sha256='a'*64,
                details_sha256=None,indices_sha256=None)))
        calendar=write(root/'calendar.json',dict(kind='official-exchange-calendar/v1',id='synthetic',
            coverage_start='2026-11-03',coverage_end='2026-11-03',closed_dates=[],evidence=[dict(synthetic=True)]))
        request=dict(schema='guanheng.daily-price-inputs.v1',universe=universe,current_configuration=base,
            snapshot_id=None,reference=reference,calendar=calendar,connections=dict(batch={},hpr={}),
            protected_slots=[],authorized_from='20261103',source_kind='sdk-synthetic')
        class Closed:
            def __init__(self,*a,**kw):pass
            def close(self):pass
        class Market(Closed):
            def call(self,*a,**kw):return dict(status=dict(code='Unavailable'),data={})
        captures=[]
        class Batch(Closed):
            def capture(self,request,output,**kw):
                captures.append(Path(output).name)
                write(Path(output)/'manifest.json',dict(source_kind='sdk-synthetic',request=request))
        progress_calls=[]
        def advance(descriptor,output,owner,**kw):
            state='pending'if not progress_calls else'call_returned';progress_calls.append(state)
            row=dict(index=0,state=state)
            write(Path(output)/'observations'/'000000.json',dict(plan_sha256=descriptor['sha256'],row=row))
            return dict(plan_sha256=descriptor['sha256'],rows=[row])
        def plan(cache,reference,snapshot,output,**kw):
            return write(Path(output)/'PLAN.json',dict(snapshot_id=snapshot['snapshot_id'],capture=cache,
                tasks=[dict(index=0,symbol='510300.SH')]))
        reads=[]
        def prices(cache,*a,**kw):
            reads.append(True)
            if len(reads)==1:raise InterruptedError('after completed readback, before INPUTS commit')
            return [(None,{'510300.SH':dict(status='empty',data={})})]
        patches={
         'integrations.guanheng.daily_price_inputs.create_native_source_market':lambda *a:Market(),
         'guanheng_app.observation.calendars.official_calendar':lambda *a:([dict(date='2026-11-03',is_open=1)],{}),
         'integrations.guanheng.daily_batch_source.DailyBatchAnalysisSource':Batch,
         'guanheng_qmt_shm.market_daily_preparation.MarketDailyPreparation':Closed,
         'integrations.guanheng.source_history_transport.BoundHistorySource':Closed,
         'integrations.guanheng.daily_price_inputs.prepare_gap_plan':plan,
         'integrations.guanheng.daily_price_inputs.advance_gap_plan':advance,
         'integrations.guanheng.daily_price_inputs.load_price_capture':lambda d:_load(dict(path=str(Path(d['directory'])/'manifest.json'),sha256=d['sha256'])),
         'integrations.guanheng.daily_price_inputs.price_batches':prices,
        }
        with ExitStack()as stack:
            for name,value in patches.items():stack.enter_context(patch(name,value))
            try:prepare_price_inputs(request,root/'inputs',deadline=time.monotonic()+30)
            except InterruptedError:pass
            else:raise AssertionError('expected interrupted fixture')
            assert not(root/'inputs'/'INPUTS.json').exists()
            old_sha=_descriptor(root/'inputs'/'readback'/'manifest.json')['sha256']
            result=prepare_price_inputs(request,root/'inputs',deadline=time.monotonic()+30)
        value=_load(result)
        continuation=requires_price_continuation(dict(inputs=result,securities={'SSE.510300':dict(
            target_readable=False,reason='target_not_in_cache')}))
        assert continuation
        assert captures==['cache','readback']
        assert value['preparation']['rows'][0]['state']=='pending'
        assert progress_calls==['pending','call_returned']
        assert value['cache']['sha256']==old_sha
