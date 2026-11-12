#pragma once
#include "WtCore/CtaStraContext.h"
#include "Includes/CtaStrategyDefs.h"
#include <set>
#include <string>
#include <vector>

namespace guanheng {
// 退役只改变本策略的恢复视图，其他上下文仍可正常交易同一证券。
class RetiredTargetContext : public CtaStraContext {
    const std::set<std::string> retired;
public:
    RetiredTargetContext(wtp::WtCtaEngine* engine, const char* name, const std::vector<std::string>& codes)
        : CtaStraContext(engine, name, 0), retired(codes.begin(), codes.end()) {}

    void on_init() override {
        CtaStraBaseCtx::on_init();
        retire_loaded_targets();
        if (auto* strategy = get_stragety()) strategy->on_init(this);
        dump_chart_info();
    }

protected:
    void retire_loaded_targets() {
        for (const auto& code : retired) {
            auto position = _pos_map.find(code);
            if (position != _pos_map.end()) {
                auto& value = position->second;
                _fund_info._total_dynprofit -= value._dynprofit;
                value._volume = value._frozen = value._dynprofit = 0;
                value._frozen_date = 0;
                value._details.clear();
            }
            _sig_map.erase(code);
            _condtions.erase(code);
            _tick_subs.erase(code);
        }
    }

public:
    void enum_position(FuncEnumCtaPosCallBack callback, bool for_execution = false) override {
        CtaStraBaseCtx::enum_position([&](const char* code, double quantity) {
            if (!for_execution || retired.count(code) == 0) callback(code, quantity);
        }, for_execution);
    }
};
}
