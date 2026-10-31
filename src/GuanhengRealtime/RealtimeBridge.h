#pragma once
#include <stdint.h>

#ifdef _WIN32
#define GH_RT_API __declspec(dllexport)
#define GH_RT_CALL __cdecl
#else
#define GH_RT_API __attribute__((visibility("default")))
#define GH_RT_CALL
#endif

#ifdef __cplusplus
extern "C" {
#endif

#define GH_RT_ABI_VERSION 1u
#define GH_RT_MAX_READS 16u
#define GH_RT_MAX_TARGETS 8u
#define GH_RT_MAX_BARS 4096u
#define GH_RT_PATH_BYTES 1024u
#define GH_RT_CODE_BYTES 64u

/* 结果是本次操作结果；最终完成还须核 status、stop 与外部进程 wait。 */
enum GhRtResult { GH_RT_OK=0, GH_RT_PENDING=1, GH_RT_INVALID=-1,
    GH_RT_STATE=-2, GH_RT_THREAD=-3, GH_RT_BORROW=-4, GH_RT_NATIVE=-5,
    GH_RT_CALLBACK=-6, GH_RT_CAPACITY=-7, GH_RT_UNKNOWN=-8 };
enum GhRtEventKind { GH_RT_INIT=1, GH_RT_SESSION_BEGIN=2, GH_RT_BAR=3,
    GH_RT_SCHEDULE=4, GH_RT_SESSION_END=5 };
enum GhRtPhase { GH_RT_NEW=0, GH_RT_CONFIGURING=1, GH_RT_CONFIGURED=2,
    GH_RT_RUNNING=3, GH_RT_STOPPING=4, GH_RT_STOPPED=5, GH_RT_REJECTED=6 };
enum GhRtModuleRole { GH_RT_BRIDGE=1, GH_RT_PARSER=2, GH_RT_READER=3 };
enum GhRtScope { GH_RT_SYNTHETIC=1 };
enum GhRtPositionFlags { GH_RT_RAW_KNOWN=1, GH_RT_ENUM_PRESENT=2,
    GH_RT_ACTUAL_KNOWN=4, GH_RT_PENDING_KNOWN=8 };

#pragma pack(push, 8)
typedef struct GhRtModule {
    uint32_t role;
    uint32_t reserved;
    char path[GH_RT_PATH_BYTES]; /* 绝对ASCII物理路径；SHA由受信安装绑定提供。 */
    char sha256[65];
    char padding[7];
} GhRtModule;

typedef struct GhRtConfig {
    uint32_t size;
    uint32_t abi_version;
    uint32_t scope; /* 首版仅GH_RT_SYNTHETIC，模块名也须匹配合成parser。 */
    uint32_t read_count;
    uint32_t execution_count;
    uint32_t reserved;
    char run_root[GH_RT_PATH_BYTES]; /* cwd必须相同；读取config.json/logcfg.json。 */
    char strategy_id[GH_RT_CODE_BYTES];
    char main_symbol[GH_RT_CODE_BYTES];
    char read_symbols[GH_RT_MAX_READS][GH_RT_CODE_BYTES];
    char execution_symbols[GH_RT_MAX_TARGETS][GH_RT_CODE_BYTES];
    GhRtModule modules[3]; /* bridge/parser/reader各一个，顺序固定。 */
} GhRtConfig;

typedef struct GhRtBar {
    uint32_t date;
    uint32_t reserved;
    uint64_t time;
    double open, high, low, close, volume, money, hold, diff;
} GhRtBar;

typedef struct GhRtEvent {
    uint32_t size;
    uint32_t kind;
    uint64_t epoch;
    uint64_t owner_token;
    uint64_t thread_id; /* 原OS线程ID；不使用Python dummy-thread对象身份。 */
    uint32_t ctx_id;
    uint32_t date;
    uint32_t time;
    uint32_t tdate;
    char symbol[GH_RT_CODE_BYTES];
    char period[8];
    GhRtBar bar; /* 仅BAR事件有效，已复制，不含原生借用地址。 */
} GhRtEvent;

typedef struct GhRtFacts {
    uint32_t size;
    uint32_t date;
    uint32_t time;
    uint32_t tdate;
    double fund_pnl; /* 原stra_get_fund_data(0)，不是现金或账户资产。 */
} GhRtFacts;

typedef struct GhRtPosition {
    uint32_t size;
    uint32_t flags;
    double raw_position; /* 原get_position(false)；新证券可能回显pending。 */
    double raw_valid;
    double enum_target; /* 仅ENUM_PRESENT有效。 */
    uint64_t first_entry;
    uint64_t last_entry;
    uint64_t last_exit;
    double actual_quantity; /* 未获RT事实证明时NaN且对应KNOWN位为0。 */
    double pending_quantity;
} GhRtPosition;

typedef struct GhRtTarget {
    char symbol[GH_RT_CODE_BYTES];
    double quantity; /* CNY现金ETF份数；有限、非负、100整数倍、double精确整数。 */
} GhRtTarget;

typedef struct GhRtStatus {
    uint32_t size;
    uint32_t phase;
    int32_t failure; /* 首个锁存错误；stop完成也不清除。 */
    int32_t native_exit;
    uint32_t stop_requested;
    uint32_t active_callbacks;
    uint64_t callback_count;
    uint64_t setter_count; /* 已进入原void setter次数；不是成交确认。 */
    uint64_t owner_token;
    uint32_t strategy_created;
    uint32_t strategy_destroyed;
} GhRtStatus;
#pragma pack(pop)

/* callback同步执行；event仅本次有效。Python须保留CFUNCTYPE/user至进程退出。
 * 返回非0锁存失败并请求停止。所有业务异常在Python侧捕获，不能穿越C ABI。 */
typedef int32_t (GH_RT_CALL *GhRtCallback)(const GhRtEvent* event, void* user);
/* layout: 1..8分别Config/Event/Bar/Facts/Position/Target/Status/Module大小；
 * 101=Bar.time, 102=Bar.open, 103=Event.bar, 104=Config.modules；未知ID为0。 */
GH_RT_API uint64_t GH_RT_CALL gh_rt_layout(uint32_t id);
GH_RT_API uint32_t GH_RT_CALL gh_rt_abi_version(void);
GH_RT_API uint64_t GH_RT_CALL gh_rt_owner_token(void);
GH_RT_API int32_t GH_RT_CALL gh_rt_configure(const GhRtConfig* config, GhRtCallback callback, void* user);
GH_RT_API int32_t GH_RT_CALL gh_rt_run(void); /* 唯一控制线程，原run(true)。 */
GH_RT_API int32_t GH_RT_CALL gh_rt_request_stop(void); /* 任意线程仅发布请求。 */
GH_RT_API int32_t GH_RT_CALL gh_rt_stop(void); /* 控制线程；可能等待原callback，父Job持原D。 */
GH_RT_API int32_t GH_RT_CALL gh_rt_status(GhRtStatus* out);
GH_RT_API int32_t GH_RT_CALL gh_rt_fail(uint64_t epoch, int32_t code);

/* epoch只在本次callback的原OS线程有效；控制线程/过期epoch均拒绝。
 * facts/price/position/bars仅INIT或SCHEDULE；BAR只允许消费event内复制数据。
 * bars返回值最多capacity，实际数量写written；null历史为UNKNOWN，不填假零。 */
GH_RT_API int32_t GH_RT_CALL gh_rt_facts(uint64_t epoch, GhRtFacts* out);
GH_RT_API int32_t GH_RT_CALL gh_rt_price(uint64_t epoch, const char* symbol, double* out);
GH_RT_API int32_t GH_RT_CALL gh_rt_position(uint64_t epoch, const char* symbol, GhRtPosition* out);
GH_RT_API int32_t GH_RT_CALL gh_rt_bars(uint64_t epoch, const char* symbol,
    const char* period, uint32_t count, uint32_t is_main,
    GhRtBar* out, uint32_t capacity, uint32_t* written);
/* 仅SCHEDULE，完整execution向量；预验全部后逐证券写入并enum回读。
 * 原框架无批事务：任何部分失败锁存NATIVE并请求停止，禁止再次setter。 */
GH_RT_API int32_t GH_RT_CALL gh_rt_set_targets(uint64_t epoch,
    const GhRtTarget* targets, uint32_t count, GhRtTarget* readback, uint32_t capacity);

#ifdef __cplusplus
}
#endif
