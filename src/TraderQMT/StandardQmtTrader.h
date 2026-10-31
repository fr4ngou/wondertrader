#pragma once
#include "Includes/ITraderApi.h"
#include "Includes/WTSMarcos.h"
#include "StandardSubmission.h"
#include <cstdint>
#include <memory>
#include <string>

namespace guanheng {
enum class StandardQmtPhase : std::uint32_t {
 Created,Initialized,Connecting,Connected,LoggingIn,LoggedIn,Closing,Closed,Failed
};
enum StandardQmtError { StandardQmtInvalid=-1,StandardQmtUnavailable=-2,
 StandardQmtWrongOwner=-3,StandardQmtClosed=-4,StandardQmtCapacity=-5,
 StandardQmtReentrant=-6,StandardQmtFailure=-7 };
enum StandardQmtWait : std::uint32_t { StandardQmtPumpReady=1,
 StandardQmtWorkerDone=2,StandardQmtStopRequested=4,StandardQmtDeadline=8 };
// 仅复制诊断值，不暴露SPI、WT对象或工作线程客户端。事件消费能力仍单独验收。
struct StandardQmtDiagnostics {
 std::uint32_t version=1,size=sizeof(StandardQmtDiagnostics),phase=0;
 std::uint32_t connected=0,logged_in=0,stop_requested=0,writes_blocked=0;
 std::uint32_t queued=0,ready=0,candidates=0,pending_commands=0;
 std::uint32_t worker_live=0,worker_done=0,drained=0,joined=0;
 std::uint32_t callbacks=0,queries=0,inserts=0,cancels=0;
 std::uint32_t event_consumption_complete=0;
 std::uint64_t payload_bytes=0,owner_thread=0,worker_thread=0;
 int error=0;char reason[256]={},last_command_id[64]={};
};
// 全实例恢复观察，字段来自原责任索引及完整查询；不包含金融数量或解除责任操作。
struct StandardQmtRecoveryV1 {
 std::uint32_t version=1,size=sizeof(StandardQmtRecoveryV1),query_first=0,submissions_closed=0;
 std::uint32_t open_group=0,unresolved_children=0,pending_commands=0,unsafe=0,active_orders=0;
 // 完整查询交给原SPI并返回后的原任务ID；0表示尚未应用。size严格拒绝混编。
 std::uint64_t next_task=0,last_order_query=0,last_position_query=0,last_account_query=0;
};
// 生命周期和pump同创建线程；native业务入口保持原有界复制/并发排队。
// query_first的新增提交组及insert只在创建线程同步base调用内准入；其它线程明确拒绝。
// worker独占I/O，owner独占BaseDataMgr/WT/SPI。宿主在原Adapter.run返回后才pump。
class StandardQmtTrader final : public wtp::ITraderApi {
public:
 StandardQmtTrader();~StandardQmtTrader() override;
 bool init(wtp::WTSVariant*) override;
 void registerSpi(wtp::ITraderSpi*) override;
 void connect() override;void disconnect() override;void release() override;
 bool isConnected() override;
 bool makeEntrustID(char*,int) override;
 int login(const char*,const char*,const char*) override;int logout() override;
 int queryPositions() override;int queryOrders() override;
 int queryTrades() override;int queryAccount() override;
 int orderInsert(wtp::WTSEntrust*) override;
 int orderAction(wtp::WTSEntrustAction*) override;
 int pump(std::uint32_t max_events);
 int wait(std::uint32_t flags,std::uint32_t timeout_ms);
 int stop();int diagnostics(StandardQmtDiagnostics&) const;
 // 同owner单向关闭新增insert/cancel；保持既有收据、查询和事件处理，0=已关闭。
 int close_submissions();int recovery(StandardQmtRecoveryV1&) const;
 // 同owner暂停/恢复新insert，保留定向cancel和查询；不解除未知或硬错保护。
 int pause_inserts(bool paused);
 // 1=仅query_first等待原单观察且无硬错，0=不属该等待，负值=调用失败。
 int awaiting_observation() const;
 int begin_submission(const SubmissionKeyV1&,SubmissionTokenV1&,SubmissionViewV1&);
 int end_submission(const SubmissionTokenV1&,SubmissionOutcome,SubmissionViewV1&);
 int inspect_submission(const SubmissionKeyV1&,SubmissionViewV1&) const;
 bool owner() const noexcept;bool deletable() const noexcept;
 const std::string& id() const noexcept;
 static StandardQmtTrader* find(const char*);
 static StandardQmtTrader* lookup(wtp::ITraderApi*);
private:
#ifdef GH_QMT_STANDARD_AUDIT_TESTING
 // 独立测试TU只访问真实私有状态函数；生产构建不声明测试访问者、无字段或导出变化。
 friend struct StandardAuditTestAccess;
#endif
 struct Impl;std::unique_ptr<Impl> impl_;
};
}
// 候选Factory与宿主共用同一C ABI；构建DLL时声明/定义保持同一导出属性。
#ifdef GH_QMT_STANDARD_BUILD_DLL
#define GH_QMT_STANDARD_EXPORT EXPORT_FLAG
#else
#define GH_QMT_STANDARD_EXPORT
#endif
extern "C" {
// 可选P/A刷新能力；默认关闭，显式配置由产品宿主在创建API前核版本。
GH_QMT_STANDARD_EXPORT std::uint32_t standardQmtObservationRefreshVersion() noexcept;
GH_QMT_STANDARD_EXPORT wtp::ITraderApi* findStandardQmtTrader(const char* instance_id);
GH_QMT_STANDARD_EXPORT int pumpStandardQmtTrader(wtp::ITraderApi*,std::uint32_t max_events);
GH_QMT_STANDARD_EXPORT int waitStandardQmtTrader(wtp::ITraderApi*,std::uint32_t flags,std::uint32_t timeout_ms);
GH_QMT_STANDARD_EXPORT int stopStandardQmtTrader(wtp::ITraderApi*);
GH_QMT_STANDARD_EXPORT int inspectStandardQmtTrader(wtp::ITraderApi*,guanheng::StandardQmtDiagnostics*);
GH_QMT_STANDARD_EXPORT int closeStandardQmtSubmissions(wtp::ITraderApi*);
GH_QMT_STANDARD_EXPORT int pauseStandardQmtInserts(wtp::ITraderApi*,std::uint32_t paused);
GH_QMT_STANDARD_EXPORT int inspectStandardQmtRecovery(wtp::ITraderApi*,guanheng::StandardQmtRecoveryV1*);
GH_QMT_STANDARD_EXPORT int inspectStandardQmtAwaitingObservation(wtp::ITraderApi*);
// 同owner同步许可；无STL跨DLL、无解除责任接口；异常只返回固定Fault。
GH_QMT_STANDARD_EXPORT int beginStandardQmtSubmission(wtp::ITraderApi*,const guanheng::SubmissionKeyV1*,guanheng::SubmissionTokenV1*,guanheng::SubmissionViewV1*) noexcept;
GH_QMT_STANDARD_EXPORT int endStandardQmtSubmission(wtp::ITraderApi*,const guanheng::SubmissionTokenV1*,std::uint32_t,guanheng::SubmissionViewV1*) noexcept;
GH_QMT_STANDARD_EXPORT int inspectStandardQmtSubmission(wtp::ITraderApi*,const guanheng::SubmissionKeyV1*,guanheng::SubmissionViewV1*) noexcept;
}
