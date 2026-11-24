#pragma once
#include <cstdint>
namespace guanheng {
// 读取来源比较位置；值只作诊断，不控制执行或恢复。
enum class ReadSourceStage : std::uint32_t { Reuse=1, Open=2, Prepare=3, EventPage=4 };
enum ReadSourceDifference : std::uint32_t {
 ReadSourceUninitialized=1, // 原来源尚未初始化。
 ReadSourceSession=2, // Source业务session变化。
 ReadSourceProfile=4, // 完整读取profile正文变化。
 ReadSourceResultCapacity=8, // 读取结果容量变化。
 ReadSourcePageCapacity=16, // 事件页容量变化。
 ReadSourceBindingInvalid=32, // 原或新binding未通过既有结构校验。
 ReadSourceStableBinding=64 // 排除原两项运输身份后的binding变化。
};
// 可选纯值诊断ABI；没有原始来源值，不授交易或恢复资格。
struct ReadSourceDiagnosticsV1 {
 std::uint32_t version=1; // 独立诊断版本，错版拒绝。
 std::uint32_t size=sizeof(ReadSourceDiagnosticsV1); // 实际结构字节数，防止混编越界。
 std::uint32_t captured=0; // 1表示首次来源差异已冻结；0保持未发生。
 std::uint32_t stage=0; // 原比较位置，取ReadSourceStage；0表示未捕获。
 std::uint32_t differences=0; // 实际已检查字段的差异位，取ReadSourceDifference。
};
}
