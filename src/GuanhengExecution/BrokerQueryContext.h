#pragma once
#include <boost/core/noncopyable.hpp>
#include "QueryFirstSubmission.h"
#include "WtCore/TraderAdapter.h"
#include "WtCore/WtLocalExecuter.h"
#include <array>
#include <string>
#include <thread>
#include <map>
#include <vector>

namespace guanheng {
// 复制原SPI已验证的成交事实；数量、金额及原编号保持，不归约账户或策略账本。
struct BrokerTradeObservation {
    std::string symbol,trade_id,order_id,user_tag;
    std::uint32_t trade_date=0,is_buy=0;
    std::uint64_t trade_time=0,first_live_revision=0,received_ms=0,submission_revision=0;
    double quantity=0,price=0,amount=0;
};
struct BrokerTradesObservation {
    bool known=false;
    std::uint32_t error=0; // 0正常，1容量，2同身份冲突，3日期范围改变。
    std::uint64_t revision=0,received_ms=0,query_revision=0,query_received_ms=0,live_revision=0;
    std::vector<BrokerTradeObservation> trades;
    bool origins_known=true;
    std::uint64_t submission_revision=0;
};
// 同owner的查询接线：完整ORDER交WT原订单表，不另存订单数组或增减查询余量。
// API/DLL、BaseDataMgr及sink的生命周期仍由宿主拥有；先停止再销毁本对象。
class BrokerQueryAdapter : public wtp::TraderAdapter {
public:
    BrokerQueryAdapter();
    ~BrokerQueryAdapter();
    BrokerQueryAdapter(const BrokerQueryAdapter&) = delete;
    BrokerQueryAdapter& operator=(const BrokerQueryAdapter&) = delete;
    // 在原Adapter.init成功后、run前绑定；选择只从同一份配置读取，实例内不可热切。
    bool bind_context(const char* adapter_id, wtp::WTSVariant* config,
                      wtp::ITraderApi* api, SubmissionFunctions functions);
    bool query_first() const noexcept { return selected_; }
    void assert_owner() const;
    void onRspOrders(const wtp::WTSArray*) override;
    void onRspPosition(const wtp::WTSArray*) override;
    void onRspAccount(wtp::WTSArray*) override;
    void onRspTrades(const wtp::WTSArray*) override;
    void onPushTrade(wtp::WTSTradeInfo*) override;
    void handleEvent(wtp::WTSTraderEvent, std::int32_t) override;
    double query_undone(const char* standard_code) const;
    // 返回新WT容器；caller按原getOrders约定release，内部对象由容器retain。
    wtp::OrderMap* query_orders(const char* standard_code) const;
    // 最近一次完整账户查询的CNY原回调值；空结果及断线为unknown，caller取得独立复制。
    bool account_observation(std::array<double,10>& values) const;
    BrokerTradesObservation trades_observation() const;
    std::uint64_t trades_revision() const;
    // 仅同owner原Local实际返回的有效编号可登记；失败只降来源资格，不改变原提交结果。
    void remember_submission(const char*,bool,const wtp::OrderIDs&) noexcept;
    // 原Adapter通知已解析的localid；仅关联当前onPushTrade借用期内的值副本。
    void observe_trade_origin(std::uint32_t,const char*,bool) noexcept;
    // 查询回调完成时的接收元数据；时间为epoch毫秒，不能当作源SDK采样时间。
    void observation_metadata(bool& positions_known,std::uint64_t& position_revision,
        std::uint64_t& position_received_ms,std::uint64_t& account_revision,std::uint64_t& account_received_ms) const;
    wtp::ITraderApi* context_api() const noexcept { return api_; }
    SubmissionFunctions submission_functions() const noexcept { return functions_; }
private:
    const std::thread::id owner_;
    wtp::ITraderApi* api_ = nullptr;
    SubmissionFunctions functions_;
    std::uint32_t max_rows_ = 0;
    bool bound_ = false, selected_ = false, query_valid_ = false;
    std::array<double,10> account_{};
    bool account_known_=false;
    bool positions_known_=false;
    std::uint64_t position_revision_=0,position_received_ms_=0,account_revision_=0,account_received_ms_=0;
    void observe_trade(const BrokerTradeObservation&,bool live);
    std::map<std::string,BrokerTradeObservation> trade_rows_;
    BrokerTradesObservation trade_metadata_;
    std::uint32_t trade_date_=0;
    struct SubmissionOrigin {std::string symbol;bool buy;std::uint64_t revision;};
    std::map<std::uint32_t,SubmissionOrigin> submission_origins_;
    BrokerTradeObservation* active_trade_=nullptr;
};

// 原WT执行器继续拥有目标、拆单、价格和通知。这里只替换查询入口并包装整次提交。
// query_first要求同owner调度（执行器poolsize=0）；不另建持仓、委托或资金账本。
class BrokerQueryLocalExecuter : public wtp::WtLocalExecuter {
public:
    BrokerQueryLocalExecuter(wtp::WtExecuterFactory*, const char*, wtp::IDataManager*, BrokerQueryAdapter&);
    BrokerQueryLocalExecuter(const BrokerQueryLocalExecuter&) = delete;
    BrokerQueryLocalExecuter& operator=(const BrokerQueryLocalExecuter&) = delete;
    double getUndoneQty(const char*) override;
    wtp::OrderMap* getOrders(const char*) override;
    void set_position(const wtp::wt_hashmap<std::string,double>&) override;
    void on_position_changed(const char*,double) override;
    wtp::OrderIDs buy(const char*, double, double, bool force_close = false) override;
    wtp::OrderIDs sell(const char*, double, double, bool force_close = false) override;
    void on_trade(std::uint32_t,const char*,bool,double,double) override;
    const SubmissionViewV1& last_submission() const noexcept { return observation_; }
private:
    wtp::OrderIDs submit(const char*, double, double, bool, bool buy);
    // 最新原CNY回调的值复制；只重放观察，金额不随提交/成交自行增减。
    void replay_account();
    BrokerQueryAdapter& adapter_;
    SubmissionViewV1 observation_;
};
}
