"""原版WT输入/报告的纯值合同；不提供Porter、会话、进程或执行入口。"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from fractions import Fraction
import hashlib
import json
import math
import re
from .report_values import SessionError, _snapshot_json, _freeze_json, _thaw_json, _run_report_checked


def _quantity(value):
    if (type(value) not in (int, float) or not 0 <= value <= 2**53 - 1
            or type(value) is float and not math.isfinite(value) or int(value) != value):
        raise SessionError('原生数量必须为非负精确整数')
    return int(value)


INPUT_SCHEMA='guanheng.original-native-replay-input.v1'
REPORT_SCHEMA='guanheng.original-native-replay-report.v1'
STRATEGY_ID='resonance-original-wt-351f9d5-stable'
STRATEGY_VERSION='0.1.0a2'
LEGACY_VERSION='0.1.0a1'
OPEN_VERSION='0.2.0a1'
OPEN_SCOPE='WT-native-original-signals; opening-minute-limit; historical/PIT/broker/production-unqualified'
OPEN_QUOTE, OPEN_MATCH, DAY_CLOSE = 931, 932, 1500
OPEN_CODES = ('159352','159780','510050','510300','510500','512100','515080','588000','589680')
OPEN_MAP = {code: '588230' if code == '589680' else code for code in OPEN_CODES}
OPEN_INPUT_FIELDS = {'opening_bars', 'execution_map', 'fee_mode'}
ALGORITHM_ID='resonance-original-351f9d5-stable'
UPSTREAM_COMMIT='351f9d58152e10efd2447c997b8ee4db66b5ac6a'
CONFIRM_ID='resonance-kc50-pullback-confirm'
CONFIRM_VERSION='0.3.0a1'
CONFIRM_FIELD='kc50_pullback_confirmation'
CONFIRM_CODES=('159352','159780','510050','510300','512100','515080','588000')
REPORT_SCOPE='WT-native-original-signals; daily-OHLC-next-tick; historical/PIT/broker/production-unqualified'
MAX_BYTES=16*1024*1024
INPUT_FIELDS=(
    'schema',  # 独立WT回放输入版本，与ORR原组合区别。
    'strategy',  # 固定展示/算法身份，不接纳动态代码。
    'reference_report',  # 冻结原报告，BUY/SELL唯一来自trades_by_code。
    'reference_report_sha256',  # 原ORR UTF8规范JSON的完整报告摘要。
    'source_snapshot_sha256',  # 原完整特征输入摘要，与原报告input_sha256核同。
    'history',  # 每证券真实冻结OHLC与量额；不合成收盘价bar。
    'calendar',  # 完整交易日；首日为原生暖机，其他上市前可以无bar。
    'evaluation_window',  # 与ORR完整评价日期一致，额外一前日仅供WT暖机。
    'policy',  # 明确100万元、CNY/份与100份整手。
    'fee_reserve_cny',  # D日数量规划保留的费用/现金缓冲，人民币。
    'fee_source',  # WT绑定fees原件的说明，不重算或替代原生费用。
    'market_manifest_source',  # 本次日线来源说明。
    'price_basis',  # 原价/复权基准，历史来源资格分别保留。
)
LEGACY_MODEL={
    'execution':'signal-close-to-next-WT-native-tick',  # 原生日线下通常下一交易日开盘。
    'allocation':'new-buy-equal-weight; sell-only-preserve-other-shares',  # 原组合目标意图。
    'sizing':'D-close-NAV-and-price; floor-100-shares',  # 下一日开盘不进入D日数量规划。
    'cash':'D-budget-only; native-gap-deficits-disclosed',  # CtaMocker不实施现金购买力检查。
    'fills':'original-CtaMocker-daily-OHLC-simulated-ticks',  # 不新增撮合器。
    'fees':'WT-bound-fees-file',  # 实际费用直接读取原生资金。
    'historical_availability':'unknown',  # 实收/最终历史不等于当时首次可知。
    'constraints':'WT-native-T+1; frozen-sells-and-equal-weight-trims-deferred-with-original-intent',  # 沿原生valid保留原BUY/SELL意图，冻结卖出或等权减持延至合法时重规划。
}
MODEL={**LEGACY_MODEL,
    'execution':'D-close-intent; WT-native-limit-next-tick; unfilled-intent-retained',  # D已知价格限价；不消费未来开盘。
    'sizing':'D-close-equal-weight-plan; cash-capped-integer-100-share-execution',  # 每次原BUY固定等权份数计划，按当前现金分批实现。
    'cash':'actual-D-cash-reserves-all-buy-principal-and-fee-upper-bounds; no-unfilled-sale-credit',  # 待卖出款不计入买入力。
    'constraints':LEGACY_MODEL['constraints']+'; cash-nonnegative; sell-limit-covers-fee',  # 卖出最低限价覆盖费用，买入保留一元舍入余量。
}


OPEN_MODEL={
    'execution':'D+1 09:31 closed bar limit; WT CtaMocker 09:32 matching',
    'allocation':LEGACY_MODEL['allocation'],
    'sizing':'D+1 09:31 equal-weight plan; floor-100-shares; executable symbols',
    'cash':'actual opening cash covers buy principal and fees; no unfilled sale credit',
    'fills':'WT CtaMocker m1 OHLC; no order book or capacity model',
    'fees':LEGACY_MODEL['fees'],
    'historical_availability':'unknown',
    'constraints':'WT-native-T+1; residual intents reconsidered on later opens',
    'execution_map':OPEN_MAP,
}


def model_for_version(version):
    models={STRATEGY_VERSION:MODEL, LEGACY_VERSION:LEGACY_MODEL, OPEN_VERSION:OPEN_MODEL,
            CONFIRM_VERSION:dict(MODEL, strategy_variant=CONFIRM_ID)}
    _need(type(version) is str and version in models)
    return models[version]


def strategy_id_for_version(version):
    return CONFIRM_ID if version == CONFIRM_VERSION else STRATEGY_ID


def scope_for_version(version):
    return OPEN_SCOPE if version == OPEN_VERSION else REPORT_SCOPE


def _encode(value, *, original=False):
    return json.dumps(value,ensure_ascii=not original,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf8' if original else 'ascii')


def _digest(value, *, original=False):
    return hashlib.sha256(_encode(value,original=original)).hexdigest()


def _need(value):
    if not value:raise SessionError('原版WT输入、身份、时钟或原生事实失配')


def _hash(value):
    _need(type(value) is str and re.fullmatch('[0-9a-f]{64}',value) is not None)


def _text(value):
    _need(type(value) is str and 1<=len(value)<=512 and all(ord(c)>=32 for c in value))


def _day(value):
    _need(type(value) is str)
    try:parsed=date.fromisoformat(value)
    except ValueError:raise SessionError('原版WT交易日期无效') from None
    _need(parsed.isoformat()==value and 1900<=parsed.year<3000)
    return int(value.replace('-',''))


def _money(value):
    _need(type(value) is str and len(value)<=128 and re.fullmatch(r'-?[0-9]+(?:\.[0-9]+)?',value) is not None)
    return Fraction(value)


def _number(value, *, positive=False):
    _need(type(value) in (int,float) and -1e20 <= value <= 1e20
          and (type(value) is int or math.isfinite(value)) and (value>0 if positive else value>=0))
    return value


def _native(code):return ('SSE' if code.startswith(('5','6')) else 'SZSE')+'.ETF.'+code


def _normalize_input(value):
    """DLL装载前复制并准入；不联网、不重新运行或翻译原信号算法。"""
    value=_snapshot_json(value,maximum=MAX_BYTES)
    _need(type(value) is dict and value.get('schema')==INPUT_SCHEMA)
    opening=type(value.get('strategy')) is dict and value['strategy'].get('strategy_version')==OPEN_VERSION
    _need(set(value)==set(INPUT_FIELDS)|(OPEN_INPUT_FIELDS if opening else set()))
    _need(type(value['strategy']) is dict)
    version=value['strategy'].get('strategy_version')
    _need(value['strategy']==dict(strategy_id=strategy_id_for_version(version),strategy_version=version,algorithm_id=ALGORITHM_ID))
    model_for_version(version)
    report=value['reference_report']
    _need(type(report) is dict and report.get('schema')=='guanheng.resonance-original-report.v1'
          and report.get('upstream_commit')==UPSTREAM_COMMIT and report.get('algorithm_id')==ALGORITHM_ID)
    for key in ('reference_report_sha256','source_snapshot_sha256'):_hash(value[key])
    _need(_digest(report,original=True)==value['reference_report_sha256'] and report.get('input_sha256')==value['source_snapshot_sha256'])
    history,calendar=value['history'],value['calendar']
    _need(type(history) is dict and 1<=len(history)<=9 and type(calendar) is list and 2<=len(calendar)<=4096)
    _need(calendar==sorted(set(calendar)))
    for day in calendar:_day(day)
    _need(value['evaluation_window']==dict(warmup_date=calendar[0],**{'from':calendar[1],'to':calendar[-1]}))
    original_days=[row['date'] for row in report.get('portfolio',{}).get('history',[])]
    if opening:
        _validate_open_input(value, original_days)
    else:
        _need(original_days==calendar[1:])
    codes=sorted(history)
    if version==CONFIRM_VERSION:
        _need(tuple(codes)==CONFIRM_CODES and report.get(CONFIRM_FIELD) is True)
    else:
        _need(CONFIRM_FIELD not in report)
    _need(all(type(code) is str and re.fullmatch('[0-9]{6}',code) is not None for code in codes))
    trades=report.get('trades_by_code')
    _need(type(trades) is dict and set(trades)==set(OPEN_CODES if opening else codes))
    for code,rows in history.items():
        _need(type(rows) is list and 1<=len(rows)<=4096)
        days=[]
        for row in rows:
            _need(type(row) is dict and set(row)=={'date','open','high','low','close','volume','amount'})
            day=row['date'];_day(day);_need(day in calendar);days.append(day)
            for name in ('open','high','low','close'):_number(row[name],positive=True)
            for name in ('volume','amount'):_number(row[name])
            _need(row['low']<=min(row['open'],row['close'])<=max(row['open'],row['close'])<=row['high'])
        _need(days==sorted(set(days)))
        if not opening:
            _validate_signals(trades[code], set(days))
    if opening:
        signal_dates=set(original_days)
        for signals in trades.values():
            _validate_signals(signals, signal_dates)
    main='510300' if '510300' in history else codes[0]
    _need([r['date'] for r in history[main]]==calendar)
    policy=value['policy']
    _need(type(policy) is dict and set(policy)=={'initial_capital_cny','capital_source','currency','quantity_unit','multiplier','lot'})
    _need(policy['initial_capital_cny']=='1000000' and policy['currency']=='CNY' and policy['quantity_unit']=='share'
          and type(policy['multiplier']) is int and policy['multiplier']==1 and type(policy['lot']) is int and policy['lot']==100)
    _text(policy['capital_source']);_need(0<=_money(value['fee_reserve_cny'])<1000000)
    for key in ('fee_source','market_manifest_source','price_basis'):_text(value[key])
    return value


def _validate_signals(signals, dates):
    _need(type(signals) is list and len(signals)<=4096)
    previous=None
    for signal in signals:
        _need(type(signal) is dict and set(signal)=={'action','date','price','reason'})
        _need(signal['action'] in ('BUY','SELL') and signal['date'] in dates)
        _need(previous is None or signal['date']>previous)
        previous=signal['date']
        _number(signal['price'],positive=True)
        _text(signal['reason'])


def _validate_open_input(value, original_days):
    calendar=value['calendar']
    index=original_days.index(calendar[0])
    _need(original_days[index:index+len(calendar)]==calendar)
    _need(value['execution_map']==OPEN_MAP)
    _need(value['fee_mode'] in ('per-share', 'turnover'))
    _need(value['fee_reserve_cny']==('0' if value['fee_mode']=='per-share' else '0.01'))
    execution_codes=set(OPEN_MAP.values())
    _need(set(value['history'])==set(value['opening_bars'])==execution_codes)
    all_days=set(calendar)
    required={(day, minute) for day in calendar[1:] for minute in (OPEN_QUOTE, DAY_CLOSE)}
    for code, rows in value['opening_bars'].items():
        _need(type(rows) is list and 0<len(rows)<=3*len(calendar))
        _need([row['date'] for row in value['history'][code]]==calendar)
        seen=set()
        previous=None
        for row in rows:
            _need(type(row) is dict and set(row)=={'date','minute','open','high','low','close','volume','amount'})
            key=(row['date'], row['minute'])
            _need(key[0] in all_days and type(key[1]) is int and key[1] in (OPEN_QUOTE, OPEN_MATCH, DAY_CLOSE))
            _need(previous is None or previous<key)
            previous=key
            seen.add(key)
            for name in ('open','high','low','close'):
                _number(row[name],positive=True)
            _number(row['volume'],positive=key[1]!=DAY_CLOSE)
            _number(row['amount'])
            _need(row['low']<=min(row['open'],row['close'])<=max(row['open'],row['close'])<=row['high'])
        _need(required<=seen and (calendar[0],DAY_CLOSE) in seen)
        if code=='510300':
            _need(all((day,OPEN_MATCH) in seen for day in calendar[1:]))


def normalize_input(value):
    """纯值输入准入，非法嵌套统一为领域异常；不持有原调用者JSON。"""
    try:return _normalize_input(value)
    except SessionError:raise
    except (KeyError,TypeError,ValueError,OverflowError):
        raise SessionError('原版WT输入嵌套结构或数值无效') from None


def build_input(snapshot,report,*,fee_reserve_cny='5000',fee_source='explicit-WT-bound-fees',market_manifest_source='frozen-original-input', execution_history=None):
    """固定原报告与输入核同后提取OHLC；默认5000元为显式模型缓冲，可由调用者选择。"""
    _need(type(snapshot) is dict and type(report) is dict and report.get('input_sha256')==_digest(snapshot,original=True))
    codes=sorted(report['trades_by_code']);history={}
    evaluation=[row['date'] for row in report['portfolio']['history']]
    _need(evaluation and evaluation==sorted(set(evaluation)))
    main='510300' if '510300' in codes else codes[0]
    earlier=[row['date'] for row in snapshot['daily'][main] if row['date']<evaluation[0]]
    _need(earlier)
    calendar=[max(earlier)]+evaluation;wanted=set(calendar)
    for code in codes:
        history[code]=[dict(date=row['date'],open=row['open_price'],high=row['high_price'],low=row['low_price'],
            close=row['close_price'],volume=row['volume'],amount=row.get('amount',0)) for row in snapshot['daily'][code] if row['date'] in wanted]
    version=CONFIRM_VERSION if report.get(CONFIRM_FIELD) is True else STRATEGY_VERSION
    if version==CONFIRM_VERSION:
        _need(type(execution_history) is dict and set(execution_history)==set(CONFIRM_CODES))
        history={code:[dict(row,amount=row.get('amount',0)) for row in execution_history[code] if row['date'] in wanted]
                 for code in codes}
        fee_reserve_cny='0.01'
    return normalize_input(dict(schema=INPUT_SCHEMA,
        strategy=dict(strategy_id=strategy_id_for_version(version),strategy_version=version,algorithm_id=ALGORITHM_ID),
        reference_report=report,reference_report_sha256=_digest(report,original=True),source_snapshot_sha256=report['input_sha256'],
        history=history,calendar=calendar,evaluation_window=dict(warmup_date=calendar[0],**{'from':calendar[1],'to':calendar[-1]}),
        policy=dict(initial_capital_cny='1000000',capital_source='explicit-original-WT-model',
            currency='CNY',quantity_unit='share',multiplier=1,lot=100),fee_reserve_cny=fee_reserve_cny,
        fee_source=fee_source,market_manifest_source=market_manifest_source,
        price_basis=str(snapshot.get('source',{}).get('price_basis','as-frozen; qualification-unknown'))))


def configuration_id(value):
    keys=('strategy','policy','fee_reserve_cny','fee_source','price_basis')
    if value['strategy']['strategy_version']==OPEN_VERSION:
        keys+=('execution_map','fee_mode')
    return _digest({key:value[key] for key in keys})


def opening_buy_bound(fee_mode, quantity, price):
    if fee_mode=='per-share':
        return quantity*(price+Fraction('0.01'))
    return quantity*price*Fraction('1.0003')+Fraction('0.01')


def verify_report_input(report,payload,*,check=None):
    """绑定已准入报告和原规范输入；仅纯值，不重算金融结果或执行路径身份。"""
    if check:check()
    value=normalize_input(payload)
    _need(report['input_sha256']==_digest(value) and report['policy']==value['policy']
          and report['configuration_sha256']==configuration_id(value)
          and report['reference_report_sha256']==value['reference_report_sha256']
          and report['source_snapshot_sha256']==value['source_snapshot_sha256']
          and report['evaluation_window']==value['evaluation_window']
          and report['strategy_version']==value['strategy']['strategy_version'])
    expected={}
    for code,signals in sorted(value['reference_report']['trades_by_code'].items()):
        for signal in signals:
            if check:check()
            expected.setdefault(_day(signal['date']),[]).append(dict(code=code,**signal))
    _need([row['trading_date'] for row in report['records']]==[_day(d) for d in value['calendar'][1:]])
    opening=report['strategy_version']==OPEN_VERSION
    for index,row in enumerate(report['records']):
        if check:check()
        signal_day=_day(value['calendar'][index]) if opening else row['trading_date']
        _need(row['signals']==expected.get(signal_day,[]))
    if opening:
        quotes={(_native(code),_day(bar['date'])):bar['close']
                for code,rows in value['opening_bars'].items() for bar in rows if bar['minute']==OPEN_QUOTE}
        matches={(_native(code),_day(bar['date']))
                 for code,rows in value['opening_bars'].items() for bar in rows if bar['minute']==OPEN_MATCH}
        closes={(_native(code),_day(bar['date'])):bar['close']
                for code,rows in value['history'].items() for bar in rows}
        for row in report['records']:
            if check:check()
            day=row['trading_date']
            _need(all(price==closes[symbol,day] for symbol,price in row['capture']['prices']))
            for order in row['cash_control']['orders']:
                key=order['symbol'],day
                _need(key in matches and _money(order['limit_price_cny'])==Fraction(str(quotes[key])))
                expected_bound=opening_buy_bound(value['fee_mode'],order['quantity'],_money(order['limit_price_cny']))
                _need(_money(order['buy_cost_bound_cny'])==(expected_bound if order['action']=='BUY' else 0))
    return value


@dataclass(frozen=True,slots=True)
class OriginalNativeInput:
    _wire: dict  # 独占规范输入副本；外部通过to_dict取得新副本。

    @classmethod
    def from_dict(cls,value):return cls(normalize_input(value))

    def to_dict(self):return json.loads(_encode(self._wire))


@dataclass(frozen=True,slots=True,init=False)
class ValidatedOriginalNativeReport:
    _wire: object  # 唯一validator拥有的递归冻结JSON，不引用调用方可变对象。

    @property
    def record_count(self):return len(self._wire['records'])

    def to_dict(self,*,check=None):return _thaw_json(self._wire,check=check)


def validate_report(value,*,check=None):
    """只读校验原生CNY事实和来源摘要；控制回调异常沿原对象返回。"""
    def admit(guarded):
        report=_snapshot_json(value,maximum=MAX_BYTES,check=guarded)
        _need(type(report) is dict and set(report)=={'schema','session_id','input_sha256','scope','policy',
            'configuration_sha256','strategy_id','strategy_version','signal_algorithm_id','historical_model',
            'reference_report_sha256','source_snapshot_sha256','status','native_files','native_outputs',
            'callback_counts','records','source_qualified','execution_qualified','point_in_time_qualified',
            'execution_model','evaluation_window'} and report.get('schema')==REPORT_SCHEMA
            and report.get('strategy_id')==strategy_id_for_version(report.get('strategy_version'))
            and report.get('strategy_version') in (STRATEGY_VERSION,LEGACY_VERSION,OPEN_VERSION,CONFIRM_VERSION)
            and report.get('signal_algorithm_id')==ALGORITHM_ID
            and report.get('scope')==scope_for_version(report['strategy_version']))
        for name in ('session_id','input_sha256','configuration_sha256','reference_report_sha256','source_snapshot_sha256'):_hash(report.get(name))
        _need(report.get('source_qualified') is False and report.get('execution_qualified') is False and report.get('point_in_time_qualified') is False)
        model=model_for_version(report['strategy_version'])
        opening=report['strategy_version']==OPEN_VERSION
        constrained=report['strategy_version']!=LEGACY_VERSION
        _need(report.get('historical_model')==model and report.get('execution_model')==model)
        policy=report['policy']
        _need(type(policy) is dict and set(policy)=={'initial_capital_cny','capital_source','currency','quantity_unit','multiplier','lot'}
              and policy['initial_capital_cny']=='1000000' and policy['currency']=='CNY' and policy['quantity_unit']=='share'
              and type(policy['multiplier']) is int and policy['multiplier']==1
              and type(policy['lot']) is int and policy['lot']==100)
        _text(policy['capital_source'])
        native=dict(report['native_files']);_need(set(native)=={'sessions','commodities','contracts','holidays','fees'} and len(report['native_files'])==5)
        for native_hash in native.values():_hash(native_hash)
        outputs=dict(report['native_outputs']);_need(len(outputs)==len(report['native_outputs']) and 'trades.csv' in outputs)
        for output_hash in outputs.values():_hash(output_hash)
        records=report['records'];_need(type(records) is list and 1<=len(records)<=4095)
        window=report['evaluation_window']
        _need(type(window) is dict and set(window)=={'from','to','warmup_date'})
        _need(_day(window['warmup_date'])<_day(window['from'])<=_day(window['to']))
        _need(_day(window['from'])==records[0]['trading_date'] and _day(window['to'])==records[-1]['trading_date'])
        _need(report['status']==records[-1]['status'])
        counts=dict(report['callback_counts'])
        calculations=counts.get('calculate')
        _need(counts.get('init')==1 and type(calculations) is int)
        _need(3*len(records)<=calculations<=3*len(records)+1 if opening else calculations==len(records))
        previous=_day(window['warmup_date']) if opening else 0
        for index,row in enumerate(records):
            if guarded:guarded()
            _need(type(row) is dict and set(row)==({'trading_date','minute','status','reason','capture','signals',
                'submit_vector','readback','cash_deficit','result','outcome','previous_status'}|
                ({'cash_control'} if constrained else set())|({'opening'} if opening else set())))
            _text(row['status']);_text(row['reason'])
            _need(type(row['cash_deficit']) is bool and row['result'] is None
                  and row['outcome'] is None and row['previous_status'] is None)
            signal_day=previous if opening else row['trading_date']
            day=row['trading_date'];_need(type(day) is int and day>previous and row['minute']==1500);previous=day
            _day(f'{day:08d}'[:4]+'-'+f'{day:08d}'[4:6]+'-'+f'{day:08d}'[6:])
            capture=row['capture']
            _need(type(capture) is dict and set(capture)=={'session_id','sequence','trading_date','minute',
                'projection','positions','prices','funds','basis'}|({'native_marks'} if opening else set())
                and capture['session_id']==report['session_id']
                and type(capture['sequence']) is int and capture['sequence']==index+1
                and capture['trading_date']==day and capture['minute']==1500)
            basis=capture['basis']
            _need(type(basis) is dict and set(basis)=={'observed_at','input_sha256','nav_cny','cash_cny','pnl_cny',
                'capital_source','cash_source','price_basis'} and basis['input_sha256']==report['input_sha256'])
            for key in ('capital_source','cash_source','price_basis'):_text(basis[key])
            observed=datetime.fromisoformat(basis['observed_at'])
            _need(observed.utcoffset()==timedelta(hours=8) and observed.strftime('%Y%m%d%H%M')==str(day)+'1500')
            nav=_money(capture['basis']['nav_cny']);cash=_money(capture['basis']['cash_cny'])
            funds=capture['funds'];_need(type(funds) is dict and set(funds)=={'net','realized','dynamic','fees'}
                and all(type(funds[k]) in (int,float) and -1e20<=funds[k]<=1e20
                        and (type(funds[k]) is int or math.isfinite(funds[k])) for k in funds))
            net=Fraction(repr(float(funds['net'])))
            _need(_money(basis['pnl_cny'])==nav-1000000 and funds['fees']>=0)
            if not opening:
                _need(nav==1000000+net)
            _need(math.isclose(funds['net'],funds['realized']+funds['dynamic']-funds['fees'],rel_tol=1e-9,abs_tol=1e-6))
            positions=capture['positions'];_need(type(positions) is list and 1<=len(positions)<=9)
            for position in positions:
                _need(type(position) is dict and set(position)=={'symbol','total','valid','first_entry','last_entry'})
                _need(type(position['symbol']) is str and re.fullmatch(r'(?:SSE|SZSE)\.ETF\.[0-9]{6}',position['symbol']))
                _need(type(position['first_entry']) is int and type(position['last_entry']) is int
                      and position['first_entry']>=0 and position['last_entry']>=0)
            symbols={p['symbol'] for p in positions}
            _need(len(symbols)==len(positions) and type(capture['prices']) is list)
            prices=dict(capture['prices'])
            _need(len(prices)==len(capture['prices']) and set(prices)==symbols)
            for price in prices.values():
                if price is not None:_number(price,positive=True)
            market=Fraction(0)
            for position in positions:
                total=_quantity(position['total']);valid=_quantity(position['valid']);_need(valid<=total and total%100==0 and valid%100==0)
                actual=total if position['first_entry'] else 0
                price=prices[position['symbol']]
                if actual:_number(price,positive=True);market+=actual*Fraction(repr(float(price)))
            _need(cash==nav-market and row['cash_deficit']==(cash<0))
            if opening:
                native_marks=dict(capture['native_marks'])
                held={pos['symbol']:_quantity(pos['total']) for pos in positions if pos['first_entry'] and pos['total']}
                _need(len(capture['native_marks'])==len(native_marks) and set(native_marks)==set(held))
                native_market=sum(held[symbol]*Fraction(str(_number(mark,positive=True)))
                                  for symbol,mark in native_marks.items())
                _need(abs(cash-(1000000+net-native_market))<=Fraction('0.005'))
            order_positions=positions
            order_cash=cash
            if opening:
                opening_state=row['opening']
                _need(type(opening_state) is dict and set(opening_state)=={'cash_cny','positions'})
                order_cash=_money(opening_state['cash_cny'])
                _need(order_cash>=0 and type(opening_state['positions']) is list)
                order_positions=opening_state['positions']
                previous_positions=records[index-1]['capture']['positions'] if index else ()
                previous_actual={p['symbol']:_quantity(p['total']) for p in previous_positions if p['first_entry']}
                _need(len(order_positions)==len(symbols) and {p['symbol'] for p in order_positions}==symbols
                      and symbols=={_native(code) for code in OPEN_MAP.values()})
                for position in order_positions:
                    _need(set(position)=={'symbol','total','valid','first_entry','last_entry'})
                    total=_quantity(position['total'])
                    valid=_quantity(position['valid'])
                    _need(total==previous_actual.get(position['symbol'],0) and valid<=total and valid%100==0)
                    _need(type(position['first_entry']) is int and type(position['last_entry']) is int
                          and position['last_entry']>=position['first_entry']>=0
                          and bool(position['first_entry'])==bool(total))
            if constrained:
                _need(cash>=0)
                control=row['cash_control']
                _need(type(control) is dict and set(control)=={'available_cash_cny','reserved_buy_cost_cny','orders'})
                available=_money(control['available_cash_cny']);reserved=_money(control['reserved_buy_cost_cny'])
                buffer=Fraction('0.01') if opening else 1
                _need(available==max(Fraction(0),order_cash-buffer) and 0<=reserved<=available
                      and type(control['orders']) is list and len(control['orders'])<=9)
                order_symbols=set();total_bound=Fraction(0)
                for order in control['orders']:
                    _need(type(order) is dict and set(order)=={'symbol','action','quantity','limit_price_cny','buy_cost_bound_cny'}
                          and order['symbol'] in symbols and order['symbol'] not in order_symbols
                          and order['action'] in ('BUY','SELL') and _quantity(order['quantity'])>0
                          and _quantity(order['quantity'])%100==0 and _money(order['limit_price_cny'])>0)
                    order_symbols.add(order['symbol']);bound=_money(order['buy_cost_bound_cny'])
                    _need(bound>=0 and (order['action']=='BUY' or bound==0))
                    if order['action']=='BUY':
                        _need(bound>=order['quantity']*_money(order['limit_price_cny'])
                              and (opening or _money(order['limit_price_cny'])==Fraction(repr(float(prices[order['symbol']])))))
                    total_bound+=bound
                _need(reserved==total_bound)
            _need(type(row['submit_vector']) is list and len(row['submit_vector'])<=9)
            submitted=set()
            frozen={position['symbol']:(_quantity(position['total'])-_quantity(position['valid'])
                    if position['first_entry'] else 0) for position in order_positions}
            for target in row['submit_vector']:
                _need(type(target) is dict and set(target)=={'symbol','quantity'} and target['symbol'] in symbols
                      and target['symbol'] not in submitted and _quantity(target['quantity'])%100==0
                      and _quantity(target['quantity'])>=frozen[target['symbol']])
                submitted.add(target['symbol'])
            for pairs in (capture['projection'],row['readback']):
                _need(type(pairs) is list and len(pairs)<=9)
                projected=dict(pairs);_need(len(projected)==len(pairs) and set(projected)<=symbols)
                for quantity in projected.values():_need(_quantity(quantity)%100==0)
            if constrained:
                actual={p['symbol']:(_quantity(p['total']) if p['first_entry'] else 0) for p in order_positions}
                submitted={p['symbol']:_quantity(p['quantity']) for p in row['submit_vector']}
                orders={p['symbol']:p for p in control['orders']}
                _need(set(orders)=={s for s,q in submitted.items() if q!=actual[s]})
                for symbol,order in orders.items():
                    change=submitted[symbol]-actual[symbol]
                    _need(order['quantity']==abs(change) and order['action']==('BUY' if change>0 else 'SELL'))
                if opening:
                    _need(not row['readback'])
                else:
                    _need(row['readback']==capture['projection'] if orders else not row['readback'])
            _need(type(row['signals']) is list and len(row['signals'])<=9)
            signal_codes=set()
            for signal in row['signals']:
                _need(type(signal) is dict and set(signal)=={'code','date','action','price','reason'}
                      and type(signal['code']) is str and _native(OPEN_MAP.get(signal['code'],signal['code']) if opening else signal['code']) in symbols
                      and signal['code'] not in signal_codes and _day(signal['date'])==signal_day
                      and signal['action'] in ('BUY','SELL'))
                _number(signal['price'],positive=True);_text(signal['reason']);signal_codes.add(signal['code'])
        result=object.__new__(ValidatedOriginalNativeReport)
        object.__setattr__(result,'_wire',_freeze_json(report,check=guarded));return result
    def checked(guarded):
        try:return admit(guarded)
        except SessionError:raise
        except (KeyError,TypeError,ValueError,OverflowError):
            raise SessionError('原版WT报告嵌套结构或数值无效') from None
    return _run_report_checked(checked,check)


def project_record(report,index,*,check=None):
    if type(report) is not ValidatedOriginalNativeReport:report=validate_report(report,check=check)
    _need(type(index) is int and 0<=index<report.record_count)
    if check:check()
    row=_thaw_json(report._wire['records'][index],check=check)
    return dict(record=row,evaluation_summary={'signals':row['signals'],'cash_deficit':row['cash_deficit']},report_schema=REPORT_SCHEMA)
