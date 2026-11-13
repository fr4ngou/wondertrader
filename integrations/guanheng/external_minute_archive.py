"""显式登记的整日外部分钟，复用原 DSB Reader 与行情选择。"""
from datetime import date, datetime
import logging
from pathlib import Path
from zoneinfo import ZoneInfo

from .market_generation import read_fixed
from .models import IntegrationUnavailable, SourceSession
from .native_history import NativeHistory, SourceHistoryMetadata
from .source_history_transport import require
from .source_market import _hash, _metadata, _minute
from ..guanheng_market_client import strict_json
from ..guanheng_market_client.source_history import validate_source_request


class ExternalMinuteArchive:
    """历史服务线程持有 Reader。配置固定每只证券当日的来源与原生制品。"""

    def __init__(self, descriptor, native):
        require(type(descriptor) is dict and set(descriptor) == {'path', 'sha256'})
        path = Path(descriptor['path'])
        require(path.is_absolute())
        identity = _hash(descriptor['sha256'])
        catalog = strict_json(read_fixed(path, maximum=16777216, identity=identity))
        require(type(catalog) is dict and set(catalog) == {'schema', 'rows'}
                and catalog['schema'] == 'guanheng.external-minute-archive.v1'
                and type(catalog['rows']) is list and 1 <= len(catalog['rows']) <= 10000)
        self.entries = {}  # 先按证券、再按 ISO 交易日索引，外部配置有且仅有一个整日来源。
        for row in catalog['rows']:
            require(type(row) is dict and set(row) == {
                'symbol', 'date', 'path', 'sha256', 'source_sha256', 'source_license', 'count'})
            security, day = row['symbol'], row['date']
            exchange, code = security.split('.')
            parsed_day = date.fromisoformat(day)
            require(parsed_day.isoformat() == day)
            stamp = parsed_day.strftime('%Y%m%d')
            validate_source_request(dict(exchange=exchange, code=code, limit=row['count'],
                                         **{'from': int(stamp + '0000'), 'to': int(stamp + '2359')}))
            file = Path(row['path'])
            require(file.is_absolute() and file.suffix.lower() == '.dsb')
            days = self.entries.setdefault(security, {})
            require(day not in days)
            metadata = SourceHistoryMetadata(
                SourceSession('BigQuant', 'cn_fund_bar1m_c', _hash(row['source_sha256']), 1),
                'DevelopmentVerified', 'bigquant-closed-minute.v1:' + identity,
                _hash(row['sha256']), row['source_license'], '1m', row['count'],
                'CNY', 'share', 'CNY', 'right')
            days[day] = file, metadata
        self.reader = NativeHistory(Path(native['library']), native['sha256'],
                                    max_bars=2000, max_file_bytes=16 * 1024 * 1024)

    def batches(self, request, native, original_preferences):
        security = request['exchange'] + '.' + request['code']
        source_symbol = request['code'] + ('.SH' if request['exchange'] == 'SSE' else '.SZ')
        today = datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat()
        batches, preferences = [], []
        for day, (path, metadata) in self.entries.get(security, {}).items():
            if day >= today:
                continue
            stamp = int(day.replace('-', ''))
            if not request['from'] // 10000 <= stamp <= request['to'] // 10000:
                continue
            grid = native.expected_minutes(security, day)
            require(bool(grid))
            if any(row['from'] <= grid[0] and row['to'] >= grid[-1] for row in original_preferences):
                continue
            try:
                history = self.reader.read_source_file(path, source_symbol, metadata)
                require(tuple(_minute(bar.occurred_at) for bar in history.bars) == tuple(grid))
            except (OSError, ValueError, IntegrationUnavailable) as error:
                logging.getLogger(__name__).warning(
                    'external_minute_archive_unavailable security=%s date=%s error_type=%s',
                    security, day, type(error).__name__)
                continue
            bars = [dict(symbol=security, minute=label, open=bar.open, high=bar.high,
                         low=bar.low, close=bar.close, volume=bar.volume, amount=bar.amount)
                    for label, bar in zip(grid, history.bars)
                    if request['from'] <= label <= request['to']]
            bars = bars[-request['limit']:]
            if not bars:
                continue
            preferences.append(dict(dataset_version=metadata.dataset_version,
                                    **{'from': grid[0], 'to': grid[-1]}))
            batches.append(dict(metadata=_metadata(metadata), bars=bars, coverage='Unknown',
                                missing_minutes=[], selection=dict(period_minutes=1, limit=request['limit'])))
        return batches, preferences

    def close(self):
        self.reader.close()
