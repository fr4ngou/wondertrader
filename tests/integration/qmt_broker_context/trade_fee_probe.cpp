// 原费用别名解释的真实helper，不涉及WT下单或券商；缺失、零、冲突分别保护。
#include "GuanhengCommon/QmtTradeFee.h"
#include <cassert>

int main()
{
    rapidjson::Document row;
    row.Parse("{}");assert(!guanheng::qmt_trade_fee(row));
    row.Parse("{\"m_dComssion\":null}");assert(!guanheng::qmt_trade_fee(row));
    row.Parse("{\"m_dComssion\":0}");assert(guanheng::qmt_trade_fee(row)==0);
    for(const auto* key:guanheng::account_fields::trade_fee_fields){
        row.SetObject();row.AddMember(rapidjson::Value(key,row.GetAllocator()),5.01403,row.GetAllocator());
        assert(guanheng::qmt_trade_fee(row)==5.01403);
    }
    row.Parse("{\"m_dCommission\":5.01403,\"m_dComssion\":5.01403}");
    assert(guanheng::qmt_trade_fee(row)==5.01403);
    for(const auto* input:{"{\"m_dComssion\":-1}","{\"m_dComssion\":\"pending\"}",
                          "{\"m_dCommission\":5,\"m_dComssion\":6}"}){
        row.Parse(input);bool rejected=false;
        try{guanheng::qmt_trade_fee(row);}catch(const std::invalid_argument&){rejected=true;}
        assert(rejected);
    }
}
