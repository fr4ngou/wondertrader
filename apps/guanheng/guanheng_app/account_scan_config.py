"""账户Scan部署配置的纯准入；不访问环境、文件、目录或运行来源。"""

import json
import math
import re
from pathlib import Path
from types import MappingProxyType

from .account_projection import AccountProtocolError, integer, text

CONFIG_BYTES = 65536
VIEW_BYTES = 16 * 1024 * 1024
_TOP = {"schema_version", "installation_root", "library", "base_data", "trader", "budget"}
_TRADER = {"module", "adapter_id", "instance_id", "enabled", "savedata", "source", "base_url",
           "key_id_env", "hmac_secret_env", "request_ms", "round_ms", "max_rows", "timeout_ms",
           "max_response_bytes", "close_ms", "expected_account", "environment", "currency", "profile", "view_bytes",
           "read_profile_version"}
_REQUIRED_TRADER = _TRADER - {"request_ms", "round_ms", "max_rows", "timeout_ms", "close_ms", "view_bytes"}


def _need(condition):
    if not condition:
        raise AccountProtocolError("invalid_configuration")


def _object(value, allowed, required=None):
    _need(type(value) is dict and set(value) <= allowed)
    _need((allowed if required is None else required) <= set(value))


def _string(value, limit, *, byte_limit=False):
    _need(type(value) is str and 0 < len(value) <= limit)
    _need(all(ord(char) >= 32 and not 127 <= ord(char) <= 159 and not 0xD800 <= ord(char) <= 0xDFFF
              for char in value))
    if byte_limit:
        _need(len(value.encode("utf-8")) <= limit)
    return value


def _absolute(value):
    _string(value, 8192, byte_limit=True)
    _need(Path(value).is_absolute())


def _bound_file(value):
    _object(value, {"path", "sha256"})
    _absolute(value["path"])
    _need(type(value["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", value["sha256"]) is not None)


def _plain(value, *, legacy=False):
    # 新typed入口也有64KiB树域；先逐节点/码点限量，再做有限UTF-8序列化。
    # 新快照不接受任意Mapping/转换协议，防止调用方可变对象在准入后换值。
    nodes, chars = 0, 0

    def copy(item, depth):
        nonlocal nodes, chars
        nodes += 1
        _need(nodes <= 65536 and depth <= 32)
        if type(item) is str:
            chars += len(item)
            _need(chars <= CONFIG_BYTES and (legacy or not any(0xD800 <= ord(char) <= 0xDFFF for char in item)))
            return item
        if item is None or type(item) in (bool, int):
            return item
        if type(item) is float:
            _need(math.isfinite(item))
            return item
        if type(item) in (dict, MappingProxyType):
            _need(len(item) <= 65536)
            result = {}
            for key, child in item.items():
                _need(type(key) is str)
                result[copy(key, depth + 1)] = copy(child, depth + 1)
            return result
        if type(item) in (list, tuple):
            _need(len(item) <= 65536)
            return [copy(child, depth + 1) for child in item]
        _need(False)

    result = copy(value, 0)
    if legacy:
        # schema1文件原raw 64KiB由from_paths保持；原父端不重编码/补Unicode规则。
        return result
    try:
        size = 0
        for piece in json.JSONEncoder(ensure_ascii=False, allow_nan=False, separators=(",", ":")).iterencode(result):
            size += len(piece.encode("utf-8"))
            _need(size <= CONFIG_BYTES)
    except (ValueError, UnicodeError, OverflowError, RecursionError):
        raise AccountProtocolError("invalid_configuration") from None
    return result


def _freeze(value):
    if type(value) is dict:
        return MappingProxyType({key: _freeze(child) for key, child in value.items()})
    if type(value) is list:
        return tuple(_freeze(child) for child in value)
    return value


def validate_account_scan_configuration(value):
    """返回无别名递归不可变快照；仅授配置资格，不核文件SHA或访问运行环境。

    schema1保持旧父端默认准入；schema2精确登记SHM来源及v3，不增加客户端恢复目录。
    实际Host max_result未知，HTTP wrapper联合下限由后继prepare核验。
    """
    _need(type(value) in (dict, MappingProxyType))
    # 先拥有唯一私有副本，再从同一副本取版本并选择来源分支；调用方变更不能拼出混版快照。
    # 此步保留legacy的Unicode域；schema2在字段准入及补默认后仍统一走严格UTF-8/64KiB边界。
    value = _plain(value, legacy=True)
    _need(type(value.get("schema_version")) is int)
    version = value["schema_version"]
    _need(version in (1, 2))
    _object(value, _TOP)
    trader, budget = value["trader"], value["budget"]
    _object(budget, {"total_ms"}, set())
    total = budget.get("total_ms", 15000)
    _need(integer(total, 1000, 30000))
    _need(type(trader) is dict)
    if version == 1:
        # 旧父端只核这些绑定；原native schema1仍独占完整文件/字段准入。
        _need(trader.get("source") == "qmt_http" and trader.get("profile") == "cny_cash_shsz_v1"
              and trader.get("currency") == "CNY")
        _need(text(trader.get("expected_account")) and text(trader.get("environment")))
        _need(integer(trader.get("max_rows", 4096), 1, 4096))
        return _freeze(value)

    _absolute(value["installation_root"])
    _bound_file(value["library"])
    _object(value["base_data"], {"sessions", "commodities", "contracts"})
    for descriptor in value["base_data"].values():
        _bound_file(descriptor)
    _object(trader, _TRADER, _REQUIRED_TRADER)
    _need(trader["module"] == "TraderQMTReadOnly" and trader["enabled"] is True and trader["savedata"] is False)
    _need(trader["source"] == "qmt_shm_bound" and trader["read_profile_version"] == "qmt.read-profile.v3")
    _need(trader["profile"] == "cny_cash_shsz_v1" and trader["currency"] == "CNY")
    _need(trader["environment"] in ("simulation", "live"))
    _string(trader["expected_account"], 63, byte_limit=True)
    _need(re.fullmatch(r"[A-Za-z0-9_-]{1,24}", _string(trader["adapter_id"], 24)) is not None)
    _string(trader["instance_id"], 48, byte_limit=True)
    _need(_string(trader["base_url"], 2048, byte_limit=True).startswith(("http://", "https://")))
    for name in ("key_id_env", "hmac_secret_env"):
        _need(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,127}", _string(trader[name], 128)) is not None)
    request = trader.get("request_ms", min(2000, total))
    _need(integer(request, 1, total))
    defaults = {"request_ms": request, "round_ms": min(10000, total), "close_ms": min(2000, total),
                "timeout_ms": request, "max_rows": 4096, "view_bytes": VIEW_BYTES}
    for key, default in defaults.items():
        trader.setdefault(key, default)
    _need(integer(trader["round_ms"], request, total) and integer(trader["close_ms"], 1, total)
          and integer(trader["timeout_ms"], 1, request) and integer(trader["max_rows"], 1, 4096)
          and integer(trader["view_bytes"], 1, VIEW_BYTES) and integer(trader["max_response_bytes"], 1, VIEW_BYTES))
    budget["total_ms"] = total
    # 默认值也进入唯一快照；补齐后的完整配置同样不能突破64KiB声明。
    return _freeze(_plain(value))
