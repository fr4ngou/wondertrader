#include "AccountEventMatch.h"
#include "JsonBoundary.h"
#include <algorithm>
#include <initializer_list>
#include <type_traits>

namespace guanheng { namespace bootstrap {
namespace {
using F=AccountFactField;
constexpr std::size_t hard_bytes=64u*1024u*1024u, fixed_bytes=128;
static_assert(std::is_trivially_copyable<AccountEventMatchResult>::value,"match result must own no payload");
static_assert(sizeof(AccountEventMatchResult)<=fixed_bytes,"match fixed payload reserve");

std::size_t plus(std::size_t used,std::size_t add,std::size_t cap){
 check(used<=cap&&add<=cap-used,"事件补查匹配字节容量超限");return used+add;
}
std::size_t string_bytes(std::size_t used,const std::string& value,std::size_t cap){
 used=plus(used,value.size(),cap);return plus(used,1,cap);
}
std::size_t query_bytes(const QmtAccountResult& query,std::size_t cap){
 const auto& b=query.bound;const auto& r=b.result;const auto& receipt=b.receipt;
 std::size_t used=0;
 for(const auto* value:{&r.status.reason,&r.data_json,&r.envelope_json,&r.request_id,&r.operation_id,
   &receipt.binding_json,&receipt.request_body,&receipt.read_profile_body,&receipt.retention_ticket_json,&b.native_result_json,&query.remote_error_code})
  used=string_bytes(used,*value,cap);
 return used;
}
std::size_t inspection_cap(std::size_t used,std::size_t cap){
 check(used<cap,"事件补查检查预留不足");return std::min<std::size_t>(4096,cap-used);
}
// 使用同一Writer计数后才分配单行文本；不复制JSON编码或金融字段规则。
struct CountingOutput {
 using Ch=char;std::size_t count=0,cap;
 explicit CountingOutput(std::size_t limit):cap(limit){}
 void Put(char){check(count<cap,"事件补查单行序列化容量超限");++count;}
 void Flush(){}
};
std::size_t encoded_bytes(const rapidjson::Value& row,std::size_t cap){
 CountingOutput output(cap);rapidjson::Writer<CountingOutput> writer(output);
 check(row.Accept(writer),"事件补查单行JSON编码失败");return output.count;
}
std::uint64_t fields(std::initializer_list<F> list){
 std::uint64_t out=0;for(auto field:list)out|=account_fact_bit(field);return out;
}
// 只比较两个inspection已经判为valid的值；optional unknown不产生补值或冲突。
std::uint64_t difference(const AccountRowInspection& a,const AccountRowInspection& b,std::uint64_t mask){
 const auto common=a.valid&b.valid&mask;std::uint64_t out=0;
 auto compare=[&](F field,const auto& left,const auto& right){
  const auto bit=account_fact_bit(field);if((common&bit)&&left!=right)out|=bit;
 };
 const auto& x=a.facts;const auto& y=b.facts;
 compare(F::Code,x.code,y.code);compare(F::Exchange,x.exchange,y.exchange);
 compare(F::Account,x.account,y.account);compare(F::Currency,x.currency,y.currency);
 compare(F::Order,x.order,y.order);compare(F::Trade,x.trade,y.trade);
 compare(F::Side,x.side,y.side);compare(F::Date,x.date,y.date);compare(F::Time,x.time,y.time);
 compare(F::Quantity,x.quantity,y.quantity);compare(F::Filled,x.filled,y.filled);
 compare(F::Remaining,x.remaining,y.remaining);compare(F::State,x.state,y.state);
 compare(F::Price,x.price,y.price);compare(F::Amount,x.amount,y.amount);compare(F::Cancel,x.cancel,y.cancel);
 return out;
}
}
AccountEventMatchResult match_account_event_row(unsigned stage,const std::string& event_raw,
 const QmtAccountResult& query,const AccountBinding& binding,const AccountEventMatchLimits& limits){
 check((stage==1||stage==2)&&limits.max_event_bytes>=1&&limits.max_event_bytes<=protocol::fixture_bytes
  &&limits.max_query_bytes>=1&&limits.max_query_bytes<=hard_bytes
  &&limits.max_rows>=1&&limits.max_rows<=protocol::max_rows&&limits.max_rows<=binding.row_limit
  &&limits.max_work_bytes>=1&&limits.max_work_bytes<=hard_bytes,"事件补查匹配参数非法");
 check(event_raw.size()<=limits.max_event_bytes,"事件补查原事件容量超限");
 const auto& input=query.bound.result;
 // 这是调用者必须满足的Core成功前提；完整账户/receipt认证仍归原Core与P8。
 check(input.status.ok()&&input.http_status==200&&input.terminal&&input.remote_ok
  &&!input.data_json.empty()&&!query.bound.native_result_json.empty()&&query.remote_error_code.empty(),
  "事件补查尚无Core成功结果");
 AccountEventMatchResult result;
 result.query_bytes=query_bytes(query,limits.max_query_bytes);
 auto used=plus(fixed_bytes,result.query_bytes,limits.max_work_bytes);
 used=string_bytes(used,event_raw,limits.max_work_bytes);
 auto event=inspect_account_row(stage,event_raw,binding,
  {limits.max_event_bytes,inspection_cap(used,limits.max_work_bytes)});
 used=plus(used,event.output_bytes,limits.max_work_bytes);result.peak_work_bytes=used;
 result.event_missing=event.missing;result.event_invalid=event.invalid;result.event_relations=event.relations;
 if(event.kind==AccountInspectionKind::Invalid){result.kind=AccountEventMatchKind::InvalidEvent;return result;}
 if(event.kind==AccountInspectionKind::Complete){result.kind=AccountEventMatchKind::NotRequired;return result;}
 if(!event.locator_complete){result.kind=AccountEventMatchKind::EventLocatorMissing;return result;}
 rapidjson::Document data;parse_json(data,input.data_json,protocol::fixture_bytes);
 check(data.IsObject()&&data.HasMember("rows")&&data["rows"].IsArray(),"事件补查查询rows结构非法");
 const auto& rows=data["rows"];
 check(rows.Size()<=limits.max_rows,"事件补查查询行容量超限");result.query_rows=rows.Size();
 const auto locator=stage==1?fields({F::Code,F::Exchange,F::Order})
  :fields({F::Code,F::Exchange,F::Order,F::Trade,F::Date});
 const auto immutable=stage==1?fields({F::Code,F::Exchange,F::Account,F::Currency,F::Order,F::Side,
  F::Date,F::Time,F::Quantity,F::Price}):std::uint64_t{65535};
 std::size_t selected=static_cast<std::size_t>(-1);bool incomplete=false;
 for(rapidjson::SizeType i=0;i<rows.Size();++i){
  // 原源/事件与两份inspection共存；本轮串与inspection在下一轮前真实析构。
  const auto length=encoded_bytes(rows[i],std::min(protocol::fixture_bytes,limits.max_work_bytes-used));
  const auto row_used=plus(plus(used,length,limits.max_work_bytes),1,limits.max_work_bytes);
  // json_text返回string时原StringBuffer仍在；分配前核两份真实文本的并存峰值。
  const auto serialize_peak=plus(plus(row_used,length,limits.max_work_bytes),1,limits.max_work_bytes);
  result.peak_work_bytes=std::max(result.peak_work_bytes,serialize_peak);
  const auto row_cap=inspection_cap(row_used,limits.max_work_bytes);
  const auto raw=json_text(rows[i]);check(raw.size()==length,"事件补查序列化长度不一致");
  const auto row=inspect_account_row(stage,raw,binding,{protocol::fixture_bytes,row_cap});
  result.peak_work_bytes=std::max(result.peak_work_bytes,plus(row_used,row.output_bytes,limits.max_work_bytes));
  ++result.scanned_rows;
  if(row.kind==AccountInspectionKind::Invalid){++result.invalid_rows;continue;}
  // 一个已知定位差异足以排除；否则缺任一定位事实保留可能匹配的不确定性。
  if(difference(event,row,locator))continue;
  if(!row.locator_complete){++result.uncertain_rows;continue;}
  ++result.matched_rows;selected=i;
  result.conflict_fields|=difference(event,row,immutable);
  if(row.kind!=AccountInspectionKind::Complete)incomplete=true;
 }
 // 完整扫描后发布唯一结论；相同原行重复也不能由本函数去重为一份。
 if(result.invalid_rows)result.kind=AccountEventMatchKind::InvalidQuery;
 else if(result.uncertain_rows)result.kind=AccountEventMatchKind::UncertainQuery;
 else if(result.matched_rows>1)result.kind=AccountEventMatchKind::Ambiguous;
 else if(result.matched_rows==0)result.kind=AccountEventMatchKind::NotMatched;
 else if(result.conflict_fields)result.kind=AccountEventMatchKind::Conflict;
 else if(incomplete)result.kind=AccountEventMatchKind::IncompleteMatch;
 else{result.kind=AccountEventMatchKind::Matched;result.row_index=selected;}
 return result;
}
}}
