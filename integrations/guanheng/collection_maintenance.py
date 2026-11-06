"""原采集管理循环的分钟覆盖/闭合日恢复；行情接收线程继续仅交付原Writer。"""
from collections import Counter, deque
from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
import threading
import time

from guanheng_qmt_shm_agent.protocol import canonical, decode
from ..guanheng_market_client import API_VERSION
from .collection_minute_reader import CollectionMinuteReader
from .market_generation import read_fixed, read_generation
from .security_reference import _descriptor, _reference_catalog, _calendar
from .source_history_transport import require
from .source_history_reads import retained_resume_state

ZONE = timezone(timedelta(hours=8))


def metadata(configuration):
    """消费资料owner原固定引用或原market-current，不调用Source/capture。"""
    require(type(configuration) is dict)
    if set(configuration) == {'current_file'}:
        pointer, unused = read_generation(configuration['current_file'])
        descriptor = pointer['configuration']
        value = decode(read_fixed(descriptor['path'], maximum=16777216, identity=descriptor['sha256']))
        require(value['mode'] == 'source-market-snapshot')
        snapshot = _descriptor(value['snapshot'], 16777216)
        for key in ('security_reference', 'calendar'):
            require(value[key]['sha256'] == snapshot['provenance'][key + '_sha256'])
        reference, calendar = value['security_reference'], value['calendar']
    else:
        require(set(configuration) == {'reference', 'calendar'})
        reference, calendar = configuration['reference'], configuration['calendar']
    original = _descriptor(reference, 16777216)
    if original.get('schema') == 'guanheng.security-reference.v3':
        reference = original['provenance']['current_reference']
        original = _descriptor(reference, 16777216)
    return _reference_catalog(original), _calendar(_descriptor(calendar, 1048576)), reference, calendar


