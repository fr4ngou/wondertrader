#include "GuanhengExecution/StandardExecutionHost.h"
#include "GuanhengExecution/ExecutionEnvironment.h"
#include <type_traits>

// 本翻译单元仅使用安装后的自有头及原SDK，缺少公共传递头时编译即失败。
static_assert(!std::is_copy_constructible<guanheng::StandardExecutionHost>::value,"host owner is unique");
guanheng::ExecutionHostStatus installed_host_status() { return {}; }

#ifdef GH_INSTALLED_CTA
#include "GuanhengExecution/CtaExecutionSession.h"
static_assert(!std::is_copy_constructible<guanheng::CtaExecutionSession>::value,"CTA session owner is unique");
static_assert(std::is_constructible<guanheng::CtaExecutionSession,wtp::IBaseDataMgr&,wtp::IHotMgr&,
    guanheng::StandardExecutionHost&,std::vector<guanheng::CtaExecutionStrategy>>::value,"installed multi-strategy constructor");
guanheng::CtaExecutionStatus installed_cta_status() { return {}; }
#endif
