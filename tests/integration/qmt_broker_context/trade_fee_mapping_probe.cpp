// 合成来源沿真实mapper与交付索引：费用变化不重复交付成交，经济冲突仍拒绝。
#define wmain standard_fixture_unused_main
#include "standard_probe.cpp"
#undef wmain
#include "GuanhengQmtBootstrap/AccountMapping.h"
#include "GuanhengQmtBootstrap/JsonBoundary.h"
#include "TraderQMT/EventDeliveryIndex.h"

int wmain(int argc,wchar_t** argv)
{
 if(argc!=2)return 2;
 try{
  auto root=fs::absolute(argv[1]);check(fs::create_directory(root),"fee_probe_new_root");
  WTSBaseDataMgr base;wtp::ActionPolicyMgr policy;base_files(root,base,policy);
  guanheng::bootstrap::AccountBinding binding{"SYNTHETIC","live","CNY","cny_cash_shsz_v1",4096};
  guanheng::QmtEventDeliveryIndex index("synthetic-binding","synthetic-session",100,65536);
  unsigned callbacks=0,observations=0;std::string immutable;
  for(unsigned step=0;step<5;++step){
   rapidjson::Document rows;rows.Parse(R"([{"m_strAccountID":"SYNTHETIC","m_strInstrumentID":"000001","m_strExchangeID":"SZ","m_strOrderSysID":"synthetic-order","m_strTradeID":"synthetic-fill","m_nOffsetFlag":48,"m_nVolume":20,"m_dPrice":10.01,"m_dTradeAmount":200.2,"m_strTradeDate":"20261106","m_strTradeTime":"09:31:02"}])");
   const double values[]={0,4.001,4.5,4.0,4.0};
   if(step)rows[0].AddMember("m_dComssion",values[step],rows.GetAllocator());
   auto mapped=guanheng::bootstrap::map_trade_event_rows(2,rows,binding,&base,{100,65536});
   check(mapped.array&&mapped.array->size()==1&&mapped.canonical_records.size()==1,"fee_mapping_shape");
   const auto& record=mapped.canonical_records[0];
   if(step)check(record.derived_facts_sha256==immutable,"fee_must_not_change_trade_economics");
   else immutable=record.derived_facts_sha256;
   rapidjson::Document view;guanheng::bootstrap::parse_json(view,mapped.views[0]);
   if(step)check(view["facts"]["fee_cny"]["value"].GetDouble()==values[step],"fee_observation_original_value");
   else check(!view["facts"].HasMember("fee_cny"),"fee_missing_remains_unknown");
   guanheng::QmtEventDeliveryObservation observation;
   observation.sequence=step+1;observation.derived_event_sha256=std::string(64,static_cast<char>('a'+step));
   observation.canonical_key=record.canonical_key;observation.derived_facts_sha256=record.derived_facts_sha256;
   observation.identity_signature="synthetic-owned";observation.is_trade=true;
   auto accepted=index.reserve(observation);check(accepted.status.ok(),"fee_update_not_trade_conflict");
   if(!step){
    check(accepted.disposition==guanheng::QmtEventDeliveryDisposition::Deliver,"first_trade_delivery");
    check(index.start(accepted.ticket)&&index.finish(accepted.ticket,guanheng::QmtEventDeliveryOutcome::Returned),"trade_delivery_commit");
    ++callbacks;
   }else check(accepted.disposition==guanheng::QmtEventDeliveryDisposition::Duplicate,"fee_only_trade_suppressed");
   ++observations;
   if(step==4){
    observation.sequence=10;observation.derived_event_sha256=std::string(64,'f');
    rows[0]["m_dPrice"].SetDouble(10.02);rows[0]["m_dTradeAmount"].SetDouble(200.4);
    auto changed=guanheng::bootstrap::map_trade_event_rows(2,rows,binding,&base,{100,65536});
    observation.derived_facts_sha256=changed.canonical_records[0].derived_facts_sha256;
    check(!index.reserve(observation).status.ok(),"real_price_conflict_kept");
   }
  }
  check(callbacks==1&&observations==5,"fee_observations_do_not_repeat_principal");
  for(bool reverse:{false,true}){
   rapidjson::Document rows;rows.Parse(R"([{"m_strAccountID":"SYNTHETIC","m_strInstrumentID":"000001","m_strExchangeID":"SZ","m_strOrderSysID":"synthetic-order","m_strTradeID":"synthetic-fill","m_nOffsetFlag":48,"m_nVolume":20,"m_dPrice":10.01,"m_dTradeAmount":200.2,"m_strTradeDate":"20261106","m_strTradeTime":"09:31:02"}])");
   auto& a=rows.GetAllocator();rapidjson::Value second;second.CopyFrom(rows[0],a);
   rows[0].AddMember("m_dComssion",reverse?5.0:4.0,a);second.AddMember("m_dComssion",reverse?4.0:5.0,a);rows.PushBack(second,a);
   bool rejected=false;try{guanheng::bootstrap::map_trade_event_rows(2,rows,binding,&base,{100,65536});}catch(const std::exception&){rejected=true;}
   check(rejected,"same_batch_fee_conflict_rejected_in_both_orders");
  }
  std::puts("actual mapper/index: 1 trade delivery, 5 fee observations, price conflict rejected");return 0;
 }catch(const std::exception& error){std::fprintf(stderr,"%s\n",error.what());return 1;}
}
