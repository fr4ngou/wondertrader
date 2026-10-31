"""分钟worker的显式受管组合；仅构造依赖，不请求、启动线程或推进游标。"""
from __future__ import annotations

from collections.abc import Mapping
import os

from . import MarketClient, encode_json, strict_json
from .history_calendar import CalendarProjectionProvider, calendar_binding_version
from .history_evidence import create_minio_evidence_sink
from .history_factory import _credential, _fields
from .minute_owner import MinuteOwnerClient
from .minute_worker import MinuteWorker
from .strategy_market import MarketSource, StrategyMarket

_CONFIG_ENV = "GUANHENG_MINUTE_WORKER_CONFIG"
_SCHEMA = "guanheng.minute.factory.v1"
_MAX_BYTES = 65536


class MinuteFactoryConfigurationError(ValueError):
    """固定去敏异常；不保留配置、凭据或底层异常上下文。"""


def _build(config, environ):
    _fields(config, ("schema_version", "owner", "stream", "sources", "calendar", "evidence", "market", "budget_seconds"))
    if config["schema_version"] != _SCHEMA:
        raise ValueError
    owner = _fields(config["owner"], ("url", "token_env", "timeout"))
    stream = _fields(config["stream"], ("stream_id", "policy_sha256", "max_batch_minutes"))
    calendar = _fields(config["calendar"], ("url", "token_env", "source_version", "timeout", "http_timeout"))
    evidence = _fields(config["evidence"], ("endpoint", "secure", "region", "bucket", "prefix",
        "access_key_env", "secret_key_env", "timeout"), ("session_token_env",))
    market_config = _fields(config["market"], ("timeout", "max_bars", "max_windows", "minimum_qualification"))
    if type(config["sources"]) is not list or not 1 <= len(config["sources"]) <= 16:
        raise ValueError
    sources = []
    for source in config["sources"]:
        _fields(source, ("name", "url", "token_env", "timeout", "dataset_version", "provider", "allow_prepare"),
                ("connect_ip",))
        client = MarketClient(source["url"], _credential(source["token_env"], environ), timeout=source["timeout"],
                              connect_ip=source.get("connect_ip"))
        sources.append(MarketSource(source["name"], client, source["dataset_version"],
                                    source["provider"], source["allow_prepare"]))
    owner_client = MinuteOwnerClient(owner["url"], _credential(owner["token_env"], environ), timeout=owner["timeout"])
    evidence_client = create_minio_evidence_sink(endpoint=evidence["endpoint"], secure=evidence["secure"],
        region=evidence["region"], bucket=evidence["bucket"], prefix=evidence["prefix"], timeout=evidence["timeout"],
        access_key=_credential(evidence["access_key_env"], environ),
        secret_key=_credential(evidence["secret_key_env"], environ),
        session_token=_credential(evidence["session_token_env"], environ) if "session_token_env" in evidence else None)
    calendar_provider = CalendarProjectionProvider(calendar["url"], _credential(calendar["token_env"], environ),
        evidence_client, calendar["source_version"], timeout=calendar["timeout"], http_timeout=calendar["http_timeout"])
    market = StrategyMarket(sources, calendar_provider, calendar_binding_version(calendar["source_version"]), **market_config)
    if (any(item.timeout >= market.timeout for item in (calendar_provider, *(source.client for source in sources)))
            or calendar_provider.timeout <= calendar_provider.http_timeout + 2 * evidence_client.timeout):
        raise ValueError
    return MinuteWorker(market, owner_client, stream["stream_id"], stream["policy_sha256"],
                        max_batch_minutes=stream["max_batch_minutes"], budget_seconds=config["budget_seconds"])


def build_worker(config, environ):
    """显式配置及环境快照；仅环境名字引用凭据，不合并进程环境。"""
    try:
        if not isinstance(config, Mapping) or not isinstance(environ, Mapping):
            raise ValueError
        raw = encode_json(dict(config))
        if len(raw) > _MAX_BYTES:
            raise ValueError
        return _build(strict_json(raw), dict(environ))
    except Exception:
        pass
    raise MinuteFactoryConfigurationError("minute worker configuration invalid")


def create():
    """CLI零参数工厂，GUANHENG_MINUTE_WORKER_CONFIG为最多64KiB严格JSON。"""
    try:
        environ = dict(os.environ)
        raw = environ.get(_CONFIG_ENV)
        if type(raw) is not str:
            raise ValueError
        raw = raw.encode("utf-8")
        if not raw or len(raw) > _MAX_BYTES:
            raise ValueError
        return build_worker(strict_json(raw), environ)
    except Exception:
        pass
    raise MinuteFactoryConfigurationError("minute worker configuration invalid")
