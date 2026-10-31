#pragma once
#include "ShmAccountMapping.h"
#include "AccountEventMatch.h"
#include "GuanhengCommon/QmtHostTradeClient.h"

namespace guanheng { namespace bootstrap {
// 本调用有限有效载荷预算；不等同分配器的实际物理内存。
// 子预算不超过total，三个值均须为1..64MiB。行数沿已核profile及固定绑定。
struct QmtAccountIdentityBudget {
 std::size_t max_lookup_bytes=0;
 std::size_t max_identity_view_bytes=0;
 std::size_t max_total_bytes=0;
};
// 独立事件来源；两SHA为本地派生诊断，不充当查询receipt或源event proof。
struct QmtTradeEventProvenance {
 QmtTradeEventSource source;
 QmtTradeEventRequestBounds original_bounds;
 std::size_t event_index=0;
 std::uint64_t sequence=0;
 std::string kind,page_json,read_profile_body;
 std::size_t read_result_capacity=0,admitted_event_page_capacity=0;
 std::string derived_page_sha256,derived_event_sha256;
};
struct QmtEventQueryIdentityBudget {
 QmtAccountIdentityBudget identity;
 AccountEventMatchLimits match{};
 std::size_t max_work_bytes=0; // 1..64MiB，整个同票据逻辑并存峰值上限
};
struct QmtEventQueryProvenance {
 QmtAccountResult original_query; // 只接原Core已验证值；完整复制一次，绝不筛rows
 std::size_t original_row_index=0, original_row_count=0;
 std::string derived_row_sha256; // 唯一Writer重编码的派生摘要，不冒充原线上行片段
};
struct QmtIdentityBrokerProof {
 // 原lookup已验的实际证明类型；不能由当前金融补查推导。
 QmtTradeBrokerProofKind kind=QmtTradeBrokerProofKind::None;
 bool dispatched=false, has_broker_proof=false;
 // 两个presence位决定对应历史字段有效性；原query_row_index=0是合法下标。
 bool has_event=false, has_query=false;
 QmtTradeEventSource event_source; // 历史Reference.source，区别于当前trigger；历史query B保留在原lookup
 std::uint64_t source_sequence=0, query_row_index=0;
 std::string source_event_sha256, query_request_id, query_result_sha256;
 std::size_t lookup_response_index=static_cast<std::size_t>(-1);
 std::string lookup_sha256;
};

struct QmtAccountIdentityResult {
 Status status;
 AccountBatch batch;
 std::vector<std::string> identity_views;
 // 每个token的原回复仅一份，新身份视图用索引和摘要引用。
 std::vector<std::string> lookup_responses;
 // 旧普通Query入口恒null；事件路径共享有限原事件来源。
 std::shared_ptr<const QmtTradeEventProvenance> event_provenance;
 // EventQuery完整原查询与历史证明；旧Query/Event保持null/空。
 std::shared_ptr<const QmtEventQueryProvenance> query_provenance;
 std::vector<QmtIdentityBrokerProof> broker_proofs;
};
class QmtAccountIdentityCandidate;
class QmtAccountIdentityPlan;
class QmtAccountIdentityResolved;
struct QmtAccountIdentityBegin;
// Query/Event/EventQuery业务try捕获std::bad_alloc时返回IoError/空reason；不重授原D。
// 结构Status与旧非法句柄前置诊断保持；此约定不声明所有入口为noexcept。
QmtAccountIdentityBegin begin_qmt_account_identity(unsigned,const QmtAccountResult&,
 const AccountBinding&,wtp::IBaseDataMgr*,const QmtAccountIdentityBudget&,SignedHttpDeadline&);
QmtAccountIdentityBegin begin_qmt_trade_event_identity(const QmtTradeEventPage&,
 const QmtTradeEventRequestBounds&,std::size_t,const QmtExpectedTrade&,
 const AccountBinding&,wtp::IBaseDataMgr*,const QmtAccountIdentityBudget&,SignedHttpDeadline&);
// 仅owner创建WT；两原输入借用至返回，成功后Sources独立持有。
// 同原D贯穿匹配/构造/发布，无SPI/I/O；容量、资源、非法输入与匹配失败沿Status区分。
QmtAccountIdentityBegin begin_qmt_event_query_identity(
 const QmtTradeEventPage&, const QmtTradeEventRequestBounds&, std::size_t,
 const QmtAccountResult&, std::size_t, const QmtExpectedTrade&,
 const AccountBinding&, wtp::IBaseDataMgr*, const QmtEventQueryIdentityBudget&, SignedHttpDeadline&);
// 返回holder/State建立前bad_alloc沿原接口传播；值参数Plan已消耗，Candidate仍由原owner回收。
// holder建立后资源失败以IoError/空reason表达，适用于Query/Event/EventQuery；
// 不分配应急holder或刷新原D。
std::unique_ptr<QmtAccountIdentityResolved> resolve_qmt_account_identity(
 std::unique_ptr<QmtAccountIdentityPlan>,QmtHostTradeClient&);
// 可识别EventQuery的Candidate/Resolved：前置诊断与异常出口固定code/空reason，无额外分配。
// 错owner/错ticket保留双方且不触WT；双空无来源句柄沿旧InvalidInput文本边界。
QmtAccountIdentityResult finish_qmt_account_identity(
 std::unique_ptr<QmtAccountIdentityCandidate>&,std::unique_ptr<QmtAccountIdentityResolved>&);

// 只在begin所在owner保留、完成和销毁；worker从不接收该句柄。
class QmtAccountIdentityCandidate {
public:
 ~QmtAccountIdentityCandidate();
 QmtAccountIdentityCandidate(const QmtAccountIdentityCandidate&)=delete;
 QmtAccountIdentityCandidate& operator=(const QmtAccountIdentityCandidate&)=delete;
private:
 struct State;std::unique_ptr<State> state_;
 QmtAccountIdentityCandidate();
 friend QmtAccountIdentityBegin begin_qmt_account_identity(unsigned,const QmtAccountResult&,
  const AccountBinding&,wtp::IBaseDataMgr*,const QmtAccountIdentityBudget&,SignedHttpDeadline&);
 friend QmtAccountIdentityBegin begin_qmt_trade_event_identity(const QmtTradeEventPage&,
  const QmtTradeEventRequestBounds&,std::size_t,const QmtExpectedTrade&,
  const AccountBinding&,wtp::IBaseDataMgr*,const QmtAccountIdentityBudget&,SignedHttpDeadline&);
 friend QmtAccountIdentityBegin begin_qmt_event_query_identity(
  const QmtTradeEventPage&,const QmtTradeEventRequestBounds&,std::size_t,
  const QmtAccountResult&,std::size_t,const QmtExpectedTrade&,
  const AccountBinding&,wtp::IBaseDataMgr*,const QmtEventQueryIdentityBudget&,SignedHttpDeadline&);
 friend QmtAccountIdentityResult finish_qmt_account_identity(
  std::unique_ptr<QmtAccountIdentityCandidate>&,std::unique_ptr<QmtAccountIdentityResolved>&);
};
// 私有不可复制计划只含独立值；可以移交worker，原输入和Candidate可先退役。
class QmtAccountIdentityPlan {
public:
 ~QmtAccountIdentityPlan();
 QmtAccountIdentityPlan(const QmtAccountIdentityPlan&)=delete;
 QmtAccountIdentityPlan& operator=(const QmtAccountIdentityPlan&)=delete;
private:
 struct State;std::unique_ptr<State> state_;
 QmtAccountIdentityPlan();
 friend QmtAccountIdentityBegin begin_qmt_account_identity(unsigned,const QmtAccountResult&,
  const AccountBinding&,wtp::IBaseDataMgr*,const QmtAccountIdentityBudget&,SignedHttpDeadline&);
 friend QmtAccountIdentityBegin begin_qmt_trade_event_identity(const QmtTradeEventPage&,
  const QmtTradeEventRequestBounds&,std::size_t,const QmtExpectedTrade&,
  const AccountBinding&,wtp::IBaseDataMgr*,const QmtAccountIdentityBudget&,SignedHttpDeadline&);
 friend QmtAccountIdentityBegin begin_qmt_event_query_identity(
  const QmtTradeEventPage&,const QmtTradeEventRequestBounds&,std::size_t,
  const QmtAccountResult&,std::size_t,const QmtExpectedTrade&,
  const AccountBinding&,wtp::IBaseDataMgr*,const QmtEventQueryIdentityBudget&,SignedHttpDeadline&);
 friend std::unique_ptr<QmtAccountIdentityResolved> resolve_qmt_account_identity(
  std::unique_ptr<QmtAccountIdentityPlan>,QmtHostTradeClient&);
};
// worker完成值无WT引用；仅const状态可见，晚完成可在任意线程销毁。
class QmtAccountIdentityResolved {
public:
 ~QmtAccountIdentityResolved();
 QmtAccountIdentityResolved(const QmtAccountIdentityResolved&)=delete;
 QmtAccountIdentityResolved& operator=(const QmtAccountIdentityResolved&)=delete;
 const Status& status() const noexcept;
private:
 struct State;std::unique_ptr<State> state_;
 QmtAccountIdentityResolved();
 friend QmtAccountIdentityBegin begin_qmt_event_query_identity(
  const QmtTradeEventPage&,const QmtTradeEventRequestBounds&,std::size_t,
  const QmtAccountResult&,std::size_t,const QmtExpectedTrade&,
  const AccountBinding&,wtp::IBaseDataMgr*,const QmtEventQueryIdentityBudget&,SignedHttpDeadline&);
 friend std::unique_ptr<QmtAccountIdentityResolved> resolve_qmt_account_identity(
  std::unique_ptr<QmtAccountIdentityPlan>,QmtHostTradeClient&);
 friend QmtAccountIdentityResult finish_qmt_account_identity(
  std::unique_ptr<QmtAccountIdentityCandidate>&,std::unique_ptr<QmtAccountIdentityResolved>&);
};
struct QmtAccountIdentityBegin {
 Status status;
 std::unique_ptr<QmtAccountIdentityCandidate> candidate;
 std::unique_ptr<QmtAccountIdentityPlan> plan;
 QmtAccountIdentityBegin();
 ~QmtAccountIdentityBegin();
 QmtAccountIdentityBegin(QmtAccountIdentityBegin&&) noexcept;
 QmtAccountIdentityBegin& operator=(QmtAccountIdentityBegin&&) noexcept;
 QmtAccountIdentityBegin(const QmtAccountIdentityBegin&)=delete;
 QmtAccountIdentityBegin& operator=(const QmtAccountIdentityBegin&)=delete;
};

// begin仅owner执行金融构造/重复预检；resolve只在客户端owner消费原absolute D。
// finish错owner或错ticket保留两个句柄；同owner同ticket终态才消费并发布整批。
// 本兼容入口顺序复用三阶段；无SPI，external/unresolved仍保留真实金融批次。
QmtAccountIdentityResult map_shm_account_identity_batch(unsigned stage,
 const QmtAccountResult&,const AccountBinding&,wtp::IBaseDataMgr*,
 QmtHostTradeClient&,const QmtAccountIdentityBudget&,SignedHttpDeadline&);
}}
