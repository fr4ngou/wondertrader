#include "RealtimeBridge.h"
#include "ContextAccess.h"
#include "../WtRunner/WtRunner.h"
#include "../WtCore/WtHelper.h"
#include "../Includes/CtaStrategyDefs.h"
#include "../Includes/ICtaStraCtx.h"
#include "../Includes/WTSDataDef.hpp"
#include "../Includes/WTSVariant.hpp"
#include <windows.h>
#include <bcrypt.h>
#include <rapidjson/document.h>
#include <algorithm>
#include <array>
#include <atomic>
#include <cmath>
#include <cstddef>
#include <cstring>
#include <filesystem>
#include <limits>
#include <map>
#include <memory>
#include <mutex>
#include <set>
#include <stdexcept>
#include <string>
#include <type_traits>
#include <vector>

namespace {
namespace fs = std::filesystem;
namespace json = rapidjson;
using namespace wtp;
static_assert(sizeof(void*) == 8, "Realtime bridge requires x64");
static_assert(std::is_standard_layout<GhRtEvent>::value, "C ABI requires POD layout");
struct Rejected { int32_t code; };
void require(bool ok, int32_t code=GH_RT_INVALID) { if (!ok) throw Rejected{code}; }

// 本进程只准入一个owner。失败/停止未确认时保持全部依赖，进程退出回收模块。
// 无静态析构Runner：析构可能无限等待，最终关闭由控制线程与父Job共同负责。
struct Owner {
    std::mutex control;
    std::atomic<uint32_t> phase{GH_RT_NEW}, controller{0}, active{0}, context_id{0};
    std::atomic<bool> initialized{false};
    std::atomic<int32_t> failure{0}, native_exit{0};
    std::atomic<bool> requested{false}, created{false}, destroyed{false};
    std::atomic<uint64_t> epochs{0}, callback_count{0}, setters{0};
    std::atomic<WtRunner*> runner{nullptr};
    GhRtConfig config{};
    GhRtCallback callback=nullptr;
    void* user=nullptr;
    std::set<std::string> reads, executions;
    std::vector<HANDLE> pinned;
    HANDLE lease=INVALID_HANDLE_VALUE;
    bool main_registered=false; // 只由串行INIT回调设置；进入run前后由原线程顺序发布。
    void fail(int32_t code) noexcept {
        int32_t expected=0;
        failure.compare_exchange_strong(expected, code<0 ? code : GH_RT_CALLBACK);
        requested.store(true);
        if (auto* p=runner.load()) p->request_stop();
    }
    void close_pins() noexcept {
        for (HANDLE h:pinned) CloseHandle(h);
        pinned.clear();
        if (lease!=INVALID_HANDLE_VALUE) { CloseHandle(lease); lease=INVALID_HANDLE_VALUE; }
    }
};
Owner& owner() { static Owner* p=new Owner(); return *p; }
uint64_t token() { return static_cast<uint64_t>(reinterpret_cast<uintptr_t>(&owner())); }

struct Borrow { ICtaStraCtx* ctx; uint64_t epoch; uint32_t kind; DWORD thread; };
thread_local Borrow* borrowed=nullptr;
Borrow& access(uint64_t epoch, bool schedule_only=false) {
    require(borrowed && borrowed->epoch==epoch && epoch, GH_RT_BORROW);
    require(borrowed->thread==GetCurrentThreadId(), GH_RT_THREAD);
    require(schedule_only ? borrowed->kind==GH_RT_SCHEDULE :
        (borrowed->kind==GH_RT_INIT || borrowed->kind==GH_RT_SCHEDULE), GH_RT_STATE);
    require(owner().failure.load()==0 && !owner().requested.load(), GH_RT_STATE);
    return *borrowed;
}

template<size_t N> std::string text(const char (&s)[N]) {
    const auto* end=static_cast<const char*>(std::memchr(s, 0, N));
    require(end && end!=s);
    return std::string(s, end);
}
std::string short_text(const char* s, size_t capacity) {
    require(s!=nullptr);
    size_t size=0;while(size<capacity&&s[size])++size;
    require(size>0&&size<capacity);return std::string(s,size);
}
bool safe_name(const std::string& s) {
    return !s.empty() && s.size()<GH_RT_CODE_BYTES && std::all_of(s.begin(),s.end(),[](unsigned char c){
        return (c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')||c=='_'||c=='-'||c=='.';
    }) && s!="." && s!="..";
}
void copy_text(char* out, size_t capacity, const std::string& s) {
    require(s.size()<capacity); std::memset(out,0,capacity); std::memcpy(out,s.data(),s.size());
}
std::string symbol(const char* value) {
    auto s=short_text(value,GH_RT_CODE_BYTES);
    require(owner().reads.count(s)!=0); return s;
}
fs::path physical(const std::string& value) {
    // WT旧CWD入口使用固定缓冲区，首版路径保留ASCII且拒绝UNC/ADS/重解析。
    require(value.size()>3 && value.size()<240 && value[1]==':' &&
        (value[2]=='/'||value[2]=='\\'));
    require(std::all_of(value.begin(),value.end(),[](unsigned char c){return c>=32&&c<127;}));
    require(value.find(':',2)==std::string::npos);
    fs::path p(value);
    for (const auto& part:p.relative_path()) require(part!="." && part!="..");
    fs::path walk=p.root_path();
    for (const auto& part:p.relative_path()) {
        walk/=part;
        DWORD attrs=GetFileAttributesW(walk.c_str());
        require(attrs!=INVALID_FILE_ATTRIBUTES && !(attrs&FILE_ATTRIBUTE_REPARSE_POINT));
    }
    return fs::canonical(p);
}
bool same(const fs::path& a,const fs::path& b) { return fs::equivalent(a,b); }

struct Handle {
    HANDLE value=INVALID_HANDLE_VALUE;
    ~Handle(){if(value!=INVALID_HANDLE_VALUE)CloseHandle(value);}
    HANDLE take(){auto p=value;value=INVALID_HANDLE_VALUE;return p;}
};
struct Hash {
    BCRYPT_ALG_HANDLE algorithm=nullptr;
    BCRYPT_HASH_HANDLE hash=nullptr;
    std::vector<unsigned char> state;
    Hash() {
        require(BCryptOpenAlgorithmProvider(&algorithm,BCRYPT_SHA256_ALGORITHM,nullptr,0)>=0);
        DWORD size=0, got=0;
        if(BCryptGetProperty(algorithm,BCRYPT_OBJECT_LENGTH,reinterpret_cast<PUCHAR>(&size),sizeof(size),&got,0)<0 || got!=sizeof(size)) {
            BCryptCloseAlgorithmProvider(algorithm,0);algorithm=nullptr;throw Rejected{GH_RT_NATIVE};
        }
        try {
            state.resize(size);
            require(BCryptCreateHash(algorithm,&hash,state.data(),size,nullptr,0,0)>=0,GH_RT_NATIVE);
        } catch(...) { BCryptCloseAlgorithmProvider(algorithm,0);algorithm=nullptr;throw; }
    }
    ~Hash(){if(hash)BCryptDestroyHash(hash);if(algorithm)BCryptCloseAlgorithmProvider(algorithm,0);}
    void add(const unsigned char* p,DWORD count) { require(BCryptHashData(hash,const_cast<PUCHAR>(p),count,0)>=0,GH_RT_NATIVE); }
    std::string finish() {
        unsigned char digest[32];require(BCryptFinishHash(hash,digest,sizeof(digest),0)>=0,GH_RT_NATIVE);
        static const char hex[]="0123456789abcdef";std::string out;
        for(auto c:digest){out.push_back(hex[c>>4]);out.push_back(hex[c&15]);}return out;
    }
};
std::string pin(const fs::path& file, uint64_t maximum, const std::string& expected={}, bool keep_bytes=true) {
    Handle h; h.value=CreateFileW(file.c_str(),GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_FLAG_OPEN_REPARSE_POINT,nullptr);
    require(h.value!=INVALID_HANDLE_VALUE);
    BY_HANDLE_FILE_INFORMATION info{};
    require(GetFileInformationByHandle(h.value,&info) && !(info.dwFileAttributes&(FILE_ATTRIBUTE_DIRECTORY|FILE_ATTRIBUTE_REPARSE_POINT)));
    const uint64_t size=(uint64_t(info.nFileSizeHigh)<<32)|info.nFileSizeLow;
    require(size>0 && size<=maximum,GH_RT_CAPACITY);
    Hash hash;std::array<unsigned char,65536> bytes{};std::string result;
    if(keep_bytes)result.reserve(static_cast<size_t>(size));
    uint64_t total=0;DWORD got=0;
    for(;;){require(ReadFile(h.value,bytes.data(),static_cast<DWORD>(bytes.size()),&got,nullptr)!=FALSE);
        if(!got)break;total+=got;require(total<=maximum,GH_RT_CAPACITY);hash.add(bytes.data(),got);
        if(keep_bytes)result.append(reinterpret_cast<const char*>(bytes.data()),got);
    }
    require(total==size);
    auto actual=hash.finish();if(!expected.empty())require(actual==expected);
    owner().pinned.push_back(h.value);h.take();return result;
}
void inspect_json(const json::Value& value,unsigned depth,size_t& nodes) {
    require(depth<=24 && ++nodes<=65536,GH_RT_CAPACITY);
    if(value.IsObject()){
        std::set<std::string> keys;
        for(auto it=value.MemberBegin();it!=value.MemberEnd();++it){
            std::string key(it->name.GetString(),it->name.GetStringLength());
            require(key.find('\0')==std::string::npos && keys.insert(key).second);
            inspect_json(it->value,depth+1,nodes);
        }
    } else if(value.IsArray()) {for(auto& v:value.GetArray())inspect_json(v,depth+1,nodes);}
    else if(value.IsString())require(std::memchr(value.GetString(),0,value.GetStringLength())==nullptr);
}
json::Document document(const std::string& bytes) {
    require(std::all_of(bytes.begin(),bytes.end(),[](unsigned char c){return c>0&&c<128;}));
    json::Document d;d.Parse<json::kParseValidateEncodingFlag|json::kParseIterativeFlag>(bytes.data(),bytes.size());
    require(!d.HasParseError()&&d.IsObject());size_t nodes=0;inspect_json(d,0,nodes);return d;
}
const json::Value& member(const json::Value& v,const char* key) {require(v.IsObject()&&v.HasMember(key));return v[key];}
void keys(const json::Value& v,std::initializer_list<const char*> allowed) {
    require(v.IsObject());for(auto it=v.MemberBegin();it!=v.MemberEnd();++it)
        require(std::any_of(allowed.begin(),allowed.end(),[&](const char* s){return std::strcmp(it->name.GetString(),s)==0;}));
}
std::string js(const json::Value& v) {require(v.IsString());return {v.GetString(),v.GetStringLength()};}
void truth(const json::Value& v,bool expected) {require(v.IsBool()&&v.GetBool()==expected);}
void zero(const json::Value& v) {require(v.IsInt()&&v.GetInt()==0);}
void inactive(const json::Value& v) {keys(v,{"active"});truth(member(v,"active"),false);}
fs::path local_file(const fs::path& root,const std::string& name) {
    fs::path p(name);require(p.is_relative()&&!name.empty());
    auto actual=physical((root/p).string());
    auto relative=actual.lexically_relative(root);require(!relative.empty()&&*relative.begin()!="..");
    return actual;
}
void admit(const GhRtConfig& cfg) {
    auto& o=owner();
    require(cfg.size==sizeof(cfg)&&cfg.abi_version==GH_RT_ABI_VERSION&&cfg.scope==GH_RT_SYNTHETIC&&cfg.reserved==0);
    require(cfg.read_count>0&&cfg.read_count<=GH_RT_MAX_READS&&cfg.execution_count>0&&cfg.execution_count<=GH_RT_MAX_TARGETS);
    for(uint32_t i=0;i<cfg.read_count;++i){auto s=text(cfg.read_symbols[i]);require(safe_name(s)&&o.reads.insert(s).second);}
    for(uint32_t i=0;i<cfg.execution_count;++i){auto s=text(cfg.execution_symbols[i]);require(o.reads.count(s)&&o.executions.insert(s).second);}
    const auto id=text(cfg.strategy_id), main=text(cfg.main_symbol);require(safe_name(id)&&o.reads.count(main));
    auto root=physical(text(cfg.run_root));require(fs::is_directory(root)&&same(root,fs::current_path()));
    require(same(root,physical(WtHelper::getCWD())));
    o.lease=CreateFileW((root/".gh-rt-owner.lock").c_str(),GENERIC_READ|GENERIC_WRITE,0,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);
    require(o.lease!=INVALID_HANDLE_VALUE);
    require(!fs::exists(root/"generated"));
    std::array<fs::path,3> modules;
    for(size_t i=0;i<3;++i){const auto& m=cfg.modules[i];require(m.role==i+1&&m.reserved==0);
        auto sha=text(m.sha256);require(sha.size()==64&&std::all_of(sha.begin(),sha.end(),[](char c){return (c>='0'&&c<='9')||(c>='a'&&c<='f');}));
        modules[i]=physical(text(m.path));pin(modules[i],64ull*1024*1024,sha,false);
    }
    require(same(modules[0].parent_path(),root/"cta"));
    require(same(modules[1].parent_path(),root/"parsers")&&modules[1].filename()=="ParserGuanhengSynthetic.dll");
    require(modules[2].filename()=="GuanhengRealtimeReader.dll");
    HMODULE self=nullptr;
    require(GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
        reinterpret_cast<LPCWSTR>(&gh_rt_owner_token),&self)!=FALSE);
    wchar_t module_path[1024]{};DWORD length=GetModuleFileNameW(self,module_path,1024);require(length>0&&length<1024);
    require(same(modules[0],fs::path(module_path)));
    size_t files=0;for(const auto& entry:fs::directory_iterator(root/"cta")){
        require(entry.is_regular_file()&&same(entry.path(),modules[0]));++files;
    }require(files==1);
    // 从可信文件描述符固定字节；FILE_SHARE_READ保留到stop，防原Loader第二次读到替换文件。
    auto config=document(pin(root/"config.json",1024*1024));
    keys(config,{"scope","noorders","basefiles","bspolicy","env","parsers","traders","executers","data","strategies","notifier"});
    require(js(member(config,"scope"))=="synthetic");truth(member(config,"noorders"),true);
    for(const char* key:{"traders","executers"}){auto& v=member(config,key);require(v.IsArray()&&v.Empty());}
    if(config.HasMember("notifier"))inactive(config["notifier"]);
    const auto& env=member(config,"env");keys(env,{"name","managed_stop","poolsize","product","riskmon","fees"});
    require(js(member(env,"name"))=="cta");truth(member(env,"managed_stop"),true);zero(member(env,"poolsize"));
    keys(member(env,"product"),{"session"});require(safe_name(js(member(env["product"],"session"))));
    if(env.HasMember("riskmon"))inactive(env["riskmon"]);
    if(env.HasMember("fees"))document(pin(local_file(root,js(env["fees"])),4*1024*1024));
    const auto& bases=member(config,"basefiles");keys(bases,{"session","commodity","contract","holiday"});
    for(const char* k:{"session","commodity","contract"})document(pin(local_file(root,js(member(bases,k))),4*1024*1024));
    if(bases.HasMember("holiday"))document(pin(local_file(root,js(bases["holiday"])),4*1024*1024));
    document(pin(local_file(root,js(member(config,"bspolicy"))),1024*1024));
    const auto& ps=member(config,"parsers");require(ps.IsArray()&&ps.Size()==1);
    require(js(member(ps[0],"module"))=="ParserGuanhengSynthetic");truth(member(ps[0],"active"),true);
    // 测试parser及Reader自行准入各自字段；模块选择只能是本发行固定名称。
    const auto& data=member(config,"data");keys(data,{"store","align_by_section"});
    const auto& store=member(data,"store");require(js(member(store,"module"))=="GuanhengRealtimeReader");
    const auto& strategies=member(config,"strategies");keys(strategies,{"cta"});
    const auto& cta=member(strategies,"cta");require(cta.IsArray()&&cta.Size()==1);
    const auto& strategy=cta[0];keys(strategy,{"id","name","active","slippage","params"});
    require(js(member(strategy,"id"))==id&&js(member(strategy,"name"))=="GuanhengRealtime.Core");
    truth(member(strategy,"active"),true);zero(member(strategy,"slippage"));
    require(member(strategy,"params").IsObject()&&strategy["params"].MemberCount()==0);
    auto logging=document(pin(root/"logcfg.json",65536));keys(logging,{"root"});
    const auto& logger=member(logging,"root");keys(logger,{"level","async","sinks"});truth(member(logger,"async"),false);
    auto level=js(member(logger,"level"));require(level=="debug"||level=="info"||level=="warn"||level=="error"||level=="off");
    const auto& sinks=member(logger,"sinks");require(sinks.IsArray()&&sinks.Size()==1);keys(sinks[0],{"type","pattern"});
    require(js(member(sinks[0],"type"))=="ostream_sink"&&js(member(sinks[0],"pattern"))=="%v");
    require(fs::create_directory(root/"generated"));
}

GhRtBar bar_value(const WTSBarStruct& value) { return guanheng::cta_bar(value); }

void emit(uint32_t kind,ICtaStraCtx* ctx,uint32_t date=0,uint32_t time=0,uint32_t tdate=0,
    const char* code=nullptr,const char* period=nullptr,const WTSBarStruct* bar=nullptr) noexcept {
    auto& o=owner();
    if(o.failure.load()||o.requested.load())return;
    // 不持control锁进入Python；回调内facts/bars等同步重入同一线程。
    if(o.active.fetch_add(1)!=0){o.active.fetch_sub(1);o.fail(GH_RT_THREAD);return;}
    struct Guard { Owner& o; ~Guard(){borrowed=nullptr;o.active.fetch_sub(1);} } guard{o};
    try {
        require(ctx&&o.callback,GH_RT_STATE);
        require(kind!=GH_RT_BAR||(bar&&code&&period),GH_RT_NATIVE);
        require(ctx->name()==std::string(o.config.strategy_id),GH_RT_NATIVE);
        if(kind==GH_RT_INIT){bool expected=false;require(o.initialized.compare_exchange_strong(expected,true),GH_RT_STATE);o.context_id.store(ctx->id());}
        else require(o.initialized.load()&&o.context_id.load()==ctx->id(),GH_RT_BORROW);
        GhRtEvent event{};event.size=sizeof(event);event.kind=kind;event.epoch=o.epochs.fetch_add(1)+1;
        require(event.epoch!=0,GH_RT_CAPACITY);
        event.owner_token=token();event.thread_id=GetCurrentThreadId();event.ctx_id=ctx->id();
        event.date=date?date:ctx->stra_get_date();event.time=time?time:ctx->stra_get_time();
        event.tdate=tdate?tdate:ctx->stra_get_tdate();
        if(code)copy_text(event.symbol,sizeof(event.symbol),short_text(code,GH_RT_CODE_BYTES));
        if(period)copy_text(event.period,sizeof(event.period),short_text(period,sizeof(event.period)));
        if(bar)event.bar=bar_value(*bar);
        Borrow b{ctx,event.epoch,kind,GetCurrentThreadId()};borrowed=&b;o.callback_count.fetch_add(1);
        if(o.callback(&event,o.user)!=0)o.fail(GH_RT_CALLBACK);
    }catch(const Rejected& e){o.fail(e.code);}catch(...){o.fail(GH_RT_NATIVE);}
}
class Strategy final:public CtaStrategy {
public:
    explicit Strategy(const char* id):CtaStrategy(id){}
    ~Strategy() override {owner().destroyed.store(true);}
    const char* getName() override {return "Core";}
    const char* getFactName() override {return "GuanhengRealtime";}
    bool init(WTSVariant*) override {return owner().phase.load()==GH_RT_CONFIGURING;}
    void on_init(ICtaStraCtx* ctx) override {
        try {for(const auto& s:owner().reads)ctx->stra_sub_ticks(s.c_str());
            ctx->stra_sub_bar_events(owner().config.main_symbol,"m1");
            emit(GH_RT_INIT,ctx);
            if(!owner().main_registered&&!owner().failure.load()&&!owner().requested.load())owner().fail(GH_RT_STATE);
        }catch(...){owner().fail(GH_RT_NATIVE);}
    }
    void on_session_begin(ICtaStraCtx* ctx,uint32_t d) override {emit(GH_RT_SESSION_BEGIN,ctx,0,0,d);}
    void on_session_end(ICtaStraCtx* ctx,uint32_t d) override {emit(GH_RT_SESSION_END,ctx,0,0,d);}
    void on_bar(ICtaStraCtx* ctx,const char* code,const char* period,WTSBarStruct* b) override {emit(GH_RT_BAR,ctx,0,0,0,code,period,b);}
    void on_schedule(ICtaStraCtx* ctx,uint32_t d,uint32_t t) override {emit(GH_RT_SCHEDULE,ctx,d,t);}
};
class Factory final:public ICtaStrategyFact {
public:
    const char* getName() override{return "GuanhengRealtime";}
    void enumStrategy(FuncEnumStrategyCallback cb) override{if(cb)cb("GuanhengRealtime","Core",true);}
    CtaStrategy* createStrategy(const char* name,const char* id) override {
        try {auto& o=owner();require(o.phase.load()==GH_RT_CONFIGURING&&name&&id&&std::strcmp(name,"Core")==0&&std::strcmp(id,o.config.strategy_id)==0);
            bool expected=false;require(o.created.compare_exchange_strong(expected,true));
            return new Strategy(id);
        }catch(...){owner().fail(GH_RT_NATIVE);return nullptr;}
    }
    bool deleteStrategy(CtaStrategy* s) override {auto* value=dynamic_cast<Strategy*>(s);if(!value)return false;delete value;return true;}
};
Factory& factory(){static Factory* p=new Factory();return *p;}

template<class F> int32_t api(F f) noexcept {
    try {return f();}catch(const guanheng::CtaAccessError& e){
        if(e.code==GH_RT_NATIVE||e.partial)owner().fail(GH_RT_NATIVE);return e.code;
    }catch(const Rejected& e){if(e.code==GH_RT_NATIVE)owner().fail(e.code);return e.code;}catch(...){owner().fail(GH_RT_NATIVE);return GH_RT_NATIVE;}
}
std::unique_lock<std::mutex> control() {
    require(!borrowed,GH_RT_THREAD);
    require(owner().controller.load()==GetCurrentThreadId(),GH_RT_THREAD);
    std::unique_lock<std::mutex> lock(owner().control,std::try_to_lock);require(lock.owns_lock(),GH_RT_STATE);return lock;
}
std::map<std::string,double> enumerate(ICtaStraCtx* ctx) {
    return guanheng::cta_targets(*ctx,owner().reads);
}

} // namespace

