#pragma once

#include "QmtBoundReadCore.h"
#include <rapidjson/document.h>
#include <chrono>
#include <cstdint>
#include <memory>
#include <string>

namespace guanheng
{
class QmtTradeClientCore;

struct QmtExpectedTrade
{
    QmtExpectedAccount account;
    std::string binding_id, binding_sha256;
    bool writes_enabled = false;
};

struct QmtTradeInsert
{
    std::string exchange, code, entrust_id, user_tag, limit_price;
    std::uint64_t quantity = 0;
    bool buy = true;
};

// 可受控保存的原查询身份。修改公开值后须重新完整准入；resume只GET原UUID。
struct QmtTradeReceipt
{
    std::string binding_json, command_body, read_profile_body;
    std::size_t read_result_capacity = 0;
};

enum class QmtTradePhase { NotSent, Queued, Dispatching, DefinitelyNotCalled, SdkReturned, Unknown };

struct QmtTradeResult
{
    Status status;
    QmtTradePhase phase = QmtTradePhase::NotSent;
    QmtTradeReceipt receipt;
    std::string record_json, source_result_json;
    unsigned http_status = 0;
    bool original_record = false;
};

class QmtPreparedTrade
{
public:
    ~QmtPreparedTrade() = default;
    QmtPreparedTrade(const QmtPreparedTrade&) = delete;
    QmtPreparedTrade& operator=(const QmtPreparedTrade&) = delete;
    const QmtTradeReceipt& receipt() const noexcept { return receipt_; }
    std::uint64_t business_deadline_ms() const noexcept { return business_deadline_ms_; }
private:
    QmtPreparedTrade() = default;
    friend class QmtTradeClientCore;
    QmtTradeReceipt receipt_;
    std::shared_ptr<const std::string> owner_;
    std::chrono::steady_clock::time_point deadline_;
    std::uint64_t business_deadline_ms_ = 0;
};

struct QmtTradePreparation
{
    Status status;
    std::unique_ptr<QmtPreparedTrade> request;
};

struct QmtTradeEventSource
{
    std::string binding_json, session_id;
};

// 同次prepare的独立读取配置；公开值不构成来源认证或写资格。
struct QmtTradeEventReadContext
{
    QmtTradeEventSource source;
    std::string read_profile_body;
    QmtTradeReadDescriptor admitted_limits;
    std::size_t read_result_capacity = 0, admitted_event_page_capacity = 0;
};

// 本地停止只关闭下一跳准入；已进入的exchange错误保持Failure。
// POD默认无恢复许可；每次event-only入口先清零，成功不携上一轮失败。
enum class QmtTradeEventReadOutcome { None, Failure, ControlStoppedBeforeStage };
enum class QmtTradeEventReadStage { None, Binding, Status, Page, Publish };
struct QmtTradeEventReadFailure
{
    QmtTradeEventReadOutcome outcome = QmtTradeEventReadOutcome::None;
    QmtTradeEventReadStage stage = QmtTradeEventReadStage::None;
    SignedHttpFailure transport;
    unsigned http_status = 0;
    bool send_attempted = false, response_complete = false;
};

enum class QmtTradeBrokerProofKind { None, Event, AccountQuery };

// 只由lookup完整验证后发布；用于身份覆盖，当前撤单仍须复核实际来源。
struct QmtTradeOrderFacts
{
    std::string account_id, account_type, binding_id, symbol;
    std::string entrust_id, user_tag, sdk_user_order_id;
    bool dispatched = false, has_broker_proof = false;
    std::uint64_t source_sequence = 0;
    std::string source_event_sha256;
    // query原行下标与摘要独立于event序号；无query时类型为None/Event，字段空/0。
    QmtTradeBrokerProofKind broker_proof_kind = QmtTradeBrokerProofKind::None;
    std::string query_request_id, query_result_sha256;
    std::uint64_t query_row_index = 0;
};

// 复用原命令/lookup的完整token准入，不推断前缀或系统归属。
bool valid_qmt_sdk_order_token(const std::string&);

class QmtTradeOrderReference
{
public:
    ~QmtTradeOrderReference() = default;
    QmtTradeOrderReference(const QmtTradeOrderReference&) = delete;
    QmtTradeOrderReference& operator=(const QmtTradeOrderReference&) = delete;
    const QmtTradeReceipt& insert() const noexcept { return insert_; }
    const QmtTradeOrderFacts& facts() const noexcept { return facts_; }
    const std::string& broker_order_id() const noexcept { return broker_order_id_; }
    const QmtTradeEventSource& source() const noexcept { return source_; }
    const std::string& association_error() const noexcept { return association_error_; }
private:
    QmtTradeOrderReference() = default;
    friend class QmtTradeClientCore;
    std::shared_ptr<const std::string> owner_;
    QmtTradeReceipt insert_;
    QmtTradeEventSource source_;
    QmtTradeOrderFacts facts_;
    std::string broker_order_id_, association_error_;
    std::string query_binding_json_;
};

enum class QmtTradeLookupKind { WtIdentity, SdkToken };
struct QmtTradeLookup
{
    QmtTradeLookupKind kind = QmtTradeLookupKind::WtIdentity;
    std::string entrust_id, user_tag, sdk_user_order_id;
};
struct QmtTradeLookupResult
{
    Status status;
    std::unique_ptr<QmtTradeOrderReference> reference;
    std::string reference_json;
    unsigned http_status = 0;
    // 原有限回复含失败/截断上下文；仅完整标准unknown_order可证明未登记。
    std::string response_body;
    bool response_complete = false, not_found = false;
};
// 仅Core从真实只读lookup发布；实际取消历史与本次申请分别保存。
// 句柄只在创建client的线程使用；跨轮可保存receipt并public resume原UUID。
class QmtTradeCancelReference
{
public:
    ~QmtTradeCancelReference() = default;
    QmtTradeCancelReference(const QmtTradeCancelReference&) = delete;
    QmtTradeCancelReference& operator=(const QmtTradeCancelReference&) = delete;
    QmtTradeCancelReference(QmtTradeCancelReference&&) noexcept = default;
    QmtTradeCancelReference& operator=(QmtTradeCancelReference&&) noexcept = default;
    const QmtTradeReceipt& receipt() const noexcept { return receipt_; }
    QmtTradePhase phase() const noexcept { return phase_; }
    const std::string& record_json() const noexcept { return record_json_; }
private:
    QmtTradeCancelReference() = default;
    friend class QmtTradeClientCore;
    std::shared_ptr<const std::string> owner_;
    QmtTradeReceipt receipt_;
    QmtTradePhase phase_ = QmtTradePhase::Unknown;
    std::string record_json_, original_command_id_, original_command_sha256_;
};
struct QmtTradeCancelLookupResult
{
    Status status;
    bool no_cancel = false;
    std::unique_ptr<QmtTradeCancelReference> reference;
    std::string response_body;
    unsigned http_status = 0;
    bool response_complete = false;
};

struct QmtTradeEventPage
{
    Status status;
    QmtTradeEventSource source;
    std::string page_json;
    std::uint64_t next_sequence = 0, durable_through = 0, source_ack_through = 0;
    std::size_t event_count = 0;
    unsigned http_status = 0;
    bool gap = false;
    // 同次Core真实prepare/refresh上下文；成功返回才发布，失败保持空/0。
    std::string read_profile_body;
    std::size_t read_result_capacity = 0, admitted_event_page_capacity = 0;
};

// 原events调用参数的独立副本，由可信Task冻结；不从响应前沿反推。
struct QmtTradeEventRequestBounds
{
    std::uint64_t after_seq = 0;
    std::size_t limit = 0, max_bytes = 0;
};

// DOM拥有独立内存，可移动、不可复制；仅表示纯校验结果，不认证Host来源。
struct QmtValidatedTradeEventPage
{
    rapidjson::Document source_binding;
    rapidjson::Document document;
    std::uint64_t next_sequence = 0, durable_through = 0, source_ack_through = 0;
    std::size_t event_count = 0;
    bool gap = false;
};

// expected/已验limits/实际Host页cap必须来自可信上下文；本函数无HTTP/WT操作。
// 原D不续，失败/异常保留out；成功一次交换独立DOM和派生值。
// 实际HTTP上限由Core和宿主私有配置核，不能以本参数重建HTTP配置。
Status validate_qmt_trade_event_page(
    const std::string& page_json,
    const QmtTradeEventSource& source,
    const QmtTradeEventRequestBounds& original_request,
    const QmtExpectedTrade& expected,
    const QmtTradeReadDescriptor& admitted_limits,
    std::size_t admitted_event_page_capacity,
    SignedHttpDeadline& original_deadline,
    QmtValidatedTradeEventPage& out);

// 创建线程独占；不启动线程、不调用SDK。prepare/create/submit/GET沿调用方原D，
// submit_once只发一次POST。原结果未知保留receipt，后继只resume原ID。
// WinHTTP晚回调仍归唯一HTTP owner；对象和DLL存活到drain_callbacks确认成功。
class QmtHostTradeClient
{
public:
    QmtHostTradeClient(QmtHttpConfig, QmtExpectedTrade);
    ~QmtHostTradeClient();
    QmtHostTradeClient(const QmtHostTradeClient&) = delete;
    QmtHostTradeClient& operator=(const QmtHostTradeClient&) = delete;
    Status prepare(SignedHttpDeadline&);
    // 原D贯穿prepare及全部复制；失败/异常保持out，成功一次无异常移动发布。
    Status prepare_event_read_context(SignedHttpDeadline&, QmtTradeEventReadContext& out);
    // event-only单次两跳准备；control借用至本次调用返回，原D/owner优先。
    Status prepare_event_read_context(SignedHttpDeadline&, QmtTradeEventReadContext& out,
        QmtTradeEventReadFailure*, const QmtAccountControl*);
    bool accepting_commands() const;
    QmtTradeEventSource event_source() const;
    QmtTradePreparation create_insert(const QmtTradeInsert&, SignedHttpDeadline&);
    QmtTradePreparation create_cancel(const QmtTradeOrderReference&, SignedHttpDeadline&);
    QmtTradeResult submit_once(std::unique_ptr<QmtPreparedTrade>, SignedHttpDeadline&);
    QmtTradeResult resume(const QmtTradeReceipt&, SignedHttpDeadline&);
    QmtTradeLookupResult lookup(const QmtTradeLookup&, SignedHttpDeadline&);
    // lookup只读，不授新写；同轮全部验证/复制共用原D，末核后一次发布。
    QmtTradeCancelLookupResult lookup_cancel(const QmtTradeOrderReference&, SignedHttpDeadline&);
    // 错owner/过D仍保原receipt和Unknown；只GET实际取消原UUID，不POST。
    QmtTradeResult resume_cancel(const QmtTradeCancelReference&, SignedHttpDeadline&);
    QmtTradeEventPage events(const QmtTradeEventSource&, std::uint64_t after,
        std::size_t limit, std::size_t max_bytes, SignedHttpDeadline&);
    // 与旧events共用同一校验；额外固定失败事实只供事件读取owner判断。
    QmtTradeEventPage events(const QmtTradeEventSource&, std::uint64_t after,
        std::size_t limit, std::size_t max_bytes, SignedHttpDeadline&,
        QmtTradeEventReadFailure*, const QmtAccountControl*);
    Status drain_callbacks(std::uint32_t milliseconds) noexcept;
private:
    // 仅Standard原提交owner调用：审计期核独立券商终态资格，全部原组O→P退休后在新insert前再核。
    // 前一阶段Standard仍保原提交fence；本方法不对外提供清未知入口，不清硬故障或关闭。
    friend class StandardQmtTrader;
    Status reconcile_observation(SignedHttpDeadline&);
    std::unique_ptr<QmtTradeClientCore> core_;
};
}
