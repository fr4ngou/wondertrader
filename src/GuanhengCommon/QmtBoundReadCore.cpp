#include "QmtBoundReadCore.h"
#include "QmtAccountFields.h"
#include "QmtHostCodec.h"
#include <chrono>
#include <limits>
#include <rapidjson/memorystream.h>
#include <rapidjson/document.h>
#include <rapidjson/reader.h>
#include <algorithm>
#include <cmath>
#include <cstring>
#include <set>
#include <thread>
#include <stdexcept>
#include <vector>
#include <type_traits>
#include <new>
#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <bcrypt.h>
#endif
#if defined(_WIN32) && defined(GH_QMT_HTTP_DRAIN_TESTING)
#include <atomic>
namespace { std::atomic<unsigned> bound_test_fault{0}; }
extern "C" __declspec(dllexport) void gh_qmt_bound_test_fault(unsigned phase) noexcept
{ bound_test_fault.store(phase); }
#endif

namespace guanheng
{
static_assert(std::is_nothrow_move_constructible<QmtBoundResult>::value,"unknown receipt must move without allocation");
namespace
{
using Document=rapidjson::Document;
using Value=rapidjson::Value;
constexpr const char* version="qmt.bound-read.v1";
Status fail(ErrorCode code,const char* reason) { return {code,reason}; }
using namespace qmt_host_codec;
bool parse(const std::string& input,Document& value,std::size_t maximum)
{ return parse_bounded_qmt_json(input,value,maximum,4*1024*1024); }
void add(Document& value,const char* key,const std::string& data)
{auto& a=value.GetAllocator();value.AddMember(Value(key,a),Value(data.data(),static_cast<rapidjson::SizeType>(data.size()),a),a);}
bool completed_at(const Value& value)
{
    if(!string(value,40))return false;const auto s=text(value);
    if(s.size()<20||s[4]!='-'||s[7]!='-'||s[10]!='T'||s[13]!=':'||s[16]!=':')return false;
    auto number=[&](unsigned index,unsigned count){unsigned result=0;for(unsigned n=0;n<count;++n){char c=s[index+n];if(c<'0'||c>'9')return 10000U;result=result*10+c-'0';}return result;};
    const auto year=number(0,4),month=number(5,2),day=number(8,2);
    const unsigned days[]={0,31,28,31,30,31,30,31,31,30,31,30,31};
    if(!year||year>9999||!month||month>12||!day||day>days[month]+(month==2&&year%4==0&&(year%100!=0||year%400==0))
        ||number(11,2)>23||number(14,2)>59||number(17,2)>59)return false;
    std::size_t i=19;
    if(i<s.size()&&s[i]=='.'){const auto begin=++i;while(i<s.size()&&s[i]>='0'&&s[i]<='9')++i;if(i==begin||i-begin>9)return false;}
    if(s.substr(i)=="Z")return true;
    return s.size()-i==6&&(s[i]=='+'||s[i]=='-')&&s[i+3]==':'&&number(static_cast<unsigned>(i+1),2)<=23&&number(static_cast<unsigned>(i+4),2)<=59;
}
bool terminal_bytes(const Value& value,std::size_t maximum,std::string& output)
{
    return text(value["state"])=="terminal"&&hex(value["result_body_sha256"],64)
        &&unbase64(value["result_body_b64"],maximum,output)
        &&signed_http_sha256(output)==text(value["result_body_sha256"]);
}
// Fixed history descriptor helpers. The original transport/binding codec is shared below.
bool base_control(const Value& value,const char* expected_version="1.0");
bool integer(const Value& value,std::uint64_t lo,std::uint64_t hi)
{return value.IsUint64()&&value.GetUint64()>=lo&&value.GetUint64()<=hi;}
bool retained_profile(const Value& p,std::uint32_t& lifetime)
{
    lifetime=0;if(!p.IsObject())return false;if(!p.HasMember("read_retention"))return true;
    const auto& r=p["read_retention"];
    if(!keys(r,{"schema","max_lifetime_ms"})||!field(r,"schema")
        ||text(r["schema"])!="qmt.read-retention.v1"||!integer(r["max_lifetime_ms"],100,300000))return false;
    lifetime=r["max_lifetime_ms"].GetUint();return true;
}
std::uint64_t retention_now()
{
#ifdef _WIN32
    return GetTickCount64();
#else
    return 0;
#endif
}
// RR的UUIDv5将原票据与去request_id后的完整请求绑定。账户/固定证券请求值均为ASCII，
// 共用原排序编码；不把新票据藏进原UUID，也不引入进程外客户端状态。
std::string retained_id(const Value& body,const Value& ticket)
{
#ifdef _WIN32
    if(!keys(ticket,{"schema","epoch","expires_ms"})||!field(ticket,"schema")
        ||text(ticket["schema"])!="qmt.read-ticket.v1"||!hex(ticket["epoch"],32)
        ||!integer(ticket["expires_ms"],1,(1ULL<<53)-1))return {};
    const auto epoch=text(ticket["epoch"]);std::string bytes;
    auto digit=[](char c){return c<='9'?c-'0':c-'a'+10;};
    for(unsigned i=0;i<32;i+=2)bytes+=static_cast<char>((digit(epoch[i])<<4)|digit(epoch[i+1]));
    Document name;name.SetObject();auto& a=name.GetAllocator();Value request(body,a);request.RemoveMember("request_id");
    name.AddMember("request",request,a);name.AddMember("ticket",Value(ticket,a),a);bytes+=encode(name);
    // CNG要求hash对象缓冲区在句柄销毁后才可释放。
    // 将算法、hash和缓冲区作为同一owner，提前返回/异常也沿相同释放顺序。
    struct HashOwner{
        BCRYPT_ALG_HANDLE algorithm=nullptr;BCRYPT_HASH_HANDLE hash=nullptr;
        std::vector<unsigned char> object;
        ~HashOwner(){if(hash)BCryptDestroyHash(hash);if(algorithm)BCryptCloseAlgorithmProvider(algorithm,0);}
    }owner;
    DWORD size=0,received=0;unsigned char digest[20]{};
    if(BCryptOpenAlgorithmProvider(&owner.algorithm,BCRYPT_SHA1_ALGORITHM,nullptr,0)<0
        ||BCryptGetProperty(owner.algorithm,BCRYPT_OBJECT_LENGTH,reinterpret_cast<PUCHAR>(&size),sizeof(size),&received,0)<0||size>65536)return {};
    owner.object.resize(size);
    if(BCryptCreateHash(owner.algorithm,&owner.hash,owner.object.data(),size,nullptr,0,0)<0
        ||BCryptHashData(owner.hash,reinterpret_cast<PUCHAR>(&bytes[0]),static_cast<ULONG>(bytes.size()),0)<0
        ||BCryptFinishHash(owner.hash,digest,20,0)<0)return {};
    digest[6]=(digest[6]&15)|80;digest[8]=(digest[8]&63)|128;
    const char alphabet[]="0123456789abcdef";std::string id;id.reserve(36);
    for(unsigned i=0;i<16;++i){if(i==4||i==6||i==8||i==10)id+='-';id+=alphabet[digest[i]>>4];id+=alphabet[digest[i]&15];}return id;
#else
    return {};
#endif
}
bool positive_number(const Value& value,double ceiling)
{return value.IsNumber()&&std::isfinite(value.GetDouble())&&value.GetDouble()>0&&value.GetDouble()<=ceiling;}
bool modern_stamp(const Value& value,std::int64_t& minutes,std::int64_t& day_number)
{
    if(!string(value,14)||value.GetStringLength()!=14)return false;
    const auto s=text(value);
    if(!std::all_of(s.begin(),s.end(),[](char c){return c>='0'&&c<='9';})||s.substr(12)!="00")return false;
    const auto year=std::stoul(s.substr(0,4)),month=std::stoul(s.substr(4,2)),day=std::stoul(s.substr(6,2));
    const auto hour=std::stoul(s.substr(8,2)),minute=std::stoul(s.substr(10,2));
    const unsigned days[]={0,31,28,31,30,31,30,31,31,30,31,30,31};
    auto leap=[](unsigned y){return y%4==0&&(y%100!=0||y%400==0);};
    if(year<2021||year>2099||!month||month>12||!day||day>days[month]+(month==2&&leap(year))||hour>23||minute>59)return false;
    day_number=0;for(unsigned y=1970;y<year;++y)day_number+=365+leap(y);
    for(unsigned m=1;m<month;++m)day_number+=days[m]+(m==2&&leap(year));
    day_number+=day-1;minutes=day_number*1440+hour*60+minute-480;
    return s.substr(0,8)>="20211101";
}
bool history_arguments(const Value& value,unsigned max_days,unsigned max_rows)
{
    if(!keys(value,{"symbol","start_time","end_time","max_rows"})||!field(value,"symbol",9)
        ||value["symbol"].GetStringLength()!=9||!integer(value["max_rows"],1,max_rows))return false;
    const auto symbol=text(value["symbol"]);
    if(!std::all_of(symbol.begin(),symbol.begin()+6,[](char c){return c>='0'&&c<='9';})
        ||(symbol.substr(6)!=".SH"&&symbol.substr(6)!=".SZ"))return false;
    std::int64_t start,stop,first,last;
    if(!modern_stamp(value["start_time"],start,first)||!modern_stamp(value["end_time"],stop,last)
        ||start>stop||last-first>=max_days)return false;
    // The supported QH date domain is modern Shanghai UTC+8. Host/Agent repeat this
    // using their trusted clock; there is no caller-provided now in the request.
    const auto now=std::chrono::duration_cast<std::chrono::minutes>(std::chrono::system_clock::now().time_since_epoch()).count();
    return last<(now+480)/1440;
}
bool history_profile(const Value& p,std::size_t result_cap,std::uint32_t& execution,
                     unsigned& days,unsigned& rows,std::size_t& bytes)
{
    if(result_cap<8192||!keys(p,{"read_profile_version","read_operations","execution_timeout_ms","control_profile","operation_profiles"})
        ||!field(p,"read_profile_version")||text(p["read_profile_version"])!="qmt.read-profile.v2"
        ||!p["read_operations"].IsArray()||p["read_operations"].Empty()||p["read_operations"].Size()>2
        ||!integer(p["execution_timeout_ms"],100,30000)||!p["operation_profiles"].IsObject()
        ||p["operation_profiles"].MemberCount()!=p["read_operations"].Size()||!base_control(p["control_profile"]))return false;
    const auto& c=p["control_profile"];
    for(auto key:{"max_pending_calls","max_call_bytes","max_reply_bytes","max_retained_bytes","max_cycle_messages","max_cycle_bytes"})
        if(!integer(c[key],1,(1ULL<<53)-1))return false;
    for(auto key:{"poll_seconds","max_call_seconds"})if(!positive_number(c[key],600))return false;
    std::string previous;std::uint32_t maximum=0;bool found=false;
    for(const auto& op:p["read_operations"].GetArray()){
        if(!string(op))return false;const auto name=text(op);
        if(name<=previous||(name!="market.full_tick"&&name!="market.history_1m")||!p["operation_profiles"].HasMember(name.c_str()))return false;
        previous=name;const auto& d=p["operation_profiles"][name.c_str()];
        if(!keys(d,{"policy_id","policy_version","execution_timeout_ms","limits"})||!field(d,"policy_id")
            ||text(d["policy_id"])!=(name=="market.full_tick"?"qmt.standard-read.v1":"qmt.history-read.v1")
            ||!field(d,"policy_version")||text(d["policy_version"])!="1.0"||!integer(d["execution_timeout_ms"],100,30000))return false;
        maximum=std::max(maximum,d["execution_timeout_ms"].GetUint());
        const auto& l=d["limits"];
        if(name=="market.full_tick"){if(!keys(l,{}))return false;}
        else{
            if(!keys(l,{"schema_version","max_calendar_days","max_rows","max_data_bytes"})||!field(l,"schema_version")
                ||text(l["schema_version"])!="qmt.history-1m.v1"||!integer(l["max_calendar_days"],1,5)
                ||!integer(l["max_rows"],1,2000)||!integer(l["max_data_bytes"],1024,result_cap-4096))return false;
            found=true;execution=d["execution_timeout_ms"].GetUint();days=l["max_calendar_days"].GetUint();
            rows=l["max_rows"].GetUint();bytes=static_cast<std::size_t>(l["max_data_bytes"].GetUint64());
        }
    }
    return found&&maximum==p["execution_timeout_ms"].GetUint();
}
bool history_terminal(const Value& v,bool retained=false,bool not_dispatched=false)
{
    if(!keys(v,{"request_id","operation_id","ok","completed_at","result_sha256","data","error_code","error_message","observation",
        "request_admission_ms","queue_wait_ms","execution_ms","result_persistence_ms","response_wakeup_ms","response_handler_ms"})
        ||!v["observation"].IsNull())return false;
    for(auto key:{"request_admission_ms","result_persistence_ms","response_wakeup_ms","response_handler_ms"})
        if(!integer(v[key],0,(1ULL<<53)-1))return false;
    for(auto key:{"queue_wait_ms","execution_ms"})if(!v[key].IsNull()&&!integer(v[key],0,(1ULL<<53)-1))return false;
    if(v["ok"].GetBool())return v["error_code"].IsNull()&&v["error_message"].IsNull();
    if(!v["data"].IsNull()||!field(v,"error_code",128)||!field(v,"error_message",1024))return false;
    const auto code=text(v["error_code"]);
    // Host在派发前终结原请求；空派发/结果绑定证明SDK没有执行。
    if(not_dispatched&&code=="source_binding_changed")return true;
    if(retained)for(auto known:{"preparation_not_executed","source_binding_changed","queue_full","invalid_arguments","capability_unavailable"})
        if(code==known)return true;
    for(auto known:{"invalid_request","owner_required","execution_timeout","queue_timeout","source_shape_invalid","source_value_invalid",
        "history_window_limit","result_too_large","qmt_call_failed","unsafe_json_value","operation_interrupted","source_binding_stale"})
        if(code==known)return true;
    return false;
}
// Find the raw UTF8 data value after bounded DOM admission. Never re-encode floats
// to measure the Agent's max_data_bytes or to replace its original terminal bytes.
bool data_span(const std::string& raw,std::size_t& start,std::size_t& length,SignedHttpDeadline& until)
{
    rapidjson::MemoryStream stream(raw.data(),raw.size());
    struct Finder:rapidjson::BaseReaderHandler<rapidjson::UTF8<>,Finder>{
        rapidjson::MemoryStream& stream;unsigned depth=0;std::size_t offset=0;bool found=false;
        explicit Finder(rapidjson::MemoryStream& s):stream(s){}
        bool StartObject(){++depth;return true;}bool EndObject(rapidjson::SizeType){--depth;return true;}
        bool StartArray(){++depth;return true;}bool EndArray(rapidjson::SizeType){--depth;return true;}
        bool Key(const char* s,rapidjson::SizeType n,bool){if(depth==1&&n==4&&std::memcmp(s,"data",4)==0){offset=stream.Tell();found=true;return false;}return true;}
    } finder(stream);
    rapidjson::Reader reader;reader.Parse(stream,finder);if(!finder.found)return false;
    std::size_t i=finder.offset;auto white=[&](){while(i<raw.size()&&(raw[i]==' '||raw[i]=='\n'||raw[i]=='\r'||raw[i]=='\t'))++i;};
    white();if(i>=raw.size()||raw[i++]!=':')return false;white();start=i;
    if(i>=raw.size()||raw[i]!='{')return false;
    unsigned depth=0;bool quoted=false,escape=false;
    for(;i<raw.size();++i){if(i%4096==0&&!until.remaining())return false;const auto c=raw[i];
        if(quoted){if(escape)escape=false;else if(c=='\\')escape=true;else if(c=='"')quoted=false;continue;}
        if(c=='"')quoted=true;else if(c=='{'||c=='[')++depth;else if(c=='}'||c==']'){
            if(!--depth){length=i+1-start;return true;}
        }
    }return false;
}
bool history_number(const Value& v,double& out)
{
    if(!v.IsNumber())return false;
    if(v.IsUint64()&&v.GetUint64()>(1ULL<<53))return false;
    if(v.IsInt64()&&(v.GetInt64()<-(1LL<<53)||v.GetInt64()>(1LL<<53)))return false;
    out=v.GetDouble();return std::isfinite(out);
}
bool history_data(const std::string& raw,const Value& v,const Value& arguments,unsigned days,unsigned rows,std::size_t bytes,QmtHistoryPage& page,SignedHttpDeadline& until)
{
    if(!history_arguments(arguments,days,rows)||!keys(v,{"schema_version","symbol","period","start_time","end_time","max_rows","rows","coverage","source_options"})
        ||!field(v,"schema_version")||text(v["schema_version"])!="qmt.history-1m.v1"||!field(v,"period")||text(v["period"])!="1m"
        ||!field(v,"coverage")||text(v["coverage"])!="unknown")return false;
    for(auto key:{"symbol","start_time","end_time"})if(!field(v,key)||text(v[key])!=text(arguments[key]))return false;
    if(!integer(v["max_rows"],1,rows)||v["max_rows"].GetUint()!=arguments["max_rows"].GetUint()
        ||!v["rows"].IsArray()||v["rows"].Size()>=v["max_rows"].GetUint())return false;
    const auto& options=v["source_options"];
    if(!keys(options,{"dividend_type","fill_data","subscribe"})||!field(options,"dividend_type")||text(options["dividend_type"])!="none"
        ||!options["fill_data"].IsBool()||options["fill_data"].GetBool()||!options["subscribe"].IsBool()||options["subscribe"].GetBool())return false;
    std::size_t start=0,count=0;if(!data_span(raw,start,count,until)||count>bytes)return false;
    std::int64_t first,last,dummy;modern_stamp(arguments["start_time"],first,dummy);modern_stamp(arguments["end_time"],last,dummy);
    QmtHistoryPage result;result.request={text(arguments["symbol"]),text(arguments["start_time"]),text(arguments["end_time"]),arguments["max_rows"].GetUint()};
    result.rows.reserve(v["rows"].Size());std::uint64_t previous=0;
    for(const auto& r:v["rows"].GetArray()){
        if(!until.remaining())return false;
        if(!keys(r,{"time","open","high","low","close","volume","amount"}))return false;
        double stamp=0;QmtHistoryRow row;
        if(!history_number(r["time"],stamp)||stamp<0||stamp>9007199254740992.||std::floor(stamp)!=stamp)return false;
        row.time=static_cast<std::uint64_t>(stamp);
        if(row.time%60000||row.time<static_cast<std::uint64_t>(first)*60000||row.time>static_cast<std::uint64_t>(last)*60000
            ||(previous&&row.time<=previous))return false;
        if(!history_number(r["open"],row.open)||!history_number(r["high"],row.high)||!history_number(r["low"],row.low)
            ||!history_number(r["close"],row.close)||!history_number(r["volume"],row.volume)||!history_number(r["amount"],row.amount)
            ||std::min({row.open,row.high,row.low,row.close})<=0||row.volume<0||row.amount<0
            ||row.high<std::max({row.open,row.low,row.close})||row.low>std::min({row.open,row.high,row.close}))return false;
        previous=row.time;result.rows.push_back(row);
    }
    page=std::move(result);return true;
}

bool stocks(const Value& value)
{
    if(!keys(value,{"stocks"})||!value["stocks"].IsArray()||value["stocks"].Empty()||value["stocks"].Size()>200)return false;
    std::set<std::string> seen;
    for(const auto& item:value["stocks"].GetArray()){
        if(!string(item,9)||item.GetStringLength()!=9)return false;
        auto symbol=text(item);
        if(!std::all_of(symbol.begin(),symbol.begin()+6,[](char c){return c>='0'&&c<='9';})
            ||(symbol.substr(6)!=".SH"&&symbol.substr(6)!=".SZ")||!seen.insert(symbol).second)return false;
    }return true;
}
bool base_control(const Value& value,const char* expected_version)
{
    // 识别同版DTO字段与原生类型；信用/容量关系仍由Host/Agent ControlProfile唯一准入。
    if(!keys(value,{"schema_version","max_pending_calls","max_call_bytes","max_reply_bytes","max_retained_bytes",
        "max_cycle_messages","max_cycle_bytes","poll_seconds","max_call_seconds"})
        ||!field(value,"schema_version")||text(value["schema_version"])!=expected_version)return false;
    for(auto key:{"max_pending_calls","max_call_bytes","max_reply_bytes","max_retained_bytes","max_cycle_messages","max_cycle_bytes"})
        if(!value[key].IsUint64())return false;
    return value["poll_seconds"].IsNumber()&&value["max_call_seconds"].IsNumber();
}

// 完整v3能力与当前固定操作分开准入；行情门面也必须认识账户descriptor。
struct AccountLimits {
    std::string account_id,environment;
    unsigned rows=0,nodes=0,characters=0;
    std::size_t bytes=0;
    // 账户投影版本来自完整可信 descriptor，不由结果 schema 反选。
    std::string policy_version=account_fields::policy_version;
};
bool account_identity(const Value& value)
{
    if(!string(value,63))return false;
    const auto* s=reinterpret_cast<const unsigned char*>(value.GetString());
    for(unsigned i=0;i<value.GetStringLength();++i){
        if(s[i]<32||s[i]==127)return false;
        if(s[i]==0xc2&&i+1<value.GetStringLength()&&s[i+1]>=0x80&&s[i+1]<=0x9f)return false;
    }
    return true; // parse_bounded_qmt_json已拒绝非法UTF8/孤立surrogate。
}
bool account_binding(const Value& b,bool origin=false)
{
    if(!(origin?keys(b,{"account_id","account_environment","currency","financial_profile","origin"}):
                   keys(b,{"account_id","account_environment","currency","financial_profile"})))return false;
    if(!account_identity(b["account_id"])||!field(b,"account_environment")
        ||(text(b["account_environment"])!="simulation"&&text(b["account_environment"])!="live")
        ||!field(b,"currency")||text(b["currency"])!="CNY"
        ||!field(b,"financial_profile")||text(b["financial_profile"])!="cny_cash_shsz_v1")return false;
    return !origin||(field(b,"origin")&&text(b["origin"])=="trusted_bootstrap_argument");
}
bool account_limits(const Value& l,std::size_t cap,AccountLimits& out)
{
    if(cap<8192||cap>2097152||!keys(l,{"schema_version","account_binding","max_rows","max_nodes","max_scalar_chars","max_data_bytes"})
        ||!field(l,"schema_version")||text(l["schema_version"])!="qmt.account-read.v1"||!account_binding(l["account_binding"])
        ||!integer(l["max_rows"],1,4096)||!integer(l["max_nodes"],1,65536)||!integer(l["max_scalar_chars"],1,262144)
        ||!integer(l["max_data_bytes"],1024,std::min<std::size_t>(1048576,cap-4096)))return false;
    out={text(l["account_binding"]["account_id"]),text(l["account_binding"]["account_environment"]),
        l["max_rows"].GetUint(),l["max_nodes"].GetUint(),l["max_scalar_chars"].GetUint(),
        static_cast<std::size_t>(l["max_data_bytes"].GetUint64())};return true;
}
bool account_arguments(const Value& args)
{
    if(!keys(args,{"account_type","datatype","scope"})||!field(args,"account_type")||text(args["account_type"])!="stock"
        ||!field(args,"scope")||text(args["scope"])!="account"||!field(args,"datatype"))return false;
    const auto type=text(args["datatype"]);return type=="position"||type=="order"||type=="deal"||type=="account";
}
const char* operation(QmtBoundProfile p)
{
    if(p==QmtBoundProfile::AccountV3||p==QmtBoundProfile::AccountV4)return "account.trade_detail";
    if(p==QmtBoundProfile::History1mV2||p==QmtBoundProfile::History1mV3)return "market.history_1m";
    return "market.full_tick";
}
const char* policy(QmtBoundProfile p)
{
    if(p==QmtBoundProfile::AccountV3||p==QmtBoundProfile::AccountV4)return "qmt.account-read.v1";
    if(p==QmtBoundProfile::History1mV2||p==QmtBoundProfile::History1mV3)return "qmt.history-read.v1";
    return "qmt.standard-read.v1";
}
bool operation_arguments(QmtBoundProfile p,const Value& args,unsigned days=5,unsigned rows=2000)
{
    if(p==QmtBoundProfile::AccountV3||p==QmtBoundProfile::AccountV4)return account_arguments(args);
    if(p==QmtBoundProfile::History1mV2||p==QmtBoundProfile::History1mV3)return history_arguments(args,days,rows);
    return stocks(args);
}
// 公开 control2 和交易 descriptor 的可知预算关系，共用 Python 协议常量。
// 实际 max_frame、io_seconds 不在公开 profile 中，由 Host 配置 owner 核验。
bool trade_control(const Value& c,std::size_t result_cap,const QmtTradeReadDescriptor& t)
{
    if(!integer(c["max_pending_calls"],4,1024)||!integer(c["max_call_bytes"],1024,1048576)
        ||!integer(c["max_reply_bytes"],1024,4190208)||!integer(c["max_retained_bytes"],1,67108864)
        ||!integer(c["max_cycle_messages"],1,64)||!integer(c["max_cycle_bytes"],2048,4190208)
        ||!c["poll_seconds"].IsNumber()||!std::isfinite(c["poll_seconds"].GetDouble())
        ||c["poll_seconds"].GetDouble()<0.001||c["poll_seconds"].GetDouble()>1
        ||!c["max_call_seconds"].IsNumber()||!std::isfinite(c["max_call_seconds"].GetDouble())
        ||c["max_call_seconds"].GetDouble()<0.1||c["max_call_seconds"].GetDouble()>360)return false;
    const auto call=c["max_call_bytes"].GetUint64(),reply=c["max_reply_bytes"].GetUint64();
    const auto cycle=c["max_cycle_bytes"].GetUint64(),retained=c["max_retained_bytes"].GetUint64();
    // 完整三字节组的 base64 上界，保留消息/周期/Session 原开销。
    // TransportBudget 的 IO 下界为 0.05，且 poll<=IO/2；这里只核可知的必要下界。
    if(4*((t.max_command_bytes+2)/3)+1024>call
        ||std::max(std::max<std::uint64_t>(result_cap,t.max_call_result_bytes),t.max_event_page_bytes)+1024>reply
        ||std::max(call,reply)+1024>cycle||cycle>4194304-4096
        ||static_cast<double>(t.max_command_ttl_ms)/1000+std::max(0.05,2*c["poll_seconds"].GetDouble())
            >c["max_call_seconds"].GetDouble())return false;
    // 七个完整保留槽保证 Host 四槽/Agent 三槽，不借用反向额度。
    // Host 的规范化公开 profile 已将两个时长编码成 float。
    Document normalized;normalized.CopyFrom(c,normalized.GetAllocator());
    normalized["poll_seconds"].SetDouble(c["poll_seconds"].GetDouble());
    normalized["max_call_seconds"].SetDouble(c["max_call_seconds"].GetDouble());
    return retained>=encode(normalized).size()+7*(call+reply+1024);
}
bool trade_descriptor(const Value& t,QmtTradeReadDescriptor& out)
{
    if(!keys(t,{"schema_version","binding_sha256","clock_schema","operations","limits"})
        ||!field(t,"schema_version")||text(t["schema_version"])!="qmt.trade-profile.v1"
        ||!hex(t["binding_sha256"],64)||!field(t,"clock_schema")||text(t["clock_schema"])!="qmt.win-uptime-ms.v1"
        ||!t["operations"].IsArray()||t["operations"].Size()!=2
        ||!string(t["operations"][0])||text(t["operations"][0])!="order.cancel"
        ||!string(t["operations"][1])||text(t["operations"][1])!="order.insert")return false;
    const auto& l=t["limits"];
    if(!keys(l,{"max_commands","max_command_bytes","max_command_ttl_ms","max_call_result_bytes",
        "max_events","max_event_bytes","max_total_event_bytes","max_event_page_bytes"})
        ||!integer(l["max_commands"],1,4096)||!integer(l["max_command_bytes"],1,65536)
        ||!integer(l["max_command_ttl_ms"],100,300000)||!integer(l["max_call_result_bytes"],1024,2097152)
        ||!integer(l["max_events"],1,4096)||!integer(l["max_event_bytes"],256,1048576)
        ||!integer(l["max_total_event_bytes"],256,16777216)||!integer(l["max_event_page_bytes"],1280,4190208)
        ||l["max_total_event_bytes"].GetUint64()<l["max_event_bytes"].GetUint64()
        ||l["max_event_page_bytes"].GetUint64()<l["max_event_bytes"].GetUint64()+1024)return false;
    out.binding_sha256=text(t["binding_sha256"]);
    out.max_commands=l["max_commands"].GetUint64();out.max_command_bytes=l["max_command_bytes"].GetUint64();
    out.max_command_ttl_ms=l["max_command_ttl_ms"].GetUint64();out.max_call_result_bytes=l["max_call_result_bytes"].GetUint64();
    out.max_events=l["max_events"].GetUint64();out.max_event_bytes=l["max_event_bytes"].GetUint64();
    out.max_total_event_bytes=l["max_total_event_bytes"].GetUint64();out.max_event_page_bytes=l["max_event_page_bytes"].GetUint64();
    return true;
}
bool profile_v3(const Value& p,std::size_t cap,QmtBoundProfile selected,std::uint32_t& execution,
    unsigned& days,unsigned& rows,std::size_t& bytes,AccountLimits& account,QmtTradeReadDescriptor* trade=nullptr)
{
    const bool v4=selected==QmtBoundProfile::AccountV4;
    std::uint32_t lifetime=0;
    const bool retained=p.IsObject()&&p.HasMember("read_retention");
    const bool shape=v4?(retained?keys(p,{"read_profile_version","read_operations","execution_timeout_ms","control_profile","operation_profiles","trade_profile","read_retention"})
        :keys(p,{"read_profile_version","read_operations","execution_timeout_ms","control_profile","operation_profiles","trade_profile"}))
        :(retained?keys(p,{"read_profile_version","read_operations","execution_timeout_ms","control_profile","operation_profiles","read_retention"})
        :keys(p,{"read_profile_version","read_operations","execution_timeout_ms","control_profile","operation_profiles"}));
    if(cap<8192||cap>2097152||!shape
        ||!field(p,"read_profile_version")||text(p["read_profile_version"])!=(v4?"qmt.read-profile.v4":"qmt.read-profile.v3")
        ||!p["read_operations"].IsArray()||p["read_operations"].Empty()||p["read_operations"].Size()>3
        ||!p["operation_profiles"].IsObject()||p["operation_profiles"].MemberCount()!=p["read_operations"].Size()
        ||!integer(p["execution_timeout_ms"],100,30000)||!base_control(p["control_profile"],v4?"2.0":"1.0")||!retained_profile(p,lifetime))return false;
    const auto& c=p["control_profile"];
    for(auto key:{"max_pending_calls","max_call_bytes","max_reply_bytes","max_retained_bytes","max_cycle_messages","max_cycle_bytes"})
        if(!integer(c[key],1,(1ULL<<53)-1))return false;
    for(auto key:{"poll_seconds","max_call_seconds"})if(!positive_number(c[key],600))return false;
    bool found_account=false,found_selected=false;std::string previous;unsigned maximum=0;
    for(const auto& op:p["read_operations"].GetArray()){
        if(!string(op))return false;const auto name=text(op);
        if(name<=previous||!p["operation_profiles"].HasMember(name.c_str()))return false;previous=name;
        QmtBoundProfile kind;
        if(name=="account.trade_detail")kind=QmtBoundProfile::AccountV3;
        else if(name=="market.full_tick")kind=QmtBoundProfile::FullTickV3;
        else if(name=="market.history_1m")kind=QmtBoundProfile::History1mV3;
        else return false;
        const auto& d=p["operation_profiles"][name.c_str()];
        if(!keys(d,{"policy_id","policy_version","execution_timeout_ms","limits"})||!field(d,"policy_id")
            ||text(d["policy_id"])!=policy(kind)||!field(d,"policy_version")
            ||(text(d["policy_version"])!=account_fields::policy_version
                &&!(v4&&kind==QmtBoundProfile::AccountV3&&account_fields::has_order_identity(text(d["policy_version"]))))
            ||!integer(d["execution_timeout_ms"],100,30000))return false;
        maximum=std::max(maximum,d["execution_timeout_ms"].GetUint());const auto& l=d["limits"];
        if(kind==QmtBoundProfile::AccountV3){
            if(!account_limits(l,cap,account))return false;
            account.policy_version=text(d["policy_version"]);found_account=true;
        }
        else if(kind==QmtBoundProfile::FullTickV3){if(!keys(l,{}))return false;}
        else{
            if(!keys(l,{"schema_version","max_calendar_days","max_rows","max_data_bytes"})||!field(l,"schema_version")
                ||text(l["schema_version"])!="qmt.history-1m.v1"||!integer(l["max_calendar_days"],1,5)
                ||!integer(l["max_rows"],1,2000)||!integer(l["max_data_bytes"],1024,cap-4096))return false;
            days=l["max_calendar_days"].GetUint();rows=l["max_rows"].GetUint();bytes=static_cast<std::size_t>(l["max_data_bytes"].GetUint64());
        }
        if(name==operation(selected)){found_selected=true;execution=d["execution_timeout_ms"].GetUint();}
    }
    if(!found_account||!found_selected||maximum!=p["execution_timeout_ms"].GetUint())return false;
    if(v4){
        QmtTradeReadDescriptor descriptor;
        if(!trade_descriptor(p["trade_profile"],descriptor)||!trade_control(c,cap,descriptor))return false;
        if(trade)*trade=std::move(descriptor);
    }
    return true;
}
// v6组合能力只授本门面full_tick。历史准备descriptor完整核验后仍无调用入口。
bool profile_v6(const Value& p,std::size_t cap,std::uint32_t& execution,bool retained=false)
{
    std::uint32_t lifetime=0;
    const bool shape=retained?keys(p,{"read_profile_version","read_operations","execution_timeout_ms","control_profile","operation_profiles","read_retention"})
        :keys(p,{"read_profile_version","read_operations","execution_timeout_ms","control_profile","operation_profiles"});
    if(cap<8192||cap>2097152||!shape||(retained&&(!retained_profile(p,lifetime)||!lifetime))
        ||!field(p,"read_profile_version")||text(p["read_profile_version"])!="qmt.read-profile.v6"
        ||!p["read_operations"].IsArray()||p["read_operations"].Size()<2||p["read_operations"].Size()>4
        ||!p["operation_profiles"].IsObject()||p["operation_profiles"].MemberCount()!=p["read_operations"].Size()
        ||!integer(p["execution_timeout_ms"],100,30000)||!base_control(p["control_profile"]))return false;
    const auto& c=p["control_profile"];
    for(auto key:{"max_pending_calls","max_call_bytes","max_reply_bytes","max_retained_bytes","max_cycle_messages","max_cycle_bytes"})
        if(!integer(c[key],1,(1ULL<<53)-1))return false;
    for(auto key:{"poll_seconds","max_call_seconds"})if(!positive_number(c[key],600))return false;
    bool full_tick=false,preparation=false;std::string previous;unsigned maximum=0,next_execution=0;
    for(const auto& op:p["read_operations"].GetArray()){
        if(!string(op))return false;const auto name=text(op);
        if(name<=previous||!p["operation_profiles"].HasMember(name.c_str()))return false;previous=name;
        const char* expected=nullptr;
        if(name=="market.full_tick")expected="qmt.standard-read.v1";
        else if(name=="market.history_1m")expected="qmt.history-read.v1";
        else if(name=="market.history_prepare")expected="qmt.history-preparation.v1";
        else if(name=="account.trade_detail")expected="qmt.account-read.v1";
        else return false;
        const auto& d=p["operation_profiles"][name.c_str()];
        if(!keys(d,{"policy_id","policy_version","execution_timeout_ms","limits"})||!field(d,"policy_id")
            ||text(d["policy_id"])!=expected||!field(d,"policy_version")||text(d["policy_version"])!="1.0"
            ||!integer(d["execution_timeout_ms"],100,30000))return false;
        maximum=std::max(maximum,d["execution_timeout_ms"].GetUint());const auto& l=d["limits"];
        if(name=="market.full_tick"){
            if(!keys(l,{}))return false;full_tick=true;next_execution=d["execution_timeout_ms"].GetUint();
        }else if(name=="market.history_1m"){
            if(!keys(l,{"schema_version","max_calendar_days","max_rows","max_data_bytes"})||!field(l,"schema_version")
                ||text(l["schema_version"])!="qmt.history-1m.v1"||!integer(l["max_calendar_days"],1,5)
                ||!integer(l["max_rows"],1,2000)||!integer(l["max_data_bytes"],1024,cap-4096))return false;
        }else if(name=="account.trade_detail"){
            AccountLimits ignored;if(!account_limits(l,cap,ignored))return false;
        }else{
            if(!field(l,"schema_version"))return false;
            const auto version=text(l["schema_version"]);
            const bool v1=version=="qmt.history-preparation-limits.v1";
            // v3由来源扩展历史准备的市场范围；本门面仍只调用full_tick，沿用v2字段及预算核验。
            if(!v1&&version!="qmt.history-preparation-limits.v2"
                &&version!="qmt.history-preparation-limits.v3")return false;
            const bool shape=v1?keys(l,{"schema_version","symbols","periods","max_calendar_days","max_tasks","max_queued","total_timeout_ms"})
                :keys(l,{"schema_version","periods","max_calendar_days","max_tasks","max_queued","total_timeout_ms"});
            if(!shape||(v1&&(!l["symbols"].IsArray()||l["symbols"].Empty()||l["symbols"].Size()>128))
                ||!l["periods"].IsArray()||l["periods"].Empty()||l["periods"].Size()>2
                ||!keys(l["max_calendar_days"],{"1m","1d"})
                ||!integer(l["max_calendar_days"]["1m"],1,36600)||!integer(l["max_calendar_days"]["1d"],1,36600)
                ||!integer(l["max_tasks"],1,1024)||!integer(l["max_queued"],1,1024)
                ||l["max_queued"].GetUint()>l["max_tasks"].GetUint()
                ||!integer(l["total_timeout_ms"],100,30000)||d["execution_timeout_ms"].GetUint()>l["total_timeout_ms"].GetUint())return false;
            std::string last;
            if(v1){
                for(const auto& symbol:l["symbols"].GetArray()){
                    if(!string(symbol,9)||symbol.GetStringLength()!=9)return false;const auto s=text(symbol);
                    if(s<=last||!std::all_of(s.begin(),s.begin()+6,[](char ch){return ch>='0'&&ch<='9';})
                        ||(s.substr(6)!=".SH"&&s.substr(6)!=".SZ"))return false;last=s;
                }
            }
            last.clear();for(const auto& period:l["periods"].GetArray()){
                if(!string(period,2))return false;const auto s=text(period);
                if(s<=last||(s!="1m"&&s!="1d"))return false;last=s;
            }
            preparation=true;
        }
    }
    if(!full_tick||!preparation||maximum!=p["execution_timeout_ms"].GetUint())return false;
    execution=next_execution;return true;
}
bool utc6(const Value& v)
{
    if(!completed_at(v)||v.GetStringLength()!=27)return false;
    const auto s=text(v);if(s[19]!='.'||s[26]!='Z')return false;
    return std::all_of(s.begin()+20,s.begin()+26,[](char c){return c>='0'&&c<='9';});
}
bool account_scalar(const Value& v)
{
    if(v.IsNull()||v.IsBool()||v.IsString())return true;
    if(v.IsUint64())return v.GetUint64()<=(1ULL<<53)-1;
    if(v.IsInt64())return v.GetInt64()>=-((1LL<<53)-1)&&v.GetInt64()<=(1LL<<53)-1;
    return v.IsDouble()&&std::isfinite(v.GetDouble());
}
struct AccountBudget {
    std::size_t nodes=0,characters=0;
    const AccountLimits& limits;SignedHttpDeadline& until;
    bool count(const Value& v){
        if(!until.remaining()||nodes>=limits.nodes)return false;++nodes;
        if(v.IsString()){
            std::size_t count=0;for(unsigned i=0;i<v.GetStringLength();++i){
                if(i%4096==0&&!until.remaining())return false;
                if((static_cast<unsigned char>(v.GetString()[i])&0xc0)!=0x80)++count;
            }
            if(count>limits.characters-characters)return false;characters+=count;
        }else if(v.IsObject()){
            for(auto i=v.MemberBegin();i!=v.MemberEnd();++i)if(!count(i->name)||!count(i->value))return false;
        }else if(v.IsArray()){
            for(const auto& item:v.GetArray())if(!count(item))return false;
        }else if(!account_scalar(v))return false;
        return until.remaining()!=0;
    }
};
template<std::size_t N>bool allowed_account_field(const Value& key,const char* const (&names)[N])
{return std::any_of(names,names+N,[&](const char* name){return text(key)==name;});}
bool account_data(const std::string& raw,const Value& v,const Value& args,const AccountLimits& limits,SignedHttpDeadline& until,std::string& original)
{
    if(!account_arguments(args)||!keys(v,{"schema_version","account_binding","query","execution","completeness","trading_date","rows"})
        ||!field(v,"schema_version")||text(v["schema_version"])!=(limits.policy_version==account_fields::fee_policy_version?account_fields::fee_schema:
            limits.policy_version==account_fields::identity_policy_version?account_fields::identity_schema:account_fields::schema)||!account_binding(v["account_binding"],true))return false;
    const auto& binding=v["account_binding"];
    if(text(binding["account_id"])!=limits.account_id||text(binding["account_environment"])!=limits.environment)return false;
    const auto& query=v["query"];
    if(!keys(query,{"account_type","datatype","scope","strategy_name"})||!query["strategy_name"].IsNull())return false;
    for(auto key:{"account_type","datatype","scope"})if(!field(query,key)||text(query[key])!=text(args[key]))return false;
    const auto& execution=v["execution"];
    if(!keys(execution,{"started_at","completed_at"})||!utc6(execution["started_at"])||!utc6(execution["completed_at"])
        ||text(execution["completed_at"])<text(execution["started_at"]))return false;
    const auto& complete=v["completeness"];
    if(!keys(complete,{"complete","truncated","row_count","coverage"})||!complete["complete"].IsBool()||!complete["complete"].GetBool()
        ||!complete["truncated"].IsBool()||complete["truncated"].GetBool()||!integer(complete["row_count"],0,limits.rows)
        ||!field(complete,"coverage")||text(complete["coverage"])!="sdk_returned_list"
        ||!v["rows"].IsArray()||v["rows"].Size()!=complete["row_count"].GetUint64())return false;
    const auto type=text(args["datatype"]);if(type=="account"&&v["rows"].Size()!=1)return false;
    const auto& date=v["trading_date"];
    if(!keys(date,{"value","source"})||!date["value"].IsNull()||!field(date,"source")||text(date["source"])!="unavailable")return false;
    for(const auto& row:v["rows"].GetArray()){
        if(!until.remaining()||!row.IsObject())return false;
        for(auto i=row.MemberBegin();i!=row.MemberEnd();++i){
            const bool identity_field=account_fields::has_order_identity(limits.policy_version)
                &&(type=="order"||type=="deal")&&allowed_account_field(i->name,account_fields::identity_fields);
            const bool fee_field=limits.policy_version==account_fields::fee_policy_version
                &&type=="deal"&&allowed_account_field(i->name,account_fields::trade_fee_fields);
            const bool allowed=identity_field||fee_field||(type=="position"?allowed_account_field(i->name,guanheng::account_fields::position_fields):
                type=="order"?allowed_account_field(i->name,guanheng::account_fields::order_fields):
                type=="deal"?allowed_account_field(i->name,guanheng::account_fields::trade_fields):allowed_account_field(i->name,guanheng::account_fields::account_fields));
            if(!allowed||!account_scalar(i->value))return false;
            const auto key=text(i->name);
            if(key==account_fields::account&&(!i->value.IsString()||text(i->value)!=limits.account_id))return false;
            // QAR-R4：来源空币种保留原字节，部署CNY声明由账户绑定独立持有。
            if(key==account_fields::money&&(!i->value.IsString()
                ||(i->value.GetStringLength()!=0&&text(i->value)!="CNY")))return false;
        }
    }
    AccountBudget budget{0,0,limits,until};if(!budget.count(v))return false;
    std::size_t start=0,length=0;if(!data_span(raw,start,length,until)||length>limits.bytes||!until.remaining())return false;
    original=raw.substr(start,length);return until.remaining()!=0;
}

std::string semantic_sha(const Value& request)
{
    Document value;value.SetObject();auto& a=value.GetAllocator();
    value.AddMember("operation_id",Value(request["operation_id"],a),a);
    value.AddMember("arguments",Value(request["arguments"],a),a);return signed_http_sha256(encode(value));
}
const char* binding_version(QmtBoundProfile profile)
{return profile==QmtBoundProfile::AccountV4?"2.0":"1.0";}
bool request(const QmtBoundReceipt& receipt,Document& body,Document& pin,QmtBoundProfile profile=QmtBoundProfile::FullTickV1)
{
    if(!parse(receipt.binding_json,pin,4096)||!binding(pin,nullptr,binding_version(profile))||!parse(receipt.request_body,body,65536)
        ||!keys(body,{"request_id","correlation_id","operation_id","arguments","timeout_ms","policy_id","policy_version","priority_class"})
        ||!uuid(body["request_id"])||!uuid(body["correlation_id"])||!field(body,"operation_id")||text(body["operation_id"])!=operation(profile)
        ||!field(body,"policy_id")||text(body["policy_id"])!=policy(profile)
        ||!field(body,"policy_version")||(text(body["policy_version"])!=account_fields::policy_version
            &&!(profile==QmtBoundProfile::AccountV4&&account_fields::has_order_identity(text(body["policy_version"]))))
        ||!field(body,"priority_class")||text(body["priority_class"])!="normal"
        ||!body["timeout_ms"].IsUint()||body["timeout_ms"].GetUint()<100||body["timeout_ms"].GetUint()>30000
        ||!operation_arguments(profile,body["arguments"]))return false;
    if(!receipt.retention_ticket_json.empty()){
        if(profile!=QmtBoundProfile::AccountV3&&profile!=QmtBoundProfile::AccountV4&&profile!=QmtBoundProfile::FullTickRetainedV6)return false;
        Document ticket,original;std::uint32_t lifetime=0,execution=0;unsigned days=0,rows=0;std::size_t bytes=0;AccountLimits account;
        if(!parse(receipt.retention_ticket_json,ticket,256)||retained_id(body,ticket)!=text(body["request_id"])
            ||text(ticket["epoch"])!=text(pin["host_instance_id"])
            ||!parse(receipt.read_profile_body,original,4096)||!retained_profile(original,lifetime)
            ||(!lifetime&&profile!=QmtBoundProfile::AccountV4)
            ||signed_http_sha256(receipt.read_profile_body)!=text(pin["capability_sha256"])
            ||(profile==QmtBoundProfile::FullTickRetainedV6
                ?!profile_v6(original,receipt.read_result_capacity,execution,true)
                :!profile_v3(original,receipt.read_result_capacity,profile,execution,days,rows,bytes,account))
            ||body["timeout_ms"].GetUint()>execution)return false;
    }
    if(profile==QmtBoundProfile::FullTickRetainedV6&&receipt.retention_ticket_json.empty())return false;
    if(profile==QmtBoundProfile::AccountV4){
        // 新 receipt 保存原 profile 与联合容量；旧 v4/1.0 两字段收据沿原绑定复核路径。
        if(receipt.read_profile_body.empty())
            return receipt.read_result_capacity==0&&text(body["policy_version"])==account_fields::policy_version;
        Document original;std::uint32_t execution=0;unsigned days=0,rows=0;std::size_t bytes=0;AccountLimits account;
        if(receipt.read_profile_body.size()>4096||signed_http_sha256(receipt.read_profile_body)!=text(pin["capability_sha256"])
            ||!parse(receipt.read_profile_body,original,4096)
            ||!profile_v3(original,receipt.read_result_capacity,profile,execution,days,rows,bytes,account)
            ||text(body["policy_version"])!=account.policy_version||body["timeout_ms"].GetUint()>execution)return false;
    }
    return true;
}
}

Status validate_qmt_trade_read_profile(const std::string& raw,std::size_t max_result_bytes,
    const QmtExpectedAccount& expected,QmtTradeReadDescriptor& out)
{
    try{
        if(expected.environment!=QmtAccountEnvironment::Simulation&&expected.environment!=QmtAccountEnvironment::Live)
            return fail(ErrorCode::InvalidInput,"qmt_account_binding_invalid");
        Document profile;std::uint32_t execution=0;unsigned days=0,rows=0;std::size_t bytes=0;
        AccountLimits account;QmtTradeReadDescriptor candidate;
        if(!parse(raw,profile,4096)||!profile_v3(profile,max_result_bytes,QmtBoundProfile::AccountV4,
            execution,days,rows,bytes,account,&candidate))return fail(ErrorCode::InvalidInput,"qmt_host_profile_invalid");
        if(account.account_id!=expected.account_id||account.environment!=
            (expected.environment==QmtAccountEnvironment::Simulation?"simulation":"live"))
            return fail(ErrorCode::Conflict,"qmt_account_binding_changed");
        // 所有解析、摘要字符串与联合容量完成后才移动发布；失败保留调用者旧值。
        static_assert(std::is_nothrow_move_assignable<QmtTradeReadDescriptor>::value,"descriptor publication must not allocate");
        out=std::move(candidate);return {};
    // 资源异常保留原类型，不能被下游.ok()/bool准入折叠为结构错误。
    // 此出口不构造Status或诊断；candidate尚未发布，out仍为调用者原值。
    }catch(const std::bad_alloc&){throw;}
    catch(...){return fail(ErrorCode::InvalidInput,"qmt_host_profile_invalid");}
}

// 请求级控制随同步栈传递，绝不借换实例control；普通查询仍由原control拥有。
class QmtBoundReadCore::RequestControl
{
public:
    RequestControl(QmtAccountReadControlResult* out,const QmtAccountControl* requested)
        :out_(out?out:&local_),requested_(requested){*out_={QmtAccountReadOutcome::Failure,QmtAccountReadStage::None};}
    bool stopped(const QmtHistoryControl* ordinary)const noexcept
    {return (ordinary&&ordinary->stop_requested())||(requested_&&requested_->stop_requested());}
    Status gate(BoundedSignedHttp& http,SignedHttpDeadline& until,const QmtHistoryControl* ordinary,QmtAccountReadStage stage)
    {
        out_->stage=stage;
        auto status=http.check();if(!status.ok())return status;
        if(!until.remaining())return fail(ErrorCode::Timeout,"qmt_host_deadline");
        if(stopped(ordinary)){
            auto result=fail(ErrorCode::Pending,"qmt_account_control_stopped");
            out_->outcome=QmtAccountReadOutcome::ControlStoppedBeforeStage;return result;
        }
        return {};
    }
    QmtAccountReadStage stage()const noexcept{return out_->stage;}
    void failed()noexcept{out_->outcome=QmtAccountReadOutcome::Failure;}
    void failed(QmtAccountReadStage stage)noexcept{out_->outcome=QmtAccountReadOutcome::Failure;out_->stage=stage;}
    bool control_stopped()const noexcept{return out_->outcome==QmtAccountReadOutcome::ControlStoppedBeforeStage;}
    void success()noexcept{*out_={};}
private:
    QmtAccountReadControlResult local_;
    QmtAccountReadControlResult* out_;
    const QmtAccountControl* requested_;
};

class QmtBoundReadCore::Impl
{
public:
    BoundedSignedHttp http;
    QmtBoundProfile profile_kind;
    const QmtHistoryControl* control;
    std::shared_ptr<const void> token_owner=std::make_shared<const int>(0);
    std::uint64_t prepare_generation=0;
    std::string profile_body;
    unsigned history_days=5,history_rows=2000;
    std::size_t history_bytes=2093056;
    QmtHistoryPage last_page;
    AccountLimits account_limits_;
    QmtExpectedAccount expected_account;
    std::string last_account_data;
    std::string last_error;
    bool history()const{return profile_kind==QmtBoundProfile::History1mV2||profile_kind==QmtBoundProfile::History1mV3;}
    bool account()const{return profile_kind==QmtBoundProfile::AccountV3||profile_kind==QmtBoundProfile::AccountV4;}
    bool retained_snapshot()const{return profile_kind==QmtBoundProfile::FullTickRetainedV6;}
    bool full_tick_v6()const{return profile_kind==QmtBoundProfile::FullTickV6||retained_snapshot();}
    bool prepared_operation()const{return history()||account();}
    bool v3()const{return profile_kind==QmtBoundProfile::FullTickV3||profile_kind==QmtBoundProfile::History1mV3||account();}
    bool stopped()const{return prepared_operation()&&control&&control->stop_requested();}
    std::size_t response_cap;
    std::string pin;
    SourceSession source;
    bool ready=false;
    std::uint32_t execution_ms=0;
    std::uint32_t retention_lifetime=0;
    std::size_t request_cap=0,result_cap=2097152,http_request_cap=0,http_response_cap=4*((2097152+2)/3)+16384;
    explicit Impl(QmtHttpConfig config,QmtBoundProfile kind,const QmtHistoryControl* stop,const QmtExpectedAccount* expected)
        :http(config),profile_kind(kind),control(stop),response_cap(config.max_response_bytes){
            if(kind!=QmtBoundProfile::FullTickV1&&kind!=QmtBoundProfile::History1mV2&&!v3()&&!full_tick_v6())
                throw std::invalid_argument("qmt_bound_profile_invalid");
            if(account()){
                if(!expected||expected->account_id.empty()||expected->account_id.size()>63
                    ||(expected->environment!=QmtAccountEnvironment::Simulation&&expected->environment!=QmtAccountEnvironment::Live))
                    throw std::invalid_argument("qmt_account_binding_invalid");
                Document candidate;candidate.SetObject();add(candidate,"account_id",expected->account_id);
                add(candidate,"account_environment",expected->environment==QmtAccountEnvironment::Simulation?"simulation":"live");
                add(candidate,"currency","CNY");add(candidate,"financial_profile","cny_cash_shsz_v1");
                Document checked;if(!parse(encode(candidate),checked,4096)||!account_binding(checked))
                    throw std::invalid_argument("qmt_account_binding_invalid");
                expected_account=*expected;
            }
        }
    Status read_binding(SignedHttpDeadline& until,std::string& observed,SourceSession& identity,
        RequestControl* request_control=nullptr,QmtAccountReadStage stage=QmtAccountReadStage::Binding)
    {
        if(request_control){auto checked=request_control->gate(http,until,control,stage);if(!checked.ok())return checked;}
        auto response=http.read_binding(until,16384,[&]{
            if(request_control)return request_control->gate(http,until,control,stage);
            return stopped()?fail(ErrorCode::Pending,"qmt_account_interrupted"):Status{};
        });
        if(!response.status.ok())return response.status;
        if(response.code!=200)return signed_http_error(response.code);
        Document value;
        if(!parse(response.body,value,16384)||!keys(value,{"schema_version","binding","binding_sha256","read_profile_body_b64","read_profile_body_sha256","limits","order_ready"})
            ||!field(value,"schema_version")||text(value["schema_version"])!=version||!binding(value["binding"],&identity,binding_version(profile_kind))
            ||!hex(value["binding_sha256"],64)||!hex(value["read_profile_body_sha256"],64)
            ||!value["order_ready"].IsBool()||value["order_ready"].GetBool())return fail(ErrorCode::IoError,"qmt_host_binding_invalid");
        observed=encode(value["binding"]);
        std::string profile_bytes;Document profile;
        if(signed_http_sha256(observed)!=text(value["binding_sha256"])
            ||!unbase64(value["read_profile_body_b64"],4096,profile_bytes)
            ||signed_http_sha256(profile_bytes)!=text(value["read_profile_body_sha256"])
            ||text(value["read_profile_body_sha256"])!=text(value["binding"]["capability_sha256"])
            ||!parse(profile_bytes,profile,4096))return fail(ErrorCode::IoError,"qmt_host_profile_invalid");
        if(!v3()&&!history()&&!full_tick_v6()&&(!keys(profile,{"read_operations","execution_timeout_ms","control_profile"})
            ||!profile["read_operations"].IsArray()||profile["read_operations"].Size()!=1
            ||!string(profile["read_operations"][0])||text(profile["read_operations"][0])!="market.full_tick"
            ||!profile["execution_timeout_ms"].IsUint()||profile["execution_timeout_ms"].GetUint()<100||profile["execution_timeout_ms"].GetUint()>30000
            ||!base_control(profile["control_profile"])))
            return fail(ErrorCode::IoError,"qmt_host_profile_invalid");
        const auto& limits=value["limits"];
        const bool http_retention=limits.IsObject()&&limits.HasMember("http_read_retention");
        if(!(http_retention?keys(limits,{"max_request_bytes","max_result_bytes","max_http_request_bytes","max_http_response_bytes","http_read_retention"})
            :keys(limits,{"max_request_bytes","max_result_bytes","max_http_request_bytes","max_http_response_bytes"})))return fail(ErrorCode::IoError,"qmt_host_limits_invalid");
        for(auto key:{"max_request_bytes","max_result_bytes","max_http_request_bytes","max_http_response_bytes"})
            if(!limits[key].IsUint64())return fail(ErrorCode::IoError,"qmt_host_limits_invalid");
        const auto req=limits["max_request_bytes"].GetUint64(),res=limits["max_result_bytes"].GetUint64();
        const auto hreq=limits["max_http_request_bytes"].GetUint64(),hres=limits["max_http_response_bytes"].GetUint64();
        if(!req||req>65536||res<1024||res>2097152||hreq<8192||hreq>4194304||req>(hreq-4096)*3/4
            ||hres!=4*((res+2)/3)+16384||response_cap<hres)return fail(ErrorCode::Backpressure,"qmt_host_limits_unusable");
        if(!v3()&&history()&&!history_profile(profile,static_cast<std::size_t>(res),execution_ms,history_days,history_rows,history_bytes))
            return fail(ErrorCode::IoError,"qmt_host_profile_invalid");
        if(full_tick_v6()){
            if(!profile_v6(profile,static_cast<std::size_t>(res),execution_ms,retained_snapshot()))return fail(ErrorCode::IoError,"qmt_host_profile_invalid");
        }else if(v3()){
            auto next_execution=execution_ms;auto next_days=history_days,next_rows=history_rows;auto next_bytes=history_bytes;
            AccountLimits next_account;
            if(!profile_v3(profile,static_cast<std::size_t>(res),profile_kind,next_execution,next_days,next_rows,next_bytes,next_account))
                return fail(ErrorCode::IoError,"qmt_host_profile_invalid");
            if(account()&&(next_account.account_id!=expected_account.account_id||next_account.environment!=
                (expected_account.environment==QmtAccountEnvironment::Simulation?"simulation":"live")))
                return fail(ErrorCode::Conflict,"qmt_account_binding_changed");
            // 完整组合 descriptor 与绑定共同准入后才替换本轮能力快照。
            account_limits_=std::move(next_account);execution_ms=next_execution;
            history_days=next_days;history_rows=next_rows;history_bytes=next_bytes;
        }else if(!history())execution_ms=profile["execution_timeout_ms"].GetUint();
        std::uint32_t next_retention=0;
        if((account()||retained_snapshot())&&!retained_profile(profile,next_retention))return fail(ErrorCode::IoError,"qmt_host_profile_invalid");
        if(http_retention&&(profile_kind!=QmtBoundProfile::AccountV4||next_retention
            ||!read_retention_capability(limits["http_read_retention"],next_retention)))
            return fail(ErrorCode::IoError,"qmt_host_http_retention_invalid");
        retention_lifetime=next_retention;
        profile_body=std::move(profile_bytes);request_cap=static_cast<std::size_t>(req);result_cap=static_cast<std::size_t>(res);
        http_request_cap=static_cast<std::size_t>(hreq);http_response_cap=static_cast<std::size_t>(hres);return {};
    }
    Status verify(SignedHttpDeadline& until,const std::string& expected,RequestControl* request_control=nullptr,
        QmtAccountReadStage stage=QmtAccountReadStage::Verify)
    {
        std::string observed;SourceSession identity;auto status=read_binding(until,observed,identity,request_control,stage);
        if(!status.ok()||observed!=expected){
            if(!request_control||!request_control->control_stopped())ready=false;
            return status.ok()?fail(ErrorCode::StaleSession,"qmt_host_binding_changed"):status;
        }
        return {};
    }
    Status capacity(SignedHttpDeadline& until,RequestControl* request_control)
    {
        if((!account()&&!retained_snapshot())||!retention_lifetime)return {};
        for(;;){
            if(request_control){auto checked=request_control->gate(http,until,control,QmtAccountReadStage::Verify);if(!checked.ok())return checked;}
            else if(stopped())return fail(ErrorCode::Pending,"qmt_account_interrupted");
            if(!until.remaining())return fail(ErrorCode::Timeout,"qmt_host_deadline");
            auto response=http.exchange("GET","/internal/v1/read-retention-status",{},until,16384);
            if(!response.status.ok())return response.status;
            if(response.code!=200)return signed_http_error(response.code);
            Document value;
            if(!parse(response.body,value,16384)||!field(value,"schema")||text(value["schema"])!="qmt.read-retention-status.v1")
                return fail(ErrorCode::IoError,"qmt_read_retention_status_invalid");
            for(auto key:{"capacity","retained","held_unknown","awaiting_consumer","queued_or_running","awaiting_ticket_end"})
                if(!value.HasMember(key)||!integer(value[key],0,(1ULL<<53)-1))return fail(ErrorCode::IoError,"qmt_read_retention_status_invalid");
            if(!value["capacity"].GetUint64())return fail(ErrorCode::IoError,"qmt_read_retention_status_invalid");
            if(value["retained"].GetUint64()<value["capacity"].GetUint64())return {};
            if(value["held_unknown"].GetUint64()||value["awaiting_consumer"].GetUint64()||value["queued_or_running"].GetUint64())
                return fail(ErrorCode::Pending,"qmt_read_retention_held_responsibility");
            // 只等待已消费票据原期限结束。整个等待继续消耗调用方原D，不扩大配额。
            std::this_thread::sleep_for(std::chrono::milliseconds(std::min<std::uint32_t>(25,until.remaining())));
        }
    }
    Status consumed(const QmtBoundResult& output,SignedHttpDeadline& until,RequestControl* request_control)
    {
        if(output.receipt.retention_ticket_json.empty())return {};
        if(request_control){auto checked=request_control->gate(http,until,control,QmtAccountReadStage::Publish);if(!checked.ok())return checked;}
        else if(stopped())return fail(ErrorCode::Pending,"qmt_account_interrupted");
        if(!until.remaining())return fail(ErrorCode::Timeout,"qmt_host_deadline");
        Document body;body.SetObject();add(body,"schema","qmt.read-consumed.v1");
        add(body,"request_body_sha256",signed_http_sha256(output.receipt.request_body));
        add(body,"result_body_sha256",signed_http_sha256(output.native_result_json));
        auto response=http.exchange_observed("POST","/internal/v1/read-results/"+output.result.request_id+"/consumed",
            encode(body),until,16384,{output.result.request_id,RequestJournalEvidence::Confirmed});
        // 本进程已持有并验完原结果。完整410确认消费责任已经结束，须先解释业务
        // 回复再处理运输层的通用错误分类，避免重复确认把正常回收变成硬故障。
        if(response.response_complete&&response.code==410){
            Document gone;
            if(parse(response.body,gone,16384)&&keys(gone,{"error_code","error_message"})
                &&field(gone,"error_code")&&text(gone["error_code"])=="read_result_unretained"
                &&string(gone["error_message"],4096))return {};
        }
        if(!response.status.ok())return response.status;
        Document value;if(!parse(response.body,value,16384))return fail(ErrorCode::IoError,"qmt_read_consumed_invalid");
        if(response.code!=200)return signed_http_error(response.code);
        if(!keys(value,{"schema","request_id","consumed","retained"})||!value["retained"].IsBool()||!field(value,"schema")||text(value["schema"])!="qmt.read-consumed-result.v1"
            ||!field(value,"request_id")||text(value["request_id"])!=output.result.request_id||!value["consumed"].IsBool()||!value["consumed"].GetBool())
            return fail(ErrorCode::IoError,"qmt_read_consumed_invalid");
        return until.remaining()?Status{}:fail(ErrorCode::Timeout,"qmt_host_deadline");
    }
    Status prepare(std::uint32_t milliseconds)
    {
        auto status=http.check();if(!status.ok())return status;
        ready=false;source={};pin.clear();
        if(!milliseconds||milliseconds>30000)return fail(ErrorCode::InvalidInput,"qmt_host_budget_invalid");
        SignedHttpDeadline until(milliseconds);std::string observed;SourceSession identity;
        status=read_binding(until,observed,identity);if(!status.ok())return status;
        status=verify(until,observed);if(!status.ok())return status;
        if(!until.remaining())return fail(ErrorCode::Timeout,"qmt_host_deadline");
        pin=std::move(observed);source=std::move(identity);ready=true;++prepare_generation;return {};
    }
    QmtBoundResult follow(QmtBoundResult output,SignedHttpDeadline& until,SignedHttpResult response,bool get,
        RequestControl* request_control=nullptr,const std::string* original_wire=nullptr,bool initial_submit=false)
    {
        // 身份/receipt/unknown诊断在I/O前已分配；后续异常仍返回这些原值。
        try {
        const auto& receipt=output.receipt;Document body,b;
        // 只有原submit_once首POST运输未知进入的GET可再投一次；公开resume没有原wire能力。
        const bool redelivery_allowed=original_wire&&get;bool redelivered=false,journal_confirmed=false;
        auto failure=[&](Status status){output.result.status=std::move(status);return std::move(output);};
        if(!request(receipt,body,b,profile_kind))return failure(fail(ErrorCode::InvalidInput,"qmt_host_receipt_invalid"));
        // 当前已认证账户能力要求显式原票据；公开receipt删字段不能绕过消费交接。
        if((account()||retained_snapshot())&&retention_lifetime&&receipt.retention_ticket_json.empty())
            return failure(fail(ErrorCode::InvalidInput,"qmt_host_receipt_invalid"));
        const auto request_id=text(body["request_id"]),operation=text(body["operation_id"]);
        output.result.request_id=request_id;output.result.operation_id=operation;
        auto observe=[&](const SignedHttpResult& value){
            if(value.code||!value.body.empty()){
                output.result.http_status=value.code;output.result.envelope_json=value.body;
            }
        };
        observe(response); // 首次POST已有部分响应时，GET截止/失败仍保留最近原件。
        for(;;){
            if(!request_control&&stopped())return failure(fail(ErrorCode::Pending,"qmt_history_interrupted"));
            if(get){
                // POST的真实运输失败先保留；停止不能把它重命名为正常控制退出。
                if(request_control&&!response.status.ok()&&request_control->stopped(control))return failure(response.status);
                if(request_control){
                    const auto previous_stage=request_control->stage();
                    auto checked=request_control->gate(http,until,control,QmtAccountReadStage::Result);
                    if(!checked.ok()){
                        if(!response.status.ok()&&request_control->control_stopped()){request_control->failed(previous_stage);return failure(response.status);}
                        return failure(checked);
                    }
                }
                if(!until.remaining())return failure(fail(ErrorCode::Timeout,"qmt_host_deadline"));
                response=http.exchange_observed("GET","/internal/v1/bound-results/"+request_id,{},until,http_response_cap,
                    {request_id,journal_confirmed?RequestJournalEvidence::Confirmed:RequestJournalEvidence::Unknown});
            }
            observe(response);
            // 认证Host保留在途、未知和未消费结果。原账户票据查询收到这个完整410，
            // 表示旧读取责任结束，供owner开始新一轮查询；它不提供任何账户事实。
            // 交易命令及其它410仍保持原错误语义。
            if(account()&&!receipt.retention_ticket_json.empty()&&response.response_complete&&response.code==410){
                Document gone;
                if(parse(response.body,gone,16384)&&keys(gone,{"error_code","error_message"})
                    &&field(gone,"error_code")&&text(gone["error_code"])=="read_ticket_ended_unretained"
                    &&string(gone["error_message"],4096))
                    return failure(fail(ErrorCode::Unavailable,"qmt_read_ticket_ended_unretained"));
            }
            if(account()&&get&&response.code==404&&response.response_complete
                &&response.status.code==ErrorCode::NotSupported&&response.status.reason=="qmt_http_endpoint_unavailable"){
                Document missing;
                if(parse_bounded_qmt_json(response.body,missing,8192,4096)
                    &&keys(missing,{"error_code","error_message"})&&field(missing,"error_code")
                    &&text(missing["error_code"])=="unknown_operation"&&string(missing["error_message"],4096)){
                    // 缺记录仍是原结果未知。原调用内以同B/ID/body/绝对D再投，Host事务去重；不续D。
                    if(!redelivery_allowed||redelivered||until.remaining()<100)
                        return failure(fail(ErrorCode::SubmissionUnknown,"qmt_host_result_unknown"));
                    auto checked=verify(until,receipt.binding_json,request_control);
                    if(!checked.ok())return failure(checked);
                    if(request_control){
                        checked=request_control->gate(http,until,control,QmtAccountReadStage::Submit);
                        if(!checked.ok())return failure(checked);
                    }
                    redelivered=true;get=false;
                    response=http.exchange_observed("POST","/internal/v1/bound-operations/"+operation,*original_wire,until,http_response_cap,{request_id});
                    if(!response.status.ok()&&response.delivery_unknown){
                        observe(response);
                        return failure(fail(ErrorCode::SubmissionUnknown,"qmt_host_result_unknown"));
                    }
                    continue;
                }
            }
            // 仅首POST的完整Host拒绝证明本轮未准入。续核/重投无法用新回复消除旧责任。
            if(account()&&initial_submit&&!get&&!redelivered&&response.response_complete
                &&!response.delivery_unknown&&response.code==400&&response.status.code==ErrorCode::InvalidInput){
                Document rejected;
                if(parse(response.body,rejected,16384)&&keys(rejected,{"error_code","error_message"})
                    &&field(rejected,"error_code")&&string(rejected["error_message"],4096)){
                    const auto code=text(rejected["error_code"]);
                    if(code=="invalid_arguments")return failure(fail(ErrorCode::Unavailable,"qmt_account_admission_invalid_arguments"));
                    if(code=="read_ticket_ended"&&!receipt.retention_ticket_json.empty())
                        return failure(fail(ErrorCode::Unavailable,"qmt_account_admission_ticket_ended"));
                }
            }
            if(!response.status.ok())return failure(response.status);
            if(response.code!=200&&response.code!=202)return failure(signed_http_error(response.code));
            Document value;
            if(!parse(response.body,value,http_response_cap)||!keys(value,{"schema_version","request_id","operation_id","request_sha256","request_body_sha256","binding_status","admitted_binding","dispatch_binding","result_binding","state","result_body_b64","result_body_sha256"})
                ||!field(value,"schema_version")||text(value["schema_version"])!=version||!field(value,"request_id")||!field(value,"operation_id")
                ||text(value["request_id"])!=request_id||text(value["operation_id"])!=operation
                ||!hex(value["request_sha256"],64)
                ||text(value["request_sha256"])!=semantic_sha(body)
                ||!field(value,"binding_status")||!field(value,"state"))return failure(fail(ErrorCode::Conflict,"qmt_host_result_identity_invalid"));
            const auto encoded_body=value["result_body_b64"].IsString()?value["result_body_b64"].GetStringLength():0;
            if(response.body.size()<encoded_body||response.body.size()-encoded_body>16384)
                return failure(fail(ErrorCode::Backpressure,"qmt_host_metadata_limit"));
            const auto state=text(value["state"]);
            if(response.code==202&&((state!="queued"&&state!="executing")
                ||!value["result_body_b64"].IsNull()||!value["result_body_sha256"].IsNull()))
                return failure(fail(ErrorCode::IoError,"qmt_host_progress_invalid"));
            if(response.code==200&&state!="terminal")return failure(fail(ErrorCode::IoError,"qmt_host_terminal_state_invalid"));
            if(text(value["binding_status"])=="legacy_unqualified"){
                if(!value["admitted_binding"].IsNull()||!value["dispatch_binding"].IsNull()||!value["result_binding"].IsNull()
                    ||(!value["request_body_sha256"].IsNull()&&!hex(value["request_body_sha256"],64)))
                    return failure(fail(ErrorCode::IoError,"qmt_host_legacy_record_invalid"));
                if(response.code==200&&!terminal_bytes(value,result_cap,output.native_result_json))
                    return failure(fail(ErrorCode::IoError,"qmt_host_result_bytes_invalid"));
                return failure(fail(ErrorCode::StaleSession,"qmt_host_legacy_source_unqualified"));
            }
            if(text(value["binding_status"])!="recorded"||!hex(value["request_body_sha256"],64)
                ||text(value["request_body_sha256"])!=signed_http_sha256(receipt.request_body))
                return failure(fail(ErrorCode::Conflict,"qmt_host_result_identity_invalid"));
            if(!binding(value["admitted_binding"],nullptr,binding_version(profile_kind))||encode(value["admitted_binding"])!=encode(b))
                return failure(fail(ErrorCode::StaleSession,"qmt_host_result_binding_unqualified"));
            for(auto key:{"dispatch_binding","result_binding"})
                if(!value[key].IsNull()&&(!binding(value[key],nullptr,binding_version(profile_kind))||encode(value[key])!=encode(b)))return failure(fail(ErrorCode::StaleSession,"qmt_host_result_binding_changed"));
            if(response.code==202){
                if(!value["result_binding"].IsNull()||(state=="queued"&&!value["dispatch_binding"].IsNull())
                    ||(state=="executing"&&value["dispatch_binding"].IsNull()))return failure(fail(ErrorCode::IoError,"qmt_host_progress_invalid"));
                journal_confirmed=true; // 同ID、正文与绑定均已核过的进度证明此请求已入库。
                const auto left=until.remaining();if(!left)return failure(fail(ErrorCode::Timeout,"qmt_host_deadline"));
                std::this_thread::sleep_for(std::chrono::milliseconds(std::min<std::uint32_t>(25,left)));get=true;continue;
            }
            if(!terminal_bytes(value,result_cap,output.native_result_json))return failure(fail(ErrorCode::IoError,"qmt_host_result_bytes_invalid"));
            Document native;
            if(!parse_bounded_qmt_json(output.native_result_json,native,result_cap)||!field(native,"request_id")||!field(native,"operation_id")
                ||text(native["request_id"])!=request_id||text(native["operation_id"])!=operation
                ||!native.HasMember("ok")||!native["ok"].IsBool()||!native.HasMember("completed_at")||!completed_at(native["completed_at"])
                ||!native.HasMember("result_sha256")||!hex(native["result_sha256"],64))return failure(fail(ErrorCode::IoError,"qmt_host_native_result_invalid"));
            if((prepared_operation()||retained_snapshot())&&!history_terminal(native,!receipt.retention_ticket_json.empty(),value["dispatch_binding"].IsNull()&&value["result_binding"].IsNull()))return failure(fail(ErrorCode::IoError,"qmt_host_native_result_invalid"));
            output.result.terminal=true;output.result.remote_ok=native["ok"].GetBool();
            if(!output.result.remote_ok){
                if((prepared_operation()||retained_snapshot())&&!value["dispatch_binding"].IsNull()&&!value["result_binding"].IsNull()){
                    // 已知业务失败保持Failure和原错误码；停止只禁止后继验证GET。
                    if(request_control)last_error=text(native["error_code"]);
                    if(request_control&&request_control->stopped(control))return failure(fail(ErrorCode::IoError,"qmt_host_native_operation_failed"));
                    auto checked=verify(until,encode(b),request_control,QmtAccountReadStage::FinalVerify);
                    if(!checked.ok()){
                        if(request_control&&request_control->control_stopped()){request_control->failed();return failure(fail(ErrorCode::IoError,"qmt_host_native_operation_failed"));}
                        return failure(checked);
                    }
                    if(!until.remaining())return failure(fail(ErrorCode::Timeout,"qmt_host_deadline"));
                    last_error=text(native["error_code"]);
                }
                if(!receipt.retention_ticket_json.empty()){
                    const auto code=text(native["error_code"]);bool confirmed=false;
                    for(auto known:{"preparation_not_executed","queue_timeout","source_binding_changed","queue_full","invalid_arguments","capability_unavailable"})
                        if(code==known)confirmed=true;
                    if(confirmed){
                        if(retained_snapshot())output.snapshot_consumption_ready=true;
                        else {auto checked=consumed(output,until,request_control);if(!checked.ok())return failure(checked);}
                    }
                }
                return failure(fail(ErrorCode::IoError,"qmt_host_native_operation_failed"));
            }
            if(value["dispatch_binding"].IsNull()||value["result_binding"].IsNull())return failure(fail(ErrorCode::StaleSession,"qmt_host_native_source_unqualified"));
            if(!native.HasMember("data"))return failure(fail(ErrorCode::IoError,"qmt_host_native_data_missing"));
#if defined(_WIN32) && defined(GH_QMT_HTTP_DRAIN_TESTING)
            // 独立测试制品注入真实异常；生产没有门控/导出，不接受运行配置触发。
            unsigned expected=2;if(bound_test_fault.compare_exchange_strong(expected,0))throw std::bad_alloc();
#endif
            // 新控制路径先核已到达的账户正文；同时停止不能遮蔽坏数据。
            bool account_validated=false;
            if(request_control&&account()){
                if(text(body["policy_version"])!=account_limits_.policy_version
                    ||(profile_kind==QmtBoundProfile::AccountV4&&!receipt.read_profile_body.empty()
                        &&(receipt.read_profile_body!=profile_body||receipt.read_result_capacity!=result_cap)))
                    return failure(fail(ErrorCode::Conflict,"qmt_account_profile_changed"));
                if(!account_data(output.native_result_json,native["data"],body["arguments"],account_limits_,until,last_account_data))
                    return failure(until.remaining()?fail(ErrorCode::IoError,"qmt_account_data_invalid"):fail(ErrorCode::Timeout,"qmt_host_deadline"));
                account_validated=true;
            }
            auto status=verify(until,encode(b),request_control,QmtAccountReadStage::FinalVerify);if(!status.ok())return failure(status);
            if(!until.remaining())return failure(fail(ErrorCode::Timeout,"qmt_host_deadline"));
            if(history()&&!history_data(output.native_result_json,native["data"],body["arguments"],history_days,history_rows,history_bytes,last_page,until))
                return failure(until.remaining()?fail(ErrorCode::IoError,"qmt_history_data_invalid"):fail(ErrorCode::Timeout,"qmt_host_deadline"));
            if(account()&&(text(body["policy_version"])!=account_limits_.policy_version
                ||(profile_kind==QmtBoundProfile::AccountV4&&!receipt.read_profile_body.empty()
                    &&(receipt.read_profile_body!=profile_body||receipt.read_result_capacity!=result_cap))))
                return failure(fail(ErrorCode::Conflict,"qmt_account_profile_changed"));
            if(account()&&!account_validated&&!account_data(output.native_result_json,native["data"],body["arguments"],account_limits_,until,last_account_data))
                return failure(until.remaining()?fail(ErrorCode::IoError,"qmt_account_data_invalid"):fail(ErrorCode::Timeout,"qmt_host_deadline"));
            if(request_control){auto checked=request_control->gate(http,until,control,QmtAccountReadStage::Publish);if(!checked.ok())return failure(checked);}
            else if(stopped())return failure(fail(ErrorCode::Pending,account()?"qmt_account_interrupted":"qmt_history_interrupted"));
            output.result.data_json=account()?std::move(last_account_data):encode(native["data"]);
            if(prepared_operation()&&!until.remaining()){output.result.data_json.clear();return failure(fail(ErrorCode::Timeout,"qmt_host_deadline"));}
            // 完整原值已归本进程返回对象，随后才交接Host读取责任；确认失败保留原收据。
            // 显式快照只交付完整原值给Native owner；映射完成并持有原结果后由它确认。
            if(retained_snapshot()){output.snapshot_consumption_ready=true;output.result.status={};return output;}
            status=consumed(output,until,request_control);
            if(!status.ok()){output.result.data_json.clear();return failure(status);}
            output.result.status={};return output;
        }
        } catch (...) {
            if(request_control)request_control->failed();
            output.result.status.code=ErrorCode::SubmissionUnknown;
            output.result.data_json.clear();return output;
        }
    }
};

QmtBoundReadCore::QmtBoundReadCore(QmtHttpConfig config,QmtBoundProfile profile,const QmtHistoryControl* control,const QmtExpectedAccount* expected)
    :impl_(new Impl(std::move(config),profile,control,expected)){}
QmtBoundReadCore::~QmtBoundReadCore()=default;
Status QmtBoundReadCore::prepare(std::uint32_t milliseconds){
    if(impl_->prepared_operation())return fail(ErrorCode::InvalidInput,"qmt_bound_profile_invalid");
    return impl_->prepare(milliseconds);
}
SourceSession QmtBoundReadCore::session()const{return impl_->http.check().ok()&&impl_->ready?impl_->source:SourceSession{};}
Capability QmtBoundReadCore::capability()const
{
    if(!impl_->http.check().ok()||!impl_->ready)
        return {false,Qualification::Unavailable,"qmt_host_not_prepared"};
    // prepare仅核对认证连接与profile；v3/v4各操作资格由各自验收登记。
    // supported保留协议支持事实；连接就绪不能把资格提高为DevelopmentVerified。
    if(impl_->v3())
        return {true,Qualification::Unavailable,impl_->profile_kind==QmtBoundProfile::AccountV4?
            "qmt_host_bound_v4_unqualified":"qmt_host_bound_v3_unqualified"};
    return {true,Qualification::DevelopmentVerified,impl_->history()?"qmt_host_bound_history_1m":"qmt_host_bound_full_tick"};
}
Status QmtBoundReadCore::drain_callbacks(std::uint32_t milliseconds)noexcept{return impl_->http.drain_callbacks(milliseconds);}
QmtBoundResult QmtBoundReadCore::read_full_tick(const std::string& input,std::uint32_t milliseconds)
{
    SignedHttpDeadline until(milliseconds);QmtBoundResult rejected;
    if(impl_->prepared_operation()){rejected.result.status=fail(ErrorCode::InvalidInput,"qmt_bound_profile_invalid");return rejected;}
    auto reject=[&](Status status){rejected.result.status=std::move(status);return rejected;};
    auto status=impl_->http.check();if(!status.ok())return reject(status);
    if(!milliseconds||milliseconds>30000)return reject(fail(ErrorCode::InvalidInput,"qmt_host_budget_invalid"));
    if(!impl_->ready)return reject(fail(ErrorCode::Unavailable,"qmt_host_not_prepared"));
    Document argument;if(!parse(input,argument,65536)||!stocks(argument))return reject(fail(ErrorCode::InvalidInput,"qmt_host_stocks_invalid"));
    status=impl_->verify(until,impl_->pin);if(!status.ok())return reject(status);
    if(impl_->retained_snapshot()){
        status=impl_->capacity(until,nullptr);if(!status.ok())return reject(status);
    }
    if(until.remaining()<100)return reject(fail(ErrorCode::Timeout,"qmt_host_deadline"));
    const auto id=signed_http_uuid();if(id.empty())return reject(fail(ErrorCode::Unavailable,"qmt_host_crypto_unavailable"));
    Document body;body.SetObject();auto& a=body.GetAllocator();add(body,"request_id",id);add(body,"correlation_id",id);
    add(body,"operation_id","market.full_tick");body.AddMember("arguments",Value(argument,a),a);
    add(body,"policy_id","qmt.standard-read.v1");add(body,"policy_version","1.0");add(body,"priority_class","normal");
    body.AddMember("timeout_ms",std::min(impl_->execution_ms,until.remaining()),a);
    QmtBoundResult output;std::string request_id=id;
    if(impl_->retained_snapshot()){
        Document binding,ticket;ticket.SetObject();
        if(!parse(impl_->pin,binding,4096))return reject(fail(ErrorCode::Conflict,"qmt_host_binding_invalid"));
        const auto now=retention_now();const auto lifetime=std::min(impl_->retention_lifetime,until.remaining());
        if(lifetime<100||!now||now>(1ULL<<53)-1-lifetime)return reject(fail(ErrorCode::Unavailable,"qmt_read_retention_clock_invalid"));
        // ticket覆盖本次剩余D；生产者max_lifetime不改，恢复也不重授旧ticket期限。
        body["timeout_ms"].SetUint(std::min(body["timeout_ms"].GetUint(),lifetime));
        add(ticket,"schema","qmt.read-ticket.v1");add(ticket,"epoch",text(binding["host_instance_id"]));
        ticket.AddMember("expires_ms",now+lifetime,ticket.GetAllocator());
        request_id=retained_id(body,ticket);if(request_id.empty())return reject(fail(ErrorCode::Unavailable,"qmt_host_crypto_unavailable"));
        body["request_id"].SetString(request_id.data(),static_cast<rapidjson::SizeType>(request_id.size()),a);
        output.receipt.retention_ticket_json=encode(ticket);output.receipt.read_profile_body=impl_->profile_body;
        output.receipt.read_result_capacity=impl_->result_cap;
    }
    output.receipt.binding_json=impl_->pin;output.receipt.request_body=encode(body);
    output.result.request_id=request_id;output.result.operation_id="market.full_tick";
    output.result.status=fail(ErrorCode::SubmissionUnknown,"qmt_host_result_unknown");
    if(output.receipt.request_body.size()>impl_->request_cap)return reject(fail(ErrorCode::Backpressure,"qmt_host_request_capacity"));
    Document outer;outer.SetObject();add(outer,"schema_version",impl_->retained_snapshot()?"qmt.bound-retained-read.v1":version);add(outer,"binding_sha256",signed_http_sha256(impl_->pin));
    add(outer,"request_body_b64",base64(output.receipt.request_body));add(outer,"request_body_sha256",signed_http_sha256(output.receipt.request_body));
    if(impl_->retained_snapshot()){
        Document ticket;if(!parse(output.receipt.retention_ticket_json,ticket,256))return reject(fail(ErrorCode::InvalidInput,"qmt_host_receipt_invalid"));
        outer.AddMember("ticket",Value(ticket,outer.GetAllocator()),outer.GetAllocator());
    }
    const auto wire=encode(outer);
    if(wire.size()>impl_->http_request_cap)return reject(fail(ErrorCode::Backpressure,"qmt_host_http_request_capacity"));
    try {
        auto response=impl_->http.exchange("POST","/internal/v1/bound-operations/market.full_tick",wire,until,impl_->http_response_cap);
#if defined(_WIN32) && defined(GH_QMT_HTTP_DRAIN_TESTING)
        unsigned expected=1;if(bound_test_fault.compare_exchange_strong(expected,0))throw std::bad_alloc();
#endif
        const bool get=!response.status.ok()&&response.delivery_unknown&&(response.code==0||response.code==200||response.code==202);
        return impl_->follow(std::move(output),until,std::move(response),get);
    } catch (...) { return output; }
}
QmtBoundResult QmtBoundReadCore::resume(const QmtBoundReceipt& receipt,std::uint32_t milliseconds)
{
    SignedHttpDeadline until(milliseconds);QmtBoundResult output;output.receipt=receipt;
    if(impl_->prepared_operation()){output.result.status=fail(ErrorCode::InvalidInput,"qmt_bound_profile_invalid");return output;}
    auto status=impl_->http.check();
    if(!status.ok()){output.result.status=status;return output;}
    if(!milliseconds||milliseconds>30000){output.result.status=fail(ErrorCode::InvalidInput,"qmt_host_budget_invalid");return output;}
    Document body,b;
    if(!request(receipt,body,b,impl_->profile_kind)){output.result.status=fail(ErrorCode::InvalidInput,"qmt_host_receipt_invalid");return output;}
    output.result.request_id=text(body["request_id"]);output.result.operation_id=text(body["operation_id"]);
    output.result.status=fail(ErrorCode::SubmissionUnknown,"qmt_host_result_unknown");
    // 先取当前受管limits；即使切代仍GET原终态用于审计，follow末次binding才决定采用。
    try {
        std::string observed;SourceSession source;status=impl_->read_binding(until,observed,source);
        if(!status.ok()&&!impl_->result_cap){output.result.status=status;return output;}
        SignedHttpResult response;bool get=true;
        if(impl_->retained_snapshot()){
            Document lookup,ticket;lookup.SetObject();parse(receipt.retention_ticket_json,ticket,256);
            add(lookup,"schema","qmt.read-lookup.v1");lookup.AddMember("ticket",Value(ticket,lookup.GetAllocator()),lookup.GetAllocator());
            add(lookup,"request_body_b64",base64(receipt.request_body));add(lookup,"request_body_sha256",signed_http_sha256(receipt.request_body));
            response=impl_->http.exchange("POST","/internal/v1/read-results/"+output.result.request_id+"/lookup",encode(lookup),until,impl_->http_response_cap);get=false;
        }
        return impl_->follow(std::move(output),until,std::move(response),get);
    } catch (...) { return output; }
}

Status QmtBoundReadCore::confirm_full_tick(const QmtBoundResult& output,std::uint32_t milliseconds)
{
    auto status=impl_->http.check();if(!status.ok())return status;
    if(!impl_->retained_snapshot()||!output.snapshot_consumption_ready||!milliseconds||milliseconds>30000)
        return fail(ErrorCode::InvalidInput,"qmt_snapshot_consumer_not_ready");
    SignedHttpDeadline until(milliseconds);Document request_body,binding,native;
    if(!request(output.receipt,request_body,binding,impl_->profile_kind)
        ||!parse_bounded_qmt_json(output.native_result_json,native,output.receipt.read_result_capacity)
        ||!field(native,"request_id")||text(native["request_id"])!=text(request_body["request_id"])
        ||!field(native,"operation_id")||text(native["operation_id"])!="market.full_tick"
        ||!native.HasMember("ok")||!native["ok"].IsBool()||!history_terminal(native,true)
        ||output.result.request_id!=text(request_body["request_id"])||output.result.operation_id!="market.full_tick")
        return fail(ErrorCode::InvalidInput,"qmt_snapshot_consumer_invalid");
    if(!native["ok"].GetBool()){
        bool confirmed=false;const auto code=text(native["error_code"]);
        for(auto known:{"preparation_not_executed","queue_timeout","source_binding_changed","queue_full","invalid_arguments","capability_unavailable"})if(code==known)confirmed=true;
        if(!confirmed)return fail(ErrorCode::Pending,"qmt_snapshot_result_unconfirmed");
    }
    // 调用者是已持有完整原值/映射的Native快照owner；此ACK不代表HTTP客户端已收到。
    // 未得到ACK时owner保留原result与receipt，只能原消费身份重确认。
    return impl_->consumed(output,until,nullptr);
}
}

