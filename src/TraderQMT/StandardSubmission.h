#pragma once
#include <cstdint>
#include "Includes/ITraderApi.h"

namespace guanheng {
// 仅自有query_first提交门；不表示券商挂单数量或已完成启动恢复。
enum class SubmissionDecision : std::uint32_t {
 Admitted=0,BlockedAwait,BlockedBusy,WrongOwner,Stopped,Capacity,ModeMismatch,Invalid,Fault,
 BlockedFunds=9, // 自有Local在提交组创建前缺少已知足额CNY观察；未产生新命令。
 BlockedAttribution=10 // 显式ASA准入暂缓；无原group、child或dispatch，原目标仍待执行。
};
enum class SubmissionObservation : std::uint32_t {
 None=0,AwaitBrokerObservation,Unknown,ObservedActive,TerminalNeedsReconciliation,Fault
};
enum class SubmissionOutcome : std::uint32_t {Returned=0,Threw=1};
struct SubmissionKeyV1 {
 std::uint32_t version=1,size=sizeof(SubmissionKeyV1);char exchange[5]={},code[7]={};
 std::uint32_t side=0; // 0=Buy，1=Sell；同证券双方向共用未决责任。
};
struct SubmissionTokenV1 {
 std::uint32_t version=1,size=sizeof(SubmissionTokenV1);std::uint64_t generation=0,group_id=0;
};
struct SubmissionViewV1 {
 std::uint32_t version=1,size=sizeof(SubmissionViewV1);
 SubmissionDecision decision=SubmissionDecision::Invalid;
 SubmissionObservation observation=SubmissionObservation::None;
 std::uint64_t group_id=0;std::uint32_t accepted_children=0,unresolved_children=0;
};
using BeginSubmissionFn=int(*)(wtp::ITraderApi*,const SubmissionKeyV1*,SubmissionTokenV1*,SubmissionViewV1*) noexcept;
using EndSubmissionFn=int(*)(wtp::ITraderApi*,const SubmissionTokenV1*,std::uint32_t,SubmissionViewV1*) noexcept;
using InspectSubmissionFn=int(*)(wtp::ITraderApi*,const SubmissionKeyV1*,SubmissionViewV1*) noexcept;
}
