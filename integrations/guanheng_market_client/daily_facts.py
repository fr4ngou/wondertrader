"""定日股票参考事实合同；价格参考用于核对，成交股数与换手保留原单位。"""
from decimal import Decimal,InvalidOperation
from math import isfinite
import re
from . import MarketProtocolError,_object,_list
from .market_snapshot import _day,_hash,_clock

FIELDS=['date','symbol','close_reference','preclose','volume','turn','tradestatus','qualification']
STATS=('identity_unverified_count','state_unverified_count','missing_float_count','special_reference_count','halted_with_trades_count')
OPTIONAL_PROJECTIONS = ('stock_cross_section', 'shsz_valuation')

def validate_facts_request(value):
    """date精确选择已归档事实，snapshot_id绑定同一WT资料及价格目录。"""
    keys=('date','snapshot_id')
    flags = tuple('include_' + key for key in OPTIONAL_PROJECTIONS)
    _object(value,keys+flags,keys)
    _day(value['date']);_hash(value['snapshot_id'])
    if any(type(value.get(flag, False)) is not bool for flag in flags):
        raise MarketProtocolError('daily facts projection flag invalid')
    if value.get('include_stock_cross_section') and value.get('include_shsz_valuation'):
        raise MarketProtocolError('daily facts projections cannot be combined')
    return value

def validate_day_facts(value,*,response=False):
    """rows按FIELDS依次为日期、证券、同日参考价、前收盘、成交股、换手%、状态、资格。"""
    keys=('schema','date','members','fields','rows','units','stats','provenance')
    if response:keys+=('source_snapshot_id','source_sha256')
    _object(value,keys+('qualification',)+OPTIONAL_PROJECTIONS,keys)
    if value['schema']!='guanheng.daily-source-facts.v1':raise MarketProtocolError('daily facts schema invalid')
    day=_day(value['date']);members=_list(value['members'],20000)
    if (not members or any(type(s)is not str or re.fullmatch(r'(SSE|SZSE|BSE)\.[0-9]{6}',s)is None for s in members)
            or members!=sorted(set(members))):
        raise MarketProtocolError('daily facts universe invalid')
    if value['fields']!=FIELDS or value['units']!=dict(close_reference='CNY',preclose='CNY',volume='share',turn='percent_of_float'):
        raise MarketProtocolError('daily facts fields or units invalid')
    rows=_list(value['rows'],20000);seen=set();pool=set(members)
    for row in rows:
        if type(row)is not list or len(row)!=len(FIELDS)or any(type(v)is not str or len(v)>128 for v in row):
            raise MarketProtocolError('daily facts row invalid')
        if row[0]!=day or row[1]not in pool or row[1]in seen:
            raise MarketProtocolError('daily facts identity or date invalid')
        seen.add(row[1])
        if row[6]not in ('0','1','?')or row[7]not in ('qualified','identity_unverified','state_unverified')or row[6]=='?'and row[7]=='qualified':
            raise MarketProtocolError('daily facts qualification invalid')
        for pos in (2,3,4,5):
            if not row[pos]:continue
            try:number=Decimal(row[pos])
            except InvalidOperation:raise MarketProtocolError('daily facts number invalid')from None
            if not number.is_finite()or number<0 or number>Decimal('1e30')or pos==4 and number!=number.to_integral_value():
                raise MarketProtocolError('daily facts number outside capacity')
    stats=_object(value['stats'],STATS)
    if any(v is not None and (type(v)is not int or not 0<=v<=len(members))or v is None and k not in ('special_reference_count','halted_with_trades_count')for k,v in stats.items()):
        raise MarketProtocolError('daily facts coverage invalid')
    original=_object(value['provenance'],('packet_sha256','universe_sha256','source_received_at'))
    _hash(original['packet_sha256']);_hash(original['universe_sha256']);_clock(original['source_received_at'])
    if 'qualification'in value:
        quality=_object(value['qualification'],('membership_method','membership_as_of','turnover_method','point_in_time','first_available_at'))
        if (quality['membership_method']not in ('same_day_public','listing_intervals_latest_identity')
                or quality['turnover_method']not in ('same_day_public','vendor_current_revised_date_series')
                or quality['point_in_time']is not False or quality['first_available_at']is not None):
            raise MarketProtocolError('daily facts source qualification invalid')
        if quality['membership_as_of']is not None:_day(quality['membership_as_of'])
    if response:_hash(value['source_snapshot_id']);_hash(value['source_sha256'])
    if 'stock_cross_section' in value:
        validate_stock_cross_section(value['stock_cross_section'], len(members))
    if 'shsz_valuation' in value:
        validate_shsz_valuation(value['shsz_valuation'])
    return value


