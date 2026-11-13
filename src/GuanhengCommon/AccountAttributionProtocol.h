#pragma once
#include <stdint.h>
#if defined(_WIN32)
#define GH_ATTR_CALL __cdecl
#else
#define GH_ATTR_CALL
#endif

#pragma pack(push,8)
typedef struct GhAttributionEventV1 {
    uint32_t size; /* 本结构字节数，接收方严格核sizeof。 */
    uint32_t version; /* 独立归属事件ABI，固定1。 */
    uint32_t kind; /* GhAttributionKind；各阶段分别确认，非成交总状态。 */
    uint32_t thread_role; /* 1原ctx、2原执行owner、3原I/O worker；worker无ctx权限。 */
    uint64_t epoch; /* 原ctx借用代；非ctx事件为0，不生成新的策略时钟。 */
    uint64_t remaining_ms; /* 本次原截止剩余毫秒；0表示本阶段没有独立原D。 */
    uint32_t json_bytes; /* 完整UTF8正文长度，不含NUL，最多2MiB。 */
    uint32_t reserved; /* 固定0，后继扩展不得重解释原ABI。 */
    const char* json_utf8; /* Native拥有完整复制值，仅本次同步回调有效；接收方须立即复制。 */
} GhAttributionEventV1;
typedef struct GhAttributionReplyV1 {
    uint32_t size; /* 回调前后均严格核本结构大小。 */
    uint32_t version; /* 回复ABI固定1。 */
    int32_t decision; /* 初值-1须明确答复；authorize:0允许、1暂缓，通知仅0。 */
    uint32_t reserved; /* 固定0。 */
    double authorized_quantity; /* authorize实际允许份数，<=原请求；暂缓及通知为0。 */
} GhAttributionReplyV1;
#pragma pack(pop)
typedef int32_t (GH_ATTR_CALL *GhAttributionCallbackV1)(const GhAttributionEventV1*,GhAttributionReplyV1*,void*);
enum GhAttributionKind {
    GH_ATTR_TARGETS=1,GH_ATTR_COMMIT=2,GH_ATTR_DELTA=3,GH_ATTR_AUTHORIZE=4,
    GH_ATTR_GROUP=5,GH_ATTR_WT_CHILD=6,GH_ATTR_PREPARED=7,GH_ATTR_FILL=8,
    GH_ATTR_ORDER=9,GH_ATTR_GROUP_END=10,GH_ATTR_INSERT_RESULT=11,GH_ATTR_QUERY_BATCH=12
};


#ifdef __cplusplus
namespace guanheng {
struct AttributionObserver {
    GhAttributionCallbackV1 callback=nullptr; // 调用方持有至原策略和worker全部关闭，默认关闭。
    void* user=nullptr; // 不透明调用方上下文，Native不解引用或改变所有权。
    explicit operator bool()const noexcept{return callback!=nullptr;}
};
}
#endif
