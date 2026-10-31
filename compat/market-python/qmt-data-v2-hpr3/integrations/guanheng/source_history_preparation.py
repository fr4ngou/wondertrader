"""显式源值按需补齐：原bound收据、原Importer和原Reader的有限编排。"""
from __future__ import annotations

import csv
from datetime import datetime,timedelta,timezone
import hashlib
import io
from itertools import chain
import os
from pathlib import Path
import re
import threading
import time
from uuid import uuid4

from guanheng_qmt_shm_agent.protocol import canonical,decode
from guanheng_qmt_shm_agent.history_1m import validated_row
from guanheng_qmt_shm.private_files import create_private_directory,write_private_new
from ..guanheng_market_client import API_VERSION,MarketUnavailable,validate_request,validate_response
from .models import IntegrationUnavailable
from .qmt_minute_import import import_dataset,_Native
from .source_market import NativeSourceMarket,create_native_source_market
from .quote_collection_service import _inspect,_read
from .source_history_transport import BoundHistorySource,SourcePending,require
from .source_history_selection import select_sources,SourceSelectionConflict
from . import source_history_followup as followup

SHANGHAI=timezone(timedelta(hours=8))


class SourcePreparationBudget(ValueError):
    """仅表示显式本地准备额度；原任务身份和已有值保持。"""


def budget(value):
    if not value:raise SourcePreparationBudget('explicit source preparation budget')


def stamp(value):
    return datetime.strptime(str(value),'%Y%m%d%H%M').replace(tzinfo=SHANGHAI)


def label(value):
    return int(value.strftime('%Y%m%d%H%M'))


def failure(code,reason):
    return dict(api_version=API_VERSION,status=dict(code=code,reason=reason),data={})


