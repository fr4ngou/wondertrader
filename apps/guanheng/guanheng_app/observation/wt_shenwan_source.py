"""用同一 WT 快照读取申万 A 指日表，供原观察计算复用。"""

from guanheng_market_client.supplement_facts import SHENWAN_FIELDS, SHENWAN_SCOPE

from .etf_flow import snapshot_reader
from .source_fetch import SourceFailure

KIND = 'wt_shenwan'
TABLE = 'source.wt_shenwan'
LEGACY_TABLE = 'source.shenwan'
DATASETS = ('spread_sw', 'pb_sw_daily')
FIELDS = tuple(field for field, _, _ in SHENWAN_FIELDS.values())


def history(fetch, start, end, client_factory, *, snapshot_dates):
    """只读取当前不可变补充目录，同日字段允许留缺。"""
    snapshot, request = snapshot_reader(fetch, client_factory, snapshot_dates)
    identity = snapshot['snapshot_id']
    supplement = snapshot.get('provenance', {}).get('supplement_facts_sha256')
    if supplement is None:
        raise SourceFailure('wt_shenwan_unavailable')
    rows = {}
    for metric, (field, _, _) in SHENWAN_FIELDS.items():
        offset = 0
        while offset is not None:
            query = dict(snapshot_id=identity, metric=metric, symbols=[SHENWAN_SCOPE],
                         limit=2000, offset=offset, **{'from': start, 'to': end})
            data = request('wt_supplement_shenwan', lambda client: client.source_supplement_query(query),
                           absent=('Unavailable', 'NotSupported'))
            if data is None:
                break
            if data['source_snapshot_id'] != identity or data['source_sha256'] != supplement:
                raise SourceFailure('wt_market_snapshot_input_differs')
            for value in data['rows']:
                day = value['date']
                row = rows.setdefault(day, dict(date=day, **dict.fromkeys(FIELDS)))
                row[field] = float(value['value'])
            offset = data['selection']['next_offset']
    return {TABLE: [rows[day] for day in sorted(rows)]}


def combined_rows(tables):
    """同日优先使用 WT 已核字段，保留旧归档中仍有出处的其他字段。"""
    legacy = tables.get(LEGACY_TABLE, [])
    incoming = tables.get(TABLE, [])
    if not incoming:
        return legacy
    by_day = {row['date']: dict(row) for row in legacy}
    for row in incoming:
        day = row['date']
        merged = by_day.setdefault(day, dict(date=day, **dict.fromkeys(FIELDS)))
        merged.update((field, row[field]) for field in FIELDS if row.get(field) is not None)
    return [by_day[day] for day in sorted(by_day)]
