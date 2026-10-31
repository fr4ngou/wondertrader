"""固定原QMT Core/Queue/Journal及原WT Adapter的合成HMAC HTTP验收，真实QMT网络为0。"""
from pathlib import Path
import argparse,base64,copy,hashlib,io,json,os,re,subprocess,sys,threading,time
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[3]
QMT_COMMIT='34777db5eab144d6fe8a2f259b9f2c0de167435a'
FUNCTIONAL_REQUEST_MS=5000
FUNCTIONAL_ROUND_MS=30000
FUNCTIONAL_HTTP_MS=4000

def child_timeout(config):
    # Lifecycle/field cases prove functional behavior, separately from the
    # dedicated deadline cases. The process guard must outlive the selected
    # owner round and close budgets, with an explicit 60 second test ceiling.
    milliseconds=int(config['round_ms'])+int(config['close_ms'])+10000
    if milliseconds<=0 or milliseconds>60000:raise ValueError('test process budget exceeds 60 seconds')
    return max(15.0,milliseconds/1000.0)
# Each invalid mapping case must reach its named cause. Earlier transport/owner
# timeout is a test failure, even when the plugin correctly stays fail-closed.
TARGET_FAILURES = {'missing-volume': ('HTTP来源缺少必需字段', 0, 1), 'fraction-volume': ('HTTP数值范围错误', 0, 1), 'bool-volume': ('HTTP数值类型错误', 0, 1), 'available-over-volume': ('HTTP可卖超过总量', 0, 1), 'unknown-security': ('HTTP合约缺失或市场冲突', 0, 1), 'duplicate-position': ('HTTP持仓证券重复', 0, 1), 'missing-balance': ('HTTP来源缺少必需字段', 7, 4), 'account-cardinality': ('HTTP记录类型或数量非法', 7, 4), 'bad-side': ('HTTP股票买卖值未知', 1, 2), 'bad-state': ('HTTP委托数量或状态错误', 1, 2), 'filled-inconsistent': ('全成委托量不守恒', 1, 2), 'bad-order-quantity': ('HTTP委托数量或状态错误', 1, 2), 'bad-date': ('HTTP日期无效', 3, 3), 'bad-time': ('HTTP时间无效', 3, 3), 'long-id': ('HTTP字段文本类型或长度错误', 1, 2), 'unicode-control-id': ('HTTP标识含控制字符', 1, 2), 'control-id': ('HTTP标识含控制字符', 1, 2), 'negative-deal-price': ('HTTP成交量价必须正数', 3, 3), 'missing-amount': ('HTTP来源缺少必需字段', 3, 3), 'wrong-row-account': ('行账户与观察不符', 0, 1), 'wrong-currency': ('行币种与显式绑定冲突', 7, 4), 'order-conflict': ('HTTP委托同ID事实冲突', 1, 2), 'optional-fact-conflict': ('HTTP委托同ID事实冲突', 1, 2), 'deal-conflict': ('HTTP成交同ID事实冲突', 3, 3), 'missing-observation': ('HTTP来源缺少必需字段', 0, 1), 'wrong-account': ('HTTP账户或会话来源改变', 0, 1), 'wrong-session': ('HTTP账户或会话来源改变', 0, 1), 'wrong-generation': ('HTTP账户或会话来源改变', 0, 1), 'wrong-scope': ('HTTP查询范围不符', 0, 1), 'false-complete': ('HTTP查询不完整', 0, 1), 'wrong-rowcount': ('HTTP查询不完整', 0, 1), 'bad-utc': ('执行区间必须UTC', 0, 1), 'missing-contract': ('qmt_http_reads_unavailable', 0, 0), 'metadata-after-position': ('观察序列化总预算超限', 1, 2), 'session-changes-at-deal': ('HTTP账户或会话来源改变', 3, 3), 'metadata-budget': ('观察序列化总预算超限', 0, 1)}

