"""合成原件覆盖周末缺口、旧名册保留和同日修订失败窗口；不连接Source。"""
from datetime import datetime
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import time
import unittest
import uuid
from unittest.mock import patch

from integrations.guanheng.daily_data_update import _descriptor
from integrations.guanheng.daily_gap_update import prepare_gap_plan
from integrations.guanheng.daily_price_continuation import requires_price_continuation
from integrations.guanheng.daily_price_scope import prepare_price_scope
from integrations.guanheng.security_reference import SecurityReference,trade_day_state,prepare_retained_reference
from integrations.guanheng.market_generation import encode
from integrations.guanheng import daily_data_service as service


def write(path,value):
    path.write_bytes(encode(value))
    return _descriptor(path)


def security(symbol,kind):
    return dict(symbol=symbol,name='合成证券',market=symbol.split('.')[0],security_type=kind,
                listed_on=None,expires_on=None,observed_at=None)


class PriceMaintenanceTests(unittest.TestCase):
    def test_retained_stock_identity_keeps_newer_observation_and_accepts_newer_complete_basic(self):
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory);old=security('SSE.600000','stock')
            old.update(name='较新Source名称',listed_on='1990-01-01',observed_at='2026-11-03T01:00:00+00:00')
            leaf=write(root/'leaf.json',dict(schema='guanheng.security-reference.v1',
                securities={'SSE.510300':security('SSE.510300','etf')},
                provenance=dict(catalog_sha256='a'*64,details_sha256=None,indices_sha256=None)))
            composite=prepare_retained_reference(leaf,{old['symbol']:old},[leaf],root/'combined.json')
            reference=SecurityReference(composite)
            try:
                basic=dict(name='较早basic名称',market='SSE',listed_on=None,expires_on=None,
                    observed_at='2026-11-02T01:00:00+00:00')
                self.assertEqual(reference.security(dict(basics={old['symbol']:basic}),old['symbol']),old)
                basic.update(name='后继资料名称',observed_at='2026-11-04T01:00:00+00:00')
                result=reference.security(dict(basics={old['symbol']:basic}),old['symbol'])
                self.assertEqual(result['name'],basic['name']);self.assertIsNone(result['listed_on'])
                self.assertEqual(result['observed_at'],basic['observed_at'])
            finally:reference.close()

    def test_reported_halt_with_missing_quantity_stays_distinct_from_confirmed_zero_trade(self):
        state=dict(qualification='qualified',tradestatus='0',volume='',close_reference='10')
        self.assertEqual(trade_day_state(state),'source_halted_quantity_unknown')
        self.assertEqual(trade_day_state(dict(state,volume='0')),'source_halted_no_trade')
        self.assertEqual(trade_day_state(dict(state,volume='3')),'source_trade_state_inconsistent')

    def test_new_dynamic_unknown_name_is_not_overwritten_by_old_snapshot_basic(self):
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory);identity=security('SSE.600000','stock')
            identity.update(name=None,observed_at='2026-11-04T01:00:00+00:00')
            evidence=write(root/'original.json',dict(synthetic=True))
            descriptor=write(root/'reference.json',dict(schema='guanheng.security-reference.v2',
                securities={'SSE.600000':identity},provenance=dict(catalog_id='a'*64,
                    captured_at='2026-11-04T01:00:00+00:00',source_as_of=None,evidence=[evidence],
                    groups=[dict(market='SH',security_type='stock',state='complete',expected_count=1,
                        observed_count=1,source_groups=['synthetic-stock'],reason_code=None)])))
            reference=SecurityReference(descriptor)
            try:
                result=reference.security(dict(basics={'SSE.600000':dict(name='旧名称',market='SSE',
                    listed_on='1990-01-01',expires_on=None,observed_at='2020-01-01T00:00:00+00:00')}),'SSE.600000')
                self.assertIsNone(result['name']);self.assertIsNone(result['listed_on'])
                self.assertEqual(result['observed_at'],identity['observed_at'])
            finally:reference.close()

    def test_consecutive_open_days_cross_weekend_but_original_protected_day_splits_request(self):
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory);capture=root/'capture';capture.mkdir()
            manifest=dict(request=dict(symbols=['510300.SH'],start_date='20261030',end_date='20261103'),
                          comparison={'510300.SH':dict(common_dates=[])})
            identity=write(capture/'manifest.json',manifest)
            descriptor=dict(directory=str(capture),sha256=identity['sha256'])
            calendar=dict(coverage_start='2026-01-01',coverage_end='2026-12-31',closed_dates=[])
            reference=SimpleNamespace(_calendar=calendar,security=lambda *_:dict(listed_on=None,expires_on=None))
            snapshot=dict(observation_date='2026-11-03',snapshot_id='a'*64)
            original=root/'original.json'
            write(original,dict(request=dict(request_id=str(uuid.uuid4()),operation_id='market.history_prepare',
                  arguments=dict(symbol='510300.SH',period='1d',start_time='20261102',end_time='20261102'))))
            with patch('guanheng_qmt_shm.analysis_batch_source.read_capture',return_value=manifest):
                complete=prepare_gap_plan(descriptor,reference,snapshot,root/'all',authorized_from='20261030',
                    authorized_to='20261103',deadline=time.monotonic()+10)
                protected=prepare_gap_plan(descriptor,reference,snapshot,root/'protected',protected_slots=[str(original)],
                    authorized_from='20261030',authorized_to='20261103',deadline=time.monotonic()+10)
            all_tasks=json.loads(Path(complete['path']).read_bytes())['tasks']
            self.assertEqual([row['dates']for row in all_tasks],[['20261030','20261102','20261103']])
            value=json.loads(Path(protected['path']).read_bytes())
            self.assertEqual([row['dates']for row in value['tasks']],[['20261030'],['20261103']])
            self.assertEqual(value['exclusions'][0]['reason'],'original_HPR_responsibility')

    def test_original_returned_observation_and_available_price_do_not_trigger_repeat(self):
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory);work=root/'gap-work/observations';work.mkdir(parents=True)
            plan=write(root/'plan.json',dict(tasks=[dict(index=0,symbol='510300.SH')]))
            # 恢复时advance会跳过已返回项，最新progress.rows为空；原单项凭据仍有效。
            write(work/'000000.json',dict(plan_sha256=plan['sha256'],row=dict(index=0,state='call_returned')))
            inputs=write(root/'INPUTS.json',dict(plan=plan,preparation=dict(rows=[])))
            result=dict(inputs=inputs,securities={'SSE.510300':dict(target_readable=False)})
            self.assertFalse(requires_price_continuation(result))
            write(work/'000000.json',dict(plan_sha256=plan['sha256'],row=dict(index=0,state='pending')))
            self.assertTrue(requires_price_continuation(result))
            result['securities']['SSE.510300']['target_readable']=True
            self.assertFalse(requires_price_continuation(result,['SSE.510300']))

    def test_missing_source_reference_retains_newly_discovered_prior_security_with_unknown_denominators(self):
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory)
            baseline=write(root/'reference.json',dict(schema='guanheng.security-reference.v1',
                securities={'SSE.510300':security('SSE.510300','etf')},
                provenance=dict(catalog_sha256='a'*64,details_sha256=None,indices_sha256=None)))
            previous=write(root/'previous.json',dict(securities={'SSE.589680':security('SSE.589680','etf')}))
            configuration=write(root/'source.json',dict(security_reference=baseline))
            pool=write(root/'pool.json',dict(members=['sh.600000']))
            scope=dict(baseline_reference=baseline,reference_connection=None,
                scope=dict(markets=['SH','SZ','BJ'],security_types=['stock','etf','index'],limit=256),
                authorized_from='20260701',maximum_history_rows=10000)
            result=prepare_price_scope(scope,'2026-11-03',pool,dict(configuration=configuration),root/'scope',
                deadline=time.monotonic()+10,cancelled=lambda:False,previous_scopes=[previous])
            value=json.loads(Path(result['path']).read_bytes());universe=json.loads(Path(value['universe']['path']).read_bytes())
            self.assertEqual(set(universe['securities']),{'SSE.510300','SSE.589680'})
            self.assertEqual(value['primary_members'],['SSE.600000'])
            self.assertEqual(universe['expected_counts'],dict(stock=None,etf=None,index=None))

    def test_restart_after_revision_registration_reuses_same_task_and_keeps_original_request(self):
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory);state=root/'state';state.mkdir();old=root/'original.json'
            old.write_bytes(b'original immutable request');old_body=old.read_bytes()
            write(state/'INDEX.json',{'2026-11-03':dict(request=str(old),state='published',continuation_required=True)})
            calendar=write(root/'calendar.json',{})
            configuration=dict(schema='guanheng.daily-data-service.v1',directory=str(state),raw_store=str(root/'raw'),
                template=dict(schema='guanheng.daily-data-update.v1',publication_directory=str(root/'publication'),calendar=calendar),
                inputs=dict(connections=dict(batch={},hpr={}),cache_from='20260701',max_rows=100,source_kind='sdk-synthetic',
                    public_facts=dict(source={},allowed_hosts=[],seconds=30,max_requests=1,max_bytes=1,response_bytes=1,timeout_seconds=1)),
                schedule=dict(timezone='Asia/Shanghai',at='09:00',poll_seconds=.1),cycle_seconds=60,retry_seconds=1)
            descriptor=write(root/'config.json',configuration);attempts=[]
            def prepare(config,day,output,**kwargs):
                attempts.append(Path(output));self.assertIn(str(old),kwargs['previous_requests'])
                if len(attempts)==1:raise InterruptedError('after revision registration, before input commit')
                output.mkdir();return write(output/'UPDATE.json',dict(synthetic_scheduler_fixture=True))
            def run(*args,**kwargs):return dict(current_sha256='b'*64,continuation_required=False)
            with patch.object(service,'prepare_update',prepare),patch.object(service,'run_update',run):
                for _ in range(3):
                    control=str(uuid.uuid4());service.serve(descriptor,root/control,control,once=True,as_of='2026-11-03')
            self.assertEqual(len(attempts),2);self.assertEqual(attempts[0],attempts[1])
            entry=json.loads((state/'INDEX.json').read_bytes())['2026-11-03']
            self.assertEqual(entry['revision'],1);self.assertEqual(entry['history_requests'],[str(old)])
            self.assertEqual(entry['state'],'published');self.assertEqual(old.read_bytes(),old_body)


if __name__=='__main__':unittest.main()
