#ifndef NOMINMAX
#define NOMINMAX
#endif
#include "StrategyReader.h"
#include "../Includes/WTSDataDef.hpp"
#include "../Includes/WTSVariant.hpp"
#include <algorithm>
#include <atomic>
#include <condition_variable>
#include <cstdlib>
#include <limits>
#include <map>
#include <mutex>
#include <set>
#include <stdexcept>

namespace guanheng
{
namespace
{
using Clock=std::chrono::steady_clock;
Status error(ErrorCode code,const char* reason){return {code,reason};}
bool text_valid(const std::string& value,std::size_t maximum)
{return !value.empty()&&value.size()<=maximum&&std::all_of(value.begin(),value.end(),[](unsigned char c){return c>=32&&c!=127;});}
std::string setting(wtp::WTSVariant* config,const char* name,std::size_t maximum)
{
    auto value=config->get(name);
    if(!value||value->type()!=wtp::WTSVariant::VT_String)throw std::invalid_argument("configuration");
    std::string result=value->asCString();if(!text_valid(result,maximum))throw std::invalid_argument("configuration");return result;
}
std::size_t bound(wtp::WTSVariant* config,const char* name,std::size_t fallback,std::size_t maximum)
{
    auto value=config->get(name);if(!value)return fallback;
    const auto kind=value->type();
    if(kind!=wtp::WTSVariant::VT_Int32&&kind!=wtp::WTSVariant::VT_Uint32&&kind!=wtp::WTSVariant::VT_Int64&&kind!=wtp::WTSVariant::VT_Uint64)
        throw std::invalid_argument("budget");
    const std::string text=value->asCString();
    if(text.empty()||!std::all_of(text.begin(),text.end(),[](char c){return c>='0'&&c<='9';}))throw std::invalid_argument("budget");
    const auto result=std::stoull(text);if(!result||result>maximum)throw std::invalid_argument("budget");return static_cast<std::size_t>(result);
}
bool symbol_valid(const std::string& value)
{return value.size()==9&&(value.substr(6)==".SH"||value.substr(6)==".SZ")&&std::all_of(value.begin(),value.begin()+6,[](char c){return c>='0'&&c<='9';});}
struct Budget
{
    std::mutex mutex;
    std::size_t live=0,slices=0,max_live=0,max_slices=0;
    bool take(std::size_t count)
    {std::lock_guard<std::mutex> lock(mutex);if(slices>=max_slices||count>max_live-live)return false;live+=count;++slices;return true;}
    void give(std::size_t count)
    {std::lock_guard<std::mutex> lock(mutex);live-=count;--slices;}
};
struct Reservation
{
    std::shared_ptr<Budget> budget;
    std::size_t count;
    Reservation(std::shared_ptr<Budget> value,std::size_t size):budget(std::move(value)),count(size){}
    ~Reservation(){if(budget)budget->give(count);}
};
class OwnedSlice final : public wtp::WTSKlineSlice
{
    std::shared_ptr<Reservation> reservation_;
    std::vector<wtp::WTSBarStruct> bars_;
public:
    OwnedSlice(const char* code,const std::vector<ReaderBar>& source,std::shared_ptr<Reservation> reservation)
        :reservation_(std::move(reservation))
    {
        bars_.reserve(source.size());for(const auto& value:source)bars_.push_back(value.bar);
        setCode(code);appendBlock(bars_.data(),static_cast<std::uint32_t>(bars_.size()));
    }
};
}

struct StrategyReader::Impl
{
    struct Subscription {std::string symbol;std::uint32_t count=0;std::uint64_t cursor=0;};
    struct Configuration
    {
        std::uint32_t timeout=5000;
        std::size_t max_bars=10000,max_symbols=256;
        std::string policy;
        std::map<std::string,Subscription> symbols;
        std::shared_ptr<Budget> budget;
        std::shared_ptr<IReaderHistoryProvider> provider;
    };
    mutable std::timed_mutex mutex;
    std::timed_mutex initialize_mutex;
    std::condition_variable_any changed;
    std::atomic<std::uint32_t> timeout{5000};
    std::shared_ptr<IReaderHistoryProvider> injected;
    std::shared_ptr<Configuration> config;
    wtp::IDataReaderSink* sink=nullptr;
    bool ready=false,stopping=true,event_active=false,callbacks=false,quarantined=false,revoked=false,init_attempted=false;
    std::size_t active=0;
    std::uint64_t lifecycle=0;
    std::string instance;
    Status status{ErrorCode::Unavailable,"reader is not configured"};
    // 未知回调结果时继续拥有宿主可能暂存的 Bar 指针；禁止重新初始化该实例。
    std::shared_ptr<std::vector<std::pair<std::string,wtp::WTSBarStruct>>> uncertain;
    explicit Impl(std::shared_ptr<IReaderHistoryProvider> provider):injected(std::move(provider)){}
    void report(Status value){std::lock_guard<std::timed_mutex> lock(mutex);status=std::move(value);}
    Status stop(std::uint32_t budget)
    {
        if(budget>300000)return error(ErrorCode::InvalidInput,"reader stop budget invalid");
        const auto deadline=Clock::now()+std::chrono::milliseconds(budget);
        std::unique_lock<std::timed_mutex> lock(mutex,std::defer_lock);
        if(!lock.try_lock_until(deadline))return error(ErrorCode::Timeout,"reader stop deadline exceeded");
        ++lifecycle;stopping=true;ready=false;
        if(callbacks)return error(ErrorCode::Pending,"reader closes after admitted callback batch");
        if(!changed.wait_until(lock,deadline,[this]{return active==0;}))return error(ErrorCode::Timeout,"reader stop deadline exceeded");
        auto provider=config?config->provider:nullptr;
        lock.unlock();
        // provider可能等待系统线程；释放reader锁，保留依赖至确认排空，多个stop可并行进入。
        if(!provider)return {};
        try
        {
            auto drained=provider->drain_callbacks(deadline);
            if(drained.ok()&&budget&&Clock::now()>=deadline)return error(ErrorCode::Timeout,"reader stop deadline exceeded");
            return drained;
        }
        catch(...){return error(ErrorCode::Unavailable,"reader provider drain failed");}
    }
    struct Flight
    {
        std::shared_ptr<Impl> impl;
        bool event=false;
        ~Flight()
        {
            if(!impl)return;
            std::lock_guard<std::timed_mutex> lock(impl->mutex);
            if(event){impl->event_active=false;impl->callbacks=false;}
            --impl->active;impl->changed.notify_all();
        }
    };
    bool identity(const ReaderResult& result,bool qualified)
    {
        if(!instance.empty()&&!result.instance_id.empty()&&result.instance_id!=instance)
        {revoked=true;status=error(ErrorCode::StaleSession,"reader service instance changed; create a new reader");return false;}
        if(qualified&&instance.empty())instance=result.instance_id;
        return !revoked;
    }
};

StrategyReader::StrategyReader(std::shared_ptr<IReaderHistoryProvider> provider):impl_(std::make_shared<Impl>(std::move(provider))){}
StrategyReader::~StrategyReader()
{
    // void析构无法向旧宿主返回未完成；保留依赖直到明确安全。错误重试退让，避免忙等。
    // 正常受管路径此前已stop成功；回调内直接销毁违反宿主生命周期契约。
    while(!impl_->stop(30000).ok())
    {std::unique_lock<std::timed_mutex> lock(impl_->mutex);impl_->changed.wait_for(lock,std::chrono::milliseconds(100));}
}
Status StrategyReader::stop(std::uint32_t timeout_ms){return impl_->stop(timeout_ms);}
Status StrategyReader::last_status()const{std::lock_guard<std::timed_mutex> lock(impl_->mutex);return impl_->status;}
void StrategyReader::init(wtp::WTSVariant* cfg,wtp::IDataReaderSink* sink,wtp::IHisDataLoader* loader)
{
    auto state=impl_;
    std::unique_lock<std::timed_mutex> initialize(state->initialize_mutex,std::defer_lock);
    if(!initialize.try_lock_for(std::chrono::seconds(30))){state->report(error(ErrorCode::Timeout,"reader initialization deadline exceeded"));return;}
    auto stopped=state->stop(30000);if(!stopped.ok()){state->report(stopped);return;}
    std::uint64_t lifecycle;
    {
        std::lock_guard<std::timed_mutex> lock(state->mutex);
        if(state->init_attempted){state->status=error(ErrorCode::Conflict,"reader initialization is single use");return;}
        state->init_attempted=true;lifecycle=state->lifecycle;
    }
    try
    {
        if(!cfg||cfg->type()!=wtp::WTSVariant::VT_Object||!sink)throw std::invalid_argument("configuration");
        const std::set<std::string> allowed={"module","base_url","token_env","policy_id","symbols","timeout_ms","max_bars","max_live_bars","max_slices","max_symbols"};
        for(const auto& name:cfg->memberNames())if(!allowed.count(name))throw std::invalid_argument("configuration fields");
        auto config=std::make_shared<Impl::Configuration>();ReaderHttpConfig http;
        http.base_url=setting(cfg,"base_url",2048);const auto token_env=setting(cfg,"token_env",128);
        if(!std::all_of(token_env.begin(),token_env.end(),[](char c){return (c>='A'&&c<='Z')||(c>='a'&&c<='z')||(c>='0'&&c<='9')||c=='_';}))throw std::invalid_argument("token name");
        const char* token=std::getenv(token_env.c_str());if(!token)throw std::invalid_argument("token missing");http.token=token;
        config->policy=http.policy_id=setting(cfg,"policy_id",128);
        config->timeout=static_cast<std::uint32_t>(bound(cfg,"timeout_ms",5000,30000));
        config->max_bars=http.max_bars=bound(cfg,"max_bars",10000,100000);
        config->max_symbols=bound(cfg,"max_symbols",256,1024);
        config->budget=std::make_shared<Budget>();config->budget->max_live=bound(cfg,"max_live_bars",100000,1000000);
        config->budget->max_slices=bound(cfg,"max_slices",128,4096);
        if(config->max_bars>config->budget->max_live)throw std::invalid_argument("live budget");
        auto symbols=cfg->get("symbols");
        if(!symbols||symbols->type()!=wtp::WTSVariant::VT_Array||!symbols->size()||symbols->size()>config->max_symbols)throw std::invalid_argument("symbols");
        std::set<std::string> unique_symbols;
        for(std::uint32_t i=0;i<symbols->size();++i)
        {
            auto mapping=symbols->get(i);
            if(!mapping||mapping->type()!=wtp::WTSVariant::VT_Object||mapping->memberNames().size()!=2)throw std::invalid_argument("mapping");
            auto code=setting(mapping,"std_code",MAX_INSTRUMENT_LENGTH-1),symbol=setting(mapping,"symbol",9);
            if(!symbol_valid(symbol)||!unique_symbols.insert(symbol).second||!config->symbols.emplace(code,Impl::Subscription{symbol,0,0}).second)
                throw std::invalid_argument("mapping");
        }
        auto provider=std::make_shared<ReaderHttpClient>(std::move(http));auto valid=provider->configured();
        if(!valid.ok()){state->report(valid);return;}
        config->provider=state->injected?state->injected:provider;
        std::lock_guard<std::timed_mutex> lock(state->mutex);
        if(state->lifecycle!=lifecycle){state->status=error(ErrorCode::Unavailable,"reader initialization cancelled");return;}
        if(state->quarantined){state->status=error(ErrorCode::Conflict,"unknown reader callback requires a new host and reader");return;}
        state->config=config;state->sink=sink;state->instance.clear();state->revoked=false;state->stopping=false;state->ready=true;
        state->timeout=config->timeout;state->status={};IDataReader::init(cfg,sink,loader);
    }
    catch(...){state->report(error(ErrorCode::InvalidInput,"reader configuration rejected"));}
}

wtp::WTSKlineSlice* StrategyReader::readKlineSlice(const char* code,wtp::WTSKlinePeriod period,std::uint32_t count,std::uint64_t end)
{
    auto state=impl_;const auto deadline=Clock::now()+std::chrono::milliseconds(state->timeout.load());
    std::shared_ptr<Impl::Configuration> config;std::shared_ptr<Reservation> reservation;ReaderRequest request;
    Impl::Flight flight;
    try
    {
        std::unique_lock<std::timed_mutex> lock(state->mutex,std::defer_lock);if(!lock.try_lock_until(deadline))return nullptr;
        if(!state->ready||state->stopping||state->revoked){state->status=error(ErrorCode::Unavailable,"reader is stopped or unqualified");return nullptr;}
        config=state->config;
        if(!code||period!=wtp::KP_Minute1||!count||count>config->max_bars||(end&&!reader_minute_valid(end)))
        {state->status=error(ErrorCode::InvalidInput,"reader supports mapped unadjusted m1 requests only");return nullptr;}
        auto found=config->symbols.find(code);if(found==config->symbols.end()){state->status=error(ErrorCode::InvalidInput,"reader symbol is not mapped");return nullptr;}
        // 初次 Pending 也登记请求，分钟回调可在同一 reader 上重试预热。
        found->second.count=std::max(found->second.count,count);
        if(!config->budget->take(count)){state->status=error(ErrorCode::Backpressure,"reader live slice budget exhausted");return nullptr;}
        try{reservation=std::make_shared<Reservation>(config->budget,count);}catch(...){config->budget->give(count);throw;}
        request.symbol=found->second.symbol;request.count=count;request.end=end;
        ++state->active;flight.impl=state;lock.unlock();
        auto result=config->provider->read(request,deadline);
        auto valid=validate_reader_result(request,result,config->policy,config->max_bars);
        lock.lock();
        if(!state->identity(result,valid.ok()))return nullptr;
        if(!valid.ok()){state->status=valid;return nullptr;}
        if(state->stopping||Clock::now()>=deadline){state->status=error(state->stopping?ErrorCode::Unavailable:ErrorCode::Timeout,"reader read cancelled or expired");return nullptr;}
        auto& subscription=config->symbols.at(code);
        if(!subscription.cursor&&!result.bars.empty())subscription.cursor=result.bars.back().bar.time+199000000000ULL;
        state->status={};lock.unlock();
        if(result.bars.empty())return nullptr;
        return new OwnedSlice(code,result.bars,std::move(reservation));
    }
    catch(...){state->report(error(ErrorCode::Unavailable,"reader history operation failed"));return nullptr;}
}

void StrategyReader::onMinuteEnd(std::uint32_t date,std::uint32_t time,std::uint32_t)
{
    auto state=impl_;const auto deadline=Clock::now()+std::chrono::milliseconds(state->timeout.load());
    const std::uint64_t end=static_cast<std::uint64_t>(date)*10000+time;
    Impl::Flight flight;std::shared_ptr<Impl::Configuration> config;
    std::map<std::string,Impl::Subscription> subscriptions;
    auto deliveries=std::make_shared<std::vector<std::pair<std::string,wtp::WTSBarStruct>>>();
    std::map<std::string,std::uint64_t> cursors;
    try
    {
        std::unique_lock<std::timed_mutex> lock(state->mutex,std::defer_lock);if(!lock.try_lock_until(deadline))return;
        if(!state->ready||state->stopping||state->revoked||state->quarantined)return;
        if(!reader_minute_valid(end)){state->status=error(ErrorCode::InvalidInput,"reader closed minute invalid");return;}
        if(state->event_active){state->status=error(ErrorCode::Backpressure,"reader minute delivery already active");return;}
        state->event_active=true;++state->active;flight.impl=state;flight.event=true;
        config=state->config;subscriptions=config->symbols;lock.unlock();
        for(const auto& item:subscriptions)
        {
            const auto& sub=item.second;if(!sub.count||sub.cursor>=end)continue;
            if(Clock::now()>=deadline){state->report(error(ErrorCode::Timeout,"reader minute deadline exceeded"));return;}
            ReaderRequest request;request.symbol=sub.symbol;request.end=end;request.tail=!sub.cursor;request.count=sub.count;request.after=sub.cursor;
            auto result=config->provider->read(request,deadline);auto valid=validate_reader_result(request,result,config->policy,config->max_bars);
            {std::lock_guard<std::timed_mutex> guard(state->mutex);if(!state->identity(result,valid.ok()))return;if(state->stopping)return;}
            if(!valid.ok()){state->report(valid);return;}
            if(!request.tail)cursors[item.first]=end;
            if(!result.bars.empty())
            {
                const auto& last=result.bars.back();const auto latest=last.bar.time+199000000000ULL;
                if(request.tail)cursors[item.first]=latest;
                // Pending 后首次合格 tail 只允许当前端点成为事件，旧历史只建立基线。
                if(latest==end&&end==result.as_of&&(request.tail||last.delivery==ReaderDelivery::Current))
                    deliveries->emplace_back(item.first,last.bar);
            }
        }
        lock.lock();
        if(state->stopping||state->revoked||Clock::now()>=deadline)
        {state->status=error(ErrorCode::Timeout,"reader minute delivery cancelled or expired");return;}
        // 同时进行的首次 tail 可能已经建立较新基线，旧事件不能回退或重复投递。
        deliveries->erase(std::remove_if(deliveries->begin(),deliveries->end(),[&](const auto& item){return config->symbols.at(item.first).cursor>=item.second.time+199000000000ULL;}),deliveries->end());
        auto sink=state->sink;state->callbacks=!deliveries->empty();lock.unlock();
        if(!deliveries->empty())
        {
            try
            {
                // 一旦准入，本批必须完成 flush；WtDtMgr 在 on_bar 后持有数组指针。
                for(auto& item:*deliveries)sink->on_bar(item.first.c_str(),wtp::KP_Minute1,&item.second);
                sink->on_all_bar_updated(time);
            }
            catch(...)
            {
                std::lock_guard<std::timed_mutex> guard(state->mutex);state->quarantined=true;state->uncertain=deliveries;
                state->status=error(ErrorCode::SubmissionUnknown,"reader callback outcome unknown; delivery quarantined");return;
            }
        }
        lock.lock();state->callbacks=false;
        for(const auto& item:cursors)config->symbols.at(item.first).cursor=std::max(config->symbols.at(item.first).cursor,item.second);
        state->status={};
    }
    catch(...){state->report(error(ErrorCode::Unavailable,"reader minute operation failed"));}
}
}
