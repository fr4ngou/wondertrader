#pragma once

#include "History.h"
#include <filesystem>
#include <memory>

namespace guanheng
{
// 启动时固定的原生模块与真实基础资料；路径均为绝对路径，无隐式测试默认值。
// 本适配入口的四类基础资料限定 UTF-8 JSON 对象（.json），预检后才交原生加载器。
struct NativeHistoryReaderConfig
{
    std::filesystem::path library;
    std::filesystem::path sessions;
    std::filesystem::path commodities;
    std::filesystem::path contracts;
    std::filesystem::path holidays;
    std::size_t cache_bytes = 0; // 在用与待释放实例已加载历史的解压字节总上限。
};

// 调用者以 Store mutex/RootLease 串行保护全部调用，并保证 root 为独占历史根。
// 原生切片只在方法内借用；返回数组自有。销毁前须结束全部查询。
class NativeHistoryReader
{
public:
    NativeHistoryReader(std::filesystem::path root, std::size_t max_bars,
        NativeHistoryReaderConfig config);
    ~NativeHistoryReader();
    NativeHistoryReader(const NativeHistoryReader&) = delete;
    NativeHistoryReader& operator=(const NativeHistoryReader&) = delete;

    // content_id/declared_rows 来自持有 RootLease 时完成的摘要与帧预算校验。
    // 返回 m1 闭区间；换代/容量暂不可用返回 Backpressure，失败始终清空 output。
    Status range(const MinuteRequest& request, const std::string& content_id,
        std::size_t declared_rows, std::vector<wtp::WTSBarStruct>& output);
    // 同一来源代际支持 m1/5/15/30/60 闭区间；limit 为最多根数，派生数据不证明分钟覆盖。
    // 周期聚合仅限真实标准沪深日间时段，OHLC/量额由原 WTSDataFactory 产生。
    Status query(const HistoryQuery& request, const std::string& content_id,
        std::size_t declared_rows, std::vector<wtp::WTSBarStruct>& output);
private:
    class Impl;
    std::unique_ptr<Impl> impl_;
};
}
