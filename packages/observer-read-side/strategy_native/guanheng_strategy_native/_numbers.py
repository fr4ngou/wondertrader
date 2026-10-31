"""有界十进制解析与精确有理数；所有运算独立于 Decimal 全局上下文。"""

from decimal import Decimal, InvalidOperation
from fractions import Fraction
from functools import lru_cache
import re
import sys


MAX_NATIVE_INTEGER = 2**53 - 1
_DECIMAL = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE]([+-]?[0-9]+))?\Z")
# 与原ord规则相同的码点集合；由正则引擎扫描有界字符串，避免每次
# 不可变值准入都为每个字符建立Python生成器调用。错误顺序保持。
_CONTROL_TEXT = re.compile(r"[\x00-\x1f\x7f]")
_CACHE_DECIMAL = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?\Z")


class QuantityError(ValueError):
    """输入或恢复状态不满足纯转换契约；原生状态保持由调用者拥有。"""


def text(value: object, name: str, maximum: int = 256) -> str:
    if type(value) is not str or not 1 <= len(value) <= maximum:
        raise QuantityError(f"{name}: invalid text length/type")
    if not value.strip():
        raise QuantityError(f"{name}: blank text")
    if _CONTROL_TEXT.search(value) is not None:
        raise QuantityError(f"{name}: control character")
    return value


def _number(value: object, name: str, *, signed: bool = False) -> str:
    if type(value) not in (str, int, Decimal):
        raise QuantityError(f"{name}: decimal string, int or Decimal required")
    if type(value) is int and value.bit_length() > 256:
        raise QuantityError(f"{name}: integer representation budget")
    # CPython Decimal 的coefficient占用随精度增加；先限制对象占用再展开字符串。
    if type(value) is Decimal and sys.getsizeof(value) > 1024:
        raise QuantityError(f"{name}: Decimal representation budget")
    raw = str(value)
    match = _DECIMAL.fullmatch(raw) if len(raw) <= 256 else None
    if match is None:
        raise QuantityError(f"{name}: invalid decimal representation")
    if match.group(1) is not None and abs(int(match.group(1))) > 64:
        raise QuantityError(f"{name}: decimal exponent budget")
    try:
        decimal = Decimal(raw)
    except InvalidOperation as exc:
        raise QuantityError(f"{name}: decimal exponent budget") from exc
    sign, digits, exponent = decimal.as_tuple()
    # 规范化的整数会展开e64；精度按去掉尾零的系数计，保证冻结值可重新构造。
    while len(digits) > 1 and digits[-1] == 0:
        digits = digits[:-1]
        exponent += 1
    if len(digits) > 64 or abs(exponent) > 64:
        raise QuantityError(f"{name}: decimal precision/exponent budget")
    if not signed and decimal < 0:
        raise QuantityError(f"{name}: negative value")
    # format(..., 'f') does not round; accepted exponent/precision bound output.
    normalized = format(decimal, "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    return "0" if decimal == 0 else normalized


@lru_cache(maxsize=2048, typed=True)
def _cached_number(value, name, signed):
    return _number(value, name, signed=signed)


def number(value: object, name: str, *, signed: bool = False) -> str:
    """有界复用成功的纯标量规范化；字段名、符号规则和精确类型进入键。

    原解析仍是唯一准入，异常不缓存。其余类型及超长字段名沿原路径，
    避免缓存键保留任意对象或改变原错误/Decimal上下文语义。
    """
    if (type(name) is str and len(name) <= 256 and type(signed) is bool
            and ((type(value) is str and len(value) <= 256)
                 or (type(value) is int and value.bit_length() <= 256))):
        return _cached_number(value, name, signed)
    return _number(value, name, signed=signed)


def _rational(value: str) -> Fraction:
    return Fraction(Decimal(value))


@lru_cache(maxsize=2048)
def _cached_rational(value):
    return _rational(value)


def rational(value: str) -> Fraction:
    """仅复用短有限十进制的原转换；每次返回独立Fraction，隔离可变私有属性。

    指数、其他类型及长文本继续原实现；缓存值的分子/分母大小由128字符
    十进制键界定，成功缓存各限2048项，不保存持仓、资金或报告事实。
    """
    if type(value) is str and len(value) <= 128 and _CACHE_DECIMAL.fullmatch(value) is not None:
        return Fraction(_cached_rational(value))
    return _rational(value)


def integer(value: object, name: str, maximum: int = MAX_NATIVE_INTEGER) -> int:
    if type(value) is not int or not 0 <= value <= maximum:
        raise QuantityError(f"{name}: nonnegative exact native integer required")
    return value


def rows(value: object, row_type: type, name: str) -> tuple:
    if type(value) is not tuple or not 1 <= len(value) <= 8:
        raise QuantityError(f"{name}: tuple of 1..8 complete rows required")
    if any(type(row) is not row_type for row in value):
        raise QuantityError(f"{name}: invalid row type")
    symbols = tuple(row.symbol for row in value)
    if len(set(symbols)) != len(symbols):
        raise QuantityError(f"{name}: duplicate execution symbol")
    return tuple(sorted(value, key=lambda row: row.symbol))
