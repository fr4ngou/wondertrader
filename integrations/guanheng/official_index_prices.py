"""数据owner的显式官方指数原价补充；原件留证，读取侧继续只读WT原生档。

持久协议：REQUEST的request保存证券和日期选择，capture_id是本次随机身份。
每个HTTP原件的url是固定发布者URL，state区分接收/传输失败，received_at是UTC
接收时刻，error_type只存错误类型；status为HTTP状态，body_sha256绑定原字节，
body_b64保存未经投影的原响应。manifest的request/evidence分别固定选择及全部
HTTP原件描述符。结果中basic为官方身份依据，provider区分CSI/CNI；state/reason
表达取得状态和目标日原因，data保存逐日原六字段，unqualified_dates逐日留因。
source_failures保存证券与接口到固定错误码的映射。所有描述符的path是受控绝对
路径，sha256固定该文件字节；该身份不表示历史PIT或对外分发资格。
"""
from datetime import datetime, timezone, timedelta
import base64
import hashlib
import math
from pathlib import Path
import re
import time
import unicodedata
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen
from uuid import uuid4

from .analysis_price_capture import original_price_quality
from .daily_data_update import _save, _load, _descriptor
from .market_generation import read_fixed,encode
from ..guanheng_market_client import strict_json
from ..guanheng_market_client.source_history import validate_source_metadata

_BASE = 'https://www.csindex.com.cn/csindex-home/'
_MAX_BODY = 8388608
_CNI = 'https://hq.cnindex.com.cn/market/market/getIndexDailyData?'
_MAX_RESULT = 268435456
_REQUEST_INTERVAL = .75


def _result_descriptor(path):
    """结果按独立256MiB预算固定身份，原通用16MiB元数据预算保持。"""
    path=Path(path).absolute()
    return dict(path=str(path),sha256=hashlib.sha256(read_fixed(path,maximum=_MAX_RESULT)).hexdigest())


def _name(value):
    return ''.join(unicodedata.normalize('NFKC', value).split()) if type(value) is str else None


def _decode_record(record,url):
    """采集、恢复和落盘共用原HTTP字节及业务应答准入，返回数据和固定失败码。"""
    if record['url']!=url:raise ValueError('official index saved request differs')
    if record['state']!='received':return None,'source_transport_unavailable'
    raw=base64.b64decode(record['body_b64'],validate=True)
    if len(raw)>_MAX_BODY or hashlib.sha256(raw).hexdigest()!=record['body_sha256']:
        raise ValueError('official index saved response differs')
    if record['status']!=200:return None,'source_http_'+str(record['status'])
    try:value=strict_json(raw)
    except ValueError:return None,'source_json_invalid'
    if type(value)is not dict or value.get('code')not in('200',200):return None,'source_reply_unavailable'
    return value.get('data'),None


def _identity(identity,basic,response):
    """官方基本资料或官方每行代码/全简称共同确证身份，缺证据保持未知。"""
    code=identity['symbol'].split('.')[1];name=_name(identity.get('name'))
    if name is None:return None
    if type(basic)is dict and basic:
        return basic if (basic.get('indexCode')==code and name in {
            _name(basic.get('indexShortNameCn')),_name(basic.get('indexFullNameCn'))})else None
    if type(response)is not list or not response:return None
    for row in response:
        if (type(row)is not dict or row.get('indexCode')!=code or name not in {
                _name(row.get('indexNameCn')),_name(row.get('indexNameCnAll'))}):return None
    row=response[0]
    return dict(indexCode=code,indexShortNameCn=row.get('indexNameCn'),
        indexFullNameCn=row.get('indexNameCnAll'),indexType=None,identity_evidence='official_price_rows')


