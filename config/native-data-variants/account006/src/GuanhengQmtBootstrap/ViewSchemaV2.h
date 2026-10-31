#pragma once
#include "GuanhengCommon/QmtAccountFields.h"
// 原观察v2只保留命名桥和版本；Common不依赖Bootstrap或任何运输协议。
namespace guanheng { namespace bootstrap { namespace fields {
using namespace ::guanheng::account_fields;
constexpr unsigned view_version=2;
}}}
