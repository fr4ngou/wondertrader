#pragma once
#include "WtCore/IExecCommand.h"
#include <cstdint>
#include <functional>
#include <string>
#include <thread>

namespace wtp { class IBaseDataMgr; }
namespace guanheng {
struct ExecutionTimeObservation {
    std::uint64_t epoch_ms = 0; // 原TimeUtils同域epoch毫秒；不作为有界请求的steady截止。
    std::uint32_t date = 0, time_ms = 0, trading_day = 0; // YYYYMMDD / HHMMSSsss / 原生交易日。
};
// 原Local的owner专用stub。基础数据/session在构造前装载，运行期间保持，至少存活至执行器关闭。
// 实时默认系统时钟；冻结provider为显式模拟选择，不能从别的线程读取CTA可变时间字段。
class ExecutionEnvironment final : public wtp::IExecuterStub {
public:
    using Clock = std::function<std::uint64_t()>;
    ExecutionEnvironment(wtp::IBaseDataMgr&, const char* reference_session, wtp::IHotMgr* = nullptr, Clock = {});
    ExecutionEnvironment(const ExecutionEnvironment&) = delete;
    ExecutionEnvironment& operator=(const ExecutionEnvironment&) = delete;
    ExecutionTimeObservation observe() const; // 同次样本，创建线程独占；非法时钟/元数据抛明确异常。
    std::uint64_t get_real_time() override;
    wtp::WTSCommodityInfo* get_comm_info(const char*) override;
    wtp::WTSSessionInfo* get_sess_info(const char*) override;
    wtp::IHotMgr* get_hot_mon() override;
    std::uint32_t get_trading_day() override;
private:
    void assert_owner() const;
    wtp::IBaseDataMgr& base_;
    const std::string session_;
    wtp::IHotMgr* const hot_;
    const Clock clock_;
    const std::thread::id owner_;
};
}
