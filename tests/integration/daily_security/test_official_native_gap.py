"""原价补采先核真实Native记录，官方来源仍只填实际目标日缺口。"""
from pathlib import Path
import tempfile,time,unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import patch
from integrations.guanheng.daily_data_update import _save,_load,_descriptor
from integrations.guanheng.daily_gap_plan import load_gap_plan
from integrations.guanheng.daily_price_inputs import prepare_price_inputs


class NativeGap(unittest.TestCase):
    def test_existing_target_or_future_tail_with_hole_have_distinct_requests(self):
        for target_present in (True,False):
            with self.subTest(present=target_present),tempfile.TemporaryDirectory()as directory:
                root=Path(directory)
                def write(path,value):
                    path.parent.mkdir(parents=True,exist_ok=True);_save(path,value);return _descriptor(path)
                identity=dict(symbol='SSE.000925',name='基本面50',market='SSE',security_type='index',listed_on=None,expires_on=None,observed_at=None)
                pool=write(root/'pool.json',dict(schema='guanheng.price-universe.v1',observation_date='2026-11-09',securities={identity['symbol']:identity}))
                base=write(root/'base.json',{})
                ref=write(root/'ref.json',dict(schema='guanheng.security-reference.v1',securities={identity['symbol']:identity},provenance=dict(catalog_sha256='a'*64,details_sha256=None,indices_sha256=None)))
                cal=write(root/'cal.json',dict(kind='official-exchange-calendar/v1',id='synthetic',coverage_start='2026-11-03',coverage_end='2026-11-09',closed_dates=[],evidence=[{}]))
                request=dict(schema='guanheng.daily-price-inputs.v1',universe=pool,current_configuration=base,snapshot_id=None,reference=ref,calendar=cal,connections=dict(batch={},hpr={}),protected_slots=[],authorized_from='20261103',source_kind='sdk-synthetic',index_fallback='official-publishers')
                class Closed:
                    def __init__(self,*args,**kwargs):pass
                    def close(self):pass
                bar=dict(open=5,high=6,low=4,close=5,volume=2,amount=10)
                archive_queries=[]
                class Market(Closed):
                    def call(self,message):
                        archive_queries.append(message['request'])
                        days=[20261103,20261109] if target_present else [20261103]
                        return dict(status=dict(code='Ok'),data=dict(
                            archive=dict(first_date=20261103,last_date=20261110,count=len(days)+1),
                            bars=[dict(date=day,**bar) for day in days]))
                def capture(request,output,*args,**kwargs):
                    manifest=dict(source_kind='sdk-synthetic',request=request,batches=[])
                    write(Path(output)/'manifest.json',manifest)
                    write(Path(output)/'BINDING.json',dict(binding={}))
                def read_capture(path):
                    return _load(_descriptor(Path(path)/'manifest.json'))
                def price_batches(*args,**kwargs):
                    yield None, {'000925.SH': dict(status='observed',data={
                        '20261104':dict(bar,close=0),'20261106':bar})}
                requested=[]
                def advance(plan,*args,**kwargs):
                    requested.extend(day for row in load_gap_plan(plan)['tasks'] for day in row['dates'])
                    return dict(plan_sha256=plan['sha256'],rows=[])
                calls=[]
                def official(securities,*args,**kwargs):
                    calls.append(sorted(securities));return write(root/'official.json',dict(securities={}))
                patches={
                    'integrations.guanheng.daily_price_inputs.create_native_source_market':lambda *args:Market(),
                    'guanheng_app.observation.calendars.official_calendar':lambda *args:(
                        [dict(date=f'2026-11-{day:02}',is_open=1) for day in (3,4,5,6,9)],{}),
                    'guanheng_qmt_shm.analysis_batch_source.read_capture':read_capture,
                    'guanheng_qmt_shm.market_daily_preparation.MarketDailyPreparation':Closed,
                    'integrations.guanheng.source_history_transport.BoundHistorySource':Closed,
                    'integrations.guanheng.daily_price_capture.capture_price_window':capture,
                    'integrations.guanheng.daily_price_inputs.advance_gap_plan':advance,
                    'integrations.guanheng.daily_price_inputs.price_batches':price_batches,
                    'integrations.guanheng.analysis_price_capture.price_batches':price_batches,
                    'integrations.guanheng.official_index_prices.prepare_official_index_prices':official}
                with ExitStack()as stack:
                    for name,value in patches.items():stack.enter_context(patch(name,value))
                    facts=SimpleNamespace(security_state=lambda day,symbol:
                        dict(qualification='qualified',tradestatus='0') if day=='2026-11-05' else None)
                    result=prepare_price_inputs(request,root/'inputs',deadline=time.monotonic()+20,daily_facts=facts)
                    self.assertEqual(prepare_price_inputs(request,root/'inputs',deadline=time.monotonic()+20,daily_facts=facts),result)
                self.assertEqual([(row['from'],row['to'],row['view'],row['adjustment']) for row in archive_queries],
                                 [(20261103,20261109,'archive','none')])
                self.assertEqual(requested,['20261104'] if target_present else ['20261104','20261109'])
                self.assertEqual([row['date'] for row in load_gap_plan(_load(result)['plan'])['exclusions']],['20261105'])
                self.assertEqual(calls,[]if target_present else[['SSE.000925']])
