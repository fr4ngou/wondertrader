"""读取 WT 已发布的中债原始事实，供原股债差计算使用。"""

from guanheng_market_client.supplement_facts import GOV10Y_SCOPE, GOV10Y_YIELD

from .etf_flow import snapshot_reader
from .source_fetch import SourceFailure

TABLE = 'source.wt_gov10y'


def history(fetch, start, end, client_factory, *, snapshot_dates):
    """同一批固定 WT 快照和补充目录，再按查询窗口逐页读取年化百分数。"""
    snapshot, request = snapshot_reader(fetch, client_factory, snapshot_dates)
    identity = snapshot['snapshot_id']
    supplement = snapshot.get('provenance', {}).get('supplement_facts_sha256')
    if supplement is None:
        raise SourceFailure('wt_gov10y_unavailable')
    rows = []
    offset = 0
    while offset is not None:
        query = dict(snapshot_id=identity, metric=GOV10Y_YIELD, symbols=[GOV10Y_SCOPE],
                     limit=2000, offset=offset, **{'from': start, 'to': end})
        data = request('wt_supplement_gov10y', lambda client: client.source_supplement_query(query),
                       absent=('Unavailable', 'NotSupported'))
        if data is None:
            raise SourceFailure('wt_gov10y_unavailable')
        if data['source_snapshot_id'] != identity or data['source_sha256'] != supplement:
            raise SourceFailure('wt_market_snapshot_input_differs')
        rows.extend(dict(date=row['date'], gov10y_pct=float(row['value'])) for row in data['rows'])
        offset = data['selection']['next_offset']
    return {TABLE: rows}
