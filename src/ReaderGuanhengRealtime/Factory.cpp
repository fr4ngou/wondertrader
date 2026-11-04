#ifndef NOMINMAX
#define NOMINMAX
#endif
#include "../GuanhengData/StrategyReader.h"
#include "../Includes/IBaseDataMgr.h"
#include "../Includes/WTSDataDef.hpp"
#include "../Includes/WTSContractInfo.hpp"
#include "../Includes/WTSSessionInfo.hpp"
#include "../Includes/WTSVariant.hpp"
#include "../Share/CodeHelper.hpp"
#include "../Share/StrUtil.hpp"
#include "../WtDataStorage/WtDataReader.h"
#include <algorithm>
#include <chrono>
#include <cmath>
#include <condition_variable>
#include <limits>
#include <memory>
#include <mutex>
#include <set>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>
#include "PublishedDaily.h"

namespace
{
using Clock = std::chrono::steady_clock;
using namespace wtp;

template<class T> struct Release
{
    void operator()(T* value) const { if (value) value->release(); }
};
using Variant = std::unique_ptr<WTSVariant, Release<WTSVariant>>;
using Slice = std::unique_ptr<WTSKlineSlice, Release<WTSKlineSlice>>;

std::uint32_t number(WTSVariant* cfg, const char* key, std::uint32_t fallback,
    std::uint32_t maximum, bool allow_zero = false)
{
    auto value = cfg->get(key);
    if (!value) return fallback;
    const auto type = value->type();
    if (type != WTSVariant::VT_Int32 && type != WTSVariant::VT_Uint32 &&
        type != WTSVariant::VT_Int64 && type != WTSVariant::VT_Uint64)
        throw std::invalid_argument("daily numeric configuration type");
    const std::string text = value->asCString();
    if (text.empty() || !std::all_of(text.begin(), text.end(), [](char c) { return c >= '0' && c <= '9'; }))
        throw std::invalid_argument("daily numeric configuration value");
    const auto result = std::stoull(text);
    if ((!allow_zero && !result) || result > maximum)
        throw std::invalid_argument("daily configuration capacity");
    return static_cast<std::uint32_t>(result);
}

void path_setting(WTSVariant* cfg, const char* key, bool required)
{
    auto value = cfg->get(key);
    if (!value && !required) return;
    if (!value || value->type() != WTSVariant::VT_String)
        throw std::invalid_argument("daily path type");
    const std::string text = value->asCString();
    if (text.empty() || text.size() > 1024 ||
        !std::all_of(text.begin(), text.end(), [](unsigned char c) { return c >= 32 && c != 127; }))
        throw std::invalid_argument("daily path value");
}

void native_path_limits(WTSVariant* cfg,
    const std::vector<std::pair<std::string, std::string>>& instruments, bool minute)
{
    // 原 Reader 的 RT 文件名使用 char[256]，日志使用 char[512]；在原 init 前核最终字节数。
    const auto root = StrUtil::standardisePath(cfg->getCString("path"));
    const auto rt = root + "rt/";
    const std::string configured_his = cfg->getCString("his_path");
    const auto his = configured_his.empty() ? root + "his/" : StrUtil::standardisePath(configured_his);
    const auto fits_log = [](const std::string& text) {
        if (text.size() >= 512) throw std::invalid_argument("native path exceeds upstream log capacity");
    };
    fits_log("WtDataReader initialized, rt dir is " + rt + ", hist dir is " + his +
        ", adjust_flag is " + std::to_string(cfg->getUInt32("adjust_flag")));
    for (const auto& instrument : instruments)
    {
        if (minute && (rt + "min1/" + instrument.first + "/" + instrument.second + ".dmb").size() >= 256)
            throw std::invalid_argument("native path exceeds upstream RT filename capacity");
        const auto filename = his + (minute ? "min1/" : "day/") + instrument.first + "/" + instrument.second + "-.dsb";
        fits_log("历史K线数据文件" + filename + "大小校验失败");
        fits_log("Sizechecking of his dta file " + filename + " failed");
    }
    if (cfg->has("adjfactor"))
    {
        const std::string path = cfg->getCString("adjfactor");
        fits_log("Adjusting factors file " + path + " not exists");
        fits_log("Loading adjusting factors file " + path + " failed");
    }
}

bool date_valid(std::uint32_t date)
{
    return guanheng::reader_minute_valid(static_cast<std::uint64_t>(date) * 10000);
}

struct SliceBudget
{
    std::mutex mutex;
    std::uint32_t live = 0, slices = 0, max_live = 16384, max_slices = 128;
    bool take(std::uint32_t count)
    {
        std::lock_guard<std::mutex> lock(mutex);
        if (slices >= max_slices || count > max_live - live) return false;
        live += count;
        ++slices;
        return true;
    }
    void give(std::uint32_t count)
    {
        std::lock_guard<std::mutex> lock(mutex);
        live -= count;
        --slices;
    }
};
struct Reservation
{
    std::shared_ptr<SliceBudget> budget;
    std::uint32_t count;
    Reservation(std::shared_ptr<SliceBudget> value, std::uint32_t size) : budget(std::move(value)), count(size) {}
    ~Reservation() { budget->give(count); }
};

// 原 slice 借用 Reader 缓存；这里只复制原输出，保持原顺序、数值与复权结果。
class DailySlice final : public WTSKlineSlice
{
    std::shared_ptr<Reservation> reservation_;
    std::vector<WTSBarStruct> bars_;
public:
    DailySlice(const char* code, std::vector<WTSBarStruct> bars, std::shared_ptr<Reservation> reservation)
        : reservation_(std::move(reservation)), bars_(std::move(bars))
    {
        setCode(code);
        appendBlock(bars_.data(), static_cast<std::uint32_t>(bars_.size()));
    }
};

class RealtimeReader final : public IDataReader
{
    struct Flight;
    static thread_local Flight* current_;
    struct Flight
    {
        RealtimeReader* owner;
        Flight* previous;
        bool event;
        bool daily = false;
        bool native = false;
        Flight(RealtimeReader* value, bool is_event) : owner(value), previous(current_), event(is_event) { current_ = this; }
        ~Flight()
        {
            current_ = previous;
            std::lock_guard<std::mutex> lock(owner->mutex_);
            --owner->active_;
            if (event) --owner->events_;
            owner->changed_.notify_all();
        }
    };
    std::mutex mutex_;
    std::condition_variable changed_;
    std::timed_mutex stop_mutex_, daily_mutex_, native_mutex_;
    bool initialized_ = false, ready_ = false, stopping_ = false, stopped_ = false;
    std::size_t active_ = 0, events_ = 0;
    std::uint32_t timeout_ = 5000, max_bars_ = 4096;
    std::uint32_t adjust_flag_ = 0;
    bool native_mode_ = false;
    std::uint32_t minute_max_bars_ = 10000;
    std::set<std::string> codes_;
    std::shared_ptr<SliceBudget> budget_;
    std::shared_ptr<SliceBudget> minute_budget_;
    guanheng::StrategyReader minute_;
    std::unique_ptr<WtDataReader> daily_;
    std::unique_ptr<guanheng::PublishedDaily> publication_;
    std::vector<std::pair<std::string, std::string>> daily_instruments_;
    std::uint32_t daily_close_time_ = 0; // 全部已准入映射会话的最晚收盘HHMM；原基础资料拥有，初始化后只读。
    bool daily_day_session_ = true; // 全部会话均为无跨日日盘时才可核当日闭合；其余会话沿原日期之前规则。
    std::unique_ptr<WtDataReader> native_minute_;

