"""最终前复权批次的显式回测假设；实际来源和接收时间保持原值。"""
from dataclasses import dataclass, field, fields, MISSING, asdict, replace
from datetime import date, datetime
from hashlib import sha256
import json
import re

from guanheng_strategy_core.contracts import KernelValidationError, utc_timestamp, canonical_bytes
from guanheng_strategy_core.models import observation_close_at
from .role_profile import STRATEGY_ID, STRATEGY_VERSION

AUXILIARY_RESEARCH_MODEL = 'research-next-common-session-0925-v1'
AUXILIARY_RESEARCH_MARKER = 'auxiliary-research:'+AUXILIARY_RESEARCH_MODEL


@dataclass(frozen=True, slots=True)
class AuxiliaryResearchDeclaration:
    """历史辅助研究假设的不可变声明；保留实际取得时钟，禁止作为实时知晓证明。"""
    schema: str  # 声明协议，固定guanheng.auxiliary-research-declaration.v1。
    model: str  # 显式下一共同交易日09:25假设；默认实时入口没有该模型。
    evidence_marker: str  # 每行研究输入的标记，供实时入口拒绝并核历史模型。
    data_sha256: str  # 原市场窗口完整字节身份，由外部组装者核原件。
    derivation: str  # 唯一原派生公式版本，不增加另一份信号数学。
    derivation_sha256: str  # 实际产生派生事实的模块字节SHA，区别于运行包版本。
    strategy_id: str  # 本次研究消费的唯一策略标识。
    strategy_version: str  # 本次实际角色/策略版本，不把旧ETF移作新角色历史。
    publications_sha256: str  # 全部统计值、原文、实际/假设时钟清单的身份。
    actual_first_received_at: str  # 辅助原件最早真实取得时刻，ISO带时区，保留原编码以核摘要。
    actual_last_received_at: str  # 辅助原件最晚真实取得时刻；不改写为历史09:25。
    historical_first_available: str  # 固定unknown；假设不证明历史首次可知。
    modeled_publications: int  # 参与研究的来源发布件数，不表示完整市场覆盖。
    historical_causal_qualified: bool  # 固定False，保持历史因果实证资格未知。
    realtime_qualified: bool  # 固定False，研究输入不进入实时。
    declaration_sha256: str  # 此字段之外全部声明的sort-keys紧凑UTF8 JSON摘要。

    @classmethod
    def from_dict(cls, value):
        if type(value) is not dict or set(value) != {f.name for f in fields(cls)}:
            raise ValueError('辅助研究声明字段无效')
        return cls(**value)

    def __post_init__(self):
        value = asdict(self)
        digest = value.pop('declaration_sha256')
        if (any(type(getattr(self, key)) is not str or re.fullmatch('[0-9a-f]{64}', getattr(self, key)) is None
                for key in ('data_sha256', 'derivation_sha256', 'publications_sha256', 'declaration_sha256'))
                or (self.schema, self.model, self.evidence_marker, self.derivation, self.strategy_id,
                    self.strategy_version, self.historical_first_available) != (
                    'guanheng.auxiliary-research-declaration.v1', AUXILIARY_RESEARCH_MODEL,
                    AUXILIARY_RESEARCH_MARKER, 'resonance-auxiliary-causal-v3', STRATEGY_ID, STRATEGY_VERSION, 'unknown')
                or self.historical_causal_qualified is not False or self.realtime_qualified is not False
                or type(self.modeled_publications) is not int or not 1 <= self.modeled_publications <= 65536
                or sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                    separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest() != digest):
            raise ValueError('辅助研究声明身份或范围无效')
        times = []
        for text in (self.actual_first_received_at, self.actual_last_received_at):
            if type(text) is not str or len(text) > 64:
                raise ValueError('研究声明需要真实带时区取得时钟')
            times.append(utc_timestamp(datetime.fromisoformat(text.replace('Z', '+00:00'))))
        if times[0] > times[1]:
            raise ValueError('辅助实际取得时钟失序')


@dataclass(frozen=True, slots=True)
class RetainedHistoricalModel:
    dataset_sha256: str  # 实际最终市场批次身份。
    factor_sha256: str  # 同一前复权因子批次身份。
    basis_date: date  # 最终分析基准的市场日期。
    received_at: datetime  # 市场批次真实接收时刻，归一UTC，区别于研究假设。
    schema: str = 'guanheng.retained-historical-model.v1'  # 原模型协议，旧报告编码保持。
    availability_basis: str = 'assumed-at-Asia/Shanghai:15:00'  # 原市场历史日末假设，辅助假设单列。
    adjustment_basis: str = 'final-batch-front-ratio'  # 保留最终批次前复权假设。
    historical_first_available: str = 'unknown'  # 原市场首次可知未知。
    revision_history: str = 'unknown'  # 原修订历史未知。
    scope: str = 'historical-backtest-only'  # 模型限原生历史回测。
    auxiliary_research: AuxiliaryResearchDeclaration | None = field(default=None, metadata={'omit_none': True})  # 显式研究声明，默认关闭且旧编码省略。
    auxiliary_input_sha256: str | None = field(default=None, metadata={'omit_none': True})  # 实际研究合并后的FrozenHistory摘要，绑定全部行和因果标记。

    def with_auxiliary_research(self, history, declaration):
        """操作员显式选择研究；原数据、真实接收时间及原市场模型保持。"""
        return replace(self, auxiliary_research=AuxiliaryResearchDeclaration.from_dict(declaration),
                       auxiliary_input_sha256=sha256(canonical_bytes(history)).hexdigest())

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
            if data.get('auxiliary_research') is not None:
                data['auxiliary_research'] = AuxiliaryResearchDeclaration.from_dict(data['auxiliary_research'])
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
        if self.auxiliary_research is None:
            if self.auxiliary_input_sha256 is not None:
                raise ValueError('研究输入摘要需要显式研究声明')
        elif (type(self.auxiliary_research) is not AuxiliaryResearchDeclaration
                or type(self.auxiliary_input_sha256) is not str
                or re.fullmatch('[0-9a-f]{64}', self.auxiliary_input_sha256) is None):
            raise ValueError('显式研究模型需要不可变声明及完整输入摘要')
