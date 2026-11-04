// 采集管理线程沿既有NMR/WT标准Reader读取；不解析活动DMB，不创建Writer。
#include <windows.h>
#include "Includes/IDataReader.h"
#include "Includes/WTSDataDef.hpp"
#include "Includes/WTSVariant.hpp"
#include "Includes/WTSContractInfo.hpp"
#include "Includes/WTSSessionInfo.hpp"
#include "WTSTools/WTSBaseDataMgr.h"
#include <algorithm>
#include <cstring>
#include <memory>
#include <mutex>
#include <set>
#include <stdexcept>
#include <string>

using namespace wtp;
namespace {
template<class T> struct Release { void operator()(T* value) const { if(value) value->release(); } };
struct Sink final : IDataReaderSink {
    WTSBaseDataMgr base; // 本读取批次独占的原基础资料，寿命覆盖Reader及全部借用切片。
    uint32_t date = 0; // 本次查询的原交易日期YYYYMMDD，历史查询显式指定。
    uint32_t minute = 0; // 本次查询的右端截止HHMM，分钟完整性仍按实际结果核对。
    IBaseDataMgr* get_basedata_mgr() override { return &base; }
    IHotMgr* get_hot_mgr() override { return nullptr; }
    uint32_t get_date() override { return date; }
    uint32_t get_min_time() override { return minute; }
    uint32_t get_secs() override { return 0; }
    void on_bar(const char*,WTSKlinePeriod,WTSBarStruct*) override {} // 只读覆盖查询不注册或投递策略事件。
    void on_all_bar_updated(uint32_t) override {}
    void reader_log(WTSLogLevel,const char*) override {} // 热读取不向状态输出路径、价格或来源正文。
};
struct Context {
    DWORD owner = GetCurrentThreadId(); // 唯一创建线程；跨线程查询及关闭拒绝。
    Sink sink; // 创建/读取/关闭均由一个管理线程拥有。
    IDataReader* reader = nullptr; // 既有NMR工厂对象；成功stop后才调用原delete。
    FuncDeleteDataReader destroy = nullptr; // 与固定原模块配对的销毁函数。
    bool(*stop)(IDataReader*,uint32_t) = nullptr; // 原有有限停止接口，false时保留对象。
    uint32_t limit = 0; // 本批复制行数上限，原Reader冷加载仍受外层进程预算管理。
    std::set<std::string> codes; // 本批已固定标准代码，查询保持相同准入集合。
};
std::mutex factory_guard;
Context* failed_context = nullptr; // 初始化失败且stop未确认时保留原对象；本进程禁止继续创建，交外层Job收束。
HMODULE reader_module(const char* path) {
    // NMR合同要求模块保留至进程退出；同进程固定一个绝对模块身份，不按批次累加加载引用。
    static std::mutex guard;
    static HMODULE module = nullptr;
    static std::string identity;
    std::lock_guard<std::mutex> lock(guard);
    if(module) return identity == path ? module : nullptr;
    module = LoadLibraryA(path);
    if(module) identity = path;
    return module;
}
bool bounded(const char* value,size_t maximum) {
    return value && *value && strnlen(value,maximum+1)<=maximum;
}
}

extern "C" __declspec(dllexport) uint32_t gh_collection_reader_version() { return 1; }
extern "C" __declspec(dllexport) uint32_t gh_collection_reader_bar_size() { return sizeof(WTSBarStruct); }

