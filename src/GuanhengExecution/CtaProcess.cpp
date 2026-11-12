#include "GuanhengCommon/AccountAttributionHooks.h"
// 显式配置的受管CTA产品入口；金融状态及执行算法由原WT拥有。
#include "CtaProcess.h"
#include "CtaExecutionSession.h"
#include "NativeRuntimeLog.h"
#include "GuanhengCommon/BoundedSignedHttp.h"
#include <mutex>
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
#include <utility>
#include <limits>

namespace fs=std::filesystem;namespace rj=rapidjson;
namespace {
// 插件工作线程借用当前进程日志。即使故障收尾未能排空，也先关闭借用再析构日志。
std::mutex request_log_mutex;
guanheng::NativeRuntimeLog* request_log=nullptr;
void log_request_rejection(const char* line) noexcept {
    try { std::lock_guard<std::mutex> lock(request_log_mutex);
        if(request_log)request_log->request_rejection(line);
    } catch (...) {}
}
}
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
guanheng::AttributionRegistration attribution_registration;
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
rj::Value* daily_publication(rj::Value& data){
    if(!data.IsObject()||!data.HasMember("store")||!data["store"].IsObject())return nullptr;
    auto& store=data["store"];
    if(!store.HasMember("module")||!store["module"].IsString()
        ||std::string(store["module"].GetString(),store["module"].GetStringLength())!="GuanhengRealtimeReader")return nullptr;
    if(!store.HasMember("daily")||!store["daily"].IsObject())return nullptr;
    auto& daily=store["daily"];
    return daily.HasMember("publication")?&daily["publication"]:nullptr;
}
// 比较时保留行情发布文件和来源父目录，同父目录下的发布代和派生缓存属于运行接线。
void normalize_publication_cache(rj::Document& value){
    auto* selected=value.HasMember("data")?daily_publication(value["data"]):nullptr;
    if(!selected)return;
    auto& publication=*selected;keys(publication,{"status_file","publication_file","cache_root","source_root"});
    for(const char* field:{"status_file","publication_file","cache_root"})absolute(text(publication,field));
    if(publication.HasMember("source_root")){
        const auto source=absolute(text(publication,"source_root"));
        const auto status=absolute(text(publication,"status_file"));
        if(status==source/"STATUS.json"&&source.parent_path()!=source.root_path()){
            const auto parent=source.parent_path().u8string();
            auto& allocator=value.GetAllocator();
            publication["status_file"].SetString("STATUS.json",allocator);
            publication["source_root"].SetString(parent.c_str(),static_cast<rj::SizeType>(parent.size()),allocator);
        }
    }
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
// 本机行情读取端口属于部署接线，其余解析器配置和认证角色继续参与身份比较。
void normalize_retained_parser_port(rj::Document& value){
    if(!value.HasMember("parsers")||!value["parsers"].IsArray())return;
    const std::string prefix="http://127.0.0.1:";
    for(auto& parser:value["parsers"].GetArray()){
        if(!parser.IsObject()||!parser.HasMember("module")||!parser["module"].IsString()
            ||parser["module"]!="ParserQMTHostRetainedV6"||!parser.HasMember("qmt")||!parser["qmt"].IsObject())continue;
        auto& qmt=parser["qmt"];
        if(!qmt.HasMember("base_url")||!qmt["base_url"].IsString())continue;
        auto url=std::string(qmt["base_url"].GetString(),qmt["base_url"].GetStringLength());
        if(!url.empty()&&url.back()=='/')url.pop_back();
        if(url.compare(0,prefix.size(),prefix)!=0)continue;
        const auto port=url.substr(prefix.size());
        if(port.empty()||port.size()>5||port.find_first_not_of("0123456789")!=std::string::npos)continue;
        const auto number=std::stoul(port);
        if(number>0&&number<=65535)qmt["base_url"].SetString("http://127.0.0.1",value.GetAllocator());
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
        normalize_retained_parser_port(*value);
        normalize_target_replacement(*value);
        if(value->HasMember("executer")&&(*value)["executer"].IsObject()){
            auto& executer=(*value)["executer"];
            if(executer.HasMember("policy")&&executer["policy"].IsObject())
                for(auto it=executer["policy"].MemberBegin();it!=executer["policy"].MemberEnd();++it){
                    auto& rule=it->value;if(!rule.IsObject()||!rule.HasMember("name")||!rule["name"].IsString())continue;
                    const std::string name=rule["name"].GetString();
                    if(name!="WtExeFact.WtStockMinImpactExeUnit"&&name!="WtExeFact.WtStockMinImpactBorrowedExeUnit")continue;
                    // 显式发行中的原生撤单参数；只移除比较副本，原件完整SHA继续校验。
                    // 分单数量随显式配置换代；原配置SHA和原委托身份保持。
                    if(rule.HasMember("lots")){
                        need(rule["lots"].IsNumber());const double lots=rule["lots"].GetDouble();
                        need(std::isfinite(lots)&&lots>0);rule.RemoveMember("lots");
                    }
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
            auto& python=parameters["python_strategy"];
            if(python.HasMember("market_window")){
                auto& window=python["market_window"];keys(window,{"path","max_age_seconds"});
                need(window.MemberCount()==2);absolute(text(window,"path"));
                const auto& age=member(window,"max_age_seconds");need(age.IsNumber());
                const double seconds=age.GetDouble();need(std::isfinite(seconds)&&seconds>=1&&seconds<=604800);
                // 原窗口路径和配置SHA保持；时效参数随显式部署换代。
                window.RemoveMember("max_age_seconds");
            }
            if(!python.HasMember("capital_account"))continue;
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
// 自有恢复准入归一化显式开关与运输引用；原账户、模型、账根继续逐项核验。
rj::Document permission_model(const rj::Value& config,unsigned depth=0){
    rj::Document current;current.CopyFrom(config,current.GetAllocator());current.RemoveMember("recovery");
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
rj::Document legacy_market_model(const rj::Value& config){
    // 历史运行代只提供实际账本配置；旧标记不再触发换标的回投。
    if(config.HasMember("role_replacement")){
        rj::Document archived;archived.CopyFrom(config,archived.GetAllocator());
        archived.RemoveMember("recovery");return archived;
    }
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

// 只读受控依赖原件；不重建Source权限或改写实际安装/Native配置。
std::string dependency_bytes(const rj::Value& reference,std::size_t maximum){
    keys(reference,{"file","sha256"});const auto raw=read(absolute(text(reference,"file")),maximum);
    need(sha(raw)==text(reference,"sha256",64));return raw;
}
std::pair<rj::Document,std::string> dependency_proof(const rj::Value& reference,std::size_t maximum){
    const auto raw=dependency_bytes(reference,maximum);return {parse(raw,std::min<std::size_t>(maximum,16*1024*1024)),raw};
}
void source_sort(rj::Value& value,rj::Document::AllocatorType& allocator){
    // Source绑定只含精确整数/文本；按原canonical排序对象键，原值保持。
    if(value.IsObject()){
        std::vector<std::string> names;for(auto it=value.MemberBegin();it!=value.MemberEnd();++it)names.emplace_back(it->name.GetString(),it->name.GetStringLength());
        std::sort(names.begin(),names.end());rj::Value sorted(rj::kObjectType);
        for(const auto& name:names){rj::Value key;key.SetString(name.c_str(),static_cast<rj::SizeType>(name.size()),allocator);
            rj::Value child;child.CopyFrom(value[name.c_str()],allocator);source_sort(child,allocator);sorted.AddMember(key,child,allocator);}
        value.Swap(sorted);
    }else if(value.IsArray()){for(auto& child:value.GetArray())source_sort(child,allocator);}
}
std::string source_identity(const rj::Value& value){
    rj::Document canonical;canonical.CopyFrom(value,canonical.GetAllocator());source_sort(canonical,canonical.GetAllocator());
    rj::StringBuffer buffer;rj::Writer<rj::StringBuffer> writer(buffer);need(canonical.Accept(writer));
    return sha({buffer.GetString(),buffer.GetSize()}); // 原Source使用UTF8规范正文，不能用Native业务ASCII转义替代。
}
rj::Document source_plan(const rj::Value& reference){
    auto plan=dependency_proof(reference,1024*1024);const auto expected=text(plan.first,"plan_sha256",64);
    // 原Owner canonical字节的ID不经另一套浮点JSON格式器重算；移除固定自身字段后核原SHA。
    auto body=plan.second;const auto token="\"plan_sha256\":\""+expected+"\"";const auto at=body.find(token);
    need(at!=std::string::npos&&body.find(token,at+token.size())==std::string::npos);
    if(at>0&&body[at-1]==',')body.erase(at-1,token.size()+1);
    else{need(at+token.size()<body.size()&&body[at+token.size()]==',');body.erase(at,token.size()+1);}
    need(sha(body)==expected);
    need(text(plan.first,"schema_version")=="qmt.trade-binding-extension-plan.v1");return std::move(plan.first);
}
rj::Document source_origin(const rj::Value& proof,const std::string& binding_sha){
    const auto identity=dependency_proof(member(proof,"origin_identity"),65536);
    const auto raw=dependency_bytes(member(proof,"origin_deployment"),16*1024*1024);
    auto plan=source_plan(member(proof,"plan"));auto deployment=parse(raw,16*1024*1024);
    const auto& host=member(deployment,"host");need(host.IsObject());
    // 只核原件身份，不在Native重复Source权限算法或复制任何凭据。
    const auto actual=absolute(text(host,"journal_path")).wstring();
    const auto stated=absolute(text(identity.first,"journal_path")).wstring();
    need(CompareStringOrdinal(actual.c_str(),static_cast<int>(actual.size()),stated.c_str(),static_cast<int>(stated.size()),TRUE)==CSTR_EQUAL
        &&source_identity(member(host,"trade_binding"))==text(identity.first,"trade_binding_sha256",64));
    keys(identity.first,{"schema","deployment_sha256","journal_path","trade_binding_sha256"});need(identity.first.MemberCount()==4);
    const auto left=absolute(text(identity.first,"journal_path")).wstring();const auto right=absolute(text(plan,"journal_path")).wstring();
    need(text(identity.first,"schema")=="qmt.trade-deployment-origin.v1"&&text(identity.first,"deployment_sha256",64)==sha(raw)
        &&text(identity.first,"trade_binding_sha256",64)==binding_sha
        &&CompareStringOrdinal(left.c_str(),static_cast<int>(left.size()),right.c_str(),static_cast<int>(right.size()),TRUE)==CSTR_EQUAL
        &&text(plan,"schema_version")=="qmt.trade-binding-extension-plan.v1");
    return plan;
}
int dependency_date(const rj::Value& value){
    need(value.IsString());const std::string s=value.GetString();need(s.size()==10&&s[4]=='-'&&s[7]=='-');
    for(std::size_t i=0;i<s.size();++i)if(i!=4&&i!=7)need(s[i]>='0'&&s[i]<='9');
    SYSTEMTIME day{};day.wYear=static_cast<WORD>(std::stoi(s.substr(0,4)));
    day.wMonth=static_cast<WORD>(std::stoi(s.substr(5,2)));day.wDay=static_cast<WORD>(std::stoi(s.substr(8,2)));
    FILETIME file{};need(SystemTimeToFileTime(&day,&file)!=0);return day.wYear*10000+day.wMonth*100+day.wDay;
}
std::vector<std::string> retired_target_symbols(const rj::Value& marker,const rj::Value& origin){
    if(!marker.HasMember("retired_targets"))return {};
    const auto& retirement=member(marker,"retired_targets");keys(retirement,{"strategy_id","symbols"});
    const auto& strategies=member(origin,"strategies");
    need(strategies.IsArray()&&strategies.Size()==1&&text(retirement,"strategy_id")==text(strategies[0],"id",63));
    const auto& symbols=member(retirement,"symbols");need(symbols.IsArray()&&!symbols.Empty());
    const auto& rows=member(member(member(origin,"data"),"store"),"symbols");need(rows.IsArray());
    std::set<std::string> selected;
    for(const auto& item:symbols.GetArray()){
        need(item.IsString());const std::string code(item.GetString(),item.GetStringLength());
        const auto prefix=code.compare(0,8,"SSE.ETF.")==0?8u:9u;
        need((prefix==8||code.compare(0,9,"SZSE.ETF.")==0)&&code.size()==prefix+6
            &&std::all_of(code.begin()+prefix,code.end(),[](char digit){return digit>='0'&&digit<='9';})
            &&selected.insert(code).second);
        for(const auto& row:rows.GetArray())need(text(row,"std_code")!=code);
    }
    return {selected.begin(),selected.end()};
}
void normalize_dependencies(rj::Document& current,const rj::Value& origin,const rj::Value& reference,
                            const std::string& origin_sha,const std::string& execution_symbol,bool confirmation,
                            const rj::Value* execution_securities,const std::vector<std::string>& retired_targets){
    auto proof=dependency_proof(reference,1024*1024);const auto& value=proof.first;
    keys(value,{"schema","origin_configuration_sha256","previous_installation","current_installation","reader_additions","contract_addition","contract_additions","contract_reference","source_extension"});
    const bool generic=execution_securities!=nullptr;
    need(generic||retired_targets.empty());
    need(value.MemberCount()==8&&value.HasMember(generic?"contract_additions":"contract_addition")
        &&text(value,"schema")== (generic?"guanheng.strategy-dependency-handoff.v2":"guanheng.strategy-dependency-handoff.v1")
        &&text(value,"origin_configuration_sha256",64)==origin_sha);
    std::string execution_code;
    if(!generic&&!execution_symbol.empty()){
        need(!confirmation&&execution_symbol.size()==14&&execution_symbol.compare(0,8,"SSE.ETF.")==0
            &&execution_symbol!="SSE.ETF.589680");
        execution_code=execution_symbol.substr(8);
        for(char digit:execution_code)need(digit>='0'&&digit<='9');
    }
    const auto& old_rows=member(member(member(origin,"data"),"store"),"symbols");
    need(old_rows.IsArray());
    std::set<std::string> declared;
    auto expected=parse("{\"rows\":[]}");
    if(generic){
        need(execution_securities->IsArray()&&!execution_securities->Empty());
        for(const auto& item:execution_securities->GetArray()){
            need(item.IsString());const std::string code(item.GetString(),item.GetStringLength());
            need(code.size()>=14&&declared.insert(code).second);
        }
        for(const auto& standard:declared){
            const bool shanghai=standard.compare(0,8,"SSE.ETF.")==0;
            const auto prefix=shanghai?8u:9u;
            need((shanghai||standard.compare(0,9,"SZSE.ETF.")==0)&&standard.size()==prefix+6);
            const auto code=standard.substr(prefix);
            need(std::all_of(code.begin(),code.end(),[](char digit){return digit>='0'&&digit<='9';}));
            const auto symbol=code+(shanghai?".SH":".SZ");
            const auto old=std::find_if(old_rows.Begin(),old_rows.End(),[&](const auto& row){return text(row,"std_code")==standard;});
            if(old!=old_rows.End())need(text(*old,"symbol")==symbol);
            else{
                auto& a=expected.GetAllocator();rj::Value row(rj::kObjectType);
                row.AddMember("std_code",rj::Value(standard.c_str(),a),a);
                row.AddMember("symbol",rj::Value(symbol.c_str(),a),a);
                expected["rows"].PushBack(row,a);
            }
        }
    }
    auto manifest=[](const rj::Value& ref,const rj::Value& config){
        const auto root=absolute(text(config,"installation_root"));
        need(absolute(text(ref,"file"))==root.parent_path()/"execution-install.json");
        auto result=dependency_proof(ref,256*1024);keys(result.first,{"schema","files"});
        need(text(result.first,"schema")=="guanheng.execution-install.v1");
        const auto& files=member(result.first,"files");need(files.IsObject()&&files.MemberCount()>0&&files.MemberCount()<=512);
        for(auto it=files.MemberBegin();it!=files.MemberEnd();++it){
            need(it->value.IsString()&&it->value.GetStringLength()==64);
            const auto name=std::string(it->name.GetString(),it->name.GetStringLength());const auto p=fs::u8path(name);
            need(!p.is_absolute()&&!p.has_root_name()&&name.find('\\')==std::string::npos&&name.find(':')==std::string::npos);
            for(const auto& part:p)need(part!=".."&&part!=".");
            for(char digit:std::string(it->value.GetString()))need((digit>='0'&&digit<='9')||(digit>='a'&&digit<='f'));
        }
        return std::move(result.first);
    };
    const auto previous=manifest(member(value,"previous_installation"),origin);
    const auto next=manifest(member(value,"current_installation"),current);
    const auto old_root=absolute(text(origin,"installation_root"));const auto root=absolute(text(current,"installation_root"));
    auto installed_body=[](const fs::path& folder,const rj::Value& manifest,const std::string& name){
        const auto path=installed(folder,name);for(auto parent=path;parent!=folder.parent_path();parent=parent.parent_path())physical(parent);
        const auto raw=read(path,16*1024*1024);const auto& files=member(manifest,"files");
        const auto key="app/"+name;need(files.HasMember(key.c_str())&&sha(raw)==text(files,key.c_str(),64));return raw;
    };
    const auto& base=member(current,"base_data");need(base==member(origin,"base_data")&&base.IsObject()&&base.HasMember("contracts"));
    for(auto it=base.MemberBegin();it!=base.MemberEnd();++it){
        need(it->value.IsString());const std::string name=it->value.GetString();
        const auto before=installed_body(old_root,previous,name);const auto after=installed_body(root,next,name);
        if(it->name!="contracts"){need(before==after);continue;}
        const auto old=parse(before);auto fresh=parse(after);
        const auto reference=dependency_proof(member(value,"contract_reference"),16*1024*1024);
        const auto schema=text(reference.first,"schema");need(schema=="guanheng.security-reference.v1"||schema=="guanheng.security-reference.v2"||schema=="guanheng.security-reference.v3");
        const auto validate_contract=[&](const std::string& exchange,const std::string& code,const rj::Value& contract){
            keys(contract,{"exchg","expiredate","name","opendate","product"});need(contract.MemberCount()==5);
            need(text(contract,"exchg")==exchange&&text(contract,"product")=="ETF"
                &&member(contract,"opendate").IsInt()&&member(contract,"expiredate").IsInt());
            const auto symbol=exchange+"."+code;
            const auto& security=member(member(reference.first,"securities"),symbol.c_str());
            keys(security,{"symbol","name","market","security_type","listed_on","expires_on","observed_at"});need(security.MemberCount()==7);
            need(text(security,"symbol")==symbol&&text(security,"market")==exchange&&text(security,"security_type")=="etf"
                &&text(security,"name",128)==text(contract,"name",128)
                &&dependency_date(member(security,"listed_on"))==member(contract,"opendate").GetInt()
                &&(member(security,"expires_on").IsNull()?20991231:dependency_date(security["expires_on"]))==member(contract,"expiredate").GetInt());
        };
        if(generic){
            const auto& claims=member(value,"contract_additions");need(claims.IsObject());
            rj::Document unclaimed;unclaimed.CopyFrom(claims,unclaimed.GetAllocator());
            for(const auto& standard:declared){
                const auto exchange=standard.substr(0,standard.find('.'));
                const auto code=standard.substr(standard.size()-6);
                const auto identity=exchange+"."+code;
                const auto& security=member(member(reference.first,"securities"),identity.c_str());
                need(text(security,"symbol")==identity&&text(security,"market")==exchange&&text(security,"security_type")=="etf");
                if(old.HasMember(exchange.c_str())&&member(old,exchange.c_str()).HasMember(code.c_str())){
                    const auto& prior_contract=member(member(old,exchange.c_str()),code.c_str());
                    need(text(prior_contract,"exchg")==exchange&&text(prior_contract,"product")=="ETF");
                    continue;
                }
                const auto& row=member(member(claims,exchange.c_str()),code.c_str());
                need(member(member(fresh,exchange.c_str()),code.c_str())==row);
                validate_contract(exchange,code,row);
                fresh[exchange.c_str()].RemoveMember(code.c_str());
                auto& unmatched=unclaimed[exchange.c_str()];unmatched.RemoveMember(code.c_str());
                if(unmatched.MemberCount()==0)unclaimed.RemoveMember(exchange.c_str());
                if(!old.HasMember(exchange.c_str())&&fresh[exchange.c_str()].MemberCount()==0)fresh.RemoveMember(exchange.c_str());
            }
            need(unclaimed.MemberCount()==0&&fresh==old);
            continue;
        }
        const auto& row=member(value,"contract_addition");
        need(!member(old,"SZSE").HasMember("159352")&&member(member(fresh,"SZSE"),"159352")==row);
        validate_contract("SZSE","159352",row);
        fresh["SZSE"].RemoveMember("159352");
        if(!execution_code.empty()){
            const auto& execution=member(member(fresh,"SSE"),execution_code.c_str());
            if(!member(old,"SSE").HasMember(execution_code.c_str())){
                validate_contract("SSE",execution_code,execution);
                fresh["SSE"].RemoveMember(execution_code.c_str());
            }
        }
        need(fresh==old);
    }
    need(member(current,"environment")==member(origin,"environment"));
    if(!retired_targets.empty())need(!text(member(origin,"environment"),"filters").empty());
    for(const char* key:{"filters","fees"}){
        const auto& env=member(origin,"environment");if(!env.HasMember(key))continue;
        need(env[key].IsString());const std::string name=env[key].GetString();
        if(name.empty())continue;
        const auto before=installed_body(old_root,previous,name),after=installed_body(root,next,name);
        if(std::strcmp(key,"filters")==0&&!retired_targets.empty()){
            auto prior_filters=parse(before);
            const auto expected_filter=parse("{\"action\":\"ignore\"}");
            for(const auto& code:retired_targets){
                need(member(member(prior_filters,"code_filters"),code.c_str())==expected_filter);
                prior_filters["code_filters"].RemoveMember(code.c_str());
            }
            need(parse(after)==prior_filters);
        }else need(before==after);
    }
    if(!generic)expected=parse("{\"rows\":[{\"std_code\":\"SSE.ETF.589680\",\"symbol\":\"589680.SH\"},{\"std_code\":\"SZSE.ETF.159352\",\"symbol\":\"159352.SZ\"}]}");
    if(!execution_code.empty()){
        const auto symbol=execution_code+".SH";
        expected["rows"][0]["std_code"].SetString(execution_symbol.c_str(),expected.GetAllocator());
        expected["rows"][0]["symbol"].SetString(symbol.c_str(),expected.GetAllocator());
    }
    if(!generic&&confirmation)expected["rows"].Erase(expected["rows"].Begin());
    const auto& additions=member(value,"reader_additions");need(additions==member(expected,"rows"));
    auto& rows=current["data"]["store"]["symbols"];need((generic||old_rows.Size()==8)&&rows.IsArray()&&rows.Size()==old_rows.Size()+additions.Size());
    std::set<std::string> standard,symbols;
    for(rj::SizeType i=0;i<rows.Size();++i){
        need(rows[i]==(i<old_rows.Size()?old_rows[i]:additions[i-old_rows.Size()]));
        need(standard.insert(text(rows[i],"std_code")).second&&symbols.insert(text(rows[i],"symbol")).second);
    }
    rows.CopyFrom(old_rows,current.GetAllocator());
    const auto& source=member(value,"source_extension");const auto& old_trader=member(origin,"trader");auto& trader=current["trader"];
    const char* names[]={"base_url","binding_sha256","instance_id","key_id_env","hmac_secret_env"};
    if(source.IsNull()){
        for(auto key:names)need(trader.HasMember(key)==old_trader.HasMember(key)&&(!trader.HasMember(key)||trader[key]==old_trader[key]));
    }else{
        keys(source,{"previous_version","current_version","adoption_receipt","transport","plan","origin_deployment","origin_identity"});need(source.MemberCount()==7);
        const auto& transport=member(source,"transport");keys(transport,{"base_url","binding_sha256","instance_id","key_id_env","hmac_secret_env"});need(transport.MemberCount()==5);
        for(auto key:names)need(old_trader.HasMember(key)&&trader.HasMember(key)&&transport[key]==trader[key]);
        auto previous=dependency_proof(member(source,"previous_version"),1024*1024);
        auto next=dependency_proof(member(source,"current_version"),1024*1024);
        auto adoption=dependency_proof(member(source,"adoption_receipt"),65536);const auto& receipt=adoption.first;
        const auto plan=source_origin(source,text(old_trader,"binding_sha256",64));
        need(member(plan,"expected_version")==member(previous.first,"version")&&member(plan,"new_identity")==member(next.first,"identity")
            &&member(plan,"new_profile")==member(next.first,"profile")
            &&text(member(plan,"protected_facts"),"facts_sha256",64)==text(next.first,"protected_facts_sha256",64)
            &&text(plan,"plan_sha256",64)==text(next.first,"plan_sha256",64));
        keys(receipt,{"schema_version","version","identity_sha256","plan_sha256","adopted"});need(receipt.MemberCount()==5);
        need(text(previous.first,"schema_version")=="qmt.trade-binding-extension.v1"&&text(next.first,"schema_version")=="qmt.trade-binding-extension.v1"
            &&member(previous.first,"version").IsInt64()&&member(next.first,"version").IsInt64()&&member(previous.first,"version").GetInt64()>=1
            &&member(previous.first,"version").GetInt64()<std::numeric_limits<int64_t>::max()
            &&member(next.first,"version").GetInt64()==member(previous.first,"version").GetInt64()+1
            &&text(next.first,"parent_sha256",64)==sha(previous.second)
            &&text(receipt,"schema_version")=="qmt.trade-binding-extension.v1"&&member(receipt,"adopted").IsTrue()
            &&member(receipt,"version").IsInt64()&&receipt["version"]==next.first["version"]
            &&text(receipt,"identity_sha256",64)==sha(next.second)&&text(receipt,"plan_sha256",64)==text(next.first,"plan_sha256",64)
            &&source_identity(member(member(previous.first,"identity"),"trade_binding"))==text(old_trader,"binding_sha256",64)
            &&source_identity(member(member(next.first,"identity"),"trade_binding"))==text(trader,"binding_sha256",64));
        for(char digit:text(receipt,"plan_sha256",64))need((digit>='0'&&digit<='9')||(digit>='a'&&digit<='f'));
        for(auto key:names)trader[key].CopyFrom(old_trader[key],current.GetAllocator());
    }
    current["installation_root"].CopyFrom(member(origin,"installation_root"),current.GetAllocator());
}
std::string extension_instance_name(const rj::Value& row){
    auto id=text(row,"id",63);
    const auto ascii_alnum=[](char ch){return (ch>='0'&&ch<='9')||(ch>='A'&&ch<='Z')||(ch>='a'&&ch<='z');};
    need(!id.empty()&&ascii_alnum(id.front())&&std::all_of(id.begin(),id.end(),[&](char ch){
        return ascii_alnum(ch)||ch=='_'||ch=='-';
    }));
    std::transform(id.begin(),id.end(),id.begin(),[](unsigned char ch){return static_cast<char>(std::toupper(ch));});
    need(id!="CON"&&id!="PRN"&&id!="AUX"&&id!="NUL");
    need(!(id.size()==4&&(id.compare(0,3,"COM")==0||id.compare(0,3,"LPT")==0)&&id[3]>='1'&&id[3]<='9'));
    return id;
}
rj::Document extension_row(const rj::Value& marker){
    return std::move(dependency_proof(member(marker,"added_strategy"),64*1024).first);
}
bool positive_capital(const std::string& amount){
    const auto point=amount.find('.');
    const auto whole=point==std::string::npos?amount.size():point;
    if(whole==0||whole>25||(point!=std::string::npos&&(amount.size()-point<2||amount.size()-point>3)))return false;
    bool positive=false;
    for(std::size_t i=0;i<amount.size();++i){
        if(i==point)continue;
        if(amount[i]<'0'||amount[i]>'9')return false;
        if(amount[i]!='0')positive=true;
    }
    return positive;
}
// 准入调用点持有原输出租约，券商O/P/A及原委托责任已沿原流程核查。
rj::Document market_model(const rj::Value& config){
    if(!config.HasMember("strategy_extension_origin"))return legacy_market_model(config);
    const auto& marker=member(config,"strategy_extension_origin");
    keys(marker,{"schema","file","sha256","added_strategy","dependency_handoff","retired_targets"});
    need(text(marker,"schema")=="guanheng.strategy-extension-origin.v1");
    const auto path=absolute(text(marker,"file"));need(path.filename()=="execution.json");
    const auto raw=read(path,256*1024);need(sha(raw)==text(marker,"sha256",64));
    const auto original=parse(raw);need(!original.HasMember("strategy_extension_origin"));
    const auto added=extension_row(marker);const auto& p=member(member(added,"parameters"),"python_strategy");
    const auto version=text(p,"strategy_version",64);
    const auto confirmation=version=="0.3.0a1"; // 旧版证券接续材料的形状由模型版本选择。
    need(!version.empty()&&(!confirmation||!p.HasMember("execution_symbol_589680"))
        &&text(p,"schema")=="guanheng.original-live-cta.v1"
        &&positive_capital(text(p,"initial_capital_cny",28))&&text(p,"state_mode")=="new"
        &&text(p,"activation_mode")=="signals-from-activation");
    const auto& prior=member(original,"strategies");const auto& rows=member(config,"strategies");
    need(prior.IsArray()&&prior.Size()==1&&rows.IsArray()&&rows.Size()==2);
    const auto retained_id=text(prior[0],"id",63);
    need(extension_instance_name(prior[0])!=extension_instance_name(added)
        &&text(member(member(prior[0],"parameters"),"python_strategy"),"schema")=="guanheng.retained-cta.v1");
    rj::Document projected;projected.CopyFrom(config,projected.GetAllocator());projected.RemoveMember("strategy_extension_origin");
    auto& keep=projected["strategies"];unsigned removed=0,retained=0;
    for(auto it=keep.Begin();it!=keep.End();){
        if(*it==added){it=keep.Erase(it);++removed;}
        else{need(text(*it,"id")==retained_id);++retained;++it;}
    }
    need(removed==1&&retained==1);
    const auto retirements=retired_target_symbols(marker,original);
    need(!config.HasMember("role_replacement"));
    if(marker.HasMember("dependency_handoff"))normalize_dependencies(projected,original,marker["dependency_handoff"],
        text(marker,"sha256",64),p.HasMember("execution_symbol_589680")?text(p,"execution_symbol_589680",14):std::string{},
        confirmation,p.HasMember("execution_securities")?&p["execution_securities"]:nullptr,retirements);
    else need(retirements.empty());
    if(original.HasMember("role_replacement")){
        need(!retirements.empty());
        // 比较副本保留原标记；本代正式配置已移除。
        auto& allocator=projected.GetAllocator();
        projected.AddMember("role_replacement",rj::Value(original["role_replacement"],allocator),allocator);
    }
    auto before=legacy_market_model(original);auto after=legacy_market_model(projected);
    before.RemoveMember("recovery");after.RemoveMember("recovery");
    need(same_business(before,after));return legacy_market_model(projected);
}
bool compatible_model(const rj::Value& previous,const rj::Value& current){
    // 后继双ctx必须保留冻结新增行及扩展原件身份；投影不能隐藏策略删除或参数变更。
    if(previous.HasMember("strategy_extension_origin")){
        need(current.HasMember("strategy_extension_origin"));
        rj::Document before,after;before.CopyFrom(previous["strategy_extension_origin"],before.GetAllocator());
        after.CopyFrom(current["strategy_extension_origin"],after.GetAllocator());
        need(!before.HasMember("dependency_handoff")||after.HasMember("dependency_handoff"));
        before.RemoveMember("dependency_handoff");after.RemoveMember("dependency_handoff");need(before==after);
        // market_model 逐代核冻结行与实际配置相等，前后引用已在上方逐字节比较。
    }
    auto before=market_model(previous);auto after=market_model(current);
    before.RemoveMember("recovery");after.RemoveMember("recovery");
    return same_business(before,after);
}
rj::Document transition_state_identity(const fs::path& output,const rj::Value& current,const rj::Value& owner){
    auto files=state_identity(output,member(owner,"strategies"));
    for(const auto& row:member(current,"strategies").GetArray()){
        const auto id=text(row,"id",63);bool existed=false;
        for(const auto& old:member(owner,"strategies").GetArray())if(text(old,"id",63)==id)existed=true;
        if(!existed){
            need(current.HasMember("strategy_extension_origin")
                &&row==extension_row(current["strategy_extension_origin"]));
            // Windows原加载器按大小写不敏感路径打开；直接核同一路径，不能借异大小写隐匿旧ctx。
            need(!fs::exists(output/"stradata"/(id+".json"))
                &&!fs::exists(output/"userdata"/("ud_"+id+".json")));
        }
    }
    return files;
}
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
    need(compatible_model(prior_config,identity));
    rj::Document state_owner;state_owner.CopyFrom(prior_config,state_owner.GetAllocator()); // 金融文件属于真实源ctx集合，新增ctx不伪造原文件。
    const auto previous=absolute(text(transition,"predecessor_control_directory"));physical(previous);
    const bool initialization_abort=transition.HasMember("initialization_abort");
    need(!initialization_abort||(!fs::exists(previous/"ready.json")&&!transition.HasMember("restoration")));
    const auto ready_raw=read(previous/(initialization_abort?"failure.json":"ready.json"),4096);const auto ready=parse(ready_raw);
    const bool clean_transition=fs::exists(previous/"closed.json");
    need(!transition.HasMember("restoration")||clean_transition);
    const bool lost_transition=!clean_transition&&!fs::exists(previous/"close-prepared.json")
        &&!fs::exists(previous/"failure.json")&&fs::exists(previous/"owner-loss.json");
    need(text(ready,"schema")== (initialization_abort?"guanheng.execution.failure.v1":"guanheng.execution.ready.v1"));
    auto same_origin=[&](const rj::Value& value){
        need(text(value,"config_sha256")==prior_sha&&text(value,"control_id")==text(ready,"control_id")
            &&member(value,"pid")==member(ready,"pid"));
    };
    same_origin(ready);
    fs::path abort_claim;
    if(initialization_abort){
        need(!clean_transition&&!lost_transition&&text(ready,"stage")=="cta");
        const auto closed=parse(read(previous/"close-prepared.json",4096));same_origin(closed);
        need(text(closed,"schema")=="guanheng.execution.close-prepared.v1"&&member(closed,"closed").IsTrue()
            &&member(closed,"ok").IsFalse()&&member(closed,"recovery_ready").IsFalse());
        const auto& reference=member(transition,"initialization_abort");keys(reference,{"file","sha256"});
        need(absolute(text(reference,"file"))==previous/"reconciled.json");
        const auto admitted_raw=read(previous/"reconciled.json",256*1024);
        need(sha(admitted_raw)==text(reference,"sha256",64));const auto admitted=parse(admitted_raw);same_origin(admitted);
        const auto admission_kind=text(admitted,"admission_kind");
        const bool aborted_loss=admission_kind=="process_lost_reconciled";
        need(text(admitted,"schema")=="guanheng.cta-reconciled.v1"&&(aborted_loss||admission_kind=="clean_transition")
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
        auto source=parse(source_raw);
        if(aborted_loss){
            // 仅沿已验证的异常退出认领接续，实际账户、执行权限和业务配置逐项保持。
            need(member(source,"trader")==member(prior_config,"trader")&&member(source,"trader")==member(current,"trader"));
            const auto& queue=member(ready,"execution_queue");
            keys(queue,{"fault","accepting","inflight","accepted","entered","delivered","rejected","queued_commands","payload_bytes"});
            need(member(ready,"closed").IsFalse()&&member(queue,"accepting").IsFalse()&&member(queue,"inflight").IsFalse());
            for(const auto* name:{"fault","accepted","entered","delivered","rejected","queued_commands","payload_bytes"})
                need(member(queue,name).IsUint64()&&member(queue,name).GetUint64()==0);
            need(!fs::exists(previous/"lifecycle-started.json")
                &&!fs::exists(origin/"closed.json")&&!fs::exists(origin/"close-prepared.json")&&!fs::exists(origin/"failure.json"));
            const auto snapshot_sha=text(admitted,"transition_sha256",64);
            need(absolute(text(snapshot,"predecessor_configuration"))==origin/"execution.json"
                &&text(admitted,"successor_installation_sha256")==text(snapshot,"successor_installation_sha256")
                &&text(admitted,"successor_installation_sha256")==text(transition,"predecessor_installation_sha256")
                &&read(output/(".cta-reconciled-"+snapshot_sha+".json"),256*1024)==admitted_raw);
            const auto source_ready_raw=read(origin/"ready.json",4096);const auto source_ready=parse(source_ready_raw);
            const auto loss=parse(read(origin/"owner-loss.json",4096));
            const auto installed=parse(read(origin/"installation-identity.json",4096));
            for(const auto* item:{&source_ready,&loss,&installed})
                need(text(*item,"control_id")==origin.filename().u8string()&&text(*item,"config_sha256")==sha(source_raw)
                    &&member(*item,"pid")==member(source_ready,"pid"));
            need(text(source_ready,"schema")=="guanheng.execution.ready.v1"
                &&text(loss,"schema")=="guanheng.execution.owner-loss.v1"&&text(loss,"reason")=="process_lost"
                &&text(loss,"ready_sha256",64)==sha(source_ready_raw)
                &&text(installed,"schema")=="guanheng.execution-installation.v1"
                &&text(installed,"installation_sha256")==text(snapshot,"predecessor_installation_sha256"));
            const auto& source_pid=member(source_ready,"pid");need(source_pid.IsUint()&&source_pid.GetUint()>0);
            Handle source_process;source_process.value=OpenProcess(SYNCHRONIZE,FALSE,source_pid.GetUint());
            if(source_process.value)need(WaitForSingleObject(source_process.value,0)==WAIT_OBJECT_0);
            else need(GetLastError()==ERROR_INVALID_PARAMETER);
            need(previous.filename().u8string()==text(ready,"control_id"));
            abort_claim=output/(".cta-initialization-abort-"+previous.filename().u8string()+".json");
            need(!fs::exists(abort_claim)&&!fs::exists(fs::path(abort_claim.wstring()+L".pending")));
        }else need(member(member(source,"trader"),"writes_enabled").IsFalse()
            &&member(member(current,"trader"),"writes_enabled").IsFalse());
        source.RemoveMember("recovery");need(compatible_model(source,identity));
        state_owner.CopyFrom(source,state_owner.GetAllocator());
        if(!aborted_loss){
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
                    &&state_identity(archive,member(prior_config,"strategies"))==member(origin,"files"));
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
                    &&compatible_model(parse(snapshot_raw),current));
                state_owner=parse(snapshot_raw);
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
        &&encode(transition_state_identity(output,current,state_owner))==encode(member(transition,"state_files")));
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
    if(!abort_claim.empty())publish(abort_claim,proof);
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
    const auto attribution=attribution_registration.value();
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
        { std::lock_guard<std::mutex> lock(request_log_mutex);request_log=&native_log; }
        const auto raw=read(config_path,256*1024);need(sha(raw)==expected_sha);auto cfg=parse(raw);
        keys(cfg,{"schema_version","installation_root","output_directory","base_data","trader","executer","environment","data","parsers","strategies","budget","queue","recovery","takeover","observation_refresh","market_input_origin","execution_permission_origin","strategy_extension_origin"});
        need(text(cfg,"schema_version")=="guanheng.cta-execution.v1");
        std::string reader_cache_path;
        if(const auto* publication=cfg.HasMember("data")?daily_publication(cfg["data"]):nullptr){
            // 原配置用于账本证明；只有交给本代 Reader 的配置使用控制代的独占缓存。
            stage="market_cache";
            absolute(text(*publication,"cache_root"));
            const auto reader_cache=control/"daily-cache";
            for(auto parent=reader_cache.parent_path();!parent.empty();parent=parent.parent_path()){
                physical(parent);need(fs::is_directory(parent));
                if(parent==parent.root_path())break;
            }
            need(!fs::exists(fs::symlink_status(reader_cache)));
            // 原 Reader 链使用 Windows 窄路径；先确认转码仍指向同一物理路径。
            reader_cache_path=reader_cache.string();
            need(fs::path(reader_cache_path)==reader_cache);
            stage="configuration";
        }
        if(cfg.HasMember("execution_permission_origin")){
            need(text(member(cfg,"recovery"),"mode")!="record_clean");market_model(cfg);
        }
        if(cfg.HasMember("market_input_origin")){
            need(text(member(cfg,"recovery"),"mode")!="record_clean");market_model(cfg);
        }
        if(cfg.HasMember("strategy_extension_origin")){
            const auto mode=text(member(cfg,"recovery"),"mode");
            need(mode=="resume_clean"||mode=="resume_reconciled");market_model(cfg);
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
        if(!reader_cache_path.empty()){
            auto* publication=data->get("store")->get("daily")->get("publication");
            need(publication&&publication->append("cache_root",reader_cache_path.c_str()));
        }
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
        if(attribution){
            functions.attribution_version=plugin.get<decltype(functions.attribution_version)>("standardQmtAttributionVersion");
            functions.attribution_configure=plugin.get<decltype(functions.attribution_configure)>("configureStandardQmtAttribution");
        }
        functions.find=plugin.get<decltype(functions.find)>("findStandardQmtTrader");
        find_event_chain=functions.find;
        inspect_event_chain=reinterpret_cast<decltype(inspect_event_chain)>(GetProcAddress(plugin.module,"inspectStandardQmtEventChain"));
        const auto request_sink=reinterpret_cast<guanheng::SetRequestRejectionSink>(
            GetProcAddress(plugin.module,"setStandardQmtRequestRejectionSink"));
        if(request_sink)request_sink(log_request_rejection);
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
        if(attribution)need(execution->configure_attribution(attribution));
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
        std::string retirement_strategy;
        std::vector<std::string> retirements;
        if(cfg.HasMember("strategy_extension_origin")&&cfg["strategy_extension_origin"].HasMember("retired_targets")){
            const auto& marker=cfg["strategy_extension_origin"];
            const auto prior_bytes=read(absolute(text(marker,"file")),256*1024);
            need(sha(prior_bytes)==text(marker,"sha256",64));
            retirements=retired_target_symbols(marker,parse(prior_bytes));
            retirement_strategy=text(marker["retired_targets"],"strategy_id",63);
            const auto& recovery=member(cfg,"recovery");
            const auto mode=text(recovery,"mode");
            need(mode=="resume_clean"||mode=="resume_reconciled");
            bool already_active=mode=="resume_clean"; // 原 clean 准入稍后核实同配置实际状态。
            if(mode=="resume_reconciled"){
                const auto transition=dependency_proof(member(recovery,"transition"),1024*1024);
                const auto old_bytes=read(absolute(text(transition.first,"predecessor_configuration")),256*1024);
                need(sha(old_bytes)==text(transition.first,"predecessor_configuration_sha256",64));
                const auto old=parse(old_bytes);
                already_active=old.HasMember("strategy_extension_origin")
                    &&old["strategy_extension_origin"].HasMember("retired_targets")
                    &&old["strategy_extension_origin"]["retired_targets"]==marker["retired_targets"];
            }
            if(!already_active){
                need(execution->broker_observation().positions_known);
                auto* rows=execution->orders("");need(rows!=nullptr);
                struct OrdersOwner{wtp::OrderMap* value;~OrdersOwner(){value->release();}} owned{rows};
                for(const auto& standard:retirements){
                    const auto market=standard.substr(0,standard.find('.')),code=standard.substr(standard.size()-6);
                    need(base.getContract(code.c_str(),market.c_str())
                        &&execution->position(standard.c_str())==0&&execution->undone(standard.c_str())==0);
                    for(auto it=rows->begin();it!=rows->end();++it){
                        const auto* order=static_cast<wtp::WTSOrderInfo*>(it->second);
                        need(!order->isAlive()||market!=order->getExchg()||code!=order->getCode());
                    }
                }
            }
        }
        stage="strategies";const auto& strategies=member(cfg,"strategies");need(strategies.IsArray()&&strategies.Size()>0&&strategies.Size()<=64);
        factories.reserve(strategies.Size());parameters.reserve(strategies.Size());unowned.reserve(strategies.Size());
        std::set<HMODULE> attribution_factories; // 同一实际DLL仅注册一次，多个ctx继续共用原Factory。
        for(const auto& item:strategies.GetArray()){
            keys(item,{"id","module","factory","name","parameters"});check_start();
            StrategyFactory owner;owner.library.reset(new Library(installed(root,text(item,"module"))));
            if(attribution&&attribution_factories.insert(owner.library->module).second){
                const auto version=owner.library->get<decltype(&gh_ms_attribution_abi_version)>("gh_ms_attribution_abi_version");
                const auto configure=owner.library->get<decltype(&gh_ms_attribution_configure)>("gh_ms_attribution_configure");
                need(version()==1&&configure(attribution.callback,attribution.user)==0);
            }
            owner.value=owner.library->get<FuncCreateStraFact>("createStrategyFact")();need(owner.value!=nullptr);
            factories.push_back(std::move(owner));need(text(item,"factory")==factories.back().value->getName());
            parameters.push_back(load_variant(member(item,"parameters")));
            auto* strategy=factories.back().value->createStrategy(text(item,"name").c_str(),text(item,"id",63).c_str());need(strategy!=nullptr);
            unowned.push_back({strategy,factories.back().value,parameters.back().get(),
                retirement_strategy==text(item,"id",63)?retirements:std::vector<std::string>{}});
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
    { std::lock_guard<std::mutex> lock(request_log_mutex);request_log=nullptr; }
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
uint32_t __cdecl gh_cta_attribution_abi_version(void){return 1;}
uint64_t __cdecl gh_cta_attribution_layout(uint32_t id){return id==1?sizeof(GhAttributionEventV1):id==2?sizeof(GhAttributionReplyV1):0;}
int32_t __cdecl gh_cta_attribution_configure(GhAttributionCallbackV1 callback,void* user){
    try{return attribution_registration.configure(callback,user);}catch(...){return -1;}
}
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
    try{attribution_registration.freeze();return run_process(static_cast<int>(argc),argv,health,user);}catch(...){return 2;}
}
}
