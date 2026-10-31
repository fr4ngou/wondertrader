#pragma once
#include "GuanhengCommon/ProviderTypes.h"
#include <cstddef>
#include <cstdint>
#include <memory>
#include <string>

namespace guanheng {
// 有界内存交付标识；唯一owner串行调用，不保存或归约账户持仓/资金。
struct QmtEventDeliveryObservation {
 std::uint64_t sequence=0;
 std::string derived_event_sha256,canonical_key,derived_facts_sha256,identity_signature;
 bool is_trade=false,order_terminal=false,diagnostic=false;
 double order_filled=0;
};
enum class QmtEventDeliveryDisposition { Deliver,Duplicate,Pending,Unknown,Suppressed,Rejected };
enum class QmtEventDeliveryOutcome { Returned,Unknown,Suppressed };
class QmtEventDeliveryIndex;
class QmtEventDeliveryTicket {
public: QmtEventDeliveryTicket()=default;
private:
 std::uint64_t owner_=0,id_=0;
 friend class QmtEventDeliveryIndex;
};
struct QmtEventDeliveryAdmission {
 Status status;
 QmtEventDeliveryDisposition disposition=QmtEventDeliveryDisposition::Rejected;
 QmtEventDeliveryTicket ticket;
};
struct QmtEventDeliveryUsage {std::size_t records=0,bytes=0;};
// 原B/session在构造时冻结，寿命限于当前插件实例；满额不逐出旧交付事实。
class QmtEventDeliveryIndex {
public:
 QmtEventDeliveryIndex(std::string binding_json,std::string session_id,
   std::size_t max_records,std::size_t max_bytes);
 ~QmtEventDeliveryIndex();
 QmtEventDeliveryIndex(const QmtEventDeliveryIndex&)=delete;
 QmtEventDeliveryIndex& operator=(const QmtEventDeliveryIndex&)=delete;
 QmtEventDeliveryAdmission reserve(const QmtEventDeliveryObservation&);
 // start在实际SPI调用前，finish在其返回/异常/明确未调用后；均不分配。
 bool start(const QmtEventDeliveryTicket&) noexcept;
 bool finish(const QmtEventDeliveryTicket&,QmtEventDeliveryOutcome) noexcept;
 QmtEventDeliveryUsage usage() const noexcept;
private: struct State;std::unique_ptr<State> state_;
};
}
