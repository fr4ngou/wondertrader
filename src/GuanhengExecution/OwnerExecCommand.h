#pragma once
#include "WtCore/IExecCommand.h"
#include <cstddef>
#include <cstdint>
#include <functional>
#include <memory>

namespace wtp { class WTSContractInfo; }
namespace guanheng {
struct ExecutionQueueLimits {
    std::size_t max_commands;
    std::size_t max_payload_bytes;
    std::size_t max_targets;
    std::uint32_t max_queue_delay_ms;
};
enum class ExecutionQueueFault : std::uint8_t { None, InvalidInput, Capacity, Expired, WrongOwner, ReentrantDrain, Destination };
struct ExecutionQueueStatus {
    bool accepting = false, inflight = false;
    ExecutionQueueFault fault = ExecutionQueueFault::None;
    std::size_t queued_commands = 0, payload_bytes = 0;
    std::uint64_t accepted = 0, entered = 0, delivered = 0, rejected = 0;
};

// 目标、stub和元数据由交易宿主在owner创建并持有；先停生产者、close并排空，再销毁目标/DLL。
// 本类不保存跨线程WT对象，不向目标转发Engine设置的_stub，不计算仓位或重复执行目标。
class OwnerExecCommand final : public wtp::IExecCommand {
public:
    // lookup仅在创建线程解析tick合约，返回借用引用，至少存活至目标回调返回。
    using ContractLookup = std::function<wtp::WTSContractInfo*(const char*)>;
    OwnerExecCommand(const char* name, wtp::IExecCommand& destination, ContractLookup lookup, ExecutionQueueLimits limits);
    ~OwnerExecCommand();
    OwnerExecCommand(const OwnerExecCommand&) = delete;
    OwnerExecCommand& operator=(const OwnerExecCommand&) = delete;
    // 可由策略/行情线程调用；输入仅在本次调用内借用。失败锁存至status，不跨WT回调抛异常。
    void set_position(const wtp::wt_hashmap<std::string,double>&) noexcept override;
    void on_position_changed(const char*,double) noexcept override;
    void on_tick(const char*,wtp::WTSTickData*) noexcept override;
    // 仅创建线程调用；锁外进入目标，返回交付数，不表示券商委托/成交已成功。
    std::size_t drain(std::size_t max_commands) noexcept;
    ExecutionQueueStatus status() const;
    // 任意线程停止准入并放弃未交付值；inflight仍为true时宿主继续保留目标及本桥。
    void close() noexcept;
private:
    class Impl;
    std::unique_ptr<Impl> impl_;
};
}
