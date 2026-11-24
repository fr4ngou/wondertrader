#pragma once
#include "QmtAccountFields.h"
#include <rapidjson/document.h>
#include <cmath>
#include <optional>
#include <stdexcept>

namespace guanheng {
// QMT 逐笔当前费用的原值；null/缺字段为未知，多个已知别名必须一致。
// caller 先验证原 JSON 和来源；这里只解释已注册 SDK 别名，不估计费用或授交易权限。
inline std::optional<double> qmt_trade_fee(const rapidjson::Value& row)
{
    if(!row.IsObject())throw std::invalid_argument("qmt_trade_fee_invalid");
    std::optional<double> fee;
    for(const auto* key:account_fields::trade_fee_fields){
        if(!row.HasMember(key)||row[key].IsNull())continue;
        const auto& value=row[key];
        if(!value.IsNumber()||!std::isfinite(value.GetDouble())||value.GetDouble()<0)
            throw std::invalid_argument("qmt_trade_fee_invalid");
        if(fee&&*fee!=value.GetDouble())throw std::invalid_argument("qmt_trade_fee_conflict");
        fee=value.GetDouble();
    }
    return fee;
}
}
