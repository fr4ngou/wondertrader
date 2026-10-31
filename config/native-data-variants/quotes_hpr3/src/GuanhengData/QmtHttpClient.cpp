#include "QmtHttpClient.h"
#include <utility>

namespace guanheng
{
QmtHttpClient::QmtHttpClient(QmtHttpConfig config) : transport_(std::move(config),QmtReadDomain::Market) {}
QmtHttpClient::~QmtHttpClient() = default;
Status QmtHttpClient::prepare(std::uint32_t budget) { return transport_.prepare(budget); }
SourceSession QmtHttpClient::session() const { return transport_.session(); }
Capability QmtHttpClient::capability(const std::string& operation) const { return transport_.capability(operation); }
std::string QmtHttpClient::last_source_time() const { return transport_.last_source_time(); }
JsonResult QmtHttpClient::read_operation(const std::string& operation, const std::string& input, std::uint32_t budget)
{ return transport_.read_operation(operation,input,budget); }
Status QmtHttpClient::drain_callbacks(std::uint32_t budget) noexcept { return transport_.drain_callbacks(budget); }
}
