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
#include <optional>
#include <set>
#include <sstream>
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
// 仅首次prepare：尚无已准入绑定/SDK请求，GET的超时及运输失败可以等待。
// 结构/认证/身份错误与任何业务未知均不取得重试资格。
bool retryable_prepare(const Status& status)
{
    if(status.code==ErrorCode::Timeout)
        return status.reason=="qmt_host_source_reconnect_deadline" || status.reason=="qmt_http_deadline"
            || status.reason=="qmt_host_deadline" || status.reason=="qmt_http_exchange_failed";
    return status.code==ErrorCode::IoError && status.reason=="qmt_http_exchange_failed";
}
// 只认原生代码固定原因；远端正文和异常文本不能进入SPI日志。
std::string diagnostic_reason(const Status& status)
{
    if(status.ok())return "ok";
    static const std::set<std::string> known={
        "qmt_host_snapshot_invalid","qmt_host_binding_invalid","qmt_host_profile_invalid","qmt_host_limits_invalid",
        "qmt_host_native_operation_failed","qmt_host_source_reconnect_deadline","qmt_host_deadline","qmt_host_pump_deadline",
        "qmt_host_original_snapshot_pending","qmt_host_original_consumption_pending","qmt_host_source_changed",
        "qmt_host_result_identity_invalid","qmt_host_transport_identity_required","qmt_http_result_identity_mismatch",
        "qmt_http_deadline","qmt_http_exchange_failed","qmt_http_body_incomplete","qmt_http_authentication_rejected",
        "qmt_http_endpoint_unavailable","qmt_http_conflict","qmt_http_backpressure","qmt_http_remote_timeout",
        "qmt_http_remote_invalid_input","qmt_http_redirect_rejected","QMT polling tick identity invalid",
        "QMT polling source changed","QMT polling snapshot qualification lost","QMT polling watermark capacity exhausted",
        "QMT polling timestamp regressed","QMT polling same-time snapshot changed","QMT polling downstream outcome unknown",
        "QMT polling callback outcome unknown","QMT polling worker failed","QMT polling dependency closed",
        "QMT polling endpoint unavailable","QMT polling startup cancelled","QMT HTTP callback cleanup is unresolved"};
    if(known.count(status.reason))return status.reason;
    const std::string snapshot_prefix="qmt_host_snapshot_invalid:";
    if(status.code==ErrorCode::InvalidInput && status.reason.compare(0,snapshot_prefix.size(),snapshot_prefix)==0) {
        const auto detail=status.reason.substr(snapshot_prefix.size());
        const auto split=detail.find(':');
        static const std::set<std::string> fields={"batch_size","json","coverage","request_symbol","duplicate_symbol",
            "row","time","lastPrice","open","high","low","lastClose","volume","amount","ohlc"};
        if(fields.count(detail.substr(0,split))) {
            if(split==std::string::npos)return status.reason;
            const auto symbol=detail.substr(split+1);
            if(symbol.size()==9 && (symbol.compare(6,3,".SH")==0 || symbol.compare(6,3,".SZ")==0)
                && std::all_of(symbol.begin(),symbol.begin()+6,[](char digit){return digit>='0'&&digit<='9';}))
                return status.reason;
        }
    }
    const std::string prefix="qmt_http_remote_failure:";
    if(status.reason.compare(0,prefix.size(),prefix)==0 && status.reason.size()>=prefix.size()+3) {
        const auto code=status.reason.substr(prefix.size(),3);
        if(std::all_of(code.begin(),code.end(),[](char digit){return digit>='0'&&digit<='9';}))return prefix+code;
    }
    if(status.code==ErrorCode::StaleSession)return "source_session_changed";
    if(status.code==ErrorCode::Conflict)return "unclassified_input_conflict";
    if(status.code==ErrorCode::SubmissionUnknown)return "downstream_outcome_unknown";
    return "unclassified";
}
std::uint64_t quote_time(const wtp::WTSTickStruct& tick)
{
    return std::uint64_t(tick.action_date)*1000000000ULL + tick.action_time;
}
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
struct TickDifference
{
    const char* field; // 第一个不同的业务字段，固定原生字段名。
    double accepted, rejected; // 沿WT字段原单位的已接受值与被拒绝值。
    int depth=-1; // 盘口从0计价档，标量为-1。
};
std::optional<TickDifference> first_difference(const wtp::WTSTickStruct& a, const wtp::WTSTickStruct& b)
{
    // 调用方已按同一规范证券和来源比较时间，保留所有有业务意义的数值字段。
    if(a.trading_date!=b.trading_date)return TickDifference{"trading_date",double(a.trading_date),double(b.trading_date)};
    using Tick=wtp::WTSTickStruct;
    const std::pair<const char*,double Tick::*> fields[]={
        {"price",&Tick::price},{"open",&Tick::open},{"high",&Tick::high},{"low",&Tick::low},
        {"settle_price",&Tick::settle_price},{"upper_limit",&Tick::upper_limit},{"lower_limit",&Tick::lower_limit},
        {"total_volume",&Tick::total_volume},{"volume",&Tick::volume},{"total_turnover",&Tick::total_turnover},
        {"turn_over",&Tick::turn_over},{"open_interest",&Tick::open_interest},{"diff_interest",&Tick::diff_interest},
        {"pre_close",&Tick::pre_close},{"pre_settle",&Tick::pre_settle},{"pre_interest",&Tick::pre_interest}};
    for(const auto& [name,field]:fields)if(a.*field!=b.*field)return TickDifference{name,a.*field,b.*field};
    const double* book_a[]={a.bid_prices,a.ask_prices,a.bid_qty,a.ask_qty};
    const double* book_b[]={b.bid_prices,b.ask_prices,b.bid_qty,b.ask_qty};
    const char* book_names[]={"bid_prices","ask_prices","bid_qty","ask_qty"};
    for(std::size_t i=0;i<std::size(book_names);++i)
        for(std::size_t depth=0;depth<std::size(a.bid_prices);++depth)
            if(book_a[i][depth]!=book_b[i][depth])return TickDifference{book_names[i],book_a[i][depth],book_b[i][depth],int(depth)};
    return {};
}
// worker 独占的去重层；MarketParser 保留原资格/时间/价格校验，重复快照只在本层吸收。
class PollingEndpoint final : public IMarketEndpoint
{
    std::shared_ptr<IMarketEndpoint> source_;
    std::function<bool(const std::string&)> admit_;
    std::map<std::string, MarketSnapshot>& accepted_; // worker持有水位，端点换代继续沿用。
    std::string& recovering_symbol_; // 同一worker的隔离证券，空值表示正常投递。
    std::size_t maximum_;
    std::string rejection_; // 本地冲突的已准入证券及前后行情值，空值表示没有本地冲突。
    bool retained_;
    std::function<void(wtp::WTSLogLevel,const Status&,const char*)> report_;
    std::string waiting_; // 同一轮询等待只在进入、原因变化和合格行情恢复时记录。
public:
    PollingEndpoint(std::shared_ptr<IMarketEndpoint> source, std::function<bool(const std::string&)> admit,
        std::map<std::string, MarketSnapshot>& accepted, std::string& recovering_symbol, std::size_t maximum,
        bool retained,std::function<void(wtp::WTSLogLevel,const Status&,const char*)> report)
        : source_(std::move(source)), admit_(std::move(admit)), accepted_(accepted),
          recovering_symbol_(recovering_symbol), maximum_(maximum),retained_(retained),report_(std::move(report)) {}
    const std::string& rejection() const noexcept { return rejection_; }
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
            const bool recovering = !recovering_symbol_.empty();
            if (recovering && key != recovering_symbol_ && admit_(recovering_symbol_)) return Status{};
            auto found = accepted_.find(key);
            if (found != accepted_.end()) {
                const auto& old = found->second;
                if (!same_session(old.source,value.source)) return failure(ErrorCode::StaleSession,"QMT polling source changed");
                const auto stamp = quote_time(tick), previous = quote_time(old.tick);
                if (stamp <= previous) {
                    if(recovering)return Status{};
                    const auto difference=stamp==previous?first_difference(old.tick,tick):std::nullopt;
                    if(stamp==previous && !difference)return Status{};
                    recovering_symbol_=key;
                    std::ostringstream detail;
                    detail.precision(17);
                    detail << " symbol=" << key << " accepted_time=" << previous << " rejected_time=" << stamp
                           << " accepted_price=" << old.tick.price << " rejected_price=" << tick.price
                           << " accepted_volume=" << old.tick.total_volume << " rejected_volume=" << tick.total_volume
                           << " accepted_turnover=" << old.tick.total_turnover << " rejected_turnover=" << tick.total_turnover;
                    if(difference)detail << " changed_field=" << difference->field << " depth=" << difference->depth
                                         << " accepted_field_value=" << difference->accepted << " rejected_field_value=" << difference->rejected;
                    rejection_=detail.str();
                    return failure(ErrorCode::Conflict,stamp < previous ? "QMT polling timestamp regressed" : "QMT polling same-time snapshot changed");
                }
            } else if (accepted_.size() >= maximum_) return failure(ErrorCode::Backpressure,"QMT polling watermark capacity exhausted");
            Status status;
            try { status = receiver(value); }
            catch (...) { return failure(ErrorCode::SubmissionUnknown,"QMT polling downstream outcome unknown"); }
            if (status.ok()) {
                accepted_[key] = value; recovering_symbol_.clear();
                if(recovering || !waiting_.empty()) { report_(wtp::LL_INFO,{},"resumed");waiting_.clear(); }
            }
            return status;
        });
    }
    Status stop() override { return source_->stop(); }
    Status subscriptions(const wtp::CodeSet& codes) override { return source_->subscriptions(codes); }
    Status pump(std::size_t count,std::uint32_t budget) override
    {
        auto status=source_->pump(count,budget);
        const bool original_pending=status.code==ErrorCode::Pending && (status.reason=="qmt_host_original_snapshot_pending"
            || status.reason=="qmt_host_original_consumption_pending");
        const bool local_deadline=status.code==ErrorCode::Timeout && status.reason=="qmt_host_pump_deadline";
        if(!retained_ || (!original_pending && !local_deadline))return status;
        // 原请求等待留在同一端点，轮询期限只结束本轮，通用MarketParser保持连接和水位。
        if(waiting_!=status.reason) {
            waiting_=status.reason;
            report_(local_deadline?wtp::LL_ERROR:wtp::LL_WARN,status,original_pending?"continue_original_request":"retry_next_poll");
        }
        return {};
    }
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
    void log(wtp::WTSLogLevel level,const Status& cause,const char* phase,const char* action,
             std::uint64_t generation,std::size_t watermarks,const std::string& detail={}) noexcept
    {
        try {
            wtp::IParserSpi* observer; std::size_t subscriptions; std::uint64_t target_revision;
            { std::lock_guard<std::timed_mutex> lock(mutex); observer=spi;subscriptions=target.size();target_revision=revision; }
            if(!observer)return;
            std::ostringstream message;
            message << "QMT polling phase=" << phase << " action=" << action
                    << " reason=\"" << diagnostic_reason(cause) << "\" error_code=" << static_cast<int>(cause.code)
                    << " source_generation=" << generation << " subscriptions=" << subscriptions
                    << " subscription_revision=" << target_revision << " accepted_symbols=" << watermarks
                    << " timeout_ms=" << config.http.timeout_ms << " poll_interval_ms=" << config.interval
                    << " batch_limit=" << config.batch << detail;
            observer->handleParserLog(level,message.str().c_str());
        } catch (...) {} // 诊断回调失败独立于行情和业务回调的效果。
    }
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
            else { if(stopping)return; if(event==wtp::WPE_Connect){connected=true;close_sent=false;} } }
        callback([&](wtp::IParserSpi* observer){observer->handleEvent(event,code);},event==wtp::WPE_Close);
    }
    struct Spi final : wtp::IParserSpi
    {
        Impl& state;
        bool defer_connect; // 重建端点的连接事件等待合格新报价。
        bool closed=false; // 当前内层MarketParser已关闭，由同一worker推进。
        explicit Spi(Impl& value,bool defer):state(value),defer_connect(defer){}
        void handleEvent(wtp::WTSParserEvent event,int32_t code) override
        {
            // 内层断开只关闭准入；外部终态由 worker 在所有依赖排空后统一发布。
            if(event==wtp::WPE_Close) {
                std::lock_guard<std::timed_mutex> lock(state.mutex);
                state.connected=false; closed=true;
                if(code)state.dependency_close_code=code;
                state.changed.notify_all(); return;
            }
            if(!defer_connect)try { state.event(event,code); } catch (...) {}
        }
        void handleSymbolList(const wtp::WTSArray*) override {}
        // endpoint 的准入在控制锁下完成；已准入回调可跨过并发 stop/退订完成。
        void handleQuote(wtp::WTSTickData* tick,uint32_t flag) override
        {
            const bool recovered=defer_connect;
            if(recovered){state.event(wtp::WPE_Connect,0);state.event(wtp::WPE_Login,0);defer_connect=false;}
            auto owned = new OwnedPollingTick(tick->getTickStruct());
            try { state.callback([&](wtp::IParserSpi* observer){observer->handleQuote(owned,flag);},true); }
            catch (...) { owned->release(); throw; }
            owned->release();
            if(recovered)state.set_status({});
        }
        // 外层按实际调用阶段记录一次；通用层原因可能含任意异常文本。
        void handleParserLog(wtp::WTSLogLevel,const char*) override {}
        wtp::IBaseDataMgr* getBaseDataMgr() override { return nullptr; }
    };
    void run() noexcept
    {
        { std::lock_guard<std::timed_mutex> lock(mutex); worker_id=std::this_thread::get_id(); }
        Status final;
        std::shared_ptr<QmtHttpClient> http;
        std::map<std::string, MarketSnapshot> accepted;
        std::string recovering_symbol;
        std::optional<SourceSession> binding;
        const char* phase="prepare";
        auto generation=[&]{return binding?binding->generation:0;};
        bool terminal_logged=false;
        auto log_terminal=[&] {
            if(final.ok() || final.reason=="QMT polling startup cancelled")return;
            log(wtp::LL_ERROR,final,phase,"stop",generation(),accepted.size());
            terminal_logged=true;
        };
        try {
          for (;;) {
            final={};bool rebuild=false;
            phase="prepare";
            // 局部对象退出顺序确保所有依赖在 worker 中完成停止及析构，再通知 join。
            std::shared_ptr<IMarketEndpoint> endpoint;
            { std::lock_guard<std::timed_mutex> lock(mutex); if(stopping)final=failure(ErrorCode::Unavailable,"QMT polling startup cancelled"); }
            if (final.ok()) {
                if(factory) endpoint=factory(config.http,config.profile,final);
                else { http=std::make_shared<QmtHttpClient>(config.http); auto native=std::make_shared<QmtHttpEndpoint>(http,config.profile);
                    final=native->prepare(config.http.timeout_ms); endpoint=native; }
            }
            // prepare只有只读绑定GET；固定来源未就绪耗尽本次预算后，沿原轮询等待。
            // 尚无pin/请求/行情，允许下一次prepare；运行期换代和未知结果仍硬失败。
            std::string preparing;
            while(factory && retryable_prepare(final)) {
                set_status(final);
                if(preparing!=final.reason) {
                    preparing=final.reason;
                    log(wtp::LL_WARN,final,phase,"retry_read_binding",generation(),accepted.size());
                }
                std::unique_lock<std::timed_mutex> lock(mutex);
                if(changed.wait_for(lock,std::chrono::milliseconds(config.interval),[&]{return stopping;})) {
                    final=failure(ErrorCode::Unavailable,"QMT polling startup cancelled");break;
                }
                lock.unlock();endpoint.reset();final={};
                endpoint=factory(config.http,config.profile,final);
            }
            if (final.ok() && !endpoint) final=failure(ErrorCode::Unavailable,"QMT polling endpoint unavailable");
            if (final.ok() && binding && !same_session(*binding,endpoint->session())) {
                final=failure(ErrorCode::StaleSession,"QMT polling source changed");
                log(wtp::LL_ERROR,final,"bind","stop",generation(),accepted.size(),
                    " candidate_generation="+std::to_string(endpoint->session().generation));
                terminal_logged=true;
            }
            if (final.ok() && recovering_symbol.empty()) set_status({});
            if (final.ok()) {
                if(!binding)binding=endpoint->session();
                if(!preparing.empty())log(wtp::LL_INFO,{},phase,"binding_ready",generation(),accepted.size());
                auto decorated=std::make_shared<PollingEndpoint>(endpoint,[this](const std::string& key){return admit(key);},
                    accepted,recovering_symbol,config.limit,host_full_tick_batches && bool(factory),
                    [&](wtp::WTSLogLevel level,const Status& cause,const char* action){log(level,cause,"pump",action,generation(),accepted.size());});
                Spi proxy(*this,!recovering_symbol.empty()); MarketParser parser(ProviderKind::Qmt,decorated,config.limit,1); parser.registerSpi(&proxy);
                wtp::CodeSet applied; std::uint64_t applied_revision;
                { std::lock_guard<std::timed_mutex> lock(mutex); applied=target; applied_revision=revision;
                    if(stopping) final=failure(ErrorCode::Unavailable,"QMT polling startup cancelled"); }
                phase="subscribe";
                if(final.ok()) { parser.subscribe(applied); final=parser.last_status(); }
                if(final.ok()) { phase="connect";if(!parser.connect())final=parser.last_status(); }
                while(final.ok()) {
                    wtp::CodeSet desired; std::uint64_t next;
                    { std::unique_lock<std::timed_mutex> lock(mutex);
                        if(stopping)break; desired=target; next=revision; }
                    if(next!=applied_revision) {
                        phase="subscribe";
                        wtp::CodeSet removed,added;
                        for(const auto& code:applied)if(!desired.count(code))removed.insert(code);
                        for(const auto& code:desired)if(!applied.count(code))added.insert(code);
                        parser.unsubscribe(removed); final=parser.last_status();
                        if(final.ok()){parser.subscribe(added);final=parser.last_status();}
                        if(!final.ok())break; applied=std::move(desired); applied_revision=next;
                    }
                    phase="pump";
                    if(!applied.empty())final=parser.pump(config.batch,config.http.timeout_ms);
                    if(!final.ok()){
                        std::lock_guard<std::timed_mutex> failed(mutex);status={final.code,diagnostic_reason(final)};connected=false;
                        rebuild=host_full_tick_batches&&factory&&!decorated->rejection().empty()&&!stopping;
                        break;
                    }
                    if(proxy.closed){final=failure(ErrorCode::Unavailable,"QMT polling dependency closed");break;}
                    std::unique_lock<std::timed_mutex> lock(mutex);
                    auto wake=[&]{return stopping||revision!=applied_revision;};
                    if(applied.empty())changed.wait(lock,wake);
                    else changed.wait_for(lock,std::chrono::milliseconds(config.interval),wake);
                }
                if(rebuild)log(wtp::LL_ERROR,final,phase,"rebuild_same_source",generation(),accepted.size(),decorated->rejection());
                else log_terminal();
                parser.release();
            }
            if(!rebuild){if(!terminal_logged)log_terminal();break;}
            // 已消费快照才进入本地水位；先隔离并释放端点，再认证同一来源建立下一代。
            event(wtp::WPE_Close,1);
            endpoint.reset();
            std::unique_lock<std::timed_mutex> lock(mutex);
            if(changed.wait_for(lock,std::chrono::milliseconds(config.interval),[&]{return stopping;})){final={};break;}
          }
        } catch (...) { final=failure(ErrorCode::Unavailable,"QMT polling worker failed"); }
        { std::lock_guard<std::timed_mutex> lock(mutex);
            if(callback_failed)final=failure(ErrorCode::SubmissionUnknown,"QMT polling callback outcome unknown"); }
        if(!terminal_logged)log_terminal();
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
            if(!final.ok())status={final.code,diagnostic_reason(final)}; }
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
