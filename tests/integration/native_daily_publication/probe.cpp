// 同一原 WtCtaEngine/WtDtMgr 读取三份已发布原件；Oracle 直接调用原 WtDataReader。
#include "WtCore/WtCtaEngine.h"
#include "WtCore/WtDtMgr.h"
#include "WtCore/WtHelper.h"
#include "WTSTools/WTSBaseDataMgr.h"
#include "WTSTools/WTSHotMgr.h"
#include "WTSUtils/WTSCfgLoader.h"
#include "Includes/WTSVariant.hpp"
#include "Includes/WTSDataDef.hpp"
#include <windows.h>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <memory>
#include <vector>
#include <cstring>
#include <cmath>

using namespace wtp;
namespace fs = std::filesystem;
namespace {
void need(bool ok, const char* reason) { if (!ok) throw std::runtime_error(reason); }
template<class T> struct Release { void operator()(T* value) const { if (value) value->release(); } };
using Config = std::unique_ptr<WTSVariant, Release<WTSVariant>>;
using Slice = std::unique_ptr<WTSKlineSlice, Release<WTSKlineSlice>>;
struct Sink final : IDataReaderSink {
    WTSBaseDataMgr* base;
    WTSHotMgr* hot;
    IBaseDataMgr* get_basedata_mgr() override { return base; }
    IHotMgr* get_hot_mgr() override { return hot; }
    uint32_t get_date() override { return 20261030; }
    uint32_t get_min_time() override { return 1130; }
    uint32_t get_secs() override { return 0; }
    void reader_log(WTSLogLevel, const char* message) override { std::cerr << message << '\n'; }
    void on_bar(const char*, WTSKlinePeriod, WTSBarStruct*) override {}
    void on_all_bar_updated(uint32_t) override {}
};
bool equal(const WTSBarStruct& a, const WTSBarStruct& b) {
    return a.date == b.date && a.time == b.time && a.open == b.open && a.high == b.high &&
        a.low == b.low && a.close == b.close && a.vol == b.vol && a.money == b.money &&
        a.settle == b.settle && a.hold == b.hold && a.add == b.add;
}
std::vector<WTSBarStruct> values(WTSKlineSlice* raw) {
    need(raw && raw->size() > 0 && raw->size() <= 4096, "original daily slice missing");
    std::vector<WTSBarStruct> result;
    for (int i = 0; i < raw->size(); ++i) result.push_back(*raw->at(i));
    return result;
}
void same(WTSKlineSlice* slice, const std::vector<WTSBarStruct>& expected) {
    auto actual = values(slice);
    need(actual.size() == expected.size(), "daily count differs");
    for (size_t i = 0; i < actual.size(); ++i) need(equal(actual[i], expected[i]), "daily original value differs");
}
HANDLE hold_projection(const fs::path& root) {
    for (const auto& item : fs::recursive_directory_iterator(root))
        if (item.is_regular_file() && item.path().extension() == ".dsb") {
            const auto handle = CreateFileW(item.path().c_str(), GENERIC_READ, FILE_SHARE_READ,
                nullptr, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
            need(handle != INVALID_HANDLE_VALUE, "projection hold failed");
            return handle;
        }
    throw std::runtime_error("projection hold input missing");
}
}
int main(int argc, char** argv) { try {
    need(argc == 2, "expected fixture plan");
    Config plan(WTSCfgLoader::load_from_file(argv[1])); need(bool(plan), "plan unavailable");
    fs::current_path(plan->getCString("work"));
    const auto plugin = fs::path(plan->getCString("plugin"));
    const auto inst = plugin.generic_string() + "/"; WtHelper::setInstDir(inst.c_str());
    const auto generated = fs::absolute("generated").string(); WtHelper::setGenerateDir(generated.c_str());
    const auto original = LoadLibraryA(plan->getCString("original_reader")); need(original, "original reader module missing");
    auto make = reinterpret_cast<FuncCreateDataReader>(GetProcAddress(original, "createDataReader"));
    auto destroy = reinterpret_cast<FuncDeleteDataReader>(GetProcAddress(original, "deleteDataReader"));
    need(make && destroy, "original reader exports missing");
    WTSBaseDataMgr base; WTSHotMgr hot;
    auto rounds = plan->get("rounds"); need(rounds && (rounds->size() == 3 || rounds->size() == 4), "three original rounds and optional factor model required");
    Config first(WTSCfgLoader::load_from_file(rounds->get(uint32_t(0))->getCString("request")));
    need(base.loadSessions(first->getCString("sessions")) && base.loadCommodities(first->getCString("commodities")) &&
        base.loadContracts(first->getCString("contracts")), "original metadata failed");
    Sink sink; sink.base = &base; sink.hot = &hot;
    Config engine_cfg(WTSVariant::createObject()), data_cfg(WTSVariant::createObject());
    engine_cfg->append("poolsize", uint32_t(0));
    auto store = WTSVariant::createObject(); store->append("module", "GuanhengRealtimeReader");
    auto minute = WTSVariant::createObject(); minute->append("path", first->getCString("path"));
    store->append("minute_native", minute); minute->release();
    auto daily = WTSVariant::createObject(); daily->append("path", first->getCString("path"));
    daily->append("max_live_bars", uint32_t(65536)); daily->append("publication", plan->get("publication"));
    store->append("daily", daily); daily->release();
    auto mappings = WTSVariant::createArray();
    std::vector<std::string> codes;
    auto symbols = first->get("symbols");
    for (uint32_t i = 0; i < symbols->size(); ++i) {
        const std::string symbol = symbols->get(i)->asCString();
        const auto code = std::string(symbol.substr(7) == "SH" ? "SSE" : "SZSE") + ".ETF." + symbol.substr(0, 6);
        codes.push_back(code);
        auto item = WTSVariant::createObject(); item->append("std_code", code.c_str()); item->append("symbol", symbol.c_str());
        mappings->append(item); item->release();
    }
    // 行情映射可覆盖日线发布以外的证券，其缺项只影响该证券的请求。
    const auto missing_code = std::string("SZSE.ETF.159352");
    const auto extra_contracts = fs::path("extra-contracts.json");
    {
        std::ofstream output(extra_contracts);
        output << R"({"SZSE":{"159352":{"exchg":"SZSE","name":"A500 ETF","product":"ETF","opendate":20240924,"expiredate":20991231}}})";
    }
    need(base.loadContracts(extra_contracts.string().c_str()) && base.getContract("159352", "SZSE"),
        "additional mapped contract");
    auto extra = WTSVariant::createObject();
    extra->append("std_code", missing_code.c_str()); extra->append("symbol", "159352.SZ");
    mappings->append(extra); extra->release();
    store->append("symbols", mappings); mappings->release(); data_cfg->append("store", store); store->release();
    WtDtMgr data; WtCtaEngine engine;
    engine.init(engine_cfg.get(), &base, &data, &hot, nullptr);
    engine.set_date_time(20261030, 1130); engine.set_trading_date(20261030);
    need(data.init(data_cfg.get(), &engine, false, true) && data.supports_stop(), "original CTA reader initialization");
    std::vector<Slice> retained;
    std::vector<std::vector<WTSBarStruct>> old;
    std::vector<WTSBarStruct> tails;
    std::vector<double> factors, front_first;
    for (uint32_t round = 0; round < rounds->size(); ++round) {
        auto item = rounds->get(round);
        const auto held = round == 1 ? hold_projection(plan->get("publication")->getCString("cache_root")) : INVALID_HANDLE_VALUE;
        fs::copy_file(item->getCString("window"), plan->get("publication")->getCString("publication_file"), fs::copy_options::overwrite_existing);
        fs::copy_file(item->getCString("status"), plan->get("publication")->getCString("status_file"), fs::copy_options::overwrite_existing);
        if (held != INVALID_HANDLE_VALUE) {
            auto* premature = data.get_kline_slice(codes[0].c_str(), KP_DAY, 1, 1);
            CloseHandle(held);
            need(premature == nullptr, "generation switch lost pending projection cleanup");
        }
        Config request(WTSCfgLoader::load_from_file(item->getCString("request")));
        need(data.get_kline_slice(missing_code.c_str(), KP_DAY, 1, 1) == nullptr,
            "unpublished daily symbol returned bars");
        need(std::isnan(data.reader()->getAdjFactorByDate(missing_code.c_str(), 20261030)),
            "unpublished daily symbol returned factor");
        std::unique_ptr<IDataReader, FuncDeleteDataReader> oracle(make(), destroy); oracle->init(request.get(), &sink);
        // 持有同批另一证券原件的独占句柄。请求本证券无需读它；解除后原证券可正常复用同一代。
        const auto blocked_code = codes.back();
        const auto dot = blocked_code.rfind('.');
        const auto blocked = fs::path(request->getCString("path")) / "his/day" /
            blocked_code.substr(0, blocked_code.find('.')) / (blocked_code.substr(dot + 1) + ".dsb");
        const auto unavailable = CreateFileW(blocked.c_str(), GENERIC_READ, 0, nullptr,
            OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
        need(unavailable != INVALID_HANDLE_VALUE, "lock other published symbol");
        Slice available(data.get_kline_slice(codes.front().c_str(), KP_DAY, 1, 1));
        auto* denied = data.get_kline_slice(blocked_code.c_str(), KP_DAY, 1, 1);
        CloseHandle(unavailable);
        need(available && !denied, "unrelated published symbol blocked independent read");
        available.reset();
        for (const auto& code : codes) {
            Slice expected(oracle->readKlineSlice(code.c_str(), KP_DAY, 1536));
            Slice actual(data.get_kline_slice(code.c_str(), KP_DAY, 1, 1536));
            auto original_values = values(expected.get()); same(actual.get(), original_values);
            if (code == "SSE.ETF.510300") tails.push_back(original_values.back());
            old.push_back(original_values); retained.push_back(std::move(actual));
            const auto adjusted = code + "-";
            Slice adjusted_expected(oracle->readKlineSlice(adjusted.c_str(), KP_DAY, 1536));
            Slice adjusted_actual(data.get_kline_slice(adjusted.c_str(), KP_DAY, 1, 1536));
            same(adjusted_actual.get(), values(adjusted_expected.get()));
            need(data.reader()->getAdjFactorByDate(code.c_str(), 20261030) == oracle->getAdjFactorByDate(code.c_str(), 20261030),
                "original factor differs");
            if (code == "SSE.ETF.510300") {
                factors.push_back(data.reader()->getAdjFactorByDate(code.c_str(), 20261030));
                front_first.push_back(adjusted_actual->at(0)->close);
            }
        }
        for (size_t i = 0; i < retained.size(); ++i) same(retained[i].get(), old[i]);
    }
    need(tails[0].date < tails[1].date && tails[1].date == tails[2].date && !equal(tails[1], tails[2]),
        "first/new day/same day revision not exercised");
    if (rounds->size() == 4)
        need(equal(tails[2], tails[3]) && factors[2] != factors[3] && front_first[2] != front_first[3],
            "actual factor bytes and native adjusted output did not change");
    const fs::path window_path = plan->get("publication")->getCString("publication_file");
    const fs::path status_path = plan->get("publication")->getCString("status_file");
    const auto missing = fs::path(window_path.string() + ".missing");
    fs::rename(window_path, missing);
    need(data.get_kline_slice(codes[0].c_str(), KP_DAY, 1, 1) == nullptr, "cached reader accepted missing current window");
    fs::rename(missing, window_path);
    fs::copy_file(plan->getCString("bad_status"), status_path, fs::copy_options::overwrite_existing);
    need(data.get_kline_slice(codes[0].c_str(), KP_DAY, 1, 1) == nullptr, "cached reader accepted mismatched status revision");
    fs::copy_file(rounds->get(uint32_t(rounds->size() - 1))->getCString("status"), status_path, fs::copy_options::overwrite_existing);
    engine.set_date_time(20261029, 1130);
    need(data.get_kline_slice(codes[0].c_str(), KP_DAY, 1, 1) == nullptr, "cached reader accepted unclosed basis");
    engine.set_date_time(20261030, 1130);
    Slice restored(data.get_kline_slice(codes[0].c_str(), KP_DAY, 1, 1));
    need(restored && equal(*restored->at(0), old[(rounds->size() - 1) * codes.size()].back()), "current publication did not recover");
    restored.reset();
    need(engine.stop(), "original CTA engine close failed");
    const auto stop_hold = hold_projection(plan->get("publication")->getCString("cache_root"));
    const auto premature_stop = data.stop(20);
    CloseHandle(stop_hold);
    need(!premature_stop, "reader stop lost pending projection cleanup");
    need(data.stop(5000), "original CTA reader cleanup retry failed");
    data.release(); need(data.reader() == nullptr, "reader not released");
    for (size_t i = 0; i < retained.size(); ++i) same(retained[i].get(), old[i]);
    retained.clear(); engine.release_contexts();
    std::ofstream result(plan->getCString("result"));
    result << "{\"passed\":true,\"same_cta\":true,\"rounds\":" << rounds->size() << ",\"factor_changed\":" << (rounds->size() == 4 ? "true" : "false")
        << ",\"symbols\":8,\"raw_and_adjusted_original_equal\":true,"
        "\"new_day\":true,\"same_day_revision\":true,\"retained_slices\":" << old.size() << ",\"retained_after_stop\":true,"
        "\"unpublished_symbol_refused\":true,\"cached_missing_refused\":true,\"cached_revision_refused\":true,\"cached_unclosed_refused\":true,"
        "\"generation_cleanup_retried\":true,\"stop_cleanup_retried\":true,\"orders\":0}";
    std::cout << "original CTA daily publication passed\n"; return 0;
} catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 2; } }
