"""LSP事实及HTTP主链；隔离发布快照与本地副本，不连接账户或下单。"""
from copy import deepcopy
from contextlib import closing
from datetime import datetime,timezone
import json
from pathlib import Path
from time import monotonic
from types import SimpleNamespace
import unittest
import tempfile
from unittest.mock import patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from guanheng_app.live_strategy_performance import LiveStrategyPerformanceOwner, _deal_rows, _amount
from guanheng_app.live_strategy_routes import router
from guanheng_app.reading import BoundedReader


def snapshot():
    stamp='2026-11-02T07:00:00+00:00'
    fields={k:dict(availability='present',value=v)for k,v in dict(side=48,quantity=100,price='2.5',amount='250',date='20261103',time='102015').items()}
    deal=dict(identity=dict(m_strInstrumentID='510300',m_strExchangeID='SH',m_strTradeID='private-original-trade'),fields=fields)
    baseline=dict(schema='guanheng.current-capital-baseline.v1',total_cny='1000',source='fixture-allocated',
        baseline_at='2026-11-02T06:00:00+00:00',historical_initial_capital_cny=None)
    return dict(configuration=SimpleNamespace(instance_id='instance',control_id='first',configuration_sha256='a'*64),
        runtime=dict(pid=555,state='ready',ready=True,components=dict(execution=dict(state='ready',ready=True))),
        reference=dict(pid=777,control_id='execution',config_sha256='b'*64,path='private-never-exposed'),
        lifecycle=dict(execution_started_at='2026-11-02T05:59:00+00:00'),
        strategy=dict(strategy_id='resonance-regime-v1',strategy_version='1.2.2',capital_baseline=baseline,
            capital=dict(nav_cny='1000',cash_balance_cny='800',market_value_cny='200',native_pnl_cny='0',
                observed_at=stamp,price_observed_at=stamp,pnl_source='broker-cash-delta'),
            broker_observed_at='2026-11-04T07:00:00+00:00',positions=[dict(symbol='510300.SH',broker_quantity=100,broker_sellable=80)]),
        account=dict(publication=dict(scope_id='c'*64),trade_date=dict(availability='present',value='20261103'),
            groups=dict(deal=dict(status='complete',execution_finished_at='2026-11-04T07:01:00+00:00',rows=[deal,deepcopy(deal)]))))


def synthetic_account_publication():
    """仅构造回调准入所需最小NAP帧；所有身份、金额和关闭事实均为测试生成。

    三类证券查询完整空，资金查询一行满足原协议；不依赖本地捕获文件、账户或SDK。
    """
    stamp='2026-11-02T01:00:00.000000Z';scan=str(uuid4());account='SYNTHETIC-LSP-ACCOUNT'
    binding=dict(account=account,environment='simulation',max_rows=8,ipc_schema='guanheng.account-scan.v2',
        inspection_version=3,source='qmt_shm_bound',read_profile_version='qmt.read-profile.v3')
    source=dict(kind='qmt_shm_bound',account_id=account,account_environment='simulation',
        transport_binding=dict(schema_version='1.0',route=dict(route_id='synthetic-route',executor_id='synthetic-executor',route_epoch=0),
            transport_generation='1'*32,host_instance_id='2'*32,journal_generation=None,observation_identity=None,capability_sha256='3'*64),
        binding_sha256='4'*64,broker_session=dict(availability='unknown',value=None,reason='未取得券商登录会话证据'))
    present=lambda value:dict(availability='present',value=value,reason='synthetic fixture')
    rows=dict(position=[],order=[],deal=[],account=[dict(version=3,view=4,index=0,identity={},
        facts=dict(m_dBalance=present(1000.0),m_dAvailable=present(900.0)),abi={})])
    batches=[dict(datatype=name,delivered=True,source_row_count=len(rows[name]),delivered_row_count=len(rows[name]),
        request_id=str(uuid4()),execution_started_at=stamp,execution_finished_at=stamp,
        result_sha256=str(index+1)*64,source=deepcopy(source))for index,name in enumerate(('position','order','deal','account'))]
    observation=dict(schema='guanheng.account-scan.v2',scan_id=scan,kind='observation',rows=rows,
        summary=dict(version=3,view=0,phase=8,source_kind='qmt_shm_bound',profile='cny_cash_shsz_v1',
            currency_binding=dict(value='CNY',source='configuration'),observation_qualified=True,aggregate_only=True,
            trade_date=dict(availability='unknown',value=None,reason='synthetic date unavailable'),batches=batches,
            close=dict(status='complete',drained=True,joined=True),
            failure=dict(code=0,reason='',transport_error=None,source_error_code=None)))
    completion=dict(schema='guanheng.account-scan.v2',scan_id=scan,kind='completion',closed=True,joined=True,
        worker_live=False,queued=0,elapsed_ms=1,error_code='ok')
    close=dict(status='complete',closed=True,joined=True,worker_live=False,queued=0,exit_code=0,error_code='ok',
        resources={name:True for name in ('member_before_resume','tree_reaped','stdout_eof','stderr_eof','readers_joined','resources_closed')})
    return dict(schema='guanheng.account-observation.v1',control_id=str(uuid4()),config_sha256='a'*64,pid=777,
        revision=1,updated_at=stamp,state='ready',error_code=None,last_success_at=stamp,binding=binding,
        scan_id=scan,observation=observation,completion=completion,close=close,
        attempt=dict(scan_id=scan,completion=completion,close=close))


class LiveTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir='E:/workspace')
        self.addCleanup(self.temp.cleanup)
        self.value=snapshot();self.owners=[]
        self.owner=self.new()
        self.addCleanup(self.close_all)

    def close_all(self):
        for owner in self.owners:owner.close()

    def new(self,**kwargs):
        owner=LiveStrategyPerformanceOwner(SimpleNamespace(),history_root=self.temp.name,
            snapshot_reader=lambda deadline:deepcopy(self.value),process_probe=lambda *args:True,**kwargs)
        self.owners.append(owner);return owner

    def read(self,owner=None,version='1.2.2',limit=90):
        return (owner or self.owner).read('resonance-regime-v1',version,limit,deadline=monotonic()+10)

    def stable_anchor(self):
        from guanheng_app.live_strategy_performance import _sha
        anchor=dict(schema='guanheng.broker-cash-anchor.v1',baseline_sha256=_sha(self.value['strategy']['capital_baseline']),
            allocated_cash_cny='800',market_value_cny='200',account_cash_cny='5000',
            account_observed_at='2026-11-02T05:59:00+00:00',account_source_sha256='1'*64,
            account_binding_sha256='2'*64,position_source_sha256='3'*64,price_source_sha256='4'*64)
        self.value['strategy']['capital']['cash_anchor']=anchor
        self.value['account_binding_sha256']='2'*64
        return anchor

    def test_actual_source_days_nav_gaps_and_account_trade_attribution_survive_restart(self):
        value=self.read()
        self.assertTrue(value['current']['is_current'])
        self.assertEqual([r['date']for r in value['daily']],['2026-11-02','2026-11-03','2026-11-04'])
        self.assertEqual(value['coverage']['point_count'],1)
        self.assertIsNone(value['daily'][1]['nav_cny'])
        self.assertIsNone(value['summary']['return_pct'])
        self.assertEqual(len(value['markers']),1)
        self.assertEqual(value['markers'][0]['attribution'],'account-universe-only')
        self.assertEqual(value['daily'][2]['positions'][0]['sellable'],80)
        text=json.dumps(value)
        self.assertNotIn('private-original-trade',text);self.assertNotIn('private-never-exposed',text)
        self.owner.close();restored=self.read(self.new())
        self.assertEqual(restored['daily'],value['daily'])

    def test_return_matches_current_nav_and_preserves_daily_snapshots(self):
        from guanheng_app.strategy_capital_projection import project_capital_return

        strategy = self.value['strategy']
        capital = strategy['capital']
        stamp = capital['observed_at']
        capital['account_observed_at'] = stamp
        proof = dict(baseline_at=strategy['capital_baseline']['baseline_at'], valued_at=stamp,
                     valuation_nav_cny='1000', cash_observed_at=stamp,
                     coverage_required_at=stamp, inflow_through=stamp, outflow_through=stamp,
                     flow_count=0, flows=[], state='available', return_pct='0', reason='已核对资金进出。')
        strategy['capital_return'] = project_capital_return(proof, strategy['capital_baseline'], capital)
        value = self.read()
        self.assertEqual(value['summary']['return_pct'], '0')
        self.assertEqual(value['summary']['capital_return'], proof)
        self.assertTrue(all(row['return_pct'] is None for row in value['daily']))

        capital['account_observed_at'] = capital['observed_at'] = '2026-11-02T08:00:00+00:00'
        capital.update(nav_cny='1010', native_pnl_cny='10', cash_balance_cny='810')
        self.assertEqual(project_capital_return(proof, strategy['capital_baseline'], capital), proof)
        self.assertEqual(self.read()['summary']['nav_cny'], '1010')
        self.assertEqual(self.read()['summary']['capital_return']['valued_at'], stamp)

    def test_new_actual_nav_uses_source_day_and_old_observation_cannot_overwrite(self):
        self.read()
        capital=self.value['strategy']['capital'];capital.update(observed_at='2026-11-04T07:00:00+00:00',nav_cny='1200',native_pnl_cny='200')
        value=self.read();self.assertEqual(value['coverage']['point_count'],2)
        self.assertEqual(value['daily'][-1]['nav_cny'],'1200')
        capital.update(observed_at='2026-11-04T06:00:00+00:00',nav_cny='1100')
        backward=self.read();self.assertEqual(backward['daily'][-1]['nav_cny'],'1200')
        self.assertEqual((backward['summary']['nav_cny'],backward['summary']['observed_at']),('1200','2026-11-04T07:00:00+00:00'))
        self.assertIsNone(self.read()['summary']['return_pct'])

    def test_noncurrent_version_returns_no_other_strategy_financial_facts(self):
        self.read();value=self.read(version='1.1.2')
        self.assertEqual(value['state'],'not_current')
        self.assertFalse(value['current']['is_current']);self.assertIsNone(value['current']['scope_id'])
        self.assertIsNone(value['summary']);self.assertIsNone(value['baseline'])
        self.assertEqual(value['daily'],[]);self.assertEqual(value['markers'],[])

    def test_complete_runtime_and_baseline_scopes_are_separate(self):
        before=self.read();self.value['configuration'].control_id='successor'
        self.value['strategy']['capital']['observed_at']='2026-11-05T07:00:00+00:00'
        after=self.read();self.assertNotEqual(before['current']['scope_id'],after['current']['scope_id'])
        self.assertEqual(after['coverage']['point_count'],1)
        self.assertEqual(after['coverage']['from'],'2026-11-05')
        scope=after['current']['scope_id'];self.value['strategy']['capital_baseline']['total_cny']='2000'
        self.assertNotEqual(self.read()['current']['scope_id'],scope)

    def test_stopped_and_unknown_process_keep_history_without_current_marker(self):
        self.read();self.owner._probe=lambda *args:None
        self.assertFalse(self.read()['current']['is_current'])
        self.value['runtime'].update(state='closed',ready=False)
        self.assertFalse(self.read()['current']['is_current'])
        self.assertEqual(self.read()['coverage']['point_count'],1)

    def test_stale_ready_with_dead_runtime_and_alive_execution_has_no_current_marker(self):
        self.owner._probe=lambda pid,started:pid!=555
        value=self.read()
        self.assertFalse(value['current']['is_current'])
        self.assertEqual(value['current']['process_state'],'exited')

    def test_exclusive_history_owner_and_deadline_preserve_existing_complete_data(self):
        self.read();second=self.new()
        with self.assertRaises(OSError):self.read(second)
        with self.assertRaises(TimeoutError):self.owner.capture_current(monotonic()-1)
        self.assertEqual(self.read()['coverage']['point_count'],1)
        second.close()

    def test_empty_deal_query_and_missing_source_remain_distinct(self):
        self.value['account']['groups']['deal']['rows']=[]
        value=self.read();self.assertEqual(next(r for r in value['daily']if r['date']=='2026-11-03')['deals_state'],'empty')
        self.value['configuration'].control_id='new-scope';self.value['account']=None
        self.assertTrue(all(r['deals_state']=='unavailable'for r in self.read()['daily']))

    def test_conflicting_same_trade_id_rejects_deal_group_and_extreme_decimal_is_bounded(self):
        rows=self.value['account']['groups']['deal']['rows'];rows[1]['fields']['quantity']['value']=200
        self.assertEqual(_deal_rows(self.value['account'],{'510300.SH'})[2],'unavailable')
        with self.assertRaises(ValueError):_amount('1e-10000000')

    def test_original_qmt_five_digit_morning_clock_is_preserved_and_normalized(self):
        for row in self.value['account']['groups']['deal']['rows']:row['fields']['time']['value']='93856'
        value=self.read();deal=next(r for r in value['daily']if r['deals'])['deals'][0]
        self.assertEqual((deal['time'],deal['source_time']),('09:38:56','93856'))
        self.assertEqual(len(value['markers']),1)

    def test_partial_new_day_failure_rolls_back_whole_observation_transaction(self):
        import guanheng_app.live_strategy_performance as live
        self.read();original=deepcopy(self.value);validate=live._stored_day
        self.value['strategy']['capital']['observed_at']='2026-11-06T07:00:00+00:00'
        self.value['strategy']['broker_observed_at']='2026-11-05T07:00:00+00:00'
        def fail_second_day(raw):
            result=validate(raw)
            if result['date']=='2026-11-05':raise TimeoutError('fixture serialization boundary')
            return result
        with patch.object(live,'_stored_day',side_effect=fail_second_day),self.assertRaises(TimeoutError):self.read()
        self.value=original;restored=self.read()
        self.assertEqual(restored['coverage']['to'],'2026-11-02')
        self.assertNotIn('2026-11-06',[row['date']for row in restored['daily']])

    def test_trade_window_is_bounded_and_reports_partial_without_deleting_history(self):
        import sqlite3
        template=self.value['account']['groups']['deal']['rows'][0]
        rows=[]
        for index in range(2005):
            row=deepcopy(template);row['identity']['m_strTradeID']='fixture-'+str(index);rows.append(row)
        self.value['account']['groups']['deal']['rows']=rows
        value=self.read();self.assertEqual(len(value['markers']),2000)
        self.assertTrue(value['coverage']['deals_truncated'])
        self.assertEqual(next(r for r in value['daily']if r['deals'])['deals_state'],'partial')
        with closing(sqlite3.connect(Path(self.temp.name)/'live-strategy-observations.sqlite3'))as database:
            self.assertEqual(database.execute('SELECT count(*) FROM deals').fetchone()[0],2005)

    def test_snapshot_only_uses_same_trade_bound(self):
        template=self.value['account']['groups']['deal']['rows'][0]
        rows=[]
        for index in range(2005):
            row=deepcopy(template);row['identity']['m_strTradeID']='fixture-'+str(index);rows.append(row)
        self.value['account']['groups']['deal']['rows']=rows
        owner=LiveStrategyPerformanceOwner(SimpleNamespace(),snapshot_reader=lambda deadline:deepcopy(self.value),process_probe=lambda *a:True)
        self.owners.append(owner);value=self.read(owner)
        self.assertEqual(len(value['markers']),2000);self.assertTrue(value['coverage']['deals_truncated'])
        self.assertEqual(value['coverage']['history_state'],'snapshot-only')

    def test_trade_after_original_group_clock_is_partial_and_not_a_marker(self):
        for row in self.value['account']['groups']['deal']['rows']:
            row['fields']['date']['value']='20261104';row['fields']['time']['value']='160001'
        self.assertEqual(_deal_rows(self.value['account'],{'510300.SH'})[2],'partial')
        self.assertEqual(self.read()['markers'],[])

    def test_readonly_write_failure_merges_current_snapshot_without_claiming_saved(self):
        self.read();original=deepcopy(self.value);open_database=self.owner._database
        self.value['strategy']['capital'].update(observed_at='2026-11-05T07:00:00+00:00',nav_cny='1300',native_pnl_cny='300')
        def readonly(deadline):
            database=open_database(deadline);database.execute('PRAGMA query_only=ON');return database
        with patch.object(self.owner,'_database',side_effect=readonly):
            value=self.read()
        self.assertEqual(value['coverage']['history_state'],'degraded-readonly-history')
        self.assertEqual(value['coverage']['point_count'],2);self.assertEqual(value['summary']['nav_cny'],'1300')
        self.value=original
        self.assertEqual(self.read()['coverage']['point_count'],1)

    def test_normal_restart_keeps_economic_history_and_trade_identity_with_runtime_provenance(self):
        self.stable_anchor();before=self.read();old_scope=before['current']['scope_id']
        self.value['configuration'].control_id='successor';self.value['reference']['control_id']='successor-execution'
        self.value['account']['publication']['scope_id']='new-transport-scope'
        self.value['strategy']['capital'].update(observed_at='2026-11-05T07:00:00+00:00',nav_cny='1100',native_pnl_cny='100')
        after=self.read()
        self.assertNotEqual(after['current']['scope_id'],old_scope)
        self.assertEqual(after['coverage']['history_scope_id'],before['coverage']['history_scope_id'])
        self.assertEqual(after['coverage']['point_count'],2);self.assertEqual(len(after['markers']),1)
        self.assertEqual(after['daily'][0]['runtime_scope_id'],old_scope)
        self.assertEqual(after['daily'][-1]['runtime_scope_id'],after['current']['scope_id'])

    def test_anchor_account_and_strategy_version_change_split_history(self):
        anchor=self.stable_anchor();before=self.read()
        anchor['account_binding_sha256']='d'*64
        changed=self.read();self.assertNotEqual(changed['coverage']['history_scope_id'],before['coverage']['history_scope_id'])
        self.assertEqual(changed['markers'],[])
        self.value['account_binding_sha256']='d'*64
        self.assertEqual(len(self.read()['markers']),1)
        self.value['strategy']['strategy_version']='1.2.3'
        versioned=self.read(version='1.2.3')
        self.assertNotEqual(versioned['coverage']['history_scope_id'],changed['coverage']['history_scope_id'])

    def test_older_same_trade_observation_cannot_rewrite_saved_amount_or_provenance(self):
        self.stable_anchor();before=self.read();original=deepcopy(self.value)
        self.value['account']['groups']['deal']['execution_finished_at']='2026-11-04T06:00:00+00:00'
        for row in self.value['account']['groups']['deal']['rows']:row['fields']['amount']['value']='240'
        after=self.read();deal=next(r for r in after['daily']if r['deals'])['deals'][0]
        self.assertEqual(deal['amount_cny'],'250')
        self.value=original

    def test_account_binding_callback_follows_original_admission_and_default_return(self):
        import guanheng_app.account_publication as consumer
        from guanheng_app.live_strategy_performance import _sha
        from guanheng_app.wt_runtime_observation import RuntimeObservationConfig
        value=synthetic_account_publication()
        root=Path(self.temp.name);folder=root/value['control_id'];folder.mkdir()
        identity={k:value[k]for k in ('control_id','config_sha256','pid')}
        reference=dict(schema='guanheng.account-observation-reference.v1',path=str(folder/'observation.json'),
            ready_path=str(folder/'ready.json'),**identity)
        ready=dict(schema='guanheng.account-observation.ready.v1',**identity)
        runtime=dict(schema='guanheng.wt-runtime-status.v1',control_id=str(uuid4()),instance_id=str(uuid4()),
            configuration_sha256='a'*64,pid=value['pid'],state='ready',ready=True,components=dict(
                account_observation=dict(pid=value['pid'],state='ready',ready=True,pending=False,forced=False,account_observation=reference)))
        status=root/'status.json'
        for path,body in ((status,runtime),(folder/'ready.json',ready),(folder/'observation.json',value)):
            path.write_text(json.dumps(body),encoding='utf8')
        configuration=RuntimeObservationConfig(status,runtime['control_id'],runtime['instance_id'],'a'*64)
        observed=[]
        callback=lambda binding:observed.append(_sha(dict(account=binding.account,environment=binding.environment,currency='CNY')))
        published=consumer.observe_published_account(configuration,monotonic()+5,binding_observer=callback)
        default=consumer.observe_published_account(configuration,monotonic()+5)
        self.assertEqual(published.model_dump(),default.model_dump());self.assertEqual(len(observed),1)
        self.assertRegex(observed[0],r'^[a-f0-9]{64}$')
        after=deepcopy(runtime);after['pid']+=1
        with patch.object(consumer,'read_runtime_snapshot',side_effect=[SimpleNamespace(value=runtime),SimpleNamespace(value=after)]),self.assertRaises(ValueError):
            consumer.observe_published_account(configuration,monotonic()+5,binding_observer=callback)
        self.assertEqual(len(observed),1)

    def test_http_uses_existing_reader_enforces_key_query_and_readonly(self):
        securities = SimpleNamespace(name={'510300.SH': '华泰柏瑞沪深300ETF', '000001.SZ': '未在观察范围内'}.get)
        app=FastAPI();app.include_router(router(securities));app.state.live_strategy_performance=self.owner
        reader=BoundedReader();reader.start();app.state.reader=reader
        try:
            with TestClient(app)as client:
                path='/v1/ui/live-strategy-performance?strategy_id=resonance-regime-v1&strategy_version=1.2.2'
                response=client.get(path);self.assertEqual(response.status_code,200)
                self.assertTrue(response.json()['current']['key_matches'])
                self.assertEqual(response.json()['security_names'], {'510300.SH': '华泰柏瑞沪深300ETF'})
                self.assertEqual(client.get(path+'&limit=367').status_code,422)
                self.assertEqual(client.get(path+'&strategy_version=1.1.2').status_code,422)
                self.assertEqual(client.get(path+'&private=secret').status_code,422)
                self.assertEqual(client.post(path).status_code,405)
                self.owner._read_snapshot=lambda deadline:(_ for _ in ()).throw(ValueError('secret-source-body'))
                failure=client.get(path);self.assertEqual(failure.status_code,503);self.assertNotIn('secret',failure.text)
        finally:self.assertTrue(reader.close(3))


if __name__=='__main__':unittest.main(verbosity=2)
