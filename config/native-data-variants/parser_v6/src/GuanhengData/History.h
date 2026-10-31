#pragma once

#include "../GuanhengCommon/ProviderTypes.h"
#include "../Includes/IDataReader.h"
#include "../Includes/WTSStruct.h"
#include <filesystem>
#include <memory>
#include <mutex>
#include <optional>
#include <vector>

namespace guanheng
{
// 所有分钟均为 Asia/Shanghai 的右端 YYYYMMDDHHMM，价格元、数量股、金额元。
// expected_minutes 由已确认的日历/停牌规则生成；空依据始终返回 Unknown。
enum class Coverage { Unknown, Complete, Gaps };
struct HistoryMetadata
{
    SourceSession source;
    Qualification qualification = Qualification::Unavailable;
    std::string dataset_version;
    std::string source_license;
    std::string adjustment = "none";
    std::string factor_version;
    std::string minute_boundary = "right";
    std::string timezone = "Asia/Shanghai";
    double volume_to_shares = 0;
    double amount_to_yuan = 0;
    std::string content_id; // 原生 DSB 内容摘要，读取和冻结副本均校验。
};
struct MinuteRequest
{
    std::string exchange;
    std::string code;
    std::uint64_t from = 0;
    std::uint64_t to = 0;
    std::vector<std::uint64_t> expected_minutes;
    std::string calendar_version;
};
struct MinuteResult
{
    Status status;
    std::vector<wtp::WTSBarStruct> bars;
    HistoryMetadata metadata;
    Coverage coverage = Coverage::Unknown;
    std::vector<std::uint64_t> missing_minutes;
};
// 输出按右端分钟选择；limit=0为范围全部，正数为区间内最多N根。
// 派生/尾部不借m1预期网格证明覆盖，源准备继续使用MinuteRequest。
struct HistoryQuery
{
    MinuteRequest window;
    std::uint32_t period_minutes = 1;
    std::size_t limit = 0;
};

// LC1 仅解析调用者获准读取的外部文件；源单位必须显式给定。
Status decode_lc1(const std::vector<std::uint8_t>& bytes, const HistoryMetadata& metadata,
    std::vector<wtp::WTSBarStruct>& bars);

// 发布和原生Reader首次加载共用字段/顺序准入，避免两条路径采用不同分钟定义。
Status validate_history_bars(const std::vector<wtp::WTSBarStruct>& bars, std::size_t maximum);
struct NativeHistoryReaderConfig;
class NativeHistoryReader;

class NativeHistoryStore
{
public:
    explicit NativeHistoryStore(std::filesystem::path root, std::size_t max_bars = 1000000);
    NativeHistoryStore(std::filesystem::path root, std::size_t max_bars,
        const NativeHistoryReaderConfig& reader_config);
    // 所有查询结束后销毁；原Reader检查线程的join属于关闭预算。
    ~NativeHistoryStore();
    Status publish(const std::string& exchange, const std::string& code,
        const std::vector<wtp::WTSBarStruct>& bars, HistoryMetadata metadata);
    // 在同一根 lease 内读取最新版、核对来源、合并分钟并发布；并发修订不会被旧页覆盖。
    Status merge_bars(const std::string& exchange, const std::string& code,
        const std::vector<wtp::WTSBarStruct>& bars, HistoryMetadata metadata);
    Status import_lc1(const std::string& exchange, const std::string& code,
        const std::vector<std::uint8_t>& bytes, HistoryMetadata metadata);
    MinuteResult query(const MinuteRequest& request);
    MinuteResult query(const HistoryQuery& request);
    // 原子排他认领全新目标 root；认领后失败保留残留供核查，不自动删除或复用。
    // 副本、来源及摘要独立于后续源修订。
    Status freeze(const std::string& exchange, const std::string& code,
        const std::filesystem::path& snapshot_root);
    // 恢复上一版到原子排他认领的新 root；目标与旧根失败残留均保留供核查。
    Status recover_into(const std::string& exchange, const std::string& code,
        const std::filesystem::path& new_root);
    std::filesystem::path bar_path(const std::string& exchange, const std::string& code) const;
private:
    MinuteResult query_impl(const HistoryQuery& request, bool require_native);
    Status publish_impl(const std::string& exchange, const std::string& code,
        const std::vector<wtp::WTSBarStruct>& bars, HistoryMetadata metadata, bool merge);
    std::filesystem::path root_;
    std::size_t max_bars_;
    std::mutex mutex_;
    std::unique_ptr<NativeHistoryReader> reader_;
    std::size_t native_cache_bytes_ = 0;
};

struct HistoryPage
{
    Status status;
    std::vector<wtp::WTSBarStruct> bars;
    HistoryMetadata metadata;
    bool complete = false; // 源页完整性单独保留，不能替代分钟覆盖证据。
};
// 未声明的维度只受调用方预算约束；跨度为自然分钟，0 表示单一时点。
struct HistoryFetchLimits
{
    std::optional<std::size_t> max_rows;
    std::optional<std::uint64_t> max_elapsed_minutes;
};
class IHistoryEndpoint
{
public:
    virtual ~IHistoryEndpoint() = default;
    virtual Capability history_capability() const = 0;
    // 固定能力，无 I/O 或状态推进；旧自有来源默认不增加源端限制。
    virtual HistoryFetchLimits fetch_limits() const { return {}; }
    // 显式 worker 调用；端点须遵守 limit 和 deadline_ms，禁止无限等待。
    virtual HistoryPage fetch(const MinuteRequest& request, std::size_t limit,
        std::uint32_t deadline_ms) = 0;
};
enum class PreparationState { Pending, Complete, Unavailable, Failed };
struct Preparation
{
    std::uint64_t id = 0;
    PreparationState state = PreparationState::Pending;
    Status status { ErrorCode::Pending, "等待历史准备" };
};
class HistoryPreparationQueue
{
public:
    HistoryPreparationQueue(NativeHistoryStore& store, std::shared_ptr<IHistoryEndpoint> endpoint,
        std::size_t capacity = 64, std::size_t page_limit = 10000, std::uint32_t deadline_ms = 1000,
        std::size_t staging_limit = 100000);
    Preparation request(const MinuteRequest& request);
    // id=0 保留 FIFO；非零仅推进该任务，终态/无网格返回原观察，不触发其他任务。
    Preparation work_one(std::uint64_t id = 0);
    Preparation inspect(std::uint64_t id) const;
    // 丢弃非运行内存任务（含 Pending 暂存），不删除 DSB；worker 期间统一背压。
    // 非零未知 id 幂等成功，0 非法；跨实例身份由外部 Bridge queue_id 约束。
    Status release(std::uint64_t id);
private:
    struct Task
    {
        MinuteRequest request;
        Preparation result;
        std::vector<wtp::WTSBarStruct> staged;
        HistoryMetadata staged_metadata;
        bool metadata_bound = false; // 空页同样固定采集身份，不能跨会话混合后续片。
        std::optional<MinuteRequest> active_window;
        std::size_t active_limit = 0;
        std::uint64_t scanned_through = 0; // 本轮已结束窗口的右端，不代表覆盖完整。
        bool source_complete = false;
    };
    NativeHistoryStore& store_;
    std::shared_ptr<IHistoryEndpoint> endpoint_;
    std::size_t capacity_, page_limit_, staging_limit_;
    std::uint32_t deadline_ms_;
    std::uint64_t next_id_ = 1;
    std::vector<Task> tasks_;
    mutable std::mutex mutex_;
    bool running_ = false;
};

// 同步 WT loader 只读已准备的原生文件，回调期间数组有效；不运行补数。
class NativeHistoryLoader : public wtp::IHisDataLoader
{
public:
    explicit NativeHistoryLoader(NativeHistoryStore& store) : store_(store) {}
    bool loadFinalHisBars(void*, const char*, wtp::WTSKlinePeriod, wtp::FuncReadBars) override { return false; }
    bool loadRawHisBars(void* obj, const char* code, wtp::WTSKlinePeriod period, wtp::FuncReadBars cb) override;
    bool loadAllAdjFactors(void*, wtp::FuncReadFactors) override { return false; }
    bool loadAdjFactors(void*, const char*, wtp::FuncReadFactors) override { return false; }
private:
    NativeHistoryStore& store_;
};
}
