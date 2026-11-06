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
#include "GuanhengCommon/AccountAttributionProtocol.h"

namespace guanheng {
// 复制原SPI已验证的成交事实；数量、金额及原编号保持，不归约账户或策略账本。
struct BrokerTradeObservation {
    std::string symbol; // 原WT标准证券代码，来自已核合约。
    std::string trade_id; // 券商成交身份，同日期内判重；跨日与trade_date共同定位。
    std::string order_id; // 原券商委托编号，关联成交所属委托。
    std::string user_tag; // 原WT委托归属标签，缺失保持空值。
    std::uint32_t trade_date=0; // 每笔成交原日期YYYYMMDD，可与查询中其他行不同。
    std::uint32_t is_buy=0; // 现货买入为1、卖出为0，由原方向与开平转换。
    std::uint64_t trade_time=0; // 原成交本地时刻HHMMSSmmm，日期归trade_date。
    std::uint64_t first_live_revision=0; // 首次实时通知修订，历史查询保持0。
    std::uint64_t received_ms=0; // 本地接收时刻epoch毫秒，不替代成交源时间。
    std::uint64_t submission_revision=0; // 原Local有效提交修订，缺来源为0。
    double quantity=0; // 原成交数量，股/份；本观察不增减持仓。
    double price=0; // 原未复权成交价，CNY/股或份。
    double amount=0; // 原成交金额，CNY，保持供应方值。
};
struct BrokerTradesObservation {
    bool known=false; // 完整成交观察可用，缺批或事实冲突时为false。
    std::uint32_t error=0; // 0正常，1容量，2同身份冲突，3旧版日期限制历史值。
    std::uint64_t revision=0; // 查询与实时观察的统一修订序号。
    std::uint64_t received_ms=0; // 最近一份原成交批/通知的本地接收时刻，epoch毫秒。
    std::uint64_t query_revision=0; // 原完整查询完成次数。
    std::uint64_t query_received_ms=0; // 最近完整查询接收时刻，epoch毫秒。
    std::uint64_t live_revision=0; // 原实时成交通知计数，重复通知沿原通知路径保留。
    std::vector<BrokerTradeObservation> trades; // 有界、去重、逐笔保留原日期的事实副本。
    bool origins_known=true; // 原提交关联完整可用；不推定历史委托为本地提交。
    std::uint64_t submission_revision=0; // 本owner已登记的有效提交修订上界。
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
    std::map<std::string,BrokerTradeObservation> trade_rows_; // 日期:原成交ID共同定位；跨日编号相同保留独立事实。
    BrokerTradesObservation trade_metadata_;
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
    // 仅原Local创建后/运行前登记一次，调用方保持回调至原worker/owner退出。
    void configure_attribution(AttributionObserver,const std::string& execution_id,const std::string& instance_id);
private:
    wtp::OrderIDs submit(const char*, double, double, bool, bool buy);
    // 最新原CNY回调的值复制；只重放观察，金额不随提交/成交自行增减。
    void replay_account();
    BrokerQueryAdapter& adapter_;
    SubmissionViewV1 observation_;
    AttributionObserver attribution_; // 可选通知/准入，默认不进入新行为。
    std::string attribution_execution_id_,attribution_instance_id_; // 原执行与插件身份的独立完整值。
};
}
