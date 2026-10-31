#include "StandardQmtTrader.h"
#include "Includes/WTSMarcos.h"
using guanheng::StandardQmtTrader;
extern "C" {
EXPORT_FLAG std::uint32_t standardQmtObservationRefreshVersion() noexcept {return 1;}
EXPORT_FLAG wtp::ITraderApi* createTrader()
{try{return new StandardQmtTrader();}catch(...){return nullptr;}}
EXPORT_FLAG void deleteTrader(wtp::ITraderApi*& api)
{
 // 关闭超时或错线程时保留原API和DLL所有权，后继由同owner继续实际排空。
 try{auto p=StandardQmtTrader::lookup(api);if(p&&p->owner()){p->release();if(p->deletable()){delete p;api=nullptr;}}}
 catch(...){/* 已受理资源保持可定位，异常不冒充删除成功。 */}
}
EXPORT_FLAG wtp::ITraderApi* findStandardQmtTrader(const char* id)
{try{return StandardQmtTrader::find(id);}catch(...){return nullptr;}}
EXPORT_FLAG int pumpStandardQmtTrader(wtp::ITraderApi* api,std::uint32_t limit)
{try{auto p=StandardQmtTrader::lookup(api);return p?p->pump(limit):guanheng::StandardQmtInvalid;}catch(...){return guanheng::StandardQmtFailure;}}
EXPORT_FLAG int waitStandardQmtTrader(wtp::ITraderApi* api,std::uint32_t flags,std::uint32_t timeout_ms)
{try{auto p=StandardQmtTrader::lookup(api);return p?p->wait(flags,timeout_ms):guanheng::StandardQmtInvalid;}catch(...){return guanheng::StandardQmtFailure;}}
EXPORT_FLAG int stopStandardQmtTrader(wtp::ITraderApi* api)
{try{auto p=StandardQmtTrader::lookup(api);return p?p->stop():guanheng::StandardQmtInvalid;}catch(...){return guanheng::StandardQmtFailure;}}
EXPORT_FLAG int inspectStandardQmtTrader(wtp::ITraderApi* api,guanheng::StandardQmtDiagnostics* out)
{try{auto p=StandardQmtTrader::lookup(api);return p&&out&&out->version==1&&out->size==sizeof(*out)?p->diagnostics(*out):guanheng::StandardQmtInvalid;}catch(...){return guanheng::StandardQmtFailure;}}
EXPORT_FLAG int closeStandardQmtSubmissions(wtp::ITraderApi* api)
{try{auto p=StandardQmtTrader::lookup(api);return p?p->close_submissions():guanheng::StandardQmtInvalid;}catch(...){return guanheng::StandardQmtFailure;}}
EXPORT_FLAG int inspectStandardQmtRecovery(wtp::ITraderApi* api,guanheng::StandardQmtRecoveryV1* out)
{try{auto p=StandardQmtTrader::lookup(api);return p&&out?p->recovery(*out):guanheng::StandardQmtInvalid;}catch(...){return guanheng::StandardQmtFailure;}}
EXPORT_FLAG int beginStandardQmtSubmission(wtp::ITraderApi* api,const guanheng::SubmissionKeyV1* key,
 guanheng::SubmissionTokenV1* token,guanheng::SubmissionViewV1* out) noexcept
{try{auto p=StandardQmtTrader::lookup(api);return p&&key&&token&&out?p->begin_submission(*key,*token,*out):static_cast<int>(guanheng::SubmissionDecision::Invalid);}
 catch(...){return static_cast<int>(guanheng::SubmissionDecision::Fault);}}
EXPORT_FLAG int endStandardQmtSubmission(wtp::ITraderApi* api,const guanheng::SubmissionTokenV1* token,
 std::uint32_t outcome,guanheng::SubmissionViewV1* out) noexcept
{try{auto p=StandardQmtTrader::lookup(api);return p&&token&&out?p->end_submission(*token,static_cast<guanheng::SubmissionOutcome>(outcome),*out):static_cast<int>(guanheng::SubmissionDecision::Invalid);}
 catch(...){return static_cast<int>(guanheng::SubmissionDecision::Fault);}}
EXPORT_FLAG int inspectStandardQmtSubmission(wtp::ITraderApi* api,const guanheng::SubmissionKeyV1* key,
 guanheng::SubmissionViewV1* out) noexcept
{try{auto p=StandardQmtTrader::lookup(api);return p&&key&&out?p->inspect_submission(*key,*out):static_cast<int>(guanheng::SubmissionDecision::Invalid);}
 catch(...){return static_cast<int>(guanheng::SubmissionDecision::Fault);}}

}
