// 正向主路径使用正式Context/插件，运输与SDK替身由原SHM夹具独立记录。
#define wmain standard_helper_unused_main
#include "../qmt_standard_trader/standard_probe.cpp"
#undef wmain
#include "GuanhengExecution/BrokerQueryContext.h"
#include "GuanhengExecution/OwnerExecCommand.h"
#include "WtCore/WtExecMgr.h"
#include "Share/CodeHelper.hpp"
#include "Share/TimeUtils.hpp"
#include "Includes/WTSContractInfo.hpp"
#include "Includes/WTSSessionInfo.hpp"

namespace {
struct TradeRelease { void operator()(wtp::WTSTradeInfo* value) const { if (value) value->release(); } };
struct OrdersRelease { void operator()(wtp::OrderMap* value) const { if (value) value->release(); } };
struct ExecutionStub final : wtp::IExecuterStub {
    WTSBaseDataMgr& base;unsigned commodity_reads=0,session_reads=0;
    explicit ExecutionStub(WTSBaseDataMgr& value):base(value){}
    uint64_t get_real_time()override{return TimeUtils::makeTime(20261022,100000000);}
    wtp::WTSCommodityInfo* get_comm_info(const char* code)override{
        ++commodity_reads;const auto key=CodeHelper::extractStdCode(code,nullptr);return base.getCommodity(key._exchg,key._product);
    }
    wtp::WTSSessionInfo* get_sess_info(const char* code)override{
        ++session_reads;auto* commodity=get_comm_info(code);return commodity?commodity->getSessionInfo():nullptr;
    }
    wtp::IHotMgr* get_hot_mon()override{return nullptr;}
    uint32_t get_trading_day()override{return 20261022;}
};
struct ObservedLocal final : guanheng::BrokerQueryLocalExecuter {
    using BrokerQueryLocalExecuter::BrokerQueryLocalExecuter;
    std::vector<std::string> algorithm_logs;
    void writeLog(const char* message)override{if(algorithm_logs.size()<32)algorithm_logs.emplace_back(std::string(message).substr(0,256));BrokerQueryLocalExecuter::writeLog(message);}
    unsigned ticks=0,buys=0,sells=0,issued_ids=0;double target=0,observed_position=0,observed_undone=0;bool session_ok=false,code_ok=false;
    void set_position(const wt_hashmap<std::string,double>& values)override{if(!values.empty())target=values.begin()->second;BrokerQueryLocalExecuter::set_position(values);}
    void on_tick(const char* code,wtp::WTSTickData* tick)override{
        ++ticks;code_ok=tick&&std::strcmp(code,tick->code())==0;auto* session=getSessionInfo(code);
        session_ok=session&&session->isInTradingTime(tick->actiontime()/100000);BrokerQueryLocalExecuter::on_tick(code,tick);
    }
    double getPosition(const char* code,bool valid=true,int32_t flag=3)override{return observed_position=BrokerQueryLocalExecuter::getPosition(code,valid,flag);}
    double getUndoneQty(const char* code)override{return observed_undone=BrokerQueryLocalExecuter::getUndoneQty(code);}
    wtp::OrderIDs buy(const char* code,double price,double quantity,bool force=false)override{++buys;auto ids=BrokerQueryLocalExecuter::buy(code,price,quantity,force);issued_ids+=static_cast<unsigned>(ids.size());return ids;}
    wtp::OrderIDs sell(const char* code,double price,double quantity,bool force=false)override{++sells;auto ids=BrokerQueryLocalExecuter::sell(code,price,quantity,force);issued_ids+=static_cast<unsigned>(ids.size());return ids;}
};
struct BusinessAdapter final : guanheng::BrokerQueryAdapter {
    unsigned returned = 0;
    void onRspEntrust(wtp::WTSEntrust* value, wtp::WTSError* error) override {
        check(value && !error, "main_successful_entrust");
        ++returned; TraderAdapter::onRspEntrust(value, error);
    }
};
}
int wmain(int argc, wchar_t** argv) {
    if (argc != 5 || std::wstring(argv[1]) != L"--config" || std::wstring(argv[3]) != L"--output") return 2;
    Exports exports; WTSBaseDataMgr base; wtp::ActionPolicyMgr policy;
    BusinessAdapter adapter;
    wtp::WtExecuterFactory execution_factory;ExecutionStub owner_stub(base);
    ObservedLocal local(&execution_factory, "broker-context-main", nullptr, adapter);
    std::unique_ptr<wtp::WTSVariant, VariantRelease> cfg;
    wtp::ITraderApi* api = nullptr;
    std::unique_ptr<wtp::WTSVariant,VariantRelease> local_config;
    std::shared_ptr<guanheng::OwnerExecCommand> owner_bridge;
    wtp::WtExecuterMgr execution_manager;
    rapidjson::Document report(rapidjson::kObjectType); auto& alloc = report.GetAllocator();
    const auto output = fs::absolute(argv[4]);
    bool passed = false, closed = false, deleted = false;
    try {
        auto raw = read_config(fs::absolute(argv[2])); rapidjson::Document input;
        input.Parse(raw.data(), raw.size()); check(!input.HasParseError(), "main_config");
        const auto mode = field(input, "order_context");
        check(mode == "native" || mode == "query_first", "main_mode");
        const bool owner_execution=input.HasMember("owner_execution")&&input["owner_execution"].GetBool();
        const bool verify_cache = input.HasMember("verify_order_cache") && input["verify_order_cache"].GetBool();
        const bool active_order = input.HasMember("active_order") && input["active_order"].GetBool();
        const bool repeated_cycle = input.HasMember("cycle_mode");
        const auto cycle_mode = repeated_cycle ? field(input, "cycle_mode") : "";
        const auto deadline = input["deadline_uptime_ms"].GetUint64();
        const auto now = GetTickCount64(); check(deadline > now + 6000, "main_original_deadline");
        const auto end = Clock::now() + std::chrono::milliseconds((std::min<uint64_t>)(30000, deadline - now - 6000));
        const auto work = fs::absolute(fs::u8path(field(input, "work")));
        check(fs::create_directories(work / "traders"), "main_new_runtime"); fs::current_path(work);
        const auto installed = work / "traders/TraderQMTStandard.dll";
        check(fs::copy_file(fs::u8path(field(input, "candidate_dll")), installed), "main_plugin_copy");
        const auto secret = field(input, "hmac_secret");
        check(!_putenv_s("QMT_STANDARD_FIXTURE_KEY", "fixture") && !_putenv_s("QMT_STANDARD_FIXTURE_SECRET", secret.c_str()), "main_credentials");
        WtHelper::setTime(20261022, 1000); WtHelper::setTDate(20261022);
        base_files(work, base, policy); exports.load(installed);
        cfg.reset(WTSCfgLoader::load_from_content(encode(input["trader"])));
        check(bool(cfg) && cfg->getString("module") == "TraderQMTStandard", "main_explicit_module");
        check(adapter.init("QOG_owned", cfg.get(), &base, &policy), "main_original_adapter_init");
        api = exports.find(cfg->getCString("instance_id")); check(api != nullptr, "main_standard_api");
        guanheng::SubmissionFunctions functions{exports.get<guanheng::BeginSubmissionFn>("beginStandardQmtSubmission"),
            exports.get<guanheng::EndSubmissionFn>("endStandardQmtSubmission"),
            exports.get<guanheng::InspectSubmissionFn>("inspectStandardQmtSubmission")};
        check(adapter.bind_context("QOG_owned", cfg.get(), api, functions), "main_product_context_bind");
        if(owner_execution){
            check(mode=="query_first"&&!repeated_cycle,"main_owner_query_configuration");
            const auto factories=work/"executers";check(fs::create_directory(factories),"main_owner_factory_directory");
            check(fs::copy_file(fs::u8path(field(input,"execution_factory")),factories/"WtExeFact.dll"),"main_owner_factory_copy");
            check(execution_factory.loadFactories(factories.string().c_str()),"main_original_factory_load");
            check(bool(execution_factory.createExeUnit("WtExeFact.WtMinImpactExeUnit")),"main_original_factory_unit_available");
            local_config.reset(WTSCfgLoader::load_from_content(R"({"scale":1,"strict_sync":false,"poolsize":0,"clear":{"active":false},"policy":{"default":{"name":"WtExeFact.WtMinImpactExeUnit","lots":100,"minopenlots":100,"pricemode":0,"offset":0,"expire":0,"span":0,"byrate":false}}})"));
            check(local_config&&local.init(local_config.get()),"main_original_local_init");local.setStub(&owner_stub);
            owner_bridge=std::make_shared<guanheng::OwnerExecCommand>("main-qmt-owner",local,[&](const char* code){
                const auto key=CodeHelper::extractStdCode(code,nullptr);return base.getContract(key._code,key._exchg);
            },guanheng::ExecutionQueueLimits{8,65536,16,10000});
            execution_manager.add_executer(owner_bridge);
        }
        if (!owner_execution) {
            // 直接委托场景也须完成原Local初始化；成交通知会读取其policy配置。
            local_config.reset(WTSCfgLoader::load_from_content(R"({"scale":1,"strict_sync":false,"poolsize":0,"clear":{"active":false},"policy":{"default":{}}})"));
            check(local_config && local.init(local_config.get()), "main_direct_local_init");
            local.setStub(&owner_stub);
        }
        adapter.addSink(&local); check(adapter.run(), "main_original_run");
        progress(exports, api, end, [&] { return adapter.isReady(); });
        const char* code = "SZSE.STK.000001";
        check(local.getPosition(code, false) == 100 && local.getPosition(code, true) == 100, "main_broker_positions");
        rapidjson::Value calls(rapidjson::kArrayType);
        const unsigned rounds = repeated_cycle ? 2 : 4;
        for (unsigned round = 0; round < rounds; ++round) {
            unsigned issued=0;
            const auto before=local.issued_ids;
            if(owner_execution){
                std::exception_ptr error;
                std::thread producer([&]{try{
                    wt_hashmap<std::string,double> targets;targets[code]=200;execution_manager.set_positions(targets);
                    wtp::WTSTickStruct values={};std::strcpy(values.code,code);std::strcpy(values.exchg,"SZSE");
                    values.price=10.01;values.action_date=20261022;values.trading_date=20261022;values.action_time=100000000+round*1000;
                    auto* tick=wtp::WTSTickData::create(values);
                    execution_manager.handle_tick(code,tick);tick->getTickStruct().price=99;tick->release();
                }catch(...){error=std::current_exception();}});
                producer.join();if(error)std::rethrow_exception(error);
                check(owner_bridge->drain(8)==2&&owner_bridge->status().fault==guanheng::ExecutionQueueFault::None,"main_owner_native_delivery");
            }else issued=static_cast<unsigned>(local.buy(code,10.01,100).size());
            progress(exports, api, end, [&] { return inspect(exports, api).pending_commands == 0; });
            if(owner_execution)issued=local.issued_ids-before;
            const auto expected = repeated_cycle || mode == "native" || round == 0 ? 1u : 0u;
            if(owner_execution&&round==0){report.AddMember("owner_commodity_reads",owner_stub.commodity_reads,alloc);report.AddMember("owner_session_reads",owner_stub.session_reads,alloc);report.AddMember("owner_first_issued",issued,alloc);report.AddMember("owner_submission_decision",static_cast<unsigned>(local.last_submission().decision),alloc);report.AddMember("owner_ticks",local.ticks,alloc);report.AddMember("owner_tick_code_ok",local.code_ok,alloc);report.AddMember("owner_session_ok",local.session_ok,alloc);report.AddMember("owner_target",local.target,alloc);report.AddMember("owner_position",local.observed_position,alloc);report.AddMember("owner_undone",local.observed_undone,alloc);report.AddMember("owner_buy_attempts",local.buys,alloc);report.AddMember("owner_sell_attempts",local.sells,alloc);rapidjson::Value logs(rapidjson::kArrayType);for(const auto& line:local.algorithm_logs)logs.PushBack(rapidjson::Value(line.c_str(),alloc),alloc);report.AddMember("owner_algorithm_logs",std::move(logs),alloc);}
            check(issued == expected, "main_actual_submission_count");
            check(api->queryOrders() == 0, "main_order_refresh");
            const auto expected_queries = repeated_cycle ? 6u + 2 * round : 5u + round;
            progress(exports, api, end, [&] { return inspect(exports, api).queries >= expected_queries; });
            check(local.getUndoneQty(code) == (active_order ? 80 : 0), "main_broker_remaining_quantity");
            std::unique_ptr<wtp::OrderMap, OrdersRelease> orders(local.getOrders(code));
            check(orders && orders->size() == (active_order ? 1 : 0), "main_query_order_count");
            if (active_order) {
                auto* row = static_cast<wtp::WTSOrderInfo*>(orders->begin()->second);
                check(row->getVolLeft() == 80 && row->getVolTraded() == 20, "main_original_broker_order");
            }
            if (verify_cache) {
                // 同一完整查询重复刷新后，原表和统计仍代表柜台当前一笔活动单。
                std::unique_ptr<wtp::OrderMap, OrdersRelease> native_orders(adapter.TraderAdapter::getOrders(""));
                check(native_orders && native_orders->size() == 1 && adapter.checkOrderLimits(code), "main_original_order_table_and_statistics");
                auto* native_row = static_cast<wtp::WTSOrderInfo*>(native_orders->begin()->second);
                check(native_row->getVolLeft() == 80 && native_orders->begin()->first == orders->begin()->first, "main_same_original_order_identity");
            }
            rapidjson::Value call(rapidjson::kObjectType);
            call.AddMember("new_order_ids", issued, alloc);
            call.AddMember("decision", static_cast<unsigned>(local.last_submission().decision), alloc);
            call.AddMember("position", local.getPosition(code, false), alloc);
            if (repeated_cycle) {
                const auto expected_position = 100.0 + (round + 1) * (cycle_mode == "filled" ? 100.0 : 20.0);
                check(local.getPosition(code, false) == expected_position, "main_post_terminal_broker_position_applied");
                guanheng::SubmissionKeyV1 key;std::strcpy(key.exchange,"SZSE");std::strcpy(key.code,"000001");
                guanheng::SubmissionViewV1 view;
                check(functions.inspect(api,&key,&view) == static_cast<int>(guanheng::SubmissionDecision::Admitted)
                    && view.unresolved_children == 0, "main_next_group_after_broker_position");
                call.AddMember("next_group_admitted", true, alloc);
            }
            calls.PushBack(std::move(call), alloc);
        }
        if (verify_cache) {
            std::unique_ptr<wtp::OrderMap, OrdersRelease> native_orders(adapter.TraderAdapter::getOrders(""));
            check(native_orders && native_orders->size() == 1, "main_original_cancel_order_found");
            auto* order = static_cast<wtp::WTSOrderInfo*>(native_orders->begin()->second);
            std::unique_ptr<wtp::WTSTradeInfo, TradeRelease> late(wtp::WTSTradeInfo::create("000001", "SZSE"));
            late->setContractInfo(order->getContractInfo()); late->setUserTag(order->getUserTag());
            late->setTradeID("late.synthetic.20"); late->setRefOrder(order->getOrderID());
            late->setDirection(wtp::WDT_LONG); late->setOffsetType(wtp::WOT_OPEN);
            late->setNetDirection(true); late->setVolume(20); late->setPrice(10.01); late->setAmount(200.2);
            late->setTradeDate(20261022); late->setTradeTime(TimeUtils::makeTime(20261022, 100000000));
            // 已查到余量80后再收到同笔20股成交；通知照常交付，查询值保持80。
            adapter.onPushTrade(late.get());
            check(local.getUndoneQty(code) == 80 && local.getPosition(code, false) == 100, "main_late_trade_does_not_recount");
            progress(exports, api, end, [&] { return inspect(exports, api).queries == 11; });
            check(local.getUndoneQty(code) == 80 && local.getPosition(code, false) == 100, "main_late_trade_followup_query_authority");
            report.AddMember("late_trade_quantity", 20u, alloc);
            report.AddMember("late_trade_remaining_quantity", local.getUndoneQty(code), alloc);
            const bool cancelled = adapter.TraderAdapter::cancel(native_orders->begin()->first);
            check(cancelled, "main_original_cancel_admitted");
            progress(exports, api, end, [&] { return inspect(exports, api).pending_commands == 0 && inspect(exports, api).cancels == 1; });
            report.AddMember("queried_active_orders", 1u, alloc);
            report.AddMember("native_cached_orders", static_cast<unsigned>(native_orders->size()), alloc);
            report.AddMember("native_cancel_returned", cancelled, alloc);
            report.AddMember("cancel_transport_calls", inspect(exports, api).cancels, alloc);
            report.AddMember("repeated_query_statistics_stable", adapter.checkOrderLimits(code), alloc);
        }
        const auto observed = inspect(exports, api);
        check(observed.inserts == (repeated_cycle ? 2 : mode == "native" ? 4 : 1) && observed.cancels == (verify_cache ? 1u : 0u) && observed.queries == (verify_cache ? 11u : 8u), "main_transport_counts");
        text(report, "order_context", mode, alloc); report.AddMember("calls", std::move(calls), alloc);
        report.AddMember("inserts", observed.inserts, alloc); report.AddMember("queries", observed.queries, alloc);
        report.AddMember("position", local.getPosition(code, false), alloc);
        report.AddMember("remaining_quantity", local.getUndoneQty(code), alloc);
        if(owner_execution){auto state=owner_bridge->status();check(state.delivered==8&&state.payload_bytes==0&&!state.inflight,"main_owner_delivery_totals");owner_bridge->close();}
        report.AddMember("owner_execution",owner_execution,alloc);
        passed = true;
    } catch (const std::exception& error) { text(report, "primary", std::string(error.what()).substr(0, 256), alloc); }
    try {
        if(owner_bridge)owner_bridge->close();
        if (api) {
            adapter.release(); const auto state = inspect(exports, api);
            closed = state.phase == static_cast<unsigned>(StandardQmtPhase::Closed) && state.joined && state.drained && !state.worker_live;
            check(closed, "main_actual_closed"); exports.destroy(api); deleted = api == nullptr;
        }
    } catch (const std::exception& error) { text(report, "cleanup", std::string(error.what()).substr(0, 256), alloc); }
    report.AddMember("passed", passed && closed && deleted, alloc);
    report.AddMember("closed", closed, alloc); report.AddMember("deleted", deleted, alloc);
    report.AddMember("real_broker_calls", 0, alloc);
    write_new(output, encode(report));
    if (api) ExitProcess(3); // 未确认关闭的SPI/BaseDataMgr留给外层隔离进程，避免悬空回调。
    return passed && closed && deleted ? 0 : 1;
}
