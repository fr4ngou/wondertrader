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
from .source_history_reads import HistoryReadOperations,retained_resume_state
from .source_history_selection import select_sources,SourceSelectionConflict
from .source_history_repository import PreparedHistoryRepository,PreparedHistoryReader,PreparedHistoryBudget,recovery_preferences
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

    def __init__(self,configuration,*,environ=None,clock=time.monotonic,wall_clock=time.time,transport_port=None):
        self.owner=threading.get_ident();self.base=self.overlay=self.lock=self.published_reader=None
        self.overlay_key=None;self.closed=False;self.clock=clock;self.wall_clock=wall_clock
        self._retained_resume_paths=None  # 可重建原窗口扫描游标；原请求责任仍由窗口及slot持有。
        try:
            require(type(configuration)is dict and set(configuration)=={'mode','base','preparation'}and configuration['mode']=='source-preparing')
            self.base_configuration=configuration['base'];c=configuration['preparation']
            require(type(c)is dict and set(c)-{'follow_up','symbols','retained_reads','closed_day_recovery','partitioned_receipts'}=={'enabled','workspace','host','helper','source_profile',
                'timeout_seconds','max_windows','max_window_minutes','max_pages','max_rows','max_bytes','overlay_cache_bars','max_import_attempts'})
            require(c['enabled']is True)
            self.follow=followup.configuration(c['follow_up'])if 'follow_up'in c else None
            require(type(c.get('retained_reads',False))is bool)
            self.closed_day_recovery=c.get('closed_day_recovery',False)  # 显式完整闭合日恢复；原始Writer归档和旧默认冲突规则保持。
            require(type(self.closed_day_recovery)is bool and(not self.closed_day_recovery or c.get('retained_reads',False)))
            self.partitioned=c.get('partitioned_receipts',False)  # 新根按证券分目录；旧配置身份保持。
            require(type(self.partitioned)is bool and(not self.partitioned or self.closed_day_recovery))
            self.receipt_schema=('qmt.source-history-preparation-receipt.v5'if self.partitioned
                else'qmt.source-history-preparation-receipt.v4'if self.closed_day_recovery
                else'qmt.source-history-preparation-receipt.v3'if c.get('retained_reads',False)
                else'qmt.source-history-preparation-receipt.v2'if self.follow else'qmt.source-history-preparation-receipt.v1')
            for key,maximum in [('max_windows',1000000 if self.partitioned else 1024),('max_window_minutes',7200),('max_pages',128),
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
            self.repository=PreparedHistoryRepository(self.root,self.identity,self.receipt_schema,
                c['max_windows'],partitioned=self.partitioned)
            self.window_count=self.repository.count()  # 唯一写owner启动核实；新增窗口递增，避免逐次扫描全市场。
            self.source=BoundHistorySource(c['host'],environ=environ,clock=clock,transport_port=transport_port)
            self.reads=HistoryReadOperations(self.source,self.root,retained=c.get('retained_reads',False))
            helper=Path(c['helper']['library'])
            require(helper.is_absolute());_inspect(helper)
            require(helper.stat().st_nlink==1)
            # 制品和ABI在任何SDK副作用前核验，仍复用Importer唯一加载逻辑。
            dependency=_Native(helper,c['helper']['sha256']);dependency.close()
            self.base=create_native_source_market(configuration['base'])
            self.published_reader=PreparedHistoryReader(self.base_configuration,self.c,clock=self.clock)
            self._profile(None,'validation-only')
        except BaseException:
            self.close();raise

    def _check(self):
        require(threading.get_ident()==self.owner and not self.closed)

    def _members(self):
        return self.repository.count()

    @staticmethod
    def _retained_records(state):
        """仅枚举本窗口已经登记的原读取，包含before/after、HPR和全部后继capture。"""
        for phase in ('before','after'):
            if state[phase] is not None:
                for record in state[phase]['pages']:
                    require(record['request']['operation_id']=='market.history_1m')
                    yield record
        if state['prepare'] is not None:
            require(state['prepare']['request']['operation_id']=='market.history_prepare')
            yield state['prepare']
        tracking=state.get('follow_up')
        if tracking is not None:
            for capture in tracking['reads']:
                if capture['capture'] is not None:
                    for record in capture['capture']['pages']:
                        require(record['request']['operation_id']=='market.history_1m')
                        yield record

    def resume_read_responsibility(self,deadline,*,maximum_windows=64):
        """跨滚动日期续核原已派发读取；至多一个原ID，不产生新Source请求。"""
        self._check()
        require(type(maximum_windows)is int and 1<=maximum_windows<=64)
        if not self.c.get('retained_reads',False):
            return retained_resume_state('idle')
        if self._retained_resume_paths is None:
            self._retained_resume_paths=iter(self.repository.directories())
        scan_deadline=min(deadline,self.clock()+1)
        scanned=0
        while scanned<maximum_windows and self.clock()<scan_deadline:
            directory=next(self._retained_resume_paths,None)
            if directory is None:
                self._retained_resume_paths=None
                return retained_resume_state('idle',scanned_windows=scanned)
            scanned+=1
            path=directory/'receipt.json'
            if not path.exists():continue
            state=decode(_read(path,self.c['max_bytes']))
            require(state['schema']==self.receipt_schema and state['configuration_sha256']==self.identity
                    and self.repository.directory(state['query'])[1]==directory)
            for record in self._retained_records(state):
                if record.get('consumed')is True or record.get('retained_slot')is None:continue
                arguments=record['request']['arguments'];query=state['query']
                symbol=query['code']+('.SH'if query['exchange']=='SSE'else'.SZ')
                require(arguments['symbol']==symbol and str(query['from'])+'00'<=arguments['start_time']
                        <=arguments['end_time']<=str(query['to'])+'00')
                rid=record['request'].get('request_id')
                try:
                    result=self.reads.resume_existing(record,lambda:self._save(directory,state),deadline)
                except SourcePending:
                    return retained_resume_state('pending',record['request'].get('request_id')or rid,scanned)
                if result is not None:
                    return dict(result,scanned_windows=scanned)
        return retained_resume_state('scanning',scanned_windows=scanned)

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
        key,directory=self.repository.directory(selected)
        if not directory.exists():
            budget(self.window_count<self.c['max_windows'])
            if self.partitioned and not directory.parent.exists():create_private_directory(directory.parent)
            create_private_directory(directory);self.window_count+=1
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
            limits=metadata['profile']['operation_profiles']['market.history_1m']['limits']
            maximum=limits['max_rows'];calendar_days=limits['max_calendar_days']
            require(maximum>=2)
            pages=[];cursor=start
            while cursor<=end:
                budget(len(pages)<self.c['max_pages'])
                calendar_end=cursor.replace(hour=0,minute=0)+timedelta(days=calendar_days,minutes=-1)
                last=min(end,cursor+timedelta(minutes=maximum-2),calendar_end)
                arguments=dict(symbol=symbol,start_time=cursor.strftime('%Y%m%d%H%M00'),end_time=last.strftime('%Y%m%d%H%M00'),max_rows=maximum)
                pages.append(self.reads.plan('market.history_1m',arguments,metadata,deadline,directory))
                cursor=last+timedelta(minutes=1)
            holder[phase]=dict(binding=metadata['binding'],pages=pages);save()
        pages=holder[phase]['pages']
        require(type(pages)is list and 1<=len(pages)<=self.c['max_pages'])
        if self.follow:self._capacity(pages[0]['limits'],len(pages))
        rows=[];previous=None;cursor=start
        for record in pages:
            args=record['request']['arguments']
            require(record['request']['operation_id']=='market.history_1m'and record['binding']==holder[phase]['binding']
                and args['symbol']==symbol and args['start_time']==cursor.strftime('%Y%m%d%H%M00'))
            last=stamp(int(args['end_time'][:12]))
            limits=record['profile']['operation_profiles']['market.history_1m']['limits']
            require(args['end_time']==last.strftime('%Y%m%d%H%M00')and cursor<=last<=end
                and args['max_rows']==limits['max_rows']and(last.date()-cursor.date()).days<limits['max_calendar_days']
                and int((last-cursor).total_seconds()/60)+1<args['max_rows'])
            cursor=last+timedelta(minutes=1)
            result=self.reads.observe(record,save,deadline)
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

    def _capacity(self,limits,pages=None):
        # 保留客户端逐页消费，Host按原票据到期回收；持久窗口总数不等于同时驻留请求数。
        windows=1 if self.c.get('retained_reads',False)else self.c['max_windows']
        pages=self.c['max_pages']if pages is None else pages
        try:followup.capacity(self.follow,windows,pages,limits)
        except followup.FollowUpExhausted as error:raise SourcePreparationBudget(str(error))from None

    def _closed_grid(self,query):
        if not self.closed_day_recovery:return[]
        first,last=stamp(query['from']),stamp(query['to'])
        if first.date()!=last.date()or last.date()>=datetime.now(SHANGHAI).date():return[]
        expected=self.base.expected_minutes(query['exchange']+'.'+query['code'],first.date().isoformat())
        return expected if expected and query['from']==expected[0]and query['to']==expected[-1]else[]

    def _complete_rows(self,state,rows):
        expected=self._closed_grid(state['query'])
        actual=[label(datetime.fromtimestamp(row[0]/1000,SHANGHAI))for row in rows]
        return bool(expected)and actual==expected

    def _publish(self,state,directory,symbol,rows,binding,deadline):
        if self.follow and self.closed_day_recovery and not self._complete_rows(state,rows)and state['follow_up']is None:
            state['follow_up']=followup.initial(self.follow,self.source.uptime.seconds(),self.wall_clock())
            self._save(directory,state)
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
        if self.closed_day_recovery and self._complete_rows(state,rows):
            published['reconciled_day']=dict(
                **{'from':state['query']['from'],'to':state['query']['to']},  # 原WT session完整右端范围。
                dataset_version=profile['dataset_version'])  # 固定完整来源版本；原采集和部分恢复根均保留。
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
        self.published_reader.select(key,published,symbol)

    def _selected_query(self,request,deadline):
        return self.published_reader.query(request,deadline)

    def _window(self,query,deadline):
        """选择范围之外的源工作只在这个显式有限窗口推进，原HPR至多一次。"""
        symbol=query['code']+('.SH'if query['exchange']=='SSE'else'.SZ')
        start,end=stamp(query['from']),stamp(query['to'])
        capacity=int((end-start).total_seconds()/60)+1
        target=min(query['limit'],capacity)
        unused,directory,state=self._state(query)
        if state['published']is not None and(not self.closed_day_recovery or state['published'].get('reconciled_day')is not None):return state
        if state['empty']or state['published']is not None:
            if self.follow:
                try:self._follow_up(state,directory,symbol,start,end,deadline)
                except (followup.FollowUpExhausted,SourcePreparationBudget)as error:
                    state['follow_up']['stopped_reason']=str(error);self._save(directory,state)
                    raise SourcePreparationBudget(str(error))from None
            return state
        before,binding=self._reads(state,'before',directory,symbol,start,end,deadline)
        # 整日恢复以session标签为准；同条数且尾标签相同仍可能用时段外标签替代缺失分钟。
        sufficient=self._complete_rows(state,before)if self._closed_grid(state['query'])else len(before)>=target
        if sufficient:rows=before
        else:
            if state['prepare']is None:
                metadata=self.source.binding(deadline)
                if self.follow:
                    self._capacity(metadata['limits'],len(state['before']['pages']))
                    state['follow_up']=followup.initial(self.follow,self.source.uptime.seconds(),self.wall_clock())
                state['prepare']=self.reads.plan('market.history_prepare',self.source.prepare_arguments(symbol,
                    start.strftime('%Y%m%d%H%M00'),end.strftime('%Y%m%d%H%M00'),metadata,deadline),metadata,deadline,directory)
                self._save(directory,state)
            planned=state['prepare']['request']
            require(planned['operation_id']=='market.history_prepare'and planned['arguments']['symbol']==symbol
                and planned['arguments']['period']=='1m'and planned['arguments']['start_time']==start.strftime('%Y%m%d%H%M00')
                and planned['arguments']['end_time']==end.strftime('%Y%m%d%H%M00'))
            prepared=self.reads.observe(state['prepare'],lambda:self._save(directory,state),deadline)
            require(prepared['ok']is True or prepared.get('error_code')=='preparation_unknown')
            rows,binding=self._reads(state,'after',directory,symbol,start,end,deadline)
        self._publish(state,directory,symbol,rows,binding,deadline)
        return state

    def _follow_up(self,state,directory,symbol,start,end,deadline):
        """空/部分观测后只读；新capture先留额度，原HPR及原请求终态保持。"""
        tracking=state['follow_up'];require(tracking is not None)
        reads=tracking['reads']
        frozen=bool(reads and reads[-1]['verified']and(reads[-1].get('complete',False)if self.closed_day_recovery else not reads[-1]['empty']))
        new_capture=not reads or(reads[-1]['verified']and not frozen)
        if new_capture:
            followup.admit(tracking,self.follow,self.source.uptime.seconds(),self.wall_clock())
            reads.append(dict(capture=None,verified=False,empty=False))
            self._save(directory,state)
        capture=reads[-1]
        read_deadline=deadline if frozen else min(deadline,self.clock()+max(0,
            tracking['deadline_ms']/1000-self.source.uptime.seconds()))
        with self.source.rpc_budget(self.follow['rpc_timeout_seconds']):
            rows,binding=self._reads(state,'capture',directory,symbol,start,end,read_deadline,holder=capture)
        if self.clock()>=read_deadline:raise SourcePending('follow-up readback returned after deadline')
        capture.update(verified=True,empty=not bool(rows));self._save(directory,state)
        if self.closed_day_recovery:
            capture['complete']=self._complete_rows(state,rows);self._save(directory,state)
        self._publish(state,directory,symbol,rows,binding,deadline)

    def _published(self,request,preferred,deadline,budget):
        """仅原成功窗口收据作路由；无第二份价格索引，最多一个活动Reader。"""
        try:
            candidates,states=self.repository.find(request['request'],preferred,deadline=deadline,
                byte_budget=budget,clock=self.clock)
        except PreparedHistoryBudget as error:
            raise SourcePreparationBudget(str(error))from error
        preferences=recovery_preferences(candidates)if self.closed_day_recovery else[]
        return self.published_reader.batches(candidates,request,deadline),states,preferences

    def _observation(self,query,window,state,data,phase,reason,deadline):
        preparation='NotNeeded';rid=None;source_rows=0
        if state is not None:
            if state['published']is not None:source_rows=state['published']['count']
            record=state['prepare']
            if record is not None:
                rid=record['request']['request_id'];preparation='Pending'
                if record['result']is not None:
                    terminal=self.reads.observe(record,lambda:None,deadline)
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
            known,states,preferences=self._published(request,preferred,deadline,budget)
            state=states.get(preferred)
            if (self.follow and self.closed_day_recovery and state is not None
                    and(state['empty']or state['published']is not None and state['published'].get('reconciled_day')is None)):
                # 部分来源可能与原采集冲突；先推进原只读后继，再做最终选择，避免冲突锁死恢复。
                try:self._window(window,deadline)
                except SourcePending:pass
                known,states,preferences=self._published(request,preferred,deadline,budget)
            batches=chain(known,[original['data']]if original['status']['code']=='Ok'else[])
            data=select_sources(batches,query,preferred_ranges=preferences)
            state=states.get(preferred)
            ready=data is not None and len(data['bars'])>=min(query['limit'],int((end-start).total_seconds()/60)+1)and data['bars'][-1]['minute']==query['to']
            expected=self._closed_grid(window)
            if expected:ready=data is not None and[bar['minute']for bar in data['bars']]==expected
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
                    known,states,preferences=self._published(request,preferred,deadline,budget);state=states.get(preferred)
                    batches=chain(known,[original['data']]if original['status']['code']=='Ok'else[])
                    data=select_sources(batches,query,preferred_ranges=preferences)
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
        if self.published_reader is not None:self.published_reader.close();self.published_reader=None
        if self.base is not None:self.base.close();self.base=None
        if self.lock is not None:self.lock.close();self.lock=None
        self.closed=True
