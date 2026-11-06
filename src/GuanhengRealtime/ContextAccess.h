#pragma once
#include <functional>
#include "RealtimeBridge.h"
#include "../Includes/ICtaStraCtx.h"
#include "../Includes/WTSDataDef.hpp"
#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstring>
#include <limits>
#include <map>
#include <set>
#include <string>
#include <vector>

namespace guanheng {
// NRT与正式Session共用原上下文值复制；错误只携带有限码和是否已进入void setter。
struct CtaAccessError { int32_t code; bool partial=false; };
inline void cta_require(bool value,int32_t code=GH_RT_INVALID){if(!value)throw CtaAccessError{code};}
inline std::string cta_text(const char* value,size_t capacity){
    cta_require(value);const auto* end=static_cast<const char*>(std::memchr(value,0,capacity));
    cta_require(end&&end!=value);return {value,end};
}
inline GhRtBar cta_bar(const wtp::WTSBarStruct& source){
    GhRtBar out{};out.date=source.date;out.time=source.time;out.open=source.open;out.high=source.high;
    out.low=source.low;out.close=source.close;out.volume=source.vol;out.money=source.money;
    out.hold=source.hold;out.diff=source.add;
    for(double value:{out.open,out.high,out.low,out.close,out.volume,out.money,out.hold,out.diff})
        cta_require(std::isfinite(value),GH_RT_NATIVE);
    return out;
}
inline std::map<std::string,double> cta_targets(wtp::ICtaStraCtx& ctx,const std::set<std::string>& reads){
    std::map<std::string,double> values;
    ctx.enum_position([&](const char* code,double quantity){
        auto name=cta_text(code,GH_RT_CODE_BYTES);
        // 原上下文保留历史理论账；本接口只投影声明reads，实际账户范围仍由券商观察准入核验。
        if(!reads.count(name))return;
        cta_require(std::isfinite(quantity)&&values.size()<GH_RT_MAX_READS,GH_RT_NATIVE);
        cta_require(values.emplace(name,quantity).second,GH_RT_NATIVE);
    },false);
    return values;
}
inline GhRtFacts cta_facts(wtp::ICtaStraCtx& ctx){
    GhRtFacts out{};out.size=sizeof(out);out.date=ctx.stra_get_date();out.time=ctx.stra_get_time();
    out.tdate=ctx.stra_get_tdate();out.fund_pnl=ctx.stra_get_fund_data(0);
    cta_require(std::isfinite(out.fund_pnl),GH_RT_NATIVE);return out;
}
inline double cta_price(wtp::ICtaStraCtx& ctx,const std::string& code){
    const auto price=ctx.stra_get_price(code.c_str());
    cta_require(std::isfinite(price)&&price>0,GH_RT_UNKNOWN);return price;
}
inline GhRtPosition cta_position(wtp::ICtaStraCtx& ctx,const std::set<std::string>& reads,const std::string& code){
    const auto targets=cta_targets(ctx,reads);
    GhRtPosition out{};out.size=sizeof(out);out.flags=GH_RT_RAW_KNOWN;
    out.raw_position=ctx.stra_get_position(code.c_str(),false,"");out.raw_valid=ctx.stra_get_position(code.c_str(),true,"");
    out.first_entry=ctx.stra_get_first_entertime(code.c_str());out.last_entry=ctx.stra_get_last_entertime(code.c_str());
    out.last_exit=ctx.stra_get_last_exittime(code.c_str());
    cta_require(std::isfinite(out.raw_position)&&std::isfinite(out.raw_valid),GH_RT_NATIVE);
    // 原RT getter在新/已有标的的pending语义不同，保留原值及未知资格。
    out.actual_quantity=out.pending_quantity=out.enum_target=std::numeric_limits<double>::quiet_NaN();
    if(auto at=targets.find(code);at!=targets.end()){out.flags|=GH_RT_ENUM_PRESENT;out.enum_target=at->second;}
    return out;
}
inline std::vector<GhRtBar> cta_bars(wtp::ICtaStraCtx& ctx,const std::string& code,const std::string& period,
    uint32_t count,bool main){
    cta_require(count&&count<=GH_RT_MAX_BARS&&(period=="m1"||period=="d1"),GH_RT_CAPACITY);
    auto* raw=ctx.stra_get_bars(code.c_str(),period.c_str(),count,main);
    struct Slice {wtp::WTSKlineSlice* value;~Slice(){if(value)value->release();}} owned{raw};
    cta_require(raw&&raw->size(),GH_RT_UNKNOWN);cta_require(raw->size()<=count,GH_RT_CAPACITY);
    std::vector<GhRtBar> out;out.reserve(raw->size());
    for(uint32_t i=0;i<raw->size();++i){auto* bar=raw->at(i);cta_require(bar,GH_RT_NATIVE);out.push_back(cta_bar(*bar));}
    return out;
}
inline std::vector<GhRtTarget> cta_set_targets(wtp::ICtaStraCtx& ctx,const std::set<std::string>& reads,
    const std::set<std::string>& executions,const GhRtTarget* rows,uint32_t count,std::atomic<uint64_t>& setters,
    uint32_t max_targets=GH_RT_MAX_TARGETS,
    const std::function<void(const std::map<std::string,double>&)>& before_set={}){
    cta_require(rows&&count==executions.size()&&count&&count<=max_targets,GH_RT_CAPACITY);
    std::map<std::string,double> wanted;
    for(uint32_t i=0;i<count;++i){const auto code=cta_text(rows[i].symbol,sizeof(rows[i].symbol));const auto q=rows[i].quantity;
        cta_require(executions.count(code)&&std::isfinite(q)&&q>=0&&q<=9007199254740900.0
            &&std::floor(q)==q&&std::fmod(q,100.0)==0&&wanted.emplace(code,q).second);
    }
    for(const auto& item:wanted)cta_price(ctx,item.first);
    if(before_set)before_set(wanted); // 完整预验后交自有归属接缝；原RT默认无回调。
    try{
        for(const auto& item:wanted){setters.fetch_add(1);ctx.stra_set_position(item.first.c_str(),item.second,"gh_rt",0,0);}
        const auto actual=cta_targets(ctx,reads);std::vector<GhRtTarget> out;
        for(const auto& item:wanted){auto at=actual.find(item.first);cta_require(at!=actual.end()&&at->second==item.second,GH_RT_NATIVE);
            GhRtTarget value{};std::memcpy(value.symbol,item.first.c_str(),item.first.size()+1);value.quantity=at->second;out.push_back(value);}
        return out;
    }catch(...){throw CtaAccessError{GH_RT_NATIVE,true};}
}
}
