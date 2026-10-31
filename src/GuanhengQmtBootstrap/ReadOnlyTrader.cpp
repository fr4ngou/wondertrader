#include "ReadOnlyTrader.h"
#include "JsonBoundary.h"
#include "HttpMapping.h"
#include "ShmAccountMapping.h"
#include "ViewSchemaV2.h"
#include "Includes/WTSVariant.hpp"
#include "Includes/WTSCollection.hpp"
#include "Includes/WTSTradeDef.hpp"
#include "Includes/WTSContractInfo.hpp"
#include "Includes/IBaseDataMgr.h"
#include <rapidjson/document.h>
#include <rapidjson/writer.h>
#include <rapidjson/stringbuffer.h>
#include <rapidjson/reader.h>
#include <rapidjson/memorystream.h>
#include <vector>
#include <array>
#include <cstdlib>
#include <algorithm>
#include <limits>
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cmath>
#include <cstring>
#include <deque>
#include <fstream>
#include <map>
#include <mutex>
#include <set>
#include <stdexcept>
#include <type_traits>

namespace guanheng { namespace bootstrap {
namespace {
using Clock = std::chrono::steady_clock;
// 此固定MSVC制品与Scan共享同一进程steady纳秒epoch；拒绝未经核验的时钟表示。
static_assert(std::is_same<Clock::duration,std::chrono::nanoseconds>::value,"runtime_deadline_ns requires native steady nanoseconds");
using Json = rapidjson::Value;
std::mutex registry_mutex;
std::atomic<std::uint64_t> next_instance_generation{1};
std::map<wtp::ITraderApi*, ReadOnlyTrader*> objects;
std::map<std::string, ReadOnlyTrader*> instances;
const char* stages[] = {"positions", "orders", "trades", "account"};
constexpr std::size_t max_file_bytes = protocol::fixture_bytes;
constexpr std::uint32_t max_rows = protocol::max_rows, max_queue = 16, max_pump = 32;
void require(bool yes, const char* reason) { if (!yes) throw std::runtime_error(reason); }
const Json& member(const Json& v, const char* key)
{ require(v.IsObject() && v.HasMember(key), "来源缺少必需字段"); return v[key]; }
std::string text(const Json& v, const char* key, std::size_t cap = 63)
{
    const auto& x = member(v, key);
    require(x.IsString() && x.GetStringLength() > 0 && x.GetStringLength() <= cap, "来源文本长度或类型错误");
    require(std::strlen(x.GetString()) == x.GetStringLength(), "来源文本含NUL");
    return {x.GetString(), x.GetStringLength()};
}
double number(const Json& v, const char* key, bool integral = false)
{
    const auto& x = member(v, key); require(x.IsNumber(), "来源数值类型错误");
    double n = x.GetDouble();
    require(std::isfinite(n) && n >= 0 && n <= 9007199254740991.0 && (!integral || std::floor(n) == n), "来源数值或数量非法");
    return n;
}
std::string encode(const Json& v)
{ rapidjson::StringBuffer b; rapidjson::Writer<rapidjson::StringBuffer> w(b); v.Accept(w); return {b.GetString(), b.GetSize()}; }
void parse(rapidjson::Document& d,const std::string& s){parse_json(d,s);}
std::string optional_tag(const Json& row)
{
    if(!row.HasMember("user_tag"))return {};
    auto& v=row["user_tag"];
    require(v.IsString() && v.GetStringLength()<=63 && !std::memchr(v.GetString(),0,v.GetStringLength()),"来源标签长度或类型错误");
    return {v.GetString(),v.GetStringLength()};
}
// 所有标签都是来源事实，只有本fixture显式证明且命名空间/十进制编号完整匹配才授管理投影。
// 0和UINT32_MAX在此接缝保守排除；原doEntrust用UINT_MAX表示失败，保持哨兵隔离。
std::uint32_t owned_local_id(const Json& row,const std::string& tag,const std::string& adapter,const std::string& oid)
{
    const auto prefix="otp."+adapter+".";
    if(tag.compare(0,prefix.size(),prefix)!=0)return 0;
    auto suffix=tag.substr(prefix.size());
    if(suffix.empty() || suffix.size()>10 || suffix[0]=='0' || suffix.find_first_not_of("0123456789")!=std::string::npos)return 0;
    std::uint64_t id=0;for(char c:suffix)id=id*10+(c-'0');
    if(id>=std::numeric_limits<std::uint32_t>::max())return 0;
    if(!row.HasMember("ownership") || !row["ownership"].IsObject())return 0;
    const auto& proof=row["ownership"];
    auto equal=[&](const char* key,const std::string& expected){return proof.HasMember(key) && proof[key].IsString() && expected==std::string(proof[key].GetString(),proof[key].GetStringLength());};
    if(!equal("kind","fixture_wt") || !equal("adapter_id",adapter) || !equal("order_id",oid) ||
       !proof.HasMember("local_id") || !proof["local_id"].IsNumber() || proof["local_id"].GetDouble()!=id)return 0;
    return static_cast<std::uint32_t>(id);
}
struct RecordFacts
{
    std::vector<std::string> texts;
    std::vector<double> numbers;
    bool operator==(const RecordFacts& other)const{return texts==other.texts && numbers==other.numbers;}
};
bool date_valid(unsigned n)
{
    unsigned y=n/10000, m=n/100%100, d=n%100;
    if (y<2000 || y>2099 || m<1 || m>12) return false;
    unsigned days[]={31,28,31,30,31,30,31,31,30,31,30,31};
    if (y%4==0 && (y%100!=0 || y%400==0)) days[1]=29;
    return d>=1 && d<=days[m-1];
}
std::uint64_t time_value(const Json& row)
{
    auto n=static_cast<std::uint64_t>(number(row,"time",true));
    require(n/10000000<24 && n/100000%100<60 && n/1000%100<60, "源时间不是本地HHMMSSmmm"); return n;
}
struct ArrayOwner {
    wtp::WTSArray* p=wtp::WTSArray::create();
    ~ArrayOwner(){p->release();}
};
}

struct ReadOnlyTrader::Impl
{
    explicit Impl(ReadOnlyTrader* p): self(p), owner(std::this_thread::get_id()) {}
    ~Impl(){
#ifdef _WIN32
        if(!http_config.hmac_secret.empty())SecureZeroMemory(&http_config.hmac_secret[0],http_config.hmac_secret.size());
#endif
    }
    ReadOnlyTrader* self;
    const std::thread::id owner;
    wtp::ITraderSpi* spi=nullptr;
    std::string instance_id, identity, adapter_id;
    unsigned day=0, timeout_ms=0, round_ms=0, delay_ms=0, row_limit=0, close_ms=1;
    bool http=false, shm=false, qualified=false;
    QmtAccountControl account_control;
    QmtHttpConfig http_config;HttpBinding binding;SourceSession source_session;
    std::size_t view_limit=protocol::default_view_bytes,view_bytes=0;
    struct BatchMeta {bool delivered=false;unsigned source_rows=0;std::string request,source,started,finished,sha;std::vector<std::string> views;};
    std::array<BatchMeta,4> batches;
    std::string close_status="not_started",transport_error,source_error;
    bool worker_done=false,drained=false;
    // v2只发布owner已经确认的资源证明；worker完成事件不能在纯值读取之间推进视图。
    bool owner_drained=false;
    const std::uint64_t instance_generation=next_instance_generation.fetch_add(1);
    std::uint64_t next_token=0,expected_token=0;
    Phase phase=Phase::Created;
    Diagnostics diag;
    bool in_callback=false, pumping=false, stop_requested=false, lost=false, connected=false;
    unsigned requested=0;
    Clock::time_point round_deadline, request_deadline;
    Clock::time_point runtime_deadline=Clock::time_point::max();
    bool request_pending=false;
    struct Task { unsigned stage, attempt; std::string request; Clock::time_point deadline; std::uint64_t generation=1,token=0; };
    struct Result {
        Task task;std::string packet;JsonResult remote;SourceSession source;bool prepare=false;QmtAccountResult account;
        const JsonResult& transport(bool bound)const{return bound&&!prepare?account.bound.result:remote;}
    };
    std::map<std::string,std::vector<std::string>> packets;
    std::mutex mutex;
    std::condition_variable cv;
    std::deque<Task> tasks;
    std::deque<Result> results;
    bool worker_stop=false;
    std::atomic<unsigned> live{0};
    std::atomic<std::uint64_t> worker_thread{0};
    std::thread worker;
    // 所有控制事件也在owner pump上交付；connect返回前没有SPI调用。
    std::deque<unsigned> controls;
    int fail(const char* reason)
    {
        if(!diag.error){diag.error=Failed;std::strncpy(diag.reason,reason,sizeof(diag.reason)-1);}
        qualified=false;
        phase=Phase::Failed; stop_requested=true;account_control.request_stop();
        { std::lock_guard<std::mutex> lock(mutex); worker_stop=true; }
        cv.notify_all(); return Failed;
    }
    static unsigned remaining(Clock::time_point deadline)
    {auto n=std::chrono::duration_cast<std::chrono::milliseconds>(deadline-Clock::now()).count();return n>0?static_cast<unsigned>(n):0;}
    void admit_delivery(Clock::time_point task_deadline)
    {
        // 出队与SPI之间仍有映射/基础资料/序列化耗时；在最后副作用边界统一核对，禁止晚交付。
        const auto now=Clock::now();
        require(!stop_requested&&now<round_deadline&&now<task_deadline,"交付前绝对截止时间耗尽");
    }
    void work()
    {
        worker_thread=std::hash<std::thread::id>{}(std::this_thread::get_id());live=1;
        // QRT从创建、查询到实际回调排空均由本worker独占；停止只关闭准入，不跨线程销毁客户端。
        std::unique_ptr<QmtReadTransport> client;
        std::unique_ptr<QmtHostAccountClient> account_client;
        try {
            for (;;) {
                Task task;
                {std::unique_lock<std::mutex> lock(mutex);cv.wait(lock,[&]{return worker_stop||!tasks.empty();});if(worker_stop)break;
                 task=std::move(tasks.front());tasks.pop_front();
                 if(delay_ms&&cv.wait_for(lock,std::chrono::milliseconds(delay_ms),[&]{return worker_stop;}))break;}
                Result result;result.task=task;
                if(shm){
                    // 与原Task共用一个绝对截止，排队/准备/读取均不续期。
                    SignedHttpDeadline end(task.deadline);
                    try {
                        if(task.stage==4){
                            result.prepare=true;
                            require(end.remaining()!=0,"来源准备截止时间耗尽");
                            QmtExpectedAccount expected{binding.account,binding.environment=="simulation"?QmtAccountEnvironment::Simulation:QmtAccountEnvironment::Live};
                            account_client.reset(new QmtHostAccountClient(http_config,std::move(expected),&account_control));
                            result.remote.status=account_client->prepare(end);
                        }else{
                            require(account_client&&task.stage<4&&end.remaining()!=0,"来源未准备或查询截止时间耗尽");
                            const QmtAccountDatatype types[]={QmtAccountDatatype::Position,QmtAccountDatatype::Order,QmtAccountDatatype::Deal,QmtAccountDatatype::Account};
                            auto prepared=account_client->create_request(types[task.stage],end);
                            result.account.bound.result.status=prepared.status;
                            if(prepared.status.ok()){
                                require(bool(prepared.request),"账户准备缺少一次性令牌");
                                // 先在活进程保留原身份；Core独占一次POST、原ID GET和绑定核验。
                                result.account.bound.receipt=prepared.request->receipt();
                                rapidjson::Document body;
                                require(parse_bounded_qmt_json(prepared.request->receipt().request_body,body,65536),"账户原请求结构不合格");
                                result.account.bound.result.request_id=text(body,"request_id",36);
                                result.account.bound.result.operation_id="account.trade_detail";
                                result.account=account_client->submit_once(std::move(prepared.request),end);
                            }
                        }
                    }catch(...){
                        auto& status=result.prepare?result.remote.status:result.account.bound.result.status;
                        status={end.remaining()?ErrorCode::IoError:ErrorCode::Timeout,"账户原请求准备或读取失败，原调用可能已执行"};
                    }
                }else if(http){
                    unsigned budget=remaining(task.deadline);
                    if(task.stage==4){
                        result.prepare=true;
                        if(budget){client.reset(new QmtReadTransport(http_config,QmtReadDomain::Account));auto left=remaining(task.deadline);result.remote.status=left?client->prepare(left):Status{ErrorCode::Timeout,"来源准备截止时间耗尽"};if(result.remote.status.ok())result.source=client->session();}
                        else result.remote.status={ErrorCode::Timeout,"来源准备截止时间耗尽"};
                    }else if(!budget)result.remote.status={ErrorCode::Timeout,"排队已耗尽查询截止"};
                    else if(!client)result.remote.status={ErrorCode::Unavailable,"来源尚未准备"};
                    else{
                        std::string arguments=std::string("{\"account_type\":\"stock\",\"datatype\":\"")+protocol::datatypes[task.stage]+"\",\"scope\":\"account\"}";
                        auto left=remaining(task.deadline);result.remote=left?client->read_operation(protocol::operation,arguments,left):JsonResult{{ErrorCode::Timeout,"排队已耗尽查询截止"},{}};
                    }
                }else{
                    auto it=packets.find(stages[task.stage]);result.packet=it!=packets.end()&&task.attempt<it->second.size()?it->second[task.attempt]:"{}";
                }
                {std::lock_guard<std::mutex> lock(mutex);if(results.size()>=max_queue)throw std::runtime_error("结果队列已满");results.push_back(std::move(result));}
                cv.notify_all();
            }
        } catch (...) {
            // 异常与正常停止共享排空尾段；owner截止负责报告失败，不以线程标志冒充回调屏障。
        }
        if(client){while(!client->drain_callbacks(100).ok()){}client.reset();}
        if(account_client){while(!account_client->drain_callbacks(100).ok()){}account_client.reset();}
        {std::lock_guard<std::mutex> lock(mutex);drained=true;worker_done=true;live=0;}cv.notify_all();
    }
    void enqueue(Task task)
    {
        std::lock_guard<std::mutex> lock(mutex);
        require(!worker_stop && tasks.size()<max_queue,"查询队列已关闭或满");
        task.deadline=std::min(task.deadline,round_deadline);task.generation=instance_generation;task.token=++next_token;expected_token=task.token;
        request_deadline=task.deadline;request_pending=true;
        tasks.push_back(std::move(task));cv.notify_one();
    }
    template<class F> void callback(F f)
    {
        require(spi!=nullptr,"SPI已经解绑");
        in_callback=true; ++diag.callbacks;
        try { f(); } catch (...) { in_callback=false; throw; }
        in_callback=false;
    }
    void close_notify()
    {
        if(!lost && spi && connected) {
            lost=true;
            callback([&]{spi->handleEvent(wtp::WTE_Close,0);});
        }
        connected=false;
    }
    wtp::WTSContractInfo* contract(const Json& row)
    {
        auto code=text(row,"code",31), exchange=text(row,"exchange",15);
        require(exchange=="SH" || exchange=="SZ","证券市场未知");
        require(code.size()==6 && code.find_first_not_of("0123456789")==std::string::npos,"证券代码非法");
        auto p=spi->getBaseDataMgr()->getContract(code.c_str(),exchange=="SH"?"SSE":"SZSE");
        require(p!=nullptr,"基础资料没有该合约"); return p;
    }
    std::string summary()
    {
        rapidjson::Document d;d.SetObject();auto& a=d.GetAllocator();
        auto str=[&](rapidjson::Value& v,const char* key,const std::string& value){v.AddMember(rapidjson::Value(key,a),rapidjson::Value(value.data(),static_cast<unsigned>(value.size()),a),a);};
        auto maybe=[&](rapidjson::Value& v,const char* key,const std::string& value){if(value.empty())v.AddMember(rapidjson::Value(key,a),rapidjson::Value(),a);else str(v,key,value);};
        d.AddMember("version",shm?3u:fields::view_version,a);d.AddMember("view",0,a);d.AddMember("phase",static_cast<unsigned>(phase),a);str(d,"source_kind",shm?"qmt_shm_bound":http?"qmt_http":"fixture");maybe(d,"profile",(http||shm)?binding.profile:std::string());if(http||shm){rapidjson::Value currency(rapidjson::kObjectType);str(currency,"value",binding.currency);str(currency,"source","configuration");d.AddMember("currency_binding",currency,a);}d.AddMember("observation_qualified",qualified,a);d.AddMember("aggregate_only",http||shm,a);
        rapidjson::Value td(rapidjson::kObjectType);str(td,"availability",(http||shm)?"unknown":"present");if(http||shm)td.AddMember("value",rapidjson::Value(),a);else td.AddMember("value",day,a);str(td,"reason",(http||shm)?"来源交易日不可用":"fixture精确交易日");d.AddMember("trade_date",td,a);
        rapidjson::Value bs(rapidjson::kArrayType);
        for(unsigned i=0;i<4;++i){const auto& b=batches[i];rapidjson::Value v(rapidjson::kObjectType);str(v,"datatype",protocol::datatypes[i]);v.AddMember("delivered",b.delivered,a);
          if(b.delivered){v.AddMember("source_row_count",b.source_rows,a);v.AddMember("delivered_row_count",static_cast<unsigned>(b.views.size()),a);}else{v.AddMember("source_row_count",rapidjson::Value(),a);v.AddMember("delivered_row_count",rapidjson::Value(),a);}
          maybe(v,"request_id",b.request);maybe(v,"execution_started_at",b.started);maybe(v,"execution_finished_at",b.finished);maybe(v,"result_sha256",b.sha);
          if(b.source.empty())v.AddMember("source",rapidjson::Value(),a);else{rapidjson::Document source;parse_json(source,b.source);v.AddMember("source",rapidjson::Value(source,a),a);}bs.PushBack(v,a);}
        d.AddMember("batches",bs,a);rapidjson::Value close(rapidjson::kObjectType);str(close,"status",close_status);close.AddMember("drained",owner_drained,a);close.AddMember("joined",diag.joined!=0,a);d.AddMember("close",close,a);
        rapidjson::Value failure(rapidjson::kObjectType);failure.AddMember("code",diag.error,a);str(failure,"reason",diag.reason);maybe(failure,"transport_error",transport_error);maybe(failure,"source_error_code",source_error);d.AddMember("failure",failure,a);return json_text(d);
    }
    void harvest_transport_evidence()
    {
        if(!http&&!shm)return;
        // 超时/stop不授批次交付资格；仍保留QRT已经返回的原ID，避免关闭丢掉认领依据。
        std::lock_guard<std::mutex> lock(mutex);
        for(const auto& r:results)if(r.task.generation==instance_generation&&r.task.stage<=4&&r.task.token==expected_token){
            const auto& remote=r.transport(shm);
            if(r.task.stage<4&&!remote.request_id.empty())batches[r.task.stage].request=remote.request_id;
            if(!remote.status.ok()&&transport_error.empty())transport_error=transport_error_name(remote.status.code);
        }
    }
    void deliver_http(unsigned stage,const JsonResult& remote,Clock::time_point deadline)
    {
        batches[stage].request=remote.request_id;
        if(!remote.status.ok()){transport_error=transport_error_name(remote.status.code);if(!remote.envelope_json.empty()){try{rapidjson::Document e;parse_json(e,remote.envelope_json,protocol::envelope_bytes);if(e.IsObject()&&e.HasMember("error_code")&&e["error_code"].IsString())source_error.assign(e["error_code"].GetString(),e["error_code"].GetStringLength());}catch(...){}}throw std::runtime_error(remote.status.reason.empty()?"HTTP传输失败":remote.status.reason);}
        auto batch=map_http_batch(stage,remote,source_session,binding,spi->getBaseDataMgr());
        publish_batch(stage,std::move(batch),deadline);
    }
    void deliver_shm(unsigned stage,const QmtAccountResult& remote,Clock::time_point deadline)
    {
        batches[stage].request=remote.bound.result.request_id;
        if(!remote.bound.result.status.ok()){
            transport_error=transport_error_name(remote.bound.result.status.code);source_error=remote.remote_error_code;
            throw std::runtime_error("共享内存账户查询未取得可采用结果，本轮停止");
        }
        auto batch=map_shm_account_batch(stage,remote,binding,spi->getBaseDataMgr());
        for(const auto& previous:batches)if(previous.delivered)require(previous.source==batch.source,"账户批次运输绑定改变");
        publish_batch(stage,std::move(batch),deadline);
    }
    void publish_batch(unsigned stage,AccountBatch batch,Clock::time_point deadline)
    {
        auto& meta=batches[stage];meta.source_rows=batch.source_rows;meta.source=batch.source;meta.started=batch.started;meta.finished=batch.finished;meta.sha=batch.result_sha;meta.views=std::move(batch.views);meta.delivered=true;
        // 当前批全部构造/序列化后、SPI之前结算。超限撤本批视图，不重投已经应用的先前批。
        if(batch.view_bytes>view_limit||view_bytes>view_limit-batch.view_bytes||summary().size()+1>view_limit-view_bytes-batch.view_bytes){meta.delivered=false;meta.views.clear();throw std::runtime_error("观察序列化总预算超限");}
        meta.delivered=false; // SPI正常退栈才发布行视图；原diag位仍在回调前记录可能的部分应用，禁止重投。
        admit_delivery(deadline);
        view_bytes+=batch.view_bytes;diag.row_counts[stage]=batch.array->size();std::memcpy(diag.observed_at[stage],batch.seconds.c_str(),21);diag.delivered|=1u<<stage;
        if(stage==3)diag.account_presence=3;
        callback([&]{if(stage==0)spi->onRspPosition(batch.array.get());else if(stage==1)spi->onRspOrders(batch.array.get());else if(stage==2)spi->onRspTrades(batch.array.get());else spi->onRspAccount(batch.array.get());});
        meta.delivered=true;if(stage==3)qualified=true;
        if(stage==3&&!stop_requested)phase=Phase::Observed;
    }
    void deliver(unsigned stage, const Json& response,Clock::time_point deadline)
    {
        rapidjson::Document expected;parse(expected,identity);
        require(member(response,"source")==expected,"查询来源身份或会话改变");
        auto observed=text(response,"observed_at",32);
        require(observed.size()==20 && observed[4]=='-' && observed[7]=='-' && observed[10]=='T' && observed[13]==':' && observed[16]==':' && observed[19]=='Z',"观察时间缺少UTC语义");
        std::string digits=observed.substr(0,4)+observed.substr(5,2)+observed.substr(8,2)+observed.substr(11,2)+observed.substr(14,2)+observed.substr(17,2);
        require(digits.find_first_not_of("0123456789")==std::string::npos && date_valid(std::stoul(digits.substr(0,8))) && std::stoul(digits.substr(8,2))<24 && std::stoul(digits.substr(10,2))<60 && std::stoul(digits.substr(12,2))<60,"观察时间无效");
        require(member(response,"complete").IsBool() && response["complete"].GetBool(),"查询不完整");
        const auto& rows=member(response,"data");
        require(rows.IsArray() && rows.Size()<=row_limit,"查询记录类型或容量错误");
        require(stage!=3 || rows.Size()==1,"账户查询必须包含唯一账户");
        ArrayOwner array;
        std::set<std::string> positions_seen;
        std::map<std::pair<std::string,std::string>,RecordFacts> seen;
        std::map<std::uint32_t,std::string> local_orders;
        for(const auto& row:rows.GetArray()) {
            if(stage==3) {
                require(text(row,"currency")=="CNY","资金币种不支持");
                double total=number(row,"total_asset"), available=number(row,"available");
                require(available<=total,"可用资金超过总资产");
                auto a=wtp::WTSAccountInfo::create(); array.p->append(a,false);initialize_account(a);
                a->setCurrency("CNY");a->setBalance(total);a->setAvailable(available);
                // 原生动态权益按balance+dynProfit输出；total_asset已包含浮盈，动态槽固定中性零。
                a->setDynProfit(0); diag.account_presence=3;
                if(row.HasMember("previous_balance")) {a->setPreBalance(number(row,"previous_balance"));diag.account_presence|=4;}
                if(row.HasMember("commission")) {a->setCommission(number(row,"commission"));diag.account_presence|=8;}
                if(row.HasMember("frozen_cash")) {number(row,"frozen_cash");diag.account_presence|=16;} // 冻结现金只保留presence，不能冒充保证金。
                continue;
            }
            auto c=contract(row);
            if(stage==0) {
                auto key=std::string(c->getExchg())+c->getCode();
                require(positions_seen.emplace(key).second,"持仓合约重复");
                auto total=number(row,"total",true), prev=number(row,"previous",true), today=number(row,"today",true);
                auto ap=number(row,"available_previous",true), at=number(row,"available_today",true);
                require(total==prev+today && ap<=prev && at<=today,"今昨仓或可卖数量不守恒");
                require(text(row,"position_semantics")=="remaining_yesterday","来源未确认剩余昨仓定义");
                require(!c->getCommInfo()->isT1() || at==0,"T+1合约存在当日可卖");
                auto p=wtp::WTSPositionItem::create(c->getCode(),"CNY",c->getExchg());array.p->append(p,false);
                p->setContractInfo(c);p->setDirection(wtp::WDT_LONG);p->setPrePosition(prev);p->setNewPosition(today);
                p->setAvailPrePos(ap);p->setAvailNewPos(at);p->setAvgPrice(number(row,"average_price"));
                p->setPositionCost(number(row,"cost"));
            } else {
                auto side=text(row,"side");require(side=="buy" || side=="sell","委托或成交方向未知");
                auto oid=text(row,"order_id"), source_tag=optional_tag(row);
                const auto local_id=owned_local_id(row,source_tag,adapter_id,oid);
                const auto tag=local_id?source_tag:std::string();
                require(number(row,"date",true)<=20991231,"原生交易日超限");
                unsigned date=static_cast<unsigned>(number(row,"date",true));
                require(date_valid(date) && date==day,"原生交易日不属于当前查询范围");
                auto time=time_value(row);auto quantity=number(row,"quantity",true), price=number(row,"price");
                require(quantity>0 && price>0,"委托成交量价缺失");
                // 先校验全部业务字段，再比较规范化值；JSON键顺序与200/200.0不改变业务事实。
                RecordFacts facts{{c->getCode(),c->getExchg(),side,oid,source_tag,tag},{double(date),double(time),quantity,price}};
                auto duplicate=[&](const std::string& trade_id){
                    auto key=std::make_pair(oid,trade_id);auto found=seen.find(key);
                    if(found!=seen.end()){require(found->second==facts,"原生身份相同但内容冲突");return true;}
                    seen.emplace(std::move(key),facts);return false;
                };
                if(stage==1) {
                    auto filled=number(row,"filled",true), remaining=number(row,"remaining",true), inactive=number(row,"inactive",true);
                    require(filled+remaining+inactive==quantity,"委托总量与成交剩余撤拒数量不守恒");
                    auto state=text(row,"state"); wtp::WTSOrderState os;
                    if(state=="accepted") {require(filled==0 && inactive==0,"已报状态数量错误");os=wtp::WOS_NotTraded_Queuing;}
                    else if(state=="partial") {require(filled>0 && remaining>0 && inactive==0,"部分成交状态数量错误");os=wtp::WOS_PartTraded_Queuing;}
                    else if(state=="filled") {require(filled==quantity,"全成状态数量错误");os=wtp::WOS_AllTraded;}
                    else if(state=="canceled" || state=="rejected") {require(remaining==0,"终态委托仍有活动数量");os=wtp::WOS_Canceled;}
                    else if(state=="canceling") {require(remaining>0 && inactive==0,"撤单中状态数量错误");os=wtp::WOS_Cancelling;}
                    else throw std::runtime_error("委托状态不支持");
                    facts.texts.push_back(state);facts.numbers.insert(facts.numbers.end(),{filled,remaining,inactive});
                    if(duplicate(""))continue;
                    // 整批校验完成前没有SPI；防止不同broker订单共享localid导致原map覆盖而undone累加。
                    if(local_id){auto inserted=local_orders.emplace(local_id,oid);require(inserted.second || inserted.first->second==oid,"本实例localid对应多个broker委托");}
                    auto o=wtp::WTSOrderInfo::create();array.p->append(o,false);
                    o->setCode(c->getCode());o->setExchange(c->getExchg());o->setContractInfo(c);
                    o->setDirection(wtp::WDT_LONG);o->setOffsetType(side=="buy"?wtp::WOT_OPEN:wtp::WOT_CLOSE);
                    o->setPriceType(wtp::WPT_LIMITPRICE);o->setOrderFlag(wtp::WOF_NOR);o->setBusinessType(wtp::BT_CASH);
                    o->setOrderID(oid.c_str());o->setEntrustID(oid.c_str());o->setUserTag(tag.c_str());o->setVolume(quantity);
                    o->setVolTraded(filled);o->setVolLeft(remaining);o->setPrice(price);o->setOrderState(os);
                    o->setOrderDate(date);o->setOrderTime(time);o->setError(state=="rejected");
                } else {
                    auto trade_id=text(row,"trade_id");auto amount=number(row,"amount");
                    facts.texts.push_back(trade_id);facts.numbers.push_back(amount);
                    if(duplicate(trade_id))continue;
                    auto t=wtp::WTSTradeInfo::create(c->getCode(),c->getExchg());array.p->append(t,false);
                    t->setContractInfo(c);t->setDirection(wtp::WDT_LONG);t->setOffsetType(side=="buy"?wtp::WOT_OPEN:wtp::WOT_CLOSE);
                    t->setTradeID(trade_id.c_str());t->setRefOrder(oid.c_str());t->setUserTag(tag.c_str());
                    t->setVolume(quantity);t->setPrice(price);t->setAmount(amount);t->setTradeDate(date);t->setTradeTime(time);
                }
            }
        }
        // bit在回调前提交；回调异常后的半应用不可重投，整个实例隔离。
        admit_delivery(deadline);
        diag.row_counts[stage]=array.p->size();
        std::strncpy(diag.observed_at[stage],observed.c_str(),20);
        diag.delivered|=1u<<stage;
        callback([&]{
            if(stage==0) spi->onRspPosition(array.p);
            else if(stage==1) spi->onRspOrders(array.p);
            else if(stage==2) spi->onRspTrades(array.p);
            else spi->onRspAccount(array.p);
        });
        if(stage==3 && !stop_requested) phase=Phase::Observed;
    }
};

ReadOnlyTrader::ReadOnlyTrader():impl_(new Impl(this))
{std::lock_guard<std::mutex> l(registry_mutex);objects[this]=this;}
ReadOnlyTrader::~ReadOnlyTrader()
{std::lock_guard<std::mutex> l(registry_mutex);objects.erase(this); }
bool ReadOnlyTrader::owner() const noexcept {return impl_->owner==std::this_thread::get_id();}
bool ReadOnlyTrader::deletable() const noexcept {return owner() && !impl_->in_callback && !impl_->pumping && impl_->phase==Phase::Closed && impl_->diag.joined && impl_->owner_drained && !impl_->worker.joinable();}
const std::string& ReadOnlyTrader::id() const noexcept {return impl_->instance_id;}
ReadOnlyTrader* ReadOnlyTrader::lookup(wtp::ITraderApi* p)
{std::lock_guard<std::mutex> l(registry_mutex);auto i=objects.find(p);return i==objects.end()?nullptr:i->second;}
ReadOnlyTrader* ReadOnlyTrader::find(const char* id)
{if(!id)return nullptr;std::lock_guard<std::mutex> l(registry_mutex);auto i=instances.find(id);return i!=instances.end() && i->second->owner()?i->second:nullptr;}

bool ReadOnlyTrader::init(wtp::WTSVariant* cfg)
{
    auto& x=*impl_;if(!owner() || x.phase!=Phase::Created)return false;
    try {
        require(cfg && cfg->getBoolean("enabled") && !cfg->getBoolean("savedata"),"只读入口缺少显式启用或savedata未关闭");
        const auto kind=cfg->getString("source");require(kind=="fixture"||kind=="qmt_http"||kind=="qmt_shm_bound","来源必须显式选择已登记只读来源");x.http=kind=="qmt_http";x.shm=kind=="qmt_shm_bound";
        if(x.shm){
            auto deadline=cfg->get("runtime_deadline_ns");
            require(deadline&&(deadline->type()==wtp::WTSVariant::VT_Int32||deadline->type()==wtp::WTSVariant::VT_Uint32||deadline->type()==wtp::WTSVariant::VT_Int64||deadline->type()==wtp::WTSVariant::VT_Uint64),"共享内存账户缺少精确父绝对截止");
            const auto ns=cfg->getUInt64("runtime_deadline_ns");
            require(ns>0&&ns<=static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max()),"父绝对截止范围非法");
            x.runtime_deadline=Clock::time_point(std::chrono::nanoseconds(static_cast<std::int64_t>(ns)));
            require(Clock::now()<x.runtime_deadline,"父绝对截止已经耗尽");
        }
        x.adapter_id=cfg->getString("adapter_id");require(!x.adapter_id.empty() && x.adapter_id.size()<=24 && x.adapter_id.find_first_not_of("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-")==std::string::npos,"原Adapter标识非法");
        x.instance_id=cfg->getString("instance_id");require(!x.instance_id.empty() && x.instance_id.size()<=48,"实例标识非法");
        x.timeout_ms=cfg->getUInt32("request_ms");x.round_ms=cfg->getUInt32("round_ms");x.row_limit=cfg->getUInt32("max_rows");
        require(x.timeout_ms>0 && x.timeout_ms<=30000 && x.round_ms>=x.timeout_ms && x.round_ms<=120000 && x.row_limit>0 && x.row_limit<=max_rows,"只读预算非法");
        if(x.http||x.shm){
            x.close_ms=cfg->getUInt32("close_ms");require(x.close_ms>0&&x.close_ms<=120000,"关闭预算非法");
            x.binding={cfg->getString("expected_account"),cfg->getString("environment"),cfg->getString("currency"),cfg->getString("profile"),x.row_limit};
            require(!x.binding.account.empty()&&x.binding.account.size()<=(x.shm?63:128)&&(x.binding.environment=="simulation"||x.binding.environment=="live")&&x.binding.currency=="CNY"&&x.binding.profile==protocol::profile,"HTTP只读绑定或profile非法");
            x.http_config.base_url=cfg->getString("base_url");auto key=cfg->getString("key_id_env"),secret=cfg->getString("hmac_secret_env");
            const char* key_value=key.empty()?nullptr:std::getenv(key.c_str());const char* secret_value=secret.empty()?nullptr:std::getenv(secret.c_str());require(key_value&&secret_value&&*key_value&&*secret_value,"HTTP凭证环境变量不可用");x.http_config.key_id=key_value;x.http_config.hmac_secret=secret_value;
            x.http_config.timeout_ms=cfg->getUInt32("timeout_ms");x.http_config.max_response_bytes=cfg->getUInt32("max_response_bytes");require(!x.http_config.base_url.empty()&&x.http_config.timeout_ms>0&&x.http_config.timeout_ms<=30000&&x.http_config.max_response_bytes>0&&x.http_config.max_response_bytes<=(x.shm?protocol::hard_view_bytes:protocol::envelope_bytes),"HTTP连接预算非法");
            if(x.shm){
                require(cfg->getString("read_profile_version")=="qmt.read-profile.v3","共享内存账户需要显式v3能力");
                require(!cfg->has("runtime_receipt_directory")&&!cfg->has("runtime_scan_id"),"已撤销的账户恢复参数不受支持");
            }
            if(cfg->has("view_bytes"))x.view_limit=cfg->getUInt32("view_bytes");require(x.view_limit>0&&x.view_limit<=protocol::hard_view_bytes,"观察预算非法");
        }else{
        x.close_ms=500;
        std::ifstream f(cfg->getCString("fixture"),std::ios::binary|std::ios::ate);require(bool(f),"fixture文件不可读");
        auto size=f.tellg();require(size>0 && size<=max_file_bytes,"fixture响应预算超限");f.seekg(0);
        std::string body(static_cast<std::size_t>(size),'\0');require(bool(f.read(&body[0],size)),"fixture读取不完整");
        rapidjson::Document d;parse(d,body);
        const auto& identity=member(d,"identity");
        for(auto k:{"source","account","environment","session"})text(identity,k);
        require(text(identity,"environment")=="fixture","合成输入环境必须标为fixture");
        require(number(identity,"generation",true)>0,"来源代际非法");require(number(identity,"trading_date",true)<=20991231,"来源交易日超限");x.day=static_cast<unsigned>(number(identity,"trading_date",true));
        require(date_valid(x.day),"来源交易日非法");x.identity=encode(identity);
        if(d.HasMember("delay_ms")){require(number(d,"delay_ms",true)<=30000,"fixture延迟超限");x.delay_ms=static_cast<unsigned>(number(d,"delay_ms",true));}
        auto& rs=member(d,"responses");
        for(auto name:stages){auto& entries=member(rs,name);require(entries.IsArray() && entries.Size()>0 && entries.Size()<=16,"fixture响应页数非法");for(auto& e:entries.GetArray())x.packets[name].push_back(encode(e));}
        }
        require(!x.shm||Clock::now()<x.runtime_deadline,"初始化耗尽父绝对截止");
        {std::lock_guard<std::mutex> l(registry_mutex);require(instances.emplace(x.instance_id,this).second,"实例标识重复");}
        x.worker=std::thread([&x]{x.work();});x.phase=Phase::Initialized;return true;
    }catch(const std::exception& e){x.fail(e.what());return false;}catch(...){x.fail("只读初始化异常");return false;}
}
void ReadOnlyTrader::registerSpi(wtp::ITraderSpi* p)
{
    if(!owner() || impl_->in_callback)return;
    if(p && impl_->phase!=Phase::Initialized)return;
    impl_->spi=p;
}
void ReadOnlyTrader::connect()
{auto& x=*impl_;if(!owner() || x.phase!=Phase::Initialized || !x.spi)return;x.phase=Phase::Connecting;x.round_deadline=std::min(x.runtime_deadline,Clock::now()+std::chrono::milliseconds(x.round_ms));if(x.http||x.shm){try{x.enqueue({4,0,{},std::min(x.round_deadline,Clock::now()+std::chrono::milliseconds(x.timeout_ms))});}catch(...){x.fail("来源准备准入失败");}}else x.controls.push_back(0);}
bool ReadOnlyTrader::isConnected(){return owner() && impl_->connected && !impl_->stop_requested;}
int ReadOnlyTrader::login(const char*,const char*,const char*)
{auto& x=*impl_;if(!owner())return WrongOwner;if(x.phase!=Phase::Connecting || !x.connected || x.stop_requested)return Unavailable;x.phase=Phase::Querying;x.controls.push_back(1);return 0;}
int ReadOnlyTrader::logout(){return stop();}
void ReadOnlyTrader::disconnect(){stop();}
int ReadOnlyTrader::stop()
{
    if(!owner())return WrongOwner;auto& x=*impl_;if(x.phase==Phase::Closed)return 0;
    x.stop_requested=true;x.account_control.request_stop();if(x.phase!=Phase::Failed)x.phase=Phase::Closing;
    {std::lock_guard<std::mutex> l(x.mutex);x.worker_stop=true;}x.cv.notify_all();return 0;
}
void ReadOnlyTrader::release()
{
    if(!owner())return;auto& x=*impl_;
    if(x.in_callback||x.pumping){stop();return;}if(x.phase==Phase::Closed)return;
    {std::lock_guard<std::mutex> l(registry_mutex);auto i=instances.find(x.instance_id);if(i!=instances.end()&&i->second==this)instances.erase(i);}
    stop();x.spi=nullptr;x.close_status="waiting";
    // release可准入而delete尚不可；超时保留线程、QRT与DLL，后续owner再等真实完成后join。
    if(x.worker.joinable()){
        auto deadline=std::min(x.runtime_deadline,Clock::now()+std::chrono::milliseconds(x.close_ms));
        std::unique_lock<std::mutex> lock(x.mutex);
        if(!x.cv.wait_until(lock,deadline,[&]{return x.worker_done;})){x.phase=Phase::Closing;x.close_status="timeout";return;}
        x.owner_drained=x.drained;lock.unlock();x.worker.join();
    }else{std::lock_guard<std::mutex> lock(x.mutex);x.drained=true;x.worker_done=true;x.owner_drained=true;}
    x.diag.joined=1;x.harvest_transport_evidence();
    {std::lock_guard<std::mutex> l(x.mutex);x.diag.discarded+=static_cast<unsigned>(x.results.size()+x.tasks.size());x.results.clear();x.tasks.clear();}
    x.controls.clear();x.request_pending=false;x.phase=Phase::Closed;x.close_status="complete";
}
int ReadOnlyTrader::queryPositions(){
    auto& x=*impl_;if(!owner())return WrongOwner;
    if(x.phase!=Phase::Querying || x.stop_requested || x.requested!=0)return Unavailable;
    try{x.enqueue({0,0,x.instance_id+":positions",Clock::now()+std::chrono::milliseconds(x.timeout_ms)});x.requested=1;++x.diag.reads;return 0;}catch(...){return x.fail("持仓请求准入失败");}
}
#define NQB_QUERY(method,stage) int ReadOnlyTrader::method(){auto& x=*impl_;if(!owner())return WrongOwner; \
 if(x.phase!=Phase::Querying || x.stop_requested || x.requested!=(1u<<(stage))-1 || !(x.diag.delivered&(1u<<((stage)-1))))return Unavailable; \
 try{x.enqueue({stage,0,x.instance_id+":"+stages[stage],Clock::now()+std::chrono::milliseconds(x.timeout_ms)});x.requested|=1u<<(stage);++x.diag.reads;return 0;}catch(...){return x.fail("查询请求准入失败");}}
