#pragma once
#include "QmtHostReadClient.h"
#include <atomic>
#include <vector>

namespace guanheng
{
class QmtBoundReadCore;
struct QmtHistoryRequest
{
    std::string symbol, start_time, end_time;
    std::uint32_t max_rows = 0;
};
struct QmtHistoryRow
{
    std::uint64_t time = 0;
    double open = 0, high = 0, low = 0, close = 0, volume = 0, amount = 0;
};
struct QmtHistoryPage
{
    QmtHistoryRequest request;
    std::vector<QmtHistoryRow> rows;
};
struct QmtHistoryResult
{
    QmtBoundResult bound;
    QmtHistoryPage page;
    std::string remote_error_code;
};

// 只运输明确的停止值；信号处理可以写lock-free值，不访问client/HTTP或日志。
// control须长于client；停止不宣称中止已经进入的WinHTTP调用。
class QmtHistoryControl
{
public:
    void request_stop() noexcept { stopped_.store(true, std::memory_order_relaxed); }
    bool stop_requested() const noexcept { return stopped_.load(std::memory_order_relaxed); }
private:
    std::atomic<bool> stopped_{false};
};
static_assert(std::atomic<bool>::is_always_lock_free, "History signal stop requires lock-free bool");

// 构造私有且不可复制；只能由同一client创建/消费一次。receipt不可恢复成POST令牌。
class QmtPreparedHistoryRead
{
public:
    const QmtBoundReceipt& receipt() const noexcept { return receipt_; }
    const std::string& read_profile_body() const noexcept { return profile_; }
    QmtPreparedHistoryRead(const QmtPreparedHistoryRead&) = delete;
    QmtPreparedHistoryRead& operator=(const QmtPreparedHistoryRead&) = delete;
private:
    QmtPreparedHistoryRead() = default;
    friend class QmtBoundReadCore;
    QmtBoundReceipt receipt_;
    std::string profile_;
    std::string request_sha256_;
    std::shared_ptr<const void> owner_;
    std::uint64_t generation_ = 0;
};
struct QmtHistoryPreparation
{
    Status status;
    std::unique_ptr<QmtPreparedHistoryRead> request;
};

// 创建线程独占；history阶段只授该能力，v2混合profile可解析不授同时运行资格。
// 同一个截止贯穿prepare/create/持久化/submit或resume；调用方先保存receipt再提交。
class QmtHostHistoryClient
{
public:
    explicit QmtHostHistoryClient(QmtHttpConfig, const QmtHistoryControl* = nullptr,
        QmtReadProfileVersion = QmtReadProfileVersion::Legacy);
    ~QmtHostHistoryClient();
    QmtHostHistoryClient(const QmtHostHistoryClient&) = delete;
    QmtHostHistoryClient& operator=(const QmtHostHistoryClient&) = delete;
    Status prepare(SignedHttpDeadline&);
    SourceSession session() const;
    Capability capability() const;
    QmtHistoryPreparation create_request(const QmtHistoryRequest&, SignedHttpDeadline&);
    QmtHistoryResult submit_once(std::unique_ptr<QmtPreparedHistoryRead>, SignedHttpDeadline&);
    QmtHistoryResult resume(const QmtBoundReceipt&, SignedHttpDeadline&);
    Status drain_callbacks(std::uint32_t milliseconds) noexcept;
private:
    std::unique_ptr<QmtBoundReadCore> core_;
};
}
