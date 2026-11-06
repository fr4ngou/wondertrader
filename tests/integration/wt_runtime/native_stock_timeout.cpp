// 原WT DLL公开执行器验收；替身只记录SDK调用，保留独立P/O，不连接现场。
#include <Windows.h>
#include <iostream>
#include <string>
#include "Includes/ExecuteDefs.h"
#include "Includes/WTSVariant.hpp"
#include "Includes/WTSContractInfo.hpp"
#include "Includes/WTSSessionInfo.hpp"
using namespace wtp;
struct Context final:ExecuteContext {
    double total=0,remaining=0; // 原P股数与原O未成交数，各自独立。
    unsigned buys=0,cancels=0,bulk_cancels=0; // SDK替身调用次数。
    double requested=0; // 实际买入请求份数，不自动增加P。
    WTSCommodityInfo* commodity=WTSCommodityInfo::create("ETF","synthetic","SSE","ALL","CHINA"); // Context持有。
    WTSSessionInfo* session=WTSSessionInfo::create("ALL","synthetic"); // Context持有。
    Context(){commodity->setCategory(CC_Stock);commodity->setTradingMode(TM_LongT1);commodity->setPriceTick(.001);session->addTradingSection(0,2359);}
    ~Context(){commodity->release();session->release();}
    WTSTickSlice* getTicks(const char*,uint32_t,uint64_t)override{return nullptr;}
    WTSTickData* grabLastTick(const char*)override{return nullptr;}
    double getPosition(const char*,bool=true,int32_t=3)override{return total;}
    OrderMap* getOrders(const char*)override{return OrderMap::create();}
    double getUndoneQty(const char*)override{return remaining;}
    OrderIDs buy(const char*,double,double q,bool)override{++buys;requested+=q;remaining=q;return {7};}
    OrderIDs sell(const char*,double,double,bool)override{throw std::runtime_error("unexpected sell");}
    bool cancel(uint32_t id)override{if(id!=7)return false;++cancels;return true;}
    OrderIDs cancel(const char*,bool,double)override{++bulk_cancels;return {7};}
    void writeLog(const char* text)override{std::cout<<text<<"\n";}
    WTSCommodityInfo* getCommodityInfo(const char*)override{return commodity;}
    WTSSessionInfo* getSessionInfo(const char*)override{return session;}
    uint64_t getCurTime()override{return 20261106143000000ULL;}
};
int wmain(int argc,wchar_t** argv){
    if(argc!=3)return 2;
    const std::wstring scenario(argv[2]);auto dll=LoadLibraryW(argv[1]);if(!dll)return 3;
    auto create=reinterpret_cast<FuncCreateExeFact>(GetProcAddress(dll,"createExecFact"));if(!create)return 4;
    auto* factory=create();auto* unit=factory->createExeUnit("WtStockMinImpactBorrowedExeUnit");if(!unit)return 5;
    Context context;const bool recovery=scenario==L"recovery";
    if(recovery){context.total=200;context.remaining=800;}
    auto* config=WTSVariant::createObject();config->append("lots",1000.);config->append("min_order",100.);
    config->append("pricemode",0);config->append("offset",0);config->append("span",0u);
    config->append("expire",scenario==L"disabled"?0u:1u);
    config->append("byrate",false);config->append("is_cancel_unmanaged_order",recovery);
    config->append("replace_equal_position_target",true);
    unit->init(&context,"SSE.ETF.588000",config);unit->on_channel_ready();unit->set_position("SSE.ETF.588000",1000.);
    WTSTickStruct raw{};strcpy_s(raw.code,"SSE.ETF.588000");strcpy_s(raw.exchg,"SSE");
    raw.price=1.3;raw.action_date=raw.trading_date=20261106;raw.action_time=143000000;
    auto tick=[&]{auto* value=WTSTickData::create(raw);unit->on_tick(value);value->release();};tick();
    bool ok=false;
    if(recovery)ok=context.bulk_cancels==1&&context.buys==0&&context.remaining==800&&context.total==200;
    else {
        Sleep(1100);raw.action_time+=1000;tick();
        if(scenario==L"disabled")ok=context.buys==1&&context.cancels==0;
        else {
            ok=context.buys==1&&context.cancels>0&&context.remaining==1000;
            // 部成部撤后原P为200、原O终态；同一原执行器只补800，不重发1000。
            context.total=200;context.remaining=0;
            unit->on_order(7,"SSE.ETF.588000",true,800,1.3,true);
            ok=ok&&context.buys==2&&context.requested==1800&&context.remaining==800;
        }
    }
    factory->deleteExeUnit(unit);config->release();
    std::cout<<"RESULT "<<(ok?"PASS":"FAIL")<<" buys="<<context.buys<<" cancels="<<context.cancels<<" bulk="<<context.bulk_cancels<<"\n";
    return ok?0:1;
}