def export_qmt(target,fixture=None,repo=None):
    if fixture is not None:
        sys.path.insert(0,str(ROOT/'scripts'))
        from native_support.qmt_readonly_fixed import verify_snapshot
        expected=verify_snapshot(fixture)
        if expected.get('commit')!=QMT_COMMIT:raise ValueError('wrong fixed QMT fixture commit')
        # The profile already owns an immutable fixed snapshot. Import it in
        # place: copying its long SHA-named config files into every deep case
        # directory both duplicates the owner and exceeds Windows path limits.
        return fixture.resolve(strict=True)
    if repo is None:raise ValueError('explicit --qmt-fixture or --qmt-source required')
    paths=subprocess.check_output(['git','-C',str(repo),'ls-tree','-r','--name-only',QMT_COMMIT,'qmt_agent','src/qmt_platform/common','docs/contracts','config']).decode().splitlines()
    raw=subprocess.check_output(['git','-C',str(repo),'cat-file','--batch'],input=('\n'.join(QMT_COMMIT+':'+p for p in paths)+'\n').encode());stream=io.BytesIO(raw);hashes={}
    target.mkdir(exist_ok=False)
    for name in paths:
        header=stream.readline().split();assert header[1]==b'blob';data=stream.read(int(header[2]));assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\x00'+data).hexdigest().encode()==header[0];assert stream.read(1)==b'\n';p=target/name;p.parent.mkdir(exist_ok=True,parents=True);p.write_bytes(data);hashes[name]=hashlib.sha256(data).hexdigest()
    assert not stream.read();(target/'input.json').write_text(json.dumps(dict(commit=QMT_COMMIT,files=hashes),indent=2),encoding='utf-8');return target

