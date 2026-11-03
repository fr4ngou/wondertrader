#include "QmtHostTradeClient.h"
#include "QmtHostCodec.h"
#include <algorithm>
#include <cmath>
#include <cstring>
#include <limits>
#include <stdexcept>
#include <thread>
#include <type_traits>
#include <utility>
#if defined(_WIN32) && defined(GH_QMT_HTTP_DRAIN_TESTING)
#include <atomic>
#include <new>
namespace { std::atomic<bool> trade_after_exchange_fault{false}, cancel_publish_fault{false}; }
// 专用测试制品在真实POST返回后触发分配异常；生产无此导出或运行开关。
extern "C" __declspec(dllexport) void gh_qmt_trade_test_after_exchange_fault(bool enabled) noexcept
{ trade_after_exchange_fault.store(enabled); }
extern "C" __declspec(dllexport) void gh_qmt_trade_test_cancel_publish_fault(bool enabled) noexcept
{ cancel_publish_fault.store(enabled); }
#endif
#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <Windows.h>
#endif

namespace guanheng
{
namespace
{
using Value = rapidjson::Value;
using Document = rapidjson::Document;
using namespace qmt_host_codec;
// 只携固定值；不从Status/reason猜运输恢复，不借用HTTP正文生命周期。
void event_reply_failure(QmtTradeEventReadFailure* out, const SignedHttpResult& reply) noexcept
{
    if (!out) return;
    out->transport = reply.failure; out->http_status = reply.code;
    out->send_attempted = reply.send_attempted; out->response_complete = reply.response_complete;
    if (reply.code && reply.code != 200) {
        out->transport.recovery = SignedHttpRecovery::None;
        out->transport.origin = SignedHttpFailureOrigin::RemoteHttp;
    } else if (reply.status.ok()) {
        out->transport = {}; // 后继协议/复制失败不继承运输许可。
        out->transport.origin = SignedHttpFailureOrigin::LocalOrProtocol;
    }
}
void event_local_failure(QmtTradeEventReadFailure* out) noexcept
{
    if (!out) return;
    out->outcome = QmtTradeEventReadOutcome::Failure;
    out->transport.recovery = SignedHttpRecovery::None;
    out->transport.origin = SignedHttpFailureOrigin::LocalOrProtocol;
}
constexpr std::uint64_t maximum_integer = (1ULL << 53) - 1;
constexpr std::size_t metadata_capacity = 16384, profile_capacity = 4096;
constexpr std::size_t command_capacity = 65536, result_capacity = 2097152;
Status fail(ErrorCode code, const char* reason) { return {code, reason}; }
bool parse(const std::string& raw, Document& out, std::size_t maximum)
{ return parse_bounded_qmt_json(raw, out, maximum, 4*1024*1024); }
bool integer(const Value& value, std::uint64_t lo = 0, std::uint64_t hi = maximum_integer)
{ return value.IsUint64() && value.GetUint64() >= lo && value.GetUint64() <= hi; }
bool finite(const Value& value) { return value.IsNumber() && std::isfinite(value.GetDouble()); }
void add(Document& value, const char* key, const std::string& item)
{
    auto& allocator = value.GetAllocator();
    value.AddMember(Value(key, allocator), Value(item.data(), static_cast<rapidjson::SizeType>(item.size()), allocator), allocator);
}
bool safe_text(const Value& value, std::size_t maximum, bool ascii = false, bool spaces = true)
{
    if (!string(value, maximum)) return false;
    const auto raw = text(value);
    bool nonspace = false;
    for (std::size_t i = 0; i < raw.size();)
    {
        auto c = static_cast<unsigned char>(raw[i++]);
        std::uint32_t codepoint = c;
        if (c >= 128)
        {
            if (ascii) return false;
            unsigned continuation = 0;
            if ((c & 0xe0) == 0xc0) { codepoint = c & 0x1f; continuation = 1; }
            else if ((c & 0xf0) == 0xe0) { codepoint = c & 0x0f; continuation = 2; }
            else if ((c & 0xf8) == 0xf0) { codepoint = c & 0x07; continuation = 3; }
            else return false;
            if (raw.size() - i < continuation) return false;
            while (continuation--)
            {
                c = static_cast<unsigned char>(raw[i++]);
                if ((c & 0xc0) != 0x80) return false;
                codepoint = (codepoint << 6) | (c & 0x3f);
            }
        }
        if (codepoint < 32 || (codepoint >= 127 && codepoint <= 159) || (!spaces && codepoint == 32)) return false;
        nonspace = nonspace || codepoint != 32;
    }
    return nonspace;
}
bool safe_text(const std::string& value, std::size_t maximum, bool ascii = false, bool spaces = true)
{
    Document encoded; encoded.SetString(value.data(), static_cast<rapidjson::SizeType>(value.size()), encoded.GetAllocator());
    Document checked;
    return parse(encode(encoded), checked, maximum*6+2) && safe_text(checked, maximum, ascii, spaces);
}
bool decimal(const Value& value)
{
    if (!string(value, 64)) return false;
    const auto raw = text(value);
    std::size_t i = 0;
    bool positive = false;
    auto digits = [&]() {
        const auto start = i;
        while (i < raw.size() && raw[i] >= '0' && raw[i] <= '9') { positive = positive || raw[i] != '0'; ++i; }
        return i > start;
    };
    if (!digits()) return false;
    if (i < raw.size() && raw[i] == '.') { ++i; if (!digits()) return false; }
    if (!positive) return false;
    if (i < raw.size() && (raw[i] == 'e' || raw[i] == 'E'))
    {
        ++i;
        if (i < raw.size() && (raw[i] == '+' || raw[i] == '-')) ++i;
        const auto start = i;
        unsigned exponent = 0;
        while (i < raw.size() && raw[i] >= '0' && raw[i] <= '9')
        { if (exponent > 308) return false; exponent = exponent*10 + static_cast<unsigned>(raw[i++] - '0'); }
        if (i == start || exponent > 308) return false;
    }
    return i == raw.size();
}
bool command(const Value& value, const QmtExpectedTrade& expected)
{
    if (!field(value, "operation")) return false;
    const bool insert = text(value["operation"]) == "order.insert";
    if (insert)
    {
        if (!keys(value, {"schema_version", "command_id", "operation", "binding_id", "account_id", "account_type",
                "entrust_id", "user_tag", "symbol", "side", "order_type", "limit_price", "quantity", "sdk_user_order_id"})) return false;
    }
    else if (text(value["operation"]) != "order.cancel" || !keys(value, {"schema_version", "command_id", "operation",
            "binding_id", "account_id", "account_type", "entrust_id", "user_tag", "original_command_id", "broker_order_id"})) return false;
    if (!field(value, "schema_version") || text(value["schema_version"]) != "qmt.trade-command.v1"
        || !uuid(value["command_id"]) || !safe_text(value["binding_id"], 128, true)
        || text(value["binding_id"]) != expected.binding_id || !safe_text(value["account_id"], 63)
        || text(value["account_id"]) != expected.account.account_id
        || !field(value, "account_type") || text(value["account_type"]) != "stock"
        || !safe_text(value["entrust_id"], 63) || !safe_text(value["user_tag"], 63)) return false;
    if (!insert) return uuid(value["original_command_id"]) && safe_text(value["broker_order_id"], 128, true);
    if (!field(value, "symbol", 9) || value["symbol"].GetStringLength() != 9
        || !field(value, "side") || (text(value["side"]) != "buy" && text(value["side"]) != "sell")
        || !field(value, "order_type") || text(value["order_type"]) != "limit"
        || !integer(value["quantity"], 1) || !decimal(value["limit_price"])
        || !value["sdk_user_order_id"].IsString() || value["sdk_user_order_id"].GetStringLength()>64
        || !valid_qmt_sdk_order_token(text(value["sdk_user_order_id"]))) return false;
    const auto symbol = text(value["symbol"]);
    return std::all_of(symbol.begin(), symbol.begin()+6, [](char c){ return c >= '0' && c <= '9'; })
        && (symbol.substr(6) == ".SH" || symbol.substr(6) == ".SZ");
}
bool gap(const Value& value)
{
    return value.IsNull() || (keys(value, {"code", "sequence"}) && safe_text(value["code"], 128, true)
        && (value["sequence"].IsNull() || integer(value["sequence"], 1)));
}
enum class StatusVersion { V1, V2 };
enum class TradeOperation { Insert, Cancel };
bool hard_fault(const Value& value)
{ return value.IsNull() || (keys(value, {"code"}) && safe_text(value["code"], 128, true)); }
bool source_status(const Value& value, const QmtExpectedTrade& expected, const QmtTradeReadDescriptor& limits, bool writes,
                   StatusVersion& version)
{
    if (!field(value, "schema_version")) return false;
    const auto schema = text(value["schema_version"]);
    const bool v2 = schema == "qmt.trade-source-status.v2";
    if (!v2 && schema != "qmt.trade-source-status.v1") return false;
    if (!(v2 ? keys(value, {"schema_version", "session_id", "binding_id", "binding_sha256", "writes_enabled", "source_mode_live",
            "write_admission", "closing", "gap", "queued", "executing", "commands", "completed", "events",
            "unknown_fenced", "hard_fault", "cancel_admission"})
        : keys(value, {"schema_version", "session_id", "binding_id", "binding_sha256", "writes_enabled", "source_mode_live",
            "write_admission", "closing", "gap", "queued", "executing", "commands", "completed", "events"}))
        || !safe_text(value["session_id"], 128, true) || !safe_text(value["binding_id"], 128, true)
        || text(value["binding_id"]) != expected.binding_id || !hex(value["binding_sha256"], 64)
        || text(value["binding_sha256"]) != expected.binding_sha256 || !gap(value["gap"])) return false;
    for (auto key : {"writes_enabled", "source_mode_live", "write_admission", "closing", "executing"})
        if (!value[key].IsBool()) return false;
    for (auto key : {"queued", "completed", "commands"}) if (!integer(value[key], 0, limits.max_commands)) return false;
    if (value["writes_enabled"].GetBool() != writes
        || value["queued"].GetUint64()+value["completed"].GetUint64() > value["commands"].GetUint64()
        || value["queued"].GetUint64()+static_cast<unsigned>(value["executing"].GetBool()) > value["commands"].GetUint64()) return false;
    const auto& events = value["events"];
    if (!keys(events, {"closed", "inflight", "retained", "used_bytes", "published_through", "offered_through",
            "acknowledged_through", "gap", "session_id", "binding_id"}) || !events["closed"].IsBool()
        || !field(events, "session_id") || text(events["session_id"]) != text(value["session_id"])
        || !field(events, "binding_id") || text(events["binding_id"]) != expected.binding_id
        || !integer(events["retained"], 0, limits.max_events) || !integer(events["inflight"], 0, events["retained"].GetUint64())
        || !integer(events["used_bytes"], 0, limits.max_total_event_bytes) || !integer(events["published_through"])
        || !integer(events["offered_through"], 0, events["published_through"].GetUint64())
        || !integer(events["acknowledged_through"], 0, events["offered_through"].GetUint64())
        || events["published_through"].GetUint64()-events["acknowledged_through"].GetUint64() > events["retained"].GetUint64()
        || !gap(events["gap"]) || (!events["gap"].IsNull() && encode(events["gap"]) != encode(value["gap"]))) return false;
    if (v2)
    {
        if (!value["unknown_fenced"].IsBool() || !value["cancel_admission"].IsBool() || !hard_fault(value["hard_fault"])
            || encode(events["gap"]) != encode(value["gap"])) return false;
        const bool base = writes && value["source_mode_live"].GetBool() && !value["closing"].GetBool()
            && !events["closed"].GetBool() && value["gap"].IsNull() && value["hard_fault"].IsNull();
        if (value["cancel_admission"].GetBool() != base
            || value["write_admission"].GetBool() != (base && !value["unknown_fenced"].GetBool())) return false;
    }
    else if (value["write_admission"].GetBool() && (!writes || !value["source_mode_live"].GetBool()
        || value["closing"].GetBool() || !value["gap"].IsNull())) return false;
    version = v2 ? StatusVersion::V2 : StatusVersion::V1;
    return true;
}
bool result(const Value& value, const Value& original)
{
    if (!keys(value, {"schema_version", "command_id", "command_sha256", "operation", "stage", "sdk_entered", "signal_sent", "error_code"})
        || !field(value, "schema_version") || text(value["schema_version"]) != "qmt.trade-call-result.v1"
        || !uuid(value["command_id"]) || text(value["command_id"]) != text(original["command_id"])
        || !hex(value["command_sha256"], 64) || text(value["command_sha256"]) != signed_http_sha256(encode(original))
        || !field(value, "operation") || text(value["operation"]) != text(original["operation"])
        || !field(value, "stage") || !value["sdk_entered"].IsBool()
        || (!value["signal_sent"].IsNull() && !value["signal_sent"].IsBool())) return false;
    const bool insert = text(original["operation"]) == "order.insert";
    const auto stage = text(value["stage"]);
    if (insert && !value["signal_sent"].IsNull()) return false;
    if (stage == "sdk_returned") return value["sdk_entered"].GetBool() && value["error_code"].IsNull()
        && (insert || value["signal_sent"].IsBool());
    if (!field(value, "error_code")) return false;
    const auto code = text(value["error_code"]);
    if (stage == "definitely_not_called")
    {
        if (value["sdk_entered"].GetBool() || !value["signal_sent"].IsNull()) return false;
        const bool general = code == "not_admitted" || code == "capacity_exhausted" || code == "binding_mismatch"
            || code == "writes_disabled" || code == "admission_closed" || code == "deadline_expired" || code == "clock_failed";
        return general || (insert && (code == "symbol_not_allowed" || code == "quantity_off_grid" || code == "price_off_grid"
            || code == "price_not_representable"));
    }
    if (stage != "unknown" || !value["sdk_entered"].GetBool()) return false;
    // cancel已返回bool后，后置时钟异常仍保留该信号事实。
    if (code == "sdk_exception") return true;
    if (code == "invalid_sdk_return") return value["signal_sent"].IsNull();
    return code == "deadline_expired_after_call" && (insert || value["signal_sent"].IsBool());
}
QmtTradePhase phase(const std::string& value)
{
    if (value == "queued") return QmtTradePhase::Queued;
    if (value == "dispatching") return QmtTradePhase::Dispatching;
    if (value == "definitely_not_called") return QmtTradePhase::DefinitelyNotCalled;
    if (value == "sdk_returned") return QmtTradePhase::SdkReturned;
    return QmtTradePhase::Unknown;
}
bool record(const Value& value, const QmtTradeReceipt& receipt, const QmtExpectedTrade& expected,
            const QmtTradeReadDescriptor& limits, QmtTradePhase& observed, std::string& native)
{
    if (!keys(value, {"schema_version", "command_id", "command_sha256", "command_body_b64", "state", "admitted_binding",
            "dispatch_binding", "result_binding", "source_result", "result_sha256", "host_reason", "queued_at", "expires_at", "started_at"})
        || !field(value, "schema_version") || text(value["schema_version"]) != "qmt.bound-trade.v1"
        || !uuid(value["command_id"]) || !hex(value["command_sha256"], 64) || !field(value, "state")) return false;
    std::string body;
    Document original;
    if (!unbase64(value["command_body_b64"], static_cast<std::size_t>(limits.max_command_bytes), body)
        || body != receipt.command_body || !parse(body, original, command_capacity) || !command(original, expected)
        || encode(original) != body || text(value["command_id"]) != text(original["command_id"])
        || signed_http_sha256(body) != text(value["command_sha256"])) return false;
    if (!binding(value["admitted_binding"], nullptr, "2.0") || encode(value["admitted_binding"]) != receipt.binding_json) return false;
    const bool dispatched = !value["dispatch_binding"].IsNull(), received = !value["result_binding"].IsNull();
    for (auto key : {"dispatch_binding", "result_binding"})
        if (!value[key].IsNull() && (!binding(value[key], nullptr, "2.0") || encode(value[key]) != receipt.binding_json)) return false;
    if ((received && !dispatched) || !finite(value["queued_at"]) || !finite(value["expires_at"])
        || (dispatched ? !finite(value["started_at"]) : !value["started_at"].IsNull())) return false;
    const auto state = text(value["state"]);
    if (state != "queued" && state != "dispatching" && state != "definitely_not_called" && state != "sdk_returned" && state != "unknown") return false;
    if ((state == "queued" && dispatched) || ((state == "dispatching" || state == "sdk_returned" || state == "unknown") && !dispatched)) return false;
    if (value["source_result"].IsNull())
    {
        if (received || !value["result_sha256"].IsNull() || state == "sdk_returned") return false;
        if (state == "queued" || state == "dispatching") { if (!value["host_reason"].IsNull()) return false; }
        else
        {
            if (!field(value, "host_reason")) return false;
            const auto reason = text(value["host_reason"]);
            if (reason != "owner_restarted" && reason != "deadline_expired" && reason != "source_binding_changed"
                && reason != "deadline_unavailable" && reason != "interrupted") return false;
        }
        native.clear();
    }
    else
    {
        if (!received || !value["host_reason"].IsNull() || !result(value["source_result"], original)
            || text(value["source_result"]["stage"]) != state || !hex(value["result_sha256"], 64)) return false;
        auto source = encode(value["source_result"]);
        if (source.size() > limits.max_call_result_bytes || signed_http_sha256(source) != text(value["result_sha256"])) return false;
        native = std::move(source);
    }
    Document metadata;
    metadata.CopyFrom(value, metadata.GetAllocator()); metadata.RemoveMember("command_body_b64");
    if (encode(metadata).size() > metadata_capacity) return false;
    observed = phase(state);
    return true;
}
std::uint64_t uptime()
{
#ifdef _WIN32
    return GetTickCount64();
#else
    return std::numeric_limits<std::uint64_t>::max();
#endif
}
std::size_t record_capacity(const QmtTradeReadDescriptor& value)
{ return static_cast<std::size_t>(4*((value.max_command_bytes+2)/3)+value.max_call_result_bytes+metadata_capacity); }
// 两个入口共用原source/请求准入；历史source不与当前pin/session作相等要求。
Status event_request(const QmtTradeEventSource& source, const QmtTradeEventRequestBounds& request,
    const QmtExpectedTrade& expected, const QmtTradeReadDescriptor& limits,
    std::size_t page_capacity, Document& source_binding)
{
    // 先限可信上下文的形状，避免给纯入口的无效参数构造超额临时JSON。
    if (expected.account.account_id.empty() || expected.account.account_id.size() > 63
        || expected.binding_id.empty() || expected.binding_id.size() > 128
        || expected.binding_sha256.size() != 64 || limits.binding_sha256 != expected.binding_sha256
        || !limits.max_event_bytes || !page_capacity || page_capacity > limits.max_event_page_bytes
        || source.session_id.size() > 128
        || request.after_seq > maximum_integer || !request.limit || request.limit > limits.max_events
        || !request.max_bytes || request.max_bytes > page_capacity)
        return fail(ErrorCode::InvalidInput, "qmt_trade_event_request_invalid");
    Document expected_hash;
    expected_hash.SetString(expected.binding_sha256.data(),
        static_cast<rapidjson::SizeType>(expected.binding_sha256.size()), expected_hash.GetAllocator());
    if (!hex(expected_hash, 64) || !safe_text(expected.account.account_id, 63)
        || !safe_text(expected.binding_id, 128, true)
        || !parse(source.binding_json, source_binding, 4096) || !binding(source_binding, nullptr, "2.0")
        || encode(source_binding) != source.binding_json || !safe_text(source.session_id, 128, true))
        return fail(ErrorCode::InvalidInput, "qmt_trade_event_request_invalid");
    return {};
}

// candidate只属于本次调用。原完整页正文每个准入边界只解析一次，DOM供后继直接使用。
Status event_body(const std::string& page_json, const QmtTradeEventSource& source,
    const QmtTradeEventRequestBounds& request, const QmtExpectedTrade& expected,
    const QmtTradeReadDescriptor& limits, SignedHttpDeadline& deadline,
    QmtValidatedTradeEventPage& candidate)
{
    auto& value = candidate.document;
    if (!parse(page_json, value, request.max_bytes) || !field(value, "schema_version"))
        return fail(ErrorCode::IoError, "qmt_trade_event_page_invalid");
    const auto schema = text(value["schema_version"]);
    const bool continued = schema == "qmt.persisted-trade-events.v2";
    if ((!continued && schema != "qmt.persisted-trade-events.v1")
        || !(continued ? keys(value, {"schema_version", "receipt", "events", "continuity"})
                       : keys(value, {"schema_version", "receipt", "events"}))
        || !value["events"].IsArray() || value["events"].Size() > request.limit)
        return fail(ErrorCode::IoError, "qmt_trade_event_page_invalid");
    const auto& receipt = value["receipt"];
    auto receipt_binding_sha = signed_http_sha256(source.binding_json);
    if (continued) {
        // 已认证 Host 证明当前连接属于原事件流；重连只续接认证关系。
        // 原收据及事件字节保留创世来源，同时核对当前连接与原收据摘要。
        const auto& proof = value["continuity"];
        if (!keys(proof, {"schema_version", "session_id", "binding_id", "current_host_binding_sha256",
                "origin_host_binding_sha256", "authenticated"})
            || !field(proof, "schema_version") || text(proof["schema_version"]) != "qmt.trade-source-continuity.v1"
            || !field(proof, "session_id") || text(proof["session_id"]) != source.session_id
            || !field(proof, "binding_id") || text(proof["binding_id"]) != expected.binding_id
            || !hex(proof["current_host_binding_sha256"], 64)
            || text(proof["current_host_binding_sha256"]) != receipt_binding_sha
            || !hex(proof["origin_host_binding_sha256"], 64)
            || !proof["authenticated"].IsBool() || !proof["authenticated"].GetBool())
            return fail(ErrorCode::IoError, "qmt_trade_event_continuity_invalid");
        receipt_binding_sha = text(proof["origin_host_binding_sha256"]);
    }
    if (!keys(receipt, {"schema_version", "session_id", "binding_id", "host_binding_sha256", "durable_through", "ack_intended_through",
            "source_ack_through", "observed_published_through", "gap"})
        || !field(receipt, "schema_version") || text(receipt["schema_version"]) != "qmt.trade-event-receipt.v1"
        || !field(receipt, "session_id") || text(receipt["session_id"]) != source.session_id
        || !field(receipt, "binding_id") || text(receipt["binding_id"]) != expected.binding_id
        || !hex(receipt["host_binding_sha256"], 64) || text(receipt["host_binding_sha256"]) != receipt_binding_sha
        || !integer(receipt["durable_through"]) || !integer(receipt["ack_intended_through"], receipt["durable_through"].GetUint64(), receipt["durable_through"].GetUint64())
        || !integer(receipt["source_ack_through"], 0, receipt["durable_through"].GetUint64())
        || !integer(receipt["observed_published_through"], receipt["durable_through"].GetUint64()) || !gap(receipt["gap"]))
        return fail(ErrorCode::IoError, "qmt_trade_event_receipt_invalid");
    auto next = request.after_seq;
    for (const auto& event : value["events"].GetArray())
    {
        if (!keys(event, {"schema_version", "session_id", "binding_id", "sequence", "kind", "payload"})
            || !field(event, "schema_version") || text(event["schema_version"]) != "qmt.trade-event.v1"
            || !field(event, "session_id") || text(event["session_id"]) != source.session_id
            || !field(event, "binding_id") || text(event["binding_id"]) != expected.binding_id
            || next == maximum_integer || !integer(event["sequence"], next+1, next+1)
            || !field(event, "kind") || !event["payload"].IsObject() || encode(event).size() > limits.max_event_bytes)
            return fail(ErrorCode::IoError, "qmt_trade_event_invalid");
        const auto kind = text(event["kind"]);
        const auto& payload = event["payload"];
        if (kind == "order" || kind == "deal")
        {
            if (!field(payload, "m_strAccountID", 63) || text(payload["m_strAccountID"]) != expected.account.account_id)
                return fail(ErrorCode::IoError, "qmt_trade_event_account_invalid");
        }
        else if (kind == "error")
        {
            if (!keys(payload, {"order_args", "err_msg"}) || !field(payload["order_args"], "accountID", 63)
                || text(payload["order_args"]["accountID"]) != expected.account.account_id || !payload["err_msg"].IsString())
                return fail(ErrorCode::IoError, "qmt_trade_event_account_invalid");
        }
        else return fail(ErrorCode::IoError, "qmt_trade_event_kind_invalid");
        ++next;
    }
    if (next > receipt["durable_through"].GetUint64()
        || (value["events"].Empty() && request.after_seq < receipt["durable_through"].GetUint64()))
        return fail(ErrorCode::IoError, "qmt_trade_event_frontier_invalid");
    candidate.next_sequence = next; candidate.event_count = value["events"].Size();
    candidate.durable_through = receipt["durable_through"].GetUint64();
    candidate.source_ack_through = receipt["source_ack_through"].GetUint64();
    candidate.gap = !receipt["gap"].IsNull();
    return deadline.remaining() ? Status{} : fail(ErrorCode::Timeout, "qmt_trade_event_deadline");
}

// 发布阶段不分配；交换后局部candidate负责回收out此前的DOM。
// 锁定RapidJSON的Document/Value/Stack::Swap仅交换值、指针及ParseResult，
// 不分配也不调用用户代码。旧版在MSVC未声明noexcept，本地封装仍据该算法保证不抛出；
// 仅在库自身声明noexcept的平台额外检查声明，不能用声明缺失推断存在分配。
void publish_event_page(QmtValidatedTradeEventPage& out, QmtValidatedTradeEventPage& candidate) noexcept
{
#if RAPIDJSON_HAS_CXX11_NOEXCEPT
    static_assert(noexcept(std::declval<Document&>().Swap(std::declval<Document&>())),
        "event page swap must remain declared non-throwing");
#endif
    out.source_binding.Swap(candidate.source_binding);
    out.document.Swap(candidate.document);
    out.next_sequence = candidate.next_sequence; out.event_count = candidate.event_count;
    out.durable_through = candidate.durable_through; out.source_ack_through = candidate.source_ack_through;
    out.gap = candidate.gap;
}
}

Status validate_qmt_trade_event_page(
    const std::string& page_json,
    const QmtTradeEventSource& source,
    const QmtTradeEventRequestBounds& original_request,
    const QmtExpectedTrade& expected,
    const QmtTradeReadDescriptor& admitted_limits,
    std::size_t admitted_event_page_capacity,
    SignedHttpDeadline& original_deadline,
    QmtValidatedTradeEventPage& out)
{
    QmtValidatedTradeEventPage candidate;
    const auto admitted = event_request(source, original_request, expected, admitted_limits,
        admitted_event_page_capacity, candidate.source_binding);
    if (!admitted.ok()) return admitted;
    const auto checked = event_body(page_json, source, original_request, expected, admitted_limits,
        original_deadline, candidate);
    if (!checked.ok()) return checked;
    publish_event_page(out, candidate);
    return {};
}

bool valid_qmt_sdk_order_token(const std::string& value)
{
    // 先限原字节，避免为超额输入编码分配；实际字符规则由原safe_text统一负责。
    return !value.empty()&&value.size()<=64&&safe_text(value,64,true,false);
}

class QmtTradeClientCore
{
public:
    BoundedSignedHttp http;
    const QmtExpectedTrade expected;
    const std::size_t response_capacity;
    const std::thread::id owner_thread = std::this_thread::get_id();
    std::shared_ptr<const std::string> owner;
    QmtTradeReadDescriptor limits;
    std::string pin, profile, source_session;
    std::size_t read_result_capacity = 0, request_capacity = 0, event_page_capacity = 0;
    bool ready = false, accepting = false, accepting_cancel = false;
    bool unknown_fenced = false, faulted = false, closed = false, versions_pinned = false;
    const char* fault_reason = nullptr; // fault调用点均传本翻译单元固定字符串，保留首个硬错。
    StatusVersion host_version = StatusVersion::V1, source_version = StatusVersion::V1;

