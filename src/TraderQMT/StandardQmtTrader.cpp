#include "StandardQmtTrader.h"
#include "EventDeliveryIndex.h"
#include "GuanhengQmtBootstrap/QmtAccountIdentity.h"
#include "StandardEventBudget.h"
#include "StandardReadFailure.h"
#include "GuanhengQmtBootstrap/JsonBoundary.h"
#include "GuanhengCommon/QmtAccountFields.h"
#include "GuanhengCommon/QmtHostCodec.h"
#include "Includes/WTSVariant.hpp"
#include "Includes/WTSTradeDef.hpp"
#include "Includes/WTSContractInfo.hpp"
#include "Includes/WTSError.hpp"
#include "Includes/IBaseDataMgr.h"
#include <algorithm>
#include <atomic>
#include <chrono>
#include <charconv>
#include <cmath>
#include <condition_variable>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <deque>
#include <limits>
#include <iterator>
#include <new>
#include <map>
#include <mutex>
#include <stdexcept>
#include <thread>
#include <type_traits>
#include <utility>

#if defined(_WIN32) && defined(GH_QMT_STANDARD_EVENT_TESTING)
#include <Windows.h>
// 只编入隔离测试DLL：真实Common完成后、发布锁之前等待，不改结果、原D或准入状态。
namespace {
std::atomic<unsigned> standard_event_test_kind{0};
std::atomic<HANDLE> standard_event_test_entered{nullptr},standard_event_test_release{nullptr};
std::atomic<std::int64_t> standard_event_test_deadline{0};
void standard_event_test_publish(unsigned kind,std::chrono::steady_clock::time_point deadline)noexcept
{
 if(!kind)return;unsigned expected=kind;
 if(!standard_event_test_kind.compare_exchange_strong(expected,0))return;
 standard_event_test_deadline.store(static_cast<std::int64_t>(deadline.time_since_epoch().count()));
 if(!SetEvent(standard_event_test_entered.load())
  ||WaitForSingleObject(standard_event_test_release.load(),15000)!=WAIT_OBJECT_0)ExitProcess(94);
}
}
extern "C" __declspec(dllexport) bool gh_qmt_standard_test_event_publish_gate(unsigned kind,HANDLE entered,HANDLE release)noexcept
{
 if((kind!=1&&kind!=2)||!entered||!release||standard_event_test_kind.load())return false;
 standard_event_test_entered.store(entered);standard_event_test_release.store(release);
 standard_event_test_deadline.store(0);standard_event_test_kind.store(kind);return true;
}
extern "C" __declspec(dllexport) std::int64_t gh_qmt_standard_test_event_deadline_ticks()noexcept
{return standard_event_test_deadline.load();}
#endif

namespace guanheng {
namespace {
using Clock=std::chrono::steady_clock;
using namespace bootstrap;
std::mutex registry_mutex;
std::map<wtp::ITraderApi*,StandardQmtTrader*> objects;
std::map<std::string,StandardQmtTrader*> instances;
std::atomic<std::uint64_t> generations{1};
void require(bool condition,const char* reason){if(!condition)throw std::runtime_error(reason);}
Status failure(ErrorCode code,const char* reason){return {code,reason};}
Status fixed_failure(ErrorCode code)noexcept{Status value;value.code=code;return value;}
static_assert(std::is_nothrow_move_assignable<Status>::value,"owner Status transfer must not allocate");
struct EventCapacity final:std::exception {const char* what()const noexcept override{return "qmt_standard_event_capacity";}};
struct EventOperationFailure final:std::exception {ErrorCode code;explicit EventOperationFailure(ErrorCode value)noexcept:code(value){}
 const char* what()const noexcept override{return "qmt_standard_event_operation_failed";}};
struct EventRowCounter {using Ch=char;std::size_t size=0,limit;
 void Put(char){if(size==limit)throw EventCapacity{};++size;}void Flush(){} };
std::string event_row_text(const rapidjson::Value& row,std::size_t cap)
{EventRowCounter output{0,cap};rapidjson::Writer<EventRowCounter> writer(output);
 require(row.Accept(writer),"qmt_standard_event_row_encoding");return bootstrap::json_text(row);}
std::size_t add_size(std::size_t lhs,std::size_t rhs)
{require(rhs<=(std::numeric_limits<std::size_t>::max)()-lhs,"qmt_standard_payload_overflow");return lhs+rhs;}
std::size_t times_size(std::size_t value,unsigned count)
{std::size_t total=0;while(count--)total=add_size(total,value);return total;}
bool same_event_source(const QmtTradeEventSource& lhs,const QmtTradeEventSource& rhs)
{return lhs.binding_json==rhs.binding_json&&lhs.session_id==rhs.session_id;}
std::size_t bytes(const QmtTradeReceipt& value)
{return add_size(add_size(value.binding_json.size(),value.command_body.size()),value.read_profile_body.size());}
std::size_t bytes(const QmtAccountResult& value)
{
 const auto& b=value.bound;const auto& r=b.result;
 std::size_t n=0;for(const auto* s:{&r.data_json,&r.envelope_json,&r.request_id,&r.operation_id,
  &r.status.reason,&b.receipt.binding_json,&b.receipt.request_body,&b.receipt.read_profile_body,
  &b.native_result_json,&value.remote_error_code})n=add_size(n,s->size());return n;
}
std::size_t bytes(const QmtTradeResult& value)
{return add_size(add_size(bytes(value.receipt),value.record_json.size()),add_size(value.source_result_json.size(),value.status.reason.size()));}
bool integer_type(const wtp::WTSVariant* value)
{return value&&(value->type()==wtp::WTSVariant::VT_Int32||value->type()==wtp::WTSVariant::VT_Uint32
 ||value->type()==wtp::WTSVariant::VT_Int64||value->type()==wtp::WTSVariant::VT_Uint64);}
std::uint64_t config_number(wtp::WTSVariant* cfg,const char* key,std::uint64_t low,std::uint64_t high)
{require(integer_type(cfg->get(key)),"qmt_standard_config_integer_required");auto n=cfg->getUInt64(key);require(n>=low&&n<=high,"qmt_standard_config_integer_range");return n;}
std::string config_text(wtp::WTSVariant* cfg,const char* key,std::size_t cap,bool bounded_native=false)
{
 auto value=cfg->get(key);require(value&&value->type()==wtp::WTSVariant::VT_String,"qmt_standard_config_text_required");
 if(bounded_native){
  // 原公开API只借用C-string；首NUL是唯一正文终止，先有界扫描再复制同一前缀。
  // 隐藏std::string后缀不可由此接口观察，不再调用按值asString/getString。
  const char* text=value->asCString();std::size_t n=0;
  if(text)while(n<=cap&&text[n])++n;
  require(text&&n>0&&n<=cap,"qmt_standard_config_text_range");return {text,n};
 }
 auto out=cfg->getString(key);require(!out.empty()&&out.size()<=cap&&out.find('\0')==std::string::npos,"qmt_standard_config_text_range");return out;
}
bool config_bool(wtp::WTSVariant* cfg,const char* key)
{auto value=cfg->get(key);require(value&&value->type()==wtp::WTSVariant::VT_Boolean,"qmt_standard_config_boolean_required");return cfg->getBoolean(key);}
std::string copied(const char* value,std::size_t cap=63)
{require(value!=nullptr,"qmt_standard_null_text");std::size_t n=0;while(n<=cap&&value[n])++n;require(n<=cap,"qmt_standard_text_limit");return {value,n};}
bool valid_day(unsigned day)
{
 unsigned year=day/10000,month=day/100%100,date=day%100;
 if(year<1||year>9999||month<1||month>12)return false;
 unsigned days[]={31,28,31,30,31,30,31,31,30,31,30,31};
 if(year%4==0&&(year%100!=0||year%400==0))days[1]=29;return date>0&&date<=days[month-1];
}
std::string price_text(double value,double tick)
{require(std::isfinite(value)&&value>0,"qmt_standard_price_invalid");
 char buffer[128];const auto out=std::to_chars(buffer,buffer+sizeof(buffer),value,std::chars_format::general);
 require(out.ec==std::errc{},"qmt_standard_price_encoding_failed");const std::string original(buffer,out.ptr);
 // 原股票执行器以整数档位乘double tick，2.885可产生2.8850000000000002。
 // 仅消除已落在WT合约档位附近的浮点运算误差；真实离档价格保持原文，由Source原规则核验。
 if(!std::isfinite(tick)||tick<=0)return original;
 const double steps=std::round(value/tick),canonical=steps*tick;
 const double tolerance=4*std::numeric_limits<double>::epsilon()*(std::max)(value,std::fabs(canonical));
 if(!std::isfinite(steps)||steps<1||steps>9007199254740991.0||!std::isfinite(canonical)
  ||tolerance>=tick/4||std::fabs(value-canonical)>tolerance)return original;
 const auto encoded_tick=std::to_chars(buffer,buffer+sizeof(buffer),tick,std::chars_format::general);
 require(encoded_tick.ec==std::errc{},"qmt_standard_price_encoding_failed");const std::string text(buffer,encoded_tick.ptr);
 const auto e=text.find_first_of("eE"),dot=text.find('.');const auto end=e==std::string::npos?text.size():e;
 int exponent=0;
 if(e!=std::string::npos){const char* first=text.data()+e+1;if(*first=='+')++first;
  const auto parsed=std::from_chars(first,text.data()+text.size(),exponent);
  if(parsed.ec!=std::errc{}||parsed.ptr!=text.data()+text.size())return original;}
 const int precision=(std::max)(0,(dot!=std::string::npos?static_cast<int>(end-dot-1):0)-exponent);
 if(precision>18)return original;
 const auto normalized=std::to_chars(buffer,buffer+sizeof(buffer),canonical,std::chars_format::fixed,precision);
 require(normalized.ec==std::errc{},"qmt_standard_price_encoding_failed");return {buffer,normalized.ptr};}
struct OrderValue {
 QmtTradeInsert insert;std::string broker;double price=0;bool net=false;
 wtp::WTSDirectionType direction=wtp::WDT_LONG;
 wtp::WTSOffsetType offset=wtp::WOT_OPEN;
 std::size_t payload()const {
  std::size_t n=0;for(const auto* s:{&insert.exchange,&insert.code,&insert.entrust_id,&insert.user_tag,&insert.limit_price,&broker})n=add_size(n,s->size());return n;
 }
};
OrderValue copy_order(const wtp::WTSEntrust& value)
{
 OrderValue out;auto& q=out.insert;q.exchange=copied(value.getExchg());q.code=copied(value.getCode());
 q.entrust_id=copied(value.getEntrustID());q.user_tag=copied(value.getUserTag());
 require((q.exchange=="SSE"||q.exchange=="SZSE")&&q.code.size()==6
  &&q.code.find_first_not_of("0123456789")==std::string::npos&&!q.entrust_id.empty()&&!q.user_tag.empty(),"qmt_standard_order_identity_invalid");
 require(value.getBusinessType()==wtp::BT_CASH&&value.getPriceType()==wtp::WPT_LIMITPRICE
  &&value.getOrderFlag()==wtp::WOF_NOR,"qmt_standard_order_type_unsupported");
 out.direction=value.getDirection();out.offset=value.getOffsetType();out.net=value.isNet();
 require((out.direction==wtp::WDT_LONG||out.direction==wtp::WDT_SHORT)
  &&(out.offset==wtp::WOT_OPEN||out.offset==wtp::WOT_CLOSE||out.offset==wtp::WOT_CLOSETODAY||out.offset==wtp::WOT_CLOSEYESTERDAY),"qmt_standard_order_side_invalid");
 q.buy=out.net?value.isBuy():((out.direction==wtp::WDT_LONG&&out.offset==wtp::WOT_OPEN)
  ||(out.direction==wtp::WDT_SHORT&&out.offset!=wtp::WOT_OPEN));
 auto volume=value.getVolume();require(std::isfinite(volume)&&volume>0&&volume<=9007199254740991.0
  &&std::floor(volume)==volume,"qmt_standard_volume_invalid");q.quantity=static_cast<std::uint64_t>(volume);out.price=value.getPrice();
 const auto contract=value.getContractInfo();const auto commodity=contract?contract->getCommInfo():nullptr;
 q.limit_price=price_text(out.price,commodity?commodity->getPriceTick():0);return out;
}
struct ObjectRelease {void operator()(wtp::WTSObject* value)const{if(value)value->release();}};
}

struct StandardQmtTrader::Impl {
 enum class PendingOperation { Insert,Cancel };
 enum class PendingRole { OriginalCall,UnadmittedTargetLookup,TargetObservation };
 enum class OrderAuditState { NotStarted,Started,Terminal };
 enum class TargetLookupState { NotObserved,NoCancel,Actual };
 enum class AuditDiagnostic { None,RetryTransport,Deadline,Capacity,IdentityConflict,SourceChanged,HardFault,Stopping };
 struct TradeObservation {
  QmtTradePhase phase=QmtTradePhase::Unknown;bool has_record=false,broker_terminal=false;
  bool terminal()const noexcept{return has_record&&(phase==QmtTradePhase::SdkReturned||phase==QmtTradePhase::DefinitelyNotCalled
   ||(phase==QmtTradePhase::Unknown&&broker_terminal));}
 };
 struct CancelObservation {QmtTradeReceipt receipt;TradeObservation observed;};
 struct OrderObservation {QmtBoundReceipt receipt;OrderAuditState state=OrderAuditState::NotStarted;};
 struct Pending {
  QmtTradeReceipt receipt;std::size_t charge=0;
  PendingOperation operation=PendingOperation::Insert;PendingRole role=PendingRole::OriginalCall;
  QmtTradeReceipt target_insert;TradeObservation own;OrderObservation order;
  TargetLookupState target_lookup=TargetLookupState::NotObserved;CancelObservation actual;
  Clock::time_point next_due;std::uint64_t inflight_task=0;
 };
 struct AuditInput {
  QmtTradeReceipt receipt,target_insert;PendingOperation operation;PendingRole role;
  TradeObservation own;OrderObservation order;TargetLookupState target_lookup;CancelObservation actual;
  bool actual_in_other_slot=false;
 };
 struct AuditSummary {
  PendingRole role=PendingRole::OriginalCall;TradeObservation own;OrderObservation order;
  TargetLookupState target_lookup=TargetLookupState::NotObserved;CancelObservation actual;
  AuditDiagnostic diagnostic=AuditDiagnostic::None;ErrorCode error{};bool apply=false;
 };
 enum class Kind { Prepare,Login,Query,Resolve,Insert,Cancel,EventPage,EventQuery,EventResolve,AuditOriginal };
 enum class QueryStep {None,Prepare,Create,ReceiptSaved,SubmitEntered,Returned};
 struct Task {
  Kind kind=Kind::Prepare;unsigned stage=0;std::uint64_t generation=0,id=0,read_generation=0; // 读取票据只跨线程传值，由worker拥有客户端。
  Clock::time_point deadline;OrderValue order;
  Clock::time_point queued_at{}; // 实际进入原任务队列的 steady_clock 时刻；仅用于诊断。
  std::unique_ptr<QmtAccountIdentityPlan> plan;
  bool resume_read=false;QmtBoundReceipt original_read; // 原SDK读取只续核原UUID，不重发POST。
  QmtTradeEventReadContext event_context;QmtTradeEventRequestBounds event_bounds;
  QmtTradeEventReadFailure event_failure;bool event_drain_only=false;
  std::size_t event_index=0,charge=0;std::string pending_key;
 };
 struct Completion {
  Kind kind=Kind::Prepare;unsigned stage=0;std::uint64_t generation=0,id=0,read_generation=0; // 读取票据只跨线程传值，由worker拥有客户端。
  Clock::time_point deadline;Status status;OrderValue order;
  std::int64_t queue_wait_ms=0,running_ms=0; // 原任务实际排队/worker处理毫秒数；纯数值旁证。
  QmtAccountResult account;QmtTradeResult trade;
  bool resume_read=false; // 本完成值只核原读责任；终态不作为新的账户事实交付。
  bool read_not_dispatched=false; // 原Host已确定派发前终结；不含SDK调用责任，不作为账户事实交付。
  bool read_interrupted=false; // 原Host已终结只读观察且无SDK终态；不作为账户事实，原委托责任保持。
  // operation恒为真实调用/本地操作结果；交付跨D仅写独立固定code，发布锁内不分配。
  Status delivery_status;bool late=false,local_failure=false,local_stopped=false;
  QmtBoundReceipt saved_receipt;QmtAccountReadControlResult control_result;
  QueryStep query_step=QueryStep::None;std::size_t event_index=0;
  std::unique_ptr<QmtAccountIdentityResolved> resolved;
  QmtTradeEventReadContext event_context;QmtTradeEventPage event_page;
  QmtTradeEventReadFailure event_failure;
  bool event_drain_pending=false,event_drain_checked=false,event_drain_failed=false,event_read_attempted=false;
  unsigned event_drain_checks=0;
  std::uint64_t event_bootstrap_cursor=0; // 首次Prepare在四查询前取得的Host已持久前沿；不是该小页末序号。
  std::size_t event_bootstrap_reserve=0; // 本次小页沿原ContextBanks.chain预留；保留到原完成值退役。
  bool event_bootstrap_ready=false; // 前沿0也是已核证据，与尚未取得前沿明确区分。
  std::size_t charge=0;bool insert_failure_confirmed=false,business_rejected=false,delivery_fault=false;std::string command_id,capacity_reason;AuditSummary audit;
 };
 // worker在任何业务I/O前取得槽；槽内纯值即使后续抛异常也归实例所有。
 // 只有一个producer，owner只取已commit的头部。额外一个槽仅供无在途值的fatal诊断。
 static_assert(std::is_nothrow_move_assignable<Task>::value,"Task reservation transfer must not allocate");
 static_assert(std::is_nothrow_default_constructible<Completion>::value,"Empty Completion must not allocate");
 static_assert(std::is_nothrow_move_constructible<Completion>::value,"Completion move must not allocate");
 static_assert(std::is_nothrow_move_assignable<Completion>::value,"Completion transfer must not allocate");
 struct CompletionRing {
  std::unique_ptr<Completion[]> slots;std::size_t capacity=0,head=0,count=0;bool reserved=false;
  void initialize(std::size_t ordinary){require(!slots&&ordinary>0,"qmt_standard_completion_ring_init");
   slots.reset(new Completion[ordinary+1]);capacity=ordinary+1;}
  bool empty()const noexcept{return count==0;}
  std::size_t size()const noexcept{return count;}
  bool can_reserve()const noexcept{return slots&&!reserved&&count<capacity-1;}
  Completion& reserve()noexcept{reserved=true;return slots[(head+count)%capacity];}
  Completion* active()noexcept{return reserved?&slots[(head+count)%capacity]:nullptr;}
  bool owns(const Completion& value)noexcept{return active()==&value;}
  void commit()noexcept{reserved=false;++count;}
  Completion& front()noexcept{return slots[head];}
  void pop_front()noexcept{slots[head]=Completion{};head=(head+1)%capacity;--count;}
  bool push_back(Completion&& value)noexcept{
   if(!slots||reserved||count>=capacity)return false;
   slots[(head+count)%capacity]=std::move(value);++count;return true;
  }
  void clear()noexcept{while(count)pop_front();}
 };
 struct NativeIdentity {std::string tag,exchange,code,broker;};
 struct Identity {
  std::string tag,exchange,code,broker;
  std::uint64_t group_id=0;SubmissionObservation observation=SubmissionObservation::None;
  char command_id[37]={};QmtTradeReceipt retained_receipt;std::size_t retained_charge=0;
  // 只标记终态后的查询顺序和来源；不保存或推算账户持仓。
  std::uint64_t terminal_query_barrier=0;char terminal_query_source[65]={};
  double terminal_query_filled=0;
 };
 struct ActiveGroup {
  SubmissionKeyV1 key;std::uint64_t id=0;std::uint32_t accepted=0;bool open=false,failed=false;
 };
 bool query_first=false;ActiveGroup submission;std::uint64_t next_group=0;
 std::atomic<bool> submissions_closed{false},inserts_paused{false};
 std::uint64_t last_order_query=0,last_position_query=0,last_account_query=0;std::uint32_t active_orders=0;
 std::uint64_t submission_refresh_task=0;
 Clock::time_point submission_refresh_after=Clock::time_point::min();
 static constexpr std::size_t submission_fixed_bytes=sizeof(ActiveGroup)+2*sizeof(bool)+3*sizeof(std::uint64_t);

 struct Candidate {std::unique_ptr<QmtAccountIdentityCandidate> value;Clock::time_point deadline;std::size_t charge=0;};
 const std::thread::id owner_thread=std::this_thread::get_id();
 const std::uint64_t generation=generations.fetch_add(1);
 StandardQmtPhase phase=StandardQmtPhase::Created;
 wtp::ITraderSpi* spi=nullptr;
 bool pumping=false,in_callback=false,joined=false,close_started=false;
 std::atomic<bool> initialized{false},connected{false},logged_in{false},stop_requested{false},writes_blocked{false};
 std::atomic<bool> worker_stop{false},worker_live{false};
 std::atomic<std::uint64_t> entrust_sequence{0};
 std::string instance_id,entrust_prefix;
 QmtHttpConfig http;QmtExpectedTrade expected;AccountBinding binding;
 QmtAccountIdentityBudget identity_budget;
 QmtAccountControl account_control,event_control;
 unsigned trading_date=0,request_ms=0,close_ms=0,max_queue=0,max_pending=0;
 // 原任务ID跨query/resolve保持；只有本次SPI返回才交接刷新阶段，不依据账户数值猜完成。
 unsigned observation_refresh_ms=0,observation_refresh_stage=3;
 std::uint64_t observation_refresh_task=0;
 Clock::time_point observation_refresh_at{};
 std::size_t max_queue_bytes=0,payload_bytes=0;unsigned outstanding=0;std::atomic<unsigned> active_ingress{0};
 std::uint64_t next_task=0,worker_thread=0;
 std::mutex mutex;std::condition_variable cv;
 std::deque<Task> tasks;CompletionRing results;
 std::map<std::string,Identity> identities;
 std::map<std::uint64_t,Candidate> candidates;
 // 一份owner续阶段；worker只持Task里的独立context/Plan。reserve保到真实终态或join。
 enum class EventPhase {ReadInFlight,ReadRetryWait,PageReady,QueryInFlight,ResolveInFlight};
 struct QueryEvidence {
  QmtBoundReceipt saved_receipt;QmtAccountResult account;QmtAccountReadControlResult control_result;
  QueryStep step=QueryStep::None;
  std::uint64_t origin_task_id=0,generation=0;std::size_t event_index=0;
  Status query_status,resolve_status,query_delivery_status,resolve_delivery_status;
  bool query_late=false,resolve_late=false,query_received=false,resolve_received=false;
  bool query_local_failure=false,query_local_stopped=false,resolve_local_failure=false,resolve_local_stopped=false;
 };
 struct EventChain {
  QmtTradeEventPage page;QmtValidatedTradeEventPage validated;
  QmtTradeEventRequestBounds bounds;Clock::time_point deadline;
  Clock::time_point started{}; // 本链原建立时刻；诊断计时不改变原绝对D。
  QmtTradeEventReadFailure last_read; // 最近实际读取返回的原运输分类；不保存正文。
  std::int64_t last_queue_wait_ms=0,last_running_ms=0; // 最近已返回原事件任务的排队/处理毫秒数。
  std::unique_ptr<QmtAccountIdentityCandidate> candidate;
  std::size_t index=0;std::uint64_t task_id=0,read_generation=0; // 同一事件链固定原读取票据。
  EventPhase phase=EventPhase::ReadInFlight;
  QueryEvidence query;std::string missing_event_row;QmtEventQueryIdentityBudget query_budget;
  std::size_t query_charge=0;
  Clock::time_point next_attempt_at;QmtTradeEventReadFailure last_transport;
  unsigned attempts=0,drain_checks=0,read_tasks=1,task_limit=0;bool drain_pending=false;
 };
 bool events_enabled=false,event_context_ready=false,event_detached=false;
 unsigned event_poll_ms=1000,query_flow_mask=0;
 std::size_t event_records=0,event_partition=0,context_reserve=0,ordinary_reserve=0,chain_reserve=0;
 std::size_t context_charge=0,chain_charge=0;
 standard_event_budget::Inputs event_budget_input;standard_event_budget::Layout event_layout;
 standard_event_budget::InstanceBanks event_banks;standard_event_budget::ContextBanks event_context_banks;
 QmtTradeEventReadContext event_context;
 std::unique_ptr<QmtEventDeliveryIndex> event_index;
 std::unique_ptr<EventChain> event_chain;
 Clock::time_point next_event_poll_at;
 std::uint64_t read_cursor=0,handled_cursor=0;
 EventChainDiagnosticsV1 event_deadline; // 首次截止旁证；owner冻结，关闭保持。
 bool diagnostic_worker_busy=false; // mutex保护的当前原worker处理状态；不参与调度。
 Kind diagnostic_worker_kind=Kind::Prepare; // 当前原任务种类；busy时有效。
 unsigned diagnostic_worker_stage=0; // 当前原任务datatype；busy时有效。
 std::uint64_t diagnostic_worker_task=0; // 当前原任务ID；不含命令/账户身份。
 Clock::time_point diagnostic_worker_started{}; // 原worker取出任务的steady_clock时刻。
 std::int64_t diagnostic_worker_wait_ms=0; // 原worker取出时冻结的实际排队毫秒数。

 // 这里只保留有限通信收据；券商持仓/资金与业务订单归约仍归WT。
 struct KeyLess {bool operator()(const std::string& a,const std::string& b)const noexcept{return a.compare(b)<0;}};
 std::map<std::string,Pending,KeyLess> pending;
 // unknown只挡新insert；真实硬错/关闭独立挡全部写。解绑独立于可选事件配置。
 std::atomic<bool> unknown_fenced{false},hard_fault{false},audit_detached{false};
 std::atomic<bool> observation_reconciled{false};
 std::atomic<bool> read_waiting{false}; // 暂不可用独立于硬错；原持仓/周期继续保留，新金融准入暂停。
 struct HeldRead {
  QmtBoundReceipt receipt; // 原请求正文、UUID、完整绑定和原profile，观察预算不改原SDK截止。
  std::uint64_t generation=0; // 原worker读取代际票据，原结果确定后才释放。
  unsigned stage=0; // 原账户数据类型；后继只调用resume，不重新调用SDK。
  std::size_t charge=0; // 原查询银行转交，涵盖在途Task/Completion与原收据。
  bool inflight=false; // 同一原UUID仅允许一个续核Task。
 };
 std::map<std::uint64_t,HeldRead> held_reads;

