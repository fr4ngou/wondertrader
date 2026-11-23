"""受管策略恢复记录。通过原回调借用上下文读写，不拥有券商或资金状态。"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json


class StrategyStateConflict(ValueError):
    """回调读到的版本已被另一次提交推进。"""


@dataclass(frozen=True)
class StrategyStateRevision:
    value: dict | None  # 独立解码的记录；None表示原存储为空。
    revision: str | None  # 原编码摘要；None表示从未写入。


@dataclass(frozen=True)
class StrategyStateWrite:
    key: str  # 策略实例内的记录键。
    expected_revision: str | None  # 读取的账本版本，None 表示该键尚未建立。
    value: str  # 原策略规范 ASCII 编码的一组业务字段。


def _pairs(items):
    fields = {}
    for key, value in items:
        if key in fields:
            raise ValueError('strategy_state_duplicate_key')
        fields[key] = value
    return fields


def _invalid_constant(_):
    raise ValueError('strategy_state_invalid_number')


def _encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)


@dataclass(frozen=True)
class StrategyStateRecord:
    """策略声明的可恢复 JSON 记录。当前 ABI 将一组业务键写入同一用户变量。"""
    schema: str  # 唯一协议及版本；更早版本须由策略显式迁移。
    transient_keys: frozenset[str] = frozenset()  # 可重建且单独变化时无需持久化的字段。

    def model_identity(self, model):
        """按状态协议及业务模型生成兼容身份；部署源码真实性由宿主绑定负责。

        model须由策略提供完整业务参数及算法契约版本。安装路径、程序源码摘要和
        初始化代号属于部署证据，变化时不应改写已经接受的业务状态。
        """
        raw = _encode(dict(contract='guanheng.strategy-state-model.v1', schema=self.schema, model=model))
        return hashlib.sha256(raw.encode('ascii')).hexdigest()

    def _decode(self, raw):
        value = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_invalid_constant)
        if type(value) is not dict or value.get('schema') != self.schema:
            raise ValueError('strategy_state_schema')
        return value

    def read(self, context, *, key=None):
        """从当前策略专属的原 WT 用户变量读取；沿回调门面核线程与生命周期。"""
        raw = context.load_quantity_state() if key is None else context.load_userdata(key)
        return self.decode(raw)

    def decode(self, raw):
        if not raw:
            return StrategyStateRevision(None, None)
        return StrategyStateRevision(self._decode(raw), hashlib.sha256(raw.encode('ascii')).hexdigest())

    def stage(self, previous, value):
        """保留现有序列化，过滤单独变化的观察字段，生成一次比较写入。"""
        raw = _encode(value)
        proposed = self.decode(raw)
        if previous.value is not None:
            before = {key: item for key, item in previous.value.items() if key not in self.transient_keys}
            after = {key: item for key, item in value.items() if key not in self.transient_keys}
            if _encode(before) == _encode(after):
                return previous, None
        return proposed, StrategyStateWrite(self.schema, previous.revision, raw)

    def commit(self, context, expected_revision, value, *, key=None):
        """校验预期版本后发布整组业务键，按规范字节判断相等。"""
        previous = self.read(context, key=key)
        if previous.revision != expected_revision:
            raise StrategyStateConflict('strategy_state_revision')
        proposed, update = self.stage(previous, value)
        if update is not None:
            if key is None:
                context.store_quantity_state(update.value)
            else:
                context.store_userdata(key, update.value)
        return proposed


class SharedStrategyState:
    """共享账户状态槽，首次从已验证的原用户变量迁入。账本提交后更新兼容副本。"""
    def __init__(self, record, allocation, strategy_id):
        self.record = record
        self.allocation = allocation
        self.strategy_id = strategy_id
        self.current = StrategyStateRevision(None, None)  # 本策略已接受的账本版本。
        self._mirrored_revision = None  # 同一 CTA 的兼容用户变量已同步的业务版本。

    def restore(self, *, deadline):
        raw = self.allocation.load_strategy_state(self.strategy_id, self.record.schema, deadline=deadline)
        self.current = self.record.decode(raw)
        return raw

    def stage(self, value):
        return self.record.stage(self.current, value)

    def for_target(self, staged):
        revision, update = staged
        return update or StrategyStateWrite(self.record.schema, revision.revision, _encode(revision.value))

    def restore_target(self, context, *, deadline):
        """用原目标身份重新交给 WT 合并；首次迁入且没有绑定目标时走原初始化。"""
        target = self.allocation.restore_strategy_target(self.strategy_id, self.record.schema, deadline=deadline)
        if target is None:
            return False
        caps = {row.symbol: row.buy_price_cap_cny for row in target.targets if row.buy_price_cap_cny is not None}
        self.allocation.prepare_intent(self.strategy_id, context.event.epoch, source_sha256=target.source_sha256,
            known_at=target.known_at, buy_price_caps=caps, common_prices=(), recovery_target=target.intent_id,
            deadline=deadline)
        vector = tuple((row.symbol, row.quantity) for row in target.targets)
        if dict(context.set_targets(vector)) != dict(vector):
            raise ValueError('strategy_recovery_target_readback')
        return True

    def accept(self, context, staged, *, target_committed=False, deadline):
        revision, update = staged
        if update is not None:
            if not target_committed:
                self.allocation.commit_strategy_state(self.strategy_id, update, deadline=deadline)
            self.current = revision
        if revision.revision != self._mirrored_revision:
            raw = _encode(revision.value)
            if context.load_quantity_state() != raw:
                context.store_quantity_state(raw)
            self._mirrored_revision = revision.revision
