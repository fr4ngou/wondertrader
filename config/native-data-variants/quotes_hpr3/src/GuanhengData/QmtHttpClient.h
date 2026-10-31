#pragma once
#include "../GuanhengCommon/QmtReadTransport.h"
#include <cstddef>
#include <cstdint>
#include <memory>
#include <string>

namespace guanheng
{
// 兼容行情调用面；准入、网络与回调所有权统一由 Market 域传输拥有。
// 每次调用以 steady_clock 总截止约束 health/POST/result GET/末次 health。
// 超时只保留原 request_id 认领，绝不重发 POST；返回数据只在同一源会话有效。
// 请求返回后 WinHTTP 仍可能回调；客户端保留最多 64 个待排空 session。
// 所有者在释放客户端/DLL 前应显式 drain_callbacks。旧式析构会等待全部回调，
// 因而可能阻塞；该最后保险不计入请求截止，也不能作为有界宿主 stop 的实现。
class QmtHttpClient
{
public:
    explicit QmtHttpClient(QmtHttpConfig config);
    ~QmtHttpClient();
    QmtHttpClient(const QmtHttpClient&) = delete;
    QmtHttpClient& operator=(const QmtHttpClient&) = delete;
    Status prepare(std::uint32_t deadline_ms);
    SourceSession session() const;
    Capability capability(const std::string& operation_id) const;
    // 原 health.last_tick_at 的 RFC3339 文本；缺少或非法时为空。
    // 仅为 Host 回调存活时间，不能授予行情源时间或历史分钟闭合资格。
    std::string last_source_time() const;
    JsonResult read_operation(const std::string& operation_id,
        const std::string& arguments_json, std::uint32_t deadline_ms);
    // 创建线程调用，0..300000 毫秒；0 只检查，未排空返回 Pending，正预算耗尽返回 Timeout。
    // 清理已结束 session，不永久关闭读取准入；成功后若又发起请求须重新排空。
    // 失败保留所有事件及回调依赖，调用者继续持有客户端与其代码所在 DLL。
    Status drain_callbacks(std::uint32_t timeout_ms) noexcept;
private:
    QmtReadTransport transport_;
};
}
