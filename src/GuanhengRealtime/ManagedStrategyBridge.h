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
    uint32_t size,abi_version,read_count,execution_count;
    char strategy_id[GH_RT_CODE_BYTES];
    char main_symbol[GH_RT_CODE_BYTES];
    char read_symbols[GH_RT_MAX_READS][GH_RT_CODE_BYTES];
    char execution_symbols[GH_RT_MAX_TARGETS][GH_RT_CODE_BYTES];
} GhMsConfig;
typedef struct GhMsStatus {
    uint32_t size,configured,created,destroyed,active;
    int32_t failure;
    uint64_t callbacks,setters,owner_token;
} GhMsStatus;
#pragma pack(pop)

// 配置线程在原工厂首次create前注册；同策略ID只注册一次，函数/user保持至进程退出。
GH_RT_API uint32_t GH_RT_CALL gh_ms_abi_version(void);
// layout 1=Config/2=Status/3=Event/4=Bar/5=Facts/6=Position/7=Target，未知为0。
GH_RT_API uint64_t GH_RT_CALL gh_ms_layout(uint32_t id);
GH_RT_API int32_t GH_RT_CALL gh_ms_configure(const GhMsConfig*,GhRtCallback,void* user);
GH_RT_API int32_t GH_RT_CALL gh_ms_status(GhMsStatus*);
// 可直接作为STQ-P20 health，只有原子读取；user忽略，0表示所有回调健康。
GH_RT_API int32_t GH_RT_CALL gh_ms_health(void* user);
// 以下操作仅在本次同OS线程epoch借用期，保留原RT值/unknown；BAR阶段只消费event。
GH_RT_API int32_t GH_RT_CALL gh_ms_facts(uint64_t epoch,GhRtFacts*);
GH_RT_API int32_t GH_RT_CALL gh_ms_price(uint64_t epoch,const char*,double*);
GH_RT_API int32_t GH_RT_CALL gh_ms_position(uint64_t epoch,const char*,GhRtPosition*);
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
