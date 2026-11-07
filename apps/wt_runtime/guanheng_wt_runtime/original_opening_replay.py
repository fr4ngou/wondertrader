"""受管 WT 开盘回测。CtaMocker 拥有委托撮合、成交、T+1 与原生费用。"""
from collections import defaultdict
import csv
from dataclasses import asdict, replace
from datetime import datetime
from decimal import Decimal
from fractions import Fraction
import hashlib
import json
from pathlib import Path

from .original_native_contracts import (
    ALGORITHM_ID, DAY_CLOSE, OPEN_CODES, OPEN_MAP, OPEN_MATCH, OPEN_MODEL, OPEN_QUOTE,
    OPEN_SCOPE, OPEN_VERSION, REPORT_SCHEMA, STRATEGY_ID, _day, _digest, _money, _native,
    _need, _quantity, configuration_id, normalize_input, opening_buy_bound, validate_report,
)
from .original_native_replay import ABI_PROBE_SHA256, ORIGINAL_BT_SHA256, ZONE, session_identity
from .strategy_porter import BacktestPorter, Bar, Callbacks, Target
from .strategy_replay_facts import _decimal, admit_native_files

CAPITAL = 1_000_000
CENT = Fraction('0.01')
# 保留原回放的顺序。现金余量不足一整手时，按此顺序处理缩量。
ORDER_CODES = ('510300', '510050', '510500', '512100', '515080', '588000', '589680', '159780', '159352')