def validate_stock_cross_section(section, member_count):
    """定日聚合随同日股票池归档，缺失只提供固定原因。"""
    if type(section) is dict and set(section) == {'reason'}:
        if section['reason'] not in ('bigquant_unavailable','cross_section_unqualified'):
            raise MarketProtocolError('stock cross section gap invalid')
        return section
    _object(section, (
        'provider',  # 原价与成交额供应商，整日同源。
        'source_sha256',  # 数据 owner 原始返回对象摘要。
        'sample_count',  # 通过 WT 同日身份、交易状态及价格核对的股票数量。
        'top5_pct',  # 成交额排名前5%的样本占全部成交额的百分比。
        'median_return_pct',  # 同一股票样本日收益的中位数，单位百分比。
    ))
    if (section['provider'] not in ('QMT', 'BigQuant')
            or type(section['sample_count']) is not int or not 1 <= section['sample_count'] <= member_count
            or any(type(section[key]) not in (int, float) or not isfinite(section[key])
                   for key in ('top5_pct', 'median_return_pct'))
            or not 0 < section['top5_pct'] <= 100 or section['median_return_pct'] <= -100):
        raise MarketProtocolError('stock cross section values invalid')
    _hash(section['source_sha256'])
    return section

def validate_shsz_valuation(value):
    """沪深估值来自 BaoStock 原证券池，样本资格与 WT 标准池独立。"""
    _object(value, (
        'equal_pb',  # 符合条件的全部沪深股票市净率算术平均。
        'median_pb',  # 同一样本市净率中位数。
        'sample_count',  # 全体合格样本数。
        'excluded_count',  # 原证券池中不满足全体估值规则的股票数。
        'universe_count',  # 已匹配原证券表的日线股票数。
        'profitable_equal_pb',  # 盈利子样本市净率算术平均，空样本时为空。
        'profitable_median_pb',  # 盈利子样本市净率中位数，空样本时为空。
        'profitable_sample_count',  # 日线市盈率为正的合格 PB 子样本数。
        'profitable_excluded_count',  # 原证券池中未进入盈利子样本的股票数。
        'stock_basic_sha256',  # BaoStock 证券表原件摘要。
        'stock_daily_sha256',  # 同日 BaoStock 日线原件摘要。
    ))
    count, sample, profitable = (value[k] for k in ('universe_count', 'sample_count', 'profitable_sample_count'))
    counts = (count, sample, profitable, value['excluded_count'], value['profitable_excluded_count'])
    if (any(type(item) is not int or not 0 <= item <= 20000 for item in counts)
            or not 0 <= profitable <= sample <= count or sample == 0
            or value['excluded_count'] != count - sample
            or value['profitable_excluded_count'] != count - profitable):
        raise MarketProtocolError('SH/SZ valuation coverage invalid')
    for key in ('equal_pb', 'median_pb', 'profitable_equal_pb', 'profitable_median_pb'):
        metric = value[key]
        if key.startswith('profitable_') and profitable == 0:
            if metric is not None:
                raise MarketProtocolError('SH/SZ valuation empty subset invalid')
        elif type(metric) not in (int, float) or not 0 < metric <= 100:
            raise MarketProtocolError('SH/SZ valuation value invalid')
    _hash(value['stock_basic_sha256'])
    _hash(value['stock_daily_sha256'])


def validate_facts_data(value,request):
    if request.get('include_shsz_valuation', False):
        fields = ('date', 'source_snapshot_id', 'source_sha256')
        _object(value, fields + ('shsz_valuation',), fields)
        _day(value['date'])
        _hash(value['source_snapshot_id'])
        _hash(value['source_sha256'])
        if 'shsz_valuation' in value:
            validate_shsz_valuation(value['shsz_valuation'])
    else:
        validate_day_facts(value,response=True)
    if (value['date']!=request['date'] or value['source_snapshot_id']!=request['snapshot_id']
            or any(key in value and not request.get('include_' + key, False) for key in OPTIONAL_PROJECTIONS)):
        raise MarketProtocolError('daily facts selection differs')
    return value
