"""策略资金进出事实与时间加权收益。记录不参与账户划款或交易授权。"""
from contextlib import closing
from datetime import datetime, timezone
from fractions import Fraction
from itertools import groupby
import json
import os
from pathlib import Path
import re
import sqlite3
from time import monotonic

from .execution_facts import _decimal
from .managed_local_process import _inspect, _json, _read
from .strategy_capital import _digest, baseline, cash_anchor

FILE_NAME = 'strategy-capital-flows.sqlite3'
_DIRECTIONS = {'inflow', 'outflow'}
_FLOW = {'direction', 'amount_cny', 'effective_at', 'nav_before_cny', 'nav_observed_at', 'nav_source_ref',
         'nav_cash_receipt_ref'}
_ID = re.compile(r'[A-Za-z0-9_.:+-]{1,128}')
_MONEY = re.compile(r'[0-9]{1,30}(?:\.[0-9]{1,30})?')
_REASONS = {
    'available': '已按资金进出时点调整。',
    'coverage_pending': '策略资金流入或提取记录尚未覆盖本次估值时点。',
    'valuation_pending': '部分资金变动缺少变动前净值，投资收益率暂不可算。',
    'reconciliation_pending': '资金变动与策略净值的入账或估值时点尚未对齐。',
    'basis_pending': '本段净值基准尚未核实，投资收益率暂不可算。',
    'record_unavailable': '策略资金流水本轮读取失败，投资收益率暂不可用。',
}


def _need(condition):
    if not condition:
        raise ValueError('strategy_capital_flow_record_invalid')


def _identifier(value):
    return type(value) is str and _ID.fullmatch(value) is not None


def _stamp(value):
    _need(type(value) is str and 1 <= len(value) <= 64)
    time = datetime.fromisoformat(value)
    _need(time.utcoffset() is not None)
    return time.astimezone(timezone.utc)


def _money(value):
    _need(type(value) is str and _MONEY.fullmatch(value) is not None)
    return Fraction(value)


def capital_identity(strategy_id, origin, anchor):
    """以原策略、资金基准和账户摘要定位稳定经济范围。"""
    _need(_identifier(strategy_id))
    origin = baseline(origin)
    anchor = cash_anchor(anchor, origin)
    return _digest([strategy_id, anchor['baseline_sha256'], anchor['account_binding_sha256']])


def _flow(value, start, now):
    _need(type(value) is dict and set(value) == _FLOW and value['direction'] in _DIRECTIONS)
    effective = _stamp(value['effective_at'])
    _need(start < effective <= now and _money(value['amount_cny']) > 0)
    _need(value['nav_cash_receipt_ref'] is None or _identifier(value['nav_cash_receipt_ref']))
    if value['nav_before_cny'] is None:
        _need(value['nav_observed_at'] is None and value['nav_source_ref'] is None)
    else:
        _need(_money(value['nav_before_cny']) >= 0 and _identifier(value['nav_source_ref']))
        _need(start <= _stamp(value['nav_observed_at']) <= effective)
    return value


def _record(value, start, now):
    _need(type(value) is dict and all(_identifier(value.get(k)) for k in ('id', 'source_ref')))
    common = {'id', 'source_ref', 'kind'}
    kind = value.get('kind')
    if kind == 'flow':
        _flow({k: v for k, v in value.items() if k not in common}, start, now)
    elif kind == 'coverage':
        _need(set(value) == common | {'direction', 'through'} and value['direction'] in _DIRECTIONS
              and start <= _stamp(value['through']) <= now)
    elif kind == 'correction':
        _need(set(value) == common | {'original_id', 'replacement', 'reason'}
              and _identifier(value['original_id']) and type(value['reason']) is str
              and 0 < len(value['reason'].strip()) <= 300)
        if value['replacement'] is not None:
            _flow(value['replacement'], start, now)
    else:
        _need(False)
    return value


def _reduce(records, start, now):
    active, originals = {}, set()
    covered = {direction: None for direction in _DIRECTIONS}

    def changed(flow):
        until = covered[flow['direction']]
        if until is not None and _stamp(flow['effective_at']) <= until:
            covered[flow['direction']] = None

    for record in records:
        item = _record(record, start, now)
        kind = item['kind']
        if kind == 'coverage':
            direction = item['direction']
            through = _stamp(item['through'])
            covered[direction] = max(covered[direction] or start, through)
        elif kind == 'flow':
            originals.add(item['id'])
            changed(item)
            active[item['id']] = {k: item[k] for k in _FLOW}
        else:
            original = item['original_id']
            _need(original in originals)
            before = active.pop(original, None)
            if before is not None:
                changed(before)
            after = item['replacement']
            if after is not None:
                changed(after)
                active[original] = after
    return covered, active


