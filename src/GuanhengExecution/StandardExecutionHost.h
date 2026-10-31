#pragma once
#include "BrokerQueryContext.h"
#include "OwnerExecCommand.h"
#include "TraderQMT/StandardQmtTrader.h"
#include <cstdint>
#include <memory>
#include <string>
#include <vector>

namespace guanheng {
// 所有函数必须来自原Adapter实际装载的同一DLL；外层保持DLL至本实例关闭/进程退出。
struct StandardPluginFunctions {
    decltype(&findStandardQmtTrader) find = nullptr;
    decltype(&pumpStandardQmtTrader) pump = nullptr;
    decltype(&inspectStandardQmtTrader) inspect = nullptr;
    decltype(&stopStandardQmtTrader) stop = nullptr;
    void (*destroy)(wtp::ITraderApi*&) = nullptr;
    SubmissionFunctions submission;
    decltype(&closeStandardQmtSubmissions) close_submissions=nullptr;
    decltype(&inspectStandardQmtRecovery) recovery=nullptr;
    decltype(&inspectStandardQmtAwaitingObservation) awaiting_observation=nullptr;
    decltype(&pauseStandardQmtInserts) pause_inserts=nullptr;
};
enum class ExecutionHostPhase : std::uint8_t { New, Connecting, Ready, Degraded, Stopping, Closed };
enum class ExecutionHostFault : std::uint8_t { None, InvalidConfiguration, Initialize, Plugin, Queue, Close, WrongOwner, Reentrant };
struct ExecutionHostStatus {
    ExecutionHostPhase phase = ExecutionHostPhase::New;
    ExecutionHostFault fault = ExecutionHostFault::None;
    bool stop_requested = false, account_ready = false;
    ExecutionQueueStatus queue;
    StandardQmtDiagnostics plugin;
    std::uint64_t broker_trade_revision=0; // 原成交观察的变更序号；状态读取不复制成交明细。
};
// 原Adapter当次表的值复制；仅表示已查询的账户事实，未引入持仓归约或状态。
struct BrokerPositionObservation {
    std::string code;
    bool is_long=true;
    double quantity=0,sellable=0;
};
struct BrokerObservation {
    bool positions_known=false,account_known=false;
    std::uint64_t position_revision=0,position_received_ms=0,account_revision=0,account_received_ms=0;
    std::array<double,10> account{};
    std::vector<BrokerPositionObservation> positions;
};

// 创建线程独占生命周期和原表读取。基础数据、规则、工厂及owner专用stub均为借用；
// 保留至close确认或进程退出。生产者只拿command()，先停生产者再最终销毁宿主。
class StandardExecutionHost final {
public:
    StandardExecutionHost(const char* channel_id, const char* executer_id,
        wtp::IBaseDataMgr&, wtp::ActionPolicyMgr&, wtp::WtExecuterFactory&,
        wtp::IExecuterStub& owner_stub, wtp::IDataManager* owner_data = nullptr);
    ~StandardExecutionHost();
    StandardExecutionHost(const StandardExecutionHost&) = delete;
    StandardExecutionHost& operator=(const StandardExecutionHost&) = delete;
    // 仅New阶段调用；false表示未完成启动，仍须由owner close。配置对象保持至close确认。
    bool initialize(wtp::WTSVariant* trader, wtp::WTSVariant* executer,
        StandardPluginFunctions functions, ExecutionQueueLimits limits);
    // 仅交接目标/行情；不向目标转发原Engine给桥设置的_stub。
    std::shared_ptr<OwnerExecCommand> command() const;
    // owner有界推进：events=1..64，commands=1..1024；非负为完成/交付数，负值沿StandardQmtError。
    // 队列交付仅表示调用原执行器，最终委托结果与未知责任由Standard继续持有。
    int pump(std::uint32_t max_events, std::size_t max_commands);
    // 异步查询：0为已受理，完成由后续pump通知原Adapter；不承诺本次调用同步刷新。
    int query_orders();
    int query_positions();
    int query_account();
    // 暂停新insert，原查询/cancel仍可用；恢复只改变此暂停，不解除未知/硬错。
    bool pause_inserts(bool paused);
    // 停止目标/行情交接并暂停新insert，供正常收束后再begin_recovery关闭全部提交。
    bool prepare_recovery();
    // 停新目标和新提交，原pump/查询继续；只在显式恢复流程且同owner调用。
    bool begin_recovery();
    // API删除后返回关闭前最后一次真实观察；版本/size须匹配。
    int recovery(StandardQmtRecoveryV1&) const;
    // 读取原Adapter最近一次有效券商观察；未ready抛异常，不把旧观察宣称为当前查询结果。
    double position(const char* standard_code, bool available_only = false) const;
    std::vector<BrokerPositionObservation> positions() const;
    BrokerObservation broker_observation() const; // 同owner的原表/最近CNY回调复制，接收时点分别标识。
    BrokerTradesObservation broker_trades() const; // 原成交查询及已交付实时事实的有限复制；零交易副作用。
    double undone(const char* standard_code) const;
    // 新WT容器，caller release；使用Adapter原表，不另存订单。
    wtp::OrderMap* orders(const char* standard_code) const;
    bool cancel(std::uint32_t local_id);
    // 非owner返回固定WrongOwner值，不跨线程读取插件/账户；其他owner入口同样拒绝越线程调用。
    ExecutionHostStatus status() const;
    // 可跨线程关闭目标准入；已进入执行器/Standard的命令保持原责任，owner继续close。
    void request_stop() noexcept;
    // 0=API/原Local单元/Adapter均已销毁，1=原owner仍在途，负值=关闭失败；依赖保留至确认。
    int close() noexcept;
private:
    class Impl;
    std::unique_ptr<Impl> impl_;
};
}
