"""真实Managed ctx消费原版业务类；账户/信号为显式合成夹具，执行器和Source为零。"""
import ctypes as C
import hashlib,json,os,shutil,sys,time
from pathlib import Path
from types import SimpleNamespace as NS
from fractions import Fraction
from dataclasses import replace
from test_profiles import make,small,Broker,Allocation,Signals,ORIGINAL_ID,RETAINED_ID
from guanheng_wt_runtime import original_live as mod
from guanheng_wt_runtime.execution_strategy import CtaRuntime,StrategyBinding,QuoteValue
from guanheng_wt_runtime.execution_process import ExecutionProcessConfig
from datetime import datetime,timezone,timedelta
from zoneinfo import ZoneInfo
class Patch:
    def setattr(self,o,k,v):setattr(o,k,v)

def main(output):
    output.mkdir();app=output/'installation/app';(app/'strategies').mkdir(parents=True)
    for key,rel in [('GH_MANAGED_V2_DLL','strategies/GuanhengManagedStrategy.dll'),('GH_MANAGED_RUNTIME_DLL','GuanhengCtaRuntime.dll')]:
        shutil.copyfile(os.environ[key],app/rel)
    files=tuple((p.relative_to(app.parent).as_posix(),hashlib.sha256(p.read_bytes()).hexdigest()) for p in app.rglob('*.dll'))
    configpath=output/'execution.json';configpath.write_text(json.dumps(dict(schema_version='guanheng.cta-execution.v1',installation_root=str(app),strategies=[dict(id=n,module='strategies/GuanhengManagedStrategy.dll',factory='GuanhengManagedStrategy',name='Core') for n in (RETAINED_ID,ORIGINAL_ID)])),encoding='utf8')
    config=ExecutionProcessConfig(app.parent,configpath,hashlib.sha256(configpath.read_bytes()).hexdigest(),output,20,8,files)
    prepared=small({'510300':'BUY'});prepared.update(decision_date='2026-11-05',eligible_date='2026-11-06',decision_at='2026-11-05T16:00:00+08:00')
    for rows in prepared['signals_today'].values():
        for row in rows:row['date']='2026-11-05'
    owner,unused,asa,signals,published=make(Patch(),signals=Signals(prepared));events=[]
    class Proxy:
        def __init__(self,ctx):self.ctx=ctx
        def __getattr__(self,k):return getattr(self.ctx,k)
        def broker_observation(self):return Broker(position_received_ms=int(time.time()*1000))
        def quote(self,symbol):
            now=datetime.now(ZoneInfo('Asia/Shanghai'))-timedelta(seconds=1)
            return QuoteValue(int(now.strftime('%Y%m%d')),int(now.strftime('%H%M%S'))*1000,10.)
    def original(ctx):events.append((ORIGINAL_ID,ctx.event.ctx_id,ctx.event.kind));owner.callback(Proxy(ctx))
    oldsymbols=tuple(sorted('SSE.ETF.588030' if s=='SSE.ETF.589680' else s for s in owner.targets if s!='SZSE.ETF.159352'))
    assert len(oldsymbols)==8 and len(set(oldsymbols)&set(owner.targets))==7
    def legacy(ctx):
        events.append((RETAINED_ID,ctx.event.ctx_id,ctx.event.kind))
        if ctx.event.kind==1:ctx.bars(oldsymbols[0],'m1',1,main=True)
        if ctx.event.kind==4:ctx.set_targets(tuple((s,100) for s in oldsymbols))
    bindings=(StrategyBinding(RETAINED_ID,oldsymbols[0],oldsymbols,oldsymbols,legacy),replace(owner.binding(),callback=original))
    runtime=CtaRuntime(config,bindings,deadline=time.monotonic()+20)
    dll=C.CDLL(os.environ['GH_MANAGED_V2_PROBE']);run=dll.gh_managed_v2_probe;run.argtypes=[C.c_char_p,C.c_char_p,C.POINTER(C.c_char_p),C.c_uint32];run.restype=C.c_int
    ids=(C.c_char_p*2)(RETAINED_ID.encode(),ORIGINAL_ID.encode());native=output/'native';native.mkdir()
    rc=run(str(app/'strategies/GuanhengManagedStrategy.dll').encode(),(str(native)+'/').encode(),ids,2)
    assert rc==0 and runtime._last_error is None,(rc,runtime._last_error)
    status=runtime.status();assert status['created']==status['destroyed']==2 and status['setters']==26 and status['failure']==0,status
    read=dll.gh_managed_v2_probe_target;read.argtypes=[C.c_char_p,C.c_char_p];read.restype=C.c_double
    actual={s:read(ORIGINAL_ID.encode(),s.encode()) for s in owner.targets};assert actual['SSE.ETF.510300']==100000 and sum(actual.values())==100000
    assert len({ctx for _,ctx,_ in events})==2 and any(type(x)is tuple and x[0]=='prepare' for x in asa.calls)
    result=dict(passed=True,events=events,targets=actual,native=status,source_requests=0,orders=0,
        qualification='actual Native Factory/CtaStraContext/Managed borrow/complete setter; synthetic signal/account/quotes; real OriginalLiveStrategy + optional ASA adapter; no Source or executor')
    (output/'RESULT.json').write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps(result))
if __name__=='__main__':main(Path(sys.argv[1]))