extern "C" __declspec(dllexport) void* gh_collection_reader_create(
    const char* library,const char* storage,const char* sessions,const char* commodities,const char* contracts,
    const char* const* codes,uint32_t count,uint32_t maximum) {
    // 输入为调用方固定的ASCII部署路径及标准代码；输出对象沿close成功后释放。
    if(!bounded(library,1023)||!bounded(storage,1023)||!bounded(sessions,1023)
       ||!bounded(commodities,1023)||!bounded(contracts,1023)||!codes||!count||count>64||!maximum||maximum>2000)
        return nullptr;
    std::unique_ptr<Context> context;
    std::lock_guard<std::mutex> guard(factory_guard);
    if(failed_context)return nullptr;
    try {
        context.reset(new Context());
        auto module=reader_module(library);if(!module)return nullptr;
        auto make=reinterpret_cast<FuncCreateDataReader>(GetProcAddress(module,"createDataReader"));
        context->destroy=reinterpret_cast<FuncDeleteDataReader>(GetProcAddress(module,"deleteDataReader"));
        context->stop=reinterpret_cast<bool(*)(IDataReader*,uint32_t)>(GetProcAddress(module,"stopDataReader"));
        if(!make||!context->destroy||!context->stop)return nullptr;
        if(!context->sink.base.loadSessions(sessions)||!context->sink.base.loadCommodities(commodities)
           ||!context->sink.base.loadContracts(contracts))return nullptr;
        std::unique_ptr<WTSVariant,Release<WTSVariant>> config(WTSVariant::createObject());
        for(const char* name:{"daily","minute_native"}) {
            auto native=WTSVariant::createObject();native->append("path",storage);config->append(name,native);native->release();
        }
        config->append("max_bars",maximum);config->append("max_live_bars",maximum*count);config->append("max_slices",count);
        std::unique_ptr<WTSVariant,Release<WTSVariant>> mappings(WTSVariant::createArray());
        for(uint32_t i=0;i<count;++i) {
            if(!bounded(codes[i],63))throw std::runtime_error("code capacity");
            std::string code(codes[i]);auto dot=code.rfind('.');
            if(dot==std::string::npos||code.size()-dot-1!=6)throw std::runtime_error("code identity");
            std::string suffix=code.rfind("SSE.",0)==0?".SH":code.rfind("SZSE.",0)==0?".SZ":"";
            if(suffix.empty())throw std::runtime_error("market mapping unavailable");
            if(!context->codes.insert(code).second)throw std::runtime_error("duplicate code");
            auto value=WTSVariant::createObject();value->append("std_code",code.c_str());
            value->append("symbol",(code.substr(dot+1)+suffix).c_str());mappings->append(value);value->release();
        }
        config->append("symbols",mappings.get());
        context->reader=make();if(!context->reader)return nullptr;
        context->reader->init(config.get(),&context->sink);context->limit=maximum;
        return context.release();
    } catch(...) {
        if(context&&context->reader) {
            try {
                if(context->stop(context->reader,3000)) {
                    context->destroy(context->reader);context->reader=nullptr;
                }
            } catch(...) {} // 初始化失败保留原错误，停止/销毁未确认继续由同一进程持有。
            if(context->reader)failed_context=context.release();
        }
        return nullptr;
    }
}

extern "C" __declspec(dllexport) int32_t gh_collection_reader_read(void* handle,const char* code,
    uint32_t date,uint32_t minute,WTSBarStruct* output,uint32_t capacity,uint32_t* written,
    uint32_t* expected,uint32_t expected_capacity,uint32_t* expected_count) {
    auto* context=static_cast<Context*>(handle);
    if(!context||context->owner!=GetCurrentThreadId()||!bounded(code,63)||!output||!written||!expected||!expected_count
       ||capacity<context->limit||expected_capacity<1440||date<19900101||date>20991231
       ||minute>2359||minute%100>59)return -1;
    *written=0;*expected_count=0;
    if(!context->codes.count(code))return -2;
    try {
        std::string identity(code);auto first=identity.find('.');auto last=identity.rfind('.');
        auto* contract=context->sink.base.getContract(identity.substr(last+1).c_str(),identity.substr(0,first).c_str());
        if(!contract||!contract->getCommInfo()||!contract->getCommInfo()->getSessionInfo())return -2;
        auto* session=contract->getCommInfo()->getSessionInfo();
        if(session->getTradingMins()>1440)return -3;
        // 原WT session给出预期右端标签；适配器不另实现会话分钟算法。
        for(uint32_t i=1;i<=session->getTradingMins();++i) {
            auto value=session->minuteToTime(i);
            if(value<=minute)expected[(*expected_count)++]=value;
        }
        context->sink.date=date;context->sink.minute=minute;
        std::unique_ptr<WTSKlineSlice,Release<WTSKlineSlice>> slice(
            context->reader->readKlineSlice(code,KP_Minute1,context->limit,static_cast<uint64_t>(date)*10000+minute));
        if(!slice)return 0;
        if(slice->size()>capacity)return -4;
        for(uint32_t i=0;i<slice->get_block_counts();++i) {
            auto count=slice->get_block_size(i);auto* begin=slice->get_block_addr(i);
            if(count>capacity-*written||(count&&!begin))return -4;
            if(count)std::copy(begin,begin+count,output+*written);
            *written+=count;
        }
        return *written==slice->size()?0:-4;
    } catch(...) {return -5;}
}

extern "C" __declspec(dllexport) bool gh_collection_reader_close(void* handle,uint32_t seconds_ms) {
    auto* context=static_cast<Context*>(handle);if(!context)return true;
    if(context->owner!=GetCurrentThreadId()||!seconds_ms||seconds_ms>60000)return false;
    try {
        if(!context->stop(context->reader,seconds_ms))return false;
        context->destroy(context->reader);delete context;return true;
    } catch(...) {return false;} // C ABI不传播C++异常，调用方仍持有原句柄及最终关闭责任。
}
