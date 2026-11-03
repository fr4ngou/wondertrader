#pragma once
#include "History.h"
#include "MarketParser.h"
#include "QmtHttpClient.h"
#include <thread>

namespace guanheng
{
// 受管配置提供的版本化源语义；缺失项保持不可用。量额仅在投影到 WT 时换算一次。
struct QmtHttpProfile
{
    std::string version, source_license, time_encoding, minute_boundary;
    double volume_to_shares = 0, amount_to_yuan = 0;
    bool full_tick_cumulative = false;
};

// 创建线程独占；构造无 I/O，prepare 显式固定 HTTP 会话。
// pump/fetch 截止预算 1..30000 毫秒；fetch 单次窗口最多连续 72 小时。
// 回调在 pump 线程，stop 清除接收者；历史完整页和分钟网格覆盖分别保留。
// profile 与本机隔离验收仅授 NativeVerified，真实终端/生产资格另行验真。
class QmtHttpEndpoint : public IMarketEndpoint, public IHistoryEndpoint
{
public:
    explicit QmtHttpEndpoint(std::shared_ptr<QmtHttpClient> client, QmtHttpProfile profile = {});
    Status prepare(std::uint32_t deadline_ms);
    Capability snapshot_capability() const override;
    Capability history_capability() const override;
    HistoryFetchLimits fetch_limits() const override { return {5000,4320}; }
    SourceSession session() const override;
    Status start(Receiver receiver) override;
    Status stop() override;
    Status subscriptions(const wtp::CodeSet& codes) override;
    Status pump(std::size_t limit, std::uint32_t deadline_ms) override;
    HistoryPage fetch(const MinuteRequest& request, std::size_t limit, std::uint32_t deadline_ms) override;
private:
    Status check_thread() const;
    Status check_profile() const;
    Status check_session();
    Capability capability(const char* operation) const;
    std::shared_ptr<QmtHttpClient> client_;
    QmtHttpProfile profile_;
    std::thread::id owner_;
    SourceSession source_;
    Receiver receiver_;
    std::vector<std::string> codes_;
    std::size_t cursor_ = 0, subscription_revision_ = 0;
    bool prepared_ = false;
};
}
