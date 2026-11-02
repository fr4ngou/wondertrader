"""来源分钟查询合同；共用基础字段校验，来源语义由独立 action 表达。"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import datetime
from uuid import UUID

from . import (MarketProtocolError, _enum, _integer, _list, _minute,
              _number, _object, _source, _symbol, _text)


def validate_source_request(value):
    """校验证券、闭区间与条数；所有字段均由调用方显式给出。"""
    _object(value, ("exchange", "code", "from", "to", "limit"))
    _enum(value["exchange"], ("SSE", "SZSE"))
    _text(value["code"], limit=6)
    _symbol(value["exchange"] + "." + value["code"])
    if _minute(value["from"]) > _minute(value["to"]):
        raise MarketProtocolError("source history range is invalid")
    _integer(value["limit"], 1, 2000)
    return value


def validate_source_metadata(value, *, period="1m", selection=False):
    """保留原来源身份及未知单位，不推导标准化比例或分钟边界。"""
    _enum(period, ("1m", "1d"))
    _object(value, ("source", "qualification", "dataset_version", "source_license",
                    "adjustment", "factor_version", "minute_boundary", "timezone",
                    "content_id", "value_semantics", "timestamp_semantics",
                    "price_unit", "volume_unit", "amount_unit") + (("period",) if period == "1d" else ()))
    if period == "1d":
        _enum(value["period"], ("1d",))
        _enum(value["minute_boundary"], ("unknown",))
    if selection:
        source = _object(value["source"], ("kind", "provider", "selection_id"))
        _enum(source["kind"], ("SourceSelection",))
        _enum(source["provider"], ("Qmt", "Tdx", "BaoStock", "Tencent", "Mixed") if period == "1d" else ("Qmt",))
        _sha(source["selection_id"])
    else:
        _source(value["source"])
    _enum(value["qualification"], ("DevelopmentVerified",))
    _text(value["dataset_version"], limit=256)
    _text(value["source_license"], limit=1024)
    _enum(value["adjustment"], ("none",))
    _enum(value["factor_version"], ("",))
    _enum(value["minute_boundary"], ("left", "right", "unknown"))
    _enum(value["timezone"], ("Asia/Shanghai",))
    _enum(value["value_semantics"], ("source",))
    _enum(value["timestamp_semantics"], ("source_date",) if period == "1d" else ("source_label",))
    _enum(value["price_unit"], ("CNY", "unknown"))
    _enum(value["volume_unit"], ("share", "lot", "unknown"))
    _enum(value["amount_unit"], ("CNY", "unknown"))
    if (type(value["content_id"]) is not str
            or re.fullmatch("[0-9a-f]{64}", value["content_id"]) is None):
        raise MarketProtocolError("source history content identity is invalid")
    return value


def _sha(value):
    if type(value) is not str or re.fullmatch("[0-9a-f]{64}", value) is None:
        raise MarketProtocolError("source selection identity is invalid")
    return value


def source_selection_metadata(bars, provenance):
    """集合身份绑定实际返回行及完整分段证据，不构造捕获会话。"""
    identity = hashlib.sha256(json.dumps(dict(schema="qmt.source-selection.v1", bars=bars, provenance=provenance),
        ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf8")).hexdigest()
    metadata = copy.deepcopy(provenance[0]["metadata"])
    for key in ("minute_boundary", "price_unit", "volume_unit", "amount_unit"):
        values = {part["metadata"][key] for part in provenance}
        metadata[key] = next(iter(values)) if len(values) == 1 else "unknown"
    metadata.update(source=dict(kind="SourceSelection", provider="Qmt", selection_id=identity),
        dataset_version="source-selection.v1:" + identity, content_id=identity,
        source_license="source-selection.v1: original licenses in provenance")
    return metadata


def daily_selection_metadata(bars, provenance):
    """日期行与分段原身份共同绑定；集合身份不代表供应商捕获会话。"""
    identity = hashlib.sha256(json.dumps(dict(schema="source-daily-selection.v1", bars=bars, provenance=provenance),
        ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf8")).hexdigest()
    metadata = copy.deepcopy(provenance[0]["metadata"])
    providers = {part["metadata"]["source"]["provider"] for part in provenance}
    for key in ("price_unit", "volume_unit", "amount_unit"):
        values = {part["metadata"][key] for part in provenance}
        metadata[key] = next(iter(values)) if len(values) == 1 else "unknown"
    metadata.update(
        # kind区分来源集合；provider共同来源或Mixed；selection_id为本选择SHA256。
        source=dict(kind="SourceSelection", provider=next(iter(providers)) if len(providers) == 1 else "Mixed", selection_id=identity),
        dataset_version="source-daily-selection.v1:" + identity,  # 绑定本次行及分段证据的版本。
        content_id=identity,  # 当前选择内容摘要，不冒充原文件摘要。
        source_license="source-daily-selection.v1: original licenses in provenance")
    return metadata


def validate_source_observation(value, request, selected_rows):
    """仅说明有限缓存观测和原HPR状态；不授市场覆盖或补齐完成。"""
    _object(value, ("schema", "state", "source_window", "source_rows", "requested_limit", "selected_rows",
                    "preparation_state", "preparation_request_id", "reason"))
    _enum(value["schema"], ("qmt.source-selection-observation.v1",))
    _enum(value["state"], ("Archive", "Observed", "Partial"))
    _enum(value["preparation_state"], ("NotNeeded", "CallReturned", "Unknown", "Pending", "Unavailable", "NotSupported", "Budget"))
    _integer(value["source_rows"], 0, 1000000)
    if value["requested_limit"] != request["limit"] or value["selected_rows"] != selected_rows:
        raise MarketProtocolError("source observation quantity differs from selection")
    _integer(value["requested_limit"], 1, 2000)
    _integer(value["selected_rows"], 0, request["limit"])
    window = value["source_window"]
    if window is not None:
        _object(window, ("from", "to"))
        if not request["from"] <= _minute(window["from"]) <= _minute(window["to"]) <= request["to"]:
            raise MarketProtocolError("source observation window differs from request")
    rid = value["preparation_request_id"]
    if rid is not None:
        try:
            if type(rid) is not str or str(UUID(rid)) != rid:
                raise ValueError
        except (ValueError, AttributeError):
            raise MarketProtocolError("source observation request identity is invalid") from None
    if value['preparation_state'] in ('CallReturned', 'Unknown') and rid is None:
        raise MarketProtocolError('source preparation has no original request identity')
    if value['state'] == 'Archive' and (window is not None or value['source_rows'] != 0
            or value['preparation_state'] != 'NotNeeded' or rid is not None):
        raise MarketProtocolError('archive observation cannot claim source preparation')
    if value['state'] == 'Observed' and (window is None or value['source_rows'] == 0):
        raise MarketProtocolError('source observation has no readback')
    _text(value["reason"], limit=500)
    return value


def _date(value):
    """日线标签只表示交易日期，不推导知晓/闭合时刻。"""
    # 八位JSON整数的范围；实际上下界再由有效公历日期校验推出。
    _integer(value, 10**7, 10**8-1)
    try:
        datetime.strptime(str(value), "%Y%m%d")
    except ValueError:
        raise MarketProtocolError("source daily date is invalid") from None
    return value


def validate_source_daily_request(value):
    _object(value, ("exchange", "code", "from", "to", "limit"))
    _enum(value["exchange"], ("SSE", "SZSE"))
    _text(value["code"], limit=6)
    _symbol(value["exchange"] + "." + value["code"])
    if _date(value["from"]) > _date(value["to"]):
        raise MarketProtocolError("source daily range is invalid")
    _integer(value["limit"], 1, 2000)
    return value


def validate_source_daily_data(value, request):
    validate_source_daily_request(request)
    fields = ("metadata", "bars", "coverage", "missing_dates", "selection")
    _object(value, fields + ("provenance",), required=fields)
    composite = "provenance" in value
    validate_source_metadata(value["metadata"], period="1d", selection=composite)
    _enum(value["coverage"], ("Unknown",))
    _list(value["missing_dates"], 0)
    selection = _object(value["selection"], ("period", "limit"))
    _enum(selection["period"], ("1d",))
    if _integer(selection["limit"], 1, 2000) != request["limit"]:
        raise MarketProtocolError("source daily selection differs from request")
    symbol = request["exchange"] + "." + request["code"]
    previous = 0
    for bar in _list(value["bars"], request["limit"]):
        _object(bar, ("symbol", "date", "open", "high", "low", "close", "volume", "amount"))
        if _symbol(bar["symbol"]) != symbol:
            raise MarketProtocolError("source daily security differs from request")
        day = _date(bar["date"])
        if not request["from"] <= day <= request["to"] or day <= previous:
            raise MarketProtocolError("source daily bars are out of range, repeated or unordered")
        for key in ("open", "high", "low", "close"):
            _number(bar[key], positive=True)
        for key in ("volume", "amount"):
            _number(bar[key])
        previous = day
    if composite:
        offset = 0
        for part in _list(value["provenance"], request["limit"]):
            # offset为从0起的bar索引；count为连续行数；metadata保存这些行的原来源。
            _object(part, ("offset", "count", "metadata"))
            if _integer(part["offset"], 0, request["limit"]) != offset:
                raise MarketProtocolError("daily source provenance is discontinuous")
            offset += _integer(part["count"], 1, request["limit"])
            validate_source_metadata(part["metadata"], period="1d")
        if (not value["provenance"] or offset != len(value["bars"]) or
                value["metadata"] != daily_selection_metadata(value["bars"], value["provenance"])):
            raise MarketProtocolError("daily source selection evidence differs")
    return value


def validate_source_data(value, request):
    """成功响应绑定原请求，空选择仍携带已验证的来源元数据。"""
    validate_source_request(request)
    fields = ("metadata", "bars", "coverage", "missing_minutes", "selection")
    _object(value, fields + ("provenance", "observation"), required=fields)
    composite = "provenance" in value
    validate_source_metadata(value["metadata"], selection=composite)
    _enum(value["coverage"], ("Unknown",))
    _list(value["missing_minutes"], 0)
    selection = _object(value["selection"], ("period_minutes", "limit"))
    _integer(selection["period_minutes"], 1, 1)
    if _integer(selection["limit"], 1, 2000) != request["limit"]:
        raise MarketProtocolError("source history selection differs from request")
    symbol = request["exchange"] + "." + request["code"]
    previous = 0
    for bar in _list(value["bars"], request["limit"]):
        _object(bar, ("symbol", "minute", "open", "high", "low", "close", "volume", "amount"))
        if _symbol(bar["symbol"]) != symbol:
            raise MarketProtocolError("source history security differs from request")
        minute = _minute(bar["minute"])
        if not request["from"] <= minute <= request["to"] or minute <= previous:
            raise MarketProtocolError("source history bars are out of range, repeated or unordered")
        for key in ("open", "high", "low", "close"):
            _number(bar[key], positive=True)
        for key in ("volume", "amount"):
            _number(bar[key])
        previous = minute
    if composite:
        offset = 0
        for part in _list(value["provenance"], request["limit"]):
            _object(part, ("offset", "count", "metadata"))
            if _integer(part["offset"], 0, request["limit"]) != offset:
                raise MarketProtocolError("source provenance is discontinuous")
            offset += _integer(part["count"], 1, request["limit"])
            validate_source_metadata(part["metadata"])
            if part["metadata"]["source"]["provider"] != "Qmt":
                raise MarketProtocolError("source provenance provider differs")
        if offset != len(value["bars"]) or not value["provenance"] or value["metadata"] != source_selection_metadata(value["bars"], value["provenance"]):
            raise MarketProtocolError("source selection evidence differs")
    if "observation" in value:
        validate_source_observation(value["observation"], request, len(value["bars"]))
    return value
