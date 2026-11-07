"""ASA唯一归属账的公开白名单；不借用账户同码数量、成交或净值。"""
from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
import hashlib
import re


def _need(ok):
    if not ok: raise ValueError('策略归属观察格式无效')


def security(value):
    match = re.fullmatch(r'(SSE|SZSE)\.ETF\.([0-9]{6})', value) if type(value) is str else None
    _need(match is not None)
    return match[2] + ('.SH' if match[1] == 'SSE' else '.SZ')


def _quantity(value):
    _need(type(value) is int and 0 <= value <= 9007199254740991)
    return value


def _money(value, *, optional=False):
    if optional and value is None: return None
    _need(type(value) is str and len(value) <= 128)
    try: amount = Decimal(value)
    except InvalidOperation: raise ValueError('策略归属金额无效') from None
    _need(amount.is_finite() and abs(amount) <= 9007199254740991 and -126 <= amount.as_tuple().exponent <= 126)
    return format(amount, 'f')


def _time(value):
    if value is None: return None
    _need(type(value) is str and len(value) <= 64)
    stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
    _need(stamp.utcoffset() is not None and stamp <= datetime.now(timezone.utc))
    return stamp.astimezone(timezone.utc).isoformat()


def _sha(value, *, optional=False):
    if optional and value is None: return None
    _need(type(value) is str and re.fullmatch('[a-f0-9]{64}', value))
    return value


def project_allocation(identity, report):
    """复制当前策略原ASA事务投影；旧DTO未发布的D/clock保持None。"""
    original = report.get('allocation_observation')
    if original is None: return None
    _need(type(original) is dict and type(original.get('strategy')) is dict)
    own = original['strategy']
    _need(own.get('strategy_id') == identity and type(own.get('version')) is str)
    _need(type(original.get('opening_cycles')) is dict)
    universe = {native: security(native) for native in original['opening_cycles']}
    _need(len(universe) <= 64 and len(set(universe.values())) == len(universe))
    _need(type(own.get('positions')) is list and len(own['positions']) <= len(universe))
    rows = {symbol: dict(symbol=symbol, quantity=0, sellable=0) for symbol in universe.values()}
    seen = set()
    for row in own['positions']:
        _need(type(row) is dict and row.get('symbol') in universe and row['symbol'] not in seen)
        seen.add(row['symbol']); q, sell = _quantity(row['quantity']), _quantity(row['sellable'])
        _need(sell <= q)
        rows[universe[row['symbol']]].update(quantity=q, sellable=sell)
    stamp = _time(original.get('observed_at'))
    targets = original.get('targets')
    if targets is not None:
        _need(type(targets) is dict and set(targets) == set(universe))
        targets = {universe[s]: _quantity(q) for s, q in targets.items()}
    fills = original.get('fills'); projected = None
    truncated = original.get('fills_truncated', False)
    _need(type(truncated) is bool)
    if fills is not None:
        _need(type(fills) is list and len(fills) <= 2000)
        projected = []; identities = set()
        for fill in fills:
            _need(type(fill) is dict and fill.get('symbol') in universe and fill.get('side') in ('buy', 'sell'))
            _need(type(fill.get('fill_id')) is str and 0 < len(fill['fill_id']) <= 256 and fill['fill_id'] not in identities)
            identities.add(fill['fill_id'])
            execution = _time(fill.get('executed_at'))
            day = fill['trading_day']; parsed = datetime.strptime(day, '%Y-%m-%d')
            _need(parsed.date().isoformat() == day and day <= datetime.now(timezone(timedelta(hours=8))).date().isoformat())
            if execution is not None:
                _need(datetime.fromisoformat(execution).astimezone(timezone(timedelta(hours=8))).date().isoformat() == day)
                _need(stamp is None or execution <= stamp)
            price, amount, fee = _money(fill['price_cny']), _money(fill['amount_cny']), _money(fill.get('fee_cny'), optional=True)
            _need(Decimal(price) > 0 and Decimal(amount) >= 0 and (fee is None or Decimal(fee) >= 0))
            projected.append(dict(
                id=hashlib.sha256((identity + '\0' + fill['fill_id']).encode()).hexdigest(),  # 去敏原D稳定身份，策略间隔离。
                symbol=universe[fill['symbol']],  # 原归属部分的证券。
                side=fill['side'].upper(),  # 原实际成交方向。
                quantity=_quantity(fill['quantity']),  # 原分配实际份额。
                price_cny=price,  # 原实际单价，元。
                amount_cny=amount,  # 原已记账分配金额，元。
                fee_cny=fee,  # 原实际分配费用，未知保持None。
                date=day,  # 原上海交易日。
                source_time=execution,  # 原成交clock，缺失不制造标记。
                source_sha256=_sha(fill['source_sha256'])))  # 原事实摘要，不回传订单号。
    return dict(
        strategy_version=own['version'],  # 原ASA初始化版本。
        positions=list(rows.values()),  # 自有完整证券池，零与未知分别表达。
        observed_at=stamp,  # 归属账原owner读取clock，非价格估值clock。
        book_scope_sha256=_sha(original.get('book_scope_sha256'), optional=True),  # 原账身份，旧发布可缺。
        revision=_quantity(own['revision']),  # 原ASA事务水位。
        cash_cny=_money(own['cash_cny'], optional=True),  # 原真实自有现金，未知费用时缺失。
        ledger_cash_cny=_money(own['ledger_cash_cny']),  # 已记账本金/已知费用后现金，未知费用另列。
        unknown_fee_count=_quantity(own['unknown_fee_count']),  # 原未确认费用条数。
        targets=targets,  # 原已提交目标，无意图为None。
        fills=projected,  # 仅实际D分配；旧发布未知为None。
        fills_truncated=truncated)  # 原发布的展示截断，账本保留。
