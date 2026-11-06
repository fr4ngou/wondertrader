"""编译真实Standard的error分支，验证券商业务诊断沿原SPI通知且保持通道可用。"""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import sys

repo = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(repo / 'scripts'))
import native

parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--source', type=Path, default=repo / 'src/TraderQMT/StandardQmtTrader.cpp')
args = parser.parse_args()
out = args.output.resolve()
out.mkdir(parents=True, exist_ok=False)
source = args.source.read_text(encoding='utf-8')
start = source.index('  if(kind=="error"){', source.index(' void begin_event('))
end = source.index('\n  if(event_control.stop_requested()', start)
branch = source[start:end]
fixture = r'''
#include <cstdint>
#include <memory>
#include <stdexcept>
#include <string>
#include <iostream>
#include "rapidjson/document.h"
#include "rapidjson/writer.h"
#include "rapidjson/stringbuffer.h"
enum class ErrorCode {Ok,IoError};
struct Status {ErrorCode code=ErrorCode::Ok;std::string reason;};
struct QmtEventDeliveryObservation {std::uint64_t sequence=0;bool diagnostic=false;std::string derived_event_sha256;};
namespace wtp {
enum {WEC_UNKNOWN};
struct WTSError {std::string message;static WTSError* create(int,const char* m){return new WTSError{m};}};
}
struct ObjectRelease {void operator()(wtp::WTSError* p)const{delete p;}};
namespace qmt_host_codec {std::string encode(const rapidjson::Value& e){rapidjson::StringBuffer b;rapidjson::Writer<rapidjson::StringBuffer>w(b);e.Accept(w);return b.GetString();}}
std::string signed_http_sha256(const std::string&){return std::string(64,'a');}
void require(bool condition,const char* reason){if(!condition)throw std::runtime_error(reason);}
struct Sink {
 unsigned errors=0;bool throws=false;
 void onTraderError(wtp::WTSError* e){require(e&&!e->message.empty(),"missing diagnostic");++errors;if(throws)throw std::runtime_error("SPI failure");}
};
struct Probe {
 Sink sink;Sink* spi=&sink;Status first_error;unsigned handled=0;int original_order_remaining=1000;
 struct Chain {int deadline=0;}chain;
 void note(const Status& s){if(first_error.code==ErrorCode::Ok)first_error=s;}
 template<class F>void deliver_event(const QmtEventDeliveryObservation& o,int,F&& f){require(o.diagnostic&&o.sequence>0,"not original diagnostic");f();++handled;}
 void run(const rapidjson::Value& event){std::string kind=event["kind"].GetString();
 // BRANCH
 }
};
int main(){try{
 for(int operation:{-1,23}){
  rapidjson::Document event;event.Parse("{\"sequence\":158,\"kind\":\"error\",\"payload\":{\"err_msg\":\"broker rejected operation\",\"order_args\":{\"opType\":-1}}}");
  event["payload"]["order_args"]["opType"].SetInt(operation);
  Probe p;p.run(event);
  require(p.first_error.code==ErrorCode::Ok,"business error poisoned channel");
  require(p.sink.errors==1&&p.handled==1&&p.original_order_remaining==1000,"notification changed order or event not handled");
  p.note({ErrorCode::IoError,"real transport failure"});p.run(event);
  require(p.first_error.reason=="real transport failure","business diagnostic replaced existing transport cause");
  Probe failing;failing.sink.throws=true;bool propagated=false;try{failing.run(event);}catch(...){propagated=true;}
  require(propagated&&failing.handled==0,"SPI exception falsely acknowledged");
 }
 std::cout<<"Original error branch: cancel/insert diagnostics, retained order, original transport cause, SPI exception PASS\n";
 }catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}
}
'''.replace('// BRANCH', branch)
cpp = out / 'probe.cpp'
cpp.write_text(fixture, encoding='utf-8')
toolchain = json.loads((repo / 'build/wo2/TOOLCHAIN.json').read_bytes())
env = toolchain['environment']
compiler = shutil.which('cl.exe', path=env['PATH'])
exe = out / 'probe.exe'
native.run([compiler, '/nologo', '/std:c++17', '/EHsc', '/MD', '/utf-8',
            '/I' + str(repo / 'build/wo2/deps/rapidjson/include'), cpp,
            '/Fe:' + str(exe), '/Fo:' + str(out / 'probe.obj')],
           cwd=out, env=env, timeout=60, log=out / 'compile.log', private_console=True)
native.run([exe], cwd=out, env=env, timeout=10, log=out / 'run.log', private_console=True)
(out / 'RESULT.json').write_text(json.dumps({'passed': True,
    'scope': 'actual StandardQmtTrader begin_event error branch; SPI spy',
    'source_sha256': hashlib.sha256(args.source.read_bytes()).hexdigest(),
    'real_orders': 0, 'real_cancels': 0}, indent=2), encoding='utf-8')
