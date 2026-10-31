// 插入的helper来自本次真实CtaProcess源码；替身只控制晚返回及旧A的到达次序。
#include <cstdint>
#include <iostream>
#include <map>
#include <set>
#include <stdexcept>
#include <string>

namespace wtp {
struct WTSOrderInfo {
    bool isAlive() const { return true; }
    const char* getEntrustID() const { return "broker.own.1"; }
    const char* getUserTag() const { return "own.1"; }
};
struct OrderMap : std::map<std::uint32_t, void*> { void release() {} };
}
namespace guanheng {
// @@RECOVERY_STRUCT@@
struct StandardExecutionHost {
    StandardQmtRecoveryV1 state;
    wtp::WTSOrderInfo order;
    wtp::OrderMap rows;
    std::string scenario;
    std::string waiting;
    bool expired = false, own_cancelled = false, latest_account_applied = false;
    unsigned cancels = 0, positions = 0, accounts = 0, account_steps = 0;
    std::uint64_t account_revision = 10, waiting_id = 0;
    explicit StandardExecutionHost(std::string name) : scenario(name) { state.next_task = 100; }
    int recovery(StandardQmtRecoveryV1& value) { value = state; return 0; }
    wtp::OrderMap* orders(const char*) {
        rows.clear();
        if ((scenario == "late_order" || scenario == "late_cancel") && !own_cancelled)
            rows[1] = &order;
        return &rows;
    }
    int query_orders() { waiting = "order"; waiting_id = ++state.next_task; return 0; }
    int query_positions() { ++positions; waiting = "position"; waiting_id = ++state.next_task; return 0; }
    int query_account() { ++accounts; waiting = "account"; waiting_id = ++state.next_task; return 0; }
    bool cancel(std::uint32_t) {
        ++cancels; own_cancelled = true;
        if (scenario == "late_cancel") expired = true;
        return true;
    }
    struct Observation { std::uint64_t account_revision; };
    Observation broker_observation() { return {account_revision}; }
    void advance() {
        if (waiting == "order") {
            state.last_order_query = waiting_id;
            if (scenario == "late_order") expired = true;
        } else if (waiting == "position") {
            state.last_position_query = waiting_id;
            if (scenario == "late_position") expired = true;
        } else if (waiting == "account") {
            ++account_revision;
            ++account_steps;
            if (scenario == "old_account" && account_steps == 1) {
                // 旧A晚交付使revision增长，原任务ID仍位于新A屏障之前。
                // @@OLD_ACCOUNT@@
            } else {
                latest_account_applied = true;
                // @@NEW_ACCOUNT@@
            }
        }
    }
};
}
void need(bool value) { if (!value) throw std::runtime_error("guard"); }
// @@REAL_HELPERS@@
int main() {
    unsigned passed = 0;
    for (const auto* name : {"late_order", "late_position", "late_cancel", "old_account"}) {
        guanheng::StandardExecutionHost execution(name);
        auto check = [&] { if (execution.expired) throw std::runtime_error("deadline"); };
        auto advance = [&] { check(); execution.advance(); };
        bool completed = false;
        try {
            // @@INVOKE@@
            completed = true;
        } catch (const std::runtime_error&) {}
        bool ok = false;
        if (execution.scenario == "late_order") ok = !completed && execution.cancels == 0;
        if (execution.scenario == "late_position") ok = !completed && execution.accounts == 0;
        if (execution.scenario == "late_cancel") ok = !completed && execution.positions == 0;
        if (execution.scenario == "old_account") ok = completed && execution.latest_account_applied && execution.account_steps == 2;
        passed += ok ? 1 : 0;
        std::cout << name << " " << (ok ? "PASS" : "FAIL") << "\n";
    }
    std::cout << "recovery_size " << sizeof(guanheng::StandardQmtRecoveryV1) << "\n";
    return passed == 4 ? 0 : 1;
}