namespace guanheng
{
Status QmtBoundReadCore::prepare(SignedHttpDeadline& until)
{return prepare_impl(until,nullptr);}
Status QmtBoundReadCore::prepare_impl(SignedHttpDeadline& until,RequestControl* request_control)
{
    auto status=impl_->http.check();if(!status.ok())return status;
    if(request_control){status=request_control->gate(impl_->http,until,impl_->control,QmtAccountReadStage::Binding);if(!status.ok())return status;}
    impl_->ready=false;impl_->source={};impl_->pin.clear();
    if(!impl_->prepared_operation()||!until.remaining()||until.remaining()>300000)
        return fail(ErrorCode::InvalidInput,"qmt_host_budget_invalid");
    if(!request_control&&impl_->stopped())return fail(ErrorCode::Pending,"qmt_history_interrupted");
    std::string observed;SourceSession identity;status=impl_->read_binding(until,observed,identity,request_control);
    if(!status.ok())return status;status=impl_->verify(until,observed,request_control);if(!status.ok())return status;
    if(request_control){status=request_control->gate(impl_->http,until,impl_->control,QmtAccountReadStage::Publish);if(!status.ok())return status;}
    if(!until.remaining())return fail(ErrorCode::Timeout,"qmt_host_deadline");
    impl_->pin=std::move(observed);impl_->source=std::move(identity);impl_->ready=true;++impl_->prepare_generation;return {};
}
QmtHistoryPreparation QmtBoundReadCore::create_history(const QmtHistoryRequest& input,SignedHttpDeadline& until)
{
    // 保留旧history门面的准入错误顺序，编码前先核owner/就绪/截止。
    auto status=impl_->http.check();if(!status.ok())return {status,{}};
    if(!impl_->history()||!impl_->ready)return {fail(ErrorCode::Unavailable,"qmt_host_not_prepared"),{}};
    if(impl_->stopped())return {fail(ErrorCode::Pending,"qmt_history_interrupted"),{}};
    if(!until.remaining()||until.remaining()>300000)return {fail(ErrorCode::Timeout,"qmt_host_deadline"),{}};
    if(input.symbol.size()!=9||input.start_time.size()!=14||input.end_time.size()!=14)
        return {fail(ErrorCode::InvalidInput,"qmt_history_arguments_invalid"),{}};
    Document args;args.SetObject();add(args,"symbol",input.symbol);add(args,"start_time",input.start_time);add(args,"end_time",input.end_time);
    args.AddMember("max_rows",input.max_rows,args.GetAllocator());return create_prepared(encode(args),until);
}
QmtAccountPreparation QmtBoundReadCore::create_account(QmtAccountDatatype type,SignedHttpDeadline& until)
{return create_account_impl(type,until,nullptr);}
QmtAccountPreparation QmtBoundReadCore::create_account_impl(QmtAccountDatatype type,SignedHttpDeadline& until,RequestControl* request_control)
{
    QmtAccountPreparation out;
    if(!impl_->account()){out.status=fail(ErrorCode::InvalidInput,"qmt_bound_profile_invalid");return out;}
    const char* datatype=nullptr;
    switch(type){case QmtAccountDatatype::Position:datatype="position";break;case QmtAccountDatatype::Order:datatype="order";break;
        case QmtAccountDatatype::Deal:datatype="deal";break;case QmtAccountDatatype::Account:datatype="account";break;
        default:out.status=fail(ErrorCode::InvalidInput,"qmt_account_datatype_invalid");return out;}
    Document args;args.SetObject();add(args,"account_type","stock");add(args,"datatype",datatype);add(args,"scope","account");
    auto prepared=create_prepared(encode(args),until,request_control);out.status=prepared.status;
    if(prepared.request){
        out.request.reset(new QmtPreparedAccountRead);out.request->prepared_=std::move(prepared.request);
        if(request_control){
            out.status=request_control->gate(impl_->http,until,impl_->control,QmtAccountReadStage::Publish);
            if(!out.status.ok())out.request.reset();
        }
    }
    return out;
}
QmtHistoryPreparation QmtBoundReadCore::create_prepared(const std::string& arguments_json,SignedHttpDeadline& until,RequestControl* request_control)
{
    QmtHistoryPreparation out;
    auto reject=[&](Status s){out.status=std::move(s);return std::move(out);};
    auto status=impl_->http.check();if(!status.ok())return reject(status);
    if(!impl_->prepared_operation()||!impl_->ready)return reject(fail(ErrorCode::Unavailable,"qmt_host_not_prepared"));
    if(!request_control&&impl_->stopped())return reject(fail(ErrorCode::Pending,"qmt_history_interrupted"));
    if(!until.remaining()||until.remaining()>300000)return reject(fail(ErrorCode::Timeout,"qmt_host_deadline"));
    Document args;if(!parse(arguments_json,args,65536)||!operation_arguments(impl_->profile_kind,args,impl_->history_days,impl_->history_rows))
        return reject(fail(ErrorCode::InvalidInput,impl_->history()?"qmt_history_arguments_invalid":"qmt_account_arguments_invalid"));
    status=impl_->verify(until,impl_->pin,request_control);if(!status.ok())return reject(status);
    status=impl_->capacity(until,request_control);if(!status.ok())return reject(status);
    if(until.remaining()<100)return reject(fail(ErrorCode::Timeout,"qmt_host_deadline"));
    const auto id=signed_http_uuid();if(id.empty())return reject(fail(ErrorCode::Unavailable,"qmt_host_crypto_unavailable"));
    Document body;body.SetObject();auto& a=body.GetAllocator();add(body,"request_id",id);add(body,"correlation_id",id);
    add(body,"operation_id",operation(impl_->profile_kind));body.AddMember("arguments",Value(args,a),a);
    add(body,"policy_id",policy(impl_->profile_kind));
    add(body,"policy_version",impl_->account()?impl_->account_limits_.policy_version:"1.0");add(body,"priority_class","normal");
    body.AddMember("timeout_ms",std::min(impl_->execution_ms,until.remaining()),a);
    std::unique_ptr<QmtPreparedHistoryRead> token(new QmtPreparedHistoryRead);
    if(impl_->account()&&impl_->retention_lifetime){
        Document pin,ticket;ticket.SetObject();
        if(!parse(impl_->pin,pin,4096))return reject(fail(ErrorCode::Conflict,"qmt_host_binding_invalid"));
        add(ticket,"schema","qmt.read-ticket.v1");add(ticket,"epoch",text(pin["host_instance_id"]));
        const auto now=retention_now();const auto lifetime=std::min(impl_->retention_lifetime,until.remaining());
        if(!now||lifetime<100||now>(1ULL<<53)-1-lifetime)return reject(fail(ErrorCode::Unavailable,"qmt_read_retention_clock_invalid"));
        ticket.AddMember("expires_ms",now+lifetime,ticket.GetAllocator());
        const auto retained=retained_id(body,ticket);if(retained.empty())return reject(fail(ErrorCode::Unavailable,"qmt_host_crypto_unavailable"));
        body["request_id"].SetString(retained.data(),static_cast<rapidjson::SizeType>(retained.size()),a);
        token->receipt_.retention_ticket_json=encode(ticket);
    }
    token->receipt_.binding_json=impl_->pin;token->receipt_.request_body=encode(body);token->profile_=impl_->profile_body;
    if(impl_->profile_kind==QmtBoundProfile::AccountV4||!token->receipt_.retention_ticket_json.empty()){
        token->receipt_.read_profile_body=impl_->profile_body;token->receipt_.read_result_capacity=impl_->result_cap;
    }
    if(token->receipt_.request_body.size()>impl_->request_cap)return reject(fail(ErrorCode::Backpressure,"qmt_host_request_capacity"));
    token->request_sha256_=signed_http_sha256(token->receipt_.request_body);
    if(token->request_sha256_.empty())return reject(fail(ErrorCode::Unavailable,"qmt_host_crypto_unavailable"));
    token->owner_=impl_->token_owner;token->generation_=impl_->prepare_generation;
    if(!until.remaining())return reject(fail(ErrorCode::Timeout,"qmt_host_deadline"));
    if(request_control){status=request_control->gate(impl_->http,until,impl_->control,QmtAccountReadStage::Publish);if(!status.ok())return reject(status);}
    out.request=std::move(token);return out;
}
QmtHistoryResult QmtBoundReadCore::submit_prepared(std::unique_ptr<QmtPreparedHistoryRead> token,SignedHttpDeadline& until,RequestControl* request_control,
    bool* submission_entered)
{
    QmtHistoryResult out;
    auto reject=[&](Status status){out.bound.result.status=std::move(status);return std::move(out);};
    if(token)out.bound.receipt=token->receipt_;
    auto status=impl_->http.check();if(!status.ok())return reject(status);
    if(!token||!impl_->prepared_operation())return reject(fail(ErrorCode::InvalidInput,"qmt_history_token_invalid"));
    impl_->last_page={};impl_->last_error.clear();impl_->last_account_data.clear();
    // Copy the recoverable identity before any network operation. Consumption of
    // unique_ptr is irreversible; receipt has no submit API and resumes via GET.
    // 原submit_once内部的缺登记再投仅沿本次原wire及绝对D，未向receipt增加提交能力。
    Document body,b;
    if(token->owner_!=impl_->token_owner||token->generation_!=impl_->prepare_generation||!impl_->ready
        ||!request(token->receipt_,body,b,impl_->profile_kind)||token->receipt_.binding_json!=impl_->pin
        ||token->profile_!=impl_->profile_body||token->request_sha256_!=signed_http_sha256(token->receipt_.request_body)
        ||!operation_arguments(impl_->profile_kind,body["arguments"],impl_->history_days,impl_->history_rows)
        ||body["timeout_ms"].GetUint()>impl_->execution_ms)
        return reject(fail(ErrorCode::InvalidInput,"qmt_history_token_invalid"));
    out.bound.result.request_id=text(body["request_id"]);out.bound.result.operation_id=operation(impl_->profile_kind);
    out.bound.result.status=fail(ErrorCode::SubmissionUnknown,"qmt_host_result_unknown");
    if(!request_control&&impl_->stopped())return reject(fail(ErrorCode::Pending,"qmt_history_interrupted"));
    if(until.remaining()<100||until.remaining()>300000)return reject(fail(ErrorCode::Timeout,"qmt_host_deadline"));
    status=impl_->verify(until,impl_->pin,request_control);if(!status.ok())return reject(status);
    Document outer;outer.SetObject();add(outer,"schema_version",token->receipt_.retention_ticket_json.empty()?version:"qmt.bound-retained-read.v1");add(outer,"binding_sha256",signed_http_sha256(impl_->pin));
    add(outer,"request_body_b64",base64(token->receipt_.request_body));add(outer,"request_body_sha256",token->request_sha256_);
    if(!token->receipt_.retention_ticket_json.empty()){
        Document ticket;if(!parse(token->receipt_.retention_ticket_json,ticket,1024))return reject(fail(ErrorCode::InvalidInput,"qmt_host_receipt_invalid"));
        outer.AddMember("ticket",Value(ticket,outer.GetAllocator()),outer.GetAllocator());
    }
    const bool original_account_deadline=impl_->account()&&token->receipt_.retention_ticket_json.empty();
    if(original_account_deadline){
        const auto now=retention_now();const auto remaining=until.remaining();
        if(!now||remaining<100||now>(1ULL<<53)-1-remaining)
            return reject(fail(ErrorCode::Unavailable,"qmt_account_original_deadline_invalid"));
        // HTTP外层只约束Host排队；原SDK请求正文、ID、摘要和来源能力保持原件。
        outer.AddMember("execution_deadline_uptime_ms",now+remaining,outer.GetAllocator());
    }
    const auto wire=encode(outer);
    if(wire.size()>impl_->http_request_cap)return reject(fail(ErrorCode::Backpressure,"qmt_host_http_request_capacity"));
    token.reset();
    if(!request_control&&impl_->stopped())return reject(fail(ErrorCode::Pending,"qmt_history_interrupted"));
    if(!until.remaining())return reject(fail(ErrorCode::Timeout,"qmt_host_deadline"));
    try{
        if(request_control){status=request_control->gate(impl_->http,until,impl_->control,QmtAccountReadStage::Submit);if(!status.ok())return reject(status);}
        // 身份复核、停止门及正文准备均已完成；进入运输调用后保留可能已提交责任。
        if(submission_entered)*submission_entered=true;
        auto response=impl_->http.exchange_observed("POST",std::string("/internal/v1/bound-operations/")+operation(impl_->profile_kind),wire,until,
            impl_->http_response_cap,{out.bound.result.request_id,impl_->account()?RequestJournalEvidence::FirstAccountAdmission:RequestJournalEvidence::Unknown});
#if defined(_WIN32) && defined(GH_QMT_HTTP_DRAIN_TESTING)
        unsigned expected=1;if(bound_test_fault.compare_exchange_strong(expected,0))throw std::bad_alloc();
#endif
        const bool get=!response.status.ok()&&response.delivery_unknown&&(response.code==0||response.code==200||response.code==202);
        out.bound=impl_->follow(std::move(out.bound),until,std::move(response),get,request_control,
            original_account_deadline?&wire:nullptr,true);
        if(out.bound.result.status.ok())out.page=std::move(impl_->last_page);
        out.remote_error_code=std::move(impl_->last_error);
    }catch(...){if(request_control)request_control->failed();out.bound.result.status.code=ErrorCode::SubmissionUnknown;out.bound.result.data_json.clear();}
    return out;
}
QmtHistoryResult QmtBoundReadCore::resume_prepared(const QmtBoundReceipt& receipt,SignedHttpDeadline& until,RequestControl* request_control)
{
    QmtHistoryResult out;out.bound.receipt=receipt;
    auto reject=[&](Status status){out.bound.result.status=std::move(status);return std::move(out);};
    auto status=impl_->http.check();if(!status.ok())return reject(status);
    if(!impl_->prepared_operation())return reject(fail(ErrorCode::InvalidInput,"qmt_host_receipt_invalid"));
    impl_->last_page={};impl_->last_error.clear();impl_->last_account_data.clear();
    Document body,b;if(!request(receipt,body,b,impl_->profile_kind))return reject(fail(ErrorCode::InvalidInput,"qmt_host_receipt_invalid"));
    out.bound.result.request_id=text(body["request_id"]);out.bound.result.operation_id=operation(impl_->profile_kind);
    out.bound.result.status=fail(ErrorCode::SubmissionUnknown,"qmt_host_result_unknown");
    if(!request_control&&impl_->stopped())return reject(fail(ErrorCode::Pending,"qmt_history_interrupted"));
    if(!until.remaining()||until.remaining()>300000)return reject(fail(ErrorCode::Timeout,"qmt_host_deadline"));
    try{
        std::string observed;SourceSession source;
        status=impl_->read_binding(until,observed,source,request_control);
        // 旧入口保留历史预读语义；显式请求入口不丢弃已发生的真实失败。
        if(request_control&&!status.ok())return reject(status);
        SignedHttpResult response;bool get=true;
        if(!receipt.retention_ticket_json.empty()){
            Document lookup,ticket;lookup.SetObject();parse(receipt.retention_ticket_json,ticket,1024);
            add(lookup,"schema","qmt.read-lookup.v1");lookup.AddMember("ticket",Value(ticket,lookup.GetAllocator()),lookup.GetAllocator());
            add(lookup,"request_body_b64",base64(receipt.request_body));add(lookup,"request_body_sha256",signed_http_sha256(receipt.request_body));
            if(request_control){status=request_control->gate(impl_->http,until,impl_->control,QmtAccountReadStage::Result);if(!status.ok())return reject(status);}
            else if(impl_->stopped())return reject(fail(ErrorCode::Pending,"qmt_account_interrupted"));
            response=impl_->http.exchange_observed("POST","/internal/v1/read-results/"+out.bound.result.request_id+"/lookup",
                encode(lookup),until,impl_->http_response_cap,{out.bound.result.request_id});get=false;
        }
        out.bound=impl_->follow(std::move(out.bound),until,std::move(response),get,request_control);
        if(out.bound.result.status.ok()){
            out.page=std::move(impl_->last_page);binding(b,&impl_->source,binding_version(impl_->profile_kind));impl_->pin=encode(b);impl_->ready=true;
        }
        out.remote_error_code=std::move(impl_->last_error);
    }catch(...){if(request_control)request_control->failed();out.bound.result.status.code=ErrorCode::SubmissionUnknown;out.bound.result.data_json.clear();}
    return out;
}
}

