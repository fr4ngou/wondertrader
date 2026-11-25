#pragma once
#include "QmtHttpEndpoint.h"
#include "../GuanhengCommon/QmtHostReadClient.h"
#include <optional>
#include <chrono>

namespace guanheng
{
// 由QmtPollingParser worker创建/调用/释放；同步I/O不在WT策略或SPI回调内执行。
// stop关闭接收准入，未排空返回Pending；析构继续持有HTTP owner至系统回调全部退出。
// 因而外层parser stop可超时并保留DLL，不能提前报告worker done。
class QmtHostEndpoint final : public IMarketEndpoint
{
public:
    // 每原请求 1..200 证券；大于 1 时订阅容量为 10000，pump 仍共用一个总截止。
    QmtHostEndpoint(std::shared_ptr<QmtHostReadClient> client,QmtHttpProfile profile,
        std::size_t full_tick_batch_size=1,bool retained=false);
    ~QmtHostEndpoint() override;
    Status prepare(std::uint32_t milliseconds);
    Status rebind_quote_transport();
    Capability snapshot_capability() const override;
    SourceSession session() const override;
    Status start(Receiver receiver) override;
    Status stop() override;
    Status subscriptions(const wtp::CodeSet& codes) override;
    Status pump(std::size_t limit,std::uint32_t milliseconds) override;
private:
    Status check() const;
    // retained快照由此worker独占：未知只核原ID，完整值/映射归本owner后确认消费。
    // Pending表示本轮没有可交付行情；调用者保留原值，下一pump继续原责任。
    Status read_snapshots(const std::vector<std::string>& codes,
        std::chrono::steady_clock::time_point until,std::vector<MarketSnapshot>& snapshots);
    bool retained_=false; // 构造固定；旧Parser缺省保持原FullTickV6行为。
    std::optional<QmtBoundResult> held_; // 唯一原请求/收据/完整结果；ACK前持续持有。
    std::vector<std::string> held_codes_; // 原请求证券，订阅变化不重写原请求。
    std::vector<MarketSnapshot> held_snapshots_; // 整批映射完成且ACK成功后才交SPI。
    Status held_status_; // 原终态或确定坏值的结果；ACK确认后才交付分类。
    Status original_error_; // 确定协议/认证/身份硬错误锁存；保留原收据但停止自动I/O续核。
    bool mapped_=false; // 已持有全部映射/失败分类，随后只重试原消费确认。
    std::shared_ptr<QmtHostReadClient> client_;
    QmtHttpProfile profile_;
    std::thread::id owner_;
    SourceSession source_;
    Receiver receiver_;
    std::vector<std::string> codes_;
    std::size_t full_tick_batch_size_=1;
    std::size_t cursor_=0,revision_=0;
    bool prepared_=false;
    bool transport_replacement_pending_=false; // 已认证换代，待旧接收器关闭后接续。
};
}
