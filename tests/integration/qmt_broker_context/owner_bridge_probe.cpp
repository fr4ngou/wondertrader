// 主路径只验证WT原执行器分发和owner交接；目标记录器不包含算法、账户或真实交易。
#define wmain standard_helper_unused_main
#include "../qmt_standard_trader/standard_probe.cpp"
#undef wmain
#include "GuanhengExecution/OwnerExecCommand.h"
#include "WtCore/WtExecMgr.h"
#include <thread>

namespace {
struct Stub final : wtp::IExecuterStub {
    uint64_t get_real_time()override{return 0;}
    wtp::WTSCommodityInfo* get_comm_info(const char*)override{return nullptr;}
    wtp::WTSSessionInfo* get_sess_info(const char*)override{return nullptr;}
    wtp::IHotMgr* get_hot_mon()override{return nullptr;}
    uint32_t get_trading_day()override{return 0;}
};
struct Destination final : wtp::IExecCommand {
    std::thread::id owner=std::this_thread::get_id();
    std::vector<std::string> events;
    wtp::WTSContractInfo* expected;
    Stub owner_stub;
    Destination(wtp::WTSContractInfo* value):IExecCommand("owner-destination"),expected(value){setStub(&owner_stub);}
    void arrived(const char* event){check(owner==std::this_thread::get_id(),"owner_actual_destination_thread");check(_stub==&owner_stub,"owner_destination_stub_preserved");events.emplace_back(event);}
    void set_position(const wtp::wt_hashmap<std::string,double>& values)override{
        arrived("targets");check(values.size()==1&&values.at("SZSE.STK.000001")==200,"owner_original_targets");
    }
    void on_position_changed(const char* code,double value)override{
        arrived("delta");check(std::string(code)=="SZSE.STK.000001"&&value==-25,"owner_original_delta");
    }
    void on_tick(const char* code,wtp::WTSTickData* tick)override{
        arrived("tick");check(std::string(code)=="SZSE.STK.000001"&&tick&&tick->price()==10.01,"owner_tick_value_copied");
        check(tick->getContractInfo()==expected&&tick->actiondate()==20261022,"owner_tick_metadata_recreated");
    }
};
}
int wmain(int argc,wchar_t** argv){
    if(argc!=3||std::wstring(argv[1])!=L"--output")return 2;
    rapidjson::Document report(rapidjson::kObjectType);auto& alloc=report.GetAllocator();
    bool passed=false;
    try {
        const auto output=fs::absolute(argv[2]);const auto work=output.parent_path()/"owner-runtime";
        check(fs::create_directory(work),"owner_new_runtime");fs::current_path(work);
        WTSBaseDataMgr base;wtp::ActionPolicyMgr policy;base_files(work,base,policy);
        auto* contract=base.getContract("000001","SZSE");check(contract!=nullptr,"owner_base_contract");
        Destination destination(contract);std::size_t lookups=0;
        auto bridge=std::make_shared<guanheng::OwnerExecCommand>("qmt-owner",destination,[&](const char* code){
            check(std::this_thread::get_id()==destination.owner,"owner_metadata_thread");++lookups;
            check(std::string(code)=="SZSE.STK.000001","owner_metadata_symbol");return base.getContract("000001","SZSE");
        },guanheng::ExecutionQueueLimits{8,65536,16,10000});
        Stub source_stub;bridge->setStub(&source_stub);
        wtp::WtExecuterMgr manager;manager.add_executer(bridge);
        std::exception_ptr failure;std::thread::id producer_id;
        std::thread producer([&]{try{
            producer_id=std::this_thread::get_id();
            wtp::wt_hashmap<std::string,double> target;target["SZSE.STK.000001"]=200;
            manager.set_positions(target);target["SZSE.STK.000001"]=999;target.clear();
            manager.handle_pos_change("SZSE.STK.000001",175,-25);
            auto* tick=wtp::WTSTickData::create("SZSE.STK.000001");
            tick->getTickStruct().price=10.01;tick->getTickStruct().action_date=20261022;
            manager.handle_tick("SZSE.STK.000001",tick);
            tick->getTickStruct().price=99.99;tick->release();
        }catch(...){failure=std::current_exception();}});
        producer.join();if(failure)std::rethrow_exception(failure);
        check(producer_id!=destination.owner&&destination.events.empty(),"owner_producer_no_destination_call");
        check(bridge->status().queued_commands==3,"owner_original_queue_order");
        check(bridge->drain(2)==2&&destination.events==std::vector<std::string>({"targets","delta"}),"owner_bounded_first_drain");
        check(bridge->status().queued_commands==1&&bridge->drain(2)==1,"owner_second_drain");
        check(destination.events==std::vector<std::string>({"targets","delta","tick"})&&lookups==1,"owner_fifo_actual_calls");
        auto state=bridge->status();check(state.accepted==3&&state.entered==3&&state.delivered==3&&state.payload_bytes==0&&!state.inflight&&state.fault==guanheng::ExecutionQueueFault::None,"owner_actual_drained");
        bridge->close();check(!bridge->status().accepting&&bridge->drain(1)==0,"owner_actual_closed");
        report.AddMember("source_and_owner_different",true,alloc);report.AddMember("destination_calls",3,alloc);
        report.AddMember("metadata_owner_lookups",static_cast<unsigned>(lookups),alloc);
        report.AddMember("source_tick_destroyed_before_delivery",true,alloc);report.AddMember("fifo",true,alloc);
        report.AddMember("closed",true,alloc);text(report,"scope","original WtExecuterMgr to owner value queue; recording destination; no strategy runtime or broker qualification",alloc);
        report.AddMember("passed",true,alloc);passed=true;write_new(output,encode(report));
    }catch(const std::exception& error){text(report,"primary",std::string(error.what()).substr(0,256),alloc);}
    if(!passed){try{write_new(fs::absolute(argv[2]),encode(report));}catch(...){} }
    return passed?0:1;
}
