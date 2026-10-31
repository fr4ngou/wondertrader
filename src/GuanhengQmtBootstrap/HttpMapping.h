#pragma once
#include "AccountMapping.h"
#include "GuanhengCommon/QmtReadTransport.h"
namespace guanheng { namespace bootstrap {
// 保留旧C++源码接口；新候选需连同AccountMapping重新构建，不与旧静态对象混链。
using HttpBinding=AccountBinding;
using HttpBatch=AccountBatch;
HttpBatch map_http_batch(unsigned stage,const JsonResult&,const SourceSession&,const HttpBinding&,wtp::IBaseDataMgr*);
const char* transport_error_name(ErrorCode) noexcept;
}}
