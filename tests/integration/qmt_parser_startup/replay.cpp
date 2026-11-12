#include "GuanhengData/QmtPollingParser.h"
#include "GuanhengData/QmtHostEndpoint.h"
#include "GuanhengData/QmtTickMapping.h"
#include "Includes/WTSVariant.hpp"
#include "Includes/WTSDataDef.hpp"
#include <rapidjson/stringbuffer.h>
#include <rapidjson/writer.h>
#include <atomic>
#include <fstream>
#include <iostream>
#include <sstream>
#include <thread>
#include <stdexcept>
using namespace guanheng;
namespace { std::string early, late; std::vector<std::string> frames; std::atomic<int> reads{0},acks{0},resumes{0},ack_delay_ms{0};
std::atomic<bool> defer_read{false};
std::vector<std::string> requested_batches;
bool split_batches=false; // 仅在worker停止之间修改，worker内记录真实分批请求。
SourceSession identity{ProviderKind::Qmt,"fixture-instance","fixture-session",1};
void require(bool b,const char* why){if(!b)throw std::runtime_error(why);}
std::string load(const char* p){std::ifstream f(p);std::stringstream s;s<<f.rdbuf();return s.str();}
QmtHttpProfile profile(){QmtHttpProfile p;p.version="fixture";p.source_license="fixture";p.time_encoding="epoch_ms";p.minute_boundary="left";p.volume_to_shares=1;p.amount_to_yuan=1;p.full_tick_cumulative=true;return p;}
std::vector<std::string> symbols(){auto d=qmt_mapping::parse(early);std::vector<std::string> result;for(auto i=d.MemberBegin();i!=d.MemberEnd();++i){std::string k=i->name.GetString();result.push_back((k.substr(7)=="SH"?"SSE.":"SZSE.")+k.substr(0,6));}return result;}
}
namespace guanheng {
class QmtHostReadClient::Impl {};
QmtHostReadClient::QmtHostReadClient(QmtHttpConfig,QmtReadProfileVersion):impl_(new Impl){}
QmtHostReadClient::~QmtHostReadClient()=default;
Status QmtHostReadClient::prepare(std::uint32_t){return {};}
SourceSession QmtHostReadClient::session()const{return identity;}
Capability QmtHostReadClient::capability()const{return {true,Qualification::DevelopmentVerified,"SDK substitute"};}
QmtBoundResult QmtHostReadClient::read_full_tick(const std::string& arguments,std::uint32_t){QmtBoundResult r;int n=++reads;r.result.data_json=frames.empty()?(n==1?early:late):frames[(std::min)(static_cast<std::size_t>(n),frames.size())-1];r.receipt.request_body="original-"+std::to_string(n);r.snapshot_consumption_ready=!defer_read.exchange(false);if(!r.snapshot_consumption_ready)r.result.status={ErrorCode::Timeout,"qmt_http_deadline"};
    if(split_batches) {
        requested_batches.push_back(arguments);
        auto selected=qmt_mapping::parse(arguments);auto all=qmt_mapping::parse(r.result.data_json);
        rapidjson::Document subset;subset.SetObject();auto& allocator=subset.GetAllocator();
        for(const auto& code:selected["stocks"].GetArray())subset.AddMember(rapidjson::Value(code,allocator),rapidjson::Value(all[code.GetString()],allocator),allocator);
        rapidjson::StringBuffer bytes;rapidjson::Writer<rapidjson::StringBuffer> writer(bytes);subset.Accept(writer);r.result.data_json=bytes.GetString();
    }
    return r;
}
QmtBoundResult QmtHostReadClient::resume(const QmtBoundReceipt& receipt,std::uint32_t){
    ++resumes;require(receipt.request_body=="original-1"&&reads==1,"resume must use original receipt");
    QmtBoundResult result;result.receipt=receipt;result.result.data_json=late;result.snapshot_consumption_ready=true;return result;
}
Status QmtHostReadClient::confirm_full_tick(const QmtBoundResult& r,std::uint32_t){require(r.receipt.request_body=="original-"+std::to_string(reads.load()),"receipt changed");std::this_thread::sleep_for(std::chrono::milliseconds(ack_delay_ms.exchange(0)));++acks;return {};}
Status QmtHostReadClient::drain_callbacks(std::uint32_t)noexcept{return {};}
}
struct Spi:wtp::IParserSpi {
std::atomic<int> quotes{0},closes{0},connects{0},snapshot_log{0};
std::vector<std::string> error_logs;
std::vector<std::string> wait_logs,info_logs;
void handleEvent(wtp::WTSParserEvent e,int32_t)override{if(e==wtp::WPE_Close)++closes;if(e==wtp::WPE_Connect)++connects;}
void handleSymbolList(const wtp::WTSArray*)override{}
void handleQuote(wtp::WTSTickData* t,uint32_t)override{require(t->price()>0,"bad tick");++quotes;}
void handleParserLog(wtp::WTSLogLevel level,const char* text)override{
    if(level==wtp::LL_ERROR)error_logs.emplace_back(text);
    if(level==wtp::LL_WARN)wait_logs.emplace_back(text);
    if(level==wtp::LL_INFO)info_logs.emplace_back(text);
    if(std::string(text).find("qmt_host_snapshot_invalid")!=std::string::npos)++snapshot_log;
}
wtp::IBaseDataMgr* getBaseDataMgr()override{return nullptr;}
};
wtp::WTSVariant* config(){auto c=wtp::WTSVariant::createObject(),q=wtp::WTSVariant::createObject(),p=wtp::WTSVariant::createObject();
q->append("base_url","http://127.0.0.1:1");q->append("key_id_env","QNP_TEST_KEY");q->append("hmac_secret_env","QNP_TEST_SECRET");q->append("timeout_ms",int32_t(1000));q->append("poll_interval_ms",int32_t(10));q->append("full_tick_batch_size",int32_t(8));q->append("batch_limit",int32_t(8));
p->append("version","fixture");p->append("source_license","fixture");p->append("time_encoding","epoch_ms");p->append("minute_boundary","left");p->append("volume_to_shares",1.0);p->append("amount_to_yuan",1.0);p->append("full_tick_cumulative",true);q->append("profile",p,false);c->append("qmt",q,false);return c;}
int main(int argc,char** argv){try{require(argc==3,"two frozen data files required");early=load(argv[1]);late=load(argv[2]);auto codes=symbols();require(codes.size()==8,"8 original ETF");
bool rejected=false;try{qmt_mapping::map_ticks(codes,early,profile(),identity);}catch(const std::invalid_argument&){rejected=true;}require(rejected,"baseline must reject preopen");
require(qmt_mapping::map_ticks(codes,early,profile(),identity,true).empty(),"unformed must emit zero ticks");require(qmt_mapping::map_ticks(codes,late,profile(),identity,true).size()==8,"formed must map eight");
// 缺字段/负量/非零成交而open=0，保持硬失败。
for(int mode=0;mode<3;++mode){auto d=qmt_mapping::parse(early);auto& row=d.MemberBegin()->value;if(mode==0)row.RemoveMember("lastClose");if(mode==1)row["volume"].SetInt(-1);if(mode==2)row["volume"].SetInt(1);rapidjson::StringBuffer b;rapidjson::Writer<rapidjson::StringBuffer>w(b);d.Accept(w);rejected=false;try{qmt_mapping::map_ticks(codes,b.GetString(),profile(),identity,true);}catch(const std::invalid_argument&){rejected=true;}require(rejected,"bad input must fail");}
_putenv_s("QNP_TEST_KEY","fixture");_putenv_s("QNP_TEST_SECRET","fixture");Spi spi;std::atomic<int> attempts{0};QmtPollingParser parser([&](const QmtHttpConfig& c,const QmtHttpProfile& p,Status& s)->std::shared_ptr<IMarketEndpoint>{auto attempt=++attempts;if(attempt<6){const char* reasons[]={"qmt_host_source_reconnect_deadline","qmt_http_deadline","qmt_host_deadline","qmt_http_exchange_failed","qmt_http_exchange_failed"};s={attempt==5?ErrorCode::IoError:ErrorCode::Timeout,reasons[attempt-1]};return {}; }auto e=std::make_shared<QmtHostEndpoint>(std::make_shared<QmtHostReadClient>(c),p,8,true);s=e->prepare(c.timeout_ms);return e;},true);
auto cfg=config();require(parser.init(cfg),"init");cfg->release();parser.registerSpi(&spi);wtp::CodeSet subscribed;for(const auto& code:codes)subscribed.insert(code);parser.subscribe(subscribed);require(parser.connect(),"connect");auto until=std::chrono::steady_clock::now()+std::chrono::seconds(3);while(spi.quotes<8&&std::chrono::steady_clock::now()<until)std::this_thread::sleep_for(std::chrono::milliseconds(1));require(spi.quotes==8,"same worker must deliver valid later quote");require(spi.closes==0,"preopen must keep worker");require(parser.stop(1000).ok(),"bounded stop");require(acks==reads&&reads>=2&&resumes==0,"original consumption");for(auto failure:std::vector<Status>{{ErrorCode::InvalidInput,"qmt_host_snapshot_invalid"},{ErrorCode::Conflict,"fixture"},{ErrorCode::SubmissionUnknown,"fixture"},{ErrorCode::Timeout,"unregistered_timeout"},{ErrorCode::StaleSession,"fixture"}}) {
    Spi failed_spi;std::atomic<int> failed_attempts{0};
    QmtPollingParser failed([&](const QmtHttpConfig&,const QmtHttpProfile&,Status& status)->std::shared_ptr<IMarketEndpoint>{++failed_attempts;status=failure;return {};},true);
    auto settings=config();require(failed.init(settings),"failure init");settings->release();failed.registerSpi(&failed_spi);require(failed.connect(),"failure connect");
    auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(1);
    while(!failed_spi.closes&&std::chrono::steady_clock::now()<deadline)std::this_thread::sleep_for(std::chrono::milliseconds(1));
    require(failed.stop(1000).ok(),"failure stop");require(failed_attempts==1&&failed_spi.closes==1&&failed_spi.quotes==0,"hard failure must not retry");require(failed.last_status().code==failure.code,"error classification retained");if(failure.reason=="qmt_host_snapshot_invalid")require(failed_spi.snapshot_log==1,"fixed safe root cause log");
}
{
    Spi waiting_spi;std::atomic<int> waiting_attempts{0};
    QmtPollingParser waiting([&](const QmtHttpConfig&,const QmtHttpProfile&,Status& status)->std::shared_ptr<IMarketEndpoint>{++waiting_attempts;status={ErrorCode::Timeout,"qmt_http_deadline"};return {};},true);
    auto settings=config();require(waiting.init(settings),"waiting init");settings->release();waiting.registerSpi(&waiting_spi);require(waiting.connect(),"waiting connect");
    auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(1);
    while(waiting_attempts<2&&std::chrono::steady_clock::now()<deadline)std::this_thread::sleep_for(std::chrono::milliseconds(1));
    require(waiting_attempts>=2,"prepare waiting must continue");require(waiting.stop(100).ok(),"stop must interrupt prepare interval");require(waiting_spi.quotes==0&&waiting_spi.connects==0&&waiting_spi.closes==1,"waiting stop events");
}
for(bool regressed:{false,true}) {
    const auto encode=[](const auto& document){rapidjson::StringBuffer bytes;rapidjson::Writer<rapidjson::StringBuffer> writer(bytes);document.Accept(writer);return std::string(bytes.GetString());};
    auto conflict=qmt_mapping::parse(late);auto& old=conflict.MemberBegin()->value;
    if(regressed)old["time"].SetUint64(static_cast<std::uint64_t>(old["time"].GetDouble())-1);
    else old["amount"].SetDouble(old["amount"].GetDouble()+1);
    auto fresh=qmt_mapping::parse(late);
    for(auto row=fresh.MemberBegin();row!=fresh.MemberEnd();++row)row->value["time"].SetUint64(static_cast<std::uint64_t>(row->value["time"].GetDouble())+1000);
    // 冲突原件已消费；重复的坏快照在同会话后继报价前始终无法进入SPI。
    frames={late,encode(conflict),encode(conflict),encode(fresh)};reads=0;acks=0;
    Spi observed;std::atomic<int> endpoints{0};
    QmtPollingParser recovering([&](const QmtHttpConfig& c,const QmtHttpProfile& p,Status& status){++endpoints;auto endpoint=std::make_shared<QmtHostEndpoint>(std::make_shared<QmtHostReadClient>(c),p,8,true);status=endpoint->prepare(c.timeout_ms);return endpoint;},true);
    auto settings=config();require(recovering.init(settings),"recovery init");settings->release();recovering.registerSpi(&observed);recovering.subscribe(subscribed);require(recovering.connect(),"recovery connect");
    auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(1);
    while(observed.quotes<16&&std::chrono::steady_clock::now()<deadline)std::this_thread::sleep_for(std::chrono::milliseconds(1));
    require(observed.quotes==16&&observed.connects==2&&observed.closes==1&&endpoints==2,"conflict must reconnect once and deliver only newer quotes");
    require(recovering.stop(1000).ok(),"recovery stop");require(reads==acks&&reads>=4&&resumes==0,"recovery preserves original consumption");
    require(observed.error_logs.size()==1,"rebuild must log a single blocking error");
    const auto& detail=observed.error_logs.front();
    require(detail.find(regressed?"timestamp regressed":"same-time snapshot changed")!=std::string::npos,"conflict classification must be exact");
    for(const auto* field:{"symbol=","accepted_time=","rejected_time=","accepted_turnover=","rejected_turnover=","source_generation="})
        require(detail.find(field)!=std::string::npos,"conflict log must record quote evidence");
}
{
    // ACK 返回后，单轮截止已过且原结果已消费。下一轮须沿同端点继续，不能终止流。
    frames={late};reads=0;acks=0;ack_delay_ms=60;split_batches=true;
    Spi observed;std::atomic<int> endpoints{0};
    QmtPollingParser parser([&](const QmtHttpConfig& c,const QmtHttpProfile& p,Status& status){++endpoints;auto endpoint=std::make_shared<QmtHostEndpoint>(std::make_shared<QmtHostReadClient>(c),p,4,true);status=endpoint->prepare(c.timeout_ms);return endpoint;},true);
    auto settings=config();settings->get("qmt")->append("timeout_ms",int32_t(25));
    require(parser.init(settings),"deadline init");settings->release();parser.registerSpi(&observed);parser.subscribe(subscribed);require(parser.connect(),"deadline connect");
    const auto until=std::chrono::steady_clock::now()+std::chrono::seconds(1);
    while(observed.quotes<8&&!observed.closes&&std::chrono::steady_clock::now()<until)std::this_thread::sleep_for(std::chrono::milliseconds(1));
    require(observed.quotes==8&&observed.closes==0&&endpoints==1,"local pump deadline must recover on the same endpoint");
    require(parser.stop(1000).ok()&&reads==acks&&reads>=2&&resumes==0,"deadline retains consumption identity");
    split_batches=false;
    require(requested_batches.size()>=3&&requested_batches[0]!=requested_batches[1]&&requested_batches[0]==requested_batches[2],"retry must visit later batches before returning to the first");
    require(observed.error_logs.size()==1&&observed.error_logs.front().find("qmt_host_pump_deadline")!=std::string::npos,"deadline log must identify the retry cause");
    require(observed.info_logs.size()==1&&observed.info_logs.front().find("action=resumed")!=std::string::npos,"deadline recovery must be observable");
}
{
    frames={late};reads=0;acks=0;resumes=0;defer_read=true;
    Spi observed;
    QmtPollingParser parser([](const QmtHttpConfig& c,const QmtHttpProfile& p,Status& status){auto endpoint=std::make_shared<QmtHostEndpoint>(std::make_shared<QmtHostReadClient>(c),p,8,true);status=endpoint->prepare(c.timeout_ms);return endpoint;},true);
    auto settings=config();require(parser.init(settings),"pending init");settings->release();parser.registerSpi(&observed);parser.subscribe(subscribed);require(parser.connect(),"pending connect");
    const auto until=std::chrono::steady_clock::now()+std::chrono::seconds(1);
    while(observed.quotes<8&&!observed.closes&&std::chrono::steady_clock::now()<until)std::this_thread::sleep_for(std::chrono::milliseconds(1));
    require(observed.quotes==8&&observed.closes==0,"original pending must keep the input open");
    require(parser.stop(1000).ok()&&reads==acks&&resumes==1,"pending continues the original receipt exactly once");
    require(observed.error_logs.empty()&&observed.wait_logs.size()==1&&observed.wait_logs.front().find("action=continue_original_request")!=std::string::npos,"waiting original reason must be visible once");
    require(observed.info_logs.size()==1&&observed.info_logs.front().find("action=resumed")!=std::string::npos,"pending recovery must be observable");
}
{
    // 端点重建必须沿原会话，后继绑定换代时尚未发出任何新读取。
    auto old=qmt_mapping::parse(late);auto& row=old.MemberBegin()->value;row["amount"].SetDouble(row["amount"].GetDouble()+1);
    rapidjson::StringBuffer bytes;rapidjson::Writer<rapidjson::StringBuffer> writer(bytes);old.Accept(writer);
    frames={late,bytes.GetString()};reads=0;acks=0;const auto original=identity;
    Spi observed;std::atomic<int> endpoints{0};
    QmtPollingParser recovering([&](const QmtHttpConfig& c,const QmtHttpProfile& p,Status& status){if(++endpoints==2)++identity.generation;auto endpoint=std::make_shared<QmtHostEndpoint>(std::make_shared<QmtHostReadClient>(c),p,8,true);status=endpoint->prepare(c.timeout_ms);return endpoint;},true);
    auto settings=config();require(recovering.init(settings),"identity init");settings->release();recovering.registerSpi(&observed);recovering.subscribe(subscribed);require(recovering.connect(),"identity connect");
    auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(1);
    while(recovering.last_status().code!=ErrorCode::StaleSession&&std::chrono::steady_clock::now()<deadline)std::this_thread::sleep_for(std::chrono::milliseconds(1));
    require(recovering.last_status().code==ErrorCode::StaleSession&&recovering.stop(1000).ok(),"different source must stop recovery");
    identity=original;
    require(reads==2&&acks==2&&observed.quotes==8&&observed.connects==1&&observed.closes==1,"changed source cannot read or deliver");
}
std::cout<<"PASS conflict_recoveries=2 conflict_evidence=2 poll_deadline_recovered=1 original_receipt_resumed=1 hard_failures=5 waiting_stop=1 preopen=0 later=8 startup_attempts="<<attempts<<"\n";return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
