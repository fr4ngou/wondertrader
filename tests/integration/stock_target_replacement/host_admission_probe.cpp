// 同一编译单元调用实际装配配置准入；不初始化交易API或执行宿主。
#include "GuanhengExecution/StandardExecutionHost.cpp"
#include <iostream>
int main(){
    using V=wtp::WTSVariant;
    auto* trader=V::createObject();trader->append("module","TraderQMTStandard");
    trader->append("order_context","query_first");trader->append("instance_id","synthetic");
    trader->append("position_by_query",true);
    auto* executer=V::createObject();executer->append("poolsize",0u);executer->append("scale",1.);
    auto* policies=V::createObject();auto* rule=V::createObject();
    rule->append("name","WtExeFact.WtStockMinImpactBorrowedExeUnit");rule->append("min_order",100.);
    policies->append("default",rule);executer->append("policy",policies);
    auto check=[&](bool wanted){if(guanheng::valid_configuration(trader,executer)!=wanted)throw std::runtime_error("mode admission mismatch");};
    check(true);rule->append("replace_equal_position_target",false);check(true);
    rule->append("replace_equal_position_target",true);check(true);
    rule->append("replace_equal_position_target","true");check(false);
    rule->append("replace_equal_position_target",1);check(false);
    rule->append("replace_equal_position_target",V::createArray());check(false);
    rule->append("replace_equal_position_target",V::createObject());check(false);
    rule->append("replace_equal_position_target",true);rule->append("name","WtExeFact.WtMinImpactExeUnit");check(false);
    executer->release();trader->release();std::cout<<"host_config_admission=passed\n";
}
