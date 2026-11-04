"""证券资料根因回归：冻结分页、真实分类、缺项、旧身份与有限资源。"""
import copy,json,math,threading,unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from guanheng_qmt_shm_agent.security_reference import (SecurityReferenceAdapter,UNIVERSE,DETAILS,
    POLICY,arguments,limits,validate_result)
from guanheng_qmt_shm_agent.errors import GatewayError
from guanheng_qmt_shm_agent.protocol import ProtocolError,canonical
from guanheng_qmt_shm_agent.read_capabilities import explicit_profile_version
from guanheng_qmt_shm.security_reference_source import SecurityReferenceSource


def scope(**changes):
    value=dict(schema='qmt.security-reference-limits.v1',max_page_size=256,max_detail_symbols=64,
        max_catalog_symbols=20000,max_catalogs=2,catalog_lifetime_seconds=900,max_cache_bytes=8*1024*1024,
        max_data_bytes=300*1024,source_groups=[dict(market='SH',security_type=t,sources=[dict(node='',name=t)])for t in ('stock','etf','index')])
    value.update(changes);return value

class SDK:
    def __init__(self,rows=None):
        self.rows=rows or {'stock':['510300.SH','000002.SH'],'etf':['600000.SH'],'index':[]}
        self.calls=[];self.detail={}
    def sectors(self,node):self.calls.append(('list',node));return [list(self.rows),[]]
    def get_stock_list_in_sector(self,name):
        self.calls.append(('members',name));value=self.rows[name]
        if isinstance(value,Exception):raise value
        return value
    def get_instrumentdetail(self,symbol):self.calls.append(('detail',symbol));return self.detail.get(symbol)

