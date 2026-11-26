// 真实HostEndpoint→MarketParser→PollingParser；仅Common结果是无网络替身。
#include "GuanhengData/QmtHostEndpoint.h"
#include "GuanhengData/QmtPollingParser.h"
#include "Includes/WTSVariant.hpp"
#include "Includes/WTSDataDef.hpp"
#include <atomic>
#include <chrono>
#include <iostream>
#include <mutex>
#include <stdexcept>
#include <thread>
#include <vector>
using namespace guanheng;
namespace {
unsigned mode=0; // 每例join后才修改，worker期间只读。
std::atomic<unsigned> reads{0},resumes{0},confirms{0},sdk_reads{0}; // 同一测试worker的调用计数。
std::atomic<bool> client_draining{false}, allow_client_close{false}; // 模拟操作系统回调晚于换代通知。
bool new_connection=false; // 测试用传输身份，worker独占。
bool client_ready=true; // Common资格仅由worker修改；模拟绑定GET失败后的实际失效。
SourceSession source(){return {ProviderKind::Qmt,"synthetic-host",new_connection?"replacement-connection":"synthetic-connection",1};}
const char* snapshot=R"({"000001.SZ":{"time":1764034260000,"lastPrice":10,"open":10,"high":10,"low":10,"lastClose":10,"volume":100,"amount":1000}})";
void require(bool value,const char* reason){if(!value)throw std::runtime_error(reason);}
struct Spi final:wtp::IParserSpi {
 std::atomic<unsigned> quotes{0},closes{0}; // 回调计数，管理线程可观察。
 std::mutex mutex; // 仅保护测试收集的日志。
 std::vector<std::string> logs; // worker发布的固定原因及恢复记录。
 std::function<void()> on_close; // 仅停机回归从 worker 发出停止请求。
 std::atomic<unsigned> connects{0},reconnect_at{0}; // 连接恢复发生在哪次请求。
 void handleEvent(wtp::WTSParserEvent event,int32_t)override{if(event==wtp::WPE_Close){++closes;if(on_close)on_close();}
  if(event==wtp::WPE_Connect){++connects;if((mode==12||mode==14) && connects==2)reconnect_at=reads.load();}}
 void handleSymbolList(const wtp::WTSArray*)override{}
 void handleQuote(wtp::WTSTickData*,uint32_t)override{if(mode==11)throw std::runtime_error("synthetic callback unknown");++quotes;}
 void handleParserLog(wtp::WTSLogLevel,const char* text)override{std::lock_guard<std::mutex> lock(mutex);logs.emplace_back(text);}
 wtp::IBaseDataMgr* getBaseDataMgr()override{return nullptr;}
};
wtp::WTSVariant* configuration(){
 auto c=wtp::WTSVariant::createObject(),q=wtp::WTSVariant::createObject(),p=wtp::WTSVariant::createObject();
 q->append("base_url","http://127.0.0.1:1");q->append("key_id_env","LIFECYCLE_QA_KEY");q->append("hmac_secret_env","LIFECYCLE_QA_SECRET");
 q->append("timeout_ms",int32_t(1000));q->append("poll_interval_ms",int32_t(10));q->append("batch_limit",int32_t(1));q->append("full_tick_batch_size",int32_t(1));
 p->append("version","synthetic");p->append("source_license","synthetic");p->append("time_encoding","epoch_ms");p->append("minute_boundary","left");
 p->append("volume_to_shares",1.0);p->append("amount_to_yuan",1.0);p->append("full_tick_cumulative",true);
 q->append("profile",p,false);c->append("qmt",q,false);return c;
}
}
namespace guanheng {
class QmtHostReadClient::Impl{};
QmtHostReadClient::QmtHostReadClient(QmtHttpConfig,QmtReadProfileVersion):impl_(new Impl){}
QmtHostReadClient::~QmtHostReadClient(){
 if(mode!=13)return;
 client_draining=true;
 const auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(1);
 while(!allow_client_close && std::chrono::steady_clock::now()<deadline)std::this_thread::sleep_for(std::chrono::milliseconds(1));
}
Status QmtHostReadClient::prepare(std::uint32_t){client_ready=true;return {};}
SourceSession QmtHostReadClient::session()const{return client_ready?source():SourceSession{};}
Capability QmtHostReadClient::capability()const{return {client_ready,Qualification::DevelopmentVerified,"synthetic"};}
QmtBoundResult QmtHostReadClient::read_full_tick(const std::string&,std::uint32_t){
 QmtBoundResult out;++reads;
 if(mode==16){
  if(reads>2){out.result.status={ErrorCode::Pending,"qmt_read_retention_held_responsibility"};return out;}
  ++sdk_reads;
  if(reads==1){
   out.receipt.request_body="original-request";out.result.status={ErrorCode::Timeout,"qmt_http_deadline"};return out;
  }
  out.receipt.request_body="next-request";out.result.data_json=snapshot;
  out.snapshot_consumption_ready=true;return out;
 }
 if(mode>=12){
  if(reads==2){
   new_connection=true;
   if(mode>=14){
    ++sdk_reads;out.receipt.request_body="old-terminal-result";
    out.snapshot_consumption_ready=true;
    out.result.status={ErrorCode::StaleSession,"qmt_host_transport_replaced_after_result"};
    out.result.data_json=mode==15?"{}":snapshot;
   }else out.result.status={ErrorCode::StaleSession,"qmt_host_transport_replaced_before_submit"};
   return out;
  }
  if(reads>=5){out.result.status={ErrorCode::Pending,"qmt_read_retention_held_responsibility"};return out;}
  ++sdk_reads;out.receipt.request_body="original-request";out.result.data_json=snapshot;
  // 新会话第一条仍是旧价。仅下一条更晚的报价恢复连接并投递。
  if(reads>=4)out.result.data_json.replace(out.result.data_json.find("1764034260000"),13,"1764034320000");
  out.snapshot_consumption_ready=true;return out;
 }
 if(sdk_reads){out.result.status={ErrorCode::Pending,"qmt_read_retention_held_responsibility"};return out;}
 if(reads==1 && mode>=2 && mode<=9){
  static const Status causes[]={{ErrorCode::Pending,"qmt_read_retention_held_responsibility"},
   {ErrorCode::Timeout,"qmt_http_deadline"},{ErrorCode::IoError,"qmt_http_exchange_failed"},
   {ErrorCode::IoError,"qmt_http_remote_failure:503:source_unavailable"},
   {ErrorCode::Backpressure,"qmt_http_backpressure"},{ErrorCode::StaleSession,"qmt_host_binding_changed"},
   {ErrorCode::InvalidInput,"qmt_host_snapshot_invalid"},{ErrorCode::SubmissionUnknown,"qmt_host_result_unknown"}};
  out.result.status=causes[mode-2];if(mode==3)client_ready=false;return out;
 }
 client_ready=true; // 下一读取成功核原pin；实际Common行为另由core.py经WinHTTP验证。
 ++sdk_reads;out.receipt.request_body="original-request";out.result.data_json=mode==10?"{}":snapshot;
 out.snapshot_consumption_ready=true;
 if(mode==0){out.snapshot_consumption_ready=false;out.result.status={ErrorCode::Timeout,"qmt_http_deadline"};}
 return out;
}
QmtBoundResult QmtHostReadClient::resume(const QmtBoundReceipt& receipt,std::uint32_t){
 ++resumes;require(receipt.request_body=="original-request" && sdk_reads==1,"original request changed");
 QmtBoundResult out;out.receipt=receipt;
 if(mode==16){out.result.status={ErrorCode::Pending,"qmt_host_snapshot_ticket_ended"};return out;}
 out.result.data_json=snapshot;out.snapshot_consumption_ready=true;return out;
}
Status QmtHostReadClient::confirm_full_tick(const QmtBoundResult& value,std::uint32_t){
 ++confirms;
 if(mode==16)require(value.receipt.request_body=="next-request","expired snapshot acknowledged");
 else if(mode>=14 && (confirms==2||confirms==3)){
  require(value.receipt.request_body=="old-terminal-result" && reads==2 && sdk_reads==2,
   "an old result was replaced before acknowledgement");
  if(mode==14 && confirms==2)return {ErrorCode::Timeout,"qmt_http_deadline"};
 }else require(value.receipt.request_body=="original-request","original ACK changed");
 if(mode==1 && confirms==1)return {ErrorCode::Pending,"qmt_snapshot_result_unconfirmed"};return {};
}
Status QmtHostReadClient::drain_callbacks(std::uint32_t)noexcept{return {};}
}
int main(){
 _putenv_s("LIFECYCLE_QA_KEY","synthetic");_putenv_s("LIFECYCLE_QA_SECRET","synthetic");
 try{for(mode=0;mode<17;++mode){
  new_connection=false;reads=0;resumes=0;confirms=0;sdk_reads=0;Spi spi;std::atomic<unsigned> factories{0};
  QmtPollingParser parser([&](const QmtHttpConfig& c,const QmtHttpProfile& p,Status& status){
   ++factories;auto endpoint=std::make_shared<QmtHostEndpoint>(std::make_shared<QmtHostReadClient>(c),p,1,true);
   status=endpoint->prepare(c.timeout_ms);return endpoint;
  },true);
  if(mode==13)spi.on_close=[&]{parser.stop(0);};
  auto cfg=configuration();require(parser.init(cfg),"init");cfg->release();parser.registerSpi(&spi);
  wtp::CodeSet symbols;symbols.insert("SZSE.000001");parser.subscribe(symbols);require(parser.connect(),"connect");
  const auto until=std::chrono::steady_clock::now()+std::chrono::seconds(2);
  if(mode==13){
   while(!client_draining && std::chrono::steady_clock::now()<until)
    std::this_thread::sleep_for(std::chrono::milliseconds(1));
   const auto pending=parser.stop(30);
   allow_client_close=true;
   require(parser.stop(1000).ok(),"rebind stop did not drain");
   require(client_draining && pending.code==ErrorCode::Timeout,"rebind published stopped before transport drain");
   require(reads==2 && spi.quotes==1 && spi.closes==1 && factories==1,"stop crossed into the replacement");
   std::cout<<"{\"mode\":13,\"passed\":true}\n";
   continue;
  }
  while(((mode==12||mode==14)?spi.quotes<2:!spi.closes && (mode==15||!spi.quotes)) && std::chrono::steady_clock::now()<until)
   std::this_thread::sleep_for(std::chrono::milliseconds(1));
  const auto closed=spi.closes.load();require(parser.stop(1000).ok(),"bounded stop");
  if(mode==12||mode==14){
   require(spi.quotes==2 && closed==1 && factories==1,"verified replacement did not reconnect");
   require(spi.connects==2 && spi.reconnect_at==4,"connection announced before newer quote");
   bool rebind=false,resumed=false;
   for(const auto& log:spi.logs){
    rebind|=log.find("action=rebind_read_transport")!=std::string::npos;
    resumed|=log.find("action=read_transport_resumed")!=std::string::npos;
   }
   require(rebind && resumed,"transport rebind/recovery log missing");
   require(sdk_reads==(mode==14?4:3) && confirms==(mode==14?5:3) && !resumes,"replacement replayed a read or its stale quote");
  }else if(mode==15){
   require(spi.quotes==1 && closed==1 && spi.connects==1 && sdk_reads==2 && confirms==2,
    "invalid old snapshot passed its original validation");
   bool invalid=false;
   for(const auto& log:spi.logs)invalid|=log.find("qmt_host_snapshot_invalid")!=std::string::npos;
   require(invalid,"invalid old snapshot diagnostic missing");
  }else if(mode==16){
   require(spi.quotes==1 && closed==0 && factories==1,"expired quote request stopped the receiver");
   require(sdk_reads==2 && resumes==1 && confirms==1,"expired quote request was retried or acknowledged");
   bool expired=false,resumed=false;
   for(const auto& log:spi.logs){
    expired|=log.find("qmt_host_snapshot_ticket_ended")!=std::string::npos
        && log.find("action=retry_next_poll")!=std::string::npos;
    resumed|=log.find("action=resumed")!=std::string::npos;
   }
   require(expired && resumed,"expiry and recovery diagnostics missing");
  }else if(mode<=6){
   require(factories==1,"unnecessary endpoint rebuild");
   require(spi.quotes==1 && closed==0 && sdk_reads==1,"safe wait did not recover exactly once");
   require(resumes==(mode==0?1:0) && confirms==(mode==1?2:1),"original result/ACK responsibility changed");
   bool waiting=false,recovered=false;
   for(const auto& log:spi.logs){
    require(log.find("unclassified")==std::string::npos,"lost fixed wait cause");
    waiting|=log.find("continue_original_request")!=std::string::npos || log.find("retry_next_poll")!=std::string::npos;
    recovered|=log.find("action=resumed")!=std::string::npos;
   }
   require(waiting && recovered,"wait/recovery log missing");
  }else{
   require(factories==1,"hard failure rebuilt source");
   require(!spi.quotes && closed==1,"hard boundary retried or delivered quote");
   require(reads==1 && sdk_reads==(mode>=10?1:0),"hard boundary repeated source read");
  }
  std::cout<<"{\"mode\":"<<mode<<",\"passed\":true,\"sdk_reads\":"<<sdk_reads<<",\"resumes\":"<<resumes<<",\"confirms\":"<<confirms<<"}\n";
 }}catch(const std::exception& e){std::cerr<<"case="<<mode<<" "<<e.what()<<'\n';return 1;}return 0;
}
