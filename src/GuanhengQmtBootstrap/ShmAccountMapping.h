#pragma once
#include "AccountMapping.h"
#include "GuanhengCommon/QmtHostAccountClient.h"

namespace guanheng { namespace bootstrap {
// owner只传原Account Core同次成功采用的返回值，不接不可信反序列化/人工拼装结果。
// Core独占原bytes/SHA/三B/末次binding认证；本层的成功标志检查不是新认证入口。
// 先核本任务stage/固定账户及来源metadata，随后只调用唯一金融mapper一次(version3)。
// 无SPI/I/O，不保留借用JSON；返回AccountBatch的原RAII与整批准入约定保持。
AccountBatch map_shm_account_batch(unsigned stage,const QmtAccountResult&,
 const AccountBinding&,wtp::IBaseDataMgr*);
// STQ-P7：仅接同次Core成功采用的v4/account2.0收据；metadata/金融转换共用旧实现。
AccountBatch map_shm_account_batch_v2(unsigned stage,const QmtAccountResult&,
 const AccountBinding&,wtp::IBaseDataMgr*);
// 仍接完整原v4/account2结果，metadata与全批入口共用；只在最后选原下标。
// 返回local0和完整原index/count；caller另做R5c全扫描，不接筛行后的伪DTO。
AccountSelectedRowBatch map_shm_account_row_v2(unsigned stage,const QmtAccountResult&,
 std::size_t row_index,const AccountBinding&,wtp::IBaseDataMgr*,const AccountCanonicalLimits&);
}}