def parse_prices(identity, basic, response, first, last):
    """核官方身份及每个原始字段；原值不换算，不以收盘值构造其他字段。"""
    code=identity['symbol'].split('.')[1]
    if _identity(identity,basic,response)is None:
        return dict(state='unavailable',reason='official_identity_unqualified',data={},unqualified_dates={})
    if type(response)is not list or len(response)>10000:
        raise ValueError('official index response rows invalid')
    rows={};bad={};seen=set()
    for item in response:
        if type(item)is not dict or item.get('indexCode')!=code:
            raise ValueError('official index response identity differs')
        day=item.get('tradeDate')
        if type(day)is not str or re.fullmatch(r'[0-9]{8}',day)is None:
            raise ValueError('official index date invalid')
        datetime.strptime(day,'%Y%m%d')
        if not first<=day<=last or day in seen:
            raise ValueError('official index date outside selection or duplicated')
        seen.add(day)
        fields={'open':'open','high':'high','low':'low','close':'close','volume':'tradingVol','amount':'tradingValue'}
        if any(item.get(key) is None for key in fields.values()):
            bad[day]='source_fields_missing';continue
        bar={key:item[field]for key,field in fields.items()}
        try:reason=original_price_quality(bar)
        except OverflowError:reason='source_nonfinite_fields'
        if reason!='qualified':bad[day]=reason
        else:rows[day]=bar
    return dict(
        state='observed'if rows else'invalid'if bad else'empty',  # 原官方原件是否提供合格完整行。
        reason='available'if last in rows else'official_target_invalid'if last in bad else'official_target_absent',  # 仅针对原闭合目标日。
        data=rows,  # 六字段原数值，单位资格由元数据分别表达。
        unqualified_dates=bad)  # 缺值/非有限/零价/矛盾逐日保留，不填0。


def parse_cni_prices(identity,response,first,last):
    """国证官方列名与毫秒时点适配；仅核对实际返回的指数身份，不猜代码类型。"""
    if (type(response)is not dict or response.get('indexCode')!=identity['symbol'].split('.')[1]
            or _name(response.get('indexName'))!=_name(identity.get('name'))
            or _name(identity.get('name'))is None):
        return dict(state='unavailable',reason='official_identity_unqualified',data={},unqualified_dates={},basic=None)
    columns=response.get('item');rows=response.get('data')
    if (type(columns)is not list or len(columns)!=len(set(columns))or len(columns)>64
            or not {'timestamp','open','high','low','close','volume','amount'}<=set(columns)
            or type(rows)is not list or len(rows)>10000):
        raise ValueError('official CNI columns or rows invalid')
    basic=dict(indexCode=response['indexCode'],indexShortNameCn=response['indexName'],indexFullNameCn=response['indexName'],indexType=None)
    projected=[]
    for values in rows:
        if type(values)is not list or len(values)!=len(columns):raise ValueError('official CNI row invalid')
        row=dict(zip(columns,values));stamp=row['timestamp']
        if type(stamp)not in(int,float)or not math.isfinite(stamp):raise ValueError('official CNI timestamp invalid')
        instant=datetime.fromtimestamp(stamp/1000,timezone.utc).astimezone(timezone(timedelta(hours=8)))
        if instant.hour or instant.minute or instant.second or instant.microsecond:
            raise ValueError('official CNI timestamp is not source day boundary')
        projected.append(dict(indexCode=basic['indexCode'],tradeDate=instant.strftime('%Y%m%d'),
            open=row['open'],high=row['high'],low=row['low'],close=row['close'],tradingVol=row['volume'],tradingValue=row['amount']))
    return dict(parse_prices(identity,basic,projected,first,last),basic=basic)


def _project(identity,basic,csi,cni,first,last):
    """同一来源选择规则用于采集与恢复；新取得的旧日也保留原发布者身份。"""
    if csi is None:
        chosen=dict(state='unavailable',reason='official_source_unavailable',data={},unqualified_dates={},basic=basic)
    else:chosen=dict(parse_prices(identity,basic,csi,first,last),basic=_identity(identity,basic,csi))
    chosen['provider']='CSI';values=dict(chosen['data']);bad=dict(chosen['unqualified_dates'])
    origins={day:'CSI'for day in values};basics={'CSI':chosen['basic']}
    if cni is not None:
        alternative=dict(parse_cni_prices(identity,cni,first,last),provider='CNI')
        basics['CNI']=alternative['basic'];bad.update(alternative['unqualified_dates'])
        for day,bar in alternative['data'].items():
            if day not in values:values[day]=bar;origins[day]='CNI'
        if last in alternative['data']or not chosen['data']:chosen=alternative
    bad={day:reason for day,reason in bad.items()if day not in values}
    chosen.update(data=values,unqualified_dates=bad,
        provider_by_date=origins,  # 每日实际入选的官方发布者，CSI既有行优先。
        source_basics=basics)  # 每个发布者自己的原身份依据，供逐源单位准入。
    if values:chosen['state']='observed'
    if last in values:chosen['reason']='available'
    elif last in bad:chosen['reason']='official_target_invalid'
    return chosen