namespace guanheng
{
QmtHistoryResult QmtBoundReadCore::submit_history(std::unique_ptr<QmtPreparedHistoryRead> token,SignedHttpDeadline& until)
{
    if(!impl_->history()){QmtHistoryResult out;out.bound.result.status=fail(ErrorCode::InvalidInput,"qmt_bound_profile_invalid");return out;}
    return submit_prepared(std::move(token),until);
}
QmtHistoryResult QmtBoundReadCore::resume_history(const QmtBoundReceipt& receipt,SignedHttpDeadline& until)
{
    if(!impl_->history()){QmtHistoryResult out;out.bound.receipt=receipt;out.bound.result.status=fail(ErrorCode::InvalidInput,"qmt_bound_profile_invalid");return out;}
    return resume_prepared(receipt,until);
}
QmtAccountResult QmtBoundReadCore::submit_account(std::unique_ptr<QmtPreparedAccountRead> token,SignedHttpDeadline& until)
{
    if(!impl_->account()||!token){QmtAccountResult out;out.bound.result.status=fail(ErrorCode::InvalidInput,"qmt_account_token_invalid");return out;}
    auto prepared=std::move(token->prepared_);token.reset();
    bool submitted=false;auto shared=submit_prepared(std::move(prepared),until,nullptr,&submitted);
    return {std::move(shared.bound),std::move(shared.remote_error_code),submitted};
}
QmtAccountResult QmtBoundReadCore::resume_account(const QmtBoundReceipt& receipt,SignedHttpDeadline& until)
{
    if(!impl_->account()){QmtAccountResult out;out.bound.receipt=receipt;out.bound.result.status=fail(ErrorCode::InvalidInput,"qmt_bound_profile_invalid");return out;}
    auto shared=resume_prepared(receipt,until);return {std::move(shared.bound),std::move(shared.remote_error_code)};
}
}

