"""从 QMT 完整成交导出与原 R21 归档冻结跨日成交范围。"""
from argparse import ArgumentParser
from base64 import urlsafe_b64encode
import csv
from datetime import date, datetime, timezone
from decimal import Decimal
from hashlib import sha256
import io
import json
import os
from pathlib import Path

from .execution_deal_history import SCHEMA, ClosedDealHistory, _digest, scope_for
from .managed_local_process import _json, _read, _require


_EXPORT_FIELDS = ('资金账号', '证券市场', '证券代码', '成交编号', '合同编号',
                  '操作', '成交价格', '成交数量', '成交日期', '成交时间', '成交金额')
_EXCHANGES = {'SH': 'SSE', 'SZ': 'SZSE'}
_SIDES = {'买入': True, '卖出': False}


def _native_trade_id(exchange, code, day, broker_trade_id):
    """逐字节复用 NQH v1 规范，见 AccountMapping.cpp scoped_trade_id。"""
    parts = [value.encode('ascii') for value in (exchange, code, day, broker_trade_id)]
    canonical = b'guanheng.nqh.trade-id.v1\0' + b''.join(len(part).to_bytes(4, 'big')+part for part in parts)
    return 'nqh1.'+urlsafe_b64encode(sha256(canonical).digest()).decode('ascii').rstrip('=')


def verify_export(raw, expected_account, first_day, last_day, expected_rows, native_rows):
    """以 QMT 查询页面总行数和范围核逐笔原事实；保留 Native 完整时间精度。"""
    exported = csv.reader(io.StringIO(raw.decode('gb18030')), delimiter='\t')
    header = next(exported)
    _require(all(header.count(name) == 1 for name in _EXPORT_FIELDS))
    indices = [header.index(name) for name in _EXPORT_FIELDS]
    by_id = {row['trade_id']: row for row in native_rows
             if first_day <= datetime.strptime(str(row['trade_date']), '%Y%m%d').date() <= last_day}
    _require(len(by_id) == expected_rows)
    result = []
    for line in exported:
        _require(len(line) == len(header))
        account, market, code, broker_id, order, side, price, quantity, day, clock, amount = (
            line[index].strip() for index in indices)
        _require(account == expected_account and market in _EXCHANGES and side in _SIDES
                 and code.isascii() and code.isdecimal() and len(code) == 6 and broker_id and order)
        exchange = _EXCHANGES[market]
        row = by_id.pop(_native_trade_id(exchange, code, day, broker_id))
        second = datetime.strptime(clock, '%H:%M:%S')
        _require(row['symbol'].split('.')[::2] == [exchange, code]
                 and row['order_id'] == order and str(row['trade_date']) == day
                 and row['trade_time']//1000 == int(second.strftime('%H%M%S'))
                 and row['is_buy'] is _SIDES[side]
                 and Decimal(str(row['price'])) == Decimal(price)
                 and Decimal(str(row['quantity'])) == Decimal(quantity)
                 and Decimal(str(row['amount'])) == Decimal(amount))
        result.append(row)
    _require(not by_id and len(result) == expected_rows)
    return sorted(result, key=lambda row: (row['trade_date'], row['trade_time'], row['trade_id']))


def _bound_snapshot(control):
    configuration_raw = _read(control/'execution.json', 256*1024)
    config = _json(configuration_raw)
    ready = _json(_read(control/'ready.json', 4096))
    snapshot_raw = _read(control/'strategies.json', 4*1024*1024)
    snapshot = _json(snapshot_raw)
    identity = dict(config_sha256=sha256(configuration_raw).hexdigest(), control_id=control.name, pid=ready['pid'])
    _require(ready['schema'] == 'guanheng.execution.ready.v1' and ready['closed'] is False
             and snapshot['schema'] == 'guanheng.configured-cta-observation.v2'
             and all(ready.get(key) == snapshot.get(key) == expected for key, expected in identity.items()))
    _require(len(config['strategies']) == 1 and len(snapshot['strategies']) == 1)
    strategy = config['strategies'][0]
    parameters = strategy['parameters']['python_strategy']
    _require(parameters['schema'] == 'guanheng.retained-cta.v1')
    raw_input = _read(Path(parameters['input_file']), 16*1024*1024)
    input_sha = sha256(raw_input).hexdigest()
    _require(input_sha == parameters['input_sha256'])
    baseline_at = _json(raw_input)['capital_baseline']['baseline_at']
    facts = snapshot['strategies'][strategy['id']]['broker_trades']
    _require(facts['known'] is True and facts['error'] == 0 and facts['query_revision'] > 0)
    return config, input_sha, baseline_at, facts['trades'], sha256(snapshot_raw).hexdigest()


