#include "ShmAccountMapping.h"
#include "JsonBoundary.h"
#include "GuanhengCommon/BoundedSignedHttp.h"
#include "GuanhengCommon/QmtBoundReadCore.h"
#include "GuanhengCommon/QmtHostCodec.h"
#include "GuanhengCommon/QmtAccountFields.h"

namespace guanheng { namespace bootstrap {
namespace {
using V=rapidjson::Value;
constexpr const char* datatypes[]={"position","order","deal","account"};
const V& member(const V& value,const char* key)
{
 check(value.IsObject()&&value.HasMember(key),"共享内存账户metadata缺少字段");
 return value[key];
}
std::string text(const V& value,const char* key,std::size_t limit)
{
 const auto& item=member(value,key);
 check(item.IsString()&&item.GetStringLength()>0&&item.GetStringLength()<=limit,
  "共享内存账户metadata文本不合格");
 return {item.GetString(),item.GetStringLength()};
}
void parse_value(const std::string& bytes,rapidjson::Document& value,std::size_t limit)
{
 // 共用Core的有界JSON准入，容许QAR码点域产生的UTF-8字符串；不走旧HTTP的更窄parser。
 check(!bytes.empty()&&parse_bounded_qmt_json(bytes,value,limit,1048576)&&value.IsObject(),
  "共享内存账户metadata结构不合格");
}
void fixed_query(const V& query,const char* datatype,bool has_strategy)
{
 check(text(query,"account_type",5)=="stock"&&text(query,"datatype",8)==datatype
  &&text(query,"scope",7)=="account","共享内存账户查询阶段或范围不符");
 if(has_strategy)check(member(query,"strategy_name").IsNull(),"共享内存账户查询含策略过滤");
}
void add(V& object,const char* key,const std::string& value,rapidjson::Document::AllocatorType& allocator)
{
 object.AddMember(V(key,allocator),V(value.data(),static_cast<unsigned>(value.size()),allocator),allocator);
}
}

namespace {
// data独立拥有rows生命周期；helper返回后只借用此仍存活owner中的原数组。
struct AdmittedShmRows {rapidjson::Document data;AccountBatchMetadata metadata;};
AdmittedShmRows admit_shm_account_rows(unsigned stage,const QmtAccountResult& input,
 const AccountBinding& binding,wtp::IBaseDataMgr* base,bool identity_projection)
{
 check(stage<4&&base,"共享内存账户阶段或基础资料非法");
 const auto& bound=input.bound;
 const auto& result=bound.result;
 check(result.status.ok()&&result.http_status==200&&result.terminal&&result.remote_ok
  &&!result.data_json.empty()&&!bound.native_result_json.empty()&&input.remote_error_code.empty(),
  "共享内存账户尚未取得成功采用的Core结果");
 check(!binding.account.empty()&&binding.account.size()<=63
  &&(binding.environment=="simulation"||binding.environment=="live")
  &&binding.currency=="CNY"&&binding.profile=="cny_cash_shsz_v1",
  "共享内存账户固定部署绑定不合格");

 AdmittedShmRows admitted;auto& data=admitted.data;
 rapidjson::Document native,request,transport;
 parse_value(result.data_json,data,1048576);
 parse_value(bound.native_result_json,native,2097152);
 parse_value(bound.receipt.request_body,request,65536);
 parse_value(bound.receipt.binding_json,transport,4096);
 check(result.operation_id=="account.trade_detail"&&!result.request_id.empty()
  &&text(request,"operation_id",64)==result.operation_id
  &&text(native,"operation_id",64)==result.operation_id
  &&text(request,"request_id",36)==result.request_id
  &&text(native,"request_id",36)==result.request_id,
  "共享内存账户原请求与结果关联不符");
 const auto& native_ok=member(native,"ok");
 check(native_ok.IsBool()&&native_ok.GetBool(),"共享内存账户原生终态失败");
 check(text(data,"schema_version",64)==(identity_projection?account_fields::identity_schema:account_fields::schema),
  "共享内存账户data版本不符");
 if(identity_projection){
  // 入口仍只接Core成功采用值；此处固定v2适用范围，不能由data反向选择版本。
  const auto& receipt=bound.receipt;
  QmtExpectedAccount expected;expected.account_id=binding.account;
  expected.environment=binding.environment=="live"?QmtAccountEnvironment::Live:QmtAccountEnvironment::Simulation;
  QmtTradeReadDescriptor descriptor;
  check(!receipt.read_profile_body.empty()&&receipt.read_profile_body.size()<=4096
   &&qmt_host_codec::binding(transport,nullptr,"2.0")
   &&signed_http_sha256(receipt.read_profile_body)==text(transport,"capability_sha256",64)
   &&validate_qmt_trade_read_profile(receipt.read_profile_body,receipt.read_result_capacity,expected,descriptor).ok(),
   "共享内存账户v2原profile或绑定不符");
  rapidjson::Document profile;parse_value(receipt.read_profile_body,profile,4096);
  const auto& operation=member(member(profile,"operation_profiles"),"account.trade_detail");
  check(text(operation,"policy_version",8)==account_fields::identity_policy_version
   &&text(request,"policy_id",64)=="qmt.account-read.v1"
   &&text(request,"policy_version",8)==account_fields::identity_policy_version,
   "共享内存账户v2原请求投影不符");
 }
 fixed_query(member(request,"arguments"),datatypes[stage],false);
 fixed_query(member(data,"query"),datatypes[stage],true);
 const auto& actual_binding=member(data,"account_binding");
 check(text(actual_binding,"account_id",63)==binding.account
  &&text(actual_binding,"account_environment",10)==binding.environment
  &&text(actual_binding,"currency",3)==binding.currency
  &&text(actual_binding,"financial_profile",64)==binding.profile
  &&text(actual_binding,"origin",64)=="trusted_bootstrap_argument",
  "共享内存账户实际参数绑定与部署不符");
 const auto& execution=member(data,"execution");
 auto& metadata=admitted.metadata;
 metadata.request_id=result.request_id;
 metadata.result_sha=text(native,"result_sha256",64);
 check(metadata.result_sha.size()==64,"共享内存账户原结果摘要缺失");
 metadata.started=text(execution,"started_at",32);
 metadata.finished=text(execution,"completed_at",32);
 const auto& rows=member(data,"rows");
 check(rows.IsArray(),"共享内存账户记录不是数组");

 // 原receipt.binding_json已由Core验证；只摘要这些原字节，不重编码来替换原认证身份。
 const auto binding_sha=signed_http_sha256(bound.receipt.binding_json);
 check(binding_sha.size()==64,"共享内存账户绑定摘要不可用");
 rapidjson::Document source;source.SetObject();auto& allocator=source.GetAllocator();
 add(source,"kind","qmt_shm_bound",allocator);
 add(source,"account_id",binding.account,allocator);
 add(source,"account_environment",binding.environment,allocator);
 source.AddMember("transport_binding",V(transport,allocator),allocator);
 add(source,"binding_sha256",binding_sha,allocator);
 V broker(rapidjson::kObjectType);
 add(broker,"availability","unknown",allocator);
 broker.AddMember("value",V(),allocator);
 add(broker,"reason","未取得券商登录会话证据",allocator);
 source.AddMember("broker_session",broker,allocator);
 metadata.source=json_text(source);
 return admitted;
}
AccountBatch map_shm_account_batch_impl(unsigned stage,const QmtAccountResult& input,
 const AccountBinding& binding,wtp::IBaseDataMgr* base,bool identity_projection)
{
 auto admitted=admit_shm_account_rows(stage,input,binding,base,identity_projection);
 // UTC及金融行归唯一mapper；完整metadata准入后才创建WT对象。
 return map_account_rows(stage,admitted.data["rows"],binding,base,admitted.metadata,3);
}
}
AccountBatch map_shm_account_batch(unsigned stage,const QmtAccountResult& input,
 const AccountBinding& binding,wtp::IBaseDataMgr* base)
{return map_shm_account_batch_impl(stage,input,binding,base,false);}
AccountBatch map_shm_account_batch_v2(unsigned stage,const QmtAccountResult& input,
 const AccountBinding& binding,wtp::IBaseDataMgr* base)
{return map_shm_account_batch_impl(stage,input,binding,base,true);}
AccountSelectedRowBatch map_shm_account_row_v2(unsigned stage,const QmtAccountResult& input,
 std::size_t row_index,const AccountBinding& binding,wtp::IBaseDataMgr* base,
 const AccountCanonicalLimits& limits)
{
 check(stage==1||stage==2,"共享内存账户选择阶段非法");
 auto admitted=admit_shm_account_rows(stage,input,binding,base,true);
 return map_account_row_at(stage,admitted.data["rows"],row_index,binding,base,admitted.metadata,limits);
}
}}