class MinuteCollectionMaintenance:
    """创建线程单owner；原准备收据拥有副作用身份，本对象只保留可重建的进度。"""

    def __init__(self, configuration, coverage, *, clock=time.monotonic, wall_clock=time.time):
        self.owner = threading.get_ident()  # 原采集管理线程；原生句柄和补缺调用都在此线程。
        self.clock, self.wall_clock = clock, wall_clock  # 推进间隔用单调时钟，业务日期用北京时间。
        self.coverage = coverage  # 原成功报价纯时间投影，不由本对象修改订阅。
        self.producer = None  # 原SourcePreparingMarket，唯一写owner及原请求身份所有者。
        self.reader = None  # 当前批次标准Reader；关闭未确认时保持本owner强引用。
        self.closed = False  # close成功后不再推进。
        self.rows = {}  # 每证券/日期的可重建覆盖投影，价格留在原Reader/Importer。
        self.jobs = deque()  # 缺口选择，仅含证券/日期，不制造来源命令或请求ID。
        self.queued = set()  # 同轮去重，最大为当前证券数乘日期数。
        self.retry_at = {}  # 未完窗口的下次观察时点；到期仍沿原请求，与新窗口轮流推进。
        self.prefer_retry = True  # 两类队列均可推进时轮流选择，慢失败原请求不会长期抢占未尝试窗口。
        self.prefer_retained_resume = True  # 原读取交接与窗口工作并存时交替，历史责任不会饿死新窗口。
        self.symbols = []  # 本次原生产base支持的标准代码；资料新增只产生订阅差异。
        self.cursor = 0  # 可重建扫描游标；不属于来源完成事实。
        self.dates = ()  # 原官方日历确认的闭合日及当天。
        self.next_step = 0.  # 原管理循环下一次允许推进的单调时刻。
        self.reference_sha = None  # 最近成功资料原件SHA，失败时原成功名册保持。
        self.reference_error = None  # 固定失败类型，不保存来源异常正文。
        self.cycle = 0  # 本进程完成扫描轮数，不作为历史覆盖资格。
        self.last_error_type = None  # 可重试观察失败类型；原生关闭失败向外层收束。
        self.retained_read_resume = retained_resume_state('not_scanned')  # 原已派发读取交接进度，独立于滚动分钟日期。
        try:
            require(type(configuration) is dict and set(configuration) == {
                'schema', 'producer', 'metadata', 'lookback_trading_days', 'batch_size',
                'interval_seconds', 'retry_seconds', 'priority_symbols'}
                and configuration['schema'] == 'qmt.collection-maintenance.v1')
            c = decode(canonical(configuration))
            for key, maximum in (('lookback_trading_days', 20), ('batch_size', 64)):
                require(type(c[key]) is int and 1 <= c[key] <= maximum)
            for key in ('interval_seconds', 'retry_seconds'):
                require(type(c[key]) in (int, float) and .1 <= c[key] <= 3600)
            require(type(c['priority_symbols']) is list and len(c['priority_symbols']) <= 10000
                    and len(set(c['priority_symbols'])) == len(c['priority_symbols']))
            descriptor = c['producer']
            require(type(descriptor) is dict and set(descriptor) == {'path', 'sha256'}
                    and Path(descriptor['path']).is_absolute())
            producer = decode(read_fixed(descriptor['path'], maximum=16777216, identity=descriptor['sha256']))
            require(producer['mode'] == 'source-preparing'
                    and producer['preparation']['partitioned_receipts'] is True)
            self.c = c  # 本实例固定维护策略及原producer描述符。
            self.producer_configuration = producer  # 共享原生产配置，公开读方据此核同一身份。
            from .source_history_preparation import SourcePreparingMarket
            self.producer = SourcePreparingMarket(producer)
            base = self.producer.base
            require(base._minute_native is not None)
            self.profile = base._minute_native  # 原标准Reader全部固定制品/基础资料身份。
            self.codes = dict(base._minute_codes)  # 原base已验证的证券→标准代码，未接入类别保持缺项。
            priority = c['priority_symbols']
            require(all(symbol in self.codes for symbol in priority))
            self.symbols = priority + sorted(set(self.codes) - set(priority))
            self._refresh_metadata()
        except BaseException:
            self.close()
            raise

    def _refresh_metadata(self):
        try:
            reference, calendar, reference_descriptor, calendar_descriptor = metadata(self.c['metadata'])
            if calendar_descriptor['sha256'] != getattr(self, 'calendar_sha', None):
                from guanheng_market_client.exchange_calendar import official_calendar
                calendar_rows, unused = official_calendar(calendar)
                open_dates = tuple(r['date'] for r in calendar_rows if r['is_open'] == 1)
            else:
                open_dates = self.open_dates
            self.coverage.adopt_reference(reference)
            self.reference_sha = reference_descriptor['sha256']
            self.calendar = calendar  # 原日历声明及验证摘要；交易日算法复用既有模块。
            self.calendar_sha = calendar_descriptor['sha256']
            self.open_dates = open_dates  # 同一已验证日历的纯日期投影；每批扫描复用，不重复遍历多年日历。
            self.reference_error = None
        except (OSError, ValueError, KeyError, TypeError) as error:
            self.coverage.reference_waiting('unavailable')
            self.reference_error = type(error).__name__
            if not hasattr(self, 'calendar'):
                return False
        return True

    def _days(self, now):
        today = now.date().isoformat()
        require(self.calendar['coverage_start'] <= today <= self.calendar['coverage_end'])
        previous = [day for day in self.open_dates if day < today]
        require(previous)
        dates = previous[-self.c['lookback_trading_days']:]
        if today in self.open_dates:
            dates.append(today)
        return tuple(dates)

    def step(self, *, source_ready=True):
        """每步至多一批原生扫描与一个原窗口推进；原来源调用受其30秒总预算约束。"""
        require(threading.get_ident() == self.owner and not self.closed)
        if self.clock() < self.next_step:
            return
        now = datetime.fromtimestamp(self.wall_clock(), ZONE)
        if self.cursor == 0 and not self._refresh_metadata():
            self.next_step = self.clock() + self.c['retry_seconds']
            return
        dates = self._days(now)
        if dates != self.dates:
            self.dates = dates
            self.rows = {key: value for key, value in self.rows.items() if key[1] in dates}
            self.jobs.clear(); self.queued.clear(); self.retry_at.clear(); self.cursor = 0
        symbols = self.symbols[self.cursor:self.cursor + self.c['batch_size']]
        if symbols:
            selected = {self.codes[symbol]: symbol for symbol in symbols}
            require(self.reader is None)
            self.reader = reader = CollectionMinuteReader(self.profile, selected)
            try:
                for symbol in symbols:
                    for day in dates:
                        cutoff = now.hour * 100 + now.minute if day == now.date().isoformat() else 2359
                        key = (symbol, day)
                        try:
                            result = reader.read_day(self.codes[symbol], day, cutoff)
                        except (OSError, ValueError, RuntimeError) as error:
                            # 可确认的单次查询失败只影响该证券观察；close失败由批次finally向外收束。
                            self.rows[key] = dict(symbol=symbol, date=day, state='reader_unavailable',
                                error_type=type(error).__name__, expected_count=None, native_count=None,
                                invalid_counter_count=None,  # Reader失败时未取得量额质量；区别成功观察的0。
                                missing_count=None, first_missing=None, last_missing=None,
                                unexpected_count=None, observed_at=self.wall_clock(), recovered_count=None)
                            continue
                        from .minute_counter_quality import negative_counter_count
                        invalid_count = negative_counter_count(result['bars'])
                        old = self.rows.get(key)
                        restored = old is not None and old['state'] == 'recovered'
                        state = ('recovered' if restored else 'awaiting_market_session' if not result['expected_minutes']
                                 else 'observed_complete' if not result['missing_minutes'] and not invalid_count
                                 else 'awaiting_closed_day' if day == now.date().isoformat()
                                 else 'invalid_counters' if invalid_count else 'missing')
                        self.rows[key] = dict(
                            symbol=symbol, date=day, state=state,  # 本次原Reader观察与完整恢复证明分别表达。
                            expected_count=len(result['expected_minutes']), native_count=len(result['bars']),
                            missing_count=len(result['missing_minutes']),  # 全部缺口可按原Reader重建；投影不复制万证券分钟清单。
                            invalid_counter_count=invalid_count,  # 原Reader负量/负额分钟数；原行及标签保持，官方恢复资格单独核。
                            first_missing=next(iter(result['missing_minutes']), None),
                            last_missing=result['missing_minutes'][-1] if result['missing_minutes'] else None,
                            unexpected_count=len(result['unexpected_minutes']),
                            observed_at=self.wall_clock(),  # 原Reader查询完成的本机epoch秒。
                            recovered_count=old.get('recovered_count') if restored else None)
                        if state in ('missing', 'invalid_counters') and key not in self.queued and key not in self.retry_at:
                            self.jobs.append(key); self.queued.add(key)
            finally:
                reader.close()
                self.reader = None
            self.cursor += len(symbols)
            if self.cursor >= len(self.symbols):
                self.cursor = 0; self.cycle += 1
        # 本地覆盖扫描照常进行；Source尚未连接时保留队首，避免启动失败项排到全市场队尾。
        ready_retries = [(due, key) for key, due in self.retry_at.items() if due <= self.clock()]
        window_work = bool(self.jobs or ready_retries)
        if source_ready and (self.prefer_retained_resume or not window_work):
            try:
                self.retained_read_resume = self.producer.resume_read_responsibility(
                    self.clock() + self.producer.c['timeout_seconds'])
            except (OSError, ValueError, KeyError, TypeError):
                self.retained_read_resume = retained_resume_state('unavailable')
                raise
            if self.retained_read_resume['state'] in ('consumed', 'pending'):
                # 原终态由原client交接；下个管理步保留给原窗口队列，未知历史也不能长期独占。
                self.prefer_retained_resume = False
                self.next_step = self.clock() + self.c['interval_seconds']
                return
        if source_ready and (self.jobs or ready_retries):
            if ready_retries and (self.prefer_retry or not self.jobs):
                unused, key = min(ready_retries)
                del self.retry_at[key]
                symbol, day = key
                self.prefer_retry = False
            else:
                symbol, day = key = self.jobs.popleft(); self.queued.remove(key)
                self.prefer_retry = True
            self.prefer_retained_resume = True  # 窗口推进或其失败后，下步仍给原责任交接机会。
            row = self.rows[key]
            grid = self.producer.base.expected_minutes(symbol, day)
            if grid:
                query = dict(exchange=symbol.split('.')[0], code=symbol.split('.')[1],
                             **{'from': grid[0], 'to': grid[-1]}, limit=len(grid))
                result = self.producer.call(dict(api_version=API_VERSION, action='history.source-query', request=query))
                labels = [bar['minute'] for bar in result['data'].get('bars', [])]
                preferred = hashlib.sha256(canonical({k: query[k] for k in ('exchange', 'code', 'from', 'to')})).hexdigest()
                candidates, unused = self.producer.repository.find(query, preferred,
                    deadline=self.clock() + self.c['interval_seconds'], byte_budget=[self.producer.c['max_bytes']], clock=self.clock)
                proven = any(state['published'].get('reconciled_day') is not None for unused, state in candidates)
                complete = result['status']['code'] == 'Ok' and labels == grid and proven
                row.update(state='recovered' if complete else 'recovery_pending',
                           recovered_count=len(labels) if complete else None,
                           recovery_status=result['status']['code'], recovery_observed_at=self.wall_clock())
                if not complete:
                    self.retry_at[key] = self.clock() + self.c['retry_seconds']
        self.next_step = self.clock() + self.c['interval_seconds']

    def snapshot(self):
        """可丢弃重建的旁路状态；原收据和Reader决定实际完成事实。"""
        require(threading.get_ident() == self.owner)
        rows = [value for unused, value in sorted(self.rows.items())]
        return dict(schema='qmt.collection-minute-maintenance.v1', observed_at=self.wall_clock(),
            producer_sha256=self.c['producer']['sha256'], reference_sha256=self.reference_sha,
            reference_error=self.reference_error, last_error_type=self.last_error_type,
            calendar_sha256=getattr(self, 'calendar_sha', None),
            scan_cycles=self.cycle, scan_cursor=self.cursor, scan_symbols=len(self.symbols),
            dates=list(self.dates), queued_count=len(self.jobs), states=dict(Counter(r['state'] for r in rows)), rows=rows,
            retained_read_resume=self.retained_read_resume)  # 有界原ID交接状态；不授分钟完整性。

    def close(self):
        require(threading.get_ident() == self.owner)
        if self.reader is not None:
            self.reader.close()
            self.reader = None
        if self.producer is not None:
            self.producer.close()
            self.producer = None
        self.closed = True
