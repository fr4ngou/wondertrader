// 真实WT宿主/执行器/订单表与标准QMT插件；仅外部SDK为明确替身。
#define wmain standard_fixture_unused_main
#include "standard_probe.cpp"
#undef wmain
#include "GuanhengExecution/StandardExecutionHost.h"
#include "GuanhengExecution/ExecutionEnvironment.h"
#include "WtCore/WtExecuterFactory.h"
#include "WtCore/WtExecMgr.h"
#include "Share/TimeUtils.hpp"
struct HostOrderRelease {void operator()(wtp::OrderMap* p)const{if(p)p->release();}};

int wmain(int argc,wchar_t** argv){
 if(argc!=5||std::wstring(argv[1])!=L"--config"||std::wstring(argv[3])!=L"--output")return 2;
 const auto output=fs::absolute(argv[4]);rapidjson::Document report(rapidjson::kObjectType);auto& a=report.GetAllocator();
 Exports exports;WTSBaseDataMgr base;wtp::ActionPolicyMgr policy;wtp::WtExecuterFactory factory;wtp::WtExecuterMgr manager;
 std::unique_ptr<guanheng::ExecutionEnvironment> environment;
 std::unique_ptr<wtp::WTSVariant,VariantRelease> trader,execution;
 std::unique_ptr<guanheng::StandardExecutionHost> host;
 bool passed=false,closed=false;
 try{
  const auto raw=read_config(fs::absolute(argv[2]));rapidjson::Document input;input.Parse(raw.data(),raw.size());check(!input.HasParseError(),"cancel_e2e_input");
  const auto scenario=field(input,"scenario");const bool missing=scenario=="missing-current",partial=scenario=="partial";
  const auto end=Clock::now()+std::chrono::seconds(24);
  const auto work=fs::absolute(fs::u8path(field(input,"work")));check(fs::create_directories(work/"traders"),"cancel_e2e_new_root");fs::current_path(work);
  const auto dll=work/"traders/TraderQMTStandard.dll";check(fs::copy_file(fs::u8path(field(input,"candidate_dll")),dll),"cancel_e2e_plugin");
  check(!_putenv_s("QMT_STANDARD_FIXTURE_KEY","fixture")&&!_putenv_s("QMT_STANDARD_FIXTURE_SECRET",field(input,"hmac_secret").c_str()),"cancel_e2e_auth");
  WtHelper::setTime(20261022,1000);WtHelper::setTDate(20261022);base_files(work,base,policy);exports.load(dll);
  environment.reset(new guanheng::ExecutionEnvironment(base,"DAY",nullptr,[]{return TimeUtils::makeTime(20261022,100000000);}));
  check(fs::create_directory(work/"executers"),"cancel_e2e_factory_root");
  check(fs::copy_file(fs::u8path(field(input,"execution_factory")),work/"executers/WtExeFact.dll"),"cancel_e2e_factory");
  check(factory.loadFactories((work/"executers").string().c_str()),"cancel_e2e_factory_load");
  trader.reset(WTSCfgLoader::load_from_content(encode(input["trader"])));
  execution.reset(WTSCfgLoader::load_from_content(R"({"scale":1,"strict_sync":false,"poolsize":0,"clear":{"active":false},"policy":{"default":{"name":"WtExeFact.WtStockMinImpactBorrowedExeUnit","lots":1000,"min_order":100,"pricemode":0,"offset":0,"expire":1,"span":0,"byrate":false,"is_cancel_unmanaged_order":true,"replace_equal_position_target":true}}})"));
  guanheng::StandardPluginFunctions functions;
  functions.find=exports.get<decltype(functions.find)>("findStandardQmtTrader");functions.pump=exports.get<decltype(functions.pump)>("pumpStandardQmtTrader");
  functions.inspect=exports.get<decltype(functions.inspect)>("inspectStandardQmtTrader");functions.stop=exports.get<decltype(functions.stop)>("stopStandardQmtTrader");functions.destroy=exports.destroy;
  functions.submission={exports.get<guanheng::BeginSubmissionFn>("beginStandardQmtSubmission"),exports.get<guanheng::EndSubmissionFn>("endStandardQmtSubmission"),exports.get<guanheng::InspectSubmissionFn>("inspectStandardQmtSubmission")};
  functions.recovery=exports.get<decltype(functions.recovery)>("inspectStandardQmtRecovery");functions.pause_inserts=exports.get<decltype(functions.pause_inserts)>("pauseStandardQmtInserts");
  host.reset(new guanheng::StandardExecutionHost("cancel_e2e","cancel_e2e_host",base,policy,factory,*environment));
  check(host->initialize(trader.get(),execution.get(),functions,{16,65536,16,10000}),"cancel_e2e_host_init");
  manager.add_executer(host->command());
  auto until=[&](auto condition){while(!condition()){check(Clock::now()<end,"cancel_e2e_deadline");check(host->pump(64,16)>=0,"cancel_e2e_pump");Sleep(2);}};
  until([&]{return host->status().phase==guanheng::ExecutionHostPhase::Ready;});
  const char* code="SZSE.STK.000001";wtp::wt_hashmap<std::string,double> targets;targets[code]=1100;manager.set_positions(targets);
  unsigned ticks=0;auto tick=[&]{wtp::WTSTickStruct v={};std::strcpy(v.code,code);std::strcpy(v.exchg,"SZSE");v.price=10.01;v.action_date=v.trading_date=20261022;v.action_time=100000000+(++ticks)*1000;auto* t=wtp::WTSTickData::create(v);manager.handle_tick(code,t);t->release();};
  tick();until([&]{return host->status().plugin.inserts==1&&host->undone(code)>0;});
  check(host->pause_inserts(true),"cancel_e2e_pause_insert_only");const auto prior=host->broker_observation();
  Sleep(1100);tick(); // 原执行器在新tick中检查超时，真正走cancel/SHM。
  guanheng::StandardQmtRecoveryV1 recovered;
  // 查询序号变化还不足以证明冻结资金释放；等待券商替身返回实际可用现金。
  // account[3]为BrokerQueryAdapter统一发布的CNY可用资金。
  const double expected_cash=partial?97998.:100000.;
  until([&]{const auto b=host->broker_observation();check(host->recovery(recovered)==0,"cancel_e2e_recovery_read");
   return b.position_revision>prior.position_revision&&b.account_revision>prior.account_revision
    &&b.account_known&&std::abs(b.account[3]-expected_cash)<0.000001
    &&host->undone(code)==0&&(missing||recovered.unresolved_children==0);});
  const auto observed=host->broker_observation();check(host->status().phase==guanheng::ExecutionHostPhase::Ready&&host->status().plugin.error==0,"cancel_e2e_channel_survives");
  check(host->position(code)==(partial?300:100),"cancel_e2e_broker_position");
  std::unique_ptr<wtp::OrderMap,HostOrderRelease> orders(host->orders(code));check(orders&&orders->size()==0,"cancel_e2e_original_order_table");
  if(missing){check(recovered.unresolved_children>0&&host->status().plugin.inserts==1,"cancel_e2e_missing_not_fake_terminal");}
  else {check(host->pause_inserts(false),"cancel_e2e_resume_original_execution");tick();until([&]{return host->status().plugin.inserts==2;});}
  report.AddMember("queries",host->status().plugin.queries,a);report.AddMember("inserts",host->status().plugin.inserts,a);
  report.AddMember("broker_position",host->position(code),a);report.AddMember("original_order_terminal",!missing,a);
  report.AddMember("unresolved_original_children",recovered.unresolved_children,a);report.AddMember("channel_ready",true,a);
  report.AddMember("position_revision",observed.position_revision,a);report.AddMember("account_revision",observed.account_revision,a);
  report.AddMember("available_cash_after_cancel",observed.account[3],a);
  report.AddMember("business_strategy_qualified",false,a);report.AddMember("real_broker_calls",0,a);passed=true;
 }catch(const std::exception& e){text(report,"primary",std::string(e.what()).substr(0,256),a);}
 if(host){host->request_stop();closed=host->close()==0;if(closed)host.reset();}
 report.AddMember("passed",passed&&closed,a);report.AddMember("closed",closed,a);write_new(output,encode(report));
 if(!closed)ExitProcess(3);return passed&&closed?0:1;
}