def _db(path, *, readonly, deadline):
    _inspect(path.parent, directory=True)
    if os.path.lexists(path) or readonly:
        _inspect(path)
    left = deadline - monotonic()
    if left <= 0:
        raise TimeoutError('strategy_capital_flow_deadline')
    connection = sqlite3.connect(path.as_uri() + ('?mode=ro' if readonly else '?mode=rwc'),
                                 uri=True, timeout=left)
    connection.set_progress_handler(lambda: monotonic() >= deadline, 1000)
    return connection


def _records(db, scope, deadline):
    for (payload,) in db.execute('SELECT payload FROM entries WHERE scope=? ORDER BY seq', (scope,)):
        _check_deadline(deadline)
        yield json.loads(payload)


def append_record(path, scope, origin, value, *, deadline):
    """原回执或请求重复时返回原记录；更正只追加，不覆盖。"""
    now = datetime.now(timezone.utc)
    start = _stamp(origin['baseline_at'])
    value = _record(value, start, now)
    payload = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':'))
    with closing(_db(path, readonly=False, deadline=deadline)) as db, db:
        db.execute('PRAGMA synchronous=FULL')
        db.execute('BEGIN IMMEDIATE')
        db.execute('CREATE TABLE IF NOT EXISTS entries(seq INTEGER PRIMARY KEY, scope TEXT NOT NULL, '
                   'id TEXT NOT NULL, kind TEXT NOT NULL, source TEXT NOT NULL, payload TEXT NOT NULL, '
                   'recorded_at TEXT NOT NULL, UNIQUE(scope,id))')
        db.execute('CREATE UNIQUE INDEX IF NOT EXISTS record_source ON entries(scope,kind,source)')
        previous = db.execute('SELECT payload,recorded_at FROM entries WHERE scope=? AND id=?',
                              (scope, value['id'])).fetchone()
        if previous is not None:
            _need(previous[0] == payload)
            return dict(value, recorded_at=previous[1])
        previous = db.execute('SELECT payload,recorded_at FROM entries WHERE scope=? AND kind=? AND source=?',
                              (scope, value['kind'], value['source_ref'])).fetchone()
        if previous is not None:
            old = json.loads(previous[0])
            _need(dict(old, id=value['id']) == value)
            return dict(old, recorded_at=previous[1])
        if value['kind'] == 'correction':
            target = db.execute("SELECT 1 FROM entries WHERE scope=? AND id=? AND kind='flow'",
                                (scope, value['original_id'])).fetchone()
            _need(target is not None)
        db.execute('INSERT INTO entries(scope,id,kind,source,payload,recorded_at) VALUES(?,?,?,?,?,?)',
                   (scope, value['id'], value['kind'], value['source_ref'], payload, now.isoformat()))
        return dict(value, recorded_at=now.isoformat())


def _weighted_return(start_value, ending, flows, start, deadline):
    if ending < 0:
        return 'basis_pending', None
    factor = Fraction(1)
    previous = start
    for effective, entries in groupby(flows, key=lambda flow: _stamp(flow['effective_at'])):
        _check_deadline(deadline)
        group = list(entries)
        if any(flow['nav_cash_receipt_ref'] is None for flow in group):
            return 'reconciliation_pending', None
        if any(flow['nav_before_cny'] is None for flow in group):
            return 'valuation_pending', None
        evidence = {(_money(flow['nav_before_cny']), _stamp(flow['nav_observed_at']), flow['nav_source_ref'])
                    for flow in group}
        if len(evidence) != 1:
            return 'valuation_pending', None
        before, observed, _ = evidence.pop()
        if observed < start or (previous > start and observed <= previous):
            return 'valuation_pending', None
        change = sum(_money(flow['amount_cny']) * (1 if flow['direction'] == 'inflow' else -1)
                     for flow in group)
        if start_value > 0:
            factor *= before / start_value
        elif before != 0:
            return 'basis_pending', None
        start_value = before + change
        if start_value < 0:
            return 'basis_pending', None
        previous = effective
    if start_value > 0:
        factor *= ending / start_value
    elif ending != 0:
        return 'basis_pending', None
    return 'available', _decimal(Fraction(round((factor - 1) * 100_000_000), 1_000_000))


def _check_deadline(deadline):
    if monotonic() >= deadline:
        raise TimeoutError('strategy_capital_flow_deadline')


