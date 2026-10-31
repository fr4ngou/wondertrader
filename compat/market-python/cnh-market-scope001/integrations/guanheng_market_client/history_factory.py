"""历史worker的显式部署组合；构造期间不访问远端或推进作业。"""
from __future__ import annotations

from collections.abc import Mapping
import os
import re

from . import MarketClient, encode_json, strict_json
from .history_calendar import CalendarProjectionProvider, calendar_binding_version
from .history_evidence import create_minio_evidence_sink
from .history_runner import HistoryBinding, HistoryRunner, OperationsClient

__all__ = ["HistoryFactoryConfigurationError", "build_runner", "create"]

_CONFIG_ENV = "GUANHENG_HISTORY_WORKER_CONFIG"
_SCHEMA = "guanheng.history.factory.v1"
_MAX_CONFIG_BYTES = 16384
_ERROR = "history worker configuration invalid"
_ENV_NAME = re.compile(r"[A-Z][A-Z0-9_]{0,127}", re.ASCII)


class HistoryFactoryConfigurationError(ValueError):
    """固定去敏的部署错误；不携带配置、凭据或原始异常链。"""


def _fields(value, required, optional=()):
    if type(value) is not dict or not set(required) <= value.keys() or value.keys() - set(required) - set(optional):
        raise ValueError
    return value


def _credential(name, environ):
    if type(name) is not str or _ENV_NAME.fullmatch(name) is None:
        raise ValueError
    value = environ.get(name)
    if type(value) is not str or not 1 <= len(value) <= 4096 or any(not 33 <= ord(c) <= 126 for c in value):
        raise ValueError
    return value


def _snapshot(config):
    if not isinstance(config, Mapping):
        raise ValueError
    # 固定已知两层JSON对象；往返保留数值类型并脱离调用方之后的修改。
    raw = encode_json({key: dict(value) if isinstance(value, Mapping) else value
                       for key, value in config.items()})
    if len(raw) > _MAX_CONFIG_BYTES:
        raise ValueError
    return strict_json(raw)


def _build(config, environ):
    _fields(config, ("schema_version", "operations", "market", "calendar", "evidence", "binding", "budget_ms"))
    if config["schema_version"] != _SCHEMA:
        raise ValueError
    ops = _fields(config["operations"], ("url", "token_env", "timeout"))
    market = _fields(config["market"], ("url", "token_env", "timeout"), ("connect_ip",))
    calendar = _fields(config["calendar"], ("url", "token_env", "source_version", "timeout", "http_timeout"))
    evidence = _fields(config["evidence"], ("endpoint", "secure", "region", "bucket", "prefix",
                       "access_key_env", "secret_key_env", "timeout"), ("session_token_env",))
    binding = _fields(config["binding"], ("agent_id", "profile_version", "source_license", "volume_to_shares", "amount_to_yuan"))
    budget = config["budget_ms"]
    if type(budget) is not int or not 1 <= budget <= 30000:
        raise ValueError
    ops_token = _credential(ops["token_env"], environ)
    market_token = _credential(market["token_env"], environ)
    calendar_token = _credential(calendar["token_env"], environ)
    access_key = _credential(evidence["access_key_env"], environ)
    secret_key = _credential(evidence["secret_key_env"], environ)
    session_token = _credential(evidence["session_token_env"], environ) if "session_token_env" in evidence else None
    bound = HistoryBinding(**binding, calendar_version=calendar_binding_version(calendar["source_version"]))
    operations_client = OperationsClient(ops["url"], ops_token, timeout=ops["timeout"])
    market_client = MarketClient(market["url"], market_token, timeout=market["timeout"],
                                 connect_ip=market.get("connect_ip"))
    storage = create_minio_evidence_sink(endpoint=evidence["endpoint"], secure=evidence["secure"],
        region=evidence["region"], bucket=evidence["bucket"], prefix=evidence["prefix"], timeout=evidence["timeout"],
        access_key=access_key, secret_key=secret_key, session_token=session_token)
    calendar_provider = CalendarProjectionProvider(calendar["url"], calendar_token,
        storage, calendar["source_version"], timeout=calendar["timeout"], http_timeout=calendar["http_timeout"])
    # 复用实际owner验证后的完整调用预算；组合关系只在部署入口维护。
    if (any(owner.timeout * 1000 >= budget for owner in (operations_client, market_client, storage, calendar_provider))
            or calendar_provider.timeout <= calendar_provider.http_timeout + 2 * storage.timeout):
        raise ValueError
    return HistoryRunner(operations_client, market_client, calendar_provider, storage, bound, budget_ms=budget)


def build_runner(config, environ):
    """仅消费传入配置/环境快照，在调用线程构造既有owner；不合并进程环境。

    配置遵循guanheng.history.factory.v1。凭据只按显式环境名字取值；
    地址、鉴权、单位和存储版本交给实际客户端校验。失败返回固定配置异常。
    """
    try:
        if not isinstance(environ, Mapping):
            raise ValueError
        environment = dict(environ)
        return _build(_snapshot(config), environment)
    except Exception:
        pass
    # 在except作用域外抛出，__context__也不保留可能包含凭据的依赖异常。
    raise HistoryFactoryConfigurationError(_ERROR)


def create():
    """worker零参数factory；环境变量内容为UTF-8 JSON，最大16384字节。"""
    try:
        environment = dict(os.environ)
        raw = environment.get(_CONFIG_ENV)
        if type(raw) is not str:
            raise ValueError
        raw = raw.encode("utf-8")
        if not raw or len(raw) > _MAX_CONFIG_BYTES:
            raise ValueError
        return build_runner(strict_json(raw), environment)
    except Exception:
        pass
    raise HistoryFactoryConfigurationError(_ERROR)
