// 显式配置的受管CTA产品入口；金融状态及执行算法由原WT拥有。
#include "CtaProcess.h"
#include "CtaExecutionSession.h"
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
    if(prior&&prior->completed_queries==status.plugin.queries&&prior->trade_facts.revision==status.broker_trade_revision)return;
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
    std::vector<std::set<std::string>> levels;unsigned nodes=0;
    bool scalar(){return ++nodes<=32768;}
    bool Null(){return scalar();}bool Bool(bool){return scalar();}bool Int(int){return scalar();}
    bool Uint(unsigned){return scalar();}bool Int64(std::int64_t){return scalar();}bool Uint64(std::uint64_t){return scalar();}
    bool Double(double v){return std::isfinite(v)&&scalar();}bool String(const char*,rj::SizeType,bool){return scalar();}
    bool Key(const char* v,rj::SizeType n,bool){return !levels.empty()&&levels.back().emplace(v,n).second;}
    bool StartObject(){levels.emplace_back();return levels.size()<=16&&scalar();}
    bool StartArray(){return StartObject();}bool EndObject(rj::SizeType){levels.pop_back();return true;}
    bool EndArray(rj::SizeType n){return EndObject(n);}
};
rj::Document parse(const std::string& body){
    need(body.find('\0')==std::string::npos);rj::MemoryStream input(body.data(),body.size());rj::Reader reader;Guard guard;
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
void publish(const fs::path& target,const rj::Value& value){
    const auto temporary=fs::path(target.wstring()+L".pending");const auto bytes=encode(value);
    Handle file;file.value=CreateFileW(temporary.c_str(),GENERIC_WRITE,0,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);
    need(file.value!=INVALID_HANDLE_VALUE);DWORD written=0;need(WriteFile(file.value,bytes.data(),static_cast<DWORD>(bytes.size()),&written,nullptr)&&written==bytes.size());
    need(FlushFileBuffers(file.value));need(CloseHandle(file.value));file.value=INVALID_HANDLE_VALUE;
    need(MoveFileExW(temporary.c_str(),target.c_str(),MOVEFILE_WRITE_THROUGH)!=0);
}
rj::Document receipt(const char* schema,const std::string& id,const std::string& config_sha,bool closed){
    rj::Document value(rj::kObjectType);auto& a=value.GetAllocator();
    value.AddMember("schema",rj::Value(schema,a),a);value.AddMember("control_id",rj::Value(id.c_str(),a),a);
    value.AddMember("config_sha256",rj::Value(config_sha.c_str(),a),a);value.AddMember("pid",static_cast<unsigned>(GetCurrentProcessId()),a);
    value.AddMember("closed",closed,a);return value;
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
bool settled(const guanheng::StandardQmtRecoveryV1& value){
    return value.query_first&&value.submissions_closed&&!value.open_group&&!value.unresolved_children
        &&!value.pending_commands&&!value.unsafe&&!value.active_orders;
}
void bootstrap_takeover(const rj::Value& input,const std::string& input_sha,const fs::path& output,
    const rj::Value& strategies,guanheng::StandardExecutionHost& execution,WTSBaseDataMgr& base,
    guanheng::ExecutionEnvironment& environment){
    // 接管只转换明确初值。原查询表核全部现存仓位，原WT继续拥有后续明细和绩效。
    keys(input,{"schema","strategy_id","strategy_version","source_sha256","captured_uptime_ms",
        "valid_until_uptime_ms","trading_date","performance_basis","positions","strategy_state"});
    const auto schema=text(input,"schema");const bool native_day=schema=="guanheng.cta-takeover.v2";
    need((native_day||schema=="guanheng.cta-takeover.v1")
        &&text(input,"strategy_id")=="resonance-regime-v1"&&text(input,"strategy_version")=="1.1.2"
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
        &&state.last_order_query&&state.last_position_query&&!state.active_orders);
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
    bool success=false,closed=false,stop_deadline_fixed=false;unsigned stop_ms=10000,native_error=0;
    const char* stage="configuration";
    try{
        need(std::wstring(argv[1])==L"--config"&&std::wstring(argv[3])==L"--control"
             &&std::wstring(argv[5])==L"--control-id"&&std::wstring(argv[7])==L"--config-sha256");
        config_path=absolute(fs::path(argv[2]).u8string());control=absolute(fs::path(argv[4]).u8string());
        id=fs::path(argv[6]).u8string();expected_sha=fs::path(argv[8]).u8string();
        need(id.size()==36&&expected_sha.size()==64&&fs::is_directory(control));
        need(!fs::exists(control/"ready.json")&&!fs::exists(control/"closed.json")&&!fs::exists(control/"close-prepared.json"));
        const auto raw=read(config_path,256*1024);need(sha(raw)==expected_sha);auto cfg=parse(raw);
        keys(cfg,{"schema_version","installation_root","output_directory","base_data","trader","executer","environment","data","parsers","strategies","budget","queue","recovery","takeover","observation_refresh"});
        need(text(cfg,"schema_version")=="guanheng.cta-execution.v1");
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
            const auto& selection=cfg["recovery"];keys(selection,{"mode"});const auto mode=text(selection,"mode",32);
            need(mode=="record_clean"||mode=="resume_clean");recovery_enabled=true;recovery_hooks.restore=mode=="resume_clean";
            need(text(member(cfg,"trader"),"order_context")=="query_first");
            need(member(member(cfg,"trader"),"savedata").IsBool()&&!cfg["trader"]["savedata"].GetBool());
            recovery_output=output;recovery_installation=installation_identity(root);
            rj::Document identity;identity.CopyFrom(cfg,identity.GetAllocator());identity.RemoveMember("recovery");
            recovery_config=sha(encode(identity));recovery_strategies.CopyFrom(member(cfg,"strategies"),recovery_strategies.GetAllocator());
            recovery_hooks.admit=[&]{
                physical(recovery_output);
                const auto marker=recovery_output/".cta-clean.json";
                need(!fs::exists(recovery_output/".cta-clean.json.pending"));
                need(!fs::exists(recovery_output/".cta-clean.prepared.json")
                    &&!fs::exists(recovery_output/".cta-clean.prepared.json.pending"));
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
                guanheng::StandardQmtRecoveryV1 state;need(execution->recovery(state)==0&&settled(state));
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
        stop_ms=number(budget,"stop_ms",1000,60000);const auto run_ms=number(budget,"run_ms",1000,86400000);
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
        functions.pump=plugin.get<decltype(functions.pump)>("pumpStandardQmtTrader");
        functions.inspect=plugin.get<decltype(functions.inspect)>("inspectStandardQmtTrader");
        functions.stop=plugin.get<decltype(functions.stop)>("stopStandardQmtTrader");
        functions.destroy=plugin.get<decltype(functions.destroy)>("deleteTrader");
        functions.submission={plugin.get<guanheng::BeginSubmissionFn>("beginStandardQmtSubmission"),
            plugin.get<guanheng::EndSubmissionFn>("endStandardQmtSubmission"),plugin.get<guanheng::InspectSubmissionFn>("inspectStandardQmtSubmission")};
        if(recovery_enabled){
            functions.close_submissions=plugin.get<decltype(functions.close_submissions)>("closeStandardQmtSubmissions");
            functions.recovery=plugin.get<decltype(functions.recovery)>("inspectStandardQmtRecovery");
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
        if(recovery_hooks.restore){
            guanheng::StandardQmtRecoveryV1 state;need(execution->recovery(state)==0);
            need(state.query_first&&!state.open_group&&!state.unresolved_children&&!state.pending_commands&&!state.unsafe
                &&state.last_order_query&&state.last_position_query&&!state.active_orders);
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
        stage="cta";session.reset(new guanheng::CtaExecutionSession(base,hot,*execution,unowned));unowned.clear();
        const auto& parsers=member(cfg,"parsers");need(parsers.IsArray());rj::Document parser_root(rj::kObjectType);
        parser_root.AddMember("parsers",rj::Value(parsers,parser_root.GetAllocator()),parser_root.GetAllocator());parser_config=load_variant(parser_root);
        need(session->initialize(env.get(),data.get(),parser_config->get("parsers"),output.string().c_str(),recovery_enabled?&recovery_hooks:nullptr));check_start();
        need(session->start());check_start();
        auto ready=receipt("guanheng.execution.ready.v1",id,expected_sha,false);publish(control/"ready.json",ready);stage="runtime";
        const auto run_until=Clock::now()+std::chrono::milliseconds(run_ms);
        bool stop_seen=false,stop_decoded=false;
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
            if(pumped<0||session->status().fault!=guanheng::CtaExecutionFault::None){
                // 有限枚举保留故障所在层；账户、配置及原始回报不进入进程诊断。
                std::fprintf(stderr,"execution_runtime_failure session=%u host=%u queue=%u\n",
                    static_cast<unsigned>(session->status().fault),static_cast<unsigned>(execution->status().fault),
                    static_cast<unsigned>(execution->command()->status().fault));std::fflush(stderr);need(false);
            }
            publish_broker(*execution,*environment);Sleep(2);
        }
        need(!stop_seen||stop_decoded);
        if(!fs::exists(control/"stop.json"))close_until=Clock::now()+std::chrono::milliseconds(stop_ms);
        if(recovery_enabled){
            stage="recovery_drain";
            int quiesced=1;while((quiesced=session->quiesce(100))==1){need(Clock::now()<close_until);Sleep(1);}need(quiesced==0);
            need(session->status().fault==guanheng::CtaExecutionFault::None&&execution->begin_recovery());
            guanheng::StandardQmtRecoveryV1 state;need(execution->recovery(state)==0);const auto barrier=state.next_task;
            need(execution->query_orders()==0);
            auto advance=[&]{need(Clock::now()<close_until&&(!health||health(health_user)==0));
                need(execution->pump(64,16)>=0&&execution->status().fault==guanheng::ExecutionHostFault::None);
                need(execution->recovery(state)==0&&!state.unsafe);Sleep(1);};
            while(state.last_order_query<=barrier)advance();
            const auto order_barrier=state.next_task;need(!state.active_orders&&execution->query_positions()==0);
            while(state.last_position_query<=order_barrier||!settled(state))advance();
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
    // 未确认关闭保留整树至进程回收；避免普通局部析构越过原截止或释放在途依赖。
    if(!closed)ExitProcess(3);
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
