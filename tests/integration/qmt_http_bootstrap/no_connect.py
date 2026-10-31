from pathlib import Path
import argparse,hashlib,json,os,re,shutil,subprocess,sys
parser=argparse.ArgumentParser();parser.add_argument('--build',type=Path);parser.add_argument('--probe',type=Path);parser.add_argument('--library',type=Path);parser.add_argument('--work',type=Path,required=True);args=parser.parse_args()
ROOT=Path(__file__).resolve().parents[3];work=args.work.resolve();work.mkdir(parents=True,exist_ok=False)
metadata={}
if args.probe is not None or args.library is not None:
 if args.probe is None or args.library is None:raise ValueError('provide --probe and --library together')
 probe=args.probe.resolve(strict=True);library=args.library.resolve(strict=True);metadata['compile_exit']=None
else:
 if args.build is None:raise ValueError('explicit --probe/--library or legacy --build required')
 BUILD=args.build.resolve();sys.path.insert(0,str(ROOT/'scripts'));import native
 env,_=native.environment(work);source=Path(__file__).with_suffix('.cpp');snapshot=work/'no_connect.cpp';snapshot.write_bytes(source.read_bytes());rsp=(BUILD/'host/compile.rsp').read_text(encoding='utf-8');rsp=re.sub(r'(?::?"[^\"]+\.cpp"|\S+\.cpp)','',rsp);rsp=re.sub(r'/Fe\S+',lambda _: '/Fe'+str(work/'probe.exe'),rsp);rsp=str(snapshot)+' '+rsp;(work/'compile.rsp').write_text(rsp,encoding='utf-8');run=subprocess.run([shutil.which('cl.exe',path=env['PATH']),'@'+str(work/'compile.rsp')],cwd=work,env=env,capture_output=True,timeout=120);(work/'compile.log').write_bytes(run.stdout+run.stderr);assert run.returncode==0,run.stderr
 probe=work/'probe.exe';library=BUILD/'traders/TraderQMTReadOnly.dll';metadata=dict(compile_exit=run.returncode,host_response_sha256=hashlib.sha256((BUILD/'host/compile.rsp').read_bytes()).hexdigest(),source_sha256=hashlib.sha256(snapshot.read_bytes()).hexdigest())
identity={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (probe,library)}
sys.path.insert(0,str(ROOT/'tests/integration/http'));from test_qmt_http import GatewayStub
results=[]
with GatewayStub() as gateway:
 for name in ['valid','invalid-binding','invalid-before-close']:
  cfg=dict(enabled=True,savedata=False,source='qmt_http',adapter_id='nqb',instance_id='no-connect-'+name,max_rows=128,request_ms=1500,round_ms=8000,close_ms=30,expected_account='SYNTHETIC-NQH',environment='simulation',currency='CNY',profile='cny_cash_shsz_v1',base_url=gateway.url,key_id_env='NQH_TEST_KEY',hmac_secret_env='NQH_TEST_SECRET',timeout_ms=1000,max_response_bytes=2097152)
  if name=='invalid-binding':cfg['expected_account']=''
  if name=='invalid-before-close':cfg.update(request_ms=0,close_ms=0)
  file=work/(name+'.json');file.write_text(json.dumps(cfg),encoding='utf-8');childenv=dict(os.environ,NQH_TEST_KEY=gateway.key_id,NQH_TEST_SECRET=gateway.secret);proc=subprocess.run([str(probe),str(library),str(file),'valid' if name=='valid' else 'invalid'],cwd=work,env=childenv,capture_output=True,timeout=5);(work/(name+'.log')).write_bytes(proc.stdout+proc.stderr);assert proc.returncode==0,(name,proc.stderr);value=json.loads(proc.stdout);assert value['close']==dict(status='complete',drained=True,joined=True);assert gateway.calls==[];assert gateway.secret.encode() not in proc.stdout+proc.stderr;results.append(dict(case=name,passed=True,close=value['close'],http_calls=0,error=value['failure']['code']))
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in identity.items())
report=dict(passed=3,failed=0,binary_inputs=identity,test_tool_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),cases=results,**metadata);(work/'summary.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('PASS',3)
