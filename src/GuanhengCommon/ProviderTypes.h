#pragma once

#include <cstdint>
#include <string>

namespace guanheng
{
enum class ProviderKind { Qmt, Tdx };
enum class RuntimeMode { Simulation, ReadOnly, Live };
enum class Qualification { Unavailable, DevelopmentVerified, NativeVerified, ProductionQualified };
enum class ErrorCode
{
    Ok, Unavailable, InvalidInput, NotSupported, Pending, Timeout,
    Backpressure, StaleSession, Conflict, SubmissionUnknown, IoError
};

struct Status
{
    ErrorCode code = ErrorCode::Ok;
    std::string reason;
    bool ok() const { return code == ErrorCode::Ok; }
};

// capability 表示该项能力的资格；连接、其他能力和模拟测试不能提高它。
struct Capability
{
    bool supported = false;
    Qualification qualification = Qualification::Unavailable;
    std::string reason;
};

// generation 标识一次源会话；重连后旧会话回调始终携带旧代际。
struct SourceSession
{
    ProviderKind provider = ProviderKind::Qmt;
    std::string instance_id;
    std::string session_id;
    std::uint64_t generation = 0;
};

// 实际账户与路由由上游控制面提供，此对象只承载身份，不赋予执行权限。
struct ExecutionIdentity
{
    SourceSession source;
    std::string account_id;
    std::string environment;
    std::uint64_t route_epoch = 0;
};

inline bool same_session(const SourceSession& lhs, const SourceSession& rhs)
{
    return lhs.provider == rhs.provider && lhs.instance_id == rhs.instance_id
        && lhs.session_id == rhs.session_id && lhs.generation == rhs.generation;
}
}
