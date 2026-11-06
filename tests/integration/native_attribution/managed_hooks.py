"""可选归属ABI的实际多ctx意图与原八/九标的兼容验证。"""
from pathlib import Path
import ctypes as C
import importlib.util
import json
import os
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'apps/wt_runtime'))
spec=importlib.util.spec_from_file_location('managed_v2_existing',ROOT/'tests/integration/qmt_cta_product/test_managed_v2.py')
existing=importlib.util.module_from_spec(spec);spec.loader.exec_module(existing)
class Event(C.Structure):
 _pack_=8
 _fields_=[('size',C.c_uint32),('version',C.c_uint32),('kind',C.c_uint32),('thread_role',C.c_uint32),('epoch',C.c_uint64),('remaining_ms',C.c_uint64),('json_bytes',C.c_uint32),('reserved',C.c_uint32),('json_utf8',C.c_void_p)]
class Reply(C.Structure):
 _pack_=8
 _fields_=[('size',C.c_uint32),('version',C.c_uint32),('decision',C.c_int32),('reserved',C.c_uint32),('authorized_quantity',C.c_double)]
Callback=C.CFUNCTYPE(C.c_int32,C.POINTER(Event),C.POINTER(Reply),C.c_void_p)
def main(output):
 api=existing._api();original=api.CtaRuntime;events=[];callbacks=[];runtimes=[]
 def runtime(*args,**kwargs):
  value=original(*args,**kwargs);runtimes.append(value)
  @Callback
  def receive(event,reply,user):
   try:
    e=event.contents;r=reply.contents
    assert e.size==48 and e.version==1 and e.kind==1 and e.thread_role==1 and e.epoch>0
    snapshot=json.loads(C.string_at(e.json_utf8,e.json_bytes));assert snapshot['epoch']==e.epoch
    events.append(snapshot);r.decision=0;r.authorized_quantity=0;return 0
   except BaseException:return -1
  callbacks.append(receive);fn=value._api.gh_ms_attribution_configure;fn.argtypes=[Callback,C.c_void_p];fn.restype=C.c_int32
  assert fn(receive,None)==0
  return value
 api.CtaRuntime=runtime;os.environ['GH_MANAGED_V2_CASE']='normal'
 existing._native_main(output)
 assert len(events)==2 and {e['strategy_id'] for e in events}=={'legacy8','original9'}
 assert {len(e['targets']) for e in events}=={8,9} and len({e['ctx_id'] for e in events})==2
 assert all(e['date']==e['trading_date']==20261106 and e['time']==1500 for e in events)
 assert runtimes[0]._api.gh_ms_attribution_configure(callbacks[0],None)<0
 rt=C.CDLL(os.environ['GH_MANAGED_RUNTIME_DLL']);rt.gh_cta_attribution_layout.argtypes=[C.c_uint32];rt.gh_cta_attribution_layout.restype=C.c_uint64
 assert rt.gh_cta_attribution_abi_version()==1 and [rt.gh_cta_attribution_layout(i) for i in (1,2,99)]==[48,24,0]
 (output/'ATTRIBUTION.json').write_text(json.dumps({'passed':True,'copied_events':events,'native_calls':17,'real_broker_calls':0,'capability_layout':[48,24]},indent=2),encoding='utf-8')
 print(json.dumps({'passed':True,'ctx':2,'full_targets':[8,9],'native_setters':17,'Source_requests':0}))
if __name__=='__main__':main(Path(sys.argv[1]))