    bool admit(bool event = false)
    {
        std::lock_guard<std::mutex> lock(mutex_);
        if (!ready_ || stopping_) return false;
        ++active_;
        if (event) ++events_;
        return true;
    }
    bool live()
    {
        std::lock_guard<std::mutex> lock(mutex_);
        return ready_ && !stopping_;
    }
    bool daily_reentry() const
    {
        for (auto flight = current_; flight; flight = flight->previous)
            if (flight->owner == this && flight->daily) return true;
        return false;
    }
    bool native_reentry() const
    {
        for (auto flight = current_; flight; flight = flight->previous)
            if (flight->owner == this && flight->native) return true;
        return false;
    }
    bool mapped(const char* code) const
    {
        if (!code) return false;
        const std::string key = code;
        if (codes_.count(key)) return true;
        return key.size() > 1 && (key.back() == '+' || key.back() == '-') && codes_.count(key.substr(0, key.size() - 1));
    }
    void log(const char* reason) noexcept
    {
        // 日志 sink 可能重入读取；该次日志链只允许一次外调，避免拒绝日志递归。
        static thread_local bool logging = false;
        if (logging) return;
        logging = true;
        try { if (_sink) _sink->reader_log(LL_ERROR, reason); } catch (...) {}
        logging = false;
    }
    std::pair<std::uint64_t,std::uint64_t> closed_day_evidence(std::uint32_t date, std::uint64_t cutoff) const
    {
        // 返回本地YYYYMMDDHHMMSSmmm标签：共同session收盘、原请求可知截止；空值表示仅准入过去日。
        // 当前日只在共同session收盘后准入，原出版物known_at另在PublishedDaily核对。
        if(!publication_ || !daily_day_session_ || !daily_close_time_ || date!=_sink->get_date() ||
            cutoff%10000<daily_close_time_)return {};
        const auto now=static_cast<std::uint64_t>(_sink->get_date())*10000+_sink->get_min_time();
        const auto seconds=cutoff<now?0:_sink->get_secs();
        if(seconds>=60000)return {};
        return {(static_cast<std::uint64_t>(date)*10000+daily_close_time_)*100000,
                cutoff*100000+seconds};
    }
    WtDataReader& daily_reader(Clock::time_point deadline, std::uint32_t cutoff_date,
        std::uint64_t cutoff=0)
    {
        if (!publication_) return *daily_;
        const auto closed=closed_day_evidence(cutoff_date,cutoff);
        return publication_->select(deadline, cutoff_date, [this](WTSVariant* cfg) {
            native_path_limits(cfg, daily_instruments_, false);
        },closed.first,closed.second);
    }
public:
    ~RealtimeReader() override
    {
        // void 析构的安全兜底。受管正常路径须由控制线程先完成有界 stop。
        while (!stop(30000))
        {
            std::unique_lock<std::mutex> lock(mutex_);
            changed_.wait_for(lock, std::chrono::milliseconds(100));
        }
    }

