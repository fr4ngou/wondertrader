// 正式产品宿主主链；仅外部夹具可调用SDK替身，原算法和订单表保持。
#define wmain standard_helper_unused_main
#include "../qmt_standard_trader/standard_probe.cpp"
#undef wmain
#include "GuanhengExecution/StandardExecutionHost.h"
#include "GuanhengExecution/ExecutionEnvironment.h"
#include "WtCore/WtExecMgr.h"
#include "Share/CodeHelper.hpp"
#include "Share/TimeUtils.hpp"
#include "Includes/WTSContractInfo.hpp"
#include "Includes/WTSSessionInfo.hpp"

namespace {
struct HostOrderRelease { void operator()(wtp::OrderMap* v)const{if(v)v->release();} };
}
int wmain(int argc,wchar_t** argv){
    if(argc!=5||std::wstring(argv[1])!=L"--config"||std::wstring(argv[3])!=L"--output")return 2;
    const auto output=fs::absolute(argv[4]);rapidjson::Document report(rapidjson::kObjectType);auto& alloc=report.GetAllocator();
    Exports exports;WTSBaseDataMgr base;wtp::ActionPolicyMgr policy;wtp::WtExecuterFactory factory;std::unique_ptr<guanheng::ExecutionEnvironment> environment;
    std::uint64_t environment_now=TimeUtils::makeTime(20261022,100000000);
    std::unique_ptr<wtp::WTSVariant,VariantRelease> trader,executer;
    std::unique_ptr<guanheng::StandardExecutionHost> host;
    std::shared_ptr<guanheng::OwnerExecCommand> command;wtp::WtExecuterMgr manager;
    bool passed=false,closed=false,deleted=false;
    auto end=Clock::now()+std::chrono::seconds(25);
    try {
        auto raw=read_config(fs::absolute(argv[2]));rapidjson::Document input;input.Parse(raw.data(),raw.size());
        check(!input.HasParseError()&&field(input,"order_context")=="query_first","host_query_config");
        const bool active=input.HasMember("active_order")&&input["active_order"].GetBool();
        auto now=GetTickCount64(),deadline=input["deadline_uptime_ms"].GetUint64();check(deadline>now+6000,"host_original_deadline");
        end=Clock::now()+std::chrono::milliseconds((std::min<uint64_t>)(30000,deadline-now-6000));
        const auto work=fs::absolute(fs::u8path(field(input,"work")));check(fs::create_directories(work/"traders"),"host_new_work");fs::current_path(work);
        const auto installed=work/"traders/TraderQMTStandard.dll";check(fs::copy_file(fs::u8path(field(input,"candidate_dll")),installed),"host_plugin_copy");
        const auto secret=field(input,"hmac_secret");check(!_putenv_s("QMT_STANDARD_FIXTURE_KEY","fixture")&&!_putenv_s("QMT_STANDARD_FIXTURE_SECRET",secret.c_str()),"host_credentials");
        WtHelper::setTime(20261022,1000);WtHelper::setTDate(20261022);base_files(work,base,policy);exports.load(installed);
        {
            guanheng::ExecutionEnvironment live(base,"DAY");const auto before=TimeUtils::getLocalTimeNow();const auto value=live.observe();
            check(value.epoch_ms>=before&&value.epoch_ms<=TimeUtils::getLocalTimeNow(),"host_default_system_clock");
            check(value.trading_day==base.calcTradingDate("DAY",value.date,value.time_ms/100000,true),"host_original_calendar");
            bool unknown_session=false;try{guanheng::ExecutionEnvironment invalid(base,"MISSING");}catch(const std::invalid_argument&){unknown_session=true;}
            check(unknown_session,"host_unknown_session_rejected");
        }
        environment.reset(new guanheng::ExecutionEnvironment(base,"DAY",nullptr,[&]{return environment_now;}));
        check(environment->observe().date==20261022&&environment->observe().time_ms==100000000&&environment->get_trading_day()==20261022,"host_frozen_product_environment");
        check(environment->get_comm_info("SZSE.STK.000001")==base.getCommodity("SZSE","STK")
            &&environment->get_sess_info("SZSE.STK.000001")==base.getSession("DAY"),"host_original_environment_metadata");
        check(!environment->get_comm_info("broken")&&!environment->get_sess_info("SZSE.STK.")
            &&!environment->get_comm_info("SZSE.STK.-")&&!environment->get_comm_info("SZSE.MISSING.000001"),"host_invalid_metadata_rejected");
        environment_now=TimeUtils::makeTime(20261024,100000000);check(environment->get_trading_day()==20261026,"host_original_weekend_rule");
        environment_now=0;bool invalid_clock=false;try{environment->observe();}catch(const std::runtime_error&){invalid_clock=true;}
        check(invalid_clock,"host_invalid_clock_rejected");environment_now=TimeUtils::makeTime(20261022,100000000);
        const auto factories=work/"executers";check(fs::create_directory(factories),"host_factory_directory");
        check(fs::copy_file(fs::u8path(field(input,"execution_factory")),factories/"WtExeFact.dll"),"host_original_factory_copy");
        check(factory.loadFactories(factories.string().c_str()),"host_original_factory_load");
        check(bool(factory.createExeUnit("WtExeFact.WtMinImpactExeUnit")),"host_original_unit_available");
        trader.reset(WTSCfgLoader::load_from_content(encode(input["trader"])));
        executer.reset(WTSCfgLoader::load_from_content(R"({"scale":1,"strict_sync":false,"poolsize":0,"clear":{"active":false},"policy":{"default":{"name":"WtExeFact.WtMinImpactExeUnit","lots":100,"minopenlots":100,"pricemode":0,"offset":0,"expire":0,"span":0,"byrate":false}}})"));
        guanheng::StandardPluginFunctions functions;
        functions.find=exports.get<decltype(functions.find)>("findStandardQmtTrader");
        functions.pump=exports.get<decltype(functions.pump)>("pumpStandardQmtTrader");
        functions.inspect=exports.get<decltype(functions.inspect)>("inspectStandardQmtTrader");
        functions.stop=exports.get<decltype(functions.stop)>("stopStandardQmtTrader");
        functions.destroy=exports.destroy;
        functions.submission={exports.get<guanheng::BeginSubmissionFn>("beginStandardQmtSubmission"),
            exports.get<guanheng::EndSubmissionFn>("endStandardQmtSubmission"),exports.get<guanheng::InspectSubmissionFn>("inspectStandardQmtSubmission")};
        {
            guanheng::StandardExecutionHost invalid("QOG_reject","product-host-reject",base,policy,factory,*environment);
            std::unique_ptr<wtp::WTSVariant,VariantRelease> bad(WTSCfgLoader::load_from_content(R"({"module":"unselected"})"));
            check(!invalid.initialize(bad.get(),executer.get(),functions,{8,65536,16,10000}),"host_configuration_rejected");
            check(!invalid.command()&&functions.find(trader->getCString("instance_id"))==nullptr,"host_configuration_no_plugin");
            check(invalid.close()==0&&invalid.close()==0,"host_uninitialized_idempotent_close");
        }
        host.reset(new guanheng::StandardExecutionHost("QOG_owned","product-host-main",base,policy,factory,*environment));
        check(host->initialize(trader.get(),executer.get(),functions,{8,65536,16,10000}),"host_actual_initialize");
        check(!host->initialize(trader.get(),executer.get(),functions,{8,65536,16,10000}),"host_no_reinitialize");
        command=host->command();check(bool(command),"host_published_command");manager.add_executer(command);
        auto pump_until=[&](auto predicate){while(!predicate()){
            check(Clock::now()<end,"host_same_deadline");check(host->pump(64,8)>=0,"host_product_pump");Sleep(1);
        }};
        pump_until([&]{return host->status().phase==guanheng::ExecutionHostPhase::Ready;});
        int wrong_pump=0,wrong_query=0,wrong_close=0;bool wrong_read=false,wrong_environment=false;guanheng::ExecutionHostStatus wrong_status;
        std::thread wrong_owner([&]{
            wrong_pump=host->pump(64,8);wrong_query=host->query_orders();wrong_close=host->close();wrong_status=host->status();
            try{host->position("SZSE.STK.000001");}catch(const std::exception&){wrong_read=true;}
            try{environment->observe();}catch(const std::exception&){wrong_environment=true;}
        });wrong_owner.join();
        check(wrong_pump==guanheng::StandardQmtWrongOwner&&wrong_query==guanheng::StandardQmtWrongOwner
            &&wrong_close==guanheng::StandardQmtWrongOwner&&wrong_read&&wrong_environment&&wrong_status.fault==guanheng::ExecutionHostFault::WrongOwner,"host_wrong_owner_rejected");
        check(host->status().phase==guanheng::ExecutionHostPhase::Ready&&!host->status().stop_requested,"host_owner_state_preserved");
        const char* code="SZSE.STK.000001";check(host->position(code)==100&&host->position(code,true)==100,"host_source_position");
        rapidjson::Value calls(rapidjson::kArrayType);
        for(unsigned round=0;round<4;++round){
            const auto before=host->status().plugin.inserts;
            std::exception_ptr error;std::thread producer([&]{try{
                wtp::wt_hashmap<std::string,double> targets;targets[code]=200;manager.set_positions(targets);
                wtp::WTSTickStruct values={};std::strcpy(values.code,code);std::strcpy(values.exchg,"SZSE");
                values.price=10.01;values.action_date=20261022;values.trading_date=20261022;values.action_time=100000000+round*1000;
                auto* tick=wtp::WTSTickData::create(values);manager.handle_tick(code,tick);tick->getTickStruct().price=99;tick->release();
            }catch(...){error=std::current_exception();}});producer.join();if(error)std::rethrow_exception(error);
            pump_until([&]{const auto s=host->status();return s.queue.delivered==(round+1)*2&&s.plugin.inserts==1&&s.plugin.pending_commands==0;});
            check(host->query_orders()==0,"host_product_order_refresh");
            pump_until([&]{return host->status().plugin.queries>=5+round;});
            check(host->position(code)==100&&host->undone(code)==(active?80:0),"host_source_observations");
            std::unique_ptr<wtp::OrderMap,HostOrderRelease> orders(host->orders(code));check(orders&&orders->size()==(active?1:0),"host_original_order_table");
            rapidjson::Value call(rapidjson::kObjectType);call.AddMember("new_order_ids",host->status().plugin.inserts-before,alloc);
            call.AddMember("position",host->position(code),alloc);calls.PushBack(std::move(call),alloc);
        }
        const auto observed=host->status();check(observed.plugin.inserts==1&&!observed.plugin.cancels&&observed.plugin.queries==8,"host_actual_transport");
        check(observed.queue.delivered==8&&observed.queue.payload_bytes==0&&!observed.queue.inflight,"host_queue_delivered");
        report.AddMember("calls",std::move(calls),alloc);report.AddMember("inserts",observed.plugin.inserts,alloc);report.AddMember("queries",observed.plugin.queries,alloc);
        report.AddMember("position",host->position(code),alloc);report.AddMember("remaining_quantity",host->undone(code),alloc);
        std::thread stopper([&]{host->request_stop();});stopper.join();
        check(host->status().stop_requested&&!command->status().accepting,"host_cross_thread_stop");
        const auto result=host->close();check(result==0&&host->close()==0,"host_product_close");
        const auto final=host->status();closed=final.phase==guanheng::ExecutionHostPhase::Closed&&final.plugin.joined&&final.plugin.drained&&!final.plugin.worker_live;
        deleted=functions.find(trader->getCString("instance_id"))==nullptr;check(closed&&deleted,"host_real_api_deleted");
        host.reset();
        // 原manager仍持有桥；关闭后迟到目标只能被拒绝，不能再访问已销毁Local。
        std::thread late([&]{wtp::wt_hashmap<std::string,double> targets;targets[code]=300;manager.set_positions(targets);});late.join();
        check(!command->status().accepting&&command->status().queued_commands==0&&command->status().rejected>0,"host_late_target_rejected");
        report.AddMember("configuration_rejected_before_plugin",true,alloc);report.AddMember("wrong_owner_rejected",true,alloc);
        report.AddMember("cross_thread_stop",true,alloc);report.AddMember("late_target_rejected",true,alloc);
        report.AddMember("product_execution_environment",true,alloc);report.AddMember("system_clock_checked",true,alloc);
        report.AddMember("native_calendar_checked",true,alloc);report.AddMember("product_host",true,alloc);report.AddMember("owner_execution",true,alloc);passed=true;
    }catch(const std::exception& e){text(report,"primary",std::string(e.what()).substr(0,256),alloc);}
    if(host){host->request_stop();const auto value=host->close();closed=value==0;if(closed){deleted=true;host.reset();}}
    report.AddMember("passed",passed&&closed&&deleted,alloc);report.AddMember("closed",closed,alloc);report.AddMember("deleted",deleted,alloc);report.AddMember("real_broker_calls",0,alloc);
    write_new(output,encode(report));if(!closed)ExitProcess(3);return passed&&closed&&deleted?0:1;
}
