#include "StandardExecutionHost.h"
#include "Includes/IBaseDataMgr.h"
#include "Includes/WTSContractInfo.hpp"
#include "Includes/WTSVariant.hpp"
#include "Share/CodeHelper.hpp"
#include "Share/StrUtil.hpp"
#include <atomic>
#include <cmath>
#include <cstring>
#include <stdexcept>
#include <string>
#include <thread>

namespace guanheng {
namespace {
std::string identity(const char* value) {
    if (!value || !*value || std::strlen(value) >= 64) throw std::invalid_argument("execution_host_identity");
    return value;
}
using Variant = wtp::WTSVariant;
bool object(Variant* value) { return value && value->isObject(); }
bool boolean(Variant* value) { return value && value->type() == Variant::VT_Boolean; }
bool string(Variant* value) { return value && value->type() == Variant::VT_String; }
bool number(Variant* value, bool integral = false) {
    if (!value) return false;
    switch (value->type()) {
    case Variant::VT_Int32: case Variant::VT_Uint32: case Variant::VT_Int64: case Variant::VT_Uint64: break;
    case Variant::VT_Real: if (!integral) break; else return false;
    default: return false;
    }
    return std::isfinite(value->asDouble());
}
bool optional_boolean(Variant* parent, const char* name) {
    auto* value = parent->get(name); return !value || boolean(value);
}
bool string_list(Variant* value) {
    if (string(value)) return true;
    if (!value || !value->isArray() || value->size() > 4096) return false;
    for (unsigned i = 0; i < value->size(); ++i) if (!string(value->get(i))) return false;
    return true;
}
// 在自有入口检查原Adapter/Local公共配置，原模块随后读取同一个配置对象。
// 特别是原asBoolean假定标量字符串存储，容器必须在进入原模块前拒绝。
bool valid_configuration(Variant* trader, Variant* executer) {
    if (!object(trader) || !object(executer)) return false;
    for (const auto* key : {"module", "order_context", "instance_id"})
        if (!string(trader->get(key)) || trader->getString(key).empty()) return false;
    if (trader->getString("module") != "TraderQMTStandard" || trader->getString("order_context") != "query_first"
        || !boolean(trader->get("position_by_query")) || !trader->getBoolean("position_by_query")
        || !optional_boolean(trader, "ignore_selfmatch") || !optional_boolean(trader, "savedata")
        || !number(executer->get("poolsize"), true) || executer->get("poolsize")->asDouble() != 0
        || !number(executer->get("scale")) || !optional_boolean(executer, "strict_sync")) return false;
    if (auto* risk = trader->get("riskmon")) {
        if (!object(risk) || !optional_boolean(risk, "active")) return false;
        if (risk->getBoolean("active")) {
            auto* policies = risk->get("policy"); if (!object(policies)) return false;
            for (const auto& name : policies->memberNames()) {
                auto* rule = policies->get(name.c_str()); if (!object(rule)) return false;
                for (const auto& field : rule->memberNames()) {
                    auto* value = rule->get(field.c_str());
                    if (!number(value, true) || value->asDouble() < 0 || value->asDouble() > UINT32_MAX) return false;
                }
            }
        }
    }
    if (auto* clear = executer->get("clear")) {
        if (!object(clear) || !optional_boolean(clear, "active")) return false;
        for (const auto* key : {"includes", "excludes"})
            if (auto* value = clear->get(key)) if (!string_list(value)) return false;
    }
    if (auto* groups = executer->get("groups")) {
        if (!object(groups)) return false;
        for (const auto& name : groups->memberNames()) {
            auto* group = groups->get(name.c_str());
            if (name.empty() || name.size() >= 32 || !object(group)) return false;
            for (const auto& code : group->memberNames()) if (!number(group->get(code.c_str()))) return false;
        }
    }
    auto* policies = executer->get("policy");
    if (!object(policies) || !policies->has("default")) return false;
    for (const auto& name : policies->memberNames()) {
        auto* rule = policies->get(name.c_str());
        if (!object(rule) || !string(rule->get("name")) || rule->getString("name").empty()
            || !optional_boolean(rule, "byrate") || !optional_boolean(rule, "is_cancel_unmanaged_order")
            || !optional_boolean(rule, "replace_equal_position_target")) return false;
        // 此开关只属于两个明确股票单元；其他算法不能静默忽略已声明的模式。
        if (rule->get("replace_equal_position_target")
            && rule->getString("name") != "WtExeFact.WtStockMinImpactExeUnit"
            && rule->getString("name") != "WtExeFact.WtStockMinImpactBorrowedExeUnit") return false;
        // 股票执行器按min_order做数量取整；自有装配在插件启动前核所需的正整数单位。
        const auto algorithm = StrUtil::split(rule->getString("name"), ".");
        // 与原工厂消费同一Variant并复用其分段语义，额外段不改变实际选中的算法身份。
        if (algorithm.size() >= 2 && algorithm[0] == "WtExeFact" && (algorithm[1] == "WtStockMinImpactExeUnit" || algorithm[1] == "WtStockMinImpactBorrowedExeUnit")
            && (!number(rule->get("min_order")) || rule->get("min_order")->asDouble() <= 0
                || rule->get("min_order")->asDouble() > INT32_MAX
                || std::floor(rule->get("min_order")->asDouble()) != rule->get("min_order")->asDouble())) return false;
        if (algorithm.size() >= 2 && algorithm[0] == "WtExeFact" && algorithm[1] == "WtStockMinImpactBorrowedExeUnit"
            && rule->getString("name") != "WtExeFact.WtStockMinImpactBorrowedExeUnit") return false;
        // 其他字段保持原算法语义；容器及非有限数在标量getter之前拒绝。
        for (const auto& field : rule->memberNames()) {
            auto* value = rule->get(field.c_str());
            if (!string(value) && !boolean(value) && !number(value)) return false;
        }
    }
    return true;
}
}
class StandardExecutionHost::Impl {
public:
    const std::thread::id owner = std::this_thread::get_id();
    std::string channel, name;
    wtp::IBaseDataMgr& base;
    wtp::ActionPolicyMgr& policy;
    wtp::WtExecuterFactory& factory;
    wtp::IExecuterStub& stub;
    wtp::IDataManager* data;
    std::unique_ptr<BrokerQueryAdapter> adapter;
    std::unique_ptr<BrokerQueryLocalExecuter> local;
    std::shared_ptr<OwnerExecCommand> bridge;
    StandardPluginFunctions functions;
    wtp::ITraderApi* api = nullptr;
    ExecutionHostPhase phase = ExecutionHostPhase::New;
    ExecutionHostFault fault = ExecutionHostFault::None;
    std::atomic<bool> requested{false};
    bool initialized = false, pumping = false;
    StandardQmtDiagnostics last_plugin;
    StandardQmtRecoveryV1 last_recovery;
    bool recovery_observed=false;
    std::uint32_t last_working_children=0; // 最后同owner原插件计数，供实际销毁后的关闭证明。
    bool working_children_observed=false; // 尚未读取与已核零挂单分别表达。
    Impl(const char* channel_id, const char* executer_id, wtp::IBaseDataMgr& b,
        wtp::ActionPolicyMgr& p, wtp::WtExecuterFactory& f, wtp::IExecuterStub& s, wtp::IDataManager* d)
        : channel(identity(channel_id)), name(identity(executer_id)), base(b), policy(p), factory(f), stub(s), data(d) {}
    bool on_owner() const noexcept { return owner == std::this_thread::get_id(); }
    void assert_owner() const { if (!on_owner()) throw std::runtime_error("execution_host_wrong_owner"); }
    void stop_bridge() noexcept { if (auto value = std::atomic_load(&bridge)) value->close(); }
    void fail(ExecutionHostFault value) noexcept {
        if (fault == ExecutionHostFault::None) fault = value;
        stop_bridge();
        if (phase != ExecutionHostPhase::Stopping && phase != ExecutionHostPhase::Closed) phase = ExecutionHostPhase::Degraded;
    }
    bool observe() {
        if (!api || !functions.inspect || functions.inspect(api, &last_plugin) != 0) return false;
        return true;
    }
    bool readable() const { return initialized && adapter && adapter->isReady() && last_plugin.connected && last_plugin.logged_in
        && phase != ExecutionHostPhase::Stopping && phase != ExecutionHostPhase::Closed; }
};
StandardExecutionHost::StandardExecutionHost(const char* channel_id, const char* executer_id,
    wtp::IBaseDataMgr& base, wtp::ActionPolicyMgr& policy, wtp::WtExecuterFactory& factory,
    wtp::IExecuterStub& stub, wtp::IDataManager* data)
    : impl_(new Impl(channel_id, executer_id, base, policy, factory, stub, data)) {}
StandardExecutionHost::~StandardExecutionHost() {
    // 未确认关闭时保留整棵SPI/执行对象，外层监督器在原进程截止回收；不能造成悬空回调。
    if (close() != 0) impl_.release();
}
bool StandardExecutionHost::initialize(wtp::WTSVariant* trader, wtp::WTSVariant* executer,
    StandardPluginFunctions functions, ExecutionQueueLimits limits) {
    auto& x = *impl_;
    if (!x.on_owner()) return false;
    if (x.phase != ExecutionHostPhase::New || x.requested.load()) return false;
    try {
        if (!valid_configuration(trader, executer) || !functions.find || !functions.pump || !functions.inspect
            || !functions.stop || !functions.destroy || !functions.submission.begin || !functions.submission.end
            || !functions.submission.inspect || !limits.max_commands || limits.max_commands > 1024
            || !limits.max_payload_bytes || limits.max_payload_bytes > 64u*1024u*1024u
            || !limits.max_targets || limits.max_targets > 4096 || !limits.max_queue_delay_ms || limits.max_queue_delay_ms > 30000) {
            x.fail(ExecutionHostFault::InvalidConfiguration); return false;
        }
        // 全部配置选择在账户插件初始化前核实际工厂；探针只构造/析构，不借用Context或调用init。
        auto* execution_policies=executer->get("policy");
        for(const auto& key:execution_policies->memberNames()){
            const auto selected=execution_policies->get(key.c_str())->getString("name");
            auto probe=x.factory.createExeUnit(selected.c_str());
            if(!probe){x.fail(ExecutionHostFault::InvalidConfiguration);return false;}
            if(selected=="WtExeFact.WtStockMinImpactBorrowedExeUnit"
                && std::string(probe->self()->getName())!="WtStockMinImpactBorrowedExeUnit"){
                x.fail(ExecutionHostFault::InvalidConfiguration);return false;
            }
        }
        const auto instance=trader->getString("instance_id");
        if(instance.empty() || functions.find(instance.c_str())!=nullptr) { x.fail(ExecutionHostFault::InvalidConfiguration);return false; }
        x.functions = functions;
        x.adapter.reset(new BrokerQueryAdapter());
        // 先构造不运行的原执行器和桥，验证完整队列预算；此阶段尚未建立插件或I/O。
        x.local.reset(new BrokerQueryLocalExecuter(&x.factory, x.name.c_str(), x.data, *x.adapter));
        if (!x.local->init(executer)) { x.fail(ExecutionHostFault::Initialize); return false; }
        x.local->setStub(&x.stub);
        auto bridge = std::make_shared<OwnerExecCommand>(x.name.c_str(), *x.local,
            [&x](const char* code) { const auto key = CodeHelper::extractStdCode(code, nullptr);
                return x.base.getContract(key._code, key._exchg); }, limits);
        if (!x.adapter->init(x.channel.c_str(), trader, &x.base, &x.policy)) {
            // init失败时不以全局同名查找取得别人的实例；原Adapter仅关闭自己已创建的API。
            x.adapter->release();x.fail(ExecutionHostFault::Initialize);return false;
        }
        x.api = functions.find(instance.c_str());
        if (!x.api || !x.adapter->bind_context(x.channel.c_str(), trader, x.api, functions.submission)) {
            x.fail(ExecutionHostFault::Initialize); return false;
        }
        std::atomic_store(&x.bridge, bridge);
        if(x.requested.load()){bridge->close();return false;}
        x.adapter->addSink(x.local.get());
        if (!x.adapter->run()) { x.fail(ExecutionHostFault::Initialize); return false; }
        x.initialized = true; x.phase = ExecutionHostPhase::Connecting;
        // run返回后才允许外层调用pump，保持原Adapter首次状态推进顺序。
        return true;
    } catch (...) { x.fail(ExecutionHostFault::Initialize); return false; }
}
std::shared_ptr<OwnerExecCommand> StandardExecutionHost::command() const { return std::atomic_load(&impl_->bridge); }
int StandardExecutionHost::pump(std::uint32_t max_events, std::size_t max_commands) {
    auto& x = *impl_;
    if (!x.on_owner()) return StandardQmtWrongOwner;
    if (x.pumping) { x.fail(ExecutionHostFault::Reentrant); return StandardQmtReentrant; }
    if (!x.initialized || !x.api || x.requested.load() || !max_events || max_events > 64 || !max_commands || max_commands > 1024)
        return StandardQmtUnavailable;
    struct Guard { bool& value; explicit Guard(bool& v):value(v){value=true;} ~Guard(){value=false;} } guard{x.pumping};
    try {
        const int events = x.functions.pump(x.api, max_events);
        if (events < 0 || !x.observe()) { x.fail(ExecutionHostFault::Plugin); return StandardQmtFailure; }
        const bool awaiting = x.last_plugin.writes_blocked && !x.last_plugin.stop_requested
            && x.functions.awaiting_observation && x.functions.awaiting_observation(x.api) == 1;
        if ((x.last_plugin.writes_blocked && !awaiting) || x.last_plugin.stop_requested) {
            x.fail(ExecutionHostFault::Plugin); return events;
        }
        auto bridge = command();
        if (x.adapter->isReady() && x.last_plugin.connected && x.last_plugin.logged_in && x.fault == ExecutionHostFault::None) {
            x.phase = ExecutionHostPhase::Ready;
            const auto delivered = bridge->drain(max_commands);
            if (bridge->status().fault != ExecutionQueueFault::None) { x.fail(ExecutionHostFault::Queue); return StandardQmtFailure; }
            return events + static_cast<int>(delivered);
        }
        return events;
    } catch (...) { x.fail(ExecutionHostFault::Plugin); return StandardQmtFailure; }
}
int StandardExecutionHost::query_orders() {
    auto& x=*impl_; if(!x.on_owner())return StandardQmtWrongOwner;
    return x.api && x.readable() ? x.api->queryOrders() : StandardQmtUnavailable;
}
int StandardExecutionHost::query_positions() {
    auto& x=*impl_; if(!x.on_owner())return StandardQmtWrongOwner;
    return x.api && x.readable() ? x.api->queryPositions() : StandardQmtUnavailable;
}
int StandardExecutionHost::query_account() {
    auto& x=*impl_;if(!x.on_owner())return StandardQmtWrongOwner;
    return x.api&&x.readable()?x.api->queryAccount():StandardQmtUnavailable;
}
bool StandardExecutionHost::pause_inserts(bool paused) {
    auto& x=*impl_;return x.on_owner()&&!x.pumping&&x.api&&x.readable()&&x.functions.pause_inserts
        &&x.functions.pause_inserts(x.api,paused?1u:0u)==0;
}
bool StandardExecutionHost::prepare_recovery() {
    auto& x=*impl_;if(!x.on_owner()||x.requested.load()||!pause_inserts(true))return false;
    x.stop_bridge();return true;
}
bool StandardExecutionHost::begin_recovery() {
    auto& x=*impl_;if(!x.on_owner()||x.pumping||!x.readable()||x.requested.load()
        ||!x.functions.close_submissions||!x.functions.recovery)return false;
    x.stop_bridge();return x.functions.close_submissions(x.api)==0;
}
int StandardExecutionHost::known_working_children(std::uint32_t& out) const {
    auto& x=*impl_;if(!x.on_owner())return StandardQmtWrongOwner;
    if(!x.functions.working_children)return StandardQmtUnavailable;
    if(x.api){
        const auto code=x.functions.working_children(x.api,&x.last_working_children);
        if(code!=0)return code;x.working_children_observed=true;
    }
    if(!x.working_children_observed)return StandardQmtUnavailable;
    out=x.last_working_children;return 0;
}
int StandardExecutionHost::recovery(StandardQmtRecoveryV1& out) const {
    auto& x=*impl_;if(!x.on_owner())return StandardQmtWrongOwner;
    if(out.version!=1||out.size!=sizeof(out)||!x.functions.recovery)return StandardQmtInvalid;
    if(x.api){const auto result=x.functions.recovery(x.api,&x.last_recovery);if(result!=0)return result;x.recovery_observed=true;}
    if(!x.recovery_observed)return StandardQmtUnavailable;out=x.last_recovery;return 0;
}
double StandardExecutionHost::position(const char* code, bool available) const {
    auto& x=*impl_;x.assert_owner();if(!x.readable())throw std::runtime_error("execution_host_not_ready");
    return x.adapter->getPosition(code,available);
}
double StandardExecutionHost::undone(const char* code) const {
    auto& x=*impl_;x.assert_owner();if(!x.readable())throw std::runtime_error("execution_host_not_ready");
    return x.adapter->query_undone(code);
}
std::vector<BrokerPositionObservation> StandardExecutionHost::positions() const {
    auto& x=*impl_;x.assert_owner();if(!x.readable())throw std::runtime_error("execution_host_not_ready");
    std::vector<BrokerPositionObservation> result;
    x.adapter->enumPosition([&](const char* code,bool is_long,double old_qty,double old_free,double new_qty,double new_free){
        result.push_back({code,is_long,old_qty+new_qty,old_free+new_free});
    });
    return result;
}
BrokerObservation StandardExecutionHost::broker_observation() const {
    auto& x=*impl_;x.assert_owner();if(!x.readable())throw std::runtime_error("execution_host_not_ready");
    BrokerObservation value;
    x.adapter->observation_metadata(value.positions_known,value.position_revision,value.position_received_ms,
        value.account_revision,value.account_received_ms);
    value.account_known=x.adapter->account_observation(value.account);
    if(value.positions_known)value.positions=positions();
    return value;
}
wtp::OrderMap* StandardExecutionHost::orders(const char* code) const {
    auto& x=*impl_;x.assert_owner();if(!x.readable())throw std::runtime_error("execution_host_not_ready");
    return x.adapter->query_orders(code);
}
BrokerTradesObservation StandardExecutionHost::broker_trades() const {
    auto& x=*impl_;x.assert_owner();if(!x.readable())throw std::runtime_error("execution_host_not_ready");
    return x.adapter->trades_observation();
}
bool StandardExecutionHost::cancel(std::uint32_t id) {
    auto& x=*impl_;if(!x.on_owner() || x.requested.load() || x.phase!=ExecutionHostPhase::Ready)return false;
    return x.local->cancel(id);
}
ExecutionHostStatus StandardExecutionHost::status() const {
    auto& x=*impl_;ExecutionHostStatus out;
    if(!x.on_owner()){out.phase=ExecutionHostPhase::Degraded;out.fault=ExecutionHostFault::WrongOwner;return out;}
    if(x.api&&!x.observe())x.fail(ExecutionHostFault::Plugin);
    out.phase=x.phase;out.fault=x.fault;out.stop_requested=x.requested.load();out.account_ready=x.readable();
    if(auto value=command())out.queue=value->status();
    out.plugin=x.last_plugin;
    if(x.adapter&&x.adapter->query_first())out.broker_trade_revision=x.adapter->trades_revision();
    return out;
}
void StandardExecutionHost::request_stop() noexcept { impl_->requested.store(true);impl_->stop_bridge(); }
int StandardExecutionHost::close() noexcept {
    auto& x=*impl_;if(!x.on_owner())return StandardQmtWrongOwner;
    request_stop();if(x.phase==ExecutionHostPhase::Closed)return 0;
    if(x.pumping)return 1;
    x.phase=ExecutionHostPhase::Stopping;
    if(auto bridge=command())if(bridge->status().inflight)return 1;
    try {
        if(x.api){
            if(x.functions.stop(x.api)<0){x.fail(ExecutionHostFault::Close);return StandardQmtFailure;}
            x.adapter->release();
            if(!x.observe()){x.fail(ExecutionHostFault::Close);return StandardQmtFailure;}
            const auto& state=x.last_plugin;
            if(state.phase!=static_cast<unsigned>(StandardQmtPhase::Closed)||!state.joined||!state.drained||state.worker_live)return 1;
            if(x.functions.recovery){StandardQmtRecoveryV1 value;if(recovery(value)!=0){x.fail(ExecutionHostFault::Close);return StandardQmtFailure;}}
            if(x.functions.working_children){std::uint32_t working=0;
                if(known_working_children(working)!=0){x.fail(ExecutionHostFault::Close);return StandardQmtFailure;}}
            x.functions.destroy(x.api);if(x.api)return 1;
        }
        // 插件已撤销SPI并确认所有回调退出；在依赖仍存活时完成原执行单元析构。
        // P21只能在这些消费者也确实关闭后发布clean，不能把析构留到成功收据之后。
        x.local.reset();
        x.adapter.reset();
        x.initialized=false;x.phase=ExecutionHostPhase::Closed;return 0;
    }catch(...){x.fail(ExecutionHostFault::Close);return StandardQmtFailure;}
}
}
