"""证券目录与搜索的公开只读合同。"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CATALOG_SCHEMA = "guanheng.security-catalog.v1"
SEARCH_SCHEMA = "guanheng.security-search.v1"


class SecurityIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    symbol: str = Field(pattern=r"^[0-9]{6}\.(SH|SZ)$")
    code: str = Field(pattern=r"^[0-9]{6}$")
    exchange: Literal["SH", "SZ"]
    name: str = Field(min_length=1, max_length=64)
    security_type: Literal["stock", "etf", "index"]
    pinyin_initials: str = Field(pattern=r"^[a-z0-9]+$", max_length=128)
    pinyin_full: str = Field(pattern=r"^[a-z0-9]+$", max_length=256)


class SecuritySearchResult(SecurityIdentity):
    match: Literal["code", "name", "pinyin_initials", "pinyin_full"]


class SecuritySearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal[SEARCH_SCHEMA] = SEARCH_SCHEMA
    query: str
    catalog_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    generated_at: str
    results: tuple[SecuritySearchResult, ...]
