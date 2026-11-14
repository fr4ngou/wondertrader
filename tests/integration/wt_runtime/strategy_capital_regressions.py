"""资金来源截止、坏型、精确金额与完整Configured等待/恢复回归；SDK调用0。"""
import argparse
from contextlib import contextmanager
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
from decimal import localcontext
from fractions import Fraction
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace
from unittest.mock import patch


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--reader-site', type=Path, required=True)
    parser.add_argument('--source', action='store_true')
    args = parser.parse_args()
    if args.source:
        sys.path.insert(0, str(args.root/'apps/wt_runtime'))
        sys.path.insert(0, str(args.root/'apps/guanheng'))
    sys.path.append(str(args.reader_site))
    from guanheng_wt_runtime import strategy_capital as module
    from guanheng_wt_runtime.execution_configured import RetainedStrategy, RetainedRuntimeInput
    from guanheng_wt_runtime.execution_strategy import PositionValue, FactsValue, BrokerObservationValue, BrokerPositionValue, BarValue
    from guanheng_wt_runtime.initial_inventory import prepare_initial_inventory
    from guanheng_app.strategy_capital_projection import project_capital
    from guanheng_app.strategy_runtime_projection import project_strategy
    now = datetime.now(timezone.utc)
    origin = dict(schema='guanheng.current-capital-baseline.v1', total_cny='1000000',
        source='user-confirmed-current-total:2026-11-02', baseline_at=now.isoformat(),
        historical_initial_capital_cny=None)
    cash = module.AccountCash('199800000', '1234.5', now.isoformat(), 'a'*64)
    value = module.observe_capital(origin, Fraction(repr(4.3655745685100555e-11)),
        Fraction(200000), now.isoformat(), cash, True, position_observed_at=now.isoformat())
    for precision in (6, 28, 64):
        with localcontext() as context:
            context.prec = precision
            assert project_capital(value, origin) == value
            for field in ('nav_cny', 'cash_balance_cny', 'spendable_cash_cny'):
                wrong = dict(value); wrong[field] = '1000001'
                try: project_capital(wrong, origin)
                except ValueError: pass
                else: raise AssertionError('inconsistent '+field)
    binding = dict(path=str(args.work/'current.json'), config_sha256='b'*64,
                   account='SYNTHETIC', environment='live')
    reader = module.AccountCashReader(binding, 60); reader.last = cash
    with patch.object(module, '_inspect', side_effect=AssertionError('expired entry did I/O')):
        assert reader.read(now, time.monotonic()-1) == (cash, False)
    # 每一种晚返回均不能进入下一步I/O；已开句柄仍须关闭。
    for late in ('inspect', 'open', 'fstat', 'read', 'parse'):
        calls=[]; clock=[0.]; raw=b'{}'
        info=SimpleNamespace(st_size=2)
        def inspect(*a, **kw):
            calls.append('inspect')
            if late == 'inspect': clock[0]=2.
        class Stream:
            def fileno(self): return 123
            def read(self, n):
                calls.append('read')
                if late == 'read': clock[0]=2.
                return raw
        @contextmanager
        def opened(path):
            calls.append('open')
            if late == 'open': clock[0]=2.
            try: yield Stream()
            finally: calls.append('closed')
        def stat(fd):
            calls.append('fstat')
            if late == 'fstat': clock[0]=2.
            return info
        def parse(raw):
            calls.append('parse')
            if late == 'parse': clock[0]=2.
            return {}
        with patch.object(module.time,'monotonic',lambda:clock[0]), patch.object(module,'_inspect',inspect), \
                patch.object(module,'_open_status_file',opened), patch.object(module.os,'fstat',stat), \
                patch.object(module,'_check',lambda *a:None), patch.object(module,'_identity',lambda v:2), \
                patch.object(module,'_json',parse):
            assert reader.read(now,1.) == (cash,False)
        expected = {'inspect':['inspect'], 'open':['inspect','open','closed'],
            'fstat':['inspect','open','fstat','closed'],
            'read':['inspect','open','fstat','read','closed'],
            'parse':['inspect','open','fstat','read','fstat','closed','parse']}[late]
        assert calls == expected, (late,calls)
    for wrong in (1, None, [], {}):
        reference=dict(schema='guanheng.account-observation-reference.v1',control_id=wrong,
            config_sha256='b'*64,pid=1,path='unused',ready_path='unused')
        with patch.object(reader,'_document',return_value=(reference,b'{}')):
            assert reader.read(now,time.monotonic()+5) == (cash,False)

    data=json.loads((args.root/'build/ms-per-date-replay-001/candidate-003/SESSION.json').read_bytes())
    template=RetainedRuntimeInput.from_dict(dict(schema='guanheng.retained-cta-input.v1',
        **{k:data[k]for k in ('request','policy','fee_reserve_cny','fee_source','market_manifest_source')}))
    facts=dict(schema='guanheng.initial-inventory-facts.v2',broker_source_sha256='c'*64,
        captured_at=now.isoformat(),valid_until=(now+timedelta(seconds=60)).isoformat(),
        captured_uptime_ms=1000,valid_until_uptime_ms=61000,
        positions=[dict(symbol='510050.SH',quantity=500,sellable=500,mark_price=4.,mark_source_sha256='d'*64)])
    prepared=prepare_initial_inventory(template,facts,now=now,uptime_ms=2000,
        capital={k:origin[k]for k in ('total_cny','source')})
    loaded=RetainedRuntimeInput.from_dict(json.loads(prepared.runtime_input))
    strategy=RetainedStrategy.__new__(RetainedStrategy)
    strategy.inputs=loaded; strategy.execution=tuple(c.symbol for c in loaded.request.cycles)
    strategy.mapping={s:('SSE'if s.endswith('.SH')else'SZSE')+'.ETF.'+s[:6]for s in strategy.execution}
    strategy.targets=tuple(strategy.mapping.values());strategy.id='resonance-regime-v1'
    strategy.seconds=5;strategy.max_age=60;strategy.capital_observation=None
    strategy.sequence=0;strategy.initialized=True;strategy.state=None;strategy.exits=()
    strategy.recovery='record_clean';strategy.restored_state_id=None;strategy.restored_sequence=None
    strategy.state_identity='e'*64;strategy._state_revision=None;strategy.flat_sources={};strategy.market_window=None
    strategy.execution_enabled=True
    strategy.cycles={c.symbol:dict(status='initial_inventory',cycle_id=c.cycle_id,
        baseline_at=c.baseline_at.isoformat(),source_sha256=c.source_sha256)
        for c in loaded.request.cycles if c.quantity}
    reports=[]; submissions=[]; stored=[]; source=[cash,True]
    strategy.publish=lambda sid,v,**kw: reports.append(v) if not kw.get('preview') else None
    strategy.capital_reader=SimpleNamespace(read=lambda *_:tuple(source))
    reverse={v:k for k,v in strategy.mapping.items()}
    class Context:
        event=SimpleNamespace(kind=4)
        pending=False
        theoretical_flat=False
        def broker_observation(self):
            ms=int(datetime.now(timezone.utc).timestamp()*1000)
            return BrokerObservationValue(True,True,1,ms,1,ms,ms,200000000.,199800000.,
                (BrokerPositionValue(strategy.mapping['510050.SH'],True,500.,500.),))
        def broker_trades(self): return None
        def position(self,code):
            n=500 if reverse[code]=='510050.SH' and not self.theoretical_flat else 0
            return PositionValue(0,n,n,1000 if self.pending and n else None,1 if n else 0,1 if n else 0,0,None,None)
        def price(self,code): return 4.
        def facts(self): return FactsValue(20261102,1000,20261102,0.)
        def bars(self,code,period,count):
            return tuple(BarValue(int(r.trade_date.strftime('%Y%m%d')),0,r.open,r.high,r.low,r.close,r.volume,r.amount,0.,0.)
                for r in loaded.request.history.observations if r.symbol==reverse[code])[-count:]
        def set_targets(self,vector): submissions.append(vector);return vector
        def load_quantity_state(self): return stored[-1] if stored else ''
        def store_quantity_state(self,text): stored.append(text)
    context=Context();strategy.callback(context)
    assert strategy.state is not None
    previous=asdict(strategy.state); exits=strategy.exits; targets=len(submissions)
    original=reports[-1]['capital']['account_observed_at'];context.pending=True
    for account,qualified in ((None,False),(cash,False)):
        source[:]=[account,qualified]
        strategy.callback(context)
        report=reports[-1]
        assert report['status']=='waiting_basis' and report['reason']=='account_cash_unavailable'
        assert asdict(strategy.state)==previous and strategy.exits==exits and len(submissions)==targets
        assert report['capital']['spendable_cash_cny'] is None
        if account is not None: assert report['capital']['account_observed_at']==original
        assert next(p for p in report['native_observation']['positions']if p['symbol']=='510050.SH')['pending_target']==1000
        assert project_strategy(dict(schema='guanheng.configured-cta-observation.v1',
            strategies={strategy.id:json.loads(json.dumps(report,default=str))}))['status']=='waiting_basis'
    source[:]=[cash,True];context.pending=False;strategy.callback(context)
    assert reports[-1]['status']!='waiting_basis'
    # 重启时理论目标已归零、券商仍持500份；预算沿完整券商P计价，不能等待成交才能授预算。
    context.theoretical_flat=True;strategy.callback(context)
    assert reports[-1]['status']!='waiting_basis'
    assert reports[-1]['capital']['market_value_cny']=='2000'
    assert reports[-1]['capital']['cash_balance_cny']=='998000'
    assert reports[-1]['capital']['spendable_cash_cny']=='996765.5'
    assert next(p for p in reports[-1]['execution_observation']['positions']if p['symbol']=='510050.SH')['actual']==500
    context.theoretical_flat=False
    # 原无capital路径无需NAP现金引用，继续以原理论现金交NSQ。
    strategy.inputs=replace(loaded,capital_baseline=None);strategy.capital_observation=None
    strategy.capital_reader=SimpleNamespace(read=lambda *_:(_ for _ in ()).throw(AssertionError('legacy read NAP')))
    strategy.callback(context)
    assert reports[-1]['status']!='waiting_basis' and 'capital' not in reports[-1]
    args.work.mkdir(parents=True,exist_ok=True)
    (args.work/'REGRESSIONS-001.json').write_text(json.dumps(dict(passed=True,source=args.source,
        expired_entry_zero_IO=True,late_IO_and_parse_not_qualified=True,late_resources_closed=True,
        UUID_bad_types_wait=True,exact_money_independent_of_decimal_context=True,
        complete_callback_wait_preserves_state_and_pending=True,valid_successor_continues=True,
        readonly_wait_projection=True,legacy_no_capital_callback=True,real_QMT_calls=0),indent=2),encoding='utf8')
    print(json.dumps(dict(passed=True,source=args.source,SDK_calls=0)))


if __name__=='__main__': main()