    Status fault(ErrorCode code, const char* reason)
    { if(!faulted)fault_reason=reason;faulted = true; accepting = accepting_cancel = false; return fail(code, reason); }
    bool admitted(TradeOperation operation) const
    { return !faulted && !closed && (operation == TradeOperation::Insert ? accepting : accepting_cancel); }

    QmtTradeClientCore(QmtHttpConfig config, QmtExpectedTrade fixed)
        : http(config), expected(std::move(fixed)), response_capacity(config.max_response_bytes)
    {
        Document hash;
        hash.SetString(expected.binding_sha256.data(), static_cast<rapidjson::SizeType>(expected.binding_sha256.size()), hash.GetAllocator());
        if (!safe_text(expected.account.account_id, 63) || expected.account.environment != QmtAccountEnvironment::Live
            || !safe_text(expected.binding_id, 128, true) || !hex(hash, 64))
            throw std::invalid_argument("qmt_trade_configuration_invalid");
        const auto id = signed_http_uuid();
        if (id.empty()) throw std::runtime_error("qmt_trade_identity_unavailable");
        owner = std::make_shared<const std::string>(id);
    }
    Status check(SignedHttpDeadline& deadline) const
    {
        if (std::this_thread::get_id() != owner_thread) return fail(ErrorCode::Conflict, "qmt_trade_owner_required");
        const auto checked = http.check();
        if (!checked.ok()) return checked;
        return deadline.remaining() ? Status{} : fail(ErrorCode::Timeout, "qmt_trade_deadline");
    }
    Status event_gate(SignedHttpDeadline& deadline, QmtTradeEventReadFailure* failure,
        const QmtAccountControl* control, QmtTradeEventReadStage stage) const
    {
        if (failure) {
            // 新一跳尚未交换，清前一跳HTTP envelope；Publish保留刚完成的真实回复。
            if (failure->stage != stage && stage != QmtTradeEventReadStage::Publish) {
                *failure = {}; failure->outcome = QmtTradeEventReadOutcome::Failure;
            }
            failure->stage = stage;
        }
        const auto checked = check(deadline);
        if (!checked.ok()) {
            if (failure) {
                event_local_failure(failure);
                if (checked.code == ErrorCode::Timeout) failure->transport.origin = SignedHttpFailureOrigin::Deadline;
            }
            return checked;
        }
        // 同原子停止值的一次读取是下一阶段准入点；已准入exchange保有原D。
        if (control && control->stop_requested()) {
            if (failure) {
                *failure = {}; failure->stage = stage;
                failure->outcome = QmtTradeEventReadOutcome::ControlStoppedBeforeStage;
            }
            return fail(ErrorCode::Unavailable, "qmt_trade_event_read_stopped");
        }
        return {};
    }
    Status refresh(SignedHttpDeadline& deadline, QmtTradeEventReadFailure* failure = nullptr,
        const QmtAccountControl* control = nullptr)
    {
        const auto checked = event_gate(deadline, failure, control, QmtTradeEventReadStage::Status); if (!checked.ok()) return checked;
        accepting = accepting_cancel = false;
        auto reply = http.exchange("GET", "/internal/v1/trade-status", "", deadline, metadata_capacity);
        event_reply_failure(failure, reply);
        if (!reply.status.ok()) return reply.status;
        if (reply.code != 200) return signed_http_error(reply.code);
        Document value;
        if (!reply.response_complete || !parse(reply.body, value, metadata_capacity) || !field(value, "schema_version"))
            return fault(ErrorCode::StaleSession, "qmt_trade_status_invalid");
        const auto schema = text(value["schema_version"]);
        const bool v2 = schema == "qmt.trade-host-status.v2";
        if ((!v2 && schema != "qmt.trade-host-status.v1")
            || !(v2 ? keys(value, {"schema_version", "binding", "binding_sha256", "read_profile_body_b64", "read_profile_body_sha256",
                "source_status", "writes_enabled", "accepting_commands", "closing", "failure", "limits",
                "unknown_fenced", "hard_fault", "cancel_admission"})
            : keys(value, {"schema_version", "binding", "binding_sha256", "read_profile_body_b64", "read_profile_body_sha256",
                "source_status", "writes_enabled", "accepting_commands", "closing", "failure", "limits"}))
            || !binding(value["binding"], nullptr, "2.0") || encode(value["binding"]) != pin
            || !hex(value["binding_sha256"], 64) || signed_http_sha256(pin) != text(value["binding_sha256"])
            || !hex(value["read_profile_body_sha256"], 64) || signed_http_sha256(profile) != text(value["read_profile_body_sha256"])
            || !value["writes_enabled"].IsBool() || !value["accepting_commands"].IsBool() || !value["closing"].IsBool()
            || (!value["failure"].IsNull() && !safe_text(value["failure"], 128, true))
            || (v2 && (!value["unknown_fenced"].IsBool() || !value["cancel_admission"].IsBool() || !hard_fault(value["hard_fault"]))))
            return fault(ErrorCode::StaleSession, "qmt_trade_status_invalid");
        std::string original_profile;
        StatusVersion observed_source = StatusVersion::V1;
        if (!unbase64(value["read_profile_body_b64"], profile_capacity, original_profile) || original_profile != profile
            || !source_status(value["source_status"], expected, limits, value["writes_enabled"].GetBool(), observed_source))
            return fault(ErrorCode::StaleSession, "qmt_trade_source_invalid");
        const auto observed_host = v2 ? StatusVersion::V2 : StatusVersion::V1;
        if (!v2 && observed_source == StatusVersion::V2)
            return fault(ErrorCode::StaleSession, "qmt_trade_source_invalid");
        // 两个状态版本各自冻结；相同B/session不能把新旧接口语义互换。
        if (versions_pinned && (host_version != observed_host || source_version != observed_source))
            return fault(ErrorCode::StaleSession, "qmt_trade_version_changed");
        const auto& public_limits = value["limits"];
        if (!keys(public_limits, {"max_command_bytes", "max_call_result_bytes", "max_command_ttl_ms", "max_event_page_bytes", "max_events", "max_http_trade_response_bytes"})
            || !integer(public_limits["max_command_bytes"], limits.max_command_bytes, limits.max_command_bytes)
            || !integer(public_limits["max_call_result_bytes"], limits.max_call_result_bytes, limits.max_call_result_bytes)
            || !integer(public_limits["max_command_ttl_ms"], limits.max_command_ttl_ms, limits.max_command_ttl_ms)
            || !integer(public_limits["max_events"], limits.max_events, limits.max_events)
            || !integer(public_limits["max_event_page_bytes"], limits.max_event_bytes+1024, limits.max_event_page_bytes)
            || !integer(public_limits["max_http_trade_response_bytes"], record_capacity(limits), record_capacity(limits))
            || record_capacity(limits) > response_capacity || public_limits["max_event_page_bytes"].GetUint64() > response_capacity)
            return fault(ErrorCode::InvalidInput, "qmt_trade_capacity_invalid");
        const auto& source = value["source_status"];
        const auto session = text(source["session_id"]);
        if (!source_session.empty() && source_session != session)
            return fault(ErrorCode::StaleSession, "qmt_trade_source_changed");
        const bool source_v2 = observed_source == StatusVersion::V2;
        const bool source_unknown = source_v2 && source["unknown_fenced"].GetBool();
        const bool source_hard = source_v2 && !source["hard_fault"].IsNull();
        const bool host_unknown = v2 && value["unknown_fenced"].GetBool();
        const bool host_hard = v2 && !value["hard_fault"].IsNull();
        const bool can_write = value["accepting_commands"].GetBool();
        const bool can_cancel = v2 ? value["cancel_admission"].GetBool() : can_write;
        const bool base = value["writes_enabled"].GetBool() && !value["closing"].GetBool()
            && !source["closing"].GetBool() && !source["events"]["closed"].GetBool()
            && source["gap"].IsNull() && !host_hard && !source_hard;
        if ((can_write && (!base || !value["failure"].IsNull() || !source["write_admission"].GetBool()
                || host_unknown || source_unknown))
            || (v2 && source_unknown && !host_unknown)
            || (can_cancel && (!base || (v2 && source_v2 ? !source["cancel_admission"].GetBool()
                : !can_write || !source["write_admission"].GetBool() || !value["failure"].IsNull())))
            || (v2 && !source_v2 && can_cancel != can_write))
            return fault(ErrorCode::IoError, "qmt_trade_readiness_invalid");
        if (!deadline.remaining()) return fail(ErrorCode::Timeout, "qmt_trade_deadline");
        // 原owner内锁存通信事实；没有跨线程共享，因此不新增互斥锁。
        // unknown只关insert；真实gap/硬错独立锁存，后续refresh不能洗掉。
        unknown_fenced = unknown_fenced || host_unknown || source_unknown;
        faulted = faulted || host_hard || source_hard || !source["gap"].IsNull();
        closed = closed || value["closing"].GetBool() || source["closing"].GetBool() || source["events"]["closed"].GetBool();
        source_session = session;
        host_version = observed_host; source_version = observed_source; versions_pinned = true;
        event_page_capacity = static_cast<std::size_t>(public_limits["max_event_page_bytes"].GetUint64());
        accepting = expected.writes_enabled && can_write && !unknown_fenced && !faulted && !closed;
        accepting_cancel = expected.writes_enabled && can_cancel && !faulted && !closed
            && (!unknown_fenced || (v2 && source_v2));
        return {};
    }
    Status prepare(SignedHttpDeadline& deadline, QmtTradeEventReadFailure* failure = nullptr,
        const QmtAccountControl* control = nullptr)
    {
        const auto checked = event_gate(deadline, failure, control, QmtTradeEventReadStage::Binding); if (!checked.ok()) return checked;
        accepting = accepting_cancel = false;
        auto reply = http.read_binding(deadline,metadata_capacity,[&]{
            return event_gate(deadline,failure,control,QmtTradeEventReadStage::Binding);
        });
        event_reply_failure(failure, reply);
        if (!reply.status.ok()) return reply.status;
        if (reply.code != 200) return signed_http_error(reply.code);
        Document value;
        if (!parse(reply.body, value, metadata_capacity)
            || !keys(value, {"schema_version", "binding", "binding_sha256", "read_profile_body_b64", "read_profile_body_sha256", "limits", "order_ready"})
            || !field(value, "schema_version") || text(value["schema_version"]) != "qmt.bound-read.v1"
            || !binding(value["binding"], nullptr, "2.0") || !hex(value["binding_sha256"], 64)
            || !hex(value["read_profile_body_sha256"], 64) || !value["order_ready"].IsBool() || value["order_ready"].GetBool())
            return fail(ErrorCode::IoError, "qmt_trade_binding_invalid");
        const auto observed = encode(value["binding"]);
        std::string raw;
        if ((!pin.empty() && pin != observed) || signed_http_sha256(observed) != text(value["binding_sha256"])
            || !unbase64(value["read_profile_body_b64"], profile_capacity, raw)
            || signed_http_sha256(raw) != text(value["read_profile_body_sha256"])
            || text(value["read_profile_body_sha256"]) != text(value["binding"]["capability_sha256"]))
            return fail(ErrorCode::StaleSession, "qmt_trade_binding_changed");
        const auto& read_limits = value["limits"];
        const bool http_retention=read_limits.IsObject()&&read_limits.HasMember("http_read_retention");
        std::uint32_t http_lifetime=0;
        if (!(http_retention?keys(read_limits,{"max_request_bytes","max_result_bytes","max_http_request_bytes","max_http_response_bytes","http_read_retention"})
                :keys(read_limits,{"max_request_bytes","max_result_bytes","max_http_request_bytes","max_http_response_bytes"}))
            ||(http_retention&&!read_retention_capability(read_limits["http_read_retention"],http_lifetime))
            || !integer(read_limits["max_result_bytes"], 8192, result_capacity)
            || !integer(read_limits["max_request_bytes"], 1, command_capacity)
            || !integer(read_limits["max_http_request_bytes"], 8192, 4194304)
            || !integer(read_limits["max_http_response_bytes"], 1, 4*((result_capacity+2)/3)+metadata_capacity))
            return fail(ErrorCode::IoError, "qmt_trade_read_capacity_invalid");
        QmtTradeReadDescriptor descriptor;
        auto admitted = validate_qmt_trade_read_profile(raw, static_cast<std::size_t>(read_limits["max_result_bytes"].GetUint64()), expected.account, descriptor);
        if (!admitted.ok() || descriptor.binding_sha256 != expected.binding_sha256)
            return fail(ErrorCode::InvalidInput, "qmt_trade_profile_invalid");
        if (!deadline.remaining()) return fail(ErrorCode::Timeout, "qmt_trade_deadline");
        pin = observed; profile = std::move(raw); limits = std::move(descriptor);
        read_result_capacity = static_cast<std::size_t>(read_limits["max_result_bytes"].GetUint64());
        request_capacity = static_cast<std::size_t>(read_limits["max_http_request_bytes"].GetUint64());
        const auto status = refresh(deadline, failure, control);
        ready = status.ok();
        return status;
    }
    bool receipt(const QmtTradeReceipt& receipt, QmtTradeReadDescriptor& descriptor) const
    {
        Document original, source;
        if (!parse(receipt.binding_json, source, 4096) || !binding(source, nullptr, "2.0")
            || encode(source) != receipt.binding_json || receipt.read_result_capacity < 8192 || receipt.read_result_capacity > result_capacity
            || !validate_qmt_trade_read_profile(receipt.read_profile_body, receipt.read_result_capacity, expected.account, descriptor).ok()
            || descriptor.binding_sha256 != expected.binding_sha256
            || signed_http_sha256(receipt.read_profile_body) != text(source["capability_sha256"])
            || !parse(receipt.command_body, original, static_cast<std::size_t>(descriptor.max_command_bytes))
            || !command(original, expected) || encode(original) != receipt.command_body) return false;
        return record_capacity(descriptor) <= response_capacity;
    }
    QmtTradePreparation prepared(Document& value, SignedHttpDeadline& deadline)
    {
        QmtTradePreparation out;
        const auto raw = encode(value);
        if (!command(value, expected) || raw.size() > limits.max_command_bytes)
        { out.status = fail(ErrorCode::InvalidInput, "qmt_trade_command_invalid"); return out; }
        // 先读共享计数，再取steady剩余并向下取整；构造/排队耗时不会授新TTL。
        const auto now = uptime();
        const auto remaining = std::chrono::duration_cast<std::chrono::milliseconds>(deadline.end-std::chrono::steady_clock::now()).count();
        if (remaining <= 0 || now > (1ULL<<32)*1000)
        { out.status = fail(ErrorCode::Timeout, "qmt_trade_deadline"); return out; }
        const auto ttl = std::min(static_cast<std::uint64_t>(remaining), limits.max_command_ttl_ms);
        if (!ttl || now > (1ULL<<32)*1000-ttl)
        { out.status = fail(ErrorCode::InvalidInput, "qmt_trade_clock_invalid"); return out; }
        auto token = std::unique_ptr<QmtPreparedTrade>(new QmtPreparedTrade);
        token->receipt_ = {pin, raw, profile, read_result_capacity};
        token->owner_ = owner; token->deadline_ = deadline.end; token->business_deadline_ms_ = now+ttl;
        if (!deadline.remaining()) { out.status = fail(ErrorCode::Timeout, "qmt_trade_deadline"); return out; }
        out.request = std::move(token);
        return out;
    }
    void common(Document& value, const char* operation, const std::string& entrust, const std::string& tag)
    {
        value.SetObject();
        add(value, "schema_version", "qmt.trade-command.v1"); add(value, "command_id", signed_http_uuid());
        add(value, "operation", operation); add(value, "binding_id", expected.binding_id);
        add(value, "account_id", expected.account.account_id); add(value, "account_type", "stock");
        add(value, "entrust_id", entrust); add(value, "user_tag", tag);
    }
    QmtTradePreparation insert(const QmtTradeInsert& fields, SignedHttpDeadline& deadline)
    {
        QmtTradePreparation out;
        auto status = check(deadline);
        if (status.ok() && ready) status = refresh(deadline);
        else if (status.ok()) status = fail(ErrorCode::Unavailable, "qmt_trade_not_prepared");
        if (!status.ok() || !admitted(TradeOperation::Insert)) { out.status = status.ok() ? fail(ErrorCode::Unavailable, "qmt_trade_writes_disabled") : status; return out; }
        if ((fields.exchange != "SSE" && fields.exchange != "SZSE") || fields.code.size() != 6
            || !std::all_of(fields.code.begin(), fields.code.end(), [](char c){ return c >= '0' && c <= '9'; }))
        { out.status = fail(ErrorCode::InvalidInput, "qmt_trade_symbol_invalid"); return out; }
        Document value;
        common(value, "order.insert", fields.entrust_id, fields.user_tag);
        add(value, "symbol", fields.code+(fields.exchange == "SSE" ? ".SH" : ".SZ"));
        add(value, "side", fields.buy ? "buy" : "sell"); add(value, "order_type", "limit");
        add(value, "limit_price", fields.limit_price); value.AddMember("quantity", fields.quantity, value.GetAllocator());
        const auto token = signed_http_uuid();
        if (token.empty()) { out.status = fail(ErrorCode::IoError, "qmt_trade_identity_unavailable"); return out; }
        add(value, "sdk_user_order_id", "wt."+token);
        return prepared(value, deadline);
    }
    QmtTradePreparation cancel(const QmtTradeOrderReference& reference, SignedHttpDeadline& deadline)
    {
        QmtTradePreparation out;
        auto status = check(deadline);
        if (status.ok() && ready) status = refresh(deadline);
        else if (status.ok()) status = fail(ErrorCode::Unavailable, "qmt_trade_not_prepared");
        if (!status.ok() || !admitted(TradeOperation::Cancel)) { out.status = status.ok() ? fail(ErrorCode::Unavailable, "qmt_trade_writes_disabled") : status; return out; }
        QmtTradeReadDescriptor original_limits;
        Document original;
        if (reference.owner_ != owner || !reference.association_error_.empty() || !safe_text(reference.broker_order_id_, 63, true)
            || !((reference.source_.binding_json == pin && reference.source_.session_id == source_session)
                 || (!reference.query_binding_json_.empty() && reference.query_binding_json_ == pin))
            || !receipt(reference.insert_, original_limits) || !parse(reference.insert_.command_body, original, command_capacity)
            || text(original["operation"]) != "order.insert")
        { out.status = fail(ErrorCode::Unavailable, "qmt_trade_cancel_reference_unavailable"); return out; }
        Document value;
        common(value, "order.cancel", text(original["entrust_id"]), text(original["user_tag"]));
        add(value, "original_command_id", text(original["command_id"])); add(value, "broker_order_id", reference.broker_order_id_);
        return prepared(value, deadline);
    }
    void observed(const SignedHttpResult& reply, const QmtTradeReceipt& receipt_value, const QmtTradeReadDescriptor& descriptor,
                  SignedHttpDeadline& deadline, QmtTradeResult& out, bool submission = false)
    {
        out.http_status = reply.code;
        // 只有POST的完整标准业务409证明本次未登记；GET/截断/末D不能借此退役。
        const auto conflict = signed_http_error(409);
        if (submission && reply.code == 409 && reply.response_complete
            && reply.status.code == conflict.code && reply.status.reason == conflict.reason && deadline.remaining())
        {
            Document error, original;
            if (parse(reply.body, error, metadata_capacity) && keys(error, {"error_code", "error_message"})
                && field(error, "error_code") && text(error["error_code"]) == "cancel_pending"
                && safe_text(error["error_message"], metadata_capacity)
                && parse(receipt_value.command_body, original, static_cast<std::size_t>(descriptor.max_command_bytes))
                && text(original["operation"]) == "order.cancel")
            {
                auto pending = fail(ErrorCode::Conflict, "qmt_trade_cancel_pending");
                if (!deadline.remaining()) { out.status = fail(ErrorCode::Timeout, "qmt_trade_deadline"); return; }
                out.status = std::move(pending); out.phase = QmtTradePhase::Unknown; out.original_record = false;
                return;
            }
        }
        if (!reply.response_complete || (reply.code != 200 && reply.code != 202))
        {
            out.status = reply.status.ok() ? signed_http_error(reply.code) : reply.status;
            accepting = accepting_cancel = false; return;
        }
        Document value;
        QmtTradePhase stage;
        std::string native;
        if (!parse(reply.body, value, record_capacity(descriptor)) || !record(value, receipt_value, expected, descriptor, stage, native)
            || ((stage == QmtTradePhase::Queued || stage == QmtTradePhase::Dispatching) ? reply.code != 202 : reply.code != 200))
        { out.status = fault(ErrorCode::IoError, "qmt_trade_record_invalid"); return; }
        auto original = reply.body;
        // 所有分配/校验完成才发布原事实；不能因晚返回把已知SDK事实伪造为拒单。
        out.record_json = std::move(original); out.source_result_json = std::move(native);
        out.phase = stage; out.original_record = true;
        out.status = !reply.status.ok() ? reply.status :
            (deadline.remaining() ? Status{} : fail(ErrorCode::Timeout, "qmt_trade_deadline"));
        if (stage == QmtTradePhase::Unknown) unknown_fenced = true;
        if (stage == QmtTradePhase::Unknown || !out.status.ok()) accepting = accepting_cancel = false;
    }
    QmtTradeResult submit(std::unique_ptr<QmtPreparedTrade> token, SignedHttpDeadline& supplied)
    {
        QmtTradeResult out;
        out.status = fail(ErrorCode::InvalidInput, "qmt_trade_prepared_required");
        if (!token) return out;
        out.receipt = token->receipt_;
        SignedHttpDeadline deadline(std::min(supplied.end, token->deadline_));
        auto status = check(deadline);
        QmtTradeReadDescriptor descriptor;
        if (!status.ok() || token->owner_ != owner || !ready || token->receipt_.binding_json != pin || !receipt(token->receipt_, descriptor))
        { if (!status.ok()) out.status = status; return out; }
        Document operation;
        if (!parse(token->receipt_.command_body, operation, static_cast<std::size_t>(descriptor.max_command_bytes))) return out;
        const auto kind = text(operation["operation"]) == "order.insert" ? TradeOperation::Insert : TradeOperation::Cancel;
        status = refresh(deadline);
        if (!status.ok() || !admitted(kind) || uptime() >= token->business_deadline_ms_)
        { out.status = status.ok() ? fail(ErrorCode::Timeout, "qmt_trade_not_sent") : status; return out; }
        Document body; body.SetObject();
        add(body, "schema_version", "qmt.trade-submit.v1"); add(body, "binding_sha256", signed_http_sha256(pin));
        add(body, "command_body_b64", base64(token->receipt_.command_body));
        add(body, "command_body_sha256", signed_http_sha256(token->receipt_.command_body));
        add(body, "clock_schema", "qmt.win-uptime-ms.v1"); body.AddMember("deadline_ms", token->business_deadline_ms_, body.GetAllocator());
        const auto wire = encode(body);
        if (wire.size() > request_capacity)
        { out.status = fail(ErrorCode::Backpressure, "qmt_trade_request_capacity"); return out; }
        if (!deadline.remaining() || uptime() >= token->business_deadline_ms_)
        { out.status = fail(ErrorCode::Timeout, "qmt_trade_not_sent"); return out; }
        // POST前先完整保有原receipt及Unknown返回值；后续异常不丢原身份，不再POST。
        out.status = fail(ErrorCode::SubmissionUnknown, "qmt_trade_delivery_unknown"); out.phase = QmtTradePhase::Unknown;
        try
        {
            auto reply = http.exchange("POST", "/internal/v1/trade-commands", wire, deadline, record_capacity(descriptor));
            if (!reply.send_attempted)
            {
                out.phase = QmtTradePhase::NotSent; out.http_status = reply.code;
                out.status = reply.status.ok() ? fail(ErrorCode::IoError, "qmt_trade_not_sent") : reply.status;
                return out;
            }
#if defined(_WIN32) && defined(GH_QMT_HTTP_DRAIN_TESTING)
            if (trade_after_exchange_fault.exchange(false)) throw std::bad_alloc();
#endif
            observed(reply, out.receipt, descriptor, deadline, out, true);
            if (!out.original_record && out.phase == QmtTradePhase::Unknown
                && out.status.reason != "qmt_trade_cancel_pending") { unknown_fenced = true; accepting = false; }
        }
        catch (...) { unknown_fenced = true; accepting = accepting_cancel = false; }
        return out;
    }
    // 输入已在out中完整持有；首次私有resume复用同一输出，避免多一份receipt并存。
    void resume_record(QmtTradeResult& out, SignedHttpDeadline& deadline)
    {
        out.phase = QmtTradePhase::Unknown;
        out.status = fail(ErrorCode::InvalidInput, "qmt_trade_receipt_invalid");
        QmtTradeReadDescriptor descriptor;
        const auto status = check(deadline);
        if (!status.ok()) { out.status = status; return; }
        if (!receipt(out.receipt, descriptor)) return;
        Document original; if (!parse(out.receipt.command_body, original, command_capacity)) return;
        const auto target = "/internal/v1/trade-commands/"+text(original["command_id"]);
        out.status = fail(ErrorCode::SubmissionUnknown, "qmt_trade_delivery_unknown");
        try
        {
            auto reply = http.exchange("GET", target, "", deadline, record_capacity(descriptor));
            observed(reply, out.receipt, descriptor, deadline, out);
        }
        catch (...) { accepting = accepting_cancel = false; }
    }
    QmtTradeResult resume(const QmtTradeReceipt& value, SignedHttpDeadline& deadline)
    {
        QmtTradeResult out;
        out.phase = QmtTradePhase::Unknown;
        out.receipt = value;
        // 公开receipt重新准入后仅GET；读失败无法证明原调用未发送。
        resume_record(out, deadline);
        return out;
    }
    QmtTradeResult resume_cancel(const QmtTradeCancelReference& actual, SignedHttpDeadline& deadline)
    {
        QmtTradeResult out;
        out.phase = QmtTradePhase::Unknown;
        out.receipt = actual.receipt_;
        out.status = fail(ErrorCode::InvalidInput, "qmt_trade_cancel_reference_unavailable");
        const auto checked = check(deadline);
        if (!checked.ok()) { out.status = checked; return out; }
        // owner身份只由Core签发；不可从可变公开receipt恢复成句柄或POST token。
        if (actual.owner_ != owner) return out;
        {
            QmtTradeReadDescriptor descriptor;
            Document original, reference;
            QmtTradePhase stage; std::string native;
            if (!receipt(out.receipt, descriptor) || !parse(out.receipt.command_body, original, command_capacity)
                || text(original["operation"]) != "order.cancel"
                || text(original["original_command_id"]) != actual.original_command_id_
                || !parse(actual.record_json_, reference, record_capacity(descriptor))
                || !record(reference, out.receipt, expected, descriptor, stage, native) || stage != actual.phase_)
                return out;
            Document digest; digest.SetString(actual.original_command_sha256_.data(),
                static_cast<rapidjson::SizeType>(actual.original_command_sha256_.size()), digest.GetAllocator());
            if (!hex(digest, 64)) return out;
        } // 私有record/解码scratch在GET前析构，原输出receipt继续持有。
        resume_record(out, deadline);
        return out;
    }
    QmtTradeCancelLookupResult lookup_cancel(const QmtTradeOrderReference& original, SignedHttpDeadline& deadline)
    {
        QmtTradeCancelLookupResult out;
        out.status = check(deadline);
        if (!out.status.ok()) return out;
        if (!versions_pinned || host_version != StatusVersion::V2 || profile.empty())
        { out.status = fail(ErrorCode::NotSupported, "qmt_trade_cancel_lookup_unavailable"); return out; }
        QmtTradeReadDescriptor descriptor;
        Document insert;
        if (original.owner_ != owner || !receipt(original.insert_, descriptor)
            || !parse(original.insert_.command_body, insert, command_capacity) || text(insert["operation"]) != "order.insert")
        { out.status = fail(ErrorCode::InvalidInput, "qmt_trade_cancel_reference_unavailable"); return out; }
        const auto id = text(insert["command_id"]), sha = signed_http_sha256(original.insert_.command_body);
        if (sha.empty()) { out.status = fail(ErrorCode::IoError, "qmt_trade_identity_unavailable"); return out; }
        Document body; body.SetObject();
        add(body, "schema_version", "qmt.trade-cancel-lookup.v1");
        add(body, "original_command_id", id); add(body, "original_command_sha256", sha);
        const auto wire = encode(body);
        if (wire.size() > request_capacity)
        { out.status = fail(ErrorCode::Backpressure, "qmt_trade_request_capacity"); return out; }
        // 这是只读POST；沿原HTTP owner/cap/D。历史B不与当前写准入合并。
        auto reply = http.exchange("POST", "/internal/v1/trade-cancel-lookup", wire, deadline,
            record_capacity(descriptor)+metadata_capacity);
        out.http_status = reply.code; out.response_complete = reply.response_complete;
        out.response_body = std::move(reply.body);
        out.status = reply.status.ok() ? signed_http_error(reply.code) : reply.status;
        if (!reply.response_complete || !reply.status.ok() || reply.code != 200) return out;
        if (!deadline.remaining()) { out.status = fail(ErrorCode::Timeout, "qmt_trade_deadline"); return out; }
        Document value;
        if (!parse(out.response_body, value, record_capacity(descriptor)+metadata_capacity)
            || !keys(value, {"schema_version", "original_command_id", "original_command_sha256", "cancel"})
            || !field(value, "schema_version") || text(value["schema_version"]) != "qmt.trade-cancel-reference.v1"
            || !uuid(value["original_command_id"]) || text(value["original_command_id"]) != id
            || !hex(value["original_command_sha256"], 64) || text(value["original_command_sha256"]) != sha)
        { out.status = fault(ErrorCode::IoError, "qmt_trade_cancel_reference_invalid"); return out; }
        if (value["cancel"].IsNull())
        {
            if (!deadline.remaining()) { out.status = fail(ErrorCode::Timeout, "qmt_trade_deadline"); return out; }
            out.no_cancel = true; out.status = {}; return out;
        }
        const auto& actual = value["cancel"];
        std::string raw;
        if (!actual.IsObject() || !actual.HasMember("command_body_b64") || !actual.HasMember("admitted_binding")
            || !unbase64(actual["command_body_b64"], static_cast<std::size_t>(descriptor.max_command_bytes), raw))
        { out.status = fault(ErrorCode::IoError, "qmt_trade_cancel_reference_invalid"); return out; }
        QmtTradeReceipt restored{encode(actual["admitted_binding"]), std::move(raw),
            original.insert_.read_profile_body, original.insert_.read_result_capacity};
        QmtTradePhase stage; std::string native; Document cancel;
        if (!receipt(restored, descriptor) || !record(actual, restored, expected, descriptor, stage, native)
            || !parse(restored.command_body, cancel, command_capacity) || text(cancel["operation"]) != "order.cancel"
            || text(cancel["original_command_id"]) != id
            || (!original.broker_order_id_.empty() && text(cancel["broker_order_id"]) != original.broker_order_id_))
        { out.status = fault(ErrorCode::Conflict, "qmt_trade_cancel_reference_invalid"); return out; }
        for (const auto key : {"account_id", "account_type", "binding_id", "entrust_id", "user_tag"})
            if (text(cancel[key]) != text(insert[key]))
            { out.status = fault(ErrorCode::Conflict, "qmt_trade_cancel_reference_invalid"); return out; }
        auto reference = std::unique_ptr<QmtTradeCancelReference>(new QmtTradeCancelReference);
        reference->owner_ = owner; reference->receipt_ = std::move(restored); reference->phase_ = stage;
#if defined(_WIN32) && defined(GH_QMT_HTTP_DRAIN_TESTING)
        if (cancel_publish_fault.exchange(false)) throw std::bad_alloc();
#endif
        reference->record_json_ = encode(actual); reference->original_command_id_ = id;
        reference->original_command_sha256_ = sha;
        if (reference->record_json_.size() > (std::min)(response_capacity, record_capacity(descriptor)))
        { out.status = fail(ErrorCode::Backpressure, "qmt_trade_cancel_reference_capacity"); return out; }
        // phase/receipt/record和目标摘要均完整后才发布；失败只销毁局部句柄。
        if (!deadline.remaining()) { out.status = fail(ErrorCode::Timeout, "qmt_trade_deadline"); return out; }
        out.reference = std::move(reference); out.status = {};
        return out;
    }
    QmtTradeLookupResult lookup(const QmtTradeLookup& query, SignedHttpDeadline& deadline)
    {
        QmtTradeLookupResult out;
        out.status = check(deadline);
        if (!out.status.ok()) return out;
        if (profile.empty()) { out.status = fail(ErrorCode::Unavailable, "qmt_trade_not_prepared"); return out; }
        Document body; body.SetObject();
        add(body, "schema_version", "qmt.trade-order-lookup.v1");
        Value identity(rapidjson::kObjectType);
        auto& allocator = body.GetAllocator();
        auto item = [&](const char* key, const std::string& value) { identity.AddMember(Value(key, allocator), Value(value.data(), static_cast<rapidjson::SizeType>(value.size()), allocator), allocator); };
        if (query.kind == QmtTradeLookupKind::WtIdentity && safe_text(query.entrust_id, 63) && safe_text(query.user_tag, 63) && query.sdk_user_order_id.empty())
        { item("entrust_id", query.entrust_id); item("user_tag", query.user_tag); }
        else if (query.kind == QmtTradeLookupKind::SdkToken && valid_qmt_sdk_order_token(query.sdk_user_order_id) && query.entrust_id.empty() && query.user_tag.empty())
            item("sdk_user_order_id", query.sdk_user_order_id);
        else { out.status = fail(ErrorCode::InvalidInput, "qmt_trade_lookup_invalid"); return out; }
        body.AddMember("identity", identity, allocator);
        auto reply = http.exchange("POST", "/internal/v1/trade-order-lookup", encode(body), deadline, record_capacity(limits)+metadata_capacity);
        out.http_status = reply.code;
        out.response_complete = reply.response_complete;
        out.response_body = std::move(reply.body);
        out.status = reply.status.ok() ? signed_http_error(reply.code) : reply.status;
        // 完整EOF的404/409带HTTP业务Status；只准入本状态码精确对应的错误，保留运输失败。
        const auto business_status=signed_http_error(reply.code);
        const bool business_reply=(reply.code==404||reply.code==409)
            &&reply.status.code==business_status.code&&reply.status.reason==business_status.reason;
        if (!out.response_complete || (!reply.status.ok()&&!business_reply)) return out;
        if (!deadline.remaining()) { out.status=fail(ErrorCode::Timeout,"qmt_trade_deadline"); return out; }
        if (reply.code == 404)
        {
            Document error;
            // 404只是运输状态；完整、未过D的标准unknown_order才是未登记事实。
            out.not_found = parse(out.response_body,error,record_capacity(limits)+metadata_capacity)
                &&keys(error,{"error_code","error_message"})&&field(error,"error_code")
                &&text(error["error_code"])=="unknown_order"&&error["error_message"].IsString()
                &&error["error_message"].GetStringLength()>0;
            if (!deadline.remaining()) { out.not_found=false; out.status=fail(ErrorCode::Timeout,"qmt_trade_deadline"); }
            return out;
        }
        if (reply.code != 200 && reply.code != 409) return out;
        Document value;
        if (!parse(out.response_body, value, record_capacity(limits)+metadata_capacity) || !field(value,"schema_version"))
        { out.status = fail(ErrorCode::IoError, "qmt_trade_reference_invalid"); return out; }
        const bool query_proof = text(value["schema_version"]) == "qmt.trade-order-reference.v2";
        if (!(query_proof ? keys(value,{"schema_version","insert","broker_order_id","source","source_sequence","source_event_sha256","association_error","query_observation"})
                : text(value["schema_version"]) == "qmt.trade-order-reference.v1"
                  && keys(value,{"schema_version","insert","broker_order_id","source","source_sequence","source_event_sha256","association_error"})))
        { out.status = fail(ErrorCode::IoError, "qmt_trade_reference_invalid"); return out; }
        const auto& insert = value["insert"];
        std::string raw;
        if (!insert.IsObject() || !insert.HasMember("command_body_b64") || !insert.HasMember("admitted_binding")
            || !unbase64(insert["command_body_b64"], static_cast<std::size_t>(limits.max_command_bytes), raw))
        { out.status = fail(ErrorCode::IoError, "qmt_trade_reference_invalid"); return out; }
        QmtTradeReceipt restored {encode(insert["admitted_binding"]), raw, profile, read_result_capacity};
        QmtTradePhase stage; std::string native;
        Document original;
        if (!record(insert, restored, expected, limits, stage, native) || !parse(raw, original, command_capacity)
            || text(original["operation"]) != "order.insert"
            || (query.kind == QmtTradeLookupKind::WtIdentity ? (text(original["entrust_id"]) != query.entrust_id || text(original["user_tag"]) != query.user_tag)
                : text(original["sdk_user_order_id"]) != query.sdk_user_order_id))
        { out.status = fail(ErrorCode::IoError, "qmt_trade_reference_invalid"); return out; }
        const bool linked = !value["broker_order_id"].IsNull();
        const bool event_proof = !value["source"].IsNull();
        if (linked && !safe_text(value["broker_order_id"],63,true))
        { out.status = fail(ErrorCode::IoError, "qmt_trade_reference_invalid"); return out; }
        if (event_proof)
        {
            if (!linked || !keys(value["source"], {"host_binding", "session_id"})
                || !binding(value["source"]["host_binding"], nullptr, "2.0") || !safe_text(value["source"]["session_id"], 128, true)
                || !integer(value["source_sequence"], 1) || !hex(value["source_event_sha256"], 64))
            { out.status = fail(ErrorCode::IoError, "qmt_trade_reference_invalid"); return out; }
        }
        else if (!value["source_sequence"].IsNull() || !value["source_event_sha256"].IsNull() || (linked && !query_proof))
        { out.status = fail(ErrorCode::IoError, "qmt_trade_reference_invalid"); return out; }
        if (query_proof)
        {
            const auto& observation=value["query_observation"];
            if (!keys(observation,{"request_id","result_sha256","row_index","host_binding"})
                || !uuid(observation["request_id"]) || !hex(observation["result_sha256"],64)
                || !integer(observation["row_index"],0) || observation["row_index"].GetUint64()>4095
                || !binding(observation["host_binding"],nullptr,"2.0")
                || (!linked && value["association_error"].IsNull()))
            { out.status=fail(ErrorCode::IoError,"qmt_trade_reference_invalid"); return out; }
        }
        if (!value["association_error"].IsNull())
        {
            if (!field(value, "association_error")) { out.status = fail(ErrorCode::IoError, "qmt_trade_reference_invalid"); return out; }
            const auto error = text(value["association_error"]);
            if (error != "broker_identity_conflict" && error != "broker_identity_unrepresentable" && error != "symbol_mismatch")
            { out.status = fail(ErrorCode::IoError, "qmt_trade_reference_invalid"); return out; }
        }
        const bool dispatched=!insert["dispatch_binding"].IsNull();
        if ((linked||query_proof||!value["association_error"].IsNull())&&!dispatched)
        { out.status=fail(ErrorCode::IoError,"qmt_trade_reference_invalid"); return out; }
        if ((reply.code == 409) != !value["association_error"].IsNull())
        { out.status = fail(ErrorCode::IoError, "qmt_trade_reference_invalid"); return out; }
        auto reference = std::unique_ptr<QmtTradeOrderReference>(new QmtTradeOrderReference);
        reference->owner_ = owner; reference->insert_ = std::move(restored);
        auto& facts=reference->facts_;
        facts.account_id=text(original["account_id"]);facts.account_type=text(original["account_type"]);
        facts.binding_id=text(original["binding_id"]);facts.symbol=text(original["symbol"]);
        facts.entrust_id=text(original["entrust_id"]);facts.user_tag=text(original["user_tag"]);
        facts.sdk_user_order_id=text(original["sdk_user_order_id"]);facts.dispatched=dispatched;
        facts.has_broker_proof=linked;
        if(event_proof){facts.source_sequence=value["source_sequence"].GetUint64();facts.source_event_sha256=text(value["source_event_sha256"]);}
        if (linked) reference->broker_order_id_ = text(value["broker_order_id"]);
        if (event_proof)
        {
            reference->source_ = {encode(value["source"]["host_binding"]), text(value["source"]["session_id"])};
        }
        facts.broker_proof_kind = linked ? (query_proof ? QmtTradeBrokerProofKind::AccountQuery : QmtTradeBrokerProofKind::Event) : QmtTradeBrokerProofKind::None;
        if(query_proof){const auto& observation=value["query_observation"];
            facts.query_request_id=text(observation["request_id"]);facts.query_result_sha256=text(observation["result_sha256"]);
            facts.query_row_index=observation["row_index"].GetUint64();reference->query_binding_json_=encode(observation["host_binding"]);}
        if (!value["association_error"].IsNull()) reference->association_error_ = text(value["association_error"]);
        if (!deadline.remaining()) { out.status = fail(ErrorCode::Timeout, "qmt_trade_deadline"); return out; }
        out.reference_json = out.response_body;
        if (!deadline.remaining()) { out.status=fail(ErrorCode::Timeout,"qmt_trade_deadline"); out.reference_json.clear(); return out; }
        out.reference = std::move(reference);
        out.status = value["association_error"].IsNull() ? Status{} : fail(ErrorCode::Conflict, "qmt_trade_association_conflict");
        return out;
    }
    QmtTradeEventPage events(const QmtTradeEventSource& source, std::uint64_t after, std::size_t limit,
                            std::size_t max_bytes, SignedHttpDeadline& deadline,
                            QmtTradeEventReadFailure* failure = nullptr, const QmtAccountControl* control = nullptr)
    {
        QmtTradeEventPage out; out.source = source; out.next_sequence = after;
        out.status = event_gate(deadline, failure, control, QmtTradeEventReadStage::Page); if (!out.status.ok()) return out;
        if (profile.empty())
        { out.status = fail(ErrorCode::InvalidInput, "qmt_trade_event_request_invalid"); return out; }
        const QmtTradeEventRequestBounds request{after, limit, max_bytes};
        QmtValidatedTradeEventPage validated;
        out.status = event_request(source, request, expected, limits, event_page_capacity, validated.source_binding);
        if (!out.status.ok()) return out;
        Document body; body.SetObject();
        add(body, "schema_version", "qmt.persisted-trade-events-request.v1");
        Value origin(rapidjson::kObjectType); auto& allocator = body.GetAllocator();
        origin.AddMember("host_binding", Value(validated.source_binding, allocator), allocator);
        origin.AddMember("session_id", Value(source.session_id.data(), static_cast<rapidjson::SizeType>(source.session_id.size()), allocator), allocator);
        body.AddMember("source", origin, allocator); body.AddMember("after_seq", after, allocator);
        body.AddMember("limit", static_cast<std::uint64_t>(limit), allocator); body.AddMember("max_bytes", static_cast<std::uint64_t>(max_bytes), allocator);
        const auto encoded = encode(body);
        out.status = event_gate(deadline, failure, control, QmtTradeEventReadStage::Page); if (!out.status.ok()) return out;
        auto reply = http.exchange("POST", "/internal/v1/trade-events", encoded, deadline, max_bytes);
        event_reply_failure(failure, reply);
        out.http_status = reply.code;
        out.status = reply.status.ok() ? signed_http_error(reply.code) : reply.status;
        if (!reply.status.ok() || reply.code != 200) return out;
        out.status = event_body(reply.body, source, request, expected, limits, deadline, validated);
        if (!out.status.ok()) return out;

        // 三个尾值来自同次客户端已验上下文；全部分配后再核D，失败不发布半页。
        std::string original_profile = profile;
        const auto original_result_capacity = read_result_capacity;
        const auto original_page_capacity = event_page_capacity;
        out.status = event_gate(deadline, failure, control, QmtTradeEventReadStage::Publish);
        if (!out.status.ok()) return out;
        out.page_json.swap(reply.body); out.read_profile_body.swap(original_profile);
        out.read_result_capacity = original_result_capacity;
        out.admitted_event_page_capacity = original_page_capacity;
        out.next_sequence = validated.next_sequence; out.event_count = validated.event_count;
        out.durable_through = validated.durable_through; out.source_ack_through = validated.source_ack_through;
        out.gap = validated.gap; out.status = {};
        return out;
    }
};

#if defined(_WIN64) && defined(_MSC_VER) && !defined(_DEBUG)
static_assert(sizeof(QmtTradeClientCore)==392, "requalify StandardEventBudget resident trade core on layout changes");
#endif
static_assert(std::is_nothrow_move_constructible<QmtTradeCancelLookupResult>::value, "publish complete cancel reference without allocation");
#if defined(_WIN32) && defined(GH_QMT_HTTP_DRAIN_TESTING)
// 专用Common测试制品核当前cohort实际布局；产品没有此导出。
extern "C" __declspec(dllexport) std::size_t gh_qmt_trade_test_core_size() noexcept
{ return sizeof(QmtTradeClientCore); }
#endif
static_assert(std::is_nothrow_move_constructible<QmtTradeResult>::value, "retain original trade receipt on uncertain delivery");
static_assert(std::is_nothrow_move_constructible<QmtTradeEventPage>::value, "publish complete event page without allocation");
static_assert(std::is_nothrow_move_assignable<QmtTradeEventReadContext>::value, "publish complete event context without allocation");
QmtHostTradeClient::QmtHostTradeClient(QmtHttpConfig config, QmtExpectedTrade expected)
    : core_(new QmtTradeClientCore(std::move(config), std::move(expected))) {}
QmtHostTradeClient::~QmtHostTradeClient() = default;
Status QmtHostTradeClient::prepare(SignedHttpDeadline& deadline) { return core_->prepare(deadline); }
Status QmtHostTradeClient::reconcile_observation(SignedHttpDeadline& deadline)
{
    const auto checked=core_->check(deadline);
    if(!checked.ok())return checked;
    const bool previous=core_->unknown_fenced;
    core_->unknown_fenced=false;core_->accepting=core_->accepting_cancel=false;
    try {
        const auto status=core_->refresh(deadline);
        if(status.ok()&&!core_->faulted&&!core_->closed&&!core_->unknown_fenced&&core_->accepting)return {};
        core_->unknown_fenced=previous||core_->unknown_fenced;core_->accepting=false;
        if(!status.ok())return status;
        if(core_->faulted)return fail(ErrorCode::Conflict,core_->fault_reason?core_->fault_reason:"qmt_trade_observation_hard_fault");
        if(core_->closed)return fail(ErrorCode::Unavailable,"qmt_trade_observation_closed");
        return fail(ErrorCode::SubmissionUnknown,"qmt_trade_observation_still_unresolved");
    } catch (...) {
        core_->unknown_fenced=previous||core_->unknown_fenced;core_->accepting=core_->accepting_cancel=false;
        return core_->fault(ErrorCode::IoError,"qmt_trade_observation_refresh_failed");
    }
}
Status QmtHostTradeClient::prepare_event_read_context(SignedHttpDeadline& deadline, QmtTradeEventReadContext& out)
{ return prepare_event_read_context(deadline, out, nullptr, nullptr); }
Status QmtHostTradeClient::prepare_event_read_context(SignedHttpDeadline& deadline, QmtTradeEventReadContext& out,
    QmtTradeEventReadFailure* failure, const QmtAccountControl* control)
{
    if (failure) { *failure = {}; failure->outcome = QmtTradeEventReadOutcome::Failure; }
    try {
        // 同次prepare失败可保留Core旧ready；只以本次Status发布独立context。
        const auto prepared = core_->prepare(deadline, failure, control);
        if (!prepared.ok()) return prepared;
        QmtTradeEventReadContext candidate;
        candidate.source = {core_->pin, core_->source_session};
        candidate.read_profile_body = core_->profile;
        candidate.admitted_limits = core_->limits;
        candidate.read_result_capacity = core_->read_result_capacity;
        candidate.admitted_event_page_capacity = core_->event_page_capacity;
        const auto checked = core_->event_gate(deadline, failure, control, QmtTradeEventReadStage::Publish);
        if (!checked.ok()) return checked;
        out = std::move(candidate);
        if (failure) *failure = {};
        return {};
    } catch (...) {
        event_local_failure(failure); // 清许可后传播原异常；out保持原完整值。
        throw;
    }
}
bool QmtHostTradeClient::accepting_commands() const { return core_->accepting; }
QmtTradeEventSource QmtHostTradeClient::event_source() const { return {core_->pin, core_->source_session}; }
QmtTradePreparation QmtHostTradeClient::create_insert(const QmtTradeInsert& value, SignedHttpDeadline& deadline) { return core_->insert(value, deadline); }
QmtTradePreparation QmtHostTradeClient::create_cancel(const QmtTradeOrderReference& value, SignedHttpDeadline& deadline) { return core_->cancel(value, deadline); }
QmtTradeResult QmtHostTradeClient::submit_once(std::unique_ptr<QmtPreparedTrade> value, SignedHttpDeadline& deadline) { return core_->submit(std::move(value), deadline); }
QmtTradeResult QmtHostTradeClient::resume(const QmtTradeReceipt& value, SignedHttpDeadline& deadline) { return core_->resume(value, deadline); }
QmtTradeLookupResult QmtHostTradeClient::lookup(const QmtTradeLookup& value, SignedHttpDeadline& deadline) { return core_->lookup(value, deadline); }
QmtTradeCancelLookupResult QmtHostTradeClient::lookup_cancel(const QmtTradeOrderReference& value, SignedHttpDeadline& deadline) { return core_->lookup_cancel(value, deadline); }
QmtTradeResult QmtHostTradeClient::resume_cancel(const QmtTradeCancelReference& value, SignedHttpDeadline& deadline) { return core_->resume_cancel(value, deadline); }
QmtTradeEventPage QmtHostTradeClient::events(const QmtTradeEventSource& source, std::uint64_t after, std::size_t limit, std::size_t max_bytes, SignedHttpDeadline& deadline)
{ return events(source, after, limit, max_bytes, deadline, nullptr, nullptr); }
QmtTradeEventPage QmtHostTradeClient::events(const QmtTradeEventSource& source, std::uint64_t after,
    std::size_t limit, std::size_t max_bytes, SignedHttpDeadline& deadline,
    QmtTradeEventReadFailure* failure, const QmtAccountControl* control)
{
    if (failure) { *failure = {}; failure->outcome = QmtTradeEventReadOutcome::Failure; }
    try {
        auto result = core_->events(source, after, limit, max_bytes, deadline, failure, control);
        if (result.status.ok() && failure) *failure = {};
        return result;
    } catch (...) {
        event_local_failure(failure);
        throw;
    }
}
Status QmtHostTradeClient::drain_callbacks(std::uint32_t milliseconds) noexcept { return core_->http.drain_callbacks(milliseconds); }
}
