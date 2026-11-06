// 真实WT上下文与Factory回归；行情/切片为显式合成来源，不运行账户或执行器。
#include "WtCore/CtaStraContext.h"
#include "WtCore/WtCtaEngine.h"
#include "WtCore/WtHelper.h"
#include "WTSTools/WTSHotMgr.h"
#include "Includes/CtaStrategyDefs.h"
#include <Windows.h>
#include <cstring>
#include <memory>
#include <map>
#include <string>
#include <vector>

namespace {
uint32_t fault_after=0;
std::map<std::string,std::map<std::string,double>> final_targets;
class Engine final : public wtp::WtCtaEngine {
    WTSHotMgr hot;
public:
    Engine(){_hot_mgr=&hot;set_date_time(20261106,1500);set_trading_date(20261106);}
};
class Context final : public CtaStraContext {
    wtp::WTSBarStruct bar{};
    uint32_t setter_calls=0;
public:
    Context(Engine& engine,const char* id):CtaStraContext(&engine,id,0){
        bar.date=20261106;bar.time=202611061500ULL-199000000000ULL;
        bar.open=bar.high=bar.low=bar.close=10;bar.vol=100;
    }
    // 原目标登记、枚举、用户数据和文件输出保持CtaStraBaseCtx原实现。
    double stra_get_price(const char* code)override{_price_map[code]=10;return 10;}
    wtp::WTSKlineSlice* stra_get_bars(const char* code,const char*,uint32_t count,bool)override{
        return count?wtp::WTSKlineSlice::create(code,wtp::KP_Minute1,1,&bar,1):nullptr;
    }
    void stra_sub_ticks(const char*)override{}
    void stra_sub_bar_events(const char*,const char*)override{}
    void stra_set_position(const char* code,double quantity,const char* tag,double limit,double stop)override{
        if(fault_after&&++setter_calls==fault_after)throw 1;
        CtaStraContext::stra_set_position(code,quantity,tag,limit,stop);
    }
};
}
extern "C" __declspec(dllexport) void __cdecl gh_managed_v2_probe_fault(uint32_t after){fault_after=after;}
extern "C" __declspec(dllexport) double __cdecl gh_managed_v2_probe_target(const char* id,const char* code){
    auto at=final_targets.find(id);if(at==final_targets.end())return -1;
    auto row=at->second.find(code);return row==at->second.end()?-1:row->second;
}
extern "C" __declspec(dllexport) int __cdecl gh_managed_v2_probe(
    const char* library,const char* output,const char* const* ids,uint32_t count){
    if(!library||!output||!ids||!count)return 1;
    auto module=LoadLibraryA(library);if(!module)return 2;
    using Create=ICtaStrategyFact*(*)();
    auto create=reinterpret_cast<Create>(GetProcAddress(module,"createStrategyFact"));
    if(!create)return 3;auto* factory=create();if(!factory)return 4;
    try{
        WtHelper::setGenerateDir(output);Engine engine;
        std::vector<std::unique_ptr<Context>> contexts;
        std::vector<CtaStrategy*> strategies;
        for(uint32_t i=0;i<count;++i){
            auto* strategy=factory->createStrategy("Core",ids[i]);if(!strategy)return 5;
            if(!strategy->init(nullptr))return 6;
            auto context=std::make_unique<Context>(engine,ids[i]);context->set_strategy(strategy);
            context->on_init();strategies.push_back(strategy);contexts.push_back(std::move(context));
        }
        for(uint32_t i=0;i<count;++i)contexts[i]->on_calculate(20261106,1500);
        for(uint32_t i=0;i<count;++i)contexts[i]->enum_position([&](const char* code,double quantity){
            final_targets[ids[i]][code]=quantity;
        });
        contexts.clear();
        for(auto* strategy:strategies)if(!factory->deleteStrategy(strategy))return 7;
        FreeLibrary(module);return 0;
    }catch(...){return 8;}
}