    void init(WTSVariant* cfg, IDataReaderSink* sink, IHisDataLoader* loader = nullptr) override
    {
        {
            std::lock_guard<std::mutex> lock(mutex_);
            if (initialized_ || stopping_) return;
            initialized_ = true;
            ++active_;
        }
        Flight flight(this, false);
        try
        {
            if (!cfg || cfg->type() != WTSVariant::VT_Object || !sink || !sink->get_basedata_mgr())
                throw std::invalid_argument("realtime reader configuration or base data missing");
            IDataReader::init(cfg, sink, loader);
            auto daily = cfg->get("daily");
            if (!daily || daily->type() != WTSVariant::VT_Object)
                throw std::invalid_argument("daily object missing");
            const std::set<std::string> allowed = {"path", "his_path", "adjfactor", "adjust_flag", "max_bars", "max_live_bars", "max_slices", "publication"};
            for (const auto& key : daily->memberNames())
                if (!allowed.count(key)) throw std::invalid_argument("unknown daily field");
            path_setting(daily, "path", true);
            path_setting(daily, "his_path", false);
            path_setting(daily, "adjfactor", false);
            adjust_flag_ = number(daily, "adjust_flag", 0, 7, true);
            if (daily->has("publication") && daily->has("his_path"))
                throw std::invalid_argument("daily publication supplies native history path");
            max_bars_ = number(daily, "max_bars", 4096, 4096);
            budget_ = std::make_shared<SliceBudget>();
            budget_->max_live = number(daily, "max_live_bars", 16384, 65536);
            budget_->max_slices = number(daily, "max_slices", 128, 1024);
            if (max_bars_ > budget_->max_live) throw std::invalid_argument("daily live budget smaller than request budget");
            auto native = cfg->get("minute_native");
            if (native && native->type() != WTSVariant::VT_Object)
                throw std::invalid_argument("native minute object required");
            Variant minute_config(WTSVariant::createObject()), daily_config(WTSVariant::createObject());
            for (const auto& key : cfg->memberNames())
                if (key != "daily" && key != "minute_native") minute_config->append(key.c_str(), cfg->get(key.c_str()));
            for (const auto& key : daily->memberNames())
                if (key != "max_bars" && key != "max_live_bars" && key != "max_slices" && key != "publication")
                    daily_config->append(key.c_str(), daily->get(key.c_str()));
            if (native)
            {
                const std::set<std::string> fields = {"path", "his_path", "adjfactor", "adjust_flag"};
                for (const auto& key : native->memberNames())
                    if (!fields.count(key)) throw std::invalid_argument("unknown native minute field");
                path_setting(native, "path", true);
                path_setting(native, "his_path", false);
                path_setting(native, "adjfactor", false);
                number(native, "adjust_flag", 0, 7, true);
                const std::set<std::string> top = {"module", "daily", "minute_native", "symbols", "timeout_ms", "max_bars",
                    "max_live_bars", "max_slices", "max_symbols", "base_url", "token_env", "policy_id"};
                for (const auto& key : cfg->memberNames())
                    if (!top.count(key)) throw std::invalid_argument("unknown realtime configuration field");
                minute_max_bars_ = number(cfg, "max_bars", 10000, 100000);
                minute_budget_ = std::make_shared<SliceBudget>();
                minute_budget_->max_live = number(cfg, "max_live_bars", 100000, 1000000);
                minute_budget_->max_slices = number(cfg, "max_slices", 128, 4096);
                if (minute_max_bars_ > minute_budget_->max_live) throw std::invalid_argument("native minute live budget");
                std::lock_guard<std::mutex> lock(mutex_);
                native_mode_ = true;
            }
            else
            {
                minute_.init(minute_config.get(), sink, loader);
                if (!minute_.last_status().ok()) throw std::invalid_argument("m1 delegate configuration rejected");
            }
            timeout_ = number(cfg, "timeout_ms", 5000, 30000);
            auto symbols = cfg->get("symbols");
            const auto max_symbols = number(cfg, "max_symbols", 256, 1024);
            if (!symbols || symbols->type() != WTSVariant::VT_Array || !symbols->size() || symbols->size() > max_symbols)
                throw std::invalid_argument("realtime symbol mappings");
            std::set<std::string> unique_symbols;
            std::map<std::string, std::string> daily_symbols;
            std::vector<std::pair<std::string, std::string>> native_instruments;
            for (std::uint32_t i = 0; i < symbols->size(); ++i)
            {
                auto mapping = symbols->get(i);
                if (!mapping || mapping->type() != WTSVariant::VT_Object || mapping->memberNames().size() != 2 ||
                    !mapping->get("std_code") || mapping->get("std_code")->type() != WTSVariant::VT_String ||
                    !mapping->get("symbol") || mapping->get("symbol")->type() != WTSVariant::VT_String)
                    throw std::invalid_argument("realtime mapping fields");
                std::string code = mapping->getCString("std_code"), symbol = mapping->getCString("symbol");
                if (symbol.size() != 9 || (symbol.substr(6) != ".SH" && symbol.substr(6) != ".SZ") ||
                    !std::all_of(symbol.begin(), symbol.begin() + 6, [](char c) { return c >= '0' && c <= '9'; }) ||
                    !unique_symbols.insert(symbol).second || codes_.count(code)) throw std::invalid_argument("realtime mapping symbol");
                // 原 CodeHelper 对缺分隔符/空片段未提供失败结果，先验证其形态前置条件。
                if (code.size() + 1 >= MAX_INSTRUMENT_LENGTH || code.size() > 56 || code.find('.') == std::string::npos ||
                    code.front() == '.' || code.back() == '.' || code.find("..") != std::string::npos ||
                    !std::all_of(code.begin(), code.end(), [](unsigned char c) {
                        return (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '.' || c == '_';
                    })) throw std::invalid_argument("daily standard code shape");
                auto info = CodeHelper::extractStdCode(code.c_str(), sink->get_hot_mgr());
                const auto commodity=sink->get_basedata_mgr()->getCommodity(info._exchg, info._product);
                if (!commodity)
                    throw std::invalid_argument("daily commodity missing");
                const auto session=commodity->getSessionInfo();
                if(!session || session->getOffsetMins()!=0 || !session->getOpenTime() ||
                    session->getOpenTime()>=session->getCloseTime() || session->getCloseTime()>=2400)
                    daily_day_session_=false;
                else daily_close_time_=std::max(daily_close_time_,session->getCloseTime());
                daily_symbols.emplace(symbol, code);
                daily_instruments_.emplace_back(info._exchg, info._code);
                if (native)
                {
                    auto contract = sink->get_basedata_mgr()->getContract(info._code, info._exchg);
                    if (!contract || symbol.substr(0, 6) != info._code ||
                        (symbol.substr(6) == ".SH" ? std::string(info._exchg) != "SSE" : std::string(info._exchg) != "SZSE") ||
                        std::string(contract->getProduct()) != info._product)
                        throw std::invalid_argument("native minute contract or mapping differs");
                    native_instruments.emplace_back(info._exchg, info._code);
                }
                codes_.insert(code);
            }
            if (native)
            {
                native_path_limits(native, native_instruments, true);
                native_path_limits(daily_config.get(), native_instruments, false);
                native_minute_ = std::make_unique<WtDataReader>();
                native_minute_->init(native, sink, loader);
            }
            if (daily->has("publication"))
                publication_ = std::make_unique<guanheng::PublishedDaily>(daily->get("publication"), adjust_flag_, sink, loader,
                    std::move(daily_symbols));
            else {
                daily_ = std::make_unique<WtDataReader>();
                daily_->init(daily_config.get(), sink, loader);
            }
            std::lock_guard<std::mutex> lock(mutex_);
            ready_ = !stopping_;
        }
        catch (const std::exception& error) { log(error.what()); }
        catch (...) { log("realtime reader initialization failed"); }
    }

    WTSKlineSlice* readKlineSlice(const char* code, WTSKlinePeriod period, std::uint32_t count, std::uint64_t end = 0) override
    {
        if (!admit()) return nullptr;
        Flight flight(this, false);
        try
        {
            if (period == KP_Minute1)
            {
                if (!native_mode_) return minute_.readKlineSlice(code, period, count, end);
                if (!mapped(code) || !count || count > minute_max_bars_ || native_reentry())
                    throw std::invalid_argument("native minute request mapping, count or reentry");
                flight.native = true;
                const auto deadline = Clock::now() + std::chrono::milliseconds(timeout_);
                std::unique_lock<std::timed_mutex> lock(native_mutex_, std::defer_lock);
                if (!lock.try_lock_until(deadline) || !live()) return nullptr;
                const auto now = static_cast<std::uint64_t>(_sink->get_date()) * 10000 + _sink->get_min_time();
                if (!guanheng::reader_minute_valid(now) || (end && (!guanheng::reader_minute_valid(end) || end > now)))
                    throw std::invalid_argument("native minute cutoff invalid or ahead of context");
                const auto cutoff = end ? end : now;
                if (!minute_budget_->take(count)) throw std::runtime_error("native minute live slice budget exhausted");
                std::shared_ptr<Reservation> reservation;
                try { reservation = std::make_shared<Reservation>(minute_budget_, count); }
                catch (...) { minute_budget_->give(count); throw; }
                Slice source(native_minute_->readKlineSlice(code, KP_Minute1, count, cutoff));
                if (!source || source->empty()) return nullptr;
                if (source->size() < 0 || static_cast<std::uint32_t>(source->size()) > count || source->get_block_counts() > count)
                    throw std::runtime_error("native minute slice capacity");
                std::vector<WTSBarStruct> bars;
                bars.reserve(source->size());
                std::uint64_t previous = 0;
                for (std::size_t block = 0; block < source->get_block_counts(); ++block)
                {
                    const auto size = source->get_block_size(block);
                    const auto data = source->get_block_addr(block);
                    if ((size && !data) || size > count - bars.size()) throw std::runtime_error("native minute block capacity");
                    for (std::uint32_t i = 0; i < size; ++i)
                    {
                        const auto& bar = data[i];
                        if (bar.time > cutoff - 199000000000ULL || !date_valid(bar.date))
                            throw std::runtime_error("native minute source date or cutoff invalid");
                        const auto time = 199000000000ULL + bar.time;
                        if (!guanheng::reader_minute_valid(time) || time <= previous || time > cutoff ||
                            !std::isfinite(bar.open) || !std::isfinite(bar.high) || !std::isfinite(bar.low) ||
                            !std::isfinite(bar.close) || !std::isfinite(bar.vol) || !std::isfinite(bar.money) ||
                            !std::isfinite(bar.settle) || !std::isfinite(bar.hold) || !std::isfinite(bar.add))
                            throw std::runtime_error("native minute bars unordered, future or nonfinite");
                        previous = time;
                        bars.push_back(bar);
                    }
                }
                if (bars.size() != source->size()) throw std::runtime_error("native minute block count differs");
                if (!live() || Clock::now() >= deadline) return nullptr;
                return new DailySlice(code, std::move(bars), std::move(reservation));
            }
            if (period != KP_DAY || !mapped(code) || !count || count > max_bars_ || daily_reentry())
                throw std::invalid_argument("daily request shape, mapping or capacity");
            flight.daily = true;
            const auto deadline = Clock::now() + std::chrono::milliseconds(timeout_);
            std::unique_lock<std::timed_mutex> lock(daily_mutex_, std::defer_lock);
            if (!lock.try_lock_until(deadline) || !live()) return nullptr;
            const auto current_date = _sink->get_date();
            const auto current_minute = _sink->get_min_time();
            const auto now = static_cast<std::uint64_t>(current_date) * 10000 + current_minute;
            if (!guanheng::reader_minute_valid(now) || (end && (!guanheng::reader_minute_valid(end) || end > now)))
                throw std::invalid_argument("daily cutoff invalid or ahead of context");
            // 已发布当日以原session与known_at共同核闭合；普通冻结目录沿日期之前规则。
            const auto cutoff_date = end ? static_cast<std::uint32_t>(end / 10000) : current_date;
            if (!budget_->take(count)) throw std::runtime_error("daily live slice budget exhausted");
            std::shared_ptr<Reservation> reservation;
            try { reservation = std::make_shared<Reservation>(budget_, count); }
            catch (...) { budget_->give(count); throw; }
            Slice source(daily_reader(deadline, cutoff_date, end ? end : now).readKlineSlice(code, KP_DAY, count, end ? end : now));
            if (!source || source->empty()) return nullptr;
            if (source->size() < 0 || static_cast<std::uint32_t>(source->size()) > count)
                throw std::runtime_error("upstream daily count exceeds request");
            std::vector<WTSBarStruct> bars;
            bars.reserve(source->size());
            std::uint32_t previous = 0;
            for (std::int32_t i = 0; i < source->size(); ++i)
            {
                const auto bar = source->at(i);
                const auto date_allowed=bar && (bar->date<cutoff_date ||
                    (publication_ && bar->date==cutoff_date && publication_->basis_date()==cutoff_date));
                if (!bar || !date_valid(bar->date) || bar->date <= previous || !date_allowed ||
                    (publication_ && bar->date>publication_->basis_date()) ||
                    !std::isfinite(bar->open) || !std::isfinite(bar->high) || !std::isfinite(bar->low) ||
                    !std::isfinite(bar->close) || !std::isfinite(bar->vol) || !std::isfinite(bar->money) ||
                    !std::isfinite(bar->settle) || !std::isfinite(bar->hold) || !std::isfinite(bar->add) ||
                    bar->open <= 0 || bar->low <= 0 || bar->high < bar->low || bar->open < bar->low ||
                    bar->open > bar->high || bar->close < bar->low || bar->close > bar->high || bar->vol < 0 || bar->money < 0)
                    throw std::runtime_error("upstream daily bars are unordered, unclosed, future or invalid");
                previous = bar->date;
                bars.push_back(*bar);
            }
            if (!live() || Clock::now() >= deadline) return nullptr;
            return new DailySlice(code, std::move(bars), std::move(reservation));
        }
        catch (const std::exception& error) { log(error.what()); return nullptr; }
        catch (...) { log("realtime reader read failed"); return nullptr; }
    }

    void onMinuteEnd(std::uint32_t date, std::uint32_t minute, std::uint32_t end_date = 0) override
    {
        if (!admit(true)) return;
        Flight flight(this, true);
        try
        {
            if (!native_mode_) { minute_.onMinuteEnd(date, minute, end_date); return; }
            if (native_reentry()) throw std::invalid_argument("native minute callback reentry");
            flight.native = true;
            const auto deadline = Clock::now() + std::chrono::milliseconds(timeout_);
            std::unique_lock<std::timed_mutex> lock(native_mutex_, std::defer_lock);
            if (!lock.try_lock_until(deadline) || !live()) return;
            const auto now = static_cast<std::uint64_t>(_sink->get_date()) * 10000 + _sink->get_min_time();
            const auto time = static_cast<std::uint64_t>(date) * 10000 + minute;
            if (!guanheng::reader_minute_valid(now) || !guanheng::reader_minute_valid(time) || time > now)
                throw std::invalid_argument("native minute callback cutoff");
            native_minute_->onMinuteEnd(date, minute, end_date);
        }
        catch (...) { log("realtime reader minute callback failed"); }
    }
    WTSTickSlice* readTickSlice(const char*, std::uint32_t, std::uint64_t = 0) override { return nullptr; }

    double getAdjFactorByDate(const char* code, std::uint32_t date = 0) override
    {
        if (!admit()) return std::numeric_limits<double>::quiet_NaN();
        Flight flight(this, false);
        try
        {
            if (!mapped(code) || daily_reentry()) throw std::invalid_argument("factor request mapping or reentry");
            flight.daily = true;
            const auto deadline = Clock::now() + std::chrono::milliseconds(timeout_);
            std::unique_lock<std::timed_mutex> lock(daily_mutex_, std::defer_lock);
            if (!lock.try_lock_until(deadline) || !live()) return std::numeric_limits<double>::quiet_NaN();
            const auto today = _sink->get_date();
            if (!date) date = today; // IDataReader 的 date=0 契约为当前日期。
            if (!date_valid(today) || !date_valid(date) || date > today) throw std::invalid_argument("factor cutoff invalid");
            const auto cutoff=static_cast<std::uint64_t>(today)*10000+_sink->get_min_time();
            const double factor = daily_reader(deadline, today, cutoff).getAdjFactorByDate(code, date);
            if (!std::isfinite(factor) || factor <= 0 || !live() || Clock::now() >= deadline)
                throw std::runtime_error("factor unavailable");
            return factor;
        }
        catch (const std::exception& error) { log(error.what()); }
        catch (...) { log("realtime reader factor lookup failed"); }
        return std::numeric_limits<double>::quiet_NaN();
    }
    std::uint32_t getAdjustingFlag() override
    {
        if (!admit()) return 0;
        Flight flight(this, false);
        return adjust_flag_; // 初始化后固定，不与发布代际切换共享可变 Reader 指针。
    }

    bool stop(std::uint32_t timeout_ms)
    {
        if (timeout_ms > 300000) return false;
        const auto deadline = Clock::now() + std::chrono::milliseconds(timeout_ms);
        {
            std::lock_guard<std::mutex> lock(mutex_);
            stopping_ = true;
            ready_ = false;
            if (stopped_) return true;
            // 回调、同步 loader/logger 重入均不能等待自身，保留两个 delegate 供控制线程重试。
            if (events_ && !native_mode_) return false;
            for (auto flight = current_; flight; flight = flight->previous)
                if (flight->owner == this) return false;
        }
        std::unique_lock<std::timed_mutex> stopping(stop_mutex_, std::defer_lock);
        if (!stopping.try_lock_until(deadline)) return false;
        {
            std::unique_lock<std::mutex> lock(mutex_);
            if (stopped_) return true;
            if (!changed_.wait_until(lock, deadline, [this] { return active_ == 0; })) return false;
        }
        const auto remaining = std::chrono::duration_cast<std::chrono::milliseconds>(deadline - Clock::now()).count();
        if (!minute_.stop(static_cast<std::uint32_t>(std::max<std::int64_t>(0, remaining))).ok()) return false;
        if (timeout_ms && Clock::now() >= deadline) return false;
        // 原 WtDataReader 没有后台线程。全部同步调用结束且 slice 已复制后，缓存可真正销毁。
        if (publication_ && !publication_->close()) return false;
        daily_.reset();
        publication_.reset();
        native_minute_.reset();
        if (timeout_ms && Clock::now() >= deadline) return false;
        std::lock_guard<std::mutex> lock(mutex_);
        stopped_ = true;
        return true;
    }
};
thread_local RealtimeReader::Flight* RealtimeReader::current_ = nullptr;
}

extern "C"
{
EXPORT_FLAG wtp::IDataReader* createDataReader()
{
    try { return new RealtimeReader(); } catch (...) { return nullptr; }
}
EXPORT_FLAG bool stopDataReader(wtp::IDataReader* reader, std::uint32_t timeout_ms)
{
    try { auto owned = dynamic_cast<RealtimeReader*>(reader); return owned && owned->stop(timeout_ms); }
    catch (...) { return false; }
}
EXPORT_FLAG void deleteDataReader(wtp::IDataReader* reader)
{
    try { auto owned = dynamic_cast<RealtimeReader*>(reader); if (owned && owned->stop(30000)) delete owned; }
    catch (...) {} // void 接口失败时保留 owner；控制线程依据 stop 的布尔结果处理。
}
}
