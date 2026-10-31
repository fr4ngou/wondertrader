#pragma once

#include "../GuanhengCommon/ProviderTypes.h"
#include "../Includes/ITraderApi.h"
#include <memory>
#include <vector>
#include <mutex>
#include <map>

namespace guanheng
{
enum class ExecutionOperation { Submit, Cancel };
enum class SubmissionStage { NotCalled, HostAccepted, BrokerAccepted, SubmissionUnknown };

struct OrderFields
{
    std::string exchange, code, entrust_id, user_tag, order_id;
    double price = 0, quantity = 0;
    bool buy = true;
    ExecutionOperation operation = ExecutionOperation::Submit;
};

struct SignedCommand
{
    std::string command_id;
    // 原始签名字节只运输；上游校验器返回解析后的强类型绑定。
    std::vector<std::uint8_t> original_bytes;
};

struct VerifiedAuthorization
{
    ExecutionIdentity identity;
    RuntimeMode mode = RuntimeMode::ReadOnly;
    std::string command_id;
    OrderFields fields;
};

class AuthorizationVerifier
{
public:
    virtual ~AuthorizationVerifier() = default;
    // 实现由可信上游提供，包含验签、有效期和许可检查；模拟实现必须返回 false。
    virtual bool production_trusted() const = 0;
    virtual Status verify(const SignedCommand&, VerifiedAuthorization&) = 0;
};

struct SubmissionReceipt
{
    Status status;
    SubmissionStage stage = SubmissionStage::NotCalled;
    std::string command_id, native_order_id;
};

struct ExecutionCapabilities
{
    Capability account, positions, orders, trades, reports, submit, cancel;
};

struct AccountRecord
{
    std::string currency = "CNY";
    double balance = 0, previous_balance = 0, available = 0, margin = 0;
    double frozen_margin = 0, commission = 0, frozen_commission = 0;
    double close_profit = 0, dynamic_profit = 0, deposit = 0, withdraw = 0;
};
struct PositionRecord
{
    std::string exchange, code, currency = "CNY";
    double previous = 0, today = 0, available_previous = 0, available_today = 0;
    double total_cost = 0, average_price = 0, margin = 0, dynamic_profit = 0;
};
enum class NativeOrderState { Submitting, Accepted, PartFilled, Filled, Canceling, Canceled, Rejected };
struct OrderRecord
{
    OrderFields fields;
    std::string command_id, native_order_id, message;
    // remaining为仍有效的活动数量；inactive_quantity为已撤/已拒绝的未成交数量。
    double traded = 0, remaining = 0, inactive_quantity = 0;
    std::uint32_t date = 0;
    std::uint64_t time = 0;
    NativeOrderState state = NativeOrderState::Submitting;
};
struct TradeRecord
{
    OrderFields fields;
    std::string command_id, native_order_id, trade_id;
    double amount = 0;
    std::uint32_t date = 0;
    std::uint64_t time = 0;
};
// 唯一Host原子证明：四快照已吸收inclusive_cursor及以前的全部事件。
// complete缺省false，cursor数值零只有在完整证明内才有效，禁止从普通序号推断。
struct CoherentBaseline
{
    ExecutionIdentity identity;
    std::string stream_id, boundary_id;
    std::uint64_t inclusive_cursor = 0;
    bool complete = false;
};
template<class T> struct ExecutionSnapshot
{
    CoherentBaseline baseline;
    std::vector<T> records;
};
struct ExecutionBootstrap
{
    CoherentBaseline baseline;
    ExecutionSnapshot<AccountRecord> account;
    ExecutionSnapshot<PositionRecord> positions;
    ExecutionSnapshot<OrderRecord> orders;
    ExecutionSnapshot<TradeRecord> trades;
};
struct RetainedResumeProof
{
    CoherentBaseline baseline;
    std::uint64_t after_cursor = 0, through_cursor = 0;
    std::uint32_t trading_date = 0;
    bool complete = false;
};
class RetainedConsumerRecovery
{
public:
    virtual ~RetainedConsumerRecovery() = default;
    // 调用方已经验证Host连续性并补投到冻结through_cursor；该方法只恢复通道通知。
    virtual Status restore_retained_channel(std::uint32_t trading_date) = 0;
    virtual Status invalidate_retained_channel() { return {ErrorCode::Unavailable, "消费者尚无资格撤销接缝"}; }
};
struct ExecutionEvent
{
    ExecutionIdentity identity;
    std::string event_id, stream_id;
    std::uint64_t cursor = 0;
    bool is_trade = false;
    OrderRecord order;
    TradeRecord trade;
};

class ExecutionEndpoint
{
public:
    virtual ~ExecutionEndpoint() = default;
    virtual ExecutionCapabilities capabilities() const = 0;
    virtual bool production_trusted() const = 0;
    // 所有调用由端点执行有界 I/O；budget_ms 是上限，端点不得跨账户或自动切路由。
    virtual Status open(const ExecutionIdentity&, std::uint32_t budget_ms) = 0;
    virtual void close() = 0;
    virtual Status bootstrap(ExecutionBootstrap&, std::uint32_t)
    { return {ErrorCode::Unavailable, "Host尚无原子快照及事件吸收水位证明"}; }
    virtual Status confirm_resume(const CoherentBaseline&, std::uint64_t, RetainedResumeProof&, std::uint32_t)
    { return {ErrorCode::Unavailable, "Host尚无保留消费者连续性及冻结前沿证明"}; }
    // 唯一 Host Journal 原子受理/去重；重复 command_id 不得产生第二次原生提交。
    virtual SubmissionReceipt execute(const SignedCommand&, const VerifiedAuthorization&, std::uint32_t budget_ms) = 0;
    virtual Status account(ExecutionSnapshot<AccountRecord>&, std::uint32_t) = 0;
    virtual Status positions(ExecutionSnapshot<PositionRecord>&, std::uint32_t) = 0;
    virtual Status orders(ExecutionSnapshot<OrderRecord>&, std::uint32_t) = 0;
    virtual Status trades(ExecutionSnapshot<TradeRecord>&, std::uint32_t) = 0;
    // 事件已由 Host 持久化；本端游标独立于 Agent/Host ACK，不改变 Host Journal。
    virtual Status events(std::uint64_t after, std::size_t limit, std::vector<ExecutionEvent>&, std::uint32_t) = 0;
    // 只有 Host 给出完整恢复证明才能解除未知闩锁，查询成功本身不构成证明。
    virtual Status reconcile(const ExecutionIdentity&, std::uint32_t) = 0;
};

struct ExecutionState
{
    ExecutionIdentity identity;
    Status status;
    bool connected = false, logged_in = false, writes_blocked = true;
    bool consumer_ready = false, delivery_unknown = false, stopping = false, resuming = false;
    bool channel_isolated = false;
    std::string command_id;
    SubmissionStage stage = SubmissionStage::NotCalled;
};
class ExecutionStateSink
{
public:
    virtual ~ExecutionStateSink() = default;
    virtual void on_execution_state(const ExecutionState&) = 0;
};

struct ManagedTraderConfig
{
    ExecutionIdentity identity;
    RuntimeMode mode = RuntimeMode::ReadOnly;
    std::uint32_t trading_date = 0, budget_ms = 1000;
    std::size_t index_capacity = 1024, event_batch = 128, snapshot_limit = 4096;
};

// 同一实例串行调用；SPI/StateSink 回调可重入查询。调用期间对象不得被销毁。
// 回调只借用 WT 对象；消费者保留时自行 retain。release/disconnect 清理连接而不删除对象。
class ManagedTrader : public wtp::ITraderApi
{
public:
    explicit ManagedTrader(ProviderKind);
    ~ManagedTrader() override;
    Status configure(const ManagedTraderConfig&, std::shared_ptr<ExecutionEndpoint>,
        std::shared_ptr<AuthorizationVerifier>, std::shared_ptr<ExecutionStateSink> = {});
    SubmissionReceipt submit(const SignedCommand&, const wtp::WTSEntrust&);
    SubmissionReceipt cancel(const SignedCommand&, const wtp::WTSEntrustAction&);
    Status poll_reports();
    Status poll_reports(std::size_t limit, std::uint32_t budget_ms);
    // 只读诊断不触发WT归约器，也不推进消费游标，delivery_unknown期间仍可使用。
    Status inspect_reports(std::uint64_t after, std::size_t limit, std::uint32_t budget_ms, std::vector<ExecutionEvent>&);
    Status reconcile();
    Status stop();
    Status retry_consumer_isolation();
    ExecutionState state() const;
    ExecutionCapabilities capabilities() const;
    bool init(wtp::WTSVariant*) override;
    void release() override;
    void registerSpi(wtp::ITraderSpi*) override;
    void connect() override;
    void disconnect() override;
    bool isConnected() override;
    bool makeEntrustID(char*, int) override;
    int login(const char*, const char*, const char*) override;
    int logout() override;
    int orderInsert(wtp::WTSEntrust*) override;
    int orderAction(wtp::WTSEntrustAction*) override;
    int queryAccount() override;
    int queryPositions() override;
    int queryOrders() override;
    int queryTrades() override;
private:
    SubmissionReceipt execute(const SignedCommand&, const OrderFields&);
    Status ready(const Capability&, bool write) const;
    void publish(const Status&, const std::string& = {}, SubmissionStage = SubmissionStage::NotCalled);
    int deliver_query(const std::function<void()>&);
    int deliver_baseline(unsigned bit, const std::function<void()>&);
    int query_failure(const Status&);
    template<class T> Status validate(const ExecutionSnapshot<T>&, bool latest_account = false) const;
    Status establish_baseline();
    Status begin_resume();
    Status finish_resume();
    Status revoke_channel();
    Status isolate_consumer(const char* reason);
    ProviderKind provider_;
    ManagedTraderConfig config_;
    std::shared_ptr<ExecutionEndpoint> endpoint_;
    std::shared_ptr<AuthorizationVerifier> verifier_;
    std::shared_ptr<ExecutionStateSink> state_sink_;
    wtp::ITraderSpi* spi_ = nullptr;
    mutable std::recursive_mutex mutex_;
    ExecutionState state_;
    std::uint64_t cursor_ = 0, entrust_sequence_ = 0;
    bool recovery_required_ = false, dispatching_reports_ = false, executing_ = false, close_pending_ = false;
    bool baseline_ready_ = false, delivery_unknown_ = false;
    bool restoring_channel_ = false;
    bool revoking_channel_ = false;
    bool account_observer_active_ = false;
    RetainedResumeProof resume_proof_;
    unsigned baseline_delivered_ = 0, baseline_dispatching_ = 0;
    ExecutionBootstrap bootstrap_;
    std::map<std::string, TradeRecord> native_trades_;
    std::map<std::uint64_t, ExecutionEvent> delivered_;
    struct DerivedReceipt { SignedCommand command; OrderFields fields; SubmissionReceipt receipt; };
    std::map<std::string, DerivedReceipt> derived_;
};
}
