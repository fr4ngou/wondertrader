#include "Session.h"
#include "../GuanhengData/QmtTickMapping.h"
#include "../WtDtCore/ParserAdapter.h"
#include "../WtDtCore/DataManager.h"
#include "../WtDtCore/StateMonitor.h"
#include "../WtDtCore/WtHelper.h"
#include "../WTSTools/WTSBaseDataMgr.h"
#include "../WTSUtils/WTSCfgLoader.h"
#include "../Includes/WTSVariant.hpp"
#include "../Includes/WTSDataDef.hpp"
#include <atomic>
#include <cstring>
#include <memory>
#include <mutex>
#include <stdexcept>
#include <thread>
#include <vector>
#include <filesystem>
#include "../Share/IniHelper.hpp"
#include "../Share/TimeUtils.hpp"

namespace {
// 仅观察原Writer已走到broadcastTick的次数，不维护另一套聚合/量额状态。
struct ObservedDataManager final : DataManager {
    std::atomic<uint64_t> processed{0};
    std::atomic<uint64_t> writer_errors{0};
    void outputLog(WTSLogLevel level,const char* message) override {
        // ParserAdapter 的 handleQuote 没有返回值；真实 Writer 错误从原公开 sink
        // 闩锁后继续原日志路径。时段过滤可以合法少广播，不能用 processed 差额推断失败。
        if(level==LL_ERROR)writer_errors.fetch_add(1,std::memory_order_release);
        DataManager::outputLog(level,message);
    }
    bool writer_failed() const { return writer_errors.load(std::memory_order_acquire)!=0; }
    void broadcastTick(wtp::WTSTickData* tick) override {
        DataManager::broadcastTick(tick); processed.fetch_add(1,std::memory_order_relaxed);
    }
};
class InputParser final : public wtp::IParserApi {
public:
    wtp::IParserSpi* sink=nullptr; wtp::CodeSet codes; bool connected=false;
    bool init(wtp::WTSVariant*) override { return true; }
    void release() override { connected=false;sink=nullptr; }
    bool connect() override { connected=true;return true; }
    bool disconnect() override { connected=false;return true; }
    bool isConnected() override { return connected; }
    void subscribe(const wtp::CodeSet& value) override { codes.insert(value.begin(),value.end()); }
    void unsubscribe(const wtp::CodeSet& value) override { for(const auto& code:value)codes.erase(code); }
    void registerSpi(wtp::IParserSpi* value) override { sink=value; }
};
struct Session {
    WTSBaseDataMgr base; StateMonitor monitor; ObservedDataManager data;
    ParserAdapter adapter; InputParser* input=nullptr;
    guanheng::QmtHttpProfile profile; guanheng::SourceSession source;
    std::mutex mutex; std::thread::id management=std::this_thread::get_id(),producer;
    std::filesystem::path writer_marker;
    std::atomic<uint64_t> delivered{0}; bool writer=false,parser=false,monitor_running=false,closed=false,lifecycle_writer=false;
    Session():adapter(&base,&data,nullptr) {}
    void finish() {
        if(monitor_running){monitor.stop();monitor_running=false;}
        if(parser){adapter.release();parser=false;input=nullptr;}
        if(writer){data.release();writer=false;}
        closed=true;
    }
    void initialize(const char* path,const char* directory) {
        if(!path||!directory||!*path||!*directory)throw std::invalid_argument("configuration");
        WtHelper::set_module_dir(directory);
        auto config=WTSCfgLoader::load_from_file(path);if(!config)throw std::invalid_argument("configuration");
        struct Release {wtp::WTSVariant* p;~Release(){p->release();}} release{config};
        auto files=config->get("basefiles");auto writer_cfg=config->get("writer");auto qmt=config->get("qmt_source");
        if(!files||!writer_cfg||!qmt)throw std::invalid_argument("configuration");
        // 模块在实例初始化时固定；缺省沿原库，适配库须由配置显式选择。
        if(writer_cfg->has("module")){
            const std::string module=writer_cfg->getCString("module");
            if(module!="WtDataStorage"&&module!="WtDataStorageLifecycle")throw std::invalid_argument("writer module");
            lifecycle_writer=module=="WtDataStorageLifecycle";
        }
        if(!base.loadSessions(files->getCString("session"))||!base.loadCommodities(files->getCString("commodity"))||!base.loadContracts(files->getCString("contract")))throw std::invalid_argument("basefiles");
        if(files->has("holiday")&&!base.loadHolidays(files->getCString("holiday")))throw std::invalid_argument("holidays");
        if(base.getContractSize()==0||base.getContractSize()>10000||writer_cfg->getBoolean("async"))throw std::invalid_argument("synchronous collector configuration");
        profile.version=qmt->getCString("version");profile.source_license=qmt->getCString("source_license");
        profile.time_encoding="epoch_ms";profile.minute_boundary="right";profile.full_tick_cumulative=true;
        profile.volume_to_shares=qmt->getDouble("volume_multiplier");profile.amount_to_yuan=qmt->getDouble("amount_multiplier");
        if(!guanheng::qmt_mapping::check_profile(profile).ok())throw std::invalid_argument("source profile");
        source.instance_id="qmt-quote-stream";source.session_id="external-native-collector";source.generation=1;
        writer_marker=std::filesystem::absolute(writer_cfg->getCString("path"))/"marker.ini";
        const bool allday=config->getBoolean("allday");
        if(!allday&&!monitor.initialize(config->getCString("statemonitor"),&base,&data))throw std::invalid_argument("statemonitor");
        // DataManager进入init后即持有已创建Writer；部分失败也必须经同一release回收。
        writer=true;
        if(!data.init(writer_cfg,&base,allday?nullptr:&monitor)||data.writer_failed())throw std::runtime_error("writer");
        input=new InputParser();parser=true;
        if(!adapter.initExt("qmt-quote-stream",input)||input->codes.size()!=base.getContractSize()||!adapter.run())throw std::runtime_error("parser");
        if(!allday){monitor.run();monitor_running=true;}
    }
    int push(const char* text,uint32_t length) {
        std::lock_guard<std::mutex> guard(mutex);
        if(closed||!text||length==0||length>2097152)return -1;
        if(data.writer_failed())return -6;
        if(producer==std::thread::id())producer=std::this_thread::get_id();
        if(producer!=std::this_thread::get_id())return -2;
        auto document=guanheng::qmt_mapping::parse(std::string(text,length));
        if(document.MemberCount()==0||document.MemberCount()>200)return -3;
        std::vector<std::string> codes;codes.reserve(document.MemberCount());
        for(auto it=document.MemberBegin();it!=document.MemberEnd();++it){
            const std::string symbol(it->name.GetString(),it->name.GetStringLength());
            if(symbol.size()!=9||symbol[6]!='.')return -3;
            std::string code=(symbol.substr(7)=="SH"?"SSE.":symbol.substr(7)=="SZ"?"SZSE.":"")+symbol.substr(0,6);
            if(!input->codes.count(code))return -4;codes.push_back(code);
        }
        auto values=guanheng::qmt_mapping::map_ticks(codes,std::string(text,length),profile,source);
        // 整批映射先完成；沿原handleQuote(procFlag=1)进行快照切片和分钟写入。
        for(auto& value:values){
            if(data.writer_failed())return -6;
            auto tick=std::unique_ptr<wtp::WTSTickData,void(*)(wtp::WTSTickData*)>(wtp::WTSTickData::create(value.tick),[](wtp::WTSTickData* item){item->release();});
            adapter.handleQuote(tick.get(),1);
            // 同步 Writer 已 flush 本次错误日志；失败 tick 不计成功投递。
            // 批内前序 tick 可能已生效，-6 代表结果失败且不可自动重放整包。
            if(data.writer_failed())return -6;
            delivered.fetch_add(1,std::memory_order_relaxed);
        }
        return static_cast<int>(values.size());
    }
};
}
int gh_datakit_create(const char* config,const char* directory,void** output){
    if(!output)return -1;*output=nullptr;auto session=std::make_unique<Session>();
    try{session->initialize(config,directory);*output=session.release();return 0;}
    catch(...){try{session->finish();}catch(...){}return -1;}
}
int gh_datakit_push_quotes(void* value,const char* text,uint32_t length){if(!value)return -1;try{return static_cast<Session*>(value)->push(text,length);}catch(...){return -5;}}
int gh_datakit_archive(void* value,const char* sid){if(!value||!sid||!*sid)return -1;try{auto& s=*static_cast<Session*>(value);std::lock_guard<std::mutex> guard(s.mutex);if(s.closed)return -1;if(s.data.writer_failed())return -6;s.data.transHisData(sid);return s.data.writer_failed()?-6:0;}catch(...){return -1;}}
int gh_datakit_archive_done(void* value,const char* sid){
    if(!value||!sid||!*sid||std::strlen(sid)>15)return -1;
    try{
        auto& s=*static_cast<Session*>(value);
        if(s.data.writer_failed())return -6;
        // isSessionProceeded读取初始化时载入的会话日期；本次异步归档以原Writer
        // 在队列尾写出的marker为兼容观察。它不能区分同日的多次归档；
        // 显式生命周期模式以close排空本次任务后，再由Helper回读数据。
        IniHelper marker;marker.load(s.writer_marker.string().c_str());
        const int state=marker.readValue<uint32_t>((std::string("markers.")+sid).c_str(),0)>=TimeUtils::getCurDate()?1:0;
        return s.data.writer_failed()?-6:state;
    }catch(...){return -1;}
}
// key=4 是原 Writer sink 的累计错误数，允许生产/归档线程并发时由管理线程读取。
uint64_t gh_datakit_count(void* value,uint32_t key){if(!value)return 0;auto& s=*static_cast<Session*>(value);if(key==0)return s.input?s.input->codes.size():0;if(key==1)return s.delivered.load();if(key==2)return s.data.processed.load();if(key==3)return s.lifecycle_writer?1:0;if(key==4)return s.data.writer_errors.load(std::memory_order_acquire);return 0;}
int gh_datakit_close(void* value){
    if(!value)return -1;
    auto* s=static_cast<Session*>(value);
    if(std::this_thread::get_id()!=s->management)return -2;
    try{std::lock_guard<std::mutex> guard(s->mutex);s->finish();}catch(...){return -3;}
    // 正值 1：资源已真实释放，但写入/后台归档曾失败。负数：保留原句柄。
    // 必须在 release 排空后台并刷出最后错误后取闩锁；不能返回负数后再 delete。
    const int result=s->data.writer_failed()?1:0;
    delete s;
    return result;
}