def prepare_official_index_prices(securities, first, last, directory, *, deadline, cancelled=lambda:False):
    """单调用线程及目录owner；有限GET原件可恢复，未保存请求可安全重新读取。

    单原件8MiB、总原件256MiB、最多2048证券；原请求/响应独立存证，来源失败逐项
    保留。当前Source SDK未知责任不由本函数确认、重派或修改。返回不可变结果描述符。
    """
    if (type(securities)is not dict or not 1<=len(securities)<=2048 or not callable(cancelled)
            or type(deadline)not in(int,float)or not math.isfinite(deadline)):
        raise ValueError('official index preparation scope or deadline invalid')
    begin=datetime.strptime(first,'%Y%m%d');end=datetime.strptime(last,'%Y%m%d')
    if first>last or (end-begin).days>3660:raise ValueError('official index range invalid')
    for symbol,identity in securities.items():
        if (re.fullmatch(r'(SSE|SZSE|BSE)\.[0-9]{6}',symbol)is None or identity.get('symbol')!=symbol
                or identity.get('security_type')!='index'):
            raise ValueError('official index security identity invalid')
    root=Path(directory).absolute();root.mkdir(exist_ok=True)
    original=root/'REQUEST.json';request=dict(
        securities=securities,  # 原Source已确认价格指数身份，不由官网补推证券类型。
        first=first,  # 授权历史起日，YYYYMMDD。
        last=last)  # 闭合目标日，YYYYMMDD。
    if original.exists():
        if _load(_descriptor(original))['request']!=request:raise ValueError('official index original request differs')
    else:_save(original,dict(
        request=request,  # 本轮固定证券身份和起止交易日。
        capture_id=str(uuid4())))  # 该原件集合的随机会话身份，恢复保持。
    original_value=_load(_descriptor(original));capture_id=original_value['capture_id']
    final=root/'RESULT.json'
    if final.exists():
        descriptor=_result_descriptor(final);load_official_index_prices(descriptor);return descriptor
    total=0;evidence=[];outputs={};failures={};last_call=0
    def check():
        if cancelled():raise InterruptedError('official index preparation stopped')
        if time.monotonic()>=deadline:raise TimeoutError('official index preparation deadline')
    def get(symbol,kind,path):
        nonlocal total,last_call
        check();url=path if path.startswith('https://')else _BASE+path;file=root/(symbol+'-'+kind+'.json')
        host=urlsplit(url).hostname
        if host not in('www.csindex.com.cn','hq.cnindex.com.cn'):raise ValueError('official publisher differs')
        if file.exists():record=_load(_descriptor(file),16777216)
        else:
            # 所有证券共享单线程节奏；阻塞期间仍核原截止和取消，避免批捕获突发请求。
            while time.monotonic()-last_call<_REQUEST_INTERVAL:
                check();time.sleep(max(0,min(.05,_REQUEST_INTERVAL-(time.monotonic()-last_call))))
            last_call=time.monotonic()
            response=None
            try:
                response=urlopen(Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; GuanhengDailyData/1.0)','Referer':'https://'+host+'/'}),
                    timeout=min(10,max(.1,deadline-time.monotonic())))
            except HTTPError as error:response=error
            except (OSError,TimeoutError)as error:
                record=dict(
                    url=url,  # 固定官方接口及原参数。
                    state='unavailable',  # 本项未收到完整原响应。
                    error_type=type(error).__name__,  # 固定异常类型，不存异常正文。
                    received_at=datetime.now(timezone.utc).isoformat())  # 本次失败观察的UTC时刻。
            if response is not None:
                try:
                    if urlsplit(response.geturl()).hostname!=host:
                        raise ValueError('official index response redirected outside publisher')
                    chunks=[];size=0
                    while True:
                        check();chunk=response.read(min(65536,_MAX_BODY+1-size));size+=len(chunk)
                        if size>_MAX_BODY:raise ValueError('official index raw response exceeds capacity')
                        if not chunk:break
                        chunks.append(chunk)
                    body=b''.join(chunks)
                    record=dict(
                        url=url,  # 固定官方请求URL及原参数。
                        state='received',  # 完整响应已接收，业务可用性另核。
                        status=response.status,  # 原HTTP状态码。
                        received_at=datetime.now(timezone.utc).isoformat(),  # 本次接收UTC时刻。
                        body_sha256=hashlib.sha256(body).hexdigest(),  # 原响应字节摘要。
                        body_b64=base64.b64encode(body).decode('ascii'))  # 原响应全部字节，不重编码JSON。
                finally:response.close()
            _save(file,record)
        evidence.append(_descriptor(file));total+=file.stat().st_size
        if total>268435456:raise ValueError('official index raw capture exceeds total capacity')
        key=symbol+':'+kind
        data,error=_decode_record(record,url)
        if error is not None:failures[key]=error
        return data
    for symbol,identity in sorted(securities.items()):
        check();code=symbol.split('.')[1]
        basic=get(symbol,'basic','indexInfo/index-basic-info/'+code)
        response=get(symbol,'prices','perf/index-perf?'+urlencode(dict(indexCode=code,startDate=first,endDate=last)))
        outputs[symbol]=_project(identity,basic,response,None,first,last)
        if last not in outputs[symbol]['data']and symbol.startswith('SZSE.'):
            url=_CNI+urlencode(dict(indexCode=code,startDate=begin.strftime('%Y-%m-%d'),endDate=end.strftime('%Y-%m-%d'),pageNum=1,pageSize=10000))
            other=get(symbol,'cni-prices',url)
            if other is not None:outputs[symbol]=_project(identity,basic,response,other,first,last)
    manifest=dict(
        schema='guanheng.official-index-capture.v1',  # 官方捕获原件目录版本。
        request=_descriptor(original),  # 固定原范围与capture_id的文件。
        evidence=evidence)  # 每项原HTTP响应描述符，保留失败原件。
    _save(root/'manifest.json',manifest);identity=_descriptor(root/'manifest.json')['sha256']
    for row in outputs.values():
        row['metadata_by_provider']={}  # 逐发布者元数据，逐日provenance只使用自己的单位和身份。
        for provider,basic in row['source_basics'].items():
            stock=type(basic)is dict and basic.get('indexType')=='stock'
            metadata=dict(
                source=dict(provider=provider,instance_id='official-index:'+identity[:32],session_id=capture_id,generation=1),  # 本次原件集合身份。
                qualification='DevelopmentVerified',  # 实际数据链；历史PIT及再分发资格分别保留。
                dataset_version=provider.lower()+'.official-index.raw-points.v1',  # 官方指数点位原值，不误称股票人民币价格。
                source_license=provider+' public website; redistribution terms not qualified',  # 原来源，未推造分发授权。
                adjustment='none',factor_version='',  # 原官方发布点位，不生成供应商前复权。
                minute_boundary='unknown',timezone='Asia/Shanghai',period='1d',  # 原交易日期，非接收时刻。
                content_id=identity,value_semantics='source',timestamp_semantics='source_date',  # 数值及逐项HTTP谱系固定。
                price_unit='unknown',  # 旧公开枚举无指数点位，数据集语义明确且不赋CNY。
                volume_unit='share'if stock else'unknown',  # 官网明确股票指数为股，债券张不冒用股票股数。
                amount_unit='unknown')  # 原tradingValue数值保留，未独立授其标准化比例。
            row['metadata_by_provider'][provider]=validate_source_metadata(metadata,period='1d')
        row['metadata']=row['metadata_by_provider'][row['provider']]  # 目标日采用者的概览；实际写入按provider_by_date。
    result=dict(
        schema='guanheng.official-index-prices.v2',  # 逐日发布者及完整历史并集投影版本。
        first=first,  # 原请求起日，不把接口返回范围扩展为授权范围。
        last=last,  # 同一闭合目标日。
        capture=_descriptor(root/'manifest.json'),  # 固定全部原件及选择的谱系。
        securities=outputs,  # 逐证券身份、合格原值、原因及单位元数据。
        source_failures=failures)  # 原接口失败分类，其他成功证券继续使用。
    if len(encode(result))>_MAX_RESULT:raise ValueError('official index derived result exceeds capacity')
    _save(final,result);return _result_descriptor(final)


