#pragma once
#include "Includes/ITraderApi.h"
#include <cstdint>
#include <memory>
#include <thread>
#include <string>

namespace guanheng { namespace bootstrap {
// 仅复制值；ABI版本固定为1，宿主不得保存内部对象或跨owner调用。
struct Diagnostics
{
    std::uint32_t version = 1, size = sizeof(Diagnostics);
    std::uint32_t phase = 0, delivered = 0, callbacks = 0, reads = 0, polls = 0;
    std::uint32_t worker_live = 0, joined = 0, queued = 0, discarded = 0, ready_results = 0;
    std::uint32_t write_rejections = 0, account_presence = 0;
    std::uint32_t row_counts[4] = {};
    char observed_at[4][21] = {};
    std::uint64_t owner_thread = 0, worker_thread = 0;
    int error = 0;
    char reason[256] = {};
};
// phase: Created, Initialized, Connecting, Querying, Observed, Closing, Closed, Failed。
enum class Phase : std::uint32_t { Created, Initialized, Connecting, Querying, Observed, Closing, Closed, Failed };
enum Error { Invalid = -1, Unavailable = -2, WrongOwner = -3, Closed = -4,
    ReadOnly = -5, Failed = -6, Reentrant = -7, Capacity = -8 };
// 等待只观察队列/资源完成；8由现有Task/round绝对截止自动产生，调用方随后pump失败收口。
enum WaitEvent : std::uint32_t { PumpReady=1, WorkerDone=2, StopRequested=4, DeadlineReached=8 };

class ReadOnlyTrader final : public wtp::ITraderApi
{
public:
    ReadOnlyTrader();
    ~ReadOnlyTrader() override;
    bool init(wtp::WTSVariant*) override;
    void registerSpi(wtp::ITraderSpi*) override;
    void connect() override;
    void disconnect() override;
    void release() override;
    bool isConnected() override;
    int login(const char*, const char*, const char*) override;
    int logout() override;
    int queryPositions() override;
    int queryOrders() override;
    int queryTrades() override;
    int queryAccount() override;
    int orderInsert(wtp::WTSEntrust*) override;
    int orderAction(wtp::WTSEntrustAction*) override;
    bool makeEntrustID(char*, int) override { return false; }
    // 同owner调用；pump仅交付已完成事件，回调重入pump拒绝。
    int pump(std::uint32_t max_events);
    // owner有限阻塞等待；不交SPI、不推进视图，伪唤醒沿用同一绝对截止。
    int wait(std::uint32_t events,std::uint32_t timeout_ms);
#ifdef GH_QMT_HTTP_DRAIN_TESTING
    void notify_wait_for_test() {impl_notify_wait();}
#endif
    int stop();
    int diagnostics(Diagnostics&) const;
    // v2为owner冻结JSON值拷贝；required含NUL，错误不写output，关闭后删除前仍可读取。
    int view(std::uint32_t version,std::uint32_t view,std::uint32_t index,char* output,std::uint32_t capacity,std::uint32_t* required) const;
    bool owner() const noexcept;
    bool deletable() const noexcept;
    const std::string& id() const noexcept;
    static ReadOnlyTrader* find(const char*);
    static ReadOnlyTrader* lookup(wtp::ITraderApi*);
private:
#ifdef GH_QMT_HTTP_DRAIN_TESTING
    void impl_notify_wait();
#endif
    struct Impl;
    std::unique_ptr<Impl> impl_;
};
}}

// create/delete沿WT ABI。查找不保活；release开始前注销ID。
// 错误返回负Error；stop仅请求停止，release按预算等待真实drain/join。
// deleteTrader仅在Closed且已join时置空；超时保留API指针及其DLL/宿主依赖。
#ifdef NQB_BUILD_DLL
#define NQB_EXPORT EXPORT_FLAG
#else
#define NQB_EXPORT
#endif
extern "C" {
NQB_EXPORT wtp::ITraderApi* findReadOnlyTrader(const char* instance_id);
NQB_EXPORT int pumpReadOnlyTrader(wtp::ITraderApi*, std::uint32_t max_events);
NQB_EXPORT int waitReadOnlyTrader(wtp::ITraderApi*,std::uint32_t events,std::uint32_t timeout_ms);
NQB_EXPORT int stopReadOnlyTrader(wtp::ITraderApi*);
NQB_EXPORT int inspectReadOnlyTraderView(wtp::ITraderApi*,std::uint32_t version,std::uint32_t view,std::uint32_t index,char* output,std::uint32_t capacity,std::uint32_t* required);
NQB_EXPORT int inspectReadOnlyTrader(wtp::ITraderApi*, guanheng::bootstrap::Diagnostics*);
}
