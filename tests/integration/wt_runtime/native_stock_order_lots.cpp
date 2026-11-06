// 原WT DLL公开执行器验收；替身只记录SDK调用，保留独立P/O，不连接现场。
#include <Windows.h>
#include <iostream>
#include <string>
#include <vector>
#include "Includes/ExecuteDefs.h"
#include "Includes/WTSVariant.hpp"
#include "Includes/WTSContractInfo.hpp"
#include "Includes/WTSSessionInfo.hpp"
using namespace wtp;
struct Context final:ExecuteContext {
    double total=0,remaining=0,sellable=0; std::vector<double> quantities; // 原P股数与原O未成交数，各自独立。
    unsigned buys=0,cancels=0,bulk_cancels=0; // SDK替身调用次数。
    double requested=0; // 实际买入请求份数，不自动增加P。
    WTSCommodityInfo* commodity=WTSCommodityInfo::create("ETF","synthetic","SSE","ALL","CHINA"); // Context持有。
    WTSSessionInfo* session=WTSSessionInfo::create("ALL","synthetic"); // Context持有。
    Context(){commodity->setCategory(CC_Stock);commodity->setTradingMode(TM_LongT1);commodity->setPriceTick(.001);session->addTradingSection(0,2359);}
    ~Context(){commodity->release();session->release();}
    WTSTickSlice* getTicks(const char*,uint32_t,uint64_t)override{return nullptr;}
    WTSTickData* grabLastTick(const char*)override{return nullptr;}
    double getPosition(const char*,bool valid=true,int32_t=3)override{return valid?sellable:total;}
    OrderMap* getOrders(const char*)override{return OrderMap::create();}
    double getUndoneQty(const char*)override{return remaining;}
    OrderIDs buy(const char*,double,double q,bool)override{++buys;requested+=q;remaining=q;quantities.push_back(q);return {7};}
    OrderIDs sell(const char*,double,double q,bool)override{remaining=-q;quantities.push_back(q);return {7};}
    bool cancel(uint32_t id)override{if(id!=7)return false;++cancels;return true;}
    OrderIDs cancel(const char*,bool,double)override{++bulk_cancels;return {7};}
    void writeLog(const char* text)override{std::cout<<text<<"\n";}
    WTSCommodityInfo* getCommodityInfo(const char*)override{return commodity;}
    WTSSessionInfo* getSessionInfo(const char*)override{return session;}
    uint64_t getCurTime()override{return 20261106143000000ULL;}
};

int wmain(int argc,wchar_t** argv){
 if(argc!=3)return 2;
 const std::wstring scenario(argv[2]);bool buy=scenario==L"buy";bool limited=scenario==L"limited";bool tail=scenario==L"tail";
 auto dll=LoadLibraryW(argv[1]);if(!dll)return 3;
 auto create=reinterpret_cast<FuncCreateExeFact>(GetProcAddress(dll,"createExecFact"));if(!create)return 4;
 auto* factory=create();auto* unit=factory->createExeUnit("WtStockMinImpactBorrowedExeUnit");if(!unit)return 5;
 Context context;context.total=buy?0:(tail?5300:25000);context.sellable=limited?2300:context.total;
 auto* config=WTSVariant::createObject();config->append("lots",10000.);config->append("min_order",100.);
 config->append("pricemode",0);config->append("offset",0);config->append("span",0u);config->append("expire",0u);
 config->append("byrate",false);config->append("is_cancel_unmanaged_order",false);config->append("replace_equal_position_target",true);
 unit->init(&context,"SSE.ETF.588000",config);unit->on_channel_ready();unit->set_position("SSE.ETF.588000",buy?25000.:0.);
 WTSTickStruct raw{};strcpy_s(raw.code,"SSE.ETF.588000");strcpy_s(raw.exchg,"SSE");raw.price=1.3;raw.action_date=raw.trading_date=20261106;raw.action_time=143000000;
 auto tick=[&]{auto* value=WTSTickData::create(raw);unit->on_tick(value);value->release();raw.action_time+=1000;};tick();
 const auto count=context.quantities.size();tick();bool ok=context.quantities.size()==count;
 for(int i=0;i<5;++i){if(context.remaining==0)break;double done=context.remaining;context.total+=done;if(!buy)context.sellable+=done;context.remaining=0;unit->on_order(7,"SSE.ETF.588000",buy,0,1.3,false);tick();}
 std::vector<double> expected=(limited?std::vector<double>{2300}:tail?std::vector<double>{5300}:std::vector<double>{10000,10000,5000});
 ok=ok&&context.quantities==expected;
 std::cout<<"RESULT "<<(ok?"PASS":"FAIL")<<" sizes=";for(double x:context.quantities)std::cout<<x<<",";std::cout<<"\n";
 factory->deleteExeUnit(unit);config->release();return ok?0:1;
}
