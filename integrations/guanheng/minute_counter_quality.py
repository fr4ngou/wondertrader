"""原生分钟量额的来源资格；保留原数值，独立于文件/身份/ABI错误。"""
import math


class NegativeMinuteCounter(ValueError):
    """仅表示原分钟存在真实负量/负额，允许原官方恢复链接手该源缺口。"""
    def __init__(self, minute):
        self.minute = minute  # 原分钟右端YYYYMMDDHHMM，仅定位，不提供替代值。
        self.reason_code = 'native_minute_negative_counter'  # 固定质量原因，不包含原路径或异常正文。
        super().__init__(self.reason_code)


def require_minute_counters(volume, amount, minute):
    """仅接收实际原值；格式/非有限仍为独立错误，负量额保留明确质量分类。"""
    if any(type(value) not in (int, float) or not math.isfinite(value) for value in (volume, amount)):
        raise ValueError('minute_counter_format_or_nonfinite')
    if volume < 0 or amount < 0:
        raise NegativeMinuteCounter(minute)


def negative_counter_count(bars):
    """统计原Reader返回行中的量额质量失败；不删除行、不填值，不创建聚合状态。"""
    count = 0
    for row in bars:
        try:
            require_minute_counters(row['volume'], row['amount'], row['minute'])
        except NegativeMinuteCounter:
            count += 1
    return count
