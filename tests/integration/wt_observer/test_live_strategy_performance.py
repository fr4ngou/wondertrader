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
        value=json.loads(Path(__file__).with_name('account-publication.fixture.json').read_bytes())
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
        app=FastAPI();app.include_router(router());app.state.live_strategy_performance=self.owner
        reader=BoundedReader();reader.start();app.state.reader=reader
        try:
            with TestClient(app)as client:
                path='/v1/ui/live-strategy-performance?strategy_id=resonance-regime-v1&strategy_version=1.2.2'
                response=client.get(path);self.assertEqual(response.status_code,200)
                self.assertTrue(response.json()['current']['key_matches'])
                self.assertEqual(client.get(path+'&limit=367').status_code,422)
                self.assertEqual(client.get(path+'&strategy_version=1.1.2').status_code,422)
                self.assertEqual(client.get(path+'&private=secret').status_code,422)
                self.assertEqual(client.post(path).status_code,405)
                self.owner._read_snapshot=lambda deadline:(_ for _ in ()).throw(ValueError('secret-source-body'))
                failure=client.get(path);self.assertEqual(failure.status_code,503);self.assertNotIn('secret',failure.text)
        finally:self.assertTrue(reader.close(3))


if __name__=='__main__':unittest.main(verbosity=2)
