#pragma once
#include "../GuanhengCommon/ProviderTypes.h"
#include "../Includes/IDataWriter.h"
#include "../Includes/IDataReader.h"
#include "../Includes/IParserApi.h"
#include "../Includes/WTSStruct.h"
#include <functional>
#include <map>
#include <thread>

namespace guanheng
{
struct MinuteClock
{
    std::uint32_t date = 0;
    std::uint32_t action_time = 0; // 交易所 HHMMSSmmm；verified 由受管时钟提供者授予。
    bool verified = false;
};
struct ClosedMinute
{
    std::string symbol;
    wtp::WTSBarStruct bar;
    SourceSession source;
    Qualification qualification = Qualification::Unavailable;
    bool coverage_verified = false;
    std::string coverage_reason = "源内快照完整性、缺失分钟与分钟高低价资格需独立来源证据";
};

// 创建线程独占；同步写入，WT 自行进行累计量差分和分钟 OHLCV 计算。
// Parser/分钟调度必须在该线程调用；停止调度和 Parser 后才释放 writer/reader。
class MinutePipeline : public wtp::IParserSpi, public wtp::IDataWriterSink, public wtp::IDataReaderSink
{
public:
    using Clock = std::function<MinuteClock()>;
    using Consumer = std::function<void(const ClosedMinute&)>;
    MinutePipeline(wtp::IDataWriter& writer,wtp::IDataReader& reader,wtp::IBaseDataMgr& basedata,
        Clock clock,Consumer consumer,std::size_t subscription_limit = 1024);
    Status initialize(wtp::WTSVariant* writer_config,wtp::WTSVariant* reader_config);
    // 每次 Parser 重新绑定前调用；重绑始终隔离旧 bucket 并预热新源首分钟。
    // baseline_evidence 仅适用首次绑定的已证明干净起始基线，不能重新归属旧缓存。
    Status bind_source(const SourceSession& source,Qualification qualification,const std::string& baseline_evidence = "");
    // 只在首个 tick 前建立固定订阅；动态盘中订阅/历史预热另行验真。
    Status subscribe(const std::string& symbol);
    Status close_through(std::uint32_t date,std::uint32_t minute);
    Status last_status() const { return status_; }
    std::uint64_t written_ticks() const { return written_ticks_; }
    std::uint64_t suppressed_minutes() const { return suppressed_minutes_; }

    void handleEvent(wtp::WTSParserEvent,int32_t) override;
    void handleSymbolList(const wtp::WTSArray*) override {}
    void handleQuote(wtp::WTSTickData*,std::uint32_t procFlag) override;
    void handleParserLog(wtp::WTSLogLevel,const char*) override {}
    wtp::IBaseDataMgr* getBaseDataMgr() override { return &basedata_; }

    wtp::IBaseDataMgr* getBDMgr() override { return &basedata_; }
    bool canSessionReceive(const char*) override { return true; }
    void broadcastTick(wtp::WTSTickData*) override { ++written_ticks_; }
    void broadcastOrdQue(wtp::WTSOrdQueData*) override {}
    void broadcastOrdDtl(wtp::WTSOrdDtlData*) override {}
    void broadcastTrans(wtp::WTSTransData*) override {}
    wtp::CodeSet* getSessionComms(const char*) override { return nullptr; }
    std::uint32_t getTradingDate(const char*) override { return clock_().date; }
    void outputLog(wtp::WTSLogLevel,const char*) override {}

    void on_bar(const char*,wtp::WTSKlinePeriod,wtp::WTSBarStruct*) override;
    void on_all_bar_updated(std::uint32_t) override {}
    wtp::IBaseDataMgr* get_basedata_mgr() override { return &basedata_; }
    wtp::IHotMgr* get_hot_mgr() override { return nullptr; }
    std::uint32_t get_date() override { return clock_().date; }
    std::uint32_t get_min_time() override;
    std::uint32_t get_secs() override { return clock_().action_time%100000; }
    void reader_log(wtp::WTSLogLevel,const char*) override {}
private:
    bool owner_thread() const { return owner_==std::this_thread::get_id(); }
    wtp::IDataWriter& writer_;
    wtp::IDataReader& reader_;
    wtp::IBaseDataMgr& basedata_;
    Clock clock_;
    Consumer consumer_;
    std::thread::id owner_;
    std::size_t subscription_limit_;
    struct Subscription
    {
        std::uint64_t delivered = 0, warmup_through = 0, last_written_bucket = 0, isolate_through = 0;
        bool first_tick = true;
    };
    std::map<std::string,Subscription> subscriptions_;
    SourceSession source_;
    Qualification qualification_ = Qualification::Unavailable;
    Status status_ {ErrorCode::Unavailable,"分钟管线尚未初始化"};
    bool initialized_ = false, source_bound_ = false, active_ = false, baseline_verified_ = false, quarantined_ = false, ever_bound_ = false;
    std::uint64_t closed_through_ = 0, emitting_through_ = 0;
    std::uint64_t written_ticks_ = 0, suppressed_minutes_ = 0;
};
}
