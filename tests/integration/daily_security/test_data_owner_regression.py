"""统一数据owner的待补恢复、历史身份和Source换代回归；全部来源为隔离替身。"""
from pathlib import Path
import json, time, unittest, uuid, tempfile
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import patch

from integrations.guanheng import daily_data_update as update
from integrations.guanheng import daily_data_service as service
from integrations.guanheng.daily_price_scope import prepare_price_scope
from integrations.guanheng.security_reference import SecurityReference


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    update._save(path,value)
    return update._descriptor(path)

def security(symbol,kind,name='synthetic retained identity'):
    return dict(symbol=symbol,name=name,market=symbol.split('.')[0],security_type=kind,
                listed_on=None,expires_on=None,observed_at=None)

class DataOwnerRegressionTests(unittest.TestCase):
    def root(self):
        directory=tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        return Path(directory.name)

    def test_empty_extra_raw_result_publishes_empty_archive_and_resumes(self):
        from integrations.guanheng import daily_price_update as prices,daily_price_archive as archive
        root=self.root();symbol='SSE.510300';identity=security(symbol,'etf')
        universe=write(root/'universe.json',dict(securities={symbol:identity}))
        scope=write(root/'scope.json',dict(universe=universe,source_members=[],reference=None,
            observation_date='2026-11-03',securities={symbol:identity},groups=[]))
        inputs=write(root/'inputs.json',dict(schema='guanheng.daily-price-input-result.v1',
            cache=dict(directory='unused',sha256='0'*64),securities={symbol:dict(reason='source_unavailable')}))
        native=write(root/'native.json',{});base=write(root/'base.json',{})
        request=dict(scope=scope,current_configuration=base,snapshot_id='0'*64,calendar=None,
            connections={},protected_slots=[],authorized_from='20260701',source_kind='sdk-synthetic',
            maximum_history_rows=2000,previous_archives=[],helper=dict(path='unused',sha256='0'*64))
        class Market:
            def call(self,*args,**kwargs):return dict(status=dict(code='Unavailable'),data={})
            def close(self):pass
        def front(inputs,market,previous,output,helper,**kwargs):
            return write(Path(output)/'RESULT.json',dict(archive=None))
        manifest=dict(source_kind='sdk-synthetic',request=dict(capture_id=str(uuid.uuid4())))
        with ExitStack()as stack:
            for name,value in dict(prepare_price_inputs=lambda *a,**kw:inputs,
                    compose_native_import=lambda *a:{},_catalog=lambda *a:dict(native_reader={}),
                    create_native_source_market=lambda *a:Market(),
                    compose_static_archive=lambda base,*a,**kw:base,prepare_front_archive=front).items():
                stack.enter_context(patch.object(prices,name,value))
            stack.enter_context(patch.object(archive,'load_price_capture',return_value=manifest))
            stack.enter_context(patch.object(archive,'price_batches',return_value=[(None,{'510300.SH':dict(data={})})]))
            stack.enter_context(patch('integrations.guanheng.daily_archive_prepare._Native',side_effect=AssertionError('no Helper')))
            result=prices.prepare_price_update(request,native,base,root/'work',deadline=time.monotonic()+10,cancelled=lambda:False)
            resumed=prices.prepare_price_update(request,native,base,root/'work',deadline=time.monotonic()+10,cancelled=lambda:False)
        self.assertEqual(result,resumed)
        value=update._load(result);raw=update._load(value['additional_archives'][0])
        self.assertEqual(raw,dict(schema='guanheng.daily-native-archive.v1',entries=[]))
        self.assertEqual(value['counts']['SSE.etf']['known_scope_count'],1)
        self.assertFalse(value['securities'][symbol]['target_readable'])
        self.assertEqual(value['securities'][symbol]['reason'],'source_unavailable')

    def test_source_binding_change_rejects_old_cursor_before_new_slot(self):
        from integrations.guanheng.source_reference_capture import capture_reference
        from guanheng_qmt_shm import security_reference_source as seam
        from guanheng_qmt_shm.read_retention_client import RetainedReadBindingChanged
        root=self.root()/'capture'
        operations=seam.UNIVERSE,seam.DETAILS
        limits=dict(max_page_size=256,max_detail_symbols=64)
        profile=dict(operation_profiles={op:dict(policy_id=seam.POLICY,policy_version='1.0',limits=limits)
            for op in operations},read_retention=dict(max_lifetime_ms=30000))
        page=dict(schema='qmt.security-universe.v1',catalog_id='a'*64,captured_at='2026-11-04T01:00:00Z',
            source_as_of=None,markets=['SH'],security_types=['stock'],state='complete',total_count=2,
            groups=[dict(market='SH',security_type='stock',state='complete',expected_count=2,
                observed_count=2,source_groups=['synthetic'],reason_code=None)],
            items=[dict(symbol='600000.SH',market='SH',security_type='stock',source_groups=['synthetic'])],
            next_cursor='original-A-cursor')
        calls=[]
        class Client:
            def __init__(self,*a,**kw):self.metadata_reads=0
            def metadata(self,**kw):
                self.metadata_reads+=1
                return dict(profile=profile,binding=dict(synthetic_epoch='A'if self.metadata_reads<=4 else'B'))
            def read(self,operation,arguments,slot,**kw):
                binding=kw['expected_binding']
                # 原保留客户端在写slot前核认证绑定；模拟外层预检A后SDK已切换B的窗口。
                if self.metadata_reads>=5 and binding!=dict(synthetic_epoch='B'):
                    raise RetainedReadBindingChanged('read_source_binding_changed')
                calls.append(dict(operation=operation,arguments=arguments,binding=binding))
                write(Path(slot),dict(binding=binding,profile=profile))
                return dict(reply=dict(ok=True,data=page),request_id='synthetic-'+str(len(calls)))
        with patch.object(seam,'RetainedReadClient',Client),patch.object(seam,'validate_result',lambda *a:None):
            source=seam.SecurityReferenceSource(None)
            with self.assertRaises(RetainedReadBindingChanged):
                capture_reference(source,dict(markets=['SH'],security_types=['stock'],limit=1),root,
                    deadline=time.monotonic()+30)
        self.assertEqual(len(calls),1)
        self.assertFalse((root/'universe-001.json').exists())
        self.assertEqual(calls[0]['binding'],dict(synthetic_epoch='A'))

    def test_stock_pending_and_late_result_request_new_revision_without_mutating_readback(self):
        self._assert_stock_readback_recovery()

    def test_unadvanced_stock_is_frozen_before_late_return_and_old_readback_resume(self):
        self._assert_stock_readback_recovery(unadvanced=True)

    def _assert_stock_readback_recovery(self,unadvanced=False):
        root=self.root()
        pool=write(root/'pool.json',dict(date='2026-11-03',members=['sh.600000']))
        cache=root/'cache';manifest=dict(request=dict(universe=pool))
        capture=write(cache/'manifest.json',manifest)
        cache_descriptor=dict(directory=str(cache),sha256=capture['sha256'])
        archive=write(root/'archive.json',{})
        prepared=write(root/'native.json',dict(state='completed',capture_sha256=capture['sha256'],
            helper_sha256='a'*64,archive=archive))
        base=write(root/'base.json',{})
        price=write(root/'price.json',dict(inputs=None,reference={},additional_archives=[],maximum_history_rows=2000,securities={
            'SSE.600000':dict(target_readable=unadvanced,reason='confirmed_missing_native'),
            **({'SSE.600001':dict(target_readable=False,reason='confirmed_missing_native')}if unadvanced else{})}))
        request=dict(schema='guanheng.daily-data-update.v1',publication_directory=str(root/'publication'),
            cache=cache_descriptor,universe=pool,daily_facts={},security_reference={},calendar={},
            base_configuration=base,basic_capture={},helper=dict(sha256='a'*64),previous_stores=[],
            previous_archives=[],protected_slots=[],authorized_from='20261103',authorized_to='20261103',
            additional_archives=[],connections=dict(batch={},hpr={}),prepared_native=prepared,price_maintenance={})
        def plan(capture,reference,snapshot,output,**kwargs):
            return write(output/'PLAN.json',dict(schema='guanheng.daily-gap-plan.v1',
                snapshot_id=snapshot['snapshot_id'],capture=capture,authorized_from='20261103',
                authorized_to='20261103',tasks=[dict(index=0,symbol='600000.SH')]+([dict(index=1,symbol='600001.SH')]if unadvanced else[])))
        advances=[]
        def advance(descriptor,output,owner,**kwargs):
            output=Path(output);observations=output/'observations'
            if advances:
                self.assertEqual(json.loads((observations/'000000.json').read_bytes())['row']['state'],'call_returned')
                rows=[] # 原已返回任务跳过；原未推进项本次晚到返回。
                if unadvanced:
                    rows=[dict(index=1,state='call_returned')]
                    write(observations/'000001.json',dict(plan_sha256=descriptor['sha256'],row=rows[0]))
            else:
                rows=[dict(index=0,state='call_returned'if unadvanced else'pending',request_id='original-synthetic-uuid',coverage='unknown')]
                write(observations/'000000.json',dict(plan_sha256=descriptor['sha256'],row=rows[0]))
            advances.append(rows)
            return dict(rows=rows,plan_sha256=descriptor['sha256'])
        def snapshot(base,native,universe,basic,output,**kwargs):
            snapshot=write(output/'snapshot.json',dict(snapshot_id='synthetic-snapshot'))
            configuration=write(output/'source.json',dict(snapshot=snapshot))
            write(output/'PREPARED.json',dict(configuration=configuration['path'],
                configuration_sha256=configuration['sha256'],observation_date='2026-11-03',
                snapshot_id='synthetic-snapshot'))
        class Closed:
            def __init__(self,*a,**kw):pass
            def close(self):pass
        class Facts(Closed):
            def query(self,*a):return dict(members=['SSE.600000'])
        replacements={
            'integrations.guanheng.daily_gap_update.prepare_gap_plan':plan,
            'integrations.guanheng.daily_gap_update.advance_gap_plan':advance,
            'integrations.guanheng.day_facts.DayFactsStore':Facts,
            'integrations.guanheng.security_reference.SecurityReference':Closed,
            'integrations.guanheng.source_history_transport.BoundHistorySource':Closed,
            'integrations.guanheng.market_snapshot_prepare.load_snapshot_basics':lambda *a:({},'a'*64),
            'integrations.guanheng.market_snapshot_prepare.prepare_market_snapshot':snapshot,
            'guanheng_qmt_shm.analysis_batch_source.read_capture':lambda *a:manifest,
            'guanheng_qmt_shm.analysis_batch_source.BatchAnalysisSource':Closed,
            'guanheng_qmt_shm.market_daily_preparation.MarketDailyPreparation':Closed,
            'guanheng_qmt_shm.market_daily_cache.assess':lambda *a:dict(full_coverage=False),
            'integrations.guanheng.daily_price_update.prepare_price_update':lambda *a,**kw:price,
            'integrations.guanheng.daily_data_update._capture':lambda *a:cache_descriptor,
            'integrations.guanheng.market_generation.GenerationPublisher.publish':lambda *a,**kw:({'configuration':a[1]},'b'*64),
        }
        work=root/'work';readbacks=[]
        replacements['integrations.guanheng.daily_data_update._capture']=lambda *a:(readbacks.append(True)or cache_descriptor)
        with ExitStack()as stack:
            for name,value in replacements.items():stack.enter_context(patch(name,value))
            first=update.run_update(request,work,deadline=time.monotonic()+60)
            observation=work/'gap-work'/'observations'/'000000.json'
            prior=json.loads(observation.read_bytes());prior['row']['state']='call_returned';write(observation,prior)
            resumed=update.run_update(request,work,deadline=time.monotonic()+60)
        self.assertTrue(first['continuation_required']);self.assertTrue(resumed['continuation_required'])
        self.assertEqual(resumed['gap_readback_progress']['rows'][0]['request_id'],'original-synthetic-uuid')
        self.assertEqual(first['gap_progress']['rows'][0]['state'],'call_returned'if unadvanced else'pending')
        self.assertEqual(resumed['gap_progress']['rows'],[dict(index=1,state='call_returned')]if unadvanced else[])
        self.assertEqual(len(readbacks),1)
        if unadvanced:self.assertEqual(resumed['gap_readback_progress']['rows'][1]['state'],'unattempted')

    def test_published_reference_preserves_old_etf_identity_and_current_group_count(self):
        root=self.root()
        old='SSE.510300';new='SSE.600000'
        baseline=write(root/'baseline.json',dict(schema='guanheng.security-reference.v1',
            securities={old:security(old,'etf')},provenance=dict(catalog_sha256='a'*64,
                details_sha256=None,indices_sha256=None)))
        evidence=write(root/'evidence.json',dict(synthetic=True))
        dynamic=write(root/'dynamic.json',dict(schema='guanheng.security-reference.v2',
            securities={new:security(new,'stock')},provenance=dict(catalog_id='a'*64,
                captured_at='2026-11-04T01:00:00+00:00',source_as_of=None,evidence=[evidence],groups=[
                dict(market='SH',security_type='stock',state='complete',expected_count=1,observed_count=1,
                    source_groups=['synthetic'],reason_code=None)])))
        configuration=write(root/'configuration.json',dict(security_reference=baseline))
        pool=write(root/'pool.json',dict(members=['sh.600000']))
        scope=dict(baseline_reference=baseline,reference_connection={},scope=dict(markets=['SH'],
            security_types=['stock'],limit=256),authorized_from='20260701',maximum_history_rows=10000)
        class Closed:
            def __init__(self,*a,**kw):pass
            def close(self):pass
        state=dict(reference=dynamic,groups=json.loads(Path(dynamic['path']).read_bytes())['provenance']['groups'])
        with patch('integrations.guanheng.source_history_transport.BoundHistorySource',Closed),\
             patch('guanheng_qmt_shm.security_reference_source.SecurityReferenceSource',Closed),\
             patch('integrations.guanheng.source_reference_capture.capture_reference',return_value=state):
            descriptor=prepare_price_scope(scope,'2026-11-03',pool,dict(configuration=configuration),root/'scope',
                deadline=time.monotonic()+10,cancelled=lambda:False)
        result=update._load(descriptor);reader=SecurityReference(result['reference'])
        try:actual=reader.security(dict(basics={}),old)
        finally:reader.close()
        self.assertEqual(result['securities'][old]['security_type'],'etf')
        self.assertEqual(actual,security(old,'etf'))
        composite=update._load(result['reference'])
        self.assertEqual(composite['schema'],'guanheng.security-reference.v3')
        self.assertEqual(composite['provenance']['current_reference'],dynamic)
        self.assertEqual(update._load(dynamic)['provenance']['groups'][0]['expected_count'],1)
        # 当前叶原件仍以摘要固定；修改后组合Reader必须拒绝采用。
        Path(dynamic['path']).write_bytes(b'changed-current')
        with self.assertRaises(ValueError):SecurityReference(result['reference'])

if __name__=='__main__':unittest.main()