def prepare(export, control, coverage):
    """冻结已核材料；查询成功与范围由受控 QMT 原件及现场观察收据负责。"""
    config, input_sha, baseline, native_rows, source_sha = _bound_snapshot(control)
    raw = _read(export, 4*1024*1024)
    receipt_raw = _read(coverage, 65536)
    receipt = _json(receipt_raw)
    scope = scope_for(config, input_sha)
    export_sha = sha256(raw).hexdigest()
    _require(set(receipt) == {'schema', 'scope', 'export_sha256', 'query', 'confirmations'}
             and receipt['schema'] == 'guanheng.qmt-deal-query-observed.v1'
             and receipt['scope'] == scope and receipt['export_sha256'] == export_sha)
    query = receipt['query']
    _require(set(query) == {'mode', 'filter', 'first_day', 'last_day', 'rows', 'pages',
                           'completed_at', 'exported_at', 'success'}
             and query['mode'] == 'deal_detail' and query['filter'] == 'all_sources'
             and query['success'] is True and query['pages'] == 1
             and type(query['rows']) is int and query['rows'] >= 0)
    first, last = (date.fromisoformat(query[key]) for key in ('first_day', 'last_day'))
    completed, received = (datetime.fromisoformat(query[key]) for key in ('completed_at', 'exported_at'))
    _require(completed.utcoffset() is not None and received.utcoffset() is not None
             and completed <= received <= datetime.now(timezone.utc))
    rows = verify_export(raw, config['trader']['expected_account'], first, last, query['rows'], native_rows)
    for confirmation in receipt['confirmations']:
        _require(set(confirmation) == {'first_day', 'last_day', 'rows', 'success', 'completed_at'}
                 and confirmation['success'] is True and type(confirmation['rows']) is int
                 and confirmation['rows'] >= 0)
        lower, upper = (date.fromisoformat(confirmation[key]) for key in ('first_day', 'last_day'))
        checked = datetime.fromisoformat(confirmation['completed_at'])
        _require(first <= lower <= upper <= last and completed <= checked <= datetime.now(timezone.utc))
        _require(sum(lower <= datetime.strptime(str(r['trade_date']), '%Y%m%d').date() <= upper
                     for r in rows) == confirmation['rows'])
    value = dict(schema=SCHEMA, scope=scope, first_day=query['first_day'], last_day=query['last_day'],
        received_at=received.isoformat(), export_sha256=export_sha,
        observation_sha256=source_sha, coverage_sha256=sha256(receipt_raw).hexdigest(), rows=rows)
    value['sha256'] = _digest(value)
    ClosedDealHistory.from_dict(value, scope, baseline)
    return value


def main(argv=None):
    parser = ArgumentParser(description='核对原账户历史成交导出和原 WT R21 观察，输出只读周期材料')
    parser.add_argument('--export', type=Path, required=True)
    parser.add_argument('--control', type=Path, required=True)
    parser.add_argument('--coverage', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    value = prepare(args.export, args.control, args.coverage)
    raw = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('ascii')
    with args.output.open('xb') as stream:
        _require(stream.write(raw) == len(raw))
        stream.flush()
        os.fsync(stream.fileno())
    print(json.dumps(dict(rows=len(value['rows']), first_day=value['first_day'], last_day=value['last_day'],
                          sha256=value['sha256']), sort_keys=True))


if __name__ == '__main__':
    main()
