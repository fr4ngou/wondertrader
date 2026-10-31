#pragma once
#include "BoundedSignedHttp.h"
#include "QmtReadTransport.h"

namespace guanheng
{
// 原请求及原完整运输绑定。公开值重新准入后方可resume；修改它不能授新身份。
// 保留原字节用于原ID核查，含私有行情，调用者负责受控保存。
enum class QmtReadProfileVersion { Legacy, AccountV3, FullTickV6 };

struct QmtBoundReceipt
{
    std::string binding_json, request_body;
    // AccountV4 保存已验原 profile/容量，恢复版本由其确定；旧门面保持空值。
    std::string read_profile_body;
    std::size_t read_result_capacity = 0;
    // 显式账户回收的原票据仅驻本进程；原ID恢复时沿用，不能重新授期。
    std::string retention_ticket_json;
};
struct QmtBoundResult
{
    JsonResult result;
    QmtBoundReceipt receipt;
    std::string native_result_json;
};

// 创建线程独占；显式版本消费独立Host full_tick，不回退旧终端HTTP。
// FullTickV6核验完整v6能力，权限固定为full_tick；其它能力仅作组合准入。
// prepare固定完整运输绑定。read/resume各使用调用起一个总截止；resume只GET原ID。
// 终态原字节与receipt保留在失败返回中；仅同binding合格结果发布data_json。
class QmtHostReadClient
{
public:
    explicit QmtHostReadClient(QmtHttpConfig config, QmtReadProfileVersion = QmtReadProfileVersion::Legacy);
    ~QmtHostReadClient();
    QmtHostReadClient(const QmtHostReadClient&) = delete;
    QmtHostReadClient& operator=(const QmtHostReadClient&) = delete;
    Status prepare(std::uint32_t milliseconds);
    SourceSession session() const;
    Capability capability() const;
    QmtBoundResult read_full_tick(const std::string& arguments_json,std::uint32_t milliseconds);
    QmtBoundResult resume(const QmtBoundReceipt& receipt,std::uint32_t milliseconds);
    Status drain_callbacks(std::uint32_t milliseconds) noexcept;
private:
    class Impl;
    std::unique_ptr<Impl> impl_;
};
}
