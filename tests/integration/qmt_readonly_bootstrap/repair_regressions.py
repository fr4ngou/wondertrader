"""F1/F2/F3 root-cause regressions against the real fixed-Adapter child process."""
from pathlib import Path
import argparse,copy,hashlib,json,subprocess,time
from run import fixture,write
from invocation import arguments,resolve,verify

def main():
    p=argparse.ArgumentParser();p.add_argument('--build',type=Path);arguments(p);a=p.parse_args()
    probe,library,cwd,build,binary_identity=resolve(a)
    cases=[]
    def add(name,edit=None,expect='external',raw=None):
        f=copy.deepcopy(fixture())
        if edit:edit(f)
        cases.append((name,f,expect,raw))
    def order(f):return f['responses']['orders'][0]['data'][0]
    def orders(f):return f['responses']['orders'][0]['data']
    def trades(f):return f['responses']['trades'][0]['data']
    def owned(o,oid=None,lid=17):
        if oid is not None:o['order_id']=oid
        o.update(user_tag='otp.nqb.'+str(lid),ownership=dict(kind='fixture_wt',adapter_id='nqb',order_id=o['order_id'],local_id=lid))
    add('valid-fixture-proof',expect='owned')
    for name,tag in [('foreign-prefix','otp.nqb-other.17'),('foreign-adjacent','otp.nqbX.17'),('foreign-adapter','otp.other.17'),('case-prefix','OTP.NQB.17'),('case-adapter','otp.NQB.17'),('alpha','otp.nqb.garbage'),('zero','otp.nqb.0'),('leading-zero','otp.nqb.017'),('plus','otp.nqb.+17'),('minus','otp.nqb.-17'),('space','otp.nqb. 17'),('trailing-space','otp.nqb.17 '),('decimal','otp.nqb.17.0'),('suffix','otp.nqb.17tail'),('empty-id','otp.nqb.'),('max-sentinel','otp.nqb.4294967295'),('overflow','otp.nqb.4294967296'),('long-overflow','otp.nqb.999999999999999999999'),('empty-tag','')]:
        add(name,lambda f,t=tag:order(f).update(user_tag=t))
    add('missing-tag',lambda f:order(f).pop('user_tag'))
    add('no-proof',lambda f:order(f).pop('ownership'))
    add('boolean-proof',lambda f:order(f).update(ownership=True))
    add('empty-proof',lambda f:order(f).update(ownership={}))
    for key,value in [('kind','http_claim'),('adapter_id','other'),('order_id','another-broker'),('local_id',18),('local_id',True)]:
        add('proof-mismatch-'+key+'-'+str(value),lambda f,k=key,v=value:order(f)['ownership'].update({k:v}))
    add('maximum-valid-id',lambda f:owned(order(f),lid=4294967294),expect='owned')
    add('minimum-valid-id',lambda f:owned(order(f),lid=1),expect='owned')
    def collision(f,terminal=False):
        other=copy.deepcopy(order(f));owned(other,oid='fixture-order-2')
        if terminal:other.update(state='filled',filled=200,remaining=0,inactive=0)
        orders(f).append(other)
    add('localid-collision',collision,expect='failed')
    add('localid-collision-terminal',lambda f:collision(f,True),expect='failed')
    def two_external(f):
        order(f)['user_tag']='otp.nqb-other.17';other=copy.deepcopy(order(f));other['order_id']='fixture-order-2';orders(f).append(other)
    add('external-ids-statistics-retained',two_external,expect='external-two')
    add('same-localid-same-order',lambda f:orders(f).append(copy.deepcopy(order(f))),expect='owned')
    add('reordered-order',lambda f:orders(f).append(dict(reversed(list(order(f).items())))),expect='owned')
    def numeric_order(f):
        other=copy.deepcopy(order(f))
        for k,v in list(other.items()):
            if type(v) is int:other[k]=float(v)
        other['ownership']['local_id']=17.0;orders(f).append(other)
    add('numeric-order',numeric_order,expect='owned')
    def extra_order(f):
        other=copy.deepcopy(order(f));order(f)['source_extension']='first';other['source_extension']={'ignored':True};orders(f).append(other)
    add('unknown-order-extension',extra_order,expect='owned')
    def normalized_empty(f):
        order(f).pop('user_tag');other=copy.deepcopy(order(f));other['user_tag']='';orders(f).append(other)
    add('missing-empty-tag-equivalent',normalized_empty)
    add('real-order-conflict',lambda f:orders(f).append(dict(order(f),price=10.36)),expect='failed')
    def eligibility_conflict(f):
        other=copy.deepcopy(order(f));other.pop('ownership');orders(f).append(other)
    add('eligibility-conflict',eligibility_conflict,expect='failed')
    add('reordered-trade',lambda f:trades(f).append(dict(reversed(list(trades(f)[0].items())))),expect='owned')
    def numeric_trade(f):
        other=copy.deepcopy(trades(f)[0])
        for k,v in list(other.items()):
            if type(v) is int:other[k]=float(v)
        trades(f).append(other)
    add('numeric-trade',numeric_trade,expect='owned')
    add('real-trade-conflict',lambda f:trades(f).append(dict(trades(f)[0],amount=722)),expect='failed')
    def tuple_identity(f):
        trades(f)[0].update(order_id='a:b',trade_id='c');trades(f).append(dict(trades(f)[0],order_id='a',trade_id='b:c'))
    add('trade-identity-tuple',tuple_identity,expect='two-trades')
    base=json.dumps(fixture(),ensure_ascii=False)
    def extension(raw):return (base[:-1]+',"extra":'+raw+'}').encode('utf-8')
    add('depth-limit-valid',expect='owned',raw=extension('['*11+'0'+']'*11))
    add('depth-limit-empty-container',expect='owned',raw=extension('['*12+']'*12))
    add('depth-first-invalid',expect='init-failed',raw=extension('['*12+'0'+']'*12))
    for depth in (13,10000,100000,400000):add('array-depth-'+str(depth),expect='init-failed',raw=('['*depth+'0'+']'*depth).encode())
    add('object-depth-100000',expect='init-failed',raw=('{"x":'*100000+'0'+'}'*100000).encode())
    add('array-capacity',expect='init-failed',raw=extension('['+','.join(['0']*4097)+']'))
    add('object-capacity',expect='init-failed',raw=extension('{'+','.join('"k'+str(i)+'":0' for i in range(4097))+'}'))
    add('node-capacity',expect='init-failed',raw=extension(json.dumps([[0]*4096 for _ in range(16)])))
    add('nested-duplicate-key',expect='init-failed',raw=extension('{"k":1,"k":2}'))
    add('invalid-utf8',expect='init-failed',raw=extension('"PLACEHOLDER"').replace(b'PLACEHOLDER',b'\xff'))
    add('raw-nul',expect='init-failed',raw=base.encode()+b'\x00{}')
    add('escaped-delimiters-not-depth',expect='owned',raw=extension(json.dumps('[{\\"'*30000)))
    out=build/('repair-regressions-'+str(time.time_ns()));out.mkdir();results=[]
    for name,f,expect,raw in cases:
        root=out/name;write(root,f)
        if raw is not None:(root/'fixture.json').write_bytes(raw)
        start=time.monotonic();proc=subprocess.run([str(probe),str(root),str(library),'normal'],cwd=cwd,capture_output=True,timeout=10)
        (root/'process.log').write_bytes(proc.stdout+proc.stderr)
        r=json.loads((root/'result.json').read_text(encoding='utf-8')) if (root/'result.json').exists() else {};errors=[]
        def check(ok,label):
            if not ok:errors.append(label)
        check(proc.returncode==0,'normal-process-exit')
        if expect=='init-failed':check(r.get('initialized') is False,'bounded-init-rejection')
        else:
            check(r.get('joined')==1 and r.get('worker_live')==0 and r.get('queue')==0,'normal-worker-close')
            check(r.get('threads_before')==r.get('threads_after'),'threads-reclaimed')
            check(r.get('trade_pushes')==0 and r.get('order_pushes')==0,'no-incremental-push')
            if expect=='failed':
                check(r.get('error',0)<0 and r.get('ready')==0,'batch-failure')
                check(r.get('rows_2' if name=='real-trade-conflict' else 'rows_1')==0,'batch-rejected-before-SPI')
            else:
                check(r.get('ready')==1 and r.get('position')==700,'native-ready-position')
                if expect.startswith('external'):check(r.get('orders')==0 and r.get('undone')==0 and r.get('rows_1')==(2 if expect=='external-two' else 1),'external-retained-without-management')
                else:check(r.get('orders')==1 and r.get('undone')==130 and r.get('rows_1')==1,'owned-order-oracle')
                check(r.get('rows_2')==(2 if expect=='two-trades' else 1),'semantic-trade-dedup')
        results.append(dict(case=name,expect=expect,passed=not errors,errors=errors,exit_code=proc.returncode,elapsed_ms=round((time.monotonic()-start)*1000),output=r));print(name,'PASS' if not errors else 'FAIL '+','.join(errors),flush=True)
    verify(binary_identity)
    report=dict(binary_inputs=binary_identity,cwd=str(cwd),passed=sum(r['passed'] for r in results),failed=sum(not r['passed'] for r in results),skipped=0,child_processes=len(results),results=results)
    (out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print('RESULT',out,report['passed'],report['failed']);return bool(report['failed'])
if __name__=='__main__':raise SystemExit(main())
