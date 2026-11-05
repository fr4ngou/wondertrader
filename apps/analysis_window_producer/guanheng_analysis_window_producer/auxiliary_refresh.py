"""WT发布Owner内的有界辅助更新：近期修订、历史缺口及持久退避共用一条链。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import time
from typing import TypedDict

from .auxiliary_store import SOURCES, aware_time, read_capture, validate_key
from .official_auxiliary import capture, parse_source, source_failure
from .source import write_json


class RefreshState(TypedDict):
    """每来源/日期的持久观察，不承担任何交易或金融状态。"""
    checked_at: str  # 最近尝试时刻，带时区；失败同样保留。
    next_retry_at: str | None  # 真实下次重试下界；成功为空，由修订周期控制。
    failures: int  # 连续失败次数，最多10，用于最长一小时的指数退避。
    error: str | None  # 有限稳定原因码；成功为空，不保存服务器正文。
    error_type: str | None  # 脱敏异常类别；与来源/日期共同定位失败。


class SourceCoverage(TypedDict):
    """来源覆盖摘要；逐日详情归COVERAGE.json，字段生效另由纯派生报告给出。"""
    expected: int  # 当前实际行情窗口中的应检查来源日期数。
    captured: int  # 已核原文且有规范值的日期数，不表示历史可知或已生效。
    missing: int  # 当前日期范围缺少有效原件的数量。
    last_date: str | None  # 最新有效原件统计日，无数据为空。


class AuxiliaryRefresh:
    """一个WT owner串行持有；网络失败留下日期和稳定原因，原件保持可读。"""

    def __init__(self, directory, *, seed_directory=None):
        self.directory = Path(directory).resolve()
        self.seed_directory = Path(seed_directory).resolve(strict=True) if seed_directory is not None else None
        if self.seed_directory == self.directory:
            raise ValueError('auxiliary_seed_must_be_readonly')
        self.path = self.directory / 'CONTINUITY.json'
        self.state = {}  # 来源/日期对应的重试与核查时钟；仅本Owner写入。
        self.directory.mkdir(parents=True, exist_ok=True)
        from guanheng_wt_runtime.__main__ import _InstanceLease
        self._lease = _InstanceLease(self.directory, 'auxiliary')
        self._lease.__enter__()
        self._closed = False  # 关闭在原AWP线程join后释放，共用WT原生进程租约适配。
        try:
            if self.path.exists():
                if self.path.stat().st_size > 16 * 1024 * 1024:
                    raise ValueError('auxiliary_continuity_capacity')
                value = json.loads(self.path.read_bytes())
                if (value.get('schema') != 'guanheng.auxiliary-continuity.v1'
                        or type(value.get('sources')) is not dict or len(value['sources']) > 20480):
                    raise ValueError('auxiliary_continuity_identity')
                self.state = value['sources']
                for key, item in self.state.items():
                    source, day = key.split('/')
                    validate_key(source, day)
                    aware_time(item['checked_at'])
                    if item.get('next_retry_at') is not None:
                        aware_time(item['next_retry_at'])
                    if type(item.get('failures')) is not int or not 0 <= item['failures'] <= 10:
                        raise ValueError('auxiliary_continuity_identity')
        except BaseException:
            self.close()
            raise

    def close(self):
        """原Owner停止准入并join后释放；失败与重复关闭沿同一租约收口。"""
        if not self._closed:
            self._lease.__exit__(None, None, None)
            self._closed = True

    def _record(self, source, day):
        record = read_capture(self.directory, source, day, parse_source)
        if record is None and self.seed_directory is not None:
            record = read_capture(self.seed_directory, source, day, parse_source)
        return record

    def _save(self):
        write_json(self.path, dict(schema='guanheng.auxiliary-continuity.v1', sources=self.state))

    def refresh(self, days, symbols, *, deadline, check, max_requests=10):
        """每轮最多十次网络读；缺口自动轮转，近期五日每小时检查修订。

        check由原WT owner提供，沿刷新和关闭绝对截止执行；本模块没有独立线程。
        近期64日优先预热，长历史缺口由同一有界轮次渐进处理。
        """
        days = sorted(set(days))
        if self._closed or not days or len(days) > 4096 or type(max_requests) is not int or not 1 <= max_requests <= 100:
            raise ValueError('auxiliary_refresh_capacity')
        active = {source + '/' + day for source in SOURCES for day in days}
        self.state = {key: value for key, value in self.state.items() if key in active}
        now = datetime.now(timezone.utc)
        pending = []
        present = {source: [] for source in SOURCES}
        for day in reversed(days):
            check()
            for source in SOURCES:
                key = source + '/' + day
                record = self._record(source, day)
                if record is not None:
                    present[source].append(day)
                previous = self.state.get(key, {})
                retry = previous.get('next_retry_at')
                if retry is not None and aware_time(retry) > now:
                    continue
                checked = previous.get('checked_at')
                if checked is None and record is not None:
                    checked = record.get('checked_at', record['received_at'])
                interval = 3600 if day in days[-5:] else 86400
                if record is not None and checked is not None and (now - aware_time(checked)).total_seconds() < interval:
                    continue
                # 近期修订优先于长期缺口，避免失效旧日期持续重试使修订永久饥饿。
                rank = (0 if day in days[-2:] and record is None else
                        1 if day in days[-5:] and record is not None else
                        2 if day in days[-64:] and record is None else
                        3 if record is None else 4)
                pending.append((rank, previous.get('checked_at', ''), day, source))
        pending.sort(key=lambda item: (item[0], item[1], -int(item[2].replace('-', '')), item[3]))
        attempted = 0
        for _, _, day, source in pending:
            check()
            if attempted >= max_requests or deadline - time.monotonic() < 1:
                break
            key = source + '/' + day
            previous = self.state.get(key, {})
            attempted += 1
            try:
                record = capture(source, day, self.directory, symbols,
                    timeout=min(3., max(.1, deadline - time.monotonic())), refresh=True,
                    seed_root=self.seed_directory)
            except Exception as error:
                # 网络异常正文可能含URL和服务器文本；只保存稳定分类和异常类型。
                failure = source_failure(error)
                reason = failure['reason']
                failures = min(10, previous.get('failures', 0) + 1)
                retry_seconds = min(3600, (300 if reason == 'auxiliary_source_not_published' else 60) * 2 ** (failures - 1))
                self.state[key] = RefreshState(checked_at=datetime.now(timezone.utc).isoformat(),
                    next_retry_at=(datetime.now(timezone.utc) + timedelta(seconds=retry_seconds)).isoformat(),
                    failures=failures, error=reason, error_type=failure['type'])
            else:
                self.state[key] = RefreshState(checked_at=record['checked_at'], next_retry_at=None,
                    failures=0, error=None, error_type=None)
                if day not in present[source]:
                    present[source].append(day)
            self._save()
        coverage = {source: SourceCoverage(expected=len(days), captured=len(present[source]),
                    missing=len(days) - len(present[source]), last_date=max(present[source], default=None))
                    for source in SOURCES}
        errors = [dict(source=key.split('/')[0], day=key.split('/')[1], **value)
                  for key, value in sorted(self.state.items()) if value.get('error') is not None]
        write_json(self.directory / 'COVERAGE.json', dict(schema='guanheng.auxiliary-source-coverage.v1',
            checked_at=datetime.now(timezone.utc).isoformat(), sources=coverage, errors=errors,
            present_dates={source: sorted(found) for source, found in present.items()}))
        return dict(sources=coverage, requests=attempted, pending=len(pending) - attempted,
                    source_error_count=len(errors), errors=errors[:20],
                    coverage_file=str(self.directory / 'COVERAGE.json'))
