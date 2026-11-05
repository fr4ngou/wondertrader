#include "ManagedStrategyBridge.h"
#include "ContextAccess.h"
#include "../Includes/CtaStrategyDefs.h"
#include <Windows.h>
#include <memory>
#include <mutex>

namespace {
using namespace guanheng;
using namespace wtp;
struct Binding {
    GhMsConfig config{};GhRtCallback callback=nullptr;void* user=nullptr;
    std::set<std::string> reads,executions;bool created=false,main_registered=false;
    std::mutex quote_mutex; // 原tick回调和原epoch读取共用，槽在configure预分配。
    std::map<std::string,GhMsQuote> quotes; // 仅固定reads集合，每证券最新已应用tick。
};
struct Owner {
    std::mutex mutex;DWORD controller=0;bool frozen=false;
    std::map<std::string,std::unique_ptr<Binding>> bindings;
    std::atomic<uint32_t> configured{0},created{0},destroyed{0},active{0};
    std::atomic<int32_t> failure{0};
    std::atomic<uint64_t> epochs{0},callbacks{0},setters{0};
    void fail(int32_t code) {int32_t expected=0;failure.compare_exchange_strong(expected,code);}
};
Owner& owner(){static auto* value=new Owner;return *value;}
uint64_t token(){return static_cast<uint64_t>(reinterpret_cast<uintptr_t>(&owner()));}
constexpr const char* state_key="guanheng.quantity.state.v1";
std::string state_value(const char* value){
    cta_require(value,GH_RT_NATIVE);
    for(uint32_t length=0;length<=GH_MS_STATE_BYTES;++length){
        if(!value[length])return {value,length};
        cta_require(value[length]>=32&&value[length]<127,GH_RT_INVALID);
    }
    throw CtaAccessError{GH_RT_CAPACITY};
}
// 原CodeHelper各段为32字节，原bar key为64字节；在进入原上下文前限制整个标准代码。
std::string configured_symbol(const char* code){
    auto value=cta_text(code,GH_RT_CODE_BYTES);
    cta_require(value.size()<MAX_INSTRUMENT_LENGTH);
    size_t segment=0,dots=0;
    for(unsigned char c:value){
        cta_require(c>32&&c<127);
        if(c=='.'){cta_require(segment&&++dots<=2);segment=0;}else ++segment;
    }
    cta_require(dots&&segment);
    cta_require(dots!=2||segment>1||(value.back()!='+'&&value.back()!='-'));
    return value;
}
struct Borrow {Binding* binding;ICtaStraCtx* ctx;uint64_t epoch;uint32_t kind;DWORD thread;};
thread_local Borrow* borrowed=nullptr;
Borrow& access(uint64_t epoch,bool schedule=false){
    cta_require(borrowed&&borrowed->epoch==epoch,GH_RT_BORROW);
    cta_require(borrowed->thread==GetCurrentThreadId(),GH_RT_THREAD);
    cta_require(!owner().failure.load(),GH_RT_STATE);
    cta_require(schedule?borrowed->kind==GH_RT_SCHEDULE:
        borrowed->kind==GH_RT_INIT||borrowed->kind==GH_RT_SCHEDULE,GH_RT_STATE);
    return *borrowed;
}
std::string symbol(Borrow& b,const char* code){
    auto value=cta_text(code,GH_RT_CODE_BYTES);cta_require(b.binding->reads.count(value));return value;
}
template<class Function>int32_t api(Function call)noexcept{
    try{return call();}catch(const CtaAccessError& error){
        if(error.code==GH_RT_NATIVE||error.partial)owner().fail(GH_RT_NATIVE);return error.code;
    }catch(...){owner().fail(GH_RT_NATIVE);return GH_RT_NATIVE;}
}
void emit(Binding& binding,ICtaStraCtx* ctx,uint32_t kind,uint32_t date=0,uint32_t time=0,
    uint32_t tdate=0,const char* code=nullptr,const char* period=nullptr,const WTSBarStruct* bar=nullptr)noexcept{
    auto& o=owner();if(o.failure.load())return;
    if(o.active.fetch_add(1)!=0){o.active.fetch_sub(1);o.fail(GH_RT_THREAD);return;}
    struct Guard {Owner& o;~Guard(){borrowed=nullptr;o.active.fetch_sub(1);}} guard{o};
    try{
        cta_require(ctx&&ctx->name()==std::string(binding.config.strategy_id)&&binding.callback,GH_RT_NATIVE);
        GhRtEvent event{};event.size=sizeof(event);event.kind=kind;event.epoch=o.epochs.fetch_add(1)+1;
        event.owner_token=token();event.thread_id=GetCurrentThreadId();event.ctx_id=ctx->id();
        event.date=date?date:ctx->stra_get_date();event.time=time?time:ctx->stra_get_time();
        event.tdate=tdate?tdate:ctx->stra_get_tdate();
        if(code){auto value=cta_text(code,sizeof(event.symbol));cta_require(binding.reads.count(value));
            std::memcpy(event.symbol,value.c_str(),value.size()+1);}
        if(period){auto value=cta_text(period,sizeof(event.period));std::memcpy(event.period,value.c_str(),value.size()+1);}
        if(bar)event.bar=cta_bar(*bar);
        Borrow borrow{&binding,ctx,event.epoch,kind,GetCurrentThreadId()};borrowed=&borrow;o.callbacks.fetch_add(1);
        if(binding.callback(&event,binding.user)!=0)o.fail(GH_RT_CALLBACK);
    }catch(...){o.fail(GH_RT_NATIVE);}
}
class Strategy final:public CtaStrategy {
    Binding& binding;
public:
    Strategy(const char* id,Binding& value):CtaStrategy(id),binding(value){}
    ~Strategy()override{owner().destroyed.fetch_add(1);}
    const char* getName()override{return "Core";}
    const char* getFactName()override{return "GuanhengManagedStrategy";}
    bool init(WTSVariant*)override{return !owner().failure.load();}
    void on_init(ICtaStraCtx* ctx)override{
        try{
            for(const auto& code:binding.reads)ctx->stra_sub_ticks(code.c_str());
            ctx->stra_sub_bar_events(binding.config.main_symbol,"m1");emit(binding,ctx,GH_RT_INIT);
            if(!binding.main_registered)owner().fail(GH_RT_STATE);
        }catch(...){owner().fail(GH_RT_NATIVE);}
        // 初始化错误沿宿主既有启动异常边界传播，避免继续启动行情生产者。
        if(const auto failure=owner().failure.load())throw CtaAccessError{failure};
    }
    void on_tick(ICtaStraCtx*,const char* code,WTSTickData* tick)override{
        try {
            cta_require(code);
            // 原WT可沿历史理论仓位继续订阅退役证券；当前桥只观察声明reads，不扩大缓存或执行集合。
            if(!binding.reads.count(code))return;
            cta_require(tick);std::lock_guard<std::mutex> guard(binding.quote_mutex);
            auto at=binding.quotes.find(code);cta_require(at!=binding.quotes.end());
            const auto& raw=tick->getTickStruct();
            cta_require(std::isfinite(raw.price)&&raw.price>0&&raw.action_date&&raw.action_time,GH_RT_UNKNOWN);
            GhMsQuote value{};value.size=sizeof(value);value.version=1;value.action_date=raw.action_date;
            value.action_time=raw.action_time;value.price_cny=raw.price;at->second=value;
        }catch(...){owner().fail(GH_RT_NATIVE);}
    }
    void on_session_begin(ICtaStraCtx* ctx,uint32_t date)override{emit(binding,ctx,GH_RT_SESSION_BEGIN,0,0,date);}
    void on_session_end(ICtaStraCtx* ctx,uint32_t date)override{emit(binding,ctx,GH_RT_SESSION_END,0,0,date);}
    void on_bar(ICtaStraCtx* ctx,const char* code,const char* period,WTSBarStruct* bar)override{
        emit(binding,ctx,GH_RT_BAR,0,0,0,code,period,bar);}
    void on_schedule(ICtaStraCtx* ctx,uint32_t date,uint32_t time)override{emit(binding,ctx,GH_RT_SCHEDULE,date,time);}
};
class Factory final:public ICtaStrategyFact {
public:
    const char* getName()override{return "GuanhengManagedStrategy";}
    void enumStrategy(FuncEnumStrategyCallback callback)override{if(callback)callback(getName(),"Core",true);}
    CtaStrategy* createStrategy(const char* name,const char* id)override{
        try{
            auto& o=owner();std::lock_guard<std::mutex> guard(o.mutex);
            cta_require(name&&std::strcmp(name,"Core")==0&&id,GH_RT_STATE);
            auto at=o.bindings.find(id);cta_require(at!=o.bindings.end()&&!at->second->created&&!o.failure.load(),GH_RT_STATE);
            auto result=std::make_unique<Strategy>(id,*at->second);at->second->created=true;o.frozen=true;o.created.fetch_add(1);
            return result.release();
        }catch(...){owner().fail(GH_RT_NATIVE);return nullptr;}
    }
    bool deleteStrategy(CtaStrategy* value)override{
        auto* strategy=dynamic_cast<Strategy*>(value);if(!strategy)return false;delete strategy;return true;
    }
};
Factory& factory(){static auto* value=new Factory;return *value;}
}
extern "C" {
GH_RT_API ICtaStrategyFact* createStrategyFact(){return &factory();}
GH_RT_API void deleteStrategyFact(ICtaStrategyFact*& value){if(value==&factory())value=nullptr;}
uint32_t GH_RT_CALL gh_ms_abi_version(void){return GH_MS_ABI_VERSION;}
uint32_t GH_RT_CALL gh_ms_read_only_abi_version(void){return 1;}
uint64_t GH_RT_CALL gh_ms_layout(uint32_t id){
    switch(id){case 1:return sizeof(GhMsConfig);case 2:return sizeof(GhMsStatus);case 3:return sizeof(GhRtEvent);
    case 4:return sizeof(GhRtBar);case 5:return sizeof(GhRtFacts);case 6:return sizeof(GhRtPosition);case 7:return sizeof(GhRtTarget);case 8:return sizeof(GhMsQuote);default:return 0;}
}
int32_t GH_RT_CALL gh_ms_configure(const GhMsConfig* config,GhRtCallback callback,void* user){return api([&]()->int32_t{
    auto& o=owner();std::lock_guard<std::mutex> guard(o.mutex);
    cta_require(!borrowed&&!o.frozen&&(!o.controller||o.controller==GetCurrentThreadId()),GH_RT_STATE);
    cta_require(config&&config->size==sizeof(*config)&&config->abi_version==GH_MS_ABI_VERSION&&callback);
    cta_require(o.bindings.size()<GH_MS_MAX_STRATEGIES&&config->read_count&&config->read_count<=GH_RT_MAX_READS
        &&config->execution_count<=GH_RT_MAX_TARGETS,GH_RT_CAPACITY);
    auto value=std::make_unique<Binding>();value->config=*config;value->callback=callback;value->user=user;
    const auto id=cta_text(config->strategy_id,sizeof(config->strategy_id));
    const auto main=configured_symbol(config->main_symbol);
    for(uint32_t i=0;i<config->read_count;++i)cta_require(value->reads.insert(configured_symbol(config->read_symbols[i])).second);
    for(uint32_t i=0;i<config->execution_count;++i){auto code=configured_symbol(config->execution_symbols[i]);
        cta_require(value->reads.count(code)&&value->executions.insert(code).second);}
    for(const auto& code:value->reads)value->quotes.emplace(code,GhMsQuote{});
    cta_require(value->reads.count(main)&&!o.bindings.count(id));
    o.bindings.emplace(id,std::move(value));o.controller=GetCurrentThreadId();o.configured.fetch_add(1);return GH_RT_OK;
});}
int32_t GH_RT_CALL gh_ms_health(void*){return owner().failure.load();}
int32_t GH_RT_CALL gh_ms_status(GhMsStatus* out){return api([&]()->int32_t{
    cta_require(out&&out->size==sizeof(*out));auto& o=owner();GhMsStatus value{};
    value.size=sizeof(value);value.configured=o.configured.load();value.created=o.created.load();value.destroyed=o.destroyed.load();
    value.active=o.active.load();value.failure=o.failure.load();value.callbacks=o.callbacks.load();value.setters=o.setters.load();
    value.owner_token=token();*out=value;return GH_RT_OK;
});}
int32_t GH_RT_CALL gh_ms_facts(uint64_t epoch,GhRtFacts* out){return api([&]()->int32_t{
    auto& b=access(epoch);cta_require(out&&out->size==sizeof(*out));*out=cta_facts(*b.ctx);return GH_RT_OK;
});}
int32_t GH_RT_CALL gh_ms_price(uint64_t epoch,const char* code,double* out){return api([&]()->int32_t{
    auto& b=access(epoch);cta_require(out);*out=cta_price(*b.ctx,symbol(b,code));return GH_RT_OK;
});}
int32_t GH_RT_CALL gh_ms_position(uint64_t epoch,const char* code,GhRtPosition* out){return api([&]()->int32_t{
    auto& b=access(epoch);cta_require(out&&out->size==sizeof(*out));*out=cta_position(*b.ctx,b.binding->reads,symbol(b,code));return GH_RT_OK;
});}
int32_t GH_RT_CALL gh_ms_quote(uint64_t epoch,const char* code,GhMsQuote* out){return api([&]()->int32_t{
    auto& b=access(epoch);cta_require(out&&out->size==sizeof(*out)&&out->version==1);
    const auto name=symbol(b,code);std::lock_guard<std::mutex> guard(b.binding->quote_mutex);
    const auto at=b.binding->quotes.find(name);cta_require(at!=b.binding->quotes.end());
    cta_require(at->second.action_date&&at->second.version==1,GH_RT_UNKNOWN);*out=at->second;return GH_RT_OK;
});}
int32_t GH_RT_CALL gh_ms_cash_basis(uint64_t epoch,const char* code,GhMsCashBasis* out){return api([&]()->int32_t{
    auto& b=access(epoch);cta_require(out&&out->size==sizeof(*out)&&out->version==1);
    const auto name=symbol(b,code);GhMsCashBasis value{};value.size=sizeof(value);value.version=1;
    value.realized_pnl_cny=b.ctx->stra_get_fund_data(1);value.fees_cny=b.ctx->stra_get_fund_data(3);
    value.average_price_cny=b.ctx->stra_get_position_avgpx(name.c_str());
    cta_require(std::isfinite(value.realized_pnl_cny)&&std::isfinite(value.fees_cny)
        &&std::isfinite(value.average_price_cny)&&value.average_price_cny>=0,GH_RT_UNKNOWN);
    *out=value;return GH_RT_OK;
});}
int32_t GH_RT_CALL gh_ms_bars(uint64_t epoch,const char* code,const char* period,uint32_t count,uint32_t main,
    GhRtBar* out,uint32_t capacity,uint32_t* written){return api([&]()->int32_t{
    auto& b=access(epoch);cta_require(out&&written&&main<=1&&capacity>=count&&capacity<=GH_RT_MAX_BARS,GH_RT_CAPACITY);
    *written=0;const auto s=symbol(b,code),p=cta_text(period,8);
    if(main)cta_require(b.kind==GH_RT_INIT&&p=="m1"&&s==b.binding->config.main_symbol&&!b.binding->main_registered,GH_RT_STATE);
    const auto values=cta_bars(*b.ctx,s,p,count,main!=0);std::copy(values.begin(),values.end(),out);
    *written=static_cast<uint32_t>(values.size());if(main)b.binding->main_registered=true;return GH_RT_OK;
});}
int32_t GH_RT_CALL gh_ms_set_targets(uint64_t epoch,const GhRtTarget* targets,uint32_t count,GhRtTarget* out,uint32_t capacity){
    return api([&]()->int32_t{
        auto& b=access(epoch,true);cta_require(out&&capacity>=count&&capacity<=GH_RT_MAX_TARGETS,GH_RT_CAPACITY);
        const auto values=cta_set_targets(*b.ctx,b.binding->reads,b.binding->executions,targets,count,owner().setters);
        std::copy(values.begin(),values.end(),out);return GH_RT_OK;
    });
}
uint32_t GH_RT_CALL gh_ms_state_abi_version(void){return 1;}
int32_t GH_RT_CALL gh_ms_state_read(uint64_t epoch,char* out,uint32_t capacity,uint32_t* written){
    return api([&]()->int32_t{
        auto& b=access(epoch);cta_require(out&&written&&capacity>=1&&capacity<=GH_MS_STATE_BYTES+1,GH_RT_CAPACITY);
        *written=0;const auto value=state_value(b.ctx->stra_load_user_data(state_key,""));
        cta_require(value.size()<capacity,GH_RT_CAPACITY);
        std::memcpy(out,value.c_str(),value.size()+1);*written=static_cast<uint32_t>(value.size());return GH_RT_OK;
    });
}
int32_t GH_RT_CALL gh_ms_state_write(uint64_t epoch,const char* value,uint32_t length){
    return api([&]()->int32_t{
        auto& b=access(epoch);cta_require(value&&length>=1&&length<=GH_MS_STATE_BYTES,GH_RT_CAPACITY);
        for(uint32_t i=0;i<length;++i)cta_require(value[i]>=32&&value[i]<127);
        const std::string copy(value,length);
        b.ctx->stra_save_user_data(state_key,copy.c_str());
        cta_require(state_value(b.ctx->stra_load_user_data(state_key,""))==copy,GH_RT_NATIVE);return GH_RT_OK;
    });
}
}
