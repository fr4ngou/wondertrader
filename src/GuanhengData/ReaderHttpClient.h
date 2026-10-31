#pragma once
#include "../GuanhengCommon/ProviderTypes.h"
#include "../Includes/WTSStruct.h"
#include <chrono>
#include <memory>
#include <string>
#include <vector>

namespace guanheng
{
using ReaderDeadline = std::chrono::steady_clock::time_point;
enum class ReaderDelivery { Historical, Recovered, Current };
struct ReaderRequest
{
    std::string symbol;
    bool tail = true;
    std::uint32_t count = 0;
    std::uint64_t end = 0, after = 0;
};
struct ReaderBar
{
    wtp::WTSBarStruct bar{};
    ReaderDelivery delivery = ReaderDelivery::Historical;
};
struct ReaderResult
{
    Status status;
    std::string instance_id, policy_id, symbol, provenance_json;
    std::uint64_t as_of = 0;
    std::vector<ReaderBar> bars;
};
// 实现必须支持并发调用，并把等待及 I/O 纳入调用者给定的绝对截止。
// 结果拥有全部数组；业务来源、日历和补齐仍由 StrategyMarket 服务负责。
class IReaderHistoryProvider
{
public:
    virtual ~IReaderHistoryProvider() = default;
    virtual ReaderResult read(const ReaderRequest& request, ReaderDeadline deadline) = 0;
    // 停止调用方先关闭新读取并等在途read结束；排空与等待锁共用绝对截止。
    // 缺省Ok仅适用于read返回后已没有系统/后台回调的同步provider；
    // 异步provider必须覆盖，支持并发stop，异常/未完成时保留依赖。
    virtual Status drain_callbacks(ReaderDeadline) { return {}; }
};
struct ReaderHttpConfig
{
    std::string base_url, token, policy_id;
    std::size_t max_bars = 10000, max_response_bytes = 16 * 1024 * 1024;
};
class ReaderHttpClient final : public IReaderHistoryProvider
{
public:
    explicit ReaderHttpClient(ReaderHttpConfig config);
    // 调用方先停止新read并等待在途read。旧式析构等待最后WinHTTP回调，可能无界；
    // 受管宿主使用有界drain成功后再销毁，并保留DLL至全部slice最后release。
    ~ReaderHttpClient();
    Status configured() const;
    ReaderResult read(const ReaderRequest& request, ReaderDeadline deadline) override;
    // 并发调用由带截止互斥串行化；只排空，之后仍允许新的read。
    Status drain_callbacks(ReaderDeadline deadline) noexcept override;
private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};
bool reader_minute_valid(std::uint64_t minute);
// typed 注入与 HTTP 返回使用相同结构/时间/价格校验，防止测试或宿主绕过准入。
Status validate_reader_result(const ReaderRequest& request, const ReaderResult& result,
    const std::string& policy_id, std::size_t max_bars);
}
