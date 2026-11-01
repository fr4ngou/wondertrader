"""部署发布的证券目录所有者；搜索只返回目录中的规范身份。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any

from .contracts.security_catalog import CATALOG_SCHEMA, SecurityIdentity, SecuritySearchResult

_PINYIN = re.compile(r"^[a-z0-9]+$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class SecurityCatalogError(ValueError):
    """目录配置、制品或查询不满足公开合同。"""


def _utf8(value: Any, maximum: int) -> str:
    if not isinstance(value, str) or not value or len(value.encode("utf-8")) > maximum:
        raise SecurityCatalogError("证券目录字段无效")
    return value


def _identity(value: Any) -> SecurityIdentity:
    if not isinstance(value, dict) or set(value) != {
        "symbol", "code", "exchange", "name", "security_type", "pinyin_initials", "pinyin_full"
    }:
        raise SecurityCatalogError("证券目录身份字段无效")
    try:
        item = SecurityIdentity.model_validate(value)
    except ValueError as error:
        raise SecurityCatalogError("证券目录身份无效") from error
    if item.symbol != f"{item.code}.{item.exchange}":
        raise SecurityCatalogError("证券目录规范身份不一致")
    if not _PINYIN.fullmatch(item.pinyin_initials) or not _PINYIN.fullmatch(item.pinyin_full):
        raise SecurityCatalogError("证券目录拼音无效")
    return item


class SecurityCatalog:
    """一次加载、不可变搜索；目录缺失时能力明确关闭。"""

    def __init__(self, path: str):
        self._items: tuple[SecurityIdentity, ...] = ()
        self.catalog_id = ""
        self.generated_at = ""
        self.reason = "尚未配置证券目录"
        if path:
            self._load(Path(path))

    @property
    def available(self) -> bool:
        return bool(self._items)

    def capability(self) -> dict[str, Any]:
        return {"available": self.available, "read_only": True,
                "types": ["stock", "etf", "index"],
                "reason": None if self.available else self.reason}

    def _load(self, path: Path) -> None:
        try:
            raw = path.read_bytes()
            value = json.loads(raw)
            if not isinstance(value, dict) or set(value) != {
                "schema_version", "catalog_id", "generated_at", "source", "securities"
            } or value.get("schema_version") != CATALOG_SCHEMA:
                raise SecurityCatalogError("证券目录制品结构无效")
            catalog_id = value.get("catalog_id")
            if not isinstance(catalog_id, str) or not _SHA256.fullmatch(catalog_id):
                raise SecurityCatalogError("证券目录身份无效")
            generated_at = _utf8(value.get("generated_at"), 64)
            source = value.get("source")
            if not isinstance(source, dict) or not source:
                raise SecurityCatalogError("证券目录来源无效")
            securities = value.get("securities")
            if not isinstance(securities, list) or not securities:
                raise SecurityCatalogError("证券目录为空")
            items = tuple(_identity(item) for item in securities)
            symbols = tuple(item.symbol for item in items)
            if len(set(symbols)) != len(symbols) or symbols != tuple(sorted(symbols)):
                raise SecurityCatalogError("证券目录规范身份重复或顺序无效")
            payload = json.dumps(securities, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
            if hashlib.sha256(payload).hexdigest() != catalog_id:
                raise SecurityCatalogError("证券目录内容身份不一致")
            self._items, self.catalog_id, self.generated_at = items, catalog_id, generated_at
            self.reason = ""
        except (OSError, UnicodeError, json.JSONDecodeError, SecurityCatalogError) as error:
            self.reason = "证券目录制品无效或不可读取"
            self._items = ()
            if isinstance(error, SecurityCatalogError):
                return

    def search(self, query: str, limit: int) -> tuple[SecuritySearchResult, ...]:
        if not self.available:
            raise SecurityCatalogError(self.reason)
        if not isinstance(query, str) or len(query.encode("utf-8")) > 128:
            raise SecurityCatalogError("证券搜索词无效")
        term = "".join(query.strip().lower().split())
        if not term or len(term) > 64:
            raise SecurityCatalogError("请输入证券简称、拼音或代码")
        ranked: list[tuple[int, str, SecurityIdentity, str]] = []
        for item in self._items:
            name = "".join(item.name.lower().split())
            match = ""
            rank = 99
            if item.code == term or item.symbol.lower() == term:
                match, rank = "code", 0
            elif item.code.startswith(term) and term.isdigit():
                match, rank = "code", 1
            elif name == term:
                match, rank = "name", 2
            elif name.startswith(term):
                match, rank = "name", 3
            elif item.pinyin_initials == term:
                match, rank = "pinyin_initials", 4
            elif item.pinyin_initials.startswith(term):
                match, rank = "pinyin_initials", 5
            elif item.pinyin_full == term:
                match, rank = "pinyin_full", 6
            elif item.pinyin_full.startswith(term):
                match, rank = "pinyin_full", 7
            elif term in name:
                match, rank = "name", 8
            if match:
                ranked.append((rank, item.symbol, item, match))
        ranked.sort(key=lambda value: (value[0], value[1]))
        return tuple(SecuritySearchResult(**item.model_dump(), match=match)
                     for _, _, item, match in ranked[:limit])
