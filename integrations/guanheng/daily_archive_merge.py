"""原价缺日的独立来源补入；原WT日期优先、历史及逐段来源完整保留。"""
from copy import deepcopy
import time

from ..guanheng_market_client import API_VERSION
from ..guanheng_market_client.source_history import validate_source_metadata
from .daily_archive_prepare import prepare_daily_archive


def merge_original_price_rows(market, additions, metadata, output, helper, helper_sha256, *, deadline, snapshot_id=None):
    """同一市场owner线程读取完整旧档，只填不存在的日期；返回新档或None。

    additions为symbol到合格原始日线行，metadata属于这些新行；前复权独立保持。
    原档超过2000条且本次没有完整读取时拒绝，避免截断旧历史。调用者关闭market。
    """
    validate_source_metadata(metadata, period='1d')
    if metadata['adjustment'] != 'none' or type(additions) is not dict or len(additions) > 10000:
        raise ValueError('original price merge input invalid')
    securities = {}
    provenance = {}
    for symbol, rows in additions.items():
        if time.monotonic() >= deadline:
            raise TimeoutError('original price merge deadline expired')
        exchange, code = symbol.split('.')
        query = dict(exchange=exchange, code=code, **{'from': 10000101, 'to': 20991231, 'limit': 2000},
                     adjustment='none', view='archive', include_archive=True)
        if snapshot_id is not None:
            query['snapshot_id'] = snapshot_id
        reply = market.call(dict(api_version=API_VERSION, action='history.source-daily-query', request=query))
        if reply['status']['code'] not in ('Ok', 'Unavailable'):
            raise ValueError('original price merge cannot read registered history')
        data = reply['data']
        existing = data.get('bars', [])
        if data.get('archive', {}).get('count', 0) != len(existing):
            raise ValueError('original price merge requires complete retained history')
        merged = {}
        if existing:
            parts = data.get('provenance', [dict(offset=0, count=len(existing), metadata=data['metadata'])])
            for part in parts:
                for bar in existing[part['offset']:part['offset'] + part['count']]:
                    merged[bar['date']] = ({key: value for key, value in bar.items() if key != 'symbol'}, part['metadata'])
        inserted = 0
        seen = set()
        for row in rows:
            if row['date'] in seen:
                raise ValueError('original price addition date repeated')
            seen.add(row['date'])
            if row['date'] not in merged:
                merged[row['date']] = (row, metadata)
                inserted += 1
        if inserted == 0:
            continue
        output_rows = []
        output_parts = []
        for day in sorted(merged):
            bar, original = merged[day]
            if not output_parts or output_parts[-1]['metadata'] != original:
                output_parts.append(dict(
                    offset=len(output_rows),  # 本段在新独立DSB中的零基起点。
                    count=0,  # 本段连续原价记录数，逐条递增。
                    metadata=deepcopy(original)))  # 每条原记录保留其来源、单位、参考和内容身份。
            output_parts[-1]['count'] += 1
            output_rows.append(deepcopy(bar))
        securities[symbol] = output_rows
        provenance[symbol] = output_parts
    if not securities:
        return None
    return prepare_daily_archive(securities, metadata, output, helper, helper_sha256,
                                 deadline=deadline, provenance=provenance)