namespace guanheng
{
Status QmtBoundReadCore::prepare(SignedHttpDeadline& until,QmtAccountReadControlResult* out,const QmtAccountControl* control)
{
    RequestControl request_control(out,control);
    if(!impl_->account())return fail(ErrorCode::InvalidInput,"qmt_bound_profile_invalid");
    auto status=prepare_impl(until,&request_control);if(status.ok())request_control.success();return status;
}
QmtAccountPreparation QmtBoundReadCore::create_account(QmtAccountDatatype type,SignedHttpDeadline& until,
    QmtAccountReadControlResult* out,const QmtAccountControl* control)
{
    RequestControl request_control(out,control);
    auto prepared=create_account_impl(type,until,&request_control);
    if(prepared.status.ok())request_control.success();return prepared;
}
QmtAccountResult QmtBoundReadCore::submit_account(std::unique_ptr<QmtPreparedAccountRead> token,SignedHttpDeadline& until,
    QmtAccountReadControlResult* out,const QmtAccountControl* control)
{
    RequestControl request_control(out,control);
    if(!impl_->account()||!token){QmtAccountResult result;result.bound.result.status=fail(ErrorCode::InvalidInput,"qmt_account_token_invalid");return result;}
    auto prepared=std::move(token->prepared_);token.reset();
    bool submitted=false;auto shared=submit_prepared(std::move(prepared),until,&request_control,&submitted);
    if(shared.bound.result.status.ok())request_control.success();
    return {std::move(shared.bound),std::move(shared.remote_error_code),submitted};
}
QmtAccountResult QmtBoundReadCore::resume_account(const QmtBoundReceipt& receipt,SignedHttpDeadline& until,
    QmtAccountReadControlResult* out,const QmtAccountControl* control)
{
    RequestControl request_control(out,control);
    if(!impl_->account()){QmtAccountResult result;result.bound.receipt=receipt;result.bound.result.status=fail(ErrorCode::InvalidInput,"qmt_bound_profile_invalid");return result;}
    auto shared=resume_prepared(receipt,until,&request_control);
    if(shared.bound.result.status.ok())request_control.success();
    return {std::move(shared.bound),std::move(shared.remote_error_code)};
}
}
