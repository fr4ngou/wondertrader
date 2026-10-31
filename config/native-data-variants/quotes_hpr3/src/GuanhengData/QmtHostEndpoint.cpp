#include "QmtHostEndpoint.h"
#include "QmtTickMapping.h"
#include <algorithm>
#include <chrono>

namespace guanheng
{
namespace
{
Status fail(ErrorCode code,const char* reason){return {code,reason};}
std::uint32_t remaining(std::chrono::steady_clock::time_point until)
{
    auto value=std::chrono::duration_cast<std::chrono::milliseconds>(until-std::chrono::steady_clock::now()).count();
    return value>0?static_cast<std::uint32_t>(value):0;
}
}
QmtHostEndpoint::QmtHostEndpoint(std::shared_ptr<QmtHostReadClient> client,QmtHttpProfile profile,std::size_t full_tick_batch_size)
    :client_(std::move(client)),profile_(std::move(profile)),owner_(std::this_thread::get_id()),
    full_tick_batch_size_(full_tick_batch_size){}
QmtHostEndpoint::~QmtHostEndpoint()
{
    receiver_={};prepared_=false;
    // client最后引用析构时，其HTTP owner保留UNLOAD_NOTIFY事件至回调返回。
    // 外层worker尚未done；外部stop仍按自己的总截止返回并保留worker/DLL。
    client_.reset();
}
Status QmtHostEndpoint::check()const
{return owner_==std::this_thread::get_id()?Status{}:fail(ErrorCode::InvalidInput,"qmt_host_endpoint_owner_required");}
Status QmtHostEndpoint::prepare(std::uint32_t milliseconds)
{
    auto status=check();if(!status.ok())return status;
    if(receiver_)return fail(ErrorCode::Conflict,"qmt_host_receiver_active");
    prepared_=false;
    if(!full_tick_batch_size_||full_tick_batch_size_>200)return fail(ErrorCode::InvalidInput,"qmt_host_batch_size_invalid");
    status=qmt_mapping::check_profile(profile_);if(!status.ok())return status;
    if(!profile_.full_tick_cumulative||!client_)return fail(ErrorCode::Unavailable,"qmt_host_full_snapshot_profile_required");
    status=client_->prepare(milliseconds);if(!status.ok())return status;
    source_=client_->session();if(source_.provider!=ProviderKind::Qmt||source_.instance_id.empty()||source_.session_id.empty()||!source_.generation)
        return fail(ErrorCode::Unavailable,"qmt_host_transport_identity_required");
    prepared_=true;return {};
}
Capability QmtHostEndpoint::snapshot_capability()const
{
    if(!check().ok()||!prepared_||!client_||!profile_.full_tick_cumulative||!qmt_mapping::check_profile(profile_).ok()
        ||!same_session(source_,client_->session()))return {false,Qualification::Unavailable,"qmt_host_snapshot_unavailable"};
    return client_->capability();
}
SourceSession QmtHostEndpoint::session()const{return check().ok()?source_:SourceSession{};}
Status QmtHostEndpoint::start(Receiver receiver)
{
    auto status=check();if(!status.ok())return status;
    if(!receiver)return fail(ErrorCode::InvalidInput,"qmt_host_receiver_required");
    if(receiver_)return fail(ErrorCode::Conflict,"qmt_host_receiver_active");
    if(!snapshot_capability().supported)return fail(ErrorCode::Unavailable,"qmt_host_not_prepared");
    receiver_=std::move(receiver);return {};
}
Status QmtHostEndpoint::stop()
{
    auto status=check();if(!status.ok())return status;
    receiver_={};prepared_=false;return client_?client_->drain_callbacks(0):Status{};
}
Status QmtHostEndpoint::subscriptions(const wtp::CodeSet& codes)
{
    auto status=check();if(!status.ok())return status;
    if(codes.size()>(full_tick_batch_size_>1?10000:200))return fail(ErrorCode::Backpressure,"qmt_host_subscription_limit");
    try{std::vector<std::string> candidate;for(const auto& code:codes){qmt_mapping::qmt_symbol(code);candidate.push_back(code);}
        codes_=std::move(candidate);cursor_=0;++revision_;return {};}
    catch(...){return fail(ErrorCode::InvalidInput,"qmt_host_symbol_invalid");}
}
Status QmtHostEndpoint::pump(std::size_t limit,std::uint32_t milliseconds)
{
    auto status=check();if(!status.ok())return status;
    if(!limit||limit>4096||!milliseconds||milliseconds>30000)return fail(ErrorCode::InvalidInput,"qmt_host_pump_budget_invalid");
    if(!receiver_||!snapshot_capability().supported)return fail(ErrorCode::Unavailable,"qmt_host_receiver_unavailable");
    auto until=std::chrono::steady_clock::now()+std::chrono::milliseconds(milliseconds);
    const auto codes=codes_;const auto count=std::min(limit,codes.size()),revision=revision_;
    for(std::size_t i=0;i<count;)
    {
        if(!receiver_||revision!=revision_)break;
        const auto size=std::min(full_tick_batch_size_,count-i);
        std::vector<std::string> batch;batch.reserve(size);
        std::string arguments="{\"stocks\":[";
        for(std::size_t n=0;n<size;++n)
        {
            batch.push_back(codes[(cursor_+i+n)%codes.size()]);
            if(n)arguments+=',';
            arguments+='\"'+qmt_mapping::qmt_symbol(batch.back())+'\"';
        }
        arguments+="]}";
        const auto budget=remaining(until);if(!budget)return fail(ErrorCode::Timeout,"qmt_host_pump_deadline");
        auto value=client_->read_full_tick(arguments,budget);
        if(!value.result.status.ok())return value.result.status;
        if(!same_session(source_,client_->session())){prepared_=false;receiver_={};return fail(ErrorCode::StaleSession,"qmt_host_source_changed");}
        std::vector<MarketSnapshot> snapshots;
        try{snapshots=qmt_mapping::map_ticks(batch,value.result.data_json,profile_,source_);}
        catch(...){return fail(ErrorCode::InvalidInput,"qmt_host_snapshot_invalid");}
        // 整批先校验；stop/退订的重入在每个 SPI 准入前继续检查，同 pump 不重置截止。
        for(const auto& snapshot:snapshots)
        {
            if(!receiver_||revision!=revision_)break;
            if(!remaining(until))return fail(ErrorCode::Timeout,"qmt_host_pump_deadline");
            const auto receive=receiver_;
            try{status=receive(snapshot);if(!status.ok())return status;}
            catch(...){receiver_={};return fail(ErrorCode::SubmissionUnknown,"qmt_host_receiver_outcome_unknown");}
        }
        i+=size;
    }
    if(revision==revision_&&!codes_.empty())cursor_=(cursor_+count)%codes_.size();return {};
}
}
