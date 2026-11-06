// 显式配置的受管CTA产品入口；金融状态及执行算法由原WT拥有。
#include "CtaProcess.h"
#include "CtaExecutionSession.h"
#include "NativeRuntimeLog.h"
#include <algorithm>
#include <atomic>
#include "StandardExecutionHost.h"
#include "ExecutionEnvironment.h"
#include "WtCore/WtExecuterFactory.h"
#include "WtCore/ActionPolicyMgr.h"
#include "WtCore/WtHelper.h"
#include "WTSTools/WTSBaseDataMgr.h"
#include "WTSTools/WTSHotMgr.h"
#include "WTSUtils/WTSCfgLoader.h"
#include "Includes/CtaStrategyDefs.h"
#include "Includes/WTSVariant.hpp"
#include "Includes/WTSTradeDef.hpp"
#include "Includes/WTSContractInfo.hpp"
#include "GuanhengRealtime/ManagedStrategyBridge.h"
#include "Share/CodeHelper.hpp"
#include <rapidjson/document.h>
#include <rapidjson/reader.h>
#include <rapidjson/memorystream.h>
#include <rapidjson/stringbuffer.h>
#include <rapidjson/writer.h>
#include <Windows.h>
#include <bcrypt.h>
#include <chrono>
#include <cctype>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <memory>
#include <map>
#include <set>
#include <string>
#include <vector>

