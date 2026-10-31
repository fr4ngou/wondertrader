#include "GuanhengQmtBootstrap/ReadOnlyTrader.h"
#include "Includes/WTSMarcos.h"
using guanheng::bootstrap::ReadOnlyTrader;
using namespace guanheng::bootstrap;
extern "C" {
EXPORT_FLAG wtp::ITraderApi* createTrader()
{ try { return new ReadOnlyTrader(); } catch (...) { return nullptr; } }
EXPORT_FLAG void deleteTrader(wtp::ITraderApi*& api)
{
    try { auto p = ReadOnlyTrader::lookup(api); if (p) { p->release(); if(p->deletable()){delete p;api=nullptr;} } }
    catch (...) { /* 保留所有权；析构失败不伪装已释放。 */ }
}
EXPORT_FLAG wtp::ITraderApi* findReadOnlyTrader(const char* id)
{ try { return ReadOnlyTrader::find(id); } catch (...) { return nullptr; } }
EXPORT_FLAG int pumpReadOnlyTrader(wtp::ITraderApi* api, std::uint32_t limit)
{ try { auto p = ReadOnlyTrader::lookup(api); return p ? p->pump(limit) : Invalid; } catch (...) { return Failed; } }
EXPORT_FLAG int waitReadOnlyTrader(wtp::ITraderApi* api,std::uint32_t events,std::uint32_t timeout_ms)
{try{auto p=ReadOnlyTrader::lookup(api);return p?p->wait(events,timeout_ms):Invalid;}catch(...){return Failed;}}
#ifdef GH_QMT_HTTP_DRAIN_TESTING
// 仅专用测试DLL可制造伪唤醒；不改队列、生命周期或任何绝对截止。
EXPORT_FLAG void gh_nqh_test_notify_wait(wtp::ITraderApi* api)
{auto p=ReadOnlyTrader::lookup(api);if(p)p->notify_wait_for_test();}
#endif
EXPORT_FLAG int stopReadOnlyTrader(wtp::ITraderApi* api)
{ try { auto p = ReadOnlyTrader::lookup(api); return p ? p->stop() : Invalid; } catch (...) { return Failed; } }
EXPORT_FLAG int inspectReadOnlyTraderView(wtp::ITraderApi* api,std::uint32_t version,std::uint32_t view,std::uint32_t index,char* output,std::uint32_t capacity,std::uint32_t* required)
{try{if(required)*required=0;auto p=ReadOnlyTrader::lookup(api);return p?p->view(version,view,index,output,capacity,required):Invalid;}catch(...){return Failed;}}
EXPORT_FLAG int inspectReadOnlyTrader(wtp::ITraderApi* api, Diagnostics* out)
{
    try { auto p = ReadOnlyTrader::lookup(api); return p && out && out->version == 1 && out->size == sizeof(Diagnostics)
        ? p->diagnostics(*out) : Invalid; } catch (...) { return Failed; }
}
}
