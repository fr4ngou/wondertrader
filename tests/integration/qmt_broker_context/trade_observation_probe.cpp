// 原Adapter公开回调的有限投影回归；历史探针入口改名且不执行，SDK/API均为替身。
#define wmain previous_trade_counterexample
#include "../qmt_standard_trader/query_live_counterexample_probe.cpp"
#undef wmain
#include "GuanhengExecution/BrokerQueryContext.h"
#include "Includes/WTSVariant.hpp"

namespace {
struct TradeApi final:wtp::ITraderApi {
    unsigned p=0,o=0,d=0,a=0,inserts=0;
    bool init(wtp::WTSVariant*)override{return true;}
    int queryPositions()override{++p;return 0;}
    int queryOrders()override{++o;return 0;}
    int queryTrades()override{++d;return 0;}
    int queryAccount()override{++a;return 0;}
    int orderInsert(wtp::WTSEntrust*)override{++inserts;return 0;}
};
struct TradeSink final:wtp::ITrdNotifySink {
    unsigned trades=0;
    void on_trade(std::uint32_t,const char*,bool,double,double)override{++trades;}
    void on_order(std::uint32_t,const char*,bool,double,double,double,bool)override{}
    void on_channel_ready()override{}
    void on_channel_lost()override{}
};
int origin_begin(wtp::ITraderApi*,const guanheng::SubmissionKeyV1*,guanheng::SubmissionTokenV1*,guanheng::SubmissionViewV1*)noexcept{return -1;}
int origin_end(wtp::ITraderApi*,const guanheng::SubmissionTokenV1*,std::uint32_t,guanheng::SubmissionViewV1*)noexcept{return -1;}
int origin_inspect(wtp::ITraderApi*,const guanheng::SubmissionKeyV1*,guanheng::SubmissionViewV1*)noexcept{return -1;}
struct TradeFixture {
    TradeApi api;TradeSink sink;guanheng::BrokerQueryAdapter adapter;WTSBaseDataMgr& base;
    TradeFixture(WTSBaseDataMgr& b,wtp::ActionPolicyMgr& policy,const char* id):base(b){
        adapter.addSink(&sink);
        auto cfg=keep(WTSVariant::createObject());cfg->append("order_context","query_first");
        cfg->append("position_by_query",true);cfg->append("max_rows",2u);
        require(adapter.initExt(id,&api,&b,&policy,true),"trade_adapter_init");
        require(adapter.bind_context(id,cfg.get(),&api,{origin_begin,origin_end,origin_inspect}),"trade_bind");
        require(adapter.run(),"trade_run");auto empty=keep(WTSArray::create());
        adapter.onLoginResult(true,"synthetic",day);adapter.onRspPosition(empty.get());
        adapter.onRspOrders(empty.get());adapter.onRspTrades(empty.get());adapter.onRspAccount(empty.get());
        require(adapter.isReady(),"trade_ready");
    }
    ~TradeFixture(){adapter.release();}
    Ref<WTSTradeInfo> trade(const char* id,unsigned time=100000000){
        auto row=keep(WTSTradeInfo::create("000001","SZSE",wtp::BT_CASH));
        row->setContractInfo(base.getContract("000001","SZSE"));row->setTradeID(id);row->setRefOrder("synthetic-order");
        row->setUserTag("external");row->setDirection(wtp::WDT_LONG);row->setOffsetType(wtp::WOT_OPEN);
        row->setVolume(20);row->setPrice(10);row->setAmount(200);row->setTradeDate(day);row->setTradeTime(time);return row;
    }
};
}
int wmain(int argc,wchar_t** argv){
    if(argc!=2)return 2;
    try{
        const auto root=fs::absolute(argv[1]);require(fs::create_directory(root),"trade_new_root");fs::current_path(root);
        WTSBaseDataMgr base;wtp::ActionPolicyMgr policy;WtHelper::setTime(day,1000);WtHelper::setTDate(day);base_files(root,base,policy);
        {
            TradeFixture f(base,policy,"trade-union");auto empty=f.adapter.trades_observation();
            require(empty.known&&empty.trades.empty()&&empty.query_revision==1,"trade_known_empty");
            auto old=f.trade("old");auto query=keep(WTSArray::create());query->append(old.get());f.adapter.onRspTrades(query.get());
            auto historical=f.adapter.trades_observation();require(historical.trades.size()==1&&!historical.trades[0].first_live_revision,"trade_query_not_live");
            f.adapter.onPushTrade(old.get());f.adapter.onPushTrade(old.get());
            auto live=f.adapter.trades_observation();require(live.known&&live.trades.size()==1&&live.trades[0].first_live_revision==1&&live.live_revision==2&&f.sink.trades==2,"trade_duplicate_union_original_notifications");
            auto earlier=f.trade("earlier",95959000);f.adapter.onPushTrade(earlier.get());
            auto rows=f.adapter.trades_observation();require(rows.trades.size()==2&&rows.trades[0].trade_time==95959000,"trade_out_of_order_source_time");
            auto no_rows=keep(WTSArray::create());f.adapter.onRspTrades(no_rows.get());
            require(f.adapter.trades_observation().trades.size()==2,"trade_query_cannot_delete_delivered");
            const auto counts=std::make_tuple(f.api.p,f.api.o,f.api.d,f.api.a,f.api.inserts);
            for(int i=0;i<8;++i)f.adapter.trades_observation();
            require(counts==std::make_tuple(f.api.p,f.api.o,f.api.d,f.api.a,f.api.inserts),"trade_read_zero_side_effects");
            f.adapter.onRspTrades(nullptr);require(!f.adapter.trades_observation().known&&f.adapter.trades_observation().trades.empty(),"trade_unknown_not_empty");
            f.adapter.onRspTrades(no_rows.get());require(f.adapter.trades_observation().known&&f.adapter.trades_observation().trades.size()==2,"trade_query_known_again");
            f.adapter.handleEvent(wtp::WTE_Close,0);require(!f.adapter.trades_observation().known,"trade_disconnect_unknown");
        }
        {
            TradeFixture f(base,policy,"trade-capacity");auto a=f.trade("a"),b=f.trade("b"),c=f.trade("c");
            f.adapter.onPushTrade(a.get());f.adapter.onPushTrade(b.get());f.adapter.onPushTrade(c.get());
            auto value=f.adapter.trades_observation();require(!value.known&&value.error==1&&value.trades.empty()&&f.sink.trades==3,"trade_capacity_original_notifications");
        }
        {
            TradeFixture f(base,policy,"trade-conflict");auto a=f.trade("a");f.adapter.onPushTrade(a.get());
            a->setVolume(30);a->setAmount(300);f.adapter.onPushTrade(a.get());
            auto value=f.adapter.trades_observation();require(!value.known&&value.error==2&&f.sink.trades==2,"trade_conflict_unknown_original_notifications");
        }
        {
            // 真实根因：完整查询含多日；同一成交编号可在不同日期重用。
            TradeFixture f(base,policy,"trade-date");auto a=f.trade("same-id"),b=f.trade("same-id");
            b->setTradeDate(20261023);auto batch=keep(WTSArray::create());batch->append(a.get());batch->append(b.get());
            f.adapter.onRspTrades(batch.get());auto history=f.adapter.trades_observation();
            require(history.known&&!history.error&&history.trades.size()==2&&f.sink.trades==0,"trade_multi_date_query_known");
            require(!history.trades[0].first_live_revision&&!history.trades[1].first_live_revision
                &&history.trades[0].trade_date!=history.trades[1].trade_date,"trade_query_preserves_dates_not_live");
            f.adapter.onRspTrades(batch.get());f.adapter.onPushTrade(b.get());f.adapter.onPushTrade(b.get());
            auto value=f.adapter.trades_observation();
            require(value.known&&!value.error&&value.trades.size()==2&&f.sink.trades==2,"trade_dates_preserved_original_notifications");
            require(value.query_revision==3&&value.live_revision==2
                &&!value.trades[0].first_live_revision&&value.trades[1].first_live_revision==1,"trade_query_live_date_identity");
        }
        std::puts("trade_projection_query_live_duplicate_out_of_order_unknown_disconnect_capacity_conflict_date_passed");return 0;
    }catch(const std::exception& error){std::fprintf(stderr,"%s\n",error.what());return 1;}
}
