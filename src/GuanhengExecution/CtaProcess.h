#pragma once
#include <stdint.h>
#include <wchar.h>

#if defined(GH_CTA_RUNTIME_BUILD)
#define GH_CTA_RUNTIME_API __declspec(dllexport)
#else
#define GH_CTA_RUNTIME_API __declspec(dllimport)
#endif

#ifdef __cplusplus
extern "C" {
#endif

// 同步owner调用；仅返回有限原子健康状态，0健康。调用者保持函数及user至run结束。
typedef int32_t (__cdecl *GhCtaHealth)(void* user);
#pragma pack(push,8)
typedef struct GhCtaBrokerFacts {
    uint32_t size,version,positions_known,account_known;
    uint64_t position_revision,position_received_ms,account_revision,account_received_ms,published_epoch_ms;
    double balance,available;
} GhCtaBrokerFacts;
typedef struct GhCtaBrokerPosition {
    char symbol[64];
    double quantity,sellable;
    uint32_t is_long;
} GhCtaBrokerPosition;
typedef struct GhCtaBrokerTradeFacts {
    uint32_t size,version,known,error;
    uint64_t revision,received_ms,query_revision,query_received_ms,live_revision,published_epoch_ms;
} GhCtaBrokerTradeFacts;
typedef struct GhCtaBrokerTrade {
    char symbol[64],trade_id[64],order_id[64],user_tag[64];
    uint32_t trade_date,is_buy;
    uint64_t trade_time,first_live_revision,received_ms;
    double quantity,price,amount;
} GhCtaBrokerTrade;
// V2在原值后附本实例原提交身份。0序号表示未证明；origins_known=0时全部身份不可用。
typedef struct GhCtaBrokerTradeFactsV2 {
    GhCtaBrokerTradeFacts facts;
    uint64_t submission_revision;
    uint32_t origins_known,reserved;
} GhCtaBrokerTradeFactsV2;
typedef struct GhCtaBrokerTradeV2 {
    GhCtaBrokerTrade trade;
    uint64_t submission_revision;
} GhCtaBrokerTradeV2;
// 原WT订单表的活动委托值副本；原命令及券商ID仍由Adapter/journal维护。
typedef struct GhCtaPendingOrder {
    char symbol[64]; // WT标准证券代码，ASCII终止串；副本归调用者。
    double remaining; // 券商查询/回报的未成交股/份，正有限值。
    uint32_t is_buy; // 原委托方向，1买、0卖；不据此计算持仓。
} GhCtaPendingOrder;
#pragma pack(pop)
GH_CTA_RUNTIME_API uint32_t __cdecl gh_cta_runtime_abi_version(void);
// 每进程只运行一次。argv为原9项宽字符CLI，0=完整成功；失败仍沿原收据/Job核资源。
// 参数及health不抛异常、不跨线程保存原生对象；未确认关闭由本子进程退出保留原责任。
GH_CTA_RUNTIME_API int32_t __cdecl gh_cta_run(uint32_t argc, const wchar_t* const* argv,
    GhCtaHealth health, void* user);
// 可选只读扩展ABI1。owner只在查询表完成后发布值副本；caller可跨线程复制，零交易副作用。
// 接收时间与发布时刻分别给出；重复发布不延长原查询新鲜度。关闭后UNAVAILABLE。
GH_CTA_RUNTIME_API uint32_t __cdecl gh_cta_broker_abi_version(void);
// 1=Facts，2=Position；未知0。
GH_CTA_RUNTIME_API uint64_t __cdecl gh_cta_broker_layout(uint32_t id);
// facts.size/version必须匹配；capacity=1..4096，written实际行数；未知/缺能力不伪作零仓。
// 0成功，-1参数，-2当前无观察，-5容量不足；返回独立值，不借出WT对象或内部指针。
GH_CTA_RUNTIME_API int32_t __cdecl gh_cta_broker_read(GhCtaBrokerFacts*,GhCtaBrokerPosition*,uint32_t capacity,uint32_t* written);
// 可选原成交观察ABI1；1=TradeFacts，2=Trade。与P/A布局独立，返回码及容量规则同上。
// 原成交时间为上海交易日/HHMMSSmmm；received_ms仅为接收时间。未知时不返回可用行。
GH_CTA_RUNTIME_API uint32_t __cdecl gh_cta_broker_trades_abi_version(void);
GH_CTA_RUNTIME_API uint64_t __cdecl gh_cta_broker_trades_layout(uint32_t id);
GH_CTA_RUNTIME_API int32_t __cdecl gh_cta_broker_trades_read(GhCtaBrokerTradeFacts*,GhCtaBrokerTrade*,uint32_t capacity,uint32_t* written);
// 可选V2读入口；layout(3)=FactsV2、layout(4)=TradeV2。内嵌facts.size=sizeof(V2)、version=2。
// 与ABI1同次原子发布、同返回码；原ABI1函数及布局保持。
GH_CTA_RUNTIME_API int32_t __cdecl gh_cta_broker_trades_v2_read(GhCtaBrokerTradeFactsV2*,GhCtaBrokerTradeV2*,uint32_t capacity,uint32_t* written);
// 可选只读活动单扩展：layout=sizeof(GhCtaPendingOrder)，旧P/A/D ABI保持。
GH_CTA_RUNTIME_API uint64_t __cdecl gh_cta_pending_order_layout(void);
// 0成功、-1参数、-2尚无完整订单观察、-5容量不足；空表是已核零活动单。
GH_CTA_RUNTIME_API int32_t __cdecl gh_cta_pending_orders_read(GhCtaPendingOrder*,uint32_t capacity,uint32_t* written);

#ifdef __cplusplus
}
#endif
