// 用真实基础资料沿 WT 两个公开 Reader 读取 DataKit 文件；本程序仅创建读取者。
#include <windows.h>
#include "Includes/IDataReader.h"
#include "Includes/IRdmDtReader.h"
#include "Includes/WTSDataDef.hpp"
#include "Includes/WTSVariant.hpp"
#include "WTSTools/WTSBaseDataMgr.h"
#include <cmath>
#include <chrono>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <memory>
#include <map>
#include <stdexcept>
#include <string>
#include <vector>

using namespace wtp;
namespace {
struct Sink final : IDataReaderSink, IRdmDtReaderSink {
    WTSBaseDataMgr base;
    uint32_t date = 0;
    uint32_t minute = 1130; // 原策略读取时钟，闭市复现可显式设置。
    unsigned closed = 0;
    unsigned updates = 0;
    std::map<std::string, std::vector<WTSBarStruct>> events;
    bool fail_minute_callback = false; // 故障回放时让真实逐证券回调抛出已知异常。
    std::string callback_failure; // 保留 Reader 经原 sink 上报的证券级诊断。
    IBaseDataMgr* get_basedata_mgr() override { return &base; }
    IHotMgr* get_hot_mgr() override { return nullptr; }
    uint32_t get_date() override { return date; }
    uint32_t get_min_time() override { return minute; }
    uint32_t get_secs() override { return 0; }
    void reader_log(WTSLogLevel, const char* text) override {
        std::cerr << text << '\n';
        if (std::string(text).find("minute callback failed code=") != std::string::npos)
            callback_failure = text;
    }
    void on_bar(const char* code, WTSKlinePeriod, WTSBarStruct* bar) override {
        if (fail_minute_callback)
            throw std::runtime_error("probe minute sink failure");
        ++closed;
        events[code].push_back(*bar);
    }
    void on_all_bar_updated(uint32_t) override { ++updates; }
};
template<class T> struct Release { void operator()(T* x) const { if (x) x->release(); } };
std::vector<WTSBarStruct> copy_slice(WTSKlineSlice* raw) {
    std::unique_ptr<WTSKlineSlice, Release<WTSKlineSlice>> slice(raw);
    if (!slice || slice->size() > 240) throw std::runtime_error("missing or oversized slice");
    std::vector<WTSBarStruct> result;
    // 切片借用原 Reader 缓存；逐块复制且先校验数量，再释放切片与 Reader。
    for (uint32_t i = 0; i < slice->get_block_counts(); ++i) {
        const auto n = slice->get_block_size(i);
        auto* begin = slice->get_block_addr(i);
        if (n > 240 - result.size() || (n && !begin)) throw std::runtime_error("slice block capacity");
        if (n) result.insert(result.end(), begin, begin + n);
    }
    if (result.size() != slice->size()) throw std::runtime_error("slice count mismatch");
    return result;
}
void rows(std::ostream& out, const std::vector<WTSBarStruct>& bars) {
    out << '[';
    uint64_t previous = 0;
    for (size_t i = 0; i < bars.size(); ++i) {
        const auto& b = bars[i];
        const uint64_t label = 199000000000ULL + b.time;
        if (label <= previous || !std::isfinite(b.open) || !std::isfinite(b.high)
            || !std::isfinite(b.low) || !std::isfinite(b.close)
            || !std::isfinite(b.vol) || !std::isfinite(b.money)) throw std::runtime_error("invalid row");
        previous = label;
        if (i) out << ',';
        out << '[' << label << ',' << b.open << ',' << b.high << ',' << b.low << ','
            << b.close << ',' << b.vol << ',' << b.money << ']';
    }
    out << ']';
}
}
int main(int argc, char** argv) {
    try {
        if (argc != 8 && argc != 10) throw std::runtime_error("expected dll/storage/sessions/commodities/contracts/day/output [minute timeout_ms]");
        HMODULE module = LoadLibraryA(argv[1]);
        if (!module) throw std::runtime_error("reader module unavailable");
        auto make = reinterpret_cast<FuncCreateDataReader>(GetProcAddress(module, "createDataReader"));
        auto destroy = reinterpret_cast<FuncDeleteDataReader>(GetProcAddress(module, "deleteDataReader"));
        auto stop = reinterpret_cast<bool(*)(IDataReader*, uint32_t)>(GetProcAddress(module, "stopDataReader"));
        if (!make || !destroy || !stop) throw std::runtime_error("reader exports missing");
        Sink sink;
        sink.date = static_cast<uint32_t>(std::stoul(argv[6]));
        if (argc == 10) sink.minute = static_cast<uint32_t>(std::stoul(argv[8]));
        if (!sink.base.loadSessions(argv[3]) || !sink.base.loadCommodities(argv[4])
            || !sink.base.loadContracts(argv[5])) throw std::runtime_error("actual base data failed");
        std::unique_ptr<WTSVariant, Release<WTSVariant>> config(WTSVariant::createObject());
        auto daily = WTSVariant::createObject(); daily->append("path", argv[2]);
        config->append("daily", daily); daily->release();
        auto native = WTSVariant::createObject(); native->append("path", argv[2]);
        config->append("minute_native", native); native->release();
        config->append("max_bars", uint32_t(120)); config->append("max_live_bars", uint32_t(480)); config->append("max_slices", uint32_t(8));
        if (argc == 10) config->append("timeout_ms", static_cast<uint32_t>(std::stoul(argv[9])));
        auto mappings = WTSVariant::createArray();
        for (const auto& item : std::vector<std::pair<std::string,std::string>>{{"SSE.ETF.510300","510300.SH"},{"SSE.STK.600000","600000.SH"},{"SZSE.STK.000001","000001.SZ"}}) {
            if (argc == 10 && item.first != "SSE.ETF.510300") continue;
            auto value = WTSVariant::createObject(); value->append("std_code", item.first.c_str()); value->append("symbol", item.second.c_str()); mappings->append(value); value->release();
        }
        config->append("symbols", mappings); mappings->release();
        // 两个 Reader 均在 sink/config 之前销毁，模块保持加载直到进程结束。
        std::unique_ptr<IDataReader, FuncDeleteDataReader> strategy(make(), destroy);
        std::vector<WTSKlineSlice*> retained;
        if (!strategy) throw std::runtime_error("reader creation failed");
        strategy->init(config.get(), &sink);
        std::ofstream out(argv[7], std::ios::binary);
        if (!out) throw std::runtime_error("result file unavailable");
        if (argc == 10) {
            out << "[";
            for (int attempt = 0; attempt < 2; ++attempt) {
                const auto start = std::chrono::steady_clock::now();
                std::unique_ptr<WTSKlineSlice, Release<WTSKlineSlice>> result(strategy->readKlineSlice("SSE.ETF.510300", KP_Minute1, 1));
                const auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-start).count();
                out << (attempt ? "," : "") << "{\"elapsed_ms\":" << elapsed << ",\"bars\":" << (result ? result->size() : 0)
                    << ",\"date\":" << (result && result->size() ? result->at(0)->date : 0)
                    << ",\"minute\":" << (result && result->size() ? result->at(0)->time % 10000 : 0) << "}";
            }
            out << "]";
            if (!stop(strategy.get(), 3000)) throw std::runtime_error("reader stop failed");
            return 0;
        }
        out << std::setprecision(17) << "{\"schema\":\"guanheng.native-live-read.v1\",\"samples\":[";
        unsigned sample = 0;
        for (const char* code : {"SSE.ETF.510300", "SSE.STK.600000", "SZSE.STK.000001"}) {
            if (sample++) out << ',';
            const uint64_t end = static_cast<uint64_t>(sink.date) * 10000 + 1130;
            const uint64_t start = static_cast<uint64_t>(sink.date) * 10000 + 931;
            auto a = copy_slice(strategy->readKlineSlice(code, KP_Minute1, 120, end));
            auto held = strategy->readKlineSlice(code, KP_Minute1, 120, end);
            if (!held) throw std::runtime_error("held copy unavailable"); retained.push_back(held);
            out << "{\"symbol\":\"" << code << "\",\"strategy\":"; rows(out, a);

            out << '}';
        }
        if (!stop(strategy.get(), 3000) || strategy->readKlineSlice("SSE.ETF.510300", KP_Minute1, 1)) throw std::runtime_error("managed stop failed");
        strategy->onMinuteEnd(sink.date, 1130);
        if (sink.closed) throw std::runtime_error("stopped reader delivered callback");
        strategy.reset();
        out << "],\"retained_after_delete\":[";
        for (size_t i=0;i<retained.size();++i) { if(i) out << ','; auto values=copy_slice(retained[i]); rows(out,values); }
        retained.clear();
        strategy.reset(make());
        out << "],\"subscriptions\":[";
        if (!strategy) throw std::runtime_error("subscription reader creation failed");
        strategy->init(config.get(), &sink);
        // 用真实已闭合文件回放原分钟结束入口：09:31预热后，只转发后续分钟。
        for (const char* code : {"SSE.ETF.510300", "SSE.STK.600000", "SZSE.STK.000001"}) {
            auto initial = copy_slice(strategy->readKlineSlice(code, KP_Minute1, 1,
                static_cast<uint64_t>(sink.date) * 10000 + 931));
            if (initial.size() != 1 || initial.front().time % 10000 != 931)
                throw std::runtime_error("subscription warmup mismatch");
        }
        strategy->onMinuteEnd(sink.date, 1130);
        const unsigned first_closed = sink.closed;
        strategy->onMinuteEnd(sink.date, 1130);
        if (sink.closed != first_closed || first_closed != 3 * 119)
            throw std::runtime_error("subscription cursor mismatch");
        sample = 0;
        for (const char* code : {"SSE.ETF.510300", "SSE.STK.600000", "SZSE.STK.000001"}) {
            if (sample++) out << ',';
            out << "{\"symbol\":\"" << code << "\",\"events\":";
            rows(out, sink.events[code]);
            out << '}';
        }
        out << "],\"repeated_minute_added_events\":0,\"all_bar_updates\":" << sink.updates
            << ",\"real_orders\":0,\"real_cancels\":0}";
        out.close();
        if (!out) throw std::runtime_error("result write failed");
        if (!stop(strategy.get(), 3000)) throw std::runtime_error("subscription stop failed");
        strategy.reset();
        strategy.reset(make());
        if (!strategy) throw std::runtime_error("failure replay reader creation failed");
        strategy->init(config.get(), &sink);
        auto warmup = copy_slice(strategy->readKlineSlice("SSE.ETF.510300", KP_Minute1, 1,
            static_cast<uint64_t>(sink.date) * 10000 + 931));
        if (warmup.size() != 1) throw std::runtime_error("failure replay warmup missing");
        sink.fail_minute_callback = true;
        strategy->onMinuteEnd(sink.date, 932);
        if (sink.callback_failure.find("code=SSE.ETF.510300") == std::string::npos ||
            sink.callback_failure.find("bar_minute=" + std::to_string(sink.date) + "0932") == std::string::npos ||
            sink.callback_failure.find("probe minute sink failure") == std::string::npos)
            throw std::runtime_error("missing per-security minute failure diagnostic");
        if (!stop(strategy.get(), 3000)) throw std::runtime_error("failure replay stop failed");
        strategy.reset();
        std::cout << "native live readers completed\n";
        return 0;
    } catch (const std::exception& e) {
        std::cerr << e.what() << '\n';
        return 2;
    }
}
