"""真实CTA等待回调与账户后台续核交替；无Native、NAP网络或目标提交。"""
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from fractions import Fraction
import json
from pathlib import Path
from types import SimpleNamespace
import time
import unittest
from unittest.mock import patch

from guanheng_wt_runtime.execution_configured import RetainedStrategy
from guanheng_wt_runtime.execution_strategy import BrokerObservationValue
from guanheng_wt_runtime import strategy_capital as capital


@dataclass(frozen=True)
class WaitingRequest:
    cycles: tuple  # 原回调本轮实际持仓周期；本用例空集合以隔离账户与行情等待。
    cycles_captured_at: datetime  # 券商持仓原接收UTC时间，不从账户资格反推。
    cycles_valid_until: datetime  # 持仓资料UTC截止，与账户期限独立。
    decision_cutoff: datetime  # 本轮策略读取UTC截止时点。
    previous_exits: tuple  # 原退出记忆，本用例保持空集合。


class CapitalWaitQualification(unittest.TestCase):
    def test_main_minute_retries_unavailable_only_within_original_deadline(self):
        from guanheng_wt_runtime.execution_strategy import NativeBarReadError, register_main_minute
        clock = [0.0]
        code = 'SSE.ETF.510300'
        missing = NativeBarReadError(code, 'm1', 1, True, -8)
        broken = NativeBarReadError(code, 'm1', 1, True, -5)
        for attempts, deadline, outcome in [((missing, ('bar',)), 1.0, ('bar',)),
                                             ((missing,), .05, missing), ((broken,), 1.0, broken)]:
            clock[0] = 0.0
            context = SimpleNamespace(bars=unittest.mock.Mock(side_effect=attempts))
            with patch('guanheng_wt_runtime.execution_strategy.time.monotonic', side_effect=lambda: clock[0]), \
                    patch('guanheng_wt_runtime.execution_strategy.time.sleep', side_effect=lambda value: clock.__setitem__(0, clock[0]+value)):
                if isinstance(outcome, Exception):
                    with self.assertRaises(NativeBarReadError) as caught:
                        register_main_minute(context, code, deadline=deadline)
                    self.assertIs(caught.exception, outcome)
                else:
                    self.assertEqual(register_main_minute(context, code, deadline=deadline), outcome)
            self.assertEqual(context.bars.call_count, len(attempts))

    def test_native_bar_error_retains_input_and_original_wait_classification(self):
        from guanheng_wt_runtime.execution_strategy import CallbackContext, NativeBarReadError
        code = 'SSE.ETF.510300'
        event = SimpleNamespace(thread_id=1, kind=1, epoch=2)
        for result, reason in ((-8, 'native_read_failed'), (-5, 'native_operation_failed')):
            owner = SimpleNamespace(_thread=lambda: 1, _api=SimpleNamespace(gh_ms_bars=lambda *args: result))
            context = owner._active = CallbackContext(owner, SimpleNamespace(read_symbols=(code,)), event)
            with self.assertRaisesRegex(NativeBarReadError, reason) as caught:
                context.bars(code, 'm1', 1, main=True)
            self.assertEqual(caught.exception.details,
                dict(symbol=code, period='m1', count=1, main=True, native_result=result))

    def setUp(self):
        self.now = datetime.now(timezone.utc)
        stamp = (self.now-timedelta(seconds=30)).isoformat()
        self.origin = dict(schema='guanheng.current-capital-baseline.v1', total_cny='1000000',
            source='synthetic-current-capital', baseline_at=self.now.isoformat(),
            historical_initial_capital_cny=None)
        binding = capital._digest(dict(account='SYNTHETIC', environment='simulation', currency='CNY'))
        self.account = capital.AccountCash('432123.4', '0', stamp, 'a'*64, binding)
        self.anchor = capital.create_cash_anchor(self.origin, Fraction('567876.6'), self.account,
            position_source_sha256='c'*64, price_source_sha256='d'*64)
        self.value = capital.observe_broker_capital(self.origin, self.anchor, Fraction(0),
            Fraction('570321.5'), self.now.isoformat(), self.account, True,
            max_age_seconds=300, position_observed_at=stamp, price_observed_at=stamp)
        self.source = [self.account, True]
        self.reader = SimpleNamespace(read=lambda *_: tuple(self.source), max_age=300)

    def strategy(self, waiting_market):
        strategy = RetainedStrategy.__new__(RetainedStrategy)
        request = WaitingRequest((), self.now, self.now+timedelta(seconds=300), self.now, ())
        strategy.inputs = SimpleNamespace(capital_baseline=self.origin, request=request)
        strategy.execution = (); strategy.mapping = {}; strategy.id = 'resonance-regime-v1'
        strategy.execution_enabled = True
        strategy.seconds = 2; strategy.max_age = 300; strategy.sequence = 1
        strategy.initialized = True; strategy.state = None; strategy.exits = (); strategy.cycles = {}
        strategy.allocation = None; strategy.allocation_observation = None; strategy.deal_history = None
        strategy.recovery_state = None
        strategy.recovery = 'record_clean'; strategy.restored_state_id = None; strategy.restored_sequence = None
        strategy.capital_reader = self.reader; strategy.capital_observation = deepcopy(self.value)
        strategy.market_window = (SimpleNamespace(read=lambda *_args, **_kw:
            SimpleNamespace(request=None, publication=None, reason='awaiting_market_window'))
            if waiting_market else None)
        strategy._state_payload = lambda *_: '{}'
        strategy._store_state = lambda _ctx, _value: None
        reports = []
        strategy.publish = lambda _sid, value, **kw: None if kw.get('preview') else reports.append(value)
        ms = int(self.now.timestamp()*1000)
        context = SimpleNamespace(event=SimpleNamespace(kind=4, epoch=7), broker_trades=lambda: None,
            broker_observation=lambda: BrokerObservationValue(waiting_market, True, 1, ms, 1, ms, ms,
                1002444.9, 432123.4, ()), store_quantity_state=lambda _text: None,
            set_targets=lambda *_: self.fail('等待资料时禁止提交目标'))
        return strategy, context, reports

    def test_native_history_timeout_defers_without_saving_or_setting_targets(self):
        strategy, context, reports = self.strategy(True)
        from guanheng_wt_runtime.execution_strategy import CtaBridgeError
        strategy.mapping = {'510300.SH': 'SSE.ETF.510300'}
        row = SimpleNamespace(symbol='510300.SH', trade_date=self.now.date())
        publication = SimpleNamespace(history=SimpleNamespace(observations=(row,)))
        strategy.market_window.read = lambda *a, **kw: SimpleNamespace(request=publication, publication={})
        diagnostics = []
        strategy.market_input_timeout = lambda *args: diagnostics.append(args)
        clock = [time.monotonic()]

        def delayed_bars(*args):
            clock[0] += strategy.seconds + 1
            raise CtaBridgeError('native_read_failed')

        context.bars = delayed_bars
        strategy._store_state = lambda *_: self.fail('行情超时不能保存数量状态')
        with patch('guanheng_wt_runtime.execution_configured.time.monotonic', side_effect=lambda: clock[0]):
            strategy.callback(context)
        self.assertEqual(diagnostics, [(strategy.id, 7, 2, strategy.seconds)])
        self.assertEqual(reports, [])
        self.assertIsNone(strategy.state)

    def initial_strategy(self):
        strategy, context, _ = self.strategy(False)
        code = 'SSE.ETF.510500'
        strategy.inputs.cash_anchor = self.anchor
        strategy.mapping = {'510500.SH': code}
        strategy.targets = (code,)
        strategy.capital_market = dict(base_url='http://127.0.0.1:18150', token_env='TEST_CAPITAL_QUOTES',
            timeout_seconds=1, max_response_bytes=8192, max_age_seconds=300)
        strategy.native_price_ticks = {code: Fraction('0.001')}
        strategy._initial_capital_basis = None
        strategy.recovery = 'resume_reconciled'
        strategy.start_deadline = time.monotonic()+2
        context.facts = lambda: SimpleNamespace(fund_pnl=0)
        stamp = self.now-timedelta(seconds=30)
        broker = SimpleNamespace(position_received_ms=int(stamp.timestamp()*1000),
            positions=(SimpleNamespace(symbol=code, is_long=True, quantity=100, sellable=100),))
        return strategy, context, broker, stamp

    def test_initial_nav_reads_qualified_quote_before_recovery_chain(self):
        from zoneinfo import ZoneInfo
        strategy, context, broker, stamp = self.initial_strategy()
        source = stamp.astimezone(ZoneInfo('Asia/Shanghai'))
        reply = dict(status={'code': 'Ok'}, data={
            'metadata': {'qualification': 'NativeVerified'},
            'snapshots': [dict(symbol='SSE.510500', date=int(source.strftime('%Y%m%d')),
                action_time=int(source.strftime('%H%M%S'))*1000, source_time_verified=True, price=1.25)]})
        with patch.dict('os.environ', TEST_CAPITAL_QUOTES='test-read-token'), \
                patch('guanheng_market_client.MarketClient') as client, \
                patch.object(strategy, '_retained_initial_valuation', side_effect=TimeoutError) as history:
            client.return_value.quotes_query.return_value = reply
            self.assertIs(strategy._read_initial_capital(context, broker), reply)
            history.assert_not_called()
        observed = strategy.capital_observation
        self.assertEqual(observed['cash_anchor'], self.anchor)
        self.assertEqual(Fraction(observed['market_value_cny']), 125)
        self.assertEqual(observed['market_value_source'], 'broker-position+raw-QMT-snapshot')

    def test_initial_nav_uses_retained_proof_when_current_source_unavailable(self):
        from guanheng_market_client import MarketUnavailable
        strategy, context, broker, stamp = self.initial_strategy()
        proof = (Fraction(125), stamp, 'broker-position+raw-CTA-price', None)
        clock = [time.monotonic()]
        strategy.start_deadline = clock[0]+strategy.seconds

        def timeout(**kwargs):
            clock[0] += kwargs['timeout']
            raise MarketUnavailable('test transport deadline')

        def retained(_broker, _funds, *, deadline):
            self.assertGreater(deadline-clock[0], 1)
            return proof

        with patch('guanheng_wt_runtime.execution_configured.time.monotonic', side_effect=lambda: clock[0]), \
                patch.dict('os.environ', TEST_CAPITAL_QUOTES='test-read-token'), \
                patch('guanheng_market_client.MarketClient') as client, \
                patch.object(strategy, '_retained_initial_valuation', side_effect=retained) as history:
            def quotes(_symbols):
                timeout(**client.call_args.kwargs)
            client.return_value.quotes_query.side_effect = quotes
            self.assertIsNone(strategy._read_initial_capital(context, broker))
            history.assert_called_once()
        observed = strategy.capital_observation
        self.assertEqual(observed['cash_anchor'], self.anchor)
        self.assertEqual(Fraction(observed['market_value_cny']), 125)
        self.assertEqual(observed['price_observed_at'], stamp.isoformat())

    def test_wait_callbacks_and_background_keep_valid_account(self):
        # 原故障：每次等待窗口的CTA回调把账户资格清空，后台线程稍后又恢复，产生闪烁。
        for waiting_market in (False, True):
            with self.subTest(waiting_market=waiting_market):
                strategy, context, reports = self.strategy(waiting_market)
                for _ in range(3):
                    strategy.callback(context)
                    report = reports[-1]
                    self.assertEqual(report['status'], 'waiting_market_input' if waiting_market else 'waiting_broker_position')
                    self.assertEqual(report['capital'], self.value)
                    refreshed = capital.refresh_capital_report(report, self.reader, time.monotonic()+2,
                        initial_basis=None, origin=self.origin, anchor=self.anchor)
                    self.assertEqual(refreshed['capital'], self.value)

    def test_wait_invalid_account_is_unknown_and_valid_successor_recovers(self):
        strategy, context, reports = self.strategy(True)
        for source in ((self.account, False), (None, False)):
            self.source[:] = source  # 原账户过期或读取失败；最后成功原件及其时点仍可展示。
            strategy.callback(context)
            observed = reports[-1]['capital']
            self.assertFalse(observed['account_observation_qualified'])
            self.assertIsNone(observed['spendable_cash_cny'])
            for field in ('nav_cny', 'cash_balance_cny', 'observed_at', 'price_observed_at',
                          'account_observed_at', 'account_valid_until', 'account_source_sha256'):
                self.assertEqual(observed[field], self.value[field])
        self.source[:] = [self.account, True]
        strategy.callback(context)
        self.assertEqual(reports[-1]['capital'], self.value)

    def test_wait_without_capital_preserves_legacy_path(self):
        strategy, context, reports = self.strategy(True)
        strategy.inputs.capital_baseline = None
        strategy.capital_observation = None
        strategy.capital_reader = SimpleNamespace(read=lambda *_: self.fail('旧无资金配置路径不得读取NAP'))
        strategy.callback(context)
        self.assertEqual(reports[-1]['status'], 'waiting_market_input')
        self.assertNotIn('capital', reports[-1])

    def test_background_older_account_revokes_qualification_preserving_newer_source(self):
        # 后台读取器冷启动取得较早合法帧；该帧不能证明已发布较新来源当前仍合格。
        older = capital.AccountCash('1', '0', (self.now-timedelta(seconds=60)).isoformat(), 'e'*64, 'b'*64)
        for qualified in (True, False):
            with self.subTest(qualified=qualified):
                self.source[:] = [older, qualified]
                updated = capital.refresh_account_constraint(self.value, self.reader, time.monotonic()+2)
                self.assertFalse(updated['account_observation_qualified'])
                self.assertIsNone(updated['spendable_cash_cny'])
                self.assertEqual(updated['account_source_sha256'], self.value['account_source_sha256'])
                self.assertEqual(updated['account_observed_at'], self.value['account_observed_at'])

    def test_actual_account_reader_expiry_binding_and_readside(self):
        # 完整NAP帧只替换文件I/O；真实Reader核来源、关闭证明、金额和五分钟账户期限。
        from guanheng_app.strategy_capital_projection import project_capital
        control = '11111111-1111-4111-8111-111111111111'
        root = Path.cwd()/'.tmp'/'capital-qualification'/'synthetic-nap'
        reader = capital.AccountCashReader(dict(path=str(root/'current.json'), config_sha256='f'*64,
            account='SYNTHETIC', environment='simulation'), 300)
        reference = dict(schema='guanheng.account-observation-reference.v1', control_id=control,
            config_sha256='f'*64, pid=123, path=str(root/control/'observation.json'),
            ready_path=str(root/control/'ready.json'))
        frame = dict(schema='guanheng.account-observation.v1', control_id=control, config_sha256='f'*64,
            pid=123, state='ready', binding=dict(account='SYNTHETIC', environment='simulation'),
            close=dict(status='complete', exit_code=0, resources=dict.fromkeys(
                ('member_before_resume', 'tree_reaped', 'stdout_eof', 'stderr_eof', 'readers_joined', 'resources_closed'), True)),
            completion=dict(closed=True, joined=True), observation=dict(summary=dict(
                source_kind='qmt_shm_bound', observation_qualified=True, batches=[dict(datatype='account',
                delivered=True, source=dict(account_id='SYNTHETIC', account_environment='simulation'),
                execution_finished_at=self.account.observed_at)]), rows=dict(account=[dict(facts=dict(
                m_dAvailable=dict(availability='present', value=432123.4),
                m_dFrozenCash=dict(availability='present', value=0)))])))
        def document(path, _maximum, _deadline):
            value = reference if path.name == 'current.json' else frame
            return value, json.dumps(value, sort_keys=True).encode('ascii')
        class PinnedDateTime(datetime):
            current = self.now  # 本例可控UTC观察时点；账户原帧时间始终不变。
            @classmethod
            def now(cls, tz=None):
                return cls.current.astimezone(tz) if tz else cls.current.replace(tzinfo=None)
        strategy, context, reports = self.strategy(True)
        strategy.capital_reader = reader
        with patch.object(reader, '_document', side_effect=document), patch.object(capital, 'datetime', PinnedDateTime):
            for seconds in (0, 269):
                PinnedDateTime.current = self.now+timedelta(seconds=seconds)
                strategy.callback(context)
                value = reports[-1]['capital']
                self.assertTrue(value['account_observation_qualified'])
                self.assertEqual(value['spendable_cash_cny'], '432123.4')
                self.assertEqual(project_capital(value, self.origin), value)
            PinnedDateTime.current = self.now+timedelta(seconds=270)
            strategy.callback(context)
            self.assertFalse(reports[-1]['capital']['account_observation_qualified'])
            self.assertIsNone(reports[-1]['capital']['spendable_cash_cny'])
            self.assertEqual(reports[-1]['capital']['observed_at'], self.value['observed_at'])
            PinnedDateTime.current = self.now
            frame['binding']['environment'] = 'live'
            strategy.callback(context)
            self.assertFalse(reports[-1]['capital']['account_observation_qualified'])
            self.assertIsNone(reports[-1]['capital']['spendable_cash_cny'])


if __name__ == '__main__':
    unittest.main()
