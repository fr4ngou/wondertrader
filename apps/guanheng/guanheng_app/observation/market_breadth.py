"""同一沪深股票池、同一来源交易日的广度和换手统计；输入保留供应商字符串。"""

from datetime import date
from decimal import Decimal, InvalidOperation
import math
import re


def _number(value):
    if value in ('', None):
        return None
    if type(value) is not str or len(value) > 128:
        raise ValueError('stock number must be a bounded provider string')
    try:
        result = Decimal(value)
    except InvalidOperation:
        raise ValueError('stock number is invalid') from None
    if not result.is_finite() or result.copy_abs() > Decimal('1e30'):
        raise ValueError('stock number is not finite or exceeds capacity')
    return result


def _ratio(numerator, denominator, scale=100):
    if not denominator:
        return None
    result = float(Decimal(numerator) * scale / Decimal(denominator))
    if not math.isfinite(result):
        raise ValueError('stock ratio exceeds capacity')
    return result


def stock_day(fields, rows, universe, day, *, scope='shsz', check=lambda: None):
    """按已声明股票池计算日终观察；缺行/缺值保留未知，停牌单列。

    universe来自同源证券类型及上市/退市日期准入，volume单位为原始股数，
    turn单位为流通股换手百分数。函数不推导财务指标或40日均线资格。
    """
    check()
    if date.fromisoformat(day).isoformat() != day:
        raise ValueError('invalid stock day')
    if not 1 <= len(universe) <= 20000 or len(set(universe)) != len(universe):
        raise ValueError('invalid stock universe size or duplicates')
    if scope not in ('shsz', 'ashare'):
        raise ValueError('invalid stock scope')
    pattern = r'(sh|sz)\.[0-9]{6}' if scope == 'shsz' else r'(sh|sz|bj)\.[0-9]{6}'
    if any(type(code) is not str or re.fullmatch(pattern, code) is None for code in universe):
        raise ValueError('invalid stock identity for declared scope')
    required = {'date', 'code', 'close', 'preclose', 'volume', 'turn', 'tradestatus'}
    if (not 1 <= len(fields) <= 64 or len(set(fields)) != len(fields)
            or not required <= set(fields) or len(rows) > 20000):
        raise ValueError('invalid stock fields or row capacity')
    eligible, seen = set(universe), set()
    up = down = flat = suspended = missing_prices = missing_volume = known_turn = hot = excluded = 0
    up_volume = down_volume = Decimal(0)
    for values in rows:
        check()
        if len(values) != len(fields) or any(type(v) is not str for v in values):
            raise ValueError('invalid stock string row')
        row = dict(zip(fields, values))
        if row['date'] != day:
            raise ValueError('stock day mismatch')
        code = row['code']
        if code not in eligible:
            excluded += 1
            continue
        if code in seen:
            raise ValueError('duplicate stock day')
        seen.add(code)
        if row['tradestatus'] not in ('0', '1'):
            raise ValueError('invalid stock trading status')
        close, prior, volume, turn = (_number(row[key]) for key in ('close', 'preclose', 'volume', 'turn'))
        if volume is not None and (volume < 0 or volume != volume.to_integral_value()):
            raise ValueError('invalid volume in shares')
        if turn is not None and turn < 0:
            raise ValueError('invalid turnover percentage')
        if row['tradestatus'] == '0':
            suspended += 1
            if volume in (None, Decimal(0)) and turn in (None, Decimal(0)):
                known_turn += 1
            continue
        if turn is not None:
            known_turn += 1
            hot += turn > Decimal(5)
        if close is None or prior is None or close <= 0 or prior <= 0:
            missing_prices += 1
            continue
        if close == prior:
            flat += 1
            continue
        if volume is None:
            missing_volume += 1
        if close > prior:
            up += 1
            if volume is not None:
                up_volume += volume
        else:
            down += 1
            if volume is not None:
                down_volume += volume
    count = len(eligible)
    classified = up + down + flat
    unclassified = count - classified - suspended
    trin = None
    if not unclassified and not missing_volume and up and down and up_volume and down_volume:
        trin = _ratio(Decimal(up) * down_volume, Decimal(down) * up_volume, 1)
    check()
    return dict(date=day, available_at=None, market_count=count, reported_count=len(seen),
                excluded_count=excluded, suspended_count=suspended, missing_stock_count=count-len(seen),
                missing_price_count=missing_prices, classified_count=classified, unclassified_count=unclassified,
                advancing_count=up, declining_count=down, flat_count=flat, net_advances=up-down,
                advancing_pct=_ratio(up, classified), rana=_ratio(up-down, up+down, 1000),
                advancing_volume=float(up_volume), declining_volume=float(down_volume),
                missing_volume_count=missing_volume, trin=trin,
                turnover_known_count=known_turn, turnover_missing_count=count-known_turn,
                turnover_gt5_count=hot, turnover_gt5_pct=_ratio(hot, count) if known_turn == count else None,
                turnover_confirmed_lower_bound_pct=_ratio(hot, count),
                turnover_sample_pct=_ratio(hot, known_turn),
                breadth_status='complete' if not unclassified else 'partial',
                turnover_status='complete' if known_turn == count else 'partial')
