#include "QmtHostEndpoint.h"
#include "QmtTickMapping.h"
#include <algorithm>
#include <chrono>
#include <type_traits>
#include <stdexcept>

namespace guanheng
{
namespace
{
Status fail(ErrorCode code,const char* reason){return {code,reason};}
bool retryable_snapshot(const Status& status){
    if(status.code==ErrorCode::Pending||status.code==ErrorCode::Timeout||status.code==ErrorCode::SubmissionUnknown)return true;
    if(status.code==ErrorCode::Backpressure)return status.reason=="qmt_http_backpressure";
    if(status.code!=ErrorCode::IoError)return false;
    if(status.reason=="qmt_http_exchange_failed"||status.reason=="qmt_http_body_incomplete")return true;
    // 原HTTP层带固定状态码及可选已登记类别；保留认证/身份/坏结构的硬边界。
    for(const auto* code:{"500","502","503"}){
        const auto prefix=std::string("qmt_http_remote_failure:")+code;
        if(status.reason==prefix||status.reason.compare(0,prefix.size()+1,prefix+":")==0)return true;
    }
    return false;
}
std::uint32_t remaining(std::chrono::steady_clock::time_point until)
{
    auto value=std::chrono::duration_cast<std::chrono::milliseconds>(until-std::chrono::steady_clock::now()).count();
    return value>0?static_cast<std::uint32_t>(value):0;
}
}
QmtHostEndpoint::QmtHostEndpoint(std::shared_ptr<QmtHostReadClient> client,QmtHttpProfile profile,std::size_t full_tick_batch_size,bool retained)
    :retained_(retained),client_(std::move(client)),profile_(std::move(profile)),owner_(std::this_thread::get_id()),
    full_tick_batch_size_(full_tick_batch_size){}
QmtHostEndpoint::~QmtHostEndpoint()
{
    receiver_={};prepared_=false;
    // 未核清的读取由原worker继续持有；外层stop可超时并保留DLL，直到原责任结束。
    // 析构期间不准入新读取、不交付SPI，每轮只GET原ID或确认原消费。
    while(held_) {
        try { std::vector<MarketSnapshot> ignored;
            if(original_error_.ok())read_snapshots(held_codes_,std::chrono::steady_clock::now()+std::chrono::milliseconds(1000),ignored);
        } catch(...) {}
        if(held_)std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
    // client最后引用析构时，其HTTP owner保留UNLOAD_NOTIFY事件至回调返回。
    // 外层worker尚未done；外部stop仍按自己的总截止返回并保留worker/DLL。
    client_.reset();
}
Status QmtHostEndpoint::check()const
{return owner_==std::this_thread::get_id()?Status{}:fail(ErrorCode::InvalidInput,"qmt_host_endpoint_owner_required");}
Status QmtHostEndpoint::prepare(std::uint32_t milliseconds)
{
    auto status=check();if(!status.ok())return status;
    if(receiver_||held_)return fail(ErrorCode::Conflict,"qmt_host_receiver_active");
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
    receiver_={};prepared_=false;
    if(held_)return fail(ErrorCode::Pending,"qmt_host_original_snapshot_pending");
    return client_?client_->drain_callbacks(0):Status{};
}
Status QmtHostEndpoint::subscriptions(const wtp::CodeSet& codes)
{
    auto status=check();if(!status.ok())return status;
    if(codes.size()>(full_tick_batch_size_>1?10000:200))return fail(ErrorCode::Backpressure,"qmt_host_subscription_limit");
    try{std::vector<std::string> candidate;for(const auto& code:codes){qmt_mapping::qmt_symbol(code);candidate.push_back(code);}
        codes_=std::move(candidate);cursor_=0;++revision_;return {};}
    catch(...){return fail(ErrorCode::InvalidInput,"qmt_host_symbol_invalid");}
}
Status QmtHostEndpoint::read_snapshots(const std::vector<std::string>& codes,
    std::chrono::steady_clock::time_point until,std::vector<MarketSnapshot>& snapshots)
{
    if(!original_error_.ok())return original_error_;
    if(!held_) {
        // 所有请求参数及证券内存先准备，再进入可能提交的调用。
        std::string arguments="{\"stocks\":[";
        for(std::size_t n=0;n<codes.size();++n) {
            if(n)arguments+=',';arguments+='\"'+qmt_mapping::qmt_symbol(codes[n])+'\"';
        }
        arguments+="]}";
        const auto budget=remaining(until);if(!budget)return fail(ErrorCode::Timeout,"qmt_host_pump_deadline");
        if(retained_)held_codes_=codes;
        auto value=client_->read_full_tick(arguments,budget);
        if(!retained_) {
            if(!value.result.status.ok())return value.result.status;
            if(!same_session(source_,client_->session()))return fail(ErrorCode::StaleSession,"qmt_host_source_changed");
            try{snapshots=qmt_mapping::map_ticks(codes,value.result.data_json,profile_,source_);}
            catch(const std::invalid_argument&){return fail(ErrorCode::InvalidInput,"qmt_host_snapshot_invalid");}
            return {};
        }
        if(value.receipt.request_body.empty()){
            held_codes_.clear();
            if(value.result.status.code==ErrorCode::Timeout && value.result.status.reason=="qmt_host_deadline")
                return fail(ErrorCode::Timeout,"qmt_host_pump_deadline");
            return value.result.status;
        }
        static_assert(std::is_nothrow_move_constructible<QmtBoundResult>::value,"original receipt move must not allocate");
        held_.emplace(std::move(value));
    } else if(!mapped_) {
        const auto budget=remaining(until);if(!budget)return fail(ErrorCode::Pending,"qmt_host_original_snapshot_pending");
        auto value=client_->resume(held_->receipt,budget);
        *held_=std::move(value);
    }
    if(!mapped_) {
        if(!held_->snapshot_consumption_ready){
            if(!retryable_snapshot(held_->result.status)){original_error_=held_->result.status;return original_error_;}
            return fail(ErrorCode::Pending,"qmt_host_original_snapshot_pending");
        }
        held_status_=held_->result.status;
        if(held_status_.ok()) {
            if(!same_session(source_,client_->session())){original_error_=fail(ErrorCode::StaleSession,"qmt_host_source_changed");return original_error_;}
            try{held_snapshots_=qmt_mapping::map_ticks(held_codes_,held_->result.data_json,profile_,source_,true);}
            catch(const std::invalid_argument&){held_status_=fail(ErrorCode::InvalidInput,"qmt_host_snapshot_invalid");}
        }
        mapped_=true;
    }
    const auto budget=remaining(until);if(!budget)return fail(ErrorCode::Pending,"qmt_host_original_consumption_pending");
    auto status=client_->confirm_full_tick(*held_,budget);
    if(!status.ok()){
        if(!retryable_snapshot(status)){original_error_=std::move(status);return original_error_;}
        return fail(ErrorCode::Pending,"qmt_host_original_consumption_pending");
    }
    // ACK前完整原结果和全部映射均在此owner；ACK丢失只重确认，不再次SDK读取。
    snapshots=std::move(held_snapshots_);status=std::move(held_status_);
    held_.reset();held_codes_.clear();mapped_=false;return status;
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
        for(std::size_t n=0;n<size;++n)batch.push_back(codes[(cursor_+n)%codes.size()]);
        const auto original_codes=held_?held_codes_:batch;
        std::vector<MarketSnapshot> snapshots;
        status=read_snapshots(batch,until,snapshots);
        // retained轮询层识别原结果/ACK等待并保持连接；原事件时间由消费者核验。
        if(!status.ok())return status;
        // 已退订的旧请求仍须确认消费；完成后按本代订阅准入，不交付旧证券。
        if(original_codes!=batch)continue;
        // 已确认消费的整批先记轮转进度；投递阶段用完预算也要让后续证券获得下轮机会。
        cursor_=(cursor_+size)%codes.size();
        i+=size;
        // 整批先校验；stop/退订的重入在每个 SPI 准入前继续检查，同 pump 不重置截止。
        for(const auto& snapshot:snapshots)
        {
            if(!receiver_||revision!=revision_)break;
            if(!remaining(until))return fail(ErrorCode::Timeout,"qmt_host_pump_deadline");
            const auto receive=receiver_;
            try{status=receive(snapshot);if(!status.ok())return status;}
            catch(...){receiver_={};return fail(ErrorCode::SubmissionUnknown,"qmt_host_receiver_outcome_unknown");}
        }
    }
    return {};
}
}
