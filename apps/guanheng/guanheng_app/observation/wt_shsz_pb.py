"""从同一 WT 版本读取原沪深股票池的估值和广度事实。"""

from .breadth_models import SHSZ_METRICS, rows_for_metrics
from .calendars import official_calendar
from .etf_flow import snapshot_reader
from .market_breadth import stock_day_from_counts
from .source_fetch import SourceFailure

KIND = 'wt_shsz_pb'
METRIC = 'pb_shsz_daily'
TABLE = 'source.wt_shsz_pb'
BREADTH_TABLE = 'source.wt_shsz_breadth'
UNIVERSE_TABLE = 'source.shsz_universe'
CALENDAR_TABLE = 'source.cn_calendar'
FULL_TABLES = [TABLE, BREADTH_TABLE, UNIVERSE_TABLE, CALENDAR_TABLE]
FULL_DATASETS = [METRIC, *sorted(SHSZ_METRICS)]


def coverage_tables(source):
    """是否完成依据 WT 表登记，原股票池和日历不能代替数据回执。"""
    return (TABLE, BREADTH_TABLE) if BREADTH_TABLE in source.get('tables', ()) else (TABLE,)


def history(fetch, source, start, end, client_factory, *, calendar, snapshot_dates):
    """按已收盘交易日读取原数据，继续以观察侧公式生成指标。"""
    if not calendar['coverage_start'] <= start <= end <= min(snapshot_dates) <= max(snapshot_dates) <= calendar['coverage_end']:
        raise SourceFailure('official_calendar_outside_coverage')
    snapshot, request = snapshot_reader(fetch, client_factory, snapshot_dates)
    sessions, _ = official_calendar(calendar, check=fetch.budget.remaining)
    full = BREADTH_TABLE in coverage_tables(source)
    result = {METRIC: [], TABLE: []}
    if full:
        result.update({key: [] for key in (*SHSZ_METRICS, BREADTH_TABLE, UNIVERSE_TABLE)})
        result[CALENDAR_TABLE] = [dict(date=row['date'], is_open=int(row['is_open'])) for row in sessions
                                  if start <= row['date'] <= end]
    for session in sessions:
        day = session['date']
        if not session['is_open'] or not start <= day <= end:
            continue
        data = request('wt_shsz_facts', lambda client: client.source_day_facts_query(
            day, snapshot['snapshot_id'], include_shsz_valuation=True, include_shsz_breadth=full),
            absent=('Unavailable',))
        if not data:
            continue
        valuation = data.get('shsz_valuation')
        if valuation is not None and valuation['universe_count'] >= source['minimum_universe']:
            metrics = {key: value for key, value in valuation.items() if not key.endswith('_sha256')}
            result[METRIC].append(dict(date=day, **metrics, available_at=None, sse_reference=None))
            result[TABLE].append(_provenance(day, data, valuation))
        breadth = data.get('shsz_breadth') if full else None
        if breadth is None or breadth['market_count'] < source['minimum_universe']:
            continue
        for key, row in rows_for_metrics(stock_day_from_counts(day, breadth), SHSZ_METRICS).items():
            result[key].append(row)
        result[BREADTH_TABLE].append(dict(**_provenance(day, data, breadth),
                                          universe_version=breadth['universe_version']))
        result[UNIVERSE_TABLE].append(dict(date=day, universe_version=breadth['universe_version'],
                                           market_count=breadth['market_count'],
                                           source_basic_sha256=breadth['stock_basic_sha256']))
    return result


def _provenance(day, data, summary):
    return dict(
        date=day,  # 沪深交易日。
        source_snapshot_id=data['source_snapshot_id'],  # 固定此次事实读取的 WT 快照。
        source_sha256=data['source_sha256'],  # WT 定日事实对象摘要。
        stock_basic_sha256=summary['stock_basic_sha256'],  # BaoStock 证券表原件摘要。
        stock_daily_sha256=summary['stock_daily_sha256'])  # BaoStock 同日日线原件摘要。