 bool audit_inflight=false,audit_source_ready=false;
 QmtTradeEventSource audit_source;
 std::uint64_t audit_cursor=0;

 // 任务名额与完成值字节分别结算。SPI可重入排队，先归还已终结任务的名额；
 // 完成值及其WT借用仍由pump栈持有，字节额度继续计费到回调退出。
 struct TaskCredit {
  Impl& owner;std::uint64_t id;bool retired=false,transferred=false;
  void retire(){if(id&&!retired&&!transferred){owner.finish_task();retired=true;}}
  void transfer(){transferred=true;}
  ~TaskCredit(){retire();}
 };
 TaskCredit* callback_credit=nullptr;
 // 查询优先Adapter的成交回报同步请求A/O/P三项。原事件续段先持有这三份
 // 名额及普通查询银行；SPI重入成功入队时转成真实任务，未使用部分随事件退役。
 static constexpr std::size_t audit_source_bytes=4224;
 unsigned event_callback_reserved=0;bool event_callback_active=false;
 std::size_t persistent_event_bytes()const
 {return add_size(event_banks.total_static,add_size(event_partition,audit_source_bytes));}
 unsigned event_callback_slots()const noexcept{return query_first?3u:0u;}
 void reserve_event_callback_locked(){
  require(!event_callback_reserved,"qmt_standard_callback_reservation_overlap");
  const auto count=event_callback_slots();
  require(count<=max_queue&&outstanding<=max_queue-count,"qmt_standard_callback_slot_capacity");
  require(charge(times_size(count,ordinary_reserve)),"qmt_standard_callback_byte_capacity");
  outstanding+=count;event_callback_reserved=count;
 }
 void release_event_callback_locked(){
  require(outstanding>=event_callback_reserved,"qmt_standard_callback_slot_accounting");
  outstanding-=event_callback_reserved;uncharge(times_size(event_callback_reserved,ordinary_reserve));event_callback_reserved=0;
 }
 bool worker_done=false,drained=false;
 Clock::time_point close_deadline;
 Status first_error,ingress_error,owner_error;
 std::string last_command;
 unsigned callbacks=0,queries=0,inserts=0,cancels=0;
 ~Impl(){if(!http.hmac_secret.empty()){volatile char* secret=&http.hmac_secret[0];for(std::size_t i=0;i<http.hmac_secret.size();++i)secret[i]=0;}}
 bool owner()const noexcept{return owner_thread==std::this_thread::get_id();}
 Clock::time_point deadline()const{return Clock::now()+std::chrono::milliseconds(request_ms);}
 void uncharge(std::size_t n){require(n<=payload_bytes,"qmt_standard_payload_accounting");payload_bytes-=n;}
 bool charge(std::size_t n){if(payload_bytes>max_queue_bytes||n>max_queue_bytes-payload_bytes)return false;payload_bytes+=n;return true;}
 void note(const Status& value)
 {
  if(value.ok()||!first_error.ok())return;
  if(!events_enabled){first_error=value;return;}
  // 先固定首因；资源不足不能在诊断复制处再次抛出并改变Unknown/真实Failure。
  first_error.code=value.code;try{first_error.reason=value.reason;}catch(...){first_error.reason.clear();}
 }
 void block(const Status& value)
 {
  hard_fault=true;writes_blocked=true;note(value);
  // 首错可能是较早的提交未知；另记实际硬故障的固定码及摘要，保留真正停止原因。
  try{const auto hash=signed_http_sha256(value.reason);
   std::fprintf(stderr,"qmt_standard_hard_fault code=%u reason_sha256=%s\n",static_cast<unsigned>(value.code),hash.c_str());}
  catch(...){/* 诊断失败不改变已经锁存的硬故障。 */}
 }
 void fence_unknown(){unknown_fenced=true;writes_blocked=true;}
 bool write_wait_stopped(Kind kind)const noexcept{return worker_stop.load()||submissions_closed.load()||(kind==Kind::Insert&&inserts_paused.load());}
 bool permits(Kind kind)const{return !submissions_closed&&!hard_fault&&!stop_requested&&!read_waiting&&(kind==Kind::Cancel||(!unknown_fenced&&!inserts_paused));}
 bool audit_io()const{return !worker_stop&&!audit_detached;}

 static bool submission_key(const SubmissionKeyV1& key)noexcept
 {
  if(key.version!=1||key.size!=sizeof(key)||key.side>1||key.code[6])return false;
  if(!((std::memcmp(key.exchange,"SSE\0",4)==0&&key.exchange[4]==0)||std::memcmp(key.exchange,"SZSE\0",5)==0))return false;
  for(unsigned i=0;i<6;++i)if(key.code[i]<'0'||key.code[i]>'9')return false;
  return true;
 }
 static bool same_security(const SubmissionKeyV1& key,const Identity& value)noexcept
 {return value.exchange==key.exchange&&value.code==key.code;}
 void submission_fault()noexcept
 {
  hard_fault=true;writes_blocked=true;
  if(first_error.ok()){
   // 已产生的容量/准入首因先于组收口诊断；固定code转交不因reason分配再变因。
   first_error.code=!ingress_error.ok()?ingress_error.code:!owner_error.ok()?owner_error.code:ErrorCode::SubmissionUnknown;
   first_error.reason.clear();
  }
 }
 std::size_t identity_extra()const noexcept
 {return query_first&&!events_enabled?sizeof(Identity)-sizeof(NativeIdentity):0;}
 std::size_t identity_charge(const std::string& key,const Identity& value)const
 {return add_size(add_size(key.size()+value.tag.size()+value.exchange.size()+value.code.size()+value.broker.size(),identity_extra()),value.retained_charge);}
 // caller持原mutex，只有固定字段；观察不生成金融数量、也不清除责任。
 void submission_view(const SubmissionKeyV1& key,SubmissionViewV1& out)const noexcept
 {
  out=SubmissionViewV1{};
  for(const auto& pair:identities){const auto& value=pair.second;
   if(value.group_id&&value.observation!=SubmissionObservation::None&&same_security(key,value)){
    ++out.unresolved_children;if(!out.group_id)out.group_id=value.group_id;
    if(out.observation==SubmissionObservation::None||value.observation==SubmissionObservation::Fault
       ||(value.observation==SubmissionObservation::Unknown&&out.observation!=SubmissionObservation::Fault))out.observation=value.observation;
   }
  }
  if(submission.open&&std::memcmp(submission.key.exchange,key.exchange,sizeof(key.exchange))==0
     &&std::memcmp(submission.key.code,key.code,sizeof(key.code))==0){out.group_id=submission.id;out.accepted_children=submission.accepted;}
 }
 // 原Pending唯一收据在SDK终态或独立券商终态核清后移交；其余Unknown留Pending。这里只改变通信所有权，
 // 不把先到的ORDER证明退回Await，也不以SDK返回或时间流逝解除券商观察责任。
 bool retain_submission_receipt(const std::string& command,Pending& p,bool not_sent=false)
 {
  if(!query_first||p.operation!=PendingOperation::Insert)return true;
  auto found=identities.end();
  for(auto it=identities.begin();it!=identities.end();++it)
   if(it->second.group_id&&command==it->second.command_id){found=it;break;}
  if(found==identities.end()){submission_fault();return false;}
  auto& value=found->second;
  if(p.own.phase==QmtTradePhase::DefinitelyNotCalled||not_sent){
   if(value.observation==SubmissionObservation::ObservedActive||value.observation==SubmissionObservation::TerminalNeedsReconciliation
      ||value.observation==SubmissionObservation::Fault){submission_fault();return false;}
   value.observation=SubmissionObservation::None;return true;
  }
  if(p.own.phase!=QmtTradePhase::SdkReturned
     &&!(p.own.phase==QmtTradePhase::Unknown&&p.own.has_record&&p.own.broker_terminal))return false;
  if(!value.retained_receipt.command_body.empty()){submission_fault();return false;}
  const auto n=bytes(p.receipt);if(n>p.charge){submission_fault();return false;}
  swap_receipt(value.retained_receipt,p.receipt);value.retained_charge=n;p.charge-=n;
  if(value.observation==SubmissionObservation::Unknown||value.observation==SubmissionObservation::None)
   value.observation=SubmissionObservation::AwaitBrokerObservation;
  return true;
 }
 void observe_submission(const std::string& command,const TradeObservation& observed)noexcept
 {
  if(!query_first||!observed.has_record||observed.phase!=QmtTradePhase::Unknown)return;
  for(auto& pair:identities){auto& value=pair.second;
   if(value.group_id&&command==value.command_id&&value.observation==SubmissionObservation::AwaitBrokerObservation)
    value.observation=SubmissionObservation::Unknown;
  }
 }

 struct Ingress {
  Impl& x;bool entered=false;
  explicit Ingress(Impl& value):x(value){std::lock_guard<std::mutex> lock(x.mutex);if(x.initialized&&!x.stop_requested){++x.active_ingress;entered=true;}}
  ~Ingress(){if(entered){std::lock_guard<std::mutex> lock(x.mutex);--x.active_ingress;x.cv.notify_all();}}
 };
 bool active()const{return initialized&&!stop_requested;}
 int enqueue(Task&& task,bool write=false,std::uint64_t* accepted_id=nullptr,
  bool share_queued_query=false,std::uint64_t after_query=0)
 {
  std::lock_guard<std::mutex> lock(mutex);
  if(!active()||(write&&!permits(task.kind)))return StandardQmtUnavailable;
  // 已开始的查询保留独立结果；仅待执行任务能在本次回调请求后取得新事实。
  // 复用原最早D和票据，未使用的事件回调预留沿原退出路径归还。
  if(query_first&&task.kind==Kind::Query&&owner()&&(in_callback||share_queued_query)){
   for(const auto& queued:tasks)if(queued.kind==Kind::Query&&queued.stage==task.stage
      &&queued.id>after_query&&queued.deadline<=task.deadline){
    if(accepted_id)*accepted_id=queued.id;return 0;
   }
  }
  if(query_first&&task.kind==Kind::Insert){
   if(!owner()||!submission.open||in_callback||pumping
      ||task.order.insert.exchange!=submission.key.exchange||task.order.insert.code!=submission.key.code
      ||task.order.insert.buy!=(submission.key.side==0)){
    if(submission.open)submission.failed=true;return StandardQmtUnavailable;
   }
  }
  if(events_enabled&&(task.kind==Kind::Prepare||task.kind==Kind::Login))task.charge=add_size(task.charge,context_reserve);
  if(events_enabled&&task.kind==Kind::Query){
   standard_event_budget::OrdinaryBanks banks;
   const auto r=standard_event_budget::detail::result_cap(event_budget_input);
   const auto status=standard_event_budget::ordinary(event_budget_input,task.stage,standard_event_budget::detail::data_cap(r),binding.row_limit,banks);
   if(!status.ok())return StandardQmtCapacity;task.charge=add_size(task.charge,banks.query);
  }
  task.charge=add_size(task.charge,512); // 每项预留固定错误/关联诊断有效载荷。
  const bool callback_slot=event_callback_reserved&&owner()&&event_callback_active&&in_callback&&task.kind==Kind::Query;
  const auto additional=callback_slot?std::size_t{0}:task.charge;
  if((callback_slot&&task.charge>ordinary_reserve)||(!callback_slot&&outstanding>=max_queue)
   ||next_task==(std::numeric_limits<std::uint64_t>::max)()||!charge(additional)){
   if(write){hard_fault=true;writes_blocked=true;if(ingress_error.ok())ingress_error=(events_enabled||query_first)?fixed_failure(ErrorCode::Backpressure):failure(ErrorCode::Backpressure,"qmt_standard_ingress_capacity");}
   return StandardQmtCapacity;
  }
  bool indexed=false;std::size_t index_charge=0;
  try {
   if(task.kind==Kind::Insert){
    const auto& value=task.order.insert;
    require(identities.find(value.entrust_id)==identities.end(),"qmt_standard_entrust_identity_reused");
    require(identities.size()<static_cast<std::size_t>(binding.row_limit)+max_pending,"qmt_standard_identity_index_capacity");
    index_charge=add_size(value.entrust_id.size()+value.user_tag.size()+value.exchange.size()+value.code.size(),identity_extra());
    require(charge(index_charge),"qmt_standard_identity_index_capacity");
    try{Identity identity{value.user_tag,value.exchange,value.code,{}};
     if(query_first){identity.group_id=submission.id;identity.observation=SubmissionObservation::AwaitBrokerObservation;}
     identities.emplace(value.entrust_id,std::move(identity));indexed=true;}
    catch(...){uncharge(index_charge);throw;}
   }
   task.generation=generation;task.id=++next_task;const auto accepted_charge=task.charge;queue_task(std::move(task));
   if(callback_slot){--event_callback_reserved;uncharge(ordinary_reserve-accepted_charge);}else ++outstanding;
   if(accepted_id)*accepted_id=next_task;
   if(indexed&&query_first)++submission.accepted;
  }catch(...){if(indexed){identities.erase(task.order.insert.entrust_id);uncharge(index_charge);}uncharge(additional);throw;}
  cv.notify_all();return 0;
 }
 void unregister_instance()
 {
  std::lock_guard<std::mutex> lock(registry_mutex);auto found=instances.find(instance_id);
  if(found!=instances.end()&&found->second->impl_.get()==this)instances.erase(found);
 }
 void request_stop()
 {
  {std::lock_guard<std::mutex> lock(mutex);
   event_control.request_stop();stop_requested=true;connected=false;logged_in=false;writes_blocked=true;worker_stop=true;
   if(!close_started){close_started=true;close_deadline=Clock::now()+std::chrono::milliseconds(close_ms);}}
  account_control.request_stop();unregister_instance();
  if(phase!=StandardQmtPhase::Closed)phase=StandardQmtPhase::Closing;cv.notify_all();
 }
 template<class F> void callback(F&& call)
 {
  if(!spi||stop_requested)return;
  if(callback_credit)callback_credit->retire();
  in_callback=true;struct Guard{bool& flag;~Guard(){flag=false;}}guard{in_callback};
  try{call();++callbacks;}catch(...){spi=nullptr;hard_fault=true;writes_blocked=true;
   if(events_enabled){if(first_error.ok())first_error.code=ErrorCode::SubmissionUnknown;}
   else note(failure(ErrorCode::SubmissionUnknown,"qmt_standard_spi_effect_unknown"));throw;}
 }
 void trader_error(const Status& status,wtp::WTSErroCode code=wtp::WEC_UNKNOWN)
 {
  note(status);std::unique_ptr<wtp::WTSError,ObjectRelease> error(wtp::WTSError::create(code,status.reason.c_str()));
  callback([&]{spi->onTraderError(error.get());});
 }
 void fail(const Status& status)
 {
  if(status.code==ErrorCode::Timeout&&status.reason=="qmt_standard_event_chain_deadline")capture_event_chain_deadline();
  block(status);try{trader_error(status);callback([&]{spi->handleEvent(wtp::WTE_Close,StandardQmtFailure);});}catch(...){spi=nullptr;}
  request_stop();
 }
 void finish_charge(std::size_t n){std::lock_guard<std::mutex> lock(mutex);uncharge(n);cv.notify_all();}
 static bool communication_responsibility(const Completion& value)noexcept
 {
  // 写/Audit与事件查询持有跨调用原票据；普通读取/解析值可在容量失败时销毁。
  return value.kind==Kind::Insert||value.kind==Kind::Cancel||value.kind==Kind::AuditOriginal
   ||value.kind==Kind::EventQuery||value.kind==Kind::EventResolve;
 }
 static void discard_replayable_payload(Completion& value)noexcept
 {
  // 先转移到局部owner并真实析构；原task身份、D、order和charge保留到错误完成值退休。
  // 移动赋空只保证逻辑为空，局部owner的析构明确早于调用方任何退费。
  {
   auto account=std::move(value.account);auto trade=std::move(value.trade);
   auto resolved=std::move(value.resolved);auto context=std::move(value.event_context);
   auto page=std::move(value.event_page);auto audit=std::move(value.audit);
   auto command=std::move(value.command_id);auto reason=std::move(value.status.reason);
   value.account={};value.trade={};value.event_context={};value.event_page={};value.audit={};
   value.command_id.clear();value.status.reason.clear();
  }
 }
 void ordinary_capacity_failure(Completion& value)noexcept
 {
  discard_replayable_payload(value);
  value.status.code=ErrorCode::Backpressure;value.status.reason.swap(value.capacity_reason);
  // capacity_reason在该worker任何I/O前准备；容量失败发布不分配，也不冒充SDK业务终态。
 }
 bool publish(Completion&& value,std::size_t wanted)
 {
#if defined(_WIN32) && defined(GH_QMT_STANDARD_EVENT_TESTING)
  if(value.kind==Kind::EventPage)standard_event_test_publish(
   value.status.ok()&&value.event_page.event_count>0?1u:
   value.event_failure.outcome==QmtTradeEventReadOutcome::ControlStoppedBeforeStage?2u:0u,value.deadline);
#endif
  std::lock_guard<std::mutex> lock(mutex);
  if(!results.owns(value))return false;
  if(communication_responsibility(value)){
   // 原写/Audit的最坏完整值已在I/O前取得reserve；超额属于内部不变量错误。
   // 保全部事实/原charge并停止后继I/O，不能用普通容量错误覆盖Started/U。
   if(wanted>value.charge){value.delivery_fault=true;hard_fault=true;writes_blocked=true;worker_stop=true;}
  }else if(wanted>value.charge){
   if(charge(wanted-value.charge))value.charge=wanted;
   else ordinary_capacity_failure(value);
  }else {std::string{}.swap(value.capacity_reason);uncharge(value.charge-wanted);value.charge=wanted;}
  std::string{}.swap(value.capacity_reason);
  // 与commit同锁最后核原D；等待发布锁本身也可能跨过截止，必须先停止后继worker任务。
  fence_terminal_event_locked(value);
  results.commit();cv.notify_all();return true;
 }
 // operation/计费异常按同一事实职责分流：不可逆组保全，普通payload先析构；无新分配或D。
 void publish_worker_failure()
 {
  std::lock_guard<std::mutex> lock(mutex);hard_fault=true;writes_blocked=true;worker_stop=true;
  if(auto value=results.active()){
   if(!communication_responsibility(*value))ordinary_capacity_failure(*value);
   std::string{}.swap(value->capacity_reason);value->delivery_fault=true;results.commit();
  }
  else {Completion error;error.kind=Kind::Prepare;error.generation=generation;error.delivery_fault=true;
   error.status.code=ErrorCode::IoError;results.push_back(std::move(error));}
  cv.notify_all();
 }

 // UC预算是有效payload字节；账户Q与交易K独立，未知可信限额时取正文硬限。
 static std::size_t bound_bytes(const QmtBoundReceipt& r){return add_size(add_size(r.binding_json.size(),r.request_body.size()),r.read_profile_body.size());}
 static bool same_receipt(const QmtTradeReceipt& a,const QmtTradeReceipt& b)noexcept
 {return a.binding_json==b.binding_json&&a.command_body==b.command_body&&a.read_profile_body==b.read_profile_body&&a.read_result_capacity==b.read_result_capacity;}
 static bool same_read(const QmtBoundReceipt& a,const QmtBoundReceipt& b)noexcept
 {return a.binding_json==b.binding_json&&a.request_body==b.request_body&&a.read_profile_body==b.read_profile_body&&a.read_result_capacity==b.read_result_capacity;}
 static void swap_receipt(QmtTradeReceipt& a,QmtTradeReceipt& b)noexcept
 {a.binding_json.swap(b.binding_json);a.command_body.swap(b.command_body);a.read_profile_body.swap(b.read_profile_body);std::swap(a.read_result_capacity,b.read_result_capacity);}
 static void swap_order(OrderObservation& a,OrderObservation& b)noexcept
 {a.receipt.binding_json.swap(b.receipt.binding_json);a.receipt.request_body.swap(b.receipt.request_body);a.receipt.read_profile_body.swap(b.receipt.read_profile_body);std::swap(a.receipt.read_result_capacity,b.receipt.read_result_capacity);std::swap(a.state,b.state);}
 static void swap_actual(CancelObservation& a,CancelObservation& b)noexcept
 {swap_receipt(a.receipt,b.receipt);std::swap(a.observed,b.observed);}
 static std::size_t pending_bytes(const Pending& p)
 {return add_size(36,add_size(add_size(bytes(p.receipt),bytes(p.target_insert)),add_size(bound_bytes(p.order.receipt),bytes(p.actual.receipt))));}
 static const QmtTradeReceipt& target(const Pending& p)noexcept
 {return p.operation==PendingOperation::Insert?p.receipt:p.target_insert;}
 static const QmtTradeReceipt& target(const AuditInput& p)noexcept
 {return p.operation==PendingOperation::Insert?p.receipt:p.target_insert;}
 static std::size_t base64_size(std::size_t n)
 {return times_size(add_size(n/3,n%3?1:0),4);}
 std::size_t audit_reserve(const Pending& p)const
 {
  constexpr std::size_t K=65536,Q=65536,N=2097152,J=1048576,S=2097152,M=16384,E=38,G=4224;
  const auto Rt=add_size(8192,K),Ra=add_size(8192,Q);
  const auto Ht=(std::min)(http.max_response_bytes,add_size(add_size(base64_size(K),S),M));
  const auto Hl=(std::min)(http.max_response_bytes,add_size(add_size(base64_size(K),S),times_size(M,2)));
  const auto Ha=(std::min)(http.max_response_bytes,add_size(base64_size(N),M));
  const auto U=add_size(add_size(Rt,Ht),add_size((std::min)(S,M),E));
  const auto A=add_size(add_size(add_size(Ra,Ha),add_size(N,J)),36+20+128+E);
  const auto O=add_size(Rt,8192+781),L=add_size(add_size(times_size(Hl,2),O),E);
  const auto Rc=add_size(add_size(Rt,Ht),100),Lc=add_size(add_size(Rc,Hl),E);
  const auto Prep=add_size(Ra,4096+64),Apre=add_size(Ra,36+20+E);
  const auto peak=(std::max)({G+E,U,add_size(Prep,Apre),A,add_size(64,L),add_size(O,Lc),add_size(Rc,U),std::size_t(36)});
  return add_size(add_size(512,pending_bytes(p)),add_size(add_size(Ra,Rt),peak));
 }
 static std::string body_field(const std::string& body,const char* field)
 {
  rapidjson::Document value;
  require(parse_bounded_qmt_json(body,value,65536,65536)&&value.IsObject()&&value.HasMember(field)&&value[field].IsString(),"qmt_standard_audit_identity_invalid");
  return qmt_host_codec::text(value[field]);
 }
 static bool receipt_id(const std::string& body,const std::string& id)
 {
  rapidjson::Document value;
  return parse_bounded_qmt_json(body,value,65536,65536)&&value.IsObject()&&value.HasMember("command_id")
   &&value["command_id"].IsString()&&id.size()==value["command_id"].GetStringLength()
   &&std::memcmp(id.data(),value["command_id"].GetString(),id.size())==0;
 }
 bool actual_slot(const std::string& current,const QmtTradeReceipt& actual,const QmtTradeReceipt& original)const
 {
  // 不复制目的槽；不同UUID以原body中的已验身份比较。返回仅作本轮读取提示。
  for(const auto& item:pending)if(item.first!=current&&receipt_id(actual.command_body,item.first)
   &&item.second.role!=PendingRole::UnadmittedTargetLookup
   &&same_receipt(item.second.receipt,actual)&&same_receipt(target(item.second),original))return true;
  return false;
 }
 Status pin_audit_source(QmtHostTradeClient& client)
 {
  auto current=client.event_source(); // G临时组在函数返回时销毁。
  if(current.binding_json.empty()||current.binding_json.size()>4096||current.session_id.empty()||current.session_id.size()>128)
   return failure(ErrorCode::StaleSession,"qmt_standard_audit_source_invalid");
  std::lock_guard<std::mutex> lock(mutex);
  if(audit_source_ready)return same_event_source(audit_source,current)?Status{}:failure(ErrorCode::StaleSession,"qmt_standard_audit_source_changed");
  audit_source=std::move(current);audit_source_ready=true;return {};
 }
 static void audit_error(AuditSummary& a,const Status& status)noexcept
 {
  a.error=status.code;
  if(status.ok())return;
  if(status.code==ErrorCode::Timeout)a.diagnostic=AuditDiagnostic::Deadline;
  else if(status.code==ErrorCode::StaleSession)a.diagnostic=AuditDiagnostic::SourceChanged;
  else if(status.code==ErrorCode::Conflict||status.code==ErrorCode::InvalidInput)a.diagnostic=AuditDiagnostic::IdentityConflict;
  else if(status.code==ErrorCode::Backpressure)a.diagnostic=AuditDiagnostic::Capacity;
  else if(status.reason.find("_invalid")!=std::string::npos||status.reason.find("_changed")!=std::string::npos)a.diagnostic=AuditDiagnostic::HardFault;
  else a.diagnostic=AuditDiagnostic::RetryTransport;
 }
 bool audit_stage(AuditSummary& a,SignedHttpDeadline& end)const
 {
  if(a.diagnostic==AuditDiagnostic::IdentityConflict||a.diagnostic==AuditDiagnostic::SourceChanged||a.diagnostic==AuditDiagnostic::HardFault)return false;
  if(!audit_io()){a.diagnostic=AuditDiagnostic::Stopping;return false;}
  if(!end.remaining()){a.diagnostic=AuditDiagnostic::Deadline;a.error=ErrorCode::Timeout;return false;}
  return true;
 }
 static void observe(TradeObservation& out,const QmtTradeResult& value)noexcept
 {if(value.original_record&&value.status.ok()){out.phase=value.phase;out.has_record=true;}}
 static bool read_terminal(const QmtAccountResult& value)
 {
  const auto& r=value.bound.result;
  return r.terminal&&((r.status.ok()&&r.remote_ok)||(!r.remote_ok&&!value.remote_error_code.empty()
   &&r.status.reason=="qmt_host_native_operation_failed"));
 }
 bool audit_lifecycle()const
 {return active()&&logged_in&&audit_source_ready&&!audit_detached;}
 bool audit_ready(Clock::time_point now)const
 {
  if(!audit_lifecycle()||audit_inflight||outstanding>=max_queue||next_task==(std::numeric_limits<std::uint64_t>::max)())return false;
  for(const auto& item:pending)if(!item.second.inflight_task&&item.second.next_due<=now
   &&payload_bytes<=max_queue_bytes&&audit_reserve(item.second)<=max_queue_bytes-payload_bytes)return true;
  return false;
 }
 Clock::time_point audit_wake(Clock::time_point until)const
 {
  if(!audit_lifecycle()||audit_inflight||outstanding>=max_queue||next_task==(std::numeric_limits<std::uint64_t>::max)())return until;
  for(const auto& item:pending)if(!item.second.inflight_task&&payload_bytes<=max_queue_bytes
   &&audit_reserve(item.second)<=max_queue_bytes-payload_bytes)until=(std::min)(until,item.second.next_due);
  return until;
 }
 void schedule_audit()
 {
  std::lock_guard<std::mutex> lock(mutex);const auto now=Clock::now();if(!audit_ready(now))return;
  const auto count=pending.size();auto it=pending.begin();std::advance(it,static_cast<std::ptrdiff_t>(audit_cursor%count));
  for(std::size_t i=0;i<count;++i){
   auto& p=it->second;const auto reserve=audit_reserve(p);
   if(!p.inflight_task&&p.next_due<=now&&reserve<=max_queue_bytes-payload_bytes){
    require(charge(reserve),"qmt_standard_audit_capacity");
    try{
     Task task;task.kind=Kind::AuditOriginal;task.pending_key=it->first;task.generation=generation;task.id=next_task+1;
     task.deadline=now+std::chrono::milliseconds(request_ms);task.charge=reserve;
     queue_task(std::move(task));p.inflight_task=++next_task;++outstanding;audit_inflight=true;
     audit_cursor=(audit_cursor+i+1)%count;
    }catch(...){uncharge(reserve);throw;}
    cv.notify_all();return;
   }
   if(++it==pending.end())it=pending.begin();
  }
 }
 void run_audit(Task& task,Completion& result,QmtHostAccountClient& account,QmtHostTradeClient& trade)
 {
  // Input完整复制发生在锁内；此后只用纯值，所有Common调用都在锁外。
  AuditInput input;
  {
   std::lock_guard<std::mutex> lock(mutex);auto found=pending.find(result.command_id);
   require(found!=pending.end()&&task.generation==generation&&found->second.inflight_task==task.id,"qmt_standard_audit_ticket");
   const auto& p=found->second;input.receipt=p.receipt;input.target_insert=p.target_insert;
   input.operation=p.operation;input.role=p.role;input.own=p.own;input.order=p.order;
   input.target_lookup=p.target_lookup;input.actual=p.actual;
   if(p.target_lookup==TargetLookupState::Actual)input.actual_in_other_slot=actual_slot(result.command_id,p.actual.receipt,target(p));
  }
  auto& a=result.audit;
  a.role=input.role;a.own=input.own;a.order=input.order;a.target_lookup=input.target_lookup;a.actual=input.actual;a.apply=true;
  SignedHttpDeadline end(task.deadline);
  if(!audit_stage(a,end))return;
  {
   auto status=trade.prepare(end);if(!status.ok()){audit_error(a,status);return;}
   status=pin_audit_source(trade);if(!status.ok()){audit_error(a,status);return;}
  }
  // 每一作用域结束后销毁返回边界对象，Peak按max计费不隐含跨阶段叠加。
  bool own_read=false;
  if(input.role!=PendingRole::UnadmittedTargetLookup&&!a.own.terminal()){
   if(!audit_stage(a,end))return;
   auto value=trade.resume(input.receipt,end);own_read=true;observe(a.own,value);
   if(!value.status.ok())audit_error(a,value.status);
  }
  if(a.order.state==OrderAuditState::Started){
   if(!audit_stage(a,end))return;
   auto value=account.resume(a.order.receipt,end);
   if(read_terminal(value))a.order.state=OrderAuditState::Terminal;
   else if(!value.bound.result.status.ok())audit_error(a,value.bound.result.status);
  }else if(a.order.state==OrderAuditState::NotStarted&&input.role==PendingRole::OriginalCall&&!a.own.terminal()){
   if(!audit_stage(a,end))return;
   auto prepared=account.create_request(QmtAccountDatatype::Order,end);
   if(!prepared.status.ok()||!prepared.request){audit_error(a,prepared.status);return;}
   // 收据先完整成组安装，才允许POST；抛出/超D后仍保Started及原UUID。
   {OrderObservation fresh;fresh.receipt=prepared.request->receipt();fresh.state=OrderAuditState::Started;swap_order(a.order,fresh);}
   if(!audit_stage(a,end))return;
   auto value=account.submit_once(std::move(prepared.request),end);
   if(read_terminal(value))a.order.state=OrderAuditState::Terminal;
   else if(!value.bound.result.status.ok())audit_error(a,value.bound.result.status);
  }
  // 已有actual未知时只能续该UUID；目标lookup不能用较新的C替换它。
  if(a.target_lookup==TargetLookupState::Actual&&!a.actual.observed.terminal()){
   if(input.actual_in_other_slot)return;
   if(same_receipt(input.receipt,a.actual.receipt)&&own_read){a.actual.observed=a.own;return;}
   if(!audit_stage(a,end))return;
   auto value=trade.resume(a.actual.receipt,end);observe(a.actual.observed,value);
   if(!value.status.ok())audit_error(a,value.status);return;
  }
  if(input.role==PendingRole::TargetObservation||a.own.terminal()
   ||(input.role==PendingRole::UnadmittedTargetLookup&&a.target_lookup!=TargetLookupState::NotObserved))return;
  if(!audit_stage(a,end))return;
  // lookup的大原文/64字节token先销毁，只留下私有O进入cancel lookup阶段。
  std::unique_ptr<QmtTradeOrderReference> original;
  {
   QmtTradeLookup query;query.kind=QmtTradeLookupKind::SdkToken;
   query.sdk_user_order_id=body_field(target(input).command_body,"sdk_user_order_id");
   auto linked=trade.lookup(query,end);
   if(!linked.status.ok()||!linked.reference){audit_error(a,linked.status);return;}
   if(!same_receipt(linked.reference->insert(),target(input))){a.diagnostic=AuditDiagnostic::IdentityConflict;a.error=ErrorCode::Conflict;return;}
   original=std::move(linked.reference);
  }
  if(query_first&&input.operation==PendingOperation::Insert&&a.own.has_record&&a.own.phase==QmtTradePhase::Unknown
     &&original->facts().has_broker_proof
     &&original->facts().broker_proof_kind==QmtTradeBrokerProofKind::AccountQuery){
   if(!audit_stage(a,end))return;
   // Host原Journal与Source自身完整ORDER均须已核原insert终态；本地硬错不可清。
   // 独立保留SDK阶段unknown，随后仍须由原WT实际消费终态O和后继P。
   auto status=trade.reconcile_observation(end);
   if(status.ok())a.own.broker_terminal=true;
   else {audit_error(a,status);return;}
  }
  if(!audit_stage(a,end))return;
  std::unique_ptr<QmtTradeCancelReference> actual;
  {
   auto linked=trade.lookup_cancel(*original,end);
   if(!linked.status.ok()||!linked.response_complete){audit_error(a,linked.status);return;}
   if(linked.no_cancel){
    a.actual={};a.target_lookup=TargetLookupState::NoCancel;return;
   }
   if(!linked.reference){a.diagnostic=AuditDiagnostic::IdentityConflict;a.error=ErrorCode::Conflict;return;}
   // Input仍保完整旧组；空Summary槽中构造新组，失败整组恢复且结束本轮。
   a.actual={};
   try{
    CancelObservation fresh;fresh.receipt=linked.reference->receipt();fresh.observed={linked.reference->phase(),true};
    swap_actual(a.actual,fresh);a.target_lookup=TargetLookupState::Actual;
   }catch(...){swap_actual(a.actual,input.actual);a.target_lookup=input.target_lookup;throw;}
   actual=std::move(linked.reference);
  }
  original.reset(); // O销毁后才进入Rc+U阶段。
  {std::lock_guard<std::mutex> lock(mutex);if(actual_slot(result.command_id,a.actual.receipt,target(input)))return;}
  if(receipt_id(a.actual.receipt.command_body,result.command_id)){
   if(!same_receipt(a.actual.receipt,input.receipt)){a.diagnostic=AuditDiagnostic::IdentityConflict;a.error=ErrorCode::Conflict;return;}
   if(own_read){a.actual.observed=a.own;return;}
  }
  if(a.actual.observed.terminal()||!audit_stage(a,end))return;
  auto value=trade.resume_cancel(*actual,end);observe(a.actual.observed,value);
  if(!value.status.ok())audit_error(a,value.status);
 }