def _lots(quantity):
    return max(0, quantity // 100 * 100)


def _minute_bar(row):
    day = _day(row['date'])
    return Bar(day, (day - 19900000) * 10000 + row['minute'], row['open'], row['high'],
               row['low'], row['close'], 0., row['amount'], row['volume'])


def _cny(value):
    """原生 double 转十进制再舍入到分，与 WT 现金回放的单位一致。"""
    return Fraction(Decimal(_decimal(value)).quantize(Decimal('.01')))


class OpeningSession:
    """一次正式 runner 独占该实例；WT 原生回调推进同一时钟。"""

    def __init__(self, inputs):
        self.inputs = normalize_input(inputs)
        self.input_id = _digest(self.inputs)
        self.mapping = {code: _native(OPEN_MAP[code]) for code in ORDER_CODES}
        self.symbols = tuple(self.mapping.values())
        calendar = tuple(map(_day, self.inputs['calendar']))
        self.days = calendar[1:]
        self.previous_day = dict(zip(self.days, calendar))
        self.series = {_native(code): tuple(map(_minute_bar, rows)) for code, rows in self.inputs['opening_bars'].items()}
        self.match = {(symbol, bar.date) for symbol, rows in self.series.items() for bar in rows
                      if bar.time % 10000 == OPEN_MATCH}
        self.closes = {(_native(code), _day(row['date'])): row['close']
                       for code, rows in self.inputs['history'].items() for row in rows}
        self.signals = defaultdict(list)
        for code in OPEN_CODES:
            for signal in self.inputs['reference_report']['trades_by_code'][code]:
                self.signals[_day(signal['date'])].append(dict(code=code, **signal))
        self.quotes = {}
        self.buying = set()
        self.selling = set()
        self.plan = None
        self.records = []
        self.open_row = None
        self.matched = False
        self.session_id = None
        self.fee_mode = self.inputs['fee_mode']
        self.fee_reserve = _money(self.inputs['fee_reserve_cny'])

    def _initialize(self, porter):
        main = self.mapping['510300']
        _need(not porter.targets() and not porter.funds().net and not porter.funds().fees)
        for symbol in self.symbols:
            _need(porter.position(symbol).total == 0)
            porter.get_bars(symbol, 'm1', 2, main=symbol == main)
            porter.subscribe_bars(symbol, 'm1')

    def _load(self, symbol, period):
        _need(period == 'm1')
        return self.series[symbol]

    def _on_bar(self, porter, symbol, period, bar):
        if bar.date in self.previous_day and bar.time % 10000 == OPEN_QUOTE:
            self.quotes[symbol, bar.date] = Fraction(str(bar.close))

    def _positions(self, porter):
        return [asdict(porter.position(symbol)) for symbol in self.symbols]

    def _cash(self, porter, positions):
        market = sum(_quantity(pos['total']) * Fraction(str(porter.get_price(pos['symbol'])))
                     for pos in positions if pos['total'])
        cash = _cny(CAPITAL + Fraction(str(porter.funds().net)) - market)
        _need(cash >= 0)
        return cash

    def _target(self, positions, cash, quotes, signals):
        self.selling.intersection_update(symbol for symbol, qty in positions.items() if qty)
        for signal in signals:
            symbol = self.mapping[signal['code']]
            if signal['action'] == 'BUY':
                self.buying.add(symbol)
                self.selling.discard(symbol)
                self.plan = None
            else:
                self.selling.add(symbol)
                self.buying.discard(symbol)
                if self.plan is not None:
                    self.plan[symbol] = 0
        if self.plan is not None and positions == self.plan:
            self.plan = None
            self.buying.clear()
        if self.buying and self.plan is None:
            active = ({symbol for symbol, qty in positions.items() if qty} | self.buying) - self.selling
            if active:
                nav = cash + sum(qty * quotes[symbol] for symbol, qty in positions.items())
                self.plan = {symbol: _lots(nav / len(active) / quotes[symbol]) if symbol in active else 0
                             for symbol in self.symbols}
        target = dict(positions if self.plan is None else self.plan)
        for symbol in self.selling:
            target[symbol] = 0
        return target

    def _open(self, porter, day):
        _need(self.open_row is None)
        snapshot = self._positions(porter)
        cash = self._cash(porter, snapshot)
        positions = {position['symbol']: _quantity(position['total']) for position in snapshot}
        quotes = {symbol: self.quotes.pop((symbol, day)) for symbol in self.symbols}
        signals = self.signals.get(self.previous_day[day], [])
        target = self._target(positions, cash, quotes, signals)
        for pos in snapshot:
            symbol = pos['symbol']
            target[symbol] = max(target[symbol], positions[symbol] - _quantity(pos['valid']))
        increases = {symbol: qty - positions[symbol] for symbol, qty in target.items() if qty > positions[symbol]}
        available = max(Fraction(0), cash - CENT)
        full_cost = sum(opening_buy_bound(self.fee_mode, qty, quotes[symbol]) for symbol, qty in increases.items())
        scale = min(Fraction(1), available / full_cost) if full_cost else Fraction(1)
        for symbol, qty in increases.items():
            target[symbol] = positions[symbol] + _lots(qty * scale)

        reserved = Fraction(0)
        orders, skipped = [], []
        for symbol in self.symbols:
            delta = target[symbol] - positions[symbol]
            if delta == 0:
                continue
            if (symbol, day) not in self.match:
                skipped.append(symbol)
                target[symbol] = positions[symbol]
                continue
            price = quotes[symbol]
            bound = opening_buy_bound(self.fee_mode, delta, price) if delta > 0 else Fraction(0)
            if delta > 0 and reserved + bound > available:
                unit = opening_buy_bound(self.fee_mode, 1, price) - self.fee_reserve
                delta = _lots((available - reserved - self.fee_reserve) / unit)
                target[symbol] = positions[symbol] + delta
                if not delta:
                    continue
                bound = opening_buy_bound(self.fee_mode, delta, price)
            _need(delta % 100 == 0)
            reserved += bound
            orders.append(dict(symbol=symbol, action='BUY' if delta > 0 else 'SELL', quantity=abs(delta),
                               limit_price_cny=_decimal(price), buy_cost_bound_cny=_decimal(bound)))
        _need(reserved <= available)
        vector = tuple(Target(symbol, target[symbol]) for symbol in self.symbols) if orders else ()
        if orders:
            limits = tuple((order['symbol'], float(order['limit_price_cny'])) for order in orders)
            porter.submit_conditional_targets(vector, limits, 'original-open-588230')
        reason = '已提交 WT 开盘限价目标' if orders else '开盘目标未变或暂无可执行整手'
        if skipped:
            reason += '。缺少撮合分钟：' + '、'.join(skipped)
        self.open_row = dict(trading_date=day, minute=DAY_CLOSE, status='submitted' if orders else 'holding',
                             reason=reason, signals=signals, submit_vector=[asdict(item) for item in vector],
                             readback=[], cash_deficit=False, result=None, outcome=None, previous_status=None,
                             opening=dict(cash_cny=_decimal(cash), positions=snapshot),
                             cash_control=dict(available_cash_cny=_decimal(available),
                                               reserved_buy_cost_cny=_decimal(reserved), orders=orders))
        self.matched = False

    def _close(self, porter, day):
        _need(self.matched and self.open_row['trading_date'] == day)
        positions = self._positions(porter)
        prices = [[pos['symbol'], self.closes[pos['symbol'], day]] for pos in positions]
        market = sum(_quantity(pos['total']) * Fraction(str(price))
                     for pos, (_, price) in zip(positions, prices) if pos['first_entry'])
        funds = asdict(porter.funds())
        pnl = Fraction(str(funds['net']))
        native_marks = [[pos['symbol'], porter.get_price(pos['symbol'])] for pos in positions if pos['total']]
        native_market = sum(_quantity(pos['total']) * Fraction(str(mark))
                            for pos, (_, mark) in zip((p for p in positions if p['total']), native_marks))
        # 原生盯市价与冻结日线可能不同。先用原生净损益和原生盯市价还原现金，
        # 再用同一批实际持仓及原价日线估值，避免把价差记入现金。
        cash = _cny(CAPITAL + pnl - native_market)
        nav = cash + market
        _need(cash >= 0)
        self.open_row['capture'] = dict(
            session_id=self.session_id, sequence=len(self.records)+1, trading_date=day, minute=DAY_CLOSE,
            projection=[list(item) for item in porter.targets()], positions=positions, prices=prices, funds=funds,
            native_marks=native_marks,
            basis=dict(observed_at=datetime.strptime(str(day)+'1500', '%Y%m%d%H%M').replace(tzinfo=ZONE).isoformat(),
                       input_sha256=self.input_id, nav_cny=_decimal(nav), cash_cny=_decimal(cash), pnl_cny=_decimal(nav-CAPITAL),
                       capital_source='explicit-genesis-plus-WT-net',
                       cash_source='WT-NAV-minus-native-marks; raw-daily-close-valuation', price_basis=self.inputs['price_basis']))
        self.records.append(self.open_row)
        self.open_row = None

    def _calculate(self, porter, day, minute):
        if day not in self.previous_day:
            return
        if minute == OPEN_QUOTE:
            self._open(porter, day)
        elif minute == OPEN_MATCH:
            _need(self.open_row is not None and self.open_row['trading_date'] == day)
            self.matched = True
        elif minute == DAY_CLOSE:
            self._close(porter, day)

    def run(self, library, abi_probe, config):
        """用已绑定原生资料运行，再沿正式报告合同返回父进程。"""
        _need(config.start == self.previous_day[self.days[0]] * 10000 + 1459
              and config.end == self.days[-1] * 10000 + DAY_CLOSE)
        identities, frozen = admit_native_files(self.mapping, config)
        verify_opening_fees(self.fee_mode, frozen['fees'])
        base = Path(config.cwd) / 'session-basefiles'
        base.mkdir()
        for name, raw in frozen.items():
            (base / (name + '.json')).write_bytes(raw)
        config = replace(config, **{name: base / (name + '.json') for name in frozen})
        self.session_id = session_identity(self.input_id, config.cwd, config.start, config.end, config.name, identities)
        porter = BacktestPorter(library, ORIGINAL_BT_SHA256, abi_probe, ABI_PROBE_SHA256,
                                symbols=self.symbols, execution_symbols=self.symbols, max_execution_symbols=len(self.symbols),
                                loader=self._load, callbacks=Callbacks(self._initialize, self._calculate, self._on_bar))
        porter.configure(config)
        try:
            counts = porter.run()
        finally:
            porter.release()
        _need(tuple(row['trading_date'] for row in self.records) == self.days and self.open_row is None)
        output = Path(config.output) / config.name
        files = [[path.name, hashlib.sha256(path.read_bytes()).hexdigest()]
                 for path in sorted(output.iterdir()) if path.is_file()]
        report = dict(schema=REPORT_SCHEMA, session_id=self.session_id, input_sha256=self.input_id, scope=OPEN_SCOPE,
                      policy=self.inputs['policy'], configuration_sha256=configuration_id(self.inputs),
                      strategy_id=STRATEGY_ID, strategy_version=OPEN_VERSION, signal_algorithm_id=ALGORITHM_ID,
                      historical_model=OPEN_MODEL, execution_model=OPEN_MODEL, evaluation_window=self.inputs['evaluation_window'],
                      reference_report_sha256=self.inputs['reference_report_sha256'],
                      source_snapshot_sha256=self.inputs['source_snapshot_sha256'], status=self.records[-1]['status'],
                      native_files=[list(item) for item in identities], native_outputs=files,
                      callback_counts=[list(item) for item in counts], records=self.records,
                      source_qualified=False, execution_qualified=False, point_in_time_qualified=False)
        return validate_report(report).to_dict()


def verify_opening_fees(mode, raw):
    """限定本模型实际绑定的两种费率，防止标签与原生收费脱钩。"""
    fees = json.loads(raw)
    expected = (dict(byvolume=True, open=.01, close=.02, closetoday=.02) if mode == 'per-share'
                else dict(byvolume=False, open=.0003, close=.0003, closetoday=.0003))
    _need(all(fees.get(product) == expected for product in ('SSE.ETF', 'SZSE.ETF')))


def reconcile_opening_trades(report, stream, mode, *, check):
    """父责任层逐笔核原生撮合与现金，在签发完成证明前检查经济事实。"""
    grouped = defaultdict(list)
    trades = csv.DictReader(stream)
    _need(trades.fieldnames == ['code', 'time', 'direct', 'action', 'price', 'qty', 'tag', 'fee', 'barno'])
    report_days = {row['trading_date'] for row in report['records']}
    for trade in trades:
        check()
        stamp = trade['time']
        _need(len(stamp) == 12 and stamp[8:] == '0932' and int(stamp[:8]) in report_days)
        grouped[int(stamp[:8])].append(trade)
    held = defaultdict(int)
    fees, cash = Fraction(0), Fraction(CAPITAL)
    for row in report['records']:
        check()
        _need(_money(row['opening']['cash_cny']) == cash)
        orders = {order['symbol']: order for order in row['cash_control']['orders']}
        used = defaultdict(int)
        sellable = held.copy()
        for trade in grouped[row['trading_date']]:
            check()
            symbol = trade['code']
            _need(symbol in orders and trade['direct'] == 'LONG' and trade['tag'] == 'original-open-588230')
            order = orders[symbol]
            buy = order['action'] == 'BUY'
            quantity = _money(trade['qty'])
            price, fee, limit = _money(trade['price']), _money(trade['fee']), _money(order['limit_price_cny'])
            _need(quantity > 0 and quantity % 100 == 0 and price > 0 and fee >= 0)
            _need((trade['action'] == 'OPEN' and price <= limit) if buy else (trade['action'] == 'CLOSE' and price >= limit))
            used[symbol] += quantity
            _need(used[symbol] <= order['quantity'])
            amount = quantity * price
            raw_fee = (quantity * (CENT if buy else 2 * CENT) if mode == 'per-share' else amount * Fraction('0.0003'))
            _need(fee % CENT == 0 and abs(fee - raw_fee) <= CENT / 2)
            fees += fee
            if buy:
                cash -= amount + fee
                held[symbol] += quantity
            else:
                _need(quantity <= sellable[symbol])
                sellable[symbol] -= quantity
                held[symbol] -= quantity
                cash += amount - fee
            _need(cash >= 0)
        capture = row['capture']
        _need(all(held[pos['symbol']] == (pos['total'] if pos['first_entry'] else 0) for pos in capture['positions']))
        _need(abs(cash - _money(capture['basis']['cash_cny'])) <= CENT
              and abs(fees - Fraction(str(capture['funds']['fees']))) <= CENT)
