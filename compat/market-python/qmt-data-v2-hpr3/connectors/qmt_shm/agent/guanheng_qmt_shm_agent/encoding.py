# -*- coding: utf-8 -*-
"""Bounded, explicit JSON conversion for QMT and data-science values."""

from __future__ import print_function

import json
import math
from datetime import date, datetime, time
from decimal import Decimal
from uuid import UUID

from .errors import GatewayError, SafeJSONError


class ConversionBudget(object):
    """Optional aggregate conversion cap, independent of per-container limits.

    max_nodes counts all values and keys; max_scalar_chars counts str characters
    or raw bytes across the whole result. Both are positive deployment budgets,
    normally derived from max_result_bytes by the restricted read owner. Unicode
    occupies at most four UTF-8 bytes per character. This bounds intermediate
    copies before the exact encoded-byte check; native SDK allocation itself
    remains owned by that SDK. A new budget is required for every conversion.
    """
    def __init__(self, max_nodes, max_scalar_chars):
        if (type(max_nodes) is not int or max_nodes < 1
                or type(max_scalar_chars) is not int or max_scalar_chars < 1):
            raise ValueError("aggregate conversion budgets must be positive integers")
        self.nodes, self.scalar_chars = max_nodes, max_scalar_chars

    @staticmethod
    def _overflow():
        raise GatewayError("result_too_large", "读取结果超过受管转换容量", 413)

    def consume(self, value):
        self.nodes -= 1
        if isinstance(value, (str, bytes)):
            self.scalar_chars -= len(value)
        if (self.nodes < 0 or self.scalar_chars < 0
                or isinstance(value, int) and not -(2 ** 63) <= value < 2 ** 64):
            self._overflow()

    def check_shape(self, value):
        # Data-science conversion must not materialize an enormous list/dict
        # before the recursive converter gets its first chance to reject it.
        size = 1
        for dimension in value.shape:
            size *= int(dimension)
        if size > self.nodes or getattr(value, "nbytes", 0) > self.scalar_chars * 4:
            self._overflow()


QMT_PUBLIC_FIELDS = (
    "m_strInstrumentID",
    "m_strExchangeID",
    "m_strInstrumentName",
    "m_strStockHolder",
    "m_strOrderSysID",
    "m_strOrderID",
    "m_nDirection",
    "m_nVolume",
    "m_nVolumeTotal",
    "m_nVolumeTraded",
    "m_nOrderStatus",
    "m_nFrozenVolume",
    "m_nCanUseVolume",
    "m_nOnRoadVolume",
    "m_nYesterdayVolume",
    "m_dAvgPrice",
    "m_dOpenPrice",
    "m_dPositionProfit",
    "m_dFloatProfit",
    "m_dMarketValue",
    "m_dLastPrice",
    "m_dProfitRate",
    "m_dBalance",
    "m_dAvailable",
    "m_dCommission",
    "m_eFutureTradeType",
    "m_strExpireDate",
    # 显式保留来源身份、原始量价和源时间；缺失仍省略，不在此推导账户事实。
    # m_nVolumeTotal 是剩余量，不能替代最初数量；股票买卖由 m_nOffsetFlag 区分。
    "m_strAccountID",
    "m_strTradingDate",
    "m_strTradingDay",
    "m_strMoneyType",
    "m_nOrderID",
    "m_strOrderRef",
    "m_strTradeID",
    "m_strDealID",
    "m_nOffsetFlag",
    "m_nBuySell",
    "m_nVolumeTotalOriginal",
    "m_nOrderVolume",
    "m_nTradedVolume",
    "m_dCancelAmount",
    "m_nOrderSubmitStatus",
    "m_dLimitPrice",
    "m_dPrice",
    "m_dTradedPrice",
    "m_dTradeAmount",
    "m_strInsertDate",
    "m_strInsertTime",
    "m_strTradeDate",
    "m_strTradeTime",
    "m_dFrozenCash",
    "m_dFrozenMargin",
    "m_dFrozenCommission",
    "m_dPreBalance",
    "m_dInstrumentValue",
    "m_dTotalAsset",
    "m_dDynamicEquity",
    "m_dComission",
    "m_dComssion",
)


def _is_dataframe(value):
    value_type = type(value)
    return value_type.__name__ == "DataFrame" and value_type.__module__.startswith("pandas")


def _is_series(value):
    value_type = type(value)
    return value_type.__name__ in ("Series", "Index") and value_type.__module__.startswith("pandas")


def _convert(value, depth, seen, max_depth, max_items, budget):
    if budget is not None:
        budget.consume(value)
    if depth > max_depth:
        raise SafeJSONError("JSON value exceeds maximum nesting depth")
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return value
    if isinstance(value, Decimal):
        converted = float(value)
        return None if budget is not None and not math.isfinite(converted) else converted
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        text = value.isoformat()
        return text[:-6] + "Z" if text.endswith("+00:00") else text
    if isinstance(value, (date, time)):
        return value.isoformat()
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError:
            raise SafeJSONError("binary value is not UTF-8")

    identity = id(value)
    if identity in seen:
        raise SafeJSONError("cyclic value cannot be encoded")
    seen.add(identity)
    try:
        if isinstance(value, dict):
            if len(value) > max_items:
                raise SafeJSONError("mapping exceeds maximum item count")
            result = {}
            for key, item in value.items():
                if not isinstance(key, (str, int, float, bool)) and key is not None:
                    raise SafeJSONError("mapping key is not JSON compatible")
                if budget is not None:
                    budget.consume(key)
                result[str(key)] = _convert(item, depth + 1, seen, max_depth, max_items, budget)
            return result
        if isinstance(value, (list, tuple, set)):
            if len(value) > max_items:
                raise SafeJSONError("sequence exceeds maximum item count")
            return [_convert(item, depth + 1, seen, max_depth, max_items, budget) for item in value]
        if _is_dataframe(value):
            if budget is not None:
                budget.check_shape(value)
            return _convert(value.to_dict(orient="records"), depth + 1, seen, max_depth, max_items, budget)
        if _is_series(value):
            if budget is not None:
                budget.check_shape(value)
            return _convert(value.to_dict(), depth + 1, seen, max_depth, max_items, budget)

        item_method = getattr(value, "item", None)
        if callable(item_method) and type(value).__module__.startswith("numpy"):
            if budget is not None:
                budget.check_shape(value)
            return _convert(item_method(), depth + 1, seen, max_depth, max_items, budget)
        tolist_method = getattr(value, "tolist", None)
        if callable(tolist_method) and type(value).__module__.startswith("numpy"):
            if budget is not None:
                budget.check_shape(value)
            return _convert(tolist_method(), depth + 1, seen, max_depth, max_items, budget)

        fields = {}
        for name in QMT_PUBLIC_FIELDS:
            if hasattr(value, name):
                field_value = getattr(value, name)
                if not callable(field_value):
                    fields[name] = _convert(
                        field_value, depth + 1, seen, max_depth, max_items, budget
                    )
        if fields:
            return fields
        raise SafeJSONError("unsupported value type: {0}".format(type(value).__name__))
    finally:
        seen.discard(identity)


def to_json_value(value, max_depth=12, max_items=10000, *, budget=None):
    # None preserves the legacy conversion contract; the restricted caller
    # supplies a fresh aggregate budget tied to its managed result byte cap.
    return _convert(value, 0, set(), int(max_depth), int(max_items), budget)


class SafeJSONEncoder(json.JSONEncoder):
    def default(self, value):
        return to_json_value(value)


def dumps(value):
    safe_value = to_json_value(value)
    return json.dumps(
        safe_value,
        cls=SafeJSONEncoder,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )
