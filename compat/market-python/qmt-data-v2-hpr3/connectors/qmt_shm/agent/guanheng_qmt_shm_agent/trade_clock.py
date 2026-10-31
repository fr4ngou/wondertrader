# -*- coding: utf-8 -*-
"""QST-R12：已核同机 Windows uptime 毫秒域的纯转换与读取。

只接受明确 GetTickCount64 的目标身份；不回退 QPC、UTC 或外部 DLL。
导入不读取时钟或 clock_info，构造才核身份。部署仍须绑定实际解释器与
DLL 资格；本模块不授交易权限，也不把计数读取视为 SDK 调用完成证明。
"""
import math
import sys
import time


CLOCK_SCHEMA = 'qmt.win-uptime-ms.v1'
_MAX_SECONDS = 2 ** 32
_MAX_MILLISECONDS = _MAX_SECONDS * 1000
_MILLISECOND_TOLERANCE = 0.01


class TradeClockError(ValueError):
    """只携带固定安全码，不包含注入时钟或来源异常正文。"""


def _fail(code):
    raise TradeClockError(code) from None


def _number(value, *, positive):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value) and (value > 0 if positive else value >= 0)
    except (OverflowError, ValueError):
        return False


def deadline_milliseconds(seconds):
    """原业务截止秒向下取整为共享整数毫秒；不新增等待窗口。

    输入必须有限、正且不超过 2**32 秒。小于一毫秒的正输入返回 0，
    交给调用方按已到期处理；不得为得到正数而加一或重新计算 now+TTL。
    """
    if not _number(seconds, positive=True) or seconds > _MAX_SECONDS:
        _fail('invalid_deadline')
    return math.floor(seconds * 1000)


def deadline_seconds(milliseconds):
    """共享正整数毫秒转秒供 kernel 检查同一原截止；不读取当前时钟。"""
    if (type(milliseconds) is not int
            or not 0 < milliseconds <= _MAX_MILLISECONDS):
        _fail('invalid_deadline')
    return milliseconds / 1000.0


class SharedUptimeClock(object):
    """可信目标/测试注入的计数读取器，无缓存或跨调用顺序状态。

    默认依赖 builtin time 与 sys。注入仅供可信 owner/纯测试；构造要求
    win32、精确 GetTickCount64()、monotonic=True、adjustable=False 和
    有限正 resolution<=1 秒。每次读取恰调用源函数一次；并发调用独立
    读取纯计数，不声称跨线程完成顺序等于计数采样顺序。
    """
    def __init__(self, monotonic=None, get_clock_info=None, platform=None):
        monotonic = time.monotonic if monotonic is None else monotonic
        get_clock_info = time.get_clock_info if get_clock_info is None else get_clock_info
        platform = sys.platform if platform is None else platform
        if (type(platform) is not str or platform != 'win32'
                or not callable(monotonic) or not callable(get_clock_info)):
            _fail('invalid_clock_configuration')
        try:
            info = get_clock_info('monotonic')
            implementation = info.implementation
            is_monotonic = info.monotonic
            adjustable = info.adjustable
            resolution = info.resolution
        except BaseException:
            _fail('invalid_clock_configuration')
        if (type(implementation) is not str or implementation != 'GetTickCount64()'
                or is_monotonic is not True or adjustable is not False
                or not _number(resolution, positive=True) or resolution > 1):
            _fail('invalid_clock_configuration')
        self._monotonic = monotonic

    def milliseconds(self):
        """还原已证整数毫秒计数；偏离整毫秒超过 0.01ms 时拒绝。

        round 只用于恢复该来源本就离散的计数；业务截止转换单独 floor，
        两者职责不同。bool、非有限、负值和超过 2**32 秒均拒绝。
        """
        try:
            seconds = self._monotonic()
        except BaseException:
            _fail('clock_unavailable')
        if not _number(seconds, positive=False) or seconds > _MAX_SECONDS:
            _fail('invalid_clock_value')
        scaled = seconds * 1000
        restored = round(scaled)
        if abs(scaled - restored) > _MILLISECOND_TOLERANCE:
            _fail('invalid_clock_value')
        return restored

    def seconds(self):
        """以一次源读取的整数毫秒重建秒值，供原业务 D 同域比较。"""
        return self.milliseconds() / 1000.0
