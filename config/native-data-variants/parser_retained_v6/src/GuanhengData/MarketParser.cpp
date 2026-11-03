#include "MarketParser.h"
#include "../Includes/WTSDataDef.hpp"
#include <algorithm>
#include <cmath>
#include <cstring>
#include <stdexcept>

namespace guanheng
{
namespace
{
bool canonical(const std::string& input,std::string& output)
{
    auto first=input.find('.'),last=input.rfind('.');
    if (first==std::string::npos) return false;
    auto exchange=input.substr(0,first),code=input.substr(last+1);
    if ((exchange!="SSE" && exchange!="SZSE") || code.size()!=6
        || !std::all_of(code.begin(),code.end(),[](char c){return c>='0'&&c<='9';})) return false;
    if (first!=last)
    {
        auto product=input.substr(first+1,last-first-1);
        if (product!="STK" && product!="ETF" && product!="IDX") return false;
    }
    output=exchange+"."+code; return true;
}
bool valid_date(std::uint32_t date)
{
    auto year=date/10000,month=date/100%100,day=date%100;
    if (year<2004||year>2099||month<1||month>12||day<1) return false;
    const unsigned days[]={31,28,31,30,31,30,31,31,30,31,30,31};
    return day<=days[month-1]+(month==2&&year%4==0&&(year%100!=0||year%400==0));
}
bool valid_tick(const wtp::WTSTickStruct& t)
{
    if (!std::memchr(t.exchg,0,sizeof t.exchg)||!std::memchr(t.code,0,sizeof t.code)) return false;
    if (!valid_date(t.action_date)||!valid_date(t.trading_date)||t.action_time/10000000>23
        ||t.action_time/100000%100>59||t.action_time/1000%100>59) return false;
    const double fields[]={t.price,t.open,t.high,t.low,t.settle_price,t.upper_limit,t.lower_limit,
        t.total_volume,t.volume,t.total_turnover,t.turn_over,t.open_interest,t.diff_interest,
        t.pre_close,t.pre_settle,t.pre_interest};
    for (auto v:fields) if (!std::isfinite(v)) return false;
    if (t.price<=0 ||t.low<=0||t.high<t.low||t.open<t.low||t.open>t.high
        ||t.price<t.low||t.price>t.high||t.total_volume<0||t.total_turnover<0
        ||t.volume<0||t.turn_over<0||t.open_interest<0||t.pre_close<0) return false;
    for (int i=0;i<10;++i)
        if (!std::isfinite(t.bid_prices[i])||!std::isfinite(t.ask_prices[i])
            ||!std::isfinite(t.bid_qty[i])||!std::isfinite(t.ask_qty[i])
            ||t.bid_prices[i]<0||t.ask_prices[i]<0||t.bid_qty[i]<0||t.ask_qty[i]<0) return false;
    return true;
}
}
MarketParser::MarketParser(ProviderKind provider,std::shared_ptr<IMarketEndpoint> endpoint,std::size_t limit,std::size_t source_instance_limit)
    :provider_(provider),endpoint_(std::move(endpoint)),subscription_limit_(limit),source_instance_limit_(source_instance_limit)
{
    if (!limit || limit>100000 || !source_instance_limit || source_instance_limit>100000)
        throw std::invalid_argument("订阅或来源实例预算非法");
}
MarketParser::~MarketParser() { release(); }
bool MarketParser::init(wtp::WTSVariant*) { return true; }
void MarketParser::registerSpi(wtp::IParserSpi* spi)
{
    std::lock_guard<std::recursive_mutex> lock(mutex_);spi_=spi;
}
void MarketParser::report(Status status)
{
    status_=std::move(status);
    if (!status_.ok()&&spi_) spi_->handleParserLog(wtp::LL_ERROR,status_.reason.c_str());
}
bool MarketParser::connect()
{
    std::lock_guard<std::recursive_mutex> lock(mutex_);
    if (connected_) return true;
    if (!endpoint_) {report({ErrorCode::Unavailable,"行情端点尚未接入"});return false;}
    try
    {
        auto cap=endpoint_->snapshot_capability();
        if (!cap.supported||cap.qualification==Qualification::Unavailable)
            {report({ErrorCode::Unavailable,cap.reason.empty()?"完整累计快照尚未具备资格":cap.reason});return false;}
        auto candidate=endpoint_->session();
        if (candidate.provider!=provider_||candidate.instance_id.empty()||candidate.session_id.empty()||!candidate.generation)
            {report({ErrorCode::InvalidInput,"行情来源会话非法"});return false;}
        auto key=std::make_pair(candidate.provider,candidate.instance_id);
        auto seen=source_generations_.find(key);
        if(seen!=source_generations_.end() && candidate.generation<=seen->second)
            {report({ErrorCode::StaleSession,"重新连接必须提供新的来源绑定代际"});return false;}
        if(seen==source_generations_.end() && source_generations_.size()>=source_instance_limit_)
            {report({ErrorCode::Backpressure,"来源实例代际表已满，保留全部旧实例拒绝依据"});return false;}
        source_generations_[key]=candidate.generation;source_=candidate;
        auto status=endpoint_->start([this](const MarketSnapshot& value){return receive(value);});
        if (!status.ok()) {endpoint_->stop();report(status);return false;}
        status=endpoint_->subscriptions(subscriptions_);
        if (!status.ok()) {endpoint_->stop();report(status);return false;}
        connected_=true;watermarks_.clear();status_={};
        if (spi_) spi_->handleEvent(wtp::WPE_Connect,0);
        if (connected_&&spi_) spi_->handleEvent(wtp::WPE_Login,0);
        return connected_;
    }
    catch (const std::exception& e)
    {
        try {endpoint_->stop();}catch (...){}
        connected_=false;report({ErrorCode::Unavailable,e.what()});return false;
    }
}
bool MarketParser::disconnect()
{
    std::lock_guard<std::recursive_mutex> lock(mutex_);
    bool was_connected=connected_;connected_=false;watermarks_.clear();
    Status status;
    try {if (endpoint_) status=endpoint_->stop();}
    catch(const std::exception& e){status={ErrorCode::Unavailable,e.what()};}
    if (was_connected&&spi_) spi_->handleEvent(wtp::WPE_Close,status.ok()?0:1);
    if (!status.ok()) report(status);
    return status.ok();
}
void MarketParser::release()
{
    std::lock_guard<std::recursive_mutex> lock(mutex_);
    disconnect();spi_=nullptr;subscriptions_.clear();
}
bool MarketParser::isConnected()
{
    std::lock_guard<std::recursive_mutex> lock(mutex_);return connected_;
}
void MarketParser::subscribe(const wtp::CodeSet& codes)
{
    std::lock_guard<std::recursive_mutex> lock(mutex_);
    auto candidate=subscriptions_;
    for(const auto& code:codes)
    {
        std::string key;if(!canonical(code,key)){report({ErrorCode::InvalidInput,"订阅证券非法"});return;}
        candidate.insert(key);
    }
    if(candidate.size()>subscription_limit_){report({ErrorCode::Backpressure,"订阅数量超过预算"});return;}
    try
    {
        if(connected_){auto status=endpoint_->subscriptions(candidate);if(!status.ok()){report(status);return;}}
        subscriptions_=std::move(candidate);status_={};
    }
    catch(const std::exception& e){report({ErrorCode::Unavailable,e.what()});}
}
void MarketParser::unsubscribe(const wtp::CodeSet& codes)
{
    std::lock_guard<std::recursive_mutex> lock(mutex_);
    auto candidate=subscriptions_;
    for(const auto& code:codes)
    {
        std::string key;if(!canonical(code,key)){report({ErrorCode::InvalidInput,"退订证券非法"});return;}
        candidate.erase(key);
    }
    try
    {
        if(connected_){auto status=endpoint_->subscriptions(candidate);if(!status.ok()){report(status);return;}}
        for(const auto& key:subscriptions_) if(!candidate.count(key)) watermarks_.erase(key);
        subscriptions_=std::move(candidate);status_={};
    }
    catch(const std::exception& e){report({ErrorCode::Unavailable,e.what()});}
}
Status MarketParser::last_status() const
{
    std::lock_guard<std::recursive_mutex> lock(mutex_);return status_;
}
Status MarketParser::pump(std::size_t limit,std::uint32_t deadline_ms)
{
    std::lock_guard<std::recursive_mutex> lock(mutex_);
    if(!connected_) return {ErrorCode::Unavailable,"行情未连接"};
    if(!limit||limit>4096||!deadline_ms||deadline_ms>60000) return {ErrorCode::InvalidInput,"行情轮询预算非法"};
    try
    {
        auto status=endpoint_->pump(limit,deadline_ms);
        if(!status.ok()){disconnect();report(status);}
        return status;
    }
    catch(const std::exception& e){disconnect();report({ErrorCode::Unavailable,e.what()});return status_;}
}
Status MarketParser::receive(const MarketSnapshot& snapshot)
{
    std::lock_guard<std::recursive_mutex> lock(mutex_);
    Status rejected;
    if(!connected_||!same_session(snapshot.source,source_)) rejected={ErrorCode::StaleSession,"行情来自已退出会话"};
    else if(!endpoint_->snapshot_capability().supported
        ||endpoint_->snapshot_capability().qualification==Qualification::Unavailable)
        rejected={ErrorCode::Unavailable,"完整累计快照资格已丢失"};
    else if(!snapshot.full_cumulative||!snapshot.source_time_verified) rejected={ErrorCode::Unavailable,"行情缺少合格完整快照或来源时间"};
    else if(!valid_tick(snapshot.tick)) rejected={ErrorCode::InvalidInput,"行情时间、价格或量额非法"};
    else
    {
        const auto& t=snapshot.tick;std::string key=std::string(t.exchg)+"."+t.code,validated;
        if(!canonical(key,validated)||!subscriptions_.count(key)) rejected={ErrorCode::InvalidInput,"行情证券尚未订阅"};
        else
        {
            auto time=std::uint64_t(t.action_date)*1000000000ULL+t.action_time;
            auto found=watermarks_.find(key);
            if(found!=watermarks_.end()&&time<=found->second) rejected={ErrorCode::Conflict,"重复或倒序行情"};
            else
            {
                watermarks_[key]=time;
                // 完整复制，WT 在回调后仍可通过 retain 延长对象生命周期。
                auto copy=t;auto* tick=wtp::WTSTickData::create(copy);
                try {if(spi_)spi_->handleQuote(tick,1);}
                catch(...){tick->release();throw;}
                tick->release();status_={};return {};
            }
        }
    }
    report(rejected);return rejected;
}
}
