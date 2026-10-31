#include "GuanhengQmtBootstrap/ReadOnlyTrader.h"
#include <boost/noncopyable.hpp>
#include "WtCore/TraderAdapter.h"
#include "WtCore/ITrdNotifySink.h"
#include "WTSTools/WTSBaseDataMgr.h"
#include "WTSUtils/WTSCfgLoader.h"
#include "Includes/WTSVariant.hpp"
#include "Includes/WTSCollection.hpp"
#include "Includes/WTSTradeDef.hpp"
#include <rapidjson/document.h>
#include <rapidjson/stringbuffer.h>
#include <rapidjson/writer.h>
#include <Windows.h>
#include <TlHelp32.h>
#include <psapi.h>
#include <algorithm>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <thread>
#include <chrono>
#include <stdexcept>
#include <functional>
#include "ProbeObservers.h"
using namespace guanheng::bootstrap;
namespace fs=std::filesystem;
#define CHECK(x) do{if(!(x))throw std::runtime_error(#x);}while(false)
unsigned threads()
{
    unsigned n=0;HANDLE h=CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD,0);THREADENTRY32 e={sizeof(e)};
    if(Thread32First(h,&e))do{if(e.th32OwnerProcessID==GetCurrentProcessId())++n;}while(Thread32Next(h,&e));CloseHandle(h);return n;
}
struct Sink:wtp::ITrdNotifySink
{
    unsigned ready=0,lost=0,positions=0,accounts=0,trades=0,orders=0;
    double balance=0,available=0,dynbalance=0,previous=0,closeprofit=0,dynprofit=0,margin=0,fee=0,deposit=0,withdraw=0;
    std::thread::id owner=std::this_thread::get_id();std::function<void()> ready_hook;
    void own(){CHECK(owner==std::this_thread::get_id());}
    void on_trade(uint32_t,const char*,bool,double,double)override{own();++trades;}
    void on_order(uint32_t,const char*,bool,double,double,double,bool)override{own();++orders;}
    void on_position(const char*,bool,double,double,double,double,uint32_t)override{own();++positions;}
    void on_channel_ready()override{own();++ready;if(ready_hook)ready_hook();}
    void on_channel_lost()override{own();++lost;}
    void on_account(const char*,double pb,double b,double db,double av,double cp,double dp,double mg,double f,double de,double wi)override
    {own();++accounts;balance=b;available=av;dynbalance=db;previous=pb;closeprofit=cp;dynprofit=dp;margin=mg;fee=f;deposit=de;withdraw=wi;}
};
int main(int argc,char** argv)
{
    try{
        CHECK(argc==4);auto root=fs::absolute(argv[1]);auto dll=fs::canonical(argv[2]);std::string mode=argv[3];
        auto before=threads();
        auto module=LoadLibraryW(dll.c_str());CHECK(module);wchar_t actual[MAX_PATH];CHECK(GetModuleFileNameW(module,actual,MAX_PATH));CHECK(fs::equivalent(actual,dll));
        auto find=reinterpret_cast<wtp::ITraderApi*(*)(const char*)>(GetProcAddress(module,"findReadOnlyTrader"));
        auto pump=reinterpret_cast<int(*)(wtp::ITraderApi*,uint32_t)>(GetProcAddress(module,"pumpReadOnlyTrader"));
        auto wait=reinterpret_cast<int(*)(wtp::ITraderApi*,uint32_t,uint32_t)>(GetProcAddress(module,"waitReadOnlyTrader"));CHECK(wait);
        auto stop=reinterpret_cast<int(*)(wtp::ITraderApi*)>(GetProcAddress(module,"stopReadOnlyTrader"));
        auto inspect=reinterpret_cast<int(*)(wtp::ITraderApi*,Diagnostics*)>(GetProcAddress(module,"inspectReadOnlyTrader"));
        auto view=reinterpret_cast<int(*)(wtp::ITraderApi*,uint32_t,uint32_t,uint32_t,char*,uint32_t,uint32_t*)>(GetProcAddress(module,"inspectReadOnlyTraderView"));CHECK(view);
        auto readview=[&](wtp::ITraderApi* p,unsigned which,unsigned index){uint32_t n=0;int status=view(p,2,which,index,nullptr,0,&n);if(status==Unavailable)return std::string();CHECK(status==Capacity&&n>0);std::string result(n,'X');CHECK(view(p,2,which,index,&result[0],n-1,&n)==Capacity&&result[0]=='X');CHECK(view(p,2,which,index,&result[0],n,&n)==0&&result.back()==0);result.pop_back();return result;};
        auto destroy=reinterpret_cast<void(*)(wtp::ITraderApi*&)>(GetProcAddress(module,"deleteTrader"));
        auto create=reinterpret_cast<wtp::ITraderApi*(*)()>(GetProcAddress(module,"createTrader"));
        CHECK(find&&pump&&stop&&inspect&&destroy&&create);
        HANDLE gate_entered=nullptr,gate_release=nullptr;
        if(mode=="closing-gate"||mode=="post-read-gate"||mode=="get-read-gate"){
            gate_entered=CreateEventW(nullptr,TRUE,FALSE,nullptr);gate_release=CreateEventW(nullptr,TRUE,FALSE,nullptr);CHECK(gate_entered&&gate_release);
            if(mode=="closing-gate"){auto arm=reinterpret_cast<void(*)(HANDLE,HANDLE)>(GetProcAddress(module,"gh_qmt_http_test_closing_gate"));CHECK(arm);arm(gate_entered,gate_release);}
            else{auto arm=reinterpret_cast<bool(*)(unsigned,HANDLE,HANDLE)>(GetProcAddress(module,"gh_qmt_http_test_read_gate"));CHECK(arm&&arm(mode=="post-read-gate"?2:3,gate_entered,gate_release));}
        }else if(mode!="spurious-wake")CHECK(GetProcAddress(module,"gh_qmt_http_test_closing_gate")==nullptr);
        auto notify=reinterpret_cast<void(*)(wtp::ITraderApi*)>(GetProcAddress(module,"gh_nqh_test_notify_wait"));
        if(!gate_entered&&mode!="spurious-wake")CHECK(notify==nullptr);
        bool retained_after_timeout=false;long long first_close_ms=0;

        CHECK(fs::equivalent(fs::current_path()/"traders/TraderQMTReadOnly.dll",dll));
        CHECK(find(nullptr)==nullptr && find("unknown-instance")==nullptr);
        CHECK(pump(nullptr,1)==Invalid && stop(nullptr)==Invalid && wait(nullptr,PumpReady,1)==Invalid);
        auto fresh=create();CHECK(fresh);{uint32_t n=77;char sentinel='X';CHECK(view(fresh,1,0,0,&sentinel,1,&n)==Invalid&&n==0&&sentinel=='X');CHECK(view(fresh,2,0,0,nullptr,1,&n)==Invalid&&n==0);CHECK(view(fresh,2,0,1,nullptr,0,&n)==Invalid);CHECK(view(fresh,2,0,0,nullptr,0,nullptr)==Invalid);CHECK(view(fresh,2,1,0,nullptr,0,&n)==Unavailable);CHECK(!readview(fresh,0,0).empty());}CHECK(pump(fresh,1)==Unavailable);CHECK(wait(fresh,PumpReady,1)==Unavailable);destroy(fresh);CHECK(fresh==nullptr);
        {
        MappingGateData data;NativeLogObserver native_log;
        WTSLogger::init(R"({"root":{"async":false,"level":"info","sinks":[]}})",false,&native_log);
        CHECK(data.loadSessions((root/"sessions.json").string().c_str()));
        CHECK(data.loadCommodities((root/"commodities.json").string().c_str()));
        CHECK(data.loadContracts((root/"contracts.json").string().c_str()));
        auto cfg=WTSCfgLoader::load_from_file((root/"config.json").string().c_str());CHECK(cfg);
        NativeAdapterObserver adapter;Sink sink;adapter.addSink(&sink);
        CHECK(cfg->getString("adapter_id")=="nqb");
        bool initialized=adapter.init(cfg->getCString("adapter_id"),cfg,&data,nullptr);
        auto api=find("nqb-fixture");Diagnostics diag;
        if(!initialized){std::ofstream(root/"result.json")<<"{\"initialized\":false}";return 0;}
        CHECK(api);CHECK(inspect(api,&diag)==0);CHECK(diag.callbacks==0);CHECK(wait(api,PumpReady,1)==0);CHECK(inspect(api,&diag)==0&&diag.callbacks==0);
        {auto original=readview(api,0,0);uint32_t n=0;CHECK(view(api,2,4,0,nullptr,0,&n)==Unavailable);CHECK(readview(api,0,0)==original);}
        CHECK(pump(api,0)==Invalid && pump(api,33)==Invalid);
        Diagnostics bad;bad.version=99;CHECK(inspect(api,&bad)==Invalid);bad.version=1;bad.size=0;CHECK(inspect(api,&bad)==Invalid);
        auto duplicate=create();CHECK(duplicate);CHECK(!duplicate->init(cfg));destroy(duplicate);CHECK(!duplicate);CHECK(find("nqb-fixture")==api);
        if(mode=="map-late-position"||mode=="map-late-order"){data.contract_calls=0;data.gate_at=mode=="map-late-position"?1:3;data.gate_ms=cfg->getUInt32("request_ms")+40;}
        if(mode=="slow-connect")adapter.slow_connect_ms=cfg->getUInt32("round_ms")+40;
        auto started=std::chrono::steady_clock::now();CHECK(adapter.run());CHECK(inspect(api,&diag)==0);CHECK(diag.callbacks==0);CHECK(adapter.state()==wtp::TraderAdapter::AS_LOGINING);
        int wrong=0;std::thread alien([&]{Diagnostics d;CHECK(find("nqb-fixture")==nullptr);auto original=api;destroy(api);CHECK(api==original);wrong=pump(api,1);CHECK(stop(api)==WrongOwner);CHECK(wait(api,PumpReady,1)==WrongOwner);CHECK(inspect(api,&d)==WrongOwner);CHECK(api->queryPositions()==WrongOwner);});alien.join();CHECK(wrong==WrongOwner);
        int reentrant=0;
        sink.ready_hook=[&]{reentrant=pump(api,1);CHECK(wait(api,PumpReady,1)==Reentrant);if(mode=="delete-ready"){auto old=api;destroy(api);CHECK(api==old);}if(mode=="throw-ready")throw std::runtime_error("fixture sink failure");if(mode=="stop-ready")CHECK(stop(api)==0);if(mode=="release-ready")api->release();};
        // 功能样例须能完成其显式round预算；宿主只添加500ms有界余量。
        // 专门截止样例仍由插件自己的原request/round截止触发并断言。
        auto deadline=std::chrono::steady_clock::now()+std::chrono::milliseconds(std::max<uint64_t>(4000,uint64_t(cfg->getUInt32("round_ms"))+500));
        FILETIME cpu_create,cpu_exit,cpu_kernel,cpu_user;CHECK(GetThreadTimes(GetCurrentThread(),&cpu_create,&cpu_exit,&cpu_kernel,&cpu_user));
        auto cpu_start=(uint64_t(cpu_kernel.dwHighDateTime)<<32|cpu_kernel.dwLowDateTime)+(uint64_t(cpu_user.dwHighDateTime)<<32|cpu_user.dwLowDateTime);
        int pumped=0;bool delayed_pump=false;unsigned wait_calls=0,wait_deadlines=0;long long blocked_wait_ms=0;
        auto wait_owner=[&](unsigned events,unsigned timeout){auto begin=std::chrono::steady_clock::now();++wait_calls;int ready=wait(api,events,timeout);CHECK(ready>=0);blocked_wait_ms+=std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-begin).count();if(ready&DeadlineReached)++wait_deadlines;return ready;};
        CHECK(wait(api,0,1)==Invalid&&wait(api,16,1)==Invalid&&wait(api,PumpReady,120001)==Invalid);
        std::thread notifier;HANDLE notify_stop=nullptr;
        if(mode=="spurious-wake"){CHECK(notify);notify_stop=CreateEventW(nullptr,TRUE,FALSE,nullptr);CHECK(notify_stop);notifier=std::thread([&]{while(WaitForSingleObject(notify_stop,10)==WAIT_TIMEOUT)notify(api);});}
        if(mode=="wait-deadline"||mode=="spurious-wake"){auto frozen=readview(api,0,0);CHECK(wait_owner(PumpReady,100)==0);CHECK(wait_owner(PumpReady,100)==0);CHECK(readview(api,0,0)==frozen);CHECK(wait_owner(PumpReady,2000)&DeadlineReached);CHECK(readview(api,0,0)==frozen);CHECK(pump(api,1)==Failed);}
        while((mode!="wait-deadline"&&mode!="spurious-wake")&&std::chrono::steady_clock::now()<deadline){
            CHECK(inspect(api,&diag)==0);
            if(gate_entered&&(mode=="closing-gate"||diag.reads==1))CHECK(WaitForSingleObject(gate_entered,2000)==WAIT_OBJECT_0);
            if(gate_entered&&WaitForSingleObject(gate_entered,0)==WAIT_OBJECT_0){
                CHECK(stop(api)==0);pump(api,1);auto begin=std::chrono::steady_clock::now();adapter.release();first_close_ms=std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-begin).count();
                CHECK(inspect(api,&diag)==0&&diag.phase==static_cast<unsigned>(Phase::Closing)&&!diag.joined);std::ofstream(root/"view-timeout.json")<<readview(api,0,0);auto old=api;destroy(api);CHECK(api==old);retained_after_timeout=true;CHECK(find("nqb-fixture")==nullptr);auto frozen_close=readview(api,0,0);
                std::thread gate_opener([&]{HANDLE timer=CreateEventW(nullptr,TRUE,FALSE,nullptr);CHECK(timer);CHECK(WaitForSingleObject(timer,100)==WAIT_TIMEOUT);CloseHandle(timer);CHECK(SetEvent(gate_release));});
                // worker实际退出后，尚未再次owner release；纯值查看必须仍等于owner冻结状态。
                CHECK(wait_owner(WorkerDone,2000)==WorkerDone);gate_opener.join();CHECK(inspect(api,&diag)==0);
                CHECK(!diag.worker_live);CHECK(readview(api,0,0)==frozen_close);break;
            }
            if(mode=="late-pump"&&!delayed_pump&&diag.reads==1&&diag.ready_results){delayed_pump=true;HANDLE pause=CreateEventW(nullptr,TRUE,FALSE,nullptr);CHECK(pause);WaitForSingleObject(pause,cfg->getUInt32("request_ms")+10);CloseHandle(pause);}
            if(mode=="stop-before") {stop(api);break;}
            if(mode=="stop-pending" && diag.reads==1){stop(api);break;}
            if(mode=="late-result" && diag.reads==1){if(diag.ready_results){stop(api);break;}wait_owner(PumpReady|StopRequested,2000);continue;}
            if(mode=="stop-position" && (diag.delivered&1)){stop(api);break;}
            if(mode=="stop-order" && (diag.delivered&2)){stop(api);break;}
            if(mode=="stop-trade" && (diag.delivered&4)){stop(api);break;}
            pumped=pump(api,mode=="slow-connect"?32:1);if(pumped<0 || sink.ready)break;
            if(gate_entered&&(mode=="closing-gate"||diag.reads==1))continue;
            wait_owner(PumpReady|StopRequested,2000);
        }
        if(notifier.joinable()){CHECK(SetEvent(notify_stop));notifier.join();CloseHandle(notify_stop);}
        CHECK(GetThreadTimes(GetCurrentThread(),&cpu_create,&cpu_exit,&cpu_kernel,&cpu_user));auto cpu_finish=(uint64_t(cpu_kernel.dwHighDateTime)<<32|cpu_kernel.dwLowDateTime)+(uint64_t(cpu_user.dwHighDateTime)<<32|cpu_user.dwLowDateTime);double owner_cpu_ms=double(cpu_finish-cpu_start)/10000;
        CHECK(inspect(api,&diag)==0);auto preclose=diag;
        if(mode=="throw-ready"){uint32_t required=0;CHECK(view(api,2,4,0,nullptr,0,&required)==Unavailable&&required==0);}
        {std::ofstream(root/"view-preclose.json")<<readview(api,0,0);for(unsigned stage=1;stage<=4;++stage){unsigned count=diag.row_counts[stage-1];for(unsigned i=0;i<count;++i)std::ofstream(root/("view-"+std::to_string(stage)+"-"+std::to_string(i)+".json"))<<readview(api,stage,i);}}
        auto observed_ms=std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-started).count();
        auto long_position=adapter.getPosition("SSE.STK.600000",false,1),short_position=adapter.getPosition("SSE.STK.600000",false,2),long_avail=adapter.getPosition("SSE.STK.600000",true,1),short_avail=adapter.getPosition("SSE.STK.600000",true,2);
        auto pos=adapter.getPosition("SSE.STK.600000",false),avail=adapter.getPosition("SSE.STK.600000",true);
        auto etfpos=adapter.getPosition("SSE.ETF.510300",false),etfavail=adapter.getPosition("SSE.ETF.510300",true);
        auto undone=adapter.getUndoneQty("SSE.STK.600000");
        unsigned order_count=0;double order_price=0,order_left=0;
        if(auto orders=adapter.getOrders("600000")){order_count=orders->size();for(auto it=orders->begin();it!=orders->end();++it){auto o=static_cast<wtp::WTSOrderInfo*>(it->second);order_price=o->getPrice();order_left=o->getVolLeft();}orders->release();}
        CHECK(api->orderInsert(nullptr)==ReadOnly);CHECK(api->orderAction(nullptr)==ReadOnly);CHECK(!api->makeEntrustID(nullptr,0));
        auto same_requery=api->queryPositions();
        bool native_order_limit=adapter.checkOrderLimits("SSE.STK.600000");bool native_cancel_limit=adapter.checkCancelLimits("SSE.STK.600000");
        adapter.write(root,native_log);WTSLogger::registerHandler(nullptr);
        auto close_started=std::chrono::steady_clock::now();CHECK(stop(api)==0);pump(api,1);adapter.release();CHECK(inspect(api,&diag)==0);if(!diag.joined){CHECK(wait_owner(WorkerDone,3000)==WorkerDone);api->release();}CHECK(find("nqb-fixture")==nullptr);
        CHECK(inspect(api,&diag)==0);CHECK(diag.joined==1 && diag.worker_live==0 && diag.queued==0);
        CHECK(diag.owner_thread!=0 && (diag.worker_thread==0 || diag.owner_thread!=diag.worker_thread));
        CHECK(wait(api,WorkerDone,0)==WorkerDone);CHECK((wait(api,WorkerDone|StopRequested,0)&(WorkerDone|StopRequested))==(WorkerDone|StopRequested));
        auto callbacks=diag.callbacks;CHECK(pump(api,1)==Closed);api->release();CHECK(stop(api)==0);CHECK(inspect(api,&diag)==0 && diag.callbacks==callbacks);
        auto after=threads();auto close_ms=std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-close_started).count();
        rapidjson::Document result;result.SetObject();auto& a=result.GetAllocator();
        auto u=[&](const char* k,unsigned v){result.AddMember(rapidjson::Value(k,a),v,a);};
        auto n=[&](const char* k,double v){result.AddMember(rapidjson::Value(k,a),v,a);};
        n("owner_cpu_ms",owner_cpu_ms);u("wait_calls",wait_calls);u("wait_deadlines",wait_deadlines);n("blocked_wait_ms",double(blocked_wait_ms));u("native_order_limit",native_order_limit?1:0);u("native_cancel_limit",native_cancel_limit?1:0);u("mapping_gate_crossed",data.gate_crossed?1:0);u("retained_after_timeout",retained_after_timeout?1:0);n("first_close_ms",double(first_close_ms));u("native_self_match",adapter.isSelfMatched("SSE.STK.600000")?1:0);n("margin",sink.margin);n("previous_balance",sink.previous);n("close_profit",sink.closeprofit);n("dynamic_profit",sink.dynprofit);n("commission",sink.fee);n("deposit",sink.deposit);n("withdraw",sink.withdraw);PROCESS_MEMORY_COUNTERS memory={sizeof(memory)};CHECK(GetProcessMemoryInfo(GetCurrentProcess(),&memory,sizeof(memory)));n("peak_working_set_bytes",double(memory.PeakWorkingSetSize));n("observed_ms",static_cast<double>(observed_ms));n("close_ms",static_cast<double>(close_ms));u("preclose_results",preclose.ready_results);u("initialized",1);u("ready",sink.ready);u("lost",sink.lost);u("delivered",diag.delivered);u("callbacks",diag.callbacks);u("reads",diag.reads);u("polls",diag.polls);u("worker_live",diag.worker_live);u("joined",diag.joined);u("queue",diag.queued);u("discarded",diag.discarded);u("write_rejections",diag.write_rejections);u("account_presence",diag.account_presence);u("threads_before",before);u("threads_after",after);u("trade_pushes",sink.trades);u("order_pushes",sink.orders);u("orders",order_count);u("preclose_phase",preclose.phase);
        result.AddMember("owner_thread",diag.owner_thread,a);result.AddMember("worker_thread",diag.worker_thread,a);
        for(unsigned i=0;i<4;++i){auto key=std::string("observed_")+std::to_string(i);result.AddMember(rapidjson::Value(key.c_str(),a),rapidjson::Value(diag.observed_at[i],a),a);key=std::string("rows_")+std::to_string(i);u(key.c_str(),diag.row_counts[i]);}
        n("long_position",long_position);n("short_position",short_position);n("long_available",long_avail);n("short_available",short_avail);n("position",pos);n("available",avail);n("etf_position",etfpos);n("etf_available",etfavail);n("undone",undone);n("order_price",order_price);n("order_left",order_left);n("balance",sink.balance);n("dynbalance",sink.dynbalance);n("cash",sink.available);
        result.AddMember("error",diag.error,a);result.AddMember("reentrant",reentrant,a);result.AddMember("same_requery",same_requery,a);result.AddMember("reason",rapidjson::Value(diag.reason,a),a);
        rapidjson::StringBuffer buffer;rapidjson::Writer<rapidjson::StringBuffer> writer(buffer);result.Accept(writer);std::ofstream(root/"result.json")<<buffer.GetString();
        std::ofstream(root/"view-closed.json")<<readview(api,0,0);
        auto stale=api;destroy(api);CHECK(api==nullptr);CHECK(pump(stale,1)==Invalid);cfg->release();
        } // API、Adapter、sink及BaseData均已退栈，之后不再调用插件函数。
        CHECK(FreeLibrary(module));CHECK(GetModuleHandleW(dll.c_str())==module);
        // 固定原Adapter单次init恰有一次LoadLibrary且析构不平衡该引用；本隔离宿主接收这次已知引用。
        CHECK(FreeLibrary(module));CHECK(GetModuleHandleW(dll.c_str())==nullptr);
        std::ofstream(root/"unload-result.json")<<"{\"balanced_probe_reference\":true,\"balanced_fixed_adapter_reference\":true,\"module_absent\":true}";
        if(gate_entered)CloseHandle(gate_entered);if(gate_release)CloseHandle(gate_release);return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<std::endl;return 2;}
}