 static bool same_read_id(const QmtBoundReceipt& a,const QmtBoundReceipt& b)
 {
  rapidjson::Document x,y;
  require(parse_bounded_qmt_json(a.request_body,x,65536,65536)&&parse_bounded_qmt_json(b.request_body,y,65536,65536)
   &&x.IsObject()&&y.IsObject()&&x.HasMember("request_id")&&y.HasMember("request_id")
   &&x["request_id"].IsString()&&y["request_id"].IsString(),"qmt_standard_audit_read_identity");
  return x["request_id"].GetStringLength()==y["request_id"].GetStringLength()
   &&std::memcmp(x["request_id"].GetString(),y["request_id"].GetString(),x["request_id"].GetStringLength())==0;
 }
 static bool finished(const Pending& p)noexcept
 {
  if(p.order.state==OrderAuditState::Started)return false;
  if(p.role==PendingRole::UnadmittedTargetLookup)
   return p.target_lookup==TargetLookupState::NoCancel||(p.target_lookup==TargetLookupState::Actual&&p.actual.observed.terminal());
  return p.own.terminal()&&(p.target_lookup!=TargetLookupState::Actual||p.actual.observed.terminal());
 }
 void audit_diagnostic(const AuditSummary& a)
 {
  if(a.diagnostic==AuditDiagnostic::IdentityConflict||a.diagnostic==AuditDiagnostic::SourceChanged||a.diagnostic==AuditDiagnostic::HardFault)
   block(failure(a.error,"qmt_standard_audit_hard_fault"));
 }
 // caller持mutex。有效payload只在整组交换后转移，旧组仍由Completion的reserve持有。
 static void transfer_charge(Pending& p,std::size_t& chain)
 {
  const auto n=pending_bytes(p);
  if(n>p.charge){require(n-p.charge<=chain,"qmt_standard_audit_accounting");chain-=n-p.charge;}
  else chain=add_size(chain,p.charge-n);
  p.charge=n;
 }
 void settle_audit(Completion& c,std::size_t& chain)
 {
  std::lock_guard<std::mutex> lock(mutex);auto it=pending.find(c.command_id);
  require(it!=pending.end()&&c.generation==generation&&it->second.inflight_task==c.id,"qmt_standard_audit_completion_ticket");
  auto& p=it->second;auto& a=c.audit;
  if(a.apply){
   // 增额检查在修改前完成；后续交换只有noexcept字段操作，不出现半组快照。
   const auto next=add_size(36,add_size(add_size(bytes(p.receipt),bytes(p.target_insert)),add_size(bound_bytes(a.order.receipt),bytes(a.actual.receipt))));
   require(next<=p.charge||next-p.charge<=chain,"qmt_standard_audit_summary_capacity");
   p.role=a.role;p.own=a.own;swap_order(p.order,a.order);swap_actual(p.actual,a.actual);p.target_lookup=a.target_lookup;
   transfer_charge(p,chain);
  }
  p.inflight_task=0;p.next_due=Clock::now()+std::chrono::milliseconds(request_ms);
  audit_diagnostic(a);
  if(stop_requested)return; // 关闭期只移交值，保留原Pending到其owner析构。
  observe_submission(c.command_id,p.own);
  if(finished(p)){if(!retain_submission_receipt(c.command_id,p))return;const auto released=p.charge;pending.erase(it);chain=add_size(chain,released);return;}
  if(p.role!=PendingRole::UnadmittedTargetLookup||p.target_lookup!=TargetLookupState::Actual||p.actual.observed.terminal())return;
  // 合并分配失败只延期；A本轮Started/U已完整提交，不能回滚已POST身份。
  try{
   auto key=body_field(p.actual.receipt.command_body,"command_id");require(key.size()==36,"qmt_standard_audit_actual_id");
   auto other=pending.find(key);
   if(other==it){
    if(!same_receipt(p.receipt,p.actual.receipt))block(failure(ErrorCode::Conflict,"qmt_standard_audit_actual_conflict"));
    return;
   }
   if(other==pending.end()){
    // 全部可抛准备在extract前结束。node插入不分配，比较器noexcept。
    const auto old=p.charge;
    const auto next=add_size(36,add_size(bytes(p.actual.receipt),add_size(bytes(p.target_insert),bound_bytes(p.order.receipt))));
    require(next<=old||next-old<=chain,"qmt_standard_audit_rekey_capacity");
    auto node=pending.extract(it);node.key().swap(key);
    auto& saved=node.mapped();swap_receipt(saved.receipt,saved.actual.receipt);saved.own=saved.actual.observed;
    saved.actual={};saved.target_lookup=TargetLookupState::NotObserved;saved.role=PendingRole::TargetObservation;
    saved.charge=next;pending.insert(std::move(node));
    // key/旧receipt均已销毁或退出局部栈前由chain继续承担，函数外再退reserve。
    if(next>old)chain-=next-old;else chain=add_size(chain,old-next);
    return;
   }
   auto& b=other->second;
   if(b.role==PendingRole::UnadmittedTargetLookup||b.inflight_task)return;
   if(!same_receipt(p.actual.receipt,b.receipt)||!same_receipt(target(p),target(b))){
    block(failure(ErrorCode::Conflict,"qmt_standard_audit_merge_identity"));return;
   }
   bool take_a=false;
   if(b.order.state==OrderAuditState::NotStarted)take_a=true;
   else if(p.order.state!=OrderAuditState::NotStarted){
    const bool same=same_read_id(p.order.receipt,b.order.receipt);
    if(same&&!same_read(p.order.receipt,b.order.receipt)){
     block(failure(ErrorCode::Conflict,"qmt_standard_audit_read_conflict"));return;
    }
    if(!same&&p.order.state==OrderAuditState::Started&&b.order.state==OrderAuditState::Started)return;
    take_a=same?p.order.state==OrderAuditState::Terminal
     :p.order.state==OrderAuditState::Started;
   }
   const auto old=add_size(p.charge,b.charge);
   const auto next=add_size(36,add_size(add_size(bytes(b.receipt),bytes(b.target_insert)),add_size(bound_bytes(take_a?p.order.receipt:b.order.receipt),bytes(b.actual.receipt))));
   require(next<=old,"qmt_standard_audit_merge_capacity");
   if(take_a)swap_order(p.order,b.order);
   if(!b.own.terminal())b.own=p.actual.observed;
   b.charge=next;
   pending.erase(it);chain=add_size(chain,old-b.charge);
  }catch(const std::bad_alloc&){/* 原node及完整新观察保有；下一轮重试只读/合并。 */}
 }
 void settle_write(Completion& c,std::size_t& completion_charge)
 {
  if(c.command_id.empty())return;
  std::lock_guard<std::mutex> lock(mutex);auto found=pending.find(c.command_id);if(found==pending.end())return;
  auto& p=found->second;
  require(c.generation==generation&&p.inflight_task==c.id,"qmt_standard_write_completion_ticket");
  if(c.audit.apply&&c.audit.role==PendingRole::UnadmittedTargetLookup){
   p.role=PendingRole::UnadmittedTargetLookup;p.own={};fence_unknown();
  }else observe(p.own,c.trade);
  // 首次写回复已进入待核查时立即交回原ID审计。request_ms仍是单请求D，
  // 不把整段超时再次当作启动核查前的等待；后继审计保留原有限节奏。
  p.inflight_task=0;p.next_due=Clock::now()+std::chrono::milliseconds(query_first&&!p.own.terminal()?0:request_ms);
  observe_submission(c.command_id,p.own);
  if(!stop_requested&&(finished(p)||(c.insert_failure_confirmed&&c.trade.phase==QmtTradePhase::NotSent))){
   if(!retain_submission_receipt(c.command_id,p,c.insert_failure_confirmed&&c.trade.phase==QmtTradePhase::NotSent))return;
   const auto released=p.charge;pending.erase(found);completion_charge=add_size(completion_charge,released);
  }
 }


 // 出队前核原chain/ticket/index。错票据仍留在Ring，只有真实join后最终清理才销毁。
 bool event_ticket_matches(const Completion& front)const noexcept
 {
  if(front.kind!=Kind::EventQuery&&front.kind!=Kind::EventResolve)return true;
  const auto expected_phase=front.kind==Kind::EventQuery?EventPhase::QueryInFlight:EventPhase::ResolveInFlight;
  if(!event_chain||front.generation!=generation||front.id!=event_chain->task_id
   ||front.event_index!=event_chain->index||event_chain->phase!=expected_phase)return false;
  const auto& q=event_chain->query;
  if(front.kind==Kind::EventQuery)return !q.query_received&&q.origin_task_id==front.id
   &&q.generation==front.generation&&q.event_index==front.event_index;
  return !q.query_received||(!q.resolve_received&&q.origin_task_id==front.id
   &&q.generation==front.generation&&q.event_index==front.event_index);
 }
 bool pop_completion(Completion& value,bool& mismatch)
 {
  std::lock_guard<std::mutex> lock(mutex);mismatch=false;if(results.empty())return false;
  const auto& front=results.front();
  if(!event_ticket_matches(front)){
   mismatch=true;hard_fault=true;writes_blocked=true;worker_stop=true;
   if(first_error.ok())first_error.code=ErrorCode::Conflict;cv.notify_all();return false;
  }
  value=std::move(results.front());results.pop_front();cv.notify_all();return true;
 }
 // 所有纯来源先接入原链，再判断Failure/D/停止；receipt和原Status不能被generic pump过滤器吞掉。
 bool receive_event_operation(Completion& value,bool stopping)
 {
  auto& chain=*event_chain;
  const bool failed=event_operation_failed(value),normal_stop=normal_event_query_stop(value);
  if(Clock::now()>=chain.deadline){value.late=true;if(value.delivery_status.ok())value.delivery_status.code=ErrorCode::Timeout;}
  const Status* operation=&value.status;const Status* delivery=&value.delivery_status;
  if(value.kind==Kind::EventQuery){
   auto& q=chain.query;
   require(!q.query_received&&q.origin_task_id==value.id&&q.generation==value.generation
    &&q.event_index==value.event_index,"qmt_standard_event_query_custody");
   q.saved_receipt=std::move(value.saved_receipt);q.account=std::move(value.account);
   q.control_result=value.control_result;q.step=value.query_step;
   q.query_status=std::move(value.status);q.query_delivery_status=std::move(value.delivery_status);
   q.query_late=value.late;q.query_local_failure=value.local_failure;q.query_local_stopped=value.local_stopped;q.query_received=true;
   operation=&q.query_status;delivery=&q.query_delivery_status;
  }else if(chain.query.query_received){
   auto& q=chain.query;require(!q.resolve_received,"qmt_standard_event_resolution_duplicate");
   q.resolve_status=std::move(value.status);q.resolve_delivery_status=std::move(value.delivery_status);
   q.resolve_late=value.late;q.resolve_local_failure=value.local_failure;q.resolve_local_stopped=value.local_stopped;q.resolve_received=true;
   operation=&q.resolve_status;delivery=&q.resolve_delivery_status;
  }
  if(failed){
   if(!operation->ok()){if(stopping)note(*operation);else fail(*operation);}
   else if(value.resolved&&!value.resolved->status().ok()){
    if(stopping)note(value.resolved->status());else fail(value.resolved->status());
   }else {auto error=fixed_failure(ErrorCode::IoError);if(stopping)note(error);else fail(error);}
   return false;
  }
  if(!delivery->ok()){if(stopping)note(*delivery);else fail(*delivery);return false;}
  if(normal_stop||stopping||stop_requested||event_detached||!spi)return false;
  return true;
 }
 void retire_completion(Completion& value,std::size_t charge)
 {
  // 先真实析构所有值，再释放逻辑payload；仅空容量保留不计有效字节。
  value.account={};value.resolved.reset();value.event_context={};value.event_page={};value.trade={};value.order={};
  value.audit={};value.command_id.clear();value.status={};value.saved_receipt={};value.delivery_status={};
  std::string{}.swap(value.capacity_reason);
  std::lock_guard<std::mutex> lock(mutex);uncharge(charge);
  if(value.kind==Kind::AuditOriginal)audit_inflight=false;cv.notify_all();
 }
 // 两种退休时序共用原结果分类；受控停止不改变已确认的执行/恢复健康事实。
 void retain_stopped_event_failure(const Completion& value)
 {
  if(value.kind==Kind::EventPage&&value.event_failure.outcome==QmtTradeEventReadOutcome::Failure
   &&!value.status.ok())note(value.status);
 }
 bool retain_stopped_results(bool final_joined_cleanup=false)
 {
  if(final_joined_cleanup&&events_enabled){
   // 这是生命周期退休：worker/HTTP/外部入口已真正结束，Ring不再有producer。
   // 原槽留到settle成功；后续write/Audit异常仍由该槽保有，release不能报告Closed。
   for(;;){
    Completion* value=nullptr;bool mismatch=false;
    {std::lock_guard<std::mutex> lock(mutex);
     if(!worker_done||!drained||worker.joinable()||active_ingress.load()!=0)return false;
     if(results.empty())return true;value=&results.front();mismatch=!event_ticket_matches(*value);}
    auto held_charge=value->charge;
    try {
     if(mismatch){hard_fault=true;writes_blocked=true;if(first_error.ok())first_error.code=ErrorCode::Conflict;}
     else if(value->kind==Kind::EventQuery||value->kind==Kind::EventResolve)receive_event_operation(*value,true);
     else if(value->kind==Kind::AuditOriginal)settle_audit(*value,held_charge);
     else if(value->kind==Kind::Insert||value->kind==Kind::Cancel)settle_write(*value,held_charge);
     else retain_stopped_event_failure(*value);
    }catch(...){value->charge=held_charge;hard_fault=true;writes_blocked=true;
     if(first_error.ok())first_error.code=ErrorCode::IoError;return false;}
    const auto id=value->id;retire_completion(*value,held_charge);
    {std::lock_guard<std::mutex> lock(mutex);results.pop_front();cv.notify_all();}
    if(id)finish_task();
   }
  }
  // stop仅抑制I/O/SPI。已POST的Started和精确U仍须由原owner按ticket移交。
  for(;;){
   Completion value;
   bool mismatch=false;
   if(!pop_completion(value,mismatch)){
    if(!mismatch||!final_joined_cleanup)break;
    // 真join后只销毁原错票据纯值，继续处理其后的写/U；绝不认领到别的事件链。
    std::lock_guard<std::mutex> lock(mutex);
    require(worker_done&&drained&&!worker.joinable(),"qmt_standard_event_final_custody");
    value=std::move(results.front());results.pop_front();cv.notify_all();
   }
   TaskCredit credit{*this,value.id};
   struct Held {Impl& x;Completion& value;std::size_t charge;~Held(){x.retire_completion(value,charge);}} held{*this,value,value.charge};
   if(mismatch)continue;
   if(value.kind==Kind::EventQuery||value.kind==Kind::EventResolve)receive_event_operation(value,true);
   else if(value.kind==Kind::AuditOriginal)settle_audit(value,held.charge);
   else if(value.kind==Kind::Insert||value.kind==Kind::Cancel)settle_write(value,held.charge);
   else retain_stopped_event_failure(value);
  }
  return true;
 }