def load_official_index_prices(descriptor):
    """恢复/落盘时核原结果、固定目录及全部HTTP原件；不连接官网或修改来源记录。"""
    result=_load(descriptor,_MAX_RESULT);capture=result['capture'];root=Path(capture['path']).parent.resolve()
    if result.get('schema')not in('guanheng.official-index-prices.v1','guanheng.official-index-prices.v2'):
        raise ValueError('official index result schema invalid')
    manifest=_load(capture)
    if manifest.get('schema')not in('guanheng.csi-daily-capture.v1','guanheng.official-index-capture.v1')or len(manifest['evidence'])>6144:
        raise ValueError('official index capture lineage invalid')
    if Path(manifest['request']['path']).resolve()!=root/'REQUEST.json':
        raise ValueError('official index original request escaped')
    original=_load(manifest['request'])['request']
    if (set(result['securities'])!=set(original['securities'])or result['first']!=original['first']
            or result['last']!=original['last']):
        raise ValueError('official index capture selection differs')
    total=0;records={}
    for item in manifest['evidence']:
        path=Path(item['path']).resolve(strict=True)
        if not path.is_relative_to(root):raise ValueError('official index raw evidence escaped')
        body=read_fixed(path,maximum=16777216,identity=item['sha256']);total+=len(body)
        if total>268435456:raise ValueError('official index retained capture exceeds total capacity')
        if path.name in records:raise ValueError('official index raw evidence repeated')
        record=strict_json(body)
        if record['state']=='received':
            raw=base64.b64decode(record['body_b64'],validate=True)
            if len(raw)>_MAX_BODY or hashlib.sha256(raw).hexdigest()!=record['body_sha256']:
                raise ValueError('official index retained raw body differs')
        records[path.name]=record
    for symbol,entry in result['securities'].items():
        validate_source_metadata(entry['metadata'],period='1d')
        if entry['metadata']['content_id']!=capture['sha256']:raise ValueError('official index metadata differs')
        if any(original_price_quality(bar)!='qualified'for bar in entry['data'].values()):
            raise ValueError('official index materialized rows invalid')
        code=symbol.split('.')[1]
        first=datetime.strptime(result['first'],'%Y%m%d').strftime('%Y-%m-%d')
        last=datetime.strptime(result['last'],'%Y%m%d').strftime('%Y-%m-%d')
        urls=(('basic',_BASE+'indexInfo/index-basic-info/'+code),
            ('prices',_BASE+'perf/index-perf?'+urlencode(dict(indexCode=code,startDate=result['first'],endDate=result['last']))),
            ('cni-prices',_CNI+urlencode(dict(indexCode=code,startDate=first,endDate=last,pageNum=1,pageSize=10000))))
        decoded=[]
        for kind,url in urls:
            record=records.get(symbol+'-'+kind+'.json')
            if record is None:
                if kind!='cni-prices':raise ValueError('official index original response absent')
                decoded.append(None);continue
            data,error=_decode_record(record,url);decoded.append(None if error else data)
        if result['schema']=='guanheng.official-index-prices.v1':
            # v1以单一入选发布者定义输出；沿原合同恢复，不拿v2并集改写旧结果资格。
            provider=entry['metadata']['source']['provider']
            if provider=='CNI':projection=parse_cni_prices(original['securities'][symbol],decoded[2],result['first'],result['last'])
            elif decoded[1]is None:projection=dict(data={})
            else:projection=parse_prices(original['securities'][symbol],decoded[0],decoded[1],result['first'],result['last'])
        else:projection=_project(original['securities'][symbol],*decoded,result['first'],result['last'])
        if projection['data']!=entry['data']:raise ValueError('official index rows differ from retained raw response')
        if result['schema']=='guanheng.official-index-prices.v2':
            for key in('provider','provider_by_date','source_basics'):
                if entry[key]!=projection[key]:raise ValueError('official index per-day publisher differs')
            sources=entry['metadata_by_provider']
        else:
            # v1只有单一发布者；保留旧原件，只在该原证明确能解释全部行时作读取投影。
            provider=entry['metadata']['source']['provider']
            sources={provider:entry['metadata']};entry['provider_by_date']={day:provider for day in entry['data']};entry['metadata_by_provider']=sources
        for provider,metadata in sources.items():
            validate_source_metadata(metadata,period='1d')
            if metadata['source']['provider']!=provider or metadata['content_id']!=capture['sha256']:
                raise ValueError('official index per-publisher metadata differs')
        if not set(entry['provider_by_date'].values())<=set(sources):raise ValueError('official index per-day metadata absent')
    return result
