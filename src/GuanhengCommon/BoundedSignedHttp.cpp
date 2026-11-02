#include "BoundedSignedHttp.h"
#include "QmtReadTransport.h"
#include "WinHttpSessionDrain.h"
#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cstring>
#include <mutex>
#include <thread>
#include <vector>
#include <set>
#include <cmath>
#include <rapidjson/reader.h>
#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <winhttp.h>
#include <bcrypt.h>
#endif
#if defined(_WIN32) && defined(GH_QMT_HTTP_DRAIN_TESTING)
// 只编入专用测试 DLL：借用的事件由测试宿主持有至 drain 成功。
// 不读取环境变量或生产配置，生产制品没有 gate 或相关导出。
namespace {
std::atomic<HANDLE> drain_test_entered{nullptr}, drain_test_release{nullptr};
std::atomic<bool> drain_test_armed{false};
std::atomic<DWORD> drain_test_callback_thread{0};
std::atomic<HANDLE> read_test_entered{nullptr}, read_test_release{nullptr};
std::atomic<unsigned> read_test_kind{0};
std::atomic<void(*)() noexcept> request_error_test_hook{nullptr};
void hold_read_callback_for_test(unsigned kind) noexcept
{
    unsigned expected=kind;
    if (!kind || !read_test_kind.compare_exchange_strong(expected,0)) return;
    drain_test_callback_thread.store(GetCurrentThreadId());
    SetEvent(read_test_entered.load());
    if (WaitForSingleObject(read_test_release.load(),20000) != WAIT_OBJECT_0) ExitProcess(96);
}
// 配置只在没有旧门控回调的阶段写入；事件由宿主持有至全部 drain 完成。
// 64 项门控分别持有实际关闭回调或 session，每项独立事件；容量准入仍走生产 owner。
// WinHttpReadData 可在持有递归锁的 DATA_AVAILABLE 内同步重入 READ_COMPLETE。
// 只在最外层回调退出后等待，确保所有原临界区均已离开，owner 可正常取消。
thread_local unsigned test_callback_depth=0, test_read_kind=0;
struct ReadCallbackScope {
    ReadCallbackScope(unsigned kind, bool read) noexcept {
        ++test_callback_depth;
        if (read) test_read_kind=kind;
    }
    ~ReadCallbackScope() {
        if (--test_callback_depth == 0) {
            const auto kind=test_read_kind; test_read_kind=0;
            if (kind) hold_read_callback_for_test(kind);
        }
    }
};
std::array<HANDLE,64> multi_entered{}, multi_release{};
std::atomic<unsigned> multi_kind{0}, multi_count{0}, multi_next{0};
std::array<std::atomic<HINTERNET>,64> held_sessions{};
// 容量场景保留实际 session，避免阻塞几十个系统回调线程造成测试调度饥饿。
// 原 track/UNLOAD_NOTIFY_EVENT 不变；测试宿主释放后才关闭本次真实 session。
bool hold_session_for_test(HINTERNET session) noexcept
{
    if (!session || multi_kind.load() != 4) return false;
    const auto index = multi_next.fetch_add(1);
    if (index >= multi_count.load()) return false;
    held_sessions[index].store(session);
    SetEvent(multi_entered[index]);
    return true;
}
void hold_closing_callback_for_test(unsigned kind) noexcept
{
    if (multi_kind.load() == kind) {
        const auto index = multi_next.fetch_add(1);
        if (index < multi_count.load()) {
            drain_test_callback_thread.store(GetCurrentThreadId());
            SetEvent(multi_entered[index]);
            if (WaitForSingleObject(multi_release[index], 20000) != WAIT_OBJECT_0)
                ExitProcess(95);
            return;
        }
    }
    if (!drain_test_armed.exchange(false)) return;
    drain_test_callback_thread.store(GetCurrentThreadId());
    SetEvent(drain_test_entered.load());
    if (WaitForSingleObject(drain_test_release.load(), 15000) != WAIT_OBJECT_0)
        ExitProcess(92); // 测试死锁硬截止；结果不能被误判为排空成功。
}
}
extern "C" __declspec(dllexport) void gh_qmt_http_test_closing_gate(HANDLE entered, HANDLE release) noexcept
{
    drain_test_entered.store(entered); drain_test_release.store(release);
    drain_test_callback_thread.store(0);
    drain_test_armed.store(entered && release);
}
// kind: 1=health，2=operation POST，3=原 ID GET 晚回调；4=真实 session 延后关闭。
extern "C" __declspec(dllexport) bool gh_qmt_http_test_closing_gates(
    unsigned kind, unsigned count, const HANDLE* entered, const HANDLE* release) noexcept
{
    if (kind < 1 || kind > 4 || !count || count > multi_entered.size() || !entered || !release)
        return false;
    for (unsigned i=0; i<count; ++i) if (!entered[i] || !release[i] || held_sessions[i].load()) return false;
    for (unsigned i=0; i<count; ++i) { multi_entered[i]=entered[i]; multi_release[i]=release[i]; }
    multi_next.store(0); multi_count.store(count); multi_kind.store(kind);
    return true;
}
extern "C" __declspec(dllexport) bool gh_qmt_http_test_release_session(unsigned index) noexcept
{
    if (index >= multi_count.load() || multi_kind.load() != 4 ||
        WaitForSingleObject(multi_release[index],0) != WAIT_OBJECT_0) return false;
    const auto session = held_sessions[index].exchange(nullptr);
    return !session || WinHttpCloseHandle(session) != FALSE;
}
// 在首段正文已复制且 mutex 已释放后保留一次在途回调，固定异步取消窗口。
extern "C" __declspec(dllexport) bool gh_qmt_http_test_read_gate(unsigned kind, HANDLE entered, HANDLE release) noexcept
{
    if ((kind != 2 && kind != 3) || !entered || !release) return false;
    read_test_entered.store(entered); read_test_release.store(release); read_test_kind.store(kind);
    return true;
}
// 只在真实REQUEST_ERROR的原生POD已保存后调用；专用probe可令实际new持续失败。
extern "C" __declspec(dllexport) void gh_qmt_http_test_request_error_hook(void(*hook)() noexcept) noexcept
{ request_error_test_hook.store(hook); }
extern "C" __declspec(dllexport) DWORD gh_qmt_http_test_callback_thread() noexcept
{ return drain_test_callback_thread.load(); }
#endif

