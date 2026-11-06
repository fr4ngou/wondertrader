"""核验后WT原件的可视化投影；金额和持仓沿原生报告，派生只用于展示。"""
import csv
from datetime import datetime
from decimal import Decimal
from hashlib import sha256
from io import StringIO

from .backtest_performance import _fraction, _percentage


def _rows(raw, fields, check):
    if raw is None:
        return None
    source = csv.DictReader(StringIO(raw.decode('utf-8-sig')))
    if source.fieldnames != fields:
        return None
    rows = []
    for row in source:
        check()
        if len(rows) >= 65536 or set(row) != set(fields) or any(v is None or len(v) > 512 for v in row.values()):
            raise ValueError('原生成交或持仓行超出展示范围')
        rows.append(row)
    return rows


def _day(value):
    datetime.strptime(value, '%Y%m%d')
    return int(value)


def _amount(value, *, positive=False, nonnegative=False):
    amount = _fraction(value)
    if positive and amount <= 0 or nonnegative and amount < 0:
        raise ValueError('原生数量、价格或费用无效')
    # 原生CSV对大数量可输出科学计数；精确展开为公开DTO十进制，原文件仍按SHA保留。
    # Decimal的固定格式保留普通2.00等尾零，不经float或舍入改变金融数值。
    normalized = format(Decimal(value), 'f')
    if not normalized or len(normalized) > 512:
        raise ValueError('原生金额格式无效')
    return normalized


def build_visuals(performance, trades, *, check):
    """日期对应收益/回撤和成交笔数；首日和跨缺失的日收益保持未知。"""
    counts = {}
    for row in trades or []:
        check()
        bucket = counts.setdefault(row['date'], [0, 0, 0])
        bucket[{'buy': 0, 'sell': 1}.get(row['side'], 2)] += 1
    peak = _fraction(performance['metrics']['initial_capital_cny'])
    previous, points = None, []
    for day, value in performance['points']:
        check()
        nav = None if value is None else _fraction(value)
        daily = None if nav is None or previous is None or previous <= 0 else _percentage((nav / previous - 1) * 100)
        if nav is not None:
            peak = max(peak, nav)
        drawdown = None if nav is None else _percentage((nav / peak - 1) * 100)
        points.append([day, daily, drawdown, *counts.get(day, [0, 0, 0])])
        previous = nav
    return {'schema': 'nbw-visuals-v1', 'run_id': performance['run_id'],
            'receipt_sha256': performance['receipt_sha256'], 'report_sha256': performance['report_sha256'],
            'trades_available': trades is not None, 'points': points}


def native_tables(read, directory, receipt, request):
    """只读取已完成归档声明的原生同名CSV，二次读取仍校验原摘要。"""
    def raw(name):
        relative = f"outputs/{receipt['configuration']['name']}/{name}.csv"
        expected = request['native_outputs'].get(relative)
        if expected is None:
            return None
        value = read.raw(directory / relative, 8 * 1024 * 1024)
        if sha256(value).hexdigest() != expected:
            raise ValueError('原件在读取期间改变')
        return value
    trades = _rows(raw('trades'), ['code', 'time', 'direct', 'action', 'price', 'qty', 'tag', 'fee', 'barno'], read.check)
    positions = _rows(raw('positions'), ['date', 'code', 'volume', 'closeprofit', 'dynprofit'], read.check)
    normalized = None if trades is None else []
    for index, row in enumerate(trades or []):
        read.check()
        datetime.strptime(row['time'], '%Y%m%d%H%M')
        side = {('LONG', 'OPEN'): 'buy', ('LONG', 'CLOSE'): 'sell',
                ('SHORT', 'OPEN'): 'sell', ('SHORT', 'CLOSE'): 'buy'}.get((row['direct'], row['action']), 'unknown')
        normalized.append({'index': index, 'date': _day(row['time'][:8]), 'time': row['time'],
            'symbol': row['code'], 'side': side, 'direction': row['direct'], 'action': row['action'],
            'price': _amount(row['price'], positive=True), 'quantity': _amount(row['qty'], positive=True),
            'fee_cny': _amount(row['fee'], nonnegative=True)})
    holdings = None if positions is None else []
    seen = set()
    for row in positions or []:
        read.check()
        day = _day(row['date']); identity = (day, row['code'])
        if identity in seen:
            raise ValueError('原生日末持仓重复')
        seen.add(identity)
        holdings.append({'date': day, 'symbol': row['code'], 'quantity': _amount(row['volume']),
                         'realized_cny': _amount(row['closeprofit']), 'floating_cny': _amount(row['dynprofit'])})
    return normalized, holdings
