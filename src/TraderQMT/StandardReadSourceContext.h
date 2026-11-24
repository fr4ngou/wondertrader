#pragma once
#include "StandardReadSource.h"
#include "GuanhengCommon/QmtHostTradeClient.h"
#include <atomic>
namespace guanheng {
inline std::uint32_t read_context_differences(const QmtTradeEventReadContext& origin,
 const QmtTradeEventReadContext& current) noexcept
{
 return (origin.source.session_id!=current.source.session_id?ReadSourceSession:0u)
  |(origin.read_profile_body!=current.read_profile_body?ReadSourceProfile:0u)
  |(origin.read_result_capacity!=current.read_result_capacity?ReadSourceResultCapacity:0u)
  |(origin.admitted_event_page_capacity!=current.admitted_event_page_capacity?ReadSourcePageCapacity:0u);
}
class ReadSourceFailure {
 // 阶段与差异位一次CAS发布，读取不会拼出不同故障的半份旁证。
 std::atomic<std::uint64_t> first_{0};
public:
 void capture(ReadSourceStage stage,std::uint32_t differences) noexcept {
  if(!differences)return;
  std::uint64_t expected=0;
  first_.compare_exchange_strong(expected,(static_cast<std::uint64_t>(stage)<<32)|differences);
 }
 ReadSourceDiagnosticsV1 snapshot()const noexcept {
  const auto value=first_.load();ReadSourceDiagnosticsV1 out;
  out.captured=value?1u:0u;out.stage=static_cast<std::uint32_t>(value>>32);
  out.differences=static_cast<std::uint32_t>(value);return out;
 }
};
}
