// 真实orderInsert入口：在kind6已确认后注入容量/停止竞态；没有worker/Source/SDK替身调用。
#define GH_QMT_STANDARD_AUDIT_TESTING
#include "TraderQMT/StandardQmtTrader.cpp"
namespace guanheng {
struct StandardAuditTestAccess {
 using I=StandardQmtTrader::Impl;unsigned assertions=0;int mode=0;I* owner=nullptr;
 unsigned child=0,not_called=0;std::string child_tag;int return_code=0;
 void check(bool v){++assertions;if(!v)throw std::runtime_error("enqueue_hook_assertion");}
 static int __cdecl hook(const GhAttributionEventV1* event,GhAttributionReplyV1* reply,void* user){
  try{auto& t=*static_cast<StandardAuditTestAccess*>(user);rapidjson::Document body;
   body.Parse(event->json_utf8,event->json_bytes);t.check(!body.HasParseError());
   if(event->kind==GH_ATTR_WT_CHILD){++t.child;t.child_tag=body["user_tag"].GetString();
    // 仅此隔离fixture安排原子关闭/容量状态，模拟kind6与原enqueue之间的竞态；生产回调仍禁止重入。
    if(t.mode==0){for(unsigned n=0;n<t.owner->max_queue;++n){
      I::Task query;query.kind=I::Kind::Query;query.stage=3;query.deadline=Clock::now()+std::chrono::seconds(1);
      t.check(t.owner->enqueue(std::move(query))==0);
     }}else t.owner->submissions_closed=true;
   }else if(event->kind==GH_ATTR_INSERT_RESULT){++t.not_called;
    t.check(body["command_id"].IsNull()&&body["command_sha256"].IsNull()&&body["source_sha256"].IsNull());
    t.check(body["dispatch_not_entered"].GetBool()&&body["phase"].GetUint()==0&&body["filled_quantity"].GetUint64()==0);
    t.check(body["quantity"].GetUint64()==100&&body["user_tag"].GetString()==t.child_tag);
    t.return_code=body["enqueue_return_code"].GetInt();
   }
   reply->decision=0;reply->authorized_quantity=0;return 0;
  }catch(...){return -1;}
 }
 void run(int selected){
  mode=selected;child=not_called=0;return_code=0;StandardQmtTrader trader;auto& x=*trader.impl_;owner=&x;
  check(trader.configure_attribution({hook,this}));x.query_first=true;x.initialized=true;x.logged_in=true;
  x.expected.writes_enabled=true;x.max_queue=16;x.max_pending=16;x.max_queue_bytes=4*1024*1024;
  x.binding.row_limit=64;x.close_ms=100;x.request_ms=1000;x.instance_id="enqueue-test";
  x.payload_bytes=I::submission_fixed_bytes;
  SubmissionKeyV1 key;std::strcpy(key.exchange,"SZSE");std::strcpy(key.code,"000001");
  SubmissionTokenV1 token;SubmissionViewV1 view;check(trader.begin_submission(key,token,view)==0);
  auto commodity=wtp::WTSCommodityInfo::create("STK","fixture","SZSE","DAY","CHINA");commodity->setPriceTick(.01);
  auto contract=wtp::WTSContractInfo::create("000001","fixture","SZSE","STK");contract->setCommInfo(commodity);
  auto order=wtp::WTSEntrust::create("000001",100,10.01,"SZSE");order->setContractInfo(contract);
  order->setEntrustID("entrust.synthetic.1");order->setUserTag("tag.synthetic.1");order->setDirection(wtp::WDT_LONG);
  order->setOffsetType(wtp::WOT_OPEN);order->setBusinessType(wtp::BT_CASH);order->setPriceType(wtp::WPT_LIMITPRICE);order->setOrderFlag(wtp::WOF_NOR);
  const auto rc=trader.orderInsert(order);order->release();contract->release();commodity->release();
  check(rc==(mode==0?StandardQmtCapacity:StandardQmtUnavailable)&&return_code==rc);
  check(child==1&&not_called==1&&x.identities.empty()&&x.pending.empty());
  check(mode==0?x.tasks.size()==x.max_queue&&x.next_task==x.max_queue:x.tasks.empty()&&x.next_task==0);
  for(const auto& task:x.tasks)check(task.kind==I::Kind::Query);
  trader.end_submission(token,SubmissionOutcome::Returned,view);check(view.accepted_children==0);
  trader.release();StandardQmtDiagnostics d;check(trader.diagnostics(d)==0&&trader.deletable()&&d.joined&&d.drained&&!d.worker_live);
 }
};
}
int main(){try{guanheng::StandardAuditTestAccess test;test.run(0);test.run(1);
 std::printf("{\"passed\":true,\"cases\":2,\"assertions\":%u,\"sdk_calls\":0,\"source_requests\":0,\"scope\":\"actual Native orderInsert with controlled state race injection\"}\n",test.assertions);return 0;
}catch(const std::exception& e){std::printf("{\"passed\":false,\"reason\":\"%s\"}\n",e.what());return 1;}}
