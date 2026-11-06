#pragma once
#include "RealtimeBridge.h"

#ifdef __cplusplus
extern "C" {
#endif
#define GH_MS_ABI_VERSION 1u
#define GH_MS_MAX_STRATEGIES 64u
#define GH_MS_STATE_BYTES 32768u
#pragma pack(push,8)
typedef struct GhMsConfig {
    uint32_t size,abi_version,read_count;
    uint32_t execution_count; /* 0为明确的只读绑定，1..8为原目标证券权限；布局不变。 */
    char strategy_id[GH_RT_CODE_BYTES];
    char main_symbol[GH_RT_CODE_BYTES];
    char read_symbols[GH_RT_MAX_READS][GH_RT_CODE_BYTES];
    char execution_symbols[GH_RT_MAX_TARGETS][GH_RT_CODE_BYTES];
} GhMsConfig;
// 可选V2只扩展受管配置；原ABI1和独立Realtime布局保持。
#define GH_MS_CONFIG_V2_VERSION 2u
#define GH_MS_CONFIG_V2_MAX_TARGETS 9u
typedef struct GhMsConfigV2 {
    uint32_t size; /* 调用方结构字节数，严格核sizeof。 */
    uint32_t abi_version; /* 可选配置版本，固定2。 */
    uint32_t read_count; /* 有效读取证券数，1..16。 */
    uint32_t execution_count; /* 目标权限数，0只读，1..9完整向量。 */
    char strategy_id[GH_RT_CODE_BYTES]; /* 固定策略身份，ASCII终止串。 */
    char main_symbol[GH_RT_CODE_BYTES]; /* 主m1证券，必须属于读取集合。 */
    char read_symbols[GH_RT_MAX_READS][GH_RT_CODE_BYTES]; /* 固定读取权限集合。 */
    char execution_symbols[GH_MS_CONFIG_V2_MAX_TARGETS][GH_RT_CODE_BYTES]; /* 固定执行子集。 */
} GhMsConfigV2;
typedef struct GhMsStatus {
    uint32_t size,configured,created,destroyed,active;
    int32_t failure;
    uint64_t callbacks,setters,owner_token;
} GhMsStatus;
typedef struct GhMsCashBasis {
    uint32_t size; /* 调用方结构字节数；严格核sizeof。 */
    uint32_t version; /* 可选现金依据ABI版本，当前1。 */
    double realized_pnl_cny; /* 原WT flag1已实现盈亏，CNY。 */
    double fees_cny; /* 原WT flag3累计费用，CNY。 */
    double average_price_cny; /* 指定证券的原WT持仓平均成本，CNY/份；空仓为0。 */
} GhMsCashBasis;
typedef struct GhMsQuote {
    uint32_t size; /* 调用方结构字节数；严格核sizeof。 */
    uint32_t version; /* 可选当前已应用tick观察ABI，当前1。 */
    uint32_t action_date; /* 原tick事件日期，Asia/Shanghai YYYYMMDD；0表示尚无观察。 */
    uint32_t action_time; /* 原tick事件时刻，Asia/Shanghai HHMMSSmmm，不以读取时间替换。 */
    double price_cny; /* 原WT已应用tick的原价，CNY/份；完整复制值不借用tick指针。 */
} GhMsQuote;
#pragma pack(pop)

// 配置线程在原工厂首次create前注册；同策略ID只注册一次，函数/user保持至进程退出。
GH_RT_API uint32_t GH_RT_CALL gh_ms_abi_version(void);
// 可选只读绑定能力1：execution_count=0仅授读取，任何target setter继续拒绝。
GH_RT_API uint32_t GH_RT_CALL gh_ms_read_only_abi_version(void);
// layout 1=Config/2=Status/3=Event/4=Bar/5=Facts/6=Position/7=Target/8=Quote，未知为0。
GH_RT_API uint64_t GH_RT_CALL gh_ms_layout(uint32_t id);
GH_RT_API int32_t GH_RT_CALL gh_ms_configure(const GhMsConfig*,GhRtCallback,void* user);
// 可选配置能力；不改变原gh_ms_abi_version/layout/目标入口。
GH_RT_API uint32_t GH_RT_CALL gh_ms_config_v2_abi_version(void);
GH_RT_API uint64_t GH_RT_CALL gh_ms_config_v2_layout(void);
GH_RT_API int32_t GH_RT_CALL gh_ms_configure_v2(const GhMsConfigV2*,GhRtCallback,void* user);
GH_RT_API int32_t GH_RT_CALL gh_ms_status(GhMsStatus*);
// 可直接作为STQ-P20 health，只有原子读取；user忽略，0表示所有回调健康。
GH_RT_API int32_t GH_RT_CALL gh_ms_health(void* user);
// 以下操作仅在本次同OS线程epoch借用期，保留原RT值/unknown；BAR阶段只消费event。
GH_RT_API int32_t GH_RT_CALL gh_ms_facts(uint64_t epoch,GhRtFacts*);
GH_RT_API int32_t GH_RT_CALL gh_ms_price(uint64_t epoch,const char*,double*);
GH_RT_API int32_t GH_RT_CALL gh_ms_position(uint64_t epoch,const char*,GhRtPosition*);
// 可选只读扩展；沿相同INIT/SCHEDULE epoch，不提供账户或交易副作用。
GH_RT_API int32_t GH_RT_CALL gh_ms_quote(uint64_t epoch,const char*,GhMsQuote*);
GH_RT_API int32_t GH_RT_CALL gh_ms_cash_basis(uint64_t epoch,const char*,GhMsCashBasis*);
GH_RT_API int32_t GH_RT_CALL gh_ms_bars(uint64_t epoch,const char*,const char*,uint32_t count,
    uint32_t main,GhRtBar*,uint32_t capacity,uint32_t* written);
// 仅SCHEDULE完整执行向量；任何已开始的部分失败锁存并禁止后继setter。
GH_RT_API int32_t GH_RT_CALL gh_ms_set_targets(uint64_t epoch,const GhRtTarget*,uint32_t count,GhRtTarget*,uint32_t capacity);
// 可选扩展ABI1，原MS ABI/结构保持。每ctx固定原用户键guanheng.quantity.state.v1。
GH_RT_API uint32_t GH_RT_CALL gh_ms_state_abi_version(void);
// 仅INIT/SCHEDULE同epoch；复制ASCII及结尾NUL，written不含NUL，缺键为0。
// capacity须容纳结尾NUL；超额返回CAPACITY，不返回原上下文借用指针。
GH_RT_API int32_t GH_RT_CALL gh_ms_state_read(uint64_t epoch,char* out,uint32_t capacity,uint32_t* written);
// 登记1..STATE_BYTES可打印ASCII到原用户变量并回读；原业务事件保存dirty KV。
// 成功只确认内存登记，写盘及完整恢复沿原WT/P21；不增加保存回调。
GH_RT_API int32_t GH_RT_CALL gh_ms_state_write(uint64_t epoch,const char* value,uint32_t length);
#ifdef __cplusplus
}
#endif
