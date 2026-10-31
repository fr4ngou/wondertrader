"""原QMT前复权序列→当期40期统计；不重建供应商复权算法。"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, DecimalException, localcontext
from fractions import Fraction
import json
import math
from pathlib import Path
import re

from .source_fetch import SourceFailure
from .storage import digest, encode
from .t2108_models import METRIC, UNIVERSE

ZONE = timezone(timedelta(hours=8))


def decode(body):
    """普通原件与slot内原结果共用重复键和非有限常量准入。"""
    def unique(pairs):
        result={}
        for key,value in pairs:
            _need(key not in result);result[key]=value
        return result
    def reject(_):raise SourceFailure('t2108_source_schema')
    return json.loads(body,object_pairs_hook=unique,parse_constant=reject)


def _need(value, code='t2108_source_schema'):
    if not value:
        raise SourceFailure(code)


def _day(value):
    _need(type(value) is str)
    parsed=date.fromisoformat(value)
    _need(parsed.isoformat()==value)
    return value


def _clock(value):
    _need(type(value) is str)
    parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
    _need(parsed.tzinfo is not None and parsed.utcoffset() is not None)
    return parsed


def _number(value, positive=False):
    _need(type(value) in (int,float) and math.isfinite(value))
    number=Decimal(str(value))
    _need(number.is_finite() and (number>0 if positive else number>=0))
    return number


class Capture:
    """逐件有限读入、校验原字节SHA并登记；原回包时间与本次入库时间分离。"""
    def __init__(self, fetch, manifest):
        self.fetch=fetch;self.root=Path(manifest).resolve().parent
        self.source_kind='unverified-capture'

    def read(self, descriptor, kind):
        _need(type(descriptor) is dict and set(descriptor)=={'path','sha256'})
        name,identity=descriptor['path'],descriptor['sha256']
        _need(type(name) is str and type(identity) is str and re.fullmatch('[a-f0-9]{64}',identity))
        path=(self.root/name).resolve(strict=True)
        _need(path.is_relative_to(self.root),'t2108_source_path')
        self.fetch.budget.remaining()
        with path.open('rb') as stream:
            body=stream.read(self.fetch.budget.response_bytes+1)
        _need(len(body)<=self.fetch.budget.response_bytes,'t2108_source_capacity')
        self.fetch.budget.consume(len(body));_need(digest(body)==identity,'t2108_source_identity')
        self.fetch.objects.put(body)
        record=dict(kind=kind,sha256=identity,media_type='application/json')
        self.fetch.records.append(record)
        value=decode(body)
        self.fetch.budget.remaining()
        return value,record


def _receipt(value, operation, seen, day):
    """原BoundAnalysisClient公开返回值；原请求UUID和实际接收时钟保持。"""
    _need(type(value) is dict and set(value)=={'request_id','requested_at','received_at','reply'})
    identity=value['request_id'];_need(type(identity) is str and identity not in seen)
    from uuid import UUID
    _need(str(UUID(identity))==identity);seen.add(identity)
    requested,received=_clock(value['requested_at']),_clock(value['received_at'])
    _need(requested<=received<=datetime.now(timezone.utc),'t2108_source_clock')
    if operation=='market.market_data':
        closing=datetime.combine(date.fromisoformat(day),datetime.min.time(),ZONE)+timedelta(hours=15)
        _need(requested>=closing,'t2108_source_not_closed')
    reply=value['reply']
    _need(type(reply) is dict and reply.get('ok') is True and reply.get('operation_id')==operation
        and reply.get('request_id')==identity and reply.get('error_code') is None)
    _need(type(reply.get('data')) is dict)
    return reply['data'],value['received_at']


def _prices(value, symbol, maximum, start, end, check):
    _need(set(value)=={symbol} and type(value[symbol]) is dict and len(value[symbol])<=maximum)
    result={}
    for label,bar in value[symbol].items():
        check()
        _need(type(label) is str and re.fullmatch('[0-9]{8}',label))
        day=_day(label[:4]+'-'+label[4:6]+'-'+label[6:])
        _need(start<=day<=end and type(bar) is dict
            and set(bar)=={'open','high','low','close','volume','amount'})
        for field,number in bar.items():_number(number)
        result[day]=_number(bar['close'])
    return result


def _original_package(capture, descriptor, binding_sha):
    """沿来源交接MANIFEST核全量原slot；导出的公开收据须逐值回指原DATA。"""
    if descriptor is None:return None
    manifest,_=capture.read(descriptor,'qmt_analysis_original_manifest')
    _need(manifest.get('schema')=='guanheng.observation-qas-package.v1'
        and manifest.get('read_only') is True and manifest.get('credentials_included') is False
        and type(manifest.get('actual_QMT')) is bool and type(manifest.get('files')) is dict
        and 1<=len(manifest['files'])<=30002)
    parent=Path(descriptor['path']).parent;values={}
    for name,identity in manifest['files'].items():
        _need(type(name) is str and not Path(name).is_absolute() and '..' not in Path(name).parts)
        values[name],_=capture.read(dict(path=(parent/name).as_posix(),sha256=identity),'qmt_analysis_original')
    data=values[manifest['data']]
    _need(data.get('schema')=='guanheng.observation-qas-capture.v1'
        and data.get('actual_QMT') is manifest['actual_QMT']
        and digest(encode(data['source_binding']))==binding_sha)
    capture.source_kind='actual-qmt' if manifest['actual_QMT'] else 'sdk-synthetic'
    requests=data['requests'];_need(type(requests) is list and len(requests)<=30000)
    mapped={}
    for item in requests:
        capture.fetch.budget.remaining();key=(item['symbol'],item['kind'])
        _need(key not in mapped and item['kind'] in ('none','front_ratio','factors')
            and all(item[k]==data['source_binding'] for k in ('admitted_binding','dispatch_binding','result_binding','source_binding'))
            and item['original_slot_sha256']==manifest['files'][item['original_slot']])
        mapped[key]=item
    return mapped


def history(fetch, config, start, end):
    """显式来源包包含定日股票池、闭合证明和原QAS收据引用，单批至多10000股。

    原v7只支持SH/SZ；v8按批量格式接收BJ，实际覆盖逐证券核对。格式/身份/时钟错误使
    整批失败保旧；前复权缺失、过期、不足期或价格不可用分别计数。
    """
    try:
        return _history(fetch,config,start,end)
    except SourceFailure:raise
    except (OSError,ValueError,KeyError,TypeError,OverflowError,RecursionError,DecimalException):
        raise SourceFailure('t2108_source_schema') from None


def _history(fetch, config, start, end):
    path=Path(config['input_manifest'])
    capture=Capture(fetch,path)
    manifest,_=capture.read(dict(path=path.name,sha256=config['input_sha256']),'qmt_analysis_capture')
    common={'schema','observation_date','closed_through','closure_observed_at','closure_evidence','source_binding_sha256','universe'}
    _need(type(manifest) is dict)
    version=manifest.get('schema')
    fields={'entries','original_package'} if version=='guanheng.observation-qas-inputs.v1' else {'batch_capture','qualifications'}
    _need(version in ('guanheng.observation-qas-inputs.v1','guanheng.observation-qas-inputs.v2') and set(manifest)==common|fields)
    day=_day(manifest['observation_date']);closed=_day(manifest['closed_through'])
    closure=_clock(manifest['closure_observed_at']).astimezone(ZONE)
    ceiling=closure.date() if closure.hour>=15 else closure.date()-timedelta(days=1)
    _need(start<=day<=end and day<=closed<=ceiling.isoformat()
        and closure<=datetime.now(timezone.utc),'t2108_source_not_closed')
    _need(type(manifest['closure_evidence']) is str and 0<len(manifest['closure_evidence'])<=2048)
    _need(type(manifest['source_binding_sha256']) is str
        and re.fullmatch('[a-f0-9]{64}',manifest['source_binding_sha256']))
    universe,universe_record=capture.read(manifest['universe'],'stock_universe')
    _need(universe['date']==day and type(universe['members']) is list and 1<=len(universe['members'])<=10000)
    members=universe['members'];_need(all(type(s) is str and re.fullmatch(r'(sh|sz|bj)\.[0-9]{6}',s) for s in members))
    _need(len(set(members))==len(members) and type(universe['market_count']) is int and universe['market_count']==len(members))
    if version=='guanheng.observation-qas-inputs.v1':
        entries=_scalar_entries(capture,manifest,day)
    else:
        from .t2108_batch import entries as batch_entries
        entries=batch_entries(capture,manifest,day,market_count=len(members))
    return _aggregate(capture,manifest,members,universe_record,entries,day)


def _scalar_entries(capture, manifest, day):
    fetch=capture.fetch
    originals=_original_package(capture,manifest['original_package'],manifest['source_binding_sha256'])
    entries=manifest['entries'];_need(type(entries) is list and len(entries)<=10000)
    seen_requests=set()
    for entry in entries:
        fetch.budget.remaining()
        _need(type(entry) is dict and set(entry)=={'symbol','arguments','raw','front_ratio','factors',
            'adjustment_qualified','adjustment_evidence'})
        _need(type(entry['adjustment_qualified']) is bool)
        symbol=entry['symbol'];_need(type(symbol) is str and re.fullmatch(r'[0-9]{6}\.(SH|SZ)',symbol))
        arguments=entry['arguments'];_need(type(arguments) is dict and set(arguments)=={'start_date','end_date','max_rows'})
        first,last=arguments['start_date'],arguments['end_date'];maximum=arguments['max_rows']
        _need(type(first) is str and re.fullmatch('[0-9]{8}',first)
            and last==day.replace('-','') and type(maximum) is int and 1<=maximum<=20000)
        first=_day(first[:4]+'-'+first[4:6]+'-'+first[6:]);_need(first<=day)
        values={};received=[]
        for kind in ('raw','front_ratio'):
            original,record=capture.read(entry[kind],'qmt_analysis_'+kind)
            if originals is not None:
                source_kind='none' if kind=='raw' else kind;source=originals[(symbol,source_kind)]
                expected=dict(request_id=source['request_id'],requested_at=source['requested_at'],
                    received_at=source['received_at'],reply=source['original_reply'])
                expected_arguments=dict(symbol=symbol,adjustment=source_kind,**arguments)
                _need(original==expected and source['arguments']==expected_arguments
                    and source['operation']=='market.market_data',
                    't2108_original_package_identity')
            data,received_at=_receipt(original,'market.market_data',seen_requests,day)
            record['retrieved_at']=received_at;received.append(received_at)
            values[kind]=_prices(data,symbol,maximum,first,day,fetch.budget.remaining)
        yield dict(symbol=symbol,adjusted=values['front_ratio'],received=received,
            status='observed' if values['front_ratio'] else 'empty')


def _aggregate(capture, manifest, members, universe_record, entries, day):
    fetch=capture.fetch
    stats=dict(above_count=0,equal_count=0,below_count=0,market_count=len(members),eligible_count=0,
        missing_count=len(members),stale_count=0,insufficient_count=0,adjustment_unverified_count=0,
        empty_count=0,invalid_count=0,partition_count=0)
    seen_symbols=set();received=[];members=set(members)
    with localcontext() as context:
        context.prec=40
        for entry in entries:
            fetch.budget.remaining()
            symbol=entry['symbol']
            member=symbol[-2:].lower()+'.'+symbol[:6]
            _need(member in members and symbol not in seen_symbols);seen_symbols.add(symbol)
            received.extend(entry['received'])
            adjusted=entry['adjusted']
            if entry['status']!='observed' or not adjusted:
                detail={'empty':'empty_count','invalid':'invalid_count','requires_partition':'partition_count'}.get(entry['status'])
                if detail:stats[detail]+=1
                continue
            stats['missing_count']-=1
            if day not in adjusted:stats['stale_count']+=1;continue
            if len(adjusted)<40:stats['insufficient_count']+=1;continue
            prices=[adjusted[d] for d in sorted(adjusted)[-40:]]
            if any(price<=0 for price in prices):
                stats['adjustment_unverified_count']+=1;continue
            # 40位Decimal仍会吞掉大数和极小数之和的尾差；原数值转有理数后精确比较。
            comparison=Fraction(prices[-1])*40-sum(map(Fraction,prices))
            stats['eligible_count']+=1
            stats['above_count' if comparison>0 else 'below_count' if comparison<0 else 'equal_count']+=1
    _need(stats['eligible_count']>0,'t2108_no_qualified_observations')
    percent=lambda count,total:float(Decimal(100)*count/total) if total else None
    row=dict(date=day,available_at=None,method_version='t2108.ashare/2',source_kind=capture.source_kind,source_received_at=max(received,key=_clock),**stats,
        above_sma40_pct=percent(stats['above_count'],stats['eligible_count']),
        market_above_sma40_pct=percent(stats['above_count'],len(members)) if stats['eligible_count']==len(members) else None,
        confirmed_market_lower_bound_pct=percent(stats['above_count'],len(members)),
        coverage_pct=percent(stats['eligible_count'],len(members)))
    return {METRIC:[row],UNIVERSE:[dict(date=day,market_count=len(members),
        universe_version=universe_record['sha256'],source_binding_sha256=manifest['source_binding_sha256'])]}
