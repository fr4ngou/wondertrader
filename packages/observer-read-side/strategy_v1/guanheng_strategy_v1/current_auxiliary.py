"""当前决策辅助事实；完整历史逐帧可知规则继续由原历史模型负责。"""
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timezone
from hashlib import sha256
import json
from math import isfinite
from zoneinfo import ZoneInfo

from guanheng_strategy_core.models import DailyObservation, DailyFeature
from .auxiliary import DERIVATION_VERSION, _Value, _derived, _effective, _validate
from .role_profile import SYMBOLS

SCHEMA = 'guanheng.current-auxiliary-view.v1'
FIELDS = ('shares_delta_yi', 'share_probability', 'turnover_percentile', 'margin_percentile')


def _need(value):
    if not value:
        raise ValueError('invalid_current_auxiliary')


def _digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _hash(value):
    return type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


@dataclass(frozen=True, slots=True)
class CurrentAuxiliaryValue:
    symbol: str  # 实际ETF证券；不以其他基金来源替换本证券。
    field: str  # 四个原公式字段之一；份额单位亿份，其余为0..100刻度。
    value: float  # 原唯一派生函数的有限数值，净份额允许负值和零。
    statistic_date: date  # 最新来源统计日，区别于行情基准日和当前决策日。
    known_by: datetime  # 全部依赖真实接收时间的最大值，带时区，禁止回填历史。
    source_dates: tuple[date, ...]  # 完整依赖统计日期，最多64个真实交易日。
    sources: tuple[str, ...]  # 完整依赖来源SHA256集合，最多64个原文/组合摘要。

    def to_dict(self):
        _need(type(self) is CurrentAuxiliaryValue and type(self.symbol) is str and self.symbol in SYMBOLS
            and type(self.field) is str and self.field in FIELDS)
        _need(type(self.value) in (int, float) and isfinite(self.value)
            and (self.field == 'shares_delta_yi' or 0 <= self.value <= 100))
        _need(type(self.statistic_date) is date and type(self.known_by) is datetime
            and self.known_by.utcoffset() is not None
            and self.known_by.astimezone(ZoneInfo('Asia/Shanghai')).date() >= self.statistic_date)
        _need(type(self.source_dates) is tuple and 1 <= len(self.source_dates) <= 64
            and all(type(d) is date for d in self.source_dates)
            and tuple(sorted(set(self.source_dates))) == self.source_dates
            and self.source_dates[-1] == self.statistic_date)
        minimum, maximum = ((2, 2) if self.field in ('shares_delta_yi', 'share_probability') else
                            (20, 60) if self.field == 'margin_percentile' else (20, 64))
        _need(minimum <= len(self.source_dates) <= maximum)
        _need(type(self.sources) is tuple and 1 <= len(self.sources) <= 64
            and all(_hash(s) for s in self.sources) and tuple(sorted(set(self.sources))) == self.sources)
        return dict(symbol=self.symbol, field=self.field, value=self.value,
            statistic_date=self.statistic_date.isoformat(), known_by=self.known_by.astimezone(timezone.utc).isoformat(),
            source_dates=[d.isoformat() for d in self.source_dates], sources=list(self.sources))

    @classmethod
    def from_dict(cls, value):
        _need(type(value) is dict and set(value) == {'symbol','field','value','statistic_date','known_by','source_dates','sources'})
        _need(type(value['statistic_date']) is str and len(value['statistic_date']) == 10
            and type(value['known_by']) is str and len(value['known_by']) <= 64
            and type(value['source_dates']) is list and 1 <= len(value['source_dates']) <= 64
            and type(value['sources']) is list and 1 <= len(value['sources']) <= 64)
        _need(all(type(d) is str and len(d) == 10 for d in value['source_dates'])
            and all(_hash(digest) for digest in value['sources']))
        result = cls(value['symbol'], value['field'], value['value'], date.fromisoformat(value['statistic_date']),
            datetime.fromisoformat(value['known_by']), tuple(date.fromisoformat(d) for d in value['source_dates']), tuple(value['sources']))
        result.to_dict()
        return result


