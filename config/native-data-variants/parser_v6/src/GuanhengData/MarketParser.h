#pragma once
#include "../GuanhengCommon/ProviderTypes.h"
#include "../Includes/IParserApi.h"
#include "../Includes/WTSStruct.h"
#include <functional>
#include <map>
#include <memory>
#include <mutex>

namespace guanheng
{
struct MarketSnapshot
{
    SourceSession source;
    wtp::WTSTickStruct tick;
    bool full_cumulative = false;
    bool source_time_verified = false;
};
class IMarketEndpoint
{
public:
    using Receiver = std::function<Status(const MarketSnapshot&)>;
    virtual ~IMarketEndpoint() = default;
    virtual Capability snapshot_capability() const = 0;
    virtual SourceSession session() const = 0;
    // 回调在显式 pump 的调用线程执行；调用前复制 receiver 以支持回调重入 stop。
    // stop 后禁止保留 receiver；已复制的在途回调仍须经过会话 fencing。
    virtual Status start(Receiver receiver) = 0;
    virtual Status stop() = 0;
    virtual Status subscriptions(const wtp::CodeSet& codes) = 0;
    virtual Status pump(std::size_t limit, std::uint32_t deadline_ms) = 0;
};

class MarketParser : public wtp::IParserApi
{
public:
    explicit MarketParser(ProviderKind provider, std::shared_ptr<IMarketEndpoint> endpoint = {},
        std::size_t subscription_limit = 1024, std::size_t source_instance_limit = 64);
    ~MarketParser() override;
    bool init(wtp::WTSVariant*) override;
    void release() override;
    bool connect() override;
    bool disconnect() override;
    bool isConnected() override;
    void subscribe(const wtp::CodeSet&) override;
    void unsubscribe(const wtp::CodeSet&) override;
    void registerSpi(wtp::IParserSpi*) override;
    Status pump(std::size_t limit = 256, std::uint32_t deadline_ms = 100);
    Status last_status() const;
private:
    Status receive(const MarketSnapshot& snapshot);
    void report(Status status);
    ProviderKind provider_;
    std::shared_ptr<IMarketEndpoint> endpoint_;
    std::size_t subscription_limit_;
    std::size_t source_instance_limit_;
    mutable std::recursive_mutex mutex_;
    wtp::IParserSpi* spi_ = nullptr;
    bool connected_ = false;
    // 已见身份永不淘汰；满额拒绝新实例，保留旧代际拒绝依据。
    std::map<std::pair<ProviderKind,std::string>,std::uint64_t> source_generations_;
    SourceSession source_;
    wtp::CodeSet subscriptions_;
    std::map<std::string, std::uint64_t> watermarks_;
    Status status_ { ErrorCode::Unavailable, "尚无合格行情端点" };
};
}