namespace fs=std::filesystem;namespace rj=rapidjson;
using Clock=std::chrono::steady_clock;
namespace {
void need(bool value){if(!value)throw std::runtime_error("execution_host_configuration");}
struct PublishedBroker {
    GhCtaBrokerFacts facts{};
    std::vector<GhCtaBrokerPosition> positions;
    GhCtaBrokerTradeFacts trade_facts{};
    std::vector<GhCtaBrokerTrade> trades;
    GhCtaBrokerTradeFactsV2 trade_facts_v2{};
    std::vector<GhCtaBrokerTradeV2> trades_v2;
    std::vector<GhCtaPendingOrder> pending_orders; // 原订单表复制；不形成另一份可变订单状态。
    std::uint32_t completed_queries=0;
};
std::shared_ptr<const PublishedBroker> broker_current;
struct BrokerPublicationLifetime {
    ~BrokerPublicationLifetime(){std::atomic_store(&broker_current,std::shared_ptr<const PublishedBroker>{});}
};
void publish_broker(guanheng::StandardExecutionHost& execution,guanheng::ExecutionEnvironment& environment){
    // owner复制原表；策略只复制本值对象，接收时点保持原查询事实。
    const auto status=execution.status();
    if(!status.account_ready||status.fault!=guanheng::ExecutionHostFault::None){std::atomic_store(&broker_current,std::shared_ptr<const PublishedBroker>{});return;}
    const auto prior=std::atomic_load(&broker_current);
    std::vector<GhCtaPendingOrder> pending_orders;
    auto* orders=execution.orders("");need(orders!=nullptr);
    struct OrdersCopyOwner{wtp::OrderMap* value;~OrdersCopyOwner(){value->release();}} owned{orders};
    need(orders->size()<=4096);
    for(auto it=orders->begin();it!=orders->end();++it){
        const auto* order=static_cast<wtp::WTSOrderInfo*>(it->second);
        if(!order->isAlive()||order->getVolLeft()==0)continue;
        need(order->getContractInfo()!=nullptr);
        const auto code=std::string(order->getExchg())+"."+order->getContractInfo()->getProduct()+"."+order->getCode();
        need(it->first&&order->getEntrustID()[0]&&order->getUserTag()[0]&&code.size()<64);
        GhCtaPendingOrder row{};std::memcpy(row.symbol,code.c_str(),code.size()+1);
        row.remaining=order->getVolLeft();
        row.is_buy=(order->getDirection()==wtp::WDT_LONG)==(order->getOffsetType()==wtp::WOT_OPEN);
        need(std::isfinite(row.remaining)&&row.remaining>0);pending_orders.push_back(row);
    }
    // 原订单回报可独立于P/D查询改变余量；值相同才复用旧发布，不另造revision或订单表。
    const bool same_pending=prior&&prior->pending_orders.size()==pending_orders.size()
        &&std::equal(pending_orders.begin(),pending_orders.end(),prior->pending_orders.begin(),
            [](const auto& a,const auto& b){return std::strcmp(a.symbol,b.symbol)==0
                &&a.remaining==b.remaining&&a.is_buy==b.is_buy;});
    if(prior&&same_pending&&prior->completed_queries==status.plugin.queries
        &&prior->trade_facts.revision==status.broker_trade_revision)return;
    const auto trades=execution.broker_trades();
    auto source=execution.broker_observation();auto value=std::make_shared<PublishedBroker>();auto& facts=value->facts;
    value->completed_queries=status.plugin.queries;
    facts.size=sizeof(facts);facts.version=1;facts.positions_known=source.positions_known;facts.account_known=source.account_known;
    facts.position_revision=source.position_revision;facts.position_received_ms=source.position_received_ms;
    facts.account_revision=source.account_revision;facts.account_received_ms=source.account_received_ms;
    facts.published_epoch_ms=environment.observe().epoch_ms;facts.balance=source.account[1];facts.available=source.account[3];
    need(source.positions.size()<=4096);
    for(const auto& p:source.positions){
        if(p.quantity==0)continue;
        need(!p.code.empty()&&p.code.size()<64&&std::isfinite(p.quantity)&&std::isfinite(p.sellable));
        GhCtaBrokerPosition row{};std::memcpy(row.symbol,p.code.c_str(),p.code.size()+1);
        row.quantity=p.quantity;row.sellable=p.sellable;row.is_long=p.is_long;value->positions.push_back(row);
    }
    std::sort(value->positions.begin(),value->positions.end(),[](const auto& a,const auto& b){
        const auto code=std::strcmp(a.symbol,b.symbol);return code<0||(code==0&&a.is_long<b.is_long);
    });
    auto& tf=value->trade_facts;tf.size=sizeof(tf);tf.version=1;tf.known=trades.known;tf.error=trades.error;
    tf.revision=trades.revision;tf.received_ms=trades.received_ms;tf.query_revision=trades.query_revision;
    tf.query_received_ms=trades.query_received_ms;tf.live_revision=trades.live_revision;tf.published_epoch_ms=facts.published_epoch_ms;
    auto& tf2=value->trade_facts_v2;tf2.facts=tf;tf2.facts.size=sizeof(tf2);tf2.facts.version=2;
    tf2.submission_revision=trades.submission_revision;tf2.origins_known=trades.origins_known;
    need(trades.trades.size()<=4096);
    for(const auto& trade:trades.trades){
        GhCtaBrokerTrade row{};
        auto copy=[](char* out,const std::string& input){need(input.size()<64);std::memcpy(out,input.c_str(),input.size()+1);};
        copy(row.symbol,trade.symbol);copy(row.trade_id,trade.trade_id);copy(row.order_id,trade.order_id);copy(row.user_tag,trade.user_tag);
        row.trade_date=trade.trade_date;row.is_buy=trade.is_buy;row.trade_time=trade.trade_time;
        row.first_live_revision=trade.first_live_revision;row.received_ms=trade.received_ms;
        row.quantity=trade.quantity;row.price=trade.price;row.amount=trade.amount;value->trades.push_back(row);
        value->trades_v2.push_back({row,trades.origins_known?trade.submission_revision:0});
    }
    value->pending_orders=std::move(pending_orders);
    std::atomic_store(&broker_current,std::shared_ptr<const PublishedBroker>(std::move(value)));
}
struct Handle {HANDLE value=INVALID_HANDLE_VALUE;~Handle(){if(value&&value!=INVALID_HANDLE_VALUE)CloseHandle(value);}};
struct ReadError:std::runtime_error {DWORD code;explicit ReadError(DWORD value):std::runtime_error("execution_file_read"),code(value){}};
std::string read(const fs::path& path,std::size_t maximum){
    // 直接保留Win32共享冲突码；CRT ifstream会将32/33压成普通访问失败。
    Handle file;file.value=CreateFileW(path.c_str(),GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_DELETE,nullptr,
        OPEN_EXISTING,FILE_FLAG_OPEN_REPARSE_POINT,nullptr);
    if(file.value==INVALID_HANDLE_VALUE)throw ReadError(GetLastError());
    BY_HANDLE_FILE_INFORMATION before{},after{};need(GetFileInformationByHandle(file.value,&before));
    const auto size=(static_cast<std::uint64_t>(before.nFileSizeHigh)<<32)|before.nFileSizeLow;
    need(!(before.dwFileAttributes&(FILE_ATTRIBUTE_DIRECTORY|FILE_ATTRIBUTE_REPARSE_POINT))&&before.nNumberOfLinks==1&&size>0&&size<=maximum);
    std::string body(static_cast<std::size_t>(size),'\0');DWORD received=0;
    if(!ReadFile(file.value,body.data(),static_cast<DWORD>(body.size()),&received,nullptr))throw ReadError(GetLastError());
    need(received==body.size()&&GetFileInformationByHandle(file.value,&after)
        &&before.dwVolumeSerialNumber==after.dwVolumeSerialNumber&&before.nFileIndexHigh==after.nFileIndexHigh
        &&before.nFileIndexLow==after.nFileIndexLow&&before.nFileSizeHigh==after.nFileSizeHigh&&before.nFileSizeLow==after.nFileSizeLow
        &&CompareFileTime(&before.ftLastWriteTime,&after.ftLastWriteTime)==0);return body;
}
std::string sha(const std::string& bytes){
    BCRYPT_ALG_HANDLE algorithm=nullptr;BCRYPT_HASH_HANDLE hash=nullptr;unsigned char digest[32];
    need(BCryptOpenAlgorithmProvider(&algorithm,BCRYPT_SHA256_ALGORITHM,nullptr,0)==0);
    const auto made=BCryptCreateHash(algorithm,&hash,nullptr,0,nullptr,0,0);
    const auto added=made==0?BCryptHashData(hash,reinterpret_cast<PUCHAR>(const_cast<char*>(bytes.data())),static_cast<ULONG>(bytes.size()),0):made;
    const auto done=added==0?BCryptFinishHash(hash,digest,32,0):added;
    if(hash)BCryptDestroyHash(hash);BCryptCloseAlgorithmProvider(algorithm,0);need(done==0);
    static const char digits[]="0123456789abcdef";std::string result;
    for(auto byte:digest){result+=digits[byte>>4];result+=digits[byte&15];}return result;
}
struct Guard:rj::BaseReaderHandler<rj::UTF8<>,Guard>{
    std::vector<std::set<std::string>> levels; // 当前嵌套层各对象的键集合，沿原16层深度及重复键检查。
    std::size_t nodes=0; // 本次SAX已读取的标量/容器节点数，不计对象键名。
    const std::size_t maximum_nodes; // 调用方明确选择的有限节点预算，普通配置默认32768。
    explicit Guard(std::size_t maximum=32768):maximum_nodes(maximum){}
    bool scalar(){return ++nodes<=maximum_nodes;}
    bool Null(){return scalar();}bool Bool(bool){return scalar();}bool Int(int){return scalar();}
    bool Uint(unsigned){return scalar();}bool Int64(std::int64_t){return scalar();}bool Uint64(std::uint64_t){return scalar();}
    bool Double(double v){return std::isfinite(v)&&scalar();}bool String(const char*,rj::SizeType,bool){return scalar();}
    bool Key(const char* v,rj::SizeType n,bool){return !levels.empty()&&levels.back().emplace(v,n).second;}
    bool StartObject(){levels.emplace_back();return levels.size()<=16&&scalar();}
    bool StartArray(){return StartObject();}bool EndObject(rj::SizeType){levels.pop_back();return true;}
    bool EndArray(rj::SizeType n){return EndObject(n);}
};
rj::Document parse(const std::string& body,std::size_t maximum_nodes=32768){
    need(maximum_nodes>0&&maximum_nodes<=16*1024*1024);
    need(body.find('\0')==std::string::npos);rj::MemoryStream input(body.data(),body.size());rj::Reader reader;Guard guard(maximum_nodes);
    need(reader.Parse<rj::kParseValidateEncodingFlag>(input,guard));rj::Document value;
    value.Parse<rj::kParseValidateEncodingFlag>(body.data(),body.size());need(!value.HasParseError()&&value.IsObject());return value;
}
const rj::Value& member(const rj::Value& value,const char* name){need(value.IsObject()&&value.HasMember(name));return value[name];}
std::string text(const rj::Value& value,const char* name,std::size_t maximum=1024){
    const auto& field=member(value,name);need(field.IsString()&&field.GetStringLength()>0&&field.GetStringLength()<=maximum);
    std::string result(field.GetString(),field.GetStringLength());for(unsigned char c:result)need(c>=32&&c!=127);return result;
}
unsigned number(const rj::Value& value,const char* name,unsigned minimum,unsigned maximum){
    const auto& field=member(value,name);need(field.IsUint()&&field.GetUint()>=minimum&&field.GetUint()<=maximum);return field.GetUint();
}
void keys(const rj::Value& value,std::initializer_list<const char*> names){
    need(value.IsObject());for(auto it=value.MemberBegin();it!=value.MemberEnd();++it){
        bool found=false;for(auto name:names)if(it->name==name)found=true;need(found);
    }
}
std::string encode(const rj::Value& value){
    rj::StringBuffer buffer;rj::Writer<rj::StringBuffer,rj::UTF8<>,rj::ASCII<>> writer(buffer);
    need(value.Accept(writer));return {buffer.GetString(),buffer.GetSize()};
}
struct Release {void operator()(wtp::WTSVariant* value)const{if(value)value->release();}};
using Variant=std::unique_ptr<wtp::WTSVariant,Release>;
Variant load_variant(const rj::Value& value){need(value.IsObject());Variant result(WTSCfgLoader::load_from_content(encode(value)));need(result!=nullptr);return result;}
fs::path absolute(const std::string& value){auto path=fs::u8path(value);need(path.is_absolute());
    for(const auto& item:path)need(item!="..");return path.lexically_normal();}
fs::path installed(const fs::path& root,const std::string& value){
    fs::path path=fs::u8path(value);need(!path.empty()&&!path.is_absolute()&&!path.has_root_name());for(const auto& item:path)need(item!=".."&&item!=".");
    auto result=root/path;need(fs::is_regular_file(result));return result;
}
void publish(const fs::path& target,const rj::Value& value,bool replace=false){
    const auto temporary=fs::path(target.wstring()+L".pending");const auto bytes=encode(value);
    Handle file;file.value=CreateFileW(temporary.c_str(),GENERIC_WRITE,0,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);
    need(file.value!=INVALID_HANDLE_VALUE);DWORD written=0;need(WriteFile(file.value,bytes.data(),static_cast<DWORD>(bytes.size()),&written,nullptr)&&written==bytes.size());
    need(FlushFileBuffers(file.value));need(CloseHandle(file.value));file.value=INVALID_HANDLE_VALUE;
    need(MoveFileExW(temporary.c_str(),target.c_str(),MOVEFILE_WRITE_THROUGH|(replace?MOVEFILE_REPLACE_EXISTING:0))!=0);
}
rj::Document receipt(const char* schema,const std::string& id,const std::string& config_sha,bool closed){
    rj::Document value(rj::kObjectType);auto& a=value.GetAllocator();
    value.AddMember("schema",rj::Value(schema,a),a);value.AddMember("control_id",rj::Value(id.c_str(),a),a);
    value.AddMember("config_sha256",rj::Value(config_sha.c_str(),a),a);value.AddMember("pid",static_cast<unsigned>(GetCurrentProcessId()),a);
    value.AddMember("closed",closed,a);return value;
}
// 生命周期时间由本原生执行器的创建/关闭线程记录；只用于只读运行展示。
// 保留原ready/closed协议及金融恢复身份，观测回执失败不改变执行结果。
void publish_lifecycle(const fs::path& control,const char* name,const char* schema,
                       const std::string& id,const std::string& config_sha,bool closed) noexcept {
    try {
        SYSTEMTIME utc{};GetSystemTime(&utc);char stamp[32]{};
        std::snprintf(stamp,sizeof(stamp),"%04u-%02u-%02uT%02u:%02u:%02u.%03uZ",
            static_cast<unsigned>(utc.wYear),static_cast<unsigned>(utc.wMonth),static_cast<unsigned>(utc.wDay),
            static_cast<unsigned>(utc.wHour),static_cast<unsigned>(utc.wMinute),
            static_cast<unsigned>(utc.wSecond),static_cast<unsigned>(utc.wMilliseconds));
        auto value=receipt(schema,id,config_sha,closed);auto& a=value.GetAllocator();
        // 事件实际发生的UTC时间，毫秒精度；与文件时间和资金基准分别解释。
        value.AddMember("event_at",rj::Value(stamp,a),a);
        publish(control/name,value);
    } catch(...) { std::fprintf(stderr,"CTA lifecycle observation unavailable\n"); }
}
struct Library {
    HMODULE module=nullptr; // 进程级工厂及插件保留至OS回收，与原工厂装载期保持一致。
    explicit Library(const fs::path& path){module=LoadLibraryExW(path.c_str(),nullptr,LOAD_WITH_ALTERED_SEARCH_PATH);need(module!=nullptr);}
    template<class T>T get(const char* name){auto fn=reinterpret_cast<T>(GetProcAddress(module,name));need(fn!=nullptr);return fn;}
};
struct StrategyFactory {std::unique_ptr<Library> library;ICtaStrategyFact* value=nullptr;};
double monotonic(){LARGE_INTEGER count,frequency;need(QueryPerformanceCounter(&count)&&QueryPerformanceFrequency(&frequency));return double(count.QuadPart)/frequency.QuadPart;}
void physical(const fs::path& path){
    const auto attributes=GetFileAttributesW(path.c_str());
    need(attributes!=INVALID_FILE_ATTRIBUTES&&!(attributes&FILE_ATTRIBUTE_REPARSE_POINT));
}
std::string installation_identity(const fs::path& root){
    const auto installation=root.parent_path();
    const auto manifest=parse(read(installation/"execution-install.json",256*1024));
    need(text(manifest,"schema")=="guanheng.execution-install.v1");const auto& files=member(manifest,"files");
    need(files.IsObject()&&files.MemberCount()>0&&files.MemberCount()<=512);
    std::set<fs::path> libraries;
    for(auto it=files.MemberBegin();it!=files.MemberEnd();++it){
        need(it->value.IsString()&&it->value.GetStringLength()==64);
        const auto path=installed(installation,{it->name.GetString(),it->name.GetStringLength()});
        for(auto parent=path;parent!=installation;parent=parent.parent_path())physical(parent);
        need(sha(read(path,64*1024*1024))==it->value.GetString());
        auto extension=path.extension().string();for(auto& c:extension)c=static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
        if(extension==".dll"||extension==".exe")libraries.insert(path.lexically_normal());
    }
    unsigned count=0;for(const auto& item:fs::recursive_directory_iterator(root)){
        need(++count<=4096);physical(item.path());
        if(item.is_regular_file()){
            auto extension=item.path().extension().string();for(auto& c:extension)c=static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
            if(extension==".dll"||extension==".exe")need(libraries.erase(item.path().lexically_normal())==1);
        }
    }
    need(libraries.empty());return sha(encode(files));
}
rj::Document state_identity(const fs::path& output,const rj::Value& strategies){
    rj::Document result(rj::kObjectType);auto& a=result.GetAllocator();std::map<std::string,std::string> files;
    for(const auto* directory:{"stradata","userdata","portfolio"}){
        const auto path=output/directory;if(!fs::exists(path))continue;physical(path);need(fs::is_directory(path));
        unsigned count=0;for(const auto& item:fs::directory_iterator(path)){
            need(++count<=512);physical(item.path());need(item.is_regular_file());
            auto extension=item.path().extension().string();for(auto& c:extension)c=static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
            if(extension==".json")files.emplace(item.path().lexically_relative(output).generic_string(),sha(read(item.path(),4*1024*1024)));
        }
    }
    need(files.count("portfolio/datas.json"));
    for(const auto& strategy:strategies.GetArray())need(files.count("stradata/"+text(strategy,"id",63)+".json"));
    for(const auto& item:files)result.AddMember(rj::Value(item.first.c_str(),a),rj::Value(item.second.c_str(),a),a);
    return result;
}
bool known_orders_recoverable(guanheng::StandardExecutionHost& execution,const guanheng::StandardQmtRecoveryV1& value){
    std::uint32_t working=0;
    return execution.known_working_children(working)==0&&value.query_first&&!value.open_group
        &&value.unresolved_children==working&&!value.pending_commands&&!value.unsafe;
}
bool settled(guanheng::StandardExecutionHost& execution,const guanheng::StandardQmtRecoveryV1& value){
    return value.submissions_closed&&known_orders_recoverable(execution,value);
}
// 自有持续Reader的缓存为派生位置；严格验证对象后，只从比较投影移除此定位。
void normalize_publication_cache(rj::Value& value){
    if(!value.HasMember("data")||!value["data"].IsObject())return;
    auto& data=value["data"];if(!data.HasMember("store")||!data["store"].IsObject())return;
    auto& store=data["store"];
    if(!store.HasMember("module")||!store["module"].IsString()
        ||std::string(store["module"].GetString(),store["module"].GetStringLength())!="GuanhengRealtimeReader")return;
    if(!store.HasMember("daily")||!store["daily"].IsObject())return;
    auto& daily=store["daily"];if(!daily.HasMember("publication"))return;
    auto& publication=daily["publication"];keys(publication,{"status_file","publication_file","cache_root","source_root"});
    for(const char* field:{"status_file","publication_file","cache_root"})absolute(text(publication,field));
    if(publication.HasMember("source_root"))absolute(text(publication,"source_root"));
    publication.RemoveMember("cache_root");
}
// 已批准的执行器目标修正属于发行行为选择；比较副本移除该开关，原配置及其SHA保持。
// 只允许原股票执行单元使用严格布尔值；其他政策、数量与金融身份仍逐项比较。
void normalize_target_replacement(rj::Value& value){
    if(!value.HasMember("executer")||!value["executer"].IsObject())return;
    auto& executer=value["executer"];
    if(!executer.HasMember("policy")||!executer["policy"].IsObject())return;
    for(auto& entry:executer["policy"].GetObject()){
        auto& rule=entry.value;
        if(!rule.IsObject()||!rule.HasMember("replace_equal_position_target"))continue;
        need(rule["replace_equal_position_target"].IsBool());
        const auto name=text(rule,"name");
        need(name=="WtExeFact.WtStockMinImpactExeUnit"||name=="WtExeFact.WtStockMinImpactBorrowedExeUnit");
        rule.RemoveMember("replace_equal_position_target");
    }
}
// 比较投影只归一化已核运行接线及已批准目标修正；来源及金融身份保持严格。
bool same_business(const rj::Value& left,const rj::Value& right){
    rj::Document before,after;before.CopyFrom(left,before.GetAllocator());after.CopyFrom(right,after.GetAllocator());
    for(auto* value:{&before,&after}){
        const auto& budget=member(*value,"budget");need(budget.IsObject());
        const auto duration=number(budget,"run_ms",0,86400000);need(duration==0||duration>=1000);
        (*value)["budget"].RemoveMember("run_ms");
        normalize_publication_cache(*value);
        normalize_target_replacement(*value);
        if(value->HasMember("executer")&&(*value)["executer"].IsObject()){
            auto& executer=(*value)["executer"];
            if(executer.HasMember("policy")&&executer["policy"].IsObject())
                for(auto it=executer["policy"].MemberBegin();it!=executer["policy"].MemberEnd();++it){
                    auto& rule=it->value;if(!rule.IsObject()||!rule.HasMember("name")||!rule["name"].IsString())continue;
                    const std::string name=rule["name"].GetString();
                    if(name!="WtExeFact.WtStockMinImpactExeUnit"&&name!="WtExeFact.WtStockMinImpactBorrowedExeUnit")continue;
                    // 显式发行中的原生撤单参数；只移除比较副本，原件完整SHA继续校验。
                    if(rule.HasMember("expire")){need(rule["expire"].IsUint());rule.RemoveMember("expire");}
                    if(rule.HasMember("is_cancel_unmanaged_order")){
                        need(rule["is_cancel_unmanaged_order"].IsBool());rule.RemoveMember("is_cancel_unmanaged_order");
                    }
                }
        }
        if(!value->HasMember("strategies")||!(*value)["strategies"].IsArray())continue;
        for(auto& strategy:(*value)["strategies"].GetArray()){
            if(!strategy.IsObject()||!strategy.HasMember("parameters")||!strategy["parameters"].IsObject())continue;
            auto& parameters=strategy["parameters"];
            if(!parameters.HasMember("python_strategy")||!parameters["python_strategy"].IsObject())continue;
            auto& python=parameters["python_strategy"];if(!python.HasMember("capital_account"))continue;
            auto& account=python["capital_account"];keys(account,{"path","config_sha256","account","environment"});
            need(account.MemberCount()==4);absolute(text(account,"path"));
            const auto config_sha=text(account,"config_sha256",64);need(config_sha.size()==64);
            for(char digit:config_sha)need((digit>='0'&&digit<='9')||(digit>='a'&&digit<='f'));
            text(account,"account",63);const auto environment=text(account,"environment",10);
            need(environment=="simulation"||environment=="live");
            // 只改深拷贝投影，发布程序升级不改金融身份；存在性、账户及环境仍逐项比较。
            account.RemoveMember("path");account.RemoveMember("config_sha256");
        }
    }
    return before==after;
}
// 单一角色换代：只回投已钉住的原业务配置；实际新基金数据仍由本代正式输入读取。
rj::Document role_model(const rj::Value& config){
    rj::Document current;current.CopyFrom(config,current.GetAllocator());
    if(!current.HasMember("role_replacement"))return current;
    const auto& marker=member(config,"role_replacement");keys(marker,{"schema","file","sha256"});
    need(text(marker,"schema")=="guanheng.zero-position-role-replacement.v1");
    const auto file=absolute(text(marker,"file"));need(file.filename()=="execution.json");
    const auto body=read(file,256*1024);need(sha(body)==text(marker,"sha256",64));auto original=parse(body);
    need(!original.HasMember("role_replacement"));
    auto parameters=[](rj::Value& value)->rj::Value&{
        auto& rows=value["strategies"];need(rows.IsArray()&&rows.Size()==1&&text(rows[0],"id")=="resonance-regime-v1");
        return rows[0]["parameters"]["python_strategy"];
    };
    auto& selected=parameters(current);auto& previous=parameters(original);
    auto input=[&](const rj::Value& p){const auto raw=read(absolute(text(p,"input_file")),16*1024*1024);
        need(sha(raw)==text(p,"input_sha256",64));
        // 原完整RuntimeInput可含数万raw/analysis行；每JSON节点至少占一字节，正文长度给出严格有限上界。
        // 文件仍沿原16MiB边界读取；普通配置/收据继续使用默认32768节点、16层及原重复键检查。
        return parse(raw,raw.size());};
    auto before=input(previous),after=input(selected);
    // 原资金、现金锚点、费用及七证券库存逐项保持；原基准和新角色均必须明确为零仓位。
    for(const char* field:{"capital_baseline","cash_anchor","policy","fee_reserve_cny","fee_source","schema"})
        need(member(before,field)==member(after,field));
    auto& old_request=before["request"];auto& new_request=after["request"];
    auto& old_config=old_request["configuration"];auto& new_config=new_request["configuration"];
    need(text(old_config,"config_revision")!=text(new_config,"config_revision"));
    for(const char* field:{"kc_composite_signal_symbol","kc_composite_execution_symbol"}){
        need(text(old_config,field)=="589680.SH"&&text(new_config,field)=="588030.SH");
        new_config[field].CopyFrom(old_config[field],after.GetAllocator());
    }
    new_config["config_revision"].CopyFrom(old_config["config_revision"],after.GetAllocator());need(new_config==old_config);
    auto& old_cycles=old_request["cycles"];auto& new_cycles=new_request["cycles"];
    need(old_cycles.IsArray()&&new_cycles.IsArray()&&old_cycles.Size()==8&&new_cycles.Size()==8);
    std::set<std::string> checked;
    for(const auto& row:old_cycles.GetArray()){
        const auto symbol=text(row,"symbol");need(checked.insert(symbol).second);const bool role=symbol=="589680.SH";
        const rj::Value* found=nullptr;
        for(const auto& other:new_cycles.GetArray())if(text(other,"symbol")== (role?"588030.SH":symbol)){
            need(found==nullptr);found=&other;
        }
        need(found!=nullptr);
        if(role)need(text(row,"status")=="flat"&&text(*found,"status")=="flat"
            &&number(row,"quantity",0,0)==0&&number(*found,"quantity",0,0)==0);
        else need(row==*found);
    }
    need(checked.count("589680.SH")==1&&old_request["previous_exits"]==new_request["previous_exits"]);
    for(const char* key:{"input_file","input_sha256"})selected[key].CopyFrom(previous[key],current.GetAllocator());
    for(const char* key:{"base_url","token_env"})selected["capital_market"][key].CopyFrom(previous["capital_market"][key],current.GetAllocator());
    selected["market_window"]["path"].CopyFrom(previous["market_window"]["path"],current.GetAllocator());
    auto& store=current["data"]["store"];auto& old_store=original["data"]["store"];
    need(store["symbols"].IsArray()&&store["symbols"].Size()==8);std::set<std::string> symbols;
    for(const auto& row:store["symbols"].GetArray()){
        const auto symbol=text(row,"symbol");need(symbols.insert(symbol).second);
        const auto expected=symbol=="588030.SH"?"589680.SH":symbol;const rj::Value* found=nullptr;
        for(const auto& other:old_store["symbols"].GetArray())if(text(other,"symbol")==expected)found=&other;
        need(found!=nullptr);
        if(symbol=="588030.SH")need(row.MemberCount()==2&&text(row,"std_code")=="SSE.ETF.588030");
        else need(row==*found);
    }
    need(symbols.count("588030.SH")==1&&symbols.count("589680.SH")==0);
    store["symbols"].CopyFrom(old_store["symbols"],current.GetAllocator());
    for(const char* key:{"path","adjfactor","publication"}){
        need(store["daily"].HasMember(key)==old_store["daily"].HasMember(key));
        if(store["daily"].HasMember(key))store["daily"][key].CopyFrom(old_store["daily"][key],current.GetAllocator());
    }
    for(const char* key:{"base_url","binding_id","binding_sha256","instance_id","key_id_env","hmac_secret_env"}){
        need(current["trader"].HasMember(key)==original["trader"].HasMember(key));
        if(current["trader"].HasMember(key))current["trader"][key].CopyFrom(original["trader"][key],current.GetAllocator());
    }
    // WT原证券ignore过滤器在恢复目标前读取，不删原理论账、不生成虚假平仓。
    need(member(original["environment"],"filters").IsString()&&original["environment"]["filters"].GetStringLength()==0);
    const auto filter_file=installed(absolute(text(config,"installation_root")),text(current["environment"],"filters",1024));
    auto filters=parse(read(filter_file,4096));auto expected_filter=parse("{\"code_filters\":{\"SSE.ETF.589680\":{\"action\":\"ignore\"}}}");need(filters==expected_filter);
    current["environment"]["filters"].CopyFrom(original["environment"]["filters"],current.GetAllocator());
    current.RemoveMember("role_replacement");current.RemoveMember("recovery");original.RemoveMember("recovery");
    need(same_business(current,original));return original;
}

// 自有恢复准入归一化显式开关与运输引用；原账户、模型、账根继续逐项核验。
rj::Document permission_model(const rj::Value& config,unsigned depth=0){
    rj::Document current=role_model(config);current.RemoveMember("recovery");
    if(!current.HasMember("execution_permission_origin"))return current;
    need(depth<16);const auto& marker=member(config,"execution_permission_origin");keys(marker,{"schema","file","sha256"});
    need(text(marker,"schema")=="guanheng.execution-permission-origin.v1");
    const auto path=absolute(text(marker,"file"));need(path.filename()=="execution.json");
    const auto raw=read(path,256*1024);need(sha(raw)==text(marker,"sha256",64));auto original=parse(raw);
    rj::Document before;before.CopyFrom(original,before.GetAllocator());before.RemoveMember("recovery");
    before.RemoveMember("execution_permission_origin");current.RemoveMember("execution_permission_origin");
    need(member(before,"trader").IsObject()&&member(current,"trader").IsObject());
    const auto& old=before["trader"];auto& selected=current["trader"];
    const auto& enabled=member(selected,"writes_enabled");const auto& prior=member(old,"writes_enabled");
    need(enabled.IsBool()&&prior.IsBool()&&enabled.GetBool()!=prior.GetBool());
    for(const char* key:{"writes_enabled","base_url","binding_id","binding_sha256","instance_id","key_id_env","hmac_secret_env"}){
        need(selected.HasMember(key)==old.HasMember(key));
        if(old.HasMember(key))selected[key].CopyFrom(old[key],current.GetAllocator());
    }
    need(same_business(current,before));return permission_model(original,depth+1);
}

// 显式只读市场引用回投原业务模型；原金融、账户及执行字段继续逐项核验。
rj::Document market_model(const rj::Value& config){
    rj::Document normalized=permission_model(config);
    rj::Document current;current.CopyFrom(normalized,current.GetAllocator());
    if(!current.HasMember("market_input_origin"))return current;
    const auto& marker=member(normalized,"market_input_origin");keys(marker,{"schema","file","sha256","quotes","parser"});
    need(text(marker,"schema")=="guanheng.market-input-origin.v1");
    const auto path=absolute(text(marker,"file"));need(path.filename()=="execution.json");
    const auto raw=read(path,256*1024);need(sha(raw)==text(marker,"sha256",64));auto original=parse(raw);
    need(!original.HasMember("market_input_origin"));original.RemoveMember("recovery");
    current.RemoveMember("market_input_origin");
    const auto& checked_rows=member(current,"strategies");const auto& old_rows=member(original,"strategies");
    need(checked_rows.IsArray()&&checked_rows.Size()==1&&old_rows.IsArray()&&old_rows.Size()==1);
    auto& rows=current["strategies"];
    need(member(rows[0],"parameters").IsObject()&&member(member(rows[0],"parameters"),"python_strategy").IsObject());
    auto& parameters=rows[0]["parameters"]["python_strategy"];
    const auto& old_parameters=member(member(old_rows[0],"parameters"),"python_strategy");
    auto local_url=[](std::string value){
        if(!value.empty()&&value.back()=='/')value.pop_back();
        const std::string prefix="http://127.0.0.1:";need(value.compare(0,prefix.size(),prefix)==0);
        const auto port=value.substr(prefix.size());need(!port.empty()&&port.size()<=5
            &&std::all_of(port.begin(),port.end(),[](char c){return c>='0'&&c<='9';}));
        const auto number=std::stoul(port);need(number>0&&number<=65535);
    };
    if(marker.HasMember("quotes")){
        const auto& quotes=marker["quotes"];keys(quotes,{"base_url","token_env","timeout_seconds","max_response_bytes","max_age_seconds"});
        local_url(text(quotes,"base_url",2048));text(quotes,"token_env",128);
        const auto& timeout=member(quotes,"timeout_seconds");const auto& age=member(quotes,"max_age_seconds");
        need(timeout.IsNumber()&&std::isfinite(timeout.GetDouble())&&timeout.GetDouble()>0&&timeout.GetDouble()<=30
            &&age.IsNumber()&&std::isfinite(age.GetDouble())&&age.GetDouble()>0&&age.GetDouble()<=3600);
        number(quotes,"max_response_bytes",8192,16*1024*1024);
        need(member(parameters,"capital_market")==quotes);
        parameters["capital_market"].CopyFrom(member(old_parameters,"capital_market"),current.GetAllocator());
    }
    if(marker.HasMember("parser")){
        const auto& parser=marker["parser"];keys(parser,{"module","base_url","key_id_env","hmac_secret_env"});
        need(text(parser,"module")=="ParserQMTHostRetainedV6");local_url(text(parser,"base_url",2048));
        const auto& checked=member(current,"parsers");const auto& old=member(original,"parsers");
        need(checked.IsArray()&&checked.Size()==1&&old.IsArray()&&old.Size()==1
            &&text(old[0],"module")=="ParserQMTHostV6"&&text(checked[0],"module")==text(parser,"module"));
        auto& selected=current["parsers"][0];selected["module"].CopyFrom(old[0]["module"],current.GetAllocator());
        need(member(selected,"qmt").IsObject()&&member(old[0],"qmt").IsObject());
        for(const char* key:{"base_url","key_id_env","hmac_secret_env"}){
            need(text(selected["qmt"],key,2048)==text(parser,key,2048));
            selected["qmt"][key].CopyFrom(member(old[0]["qmt"],key),current.GetAllocator());
        }
    }
    need(!old_parameters.HasMember("market_window"));
    const auto& window=member(parameters,"market_window");keys(window,{"path","max_age_seconds"});
    const auto publication_path=absolute(text(window,"path"));const auto& age=member(window,"max_age_seconds");
    need(age.IsNumber()&&std::isfinite(age.GetDouble())&&age.GetDouble()>=1&&age.GetDouble()<=604800);
    need(member(current,"data").IsObject()&&member(member(current,"data"),"store").IsObject()
        &&member(member(member(current,"data"),"store"),"daily").IsObject());
    auto& daily=current["data"]["store"]["daily"];
    const auto& old_daily=member(member(member(original,"data"),"store"),"daily");
    need(!old_daily.HasMember("publication")&&!old_daily.HasMember("adjustment"));
    if(daily.HasMember("adjustment"))need(text(daily,"adjustment")=="none"||text(daily,"adjustment")=="front_ratio");
    const auto& publication=member(daily,"publication");keys(publication,{"status_file","publication_file","cache_root","source_root"});
    need(absolute(text(publication,"publication_file"))==publication_path);
    absolute(text(publication,"status_file"));absolute(text(publication,"cache_root"));
    if(publication.HasMember("source_root"))absolute(text(publication,"source_root"));
    parameters.RemoveMember("market_window");daily.RemoveMember("publication");daily.RemoveMember("adjustment");
    need(same_business(current,original));return original;
}

// 准入调用点持有原输出租约，券商O/P/A及原委托责任已沿原流程核查。
void admit_reconciled(const rj::Value& selection,const rj::Value& current,const fs::path& output,
    const rj::Value& strategies,const std::string& installation,const std::string& id,
    const std::string& configuration,const fs::path& control){
    const auto& reference=member(selection,"transition");keys(reference,{"file","sha256"});
    const auto transition_sha=text(reference,"sha256",64);
    const auto raw=read(absolute(text(reference,"file")),1024*1024);need(sha(raw)==transition_sha);
    auto transition=parse(raw);
    keys(transition,{"schema","predecessor_configuration","predecessor_configuration_sha256",
        "predecessor_control_directory","predecessor_installation_sha256","successor_installation_sha256",
        "predecessor_python_binding_sha256","successor_python_code_identity","state_files","restoration","initialization_abort"});
    need(text(transition,"schema")=="guanheng.execution-recovery-transition.v1"
        &&text(transition,"successor_installation_sha256")==installation);
    const auto prior_raw=read(absolute(text(transition,"predecessor_configuration")),256*1024);
    const auto prior_sha=text(transition,"predecessor_configuration_sha256",64);need(sha(prior_raw)==prior_sha);
    auto prior_config=parse(prior_raw);prior_config.RemoveMember("recovery");
    rj::Document identity;identity.CopyFrom(current,identity.GetAllocator());identity.RemoveMember("recovery");
    need(same_business(market_model(prior_config),market_model(identity)));
    const auto previous=absolute(text(transition,"predecessor_control_directory"));physical(previous);
    const bool initialization_abort=transition.HasMember("initialization_abort");
    need(!initialization_abort||(!fs::exists(previous/"ready.json")&&!transition.HasMember("restoration")));
    const auto ready_raw=read(previous/(initialization_abort?"failure.json":"ready.json"),4096);const auto ready=parse(ready_raw);
    const bool clean_transition=fs::exists(previous/"closed.json");
    need(!transition.HasMember("restoration")||clean_transition);
    if(current.HasMember("role_replacement")&&!prior_config.HasMember("role_replacement"))
        need(clean_transition&&!initialization_abort&&!transition.HasMember("restoration"));
    const bool lost_transition=!clean_transition&&!fs::exists(previous/"close-prepared.json")
        &&!fs::exists(previous/"failure.json")&&fs::exists(previous/"owner-loss.json");
    need(text(ready,"schema")== (initialization_abort?"guanheng.execution.failure.v1":"guanheng.execution.ready.v1"));
    auto same_origin=[&](const rj::Value& value){
        need(text(value,"config_sha256")==prior_sha&&text(value,"control_id")==text(ready,"control_id")
            &&member(value,"pid")==member(ready,"pid"));
    };
    same_origin(ready);
    if(initialization_abort){
        need(!clean_transition&&!lost_transition&&text(ready,"stage")=="cta");
        const auto closed=parse(read(previous/"close-prepared.json",4096));same_origin(closed);
        need(text(closed,"schema")=="guanheng.execution.close-prepared.v1"&&member(closed,"closed").IsTrue()
            &&member(closed,"ok").IsFalse()&&member(closed,"recovery_ready").IsFalse());
        const auto& reference=member(transition,"initialization_abort");keys(reference,{"file","sha256"});
        need(absolute(text(reference,"file"))==previous/"reconciled.json");
        const auto admitted_raw=read(previous/"reconciled.json",256*1024);
        need(sha(admitted_raw)==text(reference,"sha256",64));const auto admitted=parse(admitted_raw);same_origin(admitted);
        need(text(admitted,"schema")=="guanheng.cta-reconciled.v1"&&text(admitted,"admission_kind")=="clean_transition"
            &&member(admitted,"state_files")==member(transition,"state_files"));
        const auto prior_full=parse(prior_raw);const auto& selected=member(member(prior_full,"recovery"),"transition");
        const auto snapshot_raw=read(absolute(text(selected,"file")),1024*1024);
        need(sha(snapshot_raw)==text(selected,"sha256",64)&&sha(snapshot_raw)==text(admitted,"transition_sha256",64));
        const auto snapshot=parse(snapshot_raw);
        need(text(snapshot,"schema")=="guanheng.execution-recovery-transition.v1"&&!snapshot.HasMember("restoration")
            &&!snapshot.HasMember("initialization_abort")&&member(snapshot,"state_files")==member(transition,"state_files"));
        const auto origin=absolute(text(snapshot,"predecessor_control_directory"));physical(origin);
        need(origin.filename()==text(admitted,"predecessor_control_id"));
        const auto source_raw=read(origin/"execution.json",256*1024);
        need(sha(source_raw)==text(snapshot,"predecessor_configuration_sha256",64)
            &&sha(read(origin/"python-binding.json",256*1024))==text(snapshot,"predecessor_python_binding_sha256",64));
        auto source=parse(source_raw);need(member(member(source,"trader"),"writes_enabled").IsFalse()
            &&member(member(current,"trader"),"writes_enabled").IsFalse());
        source.RemoveMember("recovery");need(same_business(market_model(source),market_model(identity)));
        const auto terminal=parse(read(origin/"closed.json",4096));
        const auto source_ready=parse(read(origin/"ready.json",4096));
        need(text(source_ready,"schema")=="guanheng.execution.ready.v1"&&text(source_ready,"control_id")==origin.filename().string()
            &&text(source_ready,"config_sha256")==sha(source_raw)&&member(source_ready,"pid")==member(terminal,"pid"));
        need(text(terminal,"schema")=="guanheng.execution.closed.v2"&&text(terminal,"control_id")==origin.filename().string()
            &&text(terminal,"config_sha256")==sha(source_raw)&&member(terminal,"closed").IsTrue()
            &&member(terminal,"ok").IsTrue()&&member(terminal,"resources_closed").IsTrue()&&member(terminal,"recovery_ready").IsTrue()
            &&member(terminal,"error_code").IsNull()&&member(terminal,"exit_code").IsInt()&&member(terminal,"exit_code").GetInt()==0);
        const auto consumed=parse(read(output/".cta-clean.consumed.json",256*1024));
        need(text(consumed,"schema")=="guanheng.cta-clean.v2"&&text(consumed,"control_id")==origin.filename().string()
            &&text(consumed,"closed_config_sha256")==sha(source_raw)&&text(consumed,"config_sha256")==sha(encode(source))
            &&member(consumed,"closed").IsTrue()
            &&text(consumed,"installation_sha256")==text(snapshot,"predecessor_installation_sha256")
            &&member(consumed,"pid")==member(terminal,"pid")&&member(consumed,"files")==member(transition,"state_files")
            &&absolute(text(consumed,"closed_receipt"))==origin/"closed.json");
    }
    if(lost_transition){
        const auto loss=parse(read(previous/"owner-loss.json",4096));
        keys(loss,{"schema","control_id","config_sha256","pid","ready_sha256","reason","observed_at","observer_pid"});
        same_origin(loss);
        need(text(loss,"schema")=="guanheng.execution.owner-loss.v1"&&text(loss,"reason")=="process_lost"
            &&text(loss,"ready_sha256",64)==sha(ready_raw)&&!text(loss,"observed_at",64).empty()
            &&member(loss,"observer_pid").IsUint()&&member(loss,"observer_pid").GetUint()>0);
    }else{
        const auto closed=parse(read(previous/(clean_transition?"closed.json":"close-prepared.json"),4096));
        same_origin(closed);need(member(closed,"closed").IsTrue());
        if(clean_transition){
            need(text(closed,"schema")=="guanheng.execution.closed.v2"&&member(closed,"ok").IsTrue()
                &&member(closed,"recovery_ready").IsTrue()&&member(closed,"exit_code").IsInt()
                &&member(closed,"exit_code").GetInt()==0&&member(closed,"error_code").IsNull()
                &&member(closed,"resources_closed").IsTrue());
            const auto clean_raw=read(output/".cta-clean.json",256*1024);const auto origin=parse(clean_raw);
            need(text(origin,"schema")=="guanheng.cta-clean.v2"&&text(origin,"control_id")==text(ready,"control_id")
                &&text(origin,"config_sha256")==sha(encode(prior_config))&&member(origin,"closed").IsTrue()
                &&member(origin,"pid")==member(ready,"pid")&&text(origin,"closed_config_sha256")==prior_sha
                &&text(origin,"installation_sha256")==text(transition,"predecessor_installation_sha256")
                &&absolute(text(origin,"closed_receipt"))==previous/"closed.json");
            if(transition.HasMember("restoration")){
                auto pinned=[](const rj::Value& reference,std::size_t maximum){
                    keys(reference,{"file","sha256"});const auto raw=read(absolute(text(reference,"file")),maximum);
                    need(sha(raw)==text(reference,"sha256",64));return parse(raw);
                };
                const auto restore=pinned(transition["restoration"],1024*1024);
                keys(restore,{"schema","current_clean_sha256","archive_directory","snapshot_admission","snapshot_transition"});
                need(text(restore,"schema")=="guanheng.execution-restoration.v1"
                    &&text(restore,"current_clean_sha256",64)==sha(clean_raw)
                    &&member(member(prior_config,"trader"),"writes_enabled").IsFalse()
                    &&member(member(current,"trader"),"writes_enabled").IsFalse());
                const auto archive=absolute(text(restore,"archive_directory"));physical(archive);
                need(read(archive/"clean.json",256*1024)==clean_raw
                    &&state_identity(archive,strategies)==member(origin,"files"));
                const auto admitted=pinned(member(restore,"snapshot_admission"),256*1024);
                const auto snapshot=pinned(member(restore,"snapshot_transition"),1024*1024);
                const auto admission_path=absolute(text(member(restore,"snapshot_admission"),"file"));
                need(admission_path.filename()=="reconciled.json");
                const auto accepted_ready=parse(read(admission_path.parent_path()/"ready.json",4096));
                need(text(snapshot,"schema")=="guanheng.execution-recovery-transition.v1"
                    &&text(accepted_ready,"schema")=="guanheng.execution.ready.v1"
                    &&text(admitted,"schema")=="guanheng.cta-reconciled.v1"&&text(admitted,"admission_kind")=="clean_transition"
                    &&text(admitted,"transition_sha256",64)==text(member(restore,"snapshot_transition"),"sha256",64)
                    &&member(admitted,"state_files")==member(snapshot,"state_files")
                    &&member(admitted,"state_files")==member(transition,"state_files"));
                for(const char* key:{"control_id","config_sha256","pid"})need(member(admitted,key)==member(accepted_ready,key));
                const auto snapshot_owner=absolute(text(snapshot,"predecessor_control_directory"));
                need(snapshot_owner.filename()==text(admitted,"predecessor_control_id"));
                const auto snapshot_raw=read(snapshot_owner/"execution.json",256*1024);
                need(sha(snapshot_raw)==text(snapshot,"predecessor_configuration_sha256",64)
                    &&sha(read(snapshot_owner/"python-binding.json",256*1024))==text(snapshot,"predecessor_python_binding_sha256",64)
                    &&same_business(market_model(parse(snapshot_raw)),market_model(current)));
            }else need(member(origin,"files")==member(transition,"state_files"));
        }else{
            const auto failure=parse(read(previous/"failure.json",4096));same_origin(failure);
            need(text(failure,"schema")=="guanheng.execution.failure.v1"
                &&text(closed,"schema")=="guanheng.execution.close-prepared.v1"
                &&member(closed,"ok").IsFalse()&&member(closed,"recovery_ready").IsFalse());
        }
    }
    const auto& pid=member(ready,"pid");need(pid.IsUint()&&pid.GetUint()>0);
    Handle process;process.value=OpenProcess(SYNCHRONIZE,FALSE,pid.GetUint());
    if(process.value)need(WaitForSingleObject(process.value,0)==WAIT_OBJECT_0);
    else need(GetLastError()==ERROR_INVALID_PARAMETER);
    need(sha(read(previous/"python-binding.json",256*1024))==text(transition,"predecessor_python_binding_sha256"));
    const auto consumed=output/".cta-clean.consumed.json";
    if(clean_transition){/* 原成功关闭证明已在同根租约内完整核验。 */}
    else if(fs::exists(previous/"installation-identity.json")){
        const auto origin=parse(read(previous/"installation-identity.json",4096));same_origin(origin);
        need(text(origin,"schema")=="guanheng.execution-installation.v1"
            &&text(origin,"installation_sha256")==text(transition,"predecessor_installation_sha256"));
    }else if(fs::exists(previous/"reconciled.json")){
        const auto origin=parse(read(previous/"reconciled.json",256*1024));
        same_origin(origin);need(text(origin,"schema")=="guanheng.cta-reconciled.v1"
            &&text(origin,"successor_installation_sha256")==text(transition,"predecessor_installation_sha256"));
    }else if(fs::exists(consumed)){
        const auto origin=parse(read(consumed,256*1024));
        need(text(origin,"schema")=="guanheng.cta-clean.v2"&&text(origin,"config_sha256")==sha(encode(prior_config))
            &&member(origin,"closed").IsTrue()
            &&text(origin,"installation_sha256")==text(transition,"predecessor_installation_sha256"));
        const auto source=parse(read(absolute(text(origin,"closed_receipt")),4096));
        need(text(source,"schema")=="guanheng.execution.closed.v2"&&text(source,"control_id")==text(origin,"control_id")
            &&text(source,"config_sha256")==text(origin,"closed_config_sha256")&&member(source,"pid")==member(origin,"pid")
            &&member(source,"closed").IsTrue()&&member(source,"ok").IsTrue()&&member(source,"recovery_ready").IsTrue()
            &&member(source,"error_code").IsNull()&&member(source,"exit_code").IsInt()
            &&member(source,"exit_code").GetInt()==0&&member(source,"resources_closed").IsTrue());
    }else need(false);
    need((clean_transition||!fs::exists(output/".cta-clean.json"))&&!fs::exists(output/".cta-clean.prepared.json")
        &&encode(state_identity(output,strategies))==encode(member(transition,"state_files")));
    const auto claimed=output/(".cta-reconciled-"+transition_sha+".json");need(!fs::exists(claimed));
    auto proof=receipt("guanheng.cta-reconciled.v1",id,configuration,false);auto& a=proof.GetAllocator();
    proof.AddMember("transition_sha256",rj::Value(transition_sha.c_str(),a),a); // 配置绑定的固定发行材料摘要。
    proof.AddMember("admission_kind",rj::Value(initialization_abort?"initialization_abort_reconciled":transition.HasMember("restoration")?"restored_snapshot":clean_transition?"clean_transition":lost_transition?"process_lost_reconciled":"fault_reconciled",a),a); // 启动失败原状态、正常关闭、显式恢复和故障依据分别保留。
    proof.AddMember("successor_installation_sha256",rj::Value(installation.c_str(),a),a); // 本代完整安装清单规范摘要。
    if(transition.HasMember("restoration"))proof.AddMember("restoration_sha256",
        rj::Value(text(transition["restoration"],"sha256",64).c_str(),a),a); // 显式恢复材料，不重放原clean。
    proof.AddMember("predecessor_control_id",rj::Value(text(ready,"control_id").c_str(),a),a); // 上代真实控制ID。
    proof.AddMember("state_files",rj::Value(member(transition,"state_files"),a),a); // 原金融JSON相对路径与字节摘要，仅作准入证据。
    // 独立核查收据记录新代认领；原failure/consumed与金融JSON均保留原字节。
    if(clean_transition)need(MoveFileExW((output/".cta-clean.json").c_str(),consumed.c_str(),
        MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH)!=0);
    publish(claimed,proof);publish(control/"reconciled.json",proof);
}
bool own_orders_empty(guanheng::StandardExecutionHost& execution){
    auto* rows=execution.orders("");need(rows!=nullptr);const bool empty=rows->size()==0;rows->release();return empty;
}
// 原query_first表只包含Host已核身份及本Adapter本地ID的活动单；人工单不进入该表。
// 完整O后读取后继P/A。已知挂单保留原ID，撤单交原WT执行器；未知调用继续原核查。
template<class Check,class Advance>void reconcile_own_orders(guanheng::StandardExecutionHost& execution,Check check,Advance advance){
    check();guanheng::StandardQmtRecoveryV1 state;need(execution.recovery(state)==0);
    auto refresh=[&]{check();advance();check();need(execution.recovery(state)==0);};
    for(;;){
        auto barrier=state.next_task;check();need(execution.query_orders()==0);check();
        while(state.last_order_query<=barrier)refresh();
        auto* rows=execution.orders("");need(rows!=nullptr);
        struct OrdersOwner{wtp::OrderMap* value;~OrdersOwner(){value->release();}} owned{rows};
        for(auto it=rows->begin();it!=rows->end();++it){
            auto* row=static_cast<wtp::WTSOrderInfo*>(it->second);
            need(it->first&&row->isAlive()&&row->getEntrustID()[0]&&row->getUserTag()[0]);
        }
        barrier=state.next_task;check();need(execution.query_positions()==0);check();
        while(state.last_position_query<=barrier)refresh();
        if(known_orders_recoverable(execution,state))break;
        refresh();
    }
    const auto barrier=state.next_task;check();need(execution.query_account()==0);check();
    while(state.last_account_query<=barrier)refresh();
}
void bootstrap_takeover(const rj::Value& input,const std::string& input_sha,const fs::path& output,
    const rj::Value& strategies,guanheng::StandardExecutionHost& execution,WTSBaseDataMgr& base,
    guanheng::ExecutionEnvironment& environment){
    // 接管只转换明确初值。原查询表核全部现存仓位，原WT继续拥有后续明细和绩效。
    keys(input,{"schema","strategy_id","strategy_version","source_sha256","captured_uptime_ms",
        "valid_until_uptime_ms","trading_date","performance_basis","positions","strategy_state"});
    // 协议格式与策略版本分别核验；新运行采用真实1.2.1版本，原1.1.2归档仍可读取。
    const auto schema=text(input,"schema");const bool native_day=schema=="guanheng.cta-takeover.v2";
    need((native_day||schema=="guanheng.cta-takeover.v1")
        &&text(input,"strategy_id")=="resonance-regime-v1"&&(text(input,"strategy_version")=="1.1.2"||text(input,"strategy_version")=="1.2.1"||text(input,"strategy_version")=="1.2.2")
        &&text(input,"performance_basis")=="takeover-mark");
    need(strategies.IsArray()&&strategies.Size()==1&&text(strategies[0],"id")==text(input,"strategy_id"));
    auto digest=[&](const rj::Value& value,const char* key){
        const auto s=text(value,key,64);need(s.size()==64);
        for(char c:s)need((c>='0'&&c<='9')||(c>='a'&&c<='f'));
    };
    digest(input,"source_sha256");
    const auto& captured=member(input,"captured_uptime_ms");const auto& until=member(input,"valid_until_uptime_ms");
    const auto now=GetTickCount64();need(captured.IsUint64()&&until.IsUint64()&&captured.GetUint64()<=now&&now<until.GetUint64());
    auto date_valid=[](unsigned date,unsigned time){
        SYSTEMTIME s{};s.wYear=static_cast<WORD>(date/10000);s.wMonth=static_cast<WORD>((date/100)%100);
        s.wDay=static_cast<WORD>(date%100);s.wHour=static_cast<WORD>(time/100);s.wMinute=static_cast<WORD>(time%100);
        FILETIME file{};SYSTEMTIME back{};
        return date>=20000101&&date<=20991231&&time/100<24&&time%100<60&&SystemTimeToFileTime(&s,&file)
            &&FileTimeToSystemTime(&file,&back)&&s.wYear==back.wYear&&s.wMonth==back.wMonth&&s.wDay==back.wDay;
    };
    // 自动初值的账本日期归原生会话日历；v1显式日期继续核同一次owner观察。
    const auto observed_time=environment.observe();
    need(!native_day||!input.HasMember("trading_date"));
    const auto day=native_day?observed_time.trading_day:number(input,"trading_date",20000101,20991231);
    need(date_valid(day,0)&&day==observed_time.trading_day);
    const auto current_minute=std::uint64_t(observed_time.date)*10000+observed_time.time_ms/100000;
    guanheng::StandardQmtRecoveryV1 state;need(execution.recovery(state)==0);
    need(state.query_first&&!state.open_group&&!state.unresolved_children&&!state.pending_commands&&!state.unsafe
        &&state.last_order_query&&state.last_position_query&&own_orders_empty(execution));
    const auto& rows=member(input,"positions");need(rows.IsArray()&&rows.Size()>0&&rows.Size()<=8);
    std::map<std::string,std::pair<double,double>> expected;
    rj::Document strategy(rj::kObjectType);auto& a=strategy.GetAllocator();rj::Value positions(rj::kArrayType);
    for(const auto& row:rows.GetArray()){
        keys(row,{"code","quantity","sellable","mark_price","mark_source_sha256","cycle_id","opened_local_minute","cycle_source_sha256"});
        const auto code=text(row,"code",63);
        // 复用owner环境的原容量/标准代码准入，再进入原CodeHelper和合约查找。
        need(environment.get_comm_info(code.c_str()));const auto key=CodeHelper::extractStdCode(code.c_str(),nullptr);
        need(base.getContract(key._code,key._exchg));
        const auto& quantity=member(row,"quantity");const auto& sellable=member(row,"sellable");
        need(quantity.IsUint64()&&sellable.IsUint64()&&sellable.GetUint64()<=quantity.GetUint64()&&quantity.GetUint64()<=9007199254740900ull);
        const double total=static_cast<double>(quantity.GetUint64()),valid=static_cast<double>(sellable.GetUint64());
        need(expected.emplace(code,std::make_pair(total,valid)).second&&execution.position(code.c_str())==total
            &&execution.position(code.c_str(),true)==valid&&execution.undone(code.c_str())==0);
        const auto& opening=member(row,"opened_local_minute");need(opening.IsUint64());
        const auto opened=opening.GetUint64();const auto& cycle=member(row,"cycle_id");need(cycle.IsString());
        const auto& mark=member(row,"mark_price");need(mark.IsNumber()&&std::isfinite(mark.GetDouble()));
        if(!total){need(!opened&&!cycle.GetStringLength()&&mark.GetDouble()==0);continue;}
        need(mark.GetDouble()>0&&opened<=current_minute&&opened/10000>=20000101
            &&date_valid(static_cast<unsigned>(opened/10000),static_cast<unsigned>(opened%10000)));
        text(row,"cycle_id",128);digest(row,"cycle_source_sha256");digest(row,"mark_source_sha256");
        rj::Value p(rj::kObjectType);p.AddMember("code",rj::Value(code.c_str(),a),a);p.AddMember("volume",total,a);
        p.AddMember("closeprofit",0.,a);p.AddMember("dynprofit",0.,a);p.AddMember("lastentertime",opened,a);
        p.AddMember("lastexittime",std::uint64_t(0),a);p.AddMember("frozen",total-valid,a);p.AddMember("frozendate",day,a);
        rj::Value detail(rj::kObjectType);detail.AddMember("long",true,a);detail.AddMember("price",mark.GetDouble(),a);
        detail.AddMember("maxprice",mark.GetDouble(),a);detail.AddMember("minprice",mark.GetDouble(),a);
        detail.AddMember("volume",total,a);detail.AddMember("opentime",opened,a);
        detail.AddMember("opentdate",static_cast<unsigned>(opened/10000),a);
        detail.AddMember("profit",0.,a);detail.AddMember("maxprofit",0.,a);detail.AddMember("maxloss",0.,a);
        detail.AddMember("opentag","takeover",a);detail.AddMember("openbarno",0u,a);
        rj::Value details(rj::kArrayType);details.PushBack(detail,a);p.AddMember("details",details,a);positions.PushBack(p,a);
    }
    for(const auto& actual:execution.positions()){
        if(actual.quantity==0)continue;
        const auto at=expected.find(actual.code);need(actual.is_long&&at!=expected.end()
            &&at->second.first==actual.quantity&&at->second.second==actual.sellable);
    }
    strategy.AddMember("positions",positions,a);rj::Value fund(rj::kObjectType);
    fund.AddMember("total_profit",0.,a);fund.AddMember("total_dynprofit",0.,a);fund.AddMember("total_fees",0.,a);fund.AddMember("tdate",day,a);
    strategy.AddMember("fund",fund,a);strategy.AddMember("conditions",rj::Value(),a);
    strategy.AddMember("signals",rj::Value(rj::kObjectType),a);
    rj::Document portfolio(rj::kObjectType);portfolio.AddMember("fund",rj::Value(),portfolio.GetAllocator());
    portfolio.AddMember("positions",rj::Value(strategy["positions"],portfolio.GetAllocator()),portfolio.GetAllocator());
    const auto saved=text(input,"strategy_state",32768);for(unsigned char c:saved)need(c>=32&&c<=126);
    rj::Document userdata(rj::kObjectType);userdata.AddMember("guanheng.quantity.state.v1",rj::Value(saved.c_str(),userdata.GetAllocator()),userdata.GetAllocator());
    // 所有字段和当次券商观察先核完；CREATE_NEW/pending失败保留现场供下一次恢复判断。
    need(!fs::exists(output/".cta-takeover.json")&&!fs::exists(output/".cta-takeover.json.pending"));
    need(fs::create_directory(output/"stradata")&&fs::create_directory(output/"portfolio")&&fs::create_directory(output/"userdata"));
    const auto id=text(input,"strategy_id");publish(output/"stradata"/(id+".json"),strategy);
    publish(output/"portfolio/datas.json",portfolio);publish(output/"userdata"/("ud_"+id+".json"),userdata);
    rj::Document proof(rj::kObjectType);auto& p=proof.GetAllocator();proof.AddMember("schema","guanheng.cta-takeover-receipt.v1",p);
    proof.AddMember("input_sha256",rj::Value(input_sha.c_str(),p),p);proof.AddMember("performance_basis","takeover-mark",p);
    if(native_day){proof.AddMember("native_trading_date",day,p);proof.AddMember("date_owner","WT-session-calendar",p);}
    proof.AddMember("source",rj::Value(input,p),p);publish(output/".cta-takeover.json",proof);
}
}
namespace {
int run_process(int argc,const wchar_t* const* argv,GhCtaHealth health,void* health_user){
    if(argc!=9)return 2;
    BrokerPublicationLifetime broker_lifetime;
    fs::path config_path,control;std::string id,expected_sha;
    guanheng::NativeRuntimeLog native_log; // 原owner持有至业务生产者全部关闭，日志失败不改变交易准入。
    const auto started=Clock::now();auto close_until=started+std::chrono::seconds(60);
    WTSBaseDataMgr base;WTSHotMgr hot;wtp::ActionPolicyMgr policy;wtp::WtExecuterFactory factory;
    std::unique_ptr<guanheng::ExecutionEnvironment> environment;
    std::unique_ptr<guanheng::StandardExecutionHost> execution;
    std::unique_ptr<guanheng::CtaExecutionSession> session;
    std::vector<StrategyFactory> factories;std::vector<Variant> parameters;
    std::vector<guanheng::CtaExecutionStrategy> unowned;
    Variant trader,executer,env,data,parser_config;Handle account_lease;
    guanheng::CtaExecutionRecovery recovery_hooks;
    fs::path recovery_output;std::string recovery_config,recovery_installation;
    rj::Document recovery_strategies;
    rj::Document takeover_input;std::string takeover_sha;
    bool recovery_enabled=false,recovery_armed=false,recovery_ready=false;
    decltype(&gh_ms_status) target_status=nullptr;std::uint64_t initial_setters=0;
    bool success=false,closed=false,stop_deadline_fixed=false;unsigned stop_ms=10000,native_error=0;
    bool lifecycle_started=false; // 原Native start已完成；用于确认停止事件属于真实启动过的这一代。
    bool native_log_attempted=false; // 控制目录已准入后才创建日志及其旁证。
    const char* stage="configuration";
    decltype(&inspectStandardQmtEventChain) inspect_event_chain=nullptr; // 可选旁证；旧DLL缺导出继续原路径。
    decltype(&findStandardQmtTrader) find_event_chain=nullptr; // 同一已装载DLL的实例查找，借用至进程退出。
    try{
        need(std::wstring(argv[1])==L"--config"&&std::wstring(argv[3])==L"--control"
             &&std::wstring(argv[5])==L"--control-id"&&std::wstring(argv[7])==L"--config-sha256");
        config_path=absolute(fs::path(argv[2]).u8string());control=absolute(fs::path(argv[4]).u8string());
        id=fs::path(argv[6]).u8string();expected_sha=fs::path(argv[8]).u8string();
        need(id.size()==36&&expected_sha.size()==64&&fs::is_directory(control));
        need(!fs::exists(control/"ready.json")&&!fs::exists(control/"closed.json")&&!fs::exists(control/"close-prepared.json"));
        native_log.start(control);
        native_log_attempted=true;
        const auto raw=read(config_path,256*1024);need(sha(raw)==expected_sha);auto cfg=parse(raw);
        keys(cfg,{"schema_version","installation_root","output_directory","base_data","trader","executer","environment","data","parsers","strategies","budget","queue","recovery","takeover","observation_refresh","market_input_origin","execution_permission_origin","role_replacement"});
        need(text(cfg,"schema_version")=="guanheng.cta-execution.v1");
        if(cfg.HasMember("role_replacement")){
            need(text(member(cfg,"recovery"),"mode")!="record_clean");role_model(cfg);
        }
        if(cfg.HasMember("execution_permission_origin")){
            need(text(member(cfg,"recovery"),"mode")!="record_clean");permission_model(cfg);
        }
        if(cfg.HasMember("market_input_origin")){
            need(text(member(cfg,"recovery"),"mode")!="record_clean");market_model(cfg);
        }
        unsigned observation_refresh_ms=0;
        const auto& trader_config=member(cfg,"trader");
        need(trader_config.IsObject()&&!trader_config.HasMember("observation_refresh_ms"));
        if(cfg.HasMember("observation_refresh")){
            const auto& refresh=member(cfg,"observation_refresh");keys(refresh,{"interval_ms"});
            observation_refresh_ms=number(refresh,"interval_ms",1000,60000);
        }
        const auto root=absolute(text(cfg,"installation_root"));need(fs::is_directory(root));fs::current_path(root);
        WtHelper::setInstDir((root.generic_string()+"/").c_str());
        const auto output=absolute(text(cfg,"output_directory"));
        if(!fs::exists(output))need(fs::create_directory(output));need(fs::is_directory(output));
        WtHelper::setGenerateDir((output.generic_string()+"/").c_str());
        if(cfg.HasMember("recovery")){
            const auto& selection=cfg["recovery"];keys(selection,{"mode","transition"});const auto mode=text(selection,"mode",32);
            need(mode=="record_clean"||mode=="resume_clean"||mode=="resume_reconciled");
            need(selection.HasMember("transition")== (mode=="resume_reconciled"));
            recovery_enabled=true;recovery_hooks.restore=mode!="record_clean";
            need(text(member(cfg,"trader"),"order_context")=="query_first");
            need(member(member(cfg,"trader"),"savedata").IsBool()&&!cfg["trader"]["savedata"].GetBool());
            recovery_output=output;recovery_installation=installation_identity(root);
            auto installation_receipt=receipt("guanheng.execution-installation.v1",id,expected_sha,false);
            installation_receipt.AddMember("installation_sha256",rj::Value(recovery_installation.c_str(),installation_receipt.GetAllocator()),installation_receipt.GetAllocator()); // 本代已核完整安装身份，供后继追溯。
            publish(control/"installation-identity.json",installation_receipt);
            rj::Document identity;identity.CopyFrom(cfg,identity.GetAllocator());identity.RemoveMember("recovery");
            recovery_config=sha(encode(identity));recovery_strategies.CopyFrom(member(cfg,"strategies"),recovery_strategies.GetAllocator());
            recovery_hooks.admit=[&,mode]{
                physical(recovery_output);
                const auto marker=recovery_output/".cta-clean.json";
                need(!fs::exists(recovery_output/".cta-clean.json.pending"));
                need(!fs::exists(recovery_output/".cta-clean.prepared.json")
                    &&!fs::exists(recovery_output/".cta-clean.prepared.json.pending"));
                if(mode=="resume_reconciled"){
                    admit_reconciled(selection,cfg,recovery_output,recovery_strategies,recovery_installation,id,expected_sha,control);return true;
                }
                if(!recovery_hooks.restore){need(!fs::exists(marker)&&!fs::exists(recovery_output/".cta-clean.consumed.json"));return true;}
                physical(marker);const auto proof=parse(read(marker,256*1024));
                need(text(proof,"schema")=="guanheng.cta-clean.v2"&&text(proof,"config_sha256")==recovery_config
                    &&text(proof,"installation_sha256")==recovery_installation);
                const auto prior=parse(read(absolute(text(proof,"closed_receipt")),4096));
                need(text(prior,"schema")=="guanheng.execution.closed.v2"&&text(prior,"control_id")==text(proof,"control_id")
                    &&text(prior,"config_sha256")==text(proof,"closed_config_sha256")&&member(prior,"pid")==member(proof,"pid")
                    &&member(prior,"closed").IsTrue()&&member(prior,"ok").IsTrue()&&member(prior,"recovery_ready").IsTrue()
                    &&member(prior,"error_code").IsNull()&&member(prior,"exit_code").IsInt()
                    &&member(prior,"exit_code").GetInt()==0&&member(prior,"resources_closed").IsTrue());
                need(encode(member(proof,"files"))==encode(state_identity(recovery_output,recovery_strategies)));
                // 原子消费后才允许原init写状态；异常退出留下consumed，下一代不能重用clean。
                need(MoveFileExW(marker.c_str(),(recovery_output/".cta-clean.consumed.json").c_str(),MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH)!=0);
                return true;
            };
            recovery_hooks.closed=[&]{
                if(!recovery_armed)return true;
                guanheng::StandardQmtRecoveryV1 state;need(execution->recovery(state)==0&&settled(*execution,state));
                need(execution->status().fault==guanheng::ExecutionHostFault::None&&execution->status().plugin.error==0);
                need(!health||health(health_user)==0);
                auto proof=receipt("guanheng.cta-clean.v2",id,recovery_config,true);auto& a=proof.GetAllocator();
                proof.AddMember("installation_sha256",rj::Value(recovery_installation.c_str(),a),a);
                proof.AddMember("closed_receipt",rj::Value((control/"closed.json").u8string().c_str(),a),a);
                proof.AddMember("closed_config_sha256",rj::Value(expected_sha.c_str(),a),a);
                auto files=state_identity(recovery_output,recovery_strategies);proof.AddMember("files",rj::Value(files,a),a);
                proof.AddMember("last_order_query",state.last_order_query,a);proof.AddMember("last_position_query",state.last_position_query,a);
                // 父监督者在正常进程退出及Job回收后才将准备材料发布为最终恢复证明。
                publish(recovery_output/".cta-clean.prepared.json",proof);recovery_ready=true;return true;
            };
        }
        const auto& budget=member(cfg,"budget");keys(budget,{"start_ms","stop_ms","run_ms"});
        const auto start_until=started+std::chrono::milliseconds(number(budget,"start_ms",1000,60000));
        stop_ms=number(budget,"stop_ms",1000,60000);const auto run_ms=number(budget,"run_ms",0,86400000);
        need(run_ms==0||run_ms>=1000); // 0持续运行至原stop；正数保留有限运行语义。
        auto check_start=[&]{need(Clock::now()<start_until);need(!health||health(health_user)==0);};
        if(cfg.HasMember("takeover")){
            need(recovery_enabled);const auto& selection=cfg["takeover"];keys(selection,{"input_file","input_sha256"});
            takeover_sha=text(selection,"input_sha256",64);const auto bytes=read(absolute(text(selection,"input_file")),128*1024);
            need(sha(bytes)==takeover_sha);takeover_input=parse(bytes);check_start();
            recovery_hooks.prepare=[&]{bootstrap_takeover(takeover_input,takeover_sha,recovery_output,recovery_strategies,*execution,base,*environment);return true;};
        }
        const auto reference_session=text(member(member(cfg,"environment"),"product"),"session",63);
        text(member(cfg,"trader"),"expected_account",63);text(member(cfg,"trader"),"environment",32);text(member(cfg,"trader"),"profile",64);
        stage="base_data";
        const auto& base_cfg=member(cfg,"base_data");keys(base_cfg,{"sessions","commodities","contracts","holidays","policy"});
        check_start();need(base.loadSessions(installed(root,text(base_cfg,"sessions")).string().c_str()));
        need(base.loadCommodities(installed(root,text(base_cfg,"commodities")).string().c_str()));
        need(base.loadContracts(installed(root,text(base_cfg,"contracts")).string().c_str()));
        need(base.loadHolidays(installed(root,text(base_cfg,"holidays")).string().c_str()));
        need(policy.init(installed(root,text(base_cfg,"policy")).string().c_str()));check_start();
        trader=load_variant(member(cfg,"trader"));executer=load_variant(member(cfg,"executer"));env=load_variant(member(cfg,"environment"));data=load_variant(member(cfg,"data"));
        stage="account_lease";
        const auto account_identity=sha(trader->getString("expected_account")+"|"+trader->getString("environment")+"|"+trader->getString("profile"));
        const auto mutex_name=std::wstring(L"Global\\GuanhengCta-")+std::wstring(account_identity.begin(),account_identity.end());
        account_lease.value=CreateMutexW(nullptr,TRUE,mutex_name.c_str());native_error=GetLastError();
        need(account_lease.value&&account_lease.value!=INVALID_HANDLE_VALUE);
        need(native_error!=ERROR_ALREADY_EXISTS);check_start();
        stage="trader";Library plugin(installed(root,"traders/TraderQMTStandard.dll"));
        if(observation_refresh_ms){
            need(plugin.get<decltype(&standardQmtObservationRefreshVersion)>("standardQmtObservationRefreshVersion")()==1);
            trader->append("observation_refresh_ms",observation_refresh_ms);
        }
        guanheng::StandardPluginFunctions functions;
        functions.find=plugin.get<decltype(functions.find)>("findStandardQmtTrader");
        find_event_chain=functions.find;
        inspect_event_chain=reinterpret_cast<decltype(inspect_event_chain)>(GetProcAddress(plugin.module,"inspectStandardQmtEventChain"));
        functions.pump=plugin.get<decltype(functions.pump)>("pumpStandardQmtTrader");
        functions.inspect=plugin.get<decltype(functions.inspect)>("inspectStandardQmtTrader");
        functions.awaiting_observation=reinterpret_cast<decltype(functions.awaiting_observation)>(
            GetProcAddress(plugin.module,"inspectStandardQmtAwaitingObservation"));
        functions.stop=plugin.get<decltype(functions.stop)>("stopStandardQmtTrader");
        functions.destroy=plugin.get<decltype(functions.destroy)>("deleteTrader");
        functions.submission={plugin.get<guanheng::BeginSubmissionFn>("beginStandardQmtSubmission"),
            plugin.get<guanheng::EndSubmissionFn>("endStandardQmtSubmission"),plugin.get<guanheng::InspectSubmissionFn>("inspectStandardQmtSubmission")};
        if(recovery_enabled){
            functions.close_submissions=plugin.get<decltype(functions.close_submissions)>("closeStandardQmtSubmissions");
            functions.recovery=plugin.get<decltype(functions.recovery)>("inspectStandardQmtRecovery");
            functions.working_children=plugin.get<decltype(functions.working_children)>("inspectStandardQmtWorkingChildren");
            functions.pause_inserts=plugin.get<decltype(functions.pause_inserts)>("pauseStandardQmtInserts");
        }
        need(factory.loadFactories((root/"executers").string().c_str()));
        environment.reset(new guanheng::ExecutionEnvironment(base,reference_session.c_str(),&hot));
        const auto& queue=member(cfg,"queue");keys(queue,{"commands","bytes","targets","delay_ms"});
        execution.reset(new guanheng::StandardExecutionHost("qmt","cta",base,policy,factory,*environment));
        need(execution->initialize(trader.get(),executer.get(),functions,
            {number(queue,"commands",1,1024),number(queue,"bytes",1,64*1024*1024),number(queue,"targets",1,4096),number(queue,"delay_ms",1,30000)}));
        while(execution->status().phase!=guanheng::ExecutionHostPhase::Ready){
            check_start();need(execution->pump(64,16)>=0);
            need(execution->status().fault==guanheng::ExecutionHostFault::None);Sleep(1);
        }
        publish_broker(*execution,*environment);
        if(recovery_enabled){
            stage="reconcile_orders";
            reconcile_own_orders(*execution,check_start,[&]{need(execution->pump(64,16)>=0
                &&execution->status().fault==guanheng::ExecutionHostFault::None);Sleep(1);});
            publish_broker(*execution,*environment);
        }
        if(cfg.HasMember("role_replacement")){
            // 同owner读取已完成的真实P/O；退役证券零持仓、两证券无活动委托，原订单恢复已完成。
            const auto observed=execution->broker_observation();need(observed.positions_known);
            need(execution->position("SSE.ETF.589680")==0);
            need(execution->undone("SSE.ETF.589680")==0);
            // 历史标记沿用时，新基金可带自有挂单；首次角色换代仍要求新角色没有旧委托。
            const auto& recovery=member(cfg,"recovery");
            if(text(recovery,"mode")=="resume_reconciled"){
                const auto& selected=member(recovery,"transition");
                const auto transition=parse(read(absolute(text(selected,"file")),1024*1024));
                const auto predecessor=parse(read(absolute(text(transition,"predecessor_configuration")),256*1024));
                if(!predecessor.HasMember("role_replacement"))need(execution->undone("SSE.ETF.588030")==0);
            }else need(execution->undone("SSE.ETF.588030")==0);
            // 新基金可有本轮WT验证成交；Python以原基准和完整D核真实开启，P保持券商查询原值。
        }
        stage="strategies";const auto& strategies=member(cfg,"strategies");need(strategies.IsArray()&&strategies.Size()>0&&strategies.Size()<=64);
        factories.reserve(strategies.Size());parameters.reserve(strategies.Size());unowned.reserve(strategies.Size());
        for(const auto& item:strategies.GetArray()){
            keys(item,{"id","module","factory","name","parameters"});check_start();
            StrategyFactory owner;owner.library.reset(new Library(installed(root,text(item,"module"))));
            owner.value=owner.library->get<FuncCreateStraFact>("createStrategyFact")();need(owner.value!=nullptr);
            factories.push_back(std::move(owner));need(text(item,"factory")==factories.back().value->getName());
            parameters.push_back(load_variant(member(item,"parameters")));
            auto* strategy=factories.back().value->createStrategy(text(item,"name").c_str(),text(item,"id",63).c_str());need(strategy!=nullptr);
            unowned.push_back({strategy,factories.back().value,parameters.back().get()});
        }
        if(recovery_enabled&&strategies.Size()==1){
            target_status=reinterpret_cast<decltype(target_status)>(GetProcAddress(factories[0].library->module,"gh_ms_status"));
            if(target_status){GhMsStatus value{};value.size=sizeof(value);
                need(target_status(&value)==0&&value.failure==0&&value.configured==1);
                initial_setters=value.setters;need(execution->pause_inserts(true));}
        }
        stage="cta";session.reset(new guanheng::CtaExecutionSession(base,hot,*execution,unowned));unowned.clear();
        const auto& parsers=member(cfg,"parsers");need(parsers.IsArray());rj::Document parser_root(rj::kObjectType);
        parser_root.AddMember("parsers",rj::Value(parsers,parser_root.GetAllocator()),parser_root.GetAllocator());parser_config=load_variant(parser_root);
        need(session->initialize(env.get(),data.get(),parser_config->get("parsers"),output.string().c_str(),recovery_enabled?&recovery_hooks:nullptr));check_start();
        need(session->start());check_start();
        lifecycle_started=true;
        publish_lifecycle(control,"lifecycle-started.json","guanheng.execution.started.v1",id,expected_sha,false);
        auto ready=receipt("guanheng.execution.ready.v1",id,expected_sha,false);publish(control/"ready.json",ready);stage="runtime";
        const auto run_until=run_ms?Clock::now()+std::chrono::milliseconds(run_ms):Clock::time_point::max();
        bool stop_seen=false,stop_decoded=false;
        int last_read_waiting=-1;unsigned read_transitions=0;
        auto next_read_publish=Clock::time_point::min();
        auto next_cta_publish=Clock::time_point::min(); // 诊断最多每秒一次，独立于交易及读取状态准入。
        while(Clock::now()<run_until){
            if(fs::exists(control/"stop.json")){
                if(!stop_seen){
                    stop_seen=true;close_until=Clock::now()+std::chrono::milliseconds(stop_ms);stop_deadline_fixed=true;
                }
                stage="stop_read";std::string stop_raw;
                try{stop_raw=read(control/"stop.json",4096);}
                catch(const ReadError& error){
                    if(error.code!=ERROR_SHARING_VIOLATION&&error.code!=ERROR_LOCK_VIOLATION)throw;
                    need(Clock::now()<close_until);Sleep(1);continue;
                }
                need(Clock::now()<close_until);
                stage="stop_parse";const auto stop=parse(stop_raw);
                stage="stop_identity";keys(stop,{"schema","control_id","deadline"});
                need(text(stop,"schema")=="guanheng.execution.stop.v1"&&text(stop,"control_id")==id);
                stage="stop_deadline";const auto& deadline=member(stop,"deadline");need(deadline.IsNumber()&&std::isfinite(deadline.GetDouble()));
                const auto remaining=deadline.GetDouble()-monotonic();need(remaining>0&&remaining<=stop_ms/1000.+1);
                close_until=(std::min)(close_until,Clock::now()+std::chrono::milliseconds(static_cast<unsigned>(remaining*1000)));stop_decoded=true;break;
            }
            need(!health||health(health_user)==0);
            const auto pumped=session->pump(64,16);
            if(Clock::now()>=next_cta_publish){
              try {
                const auto observed=session->status();
                auto value=receipt("guanheng.execution.cta-observation.v1",id,expected_sha,false);auto& a=value.GetAllocator();
                value.AddMember("initializes",observed.initializes,a);value.AddMember("schedules",observed.schedules,a);
                value.AddMember("sessions",observed.sessions,a);value.AddMember("parser_quotes",observed.parser_quotes,a);
                value.AddMember("parser_connects",observed.parser_connects,a);value.AddMember("parser_closes",observed.parser_closes,a);
                value.AddMember("parser_logs",observed.parser_logs,a);
                publish(control/"cta-observation.json",value,true);
                const auto logging=native_log.status();
                auto log_state=receipt("guanheng.execution.native-log.v1",id,expected_sha,false);
                auto& l=log_state.GetAllocator();
                log_state.AddMember("initialized",logging.initialized,l);log_state.AddMember("file_opened",logging.file_opened,l);
                log_state.AddMember("attempted_records",logging.attempted_records,l);
                log_state.AddMember("write_failures",logging.write_failures,l);
                log_state.AddMember("truncated_records",logging.truncated_records,l);
                log_state.AddMember("max_file_bytes",guanheng::NativeRuntimeLog::file_bytes,l);
                log_state.AddMember("max_files",guanheng::NativeRuntimeLog::backup_files+1,l);
                publish(control/"native-log-status.json",log_state,true);
              }catch(...){
                // 可重建旁证沿原发布方式；失败不改变策略、金融状态或关闭时序。
                std::error_code error;fs::remove(control/"cta-observation.json.pending",error);
                fs::remove(control/"native-log-status.json.pending",error);
              }
              next_cta_publish=Clock::now()+std::chrono::seconds(1);
            }
            if(pumped<0||session->status().fault!=guanheng::CtaExecutionFault::None){
                // 有限枚举保留故障所在层；账户、配置及原始回报不进入进程诊断。
                std::fprintf(stderr,"execution_runtime_failure session=%u host=%u queue=%u\n",
                    static_cast<unsigned>(session->status().fault),static_cast<unsigned>(execution->status().fault),
                    static_cast<unsigned>(execution->command()->status().fault));std::fflush(stderr);need(false);
            }
            if(target_status){
                GhMsStatus value{};value.size=sizeof(value);need(target_status(&value)==0&&value.failure==0);
                if(value.setters>initial_setters){
                    // setter计数先出现，再读取active，确认带新目标的首次回调已经结束。
                    GhMsStatus completed{};completed.size=sizeof(completed);
                    need(target_status(&completed)==0&&completed.failure==0);
                    if(!completed.active){need(execution->pause_inserts(false));target_status=nullptr;}
                }
            }
            // 私有控制收据沿原进程身份发布，只记录读取可用性转换，不含账户正文。
            const auto read_state=execution->status().plugin;
            const int waiting=std::strcmp(read_state.reason,"qmt_read_source_waiting")==0?1:0;
            if(waiting!=last_read_waiting&&Clock::now()>=next_read_publish){
              try {
                auto value=receipt("guanheng.execution.read-status.v1",id,expected_sha,false);auto& a=value.GetAllocator();
                value.AddMember("waiting",waiting!=0,a);value.AddMember("writes_blocked",read_state.writes_blocked!=0,a);
                value.AddMember("queries",read_state.queries,a);value.AddMember("transitions",read_transitions++,a);
                publish(control/"read-status.json",value,true);last_read_waiting=waiting;
              }catch(...){
                // 可重建的可用性投影失败不改变原执行事实，固定间隔后再发布当前状态。
                std::error_code error;fs::remove(control/"read-status.json.pending",error);
                next_read_publish=Clock::now()+std::chrono::milliseconds(500);
              }
            }
            publish_broker(*execution,*environment);Sleep(2);
        }
        need(!stop_seen||stop_decoded);
        if(!fs::exists(control/"stop.json"))close_until=Clock::now()+std::chrono::milliseconds(stop_ms);
        if(recovery_enabled){
            stage="recovery_drain";
            int quiesced=1;while((quiesced=session->quiesce(100))==1){need(Clock::now()<close_until);Sleep(1);}need(quiesced==0);
            need(session->status().fault==guanheng::CtaExecutionFault::None&&execution->prepare_recovery());
            reconcile_own_orders(*execution,[&]{need(Clock::now()<close_until&&(!health||health(health_user)==0));},
                [&]{need(execution->pump(64,16)>=0&&execution->status().fault==guanheng::ExecutionHostFault::None);Sleep(1);});
            need(execution->begin_recovery());
            guanheng::StandardQmtRecoveryV1 state;need(execution->recovery(state)==0&&settled(*execution,state));
            recovery_armed=true;
        }
        success=true;
    }catch(...){
        try{throw;}catch(const ReadError& error){native_error=error.code;}catch(...){}
        {guanheng::ExecutionHostStatus observed;if(execution)observed=execution->status();
            // 固定阶段/枚举及原因摘要供私有诊断；不向输出复制来源正文或账户字段。
            const auto reason=sha(observed.plugin.reason);
            std::fprintf(stderr,"CTA failure stage=%s plugin_error=%d reason_sha256=%s\n",stage,observed.plugin.error,reason.c_str());
            try{
                if(!control.empty()&&fs::is_directory(control)&&!fs::exists(control/"failure.json")){
                    auto diagnostic=receipt("guanheng.execution.failure.v1",id,expected_sha,false);auto& a=diagnostic.GetAllocator();
                    diagnostic.AddMember("stage",rj::Value(stage,a),a);diagnostic.AddMember("plugin_error",observed.plugin.error,a);
                    diagnostic.AddMember("host_fault",static_cast<unsigned>(observed.fault),a);
                    diagnostic.AddMember("session_fault",session?static_cast<unsigned>(session->status().fault):0,a);
                    diagnostic.AddMember("native_error",native_error,a);
                    diagnostic.AddMember("reason_sha256",rj::Value(reason.c_str(),a),a);
                    // 原插件的有界错误原因只保留在受控Native收据，供定位真实读取失败；不进入公开状态。
                    diagnostic.AddMember("private_reason",rj::Value(observed.plugin.reason,a),a);
                    // 固定枚举/计数区分提交等待与owner队列首错，不复制账户、订单或来源正文。
                    rj::Value plugin_state(rj::kObjectType);
                    plugin_state.AddMember("phase",observed.plugin.phase,a); // 原Standard生命周期枚举。
                    plugin_state.AddMember("writes_blocked",observed.plugin.writes_blocked,a); // 原提交保护观察，0/1。
                    plugin_state.AddMember("stop_requested",observed.plugin.stop_requested,a); // 原owner停止请求，0/1。
                    diagnostic.AddMember("plugin_state",plugin_state,a);
                    if(execution)if(const auto bridge=execution->command()){
                        const auto queue=bridge->status();rj::Value state(rj::kObjectType);
                        state.AddMember("fault",static_cast<unsigned>(queue.fault),a); // 原ExecutionQueueFault枚举。
                        state.AddMember("accepting",queue.accepting,a); // 原队列是否继续准入。
                        state.AddMember("inflight",queue.inflight,a); // 原目标回调是否仍在执行。
                        state.AddMember("accepted",queue.accepted,a); // 已准入命令前沿，单位条。
                        state.AddMember("entered",queue.entered,a); // 已进入原执行器的命令前沿。
                        state.AddMember("delivered",queue.delivered,a); // 已正常返回的命令前沿。
                        state.AddMember("rejected",queue.rejected,a); // 原队列拒绝计数，单位次。
                        state.AddMember("queued_commands",static_cast<std::uint64_t>(queue.queued_commands),a); // 排队条数。
                        state.AddMember("payload_bytes",static_cast<std::uint64_t>(queue.payload_bytes),a); // 原在途预算字节数。
                        diagnostic.AddMember("execution_queue",state,a);
                    }
                    // 同批Standard冻结的首次截止旁证；固定字段不携账户/请求/异常原文。
                    guanheng::EventChainDiagnosticsV1 event_chain;
                    if(inspect_event_chain&&find_event_chain&&trader){
                        auto* api=find_event_chain(trader->getString("instance_id").c_str());
                        if(api)inspect_event_chain(api,&event_chain);
                    }
                    if(event_chain.captured){
                        const auto& d=event_chain;rj::Value event(rj::kObjectType);
                        event.AddMember("schema",rj::Value("guanheng.qmt-event-deadline.v1",a),a);
                        event.AddMember("phase",d.phase,a);
                        event.AddMember("queued",d.queued,a);
                        event.AddMember("ready",d.ready,a);
                        event.AddMember("outstanding",d.outstanding,a);
                        event.AddMember("callback_reserved",d.callback_reserved,a);
                        event.AddMember("callback_space",d.callback_space,a);
                        event.AddMember("attempts",d.attempts,a);
                        event.AddMember("drain_checks",d.drain_checks,a);
                        event.AddMember("drain_pending",d.drain_pending,a);
                        event.AddMember("worker_busy",d.worker_busy,a);
                        event.AddMember("worker_kind",d.worker_kind,a);
                        event.AddMember("worker_stage",d.worker_stage,a);
                        event.AddMember("read_outcome",d.read_outcome,a);
                        event.AddMember("read_stage",d.read_stage,a);
                        event.AddMember("transport_from_prior_retry",d.transport_from_prior_retry,a);
                        event.AddMember("transport_recovery",d.transport_recovery,a);
                        event.AddMember("transport_origin",d.transport_origin,a);
                        event.AddMember("transport_stage",d.transport_stage,a);
                        event.AddMember("native_error",d.native_error,a);
                        event.AddMember("http_status",d.http_status,a);
                        event.AddMember("send_attempted",d.send_attempted,a);
                        event.AddMember("response_complete",d.response_complete,a);
                        event.AddMember("read_cursor",d.read_cursor,a);
                        event.AddMember("handled_cursor",d.handled_cursor,a);
                        event.AddMember("after_sequence",d.after_sequence,a);
                        event.AddMember("page_index",d.page_index,a);
                        event.AddMember("page_count",d.page_count,a);
                        event.AddMember("task_id",d.task_id,a);
                        event.AddMember("worker_task_id",d.worker_task_id,a);
                        event.AddMember("transport_operation",d.transport_operation,a);
                        event.AddMember("elapsed_ms",d.elapsed_ms,a);
                        event.AddMember("remaining_ms",d.remaining_ms,a);
                        event.AddMember("worker_queue_wait_ms",d.worker_queue_wait_ms,a);
                        event.AddMember("worker_running_ms",d.worker_running_ms,a);
                        event.AddMember("last_event_queue_wait_ms",d.last_event_queue_wait_ms,a);
                        event.AddMember("last_event_running_ms",d.last_event_running_ms,a);
                        diagnostic.AddMember("event_chain",event,a);
                    }
                    publish(control/"failure.json",diagnostic);
                }
            }catch(...){/* 诊断失败仍沿原关闭责任，不替换最初失败阶段。 */}
        }
        if(!stop_deadline_fixed)close_until=Clock::now()+std::chrono::milliseconds(stop_ms);
    }
    try{
        for(auto& binding:unowned){need(binding.factory->deleteStrategy(binding.strategy));binding.strategy=nullptr;}
        do{const auto result=session?session->close(1000):execution?execution->close():0;
            if(result==0){closed=true;break;}if(result<0)break;Sleep(1);
        }while(Clock::now()<close_until);
        // join期间最后一个回调仍可锁存失败；终态须包含生产者全部退出后的健康事实。
        if(closed&&success){
            if(health&&health(health_user)!=0){success=false;stage="strategy_callback";}
            else if(session&&session->status().fault!=guanheng::CtaExecutionFault::None){
                success=false;stage=recovery_armed&&!recovery_ready?"recovery_state":"cta_close";
            }else if(recovery_enabled&&!recovery_ready){success=false;stage="recovery_state";}
        }
        if(closed&&!control.empty()&&fs::is_directory(control)&&!id.empty()){
            auto terminal=receipt("guanheng.execution.close-prepared.v1",id,expected_sha,true);terminal.AddMember("ok",success,terminal.GetAllocator());
            if(success)terminal.AddMember("error_code",rj::Value(rj::kNullType),terminal.GetAllocator());
            else terminal.AddMember("error_code",rj::Value(stage,terminal.GetAllocator()),terminal.GetAllocator());
            terminal.AddMember("recovery_ready",success&&recovery_ready,terminal.GetAllocator());publish(control/"close-prepared.json",terminal);
        }
    }catch(...){success=false;}
    if(closed&&lifecycle_started)
        publish_lifecycle(control,"lifecycle-finished.json","guanheng.execution.finished.v1",id,expected_sha,true);
    // 未确认关闭保留整树至进程回收；避免普通局部析构越过原截止或释放在途依赖。
    if(!closed)ExitProcess(3);
    native_log.close();
    if(native_log_attempted)try {
        const auto logging=native_log.status();
        auto value=receipt("guanheng.execution.native-log.v1",id,expected_sha,true);auto& a=value.GetAllocator();
        value.AddMember("initialized",logging.initialized,a);value.AddMember("file_opened",logging.file_opened,a);
        value.AddMember("attempted_records",logging.attempted_records,a);value.AddMember("write_failures",logging.write_failures,a);
        value.AddMember("truncated_records",logging.truncated_records,a);
        value.AddMember("max_file_bytes",guanheng::NativeRuntimeLog::file_bytes,a);
        value.AddMember("max_files",guanheng::NativeRuntimeLog::backup_files+1,a);
        publish(control/"native-log-status.json",value,true);
    } catch (...) { std::error_code error;fs::remove(control/"native-log-status.json.pending",error); }
    return success?0:1;
}

} // namespace
extern "C" {
uint32_t __cdecl gh_cta_runtime_abi_version(void){return 1;}
uint32_t __cdecl gh_cta_broker_abi_version(void){return 1;}
uint64_t __cdecl gh_cta_broker_layout(uint32_t id){return id==1?sizeof(GhCtaBrokerFacts):id==2?sizeof(GhCtaBrokerPosition):0;}
int32_t __cdecl gh_cta_broker_read(GhCtaBrokerFacts* facts,GhCtaBrokerPosition* rows,uint32_t capacity,uint32_t* written){
    if(!facts||facts->size!=sizeof(*facts)||facts->version!=1||!rows||!written||!capacity||capacity>4096)return -1;
    *written=0;const auto current=std::atomic_load(&broker_current);if(!current)return -2;
    if(current->positions.size()>capacity){*written=static_cast<uint32_t>(current->positions.size());return -5;}
    *facts=current->facts;std::copy(current->positions.begin(),current->positions.end(),rows);
    *written=static_cast<uint32_t>(current->positions.size());return 0;
}
uint32_t __cdecl gh_cta_broker_trades_abi_version(void){return 1;}
uint64_t __cdecl gh_cta_pending_order_layout(void){return sizeof(GhCtaPendingOrder);}
int32_t __cdecl gh_cta_pending_orders_read(GhCtaPendingOrder* rows,uint32_t capacity,uint32_t* written){
    if(!rows||!written||!capacity||capacity>4096)return -1;
    *written=0;const auto current=std::atomic_load(&broker_current);if(!current)return -2;
    if(current->pending_orders.size()>capacity){*written=static_cast<uint32_t>(current->pending_orders.size());return -5;}
    std::copy(current->pending_orders.begin(),current->pending_orders.end(),rows);
    *written=static_cast<uint32_t>(current->pending_orders.size());return 0;
}
uint64_t __cdecl gh_cta_broker_trades_layout(uint32_t id){
    return id==1?sizeof(GhCtaBrokerTradeFacts):id==2?sizeof(GhCtaBrokerTrade):
        id==3?sizeof(GhCtaBrokerTradeFactsV2):id==4?sizeof(GhCtaBrokerTradeV2):0;
}
int32_t __cdecl gh_cta_broker_trades_read(GhCtaBrokerTradeFacts* facts,GhCtaBrokerTrade* rows,uint32_t capacity,uint32_t* written){
    if(!facts||facts->size!=sizeof(*facts)||facts->version!=1||!rows||!written||!capacity||capacity>4096)return -1;
    *written=0;const auto current=std::atomic_load(&broker_current);if(!current)return -2;
    if(current->trades.size()>capacity){*written=static_cast<uint32_t>(current->trades.size());return -5;}
    *facts=current->trade_facts;std::copy(current->trades.begin(),current->trades.end(),rows);
    *written=static_cast<uint32_t>(current->trades.size());return 0;
}
int32_t __cdecl gh_cta_broker_trades_v2_read(GhCtaBrokerTradeFactsV2* facts,GhCtaBrokerTradeV2* rows,uint32_t capacity,uint32_t* written){
    if(!facts||facts->facts.size!=sizeof(*facts)||facts->facts.version!=2||!rows||!written||!capacity||capacity>4096)return -1;
    *written=0;const auto current=std::atomic_load(&broker_current);if(!current)return -2;
    if(current->trades_v2.size()>capacity){*written=static_cast<uint32_t>(current->trades_v2.size());return -5;}
    *facts=current->trade_facts_v2;std::copy(current->trades_v2.begin(),current->trades_v2.end(),rows);
    *written=static_cast<uint32_t>(current->trades_v2.size());return 0;
}
int32_t __cdecl gh_cta_run(uint32_t argc,const wchar_t* const* argv,GhCtaHealth health,void* user){
    if(argc!=9||!argv)return 2;
    for(uint32_t i=0;i<argc;++i)if(!argv[i])return 2;
    static std::atomic<bool> entered{false};bool expected=false;
    if(!entered.compare_exchange_strong(expected,true))return 2;
    try{return run_process(static_cast<int>(argc),argv,health,user);}catch(...){return 2;}
}
}