extern "C" {
GH_RT_API ICtaStrategyFact* createStrategyFact(){return &factory();}
GH_RT_API void deleteStrategyFact(ICtaStrategyFact*& value){if(value==&factory())value=nullptr;}
uint32_t GH_RT_CALL gh_rt_abi_version(){return GH_RT_ABI_VERSION;}
uint64_t GH_RT_CALL gh_rt_owner_token(){return token();}
uint64_t GH_RT_CALL gh_rt_layout(uint32_t id){
    switch(id){case 1:return sizeof(GhRtConfig);case 2:return sizeof(GhRtEvent);case 3:return sizeof(GhRtBar);
    case 4:return sizeof(GhRtFacts);case 5:return sizeof(GhRtPosition);case 6:return sizeof(GhRtTarget);
    case 7:return sizeof(GhRtStatus);case 8:return sizeof(GhRtModule);case 101:return offsetof(GhRtBar,time);
    case 102:return offsetof(GhRtBar,open);case 103:return offsetof(GhRtEvent,bar);case 104:return offsetof(GhRtConfig,modules);default:return 0;}
}
int32_t GH_RT_CALL gh_rt_configure(const GhRtConfig* config,GhRtCallback callback,void* user){
    return api([&]()->int32_t{
        auto& o=owner();std::unique_lock<std::mutex> lock(o.control,std::try_to_lock);
        require(lock.owns_lock()&&!borrowed&&o.phase.load()==GH_RT_NEW,GH_RT_STATE);
        o.controller.store(GetCurrentThreadId());o.phase.store(GH_RT_CONFIGURING);
        try {
            require(config&&callback);o.config=*config;admit(o.config);o.callback=callback;o.user=user;
            auto* runner=new WtRunner();o.runner.store(runner);
            auto root=physical(text(o.config.run_root));runner->init((root/"logcfg.json").string());
            // Runner.init默认取解释器目录；使用原公开接口定位已核Reader及全新状态根。
            auto reader_dir=physical(text(o.config.modules[2].path)).parent_path().generic_string()+"/";
            auto generated=(root/"generated").generic_string()+"/";
            WtHelper::setInstDir(reader_dir.c_str());WtHelper::setGenerateDir(generated.c_str());
            require(runner->config((root/"config.json").string())&&o.created.load()&&!o.failure.load(),GH_RT_NATIVE);
            o.phase.store(GH_RT_CONFIGURED);return GH_RT_OK;
        }catch(const Rejected& e){o.fail(e.code);o.phase.store(o.runner.load()?GH_RT_STOPPING:GH_RT_REJECTED);if(!o.runner.load())o.close_pins();return e.code;}
        catch(...){o.fail(GH_RT_NATIVE);o.phase.store(o.runner.load()?GH_RT_STOPPING:GH_RT_REJECTED);if(!o.runner.load())o.close_pins();return GH_RT_NATIVE;}
    });
}
int32_t GH_RT_CALL gh_rt_run(){return api([]()->int32_t{
    auto lock=control();auto& o=owner();require(o.phase.load()==GH_RT_CONFIGURED&&!o.failure.load()&&!o.requested.load(),GH_RT_STATE);
    o.phase.store(GH_RT_RUNNING);o.runner.load()->run(true);o.native_exit.store(o.runner.load()->exit_code());
    if(o.runner.load()->stop_requested())o.requested.store(true);
    if(o.native_exit.load()){o.fail(GH_RT_NATIVE);return GH_RT_NATIVE;}
    return o.failure.load()?o.failure.load():GH_RT_OK;
});}
int32_t GH_RT_CALL gh_rt_request_stop(){return api([]()->int32_t{
    auto& o=owner();require(o.phase.load()!=GH_RT_NEW&&o.phase.load()!=GH_RT_REJECTED,GH_RT_STATE);
    o.requested.store(true);if(auto* r=o.runner.load())r->request_stop();return GH_RT_OK;
});}
int32_t GH_RT_CALL gh_rt_stop(){return api([]()->int32_t{
    auto lock=control();auto& o=owner();if(o.phase.load()==GH_RT_STOPPED)return GH_RT_OK;
    require(o.runner.load()!=nullptr&&o.phase.load()!=GH_RT_NEW,GH_RT_STATE);
    o.requested.store(true);o.phase.store(GH_RT_STOPPING);
    if(!o.runner.load()->stop())return GH_RT_PENDING;
    o.native_exit.store(o.runner.load()->exit_code());
    if(o.native_exit.load())o.fail(GH_RT_NATIVE);
    require(o.active.load()==0&&(!o.created.load()||o.destroyed.load()),GH_RT_NATIVE);
    o.phase.store(GH_RT_STOPPED);o.close_pins();return GH_RT_OK;
});}
int32_t GH_RT_CALL gh_rt_status(GhRtStatus* out){return api([&]()->int32_t{
    require(out&&out->size==sizeof(*out));auto& o=owner();
    // 控制线程轮询原stop_requested以观察任务失败；其他线程只取原子快照。
    if(!borrowed&&o.controller.load()==GetCurrentThreadId()){
        std::unique_lock<std::mutex> lock(o.control,std::try_to_lock);
        if(lock.owns_lock()&&o.phase.load()==GH_RT_RUNNING){
            auto* r=o.runner.load();if(r->stop_requested())o.requested.store(true);
            o.native_exit.store(r->exit_code());if(o.native_exit.load())o.fail(GH_RT_NATIVE);
        }
    }
    GhRtStatus value{};value.size=sizeof(value);
    value.phase=o.phase.load();value.failure=o.failure.load();value.native_exit=o.native_exit.load();
    value.stop_requested=o.requested.load();value.active_callbacks=o.active.load();value.callback_count=o.callback_count.load();
    value.setter_count=o.setters.load();value.owner_token=token();value.strategy_created=o.created.load();value.strategy_destroyed=o.destroyed.load();*out=value;return GH_RT_OK;
});}
int32_t GH_RT_CALL gh_rt_fail(uint64_t epoch,int32_t code){return api([&]()->int32_t{
    require(borrowed&&borrowed->epoch==epoch&&borrowed->thread==GetCurrentThreadId(),GH_RT_BORROW);
    require(code<0&&code>=GH_RT_UNKNOWN);owner().fail(code);return GH_RT_OK;
});}
int32_t GH_RT_CALL gh_rt_facts(uint64_t epoch,GhRtFacts* out){return api([&]()->int32_t{
    auto& b=access(epoch);require(out&&out->size==sizeof(*out));*out=guanheng::cta_facts(*b.ctx);return GH_RT_OK;
});}
int32_t GH_RT_CALL gh_rt_price(uint64_t epoch,const char* code,double* out){return api([&]()->int32_t{
    auto& b=access(epoch);require(out);*out=guanheng::cta_price(*b.ctx,symbol(code));return GH_RT_OK;
});}
int32_t GH_RT_CALL gh_rt_position(uint64_t epoch,const char* code,GhRtPosition* out){return api([&]()->int32_t{
    auto& b=access(epoch);require(out&&out->size==sizeof(*out));
    *out=guanheng::cta_position(*b.ctx,owner().reads,symbol(code));return GH_RT_OK;
});}
int32_t GH_RT_CALL gh_rt_bars(uint64_t epoch,const char* code,const char* period,uint32_t count,uint32_t is_main,
    GhRtBar* out,uint32_t capacity,uint32_t* written){return api([&]()->int32_t{
    auto& b=access(epoch);require(out&&written&&count&&count<=GH_RT_MAX_BARS&&capacity>=count&&capacity<=GH_RT_MAX_BARS&&is_main<=1,GH_RT_CAPACITY);
    *written=0;auto s=symbol(code);auto p=short_text(period,8);require(p=="m1"||p=="d1");
    if(is_main)require(b.kind==GH_RT_INIT&&p=="m1"&&s==owner().config.main_symbol&&!owner().main_registered,GH_RT_STATE);
    const auto copied=guanheng::cta_bars(*b.ctx,s,p,count,is_main!=0);
    std::copy(copied.begin(),copied.end(),out);*written=static_cast<uint32_t>(copied.size());
    if(is_main)owner().main_registered=true;return GH_RT_OK;
});}
int32_t GH_RT_CALL gh_rt_set_targets(uint64_t epoch,const GhRtTarget* targets,uint32_t count,GhRtTarget* readback,uint32_t capacity){
    return api([&]()->int32_t{
        auto& b=access(epoch,true);auto& o=owner();
        require(targets&&readback&&count==o.executions.size()&&capacity>=count&&capacity<=GH_RT_MAX_TARGETS);
        const auto copied=guanheng::cta_set_targets(*b.ctx,o.reads,o.executions,targets,count,o.setters);
        std::copy(copied.begin(),copied.end(),readback);return GH_RT_OK;
    });
}
} // extern C
