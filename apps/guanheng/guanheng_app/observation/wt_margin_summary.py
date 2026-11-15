"""通过 WT 的固定快照读取原「两融」报表。"""

from decimal import Decimal

from guanheng_market_client.supplement_facts import MARGIN_DAILY_SUMMARY, MARGIN_SUMMARY_FIELDS

from .etf_flow import snapshot_reader
from .source_fetch import SourceFailure


KIND = 'wt_margin_summary'
TABLE = 'source.margin_daily_summary'
DATASETS = ('leverage_margin', 'margin.short')


def row_complete(row):
    """区分真实零额、负净买入和缺失字段。"""
    return all(row.get(field) is not None for field in MARGIN_SUMMARY_FIELDS.values())


def history(fetch, start, end, client_factory, *, snapshot_dates):
    """按同一快照读取每项已核人民币原值，转为原看板的亿元口径。"""
    snapshot, request = snapshot_reader(fetch, client_factory, snapshot_dates)
    identity = snapshot['snapshot_id']
    supplement = snapshot.get('provenance', {}).get('supplement_facts_sha256')
    if supplement is None:
        raise SourceFailure('wt_margin_summary_unavailable')

    rows = {}
    for metric, field in MARGIN_SUMMARY_FIELDS.items():
        offset = 0
        while offset is not None:
            query = dict(snapshot_id=identity, metric=metric, symbols=[MARGIN_DAILY_SUMMARY],
                         limit=2000, offset=offset, **{'from': start, 'to': end})
            data = request('wt_supplement_margin_summary', lambda client: client.source_supplement_query(query),
                           absent=('Unavailable', 'NotSupported',))
            if data is None:
                break
            if data['source_snapshot_id'] != identity or data['source_sha256'] != supplement:
                raise SourceFailure('wt_market_snapshot_input_differs')
            for row in data['rows']:
                fields = rows.setdefault(row['date'], dict(date=row['date'], available_at=None))
                fields[field] = float(Decimal(row['value']) / Decimal(100_000_000))
            offset = data['selection']['next_offset']
    if not rows:
        raise SourceFailure('wt_margin_summary_unavailable')
    return {TABLE: [rows[day] for day in sorted(rows)]}