def native_rows():
    position=[dict(m_strInstrumentID='600000',m_strExchangeID='SH',m_nVolume=700,m_nCanUseVolume=420,m_nYesterdayVolume=900,m_dAvgPrice=-2.5),dict(m_strInstrumentID='510300',m_strExchangeID='SH',m_nVolume=37,m_nCanUseVolume=27)]
    order=[dict(m_strInstrumentID='600000',m_strExchangeID='SH',m_strOrderSysID='00000017',m_nOffsetFlag=48,m_nVolumeTotalOriginal=200,m_nVolumeTraded=70,m_nVolumeTotal=130,m_nOrderStatus=55,m_dLimitPrice=10.35,m_strInsertDate='20261022',m_strInsertTime='09:35:07.123')]
    deal=[dict(m_strInstrumentID='600000',m_strExchangeID='SH',m_strOrderSysID='00000017',m_strTradeID='00000031',m_nOffsetFlag=48,m_nVolume=70,m_dPrice=10.31,m_dTradeAmount=721.7,m_strTradeDate='2026-10-22',m_strTradeTime='093508.124')]
    account=[dict(m_dBalance=100000,m_dAvailable=82000,m_dPreBalance=99900,m_dCommission=12.34,m_dFrozenCash=200,m_dPositionProfit=123)]
    return dict(position=position,order=order,deal=deal,account=account)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--build',type=Path);parser.add_argument('--probe',type=Path);parser.add_argument('--library',type=Path);parser.add_argument('--cwd',type=Path);parser.add_argument('--owned-root',type=Path);parser.add_argument('--qmt-fixture',type=Path);parser.add_argument('--qmt-source',type=Path);parser.add_argument('--work',type=Path,required=True);parser.add_argument('--drain',action='store_true');parser.add_argument('--only',nargs='*');args=parser.parse_args()
    build=args.build.resolve() if args.build else None;work=args.work.resolve();work.mkdir(parents=True,exist_ok=False)
    owned=args.owned_root.resolve(strict=True) if args.owned_root else build/'snapshot'
    sys.path.insert(0,str(owned/'tests/integration/qmt_readonly_bootstrap'))
    from invocation import resolve,verify
    probe,library,cwd,_,binary_identity=resolve(args)
    source=export_qmt(work/'qmt-source',args.qmt_fixture,args.qmt_source);helpers=work/'python-inputs';helpers.mkdir();python_inputs={}
    qmt_manifest=json.loads((source/'input.json').read_text(encoding='utf-8'))
    for relative in ('tests/integration/http/test_qmt_http.py','tests/integration/qmt_readonly_bootstrap/run.py','tests/integration/qmt_readonly_bootstrap/invocation.py','tests/integration/qmt_http_bootstrap/native_oracle.py'):
        data=(owned/relative).read_bytes();target=helpers/Path(relative).name;target.write_bytes(data);python_inputs[relative]=hashlib.sha256(data).hexdigest()
    python_inputs['tests/integration/qmt_http_bootstrap/run.py']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest();(helpers/'manifest.json').write_text(json.dumps(python_inputs,indent=2),encoding='utf-8')
    sys.path[:0]=[str(source),str(source/'src'),str(helpers)]
    import test_qmt_http as original
    # This Gateway overrides every generic DTO-producing method below. Loading
    # their unused Pydantic module previously added an implicit machine-site
    # dependency without validating any NQH response.
    original.load_original(source,validate_dtos=False)
    assert original.CONTRACTS is None
    from qmt_agent.gateway.core import GatewayCore
    from qmt_agent.journal import CommandJournal
    original_oracles={}
    for symbol in (original.VERIFIER,original.CANONICAL,GatewayCore,CommandJournal):
        module=sys.modules[symbol.__module__];path=Path(module.__file__).resolve();relative=path.relative_to(source).as_posix();expected=qmt_manifest['files'][relative];expected=expected['sha256'] if isinstance(expected,dict) else expected
        digest=hashlib.sha256(path.read_bytes()).hexdigest();assert digest==expected
        original_oracles[symbol.__module__]=dict(path=relative,sha256=digest)
    from run import fixture,write
    class Gateway(original.GatewayStub):
        supported_operations=('account.trade_detail',)
        def __init__(self,path,rows,mutation=None,mode='normal'):
            self.rows,self.mutation,self.native_calls=rows,mutation,[];self.done=threading.Event();self.ready=threading.Event();self.journal=CommandJournal(str(path/'journal.db'))
            self.core=GatewayCore(dict(agent_id='http-fixture',account_id='SYNTHETIC-NQH',qmt_session_id='fixture-session',account_environment='simulation',trading_mode='shadow'),event_store=self.journal)
            def read(*values):
                self.native_calls.append((values,threading.get_ident()));assert values[:2]==('SYNTHETIC-NQH','stock') and len(values)==3
                return [SimpleNamespace(**dict(row,private_secret='must-not-appear')) for row in self.rows[values[2]]]
            def ticks():
                self.core.bind_context(object(),functions={'get_trade_detail_data':read});self.core.agent_tick();self.ready.set()
                while not self.done.wait(.005):self.core.agent_tick()
            self.ticker=threading.Thread(target=ticks);self.ticker.start();assert self.ready.wait(2);super().__init__(mode)
        def __exit__(self,*args):
            try:super().__exit__(*args)
            finally:self.done.set();self.ticker.join(3);assert not self.ticker.is_alive()
        def health(self):
            if self.mode=='slow_health':time.sleep(.8)
            return self.core.health()
        def capabilities(self):
            x=self.core.capabilities()
            if self.mode=='missing_contract':
                for v in x['operations']:
                    if v['operation_id']=='account.trade_detail':v.pop('query_contract',None)
            return x
        def respond(self,method,path,body):
            if path=='/internal/v1/health':return 200,self.health()
            if path=='/internal/v1/capabilities':return 200,self.capabilities()
            if method=='POST':
                payload=json.loads(body);assert payload['operation_id']=='account.trade_detail';self.core.submit_operation(payload['operation_id'],payload)
                if self.mode in ('slow_post','forced_slow_get'):time.sleep(.8)
                if self.mode=='post_disconnect':raise ConnectionResetError('synthetic lost response')
                rid=payload['request_id']
            else:
                rid=path.rsplit('/',1)[-1]
                if self.mode=='forced_slow_get':time.sleep(8.0)
            record=self.core.operation_record(rid)
            if method=='POST' and self.mode in ('force_get','forced_slow_get'):
                progress=self.core.operation_progress(rid);progress['status']='executing';return 202,progress
            if not record.get('result'):return 202,self.core.operation_progress(rid)
            result=copy.deepcopy(record['result'])
            if self.mutation:self.mutation(result)
            return 200,result
    from native_oracle import verify as verify_native
    cases=[]
    def add(name,edit=None,mutate=None,mode='normal',probe_mode='normal',ready=True,config=None):cases.append((name,edit,mutate,mode,probe_mode,ready,config or {}))
    add('wait-deadline',mode='slow_health',probe_mode='wait-deadline',ready=False,config=dict(request_ms=600,round_ms=3000))
    # These cases expire inside the mapping gate, after the real durable source
    # query succeeds. Use the normal fixture budget to reach that gate; the
    # probe still blocks request_ms + 40 ms and must reject the late SPI.
    add('map-late-position',probe_mode='map-late-position',ready=False,config=dict(request_ms=FUNCTIONAL_REQUEST_MS,round_ms=FUNCTIONAL_ROUND_MS))
    add('map-late-order',probe_mode='map-late-order',ready=False,config=dict(request_ms=FUNCTIONAL_REQUEST_MS,round_ms=FUNCTIONAL_ROUND_MS))
    add('slow-connect',probe_mode='slow-connect',ready=False,config=dict(request_ms=500,round_ms=700))
    add('happy');add('empty',lambda r:[r.__setitem__(k,[]) for k in ('position','order','deal')])
    add('signed-funds',lambda r:r['account'][0].update(m_dBalance=-10,m_dAvailable=20))
    add('optional-invalid',lambda r:r['account'][0].update(m_dCommission='bad',m_dPreBalance=None))
    add('duplicate-equivalent-order',lambda r:r['order'].append(dict(r['order'][0],m_strInsertDate='2026-10-22',m_strInsertTime='093507.123')))
    add('duplicate-equivalent-deal',lambda r:r['deal'].append(dict(r['deal'][0],m_strTradeDate='20261022',m_strTradeTime='09:35:08.124')))
    add('cross-order-same-trade',lambda r:r['deal'].append(dict(r['deal'][0],m_strOrderSysID='00000018')))
    add('cross-security-same-trade',lambda r:r['deal'].append(dict(r['deal'][0],m_strInstrumentID='510300',m_strOrderSysID='00000018')))
    add('cross-market-same-trade',lambda r:r['deal'].append(dict(r['deal'][0],m_strInstrumentID='000001',m_strExchangeID='SZ',m_strOrderSysID='00000018')))
    add('trade-date-leading-zero-year',lambda r:r['deal'][0].update(m_strTradeDate='0001-01-01',m_strTradeID='unicode-成交'))
    add('utc-offset-projection',mutate=lambda x:x['observation']['execution'].update({k:v.replace('Z','+00:00') for k,v in x['observation']['execution'].items()}))
    add('different-event-date',lambda r:r['deal'].append(dict(r['deal'][0],m_strTradeDate='20261023')))
    for status in range(49,58):
        add('status-'+str(status),lambda r,s=status:r['order'][0].update(m_nOrderStatus=s,m_nVolumeTraded=200 if s==56 else 70,m_nVolumeTotal=0 if s==56 else 130))
    for status in range(49,58):
        add('sell-status-'+str(status),lambda r,s=status:[r['order'][0].update(m_nOffsetFlag=49,m_nOrderStatus=s,m_nVolumeTraded=200 if s==56 else 70,m_nVolumeTotal=0 if s==56 else 130),r['deal'][0].update(m_nOffsetFlag=49)])
    add('order-limit-at-one',config=dict(riskmon=dict(active=True,policy=dict(default=dict(order_total_limits=1,cancel_total_limits=1000)))))
    def matrix(rows):
        base=rows['order'][0];rows['order']=[dict(base,m_strOrderSysID=str(side*100+state),m_nOffsetFlag=side,m_nOrderStatus=state,m_nVolumeTraded=200 if state==56 else 70,m_nVolumeTotal=0 if state==56 else 130) for side in (48,49) for state in range(49,58)]
        rows['deal'].append(dict(rows['deal'][0],m_strTradeID='00000032',m_nOffsetFlag=49))
    add('order-matrix',matrix,config=dict(riskmon=dict(active=True,policy=dict(default=dict(order_total_limits=18,cancel_total_limits=1000)))))
    add('sell-query',lambda r:[r[k][0].update(m_nOffsetFlag=49) for k in ('order','deal')])
    for name,edit in [
        ('missing-volume',lambda r:r['position'][0].pop('m_nVolume')),
        ('fraction-volume',lambda r:r['position'][0].update(m_nVolume=700.5)),
        ('bool-volume',lambda r:r['position'][0].update(m_nVolume=True)),
        ('available-over-volume',lambda r:r['position'][0].update(m_nCanUseVolume=701)),
        ('unknown-security',lambda r:r['position'][0].update(m_strInstrumentID='999999')),
        ('duplicate-position',lambda r:r['position'].append(copy.deepcopy(r['position'][0]))),
        ('missing-balance',lambda r:r['account'][0].pop('m_dBalance')),
        ('account-cardinality',lambda r:r['account'].append(copy.deepcopy(r['account'][0]))),
        ('bad-side',lambda r:r['order'][0].update(m_nOffsetFlag=50)),
        ('bad-state',lambda r:r['order'][0].update(m_nOrderStatus=48)),
        ('filled-inconsistent',lambda r:r['order'][0].update(m_nOrderStatus=56)),
        ('bad-order-quantity',lambda r:r['order'][0].update(m_nVolumeTotal=131)),
        ('bad-date',lambda r:r['deal'][0].update(m_strTradeDate='20260230')),
        ('bad-time',lambda r:r['deal'][0].update(m_strTradeTime='25:00:00')),
        ('long-id',lambda r:r['order'][0].update(m_strOrderSysID='a'*64)),
        ('unicode-control-id',lambda r:r['order'][0].update(m_strOrderSysID='a\u0085b')),
        ('control-id',lambda r:r['order'][0].update(m_strOrderSysID='a\x00b')),
        ('negative-deal-price',lambda r:r['deal'][0].update(m_dPrice=-1)),
        ('missing-amount',lambda r:r['deal'][0].pop('m_dTradeAmount')),
        ('wrong-row-account',lambda r:r['position'][0].update(m_strAccountID='other')),
        ('wrong-currency',lambda r:r['account'][0].update(m_strMoneyType='USD')),
        ('order-conflict',lambda r:r['order'].append(dict(r['order'][0],m_dLimitPrice=12))),
        ('optional-fact-conflict',lambda r:r['order'].append(dict(r['order'][0],m_strAccountID='SYNTHETIC-NQH'))),
        ('deal-conflict',lambda r:r['deal'].append(dict(r['deal'][0],m_dPrice=12))),
    ]:add(name,edit,ready=False)
    for name,mutate in [
        ('missing-observation',lambda x:x.pop('observation')),
        ('wrong-account',lambda x:x['observation']['source'].update(account_id='other')),
        ('wrong-session',lambda x:x['observation']['source'].update(qmt_session_id='other')),
        ('wrong-generation',lambda x:x['observation']['source'].update(generation=999)),
        ('wrong-scope',lambda x:x['observation']['query'].update(scope='strategy')),
        ('false-complete',lambda x:x['observation']['completeness'].update(complete=False)),
        ('wrong-rowcount',lambda x:x['observation']['completeness'].update(row_count=99)),
        ('bad-utc',lambda x:x['observation']['execution'].update(completed_at='2026-10-22T01:02:03+08:00')),
    ]:add(name,mutate=mutate,ready=False)
    add('missing-contract',mode='missing_contract',ready=False)
    add('lost-post-response',mode='post_disconnect')
    add('prepare-budget',mode='slow_health',ready=False,config=dict(request_ms=100,round_ms=500))
    for stage in ('before','pending','position','order','trade','ready'):
        add('stop-'+stage,probe_mode='stop-'+stage,ready=stage=='ready')
    add('release-ready',probe_mode='release-ready');add('delete-ready',probe_mode='delete-ready')
    add('late-owner-pump',probe_mode='late-pump',ready=False,config=dict(request_ms=1000,round_ms=2000))
    add('read-get-transport-failure',mode='forced_slow_get',ready=False,config=dict(request_ms=FUNCTIONAL_REQUEST_MS,round_ms=FUNCTIONAL_ROUND_MS,timeout_ms=100))
    add('throw-ready',probe_mode='throw-ready')
    add('metadata-after-position',ready=False,config=dict(view_bytes=6500))
    add('session-changes-at-deal',mutate=lambda x:x['observation']['source'].update(generation=999) if x['observation']['query']['datatype']=='deal' else None,ready=False)
    add('metadata-budget',ready=False,config=dict(view_bytes=2000))
    if args.drain:
        cases=[]
        for mode in ('closing-gate','post-read-gate','get-read-gate'):
            add(mode,mode='force_get' if mode=='get-read-gate' else 'normal',probe_mode=mode,ready=False,config=dict(close_ms=30))
        add('spurious-wake',mode='slow_health',probe_mode='spurious-wake',ready=False,config=dict(request_ms=600,round_ms=3000))
    if args.only:
        if set(args.only)-{c[0] for c in cases}:raise ValueError('unknown HTTP test selection')
        cases=[c for c in cases if c[0] in args.only]
    reports=[]
    for name,edit,mutation,mode,probe_mode,expected,extra in cases:
        path=work/name;rows=native_rows();
        if edit:edit(rows)
        timing_case=name in ('wait-deadline','spurious-wake','prepare-budget','late-owner-pump','slow-connect','closing-gate','post-read-gate','get-read-gate')
        write(path,fixture(),request_ms=1500 if timing_case else FUNCTIONAL_REQUEST_MS,round_ms=8000 if timing_case else FUNCTIONAL_ROUND_MS)
        contracts=json.loads((path/'contracts.json').read_text(encoding='utf-8'));contracts['SZSE']={'000001':dict(name='synthetic-SZ-stock',exchg='SZSE',product='STK',opendate=20000101,expiredate=20991231)};(path/'contracts.json').write_text(json.dumps(contracts),encoding='utf-8')
        commodities=json.loads((path/'commodities.json').read_text(encoding='utf-8'));commodities['SZSE']=copy.deepcopy(commodities['SSE']);(path/'commodities.json').write_text(json.dumps(commodities),encoding='utf-8')
        with Gateway(path,rows,mutation,mode) as gateway:
            cfg=json.loads((path/'config.json').read_text(encoding='utf-8'));cfg.update(source='qmt_http',base_url=gateway.url,key_id_env='NQH_TEST_KEY',hmac_secret_env='NQH_TEST_SECRET',timeout_ms=1000 if timing_case else FUNCTIONAL_HTTP_MS,max_response_bytes=2097152,close_ms=3000,expected_account='SYNTHETIC-NQH',environment='simulation',currency='CNY',profile='cny_cash_shsz_v1');cfg.update(riskmon=dict(active=True,policy=dict(default=dict(order_total_limits=2,cancel_total_limits=1))));cfg.update(extra);(path/'config.json').write_text(json.dumps(cfg),encoding='utf-8')
            env=dict(os.environ,NQH_TEST_KEY=gateway.key_id,NQH_TEST_SECRET=gateway.secret)
            argv=[str(probe),str(path),str(library),probe_mode];binding=dict(argv=argv,cwd=str(cwd),probe_sha256=hashlib.sha256(probe.read_bytes()).hexdigest(),dll_sha256=hashlib.sha256(library.read_bytes()).hexdigest(),python_inputs=python_inputs)
            (path/'execution.json').write_text(json.dumps(binding,indent=2),encoding='utf-8');start=time.monotonic();proc=subprocess.run(argv,cwd=cwd,env=env,capture_output=True,timeout=child_timeout(cfg));assert binding['probe_sha256']==hashlib.sha256(probe.read_bytes()).hexdigest() and binding['dll_sha256']==hashlib.sha256(library.read_bytes()).hexdigest();(path/'process.log').write_bytes(proc.stdout+proc.stderr)
            result=json.loads((path/'result.json').read_text(encoding='utf-8')) if (path/'result.json').exists() else {};errors=[]
            def check(ok,reason):
                if not ok:errors.append(reason)
            check(proc.returncode==0,'process-exit-'+str(proc.returncode));check((path/'unload-result.json').exists(),'actual-module-unload-after-owners');check(result.get('ready',0)==int(expected),'ready');check(not gateway.errors,'gateway-errors');check(gateway.secret.encode() not in proc.stdout+proc.stderr,'secret-redaction')
            check(all(json.loads(body)['operation_id']=='account.trade_detail' and json.loads(body)['arguments']==dict(account_type='stock',datatype=json.loads(body)['arguments']['datatype'],scope='account') for _,_,body in gateway.posts),'exact-read-allowlist')
            check(result.get('joined')==1 and result.get('worker_live')==0 and result.get('queue')==0,'actual-close');check(result.get('trade_pushes')==0 and result.get('order_pushes')==0,'no-push');check(len({json.loads(x[2])['request_id'] for x in gateway.posts})==len(gateway.posts),'one-post-per-id')
            if args.drain and name!='spurious-wake':
                check(result.get('blocked_wait_ms',0)>=80 and result.get('owner_cpu_ms',999)<100,'actual-callback-blocking-owner-wait')
                timeout=json.loads((path/'view-timeout.json').read_text(encoding='utf-8')) if (path/'view-timeout.json').exists() else {};check(result.get('retained_after_timeout')==1,'timeout-retains-factory-pointer');check(result.get('first_close_ms',9999)<300,'bounded-first-close');check(timeout.get('close')==dict(status='timeout',drained=False,joined=False),'real-pending-callback-barrier');check(timeout.get('failure',{}).get('code')==0,'close-timeout-keeps-first-reason')
            if expected:
                summary=json.loads((path/'view-preclose.json').read_text(encoding='utf-8'));check(summary['observation_qualified']==(name!='throw-ready'),'observation-qualification');check(summary['trade_date']['availability']=='unknown' and summary['aggregate_only'],'explicit-aggregate-unknown-day')
                if name=='happy':
                    check(result.get('margin')==0 and result.get('close_profit')==0 and result.get('dynamic_profit')==0 and result.get('deposit')==0 and result.get('withdraw')==0,'explicit-all-fund-slots');check(result.get('previous_balance')==99900 and result.get('commission')==12.34,'mapped-fund-oracle')
                    account_view=json.loads((path/'view-4-0.json').read_text(encoding='utf-8'));check(account_view['facts']['m_dFrozenCash']['value']==200 and account_view['abi']['frozenMargin']['value']==0,'cash-not-margin');check(account_view['facts']['m_dFrozenMargin']['availability']=='unknown','unknown-margin-fact')
                    for i,batch in enumerate(summary['batches']):check(result.get('observed_'+str(i))==batch['execution_finished_at'][:19]+'Z','v1-seconds-projection-'+str(i))
                    check([result.get(k) for k in ('position','available','long_position','short_position','long_available','short_available')]==[700,420,700,0,420,0],'aggregate-oracle');check(result.get('orders')==0 and result.get('undone')==0,'no-local-managed-tag');check(result.get('balance')==100000 and result.get('dynbalance')==100000,'no-double-profit');check(len(gateway.native_calls)==4,'actual-four-native-queries')
                    for i,batch in enumerate(summary['batches']):
                        stored=gateway.journal.get_gateway_operation(batch['request_id'])['result'];check(stored['observation']['query']['scope']=='account' and batch['result_sha256']==stored['result_sha256'],'original-journal-lineage-'+str(i));check('private_secret' not in json.dumps(stored),'native-whitelist')
            if expected and rows['deal']:
                ids=[]
                for i in range(result['rows_2']):
                    view=json.loads((path/f'view-3-{i}.json').read_text(encoding='utf-8'));identity=view['identity'];raw=next(r for r in rows['deal'] if r['m_strTradeID']==identity['m_strTradeID'] and r['m_strOrderSysID']==identity['m_strOrderSysID'] and r['m_strInstrumentID']==identity['m_strInstrumentID'] and r['m_strTradeDate']==identity['m_strTradeDate'])
                    day=raw['m_strTradeDate'].replace('-','');components=['SSE' if raw['m_strExchangeID']=='SH' else 'SZSE',raw['m_strInstrumentID'],day,raw['m_strTradeID']];wire=b'guanheng.nqh.trade-id.v1\x00'+b''.join(len(v.encode()).to_bytes(4,'big')+v.encode() for v in components);expected_id='nqh1.'+base64.urlsafe_b64encode(hashlib.sha256(wire).digest()).decode().rstrip('=');check(identity['derived_trade_id']==expected_id and identity['mapping_version']=='nqh.trade-id.v1','independent-trade-id-vector');ids.append(expected_id)
                if name=='cross-order-same-trade':check(len(ids)==2 and ids[0]==ids[1] and result.get('native_self_match')==1,'native-self-match-preserved')
                if name in ('cross-security-same-trade','cross-market-same-trade','different-event-date'):check(len(ids)==2 and ids[0]!=ids[1] and result.get('native_self_match')==0,'scope-isolation-no-false-self-match')
            if (path/'native-observer.json').exists():verify_native(path,rows,result,cfg,check)
            closed=json.loads((path/'view-closed.json').read_text(encoding='utf-8')) if (path/'view-closed.json').exists() else {};check(closed.get('close')==dict(status='complete',drained=True,joined=True),'closed-view-proof')
            if name in TARGET_FAILURES:
                reason,delivered,native_calls=TARGET_FAILURES[name]
                check(result.get('error',0)<0 and result.get('reason')==reason,'target-failure-reason')
                check(result.get('delivered')==delivered and len(gateway.native_calls)==native_calls,'target-reached-query-stage')
                check(closed.get('observation_qualified') is False,'target-failure-not-qualified')
                observer=json.loads((path/'native-observer.json').read_text(encoding='utf-8'))
                check(observer['position_calls']==int(bool(delivered&1)) and observer['order_calls']==int(bool(delivered&2)),'only-prior-SPI-stages-applied')
                if name=='bad-date':check(result.get('rows_2')==0 and result.get('rows_0')==2 and result.get('rows_1')==1,'date-batch-rejected-after-position-order')
                if name=='metadata-after-position':check(result.get('rows_1')==0 and result.get('position')==700 and result.get('orders')==0,'metadata-budget-rejects-order-after-real-position')
            if name.startswith('stop-'):
                stage={'before':0,'pending':0,'position':1,'order':3,'trade':7,'ready':15}[name[5:]]
                check(result.get('error')==0 and result.get('reason')=='' and result.get('delivered')==stage,'explicit-stop-stage-without-earlier-failure')
            if name=='throw-ready':check(result.get('error',0)<0 and closed.get('observation_qualified') is False and closed.get('batches',[{},{},{},{}])[3].get('delivered') is False,'callback-half-application-no-success-view-or-replay')
            if name=='metadata-after-position':check(result.get('delivered')==1 and closed.get('observation_qualified') is False,'cumulative-budget-keeps-partial-application')
            if name=='session-changes-at-deal':check(result.get('delivered')==3 and closed.get('observation_qualified') is False,'same-binding-across-four-batches')
            if name in ('wait-deadline','spurious-wake'):
                check(500<=result.get('observed_ms',0)<780,'absolute-task-cutoff-not-renewed');check(result.get('wait_deadlines')==1 and result.get('delivered')==0 and result.get('error',0)<0,'wait-deadline-pump-stops-without-result');check(result.get('owner_cpu_ms',999)<100 and result.get('blocked_wait_ms',0)>=500,'blocked-owner-low-CPU');check(len(gateway.posts)==0,'expired-prepare-no-query')
            if name.startswith('map-late-'):
                check(result.get('reason')=='交付前绝对截止时间耗尽','mapping-target-deadline-reason')
                check(len(gateway.native_calls)==(1 if name=='map-late-position' else 2) and result.get('reads')==len(gateway.native_calls),'mapping-target-query-count')
                stage=0 if name=='map-late-position' else 1;observer=json.loads((path/'native-observer.json').read_text(encoding='utf-8'));check(result.get('mapping_gate_crossed')==1,'deterministic-mapping-gate');check(result.get('delivered')==(0 if stage==0 else 1),'post-mapping-deadline-zero-current-SPI');check(observer['position_calls']==stage and observer['order_calls']==0,'original-SPI-no-late-batch');check(len(gateway.posts)>stage and closed['batches'][stage]['request_id']==json.loads(gateway.posts[stage][2])['request_id'],'late-mapping-keeps-source-id');check(result['position']==(0 if stage==0 else 700),'earlier-position-partial-preserved')
            if name=='slow-connect':
                observer=json.loads((path/'native-observer.json').read_text(encoding='utf-8'));check(observer['connect_calls']==1 and observer['login_calls']==0,'multi-event-pump-no-late-login');check(result.get('reads')==0 and result.get('delivered')==0,'late-control-no-query')
            if name in ('late-owner-pump','read-get-transport-failure'):

                check(result.get('delivered')==0,'deadline-no-SPI');check(len(gateway.posts)==1,'deadline-one-submit');check(bool(gateway.posts) and closed.get('batches',[{}])[0].get('request_id')==json.loads(gateway.posts[0][2])['request_id'],'original-id-survives-owner-deadline-close')
            if name=='prepare-budget':
                check(result.get('reason')=='单项查询截止时间耗尽' and result.get('delivered')==0 and len(gateway.posts)==0 and len(gateway.native_calls)==0,'prepare-cutoff-before-query')
            if name=='late-owner-pump':
                check(result.get('reason')=='单项查询截止时间耗尽' and len(gateway.native_calls)==1,'owner-pump-cutoff-after-source-query')
            if name=='read-get-transport-failure':
                # Async QRT currently maps REQUEST_ERROR to IoError. This case
                # proves a failed real GET before owner cutoff, not the exact
                # phase timer or independent Timeout classification.
                rid=json.loads(gateway.posts[0][2])['request_id'] if gateway.posts else ''
                gets=[call for call in gateway.calls if call[0]=='GET' and call[1].startswith('/internal/v1/operation-results/')]
                observer=json.loads((path/'native-observer.json').read_text(encoding='utf-8'))
                check(result.get('reason')=='qmt_http_exchange_failed' and closed.get('failure',{}).get('transport_error')=='IoError','exact-async-GET-transport-failure')
                check(len(gets)==1 and gets[0][1]=='/internal/v1/operation-results/'+rid,'one-GET-claims-original-POST-id')
                check(len(gateway.native_calls)<=1 and result.get('reads')==1,'failed-read-source-execution-bounded')
                check(0<result.get('observed_ms',0)<cfg['request_ms'] and result.get('wait_deadlines')==0,'transport-fails-before-owner-cutoff')
                check(observer['position_calls']==0 and observer['order_calls']==0,'failed-GET-never-reaches-original-SPI')
            report=dict(case=name,passed=not errors,errors=errors,elapsed_ms=round((time.monotonic()-start)*1000),output=result,posts=len(gateway.posts),native_calls=len(gateway.native_calls));reports.append(report);print(name,'PASS' if not errors else 'FAIL '+','.join(errors),flush=True)
    for relative,digest in python_inputs.items():assert hashlib.sha256((owned/relative).read_bytes()).hexdigest()==digest,relative
    verify(binary_identity)
    if args.qmt_fixture:
        from native_support.qmt_readonly_fixed import verify_snapshot
        verify_snapshot(source,qmt_manifest)
    output=dict(binary_inputs=binary_identity,cwd=str(cwd),python_inputs=python_inputs,original_oracles=original_oracles,generic_dto_model_validation=False,qmt_input_sha256=hashlib.sha256((source/'input.json').read_bytes()).hexdigest(),qmt_commit=QMT_COMMIT,passed=sum(r['passed'] for r in reports),failed=sum(not r['passed'] for r in reports),skipped=0,real_qmt_network_calls=0,cases=reports);(work/'summary.json').write_text(json.dumps(output,indent=2,ensure_ascii=False),encoding='utf-8');return bool(output['failed'])
if __name__=='__main__':raise SystemExit(main())
