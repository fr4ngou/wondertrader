#pragma once
#include "TraderQMT/StandardSubmission.h"
#include <exception>
#include <utility>
#include <type_traits>
#include <functional>

namespace guanheng {
// 宿主持有已加载DLL；此门只借用API及函数表，不加载模块、不保存金融状态。
struct SubmissionFunctions {BeginSubmissionFn begin=nullptr;EndSubmissionFn end=nullptr;InspectSubmissionFn inspect=nullptr;};
class SubmissionEndFailure final:public std::exception {
public:const char* what()const noexcept override{return "qmt_submission_end_failed";}
};
class QueryFirstSubmission {
 wtp::ITraderApi* api_;SubmissionFunctions functions_;bool selected_;
public:
 QueryFirstSubmission(wtp::ITraderApi* api,SubmissionFunctions functions,bool query_first)
  :api_(api),functions_(functions),selected_(query_first){}
 // ReturnValue沿原base返回型；被阻断时返回空OrderIDs并明确写Decision，不能计成新命令。
 // 始终只委派一次；原base异常先保存，end只收口许可，不覆盖首个异常。
 template<class F> auto invoke(const SubmissionKeyV1& key,SubmissionViewV1& observation,F&& delegate,
  const std::function<void(const SubmissionTokenV1&)>& before={},
  const std::function<void(const SubmissionTokenV1&,const SubmissionViewV1&,SubmissionOutcome)>& after={})
  ->decltype(delegate())
 {
  if(!selected_)return delegate();
  using ReturnValue=decltype(delegate());
  static_assert(std::is_nothrow_move_constructible<ReturnValue>::value,"submission return must move without throwing");
  observation=SubmissionViewV1{};
  if(!api_||!functions_.begin||!functions_.end){observation.decision=SubmissionDecision::Invalid;return ReturnValue{};}
  SubmissionTokenV1 token;const auto begin=functions_.begin(api_,&key,&token,&observation);
  if(begin!=static_cast<int>(SubmissionDecision::Admitted)){
   observation.decision=static_cast<SubmissionDecision>(begin);return ReturnValue{};
  }
  struct Scope {
   wtp::ITraderApi* api;EndSubmissionFn end;SubmissionTokenV1 token;SubmissionViewV1& view;
   const std::function<void(const SubmissionTokenV1&,const SubmissionViewV1&,SubmissionOutcome)>& after;bool done=false;
   int finish(SubmissionOutcome outcome)noexcept{
    done=true;const auto result=end(api,&token,static_cast<std::uint32_t>(outcome),&view);
    try{if(after)after(token,view,outcome);}catch(...){view.decision=SubmissionDecision::Fault;return static_cast<int>(SubmissionDecision::Fault);}
    return result;
   }
   ~Scope(){if(!done)finish(SubmissionOutcome::Threw);}
  } scope{api_,functions_.end,token,observation,after};
  if(before)before(token); // 原group已存在，尚未进入WT delegate；异常仍由原Scope收口。
  // 返回值的构造失败仍在scope内，已接受的子Identity不会被撤销或重发。
  ReturnValue result=delegate();
  const auto ended=scope.finish(SubmissionOutcome::Returned);
  if(ended!=static_cast<int>(SubmissionDecision::Admitted))throw SubmissionEndFailure{};
  return result;
 }
};
}
