#ifndef NOMINMAX
#define NOMINMAX
#endif
#include "QmtHttpEndpoint.h"
#include "QmtTickMapping.h"
#include <rapidjson/document.h>
#include <rapidjson/stringbuffer.h>
#include <rapidjson/writer.h>
#include <windows.h>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <stdexcept>

namespace guanheng
{
namespace
{
using namespace qmt_mapping;
std::uint32_t remaining(std::chrono::steady_clock::time_point until)
{
    auto ms=std::chrono::duration_cast<std::chrono::milliseconds>(until-std::chrono::steady_clock::now()).count();
    return ms>0?static_cast<std::uint32_t>(ms):0;
}
}

QmtHttpEndpoint::QmtHttpEndpoint(std::shared_ptr<QmtHttpClient> client,QmtHttpProfile profile)
    :client_(std::move(client)),profile_(std::move(profile)),owner_(std::this_thread::get_id()){}
Status QmtHttpEndpoint::check_thread() const
{return owner_==std::this_thread::get_id()?Status{}:invalid("HTTP 行情端点限创建线程调用");}
Status QmtHttpEndpoint::check_profile() const
{
    return qmt_mapping::check_profile(profile_);
}

Status QmtHttpEndpoint::prepare(std::uint32_t deadline_ms)
{
    auto status=check_thread();if(!status.ok())return status;
    if(receiver_)return {ErrorCode::Conflict,"准备新会话前须停止行情接收"};
    prepared_=false;status=check_profile();if(!status.ok())return status;
    if(!client_)return {ErrorCode::Unavailable,"QMT HTTP 客户端缺失"};
    status=client_->prepare(deadline_ms);if(!status.ok())return status;
    source_=client_->session();
    if(source_.provider!=ProviderKind::Qmt||source_.instance_id.empty()||source_.session_id.empty()||!source_.generation)
        return {ErrorCode::Unavailable,"HTTP 源身份不完整"};
    prepared_=true;return {};
}
Capability QmtHttpEndpoint::capability(const char* operation) const
{
    auto status=check_thread();if(!status.ok())return {false,Qualification::Unavailable,status.reason};
    status=check_profile();if(!status.ok()||!prepared_||!client_)return {false,Qualification::Unavailable,"HTTP 行情端点未准备或缺少 profile"};
    if(!same_source(source_,client_->session()))return {false,Qualification::Unavailable,"HTTP 源会话已变更"};
    auto cap=client_->capability(operation);
    if(!cap.supported||cap.qualification==Qualification::Unavailable)return cap;
    return {true,Qualification::NativeVerified,"显式源 profile 的隔离原生 HTTP 接入；真实终端资格待验真"};
}
Capability QmtHttpEndpoint::snapshot_capability() const
{
    if(!profile_.full_tick_cumulative)return {false,Qualification::Unavailable,"profile 未确认完整累计快照"};
    return capability("market.full_tick");
}
Capability QmtHttpEndpoint::history_capability() const
{
    auto result=capability("market.market_data_ex");if(!result.supported)return result;
    auto tick=client_->capability("market.full_tick");
    if(!tick.supported||tick.qualification==Qualification::Unavailable)
        return {false,Qualification::Unavailable,"历史闭合需要同会话 QMT full_tick 时间能力"};
    return result;
}
SourceSession QmtHttpEndpoint::session() const{return check_thread().ok()?source_:SourceSession{};}
Status QmtHttpEndpoint::check_session()
{
    if(!prepared_||!client_)return {ErrorCode::Unavailable,"HTTP 行情端点尚未准备"};
    if(!same_source(source_,client_->session()))
    {prepared_=false;receiver_={};return {ErrorCode::StaleSession,"HTTP 源会话已变更，需要重新准备"};}
    return {};
}
Status QmtHttpEndpoint::start(Receiver receiver)
{
    auto status=check_thread();if(!status.ok())return status;
    if(!receiver)return invalid("行情接收者为空");
    if(!snapshot_capability().supported)return {ErrorCode::Unavailable,"完整累计行情能力不可用"};
    if(receiver_)return {ErrorCode::Conflict,"行情接收已经启动"};
    receiver_=std::move(receiver);return {};
}
Status QmtHttpEndpoint::stop()
{auto status=check_thread();if(!status.ok())return status;receiver_={};return {};}
Status QmtHttpEndpoint::subscriptions(const wtp::CodeSet& codes)
{
    auto status=check_thread();if(!status.ok())return status;
    if(codes.size()>200)return {ErrorCode::Backpressure,"HTTP 行情订阅超过 200 证券预算"};
    try
    {
        std::vector<std::string> validated;for(const auto& code:codes){qmt_symbol(code);validated.push_back(code);}
        codes_=std::move(validated);cursor_=0;++subscription_revision_;return {};
    }
    catch(const std::exception&){return invalid("证券必须为 SSE/SZSE 加六位代码");}
}
Status QmtHttpEndpoint::pump(std::size_t limit,std::uint32_t deadline_ms)
{
    auto status=check_thread();if(!status.ok())return status;
    if(!limit||limit>4096||!deadline_ms||deadline_ms>30000)return invalid("HTTP 行情轮询预算非法");
    status=check_session();if(!status.ok())return status;
    if(!receiver_)return {ErrorCode::Unavailable,"HTTP 行情接收尚未启动"};
    auto until=std::chrono::steady_clock::now()+std::chrono::milliseconds(deadline_ms);
    // 复制订阅和接收者，回调重入 stop/subscriptions 时不持悬空引用。
    auto codes=codes_;auto count=std::min(limit,codes.size());auto revision=subscription_revision_;
    for(std::size_t n=0;n<count;++n)
    {
        if(!receiver_||revision!=subscription_revision_)break;
        auto code=codes[(cursor_+n)%codes.size()];auto symbol=qmt_symbol(code);
        auto budget=remaining(until);if(!budget)return {ErrorCode::Timeout,"HTTP 行情总截止已到"};
        auto result=client_->read_operation("market.full_tick","{\"stocks\":[\""+symbol+"\"]}",budget);
        if(!result.status.ok()){if(result.status.code==ErrorCode::StaleSession){prepared_=false;receiver_={};}return result.status;}
        status=check_session();if(!status.ok())return status;
        MarketSnapshot snapshot;
        try
        {
            snapshot=qmt_mapping::map_tick(code,result.data_json,profile_,source_);
            if(!remaining(until))return {ErrorCode::Timeout,"HTTP 行情总截止已到"};
        }
        catch(const std::exception&){return invalid("QMT 快照缺字段、时间或完整累计价格量额不合格");}
        auto receive=receiver_;
        try {status=receive(snapshot);if(!status.ok())return status;}
        catch(...){receiver_={};return {ErrorCode::Unavailable,"行情消费者结果未知，已停止接收"};}
    }
    if(revision==subscription_revision_&&!codes_.empty())cursor_=(cursor_+count)%codes_.size();
    return {};
}
HistoryPage QmtHttpEndpoint::fetch(const MinuteRequest& request,std::size_t limit,std::uint32_t deadline_ms)
{
    HistoryPage page;page.status=check_thread();if(!page.status.ok())return page;
    if(!limit||limit>1000000||!deadline_ms||deadline_ms>30000){page.status=invalid("HTTP 历史预算非法");return page;}
    page.status=check_session();if(!page.status.ok())return page;
    if(!history_capability().supported){page.status={ErrorCode::Unavailable,"HTTP 分钟历史能力不可用"};return page;}
    try
    {
        auto symbol=qmt_symbol(request.exchange+"."+request.code);
        auto from=request_epoch(request.from),to=request_epoch(request.to);
        if(from>to)throw std::invalid_argument("历史请求范围非法");
        // QMT count 可能返回尾部记录。限制连续时钟窗口，调用方按窗口分解长范围；
        // 页完整性仍单独核对 count，禁止假定截断方向或跳过较早缺口。
        if(to-from>72*60*60000ULL){page.status={ErrorCode::Backpressure,"历史单次窗口超过 72 小时，请缩小范围"};return page;}
        auto until=std::chrono::steady_clock::now()+std::chrono::milliseconds(deadline_ms);
        auto count=std::min<std::size_t>(limit,5000);auto shift=profile_.minute_boundary=="left"?60000ULL:0;
        auto args=std::string("{\"fields\":[\"time\",\"open\",\"high\",\"low\",\"close\",\"volume\",\"amount\"],\"stock_codes\":[\"")+symbol+
            "\"],\"period\":\"1m\",\"start_time\":\""+qmt_time(from-shift)+"\",\"end_time\":\""+qmt_time(to-shift)+
            "\",\"count\":"+std::to_string(count)+",\"dividend_type\":\"none\",\"fill_data\":false,\"subscribe\":false}";
        auto budget=remaining(until);if(!budget){page.status={ErrorCode::Timeout,"HTTP 历史总截止已到"};return page;}
        auto result=client_->read_operation("market.market_data_ex",args,budget);
        if(!result.status.ok()){page.status=result.status;if(result.status.code==ErrorCode::StaleSession){prepared_=false;receiver_={};}return page;}
        page.status=check_session();if(!page.status.ok())return page;
        // health.last_tick_at 是 Host wall-clock 存活观察。闭合依据取自相同会话、
        // 相同总截止内 QMT 返回的该证券 full_tick.time，缺失时保持未知。
        budget=remaining(until);if(!budget){page.status={ErrorCode::Timeout,"HTTP 历史总截止已到"};return page;}
        auto observation=client_->read_operation("market.full_tick","{\"stocks\":[\""+symbol+"\"]}",budget);
        if(!observation.status.ok())
        {page.status=observation.status;if(page.status.code==ErrorCode::StaleSession){prepared_=false;receiver_={};}return page;}
        page.status=check_session();if(!page.status.ok())return page;
        std::uint64_t clock=0;
        try
        {
            auto tick=parse(observation.data_json);if(tick.MemberCount()!=1)throw std::invalid_argument("tick 证券范围不一致");
            clock=epoch_of(member(tick,symbol.c_str()));
        }
        catch(const std::exception&){page.status={ErrorCode::Unavailable,"缺少同会话 QMT tick.time，分钟闭合资格未知"};return page;}
        auto data=parse(result.data_json);
        if(data.MemberCount()!=1)throw std::invalid_argument("历史证券范围不一致");
        const auto& rows=member(data,symbol.c_str());if(!rows.IsArray())throw std::invalid_argument("历史必须为带明确时间的 records");
        if(rows.Size()>count){page.status={ErrorCode::Backpressure,"源历史返回超过请求条数"};return page;}
        std::uint64_t previous=0,next_minute=from;
        bool covers_natural_window=true;
        for(const auto& row:rows.GetArray())
        {
            auto epoch=epoch_of(row);if(epoch%60000)throw std::invalid_argument("源分钟未对齐格点");
            auto right=epoch+shift;
            if(right<from||right>to||right<=previous)throw std::invalid_argument("历史越界、重复或乱序");
            if(right!=next_minute)covers_natural_window=false;
            next_minute=right+60000;
            if(right>clock){page.status={ErrorCode::Pending,"源时钟尚未证明分钟闭合"};page.bars.clear();return page;}
            auto time=from_epoch(right,true);wtp::WTSBarStruct bar;bar.date=date_of(time);
            bar.time=(std::uint64_t(bar.date)-19900000)*10000+time.wHour*100+time.wMinute;
            bar.open=number(row,"open");bar.high=number(row,"high");bar.low=number(row,"low");bar.close=number(row,"close");
            bar.vol=number(row,"volume")*profile_.volume_to_shares;bar.money=number(row,"amount")*profile_.amount_to_yuan;
            validate_prices(bar.open,bar.high,bar.low,bar.close,bar.vol,bar.money);page.bars.push_back(bar);previous=right;
        }
        auto& metadata=page.metadata;metadata.source=source_;metadata.qualification=Qualification::NativeVerified;
        metadata.dataset_version=profile_.version;metadata.source_license=profile_.source_license;
        metadata.volume_to_shares=profile_.volume_to_shares;metadata.amount_to_yuan=profile_.amount_to_yuan;
        // 源 owner 逐个核实际自然分钟集合；小 limit 用尽但全区间确已返回时可结束。
        // 该依据不使用 expected 网格，也不授予最终修订或证券覆盖完整资格。
        if(!remaining(until)){page.status={ErrorCode::Timeout,"HTTP 历史总截止已到"};page.bars.clear();return page;}
        page.complete=(rows.Size()<count || (covers_natural_window && next_minute==to+60000))&&to<=clock;return page;
    }
    catch(const std::exception&)
    {page.status=invalid("QMT 历史缺少明确 time、合法 OHLCV、顺序或请求边界依据");page.bars.clear();page.complete=false;return page;}
}
}
