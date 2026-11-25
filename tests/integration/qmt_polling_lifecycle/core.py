"""经真实 WinHTTP 核对同一绑定、同路由传输换代和非法绑定变化。"""
from pathlib import Path
import argparse,base64,ctypes,hashlib,json,shutil,socket,subprocess,sys,threading
from types import SimpleNamespace
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer

def main():
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--build',type=Path,required=True);a=p.parse_args()
    root=Path(__file__).resolve().parents[3];work=a.work.resolve();work.mkdir(parents=True,exist_ok=False)
    for component in ('agent','host'):
     sys.path.insert(0,str(root/'connectors/qmt_shm'/component))
    from guanheng_qmt_shm.read_retention_journal import RetainedReadJournal
    from guanheng_qmt_shm_agent.results import finalize_result
    clock=ctypes.windll.kernel32.GetTickCount64
    clock.restype=ctypes.c_uint64
    stage=work/'source';stage.mkdir()
    for n in ['GuanhengCommon','Includes']:shutil.copytree(root/'config/native-data-variants/parser_retained_v6/src'/n if n=='GuanhengCommon' else root/'src'/n,stage/n)
    shutil.copyfile(Path(__file__).with_name('core_probe.cpp'),stage/'probe.cpp')
    build=a.build.resolve();env=json.loads((build/'TOOLCHAIN.json').read_bytes())['environment']
    flags=['/nologo','/std:c++17','/EHsc','/MD','/O1','/utf-8','/DNOMINMAX','/DWIN32_LEAN_AND_MEAN','/DBOOST_ALL_NO_LIB','/D_CRT_SECURE_NO_WARNINGS','/FIobjbase.h']
    inc=[stage,build/'deps/rapidjson/include',build/'deps/spdlog/include',*list((build/'deps/boost/libs').glob('*/include'))]
    names=['probe.cpp',*[f'GuanhengCommon/{n}.cpp'for n in ['QmtHostReadClient','QmtBoundReadCore','QmtHostCodec','QmtReadTransport','BoundedSignedHttp']]]
    cl=shutil.which('cl.exe',path=env['PATH']);ln=shutil.which('link.exe',path=env['PATH'])
    for i,n in enumerate(names):
     r=subprocess.run([cl,*flags,*['/I'+str(x)for x in inc],'/c',str(stage/n),'/Fo'+str(work/f'{i}.obj')],env=env,cwd=work,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=90);(work/f'{i}.log').write_bytes(r.stdout+r.stderr);assert r.returncode==0,n
    r=subprocess.run([ln,'/nologo','/out:'+str(work/'probe.exe'),*[str(work/f'{i}.obj')for i in range(len(names))],'winhttp.lib','bcrypt.lib','rpcrt4.lib','ole32.lib','ws2_32.lib'],env=env,cwd=work,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW);(work/'link.log').write_bytes(r.stdout+r.stderr);assert r.returncode==0
    canon=lambda v:json.dumps(v,sort_keys=True,separators=(',',':')).encode();sha=lambda b:hashlib.sha256(b).hexdigest()
    control=dict(schema_version='1.0',max_pending_calls=8,max_call_bytes=8192,max_reply_bytes=8192,max_retained_bytes=1048576,max_cycle_messages=8,max_cycle_bytes=65536,poll_seconds=0.01,max_call_seconds=10)
    profile=dict(read_profile_version='qmt.read-profile.v6',read_operations=['market.full_tick','market.history_prepare'],execution_timeout_ms=1000,control_profile=control,operation_profiles={
    'market.full_tick':dict(policy_id='qmt.standard-read.v1',policy_version='1.0',execution_timeout_ms=1000,limits={}),
    'market.history_prepare':dict(policy_id='qmt.history-preparation.v1',policy_version='1.0',execution_timeout_ms=1000,limits=dict(schema_version='qmt.history-preparation-limits.v2',periods=['1m'],max_calendar_days={'1m':5,'1d':5},max_tasks=1,max_queued=1,total_timeout_ms=1000))},read_retention=dict(schema='qmt.read-retention.v1',max_lifetime_ms=2000))
    praw=canon(profile)
    binding=dict(schema_version='1.0',route=dict(route_id='synthetic',executor_id='synthetic',route_epoch=0),transport_generation='1'*32,host_instance_id='2'*32,journal_generation=None,observation_identity=None,capability_sha256=sha(praw))
    def envelope(change):
     b=dict(binding);raw=praw
     if change:
      b['transport_generation']='3'*32
      if change=='host':b['host_instance_id']='4'*32
      if change=='route':
       b['route']=dict(b['route'],executor_id='different-executor')
      if change=='capability':
       operations=dict(profile['operation_profiles'])
       operations['market.full_tick']=dict(operations['market.full_tick'],execution_timeout_ms=900)
       raw=canon(dict(profile,operation_profiles=operations))
       b['capability_sha256']=sha(raw)
     return dict(schema_version='qmt.bound-read.v1',binding=b,binding_sha256=sha(canon(b)),read_profile_body_b64=base64.b64encode(raw).decode(),read_profile_body_sha256=sha(raw),limits=dict(max_request_bytes=8192,max_result_bytes=8192,max_http_request_bytes=16384,max_http_response_bytes=4*((8192+2)//3)+16384),order_ready=False)
    results=[]
    for change in [None,'transport','route','capability','after-result','after-result-ack-lost']:
     transcript=[];gets=[0];original=[];acked=[]
     journal=RetainedReadJournal(work/f'{change}.sqlite',binding['route'],max_records=8,max_result_bytes=8192,
       max_request_bytes=8192,max_journal_bytes=8*32768,read_profile=profile,
       clock=SimpleNamespace(seconds=lambda:clock()/1000)) if change and change.startswith('after-result') else None
     class Handler(BaseHTTPRequestHandler):
      def log_message(self,*a):pass
      def do_GET(self):self.handle_one()
      def do_POST(self):self.handle_one()
      def handle_one(self):
       n=int(self.headers.get('Content-Length',0));body=self.rfile.read(n);transcript.append(dict(method=self.command,path=self.path,body_sha256=sha(body)))
       code=200
       if self.path=='/internal/v1/read-binding':
        gets[0]+=1
        if gets[0]==3:code=503;reply={}
        else:
         changed_binding='host' if change=='after-result-ack-lost' else 'transport'
         reply=envelope(changed_binding if original else None) if journal else envelope(change if gets[0]>3 else None)
       elif self.path=='/internal/v1/read-retention-status':reply=dict(schema='qmt.read-retention-status.v1',capacity=8,retained=0,held_unknown=0,awaiting_consumer=0,queued_or_running=0,awaiting_ticket_end=0)
       elif journal and self.path.endswith('/bound-operations/market.full_tick'):
        submitted=json.loads(body)
        original_body=base64.b64decode(submitted['request_body_b64'])
        assert not original and sha(original_body)==submitted['request_body_sha256']
        rid=journal.submit_ticket(original_body,binding,submitted['ticket'],queue_timeout_ms=1000)
        assert journal.claim_bound(binding)
        result=finalize_result(dict(request_id=rid,operation_id='market.full_tick',ok=True,
            completed_at='2025-11-25T01:31:00Z',data={'000001.SZ':dict(time=1764034260000,
             lastPrice=10,open=10,high=10,low=10,lastClose=10,volume=100,amount=1000)}),8192)
        journal.finish_bound(rid,result,binding)
        original.append(rid);reply=journal.get_bound(rid)
       elif journal and self.path.endswith('/consumed'):
        assert self.path.split('/')[-2]==original[0]
        epoch='4'*32 if change=='after-result-ack-lost' else binding['host_instance_id']
        reply=journal.consumed(original[0],json.loads(body),epoch)
        acked.append(reply)
        if change=='after-result-ack-lost':
         if len(acked)==1:
          assert reply['consumed'] and not reply['retained']
          self.connection.shutdown(socket.SHUT_RDWR)
          return
         assert reply is None
         code=410;reply={'error_code':'read_result_unretained'}
       else:code=503;reply={}
       raw=canon(reply);self.send_response(code);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
     server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever);thread.start()
     try:r=subprocess.run([str(work/'probe.exe'),f'http://127.0.0.1:{server.server_port}'],env=env,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=15)
     finally:
      server.shutdown();server.server_close();thread.join(3)
      if journal:journal.close()
     (work/f"{change or 'unchanged'}.stdout").write_bytes(r.stdout+r.stderr)
     print(r.returncode,r.stdout.decode(),flush=True)
     value=json.loads(r.stdout);assert r.returncode==0 and value['first_empty']==1 and value['invalidated']==1 and value['drained']==1
     posts=[x for x in transcript if x['path']=='/internal/v1/bound-operations/market.full_tick']
     if journal:
      acknowledgements=[x for x in transcript if x['path'].endswith('/consumed')]
      assert len(posts)==1 and value['second_receipt']==1 and value['same_origin']==0
      if change=='after-result-ack-lost':
       assert len(acknowledgements)==2 and value['old_result_retried']==1
       assert acknowledgements[0]['body_sha256']==acknowledgements[1]['body_sha256']
      else:assert len(acknowledgements)==1 and value['old_result_retried']==0
      assert value['second_reason']=='qmt_host_transport_replaced_after_result' and value['old_result_consumed']==1
     elif change in ('route','capability'):
      assert not posts and value['second_receipt']==0 and value['restored']==0 and value['second_reason']=='qmt_host_binding_changed'
     elif change=='transport':
      assert len(posts)==1 and value['second_receipt']==0 and value['restored']==1 and value['same_origin']==0
      assert value['second_reason']=='qmt_host_transport_replaced_before_submit' and value['after_rebind_receipt']==1
     else:
      assert len(posts)==1 and value['second_receipt']==1 and value['restored']==1 and value['same_origin']==1 and value['receipt_same']==1
     results.append(dict(binding_change=change,result=value,transcript=transcript))
    result=dict(passed=True,cases=results,source_sha256={n:sha((stage/n).read_bytes())for n in names},qualification='Actual retained Common+HostReadClient+WinHTTP to synthetic local HTTP; no broker/production, one original terminal result verified and acknowledged through the retained journal')
    (work/'RESULT.json').write_text(json.dumps(result,indent=2),encoding='utf8');print('passed',flush=True)

if __name__=="__main__":
    main()
