"""唯一正文新增只读owner的最小回归；全部运行资源用显式替身。"""
import ast,copy,importlib.util,itertools,threading,unittest
from pathlib import Path
from guanheng_qmt_shm import trade_source,trade_pair
from guanheng_qmt_shm.security_reference_composition import admit_security_reference_read,security_reference_read_material
from guanheng_qmt_shm_agent.protocol import canonical
from guanheng_qmt_shm_agent.security_reference import UNIVERSE,DETAILS,POLICY


def reference():
    scope=dict(schema='qmt.security-reference-limits.v1',max_page_size=256,max_detail_symbols=64,max_catalog_symbols=20000,max_catalogs=2,catalog_lifetime_seconds=900,max_cache_bytes=8*1024*1024,max_data_bytes=300*1024,source_groups=[])
    agent=dict(route=dict(route_id='synthetic-reference',executor_id='synthetic',route_epoch=1),secret=b'synthetic-reference-distinct-ipc-key',allowed_operations=sorted((UNIVERSE,DETAILS)),execution_timeout_ms=30000,max_frame=2097152,max_pending=1,max_result_bytes=524288,connect_seconds=5,io_seconds=2,
        transport=dict(kind='builtin-shm',schema_version='qmt.builtin-shm.v1',name='qmt-broker-synthetic-reference',max_mapped_bytes=16777216,poll_seconds=.005,windows_session_id=0),
        control_profile=dict(schema_version='1.0',max_pending_calls=4,max_call_bytes=16384,max_reply_bytes=528384,max_retained_bytes=4194304,max_cycle_messages=8,max_cycle_bytes=1048576,poll_seconds=.005,max_call_seconds=40),read_profile_version='qmt.read-profile.v9',
        operation_profiles={op:dict(policy_id=POLICY,policy_version='1.0',execution_timeout_ms=30000,limits=scope)for op in (UNIVERSE,DETAILS)},read_retention=dict(schema='qmt.read-retention.v1',max_lifetime_ms=30000))
    return dict(agent=agent,reconnect_seconds=.1)

class CompositionTests(unittest.TestCase):
    def test_material_roundtrip_preserves_exact_profile_and_original_ipc_identity(self):
        value=reference();normalized,profile=admit_security_reference_read(value)
        exported=security_reference_read_material(value)
        self.assertNotIn('secret',exported['agent']);self.assertEqual(security_reference_read_material(exported,decode_secrets=True),value)
        self.assertEqual(normalized,value);self.assertEqual(profile['read_operations'],sorted((UNIVERSE,DETAILS)))
        value['agent']['read_retention']['max_lifetime_ms']=1000
        with self.assertRaises(ValueError):admit_security_reference_read(value)
    def test_v5_decoder_consumes_new_identity_and_legacy_eight_tuple_rejects_it(self):
        credentials=dict(ipc_secret=b'synthetic-trade-original-secret-0000',http_keys={'fixture':'synthetic-http-secret'})
        value=trade_pair._deployment({},credentials,.1,security_reference_read=reference())
        self.assertEqual(value['schema_version'],'qmt.trade-deployment.v5')
        self.assertEqual(trade_pair._decode_reference_deployment(canonical(value))[8],reference())
        with self.assertRaises(ValueError):trade_pair._decode_all_deployment(canonical(value))
        old=trade_pair._deployment({},credentials,.1)
        self.assertEqual(len(trade_pair._decode_all_deployment(canonical(old))),8)
        self.assertEqual(old['schema_version'],'qmt.trade-deployment.v1')
    def callbacks(self,flags,heavy='trade',close_failure=None):
        events=[];owners=[]
        class Owner:
            def __init__(self,label):self.label=label;owners.append(self)
            def start(self):events.append(('start',self.label))
            def subscribe_account(self):events.append(('subscribe',self.label))
            def tick(self,allow_heavy=True):events.append(('tick',self.label,allow_heavy));return self.label==heavy and allow_heavy
            def request_close(self):
                events.append(('stop',self.label))
                if self.label==close_failure:raise RuntimeError('synthetic cleanup')
        settings={name:dict(agent=dict(label=name),reconnect_seconds=.1)for name in ('account_read','analysis_read','analysis_batch_read','security_reference_read')}
        settings.update(trade={},trade_reconnect_seconds=.1)
        if flags[0]:settings.update(quotes={},preparation={},preparation_reconnect_seconds=.1)
        space=dict(_settings=settings,_TradeAgent=lambda *args,**kwargs:Owner('trade'),_ReadAgent=lambda *args,**kwargs:Owner(kwargs['trusted_bootstrap']['label']),_QuoteAgent=lambda *args,**kwargs:Owner('quote'),_PreparationAgent=lambda *args,**kwargs:Owner('preparation'))
        # 仅剥离测试替身替代的四个类导入；正式原模板的控制流逐字执行。
        text=trade_source._security_reference_callbacks(*flags)
        text='\n'.join(line for line in text.splitlines()if not line.startswith('from guanheng_qmt_shm_agent.'))
        exec(compile(text,'<security-reference-composed-callbacks>','exec'),space)
        class Context:
            def run_time(self,*args):events.append(('timer',args[0]))
        context=Context();space['init'](context);space['agent_tick'](context)
        return space,context,owners,events
    def test_optional_prior_owners_all_sixteen_shapes_and_one_heavy_budget(self):
        for flags in itertools.product((False,True),repeat=4):
            with self.subTest(flags=flags):
                space,context,owners,events=self.callbacks(flags)
                expected={'trade','security_reference_read'}|({ 'quote','preparation'}if flags[0]else set())|({'account_read'}if flags[1]else set())|({'analysis_read'}if flags[2]else set())|({'analysis_batch_read'}if flags[3]else set())
                self.assertEqual({v.label for v in owners},expected)
                self.assertEqual(events.count(('timer','agent_tick')),1)
                self.assertIn(('tick','security_reference_read',False),events)
                space['stop'](context);self.assertEqual({v[1]for v in events if v[0]=='stop'},expected)
    def test_reference_heavy_blocks_hpr_and_first_cleanup_failure_still_stops_all(self):
        space,context,owners,events=self.callbacks((True,True,True,True),heavy='security_reference_read',close_failure='trade')
        self.assertIn(('tick','security_reference_read',True),events);self.assertIn(('tick','preparation',False),events)
        with self.assertRaises(RuntimeError):space['stop'](context)
        self.assertEqual({v[1]for v in events if v[0]=='stop'},{v.label for v in owners})
        before=list(events)
        with self.assertRaises(RuntimeError):space['stop'](context)
        self.assertEqual(before,events)

if __name__=='__main__':unittest.main()
