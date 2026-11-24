#include "TraderQMT/StandardReadSourceContext.h"
#include <stdexcept>
#include <thread>
#include <iostream>
using namespace guanheng;
static void check(bool ok){if(!ok)throw std::runtime_error("read source diagnostic differs");}
int main(){
 try{
  QmtTradeEventReadContext origin;origin.source.session_id="synthetic-session";
  origin.read_profile_body="synthetic-profile";origin.read_result_capacity=100;
  origin.admitted_event_page_capacity=200;
  auto changed=origin;check(read_context_differences(origin,changed)==0);
  changed.source.session_id="another-session";check(read_context_differences(origin,changed)==ReadSourceSession);
  changed=origin;changed.read_profile_body="another-profile";check(read_context_differences(origin,changed)==ReadSourceProfile);
  changed=origin;changed.read_result_capacity=101;check(read_context_differences(origin,changed)==ReadSourceResultCapacity);
  changed=origin;changed.admitted_event_page_capacity=201;check(read_context_differences(origin,changed)==ReadSourcePageCapacity);
  ReadSourceFailure saved;check(saved.snapshot().captured==0);
  saved.capture(ReadSourceStage::Reuse,0);check(saved.snapshot().captured==0);
  std::thread producer([&]{saved.capture(ReadSourceStage::Open,ReadSourceSession|ReadSourceProfile);});producer.join();
  saved.capture(ReadSourceStage::EventPage,ReadSourceResultCapacity);
  const auto first=saved.snapshot();check(first.captured==1&&first.stage==2&&first.differences==6);
  std::cout<<"read source first-failure diagnostics passed\n";return 0;
 }catch(const std::exception& e){std::cerr<<e.what();return 1;}
}
