"""来源四价范围的独立质量结论；不改价、不判断成交或分钟边界。"""
from __future__ import annotations

STATUSES = ("consistent", "open_outside_range", "close_outside_range",
            "open_close_outside_range", "inverted_range")


def price_range_status(opening, high, low, close):
    """调用者先核有限正价；此处只分类四价关系，供保存与消费者共同使用。"""
    if high < low:
        return "inverted_range"
    opening_outside = not low <= opening <= high
    close_outside = not low <= close <= high
    if opening_outside and close_outside:
        return "open_close_outside_range"
    if opening_outside:
        return "open_outside_range"
    if close_outside:
        return "close_outside_range"
    return "consistent"


class PriceRangeQuality:
    """流式计数和至多8个异常标签；完整记录仍在原输入与有SHA的DSB中。"""
    def __init__(self):
        self.counts = dict.fromkeys(STATUSES, 0)
        self.labels = []
        self.checked = 0

    def observe(self, label, opening, high, low, close):
        status = price_range_status(opening, high, low, close)
        self.checked += 1
        self.counts[status] += 1
        if status != "consistent" and len(self.labels) < 8:
            self.labels.append(label)

    def result(self):
        return dict(schema="qmt.source-price-range.v1", checked_rows=self.checked,
                    inconsistent_rows=self.checked-self.counts["consistent"],
                    counts=dict(self.counts), first_labels=list(self.labels))


def summarize_source_bars(bars):
    quality = PriceRangeQuality()
    for bar in bars:
        quality.observe(bar.occurred_at.isoformat(), bar.open, bar.high, bar.low, bar.close)
    return quality.result()


def validate_price_quality(value, expected_count, *, allow_consistent=False):
    """校验有界摘要；旧异常声明须有异常，完整归档显式允许零异常。"""
    if type(allow_consistent)is not bool:raise ValueError("价格质量校验模式不合格")
    fields = {"schema", "checked_rows", "inconsistent_rows", "counts", "first_labels"}
    if (type(value) is not dict or set(value) != fields
            or value["schema"] != "qmt.source-price-range.v1"
            or type(value["checked_rows"]) is not int or value["checked_rows"] != expected_count
            or type(value["inconsistent_rows"]) is not int
            or not (0 if allow_consistent else 1) <= value["inconsistent_rows"] <= expected_count
            or type(value["counts"]) is not dict or set(value["counts"]) != set(STATUSES)
            or any(type(count) is not int or count < 0 for count in value["counts"].values())
            or sum(value["counts"].values()) != expected_count
            or expected_count-value["counts"]["consistent"] != value["inconsistent_rows"]
            or type(value["first_labels"]) is not list
            or len(value["first_labels"]) != min(8, value["inconsistent_rows"])
            or any(type(label) is not str or len(label) != 25 for label in value["first_labels"])):
        raise ValueError("来源价格质量摘要不合格")
    return value
