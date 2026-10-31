"""App策略配置版本协议；唯一核校验参数，保存回执不授运行生效资格。"""

from datetime import datetime, timezone
from dataclasses import asdict, fields, MISSING
from hashlib import sha256
import json
import re

from guanheng_strategy_core import ConfiguredStrategyConfig, KernelValidationError, validate_configuration
from guanheng_strategy_core.contracts import canonical_bytes
from guanheng_strategy_v1 import RetainedConfig, STRATEGY_ID, STRATEGY_VERSION, validate_retained_configuration

PREFIX = "guanheng.strategy-configuration-"
WORKSPACE_SCHEMA = PREFIX + "workspace.v1"
STATE_SCHEMA = PREFIX + "state.v1"
SAVE_SCHEMA = PREFIX + "save.v1"
VALIDATE_SCHEMA = PREFIX + "validation-request.v1"
MAX_REQUEST_BYTES = 16 * 1024
MAX_STATE_BYTES = 512 * 1024
MAX_VERSIONS = 32
IDENTITY = re.compile(r"[a-f0-9]{32}\Z")
SHA = re.compile(r"[a-f0-9]{64}\Z")


class ConfigurationValueError(ValueError):
    """值错误仅含固定原因码，禁止回显路径或调用者原始字段。"""


def require(condition, reason="invalid_payload"):
    if not condition:
        raise ConfigurationValueError(reason)


def keys(value, expected):
    require(type(value) is dict and set(value) == set(expected))


def _pairs(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value)
        value[key] = item
    return value


def _unicode_scalars(value):
    """JSON键和值只接受Unicode标量；UTF-8检查同时覆盖转义及直接Python值。"""
    if type(value) is str:
        value.encode("utf-8", errors="strict")
    elif type(value) is dict:
        for key, item in value.items():
            require(type(key) is str)
            _unicode_scalars(key)
            _unicode_scalars(item)
    elif type(value) in (list, tuple):
        for item in value:
            _unicode_scalars(item)


def decode(raw, maximum=MAX_REQUEST_BYTES):
    require(type(raw) is bytes and 0 < len(raw) <= maximum)
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                           parse_constant=lambda _x: require(False))
        _unicode_scalars(value)
        return value
    except (ValueError, TypeError, UnicodeError, RecursionError, OverflowError):
        raise ConfigurationValueError("invalid_payload") from None


def encode(value, maximum=MAX_STATE_BYTES):
    try:
        _unicode_scalars(value)
        raw = canonical_bytes(value)
        require(0 < len(raw) <= maximum)
        return raw
    except (ValueError, TypeError, UnicodeError, RecursionError, OverflowError):
        raise ConfigurationValueError("invalid_payload") from None


def identity(value):
    require(type(value) is str and IDENTITY.fullmatch(value))
    return value


def configuration(value, *, stored=False):
    """新配置只准入正式版本；旧配置仅供持久原件校验与回执读取。"""
    try:
        require(len(encode(value, MAX_REQUEST_BYTES)) <= MAX_REQUEST_BYTES)
        require(type(value) is dict)
        if stored and value.get('strategy_version') == '1.2.0':
            model = ConfiguredStrategyConfig.from_dict(value)
            validate_configuration(model)
            normalized = model.to_dict()
        else:
            identity_fields = {'schema', 'strategy_id', 'strategy_version'}
            declared = fields(RetainedConfig)
            required = identity_fields | {f.name for f in declared if f.default is MISSING}
            require(required <= set(value) <= identity_fields | {f.name for f in declared})
            require((value['schema'], value['strategy_id'], value['strategy_version']) ==
                    ('guanheng.retained-configuration.v1', STRATEGY_ID, STRATEGY_VERSION))
            model = RetainedConfig(**{k: v for k, v in value.items() if k not in identity_fields})
            validate_retained_configuration(model)
            normalized = {k: value[k] for k in identity_fields} | asdict(model)
        raw = encode(normalized, MAX_REQUEST_BYTES)
        return normalized, sha256(raw).hexdigest()
    except KernelValidationError:
        raise
    except (ValueError, TypeError, UnicodeError, RecursionError, OverflowError):
        raise ConfigurationValueError("invalid_configuration") from None


def stamp(value):
    require(type(value) is str and len(value) <= 32 and value.endswith("Z"))
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        require(parsed.utcoffset() is not None)
        return parsed
    except (ValueError, OverflowError):
        raise ConfigurationValueError("invalid_time") from None


def validation(value, now):
    normalized, digest = configuration(value)
    stamp(now)
    return {"schema": PREFIX + "validation.v1", "configuration": normalized,
            "configuration_sha256": digest, "validation_time": now,
            "validity": "not_applicable",
            "qualification": "configuration-only; data/runtime/execution-unqualified"}


def save_request(value, *, stored=False):
    keys(value, ("schema", "store_id", "expected_revision", "request_id", "configuration"))
    require(value["schema"] == SAVE_SCHEMA)
    identity(value["store_id"])
    identity(value["request_id"])
    require(type(value["expected_revision"]) is int and 0 <= value["expected_revision"] <= MAX_VERSIONS)
    normalized, config_sha = configuration(value["configuration"], stored=stored)
    bound = {"store_id": value["store_id"], "expected_revision": value["expected_revision"], "configuration": normalized}
    return {**value, "configuration": normalized}, config_sha, sha256(encode(bound)).hexdigest()


def state(value):
    keys(value, ("schema", "store_id", "revision", "versions"))
    require(value["schema"] == STATE_SCHEMA)
    identity(value["store_id"])
    require(type(value["revision"]) is int and 0 <= value["revision"] <= MAX_VERSIONS)
    rows = value["versions"]
    require(type(rows) is list and len(rows) == value["revision"])
    seen = set()
    for index, row in enumerate(rows, 1):
        keys(row, ("revision", "request_id", "request_sha256", "configuration_sha256", "configuration", "saved_at"))
        require(type(row["revision"]) is int and row["revision"] == index)
        identity(row["request_id"])
        require(row["request_id"] not in seen)
        seen.add(row["request_id"])
        stamp(row["saved_at"])
        request, digest, request_sha = save_request({"schema": SAVE_SCHEMA, "store_id": value["store_id"],
            "expected_revision": index - 1, "request_id": row["request_id"], "configuration": row["configuration"]}, stored=True)
        require(row["configuration"] == request["configuration"] and row["configuration_sha256"] == digest
                and row["request_sha256"] == request_sha)
    return value


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def catalog():
    """正式版本的显式合成示例；加载或保存均不授予运行资格。"""
    example = {'schema': 'guanheng.retained-configuration.v1', 'strategy_id': STRATEGY_ID,
        'strategy_version': STRATEGY_VERSION, **asdict(RetainedConfig('synthetic-config-1', .8))}
    return [{"strategy_id": example["strategy_id"], "strategy_version": example["strategy_version"],
             "label": "共振市场状态 ETF 策略 · 1.1.2", "example_kind": "synthetic",
             "example": example}]