namespace guanheng
{
namespace
{
Status failure(ErrorCode code,const char* reason) { return {code,reason}; }
using HttpResult = SignedHttpResult;
HttpResult local_http_result(Status status, SignedHttpStage stage = SignedHttpStage::Setup,
    std::uint32_t native_error = 0, SignedHttpFailureOrigin origin = SignedHttpFailureOrigin::LocalOrProtocol)
{
    HttpResult result; result.status = std::move(status);
    result.failure.origin = origin; result.failure.stage = stage; result.failure.native_error = native_error;
    return result;
}
struct JsonGuard : rapidjson::BaseReaderHandler<rapidjson::UTF8<>, JsonGuard>
{
    struct Frame { bool object; std::set<std::string> keys; };
    std::vector<Frame> frames;
    std::size_t nodes = 0;
    std::size_t max_string = 1048576;
    bool item() { return ++nodes <= 1000000; }
    bool Null() { return item(); }
    bool Bool(bool) { return item(); }
    bool Int(int) { return item(); }
    bool Uint(unsigned) { return item(); }
    bool Int64(std::int64_t) { return item(); }
    bool Uint64(std::uint64_t) { return item(); }
    bool Double(double value) { return std::isfinite(value) && item(); }
    bool String(const char*, rapidjson::SizeType length, bool) { return length <= max_string && item(); }
    bool Key(const char* key, rapidjson::SizeType length, bool)
    { return !frames.empty() && frames.back().object && length <= 4096 && frames.back().keys.emplace(key, length).second; }
    bool StartObject() { return start(true); }
    bool StartArray() { return start(false); }
    bool start(bool object)
    {
        if (frames.size() >= 32 || !item()) return false;
        frames.push_back({object, {}}); return true;
    }
    bool EndObject(rapidjson::SizeType) { frames.pop_back(); return true; }
    bool EndArray(rapidjson::SizeType) { frames.pop_back(); return true; }
};
bool parse_json(const std::string& text, rapidjson::Document& document, std::size_t maximum, std::size_t string_limit)
{
    if (text.size() > maximum || text.empty() || text.find('\0') != std::string::npos) return false;
    rapidjson::Reader reader;
    rapidjson::MemoryStream stream(text.data(), text.size());
    JsonGuard guard; guard.max_string = string_limit;
    if (!reader.Parse<rapidjson::kParseValidateEncodingFlag | rapidjson::kParseIterativeFlag>(stream, guard)) return false;
    // 默认十进制转 double 可偏移一个 ULP；来源金额和价格须保留原 IEEE-754 值。
    // 结构准入仍由上面的有界 SAX 负责，DOM 使用完整精度保证后续原值复制。
    document.Parse<rapidjson::kParseValidateEncodingFlag | rapidjson::kParseFullPrecisionFlag>(text.data(), text.size());
    return !document.HasParseError();
}

Status http_error(unsigned code)
{
    if (code == 401 || code == 403) return failure(ErrorCode::Unavailable,"qmt_http_authentication_rejected");
    if (code == 404) return failure(ErrorCode::NotSupported,"qmt_http_endpoint_unavailable");
    if (code == 409) return failure(ErrorCode::Conflict,"qmt_http_conflict");
    if (code == 429) return failure(ErrorCode::Backpressure,"qmt_http_backpressure");
    if (code == 408 || code == 504) return failure(ErrorCode::Timeout,"qmt_http_remote_timeout");
    if (code == 400 || code == 422) return failure(ErrorCode::InvalidInput,"qmt_http_remote_invalid_input");
    if (code >= 300 && code < 400) return failure(ErrorCode::IoError,"qmt_http_redirect_rejected");
    return failure(ErrorCode::IoError,"qmt_http_remote_failure");
}
// 仅复制已登记错误码到诊断；不复制账户、响应正文、凭据或远端错误消息。
Status response_http_error(unsigned code,const std::string& body)
{
    auto status=http_error(code);
    if(status.reason!="qmt_http_remote_failure")return status;
    status.reason+=":"+std::to_string(code);
    rapidjson::Document value;
    if(body.size()<=65536&&parse_bounded_qmt_json(body,value,65536,1024)&&value.IsObject()){
        if(value.HasMember("error_code")&&value["error_code"].IsString()){
            const char* fixed[]={"queue_full","strategy_stale","journal_unavailable","source_unavailable","order_source_unavailable","read_retention_capacity_exhausted"};
            for(const auto* text:fixed)if(std::strcmp(value["error_code"].GetString(),text)==0){status.reason+=":"+std::string(text);break;}
        }else if(value.HasMember("schema_version")&&value["schema_version"].IsString()
            &&std::strcmp(value["schema_version"].GetString(),"qmt.trade-host-status.v2")==0)
            status.reason+=":trade_status_not_ready";
    }
    return status;
}
#ifdef _WIN32
std::wstring wide(const std::string& value)
{
    if (value.empty()) return {};
    int count = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, value.data(), static_cast<int>(value.size()), nullptr, 0);
    if (!count) return {};
    std::wstring output(count, 0);
    if (!MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, value.data(), static_cast<int>(value.size()), &output[0], count)) return {};
    return output;
}
std::string hash(const std::string& input, const std::string* key = nullptr)
{
    BCRYPT_ALG_HANDLE algorithm = nullptr;
    BCRYPT_HASH_HANDLE handle = nullptr;
    std::vector<unsigned char> object;
    struct Cleanup
    {
        BCRYPT_ALG_HANDLE& algorithm; BCRYPT_HASH_HANDLE& handle;
        ~Cleanup() { if (handle) BCryptDestroyHash(handle); if (algorithm) BCryptCloseAlgorithmProvider(algorithm,0); }
    } cleanup{algorithm, handle};
    if (BCryptOpenAlgorithmProvider(&algorithm, BCRYPT_SHA256_ALGORITHM, nullptr, key ? BCRYPT_ALG_HANDLE_HMAC_FLAG : 0) < 0) return {};
    DWORD length = 0, received = 0;
    if (BCryptGetProperty(algorithm,BCRYPT_OBJECT_LENGTH,reinterpret_cast<PUCHAR>(&length),sizeof(length),&received,0) < 0 || length > 65536) return {};
    object.resize(length);
    std::array<unsigned char,32> digest{};
    if (BCryptCreateHash(algorithm,&handle,object.data(),length,key ? reinterpret_cast<PUCHAR>(const_cast<char*>(key->data())) : nullptr,
        key ? static_cast<ULONG>(key->size()) : 0,0) < 0
        || BCryptHashData(handle,reinterpret_cast<PUCHAR>(const_cast<char*>(input.data())),static_cast<ULONG>(input.size()),0) < 0
        || BCryptFinishHash(handle,digest.data(),static_cast<ULONG>(digest.size()),0) < 0) return {};
    const char alphabet[] = "0123456789abcdef";
    std::string result; result.reserve(64);
    for (auto byte : digest) { result += alphabet[byte >> 4]; result += alphabet[byte & 15]; }
    return result;
}
std::string uuid()
{
    std::array<unsigned char,16> bytes{};
    if (BCryptGenRandom(nullptr,bytes.data(),static_cast<ULONG>(bytes.size()),BCRYPT_USE_SYSTEM_PREFERRED_RNG) < 0) return {};
    bytes[6] = static_cast<unsigned char>((bytes[6] & 15) | 64); bytes[8] = static_cast<unsigned char>((bytes[8] & 63) | 128);
    const char alphabet[] = "0123456789abcdef";
    std::string result;
    for (std::size_t index=0; index<bytes.size(); ++index)
    { if (index==4 || index==6 || index==8 || index==10) result += '-'; result += alphabet[bytes[index] >> 4]; result += alphabet[bytes[index] & 15]; }
    return result;
}
struct Internet
{
    HINTERNET handle = nullptr;
    explicit Internet(HINTERNET value = nullptr) : handle(value) {}
#ifdef GH_QMT_HTTP_DRAIN_TESTING
    bool test_session = false;
#endif
    ~Internet() {
#ifdef GH_QMT_HTTP_DRAIN_TESTING
        if (test_session && hold_session_for_test(handle)) return;
#endif
        if (handle) WinHttpCloseHandle(handle);
    }
    Internet(const Internet&) = delete;
    Internet& operator=(const Internet&) = delete;
};
struct Exchange
{
#ifdef GH_QMT_HTTP_DRAIN_TESTING
    unsigned test_kind = 0;
#endif
    std::recursive_mutex mutex;
    HANDLE event = CreateEventW(nullptr,TRUE,FALSE,nullptr);
    HINTERNET request = nullptr;
    bool cancelled = false, done = false;
    // callback兜底不依赖mutex/分配；owner醒来后在原锁下发布固定终态。
    std::atomic<bool> callback_failed{false};
    std::size_t maximum = 0;
    bool has_content_length = false;
    std::size_t content_length = 0;
    std::array<char,65536> buffer{};
    std::wstring headers;
    std::string upload;
    HttpResult result;
    ~Exchange() { if (event) CloseHandle(event); }
    void finish(Status status, bool delivery_unknown = false)
    {
        if (!done && !cancelled && !callback_failed.load()) {
            if (!status.ok() && result.failure.origin == SignedHttpFailureOrigin::None)
                result.failure.origin = SignedHttpFailureOrigin::LocalOrProtocol;
            result.status = std::move(status); result.delivery_unknown = delivery_unknown;
            done = true; SetEvent(event);
        }
    }
    void native_failure(DWORD error, std::uint64_t operation, SignedHttpStage stage)
    {
        // 先保存真实标量，再构造诊断；后继分配失败由callback_failed清除恢复许可。
        auto& f = result.failure;
        f.origin = result.code && result.code != 200 ? SignedHttpFailureOrigin::RemoteHttp : SignedHttpFailureOrigin::NativeTransport; f.native_error = error;
        f.native_operation = operation; f.stage = stage;
        f.recovery = (result.code == 0 || result.code == 200)
            && (error == ERROR_WINHTTP_CANNOT_CONNECT || error == ERROR_WINHTTP_CONNECTION_ERROR
                || error == ERROR_WINHTTP_TIMEOUT)
            ? SignedHttpRecovery::TransportInterrupted : SignedHttpRecovery::None;
    }
    bool accept(BOOL accepted, SignedHttpStage stage)
    {
        if (accepted) return true;
        const DWORD error = GetLastError(); // 每次同步失败只捕获一次原错误。
        if (error == ERROR_IO_PENDING) return true;
        native_failure(error, 0, stage);
        finish(failure(error == ERROR_WINHTTP_TIMEOUT ? ErrorCode::Timeout : ErrorCode::IoError,
            "qmt_http_exchange_failed"), true);
        return false;
    }
};
using ExchangeOwner = std::shared_ptr<Exchange>;
void CALLBACK http_callback(HINTERNET, DWORD_PTR context, DWORD code, LPVOID information, DWORD length) noexcept
{
    if (!context) return;
    auto owner = reinterpret_cast<ExchangeOwner*>(context);
    // HANDLE_CLOSING 是该 request 最后一次回调。此引用拥有取消后仍在途的缓冲区。
    if (code == WINHTTP_CALLBACK_STATUS_HANDLE_CLOSING)
    {
#ifdef GH_QMT_HTTP_DRAIN_TESTING
        hold_closing_callback_for_test((*owner)->test_kind);
#endif
        delete owner; return;
    }
    auto state = *owner;
#ifdef GH_QMT_HTTP_DRAIN_TESTING
    ReadCallbackScope test_scope(state->test_kind, code == WINHTTP_CALLBACK_STATUS_READ_COMPLETE && length);
#endif
    try
    {
        std::lock_guard<std::recursive_mutex> lock(state->mutex);
        if (state->cancelled || state->done || state->callback_failed.load()) return;
        switch (code)
        {
        case WINHTTP_CALLBACK_STATUS_SENDREQUEST_COMPLETE:
            state->result.failure.stage = SignedHttpStage::Receive;
            state->accept(WinHttpReceiveResponse(state->request,nullptr), SignedHttpStage::Receive); break;
        case WINHTTP_CALLBACK_STATUS_HEADERS_AVAILABLE:
        {
            state->result.failure.stage = SignedHttpStage::Headers;
            DWORD size = sizeof(DWORD), status = 0;
            if (!WinHttpQueryHeaders(state->request,WINHTTP_QUERY_STATUS_CODE | WINHTTP_QUERY_FLAG_NUMBER,WINHTTP_HEADER_NAME_BY_INDEX,&status,&size,WINHTTP_NO_HEADER_INDEX))
            { const DWORD error = GetLastError(); state->result.failure.native_error = error;
                state->finish(failure(ErrorCode::IoError,"qmt_http_invalid_headers")); break; }
            state->result.code = status;
            if (status != 200) { state->result.failure.origin = SignedHttpFailureOrigin::RemoteHttp;
                state->result.failure.recovery = SignedHttpRecovery::None; }
            // WinHTTP 在已知长度的截断连接上也可能报告正常 EOF。保存受界十进制
            // 长度后核对实际字节，避免将未知交付误当成完整但非法的 JSON。
            wchar_t length_text[32]{};
            DWORD length_size = sizeof(length_text);
            if (WinHttpQueryHeaders(state->request,WINHTTP_QUERY_CONTENT_LENGTH,WINHTTP_HEADER_NAME_BY_INDEX,
                length_text,&length_size,WINHTTP_NO_HEADER_INDEX))
            {
                const std::wstring declared(length_text);
                if (declared.empty() || !std::all_of(declared.begin(),declared.end(),[](wchar_t c) { return c >= L'0' && c <= L'9'; }))
                { state->finish(failure(ErrorCode::IoError,"qmt_http_content_length_invalid")); break; }
                std::size_t count = 0;
                bool exceeds = false;
                for (auto c : declared)
                {
                    const auto digit = static_cast<std::size_t>(c-L'0');
                    if (count > (state->maximum-digit)/10) { exceeds = true; break; }
                    count = count*10+digit;
                }
                if (exceeds) { state->finish(failure(ErrorCode::Backpressure,"qmt_http_response_limit")); break; }
                state->content_length = count; state->has_content_length = true;
            }
            else {
                const DWORD error = GetLastError();
                if (error != ERROR_WINHTTP_HEADER_NOT_FOUND) {
                    state->result.failure.native_error = error;
                    state->finish(failure(error == ERROR_INSUFFICIENT_BUFFER ? ErrorCode::Backpressure : ErrorCode::IoError,
                        "qmt_http_content_length_invalid")); break;
                }
            }
            // 拒绝响应也经过同一容量/截止读取，保留原错误正文而不授成功。
            state->result.failure.stage = SignedHttpStage::Body;
            state->accept(WinHttpQueryDataAvailable(state->request,nullptr), SignedHttpStage::Body); break;
        }
        case WINHTTP_CALLBACK_STATUS_DATA_AVAILABLE:
        {
            if (!information || length != sizeof(DWORD)) { state->finish(failure(ErrorCode::IoError,"qmt_http_invalid_chunk")); break; }
            const DWORD available = *static_cast<DWORD*>(information);
            if (!available)
            {
                if (state->has_content_length && state->result.body.size() != state->content_length) {
                    auto& f = state->result.failure;
                    f.origin = state->result.body.size() < state->content_length
                        ? SignedHttpFailureOrigin::IncompleteBody : SignedHttpFailureOrigin::LocalOrProtocol;
                    f.recovery = f.origin == SignedHttpFailureOrigin::IncompleteBody && state->result.code == 200
                        ? SignedHttpRecovery::TransportInterrupted : SignedHttpRecovery::None;
                    state->finish(failure(ErrorCode::IoError,"qmt_http_body_incomplete"),true);
                }
                else
                {
                    state->result.response_complete = true;
                    state->finish(state->result.code == 200 || state->result.code == 202 ? Status{} : response_http_error(state->result.code,state->result.body));
                }
                break;
            }
            if (available > state->maximum-state->result.body.size()) { state->finish(failure(ErrorCode::Backpressure,"qmt_http_response_limit")); break; }
            state->accept(WinHttpReadData(state->request,state->buffer.data(),std::min<DWORD>(available,static_cast<DWORD>(state->buffer.size())),nullptr), SignedHttpStage::Body);
            break;
        }
        case WINHTTP_CALLBACK_STATUS_READ_COMPLETE:
            if (length > state->maximum-state->result.body.size()) { state->finish(failure(ErrorCode::Backpressure,"qmt_http_response_limit")); break; }
            if (length && !information) { state->finish(failure(ErrorCode::IoError,"qmt_http_invalid_chunk")); break; }
            if (length) state->result.body.append(static_cast<const char*>(information),length);
            state->accept(WinHttpQueryDataAvailable(state->request,nullptr), SignedHttpStage::Body); break;
        case WINHTTP_CALLBACK_STATUS_REQUEST_ERROR:
        {
            if (!information || length != sizeof(WINHTTP_ASYNC_RESULT)) {
                state->finish(failure(ErrorCode::IoError,"qmt_http_invalid_async_result"),true); break;
            }
            WINHTTP_ASYNC_RESULT actual{}; std::memcpy(&actual, information, sizeof(actual));
            state->native_failure(actual.dwError, static_cast<std::uint64_t>(actual.dwResult), state->result.failure.stage);
#ifdef GH_QMT_HTTP_DRAIN_TESTING
            if (const auto hook = request_error_test_hook.load()) hook();
#endif
            state->finish(failure(actual.dwError == ERROR_WINHTTP_TIMEOUT ? ErrorCode::Timeout : ErrorCode::IoError,
                "qmt_http_exchange_failed"),true); break;
        }
        default: break;
        }
    }
    catch (...) {
        // 此处连锁本身也可能失败。只写独立atomic及唤醒；不再锁、不构造字符串。
        // 原owner持有state/上传/缓冲直至HANDLE_CLOSING和session drain确认。
        state->callback_failed.store(true); SetEvent(state->event);
    }

}
#endif
}

