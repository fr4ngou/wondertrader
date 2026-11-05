"""从原基准、完整成交和券商P核实当前开仓来源；不维护数量或现金账本。"""
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from fractions import Fraction
from hashlib import sha256
import json
from itertools import groupby
import math
from zoneinfo import ZoneInfo


def _digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                             ensure_ascii=True, allow_nan=False).encode('ascii')).hexdigest()


def _quantity(value):
    """仅接受原现货股/份整数；double的整数表达沿原值核验。"""
    if type(value) not in (int, float) or not math.isfinite(value):
        return None
    exact = Fraction(repr(value))
    return int(exact) if exact.denominator == 1 and exact >= 0 else None


def _time(row):
    """成交日期及HHMMSSmmm均来自原行，转换上海时区后统一比较UTC。"""
    day = datetime.strptime(str(row.trade_date), '%Y%m%d')
    clock = row.trade_time
    return day.replace(hour=clock // 10000000, minute=clock // 100000 % 100,
                       second=clock // 1000 % 100, microsecond=clock % 1000 * 1000,
                       tzinfo=ZoneInfo('Asia/Shanghai')).astimezone(timezone.utc)


def queried_opening_cycle(symbol, native_symbol, initial_cycle, baseline_at,
                         current_quantity, position_received_at, cutoff, trades, check):
    """核实实际零转正或原库存持续周期，返回原周期元数据或None。

    initial_cycle为原运行输入中的证券/状态/数量/来源摘要；baseline_at为原资金
    基准的带时区ISO时刻。current_quantity始终以本次券商P为准，成交净额仅用于
    验证来源链完整一致。position_received_at与cutoff限定可见的原成交源时刻。
    trades消费原Context完整可知的查询/通知并集；check沿调用方原总截止执行。
    本函数无文件、网络、持久化、委托或持仓修改副作用。
    """
    check()
    if trades is None or not trades.known or initial_cycle is None:
        return None
    initial = asdict(initial_cycle) if is_dataclass(initial_cycle) else initial_cycle
    if (not isinstance(initial, dict) or initial.get('symbol') != symbol
            or initial.get('status') not in ('flat', 'held', 'initial_inventory')):
        return None
    running, actual = _quantity(initial.get('quantity')), _quantity(current_quantity)
    if running is None or actual is None or not actual:
        return None
    try:
        baseline = datetime.fromisoformat(baseline_at.replace('Z', '+00:00'))
        if any(value.utcoffset() is None for value in (baseline, position_received_at, cutoff)):
            return None
        latest = min(position_received_at, cutoff)
    except (TypeError, ValueError, AttributeError):
        return None
    if baseline > latest:
        return None
    rows, identities = [], set()
    for row in trades.trades:
        check()
        if row.symbol != native_symbol:
            continue
        try:
            occurred = _time(row)
        except (TypeError, ValueError, OverflowError):
            return None
        if not baseline <= occurred <= latest:
            continue
        identity = (row.trade_date, row.trade_id)
        quantity = _quantity(row.quantity)
        if identity in identities or not row.trade_id or not row.order_id or not quantity:
            return None
        identities.add(identity)
        rows.append((occurred, identity, quantity, row))
    rows.sort(key=lambda item: (item[0], item[1]))
    # 同刻混合买卖只有在任何顺序均不会触及零仓时才能核为同一周期。
    # 成交ID用于确定身份，不提供先卖后买的时间顺序证据。
    probe = running
    for occurred, group in groupby(rows, key=lambda item: item[0]):
        group = list(group)
        buys = sum(item[2] for item in group if item[3].is_buy)
        sells = sum(item[2] for item in group if not item[3].is_buy)
        if buys and sells and probe - sells <= 0:
            return None
        probe += buys - sells
    opening, facts = None, []
    for occurred, unused, quantity, row in rows:
        check()
        after = running + quantity if row.is_buy else running - quantity
        if after < 0:
            return None
        if running == 0 and after > 0:
            opening = (occurred, row)
        elif after == 0:
            opening = None
        running = after
        # 原日期、时间、编号及数值保留于摘要输入；查询行不制造live身份。
        facts.append(dict(symbol=row.symbol, trade_id=row.trade_id, order_id=row.order_id,
                          user_tag=row.user_tag, trade_date=row.trade_date, trade_time=row.trade_time,
                          is_buy=row.is_buy, quantity=row.quantity, price=row.price, amount=row.amount))
    if running != actual:
        return None
    if opening is None:
        if initial.get('status') != 'initial_inventory' or not initial.get('cycle_id'):
            return None
        # 已核事实从未卖平，沿原库存基准证明同一周期；与缺事实的None明确区分。
        origin = initial.get('baseline_at') or baseline_at
        if isinstance(origin, datetime):
            origin = origin.isoformat()
        return dict(status='initial_inventory', cycle_id=initial['cycle_id'],
                    baseline_at=origin, source_sha256=initial['source_sha256'])
    # 完整券商成交查询可以缺WT附属标签；本入口的归属来自唯一策略及原固定账户基准。
    # 实际买入时刻、逐笔身份和数量链均已核实；保留原空标签，不伪造live或策略标记。
    occurred, row = opening
    anchor = dict(symbol=symbol, baseline_at=baseline_at,
                  initial_cycle={key: initial[key] for key in ('symbol', 'status', 'quantity', 'source_sha256')})
    identity = dict(opened_at=occurred.isoformat())  # 同刻后续部分成交不改变周期；逐笔身份保留在facts中。
    return dict(
        cycle_id='broker-open:' + _digest((anchor, identity)),  # 基准与真实零转正买入共同定位，重查不换周期。
        opened_at=occurred.isoformat(),  # 原真实买入成交源时刻，UTC；不采用查询或重启时刻。
        source_sha256=_digest(dict(schema='guanheng.queried-opening-source.v1', anchor=anchor,
                                  facts=facts, current_quantity=actual)))  # 原事实链与本次P的一致性证明。
