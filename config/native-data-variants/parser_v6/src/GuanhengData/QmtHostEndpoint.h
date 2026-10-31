#pragma once
#include "QmtHttpEndpoint.h"
#include "../GuanhengCommon/QmtHostReadClient.h"

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
        std::size_t full_tick_batch_size=1);
    ~QmtHostEndpoint() override;
    Status prepare(std::uint32_t milliseconds);
    Capability snapshot_capability() const override;
    SourceSession session() const override;
    Status start(Receiver receiver) override;
    Status stop() override;
    Status subscriptions(const wtp::CodeSet& codes) override;
    Status pump(std::size_t limit,std::uint32_t milliseconds) override;
private:
    Status check() const;
    std::shared_ptr<QmtHostReadClient> client_;
    QmtHttpProfile profile_;
    std::thread::id owner_;
    SourceSession source_;
    Receiver receiver_;
    std::vector<std::string> codes_;
    std::size_t full_tick_batch_size_=1;
    std::size_t cursor_=0,revision_=0;
    bool prepared_=false;
};
}