class BoundedSignedHttp::Impl
{
public:
    QmtHttpConfig config;
    std::thread::id owner = std::this_thread::get_id();
    Status configured;
#ifdef _WIN32
    std::wstring host, prefix;
    INTERNET_PORT port = 0;
    bool secure = false;
    WinHttpSessionDrain callbacks;
#endif
    explicit Impl(QmtHttpConfig value) : config(std::move(value))
    {
        if (config.base_url.empty() || config.key_id.empty() || config.hmac_secret.empty())
        { configured = failure(ErrorCode::Unavailable,"qmt_http_configuration_missing"); return; }
        if (config.base_url.size() > 2048 || config.key_id.size() > 128 || config.hmac_secret.size() > 4096
            || config.timeout_ms < 1 || config.timeout_ms > 30000 || config.max_response_bytes < 256 || config.max_response_bytes > 16*1024*1024
            || !std::all_of(config.key_id.begin(),config.key_id.end(),[](unsigned char c) { return c >= 33 && c <= 126; })
            || config.base_url.find_first_of("\r\n\t?#") != std::string::npos || config.base_url.find('\0') != std::string::npos)
        { configured = failure(ErrorCode::InvalidInput,"qmt_http_configuration_invalid"); return; }
#ifdef _WIN32
        auto url = wide(config.base_url);
        URL_COMPONENTS components{}; components.dwStructSize = sizeof(components);
        components.dwHostNameLength = components.dwUrlPathLength = components.dwUserNameLength = components.dwPasswordLength = components.dwExtraInfoLength = static_cast<DWORD>(-1);
        if (url.empty() || !WinHttpCrackUrl(url.c_str(),static_cast<DWORD>(url.size()),0,&components)
            || (components.nScheme != INTERNET_SCHEME_HTTP && components.nScheme != INTERNET_SCHEME_HTTPS)
            || components.dwUserNameLength || components.dwPasswordLength || components.dwExtraInfoLength || !components.dwHostNameLength || !components.nPort)
        { configured = failure(ErrorCode::InvalidInput,"qmt_http_url_invalid"); return; }
        host.assign(components.lpszHostName,components.dwHostNameLength);
        auto normalized = host;
        std::transform(normalized.begin(),normalized.end(),normalized.begin(),[](wchar_t c) { return c >= L'A' && c <= L'Z' ? c+32 : c; });
        secure = components.nScheme == INTERNET_SCHEME_HTTPS;
        if (!secure && normalized != L"127.0.0.1" && normalized != L"::1" && normalized != L"[::1]")
        { configured = failure(ErrorCode::Unavailable,"qmt_http_remote_requires_tls"); return; }
        prefix.assign(components.lpszUrlPath ? components.lpszUrlPath : L"",components.dwUrlPathLength);
        while (!prefix.empty() && prefix.back() == L'/') prefix.pop_back();
        // 固定 Gateway 根路径，避免路径归一化/百分号/反斜线使签名和实际路由分离。
        if (!prefix.empty()) { configured = failure(ErrorCode::InvalidInput,"qmt_http_base_path_rejected"); return; }
        port = components.nPort;
#else
        configured = failure(ErrorCode::Unavailable,"qmt_http_windows_required");
#endif
    }
    ~Impl()
    {
        // 不保留凭证诊断；清除本对象所拥有的认证材料。
#ifdef _WIN32
        if (!config.hmac_secret.empty()) SecureZeroMemory(&config.hmac_secret[0],config.hmac_secret.size());
#endif
    }
    Status check() const
    {
        if (owner != std::this_thread::get_id()) return failure(ErrorCode::InvalidInput,"qmt_http_owner_thread_required");
        return configured;
    }
    HttpResult exchange(const char* method, const std::string& target, const std::string& body, SignedHttpDeadline& deadline,
        std::size_t response_limit)
    {
        auto left = deadline.remaining();
        if (!left) return local_http_result(failure(ErrorCode::Timeout,"qmt_http_deadline"),
            SignedHttpStage::None, 0, SignedHttpFailureOrigin::Deadline);
#ifdef _WIN32
        // 先确认容量，再创建任何新 session。请求结束只关闭 WinHTTP handles，
        // 回调代码的卸载资格由独立的 session 通知事件确认。
        if (!callbacks.available()) return local_http_result(failure(ErrorCode::Backpressure,"qmt_http_pending_session_limit"));
        auto digest = hash(body), nonce = uuid();
        auto timestamp = std::to_string(std::chrono::duration_cast<std::chrono::seconds>(std::chrono::system_clock::now().time_since_epoch()).count());
        const auto signature = hash(std::string(method)+"\n"+target+"\n"+timestamp+"\n"+nonce+"\n"+digest,&config.hmac_secret);
        if (digest.empty() || nonce.empty() || signature.empty()) return local_http_result(failure(ErrorCode::Unavailable,"qmt_http_crypto_unavailable"));
        const auto header_text = "Accept: application/json\r\nContent-Type: application/json\r\nX-QMT-Key-Id: "+config.key_id+
            "\r\nX-QMT-Timestamp: "+timestamp+"\r\nX-QMT-Nonce: "+nonce+"\r\nX-QMT-Content-SHA256: "+digest+"\r\nX-QMT-Signature: "+signature+"\r\n";
        Internet internet(WinHttpOpen(L"GuanhengQmtRead/1",WINHTTP_ACCESS_TYPE_NO_PROXY,WINHTTP_NO_PROXY_NAME,WINHTTP_NO_PROXY_BYPASS,WINHTTP_FLAG_ASYNC));
        if (!internet.handle) { const DWORD error = GetLastError(); return local_http_result(failure(ErrorCode::IoError,"qmt_http_session_failed"), SignedHttpStage::Setup, error); }
        auto tracked = callbacks.track(internet.handle);
        if (!tracked.ok()) return local_http_result(std::move(tracked));
#ifdef GH_QMT_HTTP_DRAIN_TESTING
        internet.test_session = true;
#endif
        const auto phase = static_cast<int>(std::min(left,config.timeout_ms));
        if (!WinHttpSetTimeouts(internet.handle,phase,phase,phase,phase)) { const DWORD error = GetLastError(); return local_http_result(failure(ErrorCode::IoError,"qmt_http_timeout_setup_failed"), SignedHttpStage::Setup, error); }
        Internet connection(WinHttpConnect(internet.handle,host.c_str(),port,0));
        if (!connection.handle) { const DWORD error = GetLastError(); return local_http_result(failure(ErrorCode::IoError,"qmt_http_connect_failed"), SignedHttpStage::Setup, error); }
        auto path = wide(target), verb = wide(method);
        Internet request(WinHttpOpenRequest(connection.handle,verb.c_str(),path.c_str(),nullptr,WINHTTP_NO_REFERER,WINHTTP_DEFAULT_ACCEPT_TYPES,secure ? WINHTTP_FLAG_SECURE : 0));
        if (!request.handle) { const DWORD error = GetLastError(); return local_http_result(failure(ErrorCode::IoError,"qmt_http_request_failed"), SignedHttpStage::Setup, error); }
        DWORD disabled = WINHTTP_DISABLE_REDIRECTS | WINHTTP_DISABLE_COOKIES | WINHTTP_DISABLE_AUTHENTICATION;
        DWORD redirects = WINHTTP_OPTION_REDIRECT_POLICY_NEVER, logon = WINHTTP_AUTOLOGON_SECURITY_LEVEL_HIGH;
        if (!WinHttpSetOption(request.handle,WINHTTP_OPTION_DISABLE_FEATURE,&disabled,sizeof(disabled))
            || !WinHttpSetOption(request.handle,WINHTTP_OPTION_REDIRECT_POLICY,&redirects,sizeof(redirects))
            || !WinHttpSetOption(request.handle,WINHTTP_OPTION_AUTOLOGON_POLICY,&logon,sizeof(logon)))
            { const DWORD error = GetLastError(); return local_http_result(failure(ErrorCode::IoError,"qmt_http_security_setup_failed"), SignedHttpStage::Setup, error); }
        auto state = std::make_shared<Exchange>();
#ifdef GH_QMT_HTTP_DRAIN_TESTING
        state->test_kind = (target == "/internal/v1/health" || target == "/internal/v1/read-binding") ? 1 :
            (target.find("/internal/v1/operations/") == 0 || target.find("/internal/v1/bound-operations/") == 0) ? 2 :
            (target.find("/internal/v1/operation-results/") == 0 || target.find("/internal/v1/bound-results/") == 0) ? 3 : 0;
#endif
        if (!state->event) { const DWORD error = GetLastError(); return local_http_result(failure(ErrorCode::IoError,"qmt_http_wait_setup_failed"), SignedHttpStage::Setup, error); }
        state->request = request.handle; state->maximum = response_limit ? std::min(response_limit,config.max_response_bytes) : config.max_response_bytes;
        state->headers = wide(header_text); state->upload = body;
        if (WinHttpSetStatusCallback(request.handle,http_callback,WINHTTP_CALLBACK_FLAG_ALL_COMPLETIONS | WINHTTP_CALLBACK_FLAG_HANDLES,0) == WINHTTP_INVALID_STATUS_CALLBACK)
            { const DWORD error = GetLastError(); return local_http_result(failure(ErrorCode::IoError,"qmt_http_callback_setup_failed"), SignedHttpStage::Setup, error); }
        // Context 从 SendRequest 到 HANDLE_CLOSING 有独立引用；取消不等待网络线程退出。
        auto callback_owner = new ExchangeOwner(state);
        DWORD_PTR context = reinterpret_cast<DWORD_PTR>(callback_owner);
        if (!WinHttpSetOption(request.handle,WINHTTP_OPTION_CONTEXT_VALUE,&context,sizeof(context)))
        { const DWORD error = GetLastError(); delete callback_owner;
            return local_http_result(failure(ErrorCode::IoError,"qmt_http_context_setup_failed"), SignedHttpStage::Setup, error); }
        {
            std::lock_guard<std::recursive_mutex> lock(state->mutex);
            // 唯一发送边界；包括同步失败在内，进入此调用后均保留尝试事实。
            state->result.send_attempted = true; state->result.failure.stage = SignedHttpStage::Send;
            state->accept(WinHttpSendRequest(request.handle,state->headers.c_str(),static_cast<DWORD>(state->headers.size()),
                body.empty() ? WINHTTP_NO_REQUEST_DATA : &state->upload[0],static_cast<DWORD>(body.size()),static_cast<DWORD>(body.size()),context), SignedHttpStage::Send);
        }
        left = deadline.remaining();
        DWORD waited = left ? WaitForSingleObject(state->event,left) : WAIT_TIMEOUT;
        const DWORD wait_error = waited == WAIT_FAILED ? GetLastError() : 0;
        std::lock_guard<std::recursive_mutex> lock(state->mutex);
        if (state->callback_failed.load()) {
            // 无分配提交callback失败；保留实际native标量供诊断，但取消全部恢复许可。
            state->result.failure.recovery = SignedHttpRecovery::None;
            const bool expired = !deadline.remaining();
            state->result.failure.origin = expired ? SignedHttpFailureOrigin::Deadline : SignedHttpFailureOrigin::LocalOrProtocol;
            state->result.status.code = expired ? ErrorCode::Timeout : ErrorCode::IoError;
            state->result.status.reason.clear();
            state->result.delivery_unknown = true;
        } else if (waited == WAIT_FAILED) {
            state->result.failure = {}; state->result.failure.origin = SignedHttpFailureOrigin::LocalOrProtocol;
            state->result.failure.stage = SignedHttpStage::Wait; state->result.failure.native_error = wait_error;
            state->result.status = failure(ErrorCode::IoError,"qmt_http_wait_failed"); state->result.delivery_unknown = true;
        } else if (waited != WAIT_OBJECT_0 || !deadline.remaining()) {
            state->result.failure = {}; state->result.failure.origin = SignedHttpFailureOrigin::Deadline;
            state->result.failure.stage = SignedHttpStage::Wait;
            state->result.status = failure(ErrorCode::Timeout,"qmt_http_deadline"); state->result.delivery_unknown = true;
        }
        state->cancelled = true;
        return std::move(state->result);
#else
        (void)method; (void)target; (void)body;
        return local_http_result(failure(ErrorCode::Unavailable,"qmt_http_windows_required"));
#endif
    }
};

