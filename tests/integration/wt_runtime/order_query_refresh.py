"""编译实际Standard查询调度，验证原队列O/P/A、后到触发及读取恢复。"""
from pathlib import Path
import argparse
import json
import shutil
import sys

repo = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(repo / 'scripts'))
import native

parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--toolchain', type=Path, required=True)
args = parser.parse_args()
out = args.output.resolve()
out.mkdir(parents=True, exist_ok=False)
source = (repo / 'src/TraderQMT/StandardQmtTrader.cpp').read_text(encoding='utf-8')
start = source.index(' void request_order_refresh(){')
methods = source[start:source.index('\n void forget(', start)]
fixture = r'''
#include <algorithm>
#include <chrono>
#include <condition_variable>
#include <cstdint>
#include <deque>
#include <iostream>
#include <map>
#include <mutex>
#include <stdexcept>
#include <vector>
using Clock=std::chrono::steady_clock;
void need(bool ok,const char* why){if(!ok)throw std::runtime_error(why);}
struct Probe {
 enum class Kind {Query};
 struct Task {Kind kind=Kind::Query;unsigned stage=0;Clock::time_point deadline{};
  std::uint64_t id=0,generation=0,read_generation=0;bool resume_read=false;int original_read=0;std::size_t charge=0;};
 struct Held {bool inflight=false;unsigned stage=0;std::uint64_t generation=0;int receipt=0;std::size_t charge=0;};
 struct Identity {unsigned group_id=0;};
 std::mutex mutex;std::condition_variable cv;
 bool query_first=true,events_enabled=true,stop_requested=false,submissions_closed=false;
 bool read_waiting=false,logged_in=true,hard_fault=false;void* spi=this;unsigned query_flow_mask=15;
 unsigned observation_refresh_ms=30000,observation_refresh_stage=3,event_poll_ms=100,active_orders=0;
 std::uint64_t observation_refresh_task=0,next_id=0,generation=1;bool observation_orders_requested=false,observation_order_cycle=false;
 Clock::time_point observation_refresh_at{};
 std::map<unsigned,Identity>identities;std::map<std::uint64_t,Held>held_reads;std::deque<Task>queue;bool reject=false;
 bool active()const{return true;}Clock::time_point deadline(){return Clock::now()+std::chrono::seconds(5);}
 int enqueue(Task&& t,bool,std::uint64_t* id){if(reject)return -1;t.id=++next_id;*id=t.id;queue.push_back(t);return 0;}
 void queue_task(Task&& t){queue.push_back(t);}
 // METHODS
 unsigned step(){schedule_observation_refresh();need(queue.size()==1,"missing or duplicate query");auto t=queue.front();queue.pop_front();observation_refresh_applied(t.id);return t.stage;}
 void due(){observation_refresh_at=Clock::time_point::min();}
 void expect(std::initializer_list<unsigned> stages){for(auto s:stages)need(step()==s,"query order changed");}
 void idle(){schedule_observation_refresh();need(queue.empty(),"unexpected immediate query");}
};
int main(){try{
 {Probe p;p.expect({3,0,2});p.idle();need(!p.observation_order_cycle,"ordinary refresh leaked cycle");}
 {Probe p;p.active_orders=1;p.expect({1,0,2,3});p.idle();p.due();need(p.step()==1,"active order not refreshed");}
 {Probe p;p.observation_refresh_ms=0;p.idle();for(unsigned i=0;i<8;++i)p.request_order_refresh();p.expect({1,0,3});p.idle();need(p.next_id==3,"duplicate trigger created extra cycle");}
 {Probe p;p.request_order_refresh();p.schedule_observation_refresh();auto old=p.queue.front();p.queue.pop_front();
  p.request_order_refresh();p.observation_refresh_applied(old.id);p.expect({0,2,3,1,0,2,3});p.idle();}
 {Probe p;p.request_order_refresh();p.reject=true;p.schedule_observation_refresh();need(p.queue.empty()&&p.observation_orders_requested,"failed enqueue consumed request");p.reject=false;p.due();p.expect({1,0,2,3});}
 {Probe p;p.active_orders=1;p.expect({1,0,2,3});p.active_orders=0;p.due();p.expect({3,0,2});p.idle();}
 {Probe p;p.identities[7].group_id=8;p.expect({1,0,2,3});need(p.identities[7].group_id==8,"missing order falsely retired identity");p.due();need(p.step()==1,"unknown old order lost followup");}
 {Probe p;p.read_waiting=true;p.query_flow_mask=0;p.request_order_refresh();p.expect({3,1,2,0});need(!p.read_waiting,"read recovery not completed");p.query_flow_mask=15;p.expect({1,0,2,3});}
 {Probe p;p.read_waiting=true;p.held_reads[42]={false,1,17,99,123};p.schedule_observation_refresh();need(p.queue.size()==1&&p.queue.front().id==42&&p.queue.front().resume_read&&p.queue.front().original_read==99&&p.next_id==0,"held read identity changed");}
 {Probe p;p.query_first=false;p.request_order_refresh();p.expect({3,0,2});p.idle();need(!p.observation_orders_requested,"native mode acquired new behavior");}
 std::cout<<"Actual Standard query scheduler: 10 scenarios PASS\n";
 }catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
'''.replace('// METHODS', methods)
cpp = out / 'probe.cpp'
cpp.write_text(fixture, encoding='utf-8')
env = json.loads(args.toolchain.read_bytes())['environment']
compiler = shutil.which('cl.exe', path=env['PATH'])
exe = out / 'probe.exe'
native.run([compiler, '/nologo', '/std:c++17', '/EHsc', '/MD', '/utf-8', cpp,
            '/Fe:' + str(exe), '/Fo:' + str(out / 'probe.obj')],
           cwd=out, env=env, timeout=60, log=out / 'compile.log', private_console=True)
native.run([exe], cwd=out, env=env, timeout=10, log=out / 'run.log', private_console=True)
(out / 'RESULT.json').write_text(json.dumps({'passed': True, 'real_orders': 0,
    'scope': 'actual Standard query scheduling methods, enqueue/completion spy'}, indent=2), encoding='utf-8')
