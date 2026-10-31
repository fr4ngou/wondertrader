// WonderTrader MIT interfaces; Guanheng managed execution adapter.
#include "ManagedTrader.h"
#include "../Includes/WTSTradeDef.hpp"
#include "../Includes/WTSCollection.hpp"
#include "../Includes/IBaseDataMgr.h"
#include "../Includes/WTSError.hpp"
#include <cmath>
#include <cstring>
#include <cstdio>
#include <algorithm>

namespace guanheng
{
namespace
{
Status fail(ErrorCode code, const char* reason) { return {code, reason}; }
int result(const Status& s) { return s.ok() ? 0 : -1 - static_cast<int>(s.code); }
bool identity_equal(const ExecutionIdentity& a, const ExecutionIdentity& b)
{
    return same_session(a.source, b.source) && a.account_id == b.account_id
        && a.environment == b.environment && a.route_epoch == b.route_epoch;
}
bool baseline_equal(const CoherentBaseline& a, const CoherentBaseline& b)
{
    return identity_equal(a.identity, b.identity) && a.stream_id == b.stream_id && a.boundary_id == b.boundary_id
        && a.inclusive_cursor == b.inclusive_cursor && a.complete && b.complete;
}
bool fields_equal(const OrderFields& a, const OrderFields& b)
{
    return a.exchange == b.exchange && a.code == b.code && a.entrust_id == b.entrust_id
        && a.user_tag == b.user_tag && a.order_id == b.order_id && a.price == b.price
        && a.quantity == b.quantity && a.buy == b.buy && a.operation == b.operation;
}
bool text_valid(const std::string& text, std::size_t max, bool empty = false)
{
    return (empty || !text.empty()) && text.size() < max && text.find('\0') == std::string::npos;
}
bool symbol_valid(const OrderFields& f)
{
    return (f.exchange == "SSE" || f.exchange == "SZSE") && text_valid(f.code, MAX_INSTRUMENT_LENGTH)
        && text_valid(f.entrust_id, 64) && text_valid(f.user_tag, 64, true)
        && text_valid(f.order_id, 64, f.operation == ExecutionOperation::Submit);
}
bool fields_valid(const OrderFields& f)
{
    return symbol_valid(f) && (f.operation == ExecutionOperation::Cancel
        || (std::isfinite(f.price) && f.price > 0 && std::isfinite(f.quantity)
            && f.quantity > 0 && std::floor(f.quantity) == f.quantity));
}
bool cash_entrust(const wtp::WTSEntrust& e)
{
    return e.getBusinessType() == wtp::BT_CASH && e.getDirection() == wtp::WDT_LONG
        && (e.getOffsetType() == wtp::WOT_OPEN || e.getOffsetType() == wtp::WOT_CLOSE)
        && e.getPriceType() == wtp::WPT_LIMITPRICE && e.getOrderFlag() == wtp::WOF_NOR
        && (!e.isNet() || e.isBuy() == (e.getOffsetType() == wtp::WOT_OPEN));
}
bool qualified(const Capability& c, RuntimeMode mode)
{
    return c.supported && (mode == RuntimeMode::Live ? c.qualification == Qualification::ProductionQualified
        : (c.qualification == Qualification::DevelopmentVerified || c.qualification == Qualification::NativeVerified || c.qualification == Qualification::ProductionQualified));
}
struct ArrayOwner
{
    wtp::WTSArray* value = wtp::WTSArray::create();
    ~ArrayOwner() { value->release(); }
};
wtp::WTSContractInfo* contract(wtp::ITraderSpi* spi, const std::string& code, const std::string& exchange)
{
    auto mgr = spi ? spi->getBaseDataMgr() : nullptr;
    return mgr ? mgr->getContract(code.c_str(), exchange.c_str()) : nullptr;
}
wtp::WTSOrderInfo* make_order(const OrderRecord& r, wtp::ITraderSpi* spi)
{
    auto e = wtp::WTSEntrust::create(r.fields.code.c_str(), r.fields.quantity, r.fields.price, r.fields.exchange.c_str());
    e->setEntrustID(r.fields.entrust_id.c_str()); e->setUserTag(r.fields.user_tag.c_str());
    e->setDirection(wtp::WDT_LONG); e->setOffsetType(r.fields.buy ? wtp::WOT_OPEN : wtp::WOT_CLOSE);
    e->setNetDirection(r.fields.buy); e->setPriceType(wtp::WPT_LIMITPRICE); e->setOrderFlag(wtp::WOF_NOR);
    auto o = wtp::WTSOrderInfo::create(e); e->release();
    o->setNetDirection(r.fields.buy); o->setContractInfo(contract(spi, r.fields.code, r.fields.exchange));
    o->setOrderID(r.native_order_id.c_str()); o->setOrderDate(r.date); o->setOrderTime(r.time);
    o->setVolTraded(r.traded); o->setVolLeft(r.remaining); o->setOrderType(wtp::WORT_Normal);
    o->setStateMsg(r.message.c_str()); o->setError(r.state == NativeOrderState::Rejected);
    switch (r.state)
    {
    case NativeOrderState::Submitting: o->setOrderState(wtp::WOS_Submitting); break;
    case NativeOrderState::Accepted: o->setOrderState(wtp::WOS_NotTraded_Queuing); break;
    case NativeOrderState::PartFilled: o->setOrderState(wtp::WOS_PartTraded_Queuing); break;
    case NativeOrderState::Filled: o->setOrderState(wtp::WOS_AllTraded); break;
    case NativeOrderState::Canceling: o->setOrderState(wtp::WOS_Cancelling); break;
    case NativeOrderState::Canceled: o->setOrderState(wtp::WOS_Canceled); break;
    case NativeOrderState::Rejected: o->setOrderState(wtp::WOS_NotTraded_NotQueuing); break;
    }
    return o;
}
wtp::WTSTradeInfo* make_trade(const TradeRecord& r, wtp::ITraderSpi* spi)
{
    auto t = wtp::WTSTradeInfo::create(r.fields.code.c_str(), r.fields.exchange.c_str());
    t->setTradeID(r.trade_id.c_str()); t->setRefOrder(r.native_order_id.c_str()); t->setUserTag(r.fields.user_tag.c_str());
    t->setDirection(wtp::WDT_LONG); t->setOffsetType(r.fields.buy ? wtp::WOT_OPEN : wtp::WOT_CLOSE);
    t->setNetDirection(r.fields.buy); t->setOrderType(wtp::WORT_Normal); t->setTradeType(wtp::WTT_Common);
    t->setVolume(r.fields.quantity); t->setPrice(r.fields.price); t->setAmount(r.amount);
    t->setTradeDate(r.date); t->setTradeTime(r.time); t->setContractInfo(contract(spi, r.fields.code, r.fields.exchange));
    return t;
}
bool valid_date_time(std::uint32_t date, std::uint64_t time);
bool valid_order(const OrderRecord& r)
{
    auto integer = [](double n){ return std::isfinite(n) && n >= 0 && std::floor(n) == n; };
    if (r.fields.operation != ExecutionOperation::Submit || !fields_valid(r.fields) || !text_valid(r.native_order_id, 64)
        || !valid_date_time(r.date, r.time) || !integer(r.traded) || !integer(r.remaining) || !integer(r.inactive_quantity)
        || r.traded + r.remaining + r.inactive_quantity != r.fields.quantity) return false;
    switch (r.state)
    {
    case NativeOrderState::Submitting:
    case NativeOrderState::Accepted: return r.traded == 0 && r.inactive_quantity == 0;
    case NativeOrderState::PartFilled: return r.traded > 0 && r.traded < r.fields.quantity && r.remaining > 0 && r.inactive_quantity == 0;
    case NativeOrderState::Filled: return r.traded == r.fields.quantity && r.remaining == 0 && r.inactive_quantity == 0;
    case NativeOrderState::Canceling: return r.remaining > 0 && r.inactive_quantity == 0;
    case NativeOrderState::Canceled: return r.remaining == 0 && r.inactive_quantity > 0;
    case NativeOrderState::Rejected: return r.traded == 0 && r.remaining == 0 && r.inactive_quantity == r.fields.quantity;
    }
    return false;
}
bool valid_date_time(std::uint32_t date, std::uint64_t time)
{
    unsigned year = date/10000, month = date/100%100, day = date%100;
    const unsigned days[] = {31,28,31,30,31,30,31,31,30,31,30,31};
    if (year < 2004 || year > 2099 || month < 1 || month > 12 || day < 1
        || day > days[month-1] + (month == 2 && year%4 == 0 && (year%100 != 0 || year%400 == 0))) return false;
    return time/10000000 < 24 && time/100000%100 < 60 && time/1000%100 < 60;
}
bool valid_account(const AccountRecord& r)
{
    const double nums[] = {r.balance, r.previous_balance, r.available, r.margin, r.frozen_margin, r.commission, r.frozen_commission, r.close_profit, r.dynamic_profit, r.deposit, r.withdraw};
    return text_valid(r.currency, 8) && std::all_of(std::begin(nums), std::end(nums), [](double n){ return std::isfinite(n); });
}
bool valid_position(const PositionRecord& r)
{
    const double nums[] = {r.previous, r.today, r.available_previous, r.available_today, r.total_cost, r.average_price, r.margin, r.dynamic_profit};
    return (r.exchange == "SSE" || r.exchange == "SZSE") && text_valid(r.code, MAX_INSTRUMENT_LENGTH) && text_valid(r.currency, 8)
        && std::all_of(std::begin(nums), std::end(nums), [](double n){ return std::isfinite(n); })
        && r.previous >= 0 && r.today >= 0 && r.available_previous >= 0 && r.available_previous <= r.previous
        && r.available_today >= 0 && r.available_today <= r.today;
}
bool valid_trade(const TradeRecord& r)
{
    return r.fields.operation == ExecutionOperation::Submit && fields_valid(r.fields) && text_valid(r.native_order_id, 64) && text_valid(r.trade_id, 64)
        && std::isfinite(r.amount) && r.amount >= 0 && valid_date_time(r.date, r.time);
}
bool same_trade(const TradeRecord& a, const TradeRecord& b)
{
    return fields_equal(a.fields, b.fields) && a.command_id == b.command_id && a.native_order_id == b.native_order_id
        && a.trade_id == b.trade_id && a.amount == b.amount && a.date == b.date && a.time == b.time;
}
std::string trade_key(const ExecutionIdentity& identity, const TradeRecord& trade)
{
    // 长度前缀防止外部身份字符串含分隔符造成复合键碰撞；会话代际不改变同一柜台事实身份。
    std::string key;
    for (const auto& part : {std::to_string(static_cast<int>(identity.source.provider)), identity.source.instance_id,
        identity.account_id, identity.environment, std::to_string(trade.date), trade.fields.exchange, trade.trade_id})
        key += std::to_string(part.size()) + ":" + part;
    return key;
}
bool same_event(const ExecutionEvent& a, const ExecutionEvent& b)
{
    if (a.event_id != b.event_id || a.stream_id != b.stream_id || a.cursor != b.cursor || a.is_trade != b.is_trade || !identity_equal(a.identity, b.identity)) return false;
    if (a.is_trade) return fields_equal(a.trade.fields, b.trade.fields) && a.trade.command_id == b.trade.command_id
        && a.trade.native_order_id == b.trade.native_order_id && a.trade.trade_id == b.trade.trade_id
        && a.trade.amount == b.trade.amount && a.trade.date == b.trade.date && a.trade.time == b.trade.time;
    return fields_equal(a.order.fields, b.order.fields) && a.order.command_id == b.order.command_id
        && a.order.native_order_id == b.order.native_order_id && a.order.message == b.order.message
        && a.order.traded == b.order.traded && a.order.remaining == b.order.remaining && a.order.inactive_quantity == b.order.inactive_quantity
        && a.order.date == b.order.date && a.order.time == b.order.time && a.order.state == b.order.state;
}
}

ManagedTrader::ManagedTrader(ProviderKind provider) : provider_(provider)
{
    state_.status = fail(ErrorCode::Unavailable, "未注入合格交易后端");
}
ManagedTrader::~ManagedTrader() { try { disconnect(); } catch (...) {} }
Status ManagedTrader::configure(const ManagedTraderConfig& c, std::shared_ptr<ExecutionEndpoint> endpoint,
    std::shared_ptr<AuthorizationVerifier> verifier, std::shared_ptr<ExecutionStateSink> sink)
{
    std::lock_guard<std::recursive_mutex> lock(mutex_);
    if (state_.connected || close_pending_ || dispatching_reports_ || executing_ || baseline_dispatching_) return fail(ErrorCode::Conflict, "连接、关闭核查或执行期间禁止更换身份或端点");
    if ((c.mode != RuntimeMode::Simulation && c.mode != RuntimeMode::ReadOnly && c.mode != RuntimeMode::Live)
        || c.identity.source.provider != provider_ || !text_valid(c.identity.source.instance_id, 128)
        || !text_valid(c.identity.source.session_id, 128) || c.identity.source.generation == 0
        || !text_valid(c.identity.account_id, 128) || !text_valid(c.identity.environment, 128)
        || c.identity.route_epoch == 0 || c.budget_ms == 0 || c.budget_ms > 60000
        || c.index_capacity == 0 || c.index_capacity > 65536 || c.event_batch == 0
        || c.event_batch > 4096 || c.snapshot_limit == 0 || c.snapshot_limit > 100000)
        return fail(ErrorCode::InvalidInput, "交易配置身份或容量非法");
    // 未知状态仅由原 Host 恢复证明解除，重新配置不能绕过闩锁。
    if (recovery_required_ || delivery_unknown_)
        return fail(ErrorCode::SubmissionUnknown, "先由原Host核查未知提交");
    if (baseline_delivered_) return fail(ErrorCode::Conflict, "WT消费者已有初始化副作用，更换配置需要新实例与新消费者原子基线");
    config_ = c; endpoint_ = std::move(endpoint); verifier_ = std::move(verifier); state_sink_ = std::move(sink);
    state_ = {}; state_.identity = c.identity; cursor_ = 0; derived_.clear(); delivered_.clear(); native_trades_.clear();
    baseline_ready_ = false; baseline_delivered_ = 0; baseline_dispatching_ = 0; bootstrap_ = {};
    auto status = endpoint_ ? Status{} : fail(ErrorCode::Unavailable, "未注入合格交易后端");
    publish(status); return status;
}
ExecutionState ManagedTrader::state() const { std::lock_guard<std::recursive_mutex> lock(mutex_); return state_; }
ExecutionCapabilities ManagedTrader::capabilities() const
{
    std::lock_guard<std::recursive_mutex> lock(mutex_);
    try { return endpoint_ ? endpoint_->capabilities() : ExecutionCapabilities{}; }
    catch (...) { return {}; }
}
void ManagedTrader::publish(const Status& s, const std::string& command, SubmissionStage stage)
{
    state_.status = s;
    if (!command.empty()) { state_.command_id = command; state_.stage = stage; }
    auto sink = state_sink_; auto snapshot = state_;
    if (sink) { try { sink->on_execution_state(snapshot); } catch (...) {} }
}
Status ManagedTrader::ready(const Capability& cap, bool write) const
{
    if (!endpoint_ || !state_.connected || !state_.logged_in) return fail(ErrorCode::Unavailable, "交易后端尚未登录");
    if (!qualified(cap, config_.mode)) return fail(ErrorCode::Unavailable, "能力资格缺失");
    if (write && native_trades_.size() >= config_.index_capacity) return fail(ErrorCode::Backpressure, "柜台成交派生窗口已满，需要受控重建原子基线");
    if (write && state_.writes_blocked) return fail(ErrorCode::SubmissionUnknown, "未知提交阻断新写，继续查询回报并核查");
    if (write && (!baseline_ready_ || baseline_delivered_ != 15 || delivery_unknown_)) return fail(ErrorCode::Unavailable, "WT观察基线尚未完整建立");
    if (write && config_.mode == RuntimeMode::ReadOnly) return fail(ErrorCode::Unavailable, "只读模式禁止交易");
    return {};
}
bool ManagedTrader::init(wtp::WTSVariant*) { return true; }
void ManagedTrader::release() { disconnect(); }
void ManagedTrader::registerSpi(wtp::ITraderSpi* spi)
{
    std::lock_guard<std::recursive_mutex> lock(mutex_);
    if (spi_ != spi && (baseline_delivered_ || delivery_unknown_ || baseline_dispatching_)) { isolate_consumer("更换WT消费者需要新实例与Host原子基线"); if (!spi && state_.channel_isolated) spi_ = nullptr; return; }
    spi_ = spi;
}
void ManagedTrader::connect()
{
    std::lock_guard<std::recursive_mutex> lock(mutex_);
    if (close_pending_) { publish(fail(ErrorCode::Pending, "交易端点停止尚未确认，先重试stop")); return; }
    if (state_.connected) return;
    Status s = fail(ErrorCode::Unavailable, "未注入合格交易后端");
    try { if (endpoint_) s = endpoint_->open(config_.identity, config_.budget_ms); }
    catch (...) { s = fail(ErrorCode::IoError, "交易后端连接异常"); }
    state_.connected = s.ok(); publish(s);
    if (spi_) spi_->handleEvent(wtp::WTE_Connect, result(s));
}
void ManagedTrader::disconnect()
{
    stop();
}
Status ManagedTrader::stop()
{
    std::lock_guard<std::recursive_mutex> lock(mutex_);
    state_.connected = false; state_.logged_in = false; state_.writes_blocked = true;
    state_.consumer_ready = false; state_.resuming = false;
    state_.stopping = true;
    if (endpoint_)
    {
        close_pending_ = true;
        try { endpoint_->close(); }
        catch (...)
        {
            revoke_channel(); // 资源关闭未知也先撤销消费者资格，保留停止重试。
            auto s = fail(ErrorCode::IoError, "交易端点关闭失败，保留引用并重试stop"); publish(s); return s;
        }
        close_pending_ = false;
    }
    auto revoked = revoke_channel();
    if (!revoked.ok()) { close_pending_ = true; publish(revoked); return revoked; }
    state_.stopping = false;
    publish(fail(ErrorCode::Unavailable, "交易连接已关闭"));
    return {};
}
Status ManagedTrader::revoke_channel()
{
    if (revoking_channel_) return fail(ErrorCode::Pending, "消费者lost通知正在进行");
    struct Guard { bool& value; explicit Guard(bool& v) : value(v) { value = true; } ~Guard() { value = false; } } guard(revoking_channel_);
    Status status;
    try
    {
        if (auto managed = dynamic_cast<RetainedConsumerRecovery*>(spi_)) status = managed->invalidate_retained_channel();
        else if (spi_) spi_->handleEvent(wtp::WTE_Close, 0);
    }
    catch (...) { status = fail(ErrorCode::Pending, "消费者lost通知应用结果尚未确认"); }
    state_.channel_isolated = status.ok(); return status;
}
Status ManagedTrader::isolate_consumer(const char* reason)
{
    const bool first_isolation = !delivery_unknown_;
    delivery_unknown_ = true; recovery_required_ = true;
    state_.delivery_unknown = true; state_.consumer_ready = false; state_.writes_blocked = true; state_.resuming = false;
    auto revoked = first_isolation ? revoke_channel() : (state_.channel_isolated ? Status{} : fail(ErrorCode::Pending, "WT lost待显式重试确认"));
    Status unknown = fail(ErrorCode::SubmissionUnknown, reason);
    if (!revoked.ok()) unknown.reason += "；部分WT lost通知待确认，保留隔离与重试";
    publish(unknown); return unknown;
}
Status ManagedTrader::retry_consumer_isolation()
{
    std::lock_guard<std::recursive_mutex> lock(mutex_);
    if (!delivery_unknown_) return fail(ErrorCode::InvalidInput, "当前没有消费者未知隔离");
    auto status = revoke_channel();
    publish(fail(ErrorCode::SubmissionUnknown, status.ok() ? "WT lost已确认，消费者仍需新原子基线重建" : "WT lost尚未全部确认，保留隔离与重试"));
    return status;
}
bool ManagedTrader::isConnected() { std::lock_guard<std::recursive_mutex> lock(mutex_); return state_.connected; }
bool ManagedTrader::makeEntrustID(char* buffer, int length)
{
    std::lock_guard<std::recursive_mutex> lock(mutex_);
    if (!buffer || length < 64) return false;
    std::snprintf(buffer, static_cast<std::size_t>(length), "GH-%llu-%llu", static_cast<unsigned long long>(config_.identity.source.generation), static_cast<unsigned long long>(++entrust_sequence_));
    return true;
}
int ManagedTrader::login(const char*, const char*, const char*)
{
    std::lock_guard<std::recursive_mutex> lock(mutex_);
    if (restoring_channel_ || dispatching_reports_) return result(fail(ErrorCode::Pending, "消费者回调或恢复通知期间禁止重入登录"));
    if (baseline_delivered_ == 15)
    {
        if (!state_.connected) return result(fail(ErrorCode::Unavailable, "保留消费者尚未重新连接"));
        if (delivery_unknown_) return result(fail(ErrorCode::SubmissionUnknown, "消费者应用未知，须受控重建原子基线"));
        state_.logged_in = true;
        if (state_.consumer_ready) return 0;
        auto resumed = begin_resume(); publish(resumed); return result(resumed);
    }
    // 登录采用已注入身份，凭证由受管 Host 持有。
    state_.logged_in = state_.connected;
    auto s = state_.logged_in ? establish_baseline() : fail(ErrorCode::Unavailable, "交易后端尚未连接");
    if (!s.ok()) state_.logged_in = false;
    state_.writes_blocked = !state_.logged_in || recovery_required_ || baseline_delivered_ != 15;
    if (recovery_required_) publish(fail(state_.stage == SubmissionStage::SubmissionUnknown ? ErrorCode::SubmissionUnknown : ErrorCode::Pending, "等待原Host恢复证明，查询与回报继续可用"));
    else publish(s);
    try { if (spi_) spi_->onLoginResult(s.ok(), s.reason.c_str(), config_.trading_date); }
    catch (...) { return result(isolate_consumer("WT初始登录通知应用结果未知，已撤销通道资格")); }
    if (s.ok() && (delivery_unknown_ || !state_.connected || !state_.logged_in))
        return result(isolate_consumer("WT初始ready通知中发生隔离或会话改变，已撤销通道资格"));
    return result(s);
}
int ManagedTrader::logout() { return result(stop()); }
int ManagedTrader::orderInsert(wtp::WTSEntrust*)
{
    std::lock_guard<std::recursive_mutex> lock(mutex_);
    auto s = fail(ErrorCode::Unavailable, "WT委托缺少受管签名授权上下文"); publish(s); return result(s);
}
int ManagedTrader::orderAction(wtp::WTSEntrustAction*)
{
    std::lock_guard<std::recursive_mutex> lock(mutex_);
    auto s = fail(ErrorCode::Unavailable, "WT撤单缺少受管签名授权上下文"); publish(s); return result(s);
}
SubmissionReceipt ManagedTrader::submit(const SignedCommand& c, const wtp::WTSEntrust& e)
{
    std::lock_guard<std::recursive_mutex> lock(mutex_);
    if (!cash_entrust(e)) return {fail(ErrorCode::InvalidInput, "首期仅支持已授权现金股票普通限价买卖"), SubmissionStage::NotCalled, c.command_id, {}};
    OrderFields f; f.exchange = e.getExchg(); f.code = e.getCode(); f.entrust_id = e.getEntrustID();
    f.user_tag = e.getUserTag(); f.price = e.getPrice(); f.quantity = e.getVolume(); f.buy = e.getOffsetType() == wtp::WOT_OPEN;
    return execute(c, f);
}
SubmissionReceipt ManagedTrader::cancel(const SignedCommand& c, const wtp::WTSEntrustAction& a)
{
    std::lock_guard<std::recursive_mutex> lock(mutex_);
    if (a.getActionFlag() != wtp::WAF_CANCEL || a.getBusinessType() != wtp::BT_CASH)
        return {fail(ErrorCode::InvalidInput, "仅支持已授权现金股票撤单"), SubmissionStage::NotCalled, c.command_id, {}};
    OrderFields f; f.operation = ExecutionOperation::Cancel; f.exchange = a.getExchg(); f.code = a.getCode();
    f.entrust_id = a.getEntrustID(); f.order_id = a.getOrderID(); return execute(c, f);
}
SubmissionReceipt ManagedTrader::execute(const SignedCommand& c, const OrderFields& f)
{
    auto rejected = [&](Status s) { if (recovery_required_) publish(s); else publish(s, c.command_id); return SubmissionReceipt{s, SubmissionStage::NotCalled, c.command_id, {}}; };
    if (!text_valid(c.command_id, 128) || c.original_bytes.empty() || c.original_bytes.size() > 65536 || !fields_valid(f))
        return rejected(fail(ErrorCode::InvalidInput, "签名命令或WT字段非法"));
    auto old = derived_.find(c.command_id);
    if (old != derived_.end())
    {
        if (old->second.command.original_bytes != c.original_bytes || !fields_equal(old->second.fields, f))
            return rejected(fail(ErrorCode::Conflict, "相同命令身份存在冲突内容"));
        return old->second.receipt;
    }
    if (executing_) return rejected(fail(ErrorCode::Pending, "已有受管命令正在提交"));
    auto caps = capabilities(); auto s = ready(f.operation == ExecutionOperation::Submit ? caps.submit : caps.cancel, true);
    if (!s.ok()) return rejected(s);
    if (!verifier_) return rejected(fail(ErrorCode::Unavailable, "缺少上游授权校验器"));
    if (config_.mode == RuntimeMode::Live)
    {
        bool trusted = false;
        try { trusted = verifier_->production_trusted() && endpoint_->production_trusted(); } catch (...) {}
        if (!trusted) return rejected(fail(ErrorCode::Unavailable, "生产交易需要可信上游校验与后端"));
    }
    // 覆盖授权校验与Host调用的同步重入窗口，身份与端点在整个提交回合保持冻结。
    struct ExecuteGuard { bool& flag; explicit ExecuteGuard(bool& value) : flag(value) { flag = true; } ~ExecuteGuard() { flag = false; } } guard(executing_);
    VerifiedAuthorization authorization;
    try { s = verifier_->verify(c, authorization); } catch (...) { s = fail(ErrorCode::Unavailable, "上游授权校验异常"); }
    if (!s.ok()) return rejected(s);
    if (!identity_equal(authorization.identity, config_.identity) || authorization.command_id != c.command_id
        || authorization.mode != config_.mode || !fields_equal(authorization.fields, f))
        return rejected(fail(ErrorCode::Conflict, "授权与WT字段、账户、环境、会话或路由不一致"));
    s = ready(f.operation == ExecutionOperation::Submit ? capabilities().submit : capabilities().cancel, true);
    if (!s.ok()) return rejected(s);
    if (derived_.size() >= config_.index_capacity) return rejected(fail(ErrorCode::Backpressure, "派生命令索引已满，保持原Host权威"));
    // 提交前分配派生槽，分配失败尚无副作用；进入execute后任何异常均保留unknown。
    auto inserted = derived_.emplace(c.command_id, DerivedReceipt{c, f, {fail(ErrorCode::SubmissionUnknown, "提交结果待核查"), SubmissionStage::SubmissionUnknown, c.command_id, {}}});
    SubmissionReceipt receipt = inserted.first->second.receipt;
    try { receipt = endpoint_->execute(c, authorization, config_.budget_ms); }
    catch (...) { receipt.status = fail(ErrorCode::SubmissionUnknown, "Host提交出现异常，原命令需核查"); }
    if (receipt.stage < SubmissionStage::NotCalled || receipt.stage > SubmissionStage::SubmissionUnknown
        || receipt.command_id != c.command_id || (receipt.stage == SubmissionStage::NotCalled && receipt.status.ok())
        || (receipt.stage != SubmissionStage::NotCalled && !receipt.status.ok())
        || (receipt.stage == SubmissionStage::BrokerAccepted && (!text_valid(receipt.native_order_id, 64)
            || (f.operation == ExecutionOperation::Cancel && receipt.native_order_id != f.order_id)))
        || (!receipt.native_order_id.empty() && !text_valid(receipt.native_order_id, 64)))
    {
        receipt.status = fail(ErrorCode::SubmissionUnknown, "Host提交回执语义冲突，需核查"); receipt.stage = SubmissionStage::SubmissionUnknown;
    }
    receipt.command_id = c.command_id;
    if (receipt.status.code == ErrorCode::SubmissionUnknown || receipt.stage == SubmissionStage::SubmissionUnknown)
    {
        receipt.stage = SubmissionStage::SubmissionUnknown; receipt.status.code = ErrorCode::SubmissionUnknown; state_.writes_blocked = true; recovery_required_ = true;
    }
    inserted.first->second.receipt = receipt;
    publish(receipt.status, c.command_id, receipt.stage); return receipt;
}

Status ManagedTrader::establish_baseline()
{
    if (delivery_unknown_) return fail(ErrorCode::SubmissionUnknown, "WT消费者应用结果未知，需重建消费者与原子基线");
    if (baseline_ready_) return {};
    ExecutionBootstrap candidate;
    Status status;
    try { status = endpoint_->bootstrap(candidate, config_.budget_ms); }
    catch (...) { status = fail(ErrorCode::Unavailable, "Host原子基线读取异常"); }
    if (!status.ok()) return status;
    const auto& proof = candidate.baseline;
    if (!proof.complete || !identity_equal(proof.identity, config_.identity) || !text_valid(proof.stream_id, 128)
        || !text_valid(proof.boundary_id, 128)) return fail(ErrorCode::Unavailable, "Host未提供完整同身份流与吸收水位证明");
    auto coherent = [&](const auto& snapshot)
    { return baseline_equal(snapshot.baseline, proof) && snapshot.records.size() <= config_.snapshot_limit; };
    if (!coherent(candidate.account) || !coherent(candidate.positions) || !coherent(candidate.orders) || !coherent(candidate.trades))
        return fail(ErrorCode::Conflict, "四种初始化快照的冻结边界或流吸收水位不一致");
    if (!std::all_of(candidate.account.records.begin(), candidate.account.records.end(), valid_account)
        || !std::all_of(candidate.positions.records.begin(), candidate.positions.records.end(), valid_position)
        || !std::all_of(candidate.orders.records.begin(), candidate.orders.records.end(), valid_order)
        || !std::all_of(candidate.trades.records.begin(), candidate.trades.records.end(), valid_trade))
        return fail(ErrorCode::InvalidInput, "原子基线包含非法账户、持仓、委托或成交");
    std::map<std::string, TradeRecord> trades;
    std::vector<TradeRecord> unique_trades;
    for (const auto& trade : candidate.trades.records)
    {
        auto key = trade_key(config_.identity, trade); auto found = trades.find(key);
        if (found != trades.end() && !same_trade(found->second, trade)) return fail(ErrorCode::Conflict, "原子基线原生成交内容冲突");
        if (found == trades.end()) { trades[key] = trade; unique_trades.push_back(trade); }
        if (trades.size() > config_.index_capacity) return fail(ErrorCode::Backpressure, "原子基线成交身份超出派生预算");
    }
    candidate.trades.records = std::move(unique_trades);
    bootstrap_ = std::move(candidate); native_trades_ = std::move(trades);
    cursor_ = bootstrap_.baseline.inclusive_cursor; baseline_ready_ = true; return {};
}
Status ManagedTrader::begin_resume()
{
    state_.consumer_ready = false; state_.writes_blocked = true; state_.resuming = false;
    auto qualified_reports = ready(capabilities().reports, false);
    if (!qualified_reports.ok()) return qualified_reports;
    if (!dynamic_cast<RetainedConsumerRecovery*>(spi_)) return fail(ErrorCode::Unavailable, "WT消费者缺少受管保留通道恢复接缝");
    RetainedResumeProof proof; Status s;
    try { s = endpoint_->confirm_resume(bootstrap_.baseline, cursor_, proof, config_.budget_ms); }
    catch (...) { s = fail(ErrorCode::Unavailable, "Host保留消费者连续性证明读取异常"); }
    if (!s.ok()) return s;
    if (!proof.complete || !baseline_equal(proof.baseline, bootstrap_.baseline) || proof.after_cursor != cursor_
        || proof.through_cursor < proof.after_cursor || proof.trading_date != config_.trading_date)
        return fail(ErrorCode::Conflict, "Host恢复证明的流、账户、原边界、前后水位或交易日不一致");
    if (!state_.connected || !state_.logged_in || delivery_unknown_) return fail(ErrorCode::Unavailable, "取得恢复证明期间连接或消费者状态变化");
    resume_proof_ = proof; state_.resuming = true;
    return cursor_ == proof.through_cursor ? finish_resume() : fail(ErrorCode::Pending, "等待连续补投到Host冻结前沿后恢复WT通道");
}
Status ManagedTrader::finish_resume()
{
    if (!state_.resuming || cursor_ != resume_proof_.through_cursor || delivery_unknown_
        || !state_.connected || !state_.logged_in || !baseline_equal(resume_proof_.baseline, bootstrap_.baseline))
        return fail(ErrorCode::Unavailable, "WT恢复尚未达到完整连续性条件");
    auto consumer = dynamic_cast<RetainedConsumerRecovery*>(spi_);
    if (!consumer) return fail(ErrorCode::Unavailable, "保留消费者恢复接缝已丢失");
    struct Guard { bool& value; explicit Guard(bool& v) : value(v) { value = true; } ~Guard() { value = false; } } guard(restoring_channel_);
    Status s;
    try { s = consumer->restore_retained_channel(resume_proof_.trading_date); }
    catch (...)
    {
        s = fail(ErrorCode::SubmissionUnknown, "WT恢复通知可能已应用，需隔离消费者并受控重建");
    }
    if (!s.ok() || !state_.connected || !state_.logged_in || delivery_unknown_ || !state_.resuming
        || !baseline_equal(resume_proof_.baseline, bootstrap_.baseline) || cursor_ != resume_proof_.through_cursor)
    {
        state_.consumer_ready = false; state_.writes_blocked = true;
        if (delivery_unknown_ || s.code == ErrorCode::SubmissionUnknown)
            return isolate_consumer("WT恢复ready通知中消费者应用未知，已撤销通道资格并禁止归约");
        auto revoked = revoke_channel();
        if (!revoked.ok()) return revoked;
        return s.ok() ? fail(ErrorCode::Unavailable, "WT恢复回调改变连接或隔离状态，保持禁写") : s;
    }
    state_.resuming = false; state_.consumer_ready = true;
    state_.channel_isolated = false;
    state_.writes_blocked = recovery_required_ || native_trades_.size() >= config_.index_capacity;
    state_.status = {};
    return {};
}
template<class T> Status ManagedTrader::validate(const ExecutionSnapshot<T>& s, bool latest_account) const
{
    if (!identity_equal(s.baseline.identity, config_.identity)) return fail(ErrorCode::StaleSession, "查询快照来自旧账户或会话");
    if (!s.baseline.complete || s.baseline.boundary_id.empty()) return fail(ErrorCode::Pending, "查询分页或一致性边界尚未完整");
    if (s.baseline.stream_id != bootstrap_.baseline.stream_id || (!latest_account && !baseline_equal(s.baseline, bootstrap_.baseline)))
        return fail(ErrorCode::Conflict, "查询快照与受管流或冻结边界不一致");
    if (s.records.size() > config_.snapshot_limit) return fail(ErrorCode::Backpressure, "查询快照超过容量");
    return {};
}
int ManagedTrader::deliver_baseline(unsigned bit, const std::function<void()>& callback)
{
    if (baseline_delivered_ & bit) return result(fail(ErrorCode::NotSupported, "WT初始化快照仅交付一次，最新观察使用Broker只读接口"));
    if (baseline_dispatching_ & bit) return result(fail(ErrorCode::Pending, "该初始化快照正在交付"));
    baseline_dispatching_ |= bit;
    int code = deliver_query(callback);
    baseline_dispatching_ &= ~bit;
    if (code == 0 && !delivery_unknown_ && state_.connected && state_.logged_in)
    {
        baseline_delivered_ |= bit; state_.consumer_ready = baseline_delivered_ == 15;
        state_.writes_blocked = !state_.consumer_ready || recovery_required_ || delivery_unknown_;
        if (state_.consumer_ready) state_.channel_isolated = false;
    }
    return code;
}
int ManagedTrader::deliver_query(const std::function<void()>& callback)
{
    if (delivery_unknown_) return result(fail(ErrorCode::SubmissionUnknown, "WT消费者应用结果未知，仅允许只读诊断并受控重建"));
    if (!spi_) return query_failure(fail(ErrorCode::Pending, "尚未注册查询消费者"));
    try
    {
        callback();
        if (delivery_unknown_ || !state_.connected || !state_.logged_in)
            return result(isolate_consumer("WT查询回调中发生重入隔离或会话改变，禁止重复应用"));
        return 0;
    }
    catch (...)
    {
        return result(isolate_consumer("WT查询消费者应用结果未知，已撤销通道资格，需受控重建基线"));
    }
}
int ManagedTrader::query_failure(const Status& s)
{
    if (state_.connected && state_.logged_in) { recovery_required_ = true; state_.writes_blocked = true; }
    publish(s); return result(s);
}
int ManagedTrader::queryAccount()
{
    std::lock_guard<std::recursive_mutex> lock(mutex_);
    auto s = ready(capabilities().account, false); ExecutionSnapshot<AccountRecord> data;
    bool initial = !(baseline_delivered_ & 1) && !(baseline_dispatching_ & 1);
    if (!initial && account_observer_active_) return result(fail(ErrorCode::Pending, "最新账户观察正在回调，禁止同查询递归"));
    struct ObserverGuard
    {
        bool& active; bool entered;
        ObserverGuard(bool& flag, bool latest) : active(flag), entered(latest) { if (entered) active = true; }
        ~ObserverGuard() { if (entered) active = false; }
    } observer_guard(account_observer_active_, !initial);
    try { if (s.ok()) { if (initial) data = bootstrap_.account; else s = endpoint_->account(data, config_.budget_ms); } } catch (...) { s = fail(ErrorCode::IoError, "账户查询异常"); }
    if (s.ok()) s = validate(data, !initial);
    if (!s.ok()) return query_failure(s);
    ArrayOwner array;
    for (const auto& r : data.records)
    {
        if (!valid_account(r))
        { s = fail(ErrorCode::InvalidInput, "账户字段非法"); return query_failure(s); }
        auto a = wtp::WTSAccountInfo::create(); a->setCurrency(r.currency.c_str()); a->setBalance(r.balance);
        a->setPreBalance(r.previous_balance); a->setAvailable(r.available); a->setMargin(r.margin); a->setFrozenMargin(r.frozen_margin);
        a->setCommission(r.commission); a->setFrozenCommission(r.frozen_commission); a->setCloseProfit(r.close_profit);
        a->setDynProfit(r.dynamic_profit); a->setDeposit(r.deposit); a->setWithdraw(r.withdraw); array.value->append(a, false);
    }
    auto callback = [&](){ if (spi_) spi_->onRspAccount(array.value); };
    return initial ? deliver_baseline(1, callback) : deliver_query(callback);
}
int ManagedTrader::queryPositions()
{
    std::lock_guard<std::recursive_mutex> lock(mutex_);
    if (baseline_delivered_ & 2) return result(fail(ErrorCode::NotSupported, "WT持仓初始化已交付，最新观察使用Broker只读接口"));
    auto s = ready(capabilities().positions, false); ExecutionSnapshot<PositionRecord> data;
    if (s.ok()) data = bootstrap_.positions;
    if (s.ok()) s = validate(data);
    if (!s.ok()) return query_failure(s);
    ArrayOwner array;
    for (const auto& r : data.records)
    {
        if (!valid_position(r))
        { s = fail(ErrorCode::InvalidInput, "持仓字段非法"); return query_failure(s); }
        auto p = wtp::WTSPositionItem::create(r.code.c_str(), r.currency.c_str(), r.exchange.c_str());
        p->setDirection(wtp::WDT_LONG); p->setPrePosition(r.previous); p->setNewPosition(r.today);
        p->setAvailPrePos(r.available_previous); p->setAvailNewPos(r.available_today); p->setPositionCost(r.total_cost);
        p->setAvgPrice(r.average_price); p->setMargin(r.margin); p->setDynProfit(r.dynamic_profit);
        p->setContractInfo(contract(spi_, r.code, r.exchange)); array.value->append(p, false);
    }
    return deliver_baseline(2, [&](){ if (spi_) spi_->onRspPosition(array.value); });
}
int ManagedTrader::queryOrders()
{
    std::lock_guard<std::recursive_mutex> lock(mutex_);
    if (baseline_delivered_ & 4) return result(fail(ErrorCode::NotSupported, "WT委托初始化已交付，最新观察使用Broker只读接口"));
    auto s = ready(capabilities().orders, false); ExecutionSnapshot<OrderRecord> data;
    if (s.ok()) data = bootstrap_.orders;
    if (s.ok()) s = validate(data);
    if (s.ok() && !std::all_of(data.records.begin(), data.records.end(), valid_order)) s = fail(ErrorCode::InvalidInput, "委托字段非法");
    if (!s.ok()) return query_failure(s);
    ArrayOwner array; for (const auto& r : data.records) array.value->append(make_order(r, spi_), false);
    return deliver_baseline(4, [&](){ if (spi_) spi_->onRspOrders(array.value); });
}
int ManagedTrader::queryTrades()
{
    std::lock_guard<std::recursive_mutex> lock(mutex_);
    if (baseline_delivered_ & 8) return result(fail(ErrorCode::NotSupported, "WT成交初始化已交付，最新观察使用Broker只读接口"));
    auto s = ready(capabilities().trades, false); ExecutionSnapshot<TradeRecord> data;
    if (s.ok()) data = bootstrap_.trades;
    if (s.ok()) s = validate(data);
    if (s.ok() && !std::all_of(data.records.begin(), data.records.end(), valid_trade)) s = fail(ErrorCode::InvalidInput, "成交字段非法");
    if (!s.ok()) return query_failure(s);
    ArrayOwner array; for (const auto& r : data.records) array.value->append(make_trade(r, spi_), false);
    return deliver_baseline(8, [&](){ if (spi_) spi_->onRspTrades(array.value); });
}
Status ManagedTrader::poll_reports()
{
    std::lock_guard<std::recursive_mutex> lock(mutex_);
    return poll_reports(config_.event_batch, config_.budget_ms);
}
Status ManagedTrader::poll_reports(std::size_t limit, std::uint32_t budget_ms)
{
    std::lock_guard<std::recursive_mutex> lock(mutex_);
    if (!limit || limit > 4096 || !budget_ms || budget_ms > 60000)
        return fail(ErrorCode::InvalidInput, "回报轮询预算非法");
    limit = std::min(limit, config_.event_batch); budget_ms = std::min(budget_ms, config_.budget_ms);
    if (dispatching_reports_ || restoring_channel_) return fail(ErrorCode::Pending, "回报分发或通道恢复通知正在进行");
    if (delivery_unknown_) return fail(ErrorCode::SubmissionUnknown, "WT消费者应用结果未知，回报只允许inspect诊断，需重建消费者原子基线");
    if (!baseline_ready_ || baseline_delivered_ != 15) return fail(ErrorCode::Pending, "四类WT原子初始化快照尚未完整交付");
    if (!state_.consumer_ready && !state_.resuming) return fail(ErrorCode::Unavailable, "保留WT消费者尚未取得通道恢复资格");
    const auto before_poll = cursor_;
    auto s = ready(capabilities().reports, false); std::vector<ExecutionEvent> events;
    try { if (s.ok()) s = endpoint_->events(cursor_, limit, events, budget_ms); }
    catch (...) { s = fail(ErrorCode::IoError, "可靠回报读取异常"); }
    if (s.ok() && events.size() > limit) s = fail(ErrorCode::Backpressure, "回报批次超出容量");
    if (s.ok() && state_.resuming)
        events.erase(std::remove_if(events.begin(), events.end(), [&](const ExecutionEvent& e){ return e.cursor > resume_proof_.through_cursor; }), events.end());
    auto last = cursor_;
    auto staged_trades = native_trades_;
    if (s.ok()) for (const auto& event : events)
    {
        if (!identity_equal(event.identity, config_.identity) || event.stream_id != bootstrap_.baseline.stream_id) { s = fail(ErrorCode::StaleSession, "拒绝旧会话或其他流回报"); break; }
        if (event.cursor <= cursor_)
        {
            auto old = delivered_.find(event.cursor);
            if (old == delivered_.end() || !same_event(old->second, event)) { s = fail(ErrorCode::Conflict, "已处理回报出现身份或内容冲突"); break; }
            continue;
        }
        if (event.cursor <= last)
        {
            auto first = std::find_if(events.begin(), events.end(), [&](const ExecutionEvent& other){ return other.cursor == event.cursor; });
            if (first == events.end() || !same_event(*first, event)) { s = fail(ErrorCode::Conflict, "批次游标内容冲突"); break; }
            continue;
        }
        for (const auto& old : delivered_) if (old.second.event_id == event.event_id) { s = fail(ErrorCode::Conflict, "回报身份重复但游标不同"); break; }
        if (!s.ok()) break;
        for (const auto& other : events) if (&other != &event && other.event_id == event.event_id && !same_event(other, event)) { s = fail(ErrorCode::Conflict, "批次回报身份内容冲突"); break; }
        if (!s.ok()) break;
        if (!text_valid(event.event_id, 128) || event.cursor != last + 1) { s = fail(ErrorCode::Conflict, "回报存在缺口或乱序"); break; }
        if (event.is_trade ? !valid_trade(event.trade) : !valid_order(event.order)) { s = fail(ErrorCode::InvalidInput, "回报字段非法"); break; }
        if (event.is_trade)
        {
            auto key = trade_key(event.identity, event.trade); auto old = staged_trades.find(key);
            if (old != staged_trades.end() && !same_trade(old->second, event.trade)) { s = fail(ErrorCode::Conflict, "同一柜台成交身份出现内容冲突"); break; }
            if (old == staged_trades.end())
            {
                if (staged_trades.size() >= config_.index_capacity) { s = fail(ErrorCode::Backpressure, "原生成交派生窗口已满，保留全部身份并等待受控新基线"); break; }
                staged_trades[key] = event.trade;
            }
        }
        last = event.cursor;
    }
    if (!s.ok()) { state_.resuming = false; query_failure(s); return s; }
    struct DispatchGuard { bool& flag; explicit DispatchGuard(bool& value) : flag(value) { flag = true; } ~DispatchGuard() { flag = false; } } guard(dispatching_reports_);
    for (const auto& event : events)
    {
        if (event.cursor <= cursor_) continue;
        if (delivery_unknown_ || (!state_.consumer_ready && !state_.resuming)) return fail(ErrorCode::SubmissionUnknown, "WT消费者已隔离，当前批次停止归约");
        if (!state_.connected || !identity_equal(event.identity, config_.identity)) return fail(ErrorCode::StaleSession, "回调重入改变会话");
        if (!spi_) return fail(ErrorCode::Pending, "尚未注册回报消费者");
        // 消费者成功接收后推进派生游标；异常保留原游标，Host仍持有持久事件。
        if (event.is_trade)
        {
            auto key = trade_key(event.identity, event.trade);
            if (!native_trades_.count(key))
            {
                auto t = make_trade(event.trade, spi_);
                try { spi_->onPushTrade(t); }
                catch (...)
                {
                    t->release(); return isolate_consumer("WT成交回调可能已计仓，已撤销通道资格，禁止重投");
                }
                t->release();
                if (delivery_unknown_ || (!state_.consumer_ready && !state_.resuming))
                {
                    return isolate_consumer("重入回调已隔离WT消费者，停止本批次且禁止重投");
                }
                native_trades_[key] = event.trade;
            }
        }
        else
        {
            auto o = make_order(event.order, spi_);
            try { spi_->onPushOrder(o); } catch (...) { o->release(); return isolate_consumer("WT委托回调应用结果未知，已撤销通道资格，禁止重投"); }
            o->release();
            if (delivery_unknown_ || (!state_.consumer_ready && !state_.resuming))
            {
                return isolate_consumer("重入回调已隔离WT消费者，停止本批次且禁止重投");
            }
        }
        cursor_ = event.cursor;
        delivered_[cursor_] = event;
        if (delivered_.size() > config_.index_capacity) delivered_.erase(delivered_.begin());
        if (delivery_unknown_ || (!state_.consumer_ready && !state_.resuming)) return fail(ErrorCode::SubmissionUnknown, "回调后WT消费者被隔离");
        if (!state_.connected || !state_.logged_in || !identity_equal(event.identity, config_.identity))
            return fail(ErrorCode::Unavailable, "已保存本次消费进度，连接变化后停止剩余回报");
    }
    if (state_.resuming)
    {
        if (cursor_ == resume_proof_.through_cursor) return finish_resume();
        if (cursor_ == before_poll) { state_.resuming = false; auto gap = fail(ErrorCode::Conflict, "Host已证明的冻结前沿仍有不可读取缺口"); query_failure(gap); return gap; }
        return fail(ErrorCode::Pending, "正在禁写补投到Host冻结前沿");
    }
    return {};
}
Status ManagedTrader::inspect_reports(std::uint64_t after, std::size_t limit, std::uint32_t budget_ms, std::vector<ExecutionEvent>& output)
{
    std::lock_guard<std::recursive_mutex> lock(mutex_); output.clear();
    if (!limit || limit > config_.event_batch || !budget_ms || budget_ms > config_.budget_ms) return fail(ErrorCode::InvalidInput, "诊断回报预算非法");
    auto s = ready(capabilities().reports, false);
    try { if (s.ok()) s = endpoint_->events(after, limit, output, budget_ms); } catch (...) { s = fail(ErrorCode::IoError, "诊断回报读取异常"); }
    if (s.ok() && output.size() > limit) s = fail(ErrorCode::Backpressure, "诊断回报超过容量");
    if (s.ok()) for (const auto& event : output)
        if (!identity_equal(event.identity, config_.identity) || !baseline_ready_ || event.stream_id != bootstrap_.baseline.stream_id)
        { s = fail(ErrorCode::StaleSession, "诊断回报身份或流不匹配"); break; }
    if (!s.ok()) output.clear(); return s;
}
Status ManagedTrader::reconcile()
{
    std::lock_guard<std::recursive_mutex> lock(mutex_);
    if (delivery_unknown_) return fail(ErrorCode::SubmissionUnknown, "WT消费者应用结果未知，Host恢复证明不能证明消费者已应用范围，需重建消费者");
    if (native_trades_.size() >= config_.index_capacity) return fail(ErrorCode::Backpressure, "成交派生窗口已满，需要受控新消费者原子基线");
    if (!endpoint_ || !state_.connected) return fail(ErrorCode::Unavailable, "原Host尚未连接");
    Status s;
    try { s = endpoint_->reconcile(config_.identity, config_.budget_ms); } catch (...) { s = fail(ErrorCode::Pending, "Host恢复证明读取异常"); }
    if (s.ok()) { recovery_required_ = false; state_.writes_blocked = !state_.logged_in || !state_.consumer_ready; state_.stage = SubmissionStage::NotCalled; }
    publish(s); return s;
}
}
