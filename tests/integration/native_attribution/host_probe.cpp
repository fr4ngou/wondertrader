// 真实StandardHost/WT股票单元/原SDK替身的归属时序；无真实账户或交易。
#define wmain standard_helper_unused_main
#include "../qmt_standard_trader/standard_probe.cpp"
#undef wmain
#include "GuanhengExecution/StandardExecutionHost.h"
#include "GuanhengExecution/ExecutionEnvironment.h"
#include "WtCore/WtExecuterFactory.h"
#include "Share/TimeUtils.hpp"
#include <mutex>
namespace {
struct Hook {
 std::mutex mutex;std::vector<std::pair<unsigned,std::string>> events;
 std::string mode;fs::path proof;unsigned authorize=0,groups=0,children=0,prepared=0,fills=0,orders=0;
 static int __cdecl call(const GhAttributionEventV1* event,GhAttributionReplyV1* reply,void* user){
  try{
   auto& h=*static_cast<Hook*>(user);check(event&&reply&&event->size==sizeof(*event)&&event->version==1
    &&event->reserved==0&&event->json_bytes<=2*1024*1024,"hook_layout");
   const std::string raw(event->json_utf8,event->json_bytes);rapidjson::Document value;value.Parse(raw.data(),raw.size());
   check(!value.HasParseError()&&value.IsObject(),"hook_complete_json");
   {std::lock_guard<std::mutex> lock(h.mutex);h.events.push_back({event->kind,raw});}
   if(event->kind==GH_ATTR_AUTHORIZE){
    check(event->thread_role==2&&field(value,"limit_price_cny")=="10.01","authorize_actual_price");++h.authorize;
    reply->decision=h.mode=="wait"?1:0;reply->authorized_quantity=h.mode=="wait"?0:h.mode=="invalid"?150:100;return 0;
   }
   if(event->kind==GH_ATTR_GROUP){++h.groups;check(value["quantity"].GetDouble()==100,"group_clipped_quantity");}
   if(event->kind==GH_ATTR_WT_CHILD){++h.children;check(value["quantity"].GetUint64()==100&&event->thread_role==2,"child_clipped_quantity");}
   if(event->kind==GH_ATTR_PREPARED){
    ++h.prepared;check(event->thread_role==3&&value["quantity"].GetUint64()==100
     &&field(value,"command_id").size()==36&&field(value,"command_sha256").size()==64,"prepared_original_identity");
    check(h.prepared==1,"prepared_never_recreated");write_new(h.proof,raw);
    if(h.mode=="deny")return -1;
   }
   if(event->kind==GH_ATTR_INSERT_RESULT){
    check(field(value,"command_id").size()==36&&field(value,"command_sha256").size()==64,"result_original_identity");
    if(h.mode=="deny")check(value["dispatch_not_entered"].GetBool()&&value["filled_quantity"].GetUint64()==0
     &&field(value,"phase_name")=="NotSent"&&value["source_sha256"].IsNull(),"local_known_not_sent_no_fake_source");
    else check(!value["dispatch_not_entered"].GetBool()&&value["filled_quantity"].IsNull()
     &&field(value,"phase_name")=="SdkReturned"&&field(value,"source_sha256").size()==64,"SDK_return_is_not_order_terminal");
   }
   if(event->kind==GH_ATTR_FILL){++h.fills;check(field(value,"trade_id").find("nqh1.")==0
    &&value["quantity"].GetDouble()==20&&field(value,"source_sha256").size()==64
    &&field(value,"command_id").size()==36&&value["fee_cny"].IsNull(),"fill_original_identity");}
   if(event->kind==GH_ATTR_ORDER){++h.orders;check(field(value,"source_sha256").size()==64,"order_source_identity");}
   reply->decision=0;reply->authorized_quantity=0;return 0;
  }catch(...){return -1;}
 }
};
}
int wmain(int argc,wchar_t** argv){
 if(argc!=5)return 2;const auto output=fs::absolute(argv[4]);rapidjson::Document report(rapidjson::kObjectType);auto& a=report.GetAllocator();
 Exports exports;WTSBaseDataMgr base;wtp::ActionPolicyMgr policy;wtp::WtExecuterFactory factory;
 std::unique_ptr<guanheng::ExecutionEnvironment> environment;std::unique_ptr<wtp::WTSVariant,VariantRelease> trader,executer;
 std::unique_ptr<guanheng::StandardExecutionHost> host;Hook hooks;bool passed=false,closed=false,deleted=false;
 auto end=Clock::now()+std::chrono::seconds(25);
 try{
  const auto raw=read_config(fs::absolute(argv[2]));rapidjson::Document input;input.Parse(raw.data(),raw.size());check(!input.HasParseError(),"input");
  hooks.mode=field(input,"mode");hooks.proof=fs::absolute(fs::u8path(field(input,"proof")));
  const auto now=GetTickCount64(),deadline=input["deadline_uptime_ms"].GetUint64();check(deadline>now+6000,"original_D");
  end=Clock::now()+std::chrono::milliseconds((std::min<uint64_t>)(30000,deadline-now-6000));
  const auto work=fs::absolute(fs::u8path(field(input,"work")));check(fs::create_directories(work/"traders"),"new_root");fs::current_path(work);
  const auto dll=work/"traders/TraderQMTStandard.dll";check(fs::copy_file(fs::u8path(field(input,"candidate_dll")),dll),"copy_plugin");
  check(!_putenv_s("QMT_STANDARD_FIXTURE_KEY","fixture")&&!_putenv_s("QMT_STANDARD_FIXTURE_SECRET",field(input,"hmac_secret").c_str()),"credentials");
  WtHelper::setTime(20261022,1000);WtHelper::setTDate(20261022);base_files(work,base,policy);exports.load(dll);
  environment.reset(new guanheng::ExecutionEnvironment(base,"DAY",nullptr,[]{return TimeUtils::makeTime(20261022,100000000);}));
  check(fs::create_directory(work/"executers"),"factory_root");check(fs::copy_file(fs::u8path(field(input,"execution_factory")),work/"executers/WtExeFact.dll"),"original_factory");
  check(factory.loadFactories((work/"executers").string().c_str()),"load_factory");trader.reset(WTSCfgLoader::load_from_content(encode(input["trader"])));
  executer.reset(WTSCfgLoader::load_from_content(R"({"scale":1,"strict_sync":false,"poolsize":0,"clear":{"active":false},"policy":{"default":{"name":"WtExeFact.WtStockMinImpactBorrowedExeUnit","lots":1000,"min_order":100,"pricemode":0,"offset":0,"expire":0,"span":0,"byrate":false}}})"));
  guanheng::StandardPluginFunctions functions;functions.find=exports.find;functions.pump=exports.pump;functions.inspect=exports.inspect;functions.stop=exports.stop;functions.destroy=exports.destroy;
  functions.submission={exports.get<guanheng::BeginSubmissionFn>("beginStandardQmtSubmission"),exports.get<guanheng::EndSubmissionFn>("endStandardQmtSubmission"),exports.get<guanheng::InspectSubmissionFn>("inspectStandardQmtSubmission")};
  if(hooks.mode!="legacy"&&hooks.mode!="missing"){
   functions.attribution_version=exports.get<decltype(functions.attribution_version)>("standardQmtAttributionVersion");
   functions.attribution_configure=exports.get<decltype(functions.attribution_configure)>("configureStandardQmtAttribution");
  }
  host.reset(new guanheng::StandardExecutionHost("hooks-owned","hooks-host",base,policy,factory,*environment));
  if(hooks.mode!="legacy")check(host->configure_attribution({Hook::call,&hooks}),"configure_hooks");
  const bool initialized=host->initialize(trader.get(),executer.get(),functions,{16,65536,16,10000});
  if(hooks.mode=="missing"){
   check(!initialized&&functions.find(trader->getCString("instance_id"))==nullptr,"selected_missing_capability_rejected_before_API");
   report.AddMember("inserts",0,a);report.AddMember("pending",0,a);host->request_stop();check(host->close()==0,"missing_close");
   closed=deleted=passed=true;host.reset();
  }else{
  check(initialized,"host_initialize");
  auto pump=[&](bool allow_fault=false){check(Clock::now()<end,"original_deadline");const auto rc=host->pump(64,16);if(!allow_fault)check(rc>=0&&host->status().fault==guanheng::ExecutionHostFault::None,"host_pump");Sleep(2);};
  while(host->status().phase!=guanheng::ExecutionHostPhase::Ready)pump();
  auto command=host->command();const char* code="SZSE.STK.000001";wtp::wt_hashmap<std::string,double> targets;targets[code]=1000;command->set_position(targets);
  for(unsigned n=0;n<3;++n){
   wtp::WTSTickStruct value={};std::strcpy(value.code,code);std::strcpy(value.exchg,"SZSE");value.price=10.01;
   value.action_date=value.trading_date=20261022;value.action_time=100000000+(n+1)*1000;
   auto data=wtp::WTSTickData::create(value);command->on_tick(code,data);data->release();
   const auto until=Clock::now()+std::chrono::milliseconds(100);while(Clock::now()<until)pump(hooks.mode=="deny"||hooks.mode=="invalid");
   if(hooks.mode=="deny"||hooks.mode=="invalid")break;
  }
  if(hooks.mode=="allow"){
   while(host->status().plugin.pending_commands)pump();
   check(host->query_orders()==0,"query_original_order");const auto q=host->status().plugin.queries;while(host->status().plugin.queries<q+1)pump();
   check(host->undone(code)==80,"real_original_undone_is_clipped_child_remainder");
   check(functions.find(trader->getCString("instance_id"))->queryTrades()==0,"query_original_deal");const auto d=host->status().plugin.queries;while(host->status().plugin.queries<d+1)pump();
   check(hooks.fills==1&&hooks.orders==1,"original_source_callbacks");
  }
  if(hooks.mode=="event"){
   while(hooks.fills<1||hooks.orders<1||host->undone(code)!=80)pump();
   check(host->undone(code)==80,"event_original_undone");
  }
  const auto state=host->status();report.AddMember("inserts",state.plugin.inserts,a);report.AddMember("pending",state.plugin.pending_commands,a);
  report.AddMember("undone",host->undone(code),a);text(report,"last_command_id",state.plugin.last_command_id,a);
  if(hooks.mode=="deny")check(hooks.prepared==1&&state.plugin.pending_commands==1&&state.plugin.writes_blocked&&std::strlen(state.plugin.last_command_id)==36,"denied_keeps_original_uuid_receipt");
  if(hooks.mode=="wait"||hooks.mode=="invalid")check(!hooks.groups&&!hooks.children&&!hooks.prepared&&!state.plugin.inserts,"no_group_or_dispatch");
  if(hooks.mode=="allow"||hooks.mode=="event")check(hooks.groups==1&&hooks.children==1&&hooks.prepared==1,"one_original_group_child_prepared");
  host->request_stop();check(host->close()==0,"physical_close");closed=host->status().phase==guanheng::ExecutionHostPhase::Closed;
  deleted=functions.find(trader->getCString("instance_id"))==nullptr;check(closed&&deleted,"deleted_original_api");host.reset();passed=true;
  }
 }catch(const std::exception& error){text(report,"primary",std::string(error.what()).substr(0,200),a);}
 if(host){host->request_stop();closed=host->close()==0;if(closed){deleted=true;host.reset();}}
 rapidjson::Value events(rapidjson::kArrayType);{std::lock_guard<std::mutex> lock(hooks.mutex);for(const auto& row:hooks.events){rapidjson::Value v(rapidjson::kObjectType);v.AddMember("kind",row.first,a);rapidjson::Document value;value.Parse(row.second.data(),row.second.size());v.AddMember("data",rapidjson::Value(value,a),a);events.PushBack(v,a);}}
 report.AddMember("events",events,a);report.AddMember("passed",passed&&closed&&deleted,a);report.AddMember("closed",closed,a);report.AddMember("deleted",deleted,a);report.AddMember("real_broker_calls",0,a);
 write_new(output,encode(report));if(!closed)ExitProcess(3);return passed&&closed&&deleted?0:1;
}
