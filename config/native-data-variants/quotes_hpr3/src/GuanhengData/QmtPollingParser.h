#pragma once
#include "QmtHttpEndpoint.h"
#include <functional>
#include <memory>

namespace guanheng
{
// 单次运行的原生行情插件。所有 endpoint/parser 操作与 SPI 回调属于 worker；
// 控制线程只替换目标订阅并请求停止。直接销毁前必须由外部成功 stop。
// 宿主 retain 的 tick 独立于 worker 存活；DLL 保留至这些 tick 最后 release。
class QmtPollingParser final : public wtp::IParserApi
{
public:
    // 工厂在 worker 内创建并准备 endpoint；返回的依赖也在 worker 内释放。
    using EndpointFactory = std::function<std::shared_ptr<IMarketEndpoint>(
        const QmtHttpConfig&, const QmtHttpProfile&, Status&)>;
    // 仅 Host 工厂开启批量字段准入；旧 HTTP 工厂继续原配置与容量。
    explicit QmtPollingParser(EndpointFactory factory = {},bool host_full_tick_batches = false);
    ~QmtPollingParser() override;
    bool init(wtp::WTSVariant*) override;
    void registerSpi(wtp::IParserSpi*) override;
    bool connect() override;
    bool disconnect() override;
    bool isConnected() override;
    void subscribe(const wtp::CodeSet&) override;
    void unsubscribe(const wtp::CodeSet&) override;
    void release() override;
    // stop 关闭准入；worker 回调中返回 Pending，外部调用有界等待清理和 join。
    Status stop(std::uint32_t timeout_ms = 30000);
    Status last_status() const;
private:
    struct Impl;
    std::shared_ptr<Impl> impl_;
};
}
