"""Targeted checks on the existing compiled probe; no C++ rebuild required."""
from pathlib import Path
import argparse, copy, hashlib, json, subprocess, time
from run import fixture,write
from invocation import arguments,resolve,verify

def main():
    p=argparse.ArgumentParser();p.add_argument('--build',type=Path);p.add_argument('--main-results',type=Path,required=True);arguments(p);a=p.parse_args()
    probe,library,cwd,build,binary_identity=resolve(a)
    b=build
    out=b/('supplement-'+str(time.time_ns()));out.mkdir();results=[]
    for name in ('round-budget','sell-history','different-observations'):
        f=copy.deepcopy(fixture());kwargs={}
        if name=='round-budget':f['delay_ms']=60;kwargs=dict(request_ms=100,round_ms=150)
        elif name=='sell-history':
            f['responses']['orders'][0]['data'][0]['side']='sell';f['responses']['trades'][0]['data'][0]['side']='sell'
        else:
            for i,k in enumerate(('positions','orders','trades','account')):f['responses'][k][0]['observed_at']='2026-10-22T01:36:0'+str(i)+'Z'
        root=out/name;write(root,f,**kwargs)
        proc=subprocess.run([str(probe),str(root),str(library),'normal'],cwd=cwd,capture_output=True,timeout=10)
        (root/'process.log').write_bytes(proc.stdout+proc.stderr);r=json.loads((root/'result.json').read_text(encoding='utf-8'));errors=[]
        def check(ok,label):
            if not ok:errors.append(label)
        check(proc.returncode==0 and r['joined']==1 and r['worker_live']==0 and r['queue']==0,'normal-close')
        if name=='round-budget':check(r['ready']==0 and r['error']<0 and '总预算' in r['reason'],'whole-round-deadline')
        elif name=='sell-history':check(r['ready']==1 and r['position']==700 and r['available']==420 and r['undone']==-130 and r['trade_pushes']==0,'sell-projection-query-only')
        else:check(r['ready']==1 and all(r['observed_'+str(i)]=='2026-10-22T01:36:0'+str(i)+'Z' for i in range(4)),'separate-query-times-preserved')
        results.append(dict(case=name,passed=not errors,errors=errors,output=r,executed_child=True))
    previous=json.loads(a.main_results.read_text(encoding='utf-8'));lookup={r['case']:r['output'] for r in previous['results']}
    for name,expected in {'order-accepted':(1,200),'order-filled':(0,0),'order-canceled':(0,0),'order-rejected':(0,0),'order-canceling':(1,130)}.items():
        r=lookup[name];passed=(r['orders'],r['undone'])==expected
        results.append(dict(case=name+'-native-oracle',passed=passed,errors=[] if passed else ['native-state-oracle'],executed_child=False,reused=str(a.main_results)))
    verify(binary_identity)
    report=dict(binary_inputs=binary_identity,cwd=str(cwd),passed=sum(r['passed'] for r in results),failed=sum(not r['passed'] for r in results),skipped=0,new_child_processes=3,reused_result_checks=5,results=results)
    (out/'summary.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8');print('RESULT',out,report['passed'],report['failed']);return bool(report['failed'])
if __name__=='__main__':raise SystemExit(main())
