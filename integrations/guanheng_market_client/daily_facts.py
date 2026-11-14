"""定日股票参考事实合同；价格参考用于核对，成交股数与换手保留原单位。"""
from decimal import Decimal,InvalidOperation
from math import isfinite
import re
from . import MarketProtocolError,_object,_list
from .market_snapshot import _day,_hash,_clock

FIELDS=['date','symbol','close_reference','preclose','volume','turn','tradestatus','qualification']
STATS=('identity_unverified_count','state_unverified_count','missing_float_count','special_reference_count','halted_with_trades_count')

def validate_facts_request(value):
    """date精确选择已归档事实，snapshot_id绑定同一WT资料及价格目录。"""
    keys=('date','snapshot_id')
    _object(value,keys+('include_stock_cross_section',),keys)
    _day(value['date']);_hash(value['snapshot_id'])
    if 'include_stock_cross_section' in value and type(value['include_stock_cross_section']) is not bool:
        raise MarketProtocolError('stock cross section projection flag invalid')
    return value

def validate_day_facts(value,*,response=False):
    """rows按FIELDS依次为日期、证券、同日参考价、前收盘、成交股、换手%、状态、资格。"""
    keys=('schema','date','members','fields','rows','units','stats','provenance')
    if response:keys+=('source_snapshot_id','source_sha256')
    _object(value,keys+('qualification','stock_cross_section'),keys)
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

def validate_facts_data(value,request):
    validate_day_facts(value,response=True)
    if (value['date']!=request['date'] or value['source_snapshot_id']!=request['snapshot_id']
            or 'stock_cross_section' in value and not request.get('include_stock_cross_section', False)):
        raise MarketProtocolError('daily facts selection differs')
    return value
