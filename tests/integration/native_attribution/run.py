"""真实Native Host→原SHM/HMAC Host→SDK替身，归属回调验收。"""
from pathlib import Path
import argparse,hashlib,json,sys,threading
ROOT=Path(__file__).resolve().parents[3]
for name in ('apps/guanheng','connectors/qmt_shm/host','connectors/qmt_shm/agent','tests/integration/qmt_shm_trading','tests/integration/qmt_standard_trader','tests/integration/qmt_query_submission_group','tests/integration/qmt_broker_context'):
 sys.path.insert(0,str(ROOT/name))
from run_funds_host import FundsFixture
from event_query_fixture import _Child,_FixtureOwners,decode,canonical,write_new,uptime_ms
class Fixture(FundsFixture):
 def __init__(self,directory,deadline,mode):
  super().__init__(directory,deadline,'positive');self.mode=mode;self.proof=directory/'prepared-before-submit.json';self.event_count=2 if mode=='event' else 0
 def insert(self,*values):
  assert threading.get_ident()==self.owner_thread and not self.sdk and values[3]=='000001.SZ'
  assert values[5]==10.01 and values[6]==(200 if self.mode=='legacy' else 100)
  if self.mode!='legacy':
   proof=decode(self.proof.read_bytes());assert proof['quantity']==values[6] and proof['limit_price_cny']=='10.01'
   assert len(proof['command_id'])==36 and len(proof['command_sha256'])==64
  self.tokens.append(values[9]);self.sdk.append({'operation':'insert','args':list(values[:-1]),'uptime_ms':uptime_ms(),'prepared_proof_checked_before_sdk':self.mode!='legacy'})
  if self.mode=='event':
   self.emit('order',self.row('order',values[9]));self.emit('deal',self.row('deal',values[9]))
 def detail(self,account,account_type,datatype):
  if self.tokens and datatype in ('order','deal'):
   self.queries.append({'datatype':datatype,'thread':threading.get_ident()})
   return [self.row(datatype,self.tokens[0])]
  return super().detail(account,account_type,datatype)
def main():
 p=argparse.ArgumentParser();
 for name in ('exe','dll','factory','output'):p.add_argument('--'+name,type=Path,required=True)
 p.add_argument('--mode',choices=('allow','deny','wait','invalid','legacy','event','missing'),required=True);args=p.parse_args()
 args.output.mkdir();(args.output/'owners').mkdir();end=uptime_ms()+55000;fixture=Fixture(args.output,end,args.mode);owners=_FixtureOwners();report=None
 def persist():
  write_new(args.output/'fixture.json',fixture.facts(),end)
  write_new(args.output/'POSTFLIGHT.json',{'child_reaped':bool(fixture.child and fixture.child.reaped),'child_forced':bool(fixture.child and fixture.child.forced),'server_joined':fixture.server_joined,'proxy_joined':bool(fixture.proxy and fixture.proxy.joined),'host_closed':bool(fixture.host and fixture.host._closed_complete and fixture.host._io_resources_closed),'source_closed':bool(fixture.agent and fixture.agent._io_resources_closed)},end)
 with owners:
  owners.callback(persist);fixture.start(owners);trader=fixture.trader();trader['module']='TraderQMTStandard'
  value={'work':str(args.output/'runtime'),'candidate_dll':str(args.dll),'execution_factory':str(args.factory),'hmac_secret':fixture.secret,'trader':trader,'mode':args.mode,'proof':str(fixture.proof),'deadline_uptime_ms':end}
  write_new(args.output/'input.json',value,end);fixture.child=_Child(fixture.total_deadline);owners.callback(fixture.child.close)
  fixture.child.start(args.exe,args.output/'input.json',args.output/'native-result.json',fixture.work_deadline)
  fixture.pump_until(lambda:fixture.child.job.poll() is not None and fixture.child.job.active_processes()==0);fixture.child.close()
  if (args.output/'native-result.json').is_file():report=decode((args.output/'native-result.json').read_bytes())
  assert fixture.child.exit_code==0 and report and report['passed'],{'exit':fixture.child.exit_code,'native':report}
  assert len(fixture.sdk)==(1 if args.mode in ('allow','legacy','event') else 0)
  if args.mode in ('allow','event'):
   events=report['events'];prepared=next(e['data'] for e in events if e['kind']==7);fill=next(e['data'] for e in events if e['kind']==8)
   assert fill['command_id']==prepared['command_id'] and fill['user_tag']==prepared['user_tag'] and fill['quantity']==20
  assert fixture.first.facts() is None and fixture.proxy.first.facts() is None
 assert not owners.failures and fixture.child.reaped and not fixture.child.forced
 assert fixture.host._closed_complete and fixture.host._io_resources_closed and fixture.agent._io_resources_closed and fixture.server_joined and fixture.proxy.joined
 result={'passed':True,'mode':args.mode,'sdk_calls':len(fixture.sdk),'real_broker_calls':0,'full_hook_events':len(report['events']),'closed':True,'inputs':{k:hashlib.sha256(getattr(args,k).read_bytes()).hexdigest() for k in ('exe','dll','factory')}}
 write_new(args.output/'RESULT.json',result,end);print(json.dumps(result))
if __name__=='__main__':main()