 void run_write(Task& task,Completion& result,QmtHostTradeClient& client)
 {
  SignedHttpDeadline end(task.deadline);result.insert_failure_confirmed=true;
  if(!permits(task.kind)){result.status=failure(ErrorCode::Unavailable,"qmt_standard_write_admission_closed");return;}
  result.status=client.prepare(end);
  if(!result.status.ok())return;
  if(query_first&&observation_reconciled.exchange(false)){
   result.status=client.reconcile_observation(end);
   if(!result.status.ok()){
    if(result.status.code==ErrorCode::SubmissionUnknown){
     fence_unknown();result.business_rejected=true;
     result.status=failure(ErrorCode::SubmissionUnknown,"qmt_standard_observation_readmission_wait");
    }
    return;
   }
  }
  result.status=pin_audit_source(client);if(!result.status.ok())return;
  if(write_wait_stopped(task.kind)){result.status=failure(ErrorCode::Unavailable,"qmt_standard_stopping_before_submit");result.insert_failure_confirmed=true;return;}
  QmtTradePreparation prepared;QmtTradeReceipt target_insert;
  if(task.kind==Kind::Insert)prepared=client.create_insert(task.order.insert,end);
  else {
   QmtTradeLookup query;query.kind=QmtTradeLookupKind::WtIdentity;
   query.entrust_id=task.order.insert.entrust_id;query.user_tag=task.order.insert.user_tag;
   auto linked=client.lookup(query,end);result.status=linked.status;
   if(!result.status.ok())return;
   if(!linked.reference||linked.reference->broker_order_id()!=task.order.broker){result.status=failure(ErrorCode::Conflict,"qmt_standard_cancel_identity_conflict");return;}
   const auto& facts=linked.reference->facts();
   const auto symbol=task.order.insert.code+(task.order.insert.exchange=="SSE"?".SH":".SZ");
   if(facts.account_id!=binding.account||facts.account_type!="stock"||facts.symbol!=symbol
    ||!facts.dispatched||!facts.has_broker_proof){result.status=failure(ErrorCode::Conflict,"qmt_standard_cancel_proof_invalid");return;}
   target_insert=linked.reference->insert();
   prepared=client.create_cancel(*linked.reference,end);
  }
  result.status=prepared.status;
  if(!result.status.ok()||!prepared.request){result.insert_failure_confirmed=true;return;}
  const auto receipt=prepared.request->receipt();
  rapidjson::Document command;
  if(!parse_bounded_qmt_json(receipt.command_body,command,65536,65536)||!command.IsObject()
   ||!command.HasMember("command_id")||!qmt_host_codec::uuid(command["command_id"])){
   result.status=failure(ErrorCode::IoError,"qmt_standard_command_identity_invalid");result.insert_failure_confirmed=true;return;
  }
  const auto id=qmt_host_codec::text(command["command_id"]);result.command_id=id;
  // 原收据和最坏有界回复空间都在POST之前取得；容量失败可明确证明未提交。
  const auto receipt_bytes=add_size(add_size(bytes(receipt),id.size()),bytes(target_insert));
  const auto reserve=add_size(add_size(http.max_response_bytes,http.max_response_bytes),add_size(bytes(receipt),4096));
  {
   std::lock_guard<std::mutex> lock(mutex);
   auto submission_owner=identities.end();
   if(query_first&&task.kind==Kind::Insert){
    submission_owner=identities.find(task.order.insert.entrust_id);
    require(submission_owner!=identities.end()&&submission_owner->second.group_id&&id.size()==36,"qmt_standard_submission_receipt_owner");
   }
   if(pending.size()>=max_pending||!charge(add_size(receipt_bytes,reserve))){
    result.status=failure(ErrorCode::Backpressure,"qmt_standard_pending_capacity");result.insert_failure_confirmed=true;return;
   }
   try{Pending saved;saved.receipt=receipt;saved.charge=receipt_bytes;saved.operation=task.kind==Kind::Insert?PendingOperation::Insert:PendingOperation::Cancel;
    swap_receipt(saved.target_insert,target_insert);saved.inflight_task=task.id;saved.next_due=task.deadline;
    require(pending.emplace(id,std::move(saved)).second,"qmt_standard_command_identity_reused");}
   catch(...){uncharge(add_size(receipt_bytes,reserve));throw;}
   if(query_first&&task.kind==Kind::Insert){
    std::memcpy(submission_owner->second.command_id,id.data(),36);submission_owner->second.command_id[36]=0;
   }
   result.charge=add_size(result.charge,reserve);
  }
  if(write_wait_stopped(task.kind)){
   std::lock_guard<std::mutex> lock(mutex);auto found=pending.find(id);uncharge(found->second.charge);pending.erase(found);
   result.status=failure(ErrorCode::Unavailable,"qmt_standard_stopping_before_submit");result.insert_failure_confirmed=true;return;
  }
  result.insert_failure_confirmed=false;
  result.trade=client.submit_once(std::move(prepared.request),end);
  if(task.kind==Kind::Cancel&&result.trade.http_status==409&&result.trade.status.code==ErrorCode::Conflict
   &&result.trade.status.reason=="qmt_trade_cancel_pending"&&!result.trade.original_record){
   // Core只对完整、末D内的精确409生成该原因。先保存U；延期核查不占第二条链。
   result.audit.role=PendingRole::UnadmittedTargetLookup;result.audit.own={};result.audit.apply=true;fence_unknown();
   result.status=result.trade.status;return;
  }
  result.status=result.trade.status;
  // 正常运行沿原D核同一命令；恢复停机关闭写准入时结束写等待，
  // 原worker才能继续账户核查。已发送的未知收据仍由原pending保留。
  while(!write_wait_stopped(task.kind)&&end.remaining()&&(result.trade.phase==QmtTradePhase::Queued
   ||result.trade.phase==QmtTradePhase::Dispatching||(!query_first&&result.trade.phase==QmtTradePhase::Unknown))){
   std::unique_lock<std::mutex> lock(mutex);
   cv.wait_until(lock,(std::min)(task.deadline,Clock::now()+std::chrono::milliseconds(10)),[&]{return write_wait_stopped(task.kind);});
   lock.unlock();if(write_wait_stopped(task.kind)||!end.remaining())break;
   result.trade=client.resume(receipt,end);result.status=result.trade.status;
  }
  const bool terminal=result.trade.phase==QmtTradePhase::SdkReturned||result.trade.phase==QmtTradePhase::DefinitelyNotCalled
   ||result.trade.phase==QmtTradePhase::NotSent;
  result.insert_failure_confirmed=result.trade.phase==QmtTradePhase::DefinitelyNotCalled||result.trade.phase==QmtTradePhase::NotSent;
  if(result.trade.phase==QmtTradePhase::DefinitelyNotCalled){
   result.business_rejected=true;
   if(result.status.ok()){
    std::string reason="qmt_standard_confirmed_not_called";rapidjson::Document source;
    if(parse_bounded_qmt_json(result.trade.source_result_json,source,2097152,1048576)&&source.IsObject()
     &&source.HasMember("error_code")&&source["error_code"].IsString())reason+=":"+qmt_host_codec::text(source["error_code"]);
    result.status={ErrorCode::Unavailable,std::move(reason)};
   }
  }else if(task.kind==Kind::Cancel&&result.trade.phase==QmtTradePhase::SdkReturned&&result.status.ok()){
   rapidjson::Document source;
   if(parse_bounded_qmt_json(result.trade.source_result_json,source,2097152,1048576)&&source.IsObject()
    &&source.HasMember("signal_sent")&&source["signal_sent"].IsBool()&&!source["signal_sent"].GetBool()){
    result.business_rejected=true;result.status=failure(ErrorCode::Unavailable,"qmt_standard_cancel_signal_not_sent");
   }
  }
  if(!terminal){result.status=failure(ErrorCode::SubmissionUnknown,"qmt_standard_original_command_unresolved");fence_unknown();}
  // 由owner核原写ticket后统一结算；worker不能提前开放审计或退收据。
 }
 // 只读重取许可来自本次Common固定事实；原Status文本与业务写结果不参与分类。
 static bool event_transport_retry(const Completion& value)noexcept
 {
  return !value.status.ok()&&!value.event_drain_failed
   &&value.event_failure.outcome==QmtTradeEventReadOutcome::Failure
   &&value.event_failure.transport.recovery==SignedHttpRecovery::TransportInterrupted
   &&value.event_page.page_json.empty()&&!value.resolved;
 }
 static void event_local_failure(Completion& value)noexcept
 {
  value.event_failure={};value.event_failure.outcome=QmtTradeEventReadOutcome::Failure;
  value.event_failure.transport.origin=SignedHttpFailureOrigin::LocalOrProtocol;
  value.event_drain_pending=value.event_drain_checked=false;value.event_drain_failed=true;
 }
 void event_timeout(Completion& value)
 {
  // 顶层Timeout与最后一次真实transport分别保有；失败POD不因发布/owner晚到而丢失。
  value.event_failure.outcome=QmtTradeEventReadOutcome::Failure;
  if(value.event_failure.transport.origin==SignedHttpFailureOrigin::None)
   value.event_failure.transport.origin=SignedHttpFailureOrigin::Deadline;
  value.event_drain_pending=value.event_drain_checked=false;
  value.status=failure(ErrorCode::Timeout,"qmt_standard_event_chain_deadline");
 }
 void event_stopped(Completion& value)
 {
  value.status=failure(ErrorCode::Unavailable,"qmt_standard_event_control_stopped");
  value.event_failure={};value.event_failure.outcome=QmtTradeEventReadOutcome::ControlStoppedBeforeStage;
  value.event_drain_pending=value.event_drain_checked=false;
 }
 void prepare_event_bootstrap(Completion& result,QmtHostTradeClient& client,SignedHttpDeadline& end)
 {
  // 只为显式查询优先入口建立快照/增量分界；默认事件消费仍从原0游标开始。
  if(!events_enabled||!query_first)return;
  const auto& context=result.event_context;const auto& limits=context.admitted_limits;
  standard_event_budget::ContextBanks banks;
  const standard_event_budget::ContextInputs inputs{context.read_result_capacity,context.admitted_event_page_capacity,
   static_cast<std::size_t>(limits.max_event_bytes),static_cast<std::size_t>(limits.max_command_bytes),
   static_cast<std::size_t>(limits.max_call_result_bytes)};
  if(!standard_event_budget::context(event_budget_input,event_layout,inputs,banks).ok())throw EventCapacity{};
  const auto total=add_size(result.charge,banks.chain);
  {std::lock_guard<std::mutex> lock(mutex);if(!charge(banks.chain))throw EventCapacity{};
   result.charge=total;result.event_bootstrap_reserve=banks.chain;}
  for(;;){
   if(worker_stop||stop_requested){result.status=fixed_failure(ErrorCode::Pending);return;}
   if(!end.remaining()){result.status=fixed_failure(ErrorCode::Timeout);return;}
   auto page=client.events(context.source,0,1,context.admitted_event_page_capacity,end);
   if(page.status.ok()){
    if(page.gap){result.status=failure(ErrorCode::Unavailable,"qmt_standard_event_source_gap");return;}
    // 整个receipt已由原Common核验。limit=1只限复制量，durable_through仍覆盖Host完整持久前缀。
    result.event_bootstrap_cursor=page.durable_through;result.event_bootstrap_ready=true;result.status={};return;
   }
   result.status=std::move(page.status);
   // 新Host尚未形成首份空/非空receipt时可暂回404；保持原来源及原D等待原采集owner，不假设前沿0。
   if(page.http_status!=404||result.status.code!=ErrorCode::NotSupported)return;
   std::unique_lock<std::mutex> lock(mutex);
   cv.wait_until(lock,(std::min)(end.end,Clock::now()+std::chrono::milliseconds(event_poll_ms)),
    [&]{return worker_stop.load()||stop_requested.load();});
  }
 }
 void run_event_read(const Task& task,Completion& result,QmtHostTradeClient& client,SignedHttpDeadline& end)
 {
  result.event_failure=task.event_failure;
  if(!end.remaining()){event_timeout(result);return;}
  if(event_control.stop_requested()){event_stopped(result);return;}
  // 失败exchange之后的callback仍借用页链预留。零等待检查按原FIFO归还worker，绝不在这里循环。
  auto drained=client.drain_callbacks(0);++result.event_drain_checks;
  if(!drained.ok()&&drained.code!=ErrorCode::Pending){result.status=std::move(drained);result.event_failure.outcome=QmtTradeEventReadOutcome::Failure;result.event_drain_failed=true;return;}
  if(!end.remaining()){event_timeout(result);return;}
  if(event_control.stop_requested()){event_stopped(result);return;}
  if(drained.code==ErrorCode::Pending){result.status=std::move(drained);result.event_drain_pending=true;return;}
  if(task.event_drain_only){result.status={};result.event_drain_checked=true;return;}
  result.event_failure={};QmtTradeEventReadContext current;
  result.status=client.prepare_event_read_context(end,current,&result.event_failure,&event_control);
  result.event_read_attempted=result.status.ok()||result.event_failure.send_attempted
   ||result.event_failure.stage==QmtTradeEventReadStage::Status
   ||result.event_failure.stage==QmtTradeEventReadStage::Page
   ||result.event_failure.stage==QmtTradeEventReadStage::Publish;
  if(result.status.ok()){
   const auto& original=task.event_context;
   if(current.source.session_id!=original.source.session_id||current.read_profile_body!=original.read_profile_body
    ||current.read_result_capacity!=original.read_result_capacity
    ||current.admitted_event_page_capacity<task.event_bounds.max_bytes){
    result.status=failure(ErrorCode::StaleSession,"qmt_standard_event_context_changed");event_local_failure(result);
   }else {
    result.event_context=current;
    result.event_page=client.events(current.source,task.event_bounds.after_seq,task.event_bounds.limit,
     task.event_bounds.max_bytes,end,&result.event_failure,&event_control);
    result.status=result.event_page.status;
   }
  }
  if(event_transport_retry(result)){
   auto finished=client.drain_callbacks(0);++result.event_drain_checks;
   if(finished.code==ErrorCode::Pending)result.event_drain_pending=true;
   else if(!finished.ok()){result.status=std::move(finished);result.event_failure.outcome=QmtTradeEventReadOutcome::Failure;result.event_drain_failed=true;}
  }
 }
 // 先保真实operation code；诊断复制失败只归独立delivery，不能改写正常typed停止或原Failure。
 static void copy_operation_status(Completion& value,const Status& source)noexcept
 {
  value.status.code=source.code;
  try{value.status.reason=source.reason;}catch(...){
   value.status.reason.clear();
   // account/resolved保完整原Status。发布先按真实Failure判定，再核此交付错误；late不能覆盖它。
   value.delivery_status.code=ErrorCode::IoError;value.delivery_status.reason.clear();
  }
 }
 // 局部停止与Common返回的typed停止分别记录；此前真实失败不会被后来的detach抹掉。
 bool event_local_gate(Completion& value,SignedHttpDeadline& end)noexcept
 {
  if(!end.remaining()){value.status=fixed_failure(ErrorCode::Timeout);value.local_failure=true;return false;}
  if(event_control.stop_requested()){value.status=fixed_failure(ErrorCode::Pending);value.local_stopped=true;return false;}
  return true;
 }
 void run_event_query(const Task& task,Completion& result,QmtHostAccountClient& client,SignedHttpDeadline& end)
 {
  if(!event_local_gate(result,end))return;
  result.query_step=QueryStep::Prepare;
  result.status=client.prepare(end,&result.control_result,&event_control);
  if(!result.status.ok())return;
  if(!event_local_gate(result,end))return;
  result.query_step=QueryStep::Create;
  auto prepared=client.create_request(static_cast<QmtAccountDatatype>(task.stage),end,&result.control_result,&event_control);
  result.status=std::move(prepared.status);
  if(!result.status.ok())return;
  if(!prepared.request){result.local_failure=true;result.status=fixed_failure(ErrorCode::IoError);return;}
  // 收据完整复制成功以后才可能进入submit；复制失败保留已占完成槽和局部Failure。
  result.saved_receipt=prepared.request->receipt();result.query_step=QueryStep::ReceiptSaved;
  const auto& receipt=result.saved_receipt;const auto& original=task.event_context;
  if(receipt.binding_json!=original.source.binding_json||receipt.read_profile_body!=original.read_profile_body
   ||receipt.read_result_capacity!=original.read_result_capacity){
   result.local_failure=true;result.status=fixed_failure(ErrorCode::StaleSession);return;
  }
  if(!event_local_gate(result,end))return;
  // SubmitEntered仅表明同步方法已进入；具体是否POST由原Core返回的事实决定。
  result.query_step=QueryStep::SubmitEntered;
  result.account=client.submit_once(std::move(prepared.request),end,&result.control_result,&event_control);
  result.query_step=QueryStep::Returned;copy_operation_status(result,result.account.bound.result.status);
 }
 bool normal_event_query_stop(const Completion& value)const noexcept
 {
  if(value.local_failure||value.delivery_fault||!event_control.stop_requested())return false;
  if(value.local_stopped)return value.status.code==ErrorCode::Pending
   &&value.control_result.outcome==QmtAccountReadOutcome::None&&value.control_result.stage==QmtAccountReadStage::None;
  if(value.kind!=Kind::EventQuery)return false;
  const auto stage=value.control_result.stage;
  return value.status.code==ErrorCode::Pending
   &&value.control_result.outcome==QmtAccountReadOutcome::ControlStoppedBeforeStage
   &&stage>=QmtAccountReadStage::Binding&&stage<=QmtAccountReadStage::Publish
   &&(value.query_step==QueryStep::Prepare||value.query_step==QueryStep::Create
      ||value.query_step==QueryStep::Returned);
 }
 bool event_operation_failed(const Completion& value)const noexcept
 {
  if(value.local_failure||value.delivery_fault)return true;
  if(normal_event_query_stop(value))return false;
  if(value.local_stopped||value.control_result.outcome!=QmtAccountReadOutcome::None
   ||value.control_result.stage!=QmtAccountReadStage::None)return true;
  if(!value.status.ok())return true;
  return value.kind==Kind::EventResolve&&(!value.resolved||!value.resolved->status().ok());
 }
 // 只处理可确定的只读不可用；认证/账户/事件流/数据合同冲突继续原硬故障。
 // 固定原终态+原Host空绑定共同证明SDK未进入；其余坏正文/身份错误保留原故障。
 static bool read_not_dispatched(const Completion& value) {
  const auto& bound=value.account.bound;
  if(!bound.result.terminal||bound.result.remote_ok||bound.result.status.reason!="qmt_host_native_operation_failed")return false;
  rapidjson::Document native,envelope;
  if(!parse_bounded_qmt_json(bound.native_result_json,native,1048576,1048576)
    ||!parse_bounded_qmt_json(bound.result.envelope_json,envelope,4194304,4194304))return false;
  return native.IsObject()&&native.HasMember("error_code")&&native["error_code"].IsString()
   &&(std::strcmp(native["error_code"].GetString(),"source_binding_changed")==0
      ||std::strcmp(native["error_code"].GetString(),"queue_timeout")==0)
   &&envelope.IsObject()&&envelope.HasMember("dispatch_binding")&&envelope["dispatch_binding"].IsNull()
   &&envelope.HasMember("result_binding")&&envelope["result_binding"].IsNull();
 }
 static bool ended_retained_read(const Completion& value) {
  // Common仅在原账户票据及完整Host回复校验通过后发布此状态。
  // 结束读取责任不代表查询成功，也不授予重发下单或撤单的权限。
  return value.status.code==ErrorCode::Unavailable
   &&value.status.reason=="qmt_read_ticket_ended_unretained";
 }
 static bool interrupted_read(const Completion& value) {
  if((value.kind!=Kind::Query&&value.kind!=Kind::EventQuery)||value.stage>3)return false;
  const auto& bound=value.account.bound;
  if(!bound.result.terminal||bound.result.remote_ok||bound.result.operation_id!="account.trade_detail"
    ||bound.result.status.reason!="qmt_host_native_operation_failed")return false;
  rapidjson::Document native,envelope;
  if(!parse_bounded_qmt_json(bound.native_result_json,native,1048576,1048576)
    ||!parse_bounded_qmt_json(bound.result.envelope_json,envelope,4194304,4194304))return false;
  return standard_read_failure::interrupted_account_read(native,envelope);
 }
 static bool settled_read(const Completion& value) {
  return value.read_not_dispatched||value.read_interrupted||ended_retained_read(value)||(value.account.bound.result.terminal
   &&value.account.bound.result.remote_ok&&value.status.ok());
 }
 static bool temporary_read(const Completion& value) {
  if(value.read_not_dispatched||value.read_interrupted||ended_retained_read(value))return true;
  if(value.status.ok())return Clock::now()>=value.deadline&&!value.event_page.gap;
  const auto& status=value.status;
  if(status.code==ErrorCode::Timeout||status.code==ErrorCode::SubmissionUnknown)return true;
  if(status.code==ErrorCode::StaleSession)return status.reason=="qmt_host_binding_changed"
    ||status.reason=="qmt_trade_binding_changed";
  if(status.code!=ErrorCode::IoError&&status.code!=ErrorCode::Unavailable)return false;
  // 完整503仅表达只读来源/容量不可用；不据此重发任何已进入SDK的POST。
  return status.reason.compare(0,27,"qmt_http_remote_failure:503")==0
    ||value.event_failure.http_status==503&&value.event_failure.response_complete
    ||value.account.bound.result.http_status==503
    ||status.reason=="qmt_host_result_unknown";
 }
 bool wait_read(Completion& value,TaskCredit& credit,std::size_t& result_charge) {
  if(stop_requested||event_detached||!spi)return false;
  if(!logged_in&&(value.kind==Kind::Prepare||value.kind==Kind::Login)
     &&value.status.code!=ErrorCode::StaleSession&&temporary_read(value)){
   // 首次准备只有绑定/事件上下文GET，原轮次已结束且没有SDK请求责任。
   // 先归还名额，再沿原每轮D续接；初次已固定绑定冲突仍沿原故障边界。
   // 外层启动总截止和stop负责最终收口，已登录读代际另沿原ID协议处理。
   Task next;next.kind=value.kind;next.deadline=deadline();credit.retire();
   if(enqueue(std::move(next))!=0)fail(failure(ErrorCode::Backpressure,"qmt_standard_connect_capacity"));
   return true;
  }
  if(!logged_in)return false;
  const bool ordinary=value.kind==Kind::Query||value.kind==Kind::Resolve;
  const bool event=value.kind==Kind::EventPage||value.kind==Kind::EventQuery||value.kind==Kind::EventResolve;
  if(!ordinary&&!event)return false;
  if(value.resume_read){
   auto found=held_reads.find(value.id);require(found!=held_reads.end(),"qmt_standard_original_read_missing");
   if(settled_read(value)){
    held_reads.erase(found); // 原结果已收到或Host确认旧票据结束；旧观察不跨D交付。
   }else {
    if(!temporary_read(value)){fail(value.status);return true;}
    found->second.charge=result_charge;result_charge=0;found->second.inflight=false;
    credit.transfer();
   }
   std::lock_guard<std::mutex> lock(mutex);observation_refresh_task=0;
   observation_refresh_at=Clock::now()+std::chrono::milliseconds(event_poll_ms);cv.notify_all();return true;
  }
  if(!temporary_read(value))return false;
  const bool pending=(value.kind==Kind::Query||value.kind==Kind::EventQuery)
    &&value.query_step>=QueryStep::SubmitEntered&&!value.account.bound.result.terminal&&!ended_retained_read(value);
  if(pending){
   HeldRead held;held.receipt=std::move(value.account.bound.receipt);
   if(held.receipt.request_body.empty())held.receipt=std::move(value.saved_receipt);
   require(!held.receipt.request_body.empty()&&held_reads.size()<max_queue,"qmt_standard_original_read_receipt");
   held.stage=value.stage;held.generation=value.read_generation;held.charge=result_charge;result_charge=0;
   if(event_chain&&value.kind==Kind::EventQuery){held.charge=add_size(held.charge,event_chain->query_charge);event_chain->query_charge=0;}
   require(held_reads.emplace(value.id,std::move(held)).second,"qmt_standard_original_read_duplicate");credit.transfer();
  }
  // worker仅保留成功Query票据供Resolve；晚D成功在此抑制交付后归还一次。
  if(value.kind==Kind::Query&&!pending&&value.status.ok())release_read(value.read_generation);
  if(value.kind==Kind::Resolve){
   auto found=candidates.find(value.id);
   if(found!=candidates.end()){const auto reserved=found->second.charge;candidates.erase(found);finish_charge(reserved);}
  }
  std::lock_guard<std::mutex> lock(mutex);
  if(event&&event_chain){
   require(!event_chain->candidate||value.kind==Kind::EventResolve,"qmt_standard_wait_event_borrow");
   event_chain->candidate.reset();release_event_callback_locked();
   if(!pending)release_read_locked(event_chain->read_generation?event_chain->read_generation:value.read_generation);
   if(event_chain->query_charge)uncharge(event_chain->query_charge);
   event_chain.reset();uncharge(chain_charge);chain_charge=0;read_cursor=handled_cursor;
  }
  read_waiting=true;query_flow_mask=0;observation_refresh_task=0;
  observation_refresh_stage=3;observation_refresh_at=Clock::now()+std::chrono::milliseconds(event_poll_ms);
  cv.notify_all();return true;
 }
 void fence_terminal_event_locked(Completion& result)
 {
  // 真实只读失败交owner等待/原ID续核；不在发布线程把暂不可用锁存为永久退出。
  if(result.kind==Kind::EventQuery||result.kind==Kind::EventResolve){
   result.late=Clock::now()>=result.deadline;
   if(result.late&&result.delivery_status.ok())result.delivery_status.code=ErrorCode::Timeout;
  }
  if(logged_in&&!stop_requested&&!event_detached&&temporary_read(result))return;
  if(result.kind==Kind::EventQuery||result.kind==Kind::EventResolve){
   // 原operation永不覆写；同commit锁中的迟到状态只有固定code，不分配诊断文本。
   result.late=Clock::now()>=result.deadline;
   if(result.late&&result.delivery_status.ok())result.delivery_status.code=ErrorCode::Timeout;
   if(event_operation_failed(result)||!result.delivery_status.ok()){hard_fault=true;writes_blocked=true;worker_stop=true;}
   return;
  }
  if(result.kind!=Kind::EventPage)return;
  // 调用者已持发布锁。成功页、正常停止和纯排空检查共享同一个原D终结点。
  if(Clock::now()>=result.deadline){
   hard_fault=true;writes_blocked=true;worker_stop=true;event_timeout(result);return;
  }
  if(result.status.ok()||result.event_failure.outcome==QmtTradeEventReadOutcome::ControlStoppedBeforeStage)return;
  if(!event_control.stop_requested()&&!result.event_drain_failed
   &&(result.event_drain_pending||event_transport_retry(result)))return;
  // 原错误完成值仍交owner，SPI与原close D由owner形成。
  hard_fault=true;writes_blocked=true;worker_stop=true;
 }
 // 调用者持mutex；记录实际入队时刻，原任务身份/绝对D/容量和顺序保持。
 void queue_task(Task&& task){task.queued_at=Clock::now();tasks.push_back(std::move(task));}
 // 连续阶段继承原绝对D；在同一worker选择较早D，等D沿原入队顺序。
 // 调用者已持mutex且队列非空；只移动原Task，不改身份、收费或截止。
 Task take_task()
 {
  require(!tasks.empty(),"qmt_standard_task_queue_empty");
  const auto next=std::min_element(tasks.begin(),tasks.end(),[](const Task& a,const Task& b){return a.deadline<b.deadline;});
  Task value=std::move(*next);tasks.erase(next);return value;
 }
 void work()
 {
  {std::lock_guard<std::mutex> lock(mutex);worker_thread=std::hash<std::thread::id>{}(std::this_thread::get_id());}worker_live=true;
  // 两个客户端从构造到最终drain始终属于本worker；跨线程完成值没有WT地址。
  std::unique_ptr<QmtHostAccountClient> account;
  std::unique_ptr<QmtHostTradeClient> trade;
  std::map<std::uint64_t,std::unique_ptr<ReadGeneration>> reads;
  std::uint64_t next_read=0,active_read=0; // 当前认证运输代际；普通观察复用原客户端与HTTP owner。
  QmtTradeEventReadContext read_origin;
  // 固定实例/账户/profile与Source业务session。运输binding只属于该轮，不作为业务session。
  auto same_read_source=[&](const QmtTradeEventReadContext& value) {
   if(read_origin.source.session_id.empty()||value.source.session_id!=read_origin.source.session_id
    ||value.read_profile_body!=read_origin.read_profile_body
    ||value.read_result_capacity!=read_origin.read_result_capacity
    ||value.admitted_event_page_capacity!=read_origin.admitted_event_page_capacity)return false;
   // 业务来源固定账户/profile/session及完整route等原字段；仅认证连接的两项随机身份可换代。
   // 当前完整B仍归各代Core精确钉住；原票据、命令、query proof及event来源绝不改绑。
   rapidjson::Document origin,current;
   if(!parse_bounded_qmt_json(read_origin.source.binding_json,origin,4096,4096)
    ||!parse_bounded_qmt_json(value.source.binding_json,current,4096,4096)
    ||!qmt_host_codec::binding(origin,nullptr,"2.0")||!qmt_host_codec::binding(current,nullptr,"2.0"))return false;
   for(const auto key:{"transport_generation","host_instance_id"}){origin.RemoveMember(key);current.RemoveMember(key);}
   return qmt_host_codec::encode(origin)==qmt_host_codec::encode(current);
  };
  auto callback_wait=[](Clock::time_point until) {
   const auto left=std::chrono::duration_cast<std::chrono::milliseconds>(until-Clock::now()).count();
   return left>0?static_cast<unsigned>((std::min<std::int64_t>)(left,100)):0u;
  };
  auto reap_reads=[&](Clock::time_point until) {
   bool complete=true;
   for(auto it=reads.begin();it!=reads.end();){
    if(!it->second->released){++it;continue;}
    auto& read=*it->second;
    auto a=read.account?read.account->drain_callbacks(callback_wait(until)):Status{};
    auto t=read.identity?read.identity->drain_callbacks(callback_wait(until)):Status{};
    if(a.ok()&&t.ok()){
     const auto held=read.charge;it=reads.erase(it);finish_charge(held);
    }else {complete=false;++it;}
   }
   return complete;
  };
  auto open_read=[&](std::uint64_t& id,SignedHttpDeadline& end,
      QmtTradeEventReadFailure* failure,const QmtAccountControl* control)->ReadGeneration& {
   if(id){auto found=reads.find(id);require(found!=reads.end(),"qmt_standard_read_generation_missing");return *found->second;}
   if(active_read){
    auto& read=*reads.at(active_read);QmtTradeEventReadContext current;
    auto status=read.identity->prepare_event_read_context(end,current,failure,control);
    if(status.ok()){
     if(!same_read_source(current))throw ReadGenerationFailure{
         Status{ErrorCode::StaleSession,"qmt_standard_read_source_changed"}};
     require(same_event_source(current.source,read.context.source),"qmt_standard_read_generation_binding_changed");
     ++read.users;id=active_read;return read;
    }
    // 只在新观察尚无SDK请求时建立整代。原在途票据仍使用其精确B，不改绑。
    if(status.code!=ErrorCode::StaleSession||status.reason!="qmt_trade_binding_changed")
     throw ReadGenerationFailure{std::move(status)};
   }
   require(reads.size()<max_queue&&next_read!=(std::numeric_limits<std::uint64_t>::max)(),"qmt_standard_read_generation_capacity");
   // 同时预留两客户端响应银行及有限认证快照；原队列总预算继续为唯一上限。
   const auto reserved=add_size(times_size(http.max_response_bytes,2),65536);
   {std::lock_guard<std::mutex> lock(mutex);require(charge(reserved),"qmt_standard_read_generation_capacity");}
   std::unique_ptr<ReadGeneration> value;const auto created=++next_read;
   try {
    value.reset(new ReadGeneration);value->charge=reserved;
    value->account.reset(new QmtHostAccountClient(http,expected.account,&account_control,QmtAccountReadVersion::V4));
    value->identity.reset(new QmtHostTradeClient(http,expected));
    reads.emplace(created,std::move(value));
   }catch(...){finish_charge(reserved);throw;}
   auto& read=*reads.at(created);
   try {
    auto status=read.identity->prepare_event_read_context(end,read.context,failure,control);
    if(!status.ok())throw ReadGenerationFailure{std::move(status)};
    if(!same_read_source(read.context))throw ReadGenerationFailure{
        Status{ErrorCode::StaleSession,"qmt_standard_read_source_changed"}};
   }catch(...){read.released=true;throw;}
   if(active_read){auto& previous=*reads.at(active_read);if(!previous.users)previous.released=true;}
   // 新代已经完成read-binding与trade-status的同次完整准入及固定业务来源复核。
   // 发布当前认证来源供后续新写/审计使用；历史收据仍由原代、原ID和原B解释。
   auto current_source=read.context.source;
   {std::lock_guard<std::mutex> lock(mutex);audit_source=std::move(current_source);audit_source_ready=true;}
   active_read=created;id=created;read.users=1;
   return read;
  };
  try {
   account.reset(new QmtHostAccountClient(http,expected.account,&account_control,QmtAccountReadVersion::V4));
   trade.reset(new QmtHostTradeClient(http,expected));
   for(;;){
    Task task;Completion* reserved=nullptr;
    {std::unique_lock<std::mutex> lock(mutex);cv.wait(lock,[&]{return worker_stop.load()||!tasks.empty()||!released_reads.empty();});
     while(!released_reads.empty()){
      auto found=reads.find(released_reads.front());
      if(found!=reads.end()){
       require(found->second->users>0,"qmt_standard_read_generation_ticket");
       --found->second->users;if(!found->second->users&&found->first!=active_read)found->second->released=true;
      }
      released_reads.pop_front();
     }
     lock.unlock();reap_reads(Clock::now());lock.lock();
     if(worker_stop)break;
     if(tasks.empty())continue;
     // 槽必须先于I/O取得；异常满环只在取任务之前等待，stop直接唤醒退出。
     cv.wait(lock,[&]{return worker_stop.load()||results.can_reserve();});if(worker_stop)break;
     auto& slot=results.reserve();reserved=&slot;task=take_task();
     diagnostic_worker_started=Clock::now();diagnostic_worker_busy=true;diagnostic_worker_kind=task.kind;
     diagnostic_worker_stage=task.stage;diagnostic_worker_task=task.id;
     diagnostic_worker_wait_ms=std::chrono::duration_cast<std::chrono::milliseconds>(diagnostic_worker_started-task.queued_at).count();
     slot.queue_wait_ms=diagnostic_worker_wait_ms;
     slot.kind=task.kind;slot.stage=task.stage;slot.id=task.id;slot.generation=task.generation;
     slot.deadline=task.deadline;slot.charge=task.charge;slot.event_index=task.event_index;slot.read_generation=task.read_generation;slot.resume_read=task.resume_read;}
    Completion& result=*reserved;result.order=task.order;
    if(!communication_responsibility(result))
     result.capacity_reason="qmt_standard_result_capacity"; // 普通任务原512诊断预留内28 bytes；Audit/写始终空。
    result.insert_failure_confirmed=task.kind==Kind::Insert||task.kind==Kind::Cancel;
    if(task.kind==Kind::AuditOriginal)result.command_id.swap(task.pending_key);
    try {
     SignedHttpDeadline end(task.deadline);
     if(task.kind==Kind::AuditOriginal){
      // 只为本次核查借用当前已认证代；resume仍只GET原收据UUID，不重派旧命令。
      auto& current=open_read(result.read_generation,end,nullptr,nullptr);
      auto status=current.account->prepare(end);
      if(!status.ok())throw ReadGenerationFailure{std::move(status)};
      run_audit(task,result,*current.account,*current.identity);
     }
     else if(!end.remaining()){
      if(task.kind==Kind::EventPage)event_timeout(result);
      else if(task.kind==Kind::EventQuery||task.kind==Kind::EventResolve){result.status=fixed_failure(ErrorCode::Timeout);result.local_failure=true;}
      else result.status=failure(ErrorCode::Timeout,"qmt_standard_task_deadline");
     }
     else if(task.kind==Kind::Prepare||task.kind==Kind::Login){
      result.status=account->prepare(end);if(result.status.ok())result.status=events_enabled
       ?trade->prepare_event_read_context(end,result.event_context):trade->prepare(end);
      if(result.status.ok())result.status=pin_audit_source(*trade);
      if(result.status.ok()&&task.kind==Kind::Prepare)prepare_event_bootstrap(result,*trade,end);
      if(result.status.ok()){
       QmtTradeEventReadContext context;
       result.status=trade->prepare_event_read_context(end,context);
       if(result.status.ok()){
        if(read_origin.source.session_id.empty())read_origin=std::move(context);
        else require(same_read_source(context),"qmt_standard_read_source_changed");
       }
      }
     }else if(task.kind==Kind::Query){
      auto& read=open_read(result.read_generation,end,nullptr,&account_control);
      if(task.resume_read){
       result.query_step=QueryStep::SubmitEntered;
       result.account=read.account->resume(task.original_read,end);
       result.status=result.account.bound.result.status;
      }else {
      result.query_step=QueryStep::Prepare;
      result.status=read.account->prepare(end);
      if(!result.status.ok())throw ReadGenerationFailure{std::move(result.status)};
      result.query_step=QueryStep::Create;
      auto prepared=read.account->create_request(static_cast<QmtAccountDatatype>(task.stage),end);
      result.status=prepared.status;
      if(result.status.ok()&&prepared.request){
       require(prepared.request->receipt().binding_json==read.context.source.binding_json
        &&prepared.request->read_profile_body()==read.context.read_profile_body,"qmt_standard_read_generation_binding_changed");
       result.saved_receipt=prepared.request->receipt();result.query_step=QueryStep::SubmitEntered;
       result.account=read.account->submit_once(std::move(prepared.request),end);result.status=result.account.bound.result.status;
       result.query_step=QueryStep::Returned;
      }
      }
     }else if(task.kind==Kind::EventQuery){
      auto& read=open_read(result.read_generation,end,nullptr,&event_control);
      run_event_query(task,result,*read.account,end);
     }else if(task.kind==Kind::Resolve||task.kind==Kind::EventResolve){
      if(task.kind!=Kind::EventResolve||event_local_gate(result,end)){
       auto& read=open_read(result.read_generation,end,nullptr,
           task.kind==Kind::EventResolve?&event_control:&account_control);
       result.resolved=resolve_qmt_account_identity(std::move(task.plan),*read.identity);
       if(task.kind==Kind::EventResolve){
         if(result.resolved)copy_operation_status(result,result.resolved->status());
         else {result.local_failure=true;result.status=fixed_failure(ErrorCode::IoError);}
        }else result.status=result.resolved?result.resolved->status():(events_enabled?fixed_failure(ErrorCode::IoError):failure(ErrorCode::IoError,"qmt_standard_identity_resolution_missing"));
      }
     }else if(task.kind==Kind::EventPage){
      if(event_control.stop_requested())event_stopped(result);
      else {
       auto& read=open_read(result.read_generation,end,&result.event_failure,&event_control);
       run_event_read(task,result,*read.identity,end);
      }
     }else {
      // 新取消/委托沿当前完整B准备，避免只读已换代而长期交易Core仍钉住初代。
      // 原Core的pin、同代状态和当前取消proof校验保持；每个金融任务仍只提交一次。
      auto& current=open_read(result.read_generation,end,nullptr,nullptr);
      run_write(task,result,*current.identity);
     }
    }catch(ReadGenerationFailure& failure){
     if(task.kind==Kind::AuditOriginal)audit_error(result.audit,failure.status); // 准备失败仍沿原审计分类，Pending原组保持。
     result.status=std::move(failure.status);
    }catch(const std::bad_alloc&){
     if(task.kind==Kind::EventPage)event_local_failure(result);
     if(task.kind==Kind::EventQuery||task.kind==Kind::EventResolve){result.local_failure=true;result.status=fixed_failure(ErrorCode::IoError);}
     else if(task.kind==Kind::AuditOriginal){result.audit.diagnostic=AuditDiagnostic::Capacity;result.audit.error=ErrorCode::Backpressure;}
     else {const bool write=task.kind==Kind::Insert||task.kind==Kind::Cancel;
      const auto code=write&&!result.insert_failure_confirmed?ErrorCode::SubmissionUnknown:ErrorCode::IoError;
       result.status=events_enabled?fixed_failure(code):failure(code,"qmt_standard_worker_operation_failed");
      if(write){if(!result.insert_failure_confirmed)fence_unknown();else {hard_fault=true;writes_blocked=true;}}}
    }catch(...){
     if(task.kind==Kind::EventPage)event_local_failure(result);
     if(task.kind==Kind::EventQuery||task.kind==Kind::EventResolve){result.local_failure=true;result.status=fixed_failure(ErrorCode::IoError);}
     else if(task.kind==Kind::AuditOriginal){result.audit.diagnostic=AuditDiagnostic::HardFault;result.audit.error=ErrorCode::IoError;}
     else {const bool write=task.kind==Kind::Insert||task.kind==Kind::Cancel;
      const auto code=write&&!result.insert_failure_confirmed?ErrorCode::SubmissionUnknown:ErrorCode::IoError;
       result.status=events_enabled?fixed_failure(code):failure(code,"qmt_standard_worker_operation_failed");
      if(write){if(!result.insert_failure_confirmed)fence_unknown();else {hard_fault=true;writes_blocked=true;}}}
    }
    result.read_not_dispatched=read_not_dispatched(result);
    result.read_interrupted=query_first&&events_enabled&&interrupted_read(result);
    const bool held_query=task.kind==Kind::Query&&result.query_step>=QueryStep::SubmitEntered
      &&!result.account.bound.result.terminal&&temporary_read(result);
    const bool financial=task.kind==Kind::Insert||task.kind==Kind::Cancel||task.kind==Kind::AuditOriginal;
    if(result.read_generation&&(financial||task.kind==Kind::Resolve||(task.kind==Kind::Query
        &&(task.resume_read?settled_read(result):!result.status.ok()&&!held_query)))){
     auto found=reads.find(result.read_generation);if(found!=reads.end()){
      require(found->second->users>0,"qmt_standard_read_generation_ticket");
      --found->second->users;if(!found->second->users&&found->first!=active_read)found->second->released=true;
     }
     if(financial)result.read_generation=0; // 金融完成只携原收据；本次连接借用已在worker收尾，不交owner重复释放。
    }
    reap_reads(Clock::now());
    // 写任务已在POST前预留2*C+原收据+4096，审计已预留完整Peak+Sigma。
    // 两类含不可丢事实的完成值沿原reserve交付，无追加预算/字符串复制/尺寸计算。
    std::size_t wanted=result.charge;
    if(!communication_responsibility(result)){
     wanted=add_size(add_size(task.order.payload(),result.status.reason.size()),result.command_id.size());
     if(task.kind==Kind::Query)wanted=events_enabled?result.charge:add_size(wanted,bytes(result.account));
     if(task.kind==Kind::Resolve)wanted=events_enabled?512:add_size(wanted,identity_budget.max_total_bytes);
     if(events_enabled&&(task.kind==Kind::Prepare||task.kind==Kind::Login))
      wanted=add_size(add_size(context_reserve,512),result.event_bootstrap_reserve);
     if(task.kind==Kind::EventPage||task.kind==Kind::EventResolve)wanted=512;
    }
    if(task.kind==Kind::EventPage||task.kind==Kind::EventQuery||task.kind==Kind::EventResolve)task.event_context={};
    task.original_read={}; // 原收据副本先销毁，再按完成值寿命归还原银行。
    {std::lock_guard<std::mutex> lock(mutex);
     result.running_ms=std::chrono::duration_cast<std::chrono::milliseconds>(Clock::now()-diagnostic_worker_started).count();
     diagnostic_worker_busy=false;}
    if(!publish(std::move(result),wanted)){publish_worker_failure();break;}
   }
  }catch(...){
   publish_worker_failure();
  }
  cv.notify_all();
  // 关闭截止首次由owner冻结；drain超时保留客户端和worker，后继等待不重授业务TTL。
  bool complete=false;
  while(!complete){
   Clock::time_point until;
   {std::unique_lock<std::mutex> lock(mutex);cv.wait(lock,[&]{return close_started;});until=close_deadline;}
   auto a=account?account->drain_callbacks(callback_wait(until)):Status{};
   auto t=trade?trade->drain_callbacks(callback_wait(until)):Status{};
   for(auto& read:reads)read.second->released=true;
   const bool read_closed=reap_reads(until);complete=a.ok()&&t.ok()&&read_closed;
   if(!complete){std::unique_lock<std::mutex> lock(mutex);cv.wait_for(lock,std::chrono::milliseconds(10));}
  }
  account.reset();trade.reset();
  {std::lock_guard<std::mutex> lock(mutex);drained=true;worker_done=true;worker_live=false;}cv.notify_all();
 }
 // 网络客户端只存在于IO worker；Task/Completion和owner只持有有限数值票据。
 // 一代覆盖整轮Query→Resolve或事件页续段；新金融任务短借当前代，旧命令仍持有独立原收据。
 struct ReadGenerationFailure {Status status; /* 原握手结果，逐值保留固定错误与停止语义。 */};
 struct ReadGeneration {
  std::unique_ptr<QmtHostAccountClient> account; // 本轮账户查询及原结果收束，仅worker使用。
  std::unique_ptr<QmtHostTradeClient> identity; // 本代身份/事件解析及已授权新金融调用；Core完整B固定，不改绑旧请求。
  QmtTradeEventReadContext context; // 同次完整认证来源、profile及资源上限。
  std::size_t charge=0; // 原总预算内持有到全部HTTP回调排空。
  unsigned users=0; // 当前借用该运输代际的查询/事件链及金融任务票据，仅worker增减。
  bool released=false; // owner已交还票据；网络资源仍由worker判定退役。
 };
 std::deque<std::uint64_t> released_reads; // owner到worker的有限退役票据，受max_queue约束。
 void release_read_locked(std::uint64_t id) {
  if(!id)return;
  require(released_reads.size()<max_queue,"qmt_standard_read_release_capacity");
  released_reads.push_back(id);cv.notify_all();
 }
 void release_read(std::uint64_t id) {
  std::lock_guard<std::mutex> lock(mutex);release_read_locked(id);
 }
 std::thread worker;
 void remember(const AccountBatch& batch,unsigned stage,bool complete_query=false)
 {
  if(stage!=1)return;
  std::string query_source;
  if(query_first&&complete_query){
   require(!batch.source.empty(),"qmt_standard_terminal_query_source_missing");
   query_source=signed_http_sha256(batch.source);
   require(query_source.size()==64,"qmt_standard_terminal_query_source_hash");
  }
  std::lock_guard<std::mutex> lock(mutex);
  for(unsigned i=0;i<batch.array->size();++i){auto order=batch.array->at<wtp::WTSOrderInfo>(i);
   const auto entrust=copied(order->getEntrustID()),tag=copied(order->getUserTag());if(entrust.empty()||tag.empty())continue;
   auto found=identities.find(entrust);
   Identity value{tag,copied(order->getExchg()),copied(order->getCode()),copied(order->getOrderID())};
   if(found!=identities.end()){
    require(found->second.tag==value.tag&&found->second.exchange==value.exchange&&found->second.code==value.code
     &&(found->second.broker.empty()||found->second.broker==value.broker),"qmt_standard_identity_index_conflict");
    if(found->second.broker.empty())require(charge(value.broker.size()),"qmt_standard_identity_index_capacity");
   }else {
    require(identities.size()<static_cast<std::size_t>(binding.row_limit)+max_pending,"qmt_standard_identity_index_capacity");
    const auto n=add_size(entrust.size()+value.tag.size()+value.exchange.size()+value.code.size()+value.broker.size(),identity_extra());
    require(charge(n),"qmt_standard_identity_index_capacity");
   }
   if(query_first&&found!=identities.end()){
    auto& retained=found->second;retained.broker.swap(value.broker);
    if(retained.group_id){
     // P8真实身份先于SPI；原SDK完成稍后到达时只能移交收据，不能回退此事实。
     if(retained.observation==SubmissionObservation::Fault||retained.observation==SubmissionObservation::None){
      retained.observation=SubmissionObservation::Fault;submission_fault();
     }else {
      // 完整查询与事件队列独立推进：已核终态可先于较早活动回报到达。
      // 提交责任只单调收敛，不能用活动观察撤销终态或生成SDK未知；原事件仍由交付索引按序校验。
      if(retained.observation!=SubmissionObservation::TerminalNeedsReconciliation||!order->isAlive())
       retained.observation=order->isAlive()?SubmissionObservation::ObservedActive:SubmissionObservation::TerminalNeedsReconciliation;
      if(!order->isAlive()){
       // 事件终态先触发完整O补查；完整O确认后，排除此前已排队的P查询。
       if(!complete_query){retained.terminal_query_barrier=0;retained.terminal_query_source[0]=0;}
       else if(!retained.terminal_query_barrier||retained.terminal_query_filled!=order->getVolTraded()
          ||std::memcmp(retained.terminal_query_source,query_source.c_str(),65)!=0){
        retained.terminal_query_barrier=next_task;retained.terminal_query_filled=order->getVolTraded();
        std::memcpy(retained.terminal_query_source,query_source.c_str(),65);
       }
      }
     }
    }
   }else identities[entrust]=std::move(value);
  }
 }
 // 仅在完整P已交付SPI并返回后调用。终态后新建、同来源的P直接更新原WT；
 // 这里只释放防重复提交责任，不用成交量计算或覆盖账户持仓。
 void position_query_applied(const AccountBatch& batch,std::uint64_t task_id)
 {
  if(!query_first)return;
  const auto source=signed_http_sha256(batch.source);
  require(source.size()==64,"qmt_standard_position_query_source_hash");
  std::lock_guard<std::mutex> lock(mutex);
  if(stop_requested||hard_fault||!spi)return;
  bool retired_group=false;
  for(auto& pair:identities){auto& value=pair.second;
   if(!value.group_id||value.observation!=SubmissionObservation::TerminalNeedsReconciliation
      ||!value.terminal_query_barrier||task_id<=value.terminal_query_barrier)continue;
   if(std::memcmp(value.terminal_query_source,source.c_str(),65)!=0){submission_fault();return;}
   // 原调用及券商处置仍未核清、或原收据尚未移交时，保留原组和原UUID。
   if(value.retained_receipt.command_body.empty()||pending.find(value.command_id)!=pending.end())continue;
   QmtTradeReceipt retired;swap_receipt(retired,value.retained_receipt);
   uncharge(value.retained_charge);value.retained_charge=0;
   value.group_id=0;value.observation=SubmissionObservation::None;
   value.terminal_query_barrier=0;value.terminal_query_source[0]=0;
   retired_group=true;
  }
  // 本地运输未知只在原SDK收据已明确移交、原终态O及后继P均落入原SPI后退役。
  // 缺独立券商终态证明的SDK unknown仍持Pending；硬错继续阻断，原调用事实不改写。
  if(retired_group&&unknown_fenced&&pending.empty()&&!submissions_closed
     &&ingress_error.ok()&&owner_error.ok()
     &&(first_error.ok()||first_error.code==ErrorCode::SubmissionUnknown)){
   bool unresolved=false;for(const auto& pair:identities)if(pair.second.group_id&&pair.second.observation!=SubmissionObservation::None){unresolved=true;break;}
   if(!unresolved&&!hard_fault){observation_reconciled=true;unknown_fenced=false;first_error={};writes_blocked=hard_fault.load()||stop_requested.load();submission_refresh_after=Clock::time_point::min();}
  }
 }
 // owner在本轮pump末尾安排普通查询；任务数/字节/截止沿原enqueue与Query链。
 // 不占锁调用SPI或I/O，不创建另一个账户查询线程，也不在原组结束前开新组。
 void advance_submission_refresh()
 {
  if(!query_first)return;
  unsigned stage=0;bool needed=false;std::uint64_t after_query=0;
  {
   std::lock_guard<std::mutex> lock(mutex);
   if(!active()||!spi||!logged_in||hard_fault||submission.open||submission_refresh_task
      ||Clock::now()<submission_refresh_after)return;
   for(const auto& pair:identities){const auto& value=pair.second;
    // 真正SDK未知的原Pending仍由有限原ID审计持有；不循环制造普通O/P来假装核清。
    if(unknown_fenced&&value.retained_receipt.command_body.empty())continue;
    if(unknown_fenced&&value.group_id&&(value.observation==SubmissionObservation::Unknown
       ||value.observation==SubmissionObservation::AwaitBrokerObservation||value.observation==SubmissionObservation::ObservedActive)){
     needed=true;stage=1;break;
    }
    if(value.group_id&&value.observation==SubmissionObservation::TerminalNeedsReconciliation){
     needed=true;if(!value.terminal_query_barrier){stage=1;break;}
     after_query=(std::max)(after_query,value.terminal_query_barrier);
    }
   }
  }
  if(!needed)return;
  Task task;task.kind=Kind::Query;task.stage=stage;task.deadline=deadline();
  std::uint64_t id=0;
  if(enqueue(std::move(task),false,&id,stage==0,after_query)==0){std::lock_guard<std::mutex> lock(mutex);submission_refresh_task=id;
   if(unknown_fenced)submission_refresh_after=Clock::now()+std::chrono::milliseconds(request_ms);}
 }
 bool observation_refresh_ready(Clock::time_point now)const {
  return (read_waiting||observation_refresh_ms)&&active()&&logged_in&&spi&&(read_waiting||query_flow_mask==15)
   &&!submissions_closed&&!hard_fault&&!observation_refresh_task&&now>=observation_refresh_at;
 }
 Clock::time_point observation_refresh_wake(Clock::time_point until)const {
  if((read_waiting||observation_refresh_ms)&&active()&&logged_in&&spi&&(read_waiting||query_flow_mask==15)
     &&!submissions_closed&&!hard_fault&&!observation_refresh_task)
   return (std::min)(until,observation_refresh_at);
  return until;
 }
 void schedule_observation_refresh(){
  {std::lock_guard<std::mutex> lock(mutex);if(!observation_refresh_ready(Clock::now()))return;}
  if(read_waiting&&!held_reads.empty()){
   std::lock_guard<std::mutex> lock(mutex);auto& original=*held_reads.begin();if(original.second.inflight)return;
   Task task;task.kind=Kind::Query;task.id=original.first;task.generation=generation;
   task.stage=original.second.stage;task.read_generation=original.second.generation;
   task.resume_read=true;task.original_read=original.second.receipt;task.deadline=deadline();task.charge=original.second.charge;
   queue_task(std::move(task));original.second.charge=0;original.second.inflight=true;
   observation_refresh_task=original.first;cv.notify_all();return;
  }
  Task task;task.kind=Kind::Query;task.stage=observation_refresh_stage;task.deadline=deadline();
  std::uint64_t id=0;const auto rc=enqueue(std::move(task),false,&id);
  std::lock_guard<std::mutex> lock(mutex);
  if(rc==0)observation_refresh_task=id;
  else observation_refresh_at=Clock::now()+std::chrono::milliseconds(read_waiting?event_poll_ms:observation_refresh_ms);
 }
 void observation_refresh_applied(std::uint64_t task_id){
  std::lock_guard<std::mutex> lock(mutex);
  if(!observation_refresh_task||observation_refresh_task!=task_id)return;
  observation_refresh_task=0;
  if(read_waiting){
   if(observation_refresh_stage==0){read_waiting=false;observation_refresh_stage=3;
    observation_refresh_at=Clock::now()+std::chrono::milliseconds(observation_refresh_ms);}
   else {observation_refresh_stage=observation_refresh_stage==3?1:observation_refresh_stage==1?2:0;
    observation_refresh_at=Clock::now();}
  }else if(observation_refresh_stage==3){observation_refresh_stage=0;observation_refresh_at=Clock::now();}
  else {observation_refresh_stage=3;observation_refresh_at=Clock::now()+std::chrono::milliseconds(observation_refresh_ms);}
  cv.notify_all();
 }
 void forget(const std::string& entrust)
 {
  std::lock_guard<std::mutex> lock(mutex);auto found=identities.find(entrust);if(found==identities.end())return;
  const auto& value=found->second;
  if(query_first&&value.group_id&&(value.observation==SubmissionObservation::ObservedActive
     ||value.observation==SubmissionObservation::TerminalNeedsReconciliation||value.observation==SubmissionObservation::Fault)){
   submission_fault();return;
  }
  uncharge(identity_charge(entrust,value));identities.erase(found);
 }
 void entrust_reply(const OrderValue& value,const Status& status,bool rejected)
 {
  if(!spi||stop_requested)return;
  auto base=spi->getBaseDataMgr();auto contract=base?base->getContract(value.insert.code.c_str(),value.insert.exchange.c_str()):nullptr;
  require(contract!=nullptr,"qmt_standard_rejection_contract_missing");
  std::unique_ptr<wtp::WTSEntrust,ObjectRelease> entrust(wtp::WTSEntrust::create(value.insert.code.c_str(),
   static_cast<double>(value.insert.quantity),value.price,value.insert.exchange.c_str()));
  require(bool(entrust),"qmt_standard_rejection_allocation_failed");entrust->setContractInfo(contract);
  entrust->setEntrustID(value.insert.entrust_id.c_str());entrust->setUserTag(value.insert.user_tag.c_str());
  entrust->setDirection(value.direction);entrust->setOffsetType(value.offset);entrust->setPriceType(wtp::WPT_LIMITPRICE);
  entrust->setOrderFlag(wtp::WOF_NOR);entrust->setBusinessType(wtp::BT_CASH);
  // 净仓方向与原direction/offset独立，失败回报须保留调用方原isNet/isBuy语义。
  if(value.net)entrust->setNetDirection(value.insert.buy);
  std::unique_ptr<wtp::WTSError,ObjectRelease> error;
  if(rejected)error.reset(wtp::WTSError::create(wtp::WEC_ORDERINSERT,status.reason.c_str()));
  callback([&]{spi->onRspEntrust(entrust.get(),error.get());});
 }
 void publish_write_failure(Completion& result,const Status& status,bool late_completion)
 {
  // Source已证明本次Insert未进入SDK：原pending先由settle_write结算，逐单错误仍完整交给原SPI。
  // 查询优先模式下它只结束该委托，不写入全实例首错；真实未知等待和原硬故障继续独立保留。
  if(query_first&&result.kind==Kind::Insert&&result.business_rejected&&result.insert_failure_confirmed
     &&result.trade.phase==QmtTradePhase::DefinitelyNotCalled){
   forget(result.order.insert.entrust_id);entrust_reply(result.order,result.status,true);return;
  }
  if(result.business_rejected||result.audit.role==PendingRole::UnadmittedTargetLookup)note(status);
  else if(!result.insert_failure_confirmed&&status.code==ErrorCode::SubmissionUnknown){fence_unknown();note(status);}
  else block(status);
  if(result.kind==Kind::Insert&&result.insert_failure_confirmed){
   if(late_completion){
    const auto rejected=result.status.ok()?failure(ErrorCode::Unavailable,"qmt_standard_confirmed_not_called"):result.status;
    forget(result.order.insert.entrust_id);entrust_reply(result.order,rejected,true);
   }else {forget(result.order.insert.entrust_id);entrust_reply(result.order,result.status,true);}
  }else if(!(query_first&&status.code==ErrorCode::SubmissionUnknown&&!hard_fault))
   trader_error(status,!late_completion&&result.kind==Kind::Cancel?wtp::WEC_ORDERCANCEL:wtp::WEC_UNKNOWN);
 }
 void retire_candidates()
 {
  if(events_enabled){
   // owner先释放WT对象；共享Plan/晚到Resolved仍占同pair票据，真join后统一退休。
   for(auto& item:candidates)item.second.value.reset();
  }else {
   std::size_t charge=0;for(const auto& item:candidates)charge=add_size(charge,item.second.charge);
   candidates.clear();if(charge)finish_charge(charge);
  }
  // 只退WT候选；事件worker仍可能借用独立Plan，chain_charge直到join才可收回。
  if(event_chain)event_chain->candidate.reset();
 }
 void install_event_context(QmtTradeEventReadContext&& value,std::size_t& completion_charge,
  bool bootstrap_ready,std::uint64_t bootstrap_cursor)
 {
  if(!events_enabled)return;
  const auto& d=value.admitted_limits;
  require(!value.source.binding_json.empty()&&!value.source.session_id.empty()&&!value.read_profile_body.empty()
   &&d.max_events>0&&value.admitted_event_page_capacity>=add_size(static_cast<std::size_t>(d.max_event_bytes),1024)
   &&value.admitted_event_page_capacity<=d.max_event_page_bytes
   &&value.admitted_event_page_capacity<=http.max_response_bytes,"qmt_standard_event_remote_capacity");
  if(event_context_ready){
   require(same_event_source(value.source,event_context.source)&&value.read_profile_body==event_context.read_profile_body
    &&value.read_result_capacity==event_context.read_result_capacity
    &&value.admitted_event_page_capacity==event_context.admitted_event_page_capacity,"qmt_standard_event_context_changed");
   return;
  }
  if(query_first)require(bootstrap_ready,"qmt_standard_event_bootstrap_missing");
  standard_event_budget::ContextBanks banks;
  standard_event_budget::ContextInputs limits{value.read_result_capacity,value.admitted_event_page_capacity,
   static_cast<std::size_t>(d.max_event_bytes),static_cast<std::size_t>(d.max_command_bytes),static_cast<std::size_t>(d.max_call_result_bytes)};
  if(!standard_event_budget::context(event_budget_input,event_layout,limits,banks).ok())throw EventCapacity{};
  const auto reserve=banks.chain;
  const auto minimum=add_size(add_size(event_partition,context_reserve),add_size(reserve,add_size(ordinary_reserve,1024)));
  require(minimum<=max_queue_bytes&&(!query_first||callback_context_space(banks)),"qmt_standard_event_chain_capacity");
  // 构造失败无可见索引；长期索引分区已在init从同一总预算预留。
  std::unique_ptr<QmtEventDeliveryIndex> index(new QmtEventDeliveryIndex(value.source.binding_json,
   value.source.session_id,event_records,event_partition));
  std::lock_guard<std::mutex> lock(mutex);
  require(completion_charge>=context_reserve,"qmt_standard_event_context_accounting");
  event_context=std::move(value);event_index=std::move(index);chain_reserve=reserve;event_context_banks=banks;
  // 该基线由随后完整P/O/D/A覆盖；它不向交付索引登记历史回报，不ACK/删除Host事件或解除原未知委托。
  if(query_first)read_cursor=handled_cursor=bootstrap_cursor;
  completion_charge-=context_reserve;context_charge=context_reserve;event_context_ready=true;next_event_poll_at=Clock::now();
 }
 bool event_lifecycle()const
 {return events_enabled&&event_context_ready&&active()&&logged_in&&!event_detached&&spi&&query_flow_mask==15;}
 bool event_space(std::size_t n)const
 {return outstanding<max_queue&&next_task!=(std::numeric_limits<std::uint64_t>::max)()&&n<=max_queue_bytes-payload_bytes;}
 bool event_callback_space()const {
  const auto count=event_callback_slots();
  return !event_callback_reserved&&count<max_queue&&outstanding<max_queue-count
   &&event_space(add_size(512,times_size(count,ordinary_reserve)));
 }
 std::size_t callback_continuation_bytes(const standard_event_budget::ContextBanks& banks)const {
  return add_size(512,add_size(times_size(event_callback_slots()+1,ordinary_reserve),
   add_size(banks.query_extra,banks.minimum_identity_work)));
 }
 std::size_t callback_context_minimum(const standard_event_budget::ContextBanks& banks)const {
  return add_size(persistent_event_bytes(),add_size(context_reserve,
   add_size(banks.chain,callback_continuation_bytes(banks))));
 }
 bool callback_context_space(const standard_event_budget::ContextBanks& banks)const
 {return callback_context_minimum(banks)<=max_queue_bytes;}
 std::size_t page_admission_space()const
 {return query_first?add_size(chain_reserve,callback_continuation_bytes(event_context_banks))
  :add_size(chain_reserve,add_size(ordinary_reserve,512));}
 // 调度状态仅在同一mutex内观察；wait只报告可推进事实，不执行I/O或Base/SPI。
 bool event_ready(Clock::time_point now)const
 {
  if(!event_lifecycle())return false;
  if(event_chain){
   if(event_chain->phase==EventPhase::ReadRetryWait)return now>=event_chain->deadline
    ||(now>=event_chain->next_attempt_at&&event_space(512));
   return event_chain->phase==EventPhase::PageReady&&(event_chain->index==event_chain->page.event_count
    ||now>=event_chain->deadline||event_callback_space());
  }
  return now>=next_event_poll_at&&event_space(page_admission_space());
 }
 Clock::time_point event_wake(Clock::time_point until)const
 {
  if(!event_lifecycle())return until;
  if(event_chain){
   if(event_chain->phase==EventPhase::ReadRetryWait){
    const auto due=event_space(512)?(std::min)(event_chain->deadline,event_chain->next_attempt_at):event_chain->deadline;
    return (std::min)(until,due);
   }
   if(event_chain->phase==EventPhase::PageReady)return (std::min)(until,event_chain->deadline);return until;
  }
  return event_space(page_admission_space())?(std::min)(until,next_event_poll_at):until;
 }
 void advance_event()
 {
  std::lock_guard<std::mutex> lock(mutex);require(bool(event_chain),"qmt_standard_event_chain_missing");
  const auto& event=event_chain->validated.document["events"][static_cast<rapidjson::SizeType>(event_chain->index)];
  release_event_callback_locked();
  const auto sequence=event["sequence"].GetUint64();
  require(sequence==handled_cursor+1,"qmt_standard_event_handled_gap");handled_cursor=sequence;
  ++event_chain->index;event_chain->phase=EventPhase::PageReady;cv.notify_all();
 }
 // 调用者持mutex；仅在该项处理栈已退役其mapped/page借用后结算。
 // 正常终态不再受已结束任务的D约束；stop/detach仍保留借用额度直到join。
 bool settle_completed_event_chain_locked(Clock::time_point now)
 {
  if(stop_requested||event_detached||!event_chain||event_chain->phase!=EventPhase::PageReady
   ||event_chain->index!=event_chain->page.event_count)return false;
  release_read_locked(event_chain->read_generation);event_chain.reset();uncharge(chain_charge);chain_charge=0;
  next_event_poll_at=now+std::chrono::milliseconds(event_poll_ms);cv.notify_all();return true;
 }
 void settle_completed_event_chain()
 {std::lock_guard<std::mutex> lock(mutex);settle_completed_event_chain_locked(Clock::now());}
 template<class F> void deliver_event(const QmtEventDeliveryObservation& observation,Clock::time_point until,F&& call)
 {
  if(Clock::now()>=until){fail(failure(ErrorCode::Timeout,"qmt_standard_event_delivery_deadline"));return;}
  auto admitted=event_index->reserve(observation);
  if(!admitted.status.ok()){fail(admitted.status);return;}
  if(admitted.disposition==QmtEventDeliveryDisposition::Duplicate){
   if(Clock::now()>=until)fail(failure(ErrorCode::Timeout,"qmt_standard_event_delivery_deadline"));else advance_event();return;
  }
  if(admitted.disposition!=QmtEventDeliveryDisposition::Deliver){
   fail(failure(ErrorCode::SubmissionUnknown,"qmt_standard_event_delivery_unresolved"));return;
  }
  if(stop_requested||event_detached||!spi||Clock::now()>=until){
   require(event_index->finish(admitted.ticket,QmtEventDeliveryOutcome::Suppressed),"qmt_standard_event_suppression_failed");
   if(!stop_requested&&!event_detached)fail(failure(ErrorCode::Timeout,"qmt_standard_event_delivery_deadline"));return;
  }
  bool started=false,returned=false;
  try {
   callback([&]{
    // callback退当前名额后才进入此lambda；所有可抛构造在start前已经结束。
    if(stop_requested||event_detached||!spi||Clock::now()>=until)return;
    require(event_index->start(admitted.ticket),"qmt_standard_event_delivery_start_failed");started=true;
    struct CallbackScope{bool& active;explicit CallbackScope(bool& value):active(value){active=true;}~CallbackScope(){active=false;}} scope{event_callback_active};
    call();require(event_index->finish(admitted.ticket,QmtEventDeliveryOutcome::Returned),"qmt_standard_event_delivery_finish_failed");returned=true;
   });
  }catch(...){if(started&&!returned)event_index->finish(admitted.ticket,QmtEventDeliveryOutcome::Unknown);throw;}
  if(!started){
   require(event_index->finish(admitted.ticket,QmtEventDeliveryOutcome::Suppressed),"qmt_standard_event_suppression_failed");
   if(!stop_requested&&!event_detached)fail(failure(ErrorCode::Timeout,"qmt_standard_event_delivery_deadline"));return;
  }
  advance_event();
 }
 QmtEventDeliveryObservation event_observation(const QmtAccountIdentityResult& mapped)
 {
  require(mapped.event_provenance&&mapped.batch.array&&mapped.batch.array->size()==1
   &&mapped.batch.canonical_records.size()==1&&mapped.identity_views.size()==1,"qmt_standard_event_mapping_shape");
  QmtEventDeliveryObservation value;const auto& origin=*mapped.event_provenance;
  value.sequence=origin.sequence;value.derived_event_sha256=origin.derived_event_sha256;
  value.is_trade=origin.kind=="deal";value.canonical_key=mapped.batch.canonical_records[0].canonical_key;
  value.derived_facts_sha256=mapped.batch.canonical_records[0].derived_facts_sha256;
  rapidjson::Document view;require(parse_bounded_qmt_json(mapped.identity_views[0],view,identity_budget.max_identity_view_bytes)
   &&view.IsObject(),"qmt_standard_event_identity_view");
  rapidjson::Document signature;signature.SetArray();auto& a=signature.GetAllocator();
  auto append=[&](const std::string& s){signature.PushBack(rapidjson::Value(s.data(),static_cast<rapidjson::SizeType>(s.size()),a),a);};
  for(const auto* field:{"classification","entrust_id","user_tag"}){
   require(view.HasMember(field)&&view[field].IsString(),"qmt_standard_event_identity_field");append(qmt_host_codec::text(view[field]));
  }
  // 身份覆盖已沿原Remark完成lookup；交付签名沿同一来源，OrderRef保持券商诊断语义。
  const auto* name=account_fields::remark;
  require(view.HasMember(name)&&view[name].IsObject()&&view[name].HasMember("value"),"qmt_standard_event_identity_scalar");
  const auto& scalar=view[name]["value"];std::string token;
  if(scalar.IsString()){
   auto current=qmt_host_codec::text(scalar);
   if(valid_qmt_sdk_order_token(current))token=std::move(current);
  }
  append(token);
  if(!value.is_trade){
   auto order=mapped.batch.array->at<wtp::WTSOrderInfo>(0);
   signature.PushBack(order->getVolume(),a);signature.PushBack(order->getPrice(),a);
   signature.PushBack(static_cast<unsigned>(order->getDirection()),a);signature.PushBack(static_cast<unsigned>(order->getOffsetType()),a);
   signature.PushBack(static_cast<unsigned>(order->getBusinessType()),a);append(copied(order->getExchg()));append(copied(order->getCode()));
   signature.PushBack(order->getOrderDate(),a);signature.PushBack(order->getOrderTime(),a);
   signature.PushBack(static_cast<unsigned>(order->getPriceType()),a);signature.PushBack(static_cast<unsigned>(order->getOrderFlag()),a);
   value.order_filled=order->getVolTraded();value.order_terminal=!order->isAlive();
  }
  value.identity_signature=qmt_host_codec::encode(signature);return value;
 }
 // 单条Missing查询在I/O前取得完整来源+B票据预留。预算不足只产生Backpressure，不缩减原query。
 void queue_event_query(unsigned stage,std::string&& row,TaskCredit& credit,std::size_t& control_charge)
 {
  auto& chain=*event_chain;
  std::size_t reserved=0;QmtEventQueryIdentityBudget budget;
  {
   std::lock_guard<std::mutex> lock(mutex);
   if(stop_requested||event_detached||event_control.stop_requested())return;
   if(Clock::now()>=chain.deadline)throw EventOperationFailure(ErrorCode::Timeout);
   const auto extra=event_context_banks.query_extra;
   if(payload_bytes>max_queue_bytes||ordinary_reserve>max_queue_bytes-payload_bytes
    ||extra>max_queue_bytes-payload_bytes-ordinary_reserve)throw EventCapacity{};
   const auto available=max_queue_bytes-payload_bytes-ordinary_reserve-extra;
   budget.identity=identity_budget;budget.match=event_context_banks.match;
   budget.max_work_bytes=(std::min<std::size_t>)(64u*1024u*1024u,available);
   if(budget.max_work_bytes<event_context_banks.minimum_identity_work)throw EventCapacity{};
   reserved=add_size(extra,budget.max_work_bytes);if(!charge(reserved))throw EventCapacity{};
  }
  try {
   Task task;task.kind=Kind::EventQuery;task.stage=stage;task.generation=generation;
   task.id=credit.id;task.event_index=chain.index;task.deadline=chain.deadline;task.charge=512;
   task.read_generation=chain.read_generation;task.event_context=event_context;task.event_bounds=chain.bounds;
   std::lock_guard<std::mutex> lock(mutex);
   require(control_charge==512&&!chain.query_charge,"qmt_standard_event_query_charge");
   if(stop_requested||event_detached||event_control.stop_requested()){
    // task局部独立context先销毁，随后才能退本次新预留。
    task.event_context={};uncharge(reserved);return;
   }
   queue_task(std::move(task));
   chain.query.origin_task_id=credit.id;chain.query.generation=generation;chain.query.event_index=chain.index;
   chain.missing_event_row=std::move(row);chain.query_budget=budget;chain.query_charge=reserved;
   chain.task_id=credit.id;chain.phase=EventPhase::QueryInFlight;control_charge=0;
  }catch(...){finish_charge(reserved);throw;}
  credit.transfer();cv.notify_all();
 }
 void begin_event_query(Completion& value,TaskCredit& credit,std::size_t& control_charge)
 {
  auto& chain=*event_chain;auto& evidence=chain.query;SignedHttpDeadline end(chain.deadline);
  if(!end.remaining()){fail(fixed_failure(ErrorCode::Timeout));return;}
  if(stop_requested||event_detached||event_control.stop_requested()||!spi)return;
  const auto& account=evidence.account;const auto& terminal=account.bound.result;
  if(!terminal.status.ok()||!terminal.terminal||!terminal.remote_ok||terminal.http_status!=200
   ||!same_read(evidence.saved_receipt,account.bound.receipt)){
   fail(fixed_failure(ErrorCode::InvalidInput));return;
  }
  // 完整原结果与原event行交唯一匹配器；各函数的临时对象在进入下一阶段前退出作用域。
  AccountEventMatchResult matched;
  {
   matched=match_account_event_row(value.stage,chain.missing_event_row,account,binding,chain.query_budget.match);
  }
  if(!end.remaining()){fail(fixed_failure(ErrorCode::Timeout));return;}
  if(stop_requested||event_detached||event_control.stop_requested()||!spi)return;
  if(matched.kind!=AccountEventMatchKind::Matched){
   fail(fixed_failure(matched.kind==AccountEventMatchKind::Conflict?ErrorCode::Conflict:ErrorCode::InvalidInput));return;
  }
  auto base=spi->getBaseDataMgr();require(base!=nullptr,"qmt_standard_base_data_missing");
  auto begun=begin_qmt_event_query_identity(chain.page,chain.bounds,chain.index,account,matched.row_index,
   expected,binding,base,chain.query_budget,end);
  if(!begun.status.ok()){fail(begun.status);return;}
  require(begun.candidate&&begun.plan,"qmt_standard_event_query_begin_incomplete");
  if(!end.remaining()){fail(fixed_failure(ErrorCode::Timeout));return;}
  if(stop_requested||event_detached||event_control.stop_requested()||!spi)return;
  Task task;task.kind=Kind::EventResolve;task.stage=value.stage;task.generation=generation;
  task.id=credit.id;task.event_index=chain.index;task.deadline=chain.deadline;task.charge=512;
  task.plan=std::move(begun.plan);task.read_generation=chain.read_generation;task.event_context=event_context;task.event_bounds=chain.bounds;
  {
   std::lock_guard<std::mutex> lock(mutex);require(control_charge==512,"qmt_standard_event_control_accounting");
   if(stop_requested||event_detached||event_control.stop_requested())return;
   queue_task(std::move(task));chain.candidate=std::move(begun.candidate);
   chain.task_id=credit.id;chain.phase=EventPhase::ResolveInFlight;control_charge=0;
  }
  credit.transfer();cv.notify_all();
 }
 void retire_current_event_query()
 {
  // 调用点已经结束mapped/observation/SPI借用。停止路径保留纯来源直到真实join。
  if(!event_chain||stop_requested||event_detached||event_chain->phase!=EventPhase::PageReady)return;
  auto& chain=*event_chain;if(!chain.query_charge)return;
  const auto reserved=chain.query_charge;
  chain.query={};std::string{}.swap(chain.missing_event_row);chain.query_budget={};chain.query_charge=0;
  std::lock_guard<std::mutex> lock(mutex);uncharge(reserved);cv.notify_all();
 }
 void begin_event(TaskCredit& credit,std::size_t& control_charge)
 {
  require(event_chain&&event_chain->index<event_chain->page.event_count,"qmt_standard_event_index_invalid");
  auto& chain=*event_chain;SignedHttpDeadline end(chain.deadline);
  if(!end.remaining()){fail(failure(ErrorCode::Timeout,"qmt_standard_event_chain_deadline"));return;}
  const auto& event=chain.validated.document["events"][static_cast<rapidjson::SizeType>(chain.index)];
  const auto kind=qmt_host_codec::text(event["kind"]);
  if(kind=="error"){
   QmtEventDeliveryObservation observation;observation.sequence=event["sequence"].GetUint64();observation.diagnostic=true;
   observation.derived_event_sha256=signed_http_sha256(qmt_host_codec::encode(event));
   // 普通WT日志/通知只携有限引用；账户及SDK错误正文继续留在Host原通信事实。
   const auto reason=std::string("qmt_source_order_error; sequence=")+std::to_string(observation.sequence)
    +"; derived_event_sha256="+observation.derived_event_sha256;
   Status status{ErrorCode::IoError,reason};note(status);
   std::unique_ptr<wtp::WTSError,ObjectRelease> error(wtp::WTSError::create(wtp::WEC_UNKNOWN,reason.c_str()));
   require(bool(error),"qmt_standard_event_error_allocation");
   deliver_event(observation,chain.deadline,[&]{spi->onTraderError(error.get());});return;
  }
  if(event_control.stop_requested()||stop_requested||event_detached||!spi)return;
  const unsigned stage=kind=="order"?1:2;
  {
   // 唯一mapper解释缺失/null/非法；这里只分流，不拼字段或另造金融规则。
   auto row=event_row_text(event["payload"],event_context_banks.match.max_event_bytes);
   auto inspected=inspect_account_row(stage,row,binding,{event_context_banks.match.max_event_bytes,4096});
   if(!end.remaining()){fail(fixed_failure(ErrorCode::Timeout));return;}
   if(event_control.stop_requested()||stop_requested||event_detached||!spi)return;
   if(inspected.kind==AccountInspectionKind::MissingRequired&&inspected.locator_complete){
    queue_event_query(stage,std::move(row),credit,control_charge);return;
   }
   if(inspected.kind!=AccountInspectionKind::Complete){fail(fixed_failure(ErrorCode::InvalidInput));return;}
  }
  auto base=spi?spi->getBaseDataMgr():nullptr;require(base!=nullptr,"qmt_standard_base_data_missing");
  auto begun=begin_qmt_trade_event_identity(chain.page,chain.bounds,chain.index,expected,binding,
   base,identity_budget,end);
  if(!begun.status.ok()){fail(begun.status);return;}
  require(begun.candidate&&begun.plan,"qmt_standard_event_begin_incomplete");
  Task task;task.kind=Kind::EventResolve;task.stage=kind=="order"?1:2;task.generation=generation;
  task.id=credit.id;task.deadline=chain.deadline;task.event_index=chain.index;task.plan=std::move(begun.plan);task.charge=512;
  task.read_generation=chain.read_generation;task.event_context=event_context;task.event_bounds=chain.bounds;
  {std::lock_guard<std::mutex> lock(mutex);require(control_charge==512,"qmt_standard_event_control_accounting");
   queue_task(std::move(task));control_charge=0;
   chain.candidate=std::move(begun.candidate);chain.task_id=credit.id;chain.phase=EventPhase::ResolveInFlight;}
  credit.transfer();cv.notify_all();
 }
 // owner接收读取终态；等待态没有有效page，不能沿空页结算释放链或刷新D。
 bool settle_event_read(Completion& result)
 {
  require(event_chain&&event_chain->task_id==result.id&&event_chain->phase==EventPhase::ReadInFlight,
   "qmt_standard_event_read_ticket");
  auto& chain=*event_chain;chain.read_generation=result.read_generation;chain.last_read=result.event_failure;
  require(!chain.candidate&&chain.page.page_json.empty()&&chain.index==0,"qmt_standard_event_retry_after_page");
  require(chain.attempts<chain.task_limit||!result.event_read_attempted,"qmt_standard_event_attempt_limit");
  if(result.event_read_attempted)++chain.attempts;
  chain.drain_checks=static_cast<unsigned>(add_size(chain.drain_checks,result.event_drain_checks));
  require(chain.drain_checks<=times_size(chain.task_limit,2),"qmt_standard_event_drain_limit");
  if(result.event_failure.transport.recovery==SignedHttpRecovery::TransportInterrupted)
   chain.last_transport=result.event_failure;
  // owner取完成值也受原D约束；正常detach不能把已过期完成值提前吞掉。
  if(Clock::now()>=chain.deadline)return false;
  if(result.event_failure.outcome==QmtTradeEventReadOutcome::ControlStoppedBeforeStage){
   require(event_control.stop_requested()&&(stop_requested||event_detached),"qmt_standard_event_control_mismatch");
   require(result.event_failure.transport.recovery==SignedHttpRecovery::None&&result.event_page.page_json.empty(),
    "qmt_standard_event_control_shape");
   // 正常detach保持普通账户任务可用；原链借用直到实际join才统一归还。
   chain.phase=EventPhase::ReadRetryWait;return true;
  }
  if(result.event_drain_failed)return false;
  if(result.event_drain_pending||result.event_drain_checked||event_transport_retry(result)){
   if(event_control.stop_requested())return false; // 已发生真实Failure不能被并发detach吞掉。
   require(result.event_page.page_json.empty()&&!result.resolved,"qmt_standard_event_retry_payload");
   std::lock_guard<std::mutex> lock(mutex);chain.phase=EventPhase::ReadRetryWait;
   chain.drain_pending=result.event_drain_pending;chain.next_attempt_at=Clock::now()+std::chrono::milliseconds(event_poll_ms);
   cv.notify_all();return true;
  }
  return false;
 }
 void accept_event_page(Completion& result,TaskCredit& credit,std::size_t& control_charge)
 {
  require(event_chain&&event_chain->task_id==result.id,"qmt_standard_event_page_ticket");
  auto& chain=*event_chain;SignedHttpDeadline end(chain.deadline);
  auto& page=result.event_page;
  const auto& fresh=result.event_context;
  require(fresh.source.session_id==event_context.source.session_id
   &&fresh.read_profile_body==event_context.read_profile_body
   &&fresh.read_result_capacity==event_context.read_result_capacity
   &&fresh.admitted_event_page_capacity==event_context.admitted_event_page_capacity,"qmt_standard_read_source_changed");
  // 该页尚未交付；认证逻辑session与资源合同保持，原index/cursor继续保留。
  event_context=std::move(result.event_context);
  require(same_event_source(page.source,event_context.source)&&page.read_profile_body==event_context.read_profile_body
   &&page.read_result_capacity==event_context.read_result_capacity,"qmt_standard_event_page_source");
  auto status=validate_qmt_trade_event_page(page.page_json,page.source,chain.bounds,expected,event_context.admitted_limits,
   page.admitted_event_page_capacity,end,chain.validated);
  if(!status.ok()){fail(status);return;}
  require(page.event_count==chain.validated.event_count&&page.next_sequence==chain.validated.next_sequence
   &&page.gap==chain.validated.gap,"qmt_standard_event_page_shape");
  {std::lock_guard<std::mutex> lock(mutex);chain.page=std::move(page);read_cursor=chain.page.next_sequence;chain.phase=EventPhase::PageReady;
   if(chain.page.gap)block(failure(ErrorCode::Unavailable,"qmt_standard_event_source_gap"));}
  // PageReady续段统一由schedule_events在取得SPI查询预留后开始。
 }
 void finish_event(Completion& result)
 {
  require(event_chain&&event_chain->task_id==result.id&&event_chain->candidate,"qmt_standard_event_resolve_ticket");
  if(!result.resolved){fail(result.status.ok()?failure(ErrorCode::IoError,"qmt_standard_event_resolution_missing"):result.status);return;}
  auto mapped=finish_qmt_account_identity(event_chain->candidate,result.resolved);
  if(!mapped.status.ok()){fail(mapped.status);return;}
  auto observation=event_observation(mapped);remember(mapped.batch,result.stage);
  const auto until=event_chain->deadline;
  deliver_event(observation,until,[&]{
   if(observation.is_trade)spi->onPushTrade(mapped.batch.array->at<wtp::WTSTradeInfo>(0));
   else spi->onPushOrder(mapped.batch.array->at<wtp::WTSOrderInfo>(0));
  });
 }
 // 首次截止前冻结纯POD旁证；捕获失败不覆盖原错误、不改变停止/原D。
 void capture_event_chain_deadline()
 {
  try{
   std::lock_guard<std::mutex> lock(mutex);
   if(event_chain&&!event_deadline.captured){
    const auto now=Clock::now();const auto& chain=*event_chain;auto& d=event_deadline;
    d.phase=static_cast<unsigned>(chain.phase)+1;d.queued=static_cast<unsigned>(tasks.size());
    d.ready=static_cast<unsigned>(results.size());d.outstanding=outstanding;d.callback_reserved=event_callback_reserved;
    d.callback_space=event_callback_space();d.attempts=chain.attempts;d.drain_checks=chain.drain_checks;d.drain_pending=chain.drain_pending;
    d.read_cursor=read_cursor;d.handled_cursor=handled_cursor;d.after_sequence=chain.bounds.after_seq;
    d.page_index=chain.index;d.page_count=chain.page.event_count;d.task_id=chain.task_id;
    d.elapsed_ms=std::chrono::duration_cast<std::chrono::milliseconds>(now-chain.started).count();
    d.remaining_ms=std::chrono::duration_cast<std::chrono::milliseconds>(chain.deadline-now).count();
    d.last_event_queue_wait_ms=chain.last_queue_wait_ms;d.last_event_running_ms=chain.last_running_ms;
    d.worker_busy=diagnostic_worker_busy;
    if(diagnostic_worker_busy){d.worker_kind=static_cast<unsigned>(diagnostic_worker_kind)+1;
     d.worker_stage=diagnostic_worker_stage;d.worker_task_id=diagnostic_worker_task;
     d.worker_queue_wait_ms=diagnostic_worker_wait_ms;
     d.worker_running_ms=std::chrono::duration_cast<std::chrono::milliseconds>(now-diagnostic_worker_started).count();}
    d.read_outcome=static_cast<unsigned>(chain.last_read.outcome);d.read_stage=static_cast<unsigned>(chain.last_read.stage);
    const bool prior=chain.last_transport.transport.recovery==SignedHttpRecovery::TransportInterrupted;
    const auto& read=prior?chain.last_transport:chain.last_read;const auto& transport=read.transport;
    d.transport_from_prior_retry=prior;d.transport_recovery=static_cast<unsigned>(transport.recovery);
    d.transport_origin=static_cast<unsigned>(transport.origin);d.transport_stage=static_cast<unsigned>(transport.stage);
    d.native_error=transport.native_error;d.transport_operation=transport.native_operation;
    d.http_status=read.http_status;d.send_attempted=read.send_attempted;d.response_complete=read.response_complete;d.captured=1;
   }
  }catch(...){/* 旁证不改变原错误及清理。 */}
 }
 // owner的原D维护独立于本次pump完成数量。这里只处理已交回owner的等待/页状态；
 // 在途任务仍由原完成值保留真实Failure、delivery_fault与通信责任。
 void maintain_event_deadline()
 {
  bool expired=false;
  {
   std::lock_guard<std::mutex> lock(mutex);if(!event_lifecycle())return;
   const auto now=Clock::now();
   // 最后一项的借用已退出后，先按原终态结算；不能把已完成链重新判成超时。
   if(settle_completed_event_chain_locked(now)||!event_chain)return;
   const auto phase=event_chain->phase;
   expired=(phase==EventPhase::ReadRetryWait||phase==EventPhase::PageReady)&&now>=event_chain->deadline;
  }
  if(expired)fail(failure(ErrorCode::Timeout,"qmt_standard_event_chain_deadline"));
 }
 void schedule_events()
 {
  std::uint64_t continuation=0;bool expired=false;
  {
   std::lock_guard<std::mutex> lock(mutex);const auto now=Clock::now();if(!event_ready(now))return;
   if(event_chain){
    if(settle_completed_event_chain_locked(now))return;
    if(now>=event_chain->deadline)expired=true;
    else if(event_chain->phase==EventPhase::ReadRetryWait){
     auto& chain=*event_chain;require(chain.read_tasks<chain.task_limit,"qmt_standard_event_retry_task_limit");
     require(charge(512),"qmt_standard_event_retry_capacity");
     try {
      Task task;task.kind=Kind::EventPage;task.id=next_task+1;task.generation=generation;task.deadline=chain.deadline;
      task.read_generation=chain.read_generation;task.event_context=event_context;task.event_bounds=chain.bounds;task.event_failure=chain.last_transport;
      task.event_drain_only=chain.drain_pending;task.charge=512;
      queue_task(std::move(task));++next_task;++outstanding;++chain.read_tasks;
      chain.task_id=next_task;chain.phase=EventPhase::ReadInFlight;
     }catch(...){uncharge(512);throw;}
     cv.notify_all();return;
    }else {
     require(event_chain->phase==EventPhase::PageReady,"qmt_standard_event_continuation_phase");
     reserve_event_callback_locked();
     require(charge(512),"qmt_standard_event_continuation_capacity");continuation=++next_task;++outstanding;event_chain->phase=EventPhase::ResolveInFlight;
    }
   }else {
    const auto reserve=add_size(chain_reserve,512);require(charge(reserve),"qmt_standard_event_page_capacity");
    try {
     std::unique_ptr<EventChain> chain(new EventChain);chain->started=now;chain->deadline=now+std::chrono::milliseconds(request_ms);
     chain->task_limit=static_cast<unsigned>(add_size(1,add_size(request_ms,event_poll_ms-1)/event_poll_ms));
     chain->bounds={read_cursor,static_cast<std::size_t>(event_context.admitted_limits.max_events),event_context.admitted_event_page_capacity};
     Task task;task.kind=Kind::EventPage;task.id=++next_task;task.generation=generation;task.deadline=chain->deadline;
     task.event_context=event_context;task.event_bounds=chain->bounds;task.charge=512;chain->task_id=task.id;
     queue_task(std::move(task));event_chain=std::move(chain);chain_charge=chain_reserve;++outstanding;
    }catch(...){uncharge(reserve);throw;}
    cv.notify_all();return;
   }
  }
  if(expired){fail(failure(ErrorCode::Timeout,"qmt_standard_event_chain_deadline"));return;}
  TaskCredit credit{*this,continuation};
  struct Control {Impl& x;TaskCredit* previous;std::size_t charge=512;
   ~Control(){x.callback_credit=previous;x.finish_charge(charge);}} control{*this,callback_credit};
  callback_credit=&credit;begin_event(credit,control.charge);
  settle_completed_event_chain();
 }
 void finish_task()
 {std::lock_guard<std::mutex> lock(mutex);require(outstanding>0,"qmt_standard_task_accounting");--outstanding;cv.notify_all();}

};

StandardQmtTrader::StandardQmtTrader():impl_(new Impl)
{
 require(impl_->generation!=0,"qmt_standard_generation_exhausted");
 std::lock_guard<std::mutex> lock(registry_mutex);objects.emplace(this,this);
}
StandardQmtTrader::~StandardQmtTrader()
{std::lock_guard<std::mutex> lock(registry_mutex);objects.erase(this);}
bool StandardQmtTrader::owner()const noexcept{return impl_->owner();}
bool StandardQmtTrader::deletable()const noexcept
{return owner()&&impl_->phase==StandardQmtPhase::Closed&&!impl_->pumping&&!impl_->in_callback
 &&impl_->joined&&impl_->drained&&impl_->worker_done&&impl_->active_ingress==0&&!impl_->submission.open&&!impl_->worker.joinable();}
const std::string& StandardQmtTrader::id()const noexcept{return impl_->instance_id;}
StandardQmtTrader* StandardQmtTrader::lookup(wtp::ITraderApi* api)
{std::lock_guard<std::mutex> lock(registry_mutex);auto found=objects.find(api);return found==objects.end()?nullptr:found->second;}
StandardQmtTrader* StandardQmtTrader::find(const char* id)
{if(!id)return nullptr;std::lock_guard<std::mutex> lock(registry_mutex);auto found=instances.find(id);
 return found!=instances.end()&&found->second->owner()?found->second:nullptr;}

int StandardQmtTrader::inspect_submission(const SubmissionKeyV1& key,SubmissionViewV1& out)const
{
 if(out.version!=1||out.size!=sizeof(out)||!Impl::submission_key(key))return static_cast<int>(SubmissionDecision::Invalid);
 auto& x=*impl_;if(!owner()){out.decision=SubmissionDecision::WrongOwner;return static_cast<int>(out.decision);}
 std::lock_guard<std::mutex> lock(x.mutex);x.submission_view(key,out);
 out.decision=!x.query_first?SubmissionDecision::ModeMismatch:x.stop_requested?SubmissionDecision::Stopped
  :x.hard_fault?SubmissionDecision::Fault:x.submission.open?SubmissionDecision::BlockedBusy
  :(x.unknown_fenced||x.writes_blocked||x.inserts_paused||out.unresolved_children)?SubmissionDecision::BlockedAwait:SubmissionDecision::Admitted;
 return static_cast<int>(out.decision);
}
int StandardQmtTrader::begin_submission(const SubmissionKeyV1& key,SubmissionTokenV1& token,SubmissionViewV1& out)
{
 if(token.version!=1||token.size!=sizeof(token)||token.generation||token.group_id
    ||out.version!=1||out.size!=sizeof(out)||!Impl::submission_key(key))return static_cast<int>(SubmissionDecision::Invalid);
 auto& x=*impl_;if(!owner()){out.decision=SubmissionDecision::WrongOwner;return static_cast<int>(out.decision);}
 std::lock_guard<std::mutex> lock(x.mutex);x.submission_view(key,out);
 auto decision=SubmissionDecision::Admitted;
 if(!x.query_first)decision=SubmissionDecision::ModeMismatch;
 else if(!x.active()||!x.logged_in||!x.expected.writes_enabled||x.submissions_closed)decision=SubmissionDecision::Stopped;
 else if(x.hard_fault)decision=SubmissionDecision::Fault;
 else if(x.submission.open||x.pumping||x.in_callback)decision=SubmissionDecision::BlockedBusy;
 else if(x.unknown_fenced||x.writes_blocked||x.inserts_paused||out.unresolved_children)decision=SubmissionDecision::BlockedAwait;
 else if(x.next_group==(std::numeric_limits<std::uint64_t>::max)()
   ||x.identities.size()>=static_cast<std::size_t>(x.binding.row_limit)+x.max_pending||x.outstanding>=x.max_queue)
  decision=SubmissionDecision::Capacity;
 if(decision==SubmissionDecision::Admitted){
  x.submission={};x.submission.key=key;x.submission.id=++x.next_group;x.submission.open=true;
  ++x.active_ingress;token.generation=x.generation;token.group_id=x.submission.id;out.group_id=token.group_id;
 }
 out.decision=decision;return static_cast<int>(decision);
}
int StandardQmtTrader::end_submission(const SubmissionTokenV1& token,SubmissionOutcome outcome,SubmissionViewV1& out)
{
 if(out.version!=1||out.size!=sizeof(out))return static_cast<int>(SubmissionDecision::Invalid);
 auto& x=*impl_;if(!owner()){out.decision=SubmissionDecision::WrongOwner;return static_cast<int>(out.decision);}
 std::lock_guard<std::mutex> lock(x.mutex);
 if(!x.query_first){out.decision=SubmissionDecision::ModeMismatch;return static_cast<int>(out.decision);}
 if(token.version!=1||token.size!=sizeof(token)||token.generation!=x.generation||!token.group_id
    ||!x.submission.open||token.group_id!=x.submission.id
    ||(outcome!=SubmissionOutcome::Returned&&outcome!=SubmissionOutcome::Threw)){
  x.submission_fault();out.decision=SubmissionDecision::Fault;return static_cast<int>(out.decision);
 }
 x.submission_view(x.submission.key,out);
 const bool failed=x.hard_fault||x.submission.failed||outcome==SubmissionOutcome::Threw;
 x.submission.open=false;--x.active_ingress;
 if(failed)x.submission_fault();
 out.decision=failed?SubmissionDecision::Fault:x.stop_requested?SubmissionDecision::Stopped:SubmissionDecision::Admitted;
 x.cv.notify_all();return static_cast<int>(out.decision);
}

bool StandardQmtTrader::init(wtp::WTSVariant* cfg)
{
 auto& x=*impl_;if(!owner()||x.phase!=StandardQmtPhase::Created)return false;
 // 仅识别原成对事件字段的存在以选择异常文本边界；合法值仍按原顺序准入。
 const bool bounded_errors=cfg&&(cfg->get("max_event_delivery_records")||cfg->get("max_event_delivery_bytes"));
 std::size_t initialization_charge=0;
 try {
  if(bounded_errors){
   // 先借用数值上限并占有初始化银行，再复制任何配置/env正文；小预算也不能先造大文本。
   const auto capacity=cfg->get("max_queue_bytes");
   if(!integer_type(capacity))throw EventOperationFailure(ErrorCode::InvalidInput);
   const auto n=capacity->asUInt64();
   if(n<1024||n>512ULL*1024*1024)throw EventOperationFailure(ErrorCode::InvalidInput);
   x.max_queue_bytes=static_cast<std::size_t>(n);
   standard_event_budget::detail::Arithmetic arithmetic;standard_event_budget::Layout layout;layout.impl=sizeof(Impl);
   initialization_charge=standard_event_budget::detail::initialization_rejection_bound(arithmetic,layout);
   if(!arithmetic.ok||!x.charge(initialization_charge))throw EventCapacity{};
  }
  require(cfg!=nullptr,"qmt_standard_config_missing");
  if(cfg->get("order_context")){
   const auto mode=config_text(cfg,"order_context",11,true);
   require(mode=="native"||mode=="query_first","qmt_standard_order_context_invalid");x.query_first=mode=="query_first";
  }
  x.close_ms=static_cast<unsigned>(config_number(cfg,"close_ms",1,120000));
  x.instance_id=config_text(cfg,"instance_id",48,bounded_errors);
  require(x.instance_id.find_first_not_of("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-")==std::string::npos,"qmt_standard_instance_invalid");
  x.request_ms=static_cast<unsigned>(config_number(cfg,"request_ms",1,300000));
  if(cfg->get("observation_refresh_ms"))
   x.observation_refresh_ms=static_cast<unsigned>(config_number(cfg,"observation_refresh_ms",1000,60000));
  x.max_queue=static_cast<unsigned>(config_number(cfg,"max_queue",1,1024));
  if(!bounded_errors)x.max_queue_bytes=static_cast<std::size_t>(config_number(cfg,"max_queue_bytes",1024,512ULL*1024*1024));
  x.max_pending=static_cast<unsigned>(config_number(cfg,"max_pending_commands",1,4096));
  x.binding={config_text(cfg,"expected_account",63,bounded_errors),config_text(cfg,"environment",10,bounded_errors),
   config_text(cfg,"currency",3,bounded_errors),config_text(cfg,"profile",64,bounded_errors),static_cast<unsigned>(config_number(cfg,"max_rows",1,4096))};
  require(x.binding.environment=="live"&&x.binding.currency=="CNY"&&x.binding.profile=="cny_cash_shsz_v1","qmt_standard_binding_invalid");
  x.trading_date=static_cast<unsigned>(config_number(cfg,"trading_date",10101,99991231));
  require(valid_day(x.trading_date),"qmt_standard_trading_date_invalid");
  x.expected.account={x.binding.account,QmtAccountEnvironment::Live};
  x.expected.binding_id=config_text(cfg,"binding_id",128,bounded_errors);x.expected.binding_sha256=config_text(cfg,"binding_sha256",64,bounded_errors);
  x.expected.writes_enabled=config_bool(cfg,"writes_enabled");
  x.http.base_url=config_text(cfg,"base_url",2048,bounded_errors);x.http.timeout_ms=static_cast<unsigned>(config_number(cfg,"timeout_ms",1,30000));
  x.http.max_response_bytes=static_cast<std::size_t>(config_number(cfg,"max_response_bytes",8192,16ULL*1024*1024));
  const auto key_name=config_text(cfg,"key_id_env",128,bounded_errors),secret_name=config_text(cfg,"hmac_secret_env",128,bounded_errors);
  const char* key=std::getenv(key_name.c_str());const char* secret=std::getenv(secret_name.c_str());
  require(key&&*key&&secret&&*secret,"qmt_standard_credentials_unavailable");
  x.http.key_id=copied(key,128);x.http.hmac_secret=copied(secret,4096);
  x.identity_budget.max_lookup_bytes=static_cast<std::size_t>(config_number(cfg,"max_lookup_bytes",1,64ULL*1024*1024));
  x.identity_budget.max_identity_view_bytes=static_cast<std::size_t>(config_number(cfg,"max_identity_view_bytes",1,64ULL*1024*1024));
  x.identity_budget.max_total_bytes=static_cast<std::size_t>(config_number(cfg,"max_total_bytes",1,64ULL*1024*1024));
  require(x.identity_budget.max_lookup_bytes<=x.identity_budget.max_total_bytes
   &&x.identity_budget.max_identity_view_bytes<=x.identity_budget.max_total_bytes,"qmt_standard_identity_budget_invalid");
  const bool records=cfg->get("max_event_delivery_records")!=nullptr,delivery_bytes=cfg->get("max_event_delivery_bytes")!=nullptr;
  require(records==delivery_bytes,"qmt_standard_event_resources_incomplete");x.events_enabled=records;
  require(!x.observation_refresh_ms||(x.query_first&&x.events_enabled),"qmt_standard_observation_refresh_mode");
  if(x.query_first&&!x.events_enabled)require(x.charge(Impl::submission_fixed_bytes),"qmt_standard_submission_capacity");
  if(x.events_enabled){
   x.event_records=static_cast<std::size_t>(config_number(cfg,"max_event_delivery_records",1,1000000));
   x.event_partition=static_cast<std::size_t>(config_number(cfg,"max_event_delivery_bytes",1,x.max_queue_bytes));
   if(cfg->get("event_poll_ms"))x.event_poll_ms=static_cast<unsigned>(config_number(cfg,"event_poll_ms",1,60000));
   std::size_t configuration=0;for(const auto* text:{&x.instance_id,&x.binding.account,&x.binding.environment,
    &x.binding.currency,&x.binding.profile,&x.expected.account.account_id,&x.expected.binding_id,&x.expected.binding_sha256,
    &x.http.base_url,&x.http.key_id,&x.http.hmac_secret})configuration=add_size(configuration,add_size(text->size(),1));
   x.event_budget_input={x.http.max_response_bytes,x.max_queue,x.max_pending,x.binding.row_limit,
    x.identity_budget.max_total_bytes,x.identity_budget.max_lookup_bytes,x.identity_budget.max_identity_view_bytes,x.event_partition,configuration};
   x.event_layout={sizeof(Impl),sizeof(Impl::Task),sizeof(Impl::Completion),sizeof(Impl::EventChain),sizeof(Impl::QueryEvidence),
    sizeof(decltype(x.identities)::value_type),sizeof(decltype(x.pending)::value_type),sizeof(decltype(x.candidates)::value_type),
     sizeof(wtp::WTSEntrust)+sizeof(wtp::WTSError)+sizeof(OrderValue)+128+141+3*64};
   if(!standard_event_budget::instance(x.event_budget_input,x.event_layout,x.event_banks).ok())throw EventCapacity{};
   // 初始化银行始终由同一owner持有；完整static只补差额，无先退费的未计费窗口。
   if(x.payload_bytes!=initialization_charge||x.event_banks.total_static<initialization_charge
    ||!x.charge(x.event_banks.total_static-initialization_charge))throw EventCapacity{};
   x.context_reserve=sizeof(QmtTradeEventReadContext)+4097+129+4097+65;
   x.ordinary_reserve=x.event_banks.ordinary_advance;
   require(!x.query_first||x.max_queue>x.event_callback_slots(),"qmt_standard_callback_queue_configuration");
   if(x.query_first)require(add_size(x.persistent_event_bytes(),
    add_size(x.context_reserve,add_size(times_size(x.event_callback_slots()+1,x.ordinary_reserve),1024)))<=x.max_queue_bytes,
    "qmt_standard_callback_static_configuration");
   require(add_size(add_size(x.event_partition,x.context_reserve),add_size(x.ordinary_reserve,1024))<=x.max_queue_bytes,
    "qmt_standard_event_static_capacity");
   require(x.charge(x.event_partition),"qmt_standard_event_partition_capacity");
  }
  require(x.charge(Impl::audit_source_bytes),"qmt_standard_audit_source_capacity"); // 全实例G预留先于worker来源复制。
  auto uuid=signed_http_uuid();require(!uuid.empty(),"qmt_standard_entrust_identity_unavailable");
  uuid.erase(std::remove(uuid.begin(),uuid.end(),'-'),uuid.end());x.entrust_prefix="qmt."+uuid+".";
  {std::lock_guard<std::mutex> lock(registry_mutex);require(instances.emplace(x.instance_id,this).second,"qmt_standard_instance_exists");}
  x.results.initialize(x.max_queue); // 在创建worker及任何HTTP前完成全部槽分配。
  x.initialized=true;x.phase=StandardQmtPhase::Initialized;x.worker=std::thread([&x]{x.work();});return true;
 }catch(const EventCapacity&){if(x.first_error.ok())x.first_error.code=ErrorCode::Backpressure;
  x.writes_blocked=true;x.initialized=false;x.phase=StandardQmtPhase::Failed;x.unregister_instance();return false;}
 catch(const std::bad_alloc& e){
  if(bounded_errors){if(x.first_error.ok())x.first_error.code=ErrorCode::IoError;}
  else x.note(failure(ErrorCode::InvalidInput,e.what()));
  x.writes_blocked=true;x.initialized=false;x.phase=StandardQmtPhase::Failed;x.unregister_instance();return false;}
 catch(const std::exception& e){
  if(bounded_errors){if(x.first_error.ok())x.first_error.code=ErrorCode::InvalidInput;}else x.note(failure(ErrorCode::InvalidInput,e.what()));x.writes_blocked=true;
  x.initialized=false;x.phase=StandardQmtPhase::Failed;x.unregister_instance();return false;}
 catch(...){if(bounded_errors){if(x.first_error.ok())x.first_error.code=ErrorCode::IoError;}
  else x.note(failure(ErrorCode::IoError,"qmt_standard_initialization_failed"));x.initialized=false;x.phase=StandardQmtPhase::Failed;x.unregister_instance();return false;}
}
void StandardQmtTrader::registerSpi(wtp::ITraderSpi* value)
{
 if(!owner())return;auto& x=*impl_;
 // 同owner回调内detach即时关闭后继SPI；当前借用对象仍由该回调栈持有。
 if(value&&(x.in_callback||x.stop_requested||x.phase!=StandardQmtPhase::Initialized))return;
 {std::lock_guard<std::mutex> lock(x.mutex);x.spi=value;if(!value){x.audit_detached=true;if(x.events_enabled)x.event_detached=true;x.event_control.request_stop();}}x.cv.notify_all();
}
void StandardQmtTrader::connect()
{
 if(!owner())return;auto& x=*impl_;if(x.phase!=StandardQmtPhase::Initialized||!x.spi)return;
 Impl::Task task;task.kind=Impl::Kind::Prepare;task.deadline=x.deadline();
 try{if(x.enqueue(std::move(task))==0)x.phase=StandardQmtPhase::Connecting;else x.owner_error=x.events_enabled?fixed_failure(ErrorCode::Backpressure):failure(ErrorCode::Backpressure,"qmt_standard_connect_capacity");}
 catch(...){x.owner_error=x.events_enabled?fixed_failure(ErrorCode::IoError):failure(ErrorCode::IoError,"qmt_standard_connect_failed");}
}
bool StandardQmtTrader::isConnected(){return impl_->connected&&!impl_->stop_requested;}
int StandardQmtTrader::login(const char*,const char*,const char*)
{
 auto& x=*impl_;if(!owner())return StandardQmtWrongOwner;
 if(x.phase!=StandardQmtPhase::Connected||!x.connected||x.stop_requested)return StandardQmtUnavailable;
 try{Impl::Task task;task.kind=Impl::Kind::Login;task.deadline=x.deadline();auto result=x.enqueue(std::move(task));
  if(!result)x.phase=StandardQmtPhase::LoggingIn;return result;}
 catch(...){return StandardQmtFailure;}
}
int StandardQmtTrader::logout(){return stop();}
void StandardQmtTrader::disconnect(){stop();}
bool StandardQmtTrader::makeEntrustID(char* buffer,int length)
{
 auto& x=*impl_;Impl::Ingress ingress(x);if(!ingress.entered||!buffer||length<=0)return false;
 auto sequence=x.entrust_sequence.load();
 do{if(sequence==(std::numeric_limits<std::uint64_t>::max)())return false;}
 while(!x.entrust_sequence.compare_exchange_weak(sequence,sequence+1));
 const auto value=x.entrust_prefix+std::to_string(sequence+1);
 if(value.size()>63||value.size()+1>static_cast<std::size_t>(length))return false;
 std::memcpy(buffer,value.c_str(),value.size()+1);return true;
}
#define GH_STANDARD_QUERY(method,datatype) \
int StandardQmtTrader::method(){auto& x=*impl_;Impl::Ingress ingress(x);if(!ingress.entered||!x.logged_in)return StandardQmtUnavailable; \
 try{Impl::Task task;task.kind=Impl::Kind::Query;task.stage=datatype;task.deadline=x.deadline(); \
 return x.enqueue(std::move(task));}catch(...){return StandardQmtFailure;}}
GH_STANDARD_QUERY(queryPositions,0)
GH_STANDARD_QUERY(queryOrders,1)
GH_STANDARD_QUERY(queryTrades,2)
GH_STANDARD_QUERY(queryAccount,3)
#undef GH_STANDARD_QUERY
int StandardQmtTrader::orderInsert(wtp::WTSEntrust* value)
{
 auto& x=*impl_;Impl::Ingress ingress(x);if(!ingress.entered||!value||!x.logged_in||x.writes_blocked||!x.expected.writes_enabled)return StandardQmtUnavailable;
 if(x.query_first){std::lock_guard<std::mutex> lock(x.mutex);if(!owner()||!x.submission.open||x.in_callback||x.pumping)return StandardQmtUnavailable;}
 try {
  Impl::Task task;task.kind=Impl::Kind::Insert;task.deadline=x.deadline();task.order=copy_order(*value);task.charge=task.order.payload();
  const auto rc=x.enqueue(std::move(task),true);
  if(rc<0&&x.query_first){std::lock_guard<std::mutex> lock(x.mutex);if(x.submission.open)x.submission.failed=true;}
  return rc;
 }catch(...){x.hard_fault=true;x.writes_blocked=true;std::lock_guard<std::mutex> lock(x.mutex);if(x.ingress_error.ok())x.ingress_error=x.events_enabled?fixed_failure(ErrorCode::InvalidInput):failure(ErrorCode::InvalidInput,"qmt_standard_write_ingress_invalid");x.cv.notify_all();return StandardQmtInvalid;}
}
int StandardQmtTrader::orderAction(wtp::WTSEntrustAction* value)
{
 auto& x=*impl_;Impl::Ingress ingress(x);if(!ingress.entered||!value||!x.logged_in||!x.permits(Impl::Kind::Cancel)||!x.expected.writes_enabled)return StandardQmtUnavailable;
 try {
  require(value->getActionFlag()==wtp::WAF_CANCEL&&value->getBusinessType()==wtp::BT_CASH,"qmt_standard_action_unsupported");
  Impl::Task task;task.kind=Impl::Kind::Cancel;task.deadline=x.deadline();
  auto& order=task.order;order.insert.entrust_id=copied(value->getEntrustID());
  order.insert.exchange=copied(value->getExchg());order.insert.code=copied(value->getCode());order.broker=copied(value->getOrderID());
  require(!order.insert.entrust_id.empty()&&!order.broker.empty(),"qmt_standard_cancel_identity_missing");
  {std::lock_guard<std::mutex> lock(x.mutex);auto found=x.identities.find(order.insert.entrust_id);
   require(found!=x.identities.end()&&found->second.code==order.insert.code&&found->second.exchange==order.insert.exchange
    &&(found->second.broker.empty()||found->second.broker==order.broker),"qmt_standard_cancel_identity_unknown");
   order.insert.user_tag=found->second.tag;}
  task.charge=task.order.payload();return x.enqueue(std::move(task),true);
 }catch(...){x.hard_fault=true;x.writes_blocked=true;return StandardQmtInvalid;}
}
int StandardQmtTrader::pump(std::uint32_t limit)
{
 if(!owner())return StandardQmtWrongOwner;auto& x=*impl_;
 if(x.pumping||x.in_callback)return StandardQmtReentrant;
 if(!limit||limit>64)return StandardQmtInvalid;
 if(x.phase==StandardQmtPhase::Closed)return StandardQmtClosed;
 struct Guard{bool& flag;explicit Guard(bool& value):flag(value){flag=true;}~Guard(){flag=false;}}guard{x.pumping};
 unsigned delivered=0;
 try {
  if(!x.owner_error.ok()){
    // 一次性错误的原code已由生产者确定；事件域只move，诊断分配不得抢先变成IoError。
    Status error;if(x.events_enabled)error=std::move(x.owner_error);else error=x.owner_error;
    x.owner_error={};x.fail(error);return StandardQmtFailure;
   }
  Status ingress;
  {std::lock_guard<std::mutex> lock(x.mutex);
    if(x.events_enabled)ingress=std::move(x.ingress_error);else ingress=x.ingress_error;
    x.ingress_error={};}
  if(!ingress.ok())x.trader_error(ingress);
  if(x.stop_requested){x.retire_candidates();x.retain_stopped_results();return 0;}
  while(delivered<limit&&!x.stop_requested){
   Impl::Completion result;
   bool mismatch=false;if(!x.pop_completion(result,mismatch)){if(mismatch)x.fail(fixed_failure(ErrorCode::Conflict));break;}
   Impl::TaskCredit credit{x,result.id};
   struct Charge {
    Impl& x;std::size_t n;Impl::TaskCredit* previous;Impl::Completion& value;
    ~Charge(){
     // 读结果/Resolved纯值先析构再归还预留，成功抑制也保持完整的寿命计费。
     x.callback_credit=previous;x.retire_completion(value,n);
    }
   }charge{x,result.charge,x.callback_credit,result};
   x.callback_credit=&credit;
   ++delivered;
   if(x.event_chain&&x.event_chain->task_id==result.id
    &&(result.kind==Impl::Kind::EventPage||result.kind==Impl::Kind::EventQuery||result.kind==Impl::Kind::EventResolve)){
    x.event_chain->last_queue_wait_ms=result.queue_wait_ms;x.event_chain->last_running_ms=result.running_ms;
   }
   const bool write=result.kind==Impl::Kind::Insert||result.kind==Impl::Kind::Cancel;
   if(x.wait_read(result,credit,charge.n))continue;
   if(result.kind==Impl::Kind::EventQuery||result.kind==Impl::Kind::EventResolve){
    if(!x.receive_event_operation(result,false)){if(x.event_chain)x.event_chain->candidate.reset();continue;}
    if(result.kind==Impl::Kind::EventQuery)x.begin_event_query(result,credit,charge.n);
    else {x.finish_event(result);x.retire_current_event_query();}
    x.settle_completed_event_chain();continue;
   }
   // 新read/U责任先落原ticket；晚D/解绑只抑制业务交付，不能清掉通信身份。
   if(result.kind==Impl::Kind::AuditOriginal){x.settle_audit(result,charge.n);if(result.delivery_fault)x.fail(failure(ErrorCode::IoError,"qmt_standard_completion_delivery_failed"));continue;}
   if(write)x.settle_write(result,charge.n);
   if(result.delivery_fault){x.fail(failure(ErrorCode::IoError,"qmt_standard_completion_delivery_failed"));break;}
   if(write&&!result.command_id.empty())x.last_command=result.command_id;
   if(write&&!result.trade.receipt.command_body.empty()){
    rapidjson::Document command;if(parse_bounded_qmt_json(result.trade.receipt.command_body,command,65536,65536)
     &&command.IsObject()&&command.HasMember("command_id"))x.last_command=qmt_host_codec::text(command["command_id"]);
   }
   if(result.generation!=x.generation){x.fail(failure(ErrorCode::Conflict,"qmt_standard_completion_generation"));break;}
   if(result.kind==Impl::Kind::EventPage&&x.settle_event_read(result))continue;
   if(Clock::now()>=result.deadline){
    const auto error=failure(write&&!result.insert_failure_confirmed?ErrorCode::SubmissionUnknown:ErrorCode::Timeout,"qmt_standard_completion_deadline");
    if(write){
     // 两个失败出口共用分类与SPI交付；晚pump也只通知原委托一次，不给SDK第二次机会。
     x.publish_write_failure(result,error,true);
     continue;
    }
    x.fail(error);break;
   }
   if(!result.status.ok()&&result.kind!=Impl::Kind::Resolve&&result.kind!=Impl::Kind::EventResolve){
    if(write){
     x.publish_write_failure(result,result.status,false);
     continue;
    }
    x.block(result.status);
    if(result.kind==Impl::Kind::Login)x.callback([&]{x.spi->onLoginResult(false,result.status.reason.c_str(),x.trading_date);});
    x.fail(result.status);break;
   }
   if(x.events_enabled&&(result.kind==Impl::Kind::Prepare||result.kind==Impl::Kind::Login))
    x.install_event_context(std::move(result.event_context),charge.n,result.event_bootstrap_ready,result.event_bootstrap_cursor);
   if(result.kind==Impl::Kind::Prepare){
    x.connected=true;x.phase=StandardQmtPhase::Connected;
    x.callback([&]{x.spi->handleEvent(wtp::WTE_Connect,0);});
   }else if(result.kind==Impl::Kind::Login){
    x.logged_in=true;x.phase=StandardQmtPhase::LoggedIn;
    x.callback([&]{x.spi->onLoginResult(true,"QMT共享内存来源已连接",x.trading_date);});
   }else if(result.kind==Impl::Kind::Query){
    // 运输/generation/原D已核成功。解绑是正常抑制，不再访问Base或构造候选。
    if(!x.spi){x.release_read(result.read_generation);continue;}
    require(x.spi&&x.spi->getBaseDataMgr(),"qmt_standard_base_data_missing");
    std::size_t reserve=x.identity_budget.max_total_bytes;
    if(x.events_enabled){
     standard_event_budget::OrdinaryBanks banks;
     if(!standard_event_budget::ordinary(x.event_budget_input,result.stage,result.account.bound.result.data_json.size(),x.binding.row_limit,banks).ok())throw EventCapacity{};
     reserve=banks.pair;
    }
    const auto next_charge=x.events_enabled?std::size_t{512}:add_size(reserve,512);
    const auto candidate_reserve=add_size(reserve,next_charge);
    {std::lock_guard<std::mutex> lock(x.mutex);if(x.events_enabled){if(!x.charge(candidate_reserve))throw EventCapacity{};}
      else require(x.charge(candidate_reserve),"qmt_standard_candidate_capacity");}
    bool candidate_saved=false;
    try {
     SignedHttpDeadline end(result.deadline);
     auto begun=begin_qmt_account_identity(result.stage,result.account,x.binding,x.spi->getBaseDataMgr(),x.identity_budget,end);
     if(!begun.status.ok()){
      x.finish_charge(candidate_reserve);x.fail(begun.status);break;
     }
     require(begun.candidate&&begun.plan,"qmt_standard_identity_begin_incomplete");
     Impl::Candidate candidate;candidate.value=std::move(begun.candidate);candidate.deadline=result.deadline;candidate.charge=reserve;
     require(x.candidates.emplace(result.id,std::move(candidate)).second,"qmt_standard_candidate_duplicate");candidate_saved=true;
     Impl::Task task;task.kind=Impl::Kind::Resolve;task.stage=result.stage;task.id=result.id;task.generation=x.generation;
     task.read_generation=result.read_generation;task.deadline=result.deadline;task.plan=std::move(begun.plan);task.charge=next_charge;
     {std::lock_guard<std::mutex> lock(x.mutex);x.queue_task(std::move(task));}credit.transfer();x.cv.notify_all();
    }catch(...){
     if(candidate_saved)x.candidates.erase(result.id);
     x.finish_charge(candidate_reserve);throw;
    }
   }else if(result.kind==Impl::Kind::Resolve){
    auto found=x.candidates.find(result.id);require(found!=x.candidates.end(),"qmt_standard_candidate_missing");
    if(!result.resolved){x.fail(result.status.ok()?failure(ErrorCode::IoError,"qmt_standard_identity_resolution_missing"):result.status);break;}
    if(!x.spi){
     // 只抑制成功终态；真实身份/运输错误继续保留。WT候选始终由owner销毁。
     if(!result.status.ok()){x.fail(result.status);break;}
     if(!result.resolved->status().ok()){x.fail(result.resolved->status());break;}
     const auto reserved=found->second.charge;x.candidates.erase(found);
     if(x.events_enabled)result.resolved.reset(); // 成功抑制先析构独立Resolved，再退其pair票据。
     x.finish_charge(reserved);continue;
    }
    auto mapped=finish_qmt_account_identity(found->second.value,result.resolved);
    const auto reserved=found->second.charge;x.candidates.erase(found);
    // mapped仍持金融数组/lookup/views，真实Result析构后才退同票据预留。
    struct PairCharge {Impl& x;std::size_t n;QmtAccountIdentityResult& value;
     ~PairCharge(){value={};x.finish_charge(n);}} pair_charge{x,x.events_enabled?reserved:0,mapped};
    if(!x.events_enabled)x.finish_charge(reserved);
    if(!mapped.status.ok()){x.fail(mapped.status);break;}
    require(mapped.batch.array&&Clock::now()<result.deadline,"qmt_standard_identity_finish_incomplete");
    x.remember(mapped.batch,result.stage,true);++x.queries;
    x.callback([&]{if(result.stage==0)x.spi->onRspPosition(mapped.batch.array.get());
     else if(result.stage==1)x.spi->onRspOrders(mapped.batch.array.get());
     else if(result.stage==2)x.spi->onRspTrades(mapped.batch.array.get());else x.spi->onRspAccount(mapped.batch.array.get());});
    if(result.stage==0)x.position_query_applied(mapped.batch,result.id);
    x.observation_refresh_applied(result.id);
    // 只有完整查询交给原SPI并返回，才公开本次事实的序号。活动单覆盖整个账户。
    if(result.stage<=1||result.stage==3){
     std::uint32_t active=0;
     if(result.stage==1)for(unsigned i=0;i<mapped.batch.array->size();++i)
      if(mapped.batch.array->at<wtp::WTSOrderInfo>(i)->isAlive())++active;
     std::lock_guard<std::mutex> lock(x.mutex);
     if(result.stage==0)x.last_position_query=result.id;
     else if(result.stage==1){x.last_order_query=result.id;x.active_orders=active;}
     else x.last_account_query=result.id;
    }
    {std::lock_guard<std::mutex> lock(x.mutex);if(x.submission_refresh_task==result.id)x.submission_refresh_task=0;}
    if(x.events_enabled){std::lock_guard<std::mutex> lock(x.mutex);x.query_flow_mask|=1u<<result.stage;x.cv.notify_all();}
   }else if(result.kind==Impl::Kind::EventPage||result.kind==Impl::Kind::EventResolve){
    if(x.event_detached||!x.spi){
     if(result.kind==Impl::Kind::EventResolve){
      if(!result.status.ok()){x.fail(result.status);break;}
      if(!result.resolved){x.fail(failure(ErrorCode::IoError,"qmt_standard_event_resolution_missing"));break;}
      if(!result.resolved->status().ok()){x.fail(result.resolved->status());break;}
     }
     if(x.event_chain)x.event_chain->candidate.reset();continue;
    }
    if(result.kind==Impl::Kind::EventPage)x.accept_event_page(result,credit,charge.n);
    else x.finish_event(result);
    // pump(1)也在本次完成中结算空页/最后一项；不等下一次调度才判已结束任务的D。
    x.settle_completed_event_chain();
   }else {
    if(result.kind==Impl::Kind::Insert){++x.inserts;x.entrust_reply(result.order,{},false);}else ++x.cancels;
    // SDK返回仅确认原调用结果；真实订单/成交推送沿后续事件消费实现，不能构造假回报。
   }
  }
  x.maintain_event_deadline();
  x.advance_submission_refresh();
  if(!x.stop_requested&&delivered<limit){x.schedule_audit();x.schedule_events();x.schedule_observation_refresh();}
  // 调度可能同步调用SPI；回调跨D也在本次owner机会结束前维护，绝不增加完成配额。
  x.maintain_event_deadline();
  if(x.stop_requested)x.retire_candidates();
  return static_cast<int>(delivered);
 }catch(const EventCapacity&){x.fail(fixed_failure(ErrorCode::Backpressure));x.retire_candidates();return StandardQmtFailure;}
 catch(const EventOperationFailure& e){x.fail(fixed_failure(e.code));x.retire_candidates();return StandardQmtFailure;}
 catch(const std::exception& e){x.fail(x.events_enabled?fixed_failure(ErrorCode::IoError):failure(ErrorCode::IoError,e.what()));x.retire_candidates();return StandardQmtFailure;}
 catch(...){x.fail(x.events_enabled?fixed_failure(ErrorCode::SubmissionUnknown):failure(ErrorCode::SubmissionUnknown,"qmt_standard_callback_or_mapping_unknown"));x.retire_candidates();return StandardQmtFailure;}
}
int StandardQmtTrader::wait(std::uint32_t flags,std::uint32_t timeout_ms)
{
 if(!owner())return StandardQmtWrongOwner;auto& x=*impl_;
 if(x.pumping||x.in_callback)return StandardQmtReentrant;
 if(!flags||(flags&~std::uint32_t(StandardQmtPumpReady|StandardQmtWorkerDone|StandardQmtStopRequested))||timeout_ms>120000)return StandardQmtInvalid;
 const auto end=Clock::now()+std::chrono::milliseconds(timeout_ms);
 std::unique_lock<std::mutex> lock(x.mutex);
 auto available=[&]{return ((flags&StandardQmtPumpReady)&&(!x.results.empty()||!x.ingress_error.ok()||!x.owner_error.ok()||x.event_ready(Clock::now())||x.audit_ready(Clock::now())))
  ||((flags&StandardQmtPumpReady)&&x.observation_refresh_ready(Clock::now()))
  ||((flags&StandardQmtWorkerDone)&&x.worker_done)||((flags&StandardQmtStopRequested)&&x.stop_requested);};
 while(!available()&&Clock::now()<end){
  const auto until=(flags&StandardQmtPumpReady)?x.observation_refresh_wake(x.audit_wake(x.event_wake(end))):end;x.cv.wait_until(lock,until);
 }
 unsigned result=0;
 if((flags&StandardQmtPumpReady)&&(!x.results.empty()||!x.ingress_error.ok()||!x.owner_error.ok()||x.event_ready(Clock::now())||x.audit_ready(Clock::now())||x.observation_refresh_ready(Clock::now())))result|=StandardQmtPumpReady;
 if((flags&StandardQmtWorkerDone)&&x.worker_done)result|=StandardQmtWorkerDone;
 if((flags&StandardQmtStopRequested)&&x.stop_requested)result|=StandardQmtStopRequested;
 if(!result)result|=StandardQmtDeadline;return static_cast<int>(result);
}
int StandardQmtTrader::stop()
{if(!owner())return StandardQmtWrongOwner;if(impl_->phase==StandardQmtPhase::Closed)return 0;impl_->request_stop();impl_->retire_candidates();return 0;}
void StandardQmtTrader::release()
{
 if(!owner())return;auto& x=*impl_;if(x.phase==StandardQmtPhase::Closed)return;
 x.request_stop();x.spi=nullptr;if(x.in_callback||x.pumping)return;
 // 同线程base尚未退出时不能等待自己持有的ingress；end归还后由原owner再release。
 {std::lock_guard<std::mutex> lock(x.mutex);if(x.query_first&&x.submission.open)return;}
 // Candidate的WT对象在owner退役；worker晚到的Resolved仅含独立值。
 x.retire_candidates();
 if(x.worker.joinable()){
  std::unique_lock<std::mutex> lock(x.mutex);
  if(!x.cv.wait_until(lock,x.close_deadline,[&]{return x.worker_done&&x.active_ingress==0;}))return;
  require(x.drained,"qmt_standard_worker_drain_missing");lock.unlock();x.worker.join();
 }else {std::lock_guard<std::mutex> lock(x.mutex);x.worker_done=true;x.drained=true;}
 if(!x.retain_stopped_results(true))return;
 {std::lock_guard<std::mutex> lock(x.mutex);x.tasks.clear();x.results.clear();x.candidates.clear();x.held_reads.clear();
  if(!x.query_first)x.identities.clear();
  else for(auto it=x.identities.begin();it!=x.identities.end();){
   if(!it->second.group_id||it->second.observation==SubmissionObservation::None)it=x.identities.erase(it);else ++it;
  }
  x.event_chain.reset();x.event_index.reset();x.event_context={};x.audit_source={};x.audit_source_ready=false;x.audit_inflight=false;x.context_charge=0;x.chain_charge=0;x.event_context_ready=false;
  x.event_callback_reserved=0;x.outstanding=0;x.payload_bytes=0;for(const auto& item:x.pending)x.payload_bytes=add_size(x.payload_bytes,item.second.charge);
  // Closed仍可观察等待券商的原身份；真destroy才退本实例内存，不声称原委托已撤。
  if(x.query_first)for(const auto& item:x.identities){
   const auto fixed=x.events_enabled?sizeof(decltype(x.identities)::value_type):0;
   x.payload_bytes=add_size(x.payload_bytes,add_size(x.identity_charge(item.first,item.second),fixed));
  }
 }
 x.joined=true;x.initialized=false;x.phase=StandardQmtPhase::Closed;
}
int StandardQmtTrader::diagnostics(StandardQmtDiagnostics& out)const
{
 if(!owner())return StandardQmtWrongOwner;auto& x=*impl_;StandardQmtDiagnostics value;
 value.phase=static_cast<unsigned>(x.phase);value.connected=x.connected;value.logged_in=x.logged_in;
 value.stop_requested=x.stop_requested;
 // 临时调度暂停沿独立准入位处理；此字段继续表示原通信/故障围栏。
 value.writes_blocked=x.writes_blocked||x.hard_fault||x.read_waiting;
 value.worker_live=x.worker_live;value.joined=x.joined;value.callbacks=x.callbacks;
 value.queries=x.queries;value.inserts=x.inserts;value.cancels=x.cancels;
 value.candidates=static_cast<unsigned>(x.candidates.size())+(x.event_chain&&x.event_chain->candidate?1u:0u);value.owner_thread=std::hash<std::thread::id>{}(x.owner_thread);
 {std::lock_guard<std::mutex> lock(x.mutex);value.queued=static_cast<unsigned>(x.tasks.size());value.ready=static_cast<unsigned>(x.results.size());
  value.pending_commands=static_cast<unsigned>(x.pending.size());value.worker_done=x.worker_done;value.drained=x.drained;
  value.worker_thread=x.worker_thread;value.payload_bytes=x.payload_bytes;}
 value.error=static_cast<int>(x.first_error.code);
 const auto& reason=x.first_error.ok()&&x.read_waiting?std::string("qmt_read_source_waiting"):x.first_error.reason;
 std::strncpy(value.reason,reason.c_str(),sizeof(value.reason)-1);
 std::strncpy(value.last_command_id,x.last_command.c_str(),sizeof(value.last_command_id)-1);out=value;return 0;
}
int StandardQmtTrader::event_chain_diagnostics(EventChainDiagnosticsV1& out)const
{
 if(!owner())return StandardQmtWrongOwner;
 if(out.version!=1||out.size!=sizeof(out))return StandardQmtInvalid;
 std::lock_guard<std::mutex> lock(impl_->mutex);out=impl_->event_deadline;return 0;
}
int StandardQmtTrader::awaiting_observation()const
{
 if(!owner())return StandardQmtWrongOwner;
 auto& x=*impl_;std::lock_guard<std::mutex> lock(x.mutex);
 return x.query_first&&(x.unknown_fenced||x.read_waiting)&&!x.hard_fault&&!x.stop_requested&&!x.submissions_closed
     &&x.ingress_error.ok()&&x.owner_error.ok()
     &&(x.first_error.ok()||x.first_error.code==ErrorCode::SubmissionUnknown)?1:0;
}
int StandardQmtTrader::close_submissions()
{
 if(!owner())return StandardQmtWrongOwner;auto& x=*impl_;
 if(x.pumping||x.in_callback)return StandardQmtReentrant;
 std::lock_guard<std::mutex> lock(x.mutex);
 if(!x.query_first||!x.active()||!x.logged_in||x.submission.open)return StandardQmtUnavailable;
 x.submissions_closed=true;x.cv.notify_all();return 0;
}
int StandardQmtTrader::pause_inserts(bool paused)
{
 if(!owner())return StandardQmtWrongOwner;auto& x=*impl_;
 if(x.pumping||x.in_callback)return StandardQmtReentrant;
 std::lock_guard<std::mutex> lock(x.mutex);
 if(!x.query_first||!x.active()||!x.logged_in||x.submissions_closed||x.submission.open)return StandardQmtUnavailable;
 x.inserts_paused=paused;x.cv.notify_all();return 0;
}
int StandardQmtTrader::recovery(StandardQmtRecoveryV1& out)const
{
 if(!owner())return StandardQmtWrongOwner;
 if(out.version!=1||out.size!=sizeof(out))return StandardQmtInvalid;
 auto& x=*impl_;std::lock_guard<std::mutex> lock(x.mutex);StandardQmtRecoveryV1 value;
 value.query_first=x.query_first;value.submissions_closed=x.submissions_closed;value.open_group=x.submission.open;
 value.pending_commands=static_cast<std::uint32_t>(x.pending.size());
 value.unsafe=x.hard_fault||x.unknown_fenced||x.read_waiting||!x.held_reads.empty()||!x.first_error.ok()||!x.ingress_error.ok()||!x.owner_error.ok();
 value.active_orders=x.active_orders;value.next_task=x.next_task;
 value.last_order_query=x.last_order_query;value.last_position_query=x.last_position_query;value.last_account_query=x.last_account_query;
 for(const auto& item:x.identities)if(item.second.group_id&&item.second.observation!=SubmissionObservation::None)++value.unresolved_children;
 out=value;return 0;
}
}
