"""官方采集仅填真实Native缺日；原券商缓存仍独立核查。"""
from pathlib import Path
import tempfile,time,unittest
from contextlib import ExitStack
from unittest.mock import patch
from integrations.guanheng.daily_data_update import _save,_load,_descriptor
from integrations.guanheng.daily_price_inputs import prepare_price_inputs


class NativeGap(unittest.TestCase):
    def test_existing_target_or_future_tail_with_hole_have_distinct_requests(self):
        for target_present in (True,False):
            with self.subTest(present=target_present),tempfile.TemporaryDirectory()as directory:
                root=Path(directory)
                def write(path,value):
                    path.parent.mkdir(parents=True,exist_ok=True);_save(path,value);return _descriptor(path)
                identity=dict(symbol='SSE.000925',name='基本面50',market='SSE',security_type='index',listed_on=None,expires_on=None,observed_at=None)
                pool=write(root/'pool.json',dict(schema='guanheng.price-universe.v1',observation_date='2026-11-03',securities={identity['symbol']:identity}))
                base=write(root/'base.json',{})
                ref=write(root/'ref.json',dict(schema='guanheng.security-reference.v1',securities={identity['symbol']:identity},provenance=dict(catalog_sha256='a'*64,details_sha256=None,indices_sha256=None)))
                cal=write(root/'cal.json',dict(kind='official-exchange-calendar/v1',id='synthetic',coverage_start='2026-11-03',coverage_end='2026-11-03',closed_dates=[],evidence=[{}]))
                request=dict(schema='guanheng.daily-price-inputs.v1',universe=pool,current_configuration=base,snapshot_id=None,reference=ref,calendar=cal,connections=dict(batch={},hpr={}),protected_slots=[],authorized_from='20261103',source_kind='sdk-synthetic',index_fallback='official-publishers')
                class Closed:
                    def __init__(self,*args,**kwargs):pass
                    def close(self):pass
                class Market(Closed):
                    def call(self,message):
                        selected=message['request']['from']==20261103
                        bars=([dict(date=20261103)]if target_present else[])if selected else[dict(date=20261104)]
                        return dict(status=dict(code='Ok'),data=dict(archive=dict(first_date=20261102,last_date=20261104,count=2),bars=bars))
                class Batch(Closed):
                    def capture(self,request,output,**kwargs):write(Path(output)/'manifest.json',dict(source_kind='sdk-synthetic',request=request))
                def plan(cache,ref,snapshot,output,**kwargs):return write(Path(output)/'PLAN.json',dict(snapshot_id=snapshot['snapshot_id'],capture=cache,tasks=[]))
                calls=[]
                def official(securities,*args,**kwargs):
                    calls.append(sorted(securities));return write(root/'official.json',dict(securities={}))
                patches={
                    'integrations.guanheng.daily_price_inputs.create_native_source_market':lambda *args:Market(),
                    'guanheng_app.observation.calendars.official_calendar':lambda *args:([dict(date='2026-11-03',is_open=1)],{}),
                    'guanheng_qmt_shm.analysis_batch_source.BatchAnalysisSource':Batch,
                    'integrations.guanheng.source_history_transport.BoundHistorySource':Closed,
                    'integrations.guanheng.daily_price_inputs.prepare_gap_plan':plan,
                    'integrations.guanheng.daily_price_inputs.load_price_capture':lambda d:_load(dict(path=str(Path(d['directory'])/'manifest.json'),sha256=d['sha256'])),
                    'integrations.guanheng.daily_price_inputs.price_batches':lambda *args,**kwargs:[(None,{'000925.SH':dict(status='empty',data={})})],
                    'integrations.guanheng.official_index_prices.prepare_official_index_prices':official}
                with ExitStack()as stack:
                    for name,value in patches.items():stack.enter_context(patch(name,value))
                    prepare_price_inputs(request,root/'inputs',deadline=time.monotonic()+20)
                self.assertEqual(calls,[]if target_present else[['SSE.000925']])
