// 原生股票执行器的首笔资金/可卖主链；来源与SDK由外部隔离夹具提供。
#define wmain standard_helper_unused_main
#include "../qmt_standard_trader/standard_probe.cpp"
#undef wmain
#include "GuanhengExecution/StandardExecutionHost.h"
#include "GuanhengExecution/ExecutionEnvironment.h"
#include "WtCore/WtExecuterFactory.h"
#include "Share/TimeUtils.hpp"

int wmain(int argc,wchar_t** argv){
    if(argc!=5||std::wstring(argv[1])!=L"--config"||std::wstring(argv[3])!=L"--output")return 2;
    const auto output=fs::absolute(argv[4]);rapidjson::Document report(rapidjson::kObjectType);auto& a=report.GetAllocator();
    Exports exports;WTSBaseDataMgr base;wtp::ActionPolicyMgr policy;wtp::WtExecuterFactory factory;
    std::unique_ptr<guanheng::ExecutionEnvironment> environment;
    std::unique_ptr<wtp::WTSVariant,VariantRelease> trader,executer;
    std::unique_ptr<guanheng::StandardExecutionHost> host;
    bool passed=false,closed=false,deleted=false,expect_missing_account=false,source_rejected=false;
    auto end=Clock::now()+std::chrono::seconds(25);
    try{
        const auto raw=read_config(fs::absolute(argv[2]));rapidjson::Document input;input.Parse(raw.data(),raw.size());
        check(!input.HasParseError(),"funds_config");const auto scenario=field(input,"scenario");
        const bool sell=scenario=="sellable-zero"||scenario=="sellable-200";
        const bool generic=scenario=="generic-refresh"||scenario=="negative";
        expect_missing_account=scenario=="unknown";
        const unsigned first_expected=scenario=="positive"||scenario=="sellable-200"?1:0;
        const bool refresh=!sell&&scenario!="positive";
        const auto now=GetTickCount64(),deadline=input["deadline_uptime_ms"].GetUint64();
        check(deadline>now+6000,"funds_original_deadline");
        end=Clock::now()+std::chrono::milliseconds((std::min<uint64_t>)(30000,deadline-now-6000));
        const auto work=fs::absolute(fs::u8path(field(input,"work")));
        check(fs::create_directories(work/"traders"),"funds_new_root");fs::current_path(work);
        const auto dll=work/"traders/TraderQMTStandard.dll";
        check(fs::copy_file(fs::u8path(field(input,"candidate_dll")),dll),"funds_plugin_copy");
        check(!_putenv_s("QMT_STANDARD_FIXTURE_KEY","fixture")
            &&!_putenv_s("QMT_STANDARD_FIXTURE_SECRET",field(input,"hmac_secret").c_str()),"funds_credentials");
        WtHelper::setTime(20261022,1000);WtHelper::setTDate(20261022);base_files(work,base,policy);exports.load(dll);
        environment.reset(new guanheng::ExecutionEnvironment(base,"DAY",nullptr,[]{return TimeUtils::makeTime(20261022,100000000);}));
        const auto factories=work/"executers";check(fs::create_directory(factories),"funds_factory_root");
        check(fs::copy_file(fs::u8path(field(input,"execution_factory")),factories/"WtExeFact.dll"),"funds_original_factory");
        check(factory.loadFactories(factories.string().c_str()),"funds_factory_load");
        trader.reset(WTSCfgLoader::load_from_content(encode(input["trader"])));
        auto execution_text=std::string(R"({"scale":1,"strict_sync":false,"poolsize":0,"clear":{"active":false},"policy":{"default":{"name":"WtExeFact.WtStockMinImpactExeUnit","lots":1000,"min_order":100,"pricemode":0,"offset":0,"expire":0,"span":0,"byrate":false}}})");
        if(generic){const auto at=execution_text.find("WtStockMinImpactExeUnit");execution_text.replace(at,std::strlen("WtStockMinImpactExeUnit"),"WtMinImpactExeUnit");}
        executer.reset(WTSCfgLoader::load_from_content(execution_text.c_str()));
        guanheng::StandardPluginFunctions functions;
        functions.find=exports.get<decltype(functions.find)>("findStandardQmtTrader");
        functions.pump=exports.get<decltype(functions.pump)>("pumpStandardQmtTrader");
        functions.inspect=exports.get<decltype(functions.inspect)>("inspectStandardQmtTrader");
        functions.stop=exports.get<decltype(functions.stop)>("stopStandardQmtTrader");functions.destroy=exports.destroy;
        functions.submission={exports.get<guanheng::BeginSubmissionFn>("beginStandardQmtSubmission"),
            exports.get<guanheng::EndSubmissionFn>("endStandardQmtSubmission"),exports.get<guanheng::InspectSubmissionFn>("inspectStandardQmtSubmission")};
        host.reset(new guanheng::StandardExecutionHost("funds-owned","funds-host",base,policy,factory,*environment));
        check(host->initialize(trader.get(),executer.get(),functions,{16,65536,16,10000}),"funds_host_init");
        auto pump=[&]{
            check(Clock::now()<end,"funds_deadline");check(host->pump(64,16)>=0,"funds_host_pump");
            const auto state=host->status();
            if(state.fault!=guanheng::ExecutionHostFault::None){
                report.AddMember("host_fault",static_cast<unsigned>(state.fault),a);
                report.AddMember("plugin_error",state.plugin.error,a);
                report.AddMember("queries",state.plugin.queries,a);report.AddMember("inserts",state.plugin.inserts,a);
                // 固定插件在owner映射边界将空账户来源分类为IoError(10)；三项先行查询已交付。
                source_rejected=expect_missing_account&&state.plugin.error==10&&state.plugin.queries==3&&!state.plugin.inserts;
                check(false,source_rejected?"funds_account_source_rejected":"funds_host_fault");
            }
            Sleep(2);
        };
        while(host->status().phase!=guanheng::ExecutionHostPhase::Ready)pump();
        check(host->status().plugin.queries==4,"funds_four_initial_queries");
        const char* code="SZSE.STK.000001";
        check(host->position(code)==(sell?1000:0)&&host->position(code,true)==(scenario=="sellable-200"?200:0),"funds_broker_position");
        // 四查询全部完成后才首次创建执行单元，覆盖真实宿主的账户/单元先后关系。
        auto command=host->command();wtp::wt_hashmap<std::string,double> targets;targets[code]=sell?400:1000;
        command->set_position(targets);
        unsigned tick_count=0;
        auto tick=[&]{
            wtp::WTSTickStruct value={};std::strcpy(value.code,code);std::strcpy(value.exchg,"SZSE");
            value.price=10.01;value.action_date=value.trading_date=20261022;value.action_time=100000000+(++tick_count)*1000;
            auto* data=wtp::WTSTickData::create(value);command->on_tick(code,data);data->release();
            const auto until=Clock::now()+std::chrono::milliseconds(35);while(Clock::now()<until)pump();
        };
        for(unsigned i=0;i<12;++i)tick();
        while(host->status().plugin.pending_commands)pump();
        const auto first=host->status().plugin.inserts;report.AddMember("first_inserts",first,a);
        check(first==first_expected,"funds_first_cash_or_sellable_constraint");
        if(refresh){
            auto* api=functions.find(trader->getCString("instance_id"));check(api&&api->queryAccount()==0,"funds_original_account_refresh");
            while(host->status().plugin.queries<5)pump();
            // 同一原目标继续执行；新账户查询提供2500元后，原算法按100份取整买200。
            for(unsigned i=0;i<12;++i)tick();
            while(host->status().plugin.pending_commands)pump();
        }
        const auto final=host->status();const unsigned expected=refresh?1:first_expected;
        report.AddMember("inserts",final.plugin.inserts,a);report.AddMember("queries",final.plugin.queries,a);
        report.AddMember("ticks",tick_count,a);report.AddMember("cash_refresh",refresh,a);
        check(final.plugin.inserts==expected&&!final.plugin.cancels&&final.queue.fault==guanheng::ExecutionQueueFault::None,"funds_final_transport");
        host->request_stop();check(host->close()==0,"funds_host_close");const auto stopped=host->status();
        closed=stopped.phase==guanheng::ExecutionHostPhase::Closed&&stopped.plugin.joined&&stopped.plugin.drained&&!stopped.plugin.worker_live;
        deleted=functions.find(trader->getCString("instance_id"))==nullptr;check(closed&&deleted,"funds_physical_close");
        host.reset();passed=true;
    }catch(const std::exception& e){
        text(report,"primary",std::string(e.what()).substr(0,128),a);
        if(source_rejected&&std::strcmp(e.what(),"funds_account_source_rejected")==0){
            passed=true;report.AddMember("source_account_rejected",true,a);
            report.AddMember("first_inserts",0,a);
        }
    }
    if(host){host->request_stop();closed=host->close()==0;if(closed){deleted=true;host.reset();}}
    report.AddMember("passed",passed&&closed&&deleted,a);report.AddMember("closed",closed,a);report.AddMember("deleted",deleted,a);
    report.AddMember("real_broker_calls",0,a);report.AddMember("CTA_strategy_qualification",false,a);
    write_new(output,encode(report));if(!closed)ExitProcess(3);return passed&&closed&&deleted?0:1;
}
