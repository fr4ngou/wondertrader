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
#include <filesystem>
#include <fstream>
#include <iostream>
#include <thread>
#include <chrono>
#include <stdexcept>
#include <functional>
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
    double balance=0,available=0,dynbalance=0;
    std::thread::id owner=std::this_thread::get_id();std::function<void()> ready_hook;
    void own(){CHECK(owner==std::this_thread::get_id());}
    void on_trade(uint32_t,const char*,bool,double,double)override{own();++trades;}
    void on_order(uint32_t,const char*,bool,double,double,double,bool)override{own();++orders;}
    void on_position(const char*,bool,double,double,double,double,uint32_t)override{own();++positions;}
    void on_channel_ready()override{own();++ready;if(ready_hook)ready_hook();}
    void on_channel_lost()override{own();++lost;}
    void on_account(const char*,double,double b,double db,double av,double,double,double,double,double,double)override
    {own();++accounts;balance=b;available=av;dynbalance=db;}
};
int main(int argc,char** argv)
{
    try{
        CHECK(argc==4);auto root=fs::absolute(argv[1]);auto dll=fs::canonical(argv[2]);std::string mode=argv[3];
        auto before=threads();
        auto module=LoadLibraryW(dll.c_str());CHECK(module);wchar_t actual[MAX_PATH];CHECK(GetModuleFileNameW(module,actual,MAX_PATH));CHECK(fs::equivalent(actual,dll));
        auto find=reinterpret_cast<wtp::ITraderApi*(*)(const char*)>(GetProcAddress(module,"findReadOnlyTrader"));
        auto pump=reinterpret_cast<int(*)(wtp::ITraderApi*,uint32_t)>(GetProcAddress(module,"pumpReadOnlyTrader"));
        auto stop=reinterpret_cast<int(*)(wtp::ITraderApi*)>(GetProcAddress(module,"stopReadOnlyTrader"));
        auto inspect=reinterpret_cast<int(*)(wtp::ITraderApi*,Diagnostics*)>(GetProcAddress(module,"inspectReadOnlyTrader"));
        auto destroy=reinterpret_cast<void(*)(wtp::ITraderApi*&)>(GetProcAddress(module,"deleteTrader"));
        auto create=reinterpret_cast<wtp::ITraderApi*(*)()>(GetProcAddress(module,"createTrader"));
        CHECK(find&&pump&&stop&&inspect&&destroy&&create);
        CHECK(fs::equivalent(fs::current_path()/"traders/TraderQMTReadOnly.dll",dll));
        CHECK(find(nullptr)==nullptr && find("unknown-instance")==nullptr);
        CHECK(pump(nullptr,1)==Invalid && stop(nullptr)==Invalid);
        auto fresh=create();CHECK(fresh);CHECK(pump(fresh,1)==Unavailable);destroy(fresh);CHECK(fresh==nullptr);
        WTSBaseDataMgr data;
        CHECK(data.loadSessions((root/"sessions.json").string().c_str()));
        CHECK(data.loadCommodities((root/"commodities.json").string().c_str()));
        CHECK(data.loadContracts((root/"contracts.json").string().c_str()));
        auto cfg=WTSCfgLoader::load_from_file((root/"config.json").string().c_str());CHECK(cfg);
        wtp::TraderAdapter adapter;Sink sink;adapter.addSink(&sink);
        CHECK(cfg->getString("adapter_id")=="nqb");
        bool initialized=adapter.init(cfg->getCString("adapter_id"),cfg,&data,nullptr);
        auto api=find("nqb-fixture");Diagnostics diag;
        if(!initialized){std::ofstream(root/"result.json")<<"{\"initialized\":false}";return 0;}
        CHECK(api);CHECK(inspect(api,&diag)==0);CHECK(diag.callbacks==0);
        CHECK(pump(api,0)==Invalid && pump(api,33)==Invalid);
        Diagnostics bad;bad.version=99;CHECK(inspect(api,&bad)==Invalid);bad.version=1;bad.size=0;CHECK(inspect(api,&bad)==Invalid);
        auto duplicate=create();CHECK(duplicate);CHECK(!duplicate->init(cfg));destroy(duplicate);CHECK(!duplicate);CHECK(find("nqb-fixture")==api);
        auto started=std::chrono::steady_clock::now();CHECK(adapter.run());CHECK(inspect(api,&diag)==0);CHECK(diag.callbacks==0);CHECK(adapter.state()==wtp::TraderAdapter::AS_LOGINING);
        int wrong=0;std::thread alien([&]{Diagnostics d;CHECK(find("nqb-fixture")==nullptr);wrong=pump(api,1);CHECK(stop(api)==WrongOwner);CHECK(inspect(api,&d)==WrongOwner);CHECK(api->queryPositions()==WrongOwner);});alien.join();CHECK(wrong==WrongOwner);
        int reentrant=0;
        sink.ready_hook=[&]{reentrant=pump(api,1);if(mode=="throw-ready")throw std::runtime_error("fixture sink failure");if(mode=="stop-ready")CHECK(stop(api)==0);if(mode=="release-ready")api->release();};
        auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(4);
        int pumped=0;
        while(std::chrono::steady_clock::now()<deadline){
            CHECK(inspect(api,&diag)==0);
            if(mode=="stop-before") {stop(api);break;}
            if(mode=="stop-pending" && diag.reads==1){stop(api);break;}
            if(mode=="late-result" && diag.reads==1){if(diag.ready_results){stop(api);break;}std::this_thread::yield();continue;}
            if(mode=="stop-position" && (diag.delivered&1)){stop(api);break;}
            if(mode=="stop-order" && (diag.delivered&2)){stop(api);break;}
            if(mode=="stop-trade" && (diag.delivered&4)){stop(api);break;}
            pumped=pump(api,1);if(pumped<0 || sink.ready)break;
            std::this_thread::yield();
        }
        CHECK(inspect(api,&diag)==0);auto preclose=diag;
        auto observed_ms=std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-started).count();
        auto pos=adapter.getPosition("SSE.STK.600000",false),avail=adapter.getPosition("SSE.STK.600000",true);
        auto etfpos=adapter.getPosition("SSE.ETF.510300",false),etfavail=adapter.getPosition("SSE.ETF.510300",true);
        auto undone=adapter.getUndoneQty("SSE.STK.600000");
        unsigned order_count=0;double order_price=0,order_left=0;
        if(auto orders=adapter.getOrders("600000")){order_count=orders->size();for(auto it=orders->begin();it!=orders->end();++it){auto o=static_cast<wtp::WTSOrderInfo*>(it->second);order_price=o->getPrice();order_left=o->getVolLeft();}orders->release();}
        CHECK(api->orderInsert(nullptr)==ReadOnly);CHECK(api->orderAction(nullptr)==ReadOnly);CHECK(!api->makeEntrustID(nullptr,0));
        auto same_requery=api->queryPositions();
        auto close_started=std::chrono::steady_clock::now();CHECK(stop(api)==0);pump(api,1);adapter.release();CHECK(find("nqb-fixture")==nullptr);
        CHECK(inspect(api,&diag)==0);CHECK(diag.joined==1 && diag.worker_live==0 && diag.queued==0);
        CHECK(diag.owner_thread!=0 && (diag.worker_thread==0 || diag.owner_thread!=diag.worker_thread));
        auto callbacks=diag.callbacks;CHECK(pump(api,1)==Closed);api->release();CHECK(stop(api)==0);CHECK(inspect(api,&diag)==0 && diag.callbacks==callbacks);
        auto after=threads();auto close_ms=std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-close_started).count();
        rapidjson::Document result;result.SetObject();auto& a=result.GetAllocator();
        auto u=[&](const char* k,unsigned v){result.AddMember(rapidjson::Value(k,a),v,a);};
        auto n=[&](const char* k,double v){result.AddMember(rapidjson::Value(k,a),v,a);};
        n("observed_ms",static_cast<double>(observed_ms));n("close_ms",static_cast<double>(close_ms));u("preclose_results",preclose.ready_results);u("initialized",1);u("ready",sink.ready);u("lost",sink.lost);u("delivered",diag.delivered);u("callbacks",diag.callbacks);u("reads",diag.reads);u("polls",diag.polls);u("worker_live",diag.worker_live);u("joined",diag.joined);u("queue",diag.queued);u("discarded",diag.discarded);u("write_rejections",diag.write_rejections);u("account_presence",diag.account_presence);u("threads_before",before);u("threads_after",after);u("trade_pushes",sink.trades);u("order_pushes",sink.orders);u("orders",order_count);u("preclose_phase",preclose.phase);
        result.AddMember("owner_thread",diag.owner_thread,a);result.AddMember("worker_thread",diag.worker_thread,a);
        for(unsigned i=0;i<4;++i){auto key=std::string("observed_")+std::to_string(i);result.AddMember(rapidjson::Value(key.c_str(),a),rapidjson::Value(diag.observed_at[i],a),a);key=std::string("rows_")+std::to_string(i);u(key.c_str(),diag.row_counts[i]);}
        n("position",pos);n("available",avail);n("etf_position",etfpos);n("etf_available",etfavail);n("undone",undone);n("order_price",order_price);n("order_left",order_left);n("balance",sink.balance);n("dynbalance",sink.dynbalance);n("cash",sink.available);
        result.AddMember("error",diag.error,a);result.AddMember("reentrant",reentrant,a);result.AddMember("same_requery",same_requery,a);result.AddMember("reason",rapidjson::Value(diag.reason,a),a);
        rapidjson::StringBuffer buffer;rapidjson::Writer<rapidjson::StringBuffer> writer(buffer);result.Accept(writer);std::ofstream(root/"result.json")<<buffer.GetString();
        auto stale=api;destroy(api);CHECK(api==nullptr);CHECK(pump(stale,1)==Invalid);FreeLibrary(module);cfg->release();return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<std::endl;return 2;}
}
