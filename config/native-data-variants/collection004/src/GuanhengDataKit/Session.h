#pragma once
#include <stdint.h>
#ifdef _WIN32
#define GH_DATAKIT_EXPORT extern "C" __declspec(dllexport)
#else
#define GH_DATAKIT_EXPORT extern "C" __attribute__((visibility("default")))
#endif
// 专用采集进程单实例：创建/关闭由管理线程，push由唯一接收线程；关闭前先停止生产者。
// 配置沿原DataKit basefiles/writer/statemonitor/allday；新增qmt_source只拥有显式单位倍率。
GH_DATAKIT_EXPORT int gh_datakit_create(const char* config_path,const char* module_directory,void** output);
// 同步验证至多200证券并沿原ParserAdapter→DataManager→Writer投递；正数为投递数，负数为固定错误。
GH_DATAKIT_EXPORT int gh_datakit_push_quotes(void* session,const char* ticks_json,uint32_t bytes);
// 原收盘入口；返回只表示任务已受理，完成以原Writer的marker及文件回读核验。
GH_DATAKIT_EXPORT int gh_datakit_archive(void* session,const char* session_id);
GH_DATAKIT_EXPORT int gh_datakit_archive_done(void* session,const char* session_id);
// 0订阅数、1投递数、2原Writer广播数、3显式生命周期Writer标志、4累计Writer LL_ERROR。
// 1/2/4为可并发读取的原子计数；投递/广播和真正文件完整性分别核验。
GH_DATAKIT_EXPORT uint64_t gh_datakit_count(void* session,uint32_t counter);
// 原Writer当前快照的值拷贝；价量额沿实例原profile，不累计分钟、不修改缓存。
// 默认C布局，由调用方持有；三个日期/时间字段后按编译器double对齐。
struct GHCurrentDay {
    uint32_t trading_date; // 原tick交易日，YYYYMMDD；为0表示来源未提供。
    uint32_t action_date; // 原tick自然日，YYYYMMDD，不以查询日期替换。
    uint32_t action_time; // 原tick上海时区HHMMSSmmm，包含毫秒。
    double open; // 原Writer保存的当日开盘价，沿原profile价格单位。
    double high; // 原Writer保存的当日最高价。
    double low; // 原Writer保存的当日最低价。
    double close; // 原Writer保存的最新成交价，盘中可继续变化。
    double volume; // 原tick当日累计成交量，沿原profile单位。
    double amount; // 原tick当日累计成交额，沿原profile单位。
};
// 由管理线程调用；1=已复制、0=原Writer尚无该证券，负数=调用失败。
// 锁住自有Session防止push/close交叉，再复用原getCurTick的复制/引用释放接口。
GH_DATAKIT_EXPORT int gh_datakit_current_day(void* session,const char* code,const char* exchange,GHCurrentDay* output);
// 接收线程已join后调用；沿原stop/release收口，不接管仍在运行的生产者。
// 0=已释放无Writer错误，+1=已释放但Writer曾失败；两者句柄均失效。
// 负数保留原句柄与资源所有权，调用方继续原截止回收，不能按已释放处理。
GH_DATAKIT_EXPORT int gh_datakit_close(void* session);
