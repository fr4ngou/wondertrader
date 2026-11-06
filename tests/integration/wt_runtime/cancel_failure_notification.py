"""编译实际写失败通知入口，区分已确认撤单拒绝、真实未知与运输失败。"""
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
parser.add_argument('--toolchain', type=Path, required=True)
args = parser.parse_args()
out = args.output.resolve()
out.mkdir(parents=True, exist_ok=False)
source_path = repo / 'src/TraderQMT/StandardQmtTrader.cpp'
source = source_path.read_text(encoding='utf-8')
start = source.index(' void publish_write_failure(')
method = source[start:source.index('\n void retire_candidates(', start)]
classification_start = source.index('  const bool terminal=result.trade.phase==')
classification = source[classification_start:source.index('\n }\n // 只读重取许可', classification_start)]
fixture = r'''
#include <memory>
#include <stdexcept>
#include <string>
#include <iostream>
#include "rapidjson/document.h"
enum class ErrorCode {Ok,Unavailable,SubmissionUnknown,IoError,Conflict};
struct Status {ErrorCode code=ErrorCode::Ok;std::string reason;bool ok()const{return code==ErrorCode::Ok;}};
Status failure(ErrorCode c,const char* m){return {c,m};}
enum class QmtTradePhase {Unknown,SdkReturned,DefinitelyNotCalled,NotSent};
enum class PendingRole {OriginalCall,UnadmittedTargetLookup};
enum class Kind {Insert,Cancel};
struct Order {struct Insert {std::string entrust_id="original";}insert;};
struct Completion {Kind kind=Kind::Cancel;bool business_rejected=true,insert_failure_confirmed=true;
 struct Trade {QmtTradePhase phase=QmtTradePhase::DefinitelyNotCalled;Status status;std::string source_result_json;}trade;
 struct Audit {PendingRole role=PendingRole::OriginalCall;}audit;
 Status status{ErrorCode::Unavailable,"confirmed business rejection"};Order order;};
namespace wtp {enum WTSErroCode {WEC_UNKNOWN,WEC_ORDERCANCEL};
struct WTSError {WTSErroCode code;static WTSError* create(WTSErroCode c,const char*){return new WTSError{c};}};}
struct ObjectRelease {void operator()(wtp::WTSError* p)const{delete p;}};
void require(bool ok,const char* why){if(!ok)throw std::runtime_error(why);}
bool parse_bounded_qmt_json(const std::string& json,rapidjson::Document& d,unsigned,unsigned){d.Parse(json.c_str());return !d.HasParseError();}
namespace qmt_host_codec {std::string text(const rapidjson::Value& v){return v.GetString();}}
struct Sink {unsigned notifications=0;wtp::WTSErroCode last=wtp::WEC_UNKNOWN;bool throws=false;
 void onTraderError(wtp::WTSError* e){++notifications;last=e->code;if(throws)throw std::runtime_error("SPI failure");}};
struct Probe {
 Sink sink;Sink* spi=&sink;bool query_first=true,hard_fault=false,unknown=false,forgotten=false;
 unsigned refresh=0,entrust_rejections=0;Status first_error;int original_remaining=1000;
 void request_order_refresh(){++refresh;}
 void forget(const std::string&){forgotten=true;}
 void entrust_reply(const Order&,const Status&,bool rejected){entrust_rejections+=rejected;}
 void note(const Status& s){if(first_error.ok())first_error=s;}
 void block(const Status& s){hard_fault=true;note(s);}
 void fence_unknown(){unknown=true;}
 template<class F>void callback(F&& f){f();}
 void trader_error(const Status& s,wtp::WTSErroCode c){note(s);wtp::WTSError error{c};spi->onTraderError(&error);}
 void classify(Completion& result){const auto& task=result;result.status=result.trade.status;
 // CLASSIFICATION
 }
 // METHOD
};
int main(){try{
 for(bool late:{false,true})for(auto phase:{QmtTradePhase::DefinitelyNotCalled,QmtTradePhase::SdkReturned}){
  Probe p;Completion c;c.trade.phase=phase;c.insert_failure_confirmed=phase==QmtTradePhase::DefinitelyNotCalled;
  p.publish_write_failure(c,c.status,late);
  require(p.refresh==1&&p.sink.notifications==1&&p.sink.last==wtp::WEC_ORDERCANCEL,"cancel rejection not queried/notified");
  require(p.first_error.ok()&&!p.hard_fault&&!p.unknown&&!p.forgotten&&p.original_remaining==1000,"cancel rejection changed original order/channel");
 }
 {Probe p;Completion c;c.business_rejected=false;c.insert_failure_confirmed=false;c.trade.phase=QmtTradePhase::Unknown;c.status={ErrorCode::SubmissionUnknown,"real unknown"};
  p.publish_write_failure(c,c.status,false);require(p.unknown&&!p.first_error.ok()&&!p.forgotten&&p.refresh==0,"unknown cancellation falsely resolved");}
 {Probe p;Completion c;c.business_rejected=false;c.insert_failure_confirmed=false;c.status={ErrorCode::IoError,"real transport failure"};
  p.publish_write_failure(c,c.status,false);require(p.hard_fault&&p.first_error.code==ErrorCode::IoError&&p.refresh==0,"transport failure swallowed");}
 {Probe p;Completion c;c.kind=Kind::Insert;p.publish_write_failure(c,c.status,false);
  require(p.forgotten&&p.entrust_rejections==1&&p.first_error.ok()&&p.refresh==0,"insert rejection behavior changed");}
 {Probe p;Completion c;p.query_first=false;p.publish_write_failure(c,c.status,false);
  require(!p.first_error.ok()&&p.sink.notifications==1&&p.refresh==0,"native mode behavior changed");}
 for(auto phase:{QmtTradePhase::DefinitelyNotCalled,QmtTradePhase::SdkReturned,QmtTradePhase::Unknown}){
  Probe p;Completion c;c.business_rejected=false;c.insert_failure_confirmed=false;c.trade.phase=phase;
  c.trade.source_result_json="{\"signal_sent\":false,\"error_code\":\"confirmed\"}";
  p.classify(c);p.publish_write_failure(c,c.status,false);
  if(phase==QmtTradePhase::Unknown)require(p.unknown&&p.refresh==0&&!p.first_error.ok(),"SDK unknown entered business rejection branch");
  else require(c.business_rejected&&p.refresh==1&&p.first_error.ok()&&!p.forgotten,"actual SDK classification did not notify and refresh");
 }
 {Probe p;Completion c;c.business_rejected=false;c.status={ErrorCode::Conflict,"identity conflict"};
  p.publish_write_failure(c,c.status,false);require(p.hard_fault&&p.first_error.code==ErrorCode::Conflict&&p.refresh==0,"identity conflict swallowed");}
 {Probe p;Completion c;p.first_error={ErrorCode::IoError,"earlier transport failure"};p.publish_write_failure(c,c.status,false);
  require(p.first_error.reason=="earlier transport failure"&&!p.forgotten,"earlier fault cleared");}
 {Probe p;Completion c;p.sink.throws=true;bool thrown=false;try{p.publish_write_failure(c,c.status,false);}catch(...){thrown=true;}
  require(thrown&&!p.forgotten&&p.original_remaining==1000,"SPI exception hidden or order changed");}
 std::cout<<"Actual cancellation classification and notification: 14 scenarios PASS\n";
 }catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
'''.replace('// METHOD', method).replace('// CLASSIFICATION', classification)
cpp = out / 'probe.cpp'
cpp.write_text(fixture, encoding='utf-8')
env = json.loads(args.toolchain.read_bytes())['environment']
compiler = shutil.which('cl.exe', path=env['PATH'])
exe = out / 'probe.exe'
native.run([compiler, '/nologo', '/std:c++17', '/EHsc', '/MD', '/utf-8',
            '/I' + str(args.toolchain.parent / 'deps/rapidjson/include'), cpp,
            '/Fe:' + str(exe), '/Fo:' + str(out / 'probe.obj')],
           cwd=out, env=env, timeout=60, log=out / 'compile.log', private_console=True)
native.run([exe], cwd=out, env=env, timeout=10, log=out / 'run.log', private_console=True)
(out / 'RESULT.json').write_text(json.dumps({'passed': True, 'real_orders': 0,
    'source_sha256': hashlib.sha256(source_path.read_bytes()).hexdigest(),
    'scope': 'actual Standard publish_write_failure, WT notification spy'}, indent=2), encoding='utf-8')
