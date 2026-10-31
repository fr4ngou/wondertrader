"""日终官方数量口径；不包含分钟采集或历史K归档。"""
import math

def quantity(value):
    if isinstance(value, str):
        value = float(value.replace(',', ''))
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0 or int(value) != value:
        raise ValueError('invalid_quantity')
    return int(value)

OFFICIAL_QUANTITIES = {
    'oi': ('LEAVES_CALL_QTY', 'LEAVES_PUT_QTY', 'LEAVES_QTY'),
    'volume': ('CALL_VOLUME', 'PUT_VOLUME', 'TOTAL_VOLUME'),
}

def official_quantities(official, kind):
    """Normalize one official statistic independently; retain failure as quality."""
    call_field, put_field, total_field = OFFICIAL_QUANTITIES[kind]
    empty = {'call_'+kind: None, 'put_'+kind: None}
    try:
        call, put, total = (quantity(official.get(field)) for field in (call_field, put_field, total_field))
    except (ValueError, TypeError, OverflowError):
        return empty, 'official_'+kind+'_invalid_quantity'
    if call+put != total:
        return empty, 'official_'+kind+'_total_mismatch'
    return {'call_'+kind: call, 'put_'+kind: put}, 'complete_reconciled'