class SourcePreparingMarket:
    """创建线程独占；旧根与至多一个窗口Reader各有显式缓存额度。"""

    def __init__(self,configuration,*,environ=None,clock=time.monotonic,wall_clock=time.time):
        self.owner=threading.get_ident();self.base=self.overlay=self.lock=None
        self.overlay_key=None;self.closed=False;self.clock=clock;self.wall_clock=wall_clock
        try:
            require(type(configuration)is dict and set(configuration)=={'mode','base','preparation'}and configuration['mode']=='source-preparing')
            self.base_configuration=configuration['base'];c=configuration['preparation']
            require(type(c)is dict and set(c)-{'follow_up','symbols'}=={'enabled','workspace','host','helper','source_profile',
                'timeout_seconds','max_windows','max_window_minutes','max_pages','max_rows','max_bytes','overlay_cache_bars','max_import_attempts'})
            require(c['enabled']is True)
            self.follow=followup.configuration(c['follow_up'])if 'follow_up'in c else None
            self.receipt_schema='qmt.source-history-preparation-receipt.v2'if self.follow else'qmt.source-history-preparation-receipt.v1'
            for key,maximum in [('max_windows',1024),('max_window_minutes',7200),('max_pages',128),
                    ('max_rows',100000),('max_bytes',67108864),('overlay_cache_bars',1000000),('max_import_attempts',16)]:
                require(type(c[key])is int and 1<=c[key]<=maximum)
            require(type(c['timeout_seconds'])in(int,float)and .1<=c['timeout_seconds']<=30)
            # 正式配置省略symbols，查询按来源支持的市场进入补齐。
            # 旧配置的显式测试范围保留原语义，避免改写原收据身份。
            if 'symbols'in c:
                require(type(c['symbols'])is list and 1<=len(c['symbols'])<=128 and len(set(c['symbols']))==len(c['symbols'])
                    and all(type(s)is str and re.fullmatch(r'[0-9]{6}\.(SH|SZ)',s)for s in c['symbols']))
            require(type(c['helper'])is dict and set(c['helper'])=={'library','sha256'})
            self.c=decode(canonical(c));self.identity=hashlib.sha256(canonical(configuration)).hexdigest()
            self.root=Path(c['workspace']);require(self.root.is_absolute()and self.root.drive.upper()=='E:')
            _inspect(self.root.parent,True)
            if not self.root.exists():create_private_directory(self.root)
            _inspect(self.root,True)
            marker=self.root/'configuration.json'
            if marker.exists():require(_read(marker,c['max_bytes'])==canonical(configuration))
            else:write_private_new(marker,canonical(configuration))
            owner=self.root/'owner.lock'
            if not owner.exists():write_private_new(owner,b'0')
            _inspect(owner);self.lock=owner.open('r+b')
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(self.lock.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self.lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            self._members()
            self.source=BoundHistorySource(c['host'],environ=environ,clock=clock)
            helper=Path(c['helper']['library'])
            require(helper.is_absolute());_inspect(helper)
            require(helper.stat().st_nlink==1)
            # 制品和ABI在任何SDK副作用前核验，仍复用Importer唯一加载逻辑。
            dependency=_Native(helper,c['helper']['sha256']);dependency.close()
            self.base=create_native_source_market(configuration['base'])
            self._profile(None,'validation-only')
        except BaseException:
            self.close();raise

    def _check(self):
        require(threading.get_ident()==self.owner and not self.closed)

    def _members(self):
        count=0
        for path in self.root.iterdir():
            if path.name in ('configuration.json','owner.lock'):continue
            require(re.fullmatch('[0-9a-f]{64}',path.name)is not None)
            _inspect(path,True);count+=1
            require(count<=self.c['max_windows'])
        return count

    def _save(self,directory,state):
        raw=canonical(state);require(len(raw)<=self.c['max_bytes'])
        count=temporary_count=0
        for path in directory.iterdir():
            count+=1;require(count<=2*self.c['max_import_attempts']+1)
            if re.fullmatch(r'receipt-[0-9a-f]{32}\.tmp',path.name):
                temporary_count+=1
        require(temporary_count<self.c['max_import_attempts'])
        temporary=directory/('receipt-'+uuid4().hex+'.tmp')
        write_private_new(temporary,raw);os.replace(temporary,directory/'receipt.json')

    def _state(self,query):
        selected={key:query[key]for key in ('exchange','code','from','to')}
        key=hashlib.sha256(canonical(selected)).hexdigest();directory=self.root/key
        if not directory.exists():
            budget(self._members()<self.c['max_windows']);create_private_directory(directory)
        _inspect(directory,True)
        if (directory/'receipt.json').exists():
            state=decode(_read(directory/'receipt.json',self.c['max_bytes']))
            require(state['schema']==self.receipt_schema and
                state['configuration_sha256']==self.identity and state['query']==selected)
        else:
            # 首收据提交前没有任何源调用。原子replace保留旧receipt；缺少最终
            # receipt且仅有首写临时文件，才有资格重建尚未派发的窗口。
            count=0
            for path in directory.iterdir():
                count+=1;require(count<=self.c['max_import_attempts'])
                require(re.fullmatch(r'receipt-[0-9a-f]{32}\.tmp',path.name)is not None);_inspect(path)
            state=dict(schema=self.receipt_schema,configuration_sha256=self.identity,
                query=selected,window_id=str(uuid4()),before=None,prepare=None,after=None,published=None,empty=False,imports=[])
            if self.follow:state['follow_up']=None
            self._save(directory,state)
        return key,directory,state

    def _profile(self,binding,version):
        profile=self.c['source_profile']
        fields={'dataset_version','source_license','input_kind','timezone','minute_boundary','adjustment','factor_version',
            'value_semantics','price_unit','volume_unit','amount_unit'}
        require(type(profile)is dict and set(profile)==fields)
        require(profile['value_semantics']=='source'and profile['adjustment']=='none'and profile['factor_version']==''
            and profile['timezone']=='Asia/Shanghai'and profile['minute_boundary']in('left','right','unknown')
            and profile['price_unit']in('CNY','unknown')and profile['volume_unit']in('share','lot','unknown')
            and profile['amount_unit']in('CNY','unknown')and profile['input_kind']in('synthetic','qmt_export'))
        require(all(type(profile[k])is str and 1<=len(profile[k])<=128 for k in('dataset_version','source_license')))
        source=dict(provider='Qmt',instance_id='validation',session_id='validation',generation=1)
        if binding is not None:
            source.update(instance_id=binding['host_instance_id'],
                # 原运输generation是nonce字符串；不伪造序号。完整B摘要区分每代，
                # generation=1表示这一份固定绑定捕获，原nonce完整留在采集收据。
                session_id='shm:'+hashlib.sha256(canonical(binding)).hexdigest(),generation=1)
        return dict(profile,**source,dataset_version=profile['dataset_version']+':'+version)

    def _reads(self,state,phase,directory,symbol,start,end,deadline,*,holder=None):
        save=lambda:self._save(directory,state)
        holder=state if holder is None else holder
        if holder[phase]is None:
            metadata=self.source.binding(deadline)
            if self.follow:
                self._capacity(metadata['limits'])
            limits=metadata['profile']['operation_profiles']['market.history_1m']['limits']
            maximum=limits['max_rows'];calendar_days=limits['max_calendar_days']
            require(maximum>=2)
            pages=[];cursor=start
            while cursor<=end:
                budget(len(pages)<self.c['max_pages'])
                calendar_end=cursor.replace(hour=0,minute=0)+timedelta(days=calendar_days,minutes=-1)
                last=min(end,cursor+timedelta(minutes=maximum-2),calendar_end)
                arguments=dict(symbol=symbol,start_time=cursor.strftime('%Y%m%d%H%M00'),end_time=last.strftime('%Y%m%d%H%M00'),max_rows=maximum)
                pages.append(self.source.plan('market.history_1m',arguments,metadata,deadline))
                cursor=last+timedelta(minutes=1)
            holder[phase]=dict(binding=metadata['binding'],pages=pages);save()
        pages=holder[phase]['pages']
        require(type(pages)is list and 1<=len(pages)<=self.c['max_pages'])
        rows=[];previous=None;cursor=start
        for record in pages:
            if self.follow:
                self._capacity(record['limits'])
            args=record['request']['arguments']
            require(record['request']['operation_id']=='market.history_1m'and record['binding']==holder[phase]['binding']
                and args['symbol']==symbol and args['start_time']==cursor.strftime('%Y%m%d%H%M00'))
            last=stamp(int(args['end_time'][:12]))
            limits=record['profile']['operation_profiles']['market.history_1m']['limits']
            require(args['end_time']==last.strftime('%Y%m%d%H%M00')and cursor<=last<=end
                and args['max_rows']==limits['max_rows']and(last.date()-cursor.date()).days<limits['max_calendar_days']
                and int((last-cursor).total_seconds()/60)+1<args['max_rows'])
            cursor=last+timedelta(minutes=1)
            result=self.source.observe(record,save,deadline)
            require(result['ok']is True)
            data=result['data'];args=record['request']['arguments']
            require(type(data)is dict and set(data)=={'schema_version','symbol','period','start_time','end_time','max_rows','rows','coverage','source_options'}
                and data['schema_version']=='qmt.history-1m.v1'and data['symbol']==symbol and data['period']=='1m'
                and data['start_time']==args['start_time']and data['end_time']==args['end_time']and data['max_rows']==args['max_rows']
                and data['coverage']=='unknown'and data['source_options']==dict(dividend_type='none',fill_data=False,subscribe=False))
            require(type(data['rows'])is list and len(data['rows'])<args['max_rows'])
            for row in data['rows']:
                require(type(row)is dict and set(row)=={'time','open','high','low','close','volume','amount'})
                checked=validated_row(tuple(row[k]for k in('time','open','high','low','close','volume','amount')),
                    stamp(int(args['start_time'][:12])).timestamp()*1000,stamp(int(args['end_time'][:12])).timestamp()*1000,previous)
                rows.append(checked);previous=checked[0];require(len(rows)<=self.c['max_rows'])
        require(cursor==end+timedelta(minutes=1))
        # 完整窗口读前后来源固定；新代不能把旧片重标为本次来源。
        if not holder.get('verified',False):require(self.source.binding(deadline)['binding']==holder[phase]['binding'])
        return rows,holder[phase]['binding']

    def _capacity(self,limits):
        try:followup.capacity(self.follow,self.c['max_windows'],self.c['max_pages'],limits)
        except followup.FollowUpExhausted as error:raise SourcePreparationBudget(str(error))from None

    def _publish(self,state,directory,symbol,rows,binding,deadline):
        if not rows:
            state['empty']=True;self._save(directory,state);raise SourcePending('source cache window is empty')
        stream=io.StringIO(newline='');writer=csv.writer(stream);writer.writerow(('timestamp','open','high','low','close','volume','amount'))
        for row in rows:writer.writerow((datetime.fromtimestamp(row[0]/1000,SHANGHAI).isoformat(),*(repr(float(v))for v in row[1:])))
        csv_bytes=stream.getvalue().encode('utf8');budget(len(csv_bytes)<=self.c['max_bytes'])
        profile=self._profile(binding,hashlib.sha256(canonical(binding)).hexdigest()[:16]+':'+state['window_id'])
        manifest=canonical(dict(schema_version=2,profile=profile,securities=[dict(symbol=symbol,chunks=[dict(path='bars.csv',sha256=hashlib.sha256(csv_bytes).hexdigest())])]))
        manifest_path,store=self._import_target(state,directory,csv_bytes,manifest)
        if self.clock()>=deadline:raise SourcePending('source deadline')
        if not store.exists():
            import_dataset(manifest_path,store,self.c['helper']['library'],self.c['helper']['sha256'],
                max_bars=self.c['max_rows'],max_input_bytes=self.c['max_bytes'],max_total_bars=self.c['max_rows'])
        receipt=store/'qmt-import.json';raw=_read(receipt,self.c['max_bytes'])
        verified=decode(raw)
        require(verified['schema_version']==2 and verified['status']=='passed'and verified['profile']==profile
            and verified['manifest_sha256']==hashlib.sha256(manifest).hexdigest()
            and verified['helper_sha256']==self.c['helper']['sha256']and len(verified['securities'])==1
            and verified['securities'][0]['symbol']==symbol and verified['securities'][0]['count']==len(rows))
        if self.clock()>=deadline:raise SourcePending('native import returned after deadline')
        published=dict(root=str(store),import_receipt_sha256=hashlib.sha256(raw).hexdigest(),count=len(rows))
        # 注册前原Reader再次验成功收据、同一metadata、DSB和实际行，不把Helper返回当发布。
        self._select(state['window_id'],published,symbol)
        if self.clock()>=deadline:raise SourcePending('native readback returned after deadline')
        state['published']=published;state['empty']=False;self._save(directory,state)
        if self.clock()>=deadline:raise SourcePending('source publication returned after deadline')

    def _import_target(self,state,directory,csv_bytes,manifest):
        """本地失败根保留；仅重做原冻结输入的Importer，不重派任何来源命令。"""
        attempts=state['imports']
        require(type(attempts)is list and len(attempts)<=self.c['max_import_attempts']
            and attempts==['import-%04d'%n for n in range(1,len(attempts)+1)])
        while True:
            if not attempts:
                attempts.append('import-0001');self._save(directory,state)
            attempt=directory/attempts[-1]
            if not attempt.exists():create_private_directory(attempt)
            _inspect(attempt,True)
            input_root=attempt/'input';store=attempt/'store'
            if not input_root.exists():create_private_directory(input_root)
            _inspect(input_root,True)
            csv_path=input_root/'bars.csv';manifest_path=input_root/'manifest.json'
            csv_exists,manifest_exists=csv_path.exists(),manifest_path.exists()
            csv_info=_inspect(csv_path)if csv_exists else None
            manifest_info=_inspect(manifest_path)if manifest_exists else None
            if store.exists():_inspect(store,True)
            incomplete=csv_exists!=manifest_exists or(store.exists()and not(store/'qmt-import.json').exists())
            if csv_exists and manifest_exists:
                # 创建并不等于完整写入；零长、半写和字节错配均保留在失败尝试。
                matches=csv_info.st_size==len(csv_bytes)and manifest_info.st_size==len(manifest)
                if matches:matches=_read(csv_path,self.c['max_bytes'])==csv_bytes and _read(manifest_path,self.c['max_bytes'])==manifest
                incomplete=incomplete or not matches
            if incomplete:
                budget(len(attempts)<self.c['max_import_attempts'])
                attempts.append('import-%04d'%(len(attempts)+1));self._save(directory,state);continue
            if not csv_exists:
                write_private_new(csv_path,csv_bytes);write_private_new(manifest_path,manifest)
            return manifest_path,store

    def _select(self,key,published,symbol):
        identity=(key,published['root'],published['import_receipt_sha256'])
        if self.overlay_key==identity:return
        if self.overlay is not None:self.overlay.close();self.overlay=None;self.overlay_key=None
        require(published['count']<=self.c['overlay_cache_bars'])
        security=('SSE.'if symbol.endswith('.SH')else'SZSE.')+symbol[:6]
        config=dict(mode='source-store',store_root=published['root'],import_receipt_sha256=published['import_receipt_sha256'],
            native_reader=self.base_configuration['native_reader'],max_bars=self.c['max_rows'],
            max_cache_bars=self.c['overlay_cache_bars'],preload_symbols=[security])
        self.overlay=NativeSourceMarket(config);self.overlay_key=identity

    def _selected_query(self,request,deadline):
        if self.clock()>=deadline:raise SourcePending('source readback deadline')
        result=self.overlay.call(request)
        if self.clock()>=deadline:raise SourcePending('source readback returned after deadline')
        return result

    def _window(self,query,deadline):
        """选择范围之外的源工作只在这个显式有限窗口推进，原HPR至多一次。"""
        symbol=query['code']+('.SH'if query['exchange']=='SSE'else'.SZ')
        start,end=stamp(query['from']),stamp(query['to'])
        capacity=int((end-start).total_seconds()/60)+1
        target=min(query['limit'],capacity)
        unused,directory,state=self._state(query)
        if state['published']is not None:return state
        if state['empty']:
            if self.follow:
                try:self._follow_up(state,directory,symbol,start,end,deadline)
                except (followup.FollowUpExhausted,SourcePreparationBudget)as error:
                    state['follow_up']['stopped_reason']=str(error);self._save(directory,state)
                    raise SourcePreparationBudget(str(error))from None
            return state
        before,binding=self._reads(state,'before',directory,symbol,start,end,deadline)
        if len(before)>=target:rows=before
        else:
            if state['prepare']is None:
                metadata=self.source.binding(deadline)
                if self.follow:
                    self._capacity(metadata['limits'])
                    state['follow_up']=followup.initial(self.follow,self.source.uptime.seconds(),self.wall_clock())
                state['prepare']=self.source.plan('market.history_prepare',self.source.prepare_arguments(symbol,
                    start.strftime('%Y%m%d%H%M00'),end.strftime('%Y%m%d%H%M00'),metadata,deadline),metadata,deadline)
                self._save(directory,state)
            planned=state['prepare']['request']
            require(planned['operation_id']=='market.history_prepare'and planned['arguments']['symbol']==symbol
                and planned['arguments']['period']=='1m'and planned['arguments']['start_time']==start.strftime('%Y%m%d%H%M00')
                and planned['arguments']['end_time']==end.strftime('%Y%m%d%H%M00'))
            prepared=self.source.observe(state['prepare'],lambda:self._save(directory,state),deadline)
            require(prepared['ok']is True or prepared.get('error_code')=='preparation_unknown')
            rows,binding=self._reads(state,'after',directory,symbol,start,end,deadline)
        self._publish(state,directory,symbol,rows,binding,deadline)
        return state

    def _follow_up(self,state,directory,symbol,start,end,deadline):
        """空观测后只读；每次推进先留额度，原HPR与原终态始终保持。"""
        tracking=state['follow_up'];require(tracking is not None and state['prepare']is not None)
        reads=tracking['reads']
        frozen=bool(reads and reads[-1]['verified']and not reads[-1]['empty'])
        if not frozen:
            followup.admit(tracking,self.follow,self.source.uptime.seconds(),self.wall_clock())
            if not reads or reads[-1]['empty']:reads.append(dict(capture=None,verified=False,empty=False))
            self._save(directory,state)
        capture=reads[-1]
        read_deadline=deadline if frozen else min(deadline,self.clock()+max(0,
            tracking['deadline_ms']/1000-self.source.uptime.seconds()))
        with self.source.rpc_budget(self.follow['rpc_timeout_seconds']):
            rows,binding=self._reads(state,'capture',directory,symbol,start,end,read_deadline,holder=capture)
        if self.clock()>=read_deadline:raise SourcePending('follow-up readback returned after deadline')
        capture.update(verified=True,empty=not bool(rows));self._save(directory,state)
        self._publish(state,directory,symbol,rows,binding,deadline)

    def _published(self,request,preferred,deadline,budget):
        """仅原成功窗口收据作路由；无第二份价格索引，最多一个活动Reader。"""
        query=request['request'];candidates=[];states={};count=0
        for path in self.root.iterdir():
            if path.name in('configuration.json','owner.lock'):continue
            count+=1;require(count<=self.c['max_windows']);_inspect(path,True)
            receipt=path/'receipt.json'
            if not receipt.exists():continue
            if self.clock()>=deadline:raise SourcePending('source registry deadline')
            if _inspect(receipt).st_size>budget[0]:raise SourcePreparationBudget('source registry bytes')
            raw=_read(receipt,budget[0]);budget[0]-=len(raw)
            state=decode(raw)
            require(state['schema']==self.receipt_schema and state['configuration_sha256']==self.identity)
            selected=state['query']
            require(set(selected)=={'exchange','code','from','to'})
            validate_request(dict(api_version=API_VERSION,action='history.source-query',request=dict(selected,limit=query['limit'])))
            require(path.name==hashlib.sha256(canonical(selected)).hexdigest())
            if path.name==preferred:states[path.name]=state
            if selected['exchange']!=query['exchange']or selected['code']!=query['code']or selected['to']<query['from']or selected['from']>query['to']:continue
            if state['published']is not None:candidates.append((path.name,state))
        def batches():
            for key,state in sorted(candidates,key=lambda pair:(pair[0]!=preferred,pair[0])):
                symbol=query['code']+('.SH'if query['exchange']=='SSE'else'.SZ')
                self._select(state['window_id'],state['published'],symbol)
                result=self._selected_query(request,deadline)
                require(result['status']['code']=='Ok')
                yield result['data']
        return batches(),states

    def _observation(self,query,window,state,data,phase,reason,deadline):
        preparation='NotNeeded';rid=None;source_rows=0
        if state is not None:
            if state['published']is not None:source_rows=state['published']['count']
            record=state['prepare']
            if record is not None:
                rid=record['request']['request_id'];preparation='Pending'
                if record['result']is not None:
                    terminal=self.source.observe(record,lambda:None,deadline)
                    preparation='CallReturned'if terminal['ok']else'Unknown'if terminal.get('error_code')=='preparation_unknown'else'Unavailable'
        if phase in('Pending','Unavailable','NotSupported','Budget'):preparation=phase if rid is None else preparation
        return dict(schema='qmt.source-selection-observation.v1',state=phase if phase in('Archive','Observed')else'Partial',
            source_window=None if window is None else{key:window[key]for key in('from','to')},
            source_rows=source_rows,requested_limit=query['limit'],selected_rows=len(data['bars']),
            preparation_state=preparation,preparation_request_id=rid,reason=reason)

    def call(self,request):
        self._check();request=validate_request(decode(canonical(request)))
        if request['action']=='capabilities':
            result=self.base.call(request)
            result['data']['history']['reason']='已显式启用来源最近N根与有限尾窗准备；原值覆盖保持未知'
            return validate_response(result,request)
        if request['action']!='history.source-query':return self.base.call(request)
        query=request['request'];symbol=query['code']+('.SH'if query['exchange']=='SSE'else'.SZ')
        if 'symbols'in self.c and symbol not in self.c['symbols']:return self.base.call(request)
        deadline=self.clock()+self.c['timeout_seconds'];budget=[self.c['max_bytes']]
        start,end=stamp(query['from']),stamp(query['to'])
        window=dict(query,**{'from':label(max(start,end-timedelta(minutes=self.c['max_window_minutes']-1)))})
        preferred=hashlib.sha256(canonical({key:window[key]for key in('exchange','code','from','to')})).hexdigest()
        original=data=None;known=[];states={};phase='Archive';reason='原档案选择；覆盖未知';state=None
        try:
            # 原from/to/limit先选已有值，准备预算不改变档案查询的允许范围。
            original=self.base.call(request)
            if self.clock()>=deadline:raise SourcePending('archive readback returned after deadline')
            known,states=self._published(request,preferred,deadline,budget)
            batches=chain(known,[original['data']]if original['status']['code']=='Ok'else[])
            data=select_sources(batches,query)
            state=states.get(preferred)
            ready=data is not None and len(data['bars'])>=min(query['limit'],int((end-start).total_seconds()/60)+1)and data['bars'][-1]['minute']==query['to']
            if state is not None and state['published']is not None:
                phase='Observed'if state['published']['count']>=min(query['limit'],int((end-start).total_seconds()/60)+1)else'Partial'
                reason='有限尾窗已实际回读；返回最近可读原值，未授市场完整覆盖'
            elif ready and state is not None:
                phase='Pending';reason='已读足量档案；同尾窗原准备身份及未发布状态保持待核查'
            elif not ready:
                if end.date()>=datetime.now(SHANGHAI).date():
                    phase='NotSupported';reason='已读档案；原v6不读取或补齐当日及未来分钟'
                else:
                    phase='Pending';reason='已返回可读原值；有限尾窗准备仍待核查'
                    try:self._window(window,deadline)
                    except SourcePending:pass
                    except SourcePreparationBudget as error:
                        phase='Budget';reason='已返回可读原值；有限准备预算已停，尾部待补：'+str(error)
                    except (OSError,ValueError,KeyError,TypeError,MarketUnavailable,IntegrationUnavailable):phase='Unavailable'
                    if self.clock()>=deadline:raise SourcePending('source original deadline')
                    known,states=self._published(request,preferred,deadline,budget);state=states.get(preferred)
                    batches=chain(known,[original['data']]if original['status']['code']=='Ok'else[])
                    data=select_sources(batches,query)
                    if state is not None and state['published']is not None:
                        phase='Observed'if state['published']['count']>=min(query['limit'],int((end-start).total_seconds()/60)+1)else'Partial'
                        reason='有限尾窗已实际回读；返回最近可读原值，未授市场完整覆盖'
            if data is None:
                return failure('NotSupported'if phase=='NotSupported'else'Unavailable'if phase=='Unavailable'else'Backpressure'if phase=='Budget'else'Pending',reason if phase=='Budget'else'来源当前无可读原值，准备及覆盖仍待核查')
            data['observation']=self._observation(query,window if phase!='Archive'else None,state,data,phase,reason,deadline)
            if self.clock()>=deadline:raise SourcePending('source selection deadline')
            if len(canonical(data))>self.c['max_bytes']:raise SourcePreparationBudget('source selection bytes')
            return validate_response(dict(api_version=API_VERSION,status=dict(code='Ok',reason=reason),data=data),request)
        except SourceSelectionConflict:return failure('Conflict','最终选择中的原来源分钟存在不同原值，保留各自证据')
        except SourcePreparationBudget:
            if self.clock()>=deadline:return failure('Pending','原准备截止已耗尽；请按原选择核查')
            if data is None and original is not None and original['status']['code']=='Ok':data=original['data']
            if data is None or not data['bars']:
                return failure('Backpressure','来源准备超过明确额度，原身份及产物保留')
            data=decode(canonical(data))
            reason='本次返回已核最近原值及分段来源；新根注册或准备超过明确预算，尾部待补'
            data['observation']=self._observation(query,window,state,data,'Budget',reason,deadline)
            if len(canonical(data))>self.c['max_bytes']:return failure('Backpressure','来源选择超过明确响应字节额度，原值与身份保留')
            return validate_response(dict(api_version=API_VERSION,status=dict(code='Ok',reason=reason),data=data),request)
        except SourcePending:return failure('Pending','正在核查原来源请求或缓存发布；请按原选择重读')
        except (OSError,ValueError,KeyError,TypeError):return failure('Unavailable','来源选择、身份或原生发布未完成')

    def close(self):
        require(threading.get_ident()==self.owner)
        if self.overlay is not None:self.overlay.close();self.overlay=None
        if self.base is not None:self.base.close();self.base=None
        if self.lock is not None:self.lock.close();self.lock=None
        self.closed=True
