#pragma once
#include "QmtHostAccountClient.h"

namespace guanheng
{
// 内部封闭描述；调用方不能提供operation、路径、validator或执行callback。
enum class QmtBoundProfile { FullTickV1, History1mV2, FullTickV3, History1mV3, AccountV3, AccountV4, FullTickV6, FullTickRetainedV6 };
// 公开交易能力快照；私有 binding 摘要由部署调用者另核。
struct QmtTradeReadDescriptor
{
    std::string binding_sha256;
    std::uint64_t max_commands=0, max_command_bytes=0, max_command_ttl_ms=0;
    std::uint64_t max_call_result_bytes=0, max_events=0, max_event_bytes=0;
    std::uint64_t max_total_event_bytes=0, max_event_page_bytes=0;
};
// 纯准入完整 v4/control2；结构/绑定失败返回原Status，成功一次发布完整快照。
// std::bad_alloc原样传播且不构造错误诊断；所有失败均保留out原值。
// 调用方不得以.ok()/bool将资源异常改作输入不合法；在自身资源边界精确处理。
Status validate_qmt_trade_read_profile(const std::string& raw, std::size_t max_result_bytes,
    const QmtExpectedAccount& expected, QmtTradeReadDescriptor& out);
class QmtBoundReadCore
{
public:
    QmtBoundReadCore(QmtHttpConfig, QmtBoundProfile, const QmtHistoryControl* = nullptr, const QmtExpectedAccount* = nullptr);
    ~QmtBoundReadCore();
    Status prepare(std::uint32_t milliseconds); // 原v1语义
    Status prepare(SignedHttpDeadline&);
    SourceSession session() const;
    Capability capability() const;
    QmtBoundResult read_full_tick(const std::string&, std::uint32_t milliseconds);
    QmtBoundResult resume(const QmtBoundReceipt&, std::uint32_t milliseconds);
    Status confirm_full_tick(const QmtBoundResult&, std::uint32_t milliseconds);
    QmtHistoryPreparation create_history(const QmtHistoryRequest&, SignedHttpDeadline&);
    QmtHistoryResult submit_history(std::unique_ptr<QmtPreparedHistoryRead>, SignedHttpDeadline&);
    QmtHistoryResult resume_history(const QmtBoundReceipt&, SignedHttpDeadline&);
    QmtAccountPreparation create_account(QmtAccountDatatype, SignedHttpDeadline&);
    QmtAccountResult submit_account(std::unique_ptr<QmtPreparedAccountRead>, SignedHttpDeadline&);
    QmtAccountResult resume_account(const QmtBoundReceipt&, SignedHttpDeadline&);
    Status prepare(SignedHttpDeadline&, QmtAccountReadControlResult*, const QmtAccountControl*);
    QmtAccountPreparation create_account(QmtAccountDatatype, SignedHttpDeadline&, QmtAccountReadControlResult*, const QmtAccountControl*);
    QmtAccountResult submit_account(std::unique_ptr<QmtPreparedAccountRead>, SignedHttpDeadline&, QmtAccountReadControlResult*, const QmtAccountControl*);
    QmtAccountResult resume_account(const QmtBoundReceipt&, SignedHttpDeadline&, QmtAccountReadControlResult*, const QmtAccountControl*);
    Status drain_callbacks(std::uint32_t milliseconds) noexcept;
private:
    class RequestControl;
    Status prepare_impl(SignedHttpDeadline&, RequestControl*);
    QmtAccountPreparation create_account_impl(QmtAccountDatatype, SignedHttpDeadline&, RequestControl*);
    QmtHistoryPreparation create_prepared(const std::string&, SignedHttpDeadline&, RequestControl* = nullptr);
    QmtHistoryResult submit_prepared(std::unique_ptr<QmtPreparedHistoryRead>, SignedHttpDeadline&, RequestControl* = nullptr,
        bool* submission_entered = nullptr);
    QmtHistoryResult resume_prepared(const QmtBoundReceipt&, SignedHttpDeadline&, RequestControl* = nullptr);
    class Impl;
    std::unique_ptr<Impl> impl_;
};
}
