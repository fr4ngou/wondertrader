"""读取A发布的原分析窗口；事实仍归QNA/原Reader，不维护行情或金融账本。"""
from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import timedelta
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import time

from .managed_local_process import _identity, _inspect, _json, _open_read
from .execution_strategy import CtaBridgeError, _need

_FIELDS = {'schema', 'analysis_ready', 'analysis', 'history', 'current_view', 'units',
           'input_sha256', 'native_output_sha256', 'native_identity', 'references',
           'factor_events', 'native_securities', 'selection', 'qualification'}


def _snapshot(path, deadline):
    """发布者原子换名时读取已打开的一代；同一文件原地写入属于协议错误。"""
    maximum = 32*1024*1024
    before = _inspect(path)
    _need(time.monotonic() < deadline, 'evaluation_deadline')
    with _open_read(path) as stream:
        opened = os.fstat(stream.fileno())
        _need(stat.S_ISREG(opened.st_mode) and opened.st_nlink == 1
              and not (getattr(opened, 'st_file_attributes', 0) & 0x400)
              and 0 < opened.st_size <= maximum, 'market_window_file')
        # 查验与打开之间换代时，本轮等待下一次读取，不混用两代字节。
        if (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino):
            return None
        raw = stream.read(maximum+1)
        _need(_identity(os.fstat(stream.fileno())) == _identity(opened)
              and len(raw) == opened.st_size, 'market_window_file')
    _need(time.monotonic() < deadline, 'evaluation_deadline')
    return raw


@dataclass(frozen=True)
class MarketWindowRead:
    request: object | None
    publication: dict | None
    reason: str | None


@dataclass(frozen=True)
class MarketWindowFile:
    """部署选定的源位置；每次read沿调用者原D读取一份完整快照。"""
    path: Path
    max_age_seconds: float

    @classmethod
    def from_dict(cls, value):
        _need(type(value) is dict and set(value) == {'path', 'max_age_seconds'}, 'market_window_configuration')
        path, age = value['path'], value['max_age_seconds']
        _need(type(path) is str and path and Path(path).is_absolute()
              and type(age) in (int, float) and math.isfinite(age) and 1 <= age <= 604800,
              'market_window_configuration')
        return cls(Path(path), age)

    @property
    def configuration_identity(self):
        return (str(self.path), self.max_age_seconds)

    def read(self, request, *, deadline):
        """保留C唯一wire解码；源文件只替换三项市场事实，周期等由原调用者提供。"""
        from guanheng_strategy_core.contracts import canonical_bytes
        from guanheng_strategy_v1 import RetainedInput
        try:
            raw = _snapshot(self.path, deadline)
        except OSError:
            return MarketWindowRead(None, None, 'market_window_unavailable')
        if raw is None:
            return MarketWindowRead(None, None, 'market_window_unavailable')
        value = _json(raw)
        _need(type(value) is dict and set(value) == _FIELDS
              and value['schema'] == 'guanheng.qmt-native-analysis-window.v1'
              and value['analysis_ready'] is True
              and value['units'] == {'price': 'CNY', 'volume': 'lot', 'amount': 'unknown'}, 'market_window_protocol')
        # 只编码少量非行情字段；完整市场数组已经来自本次原JSON，不另复制旧窗口。
        small = {field.name: getattr(request, field.name) for field in fields(RetainedInput)
                 if field.name not in ('history', 'analysis', 'current_view')}
        wire = json.loads(canonical_bytes(small, max_bytes=65536))
        wire.update({key: value[key] for key in ('history', 'analysis', 'current_view')})
        updated = RetainedInput.from_dict(wire)
        publication = dict(schema='guanheng.retained-market-window-observation.v1',
            publication_sha256=hashlib.sha256(raw).hexdigest(),
            source_revision=updated.history.source_revision, factor_revision=updated.history.factor_revision,
            basis_date=updated.analysis.basis_date.isoformat(), known_at=updated.analysis.known_at.isoformat(),
            received_at=updated.current_view.received_at.isoformat(), units=value['units'])
        _need(updated.current_view.received_at <= request.decision_cutoff
              and updated.analysis.known_at <= updated.current_view.received_at, 'market_window_future')
        _need(time.monotonic() < deadline, 'evaluation_deadline')
        if request.decision_cutoff >= updated.current_view.received_at+timedelta(seconds=self.max_age_seconds):
            return MarketWindowRead(None, publication, 'market_window_stale')
        return MarketWindowRead(updated, publication, None)


def native_history_matches(request, mapping, context, check):
    """核声明日期窗；一条窗口外在途bar不进入纯核，缺失/冲突交调用者等待。"""
    by_symbol = {symbol: [] for symbol in mapping}
    for row in request.history.observations:
        if row.symbol not in by_symbol:
            return False
        by_symbol[row.symbol].append(row)
    for symbol, code in mapping.items():
        expected = by_symbol[symbol]
        if not expected or len(expected) > 4096:
            return False
        first = int(expected[0].trade_date.strftime('%Y%m%d'))
        last = int(expected[-1].trade_date.strftime('%Y%m%d'))
        try:
            actual = context.bars(code, 'd1', min(4096, len(expected)+1))
        except CtaBridgeError as error:
            if str(error) != 'native_read_failed':
                raise
            # Reader在发布交接或缺数据时返回不可用；沿本轮原D等待，
            # 不推进数量状态或setter，下一回调重新核对同一公开窗口。
            check()
            return False
        check()
        actual = tuple(row for row in actual if first <= row.date <= last)
        if len(actual) != len(expected):
            return False
        for row, bar in zip(actual, expected, strict=True):
            check()
            if ((row.date, row.open, row.high, row.low, row.close, row.volume, row.money)
                    != (int(bar.trade_date.strftime('%Y%m%d')), bar.open, bar.high, bar.low,
                        bar.close, bar.volume, bar.amount)):
                return False
    return True
