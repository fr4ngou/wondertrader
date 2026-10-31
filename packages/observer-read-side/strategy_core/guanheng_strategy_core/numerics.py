"""保留普通算序的稳定正数均值；派生结果须能由有限浮点表示。"""

from fractions import Fraction
from math import fsum, isfinite
from sys import float_info

from .contracts import KernelValidationError
from .computation import checked


def finite(value: float) -> float:
    """在业务阈值判断之前拒绝不可表示结果，避免clamp把异常掩成有效值。"""
    try:
        represented = isfinite(value)
    except OverflowError:
        represented = False
    if not represented:
        raise KernelValidationError("derived_value_unrepresentable", "策略派生数值超出有限浮点表示范围")
    return value


def _divide(numerator, denominator) -> float:
    """除法异常与不可表示结果统一作为领域错误返回。"""
    try:
        result = finite(numerator / denominator)
        if result == 0 and numerator != 0:
            raise KernelValidationError("derived_value_unrepresentable", "非零策略比率下溢，无法由有限浮点表示")
        return result
    except (OverflowError, ZeroDivisionError) as exc:
        raise KernelValidationError("derived_value_unrepresentable", "策略派生数值超出有限浮点表示范围") from exc


def _exact_binary64(exact: Fraction) -> float:
    """仅极小范围调用；真实结果须可无损回写binary64，禁止舍入后跨业务阈值。"""
    result = finite(float(exact))
    if Fraction(result) != exact:
        raise KernelValidationError("derived_value_unrepresentable", "次正规策略数值无法由binary64精确表示")
    return result


def _tiny_result(result, exact_value):
    """普通normal结果保持算序；极小结果按原操作数检验精确可表示性。

    包括舍入到0及最小normal的邻界，避免先舍入中间值再授业务资格。
    精确路径的整数位宽由有限binary64输入及有界窗口共同限制。
    """
    result = finite(result)
    if abs(result) <= float_info.min:
        exact = exact_value()
        if exact and abs(exact) < Fraction(float_info.min):
            return _exact_binary64(exact)
    return result


def product(left, right) -> float:
    if left == 0 or right == 0:
        return left * right
    return _tiny_result(left * right, lambda: Fraction(left) * Fraction(right))


def add(left, right) -> float:
    if left == -right:
        return left + right
    return _tiny_result(left + right, lambda: Fraction(left) + Fraction(right))


def subtract(left, right) -> float:
    if left == right:
        return left - right
    return _tiny_result(left - right, lambda: Fraction(left) - Fraction(right))


def ratio(numerator, denominator) -> float:
    """正常范围保持原除法；次正规及最小normal交界按原操作数作精确资格检查。"""
    return _tiny_result(_divide(numerator, denominator),
                        lambda: Fraction(numerator) / Fraction(denominator))


def _qualified_mean(mean, values, largest, check=None):
    # mean >= largest/count。只有此界或已算结果进入极小范围时才分配精确有理数。
    # 原float的分母均为2的幂，窗口最长10000，求和及除count后的位宽因此有界。
    if largest > 0 and (largest < float_info.min * len(values) or mean <= float_info.min):
        exact = sum((Fraction(value) for value in checked(values, check, interval=32)), Fraction(0)) / len(values)
        if exact < Fraction(float_info.min):
            return _exact_binary64(exact)
    return mean


def positive_mean(values, *, check=None) -> float:
    """价/量同一实现；普通有限sum保持原舍入，溢出时先按最大项缩放。"""
    if not values:
        raise KernelValidationError("derived_value_unrepresentable", "计算均值缺少有效窗口")
    if check is not None:
        check()
    try:
        # 混合int/float在sum遇到浮点项时就可能溢出，必须和总和表示检查共同保护。
        total = sum(values)
        finite_total = isfinite(total)
    except OverflowError:  # Python整数总和可超出float范围，但均值仍可表示。
        finite_total = False
    largest = max(values)
    if check is not None:
        check()
    if finite_total:
        # 这里的精确参考须取原始窗口，不能先对已舍入sum/count单独授资格。
        return _qualified_mean(_divide(total, len(values)), values, largest, check)
    # 输入边界已确认各项有限且非负，缩放和均值均在[0,1]内。
    mean = finite((fsum(value / largest for value in checked(values, check, interval=32)) / len(values)) * largest)
    if mean == 0 and largest > 0:
        raise KernelValidationError("derived_value_unrepresentable", "正数策略均值下溢，无法由有限浮点表示")
    return _qualified_mean(mean, values, largest, check)
