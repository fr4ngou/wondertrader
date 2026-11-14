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

    def _decode(self, raw):
        value = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_invalid_constant)
        if type(value) is not dict or value.get('schema') != self.schema:
            raise ValueError('strategy_state_schema')
        return value

    def read(self, context, *, key=None):
        """从当前策略专属的原 WT 用户变量读取；沿回调门面核线程与生命周期。"""
        raw = context.load_quantity_state() if key is None else context.load_userdata(key)
        if not raw:
            return StrategyStateRevision(None, None)
        return StrategyStateRevision(self._decode(raw), hashlib.sha256(raw.encode('ascii')).hexdigest())

    def commit(self, context, expected_revision, value, *, key=None):
        """校验预期版本后发布整组业务键，按规范字节判断相等。"""
        raw = _encode(value)
        proposed = self._decode(raw)
        previous = self.read(context, key=key)
        if previous.revision != expected_revision:
            raise StrategyStateConflict('strategy_state_revision')
        if previous.value is not None:
            before = {key: item for key, item in previous.value.items() if key not in self.transient_keys}
            after = {key: item for key, item in proposed.items() if key not in self.transient_keys}
            if _encode(before) == _encode(after):
                return previous
        if key is None:
            context.store_quantity_state(raw)
        else:
            context.store_userdata(key, raw)
        return StrategyStateRevision(proposed, hashlib.sha256(raw.encode('ascii')).hexdigest())
