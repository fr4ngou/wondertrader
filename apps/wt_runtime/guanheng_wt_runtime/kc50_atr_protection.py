"""七只 ETF 收复确认版的持仓 ATR 退出，成交与持仓仍取 WT。"""
from statistics import median


def protection_line(close, atr, multiplier, previous_peak=None, previous_level=None):
    """按实际持仓周期递推原价最高收盘和只升的保护线，单位均为元/份。"""
    peak = max(close, close if previous_peak is None else previous_peak)
    level = max(0 if previous_level is None else previous_level, peak - atr * multiplier)
    return peak, level


class AtrProtection:
    def __init__(self, history, activation):
        self.observations = {}
        self.ready = {}
        self.multiplier = {}
        self.peaks = {}
        self.levels = {}
        for code, rows in history.items():
            observations = dict(self._observations(rows))
            self.observations[code] = observations
            ratios = [(day, atr / close) for day, (close, atr) in observations.items() if atr is not None]
            seed = [ratio for day, ratio in ratios if day < activation]
            ready = activation
            if len(seed) < 20:
                if len(ratios) <= 20:
                    continue
                ready = ratios[20][0]
                seed = [ratio for _, ratio in ratios[:20]]
            typical = median(seed)
            if typical > 0:
                self.ready[code] = ready
                self.multiplier[code] = 0.10 / typical

    @staticmethod
    def _observations(rows):
        previous_close = atr = None
        seed = []
        for row in rows:
            close = row['close']
            if previous_close is not None:
                true_range = max(row['high'] - row['low'], abs(row['high'] - previous_close),
                                 abs(row['low'] - previous_close))
                if atr is None:
                    seed.append(true_range)
                    if len(seed) == 14:
                        atr = sum(seed) / 14
                else:
                    atr += (true_range - atr) / 14
            yield row['date'], (close, atr)
            previous_close = close

    def exits(self, day, positions, signals, exiting):
        """闭合日用实际持仓更新保护线，原买卖信号和未完成退出优先。"""
        actions = {signal['code']: signal['action'] for signal in signals}
        for code, quantity in positions.items():
            if not quantity or actions.get(code) == 'BUY':
                self.peaks.pop(code, None)
                self.levels.pop(code, None)
            if not quantity or code in actions or code in exiting:
                continue
            observation = self.observations[code].get(day)
            if observation is None:
                continue
            close, atr = observation
            peak = self.peaks[code] = max(self.peaks.get(code, close), close)
            if code not in self.ready or day < self.ready[code] or atr is None:
                continue
            _, level = protection_line(close, atr, self.multiplier[code], peak, self.levels.get(code))
            self.levels[code] = level
            if close <= level:
                yield dict(code=code, action='SELL', reason=f'{code} {close:.4f}≤{level:.4f}')
