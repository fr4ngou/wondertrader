"""原券商历史成交覆盖；只向唯一策略提供经核实的周期来源。"""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
import math
from pathlib import Path
import time as monotonic_time
from zoneinfo import ZoneInfo

from .execution_cycle_source import _digest, _quantity, _time
from .execution_strategy import BrokerTradeValue
from .managed_local_process import _json, _read, _require, _sha


SCHEMA = 'guanheng.closed-broker-deals.v1'
FILE_NAME = 'broker-deal-history.json'
SHANGHAI = ZoneInfo('Asia/Shanghai')
_FIELDS = {'schema', 'scope', 'first_day', 'last_day', 'received_at',
           'export_sha256', 'observation_sha256', 'coverage_sha256', 'rows', 'sha256'}


def scope_for(native, input_sha):
    """固定账户、交易绑定及原策略输入身份；路径/进程代不参与。"""
    trader = native['trader']
    return _digest({key: trader[key] for key in
                    ('expected_account', 'environment', 'profile', 'binding_id', 'binding_sha256',
                     'instance_id')} | {'input_sha256': input_sha})


def _market_fact(row):
    """重复成交比较券商经济事实；本地标签、接收时刻和通知修订可各自保留。"""
    return (row.symbol, row.trade_date, row.trade_time, row.trade_id, row.order_id,
            row.is_buy, row.quantity, row.price, row.amount)


def _key(row):
    return row.trade_date, row.trade_id


def _stamp(value):
    stamp = datetime.fromisoformat(value)
    _require(stamp.utcoffset() is not None)
    return stamp


@dataclass(frozen=True)
class CycleTrades:
    """仅用于 R22 的成交集合；不声明 Native 查询修订或实时通知水位。"""
    trades: tuple[BrokerTradeValue, ...]  # 已按成交身份去重的历史和当前原成交。
    known: bool = True  # 仅由历史覆盖与当前来源联合核验后构造。


@dataclass(frozen=True)
class ClosedDealHistory:
    """已闭合的同账户历史成交及查询覆盖日期。"""
    first_day: date  # 券商查询范围首个上海自然日，含该日。
    last_day: date  # 已闭合且在券商查询范围内的最后上海自然日，含该日。
    received_at: datetime  # 完整历史原件的实际取得时刻，带时区。
    source_sha256: str  # 材料规范内容摘要，含两项原件摘要和逐笔记录。
    rows: tuple[BrokerTradeValue, ...]  # 原 R21 逐笔记录，保留其真实时点和身份。

    @classmethod
    def from_dict(cls, value, scope, baseline_at):
        _require(type(value) is dict and set(value) == _FIELDS and value['schema'] == SCHEMA
                 and _sha(value['scope']) == scope)
        for name in ('export_sha256', 'observation_sha256', 'coverage_sha256', 'sha256'):
            _sha(value[name])
        _require(value['sha256'] == _digest({key: item for key, item in value.items() if key != 'sha256'}))
        first, last = (date.fromisoformat(value[name]) for name in ('first_day', 'last_day'))
        received = _stamp(value['received_at'])
        baseline_day = _stamp(baseline_at).astimezone(SHANGHAI).date()
        _require(first <= baseline_day <= last and datetime.combine(last, time(15), SHANGHAI) <= received)
        records = value['rows']
        _require(type(records) is list)
        rows = []
        seen = set()
        for value_row in records:
            _require(type(value_row) is dict and value_row.keys() == BrokerTradeValue.__dataclass_fields__.keys())
            row = BrokerTradeValue(**value_row)
            _require(type(row.is_buy) is bool and type(row.trade_date) is int and type(row.trade_time) is int
                     and _quantity(row.quantity) and type(row.price) in (int, float)
                     and math.isfinite(row.price) and row.price > 0 and type(row.amount) in (int, float)
                     and math.isfinite(row.amount) and row.amount >= 0)
            _require(all(type(s) is str and 0 < len(s) < 64 and s.isascii()
                         for s in (row.symbol, row.trade_id, row.order_id))
                     and type(row.user_tag) is str and row.user_tag.isascii())
            _require(first <= _time(row).astimezone(SHANGHAI).date() <= last and _key(row) not in seen)
            seen.add(_key(row))
            rows.append(row)
        return cls(first, last, received, value['sha256'], tuple(rows))

    @classmethod
    def load(cls, native, input_sha, baseline_at, deadline):
        path = Path(native['output_directory'])/FILE_NAME
        try:
            raw = _read(path, 4*1024*1024, clock=monotonic_time.monotonic, deadline=deadline)
        except FileNotFoundError:
            return None
        return cls.from_dict(_json(raw), scope_for(native, input_sha), baseline_at)

    def join(self, current, current_observed_at, position_at, cutoff, check):
        """拒绝覆盖缺口及历史冲突；只在同一上海日拼接当前完整券商查询。"""
        check()
        day = cutoff.astimezone(SHANGHAI).date()
        if (self.received_at > cutoff or day > self.last_day + timedelta(days=1)
                or position_at.astimezone(SHANGHAI).date() != day
                or current_observed_at is None or current_observed_at.astimezone(SHANGHAI).date() != day
                or not position_at <= current_observed_at <= cutoff):
            return None
        merged = {_key(row): row for row in self.rows}
        for row in current:
            check()
            key = _key(row)
            previous = merged.get(key)
            if previous is not None:
                if _market_fact(previous) != _market_fact(row):
                    return None
            elif self.first_day <= _time(row).astimezone(SHANGHAI).date() <= self.last_day:
                return None
            else:
                merged[key] = row
        return CycleTrades(tuple(merged.values()))

    def source(self):
        """公开覆盖及摘要供当前决策诊断；逐笔金融明细留原受控材料。"""
        return dict(first_day=self.first_day.isoformat(), last_day=self.last_day.isoformat(),
                    source_sha256=self.source_sha256)
