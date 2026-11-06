// 同一TU访问既有测试friend，执行真实Standard准入/收口及原owner桥；不启动worker或连接账户。
#define GH_QMT_STANDARD_AUDIT_TESTING
#include "TraderQMT/StandardQmtTrader.cpp"
#include "GuanhengExecution/QueryFirstSubmission.h"
#include "GuanhengExecution/OwnerExecCommand.h"
#include "Includes/ExecuteDefs.h"
#include <iostream>
#include <thread>
namespace guanheng {
struct StandardAuditTestAccess {
    static void ready(StandardQmtTrader& api){
        auto& x=*api.impl_;x.initialized=true;x.logged_in=true;x.connected=true;
        x.phase=StandardQmtPhase::LoggedIn;x.query_first=true;x.expected.writes_enabled=true;
        x.binding.row_limit=4096;x.max_pending=16;x.max_queue=16;x.max_queue_bytes=1024*1024;
        x.read_waiting=true;
    }
    static bool hard(StandardQmtTrader& api){return api.impl_->hard_fault;}
    static unsigned error(StandardQmtTrader& api){return static_cast<unsigned>(api.impl_->first_error.code);}
    static void resumed(StandardQmtTrader& api){
        auto& x=*api.impl_;x.observation_refresh_stage=0;x.observation_refresh_task=100;
        x.observation_refresh_applied(100);
    }
    static unsigned accepted(StandardQmtTrader& api){return static_cast<unsigned>(api.impl_->identities.size());}
    static void original_unknown(StandardQmtTrader& api){
        auto& x=*api.impl_;x.read_waiting=false;x.unknown_fenced=true;x.writes_blocked=true;
        x.first_error.code=ErrorCode::SubmissionUnknown;
        StandardQmtTrader::Impl::Identity identity{"original-tag","SZSE","159780","original-broker"};
        identity.group_id=777;identity.observation=SubmissionObservation::Unknown;
        strcpy_s(identity.command_id,"11111111-1111-4111-8111-111111111111");
        identity.retained_receipt.command_body="synthetic-original-receipt";
        x.identities.emplace("original-entrust",std::move(identity));
    }
    static bool unknown_preserved(StandardQmtTrader& api){
        auto& x=*api.impl_;auto p=x.identities.find("original-entrust");
        return p!=x.identities.end()&&p->second.group_id==777
            &&p->second.observation==SubmissionObservation::Unknown
            &&strcmp(p->second.command_id,"11111111-1111-4111-8111-111111111111")==0
            &&p->second.retained_receipt.command_body=="synthetic-original-receipt"&&x.unknown_fenced;
    }
};
}
struct Destination final:wtp::IExecCommand {
    guanheng::StandardQmtTrader& api;unsigned delegates=0; // 真实原insert准入调用数；本测试无worker/SDK。
    explicit Destination(guanheng::StandardQmtTrader& value):IExecCommand("synthetic"),api(value){}
    void set_position(const wtp::wt_hashmap<std::string,double>&)override{}
    void on_tick(const char*,wtp::WTSTickData*)override{}
    void on_position_changed(const char*,double)override{
        guanheng::SubmissionKeyV1 key;strcpy_s(key.exchange,"SZSE");strcpy_s(key.code,"159780");
        guanheng::SubmissionViewV1 view;
        guanheng::QueryFirstSubmission gate(&api,{beginStandardQmtSubmission,endStandardQmtSubmission,inspectStandardQmtSubmission},true);
        gate.invoke(key,view,[&]{
            ++delegates;auto* order=wtp::WTSEntrust::create("159780",1000,.728,"SZSE");
            order->setEntrustID("synthetic-original-entrust");order->setUserTag("synthetic-original-tag");
            order->setDirection(wtp::WDT_LONG);order->setOffsetType(wtp::WOT_OPEN);order->setPriceType(wtp::WPT_LIMITPRICE);
            const int rc=api.orderInsert(order);order->release();
            std::cout<<"insert_result="<<rc<<"\n";return wtp::OrderIDs{};
        });
    }
};
struct ThrowingDestination final:wtp::IExecCommand {
    ThrowingDestination():IExecCommand("throwing"){}
    void set_position(const wtp::wt_hashmap<std::string,double>&)override{}
    void on_tick(const char*,wtp::WTSTickData*)override{}
    void on_position_changed(const char*,double)override{throw std::runtime_error("synthetic-independent-destination-fault");}
};
int main(int argc,char**){
    guanheng::StandardQmtTrader api;guanheng::StandardAuditTestAccess::ready(api);Destination destination(api);
    guanheng::OwnerExecCommand queue("synthetic",destination,[](const char*){return static_cast<wtp::WTSContractInfo*>(nullptr);},
        {128,1048576,128,10000});
    const auto before=api.awaiting_observation();queue.on_position_changed("SZSE.ETF.159780",1000);queue.drain(16);
    const auto result=queue.status();
    std::cout<<"queue_fault="<<static_cast<unsigned>(result.fault)<<" awaiting_before="<<before
        <<" awaiting_after="<<api.awaiting_observation()<<" plugin_error="<<guanheng::StandardAuditTestAccess::error(api)
        <<" delegate_calls="<<destination.delegates<<"\n";
    if(argc>1)return result.fault==guanheng::ExecutionQueueFault::Destination
        &&guanheng::StandardAuditTestAccess::error(api)==9&&destination.delegates==1?0:2;
    guanheng::SubmissionKeyV1 inspect_key;strcpy_s(inspect_key.exchange,"SZSE");strcpy_s(inspect_key.code,"159780");
    guanheng::SubmissionViewV1 inspected;
    if(api.inspect_submission(inspect_key,inspected)!=static_cast<int>(guanheng::SubmissionDecision::BlockedAwait))return 10;
    if(result.fault!=guanheng::ExecutionQueueFault::None||guanheng::StandardAuditTestAccess::hard(api)
        ||api.awaiting_observation()!=1||destination.delegates!=0)return 1;
    // 旧只读责任由原owner应用后继P收束；后继目标仅创建一次新子身份。
    guanheng::StandardAuditTestAccess::resumed(api);queue.on_position_changed("SZSE.ETF.159780",1000);queue.drain(16);
    if(queue.status().fault!=guanheng::ExecutionQueueFault::None||destination.delegates!=1
        ||guanheng::StandardAuditTestAccess::accepted(api)!=1)return 3;
    queue.on_position_changed("SZSE.ETF.159780",1000);queue.drain(16);
    if(destination.delegates!=1||guanheng::StandardAuditTestAccess::accepted(api)!=1)return 4;
    guanheng::StandardQmtTrader unknown;guanheng::StandardAuditTestAccess::ready(unknown);
    guanheng::StandardAuditTestAccess::original_unknown(unknown);Destination waiting(unknown);
    guanheng::OwnerExecCommand unknown_queue("unknown",waiting,[](const char*){return static_cast<wtp::WTSContractInfo*>(nullptr);},{8,65536,8,10000});
    unknown_queue.on_position_changed("SZSE.ETF.159780",1000);unknown_queue.drain(16);
    if(waiting.delegates||unknown_queue.status().fault!=guanheng::ExecutionQueueFault::None
        ||!guanheng::StandardAuditTestAccess::unknown_preserved(unknown)
        ||guanheng::StandardAuditTestAccess::error(unknown)!=9||unknown.awaiting_observation()!=1)return 5;
    // 独立桥故障保持原分类：容量和过期均在目标调用前拒绝。
    guanheng::OwnerExecCommand capacity("capacity",waiting,[](const char*){return static_cast<wtp::WTSContractInfo*>(nullptr);},{1,65536,8,10000});
    capacity.on_position_changed("SZSE.ETF.159780",1);capacity.on_position_changed("SZSE.ETF.159780",1);
    if(capacity.status().fault!=guanheng::ExecutionQueueFault::Capacity)return 6;
    guanheng::OwnerExecCommand expired("expired",waiting,[](const char*){return static_cast<wtp::WTSContractInfo*>(nullptr);},{8,65536,8,1});
    expired.on_position_changed("SZSE.ETF.159780",1);std::this_thread::sleep_for(std::chrono::milliseconds(5));expired.drain(1);
    if(expired.status().fault!=guanheng::ExecutionQueueFault::Expired)return 7;
    ThrowingDestination throwing;
    guanheng::OwnerExecCommand failed("destination",throwing,[](const char*){return static_cast<wtp::WTSContractInfo*>(nullptr);},{8,65536,8,10000});
    failed.on_position_changed("SZSE.ETF.159780",1);failed.drain(1);
    if(failed.status().fault!=guanheng::ExecutionQueueFault::Destination)return 8;
    unsigned native_calls=0;guanheng::SubmissionKeyV1 key;guanheng::SubmissionViewV1 view;
    guanheng::QueryFirstSubmission native_gate(nullptr,{},false);
    native_gate.invoke(key,view,[&]{++native_calls;return wtp::OrderIDs{};});
    if(native_calls!=1)return 9;
    std::cout<<"waiting_resume_once=passed unknown_identity_preserved=passed capacity_expired_destination_preserved=passed native_bypass_preserved=passed\n";
    return 0;
}
