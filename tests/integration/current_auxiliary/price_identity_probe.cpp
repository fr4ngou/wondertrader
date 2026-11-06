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
    uint32_t get_date() override { return 20261106; }
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
int main(int argc,char** argv){try{
 need(argc==2,"plan"); Config p(WTSCfgLoader::load_from_file(argv[1]));
 Config req(WTSCfgLoader::load_from_file(p->getCString("request")));
 WTSBaseDataMgr base; WTSHotMgr hot;
 need(base.loadSessions(req->getCString("sessions"))&&base.loadCommodities(req->getCString("commodities"))&&base.loadContracts(req->getCString("contracts")),"metadata");
 Sink sink; sink.base=&base;sink.hot=&hot;
 const auto dll=LoadLibraryA(p->getCString("reader"));need(dll,"reader dll");
 auto make=reinterpret_cast<FuncCreateDataReader>(GetProcAddress(dll,"createDataReader"));
 auto destroy=reinterpret_cast<FuncDeleteDataReader>(GetProcAddress(dll,"deleteDataReader"));need(make&&destroy,"exports");
 Config cfg(WTSCfgLoader::load_from_file(p->getCString("config")));
 {std::unique_ptr<IDataReader,FuncDeleteDataReader> reader(make(),destroy);reader->init(cfg.get(),&sink);
 Slice actual(reader->readKlineSlice("SSE.ETF.510300",KP_DAY,1536));
 if(p->getBoolean("expect_success")){need(actual&&actual->size()>0,"published slice missing");auto symbols=req->get("symbols");uint32_t total=0;
 for(uint32_t i=0;i<symbols->size();++i){std::string symbol=symbols->get(i)->asCString();auto code=std::string(symbol.substr(7)=="SH"?"SSE":"SZSE")+".ETF."+symbol.substr(0,6);Slice row(reader->readKlineSlice(code.c_str(),KP_DAY,1536));need(row&&row->size()>0,"role bars missing");need(row->at(row->size()-1)->date==20261105,"role basis");total+=row->size();}
 std::cout<<"PASS symbols="<<symbols->size()<<" total="<<total<<" reader bars="<<actual->size()<<" tail="<<actual->at(actual->size()-1)->date<<"\n";}
 else {need(!actual,"bad original unexpectedly accepted");std::cout<<"PASS original identity rejected\n";}}
 return 0;}catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 2;}}
