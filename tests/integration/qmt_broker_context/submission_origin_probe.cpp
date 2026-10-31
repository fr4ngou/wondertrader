// 已安装原实现的来源投影边界；API为显式零调用替身，不提交订单或回报金融事实。
#include "GuanhengExecution/BrokerQueryContext.h"
#include "Includes/WTSVariant.hpp"
#include <limits>
#include <memory>
#include <stdexcept>
#include <cstdio>

namespace {
void check(bool value){if(!value)throw std::runtime_error("submission_origin_boundary");}
struct Api final:wtp::ITraderApi {bool init(wtp::WTSVariant*)override{return true;}};
int begin(wtp::ITraderApi*,const guanheng::SubmissionKeyV1*,guanheng::SubmissionTokenV1*,guanheng::SubmissionViewV1*)noexcept{return -1;}
int end(wtp::ITraderApi*,const guanheng::SubmissionTokenV1*,std::uint32_t,guanheng::SubmissionViewV1*)noexcept{return -1;}
int inspect(wtp::ITraderApi*,const guanheng::SubmissionKeyV1*,guanheng::SubmissionViewV1*)noexcept{return -1;}
struct Release {void operator()(wtp::WTSVariant* value)const{value->release();}};
void bind(guanheng::BrokerQueryAdapter& adapter,Api& api){
    std::unique_ptr<wtp::WTSVariant,Release> cfg(wtp::WTSVariant::createObject());
    cfg->append("order_context","query_first");cfg->append("position_by_query",true);cfg->append("max_rows",2u);
    check(adapter.bind_context("synthetic",cfg.get(),&api,{begin,end,inspect}));
}
}
int main(){
    try{
        Api api;guanheng::BrokerQueryAdapter adapter;bind(adapter,api);
        auto before=adapter.trades_observation();check(!before.known&&before.origins_known&&!before.submission_revision);
        adapter.remember_submission("SSE.ETF.510300",true,{});
        adapter.remember_submission("SSE.ETF.510300",true,{0,(std::numeric_limits<std::uint32_t>::max)()});
        check(adapter.trades_revision()==before.revision);
        adapter.remember_submission("SSE.ETF.510300",true,{11});
        adapter.remember_submission("SSE.ETF.510300",false,{12});
        auto known=adapter.trades_observation();check(known.origins_known&&known.submission_revision==2&&!known.known);
        const wtp::OrderIDs returned{13};adapter.remember_submission("SSE.ETF.510300",true,returned);
        auto full=adapter.trades_observation();check(!full.origins_known&&full.submission_revision==2&&returned==wtp::OrderIDs{13});
        adapter.remember_submission("SSE.ETF.510300",true,{14});check(adapter.trades_revision()==full.revision);
        guanheng::BrokerQueryAdapter duplicate;bind(duplicate,api);
        duplicate.remember_submission("SSE.ETF.510300",true,{11});
        duplicate.remember_submission("SSE.ETF.510300",true,{11});
        auto conflict=duplicate.trades_observation();check(!conflict.origins_known&&conflict.submission_revision==1);
        std::puts("submission_origin_empty_invalid_capacity_conflict_passed");return 0;
    }catch(...){return 1;}
}
