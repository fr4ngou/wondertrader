"""原价缺日的独立来源补入；原WT日期优先、历史及逐段来源完整保留。"""
from copy import deepcopy
from datetime import datetime, timedelta
import math
import time

from ..guanheng_market_client import API_VERSION
from ..guanheng_market_client.source_history import validate_source_metadata
from .daily_archive_prepare import prepare_daily_archive


def read_price_history(market,symbol,adjustment,*,deadline,maximum_history_rows,cancelled,snapshot_id=None):
    """原查询分页读取完整价格档，日期映射保留逐段来源；调用者关闭market。"""
    def check():
        if cancelled():raise InterruptedError('price history read stopped')
        if time.monotonic()>=deadline:raise TimeoutError('price history read deadline')
    exchange,code=symbol.split('.')
    query=dict(exchange=exchange,code=code,**{'from':10000101,'to':20991231,'limit':2000},
        adjustment=adjustment,view='archive',include_archive=True)
    if snapshot_id is not None:query['snapshot_id']=snapshot_id
    check();reply=market.call(dict(api_version=API_VERSION,action='history.source-daily-query',request=query))
    if reply['status']['code']not in('Ok','Unavailable'):raise ValueError('price history read unavailable')
    data=reply['data'];existing=data.get('bars',[]);archive=data.get('archive');merged={}
    if existing and(type(archive)is not dict or archive['count']>maximum_history_rows):
        raise ValueError('price history exceeds declared capacity')
    while existing:
        check();parts=data.get('provenance',[dict(offset=0,count=len(existing),metadata=data['metadata'])]);covered=0
        for part in parts:
            if part['offset']!=covered or type(part['count'])is not int or not 1<=part['count']<=len(existing)-covered:
                raise ValueError('price history provenance invalid')
            validate_source_metadata(part['metadata'],period='1d')
            if part['metadata']['adjustment']!=adjustment:raise ValueError('price history basis differs')
            for bar in existing[covered:covered+part['count']]:
                if bar['date']in merged:raise ValueError('price history page repeated')
                merged[bar['date']]=({key:value for key,value in bar.items()if key!='symbol'},part['metadata'])
            covered+=part['count']
        if covered!=len(existing):raise ValueError('price history provenance count differs')
        if len(merged)==archive['count']:
            if min(merged)!=archive['first_date']or max(merged)!=archive['last_date']:
                raise ValueError('price history range differs')
            break
        if len(merged)>archive['count']:raise ValueError('price history count differs')
        before=datetime.strptime(str(min(merged)),'%Y%m%d')-timedelta(days=1)
        query['to']=int(before.strftime('%Y%m%d'));check()
        reply=market.call(dict(api_version=API_VERSION,action='history.source-daily-query',request=query))
        if reply['status']['code']!='Ok'or reply['data'].get('archive')!=archive:
            raise ValueError('price history changed during pagination')
        data=reply['data'];existing=data.get('bars',[])
        if not existing:raise ValueError('price history incomplete')
    if archive is not None and not merged and archive['count']:
        raise ValueError('price history missing archive rows')
    return merged


def merge_original_price_rows(market, additions, metadata, output, helper, helper_sha256, *, deadline, snapshot_id=None,
                              addition_provenance=None, retain_unchanged=False, maximum_history_rows=2000,
                              cancelled=lambda:False,reusable_files=None):
    """同一市场owner线程读取完整旧档，只填不存在的日期；返回新档或None。

    additions为symbol到合格原始日线行，metadata属于这些新行；前复权独立保持。
    addition_provenance可按证券声明新行的逐段来源；缺省沿同一metadata。
    retain_unchanged仅用于完整补充目录发布，保留本次没有新增行的旧证券。
    maximum_history_rows为显式旧档/输出记录预算，默认2000；长指数按原查询分页
    读取完整旧档，单次公开查询仍最多2000条。cancelled沿外层owner的原停止请求，
    逐证券/分页及写入前检查；调用者关闭market。
    """
    validate_source_metadata(metadata, period='1d')
    if metadata['adjustment'] != 'none' or type(additions) is not dict or len(additions) > 10000:
        raise ValueError('original price merge input invalid')
    if type(retain_unchanged) is not bool or (addition_provenance is not None
            and (type(addition_provenance) is not dict or set(addition_provenance) != set(additions))):
        raise ValueError('original price merge provenance selection invalid')
    if type(maximum_history_rows) is not int or not 1 <= maximum_history_rows <= 1000000:
        raise ValueError('original price merge history capacity invalid')
    if type(deadline) not in (int,float) or not math.isfinite(deadline):
        raise ValueError('original price merge finite deadline required')
    if not callable(cancelled):raise ValueError('original price merge cancellation invalid')
    def check():
        if cancelled():raise InterruptedError('original price merge stopped')
        if time.monotonic() >= deadline:raise TimeoutError('original price merge deadline expired')
    securities = {}
    provenance = {}
    for symbol, rows in additions.items():
        check()
        merged=read_price_history(market,symbol,'none',deadline=deadline,maximum_history_rows=maximum_history_rows,
            cancelled=cancelled,snapshot_id=snapshot_id)
        inserted = 0
        seen = set()
        sources = [metadata] * len(rows)
        if addition_provenance is not None:
            covered = 0
            for part in addition_provenance[symbol]:
                if (type(part) is not dict or set(part) != {'offset', 'count', 'metadata'}
                        or part['offset'] != covered or type(part['count']) is not int
                        or not 1 <= part['count'] <= len(rows) - covered):
                    raise ValueError('original price addition provenance invalid')
                validate_source_metadata(part['metadata'], period='1d')
                if part['metadata']['adjustment'] != 'none':
                    raise ValueError('original price addition basis differs')
                sources[covered:covered + part['count']] = [part['metadata']] * part['count']
                covered += part['count']
            if covered != len(rows):
                raise ValueError('original price addition provenance count differs')
        for row, original in zip(rows, sources):
            if row['date'] in seen:
                raise ValueError('original price addition date repeated')
            seen.add(row['date'])
            if row['date'] not in merged:
                merged[row['date']] = (row, original)
                inserted += 1
        if not merged or inserted == 0 and not retain_unchanged:
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
                                 deadline=deadline, provenance=provenance, maximum_history_rows=maximum_history_rows,
                                 cancelled=cancelled,reusable_files=reusable_files)
