"""原值最近N根选择；保留逐段原metadata，集合身份不冒充捕获身份。"""
from __future__ import annotations

from copy import deepcopy

from ..guanheng_market_client.source_history import source_selection_metadata, validate_source_data


class SourceSelectionConflict(ValueError):
    """最终选择中同分钟原值冲突，调用方保留原根并显式报告。"""


def select_sources(batches, request):
    """batches优先顺序由编排显式给出；相同原值去重，差异不静默覆盖。"""
    selected = {}
    conflicts = set()
    for data in batches:
        validate_source_data(data, request)
        for bar in data['bars']:
            minute = bar['minute']
            if minute in selected:
                if selected[minute][0] != bar:
                    conflicts.add(minute)
            else:
                selected[minute] = (bar, data['metadata'])
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
