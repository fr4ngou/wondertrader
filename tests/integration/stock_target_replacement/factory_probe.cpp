// 隔离SDK替身：调用原DLL公开工厂/执行单元，记录发单，不连接任何现场。
#include <Windows.h>
#include <iostream>
#include <string>
#include <vector>
#include <map>
#include "Includes/ExecuteDefs.h"
#include "Includes/WTSVariant.hpp"
#include "Includes/WTSContractInfo.hpp"
#include "Includes/WTSSessionInfo.hpp"
using namespace wtp;
struct Context final : ExecuteContext {
    double total=22000, available=22000; // 完整P总量与可卖量分别提供。
    unsigned buys=0,sells=0; // SDK替身调用次数。
    double buy_quantity=0,sell_quantity=0,undone=0; // 实际请求份数及独立活动单余量；不自动改变P。
    std::map<uint32_t,double> active_orders; // 独立SDK活动单：原本地ID→带方向余量，买正卖负。
    unsigned cancels=0; // 撤单实际请求次数，两个公开重载均记录。
    WTSCommodityInfo* commodity=WTSCommodityInfo::create("ETF","synthetic","SZSE","ALL","CHINA");
    WTSSessionInfo* session=WTSSessionInfo::create("ALL","synthetic");
    Context(){commodity->setCategory(CC_Stock);commodity->setTradingMode(TM_LongT1);commodity->setPriceTick(.001);session->addTradingSection(0,2359);}
    ~Context(){commodity->release();session->release();}
    WTSTickSlice* getTicks(const char*,uint32_t,uint64_t)override{return nullptr;}
    WTSTickData* grabLastTick(const char*)override{return nullptr;}
    double getPosition(const char*,bool valid=true,int32_t=3)override{return valid?available:total;}
    OrderMap* getOrders(const char*)override{return OrderMap::create();}
    double getUndoneQty(const char*)override{double value=0;for(const auto& row:active_orders)value+=row.second;return value;}
    OrderIDs buy(const char*,double,double q,bool)override{++buys;buy_quantity+=q;std::cout<<"BUY "<<q<<"\n";return {};}
    OrderIDs sell(const char*,double,double q,bool)override{++sells;sell_quantity+=q;std::cout<<"SELL "<<q<<"\n";return {};}
    bool cancel(uint32_t id)override{++cancels;return active_orders.erase(id)!=0;}
    OrderIDs cancel(const char*,bool buy,double)override{
        ++cancels;OrderIDs removed;
        for(auto it=active_orders.begin();it!=active_orders.end();){
            if((it->second>0)==buy){removed.push_back(it->first);it=active_orders.erase(it);}else ++it;
        }
        return removed;
    }
    void writeLog(const char* m)override{std::cout<<m<<"\n";}
    WTSCommodityInfo* getCommodityInfo(const char*)override{return commodity;}
    WTSSessionInfo* getSessionInfo(const char*)override{return session;}
    uint64_t getCurTime()override{return 20261106093814000ULL;}
};
int wmain(int argc,wchar_t**argv){
    if(argc!=10&&argc!=11)return 2;
    auto dll=LoadLibraryW(argv[1]);if(!dll)return 3;
    auto create=reinterpret_cast<FuncCreateExeFact>(GetProcAddress(dll,"createExecFact"));
    if(!create)create=reinterpret_cast<FuncCreateExeFact>(GetProcAddress(dll,"createExeFact"));
    if(!create)return 4;
    auto* factory=create();Context context;
    context.total=_wtof(argv[4]);context.available=_wtof(argv[5]);context.undone=_wtof(argv[7]);
    if(context.undone)context.active_orders.emplace(4242,context.undone);
    const std::wstring wide_factory(argv[9]);std::string selected;
    for(auto ch:wide_factory){if(ch>127)return 8;selected.push_back(static_cast<char>(ch));}
    auto* unit=factory->createExeUnit(selected.c_str());if(!unit)return 5;
    auto* config=WTSVariant::createObject();config->append("lots",1000.);config->append("min_order",100.);
    config->append("pricemode",0);config->append("offset",0);config->append("expire",0u);config->append("span",0u);
    config->append("byrate",false);config->append("is_cancel_unmanaged_order",false);
    const std::wstring mode(argv[8]);
    if(mode==L"true"||mode==L"false")config->append("replace_equal_position_target",mode==L"true");
    else if(mode!=L"default")return 7;
    const std::wstring wide_code(argv[2]);const std::string code_value(wide_code.begin(),wide_code.end());const char* code=code_value.c_str();
    // 原工厂临时getter会消费引用；本替身显式提供该引用，Borrowed路径继续只借用。
    if(selected=="WtStockMinImpactExeUnit")context.commodity->retain();
    unit->init(&context,code,config);unit->on_channel_ready();
    // 冻结旧理论目标先进入原执行器，再交本轮与完整P相等的卖出阶段绝对目标。
    const double old_target=_wtof(argv[3]),new_target=_wtof(argv[6]);
    if(old_target>=0)unit->set_position(code,old_target);
    unit->set_position(code,new_target);
    WTSTickStruct raw={};strcpy_s(raw.code,code);strcpy_s(raw.exchg,"SZSE");
    raw.price=.728;raw.action_date=raw.trading_date=20261106;raw.action_time=93814000;
    auto* tick=WTSTickData::create(raw);unit->on_tick(tick);tick->release();
    if(argc==11){
        // 首笔真实买入后完整P为23000、可卖仍22000；下一轮相同绝对目标再次被提前返回。
        context.total+=context.buy_quantity;unit->set_position(code,new_target);
        raw.action_time=93914000;tick=WTSTickData::create(raw);unit->on_tick(tick);tick->release();
    }
    std::cout<<"RESULT {\"buys\":"<<context.buys<<",\"sells\":"<<context.sells
        <<",\"buy_quantity\":"<<context.buy_quantity<<",\"sell_quantity\":"<<context.sell_quantity
        <<",\"undone_unchanged\":"<<context.getUndoneQty(code)<<",\"cancel_calls\":"<<context.cancels
        <<",\"original_order_retained\":"<<(context.active_orders.count(4242)?"true":"false")<<"}\n";
    factory->deleteExeUnit(unit);config->release();return 0;
}
