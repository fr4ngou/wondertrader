#ifndef NOMINMAX
#define NOMINMAX
#endif
#include "ReaderHttpClient.h"
#include "../GuanhengCommon/WinHttpSessionDrain.h"
#include <rapidjson/document.h>
#include <rapidjson/reader.h>
#include <rapidjson/stringbuffer.h>
#include <rapidjson/writer.h>
#include <algorithm>
#include <array>
#include <atomic>
#include <cmath>
#include <cstring>
#include <mutex>
#include <set>
#include <stdexcept>
#ifdef _WIN32
#include <windows.h>
#include <winhttp.h>
#include <bcrypt.h>
#endif

#if defined(_WIN32) && defined(GH_READER_HTTP_DRAIN_TESTING)
// 专用测试DLL的真实关闭回调闸门；生产构建不含hook与导出。
namespace {
std::atomic<HANDLE> reader_gate_entered{nullptr},reader_gate_release{nullptr};
std::atomic<bool> reader_gate_armed{false};
std::atomic<DWORD> reader_gate_thread{0};
void reader_hold_closing_for_test() noexcept {
    if(!reader_gate_armed.exchange(false))return;
    reader_gate_thread.store(GetCurrentThreadId());SetEvent(reader_gate_entered.load());
    if(WaitForSingleObject(reader_gate_release.load(),15000)!=WAIT_OBJECT_0)ExitProcess(95);
}
}
extern "C" __declspec(dllexport) void gh_reader_http_test_gate(HANDLE entered,HANDLE release) noexcept {
    reader_gate_entered.store(entered);reader_gate_release.store(release);reader_gate_thread.store(0);
    reader_gate_armed.store(entered&&release);
}
extern "C" __declspec(dllexport) DWORD gh_reader_http_test_callback_thread() noexcept {return reader_gate_thread.load();}
#endif

