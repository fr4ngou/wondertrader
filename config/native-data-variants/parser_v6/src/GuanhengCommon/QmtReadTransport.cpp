#include "QmtReadTransport.h"
#include "BoundedSignedHttp.h"
#include <rapidjson/document.h>
#include <rapidjson/reader.h>
#include <rapidjson/stringbuffer.h>
#include <rapidjson/writer.h>
#include <algorithm>
#include <atomic>
#include <array>
#include <chrono>
#include <cmath>
#include <cstring>
#include <map>
#include <mutex>
#include <set>
#include <thread>
#include <vector>
#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <winhttp.h>
#include <bcrypt.h>
#endif

namespace guanheng
{
namespace
{
using Clock=std::chrono::steady_clock;
using Document=rapidjson::Document;
using Value=rapidjson::Value;
using Deadline=SignedHttpDeadline;
using HttpResult=SignedHttpResult;
Status failure(ErrorCode code,const char* reason) { return {code,reason}; }
bool permitted(QmtReadDomain domain, const std::string& operation)
{
    if (domain == QmtReadDomain::Market) return operation == "market.full_tick" || operation == "market.market_data_ex";
    return domain == QmtReadDomain::Account && operation == "account.trade_detail";
}

// 在 DOM 分配前限制深度/节点并拒绝重复键，防止恶意响应覆盖身份字段。
bool parse(const std::string& text,Document& value)
{ return parse_bounded_qmt_json(text,value); }
bool string_value(const Value& value, std::size_t maximum = 128)
{
    return value.IsString() && value.GetStringLength() > 0 && value.GetStringLength() <= maximum
        && std::memchr(value.GetString(), 0, value.GetStringLength()) == nullptr;
}
std::string text(const Value& value) { return {value.GetString(), value.GetStringLength()}; }
bool has_string(const Value& object, const char* name)
{ return object.HasMember(name) && string_value(object[name]); }
bool keys(const Value& value, std::initializer_list<const char*> expected)
{
    if (!value.IsObject() || value.MemberCount() != expected.size()) return false;
    for (auto name : expected) if (!value.HasMember(name)) return false;
    return true;
}
template<class Writer> void canonical(const Value& value, Writer& writer)
{
    if (value.IsObject())
    {
        std::vector<const Value::Member*> members;
        for (auto it = value.MemberBegin(); it != value.MemberEnd(); ++it) members.push_back(&*it);
        std::sort(members.begin(), members.end(), [](auto lhs, auto rhs) { return text(lhs->name) < text(rhs->name); });
        writer.StartObject();
        for (auto member : members)
        { writer.Key(member->name.GetString(), member->name.GetStringLength()); canonical(member->value, writer); }
        writer.EndObject();
    }
    else if (value.IsArray())
    { writer.StartArray(); for (const auto& item : value.GetArray()) canonical(item, writer); writer.EndArray(); }
    else value.Accept(writer);
}
std::string encode(const Value& value)
{
    rapidjson::StringBuffer buffer;
    rapidjson::Writer<rapidjson::StringBuffer> writer(buffer);
    canonical(value, writer);
    return {buffer.GetString(), buffer.GetSize()};
}
bool digits(const std::string& value)
{ return !value.empty() && std::all_of(value.begin(), value.end(), [](char c) { return c >= '0' && c <= '9'; }); }
bool date_time(const std::string& value)
{
    if (value.size() != 14 || !digits(value)) return false;
    auto part = [&](std::size_t index, std::size_t size) { return std::stoi(value.substr(index, size)); };
    const int year = part(0, 4), month = part(4, 2), day = part(6, 2);
    static const int days[] = {0,31,28,31,30,31,30,31,31,30,31,30,31};
    if (year < 1992 || year > 9999 || month < 1 || month > 12) return false;
    const int maximum = days[month] + (month == 2 && year % 4 == 0 && (year % 100 != 0 || year % 400 == 0));
    return day >= 1 && day <= maximum && part(8,2) <= 23 && part(10,2) <= 59 && part(12,2) <= 59;
}
bool source_time(const std::string& value)
{
    if (value.size() < 20 || value.size() > 40 || value[4] != '-' || value[7] != '-' || value[10] != 'T'
        || value[13] != ':' || value[16] != ':') return false;
    if (!date_time(value.substr(0,4)+value.substr(5,2)+value.substr(8,2)+value.substr(11,2)+value.substr(14,2)+value.substr(17,2))) return false;
    std::size_t index = 19;
    if (index < value.size() && value[index] == '.')
    {
        auto begin = ++index;
        while (index < value.size() && value[index] >= '0' && value[index] <= '9') ++index;
        if (index == begin || index - begin > 9) return false;
    }
    if (value.substr(index) == "Z") return true;
    if (value.size() - index != 6 || (value[index] != '+' && value[index] != '-') || value[index+3] != ':') return false;
    const auto hour = value.substr(index+1,2), minute = value.substr(index+4,2);
    return digits(hour) && digits(minute) && std::stoi(hour) <= 23 && std::stoi(minute) <= 59;
}
bool symbols(const Value& value)
{
    if (!value.IsArray() || value.Empty() || value.Size() > 200) return false;
    std::set<std::string> unique;
    for (const auto& item : value.GetArray())
    {
        if (!string_value(item, 9)) return false;
        auto code = text(item);
        if (code.size() != 9 || !digits(code.substr(0,6)) || (code.substr(6) != ".SH" && code.substr(6) != ".SZ")
            || !unique.insert(code).second) return false;
    }
    return true;
}
bool arguments(const std::string& operation, const Value& value)
{
    if (operation == "account.trade_detail")
    {
        if (!keys(value,{"account_type","datatype","scope"}) || !has_string(value,"account_type")
            || !has_string(value,"datatype") || !has_string(value,"scope")) return false;
        const auto type = text(value["datatype"]);
        return text(value["account_type"]) == "stock" && text(value["scope"]) == "account"
            && (type == "position" || type == "order" || type == "deal" || type == "account");
    }
    if (operation == "market.full_tick") return keys(value, {"stocks"}) && symbols(value["stocks"]);
    if (!keys(value, {"fields", "stock_codes", "period", "start_time", "end_time", "count", "dividend_type", "fill_data", "subscribe"})) return false;
    if (!symbols(value["stock_codes"]) || !value["fields"].IsArray() || value["fields"].Size() != 7) return false;
    std::set<std::string> fields;
    for (const auto& item : value["fields"].GetArray()) { if (!string_value(item)) return false; fields.insert(text(item)); }
    if (fields != std::set<std::string>{"time","open","high","low","close","volume","amount"}) return false;
    if (!has_string(value,"period") || text(value["period"]) != "1m" || !has_string(value,"dividend_type") || text(value["dividend_type"]) != "none"
        || !value["fill_data"].IsBool() || value["fill_data"].GetBool() || !value["subscribe"].IsBool() || value["subscribe"].GetBool()
        || !value["count"].IsUint() || value["count"].GetUint() < 1 || value["count"].GetUint() > 5000
        || !has_string(value,"start_time") || !has_string(value,"end_time")) return false;
    const auto from = text(value["start_time"]), to = text(value["end_time"]);
    return date_time(from) && date_time(to) && from <= to;
}
// 能力文档只缩小固定域；旧策略范围不能代替全账户查询契约。
bool includes_strings(const Value& value, std::initializer_list<const char*> required)
{
    if (!value.IsArray() || value.Size() > 64) return false;
    std::set<std::string> actual;
    for (const auto& item : value.GetArray())
        if (!string_value(item) || !actual.insert(text(item)).second) return false;
    for (auto item : required) if (!actual.count(item)) return false;
    return true;
}
bool account_contract(const Value& operation)
{
    if (!operation.HasMember("query_contract") || !operation["query_contract"].IsObject()) return false;
    const auto& contract = operation["query_contract"];
    return has_string(contract,"schema_version") && text(contract["schema_version"]) == "qmt.account-query.v1"
        && has_string(contract,"default_scope") && text(contract["default_scope"]) == "strategy"
        && contract.HasMember("scopes") && includes_strings(contract["scopes"],{"account"})
        && contract.HasMember("account_types") && includes_strings(contract["account_types"],{"stock"})
        && contract.HasMember("datatypes") && includes_strings(contract["datatypes"],{"position","order","deal","account"});
}
}

class QmtReadTransport::Impl
{
public:
    BoundedSignedHttp http;
    const QmtReadDomain domain;
    std::thread::id owner = std::this_thread::get_id();
    SourceSession source;
    std::string last_tick;
    bool ready = false;
    std::set<std::string> operations;
    Status configured;
    Impl(QmtHttpConfig config,QmtReadDomain selected) : http(std::move(config)), domain(selected)
    {
        if (domain != QmtReadDomain::Market && domain != QmtReadDomain::Account)
            configured = failure(ErrorCode::InvalidInput,"qmt_http_domain_invalid");
    }
    Status check() const
    {
        if (owner != std::this_thread::get_id()) return failure(ErrorCode::InvalidInput,"qmt_http_owner_thread_required");
        return configured.ok() ? http.check() : configured;
    }
    HttpResult exchange(const char* method,const std::string& target,const std::string& body,Deadline& deadline)
    { return http.exchange(method,target,body,deadline); }
    Status health(Deadline& deadline, SourceSession& identity, std::string& tick)
    {
        auto response = exchange("GET","/internal/v1/health",{},deadline);
        if (!response.status.ok()) return response.status;
        Document document;
        if (response.code != 200 || !parse(response.body,document) || !document.IsObject() || !has_string(document,"gateway_version")
            || !has_string(document,"agent_id") || !has_string(document,"qmt_session_id") || !has_string(document,"capabilities_version")
            || !has_string(document,"status") || !document.HasMember("generation") || !document["generation"].IsUint64() || !document["generation"].GetUint64())
            return failure(ErrorCode::IoError,"qmt_http_health_invalid");
        if (text(document["status"]) != "ready") return failure(ErrorCode::Unavailable,"qmt_http_source_not_ready");
        identity = {ProviderKind::Qmt,text(document["agent_id"]),text(document["qmt_session_id"]),document["generation"].GetUint64()};
        tick.clear();
        if (document.HasMember("last_tick_at") && document["last_tick_at"].IsString() && source_time(text(document["last_tick_at"]))) tick = text(document["last_tick_at"]);
        return {};
    }
    Status verify_health(Deadline& deadline)
    {
        SourceSession observed; std::string tick;
        auto status = health(deadline,observed,tick);
        if (!status.ok()) { ready = false; operations.clear(); last_tick.clear(); return status; }
        if (!same_session(source,observed)) { ready = false; operations.clear(); last_tick.clear(); return failure(ErrorCode::StaleSession,"qmt_http_source_session_changed"); }
        last_tick = tick; return {};
    }
    Status prepare(std::uint32_t milliseconds)
    {
        auto status = check(); if (!status.ok()) return status;
        ready = false; operations.clear(); last_tick.clear(); source = {};
        if (!milliseconds || milliseconds > 30000) return failure(ErrorCode::InvalidInput,"qmt_http_budget_invalid");
        Deadline deadline(milliseconds);
        SourceSession first, second; std::string tick;
        status = health(deadline,first,tick); if (!status.ok()) return status;
        auto response = exchange("GET","/internal/v1/capabilities",{},deadline);
        if (!response.status.ok()) return response.status;
        Document document;
        if (response.code != 200 || !parse(response.body,document) || !document.IsObject() || !has_string(document,"capabilities_version")
            || !document.HasMember("operations") || !document["operations"].IsArray() || document["operations"].Size() > 1000)
            return failure(ErrorCode::IoError,"qmt_http_capabilities_invalid");
        std::set<std::string> seen;
        for (const auto& operation : document["operations"].GetArray())
        {
            if (!operation.IsObject() || !has_string(operation,"operation_id") || !seen.insert(text(operation["operation_id"])).second)
                return failure(ErrorCode::IoError,"qmt_http_capabilities_invalid");
            const auto name = text(operation["operation_id"]);
            if (!permitted(domain,name)) continue;
            if (!operation.HasMember("implemented") || !operation["implemented"].IsBool() || !operation["implemented"].GetBool()
                || !operation.HasMember("mutating") || !operation["mutating"].IsBool() || operation["mutating"].GetBool()) continue;
            if (domain == QmtReadDomain::Account && !account_contract(operation)) continue;
            operations.insert(name);
        }
        status = health(deadline,second,tick); if (!status.ok()) { operations.clear(); return status; }
        if (!same_session(first,second)) { operations.clear(); return failure(ErrorCode::StaleSession,"qmt_http_source_session_changed"); }
        if (operations.empty()) return failure(ErrorCode::Unavailable,"qmt_http_reads_unavailable");
        source = second; last_tick = tick; ready = true; return {};
    }
    JsonResult read(const std::string& operation, const std::string& input, std::uint32_t milliseconds)
    {
        Deadline deadline(milliseconds);
        auto status = check(); if (!status.ok()) return {status,{}};
        if (!permitted(domain,operation)) return {failure(ErrorCode::NotSupported,"qmt_http_operation_rejected"),{}};
        if (!ready || !operations.count(operation)) return {failure(ErrorCode::Unavailable,"qmt_http_operation_unprepared"),{}};
        if (!milliseconds || milliseconds > 30000 || input.size() > 65536) return {failure(ErrorCode::InvalidInput,"qmt_http_request_limit"),{}};
        Document argument;
        if (!parse(input,argument) || !arguments(operation,argument)) return {failure(ErrorCode::InvalidInput,"qmt_http_arguments_rejected"),{}};
        status = verify_health(deadline); if (!status.ok()) return {status,{}};
        if (deadline.remaining() < 100) return {failure(ErrorCode::Timeout,"qmt_http_deadline"),{}};
#ifdef _WIN32
        const auto request_id = signed_http_uuid();
        if (request_id.empty()) return {failure(ErrorCode::Unavailable,"qmt_http_crypto_unavailable"),{}};
#else
        const std::string request_id;
#endif
        // 请求身份一旦创建即由本次结果持有；任何网络/协议失败均保留它。
        JsonResult output; output.request_id = request_id; output.operation_id = operation;
        auto failed = [&](Status error) { output.status = std::move(error); return output; };
        auto observe = [&](HttpResult& response) {
            if (response.code || !response.body.empty())
            {
                output.http_status = response.code; output.envelope_json = std::move(response.body);
                output.terminal = false; output.remote_ok = false;
            }
        };
        Document request; request.SetObject(); auto& allocator = request.GetAllocator();
        auto add = [&](const char* name, const std::string& value) { request.AddMember(Value(name,allocator),Value(value.data(),static_cast<rapidjson::SizeType>(value.size()),allocator),allocator); };
        add("request_id",request_id); add("correlation_id",request_id); add("operation_id",operation);
        request.AddMember("arguments",Value(argument,allocator),allocator);
        add("policy_id","qmt.standard-read.v1"); add("policy_version","1.0"); add("priority_class","normal");
        request.AddMember("timeout_ms",std::min<std::uint32_t>(5000,deadline.remaining()),allocator);
        auto response = exchange("POST","/internal/v1/operations/"+operation,encode(request),deadline);
        observe(response);
        // POST 的网络结果未知（包括已收到成功头但正文中断）只沿原 ID 认领。
        // 明确 HTTP 拒绝和容量失败没有自动重投或认领。
        bool claim = !response.status.ok() && response.delivery_unknown
            && (response.code == 0 || response.code == 200 || response.code == 202);
        if (!response.status.ok() && !claim) return failed(response.status);
        for (;;)
        {
            if (claim)
            {
                if (!deadline.remaining()) return failed(failure(ErrorCode::Timeout,"qmt_http_deadline"));
                response = exchange("GET","/internal/v1/operation-results/"+request_id,{},deadline);
                observe(response);
                if (!response.status.ok()) return failed(response.status);
            }
            Document result;
            if (!parse(output.envelope_json,result) || !result.IsObject() || !has_string(result,"request_id") || !has_string(result,"operation_id"))
                return failed(failure(ErrorCode::IoError,"qmt_http_result_invalid"));
            if (text(result["request_id"]) != request_id || text(result["operation_id"]) != operation)
                return failed(failure(ErrorCode::Conflict,"qmt_http_result_identity_mismatch"));
            if (response.code == 202)
            {
                if (!has_string(result,"status") || (text(result["status"]) != "queued" && text(result["status"]) != "executing"))
                    return failed(failure(ErrorCode::IoError,"qmt_http_progress_invalid"));
                const auto remaining = deadline.remaining();
                if (!remaining) return failed(failure(ErrorCode::Timeout,"qmt_http_deadline"));
                std::this_thread::sleep_for(std::chrono::milliseconds(std::min<std::uint32_t>(25,remaining)));
                claim = true; continue;
            }
            if (response.code != 200 || !result.HasMember("ok") || !result["ok"].IsBool() || !result.HasMember("completed_at")
                || !result["completed_at"].IsString() || !source_time(text(result["completed_at"])))
                return failed(failure(ErrorCode::IoError,"qmt_http_result_invalid"));
            output.terminal = true; output.remote_ok = result["ok"].GetBool();
            if (!output.remote_ok) return failed(failure(ErrorCode::IoError,"qmt_http_operation_failed"));
            if (!result.HasMember("data")) return failed(failure(ErrorCode::IoError,"qmt_http_result_data_missing"));
            auto data = encode(result["data"]);
            status = verify_health(deadline);
            if (!status.ok()) return failed(status);
            if (!deadline.remaining()) return failed(failure(ErrorCode::Timeout,"qmt_http_deadline"));
            output.data_json = std::move(data); return output;
        }
    }
};

QmtReadTransport::QmtReadTransport(QmtHttpConfig config, QmtReadDomain domain) : impl_(new Impl(std::move(config),domain)) {}
QmtReadTransport::~QmtReadTransport() = default;
Status QmtReadTransport::drain_callbacks(std::uint32_t milliseconds) noexcept
{ return impl_->http.drain_callbacks(milliseconds); }
Status QmtReadTransport::prepare(std::uint32_t deadline_ms) { return impl_->prepare(deadline_ms); }
SourceSession QmtReadTransport::session() const { return impl_->check().ok() && impl_->ready ? impl_->source : SourceSession{}; }
Capability QmtReadTransport::capability(const std::string& operation) const
{
    if (impl_->check().ok() && impl_->ready && impl_->operations.count(operation)) return {true,Qualification::DevelopmentVerified,"qmt_http_read_capability"};
    return {false,Qualification::Unavailable,"qmt_http_read_unavailable"};
}
std::string QmtReadTransport::last_source_time() const { return impl_->check().ok() && impl_->ready ? impl_->last_tick : std::string{}; }
JsonResult QmtReadTransport::read_operation(const std::string& operation, const std::string& input, std::uint32_t deadline_ms)
{ return impl_->read(operation,input,deadline_ms); }
}
