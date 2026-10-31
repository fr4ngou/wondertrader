"""个人观察偏好的值契约；纯校验/编码，不读文件或调用行情、账户、策略。"""

from dataclasses import dataclass
from datetime import datetime
import json
import re
from uuid import UUID

from ..native_chart import normalize_chart_symbol


SCHEMA_VERSION = "guanheng.personal-watchlist.v1"
MAX_ITEMS = 100
MAX_VERSION = 9007199254740991
MAX_REQUEST_BYTES = 4096
MAX_STATE_BYTES = 16 * 1024
MAX_REASON_BYTES = 256

_STATE_KEYS = frozenset(("schema_version", "watchlist_id", "version", "symbols", "updated_at"))
_REQUEST_KEYS = frozenset(("schema_version", "watchlist_id", "expected_version", "symbols"))
_UTC = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?Z")
_INVALID = "个人观察资料格式无效"


def _invalid():
    raise ValueError(_INVALID)


def _identity(value):
    if type(value) is not str or len(value) != 36:
        _invalid()
    try:
        parsed = UUID(value)
    except ValueError:
        _invalid()
    if parsed.version != 4 or str(parsed) != value:
        _invalid()
    return value


def _version(value):
    # bool/float都不能成为因果版本；浏览器整数精度限制由协议统一拥有。
    if type(value) is not int or not 1 <= value <= MAX_VERSION:
        _invalid()
    return value


def _timestamp(value):
    if type(value) is not str or not _UTC.fullmatch(value):
        _invalid()
    try:
        datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        _invalid()
    return value


def _symbols(value, *, normalize):
    if type(value) not in (list, tuple) or len(value) > MAX_ITEMS:
        _invalid()
    result, seen = [], set()
    for symbol in value:
        if type(symbol) is not str or len(symbol) > 32:
            _invalid()
        try:
            if len(symbol.encode("utf-8")) > 32:
                _invalid()
            canonical = normalize_chart_symbol(symbol)
        except (ValueError, UnicodeError):
            _invalid()
        # 磁盘及typed值必须已经规范化；用户输入只在PUT解码边界规范化一次。
        if (not normalize and canonical != symbol) or canonical in seen:
            _invalid()
        result.append(canonical)
        seen.add(canonical)
    return tuple(result)


def _keys(value, keys):
    if type(value) is not dict or set(value) != keys or value["schema_version"] != SCHEMA_VERSION:
        _invalid()


def _pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            _invalid()
        value[key] = item
    return value


def _constant(_value):
    _invalid()


def _decode(raw, limit):
    if type(raw) is not bytes or not raw or len(raw) > limit:
        _invalid()
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_constant)
    except (ValueError, UnicodeError, RecursionError):
        raise ValueError(_INVALID) from None


def _encode(value):
    try:
        raw = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise ValueError(_INVALID) from None
    if len(raw) > MAX_STATE_BYTES:
        _invalid()
    return raw


@dataclass(frozen=True, slots=True)
class WatchlistSnapshot:
    """已保存的完整偏好；字符串与tuple独占不可变，不含账户/策略身份。"""

    watchlist_id: str
    version: int
    symbols: tuple[str, ...]
    updated_at: str

    def __post_init__(self):
        _identity(self.watchlist_id)
        _version(self.version)
        _timestamp(self.updated_at)
        if type(self.symbols) is not tuple:
            _invalid()
        _symbols(self.symbols, normalize=False)

    def validated(self):
        """owner准入时重新核值；typed输入不能绕过公共协议边界。"""
        if type(self) is not WatchlistSnapshot:
            _invalid()
        return WatchlistSnapshot(self.watchlist_id, self.version,
                                 _symbols(self.symbols, normalize=False), self.updated_at)

    def state(self):
        valid = self.validated()
        return {"schema_version": SCHEMA_VERSION, "watchlist_id": valid.watchlist_id,
                "version": valid.version, "symbols": list(valid.symbols), "updated_at": valid.updated_at}

    def public(self, *, editable, reason):
        """每次创建新JSON值树；运行能力从owner传入，不从文件自报。"""
        if type(editable) is not bool:
            _invalid()
        if editable:
            if reason is not None:
                _invalid()
        else:
            if type(reason) is not str or not reason or len(reason) > MAX_REASON_BYTES:
                _invalid()
            try:
                if len(reason.encode("utf-8")) > MAX_REASON_BYTES:
                    _invalid()
            except UnicodeError:
                _invalid()
        return {**self.state(), "affects_strategy": False, "editable": editable, "reason": reason}


@dataclass(frozen=True, slots=True)
class WatchlistReplacement:
    """一次完整替换的期望版本；没有命令、审计或重放身份。"""

    watchlist_id: str
    expected_version: int
    symbols: tuple[str, ...]

    def __post_init__(self):
        _identity(self.watchlist_id)
        _version(self.expected_version)
        if type(self.symbols) is not tuple:
            _invalid()
        _symbols(self.symbols, normalize=False)

    def validated(self):
        if type(self) is not WatchlistReplacement:
            _invalid()
        return WatchlistReplacement(self.watchlist_id, self.expected_version,
                                    _symbols(self.symbols, normalize=False))


def decode_snapshot(raw):
    """有限磁盘JSON→不可变快照；坏文件保持失败，不能映射为空成功。"""
    value = _decode(raw, MAX_STATE_BYTES)
    _keys(value, _STATE_KEYS)
    if type(value["symbols"]) is not list:
        _invalid()
    return WatchlistSnapshot(value["watchlist_id"], value["version"],
                             _symbols(value["symbols"], normalize=False), value["updated_at"])


def encode_snapshot(snapshot):
    if type(snapshot) is not WatchlistSnapshot:
        _invalid()
    return _encode(snapshot.state())


def decode_replacement(raw):
    """有限PUT JSON→完整替换；原输入列表不会跨worker共享可变别名。"""
    value = _decode(raw, MAX_REQUEST_BYTES)
    _keys(value, _REQUEST_KEYS)
    if type(value["symbols"]) is not list:
        _invalid()
    return WatchlistReplacement(value["watchlist_id"], value["expected_version"],
                                _symbols(value["symbols"], normalize=True))


def encode_replacement_result(*, snapshot, previous, request):
    """返回200前核整份目标和版本关系，不能把矛盾结果投影为已保存。"""
    if (type(snapshot) is not WatchlistSnapshot or type(previous) is not WatchlistSnapshot
            or type(request) is not WatchlistReplacement):
        _invalid()
    current, old, replacement = snapshot.validated(), previous.validated(), request.validated()
    changed = old.symbols != replacement.symbols
    if (old.watchlist_id != replacement.watchlist_id or old.version != replacement.expected_version
            or current.watchlist_id != old.watchlist_id or current.symbols != replacement.symbols
            or current.version != old.version + int(changed)
            or (not changed and current.updated_at != old.updated_at)):
        _invalid()
    return _encode({"schema_version": SCHEMA_VERSION, "changed": changed,
                    "watchlist": current.public(editable=True, reason=None)})


def encode_public_snapshot(snapshot, *, editable, reason):
    """HTTP输出在同一有界编码边界生成；文件字段不拥有运行能力。"""
    if type(snapshot) is not WatchlistSnapshot:
        _invalid()
    return _encode(snapshot.public(editable=editable, reason=reason))
