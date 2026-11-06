"""已准入QST原计数的有限观察；不筛行情、不换算、不参与WT聚合。"""
from collections import deque


class QuoteCounterObservation:
    """由QuoteCollection原锁保护；只保配置名册的末笔和最近16个修订样本。"""
    def __init__(self, symbols):
        self.previous = dict.fromkeys(symbols)  # 固定原QST集合，每证券一个(time,volume,amount)副本。
        self.counts = dict(amount_regressions=0, volume_regressions=0,
                           source_time_regressions=0)  # 原接收顺序的事件数；同笔可命中多类。
        self.recent = deque(maxlen=16)  # 原计数修订的有限样本，无全量报价/历史积累。
        self.observed = 0  # 已观察的原QST证券记录数，不证明Writer已接收或分钟完整。

    def observe(self, ticks, kind):
        """输入由原Receiver校验；按原接收顺序观察，始终保持原ticks对象与数值。"""
        for symbol, row in ticks.items():
            if symbol not in self.previous:
                continue  # 诊断不改变原接收/原生范围校验；不为异常外来身份扩容。
            current = row['time'], row['volume'], row['amount']
            previous = self.previous[symbol]
            self.previous[symbol] = current
            self.observed += 1
            if previous is None:
                continue
            same_day = ((current[0] + 28800000) // 86400000
                        == (previous[0] + 28800000) // 86400000)
            reasons = []
            for name, happened in (
                    ('source_time_regressions', current[0] < previous[0]),
                    ('volume_regressions', same_day and current[1] < previous[1]),
                    ('amount_regressions', same_day and current[2] < previous[2])):
                if happened:
                    self.counts[name] += 1
                    reasons.append(name)
            if reasons:
                self.recent.append(dict(
                    symbol=symbol,  # 原QMT完整市场代码，不按六位代码合并。
                    kind=kind if kind in ('snapshot', 'incremental') else 'other',  # 原QST交接种类。
                    reasons=reasons,  # 固定原因枚举；同笔计数可同时修订或倒序。
                    previous_time_ms=previous[0], time_ms=current[0],  # 两笔原epoch毫秒，未合成+200ms。
                    previous_volume=previous[1], volume=current[1],  # 原SDK累计量，单位沿原profile。
                    previous_amount=previous[2], amount=current[2]))  # 原SDK累计额，不加offset或钳零。

    def snapshot(self):
        """有限市场数据摘录；不含凭据、路径、账户或其他完整SDK报价字段。"""
        return dict(
            observed_ticks=self.observed,  # 原到达记录计数，与Writer成功/归档资格分别表达。
            counts=dict(self.counts),  # 各固定修订原因的累计数量，不作为交易或接收门禁。
            recent=[dict(row, reasons=list(row['reasons'])) for row in self.recent])  # 最多16条原计数样本。
