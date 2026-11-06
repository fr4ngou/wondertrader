"""编译实际自有恢复入口：保留普通挂单，未知责任及O/P/A屏障维持。"""
from pathlib import Path
import hashlib,json,re,shutil,sys
repo=Path(__file__).resolve().parents[3];sys.path.insert(0,str(repo/'scripts'));import native
import argparse
parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
q=args.output.resolve();assert not q.exists();q.mkdir(parents=True)
cpp=(repo/'src/GuanhengExecution/CtaProcess.cpp').read_text(encoding='utf-8');header=(repo/'src/TraderQMT/StandardQmtTrader.h').read_text(encoding='utf-8')
state=re.search(r'struct StandardQmtRecoveryV1\s*\{.*?\n\};',header,re.S).group()
predicates=cpp[cpp.index('bool known_orders_recoverable('):cpp.index('// 自有持续Reader',cpp.index('bool known_orders_recoverable('))]
helpers=cpp[cpp.index('bool own_orders_empty('):cpp.index('void bootstrap_takeover(')]
fixture=r'''
#include <cstdint>
#include <map>
#include <stdexcept>
#include <string>
#include <iostream>
namespace wtp {
struct WTSOrderInfo {bool missing=false;bool isAlive()const{return true;}const char* getEntrustID()const{return missing?"":"original";}const char* getUserTag()const{return "original-tag";}};
struct OrderMap:std::map<std::uint32_t,void*>{void release(){}};
}
namespace guanheng {
// STATE
struct StandardExecutionHost {
 StandardQmtRecoveryV1 state;wtp::WTSOrderInfo row;wtp::OrderMap rows;std::string scenario,waiting;
 unsigned steps=0,cancels=0,working=0,account_steps=0;std::uint64_t task=0;
 StandardExecutionHost(std::string name):scenario(name){state.query_first=1;state.next_task=100;
  rows[1]=&row;rows[2]=&row;state.active_orders=2;
  if(name=="active"||name=="partial"){state.unresolved_children=2;working=2;}
  if(name=="unknown"){state.unresolved_children=1;state.unsafe=1;}
  if(name=="unobserved")state.unresolved_children=1;
  row.missing=name=="missing";
 }
 int recovery(StandardQmtRecoveryV1& out){out=state;return 0;}
 int known_working_children(std::uint32_t& out){out=working;return 0;}
 wtp::OrderMap* orders(const char*){return &rows;}
 int query_orders(){waiting="O";task=++state.next_task;return 0;}
 int query_positions(){waiting="P";task=++state.next_task;return 0;}
 int query_account(){waiting="A";task=++state.next_task;return 0;}
 void advance(){++steps;if(waiting=="O")state.last_order_query=task;
  if(waiting=="P")state.last_position_query=task;
  if(waiting=="A"){++account_steps;state.last_account_query=(scenario=="old_account"&&account_steps==1)?42:task;}
 }
};}
void need(bool value){if(!value)throw std::runtime_error("guard");}
// PREDICATES
// HELPERS
int main(){unsigned passed=0;
 for(const char* name:{"active","partial","restarted","unknown","unobserved","missing","old_account"}){
  guanheng::StandardExecutionHost host(name);bool completed=false;
  auto check=[&]{if(host.steps>12)throw std::runtime_error("test deadline");};
  try{reconcile_own_orders(host,check,[&]{host.advance();});completed=true;}catch(const std::runtime_error&){}
  const bool rejected=host.scenario=="unknown"||host.scenario=="unobserved"||host.scenario=="missing";
  bool ok=completed!=rejected&&host.cancels==0&&host.rows.size()==2;
  if(!rejected){host.state.submissions_closed=1;ok=ok&&settled(host,host.state);}
  if(host.scenario=="old_account")ok=ok&&host.account_steps==2;
  std::cout<<name<<" "<<(ok?"PASS":"FAIL")<<"\n";passed+=ok;
 }
 return passed==7?0:1;
}
'''
fixture=fixture.replace('// STATE',state).replace('// PREDICATES',predicates).replace('// HELPERS',helpers)
source=q/'probe.cpp';source.write_text(fixture,encoding='utf-8');exe=q/'probe.exe'
env,unused=native.environment(q);compiler=shutil.which('cl.exe',path=env['PATH'])
native.run([compiler,'/nologo','/std:c++17','/EHsc','/MD','/utf-8',source,'/Fe:'+str(exe),'/Fo:'+str(q/'probe.obj')],
 cwd=q,env=env,timeout=60,log=q/'compile.log',private_console=True)
native.run([exe],cwd=q,env=env,timeout=10,log=q/'run.log',private_console=True)
(q/'RESULT.json').write_text(json.dumps({'passed':True,'scope':'actual CtaProcess recovery helpers; original-order retention and unknown rejection',
 'source_sha256':hashlib.sha256((repo/'src/GuanhengExecution/CtaProcess.cpp').read_bytes()).hexdigest(),'real_orders':0},indent=2),encoding='utf-8')
