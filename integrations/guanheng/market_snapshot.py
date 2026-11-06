"""WT数据快照接线；复用原市场服务与Reader，资料和价格从同一冻结版本读取。"""
from copy import deepcopy
import hashlib,json
from pathlib import Path
import threading

from ..guanheng_market_client import API_VERSION,MarketUnavailable,strict_json,encode_json,validate_request,validate_response
from ..guanheng_market_client.market_snapshot import validate_market_snapshot


class SnapshotSourceMarket:
    """创建线程独占base生命周期；无SDK、下载、调度或另一套行情存储。"""
    def __init__(self,config,*,max_response_bytes):
        if (type(config)is not dict or not {'mode','base','snapshot'}<=set(config)
                or set(config)-{'mode','base','snapshot','daily_facts','security_reference','calendar','supplement_facts'}or config['mode']!='source-market-snapshot'):
            raise ValueError('market snapshot configuration invalid')
        descriptor=config['snapshot']
        if type(descriptor)is not dict or set(descriptor)!={'path','sha256'}:
            raise ValueError('market snapshot descriptor invalid')
        path=Path(descriptor['path'])
        if not path.is_absolute():raise ValueError('market snapshot path invalid')
        before=path.stat()
        with path.open('rb')as stream:body=stream.read(16777217)
        after=path.stat()
        if (len(body)>16777216 or (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns)
                or hashlib.sha256(body).hexdigest()!=descriptor['sha256']):
            raise ValueError('market snapshot source differs')
        snapshot=validate_market_snapshot(strict_json(body))
        base_sha=hashlib.sha256(json.dumps(config['base'],ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf8')).hexdigest()
        if snapshot['provenance']['base_configuration_sha256']!=base_sha:
            raise ValueError('market snapshot base differs')
        from .source_market import create_native_source_market
        self._facts=None  # 固定补充事实目录及有界LRU，与本市场版本一起关闭。
        if 'daily_facts'in config:
            from .day_facts import DayFactsStore
            if (type(config['daily_facts'])is not dict
                    or snapshot['provenance'].get('daily_facts_sha256')!=config['daily_facts'].get('sha256')):
                raise ValueError('market snapshot daily facts differs')
            self._facts=DayFactsStore(config['daily_facts'])
        elif 'daily_facts_sha256'in snapshot['provenance']:
            raise ValueError('market snapshot daily facts missing')
        self._reference=None  # 本版本证券参考与日历；可缺项，关闭释放固定对象及索引。
        self._supplement=None  # 可选独立ETF/市场事实目录；同创建线程读取及关闭。
        try:
            expected=snapshot['provenance'].get('supplement_facts_sha256')
            if 'supplement_facts' in config:
                from .market_supplement_store import MarketSupplementStore
                if (type(config['supplement_facts']) is not dict
                        or expected != config['supplement_facts'].get('sha256')):
                    raise ValueError('market snapshot supplement facts differs')
                self._supplement=MarketSupplementStore(config['supplement_facts'],
                    observation_date=snapshot['observation_date'])
            elif expected is not None:
                raise ValueError('market snapshot supplement facts missing')
            for key in ('security_reference','calendar'):
                expected=snapshot['provenance'].get(key+'_sha256')
                if key in config:
                    if type(config[key])is not dict or expected!=config[key].get('sha256'):
                        raise ValueError('market snapshot reference differs')
                elif expected is not None:raise ValueError('market snapshot reference missing')
            from .security_reference import SecurityReference
            self._reference=SecurityReference(config.get('security_reference'),config.get('calendar'))
            self._base=create_native_source_market(config['base'],max_response_bytes=max_response_bytes)
        except BaseException:
            if self._facts is not None:self._facts.close()
            if self._reference is not None:self._reference.close()
            if self._supplement is not None:self._supplement.close()
            raise
        self._snapshot=snapshot;self._owner=threading.get_ident();self._closed=False

    def _check_owner(self):
        if self._closed or threading.get_ident()!=self._owner:
            raise MarketUnavailable('market snapshot owner unavailable')

    def call(self,request):
        """定日快照精确匹配；带snapshot_id的价格请求核版本后走原归档Reader。"""
        self._check_owner();request=validate_request(strict_json(encode_json(request)))
        if request['action']=='market.source-security-query':
            return self._security(request)
        if request['action']=='market.source-supplement-query':
            return self._supplement_query(request)
        if request['action']=='market.source-day-facts-query':
            query=request['request'];data={};code='Unavailable';reason='requested daily facts are not published'
            if query['snapshot_id']!=self._snapshot['snapshot_id']:
                code='Conflict';reason='market snapshot changed'
            elif self._facts is not None and query['date']<=self._snapshot['observation_date']:
                try:
                    data=self._facts.query(query['date'],self._snapshot['snapshot_id'])
                    if data is not None:code='Ok';reason=''
                    else:data={}
                except (OSError,ValueError,KeyError,TypeError):
                    code='IoError';reason='daily facts read failed';data={}
            return validate_response(dict(api_version=API_VERSION,status=dict(code=code,reason=reason),data=data),request)
        if request['action']=='market.source-snapshot-query':
            if request['request']['date']!=self._snapshot['observation_date']:
                response=dict(api_version=API_VERSION,status=dict(code='Unavailable',reason='requested market snapshot is not published'),data={})
            else:
                response=dict(api_version=API_VERSION,status=dict(code='Ok',reason=''),data=deepcopy(self._snapshot))
            return validate_response(response,request)
        if request['action']=='history.source-daily-query'and 'snapshot_id'in request['request']:
            if request['request']['snapshot_id']!=self._snapshot['snapshot_id']:
                return dict(api_version=API_VERSION,status=dict(code='Conflict',reason='market snapshot changed'),data={})
            internal=deepcopy(request);internal['request'].pop('snapshot_id');internal['request']['view']='archive'
            response=self._base.call(internal)
            if response['status']['code']=='Ok':response['data']['source_snapshot_id']=self._snapshot['snapshot_id']
            return validate_response(response,request)
        return self._base.call(request)

    def _supplement_query(self,request):
        """原件查询不采集；缺装配、快照冲突和源损坏保持不同业务状态。"""
        query=request['request'];data={};code='Ok';reason=''
        if query['snapshot_id']!=self._snapshot['snapshot_id']:
            code='Conflict';reason='market snapshot changed'
        elif self._supplement is None:
            code='NotSupported';reason='market supplement facts are not configured'
        else:
            try:
                data=self._supplement.query(query)
            except (OSError,ValueError,KeyError,TypeError):
                code='IoError';reason='market supplement facts read failed';data={}
        return validate_response(dict(api_version=API_VERSION,status=dict(code=code,reason=reason),data=data),request)

    def _security(self,request):
        """资料和实际日期沿同一版本；真实价格错误保持原错误类别。"""
        query=request['request'];code='Ok';reason='';data={}
        if query['snapshot_id']!=self._snapshot['snapshot_id']:
            code='Conflict';reason='market snapshot changed'
        else:
            try:
                exchange,security_code=query['symbol'].split('.')
                prices=self._base.call(dict(api_version=API_VERSION,action='history.source-daily-query',request=dict(
                    exchange=exchange,code=security_code,**{'from':query['from'],'to':query['to'],'limit':2000},
                    adjustment=query['adjustment'],view='archive',include_archive=True)))
                if prices['status']['code']not in ('Ok','Unavailable'):
                    code=prices['status']['code'];reason=prices['status']['reason']
                else:
                    security=self._reference.security(self._snapshot,query['symbol'])
                    if prices['status']['code']=='Unavailable'and security['security_type']=='unknown'and security['name']is None:
                        code='Unavailable';reason='requested security is not registered'
                    else:
                        dates=[bar['date']for bar in prices['data'].get('bars',[])]
                        data=dict(
                            security=security,  # 原证券资料，名称/日期缺项独立于价格可用性。
                            source_snapshot_id=self._snapshot['snapshot_id'],  # 同一价格/资料/日事实版本身份。
                            adjustment=query['adjustment'],  # 请求的明确价格口径。
                            history_status=prices['status'],  # 原日线Ok或Unavailable，价格读取错误直接传播。
                            archive=prices['data'].get('archive'),  # 实际全档首尾及记录数，来源未知时None。
                            available_dates=dates,  # 请求窗口内实际原生记录日期，最多366日。
                            gap_assessment=self._reference.assess(query,security,dates,self._facts),  # 有来源资格的互斥日期分类。
                            reference_sha256=self._reference.reference_sha256)  # 冻结资料摘要，缺配置时None。
            except (OSError,ValueError,KeyError,TypeError):
                code='IoError';reason='security reference or daily history read failed';data={}
        return validate_response(dict(api_version=API_VERSION,status=dict(code=code,reason=reason),data=data),request)

    def close(self):
        if self._closed:return
        self._check_owner()
        try:self._base.close()
        finally:
            if self._facts is not None:self._facts.close()
            if self._reference is not None:self._reference.close()
            if self._supplement is not None:self._supplement.close()
            self._closed=True
