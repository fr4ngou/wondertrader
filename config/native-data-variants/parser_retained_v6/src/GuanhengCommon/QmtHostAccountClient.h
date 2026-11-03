#pragma once
#include "QmtHostHistoryClient.h"

namespace guanheng
{
enum class QmtAccountReadVersion { V3, V4 };
enum class QmtAccountDatatype { Position, Order, Deal, Account };
enum class QmtAccountEnvironment { Simulation, Live };
// 部署所有者固定账号与环境；币种CNY、金融profile cny_cash_shsz_v1封闭。
struct QmtExpectedAccount
{
    std::string account_id;
    QmtAccountEnvironment environment = QmtAccountEnvironment::Simulation;
};
// 复用同一停止值和HTTP回调owner，不增加账户停止状态机。
using QmtAccountControl = QmtHistoryControl;
// 请求控制仅借用到同步方法返回；停止关下一跳，不取消已准入HTTP。
enum class QmtAccountReadOutcome { None, Failure, ControlStoppedBeforeStage };
enum class QmtAccountReadStage { None, Binding, Verify, Submit, Result, FinalVerify, Publish };
struct QmtAccountReadControlResult
{
    QmtAccountReadOutcome outcome = QmtAccountReadOutcome::None;
    QmtAccountReadStage stage = QmtAccountReadStage::None;
};
class QmtPreparedAccountRead
{
public:
    const QmtBoundReceipt& receipt() const noexcept { return prepared_->receipt(); }
    const std::string& read_profile_body() const noexcept { return prepared_->read_profile_body(); }
    ~QmtPreparedAccountRead() = default;
    QmtPreparedAccountRead(const QmtPreparedAccountRead&) = delete;
    QmtPreparedAccountRead& operator=(const QmtPreparedAccountRead&) = delete;
private:
    QmtPreparedAccountRead() = default;
    friend class QmtBoundReadCore;
    std::unique_ptr<QmtPreparedHistoryRead> prepared_;
};
struct QmtAccountPreparation
{
    Status status;
    std::unique_ptr<QmtPreparedAccountRead> request;
};
struct QmtAccountResult
{
    QmtBoundResult bound;
    std::string remote_error_code;
};
// 创建线程独占。create只产生本轮有限内存原身份；submit_once消费一次性token。
// 账户观察进程死亡后按新轮重读；调用方不需要跨进程持久化收据。
// resume只GET原UUID；bound保留原终态bytes，成功data_json为原data片段。
// 这里仅核运输/形状与额度，金融字段解释归唯一账户mapper。
class QmtHostAccountClient
{
public:
    QmtHostAccountClient(QmtHttpConfig, QmtExpectedAccount, const QmtAccountControl* = nullptr,
        QmtAccountReadVersion = QmtAccountReadVersion::V3);
    ~QmtHostAccountClient();
    QmtHostAccountClient(const QmtHostAccountClient&) = delete;
    QmtHostAccountClient& operator=(const QmtHostAccountClient&) = delete;
    Status prepare(SignedHttpDeadline&);
    SourceSession session() const;
    Capability capability() const;
    QmtAccountPreparation create_request(QmtAccountDatatype, SignedHttpDeadline&);
    QmtAccountResult submit_once(std::unique_ptr<QmtPreparedAccountRead>, SignedHttpDeadline&);
    QmtAccountResult resume(const QmtBoundReceipt&, SignedHttpDeadline&);
    // 显式按次control与构造control做OR；out为空仍执行请求级停止契约。
    Status prepare(SignedHttpDeadline&, QmtAccountReadControlResult*, const QmtAccountControl*);
    QmtAccountPreparation create_request(QmtAccountDatatype, SignedHttpDeadline&,
        QmtAccountReadControlResult*, const QmtAccountControl*);
    QmtAccountResult submit_once(std::unique_ptr<QmtPreparedAccountRead>, SignedHttpDeadline&,
        QmtAccountReadControlResult*, const QmtAccountControl*);
    QmtAccountResult resume(const QmtBoundReceipt&, SignedHttpDeadline&,
        QmtAccountReadControlResult*, const QmtAccountControl*);
    Status drain_callbacks(std::uint32_t milliseconds) noexcept;
private:
    std::unique_ptr<QmtBoundReadCore> core_;
};
}
