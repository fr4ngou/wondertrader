"""原值最近N根选择；保留逐段原metadata，集合身份不冒充捕获身份。"""
from __future__ import annotations

from copy import deepcopy

from ..guanheng_market_client.source_history import source_selection_metadata, validate_source_data


class SourceSelectionConflict(ValueError):
    """最终选择中同分钟原值冲突，调用方保留原根并显式报告。"""


def select_sources(batches, request, *, preferred_ranges=()):
    """默认同分钟差异保持冲突；仅已验证完整闭合日可显式选择其固定数据版本。"""
    if type(preferred_ranges) not in (tuple, list):
        raise ValueError('source preferred ranges invalid')
    for value in preferred_ranges:
        if (type(value) is not dict or set(value) != {'from', 'to', 'dataset_version'}
                or type(value['from']) is not int or type(value['to']) is not int or value['from'] > value['to']
                or type(value['dataset_version']) is not str or not value['dataset_version']):
            raise ValueError('source preferred range identity invalid')
    selected = {}
    conflicts = set()
    for data in batches:
        validate_source_data(data, request)
        pieces = data.get('provenance')
        piece = 0
        for index, bar in enumerate(data['bars']):
            minute = bar['minute']
            metadata = data['metadata']
            if pieces:
                while index >= pieces[piece]['offset'] + pieces[piece]['count']:
                    piece += 1
                metadata = pieces[piece]['metadata']
            versions = {value['dataset_version'] for value in preferred_ranges if value['from'] <= minute <= value['to']}
            if len(versions) > 1:
                raise SourceSelectionConflict('multiple complete source versions overlap')
            if versions and metadata['dataset_version'] not in versions:
                continue
            if minute in selected:
                if selected[minute][0] != bar:
                    conflicts.add(minute)
            else:
                selected[minute] = (bar, metadata)
        # 每批后仅保留最新limit行，内存不随历史根数增长。
        keep = set(sorted(selected)[-request['limit']:])
        selected = {minute: value for minute, value in selected.items() if minute in keep}
        conflicts.intersection_update(keep)
    if conflicts:
        raise SourceSelectionConflict('source values conflict within selection')
    if not selected:
        return None
    bars = []
    provenance = []
    for minute in sorted(selected):
        bar, metadata = selected[minute]
        if not provenance or provenance[-1]['metadata'] != metadata:
            provenance.append(dict(offset=len(bars), count=0, metadata=deepcopy(metadata)))
        provenance[-1]['count'] += 1
        bars.append(deepcopy(bar))
    result = dict(metadata=deepcopy(provenance[0]['metadata']), bars=bars, coverage='Unknown', missing_minutes=[],
        selection=dict(period_minutes=1, limit=request['limit']))
    if len(provenance) > 1:
        result.update(provenance=provenance, metadata=source_selection_metadata(bars, provenance))
    return validate_source_data(result, request)
