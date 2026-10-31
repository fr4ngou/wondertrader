#include "QmtAccountIdentity.h"
#include "JsonBoundary.h"
#include "GuanhengCommon/QmtAccountFields.h"
#include "GuanhengCommon/QmtHostCodec.h"
#include "Includes/WTSTradeDef.hpp"
#include <algorithm>
#include <cmath>
#include <limits>
#include <map>
#include <utility>
#include <thread>
#include <initializer_list>
#include <new>

namespace guanheng { namespace bootstrap {
namespace {
using V=rapidjson::Value;
using Allocator=rapidjson::Document::AllocatorType;
// SEV-R2b逻辑索引预留：provenance来源/界限/摘要引用，group输出/lookup引用。
// 不是sizeof，也不等同分配器实际占用；全部可变字符串另计。
constexpr std::size_t event_provenance_index_bytes=128,event_group_index_bytes=64;
enum class IdentitySourceKind { Query, Event, EventQuery };
struct IdentityFailure { Status status; };
// 资源错误出口只改固定分类并清空诊断；资源不足时不再构造第二个字符串。
void fixed_status(Status& status,ErrorCode code) noexcept
{ status.code=code;status.reason.clear(); }
void require(bool condition,ErrorCode code,const char* reason)
{ if(!condition)throw IdentityFailure{{code,reason}}; }
void current(SignedHttpDeadline& deadline)
{ require(deadline.remaining()!=0,ErrorCode::Timeout,"qmt_account_identity_deadline"); }
const V& member(const V& value,const char* key)
{
 require(value.IsObject()&&value.HasMember(key),ErrorCode::InvalidInput,"qmt_account_identity_metadata_invalid");
 return value[key];
}
void parse(const std::string& raw,rapidjson::Document& out,std::size_t cap)
{
 require(!raw.empty()&&parse_bounded_qmt_json(raw,out,cap,1048576)&&out.IsObject(),
  ErrorCode::InvalidInput,"qmt_account_identity_metadata_invalid");
}
std::string text(const V& value)
{
 require(value.IsString(),ErrorCode::InvalidInput,"qmt_account_identity_metadata_invalid");
 return {value.GetString(),value.GetStringLength()};
}
struct PayloadBudget {
 const QmtAccountIdentityBudget& limits;
 std::size_t total=0,lookup=0,views=0;
 explicit PayloadBudget(const QmtAccountIdentityBudget& value):limits(value)
 {
  const std::size_t hard=64*1024*1024;
  require(value.max_total_bytes>0&&value.max_total_bytes<=hard
   &&value.max_lookup_bytes>0&&value.max_lookup_bytes<=value.max_total_bytes
   &&value.max_identity_view_bytes>0&&value.max_identity_view_bytes<=value.max_total_bytes,
   ErrorCode::InvalidInput,"qmt_account_identity_budget_invalid");
 }
 void add(std::size_t value)
 {
  require(value<=limits.max_total_bytes-total,ErrorCode::Backpressure,"qmt_account_identity_payload_limit");
  total+=value;
 }
 void lookup_bytes(std::size_t value)
 {
  require(value<=limits.max_lookup_bytes-lookup,ErrorCode::Backpressure,"qmt_account_identity_lookup_limit");
  add(value);lookup+=value;
 }
 void view_bytes(std::size_t value)
 {
  require(value<=limits.max_identity_view_bytes-views,ErrorCode::Backpressure,"qmt_account_identity_view_limit");
  add(value);views+=value;
 }
};
// WT setter按C字符串复制。先拒绝NUL、过长及非规范UTF-8，防止截断后认领其他身份。
bool slot(const std::string& value)
{
 if(value.size()>63)return false;
 for(std::size_t i=0;i<value.size();){
  const auto lead=static_cast<unsigned char>(value[i++]);
  if(lead==0)return false;
  if(lead<0x80)continue;
  unsigned count=0,code=0,minimum=0;
  if(lead>=0xc2&&lead<=0xdf){count=1;code=lead&31;minimum=0x80;}
  else if(lead>=0xe0&&lead<=0xef){count=2;code=lead&15;minimum=0x800;}
  else if(lead>=0xf0&&lead<=0xf4){count=3;code=lead&7;minimum=0x10000;}
  else return false;
  if(count>value.size()-i)return false;
  for(unsigned n=0;n<count;++n){const auto next=static_cast<unsigned char>(value[i++]);if((next&0xc0)!=0x80)return false;code=(code<<6)|(next&63);}
  if(code<minimum||code>0x10ffff||(code>=0xd800&&code<=0xdfff))return false;
 }
 return true;
}
const V* optional(const V& row,const char* key)
{ return row.HasMember(key)?&row[key]:nullptr; }
bool same_scalar(const V* lhs,const V* rhs)
{
 if(!lhs||!rhs)return lhs==rhs;
 if(lhs->GetType()!=rhs->GetType()||lhs->IsDouble()!=rhs->IsDouble())return false;
 if(lhs->IsNull())return true;
 if(lhs->IsBool())return lhs->GetBool()==rhs->GetBool();
 if(lhs->IsString())return lhs->GetStringLength()==rhs->GetStringLength()
  &&std::equal(lhs->GetString(),lhs->GetString()+lhs->GetStringLength(),rhs->GetString());
 if(lhs->IsDouble())return lhs->GetDouble()==rhs->GetDouble();
 if(lhs->IsInt64()&&rhs->IsInt64())return lhs->GetInt64()==rhs->GetInt64();
 return lhs->IsUint64()&&rhs->IsUint64()&&lhs->GetUint64()==rhs->GetUint64();
}
void scalar(const V* value)
{
 require(!value||value->IsNull()||value->IsBool()||value->IsString()
  ||(value->IsNumber()&&std::isfinite(value->GetDouble())),
  ErrorCode::InvalidInput,"qmt_account_identity_scalar_invalid");
}
void add(V& object,const char* key,const std::string& value,Allocator& allocator)
{ object.AddMember(V(key,allocator),V(value.data(),static_cast<unsigned>(value.size()),allocator),allocator); }
void source_scalar(V& object,const char* key,const V* value,Allocator& allocator)
{
 V field(rapidjson::kObjectType);field.AddMember("presence",value!=nullptr,allocator);
 V copy;if(value)copy.CopyFrom(*value,allocator);field.AddMember("value",copy,allocator);
 object.AddMember(V(key,allocator),field,allocator);
}
void same_source(const QmtTradeEventSource& actual,const V& account_binding,const std::string& original_session)
{
 rapidjson::Document binding;parse(actual.binding_json,binding,4096);
 require(qmt_host_codec::binding(binding,nullptr,"2.0")&&binding==account_binding
  &&!actual.session_id.empty()&&(original_session.empty()||actual.session_id==original_session),
  ErrorCode::StaleSession,"qmt_account_identity_source_changed");
}
struct AdmittedIdentityEvent {
 QmtTradeReadDescriptor descriptor;QmtValidatedTradeEventPage validated;
 std::string kind;unsigned stage=0;
};
// 两种事件来源共用原页/绑定准入；此层不构造金融值，也不扩展Common控制。
AdmittedIdentityEvent admit_identity_event(const QmtTradeEventPage& input,
 const QmtTradeEventRequestBounds& bounds,std::size_t event_index,const QmtExpectedTrade& expected,
 const AccountBinding& binding,wtp::IBaseDataMgr* base,PayloadBudget& budget,SignedHttpDeadline& deadline)
{
 AdmittedIdentityEvent out;
  if(!input.status.ok())throw IdentityFailure{input.status};
  require(base&&input.http_status==200&&!input.page_json.empty()
   &&input.page_json.size()<=bounds.max_bytes&&input.page_json.size()<=input.admitted_event_page_capacity
   &&!input.read_profile_body.empty()&&input.read_profile_body.size()<=4096
   &&input.source.binding_json.size()<=4096&&input.source.session_id.size()<=128,
   ErrorCode::InvalidInput,"qmt_event_identity_input_invalid");
  require(binding.account==expected.account.account_id&&binding.row_limit>0
   &&(expected.account.environment==QmtAccountEnvironment::Simulation||expected.account.environment==QmtAccountEnvironment::Live)
   &&binding.environment==(expected.account.environment==QmtAccountEnvironment::Simulation?"simulation":"live"),
   ErrorCode::Conflict,"qmt_event_identity_account_conflict");
  // 原bytes先计入同一预算，再准入profile/page DOM；实际HTTP cap仍由宿主拥有。
  budget.add(event_provenance_index_bytes);
  for(const auto* value:{&input.source.binding_json,&input.source.session_id,&input.page_json,&input.read_profile_body}){
   budget.add(value->size());budget.add(1);
  }
  budget.add(2*(64+1)); // 两个固定长度派生SHA的字符串及逻辑NUL。
  auto& descriptor=out.descriptor;
  const auto profile_status=validate_qmt_trade_read_profile(input.read_profile_body,input.read_result_capacity,
   expected.account,descriptor);
  if(!profile_status.ok())throw IdentityFailure{profile_status};
  // Common兼容旧account policy；事件身份入口明确消费2.0的原字段契约。
  rapidjson::Document profile;parse(input.read_profile_body,profile,4096);
  const auto& operation=member(member(profile,"operation_profiles"),"account.trade_detail");
  require(text(member(operation,"policy_version"))==account_fields::identity_policy_version,
   ErrorCode::InvalidInput,"qmt_event_identity_policy_invalid");
  require(input.page_json.size()<=descriptor.max_event_page_bytes,
   ErrorCode::InvalidInput,"qmt_event_identity_input_invalid");
  current(deadline);auto& validated=out.validated;
  const auto page_status=validate_qmt_trade_event_page(input.page_json,input.source,bounds,expected,
   descriptor,input.admitted_event_page_capacity,deadline,validated);
  if(!page_status.ok())throw IdentityFailure{page_status};
  require(signed_http_sha256(input.read_profile_body)==text(member(validated.source_binding,"capability_sha256")),
   ErrorCode::Conflict,"qmt_event_identity_profile_conflict");
  require(input.next_sequence==validated.next_sequence&&input.event_count==validated.event_count
   &&input.durable_through==validated.durable_through&&input.source_ack_through==validated.source_ack_through
   &&input.gap==validated.gap&&event_index<validated.event_count,
   ErrorCode::InvalidInput,"qmt_event_identity_page_conflict");
  const auto& event=member(validated.document,"events")[static_cast<rapidjson::SizeType>(event_index)];
  out.kind=text(member(event,"kind"));const auto& kind=out.kind;
  require(kind=="order"||kind=="deal",ErrorCode::InvalidInput,"qmt_event_identity_kind_invalid");
  out.stage=kind=="order"?1:2;
  budget.add(kind.size());budget.add(1);current(deadline);
 return out;
}
struct Group {
 const V* remark=nullptr;const V* order_ref=nullptr;bool present=false;
 std::string broker,symbol,trade_id,classification,reason,entrust_id,user_tag,lookup_sha;
 std::size_t lookup_index=0;bool has_lookup=false;
};
void collect_group_row(Group& group,const V& row)
{
 const auto remark=optional(row,account_fields::remark),order_ref=optional(row,account_fields::order_ref);
 scalar(remark);scalar(order_ref);
 if(group.present)require(same_scalar(group.remark,remark)&&same_scalar(group.order_ref,order_ref),
  ErrorCode::Conflict,"qmt_account_identity_duplicate_conflict");
 else {group.present=true;group.remark=remark;group.order_ref=order_ref;}
}
void complete_group_facts(unsigned stage,const AccountBatch& batch,std::vector<Group>& groups)
{
 for(std::size_t i=0;i<groups.size();++i){
  auto& group=groups[i];require(group.present,ErrorCode::InvalidInput,"qmt_account_identity_mapping_invalid");
  const char* exchange=nullptr;const char* code=nullptr;
  if(stage==1){auto order=batch.array->at<wtp::WTSOrderInfo>(static_cast<unsigned>(i));
   require(order!=nullptr,ErrorCode::InvalidInput,"qmt_account_identity_mapping_invalid");
   group.broker=order->getOrderID();exchange=order->getExchg();code=order->getCode();}
  else {auto fill=batch.array->at<wtp::WTSTradeInfo>(static_cast<unsigned>(i));
   require(fill!=nullptr,ErrorCode::InvalidInput,"qmt_account_identity_mapping_invalid");
   group.broker=fill->getRefOrder();group.trade_id=fill->getTradeID();exchange=fill->getExchg();code=fill->getCode();}
  require(slot(group.broker)&&!group.broker.empty()&&slot(group.trade_id),
   ErrorCode::InvalidInput,"qmt_account_identity_slot_invalid");
  require(std::string(exchange)=="SSE"||std::string(exchange)=="SZSE",
   ErrorCode::InvalidInput,"qmt_account_identity_mapping_invalid");
  group.symbol=std::string(code)+(std::string(exchange)=="SSE"?".SH":".SZ");
 }
}
void build_groups(unsigned stage,const AccountBatch& batch,const V& rows,
 std::vector<Group>& groups,SignedHttpDeadline& deadline)
{
 require(rows.IsArray()&&rows.Size()==batch.source_rows,
  ErrorCode::InvalidInput,"qmt_account_identity_mapping_invalid");
 if(stage!=1&&stage!=2)return;
 groups.resize(batch.array->size());
 for(std::size_t i=0;i<batch.source_to_output.size();++i){
  current(deadline);const auto output=batch.source_to_output[i];
  require(output<groups.size()&&rows[static_cast<rapidjson::SizeType>(i)].IsObject(),
   ErrorCode::InvalidInput,"qmt_account_identity_mapping_invalid");
  collect_group_row(groups[output],rows[static_cast<rapidjson::SizeType>(i)]);
 }
 complete_group_facts(stage,batch,groups);
}
void build_selected_group(unsigned stage,const AccountSelectedRowBatch& selected,const V& original_rows,
 rapidjson::Document& owned_row,std::vector<Group>& groups,SignedHttpDeadline& deadline)
{
 current(deadline);const auto& batch=selected.batch;
 require(original_rows.IsArray()&&original_rows.Size()==selected.original_row_count
  &&selected.original_row_index<original_rows.Size()&&batch.array&&batch.array->size()==1
  &&batch.source_rows==1&&batch.source_to_output.size()==1&&batch.source_to_output[0]==0,
  ErrorCode::InvalidInput,"qmt_account_identity_mapping_invalid");
 // 仅标量借用owner复制选中的完整原行；原查询DTO和原下标始终独立保留。
 owned_row.CopyFrom(original_rows[static_cast<rapidjson::SizeType>(selected.original_row_index)],owned_row.GetAllocator());
 groups.resize(1);collect_group_row(groups[0],owned_row);complete_group_facts(stage,batch,groups);
}
void charge_batch(const AccountBatch& batch,PayloadBudget& budget)
{
 for(const auto& view:batch.views)budget.add(view.size());
 require(batch.source_to_output.size()<=(std::numeric_limits<std::size_t>::max)()/sizeof(std::size_t),
  ErrorCode::Backpressure,"qmt_account_identity_payload_limit");
 budget.add(batch.source_to_output.size()*sizeof(std::size_t));
}

// R5d-B只度量逻辑并存载荷；这些checked算术在任何相应复制/编码前执行。
constexpr std::size_t event_query_hard=64u*1024u*1024u;
std::size_t qadd(std::size_t a,std::size_t b){require(b<=(std::numeric_limits<std::size_t>::max)()-a,ErrorCode::Backpressure,"qmt_event_query_work_limit");return a+b;}
std::size_t qmul(std::size_t a,std::size_t b){require(!a||b<=(std::numeric_limits<std::size_t>::max)()/a,ErrorCode::Backpressure,"qmt_event_query_work_limit");return a*b;}
std::size_t qsum(std::initializer_list<std::size_t> values){std::size_t n=0;for(auto v:values)n=qadd(n,v);return n;}
std::size_t qt(std::size_t n){return qadd(n,1);}
std::size_t qj(std::size_t n){return qmul(9,qt(n));}
std::size_t qx(std::size_t n){return qmul(32,qt(n));}
std::size_t qs(std::size_t n){return qadd(qmul(6,n),2);}
using BoundField=std::pair<const char*,std::size_t>;
std::size_t qo(std::initializer_list<BoundField> fields){std::size_t n=qadd(2,fields.size()?fields.size()-1:0);for(const auto& f:fields)n=qsum({n,std::strlen(f.first),3,f.second});return n;}
struct IdentityCountingOutput {
 using Ch=char;std::size_t size=0;
 void Put(char){size=qadd(size,1);}void Flush(){}
};
std::size_t json_count(const V& value){IdentityCountingOutput out;rapidjson::Writer<IdentityCountingOutput> writer(out);require(value.Accept(writer),ErrorCode::InvalidInput,"qmt_event_query_json_invalid");return out.size;}
std::size_t query_text_bytes(const QmtAccountResult& q){
 const auto& b=q.bound;const auto& r=b.result;std::size_t n=0;
 for(const auto* v:{&r.status.reason,&r.data_json,&r.envelope_json,&r.request_id,&r.operation_id,
  &b.receipt.binding_json,&b.receipt.request_body,&b.receipt.read_profile_body,&b.receipt.retention_ticket_json,&b.native_result_json,&q.remote_error_code})n=qadd(n,qt(v->size()));return n;
}
std::size_t event_text_bytes(const QmtTradeEventPage& p){std::size_t n=0;for(const auto* v:{&p.status.reason,&p.source.binding_json,&p.source.session_id,&p.page_json,&p.read_profile_body})n=qadd(n,qt(v->size()));return n;}
std::size_t admission_dom_bytes(const QmtTradeEventPage& p,const QmtAccountResult& q){return qsum({qj(p.page_json.size()),qj(p.source.binding_json.size()),qj(p.read_profile_body.size()),qj(q.bound.result.data_json.size()),qj(q.bound.receipt.binding_json.size()),qj(q.bound.receipt.read_profile_body.size())});}
// descriptor SHA65、Bootstrap比较的两SHA各65、policy4、kind6分别持有。
constexpr std::size_t event_query_admission_text=65+2*65+4+6;
std::size_t event_query_admission_bytes(const QmtTradeEventPage& p,const QmtAccountResult& q){return qsum({event_text_bytes(p),query_text_bytes(q),admission_dom_bytes(p,q),event_query_admission_text});}
void work_fits(std::size_t need,const QmtEventQueryIdentityBudget& b){require(b.max_work_bytes>0&&b.max_work_bytes<=event_query_hard&&need<=b.max_work_bytes,ErrorCode::Backpressure,"qmt_event_query_work_limit");}
std::size_t event_query_match_bytes(const QmtTradeEventPage& p,const QmtAccountResult& q,std::size_t e,const QmtEventQueryIdentityBudget& b){
 const auto row=(std::min)(std::size_t(1048576),qx(q.bound.result.data_json.size()));
 const auto dom=qsum({qj(q.bound.result.data_json.size()),qj(e),qj(row),qmul(2,qj(1024)),2*1025});
 return qsum({event_query_admission_bytes(p,q),qmul(2,qt(e)),b.match.max_work_bytes,dom});
}
std::size_t event_query_view_bound(std::size_t r,std::size_t o){
 const auto ev=qo({{"event_index",20},{"sequence",20},{"kind",qs(5)},{"derived_page_sha256",qs(64)},{"derived_event_sha256",qs(64)}});
 const auto query=qo({{"request_id",qs(36)},{"result_sha256",qs(64)},{"original_row_index",20},{"original_row_count",20},{"derived_row_sha256",qs(64)}});
 const auto pe=qo({{"source_sequence",20},{"source_event_sha256",qs(64)}});
 const auto pq=qo({{"query_request_id",qs(36)},{"query_result_sha256",qs(64)},{"query_row_index",20}});
 const auto proof=qo({{"kind",qs(13)},{"dispatched",5},{"has_broker_proof",5},{"event",pe},{"query",pq}});
 return qo({{"schema_version",qs(std::strlen("qmt.wt-event-query-identity.v1"))},{"stage",20},{"output_index",20},
  {"order_id",qs(63)},{"ref_order",qs(63)},{"trade_id",qs(63)},
  {"m_strRemark",qo({{"presence",5},{"value",r}})},{"m_strOrderRef",qo({{"presence",5},{"value",o}})},
  {"classification",qs(std::strlen("unresolved"))},{"entrust_id",qs(63)},{"user_tag",qs(63)},
  {"reason",qs(std::strlen("original_insert_and_broker_proof"))},{"lookup_response_index",20},{"lookup_sha256",qs(64)},
  {"event_trigger",ev},{"selected_query",query},{"broker_proof",proof}});
}
struct EventQueryWork {std::size_t admission=0,match=0,begin=0,resolve=0,finish=0,need=0,identity_view=0,lookup_response=0;};
EventQueryWork event_query_work(const QmtTradeEventPage& p,const QmtAccountResult& q,const AccountBinding& binding,
 const QmtEventQueryIdentityBudget& b,const QmtTradeReadDescriptor& descriptor,unsigned stage,
 std::size_t e,std::size_t event_record,std::size_t selected,std::size_t remark,std::size_t order_ref,std::size_t fixed_bytes){
 EventQueryWork w;w.admission=event_query_admission_bytes(p,q);w.match=event_query_match_bytes(p,q,e,b);
 require(descriptor.max_command_bytes>0&&descriptor.max_command_bytes<=65536&&descriptor.max_call_result_bytes>0&&descriptor.max_call_result_bytes<=2097152,
  ErrorCode::InvalidInput,"qmt_event_query_descriptor_invalid");
 const auto k=static_cast<std::size_t>(descriptor.max_command_bytes),result=static_cast<std::size_t>(descriptor.max_call_result_bytes);
 w.lookup_response=qsum({qmul(4,qadd(k,2)/3),result,32768});
 const auto& receipt=q.bound.receipt;const auto& qr=q.bound.result;
 const auto source=qo({{"kind",qs(13)},{"account_id",qs(binding.account.size())},{"account_environment",qs(binding.environment.size())},
  {"transport_binding",qx(receipt.binding_json.size())},{"binding_sha256",qs(64)},
  {"broker_session",qo({{"availability",qs(7)},{"value",4},{"reason",qs(std::strlen("未取得券商登录会话证据"))}})}});
 const auto metadata=qsum({qt(source),37,65,33,33});
 const auto f=stage==1?std::size_t(57133):std::size_t(46315),n=stage==1?std::size_t(34130):std::size_t(29118);
 const auto a=qsum({qmul(2,qj(1024)),2*1025,qj(qr.data_json.size()),qj(q.bound.native_result_json.size()),qj(receipt.request_body.size()),
  qj(receipt.binding_json.size()),qj(receipt.read_profile_body.size()),qj(source),qmul(2,qt(source)),qmul(2,metadata),21,
  4096,7,3,4,64,11,13,64,64,84,stage==1?64u:128u,stage==2?148u:0u,stage==2?122u:0u,stage==2?84u:0u,
  220,stage==1?1u:64u,qj(f),qj(n),qmul(3,qt(n)),qj(4193),2*4194,65,65536,32,qmul(2,qt(f))});
 const auto group=qsum({64,10,64,qt(std::strlen("unresolved")),qt(std::strlen("original_insert_and_broker_proof")),64,64,65});
 // E'/Q'显式保留一个完整副本；原status reason保守多计，绝不以别名抵消独立文本。
 w.begin=qsum({fixed_bytes,event_text_bytes(p),query_text_bytes(q),admission_dom_bytes(p,q),event_query_admission_text,295,
  event_text_bytes(p),query_text_bytes(q),12,65,65,65,qj(selected),qj(receipt.binding_json.size()),
  qmul(2,qt(e)),qmul(2,qt(event_record)),qmul(2,qt(selected)),a,qmul(2,group),2*65});
 const auto facts=qsum({64,6,129,10,64,64,65,65,37,65});
 const auto association=qt(std::strlen("broker_identity_unrepresentable"));
 const auto lookup=qsum({qmul(2,qt(w.lookup_response)),4097,qt(k),4097,4097,129,4097,64,association,
  qmul(2,facts),64,association,65,3*65,4097,129,65,37,65,65,2*(4097+129),qj(4096)});
 w.identity_view=event_query_view_bound(remark,order_ref);
 require(qt(w.identity_view)<=b.identity.max_identity_view_bytes,ErrorCode::Backpressure,"qmt_account_identity_view_limit");
 w.resolve=qsum({w.begin,lookup,qj(w.identity_view),qmul(2,qt(w.identity_view))});w.finish=w.resolve;
 w.need=(std::max)({w.admission,w.match,w.begin,w.resolve,w.finish});return w;
}
// 仅完整token参与冲突；长普通备注仍作为原标量保存，不为检测分配长副本。
std::string full_token(const V* value){if(!value||!value->IsString()||value->GetStringLength()>64)return {};auto v=text(*value);return valid_qmt_sdk_order_token(v)?v:std::string{};}

struct CachedLookup {
 bool not_found=false,has_reference=false;
 QmtTradeOrderFacts facts;
 std::string broker,association_error,sha;
 std::size_t response_index=0;
};
// 票据只记录本批独立事实；共享生命期让候选退役后worker仍可安全完成。
// 一个来源owner贯穿三个阶段；Result用别名shared_ptr继续拥有同一份原文与预留。
struct EventQuerySources {
 QmtTradeEventProvenance event;QmtEventQueryProvenance query;
 const QmtEventQueryIdentityBudget budget;const std::size_t reserved_work_bytes,identity_view_bound;
 EventQuerySources(const QmtEventQueryIdentityBudget& b,std::size_t reserve,std::size_t view)
  :budget(b),reserved_work_bytes(reserve),identity_view_bound(view){}
};

void event_query_view_sources(V& view,const EventQuerySources& sources,const QmtIdentityBrokerProof& proof,const std::string& result_sha,Allocator& a){
 const auto& e=sources.event;const auto& q=sources.query;V event(rapidjson::kObjectType),query(rapidjson::kObjectType),p(rapidjson::kObjectType);
 event.AddMember("event_index",static_cast<std::uint64_t>(e.event_index),a);event.AddMember("sequence",e.sequence,a);add(event,"kind",e.kind,a);
 add(event,"derived_page_sha256",e.derived_page_sha256,a);add(event,"derived_event_sha256",e.derived_event_sha256,a);
 add(query,"request_id",q.original_query.bound.result.request_id,a);
 // 原结果SHA由完整native终态准入取得；这里只引用候选原metadata，不制造新proof。
 add(query,"result_sha256",result_sha,a);
 query.AddMember("original_row_index",static_cast<std::uint64_t>(q.original_row_index),a);
 query.AddMember("original_row_count",static_cast<std::uint64_t>(q.original_row_count),a);add(query,"derived_row_sha256",q.derived_row_sha256,a);
 const char* kind=proof.kind==QmtTradeBrokerProofKind::Event?"event":proof.kind==QmtTradeBrokerProofKind::AccountQuery?"account_query":"none";
 add(p,"kind",kind,a);p.AddMember("dispatched",proof.dispatched,a);p.AddMember("has_broker_proof",proof.has_broker_proof,a);
 V pe,pq;if(proof.has_event){pe.SetObject();pe.AddMember("source_sequence",proof.source_sequence,a);add(pe,"source_event_sha256",proof.source_event_sha256,a);}
 if(proof.has_query){pq.SetObject();add(pq,"query_request_id",proof.query_request_id,a);add(pq,"query_result_sha256",proof.query_result_sha256,a);pq.AddMember("query_row_index",proof.query_row_index,a);}
 p.AddMember("event",pe,a);p.AddMember("query",pq,a);view.AddMember("event_trigger",event,a);view.AddMember("selected_query",query,a);view.AddMember("broker_proof",p,a);
}

struct IdentityTicket {
 std::thread::id owner;
 std::chrono::steady_clock::time_point deadline;
 unsigned stage=0;
 std::size_t max_rows=0,initial_total=0,output_count=0;
 QmtAccountIdentityBudget limits;
 std::string account,request_id,result_sha,original_session;
 std::shared_ptr<const EventQuerySources> event_query_sources;
};
struct IdentityPlanData {
 std::shared_ptr<const IdentityTicket> ticket;
 IdentitySourceKind source_kind=IdentitySourceKind::Query;
 rapidjson::Document rows,transport;
 std::shared_ptr<const QmtTradeEventProvenance> event_provenance;
 // 标量指针只指向本对象拥有的DOM；发布后整个对象只读，不借用调用者输入。
 std::vector<Group> groups;
};
}

struct QmtAccountIdentityCandidate::State {
 AccountBatch batch;
 std::shared_ptr<const IdentityPlanData> data;
};
struct QmtAccountIdentityPlan::State {
 std::shared_ptr<const IdentityPlanData> data;
};
struct QmtAccountIdentityResolved::State {
 Status status;
 std::shared_ptr<const IdentityPlanData> data;
 std::vector<Group> groups;
 std::vector<std::string> identity_views,lookup_responses;
 std::vector<QmtIdentityBrokerProof> broker_proofs;
 std::size_t total=0,lookup=0,views=0;
};
QmtAccountIdentityCandidate::QmtAccountIdentityCandidate():state_(new State){}
QmtAccountIdentityCandidate::~QmtAccountIdentityCandidate()=default;
QmtAccountIdentityPlan::QmtAccountIdentityPlan():state_(new State){}
QmtAccountIdentityPlan::~QmtAccountIdentityPlan()=default;
QmtAccountIdentityResolved::QmtAccountIdentityResolved():state_(new State){}
QmtAccountIdentityResolved::~QmtAccountIdentityResolved()=default;
const Status& QmtAccountIdentityResolved::status()const noexcept{return state_->status;}
QmtAccountIdentityBegin::QmtAccountIdentityBegin()=default;
QmtAccountIdentityBegin::~QmtAccountIdentityBegin()=default;
QmtAccountIdentityBegin::QmtAccountIdentityBegin(QmtAccountIdentityBegin&&)noexcept=default;
QmtAccountIdentityBegin& QmtAccountIdentityBegin::operator=(QmtAccountIdentityBegin&&)noexcept=default;

QmtAccountIdentityBegin begin_qmt_account_identity(unsigned stage,
 const QmtAccountResult& input,const AccountBinding& binding,wtp::IBaseDataMgr* base,
 const QmtAccountIdentityBudget& limits,SignedHttpDeadline& original_deadline)
{
 QmtAccountIdentityBegin out;
 try {
  SignedHttpDeadline deadline(original_deadline.end);
  auto ticket=std::make_shared<IdentityTicket>();
  ticket->owner=std::this_thread::get_id();ticket->deadline=deadline.end;
  ticket->stage=stage;ticket->limits=limits;ticket->account=binding.account;
  auto data_owner=std::make_shared<IdentityPlanData>();
  data_owner->ticket=ticket;
  out.candidate=std::unique_ptr<QmtAccountIdentityCandidate>(new QmtAccountIdentityCandidate);
  auto& batch=out.candidate->state_->batch;
  rapidjson::Document data;auto& transport=data_owner->transport;
  auto& groups=data_owner->groups;
  current(deadline);PayloadBudget budget(limits);
  require(stage<4&&base,ErrorCode::InvalidInput,"qmt_account_identity_stage_invalid");
  budget.add(input.bound.result.data_json.size());
  rapidjson::Document profile;
  parse(input.bound.receipt.read_profile_body,profile,16*1024*1024);
  parse(input.bound.receipt.binding_json,transport,4096);
  parse(input.bound.result.data_json,data,1048576);
  require(qmt_host_codec::binding(transport,nullptr,"2.0"),ErrorCode::InvalidInput,"qmt_account_identity_binding_invalid");
  const auto& descriptor=member(member(profile,"operation_profiles"),"account.trade_detail");
  const auto& count=member(member(descriptor,"limits"),"max_rows");
  require(count.IsUint64()&&count.GetUint64()>0&&count.GetUint64()<=4096
   &&binding.row_limit>0,ErrorCode::InvalidInput,"qmt_account_identity_rows_invalid");
  const auto max_rows=std::min<std::size_t>(static_cast<std::size_t>(count.GetUint64()),binding.row_limit);
  // 完整源metadata及所有金融解释由原入口负责；本层只消费它给出的去重对应表。
  batch=map_shm_account_batch_v2(stage,input,binding,base);
  current(deadline);
  require(batch.array&&batch.source_rows<=max_rows&&batch.array->size()<=max_rows
   &&batch.source_to_output.size()==batch.source_rows,
   ErrorCode::InvalidInput,"qmt_account_identity_mapping_invalid");
  charge_batch(batch,budget);
  data_owner->rows.CopyFrom(member(data,"rows"),data_owner->rows.GetAllocator());
  build_groups(stage,batch,data_owner->rows,groups,deadline);
  current(deadline);
  ticket->max_rows=max_rows;ticket->initial_total=budget.total;
  ticket->output_count=batch.array->size();ticket->request_id=batch.request_id;ticket->result_sha=batch.result_sha;
  out.plan=std::unique_ptr<QmtAccountIdentityPlan>(new QmtAccountIdentityPlan);
  out.plan->state_->data=data_owner;out.candidate->state_->data=data_owner;
  // 完成全部分配后再交出句柄；失败始终在owner销毁金融候选。
  current(deadline);out.status={};
 }
 catch(const IdentityFailure& failure){out.candidate.reset();out.plan.reset();out.status=failure.status;}
 // 精确区分资源耗尽与结构异常；Query/Event沿同一无分配资源出口。
 catch(const std::bad_alloc&){out.candidate.reset();out.plan.reset();fixed_status(out.status,ErrorCode::IoError);}
 catch(const std::exception&){out.candidate.reset();out.plan.reset();out.status={ErrorCode::InvalidInput,"qmt_account_identity_mapping_failed"};}
 catch(...){out.candidate.reset();out.plan.reset();out.status={ErrorCode::IoError,"qmt_account_identity_failed"};}
 return out;
}

QmtAccountIdentityBegin begin_qmt_trade_event_identity(const QmtTradeEventPage& input,
 const QmtTradeEventRequestBounds& bounds,std::size_t event_index,const QmtExpectedTrade& expected,
 const AccountBinding& binding,wtp::IBaseDataMgr* base,const QmtAccountIdentityBudget& limits,
 SignedHttpDeadline& original_deadline)
{
 QmtAccountIdentityBegin out;
 try {
  SignedHttpDeadline deadline(original_deadline.end);current(deadline);PayloadBudget budget(limits);
  auto admitted=admit_identity_event(input,bounds,event_index,expected,binding,base,budget,deadline);
  auto& validated=admitted.validated;const auto& kind=admitted.kind;const auto stage=admitted.stage;
  const auto& event=member(validated.document,"events")[static_cast<rapidjson::SizeType>(event_index)];
  // 独立单行数组的逻辑编码恰为原payload编码加[]，复制DOM前先计费。
  budget.add(json_text(member(event,"payload")).size());budget.add(2);
  auto provenance=std::make_shared<QmtTradeEventProvenance>();
  provenance->source=input.source;provenance->original_bounds=bounds;provenance->event_index=event_index;
  provenance->sequence=member(event,"sequence").GetUint64();provenance->kind=kind;
  provenance->page_json=input.page_json;provenance->read_profile_body=input.read_profile_body;
  provenance->read_result_capacity=input.read_result_capacity;
  provenance->admitted_event_page_capacity=input.admitted_event_page_capacity;
  provenance->derived_page_sha256=signed_http_sha256(input.page_json);
  provenance->derived_event_sha256=signed_http_sha256(json_text(event));
  require(provenance->derived_page_sha256.size()==64&&provenance->derived_event_sha256.size()==64,
   ErrorCode::Unavailable,"qmt_account_identity_hash_unavailable");
  auto ticket=std::make_shared<IdentityTicket>();
  ticket->owner=std::this_thread::get_id();ticket->deadline=deadline.end;ticket->stage=stage;
  ticket->limits=limits;ticket->account=binding.account;ticket->original_session=input.source.session_id;
  auto data_owner=std::make_shared<IdentityPlanData>();data_owner->ticket=ticket;
  data_owner->source_kind=IdentitySourceKind::Event;data_owner->event_provenance=provenance;
  data_owner->transport.Swap(validated.source_binding);
  auto& rows=data_owner->rows;rows.SetArray();V row;
  row.CopyFrom(member(event,"payload"),rows.GetAllocator());rows.PushBack(row,rows.GetAllocator());
  current(deadline);
  out.candidate=std::unique_ptr<QmtAccountIdentityCandidate>(new QmtAccountIdentityCandidate);
  auto& batch=out.candidate->state_->batch;
  batch=map_trade_event_rows(stage,rows,binding,base,AccountCanonicalLimits{1,limits.max_total_bytes});
  current(deadline);
  require(batch.array&&batch.source_rows==1&&batch.array->size()==1
   &&batch.source_to_output.size()==1&&batch.source_to_output[0]==0&&batch.canonical_records.size()==1
   &&batch.source.empty()&&batch.request_id.empty()&&batch.result_sha.empty()
   &&batch.started.empty()&&batch.finished.empty()&&batch.seconds.empty(),
   ErrorCode::InvalidInput,"qmt_account_identity_mapping_invalid");
  charge_batch(batch,budget);budget.add(batch.canonical_bytes);
  build_groups(stage,batch,rows,data_owner->groups,deadline);
  budget.add(event_group_index_bytes);
  const auto& group=data_owner->groups[0];
  for(const auto* value:{&group.broker,&group.symbol,&group.trade_id}){budget.add(value->size());budget.add(1);}
  ticket->max_rows=1;ticket->initial_total=budget.total;ticket->output_count=1;
  out.plan=std::unique_ptr<QmtAccountIdentityPlan>(new QmtAccountIdentityPlan);
  out.plan->state_->data=data_owner;out.candidate->state_->data=data_owner;
  current(deadline);out.status={};
 }
 catch(const IdentityFailure& failure){out.candidate.reset();out.plan.reset();out.status=failure.status;}
 // 精确区分资源耗尽与结构异常；Query/Event沿同一无分配资源出口。
 catch(const std::bad_alloc&){out.candidate.reset();out.plan.reset();fixed_status(out.status,ErrorCode::IoError);}
 catch(const std::exception&){out.candidate.reset();out.plan.reset();out.status={ErrorCode::InvalidInput,"qmt_account_identity_mapping_failed"};}
 catch(...){out.candidate.reset();out.plan.reset();out.status={ErrorCode::IoError,"qmt_account_identity_failed"};}
 return out;
}

QmtAccountIdentityBegin begin_qmt_event_query_identity(const QmtTradeEventPage& input,
 const QmtTradeEventRequestBounds& bounds,std::size_t event_index,const QmtAccountResult& query,
 std::size_t query_row_index,const QmtExpectedTrade& expected,const AccountBinding& binding,
 wtp::IBaseDataMgr* base,const QmtEventQueryIdentityBudget& limits,SignedHttpDeadline& original_deadline)
{
 QmtAccountIdentityBegin out;
 try{
  SignedHttpDeadline deadline(original_deadline.end);current(deadline);
  // 新双来源入口把旧子限额非法统一归为容量拒绝；原D先核，旧入口的构造语义保持。
  const auto& identity=limits.identity;const std::size_t identity_hard=64*1024*1024;
  if(!(identity.max_total_bytes>0&&identity.max_total_bytes<=identity_hard
   &&identity.max_lookup_bytes>0&&identity.max_lookup_bytes<=identity.max_total_bytes
   &&identity.max_identity_view_bytes>0&&identity.max_identity_view_bytes<=identity.max_total_bytes)){
   fixed_status(out.status,ErrorCode::Backpressure);return out;
  }
  PayloadBudget budget(identity);
  // 原输入仍活着；先以长度核六个admission DOM，再进入任何解析。
  work_fits(event_query_admission_bytes(input,query),limits);
  const auto& ml=limits.match;const auto& qr=query.bound.result;const auto& receipt=query.bound.receipt;
  require(ml.max_event_bytes>0&&ml.max_event_bytes<=1048576&&ml.max_query_bytes>0&&ml.max_query_bytes<=event_query_hard
   &&ml.max_work_bytes>0&&ml.max_work_bytes<=event_query_hard&&ml.max_rows>0&&ml.max_rows<=4096&&ml.max_rows<=binding.row_limit,
   ErrorCode::InvalidInput,"qmt_event_query_budget_invalid");
  require(query_text_bytes(query)<=ml.max_query_bytes,ErrorCode::Backpressure,"qmt_event_query_work_limit");
  if(!qr.status.ok())throw IdentityFailure{qr.status};
  require(qr.http_status==200&&qr.terminal&&qr.remote_ok&&!qr.data_json.empty()&&!query.bound.native_result_json.empty()
   &&query.remote_error_code.empty(),ErrorCode::InvalidInput,"qmt_event_query_result_invalid");
  auto admitted=admit_identity_event(input,bounds,event_index,expected,binding,base,budget,deadline);
  const auto& event=member(admitted.validated.document,"events")[static_cast<rapidjson::SizeType>(event_index)];
  const auto& payload=member(event,"payload");
  require(payload.IsObject(),ErrorCode::InvalidInput,"qmt_event_query_row_invalid");
  const auto e=json_count(payload);require(e<=ml.max_event_bytes,ErrorCode::Backpressure,"qmt_event_query_work_limit");
  work_fits(event_query_match_bytes(input,query,e,limits),limits);
  rapidjson::Document qdata,qbinding,qprofile;
  parse(qr.data_json,qdata,1048576);parse(receipt.binding_json,qbinding,4096);parse(receipt.read_profile_body,qprofile,4096);
  require(qbinding==admitted.validated.source_binding&&receipt.read_profile_body==input.read_profile_body
   &&receipt.read_result_capacity==input.read_result_capacity,
   ErrorCode::Conflict,"qmt_event_query_source_conflict");
  const auto& rows=member(qdata,"rows");
  require(rows.IsArray()&&query_row_index<rows.Size(),ErrorCode::InvalidInput,"qmt_event_query_row_invalid");
  require(rows.Size()<=ml.max_rows,ErrorCode::Backpressure,"qmt_event_query_work_limit");
  const auto& selected=rows[static_cast<rapidjson::SizeType>(query_row_index)];
  require(selected.IsObject(),ErrorCode::InvalidInput,"qmt_event_query_row_invalid");
  const auto s=json_count(selected);
  require(s<=1048576,ErrorCode::Backpressure,"qmt_event_query_work_limit");
  // 原matcher结构/容量共用runtime_error；前置计数保守覆盖其子额度，使容量有固定Status。
  std::size_t longest=0;for(const auto& row:rows.GetArray()){current(deadline);const auto bytes=json_count(row);
   require(bytes<=1048576,ErrorCode::Backpressure,"qmt_event_query_work_limit");longest=(std::max)(longest,bytes);}
  const auto matcher_base=qsum({128,query_text_bytes(query),qt(e),4096});
  const auto matcher_peak=qadd(matcher_base,(std::max)(qmul(2,qt(longest)),qadd(qt(longest),4096)));
  require(matcher_peak<=ml.max_work_bytes,ErrorCode::Backpressure,"qmt_event_query_work_limit");
  const auto remark=optional(selected,account_fields::remark),order_ref=optional(selected,account_fields::order_ref);
  scalar(remark);scalar(order_ref);
  const auto r=remark?json_count(*remark):4,o=order_ref?json_count(*order_ref):4;
  // 固定表只列真实逻辑对象/元素；allocator树链接、arena余量另归原解析硬界。
  // private State在本friend函数中取实际sizeof，测试独立逐项核对。
  using SeenEntry=std::pair<const std::string,std::pair<std::string,std::size_t>>;
  using ReverseEntry=std::pair<const std::string,std::string>;
  using CacheEntry=std::pair<const std::string,CachedLookup>;
  const auto fixed_bytes=qsum({sizeof(IdentityTicket),sizeof(IdentityPlanData),sizeof(EventQuerySources),
   sizeof(QmtAccountIdentityCandidate),sizeof(QmtAccountIdentityPlan),sizeof(QmtAccountIdentityResolved),
   sizeof(QmtAccountIdentityCandidate::State),sizeof(QmtAccountIdentityPlan::State),sizeof(QmtAccountIdentityResolved::State),
   sizeof(QmtAccountIdentityBegin),sizeof(QmtAccountIdentityResult),sizeof(QmtTradeEventPage),sizeof(QmtAccountResult),2*sizeof(Group),sizeof(CacheEntry),
   sizeof(QmtIdentityBrokerProof),sizeof(QmtTradeOrderReference),sizeof(QmtTradeLookup),sizeof(QmtTradeLookupResult),
   sizeof(QmtTradeEventSource)*2,sizeof(SeenEntry),admitted.stage==2?sizeof(ReverseEntry):0,
   sizeof(std::size_t),sizeof(AccountCanonicalRecord),3*sizeof(std::string),
   sizeof(wtp::WTSArray),sizeof(wtp::WTSObject*),admitted.stage==1?sizeof(wtp::WTSOrderInfo):sizeof(wtp::WTSTradeInfo),
   2*sizeof(AccountRowInspection),2*sizeof(AccountSelectedRowBatch),sizeof(AccountBatch),sizeof(AccountBatchMetadata),
   sizeof(rapidjson::Document)+sizeof(AccountBatchMetadata)+alignof(rapidjson::Document)+alignof(AccountBatchMetadata),
   // qdata/B/profile3；helper native/request/B/profile/source5；canonical准入2；
   // inspection row1、金融view1、canonical key1、same_source1、identity view1。
   (3+5+2+1+1+1+1+1)*sizeof(rapidjson::Document),6*sizeof(V),
   sizeof(std::map<std::string,std::pair<std::string,std::size_t>>),sizeof(std::map<std::string,std::string>),sizeof(std::map<std::string,CachedLookup>),
   sizeof(std::vector<const char*>)+(admitted.stage==1?14:12)*sizeof(const char*),
   sizeof(rapidjson::StringBuffer)+sizeof(rapidjson::Writer<rapidjson::StringBuffer>),
   sizeof(IdentityCountingOutput)+sizeof(rapidjson::Writer<IdentityCountingOutput>),
   sizeof(std::vector<unsigned char>)+4*sizeof(void*),
   sizeof(AdmittedIdentityEvent),sizeof(AccountEventMatchResult),sizeof(EventQueryWork),
   10*sizeof(std::string),admitted.stage==2?4*sizeof(std::string)+9:sizeof(std::string)});
  const auto work=event_query_work(input,query,binding,limits,admitted.descriptor,admitted.stage,e,json_count(event),s,r,o,fixed_bytes);
  work_fits(work.need,limits);
  const auto event_raw=json_text(payload);
  current(deadline);const auto matched=match_account_event_row(admitted.stage,event_raw,query,binding,ml);current(deadline);
  require(matched.kind!=AccountEventMatchKind::InvalidEvent&&matched.kind!=AccountEventMatchKind::InvalidQuery
   &&matched.kind!=AccountEventMatchKind::NotRequired,ErrorCode::InvalidInput,"qmt_event_query_facts_invalid");
  require(matched.kind==AccountEventMatchKind::Matched&&matched.row_index==query_row_index,
   ErrorCode::Conflict,"qmt_event_query_match_failed");
  const auto et=full_token(optional(payload,account_fields::remark)),st=full_token(remark);
  require(et.empty()||st.empty()||et==st,ErrorCode::Conflict,"qmt_event_query_token_conflict");
  auto sources=std::make_shared<EventQuerySources>(limits,work.need,work.identity_view);
  auto& ep=sources->event;ep.source=input.source;ep.original_bounds=bounds;ep.event_index=event_index;
  ep.sequence=member(event,"sequence").GetUint64();ep.kind=admitted.kind;ep.page_json=input.page_json;
  ep.read_profile_body=input.read_profile_body;ep.read_result_capacity=input.read_result_capacity;
  ep.admitted_event_page_capacity=input.admitted_event_page_capacity;
  ep.derived_page_sha256=signed_http_sha256(input.page_json);ep.derived_event_sha256=signed_http_sha256(json_text(event));
  auto& qp=sources->query;qp.original_query=query;qp.original_row_index=query_row_index;qp.original_row_count=rows.Size();
  qp.derived_row_sha256=signed_http_sha256(json_text(selected));
  require(ep.derived_page_sha256.size()==64&&ep.derived_event_sha256.size()==64&&qp.derived_row_sha256.size()==64,
   ErrorCode::Unavailable,"qmt_account_identity_hash_unavailable");
  auto ticket=std::make_shared<IdentityTicket>();ticket->owner=std::this_thread::get_id();ticket->deadline=deadline.end;
  ticket->stage=admitted.stage;ticket->limits=limits.identity;ticket->account=binding.account;ticket->original_session=input.source.session_id;
  ticket->event_query_sources=sources;
  auto data=std::make_shared<IdentityPlanData>();data->ticket=ticket;data->source_kind=IdentitySourceKind::EventQuery;
  data->event_provenance=std::shared_ptr<const QmtTradeEventProvenance>(sources,&sources->event);
  data->transport.CopyFrom(qbinding,data->transport.GetAllocator());
  current(deadline);
  auto financial=map_shm_account_row_v2(admitted.stage,query,query_row_index,binding,base,{1,limits.identity.max_total_bytes});
  current(deadline);build_selected_group(admitted.stage,financial,rows,data->rows,data->groups,deadline);
  require(financial.batch.canonical_records.size()==1,ErrorCode::InvalidInput,"qmt_account_identity_mapping_invalid");
  charge_batch(financial.batch,budget);budget.add(financial.batch.canonical_bytes);
  budget.add(event_group_index_bytes);budget.add(qr.data_json.size());
  ticket->request_id=financial.batch.request_id;ticket->result_sha=financial.batch.result_sha;
  require(ticket->account.size()<=63&&ticket->request_id.size()<=36&&ticket->result_sha.size()<=64&&ticket->original_session.size()<=128,
   ErrorCode::InvalidInput,"qmt_event_query_ticket_invalid");
  ticket->max_rows=1;ticket->initial_total=budget.total;ticket->output_count=1;
  out.candidate=std::unique_ptr<QmtAccountIdentityCandidate>(new QmtAccountIdentityCandidate);
  out.candidate->state_->batch=std::move(financial.batch);out.candidate->state_->data=data;
  out.plan=std::unique_ptr<QmtAccountIdentityPlan>(new QmtAccountIdentityPlan);out.plan->state_->data=data;
  current(deadline);out.status={};
 }catch(IdentityFailure& failure){out.candidate.reset();out.plan.reset();out.status=std::move(failure.status);}
 catch(const std::bad_alloc&){out.candidate.reset();out.plan.reset();fixed_status(out.status,ErrorCode::IoError);}
 // 结构异常已经形成；此出口只写固定分类，避免构造诊断字符串再次分配并逃逸。
 catch(const std::exception&){out.candidate.reset();out.plan.reset();fixed_status(out.status,ErrorCode::InvalidInput);}
 catch(...){out.candidate.reset();out.plan.reset();fixed_status(out.status,ErrorCode::IoError);}
 return out;
}

std::unique_ptr<QmtAccountIdentityResolved> resolve_qmt_account_identity(
 std::unique_ptr<QmtAccountIdentityPlan> plan,QmtHostTradeClient& trade)
{
 std::unique_ptr<QmtAccountIdentityResolved> result(new QmtAccountIdentityResolved);
 auto& out=*result->state_;
 try {
  require(plan&&plan->state_&&plan->state_->data&&plan->state_->data->ticket,
   ErrorCode::InvalidInput,"qmt_account_identity_plan_invalid");
  out.data=plan->state_->data;
  const auto& ticket=*out.data->ticket;
  SignedHttpDeadline deadline(ticket.deadline);current(deadline);
  PayloadBudget budget(ticket.limits);budget.add(ticket.initial_total);
  const auto stage=ticket.stage;const auto max_rows=ticket.max_rows;
  const auto& transport=out.data->transport;
  const bool event_query=out.data->source_kind==IdentitySourceKind::EventQuery;
  if(event_query){const auto& s=*ticket.event_query_sources;work_fits(s.reserved_work_bytes,s.budget);out.broker_proofs.resize(1);}
  out.groups=out.data->groups;auto& groups=out.groups;
  current(deadline);const auto prepared=trade.prepare(deadline);
  if(!prepared.ok())throw IdentityFailure{prepared};
  const auto source=trade.event_source();same_source(source,transport,ticket.original_session);current(deadline);
  std::map<std::string,CachedLookup> cache;
  for(auto& group:groups){
   current(deadline);
   std::string token;
   if(event_query)token=full_token(group.remark);
   else if(group.remark&&group.remark->IsString())token=text(*group.remark);
   if(token.empty()||!valid_qmt_sdk_order_token(token)){
    group.classification="external";group.reason="source_remark_not_sdk_token";continue;
   }
   auto found=cache.find(token);
   if(found==cache.end()){
    require(cache.size()<max_rows,ErrorCode::Backpressure,"qmt_account_identity_lookup_limit");
    budget.add(token.size());QmtTradeLookup query;
    query.kind=QmtTradeLookupKind::SdkToken;query.sdk_user_order_id=token;
    auto lookup=trade.lookup(query,deadline);current(deadline);
    // 每个token原回复只在返回数组留一份；私有reference只在本轮提取已核事实。
    budget.lookup_bytes(lookup.response_body.size());CachedLookup saved;
    saved.response_index=out.lookup_responses.size();
    saved.sha=signed_http_sha256(lookup.response_body);
    require(saved.sha.size()==64,ErrorCode::Unavailable,"qmt_account_identity_hash_unavailable");
    out.lookup_responses.push_back(std::move(lookup.response_body));
    if(lookup.not_found&&lookup.response_complete&&lookup.http_status==404)saved.not_found=true;
    else {
     if(!lookup.status.ok())throw IdentityFailure{lookup.status};
     require(lookup.response_complete&&lookup.reference!=nullptr,ErrorCode::IoError,"qmt_account_identity_lookup_incomplete");
     saved.has_reference=true;saved.facts=lookup.reference->facts();
     saved.broker=lookup.reference->broker_order_id();saved.association_error=lookup.reference->association_error();
     if(event_query){
      auto& proof=out.broker_proofs[0];const auto& f=saved.facts;
      proof.kind=f.broker_proof_kind;proof.dispatched=f.dispatched;proof.has_broker_proof=f.has_broker_proof;
      proof.has_event=f.source_sequence>0&&f.source_event_sha256.size()==64;
      proof.has_query=f.query_request_id.size()==36&&f.query_result_sha256.size()==64;
      if(proof.has_event){proof.event_source=lookup.reference->source();proof.source_sequence=f.source_sequence;proof.source_event_sha256=f.source_event_sha256;}
      if(proof.has_query){proof.query_request_id=f.query_request_id;proof.query_result_sha256=f.query_result_sha256;proof.query_row_index=f.query_row_index;}
     }
    }
    found=cache.emplace(std::move(token),std::move(saved)).first;
   }
   const auto& saved=found->second;group.has_lookup=true;
   group.lookup_index=saved.response_index;group.lookup_sha=saved.sha;
   if(event_query){out.broker_proofs[0].lookup_response_index=saved.response_index;out.broker_proofs[0].lookup_sha256=saved.sha;}
   if(saved.not_found){group.classification="external";group.reason="host_unknown_order";continue;}
   const auto& facts=saved.facts;
   require(saved.has_reference&&facts.account_id==ticket.account&&facts.account_type=="stock"
    &&facts.sdk_user_order_id==found->first&&facts.symbol==group.symbol&&!facts.binding_id.empty(),
    ErrorCode::Conflict,"qmt_account_identity_original_conflict");
   require(saved.association_error.empty(),ErrorCode::Conflict,"qmt_account_identity_association_conflict");
   if(facts.has_broker_proof)require(saved.broker==group.broker,
    ErrorCode::Conflict,"qmt_account_identity_broker_conflict");
   if(!facts.dispatched||!facts.has_broker_proof){
    group.classification="unresolved";group.reason=facts.dispatched?"broker_proof_missing":"original_not_dispatched";continue;
   }
   // lookup只发布已完整准入的私有reference。查询观察有自己的请求/结果来源，
   // 不用事件序号或session冒充它；历史证明解释身份，当前可撤仍由client/Host核实。
   const bool event_proof=facts.broker_proof_kind==QmtTradeBrokerProofKind::Event
    &&facts.source_sequence>0&&facts.source_event_sha256.size()==64;
   const bool query_proof=facts.broker_proof_kind==QmtTradeBrokerProofKind::AccountQuery
    &&facts.query_request_id.size()==36&&facts.query_result_sha256.size()==64
    &&facts.query_row_index<4096;
   require(event_proof||query_proof,
    ErrorCode::Conflict,"qmt_account_identity_proof_invalid");
   require(slot(facts.entrust_id)&&!facts.entrust_id.empty()&&slot(facts.user_tag)&&!facts.user_tag.empty(),
    ErrorCode::Conflict,"qmt_account_identity_slot_invalid");
   group.classification="owned";group.reason="original_insert_and_broker_proof";
   if(stage==1)group.entrust_id=facts.entrust_id;
   group.user_tag=facts.user_tag;
  }
  for(std::size_t i=0;i<groups.size();++i){
   current(deadline);const auto& group=groups[i];rapidjson::Document view;view.SetObject();auto& allocator=view.GetAllocator();
   const bool event_source=out.data->source_kind==IdentitySourceKind::Event;
   if(event_query)require(qt(ticket.event_query_sources->identity_view_bound)<=ticket.limits.max_identity_view_bytes,ErrorCode::Backpressure,"qmt_account_identity_view_limit");
   add(view,"schema_version",event_query?"qmt.wt-event-query-identity.v1":event_source?"qmt.wt-event-identity.v1":"qmt.wt-order-identity.v1",allocator);
   view.AddMember("stage",stage,allocator);view.AddMember("output_index",static_cast<std::uint64_t>(i),allocator);
   if(event_source){
    const auto& provenance=*out.data->event_provenance;
    view.AddMember("event_index",static_cast<std::uint64_t>(provenance.event_index),allocator);
    view.AddMember("sequence",provenance.sequence,allocator);add(view,"kind",provenance.kind,allocator);
    add(view,"derived_page_sha256",provenance.derived_page_sha256,allocator);
    add(view,"derived_event_sha256",provenance.derived_event_sha256,allocator);
   }else if(event_query){event_query_view_sources(view,*ticket.event_query_sources,out.broker_proofs[0],ticket.result_sha,allocator);}
   else {add(view,"request_id",ticket.request_id,allocator);add(view,"result_sha256",ticket.result_sha,allocator);}
   if(stage==1){add(view,"order_id",group.broker,allocator);view.AddMember("ref_order",V(),allocator);view.AddMember("trade_id",V(),allocator);}
   else {view.AddMember("order_id",V(),allocator);add(view,"ref_order",group.broker,allocator);add(view,"trade_id",group.trade_id,allocator);}
   source_scalar(view,account_fields::remark,group.remark,allocator);source_scalar(view,account_fields::order_ref,group.order_ref,allocator);
   add(view,"classification",group.classification,allocator);add(view,"entrust_id",group.entrust_id,allocator);
   add(view,"user_tag",group.user_tag,allocator);add(view,"reason",group.reason,allocator);
   if(group.has_lookup){view.AddMember("lookup_response_index",static_cast<std::uint64_t>(group.lookup_index),allocator);add(view,"lookup_sha256",group.lookup_sha,allocator);}
   else {view.AddMember("lookup_response_index",V(),allocator);view.AddMember("lookup_sha256",V(),allocator);}
   if(event_query)require(json_count(view)<=ticket.event_query_sources->identity_view_bound,ErrorCode::Backpressure,"qmt_account_identity_view_limit");
   auto raw=json_text(view);budget.view_bytes(raw.size());out.identity_views.push_back(std::move(raw));
  }
  current(deadline);
  // 重新观察Host当前绑定，防止lookup期间切代被客户端旧pin掩盖；仍消费原D。
  const auto confirmed=trade.prepare(deadline);
  if(!confirmed.ok())throw IdentityFailure{confirmed};
  same_source(trade.event_source(),transport,
   ticket.original_session.empty()?source.session_id:ticket.original_session);current(deadline);
  out.total=budget.total;out.lookup=budget.lookup;out.views=budget.views;
  out.status={};
 }
 catch(IdentityFailure& failure){out.status=std::move(failure.status);}
 catch(const std::bad_alloc&){fixed_status(out.status,ErrorCode::IoError);}
 catch(const std::exception&){if(out.data&&out.data->source_kind==IdentitySourceKind::EventQuery)fixed_status(out.status,ErrorCode::InvalidInput);else out.status={ErrorCode::InvalidInput,"qmt_account_identity_mapping_failed"};}
 catch(...){if(out.data&&out.data->source_kind==IdentitySourceKind::EventQuery)fixed_status(out.status,ErrorCode::IoError);else out.status={ErrorCode::IoError,"qmt_account_identity_failed"};}
 return result;
}

QmtAccountIdentityResult finish_qmt_account_identity(
 std::unique_ptr<QmtAccountIdentityCandidate>& candidate,
 std::unique_ptr<QmtAccountIdentityResolved>& resolved)
{
 QmtAccountIdentityResult out;
 // 这里只借用纯值来源；Candidate优先，缺Candidate时才由Resolved识别。
 // 双空没有来源，保持旧非法句柄诊断；识别过程不复制或释放WT对象。
 const auto* origin=candidate&&candidate->state_&&candidate->state_->data?candidate->state_->data.get():
  resolved&&resolved->state_&&resolved->state_->data?resolved->state_->data.get():nullptr;
 const bool event_query=origin&&origin->source_kind==IdentitySourceKind::EventQuery;
 if(!candidate||!candidate->state_||!candidate->state_->data){
  if(event_query)fixed_status(out.status,ErrorCode::InvalidInput);
  else out.status={ErrorCode::InvalidInput,"qmt_account_identity_candidate_invalid"};
  return out;
 }
 const auto& data=candidate->state_->data;
 const auto& ticket=*data->ticket;
 // 错误线程和错票据属于交接错误，两个句柄都留给原owner重试。
 // 此处只读纯值，不触碰或释放任何WT对象；调用者负责句柄表的串行所有权。
 if(std::this_thread::get_id()!=ticket.owner){
  if(event_query)fixed_status(out.status,ErrorCode::Conflict);
  else out.status={ErrorCode::Conflict,"qmt_account_identity_owner_required"};
  return out;
 }
 if(!resolved||!resolved->state_||!resolved->state_->data){
  if(event_query)fixed_status(out.status,ErrorCode::InvalidInput);
  else out.status={ErrorCode::InvalidInput,"qmt_account_identity_resolution_missing"};
  return out;
 }
 if(resolved->state_->data->ticket.get()!=data->ticket.get()){
  if(event_query)fixed_status(out.status,ErrorCode::Conflict);
  else out.status={ErrorCode::Conflict,"qmt_account_identity_ticket_mismatch"};
  return out;
 }
 try {
  auto& value=*resolved->state_;
  out.event_provenance=data->event_provenance;
  if(ticket.event_query_sources){
   const auto& sources=ticket.event_query_sources;work_fits(sources->reserved_work_bytes,sources->budget);
   out.query_provenance=std::shared_ptr<const QmtEventQueryProvenance>(sources,&sources->query);
   out.broker_proofs=std::move(value.broker_proofs);
  }
  out.identity_views=std::move(value.identity_views);out.lookup_responses=std::move(value.lookup_responses);
  SignedHttpDeadline deadline(ticket.deadline);current(deadline);
  if(!value.status.ok())throw IdentityFailure{value.status};
  auto& batch=candidate->state_->batch;const auto stage=ticket.stage;
  const auto& groups=value.groups;
  require(batch.array&&batch.array->size()==ticket.output_count
   &&groups.size()==((stage==1||stage==2)?ticket.output_count:0)
   &&out.identity_views.size()==groups.size(),
   ErrorCode::InvalidInput,"qmt_account_identity_mapping_invalid");
  // 预算从begin累计到resolve，finish不重新授予任何子额度。
  require(value.total>=ticket.initial_total&&value.total<=ticket.limits.max_total_bytes
   &&value.lookup<=ticket.limits.max_lookup_bytes&&value.views<=ticket.limits.max_identity_view_bytes,
   ErrorCode::Backpressure,"qmt_account_identity_payload_limit");
  // 同owner、同票据、整批通过后统一写槽，失败由原owner销毁候选。
  for(std::size_t i=0;i<groups.size();++i){
   const auto& group=groups[i];
   if(stage==1){auto order=batch.array->at<wtp::WTSOrderInfo>(static_cast<unsigned>(i));
    order->setEntrustID(group.entrust_id.c_str());order->setUserTag(group.user_tag.c_str());}
   else batch.array->at<wtp::WTSTradeInfo>(static_cast<unsigned>(i))->setUserTag(group.user_tag.c_str());
  }
  current(deadline);out.batch=std::move(batch);out.status={};
 }
 catch(IdentityFailure& failure){out.status=std::move(failure.status);}
 catch(const std::bad_alloc&){fixed_status(out.status,ErrorCode::IoError);}
 catch(const std::exception&){if(event_query)fixed_status(out.status,ErrorCode::InvalidInput);else out.status={ErrorCode::InvalidInput,"qmt_account_identity_mapping_failed"};}
 catch(...){if(event_query)fixed_status(out.status,ErrorCode::IoError);else out.status={ErrorCode::IoError,"qmt_account_identity_failed"};}
 // 匹配的终态单次消费；WT释放和成功数组移交都只发生在原owner。
 candidate.reset();resolved.reset();
 return out;
}

QmtAccountIdentityResult map_shm_account_identity_batch(unsigned stage,
 const QmtAccountResult& input,const AccountBinding& binding,wtp::IBaseDataMgr* base,
 QmtHostTradeClient& trade,const QmtAccountIdentityBudget& limits,SignedHttpDeadline& deadline)
{
 QmtAccountIdentityResult out;
 try {
  auto begun=begin_qmt_account_identity(stage,input,binding,base,limits,deadline);
  if(!begun.status.ok()){out.status=begun.status;return out;}
  auto resolved=resolve_qmt_account_identity(std::move(begun.plan),trade);
  return finish_qmt_account_identity(begun.candidate,resolved);
 }
 catch(const std::bad_alloc&){fixed_status(out.status,ErrorCode::IoError);}
 catch(const std::exception&){out.status={ErrorCode::InvalidInput,"qmt_account_identity_mapping_failed"};}
 catch(...){out.status={ErrorCode::IoError,"qmt_account_identity_failed"};}
 return out;
}
}}
