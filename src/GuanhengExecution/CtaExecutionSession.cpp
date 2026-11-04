#include "CtaExecutionSession.h"
#include "StandardExecutionHost.h"
#include "WtCore/WtCtaEngine.h"
#include "WtCore/WtDtMgr.h"
#include "WtCore/CtaStraContext.h"
#include "WtCore/TraderAdapter.h"
#include "WtCore/WtHelper.h"
#include "Includes/CtaStrategyDefs.h"
#include "Includes/IBaseDataMgr.h"
#include "Includes/WTSVariant.hpp"
#include <atomic>
#include <filesystem>
#include <stdexcept>
#include <thread>
#include <string>
#include <set>
#include <utility>
#include <Windows.h>

namespace guanheng {
namespace {
struct Busy {bool& value;explicit Busy(bool& v):value(v){value=true;}~Busy(){value=false;}};
std::atomic<bool> session_claimed{false};
struct ParserObservation {
    std::atomic<std::uint64_t> quotes{0}; // 行情worker进入自有SPI的报价次数，单位条。
    std::atomic<std::uint64_t> connects{0}; // 插件连接事件计数，单位次；不代表策略已计算。
    std::atomic<std::uint64_t> closes{0}; // 插件断开事件计数，单位次；停止过程同样保留。
    std::atomic<std::uint64_t> logs{0}; // 插件日志事件计数，单位次；日志正文继续归原日志入口。
};
// 只观察现有SPI再交原Adapter；不改变证券转换、分钟算法、订阅或事件准入。
class ObservedParserAdapter final:public wtp::ParserAdapter {
    std::shared_ptr<ParserObservation> observation; // 与Session共享，覆盖全部在途回调的有效期。
public:
    explicit ObservedParserAdapter(std::shared_ptr<ParserObservation> value):observation(std::move(value)){}
    void handleEvent(wtp::WTSParserEvent event,int32_t code)override {
        if(event==wtp::WPE_Connect)++observation->connects;
        if(event==wtp::WPE_Close)++observation->closes;
        wtp::ParserAdapter::handleEvent(event,code);
    }
    void handleQuote(wtp::WTSTickData* tick,uint32_t flag)override {
        ++observation->quotes;wtp::ParserAdapter::handleQuote(tick,flag);
    }
    void handleParserLog(wtp::WTSLogLevel level,const char* message)override {
        ++observation->logs;wtp::ParserAdapter::handleParserLog(level,message);
    }
};
bool name_valid(const std::string& value) {return !value.empty()&&value.size()<64&&value.find_first_of("/\\: \t\r\n")==std::string::npos&&value.find('\0')==std::string::npos;}
std::string strategy_file_key(const char* id) {
    if(!id)return {};
    std::string key;
    for(const unsigned char c:std::string(id)){
        if(c>='A'&&c<='Z')key+=static_cast<char>(c-'A'+'a');
        else if((c>='a'&&c<='z')||(c>='0'&&c<='9')||c=='_'||c=='-'||c=='.')key+=static_cast<char>(c);
        else return {};
    }
    if(key.empty()||key.size()>=64||key.back()=='.')return {};
    const auto stem=key.substr(0,key.find('.'));
    if(stem=="con"||stem=="prn"||stem=="aux"||stem=="nul"
        ||(stem.size()==4&&(stem.substr(0,3)=="com"||stem.substr(0,3)=="lpt")&&stem[3]>='1'&&stem[3]<='9'))return {};
    return key;
}
using Variant=wtp::WTSVariant;
bool field_type(const Variant* object,const char* key,Variant::ValueType type,bool required=false) {
    const auto* value=object->get(key);
    return value?value->type()==type:!required;
}
bool text_field(const Variant* object,const char* key) {
    if(!field_type(object,key,Variant::VT_String,true))return false;
    const auto value=object->getString(key);
    return !value.empty()&&value.size()<256&&value.find('\0')==std::string::npos;
}
bool configuration_valid(Variant* env,Variant* data,Variant* parsers) {
    // 原Boolean转换假定标量；全部公共字段先核类型，再交给原模块，避免局部插件已装载。
    if(!env||env->type()!=Variant::VT_Object||!data||data->type()!=Variant::VT_Object
        ||!parsers||parsers->type()!=Variant::VT_Array||!parsers->size()||parsers->size()>16
        ||!field_type(env,"name",Variant::VT_String,true)||env->getString("name")!="cta"
        ||!field_type(env,"product",Variant::VT_Object,true)
        ||!field_type(env,"filters",Variant::VT_String)||!field_type(env,"fees",Variant::VT_String)
        ||!field_type(env,"riskmon",Variant::VT_Object)
        ||!field_type(data,"align_by_section",Variant::VT_Boolean)
        ||!field_type(data,"store",Variant::VT_Object,true))return false;
    if(auto* pool=env->get("poolsize")) {
        const auto type=pool->type();
        if((type!=Variant::VT_Int32&&type!=Variant::VT_Uint32&&type!=Variant::VT_Int64&&type!=Variant::VT_Uint64)
            ||pool->asString()!="0")return false;
    }
    if(!text_field(env->get("product"),"session")||!text_field(data->get("store"),"module"))return false;
    if(auto* risk=env->get("riskmon")) {
        if(!field_type(risk,"active",Variant::VT_Boolean)||risk->getBoolean("active"))return false;
    }
    std::set<std::string> active_ids;
    for(std::uint32_t i=0;i<parsers->size();++i) {
        auto* cfg=parsers->get(i);
        if(!cfg||cfg->type()!=Variant::VT_Object||!field_type(cfg,"active",Variant::VT_Boolean))return false;
        if(!cfg->getBoolean("active"))continue;
        if(!text_field(cfg,"id")||!name_valid(cfg->getString("id"))||!text_field(cfg,"module")
            ||!field_type(cfg,"check_time",Variant::VT_Boolean)||!field_type(cfg,"filter",Variant::VT_String)
            ||!field_type(cfg,"code",Variant::VT_String)||!active_ids.insert(cfg->getString("id")).second)return false;
    }
    return !active_ids.empty();
}

}
class CtaExecutionSession::Impl:public wtp::IEngineEvtListener {
public:
    const std::thread::id owner=std::this_thread::get_id();
    wtp::IBaseDataMgr& base;wtp::IHotMgr* hot;StandardExecutionHost& execution;
    struct StrategyOwner {CtaExecutionStrategy binding;std::string id;bool delete_attempted=false;};
    std::vector<StrategyOwner> strategies;
    wtp::WtCtaEngine engine;wtp::WtDtMgr data;wtp::ParserAdapterMgr parsers;wtp::TraderAdapterMgr engine_traders;
    std::atomic<bool> requested{false};
    std::atomic<std::uint64_t> initializes{0},schedules{0},sessions{0};
    std::shared_ptr<ParserObservation> parser_observation=std::make_shared<ParserObservation>(); // Session及SPI共享的诊断owner。
    CtaExecutionPhase phase=CtaExecutionPhase::New;CtaExecutionFault fault=CtaExecutionFault::None;
    bool busy=false,engine_initialized=false,data_attempted=false,engine_stopped=false;
    HANDLE output_lease=INVALID_HANDLE_VALUE;
    CtaExecutionRecovery* recovery=nullptr;
    Impl(wtp::IBaseDataMgr& b,wtp::IHotMgr* h,StandardExecutionHost& e,std::vector<CtaExecutionStrategy> bindings)
        :base(b),hot(h),execution(e){
        if(bindings.empty()||bindings.size()>64)throw std::invalid_argument("cta_session_strategy_count");
        std::set<CtaStrategy*> pointers;
        std::set<std::string> names;
        for(const auto& value:bindings){
            if(!value.strategy||!value.factory)throw std::invalid_argument("cta_session_strategy_binding");
            const char* raw_id=value.strategy->id();const std::string id=raw_id?raw_id:"";
            const auto key=strategy_file_key(id.c_str());
            if(!pointers.insert(value.strategy).second||key.empty()||!names.insert(key).second
                ||(value.parameters&&value.parameters->type()!=Variant::VT_Object))
                throw std::invalid_argument("cta_session_strategy_binding");
            strategies.push_back({value,id,false});
        }
        // 在接管策略前完成全部可抛分配/检查；pending关闭保留此占用及完整依赖树。
        bool expected=false;
        if(!session_claimed.compare_exchange_strong(expected,true))throw std::invalid_argument("cta_session_already_active");
    }
    bool on_owner()const noexcept{return owner==std::this_thread::get_id();}
    void fail(CtaExecutionFault value) noexcept {if(fault==CtaExecutionFault::None)fault=value;requested.store(true);execution.request_stop();if(phase!=CtaExecutionPhase::Stopping&&phase!=CtaExecutionPhase::Closed)phase=CtaExecutionPhase::Failed;}
    void on_initialize_event() override{++initializes;}
    void on_schedule_event(std::uint32_t,std::uint32_t) override{++schedules;}
    void on_session_event(std::uint32_t,bool) override{++sessions;}
    bool stop_producers(std::uint32_t timeout){
        if(engine_initialized)engine.request_stop();
        if(!parsers.stop(timeout))return false;
        if(engine_initialized&&!engine_stopped){if(!engine.stop()&&fault==CtaExecutionFault::None)fault=CtaExecutionFault::NativeTask;engine_stopped=true;}
        return !data_attempted||data.stop(timeout);
    }
};
CtaExecutionSession::CtaExecutionSession(wtp::IBaseDataMgr& b,wtp::IHotMgr& h,StandardExecutionHost& e,CtaStrategy* s,ICtaStrategyFact& f)
    :CtaExecutionSession(b,h,e,std::vector<CtaExecutionStrategy>{{s,&f,nullptr}}){}
CtaExecutionSession::CtaExecutionSession(wtp::IBaseDataMgr& b,wtp::IHotMgr& h,StandardExecutionHost& e,std::vector<CtaExecutionStrategy> bindings)
    :impl_(new Impl(b,&h,e,std::move(bindings))){}
CtaExecutionSession::~CtaExecutionSession(){if(close(1000)!=0)impl_.release();}
bool CtaExecutionSession::initialize(wtp::WTSVariant* env,wtp::WTSVariant* data,wtp::WTSVariant* parsers,wtp::WTSVariant* params,const char* output){
    auto& x=*impl_;if(!x.on_owner()||x.busy||x.phase!=CtaExecutionPhase::New||x.requested.load())return false;
    if(x.strategies.size()!=1||(params&&params->type()!=Variant::VT_Object)){x.fail(CtaExecutionFault::Configuration);return false;}
    x.strategies.front().binding.parameters=params;
    return initialize(env,data,parsers,output);
}
bool CtaExecutionSession::initialize(wtp::WTSVariant* env,wtp::WTSVariant* data,wtp::WTSVariant* parsers,const char* output,CtaExecutionRecovery* recovery){
    auto& x=*impl_;if(!x.on_owner()||x.busy||x.phase!=CtaExecutionPhase::New||x.requested.load())return false;Busy guard(x.busy);
    try {
        if(!configuration_valid(env,data,parsers)||!x.base.getSession(env->get("product")->getCString("session"))
            ||!output||!*output||!x.execution.command()
            ||x.execution.status().phase!=ExecutionHostPhase::Ready||x.execution.status().stop_requested){x.fail(CtaExecutionFault::Configuration);return false;}
        std::filesystem::path directory(output);
        // 原WT目录getter缓存全进程路径；外层须在执行插件初始化前独占准备同一根。
        if(!directory.is_absolute()||!std::filesystem::is_directory(directory)
            ||!std::filesystem::equivalent(directory,std::filesystem::path(WtHelper::getBaseDir()))){x.fail(CtaExecutionFault::Configuration);return false;}
        // 同进程占用无法保护跨进程的检查/创建窗口；OS句柄覆盖整个原生输出生命周期。
        x.output_lease=CreateFileW((directory/".cta-session.lock").c_str(),GENERIC_READ|GENERIC_WRITE,0,
            nullptr,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);
        if(x.output_lease==INVALID_HANDLE_VALUE){
            const auto error=GetLastError();x.fail(error==ERROR_SHARING_VIOLATION||error==ERROR_LOCK_VIOLATION
                ?CtaExecutionFault::OutputBusy:CtaExecutionFault::Configuration);return false;
        }
        if((!recovery||!recovery->restore)&&(std::filesystem::exists(directory/"stradata")||std::filesystem::exists(directory/"userdata")
            ||std::filesystem::exists(directory/"portfolio")||std::filesystem::exists(directory/"outputs"))){x.fail(CtaExecutionFault::Configuration);return false;}
        if(recovery){
            if(!recovery->admit||!recovery->closed||!recovery->admit()){x.fail(CtaExecutionFault::Configuration);return false;}
            x.recovery=recovery;
            if(!recovery->restore&&recovery->prepare&&!recovery->prepare()){x.fail(CtaExecutionFault::Configuration);return false;}
        }
        x.engine.init(env,&x.base,&x.data,x.hot,nullptr);x.engine_initialized=true;x.engine.set_adapter_mgr(&x.engine_traders);x.engine.regEventListener(&x);
        x.data_attempted=true;if(!x.data.init(data,&x.engine,false,true)||!x.data.supports_stop()){x.fail(CtaExecutionFault::Initialize);return false;}
        std::uint32_t count=0;
        for(std::uint32_t i=0;i<parsers->size();++i){
            auto* cfg=parsers->get(i);
            if(!cfg||cfg->type()!=wtp::WTSVariant::VT_Object){x.fail(CtaExecutionFault::Configuration);return false;}
            if(!cfg->getBoolean("active"))continue;
            const auto id=cfg->getString("id");if(!name_valid(id)||x.parsers.getAdapter(id.c_str())){x.fail(CtaExecutionFault::Configuration);return false;}
            wtp::ParserAdapterPtr adapter=std::make_shared<ObservedParserAdapter>(x.parser_observation);
            // 先归原manager所有，即使init局部失败也保持SPI树至统一停止。
            if(!x.parsers.addAdapter(id.c_str(),adapter)||!adapter->init(id.c_str(),cfg,&x.engine,&x.base,x.hot,true)||!adapter->supports_stop()){x.fail(CtaExecutionFault::Initialize);return false;}++count;
        }
        if(!count){x.fail(CtaExecutionFault::Initialize);return false;}
        for(auto& value:x.strategies){
            auto& binding=value.binding;
            if(!binding.strategy->init(binding.parameters)){x.fail(CtaExecutionFault::Initialize);return false;}
        }
        // 工厂策略可在init中改写_id；全部init返回后核冻结身份，避免共享原JSON文件。
        for(auto& value:x.strategies){
            const char* current=value.binding.strategy->id();
            if(!current||value.id!=current){x.fail(CtaExecutionFault::Initialize);return false;}
        }
        for(auto& value:x.strategies){
            auto& binding=value.binding;
            auto context=std::make_shared<CtaStraContext>(&x.engine,value.id.c_str(),0);
            context->set_strategy(binding.strategy);x.engine.addContext(context);
        }
        x.engine.addExecuter(x.execution.command());x.phase=CtaExecutionPhase::Configured;return true;
    }catch(...){x.fail(CtaExecutionFault::Initialize);return false;}
}
bool CtaExecutionSession::start(){
    auto& x=*impl_;if(!x.on_owner()||x.busy||x.phase!=CtaExecutionPhase::Configured||x.requested.load())return false;Busy guard(x.busy);
    try{x.engine.run();if(x.requested.load()||!x.parsers.run(true)){x.fail(CtaExecutionFault::Start);return false;}x.phase=CtaExecutionPhase::Running;return true;}
    catch(...){x.fail(CtaExecutionFault::Start);return false;}
}
int CtaExecutionSession::pump(std::uint32_t events,std::uint32_t commands){
    auto& x=*impl_;if(!x.on_owner())return StandardQmtWrongOwner;if(x.busy)return StandardQmtReentrant;
    if(x.phase!=CtaExecutionPhase::Running||x.requested.load())return StandardQmtUnavailable;Busy guard(x.busy);
    // 与原Runner相同，观察原后台任务失败；关闭新交易准入，失败任务保持原不重放语义。
    if(x.engine.task_failure()){x.fail(CtaExecutionFault::NativeTask);return StandardQmtFailure;}
    const auto result=x.execution.pump(events,commands);
    const auto execution=x.execution.status();
    // 原宿主可能处理完事件后锁存故障并返回非负计数；故障状态同样终止策略准入。
    if(result<0||execution.fault!=ExecutionHostFault::None||execution.stop_requested
        ||execution.phase==ExecutionHostPhase::Degraded||execution.phase==ExecutionHostPhase::Stopping
        ||execution.phase==ExecutionHostPhase::Closed){x.fail(CtaExecutionFault::Execution);return StandardQmtFailure;}
    return result;
}
CtaExecutionStatus CtaExecutionSession::status()const {
    auto& x=*impl_;if(!x.on_owner())throw std::runtime_error("cta_session_wrong_owner");
    const auto& p=*x.parser_observation;
    return {x.phase,x.fault,x.requested.load(),x.initializes.load(),x.schedules.load(),x.sessions.load(),
        p.quotes.load(),p.connects.load(),p.closes.load(),p.logs.load()};
}
void CtaExecutionSession::request_stop()noexcept{impl_->requested.store(true);impl_->execution.request_stop();}
int CtaExecutionSession::quiesce(std::uint32_t timeout)noexcept{
    auto& x=*impl_;if(!x.on_owner())return StandardQmtWrongOwner;
    if(x.busy)return StandardQmtReentrant;if(!timeout||timeout>30000||x.phase==CtaExecutionPhase::Closed)return StandardQmtInvalid;
    x.requested.store(true);if(auto bridge=x.execution.command())bridge->close();
    Busy guard(x.busy);x.phase=CtaExecutionPhase::Stopping;
    try{return x.stop_producers(timeout)?0:1;}catch(...){x.fail(CtaExecutionFault::Close);return StandardQmtFailure;}
}
int CtaExecutionSession::close(std::uint32_t timeout)noexcept{
    auto& x=*impl_;if(!x.on_owner())return StandardQmtWrongOwner;request_stop();if(x.phase==CtaExecutionPhase::Closed)return 0;
    if(x.busy)return 1;if(!timeout||timeout>30000)return StandardQmtInvalid;Busy guard(x.busy);x.phase=CtaExecutionPhase::Stopping;
    try {
        if(!x.stop_producers(timeout))return 1;
        for(auto& value:x.strategies){
            if(!value.binding.strategy)continue;
            if(value.delete_attempted)return 1;value.delete_attempted=true;
            try {
                if(!value.binding.factory->deleteStrategy(value.binding.strategy)){x.fail(CtaExecutionFault::StrategyDelete);return 1;}
            }catch(...){x.fail(CtaExecutionFault::StrategyDelete);return StandardQmtFailure;}
            value.binding.strategy=nullptr;
        }
        const auto closed=x.execution.close();if(closed!=0)return closed;
        // 执行消费者关闭后才释放其借用的原行情/上下文依赖，根租约继续持有至最终证明。
        if(x.engine_initialized)x.engine.release_contexts();x.parsers.release();if(x.data_attempted)x.data.release();
        if(x.recovery&&x.fault==CtaExecutionFault::None){
            try{if(!x.recovery->closed())x.fault=CtaExecutionFault::Close;}
            catch(...){x.fault=CtaExecutionFault::Close;}
            x.recovery=nullptr;
        }
        if(x.output_lease!=INVALID_HANDLE_VALUE){
            if(!CloseHandle(x.output_lease)){x.fail(CtaExecutionFault::Close);return StandardQmtFailure;}
            x.output_lease=INVALID_HANDLE_VALUE;
        }
        x.phase=CtaExecutionPhase::Closed;session_claimed.store(false);return 0;
    }catch(...){x.fail(CtaExecutionFault::Close);return StandardQmtFailure;}
}
}
