#pragma once
#include "AccountMapping.h"
#include "GuanhengCommon/QmtHostAccountClient.h"

namespace guanheng { namespace bootstrap {
// 仅值比较结果；Matched不认证输入，不授金融发布、身份认领或SPI资格。
enum class AccountEventMatchKind {
 Matched, NotRequired, InvalidEvent, EventLocatorMissing, NotMatched,
 Ambiguous, InvalidQuery, UncertainQuery, IncompleteMatch, Conflict
};
struct AccountEventMatchLimits {
 std::size_t max_event_bytes, max_query_bytes, max_rows, max_work_bytes;
};
struct AccountEventMatchResult {
 AccountEventMatchKind kind=AccountEventMatchKind::NotMatched;
 // 仅Matched时有可用索引；其余结果固定为size_t最大值。
 std::size_t row_index=static_cast<std::size_t>(-1);
 std::size_t query_rows=0,scanned_rows=0,matched_rows=0,invalid_rows=0,uncertain_rows=0;
 std::uint64_t event_missing=0,event_invalid=0,conflict_fields=0;
 std::uint32_t event_relations=0;
 std::size_t query_bytes=0,peak_work_bytes=0;
};
// query必须是同次Core已采用的原AccountV4/account2结果，认证/标头/同B/同D由caller负责。
// 纯值函数不调用任何client；原事件和完整query均借用到返回，结果不持有输入。
// 只返回整条原query行索引，不拼字段、不改原DTO。结构/预算/资源失败抛原异常；
// 赋值式调用失败保留旧结果，caller在调用前后核原D与专用event_control。
AccountEventMatchResult match_account_event_row(unsigned stage,const std::string& event_row_json,
 const QmtAccountResult& query,const AccountBinding&,const AccountEventMatchLimits&);
}}