std::uint32_t SignedHttpDeadline::remaining() const
{
    const auto value = std::chrono::duration_cast<std::chrono::milliseconds>(end-std::chrono::steady_clock::now()).count();
    return value > 0 ? static_cast<std::uint32_t>(std::min<std::int64_t>(value, UINT32_MAX)) : 0;
}
BoundedSignedHttp::BoundedSignedHttp(QmtHttpConfig config) : impl_(new Impl(std::move(config))) {}
BoundedSignedHttp::~BoundedSignedHttp() = default;
Status BoundedSignedHttp::check() const { return impl_->check(); }
SignedHttpResult BoundedSignedHttp::exchange(const char* method,const std::string& target,
    const std::string& body,SignedHttpDeadline& deadline,std::size_t response_limit)
{
    const auto status = check();
    if (!status.ok()) return local_http_result(status, SignedHttpStage::None);
    return impl_->exchange(method,target,body,deadline,response_limit);
}
Status BoundedSignedHttp::drain_callbacks(std::uint32_t timeout_ms) noexcept
{
    try {
        if (impl_->owner != std::this_thread::get_id())
            return failure(ErrorCode::InvalidInput,"qmt_http_owner_thread_required");
        if (timeout_ms > 300000) return failure(ErrorCode::InvalidInput,"qmt_http_drain_budget_invalid");
#ifdef _WIN32
        return impl_->callbacks.drain(timeout_ms);
#else
        return {};
#endif
    } catch (...) { return {ErrorCode::IoError,{}}; }
}
std::string signed_http_sha256(const std::string& bytes)
{
#ifdef _WIN32
    return hash(bytes);
#else
    return {};
#endif
}
std::string signed_http_uuid()
{
#ifdef _WIN32
    return uuid();
#else
    return {};
#endif
}
Status signed_http_error(unsigned code) { return http_error(code); }
bool parse_bounded_qmt_json(const std::string& input,rapidjson::Document& value,std::size_t maximum,std::size_t string_limit)
{ return parse_json(input,value,maximum,string_limit); }
}
