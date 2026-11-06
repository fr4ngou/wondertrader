// 独立回调ABI边界：完整复制、显式答复、一次注册与原owner冻结。
#include "GuanhengCommon/AccountAttributionHooks.h"
#include "TraderQMT/StandardOrderPrice.h"
#include <cstdio>
#include <thread>
#include <vector>
#include <limits>
using namespace guanheng;
namespace {
unsigned assertions=0;std::string copied;unsigned mode=0,calls=0;uint64_t received_remaining=0;
void check(bool value){++assertions;if(!value)throw std::runtime_error("hook_contract_assertion");}
int __cdecl receive(const GhAttributionEventV1* event,GhAttributionReplyV1* reply,void*){
 ++calls;received_remaining=event->remaining_ms;copied.assign(event->json_utf8,event->json_bytes);if(mode==1)return 0;
 reply->decision=0;reply->authorized_quantity=0;
 if(mode==2)reply->size=0;if(mode==3)reply->reserved=1;if(mode==4)reply->authorized_quantity=std::numeric_limits<double>::quiet_NaN();
 if(mode==6)std::this_thread::sleep_for(std::chrono::milliseconds(30));
 return mode==5?-1:0;
}
}
int main(){try{
 check(sizeof(GhAttributionEventV1)==48&&sizeof(GhAttributionReplyV1)==24);
 AttributionRegistration reg;check(reg.configure(nullptr,nullptr)<0);check(reg.configure(receive,nullptr)==0);check(reg.configure(receive,nullptr)<0);
 bool wrong_rejected=false;std::thread other([&]{try{reg.freeze();}catch(...){wrong_rejected=true;}});other.join();check(wrong_rejected);
 const auto observer=reg.freeze();check(static_cast<bool>(observer));check(reg.configure(receive,nullptr)<0);
 rapidjson::Document value(rapidjson::kObjectType);auto& a=value.GetAllocator();attribution_text(value,"text","完整\\文本\"\n",a);
 attribution_notify(observer,GH_ATTR_COMMIT,2,value);check(copied.find("text")!=std::string::npos&&copied.find("\\\\")!=std::string::npos);
 const auto saved=copied;value.SetObject();check(copied==saved);
 for(mode=1;mode<=5;++mode){bool rejected=false;try{attribution_notify(observer,GH_ATTR_COMMIT,2,value);}catch(...){rejected=true;}check(rejected);}
 mode=0;rapidjson::Document large(rapidjson::kObjectType);attribution_text(large,"large",std::string(2*1024*1024,'x'),large.GetAllocator());
 bool limit=false;try{attribution_notify(observer,GH_ATTR_COMMIT,2,large);}catch(...){limit=true;}check(limit);
 // 真实序列化完成后核同一D：已到/不足1ms不进入7/8/9回调，晚回调也不刷新原D。
 mode=0;for(unsigned kind:{GH_ATTR_PREPARED,GH_ATTR_FILL,GH_ATTR_ORDER}){
  const auto before=calls;bool expired=false;
  try{attribution_notify_until(observer,kind,3,value,std::chrono::steady_clock::now());}catch(const AttributionDeadline&){expired=true;}
  check(expired&&calls==before);
 }
 const auto before=calls;mode=6;bool late=false;
 try{attribution_notify_until(observer,GH_ATTR_PREPARED,3,value,std::chrono::steady_clock::now()+std::chrono::milliseconds(20));}
 catch(const AttributionDeadline&){late=true;}
 check(late&&calls==before+1&&received_remaining>0&&received_remaining<=20);mode=0;
 // 原规范限价文本正文：档位乘法噪声收敛，真实离档值和默认值保持。
 check(standard_order_price_text(2885*.001,.001)=="2.885");check(standard_order_price_text(2.88501,.001)=="2.88501");
 check(standard_order_price_text(10.01,.01)=="10.01");
 std::printf("{\"passed\":true,\"assertions\":%u,\"sdk_calls\":0}\n",assertions);return 0;
}catch(const std::exception& e){std::printf("{\"passed\":false,\"assertions\":%u,\"reason\":\"%s\"}\n",assertions,e.what());return 1;}}
