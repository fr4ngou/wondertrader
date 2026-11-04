"""统一WT证券资料与实际日期缺口合同；资料未知与缺少价格分别表达。"""
from datetime import datetime
import re
from . import MarketProtocolError, _object, _text, _integer, _list
from .market_snapshot import _day, _clock, _hash
from .source_history import _date

GAP_FIELDS = ('missing_dates', 'before_listing_dates', 'after_expiry_dates',
              'no_trade_dates', 'unresolved_dates')


def validate_security_request(value):
    """symbol为WT身份；日期窗口最多366自然日，价格口径和版本均为必填。"""
    _object(value, ('symbol', 'from', 'to', 'adjustment', 'snapshot_id'))
    if type(value['symbol']) is not str or re.fullmatch(r'(SSE|SZSE|BSE)\.[0-9]{6}', value['symbol']) is None:
        raise MarketProtocolError('security identity invalid')
    first, last = _date(value['from']), _date(value['to'])
    if first > last or (datetime.strptime(str(last), '%Y%m%d') - datetime.strptime(str(first), '%Y%m%d')).days > 365:
        raise MarketProtocolError('security assessment range exceeds 366 days')
    if value['adjustment'] not in ('none', 'front_ratio'):
        raise MarketProtocolError('security price basis invalid')
    _hash(value['snapshot_id'])
    return value


def validate_security_identity(value):
    """资料来源时刻指名称/上市信息的采集时刻，缺项为None，不从价格推测。"""
    _object(value, ('symbol', 'name', 'market', 'security_type', 'listed_on', 'expires_on', 'observed_at'))
    symbol = value['symbol']
    if type(symbol) is not str or re.fullmatch(r'(SSE|SZSE|BSE)\.[0-9]{6}', symbol) is None:
        raise MarketProtocolError('security identity invalid')
    if value['market'] != symbol.split('.')[0] or value['security_type'] not in ('stock', 'etf', 'index', 'unknown'):
        raise MarketProtocolError('security classification invalid')
    if value['name'] is not None:
        _text(value['name'], limit=128)
    for key in ('listed_on', 'expires_on'):
        if value[key] is not None:
            _day(value[key])
    if value['observed_at'] is not None:
        _clock(value['observed_at'])
    return value


def validate_security_data(value, request):
    validate_security_request(request)
    _object(value, ('security', 'source_snapshot_id', 'adjustment', 'history_status', 'archive',
                    'available_dates', 'gap_assessment', 'reference_sha256'))
    identity = validate_security_identity(value['security'])
    if (identity['symbol'] != request['symbol'] or value['source_snapshot_id'] != request['snapshot_id']
            or value['adjustment'] != request['adjustment']):
        raise MarketProtocolError('security selection differs')
    _hash(value['source_snapshot_id'])
    if value['reference_sha256'] is not None:
        _hash(value['reference_sha256'])
    status = _object(value['history_status'], ('code', 'reason'))
    if status['code'] not in ('Ok', 'Unavailable'):
        raise MarketProtocolError('security history status invalid')
    if type(status['reason']) is not str or len(status['reason']) > 512:
        raise MarketProtocolError('security history reason invalid')
    archive = value['archive']
    if archive is not None:
        _object(archive, ('first_date', 'last_date', 'count'))
        if _date(archive['first_date']) > _date(archive['last_date']):
            raise MarketProtocolError('security archive range invalid')
        _integer(archive['count'], 1, 1000000)
    dates = _list(value['available_dates'], 366)
    if dates != sorted(set(dates)) or any(not request['from'] <= _date(day) <= request['to'] for day in dates):
        raise MarketProtocolError('security available dates invalid')
    if status['code'] == 'Unavailable' and (dates or archive is not None):
        raise MarketProtocolError('unavailable security has observed price dates')
    assessment = _object(value['gap_assessment'], ('from', 'to', 'calendar_id', 'calendar_sha256',
        'calendar_covered', 'calendar_verified_through') + GAP_FIELDS)
    if assessment['from'] != request['from'] or assessment['to'] != request['to']:
        raise MarketProtocolError('security assessment window differs')
    if type(assessment['calendar_covered']) is not bool:
        raise MarketProtocolError('security calendar coverage invalid')
    if assessment['calendar_id'] is not None:
        _text(assessment['calendar_id'], limit=128)
        _hash(assessment['calendar_sha256'])
        if assessment['calendar_verified_through'] is not None:
            _day(assessment['calendar_verified_through'])
    elif (assessment['calendar_sha256'] is not None or assessment['calendar_verified_through'] is not None
          or assessment['calendar_covered']):
        raise MarketProtocolError('unconfigured security calendar differs')
    seen = set(dates)
    for key in GAP_FIELDS:
        days = _list(assessment[key], 366)
        if days != sorted(set(days)) or any(not request['from'] <= _date(day) <= request['to'] or day in seen for day in days):
            raise MarketProtocolError('security gap classification invalid')
        seen.update(days)
    return value