class ReferenceTests(unittest.TestCase):
    def make(self,sdk=None,**changes):
        sdk=sdk or SDK();self.clock=[100.]
        return sdk,SecurityReferenceAdapter(sdk,scope(**changes),524288,sdk.sectors,lambda:self.clock[0])
    def read(self,owner,**changes):
        args=dict(markets=['SH'],security_types=['stock','etf','index'],limit=1,cursor=None);args.update(changes)
        value=owner.execute(UNIVERSE,args,9999)
        validate_result(dict(operation_id=UNIVERSE,arguments=args),dict(ok=True,data=value));return value
    def error(self,code,call):
        with self.assertRaises(GatewayError)as raised:call()
        self.assertEqual(raised.exception.code,code)
    def test_pages_freeze_identity_scope_count_and_detach_returned_rows(self):
        sdk,owner=self.make();page=self.read(owner);original=copy.deepcopy(page);calls=len(sdk.calls)
        sdk.rows['stock'].append('000003.SH');page['groups'][0]['observed_count']=999;page['items'][0]['symbol']='999999.SH'
        second=self.read(owner,cursor=original['next_cursor'])
        self.assertEqual(second['catalog_id'],original['catalog_id']);self.assertEqual(second['captured_at'],original['captured_at'])
        self.assertEqual(second['total_count'],3);self.assertEqual(second['groups'],original['groups']);self.assertEqual(len(sdk.calls),calls)
        all_items=original['items']+second['items'];third=self.read(owner,cursor=second['next_cursor']);all_items+=third['items']
        self.assertIsNone(third['next_cursor']);self.assertEqual(len({v['symbol']for v in all_items}),3)
        self.assertEqual({v['symbol']:v['security_type']for v in all_items}['510300.SH'],'stock')
        self.assertEqual({v['symbol']:v['security_type']for v in all_items}['600000.SH'],'etf')
    def test_expiry_eviction_scope_tamper_and_source_generation_are_explicit(self):
        sdk,owner=self.make();first=self.read(owner)
        self.error('security_catalog_cursor_invalid',lambda:self.read(owner,cursor=first['next_cursor'],limit=2))
        self.error('security_catalog_cursor_invalid',lambda:self.read(owner,cursor=first['next_cursor']+'x'))
        other=SecurityReferenceAdapter(sdk,scope(),524288,sdk.sectors,lambda:self.clock[0])
        self.error('security_catalog_cursor_invalid',lambda:self.read(other,cursor=first['next_cursor']))
        self.read(owner);self.read(owner);self.assertEqual(len(owner.catalogs),2)
        self.error('security_catalog_expired',lambda:self.read(owner,cursor=first['next_cursor']))
        latest=self.read(owner);self.clock[0]+=900
        self.error('security_catalog_expired',lambda:self.read(owner,cursor=latest['next_cursor']))
        self.assertFalse(owner.catalogs)
    def test_missing_failed_and_empty_groups_keep_distinct_qualification(self):
        sdk,owner=self.make(SDK({'stock':[],'etf':RuntimeError('private SDK body')}))
        value=self.read(owner,limit=256);groups={v['security_type']:v for v in value['groups']}
        self.assertEqual(groups['stock']['state'],'complete');self.assertEqual(groups['stock']['expected_count'],0)
        self.assertEqual(groups['etf']['state'],'unavailable');self.assertEqual(groups['etf']['reason_code'],'source_call_failed')
        self.assertEqual(groups['index']['reason_code'],'source_group_unavailable');self.assertIsNone(value['total_count'])
        self.assertNotIn(b'private SDK body',canonical(value))
        _,unsupported=self.make(source_groups=[]);value=self.read(unsupported)
        self.assertTrue(all(v['state']=='unsupported'and v['expected_count']is None for v in value['groups']))
    def test_conflict_retains_unknown_security_and_full_original_group_counts(self):
        sdk,owner=self.make(SDK({'stock':['510300.SH'],'etf':['510300.SH'],'index':[]}))
        value=self.read(owner);self.assertEqual(value['items'][0]['security_type'],'unknown')
        self.assertEqual(value['items'][0]['source_groups'],['etf','stock']);self.assertIsNone(value['total_count'])
        self.assertEqual([v['state']for v in value['groups']],['partial','partial','complete'])
        self.assertTrue(all(v['observed_count']==1 for v in value['groups'][:2]))
    def test_details_preserve_missing_zero_nonfinite_sentinels_and_market_conflict(self):
        sdk,owner=self.make();sdk.detail={'510300.SH':dict(ExchangeID='SH',InstrumentID='510300',InstrumentName='',OpenDate=99999999,ExpireDate=0,IsTrading=False,FloatVolumn=0,TotalVolumn=math.nan),'600000.SH':dict(ExchangeID='SZ',InstrumentID='600000',InstrumentName='错误市场',OpenDate=20200101,IsTrading=True)}
        args=dict(catalog_id=None,symbols=['510300.SH','600000.SH','000002.SH'])
        value=owner.execute(DETAILS,args,9999);validate_result(dict(operation_id=DETAILS,arguments=args),dict(ok=True,data=value))
        first,conflict,missing=value['items'];self.assertIsNone(first['name']);self.assertIsNone(first['listed_on']);self.assertIsNone(first['expires_on'])
        self.assertEqual(first['raw_fields']['FloatVolumn'],0);self.assertIsNone(first['raw_fields']['TotalVolumn']);self.assertEqual(first['field_reasons']['TotalVolumn'],'source_nonfinite')
        self.assertEqual(first['trading_status'],'unknown');self.assertEqual(conflict['status'],'unavailable');self.assertEqual(conflict['field_reasons']['identity'],'source_market_conflict');self.assertEqual(missing['status'],'unavailable')
        for value in (0,99999999,'2020--0101','２０２００１０１','20200230'):self.assertIsNone(owner._day(value))
        self.assertEqual(owner._day('2020-01-02'),'2020-01-02')
    def test_catalog_restricts_details_and_capacity_bytes_are_finite(self):
        sdk,owner=self.make(max_catalog_symbols=2)
        self.error('security_catalog_capacity',lambda:self.read(owner));self.assertFalse(owner.catalogs)
        sdk,owner=self.make();catalog=self.read(owner)['catalog_id'];before=len(sdk.calls)
        self.error('invalid_arguments',lambda:owner.execute(DETAILS,dict(catalog_id=catalog,symbols=['999999.SH']),9999));self.assertEqual(len(sdk.calls),before)
        sdk.detail['510300.SH']={'InstrumentName':'x'*4096}
        self.error('result_too_large',lambda:owner.execute(DETAILS,dict(catalog_id=None,symbols=['510300.SH']),9999))
        sdk,owner=self.make(SDK({'stock':['%06d.SH'%i for i in range(100)],'etf':[],'index':[]}),max_cache_bytes=4096)
        self.error('result_too_large',lambda:self.read(owner));self.assertFalse(owner.catalogs)
    def test_deadline_before_and_after_sdk_and_original_thread(self):
        sdk,owner=self.make();self.clock[0]=9999
        self.error('execution_timeout',lambda:self.read(owner));self.assertFalse(sdk.calls)
        self.clock[0]=100;original=sdk.sectors
        def slow(node):value=original(node);self.clock[0]=9999;return value
        owner.sector_list_query=slow;self.error('execution_timeout',lambda:self.read(owner));self.assertFalse(owner.catalogs)
        self.clock[0]=100;errors=[]
        def other_thread():
            try:self.read(owner)
            except GatewayError as error:errors.append(error.code)
        thread=threading.Thread(target=other_thread);thread.start();thread.join();self.assertEqual(errors,['owner_required'])
    def test_explicit_profile_and_argument_projection_boundaries(self):
        self.assertEqual(explicit_profile_version(sorted((UNIVERSE,DETAILS))),'qmt.read-profile.v9')
        for ops in ([UNIVERSE],sorted((UNIVERSE,DETAILS,'market.full_tick'))):
            with self.assertRaises(ProtocolError):explicit_profile_version(ops)
        for value in (dict(markets=['SZ','SH'],security_types=['stock'],limit=1,cursor=None),dict(markets=['SH'],security_types=['stock'],limit=True,cursor=None)):
            with self.assertRaises(ProtocolError):arguments(UNIVERSE,value,scope())
        for symbols in ([],['510300.SH','510300.SH'],['510300.SH\n']):
            with self.assertRaises(ProtocolError):arguments(DETAILS,dict(catalog_id=None,symbols=symbols),scope())
        with self.assertRaises(ProtocolError):limits(scope(max_catalogs=3),524288)
        sdk,owner=self.make();args=dict(markets=['SH'],security_types=['stock','etf','index'],limit=1,cursor=None)
        value=self.read(owner);value['groups'][0]['reason_code']='private exception'
        with self.assertRaises(ProtocolError):validate_result(dict(operation_id=UNIVERSE,arguments=args),dict(ok=True,data=value))
    def test_missing_capability_waits_without_creating_slot_or_new_request(self):
        source=object.__new__(SecurityReferenceSource)
        class OldClient:
            def metadata(self,deadline):return dict(profile=dict(operation_profiles={}))
        source.client=OldClient()
        with TemporaryDirectory()as directory:
            path=Path(directory)/'never.json'
            self.assertEqual(source.universe({},path,deadline=100)['state'],'waiting_reference_capability');self.assertFalse(path.exists())

    def test_old_authenticated_profile_without_retention_discovers_waiting(self):
        from contextlib import nullcontext
        from types import SimpleNamespace
        from guanheng_qmt_shm_agent.control_messages import host_binding
        from guanheng_qmt_shm_agent.history_preparation import validate_configuration
        from guanheng_qmt_shm.bound import digest,b64
        from tests.integration.qmt_history_preparation.support import configuration
        with TemporaryDirectory()as directory:
            config,settings=configuration(Path(directory));profile=validate_configuration(settings).profile
            binding=host_binding(route=config['route'],generation='a'*32,host_instance_id='b'*32,journal_generation=None,observation_identity=None,capability_sha256=digest(canonical(profile)))
            metadata=dict(schema_version='qmt.bound-read.v1',binding=binding,binding_sha256=digest(canonical(binding)),read_profile_body_b64=b64(canonical(profile)),read_profile_body_sha256=digest(canonical(profile)),limits=dict(max_result_bytes=8192),order_ready=False)
            calls=[]
            def exchange(method,path,body,deadline):calls.append((method,path));return 200,metadata
            def plan(*args):raise AssertionError('waiting must not plan a new request')
            transport=SimpleNamespace(exchange=exchange,plan=plan,rpc_budget=lambda timeout:nullcontext())
            source=SecurityReferenceSource(transport)
            self.assertEqual(source.capabilities(deadline=999999999)['state'],'waiting_reference_capability')
            self.assertEqual(calls,[('GET','/internal/v1/read-binding')])
    def test_twenty_thousand_name_main_chain_remains_frozen_and_bounded(self):
        sdk,owner=self.make(SDK({'stock':['%06d.SH'%i for i in range(20000)],'etf':[],'index':[]}))
        page=self.read(owner,limit=256);calls=len(sdk.calls);all_items=[]
        while True:
            all_items.extend(page['items'])
            self.assertLessEqual(len(page['items']),256);self.assertLessEqual(len(canonical(page)),300*1024)
            if page['next_cursor']is None:break
            page=self.read(owner,limit=256,cursor=page['next_cursor'])
        self.assertEqual(len(all_items),20000);self.assertEqual(len({v['symbol']for v in all_items}),20000)
        self.assertEqual(len(sdk.calls),calls);self.assertEqual(len(owner.catalogs),1)
        self.assertLessEqual(sum(v['bytes']for v in owner.catalogs.values()),8*1024*1024)
    def test_reference_known_errors_do_not_relax_old_operation_unknowns(self):
        from guanheng_qmt_shm_agent.read_retention import result_confirmed
        for code in ('security_catalog_expired','security_catalog_cursor_invalid','security_catalog_capacity','result_too_large'):
            self.assertTrue(result_confirmed(dict(operation_id=UNIVERSE,ok=False,error_code=code)))
            self.assertFalse(result_confirmed(dict(operation_id='market.full_tick',ok=False,error_code=code)))
        self.assertFalse(result_confirmed(dict(operation_id=UNIVERSE,ok=False,error_code='execution_unknown')))

if __name__=='__main__':unittest.main()
