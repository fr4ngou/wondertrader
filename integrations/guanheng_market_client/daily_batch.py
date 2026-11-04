"""统一WT日线批量合同；单证券语义复用原来源日线，当前口径显式选择。"""
import re
from . import API_VERSION, MarketProtocolError, _object, _list, _integer, validate_response
from .source_history import validate_source_daily_request


def validate_daily_batch_request(value):
    """symbols为1..64个WT日线证券，日期闭区间；limit是每证券条数，adjustment显式声明。"""
    fields=('symbols','from','to','limit','adjustment')
    _object(value, fields+('snapshot_id','view','include_archive'),required=fields)
    symbols=_list(value['symbols'],64)
    if not symbols or any(type(s)is not str or re.fullmatch(r'(SSE|SZSE|BSE)\.[0-9]{6}',s)is None for s in symbols):
        raise MarketProtocolError('daily batch security invalid')
    if len(set(symbols))!=len(symbols):
        raise MarketProtocolError('daily batch securities repeated')
    for _symbol,request in daily_batch_requests(value):
        validate_source_daily_request(request)
    return value


def daily_batch_requests(value):
    """按原顺序生成同窗口单证券请求；调用方先完成整个批次准入。"""
    for symbol in value['symbols']:
        exchange,code=symbol.split('.')
        fields=('from','to','limit','adjustment')+tuple(k for k in ('snapshot_id','view','include_archive')if k in value)
        yield symbol,dict(exchange=exchange,code=code,**{k:value[k]for k in fields})


def validate_daily_batch_data(value,request):
    """results逐项携原status/data；available_count仅为成功读取项数，不代表市场覆盖。"""
    validate_daily_batch_request(request)
    _object(value,('results','available_count'))
    results=_list(value['results'],64)
    if len(results)!=len(request['symbols']):
        raise MarketProtocolError('daily batch result count differs')
    available=0
    for row,(symbol,single)in zip(results,daily_batch_requests(request)):
        _object(row,('symbol','status','data'))
        if row['symbol']!=symbol:
            raise MarketProtocolError('daily batch result security differs')
        validate_response(dict(api_version=API_VERSION,status=row['status'],data=row['data']),
            dict(api_version=API_VERSION,action='history.source-daily-query',request=single))
        available+=row['status']['code']=='Ok'
    if _integer(value['available_count'],0,len(results))!=available:
        raise MarketProtocolError('daily batch availability differs')
    return value
