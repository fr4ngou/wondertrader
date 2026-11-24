"""合成Host/WinSHM→真实Native主入口→故障文件的来源差异回归。

仅使用SYNTHETIC账户及测试凭据；惰性测试插件不产生行情或策略委托。
通过有界代理改变声明字段，保留原请求身份和来源摘要；不载入生产配置。
"""
from pathlib import Path
import argparse, base64, collections, hashlib, http.client, json, os, shutil
import subprocess, sys, threading, time, traceback
from http.server import BaseHTTPRequestHandler, HTTPServer
from uuid import uuid4


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source',type=Path,required=True)
    ap.add_argument('--legacy-fixtures',type=Path,required=True)
    ap.add_argument('--candidate-app',type=Path,required=True)
    ap.add_argument('--toolchain',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--scenario',choices=['session','authentication','stable-binding','invalid-binding'],required=True)
    a=ap.parse_args(); a.output.mkdir(parents=True,exist_ok=False)
    for p in ['qmt_shm_trading','qmt_standard_trader','qmt_query_submission_group']:
        sys.path.insert(0,str(a.legacy_fixtures/p))
    for p in ['apps/guanheng','connectors/qmt_shm/host','connectors/qmt_shm/agent','integrations']:
        sys.path.insert(0,str(a.source/p))
    from test_submission_group import GapFixture
    from event_query_fixture import _FixtureOwners, canonical, decode, uptime_ms
    from guanheng_qmt_shm.auth import sign_request
    from guanheng_app.thread_owner import ThreadOwner
    sys.path.insert(0,str(a.source/'scripts'))
    from native_support.process_startup import background_process_options

    def sha(raw):return hashlib.sha256(raw).hexdigest()
    def save(p,v):p.write_bytes(canonical(v))
    env=json.loads(a.toolchain.read_bytes())['environment']
    owned=a.candidate_app.parents[1]/'inputs/owned'
    native_names=['src/TraderQMT/'+n for n in ['StandardQmtTrader.cpp','StandardQmtTrader.h',
        'StandardFactory.cpp','StandardReadSource.h','StandardReadSourceContext.h']]
    native_names+=['src/GuanhengExecution/'+n for n in ['CtaProcess.cpp','StandardExecutionHost.cpp','StandardExecutionHost.h']]
    native_sources={n:sha((owned/n).read_bytes())for n in native_names}
    assert all(sha((a.source/n).read_bytes())==v for n,v in native_sources.items()),'source differs from same-batch native closure'
    compiler=shutil.which('cl.exe',path=env['PATH']); assert compiler
    app=a.output/'app'; app.mkdir()
    for name in ['GuanhengCtaHost.exe','GuanhengCtaRuntime.dll','traders','executers']:
        src=a.candidate_app/name
        if src.is_dir():shutil.copytree(src,app/name)
        else:shutil.copyfile(src,app/name)
    compile_cmd=[compiler,'/nologo','/std:c++17','/EHsc','/MD','/LD','/utf-8',
        '/I'+str(a.source/'src'),str(Path(__file__).with_name('qa_plugins.cpp')),
        '/Fo'+str(a.output/'qa.obj'),'/Fe'+str(app/'ReadSourceQA.dll')]
    compiled=subprocess.run(compile_cmd,env=env,cwd=a.output,capture_output=True,
        timeout=60,**background_process_options())
    (a.output/'compile.log').write_bytes(compiled.stdout+compiled.stderr)
    assert compiled.returncode==0,'QA plugin compile; see compile.log'
    (app/'parsers').mkdir();shutil.copyfile(app/'ReadSourceQA.dll',app/'parsers/ReadSourceQA.dll')
    total=uptime_ms()+55000
    class Fixture(GapFixture):
        def configure_host(self,c,credentials):
            c=super().configure_host(c,credentials)
            c['max_records']=128;c['max_journal_bytes']=128*self.read_budget['unit_bytes']
            return c
        def detail(self,account,account_type,datatype):
            assert threading.get_ident()==self.owner_thread and (account,account_type)==('SYNTHETIC','stock')
            assert len(self.queries)<64
            if datatype=='position':
                rows=[dict(m_strAccountID=account,m_strMoneyType='CNY',m_strInstrumentID='000001',
                    m_strExchangeID='SZ',m_nVolume=100,m_nCanUseVolume=100)]
            elif datatype=='account':
                rows=[dict(m_strAccountID=account,m_strMoneyType='CNY',m_dBalance=10000.,m_dAvailable=8000.,
                    m_dPreBalance=10000.,m_dCommission=0.,m_dFrozenCash=2000.,m_dFrozenMargin=0.,
                    m_dFrozenCommission=0.,m_dPositionProfit=0.,m_dFloatProfit=0.)]
            else:
                assert datatype in ['order','deal'];rows=[]
            self.queries.append(dict(datatype=datatype,thread=threading.get_ident(),returned_rows=rows))
            return rows
    (a.output/'owners').mkdir(); f=Fixture(a.output,total,'query_first')
    control=a.output/'control';control.mkdir(); owners=_FixtureOwners()
    native=None;result={'passed':False,'scenario':a.scenario,'production_inputs':False}

    class Proxy:
        """Bounded single HTTP owner; no financial POST is admitted by this harness."""
        def __init__(self,owner):
            self.owner=owner;self.active=False;self.original=None;self.changed=None
            self.transcript=[];self.errors=[];self.requests=[];self.ids=set();self.stop=threading.Event()
            self.entered=threading.Event();self.joined=False;self.max_requests=2048
            proxy=self
            class Handler(BaseHTTPRequestHandler):
                protocol_version='HTTP/1.1'
                def log_message(self,*args):pass
                def do_GET(self):self.forward()
                def do_POST(self):self.forward()
                def forward(self):
                    conn=None
                    try:
                        self.connection.settimeout(3)
                        assert len(proxy.transcript)<proxy.max_requests
                        n=int(self.headers.get('Content-Length','0'));assert 0<=n<=262144
                        raw=self.rfile.read(n);assert len(raw)==n
                        request=decode(raw)if raw else None
                        assert self.path!='/internal/v1/trade-commands','unexpected financial POST'
                        if (not proxy.active and self.path=='/internal/v1/read-binding'
                                and (control/'ready.json').exists() and len(owner.queries)>=4
                                and proxy.transcript and proxy.transcript[-1]['path']=='/internal/v1/trade-events'
                                and proxy.transcript[-1]['status']==200):
                            proxy.active=True
                            proxy.activation_query_count=len(owner.queries)
                        use_changed=False
                        if request is not None and proxy.changed:
                            encoded=canonical(request)
                            use_changed=canonical(proxy.changed)in encoded or sha(canonical(proxy.changed)).encode()in encoded
                            if use_changed:
                                if 'request_body_b64'in request:
                                    rid=decode(base64.b64decode(request['request_body_b64']))['request_id'];proxy.ids.add(rid)
                                request=proxy.replace(request,proxy.changed,proxy.original)
                                raw=canonical(request)
                        if self.path.startswith('/internal/v1/bound-results/'):
                            use_changed=self.path.rsplit('/',1)[-1]in proxy.ids
                        headers={k:v for k,v in self.headers.items()if k.lower()not in ['host','connection','content-length']}
                        digest=sha(raw);timestamp=str(time.time());nonce=uuid4().hex
                        headers.update({'X-QMT-Key-Id':'fixture','X-QMT-Timestamp':timestamp,
                            'X-QMT-Nonce':nonce,'X-QMT-Content-SHA256':digest,
                            'X-QMT-Signature':sign_request(owner.secret,self.command,self.path,timestamp,nonce,digest),
                            'Connection':'close','Content-Length':str(len(raw))})
                        conn=http.client.HTTPConnection('127.0.0.1',owner.host.listen_port,timeout=3)
                        conn.request(self.command,self.path,body=raw,headers=headers)
                        reply=conn.getresponse();original=reply.read(262145);assert len(original)<=262144
                        value=decode(original)
                        if self.path in ['/internal/v1/read-binding','/internal/v1/trade-status'] and reply.status==200:
                            if proxy.original is None:proxy.original=value['binding']
                            if proxy.active:
                                if proxy.changed is None:
                                    proxy.changed=decode(canonical(proxy.original))
                                    proxy.changed['host_instance_id']=uuid4().hex
                                    proxy.changed['transport_generation']=uuid4().hex
                                    if a.scenario=='stable-binding':proxy.changed['route']['route_epoch']+=1
                                    if a.scenario=='invalid-binding':proxy.changed['route']['route_epoch']='invalid-synthetic'
                                value['binding']=proxy.changed;value['binding_sha256']=sha(canonical(proxy.changed))
                                if self.path.endswith('trade-status')and a.scenario=='session':
                                    value['source_status']['session_id']='synthetic-successor-session'
                                    value['source_status']['events']['session_id']='synthetic-successor-session'
                        elif use_changed:
                            value=proxy.replace(value,proxy.original,proxy.changed)
                        body=canonical(value)
                        proxy.transcript.append({'method':self.command,'path':self.path,'status':reply.status,
                            'active':proxy.active,'translated_request':use_changed,
                            'original_sha256':sha(original),'delivered_sha256':sha(body)})
                        self.send_response(reply.status);self.send_header('Content-Type','application/json')
                        self.send_header('Content-Length',str(len(body)));self.send_header('Connection','close')
                        self.end_headers();self.wfile.write(body);self.wfile.flush();self.close_connection=True
                    except BaseException as e:
                        proxy.errors.append({'type':type(e).__name__,'reason':str(e)[:256],
                            'frames':[(Path(x.filename).name,x.lineno)for x in traceback.extract_tb(e.__traceback__)[-4:]]})
                        self.close_connection=True
                    finally:
                        if conn:conn.close()
            self.server=HTTPServer(('127.0.0.1',0),Handler);self.server.timeout=.05
            self.thread=ThreadOwner(target=self.run,name='read-source-QA-proxy',daemon=True)
        def replace(self,value,old,new):
            if isinstance(value,dict):
                if value==old:return new
                return{k:self.replace(v,old,new)for k,v in value.items()}
            if isinstance(value,list):return[self.replace(v,old,new)for v in value]
            if value==sha(canonical(old)):return sha(canonical(new))
            return value
        @property
        def port(self):return self.server.server_port
        def run(self):
            self.entered.set()
            while not self.stop.is_set()and time.monotonic()<f.total_deadline:self.server.handle_request()
        def start(self):self.thread.start()
        def close(self):
            self.stop.set();self.joined=self.thread.join_until(f.total_deadline);self.server.server_close()
            assert self.joined
    f.proxy_type=Proxy
    try:
        with owners:
            f.start(owners)
            base=app/'base';base.mkdir()
            for name,value in {
              'sessions':{'DAY':{'name':'synthetic','offset':0,'sections':[{'from':0,'to':2359}]}},
              'commodities':{'SZSE':{'STK':{'name':'synthetic','session':'DAY','holiday':'CHINA','category':0,'pricetick':.01,'volscale':1,'covermode':0,'pricemode':0,'trademode':2}}},
              'contracts':{'SZSE':{'000001':{'name':'synthetic','exchg':'SZSE','product':'STK','opendate':20000101,'expiredate':20991231}}},
              'holidays':{'CHINA':[]},'policy':{'default':{'order':[{'action':'close','limit':0},{'action':'open','limit':0}]}}
            }.items():save(base/(name+'.json'),value)
            trader=f.trader();trader['module']='TraderQMTStandard';trader.pop('observation_refresh_ms',None)
            cfg=dict(schema_version='guanheng.cta-execution.v1',installation_root=str(app),
                output_directory=str(a.output/'native-state'),base_data={n:'base/'+n+'.json'for n in ['sessions','commodities','contracts','holidays','policy']},
                trader=trader,executer={'scale':1,'strict_sync':False,'poolsize':0,'clear':{'active':False},
                  'policy':{'default':{'name':'WtExeFact.WtStockMinImpactBorrowedExeUnit','lots':1000,'min_order':100,'pricemode':0,'offset':0,'expire':1,'span':0,'byrate':False,'is_cancel_unmanaged_order':True,'replace_equal_position_target':True}}},
                environment={'name':'cta','product':{'session':'DAY'},'poolsize':0},
                data={'align_by_section':False,'store':{'module':'ReadSourceQA'}},
                parsers=[{'id':'qa','active':True,'module':'ReadSourceQA','check_time':False,'filter':'','code':''}],
                strategies=[{'id':'read-source-qa','module':'ReadSourceQA.dll','factory':'ReadSourceQA','name':'Quiet','parameters':{}}],
                budget={'start_ms':15000,'stop_ms':5000,'run_ms':6000},queue={'commands':16,'bytes':65536,'targets':16,'delay_ms':10000},
                observation_refresh={'interval_ms':1000})
            config=a.output/'execution.json';save(config,cfg)
            childenv=dict(os.environ,QMT_STANDARD_FIXTURE_KEY='fixture',QMT_STANDARD_FIXTURE_SECRET=f.secret)
            command=[str(app/'GuanhengCtaHost.exe'),'--config',str(config),'--control',str(control),
                '--control-id',str(uuid4()),'--config-sha256',sha(config.read_bytes())]
            out=(a.output/'native.stdout').open('wb');err=(a.output/'native.stderr').open('wb')
            try:
                native=subprocess.Popen(command,cwd=app,env=childenv,stdout=out,stderr=err,creationflags=subprocess.CREATE_NO_WINDOW)
                def close_native():
                    if native.poll()is None:native.kill()
                    native.wait(timeout=3)
                owners.callback(close_native)
                f.pump_until(lambda:native.poll()is not None)
                code=native.wait(timeout=2)
            finally:out.close();err.close()
            failure=decode((control/'failure.json').read_bytes())if(control/'failure.json').exists()else None
            result.update(exit_code=code,ready=(control/'ready.json').exists(),failure=failure,
                closed=decode((control/'close-prepared.json').read_bytes()),sdk_calls=len(f.sdk),queries=len(f.queries),
                active=f.proxy.active,proxy_errors=f.proxy.errors,transcript=f.proxy.transcript)
            assert f.proxy.active and not f.sdk and not f.tokens and not f.proxy.errors
            if a.scenario in ['session','stable-binding']:
                assert code!=0 and failure and failure['private_reason']=='qmt_standard_read_source_changed',failure
                assert failure['read_source']=={'schema':'guanheng.qmt-read-source-failure.v1','stage':2,'differences':2 if a.scenario=='session' else 64},failure
            elif a.scenario=='invalid-binding':
                assert code!=0 and failure and 'read_source'not in failure,failure
                # 账户与交易读取共用read-binding；先读取者各沿原Common校验拒绝。
                assert failure['plugin_error']==10,failure  # ErrorCode::IoError，原协议分类保持。
                assert failure['private_reason']in ('qmt_host_binding_invalid','qmt_trade_binding_invalid'),failure
            else:
                assert code==0 and failure is None,result
                assert result['closed']['ok']is True
                assert len(f.queries)>f.proxy.activation_query_count
                assert any(x['active'] and x['translated_request'] and '/bound-results/'in x['path'] and x['status']==200 for x in f.proxy.transcript)
                assert not any(x['status']==404 for x in f.proxy.transcript)
            result['passed']=True
    except BaseException as e:
        result['error']={'type':type(e).__name__,'reason':str(e)[:1024]}
        (a.output/'failure-trace.txt').write_text(traceback.format_exc(),encoding='utf8')
    finally:
        result['resources']={'source_closed':bool(f.agent and f.agent._io_resources_closed),
            'host_closed':bool(f.host and f.host._io_resources_closed),'proxy_joined':bool(f.proxy and f.proxy.joined),
            'native_exited':bool(native and native.poll()is not None)}
        result['sdk_calls']=len(f.sdk);result['query_count']=len(f.queries)
        result['qualification']='Synthetic SDK/account/quotes with actual WinSHM, Host, Standard, Native main and failure receipt; no production or real broker qualification'
        result['inputs']={'harness_sha256':sha(Path(__file__).read_bytes()),'qa_plugin_sha256':sha(Path(__file__).with_name('qa_plugins.cpp').read_bytes()),
            'candidate_files':{str(p.relative_to(app)):sha(p.read_bytes())for p in app.rglob('*')if p.is_file()and p.suffix in ['.dll','.exe']},
            'native_source_inputs':native_sources,
            'python_sources':{str(p):sha(p.read_bytes())for m in tuple(sys.modules.values())
                if getattr(m,'__file__',None) and (p:=Path(m.__file__).resolve()).is_file()
                and (p.is_relative_to(a.source.resolve()) or p.is_relative_to(a.legacy_fixtures.resolve()))}}
        save(a.output/'RESULT.json',result)
        print(json.dumps({k:result[k]for k in ['passed','scenario','sdk_calls','query_count','resources']}),flush=True)
    return 0 if result['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