NQB_QUERY(queryOrders,1)
NQB_QUERY(queryTrades,2)
NQB_QUERY(queryAccount,3)
#undef NQB_QUERY
int ReadOnlyTrader::orderInsert(wtp::WTSEntrust*){if(!owner())return WrongOwner;++impl_->diag.write_rejections;return ReadOnly;}
int ReadOnlyTrader::orderAction(wtp::WTSEntrustAction*){if(!owner())return WrongOwner;++impl_->diag.write_rejections;return ReadOnly;}
int ReadOnlyTrader::pump(std::uint32_t limit)
{
    if(!owner())return WrongOwner;auto& x=*impl_;if(x.pumping)return Reentrant;
    if(!limit || limit>max_pump)return Invalid;if(x.phase==Phase::Closed)return Closed;
    struct Guard {bool& f;Guard(bool& a):f(a){f=true;}~Guard(){f=false;}} guard(x.pumping);
    try {
        if(x.stop_requested){x.close_notify();return x.diag.error?Failed:0;}
        if(x.phase==Phase::Created)return Unavailable;
        if((x.phase==Phase::Connecting || x.phase==Phase::Querying) && Clock::now()>=x.round_deadline){x.harvest_transport_evidence();return x.fail("初始化总预算耗尽");}
        if(x.request_pending && Clock::now()>=x.request_deadline){x.harvest_transport_evidence();return x.fail("单项查询截止时间耗尽");}
        unsigned count=0;
        while(count<limit && !x.stop_requested){
            if(!x.controls.empty()){
                x.admit_delivery(x.round_deadline);
                unsigned c=x.controls.front();x.controls.pop_front();++count;
                if(c==0){x.connected=true;x.callback([&]{x.spi->handleEvent(wtp::WTE_Connect,0);});}
                else x.callback([&]{x.spi->onLoginResult(true,"只读来源初始化",x.day);});
                continue;
            }
            Impl::Result r;
            {std::lock_guard<std::mutex> lock(x.mutex);if(x.results.empty())break;r=std::move(x.results.front());x.results.pop_front();}
            ++count;
            require(r.task.generation==x.instance_generation&&r.task.token==x.expected_token,"旧实例或任务结果");
            if(x.http||x.shm){
                const auto& remote=r.transport(x.shm);
                // 即使最后准入失败，仍保留已经认领的来源ID；它不授数据应用资格。
                if(r.task.stage<4&&!remote.request_id.empty())x.batches[r.task.stage].request=remote.request_id;
                x.admit_delivery(r.task.deadline);
                if(r.prepare){x.request_pending=false;if(!r.remote.status.ok()){x.transport_error=transport_error_name(r.remote.status.code);throw std::runtime_error(r.remote.status.reason);}x.source_session=std::move(r.source);x.controls.push_back(0);}
                else{x.request_pending=false;if(x.shm)x.deliver_shm(r.task.stage,r.account,r.task.deadline);else x.deliver_http(r.task.stage,r.remote,r.task.deadline);}continue;
            }
            x.admit_delivery(r.task.deadline);
            rapidjson::Document d;parse(d,r.packet);
            require(text(d,"request_id")==r.task.request,"回包请求身份不匹配");
            auto http=number(d,"http_status",true);
            if(http==202){require(r.task.attempt<15,"状态回查次数耗尽");++r.task.attempt;++x.diag.polls;x.enqueue(std::move(r.task));continue;}
            require(http==200 && member(d,"ok").IsBool() && d["ok"].GetBool(),"来源查询失败");
            x.request_pending=false;
            x.deliver(r.task.stage,d,r.task.deadline);
        }
        if(x.stop_requested)x.close_notify();
        return static_cast<int>(count);
    }catch(const std::exception& e){return x.fail(e.what());}catch(...){return x.fail("SPI回调应用未知，实例隔离");}
}
int ReadOnlyTrader::wait(std::uint32_t events,std::uint32_t timeout_ms)
{
    if(!owner())return WrongOwner;
    auto& x=*impl_;
    if(x.pumping||x.in_callback)return Reentrant;
    if(!events||(events&~std::uint32_t(PumpReady|WorkerDone|StopRequested))||timeout_ms>120000)return Invalid;
    if(x.phase==Phase::Created||(!x.worker.joinable()&&x.phase!=Phase::Closed))return Unavailable;
    const bool active=x.phase==Phase::Connecting||x.phase==Phase::Querying;
    const auto caller_deadline=Clock::now()+std::chrono::milliseconds(timeout_ms);
    auto deadline=caller_deadline;
    if(active){deadline=std::min(deadline,x.round_deadline);if(x.request_pending)deadline=std::min(deadline,x.request_deadline);}
    std::unique_lock<std::mutex> lock(x.mutex);
    auto ready=[&]{
        unsigned result=0;
        if((events&PumpReady)&&(!x.controls.empty()||!x.results.empty()))result|=PumpReady;
        if((events&WorkerDone)&&x.worker_done)result|=WorkerDone;
        if((events&StopRequested)&&x.stop_requested)result|=StopRequested;
        const auto now=Clock::now();
        if(active&&(now>=x.round_deadline||(x.request_pending&&now>=x.request_deadline)))result|=DeadlineReached;
        return result;
    };
    // 结果通知/伪唤醒只重查谓词；本次调用与Task的绝对截止均不续期，也不发布owner资源证明。
    unsigned result=ready();
    if(!result&&timeout_ms){x.cv.wait_until(lock,deadline,[&]{return (result=ready())!=0;});result=ready();}
    return static_cast<int>(result);
}
#ifdef GH_QMT_HTTP_DRAIN_TESTING
void ReadOnlyTrader::impl_notify_wait(){impl_->cv.notify_all();}
#endif
int ReadOnlyTrader::view(std::uint32_t version,std::uint32_t which,std::uint32_t index,char* output,std::uint32_t capacity,std::uint32_t* required) const
{
    if(!required)return Invalid;*required=0;
    if(!owner())return WrongOwner;auto& x=*impl_;
    if(version!=(x.shm?3u:fields::view_version)||which>4||(!output&&capacity)||(!which&&index))return Invalid;
    std::string value;
    if(which){const auto& b=x.batches[which-1];if(!b.delivered)return Unavailable;if(index>=b.views.size())return Invalid;value=b.views[index];}else value=x.summary();
    if(value.size()>=std::numeric_limits<std::uint32_t>::max())return Capacity;
    *required=static_cast<std::uint32_t>(value.size()+1);if(capacity<*required)return Capacity;
    std::memcpy(output,value.c_str(),*required);return 0;
}
int ReadOnlyTrader::diagnostics(Diagnostics& out)const
{
    if(!owner())return WrongOwner;auto& x=*impl_;out=x.diag;out.phase=static_cast<unsigned>(x.phase);out.worker_live=x.live.load();out.owner_thread=std::hash<std::thread::id>{}(x.owner);out.worker_thread=x.worker_thread.load();
    {std::lock_guard<std::mutex> lock(x.mutex);out.queued=static_cast<unsigned>(x.tasks.size()+x.results.size()+x.controls.size());out.ready_results=static_cast<unsigned>(x.results.size());}return 0;
}
}}
