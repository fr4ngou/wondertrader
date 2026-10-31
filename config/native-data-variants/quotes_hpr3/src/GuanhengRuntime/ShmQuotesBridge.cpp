// WT外部服务的SHM报价适配：线程/绑定/未知责任沿原Common，不承载交易。
#include "MarketBridge.h"
#include "../GuanhengCommon/QmtHostReadClient.h"
#include "../GuanhengData/QmtTickMapping.h"
#include <rapidjson/document.h>
#include <rapidjson/stringbuffer.h>
#include <rapidjson/writer.h>
#include <chrono>
#include <cmath>
#include <cstring>
#include <memory>
#include <optional>
#include <set>
#include <stdexcept>
#include <thread>

namespace {
using namespace guanheng;
using J=rapidjson::Value;using A=rapidjson::Document::AllocatorType;
constexpr const char* version="guanheng.market.v1";
void text(J& o,const char* k,const std::string& v,A& a){o.AddMember(J(k,a),J(v.data(),static_cast<rapidjson::SizeType>(v.size()),a),a);}
std::string encode(const J& v){rapidjson::StringBuffer b;rapidjson::Writer<rapidjson::StringBuffer>w(b);v.Accept(w);return {b.GetString(),b.GetSize()};}
rapidjson::Document parse(const char* raw,std::size_t maximum){
 if(!raw||!strnlen(raw,maximum+1)||strnlen(raw,maximum+1)>maximum)throw std::invalid_argument("json");
 rapidjson::Document d;d.Parse<rapidjson::kParseIterativeFlag|rapidjson::kParseValidateEncodingFlag|rapidjson::kParseFullPrecisionFlag>(raw);
 if(d.HasParseError()||!d.IsObject())throw std::invalid_argument("json");
 std::vector<std::pair<const J*,unsigned>> pending{{&d,0}};
 while(!pending.empty()){
  auto p=pending.back();pending.pop_back();if(p.second>16)throw std::invalid_argument("depth");
  if(p.first->IsObject()){
   std::set<std::string> names;for(auto m=p.first->MemberBegin();m!=p.first->MemberEnd();++m){
    if(!names.insert({m->name.GetString(),m->name.GetStringLength()}).second)throw std::invalid_argument("duplicate");
    pending.push_back({&m->value,p.second+1});}
  }else if(p.first->IsArray())for(const auto& v:p.first->GetArray())pending.push_back({&v,p.second+1});
 }
 return d;
}
void keys(const J& o,std::initializer_list<const char*> names){
 if(!o.IsObject()||o.MemberCount()!=names.size())throw std::invalid_argument("fields");
 for(auto k:names)if(!o.HasMember(k))throw std::invalid_argument("fields");
}
std::string string(const J& o,const char* k,std::size_t maximum=4096){
 if(!o.HasMember(k)||!o[k].IsString()||!o[k].GetStringLength()||o[k].GetStringLength()>maximum)throw std::invalid_argument("string");
 std::string v(o[k].GetString(),o[k].GetStringLength());if(v.find('\0')!=v.npos)throw std::invalid_argument("nul");return v;
}
const char* code(ErrorCode c){switch(c){
 case ErrorCode::Ok:return "Ok";case ErrorCode::InvalidInput:return "InvalidInput";case ErrorCode::NotSupported:return "NotSupported";
 case ErrorCode::Pending:return "Pending";case ErrorCode::Timeout:return "Timeout";case ErrorCode::Backpressure:return "Backpressure";
 case ErrorCode::StaleSession:return "StaleSession";case ErrorCode::Conflict:return "Conflict";case ErrorCode::SubmissionUnknown:return "SubmissionUnknown";
 case ErrorCode::IoError:return "IoError";default:return "Unavailable";}}
J source(const SourceSession& s,A& a){
 if(s.instance_id.empty()||s.session_id.empty()||!s.generation)return J();
 J j(rapidjson::kObjectType);text(j,"provider","Qmt",a);text(j,"instance_id",s.instance_id,a);text(j,"session_id",s.session_id,a);j.AddMember("generation",s.generation,a);return j;
}
J capability(bool supported,A& a){J j(rapidjson::kObjectType);j.AddMember("supported",supported,a);text(j,"qualification",supported?"NativeVerified":"Unavailable",a);text(j,"reason",supported?"独立Host SHM报价；真实来源及新鲜度另验":"该能力未就绪或不由报价入口承载",a);return j;}
struct Bridge {
 std::thread::id owner=std::this_thread::get_id();std::unique_ptr<QmtHostReadClient> client;QmtHttpProfile profile;
 std::optional<QmtBoundReceipt> pending;std::vector<std::string> pending_codes;std::uint32_t budget=5000;std::string output;
 bool retained=false;std::optional<QmtBoundResult> confirmed;std::string prepared_output;
 explicit Bridge(const J& c){
  keys(c,{"schema","base_url","key_id","hmac_secret","timeout_ms","max_response_bytes","profile"});
  const auto schema=string(c,"schema");retained=schema=="guanheng.shm-quotes.retained.v1";
  if((schema!="guanheng.shm-quotes.v1"&&!retained)||!c["timeout_ms"].IsUint()||c["timeout_ms"].GetUint()<100||c["timeout_ms"].GetUint()>30000||!c["max_response_bytes"].IsUint64()||c["max_response_bytes"].GetUint64()<1024||c["max_response_bytes"].GetUint64()>16*1024*1024)throw std::invalid_argument("budget");
  QmtHttpConfig h;h.base_url=string(c,"base_url");h.key_id=string(c,"key_id",128);h.hmac_secret=string(c,"hmac_secret");h.timeout_ms=budget=c["timeout_ms"].GetUint();h.max_response_bytes=static_cast<std::size_t>(c["max_response_bytes"].GetUint64());
  const auto& p=c["profile"];keys(p,{"version","source_license","time_encoding","minute_boundary","volume_to_shares","amount_to_yuan","full_tick_cumulative"});
  profile.version=string(p,"version",128);profile.source_license=string(p,"source_license",256);profile.time_encoding=string(p,"time_encoding",32);profile.minute_boundary=string(p,"minute_boundary",16);
  if(!p["volume_to_shares"].IsNumber()||!p["amount_to_yuan"].IsNumber()||!p["full_tick_cumulative"].IsBool())throw std::invalid_argument("profile");
  profile.volume_to_shares=p["volume_to_shares"].GetDouble();profile.amount_to_yuan=p["amount_to_yuan"].GetDouble();profile.full_tick_cumulative=p["full_tick_cumulative"].GetBool();
  if(!qmt_mapping::check_profile(profile).ok()||!profile.full_tick_cumulative)throw std::invalid_argument("profile");
  client=std::make_unique<QmtHostReadClient>(std::move(h),retained?QmtReadProfileVersion::FullTickRetainedV6:QmtReadProfileVersion::FullTickV6);
 }
 const char* finish(Status s,J data,rapidjson::Document& d){auto&a=d.GetAllocator();d.SetObject();text(d,"api_version",version,a);J status(rapidjson::kObjectType);text(status,"code",code(s.code),a);text(status,"reason",s.ok()?"":"共享内存报价未就绪、结果待核或输入不合格；保留原请求责任",a);d.AddMember("status",status,a);d.AddMember("data",data,a);output=encode(d);return output.c_str();}
 // ACK的责任者是本Native快照owner，绝不把它表述成外层HTTP已收到。
 // 原result/receipt与验证后的输出保持同一有界owner；ACK丢失不重新读取/提交市场请求。
 const char* confirm_cached(std::chrono::steady_clock::time_point end,rapidjson::Document& d){
  auto n=std::chrono::duration_cast<std::chrono::milliseconds>(end-std::chrono::steady_clock::now()).count();
  if(n<=0)return finish({ErrorCode::Timeout,"deadline"},J(rapidjson::kObjectType),d);
  auto status=client->confirm_full_tick(*confirmed,static_cast<std::uint32_t>(n));
  if(!status.ok())return finish(status,J(rapidjson::kObjectType),d);
  output=std::move(prepared_output);confirmed.reset();pending.reset();pending_codes.clear();return output.c_str();
 }
 const char* stage_complete(QmtBoundResult value,Status status,J data,rapidjson::Document& d,std::chrono::steady_clock::time_point end){
  // 在任何consumed I/O之前，完整原值和最终投影都已由本owner取得。
  value.receipt=*pending;finish(status,std::move(data),d);
  prepared_output=std::move(output);confirmed.emplace(std::move(value));return confirm_cached(end,d);
 }
 const char* call(const char* raw){
  rapidjson::Document d;auto&a=d.GetAllocator();J data(rapidjson::kObjectType);
  const auto end=std::chrono::steady_clock::now()+std::chrono::milliseconds(budget);
  auto left=[&](){auto n=std::chrono::duration_cast<std::chrono::milliseconds>(end-std::chrono::steady_clock::now()).count();return n>0?static_cast<std::uint32_t>(n):0u;};
  try{
   auto r=parse(raw,262144);if(string(r,"api_version",64)!=version)throw std::invalid_argument("version");const auto action=string(r,"action",64);
   if(action=="capabilities"){
    keys(r,{"api_version","action"});Status s=pending?Status{ErrorCode::Pending,"pending"}:client->prepare(left());
    data.AddMember("source",s.ok()?source(client->session(),a):J(),a);data.AddMember("snapshot",capability(s.ok()&&client->capability().supported,a),a);data.AddMember("history",capability(false,a),a);data.AddMember("trading",capability(false,a),a);return finish(s,std::move(data),d);
   }
   if(action!="quotes.query")return finish({ErrorCode::NotSupported,"quotes only"},std::move(data),d);
   keys(r,{"api_version","action","symbols"});if(!r["symbols"].IsArray()||r["symbols"].Empty()||r["symbols"].Size()>64)throw std::invalid_argument("symbols");
   std::set<std::string> unique;for(const auto& v:r["symbols"].GetArray()){
    if(!v.IsString()||v.GetStringLength()>20)throw std::invalid_argument("symbol");std::string s(v.GetString(),v.GetStringLength());qmt_mapping::qmt_symbol(s);if(!unique.insert(s).second)throw std::invalid_argument("duplicate");}
   std::vector<std::string> codes(unique.begin(),unique.end());QmtBoundResult value;
   if(pending){
    // 原请求未确认时只GET原ID。更换证券不能绕过未知责任，且不重授任何截止。
    if(codes!=pending_codes)return finish({ErrorCode::Pending,"original read pending"},std::move(data),d);
    if(confirmed)return confirm_cached(end,d);
    value=client->resume(*pending,left());
   }else{
    auto prepared=client->prepare(left());if(!prepared.ok())return finish(prepared,std::move(data),d);
    rapidjson::Document arguments;arguments.SetObject();J stocks(rapidjson::kArrayType);for(const auto& s:codes){auto q=qmt_mapping::qmt_symbol(s);stocks.PushBack(J(q.data(),static_cast<rapidjson::SizeType>(q.size()),arguments.GetAllocator()),arguments.GetAllocator());}arguments.AddMember("stocks",stocks,arguments.GetAllocator());
    value=client->read_full_tick(encode(arguments),left());
    // move取得完整原receipt在任何后续投影/序列化前；分配失败也保留已发请求身份。
    if(!value.receipt.request_body.empty()){pending.emplace(std::move(value.receipt));pending_codes=std::move(codes);}
   }
   if(!value.result.status.ok()){
    if(retained&&value.snapshot_consumption_ready){
     auto status=value.result.status;return stage_complete(std::move(value),std::move(status),std::move(data),d,end);
    }
    if(!retained&&value.result.terminal){pending.reset();pending_codes.clear();}
    return finish(value.result.status,std::move(data),d);
   }
   auto selected=pending?pending_codes:codes;
   // Common已确认完整绑定及原终态。值不合格属于已知读取失败，释放内存核查
   // 责任后允许下一次观察；Host原终态记录继续保留，不能误标为未知而永久挂住。
   if(!retained){pending.reset();pending_codes.clear();}
   std::vector<MarketSnapshot> ticks;
   try {ticks=qmt_mapping::map_ticks(selected,value.result.data_json,profile,client->session());}
   catch(const std::invalid_argument&){
    // 原结果完整且确定返回、值投影明确不合格：owner取得原值及失败分类后确认此观察，
    // 不把确定坏行情永久伪装成SDK执行未知；身份/结构未确认的上游失败不会到达这里。
    if(retained)return stage_complete(std::move(value),{ErrorCode::InvalidInput,"invalid snapshot"},J(rapidjson::kObjectType),d,end);
    throw;
   }
   J snapshots(rapidjson::kArrayType);
   for(const auto& s:ticks){J q(rapidjson::kObjectType);q.AddMember("source",source(s.source,a),a);text(q,"symbol",std::string(s.tick.exchg)+"."+s.tick.code,a);
    q.AddMember("date",s.tick.action_date,a);q.AddMember("action_time",s.tick.action_time,a);q.AddMember("price",s.tick.price,a);q.AddMember("open",s.tick.open,a);q.AddMember("high",s.tick.high,a);q.AddMember("low",s.tick.low,a);q.AddMember("pre_close",s.tick.pre_close,a);q.AddMember("total_volume",s.tick.total_volume,a);q.AddMember("total_turnover",s.tick.total_turnover,a);q.AddMember("full_cumulative",s.full_cumulative,a);q.AddMember("source_time_verified",s.source_time_verified,a);snapshots.PushBack(q,a);}
   if(!left())return finish({ErrorCode::Timeout,"deadline"},J(rapidjson::kObjectType),d);
   data.AddMember("snapshots",snapshots,a);J meta(rapidjson::kObjectType);text(meta,"qualification","NativeVerified",a);text(meta,"profile_version",profile.version,a);text(meta,"source_license",profile.source_license,a);text(meta,"timezone","Asia/Shanghai",a);text(meta,"price_unit","CNY",a);text(meta,"volume_unit","share",a);text(meta,"amount_unit","CNY",a);meta.AddMember("volume_to_shares",profile.volume_to_shares,a);meta.AddMember("amount_to_yuan",profile.amount_to_yuan,a);data.AddMember("metadata",meta,a);
   if(retained)return stage_complete(std::move(value),{},std::move(data),d,end);
   pending.reset();pending_codes.clear();return finish({},std::move(data),d);
  }catch(const std::invalid_argument&){return finish({ErrorCode::InvalidInput,"invalid"},J(rapidjson::kObjectType),d);}
  catch(...){return finish({ErrorCode::Unavailable,"unavailable"},J(rapidjson::kObjectType),d);}
 }
};
constexpr const char* unavailable="{\"api_version\":\"guanheng.market.v1\",\"status\":{\"code\":\"Unavailable\",\"reason\":\"原生报价owner不可用\"},\"data\":{}}";
}
extern "C" {
void* gh_market_create(const char* raw)noexcept{try{return new Bridge(parse(raw,65536));}catch(...){return nullptr;}}
const char* gh_market_call(void* h,const char* raw)noexcept{try{auto*b=static_cast<Bridge*>(h);if(b&&b->owner==std::this_thread::get_id())return b->call(raw);}catch(...){}return unavailable;}
void gh_market_destroy(void* h)noexcept{try{auto*b=static_cast<Bridge*>(h);if(b&&b->owner==std::this_thread::get_id())delete b;}catch(...){}}
}
