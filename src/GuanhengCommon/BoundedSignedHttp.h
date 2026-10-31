#pragma once
#include "ProviderTypes.h"
#include <chrono>
#include <cstdint>
#include <memory>
#include <string>
#include <rapidjson/document.h>

namespace guanheng
{
struct QmtHttpConfig;
// 一个绝对steady截止贯穿协议的全部HTTP跳，不在每跳重新授予预算。
struct SignedHttpDeadline
{
    std::chrono::steady_clock::time_point end;
    explicit SignedHttpDeadline(std::uint32_t milliseconds)
        : end(std::chrono::steady_clock::now()+std::chrono::milliseconds(milliseconds)) {}
    explicit SignedHttpDeadline(std::chrono::steady_clock::time_point until) : end(until) {}
    std::uint32_t remaining() const;
};
// 固定运输事实仅由实际WinHTTP/EOF分支填写；默认不授事件读取恢复。
// 所有字段均为值，复制/移动及回调异常兜底不分配内存。
enum class SignedHttpRecovery { None, TransportInterrupted };
enum class SignedHttpFailureOrigin { None, NativeTransport, IncompleteBody, RemoteHttp, Deadline, LocalOrProtocol };
enum class SignedHttpStage { None, Setup, Send, Receive, Headers, Body, Wait };
struct SignedHttpFailure
{
    SignedHttpRecovery recovery = SignedHttpRecovery::None;
    SignedHttpFailureOrigin origin = SignedHttpFailureOrigin::None;
    std::uint32_t native_error = 0;
    std::uint64_t native_operation = 0;
    SignedHttpStage stage = SignedHttpStage::None;
};
struct SignedHttpResult
{
    Status status;
    unsigned code = 0;
    std::string body;
    bool delivery_unknown = false;
    // 独立发送边界：false仅在正常返回时证明尚未调用SendRequest；异常由上层保守处理。
    bool send_attempted = false;
    // 完整EOF及声明长度已核对；HTTP业务错误也可携带完整、可验证的原正文。
    bool response_complete = false;
    SignedHttpFailure failure;
};

// 创建线程独占；构造无网络I/O。统一拥有WinHTTP回调、原body签名和64项排空屏障。
// exchange返回后仍可能有系统回调；DLL/对象必须保持至drain_callbacks成功。
// 析构保留旧最终等待保险，受管宿主用自己的有界stop等待该owner退出。
class BoundedSignedHttp
{
public:
    explicit BoundedSignedHttp(QmtHttpConfig config);
    ~BoundedSignedHttp();
    BoundedSignedHttp(const BoundedSignedHttp&) = delete;
    BoundedSignedHttp& operator=(const BoundedSignedHttp&) = delete;
    Status check() const;
    // response_limit=0沿配置上限；非零只能收紧本跳，在接收/Content-Length阶段执行。
    SignedHttpResult exchange(const char* method, const std::string& target,
        const std::string& body, SignedHttpDeadline& deadline,std::size_t response_limit=0);
    Status drain_callbacks(std::uint32_t milliseconds) noexcept;
private:
    class Impl;
    std::unique_ptr<Impl> impl_;
};
// 使用同一BCrypt owner；失败返回空值，调用者按不可用处理。
std::string signed_http_sha256(const std::string& bytes);
std::string signed_http_uuid();
Status signed_http_error(unsigned code);
// 统一的协议JSON准入：DOM分配前限制32层/百万节点/重复键/UTF8/有限数。
// 两端codec与纯mapping共用；base64外层可显式放宽单字符串，原结果沿1MiB上限。
bool parse_bounded_qmt_json(const std::string& bytes,rapidjson::Document& value,
    std::size_t max_bytes=16*1024*1024,std::size_t max_string_bytes=1048576);
}
