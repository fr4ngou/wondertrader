#include "QmtHostHistoryClient.h"
#include "QmtBoundReadCore.h"
#include <stdexcept>

namespace guanheng
{
QmtHostHistoryClient::QmtHostHistoryClient(QmtHttpConfig config, const QmtHistoryControl* control, QmtReadProfileVersion version)
    : core_(new QmtBoundReadCore(std::move(config), version==QmtReadProfileVersion::Legacy?QmtBoundProfile::History1mV2:QmtBoundProfile::History1mV3, control)) {
    if(version!=QmtReadProfileVersion::Legacy&&version!=QmtReadProfileVersion::AccountV3)
        throw std::invalid_argument("qmt_bound_profile_invalid");
}
QmtHostHistoryClient::~QmtHostHistoryClient() = default;
Status QmtHostHistoryClient::prepare(SignedHttpDeadline& end) { return core_->prepare(end); }
SourceSession QmtHostHistoryClient::session() const { return core_->session(); }
Capability QmtHostHistoryClient::capability() const { return core_->capability(); }
QmtHistoryPreparation QmtHostHistoryClient::create_request(const QmtHistoryRequest& request, SignedHttpDeadline& end)
{ return core_->create_history(request, end); }
QmtHistoryResult QmtHostHistoryClient::submit_once(std::unique_ptr<QmtPreparedHistoryRead> request, SignedHttpDeadline& end)
{ return core_->submit_history(std::move(request), end); }
QmtHistoryResult QmtHostHistoryClient::resume(const QmtBoundReceipt& request, SignedHttpDeadline& end)
{ return core_->resume_history(request, end); }
Status QmtHostHistoryClient::drain_callbacks(std::uint32_t milliseconds) noexcept
{ return core_->drain_callbacks(milliseconds); }
}
