#include "OwnerExecCommand.h"
#include "Includes/WTSDataDef.hpp"
#include <chrono>
#include <cmath>
#include <cstring>
#include <deque>
#include <limits>
#include <mutex>
#include <stdexcept>
#include <thread>
#include <type_traits>
#include <vector>

namespace guanheng {
namespace {
using Clock=std::chrono::steady_clock;
struct Target { char code[64]={}; double value=0; };
struct Command {
    enum class Kind { Targets, Delta, Tick } kind=Kind::Delta;
    char code[64]={}; double delta=0;
    wtp::WTSTickStruct tick={};
    std::vector<Target> targets;
    Clock::time_point expires;
    std::uint64_t sequence=0;
    std::size_t charge() const { return sizeof(Command)+targets.capacity()*sizeof(Target); }
};
static_assert(std::is_trivially_copyable<wtp::WTSTickStruct>::value,"tick queue requires independent values");
bool copy_code(char (&output)[64],const char* input) {
    if(!input)return false;
    std::size_t n=0;
    while(n<64 && input[n]) { if(static_cast<unsigned char>(input[n])<=32)return false; ++n; }
    if(!n||n>=64)return false;
    std::memcpy(output,input,n);output[n]=0;return true;
}
struct TickRelease { void operator()(wtp::WTSTickData* value)const {if(value)value->release();} };
}
class OwnerExecCommand::Impl {
public:
    Impl(wtp::IExecCommand& target,ContractLookup resolve,ExecutionQueueLimits bound)
        : destination(target),lookup(std::move(resolve)),limits(bound),owner(std::this_thread::get_id()) {
        if(!lookup || !limits.max_commands || limits.max_commands>1024 || !limits.max_targets
            || limits.max_targets>4096 || limits.max_payload_bytes<sizeof(Command)
            || limits.max_payload_bytes>64u*1024u*1024u || !limits.max_queue_delay_ms || limits.max_queue_delay_ms>30000)
            throw std::invalid_argument("execution_owner_queue_limits");
        view.accepting=true;
    }
    void clear_locked() {
        for(const auto& item:queue)view.payload_bytes-=item.charge();
        queue.clear();view.queued_commands=0;
    }
    void fault_locked(ExecutionQueueFault fault) {
        if(view.fault==ExecutionQueueFault::None)view.fault=fault;
        view.accepting=false;clear_locked();
    }
    void fault(ExecutionQueueFault reason) noexcept {
        std::lock_guard<std::mutex> lock(mutex);++view.rejected;fault_locked(reason);
    }
    void enqueue(Command&& item) noexcept {
        std::lock_guard<std::mutex> lock(mutex);
        if(!view.accepting){++view.rejected;return;}
        const auto charge=item.charge();
        if(queue.size()+(view.inflight?1u:0u)>=limits.max_commands || charge>limits.max_payload_bytes-view.payload_bytes
            || view.accepted==(std::numeric_limits<std::uint64_t>::max)()) {
            ++view.rejected;fault_locked(ExecutionQueueFault::Capacity);return;
        }
        item.sequence=view.accepted+1;
        try { queue.push_back(std::move(item)); }
        catch(...) { ++view.rejected;fault_locked(ExecutionQueueFault::Capacity);return; }
        ++view.accepted;view.payload_bytes+=charge;view.queued_commands=queue.size();
    }
    void finish(const Command& item,bool delivered,ExecutionQueueFault fault=ExecutionQueueFault::None) {
        std::lock_guard<std::mutex> lock(mutex);
        if(delivered)view.delivered=item.sequence;
        view.inflight=false;view.payload_bytes-=item.charge();
        if(fault!=ExecutionQueueFault::None)fault_locked(fault);
    }
    void enter(std::uint64_t sequence) {
        std::lock_guard<std::mutex> lock(mutex);view.entered=sequence;
    }
    wtp::IExecCommand& destination;
    ContractLookup lookup;
    const ExecutionQueueLimits limits;
    const std::thread::id owner;
    mutable std::mutex mutex;
    std::deque<Command> queue;
    ExecutionQueueStatus view;
    bool draining=false; // 仅owner访问；目标回调可能重入drain。
};
OwnerExecCommand::OwnerExecCommand(const char* name,wtp::IExecCommand& target,ContractLookup lookup,ExecutionQueueLimits limits)
    : IExecCommand(name?name:""),impl_(new Impl(target,std::move(lookup),limits)) {
    char checked[64];if(!copy_code(checked,name))throw std::invalid_argument("execution_owner_name");
}
OwnerExecCommand::~OwnerExecCommand() { close(); }
void OwnerExecCommand::set_position(const wtp::wt_hashmap<std::string,double>& values) noexcept {
    Command item;item.kind=Command::Kind::Targets;
    item.expires=Clock::now()+std::chrono::milliseconds(impl_->limits.max_queue_delay_ms);
    if(values.size()>impl_->limits.max_targets){impl_->fault(ExecutionQueueFault::Capacity);return;}
    try {
        item.targets.reserve(values.size());
        for(const auto& pair:values) {
            Target target;
            if(!std::isfinite(pair.second)||!copy_code(target.code,pair.first.c_str())||std::strlen(target.code)!=pair.first.size()){impl_->fault(ExecutionQueueFault::InvalidInput);return;}
            target.value=pair.second;item.targets.push_back(target);
        }
        impl_->enqueue(std::move(item));
    } catch(...) {impl_->fault(ExecutionQueueFault::Capacity);}
}
void OwnerExecCommand::on_position_changed(const char* code,double delta) noexcept {
    Command item;item.kind=Command::Kind::Delta;item.delta=delta;
    item.expires=Clock::now()+std::chrono::milliseconds(impl_->limits.max_queue_delay_ms);
    if(!std::isfinite(delta)||!copy_code(item.code,code)){impl_->fault(ExecutionQueueFault::InvalidInput);return;}
    impl_->enqueue(std::move(item));
}
void OwnerExecCommand::on_tick(const char* code,wtp::WTSTickData* tick) noexcept {
    Command item;item.kind=Command::Kind::Tick;
    item.expires=Clock::now()+std::chrono::milliseconds(impl_->limits.max_queue_delay_ms);
    if(!tick||!copy_code(item.code,code)){impl_->fault(ExecutionQueueFault::InvalidInput);return;}
    item.tick=tick->getTickStruct();impl_->enqueue(std::move(item));
}
std::size_t OwnerExecCommand::drain(std::size_t maximum) noexcept {
    if(impl_->owner!=std::this_thread::get_id()){impl_->fault(ExecutionQueueFault::WrongOwner);return 0;}
    if(impl_->draining){impl_->fault(ExecutionQueueFault::ReentrantDrain);return 0;}
    impl_->draining=true;
    struct DrainingReset { bool& value;~DrainingReset(){value=false;} } reset{impl_->draining};
    std::size_t delivered=0;
    while(delivered<maximum) {
        Command item;
        {
            std::lock_guard<std::mutex> lock(impl_->mutex);
            if(!impl_->view.accepting||impl_->queue.empty())break;
            item=std::move(impl_->queue.front());impl_->queue.pop_front();
            impl_->view.queued_commands=impl_->queue.size();impl_->view.inflight=true;
        }
        if(Clock::now()>=item.expires){impl_->finish(item,false,ExecutionQueueFault::Expired);break;}
        try {
            if(item.kind==Command::Kind::Targets) {
                wtp::wt_hashmap<std::string,double> targets;
                for(const auto& value:item.targets)targets[value.code]=value.value;
                impl_->enter(item.sequence);impl_->destination.set_position(targets);
            } else if(item.kind==Command::Kind::Delta) {
                impl_->enter(item.sequence);impl_->destination.on_position_changed(item.code,item.delta);
            } else {
                auto* contract=impl_->lookup(item.code);
                if(!contract)throw std::runtime_error("execution_owner_tick_metadata");
                std::unique_ptr<wtp::WTSTickData,TickRelease> tick(wtp::WTSTickData::create(item.tick));
                if(!tick)throw std::runtime_error("execution_owner_tick_allocation");
                tick->setContractInfo(contract);
                impl_->enter(item.sequence);impl_->destination.on_tick(item.code,tick.get());
            }
            impl_->finish(item,true);++delivered;
        } catch(...) {impl_->finish(item,false,ExecutionQueueFault::Destination);break;}
    }
    return delivered;
}
ExecutionQueueStatus OwnerExecCommand::status() const {
    std::lock_guard<std::mutex> lock(impl_->mutex);return impl_->view;
}
void OwnerExecCommand::close() noexcept {
    if(!impl_)return;
    std::lock_guard<std::mutex> lock(impl_->mutex);impl_->view.accepting=false;impl_->clear_locked();
}
}