namespace guanheng
{
namespace
{
using Json = rapidjson::Value;
using Clock = std::chrono::steady_clock;
Status fail(ErrorCode code, const char* reason) { return {code, reason}; }
std::uint32_t left(ReaderDeadline deadline)
{
    const auto ms=std::chrono::duration_cast<std::chrono::milliseconds>(deadline-Clock::now()).count();
    return ms>0?static_cast<std::uint32_t>(std::min<std::int64_t>(ms,300000)):0;
}
bool text_ok(const std::string& value,std::size_t maximum,bool empty=false)
{
    return (empty||!value.empty())&&value.size()<=maximum&&std::none_of(value.begin(),value.end(),
        [](unsigned char c){return c<32||c==127;});
}
bool hex(const std::string& value,std::size_t size)
{return value.size()==size&&std::all_of(value.begin(),value.end(),[](char c){return (c>='0'&&c<='9')||(c>='a'&&c<='f');});}
bool security(const std::string& value)
{return value.size()==9&&(value.substr(6)==".SH"||value.substr(6)==".SZ")&&std::all_of(value.begin(),value.begin()+6,[](char c){return c>='0'&&c<='9';});}
std::string str(const Json& value,std::size_t maximum=256,bool empty=false)
{
    if(!value.IsString())throw std::invalid_argument("text");
    std::string result(value.GetString(),value.GetStringLength());
    if(!text_ok(result,maximum,empty))throw std::invalid_argument("text");
    return result;
}
void fields(const Json& value,std::initializer_list<const char*> names)
{
    if(!value.IsObject()||value.MemberCount()!=names.size())throw std::invalid_argument("fields");
    for(auto name:names)if(!value.HasMember(name))throw std::invalid_argument("fields");
}
double number(const Json& value,bool positive=false)
{
    if(!value.IsNumber()||!std::isfinite(value.GetDouble())||(positive?value.GetDouble()<=0:value.GetDouble()<0))
        throw std::invalid_argument("number");
    return value.GetDouble();
}
std::uint64_t minute(const Json& value)
{
    if(!value.IsUint64()||!reader_minute_valid(value.GetUint64()))throw std::invalid_argument("minute");
    return value.GetUint64();
}
// 在 DOM 分配之前拒绝重复键、过深嵌套及超预算节点。
struct Guard : rapidjson::BaseReaderHandler<rapidjson::UTF8<>,Guard>
{
    std::vector<std::set<std::string>> keys;
    std::size_t nodes=0;
    bool item(){return ++nodes<=1500000;}
    bool Null(){return item();} bool Bool(bool){return item();} bool Int(int){return item();}
    bool Uint(unsigned){return item();} bool Int64(std::int64_t){return item();} bool Uint64(std::uint64_t){return item();}
    bool Double(double v){return std::isfinite(v)&&item();}
    bool String(const char*,rapidjson::SizeType n,bool){return n<=65536&&item();}
    bool Key(const char* s,rapidjson::SizeType n,bool){return !keys.empty()&&n<=4096&&keys.back().emplace(s,n).second;}
    bool StartObject(){if(keys.size()>=24||!item())return false;keys.emplace_back();return true;}
    bool StartArray(){return StartObject();}
    bool EndObject(rapidjson::SizeType){keys.pop_back();return true;}
    bool EndArray(rapidjson::SizeType){keys.pop_back();return true;}
};
rapidjson::Document parse(const std::string& raw)
{
    if(raw.empty()||raw.find('\0')!=std::string::npos)throw std::invalid_argument("json");
    rapidjson::MemoryStream stream(raw.data(),raw.size());rapidjson::Reader parser;Guard guard;
    if(!parser.Parse<rapidjson::kParseValidateEncodingFlag|rapidjson::kParseIterativeFlag>(stream,guard))throw std::invalid_argument("json");
    rapidjson::Document doc;doc.Parse<rapidjson::kParseValidateEncodingFlag>(raw.data(),raw.size());
    if(doc.HasParseError())throw std::invalid_argument("json");
    return doc;
}
std::string encode(const Json& value)
{rapidjson::StringBuffer b;rapidjson::Writer<rapidjson::StringBuffer> w(b);value.Accept(w);return {b.GetString(),b.GetSize()};}
void provenance(const std::string& raw,bool required)
{
    auto value=parse(raw);
    if(!value.IsObject()||value.MemberCount()>16||(required&&value.ObjectEmpty()))throw std::invalid_argument("provenance");
    for(auto it=value.MemberBegin();it!=value.MemberEnd();++it)
    {
        str(it->name,128);const auto& versions=it->value;
        if(!versions.IsArray()||versions.Empty()||versions.Size()>1024)throw std::invalid_argument("provenance");
        for(const auto& meta:versions.GetArray())
        {
            fields(meta,{"source","qualification","dataset_version","source_license","adjustment","factor_version","minute_boundary","timezone","volume_to_shares","amount_to_yuan","content_id"});
            fields(meta["source"],{"provider","instance_id","session_id","generation"});
            const auto provider=str(meta["source"]["provider"]);
            if(provider!="Qmt"&&provider!="Tdx")throw std::invalid_argument("provider");
            str(meta["source"]["instance_id"]);str(meta["source"]["session_id"]);
            if(!meta["source"]["generation"].IsUint64()||!meta["source"]["generation"].GetUint64())throw std::invalid_argument("generation");
            const auto qualification=str(meta["qualification"]);
            if(qualification!="DevelopmentVerified"&&qualification!="NativeVerified"&&qualification!="ProductionQualified")throw std::invalid_argument("qualification");
            str(meta["dataset_version"]);str(meta["source_license"],1024);
            if(str(meta["adjustment"])!="none"||str(meta["factor_version"],256,true)!=""||str(meta["minute_boundary"])!="right"
                ||str(meta["timezone"])!="Asia/Shanghai"||!hex(str(meta["content_id"]),64))throw std::invalid_argument("semantics");
            number(meta["volume_to_shares"],true);number(meta["amount_to_yuan"],true);
        }
    }
}
ErrorCode status_code(const std::string& name)
{
    const char* names[]={"Ok","Unavailable","InvalidInput","NotSupported","Pending","Timeout","Backpressure","StaleSession","Conflict","SubmissionUnknown","IoError"};
    for(unsigned i=0;i<sizeof(names)/sizeof(names[0]);++i)if(name==names[i])return static_cast<ErrorCode>(i);
    throw std::invalid_argument("status");
}
#ifdef _WIN32
struct Handle
{
    HINTERNET value=nullptr;
    explicit Handle(HINTERNET v=nullptr):value(v){}
    ~Handle(){if(value)WinHttpCloseHandle(value);}
    Handle(const Handle&)=delete;
};
struct Exchange
{
    std::recursive_mutex mutex;
    HANDLE event=CreateEventW(nullptr,TRUE,FALSE,nullptr);
    HINTERNET request=nullptr;
    bool done=false,cancelled=false;
    std::size_t maximum=0;
    DWORD status=0;
    std::array<char,32768> buffer{};
    std::string body,upload;
    std::wstring headers;
    Status result;
    ~Exchange(){if(event)CloseHandle(event);}
    void finish(Status status){if(!done&&!cancelled){result=std::move(status);done=true;SetEvent(event);}}
    void accept(BOOL ok){if(!ok&&GetLastError()!=ERROR_IO_PENDING)finish(fail(ErrorCode::IoError,"reader HTTP exchange failed"));}
};
using ExchangeOwner=std::shared_ptr<Exchange>;
void CALLBACK callback(HINTERNET,DWORD_PTR context,DWORD event,LPVOID info,DWORD length)
{
    if(!context)return;
    auto owner=reinterpret_cast<ExchangeOwner*>(context);
    if(event==WINHTTP_CALLBACK_STATUS_HANDLE_CLOSING){
#ifdef GH_READER_HTTP_DRAIN_TESTING
        reader_hold_closing_for_test();
#endif
        delete owner;return;
    }
    auto state=*owner;
    try
    {
        std::lock_guard<std::recursive_mutex> lock(state->mutex);
        if(state->done||state->cancelled)return;
        switch(event)
        {
        case WINHTTP_CALLBACK_STATUS_SENDREQUEST_COMPLETE:state->accept(WinHttpReceiveResponse(state->request,nullptr));break;
        case WINHTTP_CALLBACK_STATUS_HEADERS_AVAILABLE:
        {
            DWORD size=sizeof(DWORD);
            if(!WinHttpQueryHeaders(state->request,WINHTTP_QUERY_STATUS_CODE|WINHTTP_QUERY_FLAG_NUMBER,nullptr,&state->status,&size,nullptr))
            {state->finish(fail(ErrorCode::IoError,"reader HTTP headers invalid"));break;}
            if(state->status>=300&&state->status<400){state->finish(fail(ErrorCode::IoError,"reader HTTP redirect rejected"));break;}
            if(state->status==401||state->status==403){state->finish(fail(ErrorCode::Unavailable,"reader HTTP authentication rejected"));break;}
            state->accept(WinHttpQueryDataAvailable(state->request,nullptr));break;
        }
        case WINHTTP_CALLBACK_STATUS_DATA_AVAILABLE:
        {
            if(!info||length!=sizeof(DWORD)){state->finish(fail(ErrorCode::IoError,"reader HTTP body invalid"));break;}
            const DWORD count=*static_cast<DWORD*>(info);
            if(!count){state->finish({});break;}
            if(count>state->maximum-state->body.size()){state->finish(fail(ErrorCode::Backpressure,"reader response exceeds budget"));break;}
            state->accept(WinHttpReadData(state->request,state->buffer.data(),std::min<DWORD>(count,static_cast<DWORD>(state->buffer.size())),nullptr));break;
        }
        case WINHTTP_CALLBACK_STATUS_READ_COMPLETE:
            if(length>state->maximum-state->body.size()){state->finish(fail(ErrorCode::Backpressure,"reader response exceeds budget"));break;}
            if(length)state->body.append(static_cast<const char*>(info),length);
            state->accept(WinHttpQueryDataAvailable(state->request,nullptr));break;
        case WINHTTP_CALLBACK_STATUS_REQUEST_ERROR:state->finish(fail(ErrorCode::IoError,"reader HTTP exchange failed"));break;
        default:break;
        }
    }
    catch(...){std::lock_guard<std::recursive_mutex> lock(state->mutex);state->finish(fail(ErrorCode::IoError,"reader HTTP callback failed"));}
}
std::string nonce()
{
    std::array<unsigned char,16> bytes{};
    if(BCryptGenRandom(nullptr,bytes.data(),static_cast<ULONG>(bytes.size()),BCRYPT_USE_SYSTEM_PREFERRED_RNG)<0)throw std::runtime_error("random");
    std::string result;const char* alphabet="0123456789abcdef";
    for(auto byte:bytes){result+=alphabet[byte>>4];result+=alphabet[byte&15];}return result;
}
#endif
}

bool reader_minute_valid(std::uint64_t value)
{
    const auto year=value/100000000,month=value/1000000%100,day=value/10000%100,hour=value/100%100,minute=value%100;
    if(year<2004||year>2099||month<1||month>12||day<1||hour>23||minute>59)return false;
    const unsigned days[]={31,28,31,30,31,30,31,31,30,31,30,31};
    return day<=days[month-1]+(month==2&&year%4==0&&(year%100!=0||year%400==0));
}
Status validate_reader_result(const ReaderRequest& request,const ReaderResult& result,const std::string& policy,std::size_t maximum)
{
    try
    {
        if(!result.status.ok())
        {
            if(!result.bars.empty()||(!result.instance_id.empty()&&(!hex(result.instance_id,32)||result.policy_id!=policy)))
                throw std::invalid_argument("failure");
            return result.status;
        }
        if(!hex(result.instance_id,32)||result.policy_id!=policy)throw std::invalid_argument("identity");
        if(result.symbol!=request.symbol||!reader_minute_valid(result.as_of)||(request.end&&request.end>result.as_of)
            ||result.bars.size()>maximum||(request.tail&&result.bars.size()!=request.count))throw std::invalid_argument("range");
        provenance(result.provenance_json,!result.bars.empty());
        const auto end=request.end?request.end:result.as_of;
        std::uint64_t previous=request.tail?0:request.after;
        for(const auto& value:result.bars)
        {
            const auto& bar=value.bar;const auto label=bar.time+199000000000ULL;
            if(!reader_minute_valid(label)||label/10000!=bar.date||label> end||label<=previous)throw std::invalid_argument("order");
            const auto expected=request.tail?ReaderDelivery::Historical:(label==result.as_of?ReaderDelivery::Current:ReaderDelivery::Recovered);
            if(value.delivery!=expected)throw std::invalid_argument("delivery");
            for(double v:{bar.open,bar.high,bar.low,bar.close})if(!std::isfinite(v)||v<=0)throw std::invalid_argument("price");
            if(bar.low>std::min(bar.open,bar.close)||bar.high<std::max(bar.open,bar.close)||bar.low>bar.high
                ||!std::isfinite(bar.vol)||bar.vol<0||!std::isfinite(bar.money)||bar.money<0)throw std::invalid_argument("prices");
            previous=label;
        }
        return {};
    }
    catch(...){return fail(ErrorCode::Conflict,"reader response identity or history invalid");}
}

struct ReaderHttpClient::Impl
{
    ReaderHttpConfig config;
    Status status;
#ifdef _WIN32
    std::wstring host;
    INTERNET_PORT port=0;
    bool secure=false;
    // 仅登记/排空持锁；HTTP I/O、callback及响应校验均在锁外。
    std::timed_mutex sessions_mutex;
    WinHttpSessionDrain sessions;
#endif
    explicit Impl(ReaderHttpConfig cfg):config(std::move(cfg))
    {
        status=fail(ErrorCode::InvalidInput,"reader HTTP configuration invalid");
        if(!text_ok(config.base_url,2048)||!text_ok(config.token,4096)||!text_ok(config.policy_id,128)
            ||!config.max_bars||config.max_bars>100000||config.max_response_bytes<1024||config.max_response_bytes>32*1024*1024
            ||!std::all_of(config.token.begin(),config.token.end(),[](unsigned char c){return c>=33&&c<=126;})
            ||config.base_url.find_first_of("?#\\")!=std::string::npos)return;
#ifdef _WIN32
        if(!std::all_of(config.base_url.begin(),config.base_url.end(),[](unsigned char c){return c>=33&&c<=126;}))return;
        std::wstring url(config.base_url.begin(),config.base_url.end());URL_COMPONENTS parts{};parts.dwStructSize=sizeof(parts);
        parts.dwHostNameLength=parts.dwUrlPathLength=parts.dwUserNameLength=parts.dwPasswordLength=parts.dwExtraInfoLength=static_cast<DWORD>(-1);
        if(!WinHttpCrackUrl(url.c_str(),static_cast<DWORD>(url.size()),0,&parts)||parts.dwUserNameLength||parts.dwPasswordLength||parts.dwExtraInfoLength
            ||!parts.nPort||(parts.nScheme!=INTERNET_SCHEME_HTTP&&parts.nScheme!=INTERNET_SCHEME_HTTPS))return;
        host.assign(parts.lpszHostName,parts.dwHostNameLength);
        if(host!=L"127.0.0.1"&&host!=L"::1"&&host!=L"[::1]")return;
        const std::wstring path(parts.lpszUrlPath?parts.lpszUrlPath:L"",parts.dwUrlPathLength);
        if(!path.empty()&&path!=L"/")return;
        port=parts.nPort;secure=parts.nScheme==INTERNET_SCHEME_HTTPS;status={};
#else
        status=fail(ErrorCode::Unavailable,"reader HTTP requires Windows");
#endif
    }
    ~Impl()
    {
#ifdef _WIN32
        if(!config.token.empty())SecureZeroMemory(&config.token[0],config.token.size());
#endif
    }
    ReaderResult read(const ReaderRequest& input,ReaderDeadline deadline)
    {
        ReaderResult result;result.status=status;if(!status.ok())return result;
        if(!security(input.symbol)||(input.end&&!reader_minute_valid(input.end))
            ||(input.tail?(!input.count||input.count>config.max_bars):!reader_minute_valid(input.after)))
        {result.status=fail(ErrorCode::InvalidInput,"reader request invalid");return result;}
        if(!left(deadline)){result.status=fail(ErrorCode::Timeout,"reader deadline exceeded");return result;}
        try
        {
#ifdef _WIN32
            const auto id=nonce();rapidjson::StringBuffer buffer;rapidjson::Writer<rapidjson::StringBuffer> writer(buffer);
            writer.StartObject();writer.Key("api_version");writer.String("guanheng.reader.v1");writer.Key("id");writer.String(id.c_str());
            writer.Key("action");writer.String(input.tail?"tail":"range");writer.Key("symbol");writer.String(input.symbol.c_str());
            writer.Key("end");writer.Uint64(input.end);writer.Key(input.tail?"count":"after");writer.Uint64(input.tail?input.count:input.after);writer.EndObject();
            auto state=std::make_shared<Exchange>();state->upload.assign(buffer.GetString(),buffer.GetSize());state->maximum=config.max_response_bytes;
            const auto headers="Content-Type: application/json\r\nAccept: application/json\r\nConnection: close\r\nAuthorization: Bearer "+config.token+"\r\n";
            state->headers.assign(headers.begin(),headers.end());
            Handle session;
            {
                std::unique_lock<std::timed_mutex> lock(sessions_mutex,std::defer_lock);
                if(!lock.try_lock_until(deadline)||!left(deadline))
                {result.status=fail(ErrorCode::Timeout,"reader session admission deadline exceeded");return result;}
                if(!sessions.available())
                {result.status=fail(ErrorCode::Backpressure,"reader pending session limit");return result;}
                session.value=WinHttpOpen(L"GuanhengReader/1",WINHTTP_ACCESS_TYPE_NO_PROXY,nullptr,nullptr,WINHTTP_FLAG_ASYNC);
                if(!session.value)throw std::runtime_error("session");
                result.status=sessions.track(session.value);
                if(!result.status.ok())return result;
            }
            if(!session.value||!state->event)throw std::runtime_error("session");
            const auto budget=left(deadline);if(!budget){result.status=fail(ErrorCode::Timeout,"reader deadline exceeded");return result;}
            if(!WinHttpSetTimeouts(session.value,budget,budget,budget,budget))throw std::runtime_error("timeout");
            Handle connection(WinHttpConnect(session.value,host.c_str(),port,0));if(!connection.value)throw std::runtime_error("connect");
            Handle request(WinHttpOpenRequest(connection.value,L"POST",L"/api/reader/v1/history",nullptr,nullptr,nullptr,secure?WINHTTP_FLAG_SECURE:0));
            if(!request.value)throw std::runtime_error("request");
            DWORD disabled=WINHTTP_DISABLE_REDIRECTS|WINHTTP_DISABLE_COOKIES|WINHTTP_DISABLE_AUTHENTICATION;
            if(!WinHttpSetOption(request.value,WINHTTP_OPTION_DISABLE_FEATURE,&disabled,sizeof(disabled)))throw std::runtime_error("options");
            if(WinHttpSetStatusCallback(request.value,callback,WINHTTP_CALLBACK_FLAG_ALL_COMPLETIONS|WINHTTP_CALLBACK_FLAG_HANDLES,0)==WINHTTP_INVALID_STATUS_CALLBACK)throw std::runtime_error("callback");
            state->request=request.value;
            auto retained=new ExchangeOwner(state);DWORD_PTR context=reinterpret_cast<DWORD_PTR>(retained);
            if(!WinHttpSetOption(request.value,WINHTTP_OPTION_CONTEXT_VALUE,&context,sizeof(context))){delete retained;throw std::runtime_error("context");}
            {std::lock_guard<std::recursive_mutex> lock(state->mutex);state->accept(WinHttpSendRequest(request.value,state->headers.c_str(),static_cast<DWORD>(state->headers.size()),
                &state->upload[0],static_cast<DWORD>(state->upload.size()),static_cast<DWORD>(state->upload.size()),context));}
            const auto remaining=left(deadline);
            const auto waited=remaining?WaitForSingleObject(state->event,remaining):WAIT_TIMEOUT;
            std::string raw;DWORD http_status=0;
            {
                std::lock_guard<std::recursive_mutex> lock(state->mutex);
                if(waited!=WAIT_OBJECT_0||!left(deadline)){state->cancelled=true;result.status=fail(ErrorCode::Timeout,"reader deadline exceeded");return result;}
                result.status=state->result;if(!result.status.ok())return result;
                raw=std::move(state->body);http_status=state->status;state->cancelled=true;
            }
            auto doc=parse(raw);fields(doc,{"api_version","id","instance_id","policy_id","status","data"});
            if(str(doc["api_version"])!="guanheng.reader.v1"||str(doc["id"])!=id)throw std::invalid_argument("identity");
            result.instance_id=str(doc["instance_id"]);result.policy_id=str(doc["policy_id"],128);
            if(!hex(result.instance_id,32)||result.policy_id!=config.policy_id)throw std::invalid_argument("policy");
            fields(doc["status"],{"code","reason"});result.status.code=status_code(str(doc["status"]["code"]));
            str(doc["status"]["reason"],1024,true); // 源 reason 只验证，不传播到日志或宿主。
            if(!result.status.ok())
            {if(!doc["data"].IsObject()||!doc["data"].ObjectEmpty())throw std::invalid_argument("failure data");result.status.reason="reader service not ready";return result;}
            if(http_status!=200)throw std::invalid_argument("HTTP status");
            const auto& data=doc["data"];fields(data,{"symbol","as_of","bars","provenance"});
            result.symbol=str(data["symbol"]);result.as_of=minute(data["as_of"]);result.provenance_json=encode(data["provenance"]);
            const auto& bars=data["bars"];if(!bars.IsArray()||bars.Size()>config.max_bars)throw std::invalid_argument("bars");
            result.bars.reserve(bars.Size());
            for(const auto& row:bars.GetArray())
            {
                fields(row,{"minute","open","high","low","close","volume","amount","delivery"});ReaderBar value;
                const auto label=minute(row["minute"]);value.bar.date=static_cast<std::uint32_t>(label/10000);value.bar.time=label-199000000000ULL;
                value.bar.open=number(row["open"],true);value.bar.high=number(row["high"],true);value.bar.low=number(row["low"],true);value.bar.close=number(row["close"],true);
                value.bar.vol=number(row["volume"]);value.bar.money=number(row["amount"]);const auto delivery=str(row["delivery"]);
                if(delivery=="historical")value.delivery=ReaderDelivery::Historical;else if(delivery=="recovered")value.delivery=ReaderDelivery::Recovered;
                else if(delivery=="current")value.delivery=ReaderDelivery::Current;else throw std::invalid_argument("delivery");
                result.bars.push_back(value);
            }
            result.status=validate_reader_result(input,result,config.policy_id,config.max_bars);
            if(!left(deadline))result.status=fail(ErrorCode::Timeout,"reader deadline exceeded");
            if(!result.status.ok())result.bars.clear();
#else
            result.status=fail(ErrorCode::Unavailable,"reader HTTP requires Windows");
#endif
        }
        catch(...){result.status=fail(ErrorCode::Conflict,"reader HTTP response rejected");result.bars.clear();}
        return result;
    }
};
ReaderHttpClient::ReaderHttpClient(ReaderHttpConfig config):impl_(new Impl(std::move(config))){}
ReaderHttpClient::~ReaderHttpClient()=default;
Status ReaderHttpClient::drain_callbacks(ReaderDeadline deadline) noexcept
{
    try
    {
#ifdef _WIN32
        std::unique_lock<std::timed_mutex> lock(impl_->sessions_mutex,std::defer_lock);
        if(!lock.try_lock_until(deadline))return fail(ErrorCode::Timeout,"reader drain lock deadline exceeded");
        return impl_->sessions.drain(left(deadline));
#else
        return {};
#endif
    }
    catch(...){return {ErrorCode::IoError,{}};}
}
Status ReaderHttpClient::configured()const{return impl_->status;}
ReaderResult ReaderHttpClient::read(const ReaderRequest& request,ReaderDeadline deadline){return impl_->read(request,deadline);}
}