def observe_return(path, strategy_id, capital, *, deadline):
    """消费同一估值和策略资金范围。流水读取异常只降级收益观察。"""
    origin, anchor = capital['baseline'], capital['cash_anchor']
    start, end = _stamp(origin['baseline_at']), _stamp(capital['observed_at'])
    cash_at = _stamp(capital['account_observed_at'])
    required = max(cash_at, end)
    result = dict(baseline_at=start.isoformat(), valued_at=end.isoformat(),
                  valuation_nav_cny=capital['nav_cny'], cash_observed_at=cash_at.isoformat(),
                  coverage_required_at=required.isoformat(),
                  inflow_through=None, outflow_through=None, flow_count=0, flows=[])
    state, rate = 'coverage_pending', None
    try:
        scope = capital_identity(strategy_id, origin, anchor)
        if os.path.lexists(path):
            with closing(_db(path, readonly=True, deadline=deadline)) as db:
                covered, active = _reduce(_records(db, scope, deadline), start, datetime.now(timezone.utc))
            selected = sorted(((key, flow) for key, flow in active.items() if _stamp(flow['effective_at']) <= end),
                              key=lambda row: (_stamp(row[1]['effective_at']), row[0]))
            result.update(flow_count=len(selected), flows=[dict(id=_digest([scope, key]),
                **{name: flow[name] for name in ('direction', 'amount_cny', 'effective_at')})
                for key, flow in selected[-20:]])
            for direction, stamp in covered.items():
                result[direction + '_through'] = stamp.isoformat() if stamp else None
            if end >= start and all(stamp is not None and stamp >= required for stamp in covered.values()):
                # 持仓估值与账户现金可能来自不同时点；期间发生资金变动时等待同口径终点。
                low, high = sorted((cash_at, end))
                if any(low < _stamp(flow['effective_at']) <= high for flow in active.values()):
                    state = 'reconciliation_pending'
                else:
                    state, rate = _weighted_return(_money(origin['total_cny']), Fraction(capital['nav_cny']),
                                                   (flow for _, flow in selected), start, deadline)
    except (OSError, sqlite3.Error, ValueError, TypeError, KeyError, TimeoutError):
        state = 'record_unavailable'
    return dict(result, state=state, return_pct=rate, reason=_REASONS[state])


class ReturnValuations:
    """账户观察线程保存待对账的估值与最近已核估值，并按有效流水重算。"""

    def __init__(self, path, strategy_id):
        self.path = path
        self.strategy_id = strategy_id
        self.pending = None
        self.settled = None

    def observe(self, capital, *, deadline):
        if self.pending is None or (self.pending['baseline'], self.pending['cash_anchor']) != (
                capital['baseline'], capital['cash_anchor']):
            self.pending = capital
            self.settled = None
        current = observe_return(self.path, self.strategy_id, capital, deadline=deadline)
        if current['state'] == 'available':
            self.pending = self.settled = capital
            return current
        if self.pending is self.settled:
            self.pending = capital
        if self.pending != capital:
            result = observe_return(self.path, self.strategy_id, self.pending, deadline=deadline)
            if result['state'] == 'available':
                self.settled, self.pending = self.pending, capital
                return result
            if result['state'] in ('reconciliation_pending', 'valuation_pending', 'basis_pending'):
                self.pending = capital
        if self.settled is not None:
            result = observe_return(self.path, self.strategy_id, self.settled, deadline=deadline)
            if result['state'] == 'available':
                return result
        return current


def main(argv=None):
    """运维录入沿实际WT配置定位策略原点，只写资金事件。"""
    import argparse
    from hashlib import sha256

    parser = argparse.ArgumentParser(description='登记已生效的策略资金进出或覆盖事实')
    parser.add_argument('--execution-config', type=Path, required=True)
    parser.add_argument('--config-sha256', required=True)
    parser.add_argument('--strategy-id', required=True)
    parser.add_argument('--record', type=Path, required=True)
    args = parser.parse_args(argv)
    deadline = monotonic() + 5
    raw = _read(args.execution_config, 256 * 1024, clock=monotonic, deadline=deadline)
    _need(sha256(raw).hexdigest() == args.config_sha256)
    configuration = _json(raw)
    rows = [row for row in configuration['strategies'] if row['id'] == args.strategy_id]
    _need(len(rows) == 1 and configuration['trader']['environment'] in ('simulation', 'live'))
    settings = rows[0]['parameters']['python_strategy']
    original = _read(Path(settings['input_file']), 16 * 1024 * 1024, clock=monotonic, deadline=deadline)
    _need(sha256(original).hexdigest() == settings['input_sha256'])
    inputs = _json(original)
    origin, anchor = inputs['capital_baseline'], inputs['cash_anchor']
    scope = capital_identity(args.strategy_id, origin, anchor)
    account = dict(account=configuration['trader']['expected_account'], environment=configuration['trader']['environment'], currency='CNY')
    _need(anchor['account_binding_sha256'] == _digest(account))
    path = Path(configuration['output_directory']) / FILE_NAME
    operation = _json(_read(args.record, 64 * 1024, clock=monotonic, deadline=deadline))
    receipt = append_record(path, scope, origin, operation, deadline=deadline)
    print(json.dumps({key: receipt[key] for key in ('id', 'kind', 'recorded_at')}, ensure_ascii=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
