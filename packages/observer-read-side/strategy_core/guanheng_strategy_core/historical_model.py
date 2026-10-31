"""事后历史快照的显式回测假设；实际可知资格仍由严格入口验证。"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
import re

from .contracts import KernelValidationError, _strict_fields, _timestamp, json_value, utc_timestamp


@dataclass(frozen=True)
class HistoricalEodModel:
    """绑定完整批次的回测条件，received_at是本次实际收到该批的时间。

    amount保留原数值，CNY只属于模型解释；历史首次可知和修订保持未知。
    本值没有运行或交易权限，消费者必须显式调用回测库函数。
    """
    dataset_sha256: str
    received_at: datetime
    source_amount_unit: str
    amount_interpretation: str
    availability_basis: str
    model_close: str
    historical_first_available: str
    revision_history: str
    schema: str = "guanheng.historical-eod-model.v1"

    def __post_init__(self):
        expected = {
            "schema": "guanheng.historical-eod-model.v1",
            "source_amount_unit": "unknown", "amount_interpretation": "assumed-CNY",
            "availability_basis": "assumed-at-model-close", "model_close": "Asia/Shanghai:15:00",
            "historical_first_available": "unknown", "revision_history": "unknown",
        }
        if (type(self.dataset_sha256) is not str
                or re.fullmatch(r"[0-9a-f]{64}", self.dataset_sha256) is None
                or any(type(getattr(self, key)) is not str or getattr(self, key) != value
                       for key, value in expected.items())):
            raise KernelValidationError("invalid_historical_model", "历史回测模型需要明确批次身份及固定假设")
        utc_timestamp(self.received_at)

    @classmethod
    def from_dict(cls, value):
        data = _strict_fields(cls, value)
        data["received_at"] = _timestamp(data.get("received_at"))
        try:
            return cls(**data)
        except TypeError as exc:
            raise KernelValidationError("invalid_historical_model", "历史回测模型缺少必要事实或假设") from exc

    def to_dict(self):
        return json_value(self)

    def validated_copy(self):
        """公开消费边界重验全部固定字段，并与调用方typed对象断开引用。"""
        if type(self) is not HistoricalEodModel:
            raise KernelValidationError("invalid_historical_model", "历史回测输入需要明确模型类型")
        return replace(self)


HISTORICAL_REASON = "事后最终日线的日末回测假设；金额按CNY假设，历史首次可知和修订未知，未取得实时或交易资格"
HISTORICAL_SCOPE = "historical-eod-backtest-only; historical-first-availability/revisions/RT/broker/production-unqualified"
HISTORICAL_REPORT_SCHEMA = "nsb-historical-report-v1"
