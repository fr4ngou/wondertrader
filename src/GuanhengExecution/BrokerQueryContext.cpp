#include "GuanhengCommon/AccountAttributionHooks.h"
#include "BrokerQueryContext.h"
#include "TraderQMT/StandardOrderPrice.h"
#include "Includes/WTSVariant.hpp"
#include "Includes/WTSTradeDef.hpp"
#include "Includes/WTSContractInfo.hpp"
#include "Share/CodeHelper.hpp"
#include "Share/TimeUtils.hpp"
#include <cmath>
#include <cstring>
#include <stdexcept>
#include <limits>

namespace guanheng {
namespace {
void require(bool value, const char* reason) { if (!value) throw std::runtime_error(reason); }
std::uint64_t received_time(){const auto value=TimeUtils::getLocalTimeNow();require(value>0,"qmt_query_context_clock");return static_cast<std::uint64_t>(value);}
BrokerTradeObservation trade_value(const wtp::WTSTradeInfo& row,std::uint64_t received){
    auto* contract=row.getContractInfo();require(contract&&contract->getCommInfo(),"qmt_query_context_trade_contract");
    const auto category=contract->getCommInfo()->getCategoty();BrokerTradeObservation value;
    if(category==wtp::CC_Future)value.symbol=CodeHelper::rawMonthCodeToStdCode(contract->getCode(),contract->getExchg());
    else if(category==wtp::CC_FutOption||category==wtp::CC_SpotOption)
        value.symbol=CodeHelper::rawFutOptCodeToStdCode(contract->getCode(),contract->getExchg());
    else value.symbol=CodeHelper::rawFlatCodeToStdCode(contract->getCode(),contract->getExchg(),contract->getProduct());
    value.trade_id=row.getTradeID();value.order_id=row.getRefOrder();value.user_tag=row.getUserTag();
    value.trade_date=row.getTradeDate();value.trade_time=row.getTradeTime();value.received_ms=received;
    value.is_buy=(row.getDirection()==wtp::WDT_LONG&&row.getOffsetType()==wtp::WOT_OPEN)
        ||(row.getDirection()==wtp::WDT_SHORT&&row.getOffsetType()!=wtp::WOT_OPEN);
    value.quantity=row.getVolume();value.price=row.getPrice();value.amount=row.getAmount();
    require(!value.symbol.empty()&&value.symbol.size()<64&&!value.trade_id.empty()&&value.trade_id.size()<64
        &&!value.order_id.empty()&&value.order_id.size()<64&&value.user_tag.size()<64
        &&std::isfinite(value.quantity)&&value.quantity>0&&std::isfinite(value.price)&&value.price>0
        &&std::isfinite(value.amount)&&value.amount>=0,"qmt_query_context_trade_value");
    return value;
}
}
BrokerQueryAdapter::BrokerQueryAdapter() : owner_(std::this_thread::get_id()) {}
BrokerQueryAdapter::~BrokerQueryAdapter() {}
void BrokerQueryAdapter::assert_owner() const {
    require(owner_ == std::this_thread::get_id(), "qmt_query_context_wrong_owner");
}
bool BrokerQueryAdapter::bind_context(const char* id, wtp::WTSVariant* config,
                                     wtp::ITraderApi* api, SubmissionFunctions functions) {
    assert_owner();
    if (bound_ || !id || !*id || !config || !api) return false;
    const auto mode = config->getString("order_context");
    if (!mode.empty() && mode != "native" && mode != "query_first") return false;
    const bool selected = mode == "query_first";
    if (selected && (!config->getBoolean("position_by_query") || !functions.begin || !functions.end || !functions.inspect)) return false;
    const auto max_rows = config->getUInt32("max_rows");
    if (selected && (!max_rows || max_rows > 4096)) return false;
    max_rows_ = max_rows; api_ = api; functions_ = functions;
    selected_ = selected; bound_ = true;
    return true;
}
void BrokerQueryAdapter::onRspOrders(const wtp::WTSArray* rows) {
    if (!selected_) { TraderAdapter::onRspOrders(rows); return; }
    assert_owner();
    require(bound_ && rows && rows->size() <= max_rows_, "qmt_query_context_order_batch");
    for (auto it = rows->begin(); it != rows->end(); ++it) {
        auto* row = dynamic_cast<wtp::WTSOrderInfo*>(*it);
        require(row && std::isfinite(row->getVolLeft()) && row->getVolLeft() >= 0,
                "qmt_query_context_order_row");
    }
    // 完整查询交原Adapter发布，同一原订单表供读取和原生撤单使用。
    TraderAdapter::onRspOrders(rows); query_valid_ = true;
}
void BrokerQueryAdapter::handleEvent(wtp::WTSTraderEvent event, std::int32_t code) {
    if (selected_) {
        assert_owner();
        if (event == wtp::WTE_Close) {query_valid_ = false;account_known_=positions_known_=false;account_received_ms_=position_received_ms_=0;trade_metadata_.known=false;}
    }
    TraderAdapter::handleEvent(event, code);
}
void BrokerQueryAdapter::onRspPosition(const wtp::WTSArray* rows) {
    if(!selected_){TraderAdapter::onRspPosition(rows);return;}
    assert_owner();positions_known_=false;
    require(bound_&&(!rows||rows->size()<=max_rows_),"qmt_query_context_position_batch");
    TraderAdapter::onRspPosition(rows);
    positions_known_=rows!=nullptr;++position_revision_;
    position_received_ms_=positions_known_?received_time():0;
}
void BrokerQueryAdapter::onRspAccount(wtp::WTSArray* rows) {
    if(!selected_){TraderAdapter::onRspAccount(rows);return;}
    assert_owner();account_known_=false;
    require(bound_&&(!rows||rows->size()<=max_rows_),"qmt_query_context_account_batch");
    std::array<double,10> values{};bool found=false;
    for(unsigned i=0;rows&&i<rows->size();++i){
        auto* row=dynamic_cast<wtp::WTSAccountInfo*>(rows->at(i));
        require(row&&row->getCurrency(),"qmt_query_context_account_currency");
        if(std::strcmp(row->getCurrency(),"CNY")!=0)continue;
        require(!found,"qmt_query_context_account_duplicate");found=true;
        values={row->getPreBalance(),row->getBalance(),row->getBalance()+row->getDynProfit(),row->getAvailable(),
            row->getCloseProfit(),row->getDynProfit(),row->getMargin(),row->getCommission(),row->getDeposit(),row->getWithdraw()};
        for(double value:values)require(std::isfinite(value),"qmt_query_context_account_value");
    }
    account_=values;account_known_=found;TraderAdapter::onRspAccount(rows);++account_revision_;
    account_received_ms_=found?received_time():0;
}
void BrokerQueryAdapter::observe_trade(const BrokerTradeObservation& value,bool live){
    if(trade_metadata_.error)return;
    // 券商完整查询可跨日；日期属于每笔事实，同日编号冲突仍由下方逐字段核验。
    const auto key=std::to_string(value.trade_date)+":"+value.trade_id;
    auto found=trade_rows_.find(key);
    if(found==trade_rows_.end()){
        if(trade_rows_.size()>=max_rows_){trade_metadata_.error=1;trade_metadata_.known=false;return;}
        auto copy=value;if(live)copy.first_live_revision=trade_metadata_.live_revision;
        trade_rows_.emplace(key,std::move(copy));return;
    }
    auto& old=found->second;
    if(old.symbol!=value.symbol||old.order_id!=value.order_id||old.trade_date!=value.trade_date
        ||old.trade_time!=value.trade_time||old.is_buy!=value.is_buy||old.quantity!=value.quantity
        ||old.price!=value.price||old.amount!=value.amount
        ||(!old.user_tag.empty()&&!value.user_tag.empty()&&old.user_tag!=value.user_tag)){
        trade_metadata_.error=2;trade_metadata_.known=false;return;
    }
    if(old.user_tag.empty())old.user_tag=value.user_tag;
    if(value.submission_revision){
        if(old.submission_revision&&old.submission_revision!=value.submission_revision)trade_metadata_.origins_known=false;
        else old.submission_revision=value.submission_revision;
    }
    if(live&&!old.first_live_revision){old.first_live_revision=trade_metadata_.live_revision;old.received_ms=value.received_ms;}
}
void BrokerQueryAdapter::onRspTrades(const wtp::WTSArray* rows){
    if(!selected_){TraderAdapter::onRspTrades(rows);return;}
    assert_owner();require(bound_&&(!rows||rows->size()<=max_rows_),"qmt_query_context_trade_batch");
    const auto received=rows?received_time():0;std::vector<BrokerTradeObservation> values;
    if(rows)for(auto i=rows->begin();i!=rows->end();++i){
        auto* row=dynamic_cast<wtp::WTSTradeInfo*>(*i);require(row,"qmt_query_context_trade_row");
        values.push_back(trade_value(*row,received));
    }
    // 只把原回调交WT一次；观察副本不再调用查询或重复交付历史成交统计。
    TraderAdapter::onRspTrades(rows);
    ++trade_metadata_.revision;++trade_metadata_.query_revision;
    trade_metadata_.received_ms=trade_metadata_.query_received_ms=received;
    trade_metadata_.known=rows&&!trade_metadata_.error;
    for(const auto& value:values)observe_trade(value,false);
}
void BrokerQueryAdapter::onPushTrade(wtp::WTSTradeInfo* row){
    if(!selected_){TraderAdapter::onPushTrade(row);return;}
    assert_owner();require(bound_&&row,"qmt_query_context_trade_row");
    auto value=trade_value(*row,received_time());
    require(!active_trade_,"qmt_query_context_trade_reentrant");
    struct Borrow {BrokerTradeObservation*& target;~Borrow(){target=nullptr;}} borrow{active_trade_};
    active_trade_=&value;TraderAdapter::onPushTrade(row);
    ++trade_metadata_.revision;++trade_metadata_.live_revision;trade_metadata_.received_ms=value.received_ms;
    observe_trade(value,true);
}
void BrokerQueryAdapter::remember_submission(const char* code,bool buy,const wtp::OrderIDs& ids) noexcept{
    if(!trade_metadata_.origins_known||ids.empty())return;
    const auto before=trade_metadata_.submission_revision;
    try{
        assert_owner();
        for(const auto id:ids){
            if(!id||id==(std::numeric_limits<std::uint32_t>::max)())continue;
            if(submission_origins_.size()>=max_rows_||submission_origins_.count(id)
                ||trade_metadata_.submission_revision==(std::numeric_limits<std::uint64_t>::max)()){
                trade_metadata_.origins_known=false;break;
            }
            const auto revision=trade_metadata_.submission_revision+1;
            submission_origins_.emplace(id,SubmissionOrigin{code,buy,revision});
            trade_metadata_.submission_revision=revision;
        }
    }catch(...){trade_metadata_.origins_known=false;}
    // 即使尚无成交，也让原pump发布新的身份下界；金融事实及其接收时间保持。
    if(before!=trade_metadata_.submission_revision||!trade_metadata_.origins_known)++trade_metadata_.revision;
}
void BrokerQueryAdapter::observe_trade_origin(std::uint32_t id,const char* code,bool buy) noexcept{
    if(!active_trade_||!trade_metadata_.origins_known||!id)return;
    const auto found=submission_origins_.find(id);
    if(found==submission_origins_.end())return;
    const auto& origin=found->second;
    if(origin.symbol!=code||origin.buy!=buy||active_trade_->symbol!=code||active_trade_->is_buy!=buy){
        trade_metadata_.origins_known=false;return;
    }
    active_trade_->submission_revision=origin.revision;
}
BrokerTradesObservation BrokerQueryAdapter::trades_observation() const{
    assert_owner();require(selected_&&bound_,"qmt_query_context_trade_mode");
    auto value=trade_metadata_;
    if(value.known)for(const auto& row:trade_rows_)value.trades.push_back(row.second);
    return value;
}
std::uint64_t BrokerQueryAdapter::trades_revision() const{
    assert_owner();require(selected_&&bound_,"qmt_query_context_trade_mode");return trade_metadata_.revision;
}
void BrokerQueryAdapter::observation_metadata(bool& known,std::uint64_t& position_revision,
    std::uint64_t& position_received_ms,std::uint64_t& account_revision,std::uint64_t& account_received_ms) const {
    assert_owner();require(selected_&&bound_,"qmt_query_context_observation_mode");
    known=positions_known_;position_revision=position_revision_;position_received_ms=position_received_ms_;
    account_revision=account_revision_;account_received_ms=account_received_ms_;
}
bool BrokerQueryAdapter::account_observation(std::array<double,10>& values) const {
    assert_owner();require(selected_&&bound_,"qmt_query_context_account_mode");
    if(!account_known_)return false;values=account_;return true;
}
double BrokerQueryAdapter::query_undone(const char* code) const {
    assert_owner();
    require(selected_ && bound_ && query_valid_, "qmt_query_context_not_ready");
    return const_cast<BrokerQueryAdapter*>(this)->TraderAdapter::getUndoneQty(code);
}
wtp::OrderMap* BrokerQueryAdapter::query_orders(const char* code) const {
    assert_owner();
    require(selected_ && bound_ && query_valid_, "qmt_query_context_not_ready");
    return const_cast<BrokerQueryAdapter*>(this)->TraderAdapter::getOrders(code);
}

BrokerQueryLocalExecuter::BrokerQueryLocalExecuter(wtp::WtExecuterFactory* factory, const char* name,
                                                 wtp::IDataManager* data, BrokerQueryAdapter& adapter)
    : WtLocalExecuter(factory, name, data), adapter_(adapter) { setTrader(&adapter); }
double BrokerQueryLocalExecuter::getUndoneQty(const char* code) {
    return adapter_.query_first() ? adapter_.query_undone(code) : WtLocalExecuter::getUndoneQty(code);
}
wtp::OrderMap* BrokerQueryLocalExecuter::getOrders(const char* code) {
    return adapter_.query_first() ? adapter_.query_orders(code) : WtLocalExecuter::getOrders(code);
}
void BrokerQueryLocalExecuter::replay_account() {
    std::array<double,10> value;
    if(adapter_.query_first()&&adapter_.account_observation(value))
        WtLocalExecuter::on_account("CNY",value[0],value[1],value[2],value[3],value[4],
            value[5],value[6],value[7],value[8],value[9]);
}
void BrokerQueryLocalExecuter::configure_attribution(AttributionObserver observer,const std::string& execution_id,const std::string& instance_id){
    require(observer&&!attribution_&&!execution_id.empty()&&!instance_id.empty(),"account_attribution_registration");
    attribution_=observer;attribution_execution_id_=execution_id;attribution_instance_id_=instance_id;
}
void BrokerQueryLocalExecuter::set_position(const wtp::wt_hashmap<std::string,double>& values) {
    if(adapter_.query_first())adapter_.assert_owner();
    if(attribution_){
        rapidjson::Document event;event.SetObject();auto& a=event.GetAllocator();
        attribution_text(event,"execution_id",attribution_execution_id_,a);rapidjson::Value rows(rapidjson::kArrayType);
        std::map<std::string,double> ordered(values.begin(),values.end());
        for(const auto& item:ordered){rapidjson::Value row(rapidjson::kObjectType);attribution_text(row,"symbol",item.first,a);
            attribution_number(row,"quantity",item.second,a);rows.PushBack(row,a);}
        event.AddMember("targets",rows,a);attribution_notify(attribution_,GH_ATTR_COMMIT,2,event);
    }
    WtLocalExecuter::set_position(values);
    // 新单元此时尚无首tick；在其首次计算前交付初始化时已查询的账户原值。
    replay_account();
}
void BrokerQueryLocalExecuter::on_position_changed(const char* code,double quantity) {
    if(adapter_.query_first())adapter_.assert_owner();
    if(attribution_){rapidjson::Document event;event.SetObject();auto& a=event.GetAllocator();
        attribution_text(event,"execution_id",attribution_execution_id_,a);attribution_text(event,"symbol",code,a);
        attribution_number(event,"quantity_delta",quantity,a);attribution_notify(attribution_,GH_ATTR_DELTA,2,event);}
    WtLocalExecuter::on_position_changed(code,quantity);replay_account();
}
wtp::OrderIDs BrokerQueryLocalExecuter::submit(const char* code, double price, double quantity, bool force, bool buy) {
    if (!adapter_.query_first()) return buy ? WtLocalExecuter::buy(code, price, quantity, force) : WtLocalExecuter::sell(code, price, quantity, force);
    adapter_.assert_owner();
    std::array<double,10> account;
    std::string canonical_price;
    if(attribution_){
        require(code&&std::strlen(code)<64,"account_attribution_symbol_invalid");
        const auto* commodity=getCommodityInfo(code);
        canonical_price=standard_order_price_text(price,commodity?commodity->getPriceTick():0);
        rapidjson::Document event;event.SetObject();auto& a=event.GetAllocator();
        attribution_text(event,"execution_id",attribution_execution_id_,a);attribution_text(event,"instance_id",attribution_instance_id_,a);
        attribution_text(event,"symbol",code,a);attribution_text(event,"side",buy?"buy":"sell",a);
        attribution_text(event,"limit_price_cny",canonical_price,a);attribution_number(event,"requested_quantity",quantity,a);
        const bool known=adapter_.account_observation(account);event.AddMember("account_known",known,a);
        if(known)attribution_number(event,"account_available_cny",account[3],a);else event.AddMember("account_available_cny",rapidjson::Value(),a);
        GhAttributionReplyV1 reply{sizeof(reply),1,-1,0,0};
        require(attribution_call(attribution_,GH_ATTR_AUTHORIZE,2,0,0,event,reply)==0,"account_attribution_authorize_failed");
        if(reply.decision==1&&reply.authorized_quantity==0){observation_=SubmissionViewV1{};observation_.decision=SubmissionDecision::BlockedAttribution;return {};}
        const auto approved=reply.authorized_quantity;
        require(reply.decision==0&&std::isfinite(approved)&&approved>0&&approved<=quantity&&std::floor(approved)==approved
            &&(!buy||std::fmod(approved,100.)==0),"account_attribution_quantity_invalid");
        quantity=approved;
    }
    if(buy&&(!adapter_.account_observation(account)||account[3]<=0||!std::isfinite(price)||!std::isfinite(quantity)
        ||price<=0||quantity<=0||static_cast<long double>(price)*quantity>account[3])){
        observation_=SubmissionViewV1{};observation_.decision=SubmissionDecision::BlockedFunds;
        return {};
    }
    require(code && std::strlen(code) < 64, "qmt_query_context_symbol");
    const auto security = CodeHelper::extractStdCode(code, nullptr);
    SubmissionKeyV1 key;
    require(std::strlen(security._exchg) < sizeof(key.exchange) && std::strlen(security._code) == 6,
            "qmt_query_context_security");
    std::strcpy(key.exchange, security._exchg); std::strcpy(key.code, security._code); key.side = buy ? 0 : 1;
    QueryFirstSubmission gate(adapter_.context_api(), adapter_.submission_functions(), true);
    auto group_event=[&](const SubmissionTokenV1& token){
        rapidjson::Document event;event.SetObject();auto& a=event.GetAllocator();
        attribution_text(event,"execution_id",attribution_execution_id_,a);attribution_text(event,"instance_id",attribution_instance_id_,a);
        attribution_uint(event,"native_generation",token.generation,a);attribution_uint(event,"group_id",token.group_id,a);
        attribution_text(event,"symbol",code,a);attribution_text(event,"side",buy?"buy":"sell",a);
        attribution_number(event,"quantity",quantity,a);attribution_text(event,"limit_price_cny",canonical_price,a);
        return event;
    };
    auto before=[&](const SubmissionTokenV1& token){if(attribution_){auto event=group_event(token);attribution_notify(attribution_,GH_ATTR_GROUP,2,event);}};
    auto after=[&](const SubmissionTokenV1& token,const SubmissionViewV1& view,SubmissionOutcome outcome){if(attribution_){
        auto event=group_event(token);auto& a=event.GetAllocator();attribution_uint(event,"accepted_children",view.accepted_children,a);
        attribution_uint(event,"decision",static_cast<uint32_t>(view.decision),a);attribution_uint(event,"outcome",static_cast<uint32_t>(outcome),a);
        attribution_notify(attribution_,GH_ATTR_GROUP_END,2,event);
    }};
    auto result=gate.invoke(key, observation_, [&] {
        return buy ? WtLocalExecuter::buy(code, price, quantity, force) : WtLocalExecuter::sell(code, price, quantity, force);
    },before,after);
    adapter_.remember_submission(code,buy,result);return result;
}
wtp::OrderIDs BrokerQueryLocalExecuter::buy(const char* code, double price, double quantity, bool force) {
    return submit(code, price, quantity, force, true);
}
wtp::OrderIDs BrokerQueryLocalExecuter::sell(const char* code, double price, double quantity, bool force) {
    return submit(code, price, quantity, force, false);
}
void BrokerQueryLocalExecuter::on_trade(std::uint32_t id,const char* code,bool buy,double quantity,double price){
    adapter_.observe_trade_origin(id,code,buy);WtLocalExecuter::on_trade(id,code,buy,quantity,price);
}
}
