#include "EventDeliveryIndex.h"
#include <atomic>
#include <cmath>
#include <limits>
#include <map>
#include <stdexcept>
#include <string_view>
#include <thread>
#include <utility>

namespace guanheng {
namespace {
// R4a的逻辑有效载荷预留；固定项覆盖索引结构，不表示sizeof或RSS。
constexpr std::size_t base_bytes=128,transport_bytes=96,snapshot_bytes=128;
constexpr std::size_t hard_records=1000000,hard_bytes=512u*1024u*1024u;
constexpr std::uint64_t max_sequence=9007199254740991ULL;
enum class Phase { Reserved,Started,Returned,Unknown,Suppressed };

bool add_size(std::size_t& total,std::size_t value,std::size_t maximum) noexcept {
 if(total>maximum||value>maximum-total)return false;
 total+=value;return true;
}
bool add_text(std::size_t& total,const std::string& value,std::size_t maximum) noexcept {
 return add_size(total,value.size(),maximum)&&add_size(total,1,maximum);
}
bool digest(const std::string& value) noexcept {
 if(value.size()!=64)return false;
 for(char c:value)if(!((c>='0'&&c<='9')||(c>='a'&&c<='f')))return false;
 return true;
}
bool valid(const QmtEventDeliveryObservation& value) noexcept {
 if(value.sequence==0||value.sequence>max_sequence||!digest(value.derived_event_sha256)
    ||!std::isfinite(value.order_filled)||value.order_filled<0)return false;
 if(value.diagnostic)return !value.is_trade&&!value.order_terminal&&value.order_filled==0
    &&value.canonical_key.empty()&&value.derived_facts_sha256.empty()&&value.identity_signature.empty();
 return !value.canonical_key.empty()&&digest(value.derived_facts_sha256)&&!value.identity_signature.empty();
}
bool same(const QmtEventDeliveryObservation& left,const QmtEventDeliveryObservation& right) noexcept {
 return left.sequence==right.sequence&&left.derived_event_sha256==right.derived_event_sha256
  &&left.canonical_key==right.canonical_key&&left.derived_facts_sha256==right.derived_facts_sha256
  &&left.identity_signature==right.identity_signature&&left.is_trade==right.is_trade
  &&left.order_terminal==right.order_terminal&&left.diagnostic==right.diagnostic&&left.order_filled==right.order_filled;
}
QmtEventDeliveryDisposition disposition(Phase phase) noexcept {
 switch(phase) {
 case Phase::Reserved:case Phase::Started:return QmtEventDeliveryDisposition::Pending;
 case Phase::Returned:return QmtEventDeliveryDisposition::Duplicate;
 case Phase::Unknown:return QmtEventDeliveryDisposition::Unknown;
 case Phase::Suppressed:return QmtEventDeliveryDisposition::Suppressed;
 }
 return QmtEventDeliveryDisposition::Rejected;
}
QmtEventDeliveryAdmission rejected(ErrorCode code,const char* reason) {
 QmtEventDeliveryAdmission result;result.status={code,reason};return result;
}
QmtEventDeliveryAdmission observed(Phase phase) {
 QmtEventDeliveryAdmission result;result.disposition=disposition(phase);return result;
}
std::uint64_t instance_id() {
 static std::atomic<std::uint64_t> next{1};
 auto value=next.load(std::memory_order_relaxed);
 for(;;) {
  if(value==std::numeric_limits<std::uint64_t>::max())throw std::overflow_error("event delivery instance exhausted");
  if(next.compare_exchange_weak(value,value+1,std::memory_order_relaxed))return value;
 }
}
}

struct QmtEventDeliveryIndex::State {
 struct Group;
 struct Snapshot {
  std::string key,facts,signature;
  double filled=0;bool terminal=false;
  Phase phase=Phase::Reserved;Group* group=nullptr;
  explicit Snapshot(const QmtEventDeliveryObservation& v)
   :key(v.canonical_key),facts(v.derived_facts_sha256),signature(v.identity_signature),
    filled(v.order_filled),terminal(v.order_terminal){}
 };
 struct Group {
  bool trade=false,returned=false,terminal=false;
  double filled=0;
  Snapshot* first=nullptr;Snapshot* unresolved=nullptr;
  // string_view只引用本组稳定unique_ptr所拥有的字符串；不额外复制金融正文。
  std::map<std::string_view,std::unique_ptr<Snapshot>,std::less<>> snapshots;
 };
 struct Transport {
  QmtEventDeliveryObservation value;
  Snapshot* snapshot=nullptr;Phase phase=Phase::Reserved;
  Transport(const QmtEventDeliveryObservation& v,Snapshot* s):value(v),snapshot(s){}
  Phase current() const noexcept {return snapshot?snapshot->phase:phase;}
 };
 const std::thread::id owner=std::this_thread::get_id();
 const std::uint64_t identity=instance_id();
 const std::string binding,session;
 const std::size_t max_records,max_bytes;
 QmtEventDeliveryUsage used;
 std::map<std::string_view,std::unique_ptr<Group>,std::less<>> groups;
 std::map<std::uint64_t,Transport> transports;
 State(std::string b,std::string s,std::size_t records,std::size_t bytes,std::size_t base)
  :binding(std::move(b)),session(std::move(s)),max_records(records),max_bytes(bytes),used{0,base}{}
 bool owned() const noexcept {return owner==std::this_thread::get_id();}
 bool room(std::size_t records,std::size_t bytes) const noexcept {
  return used.records<=max_records&&records<=max_records-used.records
   &&used.bytes<=max_bytes&&bytes<=max_bytes-used.bytes;
 }
};

QmtEventDeliveryIndex::QmtEventDeliveryIndex(std::string binding,std::string session,
 std::size_t max_records,std::size_t max_bytes) {
 std::size_t base=base_bytes;
 if(binding.empty()||session.empty()||max_records==0||max_records>hard_records||max_bytes==0
    ||max_bytes>hard_bytes||!add_text(base,binding,max_bytes)||!add_text(base,session,max_bytes))
  throw std::invalid_argument("event delivery limits or source invalid");
 state_.reset(new State(std::move(binding),std::move(session),max_records,max_bytes,base));
}
QmtEventDeliveryIndex::~QmtEventDeliveryIndex()=default;

QmtEventDeliveryAdmission QmtEventDeliveryIndex::reserve(const QmtEventDeliveryObservation& value) {
 auto& state=*state_;
 if(!state.owned())return rejected(ErrorCode::Conflict,"event_delivery_wrong_owner");
 if(!valid(value))return rejected(ErrorCode::InvalidInput,"event_delivery_invalid");
 auto prior=state.transports.find(value.sequence);
 if(prior!=state.transports.end()) {
  if(!same(prior->second.value,value))return rejected(ErrorCode::Conflict,"event_delivery_sequence_conflict");
  return observed(prior->second.current());
 }
 State::Group* group=nullptr;State::Snapshot* snapshot=nullptr;
 if(!value.diagnostic) {
  auto found=state.groups.find(value.canonical_key);
  if(found!=state.groups.end()) {
   group=found->second.get();
   if(group->trade!=value.is_trade||group->first->signature!=value.identity_signature)
    return rejected(ErrorCode::Conflict,"event_delivery_identity_conflict");
   auto exact=group->snapshots.find(value.derived_facts_sha256);
   if(exact!=group->snapshots.end()) {
    snapshot=exact->second.get();
    if(snapshot->filled!=value.order_filled||snapshot->terminal!=value.order_terminal)
     return rejected(ErrorCode::Conflict,"event_delivery_snapshot_conflict");
   } else if(group->trade) return rejected(ErrorCode::Conflict,"event_delivery_trade_conflict");
   // 未准入的新seq没有交付事实；旧项后来返回时，调用方可原值重取并重新判断。
   if(group->unresolved)return observed(group->unresolved->phase);
   if(!snapshot&&(group->terminal||(group->returned&&value.order_filled<group->filled)))
    return rejected(ErrorCode::Conflict,"event_delivery_order_regression");
  }
 }
 const bool new_snapshot=!value.diagnostic&&!snapshot;
 const std::size_t records=new_snapshot?2:1;
 std::size_t bytes=transport_bytes;
 for(const auto* text:{&value.derived_event_sha256,&value.canonical_key,&value.derived_facts_sha256,&value.identity_signature})
  if(!add_text(bytes,*text,state.max_bytes))return rejected(ErrorCode::Backpressure,"event_delivery_capacity");
 if(new_snapshot) {
  if(!add_size(bytes,snapshot_bytes,state.max_bytes))return rejected(ErrorCode::Backpressure,"event_delivery_capacity");
  for(const auto* text:{&value.canonical_key,&value.derived_facts_sha256,&value.identity_signature})
   if(!add_text(bytes,*text,state.max_bytes))return rejected(ErrorCode::Backpressure,"event_delivery_capacity");
 }
 if(!state.room(records,bytes))return rejected(ErrorCode::Backpressure,"event_delivery_capacity");

 // 两索引提交前完成所有字符串复制。第二次插入失败撤销第一次，usage与原phase均不变。
 std::unique_ptr<State::Snapshot> pending;
 if(new_snapshot)pending.reset(new State::Snapshot(value));
 if(pending)snapshot=pending.get();
 State::Transport transport(value,snapshot);
 bool group_added=false,snapshot_added=false;
 decltype(state.groups)::iterator group_it=state.groups.end();
 decltype(State::Group::snapshots)::iterator snapshot_it;
 try {
  if(new_snapshot) {
   if(!group) {
    auto owned=std::make_unique<State::Group>();group=owned.get();group->trade=value.is_trade;group->first=snapshot;
    snapshot->group=group;
    const std::string_view facts=snapshot->facts,key=snapshot->key;
    group->snapshots.emplace(facts,std::move(pending));
    group_it=state.groups.emplace(key,std::move(owned)).first;group_added=true;
   } else {
    snapshot->group=group;
    const std::string_view facts=snapshot->facts;
    snapshot_it=group->snapshots.emplace(facts,std::move(pending)).first;snapshot_added=true;
   }
  }
  state.transports.emplace(value.sequence,std::move(transport));
 } catch(...) {
  if(group_added)state.groups.erase(group_it);
  else if(snapshot_added)group->snapshots.erase(snapshot_it);
  throw;
 }
 state.used.records+=records;state.used.bytes+=bytes;
 if(new_snapshot)group->unresolved=snapshot;
 if(snapshot&&!new_snapshot)return observed(snapshot->phase);
 QmtEventDeliveryAdmission result;result.disposition=QmtEventDeliveryDisposition::Deliver;
 result.ticket.owner_=state.identity;result.ticket.id_=value.sequence;return result;
}

bool QmtEventDeliveryIndex::start(const QmtEventDeliveryTicket& ticket) noexcept {
 auto& state=*state_;
 if(!state.owned()||ticket.owner_!=state.identity||ticket.id_==0)return false;
 auto found=state.transports.find(ticket.id_);
 if(found==state.transports.end())return false;
 auto& phase=found->second.snapshot?found->second.snapshot->phase:found->second.phase;
 if(phase!=Phase::Reserved)return false;
 phase=Phase::Started;return true;
}
bool QmtEventDeliveryIndex::finish(const QmtEventDeliveryTicket& ticket,QmtEventDeliveryOutcome outcome) noexcept {
 auto& state=*state_;
 if(!state.owned()||ticket.owner_!=state.identity||ticket.id_==0)return false;
 auto found=state.transports.find(ticket.id_);
 if(found==state.transports.end())return false;
 auto* snapshot=found->second.snapshot;
 auto& phase=snapshot?snapshot->phase:found->second.phase;
 if(outcome==QmtEventDeliveryOutcome::Suppressed) {
  if(phase!=Phase::Reserved)return false;
  phase=Phase::Suppressed;return true;
 }
 if(phase!=Phase::Started||(outcome!=QmtEventDeliveryOutcome::Returned&&outcome!=QmtEventDeliveryOutcome::Unknown))return false;
 phase=outcome==QmtEventDeliveryOutcome::Returned?Phase::Returned:Phase::Unknown;
 if(snapshot&&phase==Phase::Returned) {
  auto& group=*snapshot->group;
  group.returned=true;group.filled=snapshot->filled;group.terminal=group.terminal||snapshot->terminal;
  group.unresolved=nullptr;
 }
 return true;
}
QmtEventDeliveryUsage QmtEventDeliveryIndex::usage() const noexcept {
 return state_->owned()?state_->used:QmtEventDeliveryUsage{};
}
}
