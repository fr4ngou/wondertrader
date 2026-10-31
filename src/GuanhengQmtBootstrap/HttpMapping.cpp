#include "HttpMapping.h"
#include "JsonBoundary.h"
#include "ViewSchemaV2.h"
namespace guanheng { namespace bootstrap {
namespace {
using V=rapidjson::Value;
const V& get(const V& v,const char* key){check(v.IsObject()&&v.HasMember(key),"HTTP来源缺少必需字段");return v[key];}
std::string str(const V& v,const char* k,std::size_t cap=63){const auto& x=get(v,k);check(x.IsString()&&x.GetStringLength()>0&&x.GetStringLength()<=cap,"HTTP字段文本类型或长度错误");std::string s(x.GetString(),x.GetStringLength());for(std::size_t i=0;i<s.size();++i){unsigned char c=s[i];check(c>=32&&c!=127&&!(c==0xc2&&i+1<s.size()&&static_cast<unsigned char>(s[i+1])>=0x80&&static_cast<unsigned char>(s[i+1])<=0x9f),"HTTP标识含控制字符");}return s;}
bool equal(const V& v,const char* k,const std::string& s){return v.IsObject()&&v.HasMember(k)&&v[k].IsString()&&s==std::string(v[k].GetString(),v[k].GetStringLength());}
}
const char* transport_error_name(ErrorCode c)noexcept{switch(c){case ErrorCode::Ok:return "Ok";case ErrorCode::Unavailable:return "Unavailable";case ErrorCode::InvalidInput:return "InvalidInput";case ErrorCode::NotSupported:return "NotSupported";case ErrorCode::Pending:return "Pending";case ErrorCode::Timeout:return "Timeout";case ErrorCode::Backpressure:return "Backpressure";case ErrorCode::StaleSession:return "StaleSession";case ErrorCode::Conflict:return "Conflict";case ErrorCode::SubmissionUnknown:return "SubmissionUnknown";default:return "IoError";}}
HttpBatch map_http_batch(unsigned stage,const JsonResult& result,const SourceSession& session,const HttpBinding& binding,wtp::IBaseDataMgr* base){
 using namespace fields;check(stage<4&&base,"HTTP批次或基础资料非法");check(result.status.ok()&&result.http_status==200&&result.terminal&&result.remote_ok,"HTTP查询尚未取得成功终态");
 rapidjson::Document d;parse_json(d,result.envelope_json,protocol::envelope_bytes);check(equal(d,"request_id",result.request_id)&&!result.request_id.empty()&&equal(d,"operation_id",protocol::operation)&&result.operation_id==protocol::operation,"HTTP结果关联错误");
 check(get(d,"ok").IsBool()&&d["ok"].GetBool(),"HTTP远端失败");const auto& o=get(d,"observation");check(equal(o,"schema_version",protocol::schema),"HTTP观察版本不支持");const auto& q=get(o,"query");check(equal(q,"account_type","stock")&&equal(q,"datatype",protocol::datatypes[stage])&&equal(q,"scope","account")&&get(q,"strategy_name").IsNull(),"HTTP查询范围不符");
 const auto& rows=get(d,"data");check(rows.IsArray()&&rows.Size()<=binding.row_limit&&(stage!=3||rows.Size()==1),"HTTP记录类型或数量非法");const auto& complete=get(o,"completeness");check(get(complete,"complete").IsBool()&&complete["complete"].GetBool()&&get(complete,"truncated").IsBool()&&!complete["truncated"].GetBool()&&get(complete,"row_count").IsUint()&&complete["row_count"].GetUint()==rows.Size()&&equal(complete,"reason","complete"),"HTTP查询不完整");
 const auto& source=get(o,"source");check(equal(source,"agent_id",session.instance_id)&&equal(source,"qmt_session_id",session.session_id)&&get(source,"generation").IsUint64()&&source["generation"].GetUint64()==session.generation&&equal(source,"account_id",binding.account)&&equal(source,"account_environment",binding.environment),"HTTP账户或会话来源改变");const auto& td=get(o,"trading_date");check(get(td,"value").IsNull()&&equal(td,"source","unavailable"),"HTTP交易日契约不符");
 AccountBatchMetadata metadata;metadata.source=json_text(source);metadata.request_id=result.request_id;
 metadata.result_sha=str(d,"result_sha256",64);check(metadata.result_sha.size()==64&&metadata.result_sha.find_first_not_of("0123456789abcdef")==std::string::npos,"HTTP结果摘要格式非法");
 const auto& ex=get(o,"execution");metadata.started=str(ex,"started_at",32);metadata.finished=str(ex,"completed_at",32);
 return map_account_rows(stage,rows,binding,base,metadata,fields::view_version);
}
}}
