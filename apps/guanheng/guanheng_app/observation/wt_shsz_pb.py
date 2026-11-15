"""观衡从固定 WT 版本读取沪深估值，沿原指标行结构发布。"""

from .calendars import official_calendar
from .etf_flow import snapshot_reader
from .source_fetch import SourceFailure

KIND = 'wt_shsz_pb'
METRIC = 'pb_shsz_daily'
TABLE = 'source.wt_shsz_pb'


def history(fetch, source, start, end, client_factory, *, calendar, snapshot_dates):
    """按沪深已收盘交易日读取，保留原事实摘录和两份 BaoStock 原件摘要。"""
    if not calendar['coverage_start'] <= start <= end <= min(snapshot_dates) <= max(snapshot_dates) <= calendar['coverage_end']:
        raise SourceFailure('official_calendar_outside_coverage')
    snapshot, request = snapshot_reader(fetch, client_factory, snapshot_dates)
    sessions, _ = official_calendar(calendar, check=fetch.budget.remaining)
    rows = []
    provenance = []
    for session in sessions:
        day = session['date']
        if not session['is_open'] or not start <= day <= end:
            continue
        data = request('wt_shsz_valuation', lambda client: client.source_day_facts_query(
            day, snapshot['snapshot_id'], include_shsz_valuation=True), absent=('Unavailable',))
        valuation = (data or {}).get('shsz_valuation')
        if valuation is None or valuation['universe_count'] < source['minimum_universe']:
            continue
        metrics = {key: value for key, value in valuation.items() if not key.endswith('_sha256')}
        rows.append(dict(date=day, **metrics, available_at=None, sse_reference=None))
        provenance.append(dict(
            date=day,  # 沪深交易日。
            source_snapshot_id=data['source_snapshot_id'],  # 原读取请求固定的 WT 快照。
            source_sha256=data['source_sha256'],  # WT 定日事实摘要。
            stock_basic_sha256=valuation['stock_basic_sha256'],  # 原上市证券表摘要。
            stock_daily_sha256=valuation['stock_daily_sha256']))  # 原同日估值日线摘要。
    return {METRIC: rows, TABLE: provenance}
