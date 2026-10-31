#include "MinutePipeline.h"
#include "../Includes/IBaseDataMgr.h"
#include "../Includes/WTSContractInfo.hpp"
#include "../Includes/WTSDataDef.hpp"
#include "../Includes/WTSVariant.hpp"
#include "../Includes/WTSSessionInfo.hpp"
#include "../Share/TimeUtils.hpp"
#include <stdexcept>
#include <algorithm>

namespace guanheng
{
namespace
{
bool clock_valid(const MinuteClock& clock)
{
    auto y=clock.date/10000,m=clock.date/100%100,d=clock.date%100;
    if(!clock.verified||y<2004||y>2099||m<1||m>12||d<1)return false;
    const unsigned days[]={31,28,31,30,31,30,31,31,30,31,30,31};
    return d<=days[m-1]+(m==2&&y%4==0&&(y%100!=0||y%400==0))
        &&clock.action_time/10000000<24&&clock.action_time/100000%100<60&&clock.action_time/1000%100<60;
}
std::uint64_t endpoint(wtp::WTSContractInfo& contract,wtp::WTSTickData& tick)
{
    auto* session=contract.getCommInfo()->getSessionInfo();auto time=tick.actiontime()/100000;
    auto minutes=session->timeToMinutes(time,false);
    if(minutes==INVALID_UINT32)return 0;
    if(session->isLastOfSection(time)) {if(!minutes)return 0;--minutes;}
    auto end=session->minuteToTime(minutes+1);
    auto date=end==0?TimeUtils::getNextDate(tick.actiondate()):tick.actiondate();
    return std::uint64_t(date)*10000+end;
}
}
MinutePipeline::MinutePipeline(wtp::IDataWriter& writer,wtp::IDataReader& reader,wtp::IBaseDataMgr& basedata,
    Clock clock,Consumer consumer,std::size_t limit)
    :writer_(writer),reader_(reader),basedata_(basedata),clock_(std::move(clock)),consumer_(std::move(consumer)),
    owner_(std::this_thread::get_id()),subscription_limit_(limit)
{
    if(!clock_||!consumer_||!limit||limit>100000)throw std::invalid_argument("分钟管线依赖或预算非法");
}
Status MinutePipeline::initialize(wtp::WTSVariant* writer_config,wtp::WTSVariant* reader_config)
{
    if(!owner_thread()||initialized_||!writer_config||!reader_config||writer_config->getBoolean("async"))
        return status_={ErrorCode::InvalidInput,"分钟管线要求创建线程一次初始化且使用同步 writer"};
    if(!writer_.init(writer_config,this))return status_={ErrorCode::Unavailable,"WT 分钟 writer 初始化失败"};
    reader_.init(reader_config,this);initialized_=true;return status_={};
}
Status MinutePipeline::bind_source(const SourceSession& source,Qualification qualification,const std::string& baseline_evidence)
{
    if(quarantined_)return status_;
    if(!owner_thread()||active_||source.instance_id.empty()||source.session_id.empty()||!source.generation
        ||qualification==Qualification::Unavailable)
        return status_={ErrorCode::InvalidInput,"分钟来源必须在停止 Parser 后显式绑定合格会话"};
    source_=source;qualification_=qualification;source_bound_=true;
    // 已复用的 WT cache 含旧来源累计基线及 pending bucket，新来源证据不能重新授予它们归属。
    baseline_verified_=!ever_bound_&&!baseline_evidence.empty();ever_bound_=true;
    for(auto& entry:subscriptions_)
    {
        auto& state=entry.second;state.first_tick=true;state.warmup_through=0;
        state.isolate_through=std::max(state.isolate_through,state.last_written_bucket);
    }
    return status_={};
}
Status MinutePipeline::subscribe(const std::string& symbol)
{
    if(quarantined_)return status_;
    if(!owner_thread()||!initialized_||written_ticks_)
        return status_={ErrorCode::NotSupported,"固定分钟订阅须在首个 tick 前建立"};
    if(subscriptions_.count(symbol))return status_={};
    if(subscriptions_.size()>=subscription_limit_)return status_={ErrorCode::Backpressure,"分钟订阅预算已满"};
    auto first=symbol.find('.'),last=symbol.rfind('.');
    auto* contract=first==std::string::npos?nullptr:
        basedata_.getContract(symbol.substr(last+1).c_str(),symbol.substr(0,first).c_str());
    if(first==std::string::npos||first==last||symbol.substr(first+1,last-first-1)!="ETF"||!contract
        ||std::string(contract->getCommInfo()->getProduct())!="ETF")
        return status_={ErrorCode::InvalidInput,"当前分钟管线仅接已登记的标准 ETF 证券"};
    auto clock=clock_();if(!clock_valid(clock))return status_={ErrorCode::Unavailable,"分钟订阅缺少已验证时钟"};
    auto* slice=reader_.readKlineSlice(symbol.c_str(),wtp::KP_Minute1,1,std::uint64_t(clock.date)*10000+clock.action_time/100000);
    if(!slice)return status_={ErrorCode::Unavailable,"WT 分钟订阅注册失败"};
    slice->release();subscriptions_.emplace(symbol,Subscription{});return status_={};
}
void MinutePipeline::handleEvent(wtp::WTSParserEvent event,int32_t error)
{
    if(!owner_thread()||quarantined_)return;
    if(event==wtp::WPE_Close||event==wtp::WPE_Logout||error){active_=false;source_bound_=false;}
    else if(event==wtp::WPE_Login)active_=source_bound_;
}
void MinutePipeline::handleQuote(wtp::WTSTickData* tick,std::uint32_t procFlag)
{
    if(quarantined_)return;
    if(!owner_thread()||!initialized_||!active_||!tick||procFlag!=1)
        {status_={ErrorCode::Unavailable,"分钟管线仅接已绑定完整累计快照"};return;}
    auto* contract=basedata_.getContract(tick->code(),tick->exchg());
    if(!contract){status_={ErrorCode::InvalidInput,"分钟行情证券未登记"};return;}
    auto symbol=std::string(contract->getExchg())+".ETF."+contract->getCode();
    auto subscription=subscriptions_.find(symbol);
    if(subscription==subscriptions_.end()){status_={ErrorCode::InvalidInput,"分钟行情证券未订阅"};return;}
    auto clock=clock_();
    if(!clock_valid(clock)){status_={ErrorCode::Unavailable,"分钟写入缺少已验证时钟"};return;}
    if(std::uint64_t(tick->actiondate())*1000000000+tick->actiontime()
        >std::uint64_t(clock.date)*1000000000+clock.action_time)
        {status_={ErrorCode::Pending,"未来行情尚未到达已验证时钟"};return;}
    auto right=endpoint(*contract,*tick);
    if(!right){status_={ErrorCode::Unavailable,"行情时间位于交易时段之外"};return;}
    if(right<=closed_through_){status_={ErrorCode::Conflict,"行情对应分钟已闭合，拒绝修改已投递数据"};return;}
    tick->setContractInfo(contract);
    auto before=written_ticks_;
    if(!writer_.writeTick(tick,1)||before==written_ticks_)
        status_={ErrorCode::Unavailable,"WT 分钟 writer 未确认处理输入"};
    else
    {
        auto& state=subscription->second;
        if(state.first_tick){if(!baseline_verified_)state.warmup_through=right;state.first_tick=false;}
        state.last_written_bucket=std::max(state.last_written_bucket,right);
        status_={};
    }
}
Status MinutePipeline::close_through(std::uint32_t date,std::uint32_t minute)
{
    if(quarantined_)return status_;
    if(!owner_thread()||!initialized_||!active_)return status_={ErrorCode::Unavailable,"分钟管线尚未具备闭合资格"};
    auto clock=clock_();MinuteClock requested{date,minute*100000,true};
    if(!clock_valid(clock)||!clock_valid(requested))return status_={ErrorCode::InvalidInput,"闭合分钟或时钟缺少有效证据"};
    auto end=std::uint64_t(date)*10000+minute;
    if(end>std::uint64_t(clock.date)*10000+clock.action_time/100000)
        return status_={ErrorCode::Pending,"分钟尚未结束"};
    if(end<=closed_through_)return status_={ErrorCode::Conflict,"闭合时钟重复或倒退"};
    emitting_through_=end;status_={};
    try{reader_.onMinuteEnd(date,minute);}
    catch(...){emitting_through_=0;throw;}
    emitting_through_=0;closed_through_=end;return status_;
}
void MinutePipeline::on_bar(const char* symbol,wtp::WTSKlinePeriod period,wtp::WTSBarStruct* bar)
{
    if(quarantined_)return;
    auto found=symbol?subscriptions_.find(symbol):subscriptions_.end();
    auto time=bar?bar->time+199000000000ULL:0;
    if(!owner_thread()||!bar||period!=wtp::KP_Minute1||!emitting_through_
        ||time>emitting_through_||found==subscriptions_.end()||time<=found->second.delivered)
        {status_={ErrorCode::Conflict,"拒绝未闭合、重复或非订阅分钟事件"};return;}
    auto& state=found->second;state.delivered=time;
    if(state.first_tick||time<=state.warmup_through||time<=state.isolate_through){++suppressed_minutes_;return;}
    ClosedMinute event{symbol,*bar,source_,qualification_};
    try{consumer_(event);}
    catch(...)
    {
        quarantined_=true;active_=false;source_bound_=false;
        status_={ErrorCode::Unavailable,"分钟消费者调用结果未知，已隔离投递；核查后以新管线恢复"};
    }
}
std::uint32_t MinutePipeline::get_min_time()
{
    auto hhmm=clock_().action_time/100000;
    auto minutes=(hhmm/100*60+hhmm%100+1)%1440;return minutes/60*100+minutes%60;
}
}
