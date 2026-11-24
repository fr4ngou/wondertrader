"""归属账内部金额：整数分及费用产生的有限十进制分数，精确且不借用 Decimal 上下文。"""
from decimal import Decimal
from fractions import Fraction


def decimal_value(value, *, min_places=0):
    """精确构造有限十进制；调用者负责金融范围及正负资格。"""
    value = Fraction(value)
    numerator, denominator = value.numerator, value.denominator
    twos = fives = 0
    while denominator % 2 == 0:
        denominator //= 2
        twos += 1
    while denominator % 5 == 0:
        denominator //= 5
        fives += 1
    if denominator != 1:
        raise ValueError('money_precision')
    places = max(twos, fives, min_places)
    coefficient = abs(numerator) * 2 ** (places-twos) * 5 ** (places-fives)
    return Decimal((int(numerator < 0), tuple(map(int, str(coefficient))), -places))


def encode_fraction(value):
    """持久金额使用规范有限十进制字符串；原整数分保持 JSON 整数。"""
    return format(decimal_value(value), 'f')


def restore_money(value):
    """仅用于 v4 指定金额字段；旧整数分可原样读取。"""
    if type(value) is int or type(value) is Fraction:
        return value
    if type(value) is not str or not 0 < len(value) <= 160:
        raise ValueError('storage_invalid')
    number = Decimal(value)
    if not number.is_finite() or encode_fraction(Fraction(number)) != value:
        raise ValueError('storage_invalid')
    return Fraction(number)


def restore_record(kind, value):
    """记录仍按原实体 ID 懒加载，只转换该实体拥有的费用字段。"""
    for key in {'groups': ('fee_paid',), 'fills': ('fee',)}.get(kind, ()):
        if value[key] is not None:
            value[key] = restore_money(value[key])
    return value