@dataclass(frozen=True, slots=True)
class CurrentAuxiliaryView:
    basis_date: date  # 最近真实闭合行情基准日；本对象不生成当日/未来行情。
    derivation_version: str  # 原辅助派生版本；公式、阈值及来源口径有唯一所有者。
    values: tuple[CurrentAuxiliaryValue, ...]  # 按实际证券/字段排序的最新事实，最多8×4项。
    schema: str = SCHEMA  # 当前辅助视图协议；与历史行和研究模型明确分开。
    sha256: str = field(init=False)  # 只含实际数据和行情基准的规范摘要，不含轮询/求值时间。

    def __post_init__(self):
        object.__setattr__(self, 'sha256', _digest(self._body()))

    def _body(self):
        _need(type(self) is CurrentAuxiliaryView and type(self.basis_date) is date
            and type(self.derivation_version) is str and self.derivation_version == DERIVATION_VERSION
            and type(self.schema) is str and self.schema == SCHEMA)
        _need(type(self.values) is tuple and len(self.values) <= 32
            and all(type(v) is CurrentAuxiliaryValue for v in self.values))
        values = [v.to_dict() for v in self.values]
        keys = [(v.symbol, v.field) for v in self.values]
        _need(keys == sorted(set(keys)) and all(v.statistic_date <= self.basis_date for v in self.values))
        return dict(schema=self.schema, basis_date=self.basis_date.isoformat(),
            derivation_version=self.derivation_version, values=values)

    def to_dict(self):
        body = self._body()
        _need(self.sha256 == _digest(body))
        return dict(body, sha256=self.sha256)

    @classmethod
    def from_dict(cls, value):
        _need(type(value) is dict and set(value) == {'schema','basis_date','derivation_version','values','sha256'}
            and type(value['basis_date']) is str and len(value['basis_date']) == 10
            and type(value['values']) is list and len(value['values']) <= 32 and _hash(value['sha256']))
        result = cls(date.fromisoformat(value['basis_date']), value['derivation_version'],
            tuple(CurrentAuxiliaryValue.from_dict(v) for v in value['values']), value['schema'])
        _need(result.sha256 == value['sha256'])
        return result

    def qualify(self, basis_date, decision_cutoff, market_dates=None):
        """原发布者已冻结最新事实；未来可知、错基准整体拒绝，不静默换旧值。"""
        self.to_dict()
        _need(self.basis_date == basis_date and type(decision_cutoff) is datetime
            and decision_cutoff.utcoffset() is not None)
        _need(all(v.known_by <= decision_cutoff for v in self.values))
        if market_dates is not None:
            days = set(market_dates)
            _need(all(set(v.source_dates) <= days for v in self.values))
            ordered = {day: index for index, day in enumerate(sorted(days))}
            _need(all(ordered[v.source_dates[1]] == ordered[v.source_dates[0]] + 1
                      for v in self.values if v.field in ('shares_delta_yi', 'share_probability')))
        return self

    def projected_values(self, market_dates):
        """沿原首次生效日资格；已在更早历史帧生效的值不向新末bar携带。"""
        days = sorted(set(market_dates))
        _need(bool(days) and days[-1] == self.basis_date)
        result = []
        for value in self.values:
            original = _Value(value.statistic_date, value.known_by, value.value, value.source_dates, value.sources)
            effective = _effective((original,), days)
            if not effective or self.basis_date in effective:
                result.append(value)
        return tuple(result)


def build_current_auxiliary(publications, market_dates):
    """复用完整前缀的唯一派生；无网络、无未来行情、无历史事实改写。"""
    days = sorted(set(market_dates))
    _need(bool(days) and len(days) <= 4096 and all(type(d) is date for d in days))
    publications = tuple(publications)
    _validate(publications, set(SYMBOLS))
    values = []
    for (symbol, field), items in sorted(_derived(publications, days).items()):
        eligible = [item for item in items if item.statistic_date <= days[-1]]
        if eligible:
            item = max(eligible, key=lambda v: v.statistic_date)
            values.append(CurrentAuxiliaryValue(symbol, field, item.value, item.statistic_date,
                item.available_at, item.source_dates, item.sources))
    result = CurrentAuxiliaryView(days[-1], DERIVATION_VERSION, tuple(values))
    result.to_dict()
    return result


@dataclass(frozen=True, slots=True)
class CurrentDecisionObservation:
    market: DailyObservation  # 已通过原历史校验的真实基准bar，只读保留原日期和价格。
    values: tuple[CurrentAuxiliaryValue, ...]  # 当前决策已准入的本证券事实，不进入历史重放帧。
    identity: str  # 当前完整辅助视图的稳定数据摘要，作为当前决定的来源证据。

    def __getattr__(self, name):
        if name in FIELDS:
            return next((v.value for v in self.values if v.field == name), getattr(self.market, name))
        if name == 'auxiliary_available_at':
            return max((v.known_by for v in self.values), default=self.market.auxiliary_available_at)
        if name == 'evidence_refs':
            return self.market.evidence_refs + ('current-auxiliary:' + self.identity,)
        return getattr(self.market, name)


def project_current_features(series, view):
    """仅末端当前信号视图引用实际bar；历史DailyObservation不复制/改写辅助值。"""
    projected = {}
    eligible = view.projected_values({f.observation.trade_date for items in series.values() for f in items})
    for symbol, items in series.items():
        current = [v for v in eligible if v.symbol == symbol]
        projected[symbol] = list(items)
        if current:
            last = items[-1]
            projected[symbol][-1] = replace(last,
                observation=CurrentDecisionObservation(last.observation, tuple(current), view.sha256))
    return projected
