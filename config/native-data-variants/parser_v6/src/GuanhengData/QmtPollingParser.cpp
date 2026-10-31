#ifndef NOMINMAX
#define NOMINMAX
#endif
#include "QmtPollingParser.h"
#include "../Includes/WTSVariant.hpp"
#include "../Includes/WTSDataDef.hpp"
#include <algorithm>
#include <cmath>
#include <condition_variable>
#include <cstdlib>
#include <cstring>
#include <set>
#include <stdexcept>
#include <thread>
#ifdef _WIN32
#include <windows.h>
#include <winhttp.h>
#endif

namespace guanheng
{
namespace
{
using Clock = std::chrono::steady_clock;
Status failure(ErrorCode code, const char* reason) { return {code, reason}; }
bool text(const std::string& value, std::size_t maximum)
{
    return !value.empty() && value.size() <= maximum
        && std::none_of(value.begin(), value.end(), [](unsigned char c) { return c < 32 || c == 127; })
        && value.find_first_not_of(' ') != std::string::npos;
}
std::string string_value(wtp::WTSVariant* parent, const char* key, std::size_t maximum)
{
    auto value = parent->get(key);
    if (!value || value->type() != wtp::WTSVariant::VT_String) throw std::invalid_argument("configuration");
    std::string result = value->asCString();
    if (!text(result, maximum)) throw std::invalid_argument("configuration");
    return result;
}
void fields(wtp::WTSVariant* value, const std::set<std::string>& allowed)
{
    if (!value || value->type() != wtp::WTSVariant::VT_Object) throw std::invalid_argument("configuration");
    for (const auto& key : value->memberNames()) if (!allowed.count(key)) throw std::invalid_argument("configuration");
}
std::size_t bounded(wtp::WTSVariant* parent, const char* key, std::size_t fallback, std::size_t minimum, std::size_t maximum)
{
    auto value = parent->get(key); if (!value) return fallback;
    auto kind = value->type();
    if (kind != wtp::WTSVariant::VT_Int32 && kind != wtp::WTSVariant::VT_Uint32
        && kind != wtp::WTSVariant::VT_Int64 && kind != wtp::WTSVariant::VT_Uint64) throw std::invalid_argument("budget");
    const std::string raw = value->asCString();
    if (raw.empty() || !std::all_of(raw.begin(), raw.end(), [](char c) { return c >= '0' && c <= '9'; })) throw std::invalid_argument("budget");
    auto result = std::stoull(raw);
    if (result < minimum || result > maximum) throw std::invalid_argument("budget");
    return static_cast<std::size_t>(result);
}
double factor(wtp::WTSVariant* profile, const char* name)
{
    auto value = profile->get(name);
    if (!value || (value->type() != wtp::WTSVariant::VT_Real && value->type() != wtp::WTSVariant::VT_Int32
        && value->type() != wtp::WTSVariant::VT_Uint32 && value->type() != wtp::WTSVariant::VT_Int64
        && value->type() != wtp::WTSVariant::VT_Uint64)) throw std::invalid_argument("factor");
    auto result = value->asDouble();
    if (!std::isfinite(result) || result <= 0) throw std::invalid_argument("factor");
    return result;
}
std::string credential(wtp::WTSVariant* config, const char* name, std::size_t maximum)
{
    const auto key = string_value(config, name, 128);
    auto letter = [](char c) { return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || c == '_'; };
    if (!letter(key[0]) || !std::all_of(key.begin(), key.end(), [&](char c) { return letter(c) || (c >= '0' && c <= '9'); }))
        throw std::invalid_argument("environment");
    const auto raw = std::getenv(key.c_str());
    if (!raw || !text(raw, maximum)) throw std::invalid_argument("environment");
    return raw;
}
bool valid_url(const std::string& value)
{
    if (!text(value, 2048) || value.find_first_of("?#\\") != std::string::npos
        || !std::all_of(value.begin(), value.end(), [](unsigned char c) { return c >= 33 && c <= 126; })) return false;
#ifdef _WIN32
    std::wstring url(value.begin(), value.end()); URL_COMPONENTS parts{}; parts.dwStructSize = sizeof(parts);
    parts.dwHostNameLength = parts.dwUrlPathLength = parts.dwUserNameLength = parts.dwPasswordLength = parts.dwExtraInfoLength = DWORD(-1);
    if (!WinHttpCrackUrl(url.c_str(), static_cast<DWORD>(url.size()), 0, &parts) || !parts.dwHostNameLength
        || !parts.nPort || parts.dwUserNameLength || parts.dwPasswordLength || parts.dwExtraInfoLength) return false;
    const std::wstring host(parts.lpszHostName, parts.dwHostNameLength);
    const std::wstring path(parts.lpszUrlPath ? parts.lpszUrlPath : L"", parts.dwUrlPathLength);
    if (!path.empty() && path != L"/") return false;
    return parts.nScheme == INTERNET_SCHEME_HTTPS || (parts.nScheme == INTERNET_SCHEME_HTTP
        && (host == L"127.0.0.1" || host == L"::1" || host == L"[::1]"));
#else
    return false;
#endif
}
bool canonical(const std::string& value, std::string& output)
{
    // 四种受支持的证券形式最长为 SZSE.STK.000001；先限制长度再分配子串。
    if (value.size() > 15) return false;
    const auto first = value.find('.'), last = value.rfind('.');
    if (first == std::string::npos) return false;
    const auto exchange = value.substr(0, first), code = value.substr(last + 1);
    if ((exchange != "SSE" && exchange != "SZSE") || code.size() != 6
        || !std::all_of(code.begin(), code.end(), [](char c) { return c >= '0' && c <= '9'; })) return false;
    if (first != last) { const auto product = value.substr(first + 1, last - first - 1);
        if (product != "STK" && product != "ETF" && product != "IDX") return false; }
    output = exchange + "." + code; return true;
}
class OwnedPollingTick final : public wtp::WTSTickData
{
public:
    explicit OwnedPollingTick(const wtp::WTSTickStruct& value) { getTickStruct() = value; }
    // WT 默认 tick 来自 thread_local pool，worker 退出会销毁该池。
    // 跨 SPI 的对象独立分配，宿主 retain 后可在 worker/parser 退出后 release。
    void release() override { wtp::WTSObject::release(); }
};
bool same_tick(const wtp::WTSTickStruct& a, const wtp::WTSTickStruct& b)
{
    // reserve_ 与 padding 不属于来源事实。每个有业务意义的字段逐项比较。
    if (std::strcmp(a.exchg,b.exchg) || std::strcmp(a.code,b.code) || a.trading_date != b.trading_date
        || a.action_date != b.action_date || a.action_time != b.action_time) return false;
    const double left[] = {a.price,a.open,a.high,a.low,a.settle_price,a.upper_limit,a.lower_limit,a.total_volume,a.volume,
        a.total_turnover,a.turn_over,a.open_interest,a.diff_interest,a.pre_close,a.pre_settle,a.pre_interest};
    const double right[] = {b.price,b.open,b.high,b.low,b.settle_price,b.upper_limit,b.lower_limit,b.total_volume,b.volume,
        b.total_turnover,b.turn_over,b.open_interest,b.diff_interest,b.pre_close,b.pre_settle,b.pre_interest};
    return std::equal(std::begin(left),std::end(left),std::begin(right))
        && std::equal(std::begin(a.bid_prices),std::end(a.bid_prices),std::begin(b.bid_prices))
        && std::equal(std::begin(a.ask_prices),std::end(a.ask_prices),std::begin(b.ask_prices))
        && std::equal(std::begin(a.bid_qty),std::end(a.bid_qty),std::begin(b.bid_qty))
        && std::equal(std::begin(a.ask_qty),std::end(a.ask_qty),std::begin(b.ask_qty));
}
// worker 独占的去重层；MarketParser 保留原资格/时间/价格校验，重复快照只在本层吸收。
class PollingEndpoint final : public IMarketEndpoint
{
    std::shared_ptr<IMarketEndpoint> source_;
    std::function<bool(const std::string&)> admit_;
    std::map<std::string, MarketSnapshot> accepted_;
    std::size_t maximum_;
public:
    PollingEndpoint(std::shared_ptr<IMarketEndpoint> source, std::function<bool(const std::string&)> admit, std::size_t maximum)
        : source_(std::move(source)), admit_(std::move(admit)), maximum_(maximum) {}
    Capability snapshot_capability() const override { return source_->snapshot_capability(); }
    SourceSession session() const override { return source_->session(); }
    Status start(Receiver receiver) override
    {
        return source_->start([this, receiver](const MarketSnapshot& value) {
            const auto& tick = value.tick;
            if (!std::memchr(tick.exchg,0,sizeof tick.exchg) || !std::memchr(tick.code,0,sizeof tick.code))
                return failure(ErrorCode::InvalidInput,"QMT polling tick identity invalid");
            const auto key = std::string(tick.exchg) + "." + tick.code;
            if (!admit_(key)) return Status{};
            const auto capability = source_->snapshot_capability();
            if (!same_session(value.source,source_->session())) return failure(ErrorCode::StaleSession,"QMT polling source changed");
            if (!capability.supported || capability.qualification == Qualification::Unavailable
                || !value.full_cumulative || !value.source_time_verified)
                return failure(ErrorCode::Unavailable,"QMT polling snapshot qualification lost");
            auto found = accepted_.find(key);
            if (found != accepted_.end()) {
                const auto& old = found->second;
                if (!same_session(old.source,value.source)) return failure(ErrorCode::StaleSession,"QMT polling source changed");
                const auto stamp = std::uint64_t(tick.action_date)*1000000000ULL + tick.action_time;
                const auto previous = std::uint64_t(old.tick.action_date)*1000000000ULL + old.tick.action_time;
                if (stamp < previous) return failure(ErrorCode::Conflict,"QMT polling timestamp regressed");
                if (stamp == previous) {
                    if (old.full_cumulative == value.full_cumulative && old.source_time_verified == value.source_time_verified
                        && same_tick(old.tick,tick)) return Status{};
                    return failure(ErrorCode::Conflict,"QMT polling same-time snapshot changed");
                }
            } else if (accepted_.size() >= maximum_) return failure(ErrorCode::Backpressure,"QMT polling watermark capacity exhausted");
            Status status;
            try { status = receiver(value); }
            catch (...) { return failure(ErrorCode::SubmissionUnknown,"QMT polling downstream outcome unknown"); }
            if (status.ok()) accepted_[key] = value;
            return status;
        });
    }
    Status stop() override { return source_->stop(); }
    Status subscriptions(const wtp::CodeSet& codes) override { return source_->subscriptions(codes); }
    Status pump(std::size_t count,std::uint32_t budget) override { return source_->pump(count,budget); }
};
}

struct QmtPollingParser::Impl : std::enable_shared_from_this<Impl>
{
    struct Config { QmtHttpConfig http; QmtHttpProfile profile; std::uint32_t interval=1000; std::size_t batch=32, limit=200; } config;
    mutable std::timed_mutex mutex;
    std::timed_mutex join_mutex;
    std::condition_variable_any changed;
    EndpointFactory factory;
    const bool host_full_tick_batches;
    std::thread worker;
    std::thread::id worker_id;
    wtp::IParserSpi* spi=nullptr;
    wtp::CodeSet target, seen;
    std::uint64_t revision=0;
    bool init_attempted=false, configured=false, started=false, stopping=false, done=true, connected=false, close_sent=false, callback_failed=false;
    int dependency_close_code=0;
    Status status{ErrorCode::Unavailable,"QMT polling parser is not configured"};
    Impl(EndpointFactory value,bool host_batches) : factory(std::move(value)),host_full_tick_batches(host_batches) {}
    void set_status(Status value) { std::lock_guard<std::timed_mutex> lock(mutex); status=std::move(value); }
    bool admit(const std::string& code) { std::lock_guard<std::timed_mutex> lock(mutex); return !stopping && target.count(code); }
    template<class Callback> void callback(Callback call, bool terminal=false)
    {
        wtp::IParserSpi* observer;
        { std::lock_guard<std::timed_mutex> lock(mutex); if (stopping && !terminal) return; observer=spi; }
        if (!observer) return;
        try { call(observer); }
        catch (...) { std::lock_guard<std::timed_mutex> lock(mutex); callback_failed=true; stopping=true; connected=false;
            status=failure(ErrorCode::SubmissionUnknown,"QMT polling callback outcome unknown"); changed.notify_all(); throw; }
    }
    void event(wtp::WTSParserEvent event,int code)
    {
        { std::lock_guard<std::timed_mutex> lock(mutex);
            if (event==wtp::WPE_Close) { connected=false; if(close_sent)return; close_sent=true; }
            else { if(stopping)return; if(event==wtp::WPE_Connect)connected=true; } }
        callback([&](wtp::IParserSpi* observer){observer->handleEvent(event,code);},event==wtp::WPE_Close);
    }
    struct Spi final : wtp::IParserSpi
    {
        Impl& state; explicit Spi(Impl& value):state(value){}
        void handleEvent(wtp::WTSParserEvent event,int32_t code) override
        {
            // 内层断开只关闭准入；外部终态由 worker 在所有依赖排空后统一发布。
            if(event==wtp::WPE_Close) {
                std::lock_guard<std::timed_mutex> lock(state.mutex);
                state.connected=false; state.stopping=true;
                if(code)state.dependency_close_code=code;
                state.changed.notify_all(); return;
            }
            try { state.event(event,code); } catch (...) {}
        }
        void handleSymbolList(const wtp::WTSArray*) override {}
        // endpoint 的准入在控制锁下完成；已准入回调可跨过并发 stop/退订完成。
        void handleQuote(wtp::WTSTickData* tick,uint32_t flag) override
        {
            auto owned = new OwnedPollingTick(tick->getTickStruct());
            try { state.callback([&](wtp::IParserSpi* observer){observer->handleQuote(owned,flag);},true); }
            catch (...) { owned->release(); throw; }
            owned->release();
        }
        void handleParserLog(wtp::WTSLogLevel,const char*) override
        { try { state.callback([](wtp::IParserSpi* observer){observer->handleParserLog(wtp::LL_ERROR,"QMT polling dependency not ready");}); } catch (...) {} }
        wtp::IBaseDataMgr* getBaseDataMgr() override { return nullptr; }
    };
    void run() noexcept
    {
        { std::lock_guard<std::timed_mutex> lock(mutex); worker_id=std::this_thread::get_id(); }
        Status final;
        std::shared_ptr<QmtHttpClient> http;
        try {
            // 局部对象退出顺序确保所有依赖在 worker 中完成停止及析构，再通知 join。
            std::shared_ptr<IMarketEndpoint> endpoint;
            { std::lock_guard<std::timed_mutex> lock(mutex); if(stopping)final=failure(ErrorCode::Unavailable,"QMT polling startup cancelled"); }
            if (final.ok()) {
                if(factory) endpoint=factory(config.http,config.profile,final);
                else { http=std::make_shared<QmtHttpClient>(config.http); auto native=std::make_shared<QmtHttpEndpoint>(http,config.profile);
                    final=native->prepare(config.http.timeout_ms); endpoint=native; }
            }
            if (final.ok() && !endpoint) final=failure(ErrorCode::Unavailable,"QMT polling endpoint unavailable");
            if (final.ok()) {
                auto decorated=std::make_shared<PollingEndpoint>(endpoint,[this](const std::string& key){return admit(key);},config.limit);
                Spi proxy(*this); MarketParser parser(ProviderKind::Qmt,decorated,config.limit,1); parser.registerSpi(&proxy);
                wtp::CodeSet applied; std::uint64_t applied_revision;
                { std::lock_guard<std::timed_mutex> lock(mutex); applied=target; applied_revision=revision;
                    if(stopping) final=failure(ErrorCode::Unavailable,"QMT polling startup cancelled"); }
                if(final.ok()) { parser.subscribe(applied); final=parser.last_status(); }
                if(final.ok() && !parser.connect()) final=parser.last_status();
                while(final.ok()) {
                    wtp::CodeSet desired; std::uint64_t next;
                    { std::unique_lock<std::timed_mutex> lock(mutex);
                        if(stopping)break; desired=target; next=revision; }
                    if(next!=applied_revision) {
                        wtp::CodeSet removed,added;
                        for(const auto& code:applied)if(!desired.count(code))removed.insert(code);
                        for(const auto& code:desired)if(!applied.count(code))added.insert(code);
                        parser.unsubscribe(removed); final=parser.last_status();
                        if(final.ok()){parser.subscribe(added);final=parser.last_status();}
                        if(!final.ok())break; applied=std::move(desired); applied_revision=next;
                    }
                    if(!applied.empty())final=parser.pump(config.batch,config.http.timeout_ms);
                    if(!final.ok())break;
                    std::unique_lock<std::timed_mutex> lock(mutex);
                    auto wake=[&]{return stopping||revision!=applied_revision;};
                    if(applied.empty())changed.wait(lock,wake);
                    else changed.wait_for(lock,std::chrono::milliseconds(config.interval),wake);
                }
                parser.release();
            }
        } catch (...) { final=failure(ErrorCode::Unavailable,"QMT polling worker failed"); }
        { std::lock_guard<std::timed_mutex> lock(mutex); connected=false; stopping=true; }
        // 请求返回后 WinHTTP 仍可能执行关闭回调。系统确认全部回调返回前，
        // worker 持有客户端与代码；外部 stop 可超时，但不得提前确认 done。
        if (http) {
            for (;;) {
                Status drained;
                try { drained=http->drain_callbacks(1000); }
                catch (...) { drained=failure(ErrorCode::IoError,"QMT HTTP callback cleanup failed"); }
                if (drained.ok()) break;
                if (drained.code!=ErrorCode::Timeout && drained.code!=ErrorCode::Pending) {
                    // 系统清理错误时保留依赖和可观察状态，退避避免错误忙循环。
                    std::unique_lock<std::timed_mutex> lock(mutex);
                    status=failure(ErrorCode::IoError,"QMT HTTP callback cleanup is unresolved");
                    changed.wait_for(lock,std::chrono::seconds(1));
                }
            }
            http.reset();
        }
        { std::lock_guard<std::timed_mutex> lock(mutex); connected=false; stopping=true;
            if(callback_failed)final=failure(ErrorCode::SubmissionUnknown,"QMT polling callback outcome unknown");
            // endpoint/注入实现的异常原因不越过插件边界，仅保留状态代码。
            if(!final.ok())status=failure(final.code,callback_failed?"QMT polling callback outcome unknown":"QMT polling source stopped"); }
        try { if(!final.ok())callback([](wtp::IParserSpi* observer){observer->handleParserLog(wtp::LL_ERROR,"QMT polling stopped; inspect managed status");},true); }catch(...){}
        try { event(wtp::WPE_Close,final.ok()?dependency_close_code:1); }catch(...){}
        { std::lock_guard<std::timed_mutex> lock(mutex); done=true; changed.notify_all(); }
    }
    Status stop(std::uint32_t budget)
    {
        if(budget>300000)return failure(ErrorCode::InvalidInput,"QMT polling stop budget invalid");
        const auto deadline=Clock::now()+std::chrono::milliseconds(budget);
        std::unique_lock<std::timed_mutex> lock(mutex,std::defer_lock);
        if(!lock.try_lock_until(deadline))return failure(ErrorCode::Timeout,"QMT polling stop deadline exceeded");
        stopping=true; connected=false; changed.notify_all();
        if(started && worker_id==std::this_thread::get_id() && !done)return failure(ErrorCode::Pending,"QMT polling worker stop requested");
        if(!changed.wait_until(lock,deadline,[&]{return done;}))return failure(ErrorCode::Timeout,"QMT polling stop deadline exceeded");
        lock.unlock();
        std::unique_lock<std::timed_mutex> join(join_mutex,std::defer_lock);
        if(!join.try_lock_until(deadline))return failure(ErrorCode::Timeout,"QMT polling join deadline exceeded");
        if(worker.joinable())worker.join();
        return {};
    }
    void subscriptions(const wtp::CodeSet& codes,bool add)
    {
        std::lock_guard<std::timed_mutex> lock(mutex);
        if(!configured||stopping){status=failure(ErrorCode::Unavailable,"QMT polling subscription admission closed");return;}
        try {
            auto candidate=target, history=seen;
            wtp::CodeSet requested;
            for(const auto& code:codes) {
                std::string key;
                if(!canonical(code,key)){status=failure(ErrorCode::InvalidInput,"QMT polling symbol invalid");return;}
                // 请求本身也有证券上限，退订大量不存在的代码不能无限占用控制锁。
                // 每个证券最多四种受支持别名，扫描和全部临时集合均受同一容量约束。
                if(!requested.count(key)) {
                    if(requested.size()>=config.limit){status=failure(ErrorCode::Backpressure,"QMT polling request capacity exhausted");return;}
                    requested.insert(key);
                }
                if(add) {
                    if((!candidate.count(key)&&candidate.size()>=config.limit)
                        ||(!history.count(key)&&history.size()>=config.limit)) {
                        status=failure(ErrorCode::Backpressure,"QMT polling subscription lifetime capacity exhausted");return;
                    }
                    candidate.insert(key);history.insert(key);
                } else candidate.erase(key);
            }
            // 完整验证后交换，不在异常路径发布部分目标或部分终生水位资格。
            target.swap(candidate);seen.swap(history);++revision;status={};changed.notify_all();
        } catch (...) { status=failure(ErrorCode::Backpressure,"QNP capacity"); }
    }
};

QmtPollingParser::QmtPollingParser(EndpointFactory factory,bool host_full_tick_batches)
    :impl_(std::make_shared<Impl>(std::move(factory),host_full_tick_batches)){}
QmtPollingParser::~QmtPollingParser() { if(!impl_->stop(30000).ok())std::terminate(); }
bool QmtPollingParser::init(wtp::WTSVariant* cfg)
{
    auto state=impl_; std::lock_guard<std::timed_mutex> lock(state->mutex);
    if(state->init_attempted||state->stopping){state->status=failure(ErrorCode::Conflict,"QMT polling initialization is single use");return false;}
    state->init_attempted=true;
    try {
        fields(cfg,{"id","active","module","check_time","filter","code","qmt"});
        auto value=cfg->get("qmt");
        std::set<std::string> allowed{"base_url","key_id_env","hmac_secret_env","timeout_ms","max_response_bytes","poll_interval_ms","batch_limit","subscription_limit","profile"};
        if(state->host_full_tick_batches)allowed.insert("full_tick_batch_size");
        fields(value,allowed);
        Impl::Config config;
        config.http.base_url=string_value(value,"base_url",2048);if(!valid_url(config.http.base_url))throw std::invalid_argument("URL");
        config.http.key_id=credential(value,"key_id_env",128);config.http.hmac_secret=credential(value,"hmac_secret_env",4096);
        if(!std::all_of(config.http.key_id.begin(),config.http.key_id.end(),[](unsigned char c){return c>=33&&c<=126;}))throw std::invalid_argument("key");
        config.http.timeout_ms=static_cast<std::uint32_t>(bounded(value,"timeout_ms",5000,1,30000));
        config.http.max_response_bytes=bounded(value,"max_response_bytes",16*1024*1024,256,16*1024*1024);
        config.interval=static_cast<std::uint32_t>(bounded(value,"poll_interval_ms",1000,10,60000));
        if(state->host_full_tick_batches)config.http.full_tick_batch_size=bounded(value,"full_tick_batch_size",1,1,200);
        const bool batched=config.http.full_tick_batch_size>1;
        config.batch=bounded(value,"batch_limit",32,1,batched?4096:200);
        config.limit=bounded(value,"subscription_limit",200,1,batched?10000:200);
        auto profile=value->get("profile");fields(profile,{"version","source_license","time_encoding","minute_boundary","volume_to_shares","amount_to_yuan","full_tick_cumulative"});
        config.profile.version=string_value(profile,"version",256);config.profile.source_license=string_value(profile,"source_license",4096);
        config.profile.time_encoding=string_value(profile,"time_encoding",32);config.profile.minute_boundary=string_value(profile,"minute_boundary",32);
        config.profile.volume_to_shares=factor(profile,"volume_to_shares");config.profile.amount_to_yuan=factor(profile,"amount_to_yuan");
        auto cumulative=profile->get("full_tick_cumulative");
        if(!cumulative||cumulative->type()!=wtp::WTSVariant::VT_Boolean)throw std::invalid_argument("cumulative");
        config.profile.full_tick_cumulative=cumulative->asBoolean();
        if(config.profile.time_encoding!="epoch_ms"||(config.profile.minute_boundary!="left"&&config.profile.minute_boundary!="right"))throw std::invalid_argument("profile");
        state->config=std::move(config);state->configured=true;state->status={};return true;
    } catch (...) {state->status=failure(ErrorCode::InvalidInput,"QMT polling configuration rejected");return false;}
}
void QmtPollingParser::registerSpi(wtp::IParserSpi* spi)
{
    std::lock_guard<std::timed_mutex> lock(impl_->mutex);
    if(impl_->started||impl_->stopping){impl_->status=failure(ErrorCode::Conflict,"QMT polling SPI binding is fixed for its lifecycle");return;}
    impl_->spi=spi;
}
bool QmtPollingParser::connect()
{
    auto state=impl_;std::lock_guard<std::timed_mutex> lock(state->mutex);
    if(state->started)return !state->stopping&&!state->done;
    if(!state->configured||state->stopping||!state->spi){state->status=failure(ErrorCode::Unavailable,"QMT polling configuration or SPI missing");return false;}
    state->started=true;state->done=false;
    try {state->worker=std::thread([state]{state->run();});return true;}
    catch(...){state->done=true;state->stopping=true;state->status=failure(ErrorCode::Unavailable,"QMT polling worker unavailable");return false;}
}
bool QmtPollingParser::disconnect(){auto result=stop();return result.ok()||result.code==ErrorCode::Pending;}
bool QmtPollingParser::isConnected(){std::lock_guard<std::timed_mutex> lock(impl_->mutex);return impl_->connected&&!impl_->stopping;}
void QmtPollingParser::subscribe(const wtp::CodeSet& codes){impl_->subscriptions(codes,true);}
void QmtPollingParser::unsubscribe(const wtp::CodeSet& codes){impl_->subscriptions(codes,false);}
Status QmtPollingParser::stop(std::uint32_t timeout_ms){return impl_->stop(timeout_ms);}
Status QmtPollingParser::last_status()const{std::lock_guard<std::timed_mutex> lock(impl_->mutex);return impl_->status;}
void QmtPollingParser::release(){if(stop().ok()){std::lock_guard<std::timed_mutex> lock(impl_->mutex);impl_->spi=nullptr;}}
}
