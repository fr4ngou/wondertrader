"""最终前复权批次的显式回测假设；实际来源和接收时间保持原值。"""
from dataclasses import dataclass, fields, MISSING
from datetime import date, datetime
import re

from guanheng_strategy_core.contracts import KernelValidationError, utc_timestamp
from guanheng_strategy_core.models import observation_close_at


@dataclass(frozen=True, slots=True)
class RetainedHistoricalModel:
    dataset_sha256: str
    factor_sha256: str
    basis_date: date
    received_at: datetime
    schema: str = 'guanheng.retained-historical-model.v1'
    availability_basis: str = 'assumed-at-Asia/Shanghai:15:00'
    adjustment_basis: str = 'final-batch-front-ratio'
    historical_first_available: str = 'unknown'
    revision_history: str = 'unknown'
    scope: str = 'historical-backtest-only'

    @classmethod
    def from_dict(cls, value):
        declared = fields(cls)
        required = {f.name for f in declared if f.default is MISSING}
        if (cls is not RetainedHistoricalModel or type(value) is not dict
                or not required <= set(value) <= {f.name for f in declared}):
            raise ValueError('历史模型字段与固定协议不一致')
        data = dict(value)
        try:
            if type(data['basis_date']) is not str or len(data['basis_date']) != 10:
                raise ValueError()
            if type(data['received_at']) is not str or len(data['received_at']) > 64:
                raise ValueError()
            data['basis_date'] = date.fromisoformat(data['basis_date'])
            data['received_at'] = datetime.fromisoformat(data['received_at'].replace('Z', '+00:00'))
            return cls(**data)
        except (KeyError, TypeError, ValueError, OverflowError):
            raise ValueError('历史模型字段或时间格式无效') from None

    def __post_init__(self):
        expected = ('guanheng.retained-historical-model.v1', 'assumed-at-Asia/Shanghai:15:00',
            'final-batch-front-ratio', 'unknown', 'unknown', 'historical-backtest-only')
        if (any(type(v) is not str or re.fullmatch('[0-9a-f]{64}', v) is None
                for v in (self.dataset_sha256, self.factor_sha256))
                or type(self.basis_date) is not date
                or any(type(v) is not str for v in (self.schema, self.availability_basis, self.adjustment_basis,
                    self.historical_first_available, self.revision_history, self.scope))
                or (self.schema, self.availability_basis, self.adjustment_basis,
                    self.historical_first_available, self.revision_history, self.scope) != expected):
            raise ValueError('历史模型需要完整批次身份和固定回测假设')
        try:
            object.__setattr__(self, 'received_at', utc_timestamp(self.received_at))
            if observation_close_at(self.basis_date) > self.received_at:
                raise ValueError('实际接收时间尚未覆盖最终分析基准日')
        except KernelValidationError:
            raise ValueError('历史批次需要明确实际接收时间') from None
