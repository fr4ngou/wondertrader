#pragma once
#include <cstdint>
#include <memory>
#include <functional>
#include <vector>
namespace wtp { class IBaseDataMgr;class IHotMgr;class WTSVariant; }
class CtaStrategy;class ICtaStrategyFact;
namespace guanheng {
class StandardExecutionHost;
enum class CtaExecutionPhase:std::uint8_t {New,Configured,Running,Stopping,Closed,Failed};
enum class CtaExecutionFault:std::uint8_t {None,Configuration,Initialize,Start,Execution,NativeTask,StrategyDelete,Close,OutputBusy};
struct CtaExecutionStatus {
    CtaExecutionPhase phase=CtaExecutionPhase::New; // 自有会话生命周期阶段，由执行owner推进。
    CtaExecutionFault fault=CtaExecutionFault::None; // 首个会话故障枚举，None表示尚未锁存故障。
    bool stop_requested=false; // 已收到停止请求；资源实际关闭另由phase确认。
    std::uint64_t initializes=0; // 原引擎初始化事件次数，单位次。
    std::uint64_t schedules=0; // 原引擎分钟调度事件次数，单位次。
    std::uint64_t sessions=0; // 原引擎交易时段开始/结束事件总数，单位次。
    std::uint64_t parser_quotes=0; // 自有SPI实际收到的报价次数；与引擎分钟调度次数分别观察。
    std::uint64_t parser_connects=0; // 插件已报告连接事件次数，连接命令受理不计入。
    std::uint64_t parser_closes=0; // 插件已报告关闭事件次数；正常停止也会增加。
    std::uint64_t parser_logs=0; // 插件日志事件次数；不复制日志正文或源凭据。
};
struct CtaExecutionStrategy {
    CtaStrategy* strategy=nullptr;
    ICtaStrategyFact* factory=nullptr;
    wtp::WTSVariant* parameters=nullptr; // 借用至close；每项保持本策略的独立参数。
};
// 同owner、输出根租约内的生命周期证明；回调不得触发交易、调度或原生save。
// admit在原init前消费上代证明；closed在全部资源关闭后、释放根租约前记录本代。
// 调用方保持钩子及借用依赖至close确认；任一false锁存关闭/配置故障。
struct CtaExecutionRecovery {
    bool restore=false;
    std::function<bool()> admit,closed;
    // 首次接管在空金融目录及根租约内准备原WT初值；restore时跳过，失败原件保留。
    std::function<bool()> prepare;
};
// 本进程同时只允许一个Session；固定集合1..64项共用原引擎和一个账户执行出口。
// 构造成功即独占全部strategy，抛异常时仍归调用方；关闭经各自原factory删除。
// base/hot/factory/execution均借用至close确认或进程退出；策略仅在原回调借用ctx。
class CtaExecutionSession final {
public:
    CtaExecutionSession(wtp::IBaseDataMgr&,wtp::IHotMgr&,StandardExecutionHost&,CtaStrategy*,ICtaStrategyFact&);
    CtaExecutionSession(wtp::IBaseDataMgr&,wtp::IHotMgr&,StandardExecutionHost&,std::vector<CtaExecutionStrategy>);
    ~CtaExecutionSession();
    CtaExecutionSession(const CtaExecutionSession&)=delete;
    CtaExecutionSession& operator=(const CtaExecutionSession&)=delete;
    // 配置保留至close；外层在首次WT插件初始化前独占创建output_directory并setGenerateDir。
    // Session独占该根租约至完整close，并核空CTA状态；原WT目录getter全进程固定。
    bool initialize(wtp::WTSVariant* environment,wtp::WTSVariant* data,wtp::WTSVariant* parsers,
        wtp::WTSVariant* strategy_params,const char* output_directory);
    // 固定集合使用构造时逐项参数；同一轮全部上下文由原WT汇总后交一个执行器。
    bool initialize(wtp::WTSVariant* environment,wtp::WTSVariant* data,wtp::WTSVariant* parsers,
        const char* output_directory,CtaExecutionRecovery* recovery=nullptr);
    bool start();
    int pump(std::uint32_t max_events,std::uint32_t max_commands);
    CtaExecutionStatus status() const; // 仅owner，诊断计数为原事件，不代表完整回调栈返回。
    void request_stop() noexcept; // 可跨线程；最终等待由owner close执行。
    // 同owner关闭目标桥并join生产者，交易owner仍可pump查询/原责任；0=生产者全停。
    int quiesce(std::uint32_t timeout_ms) noexcept;
    int close(std::uint32_t timeout_ms) noexcept; // 0=完整关闭，1=pending，负值=错误；整体截止归外层Job。
private:
    class Impl;std::unique_ptr<Impl> impl_;
};
}
