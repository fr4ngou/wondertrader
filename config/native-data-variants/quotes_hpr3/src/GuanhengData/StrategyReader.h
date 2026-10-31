#pragma once
#include "ReaderHttpClient.h"
#include "../Includes/IDataReader.h"
#include <memory>

namespace guanheng
{
// IDataReader 仅提供基础 m1。每次读取重新访问统一服务；每个 slice 独占数组。
// 宿主销毁前停止新调用并完成 stop；已返回 slice 可独立存活至最后 release。
class StrategyReader final : public wtp::IDataReader
{
public:
    explicit StrategyReader(std::shared_ptr<IReaderHistoryProvider> provider = {});
    ~StrategyReader() override;
    void init(wtp::WTSVariant* config, wtp::IDataReaderSink* sink,
        wtp::IHisDataLoader* loader = nullptr) override;
    wtp::WTSKlineSlice* readKlineSlice(const char* code, wtp::WTSKlinePeriod period,
        std::uint32_t count, std::uint64_t end = 0) override;
    wtp::WTSTickSlice* readTickSlice(const char*, std::uint32_t, std::uint64_t = 0) override { return nullptr; }
    void onMinuteEnd(std::uint32_t date, std::uint32_t minute, std::uint32_t end_date = 0) override;
    // 回调期间仅关闭准入并返回 Pending，避免同线程或 WT pool 重入自等。
    // 其余调用在同一截止内等待在途工作及provider回调排空；失败保留依赖且准入关闭。
    // 析构仅作可能无界的安全兜底；回调内直接销毁禁止，宿主须外部stop成功后销毁。
    Status stop(std::uint32_t timeout_ms = 30000);
    Status last_status() const;
private:
    struct Impl;
    std::shared_ptr<Impl> impl_;
};
}
