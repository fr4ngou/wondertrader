// NMR边界沿实际安装DLL；不创建Parser/Trader/委托通道。
#include <windows.h>
#include "Includes/IDataReader.h"
#include "Includes/WTSDataDef.hpp"
#include "Includes/WTSVariant.hpp"
#include "WTSTools/WTSBaseDataMgr.h"
#include <chrono>
#include <condition_variable>
#include <functional>
#include <iostream>
#include <memory>
#include <mutex>
#include <stdexcept>
#include <thread>
#include <vector>
using namespace wtp;
namespace {
void check(bool value,const char* reason){if(!value)throw std::runtime_error(reason);}
template<class T>struct Release{void operator()(T* p)const{if(p)p->release();}};
using Config=std::unique_ptr<WTSVariant,Release<WTSVariant>>;
using Slice=std::unique_ptr<WTSKlineSlice,Release<WTSKlineSlice>>;
struct Sink:IDataReaderSink{
 WTSBaseDataMgr base;uint32_t date=20261029,minute=1130;unsigned events=0,initialized=0;std::function<void()> callback;
 IBaseDataMgr* get_basedata_mgr()override{return &base;}IHotMgr* get_hot_mgr()override{return nullptr;}
 uint32_t get_date()override{return date;}uint32_t get_min_time()override{return minute;}uint32_t get_secs()override{return 0;}
 void reader_log(WTSLogLevel,const char* text)override{if(std::string(text).find("WtDataReader initialized")!=std::string::npos)++initialized;}
 void on_bar(const char*,WTSKlinePeriod,WTSBarStruct*)override{++events;if(callback)callback();}
 void on_all_bar_updated(uint32_t)override{}
};
struct Loader:IHisDataLoader{
 std::function<void()> minute;
 bool loadFinalHisBars(void* obj,const char*,WTSKlinePeriod period,FuncReadBars cb)override{
  if(period==KP_Minute1&&minute){minute();WTSBarStruct b{};b.date=20261029;b.time=202610290931ULL-199000000000ULL;b.open=10;b.high=12;b.low=9;b.close=11;b.vol=1;b.money=11;cb(obj,&b,1);return true;}
  if(period!=KP_DAY)return false;WTSBarStruct b{};b.date=20261028;b.open=10;b.high=12;b.low=9;b.close=11;b.vol=1;b.money=11;cb(obj,&b,1);return true;
 }
 bool loadRawHisBars(void*,const char*,WTSKlinePeriod,FuncReadBars)override{return false;}
 bool loadAllAdjFactors(void*,FuncReadFactors)override{return false;}
 bool loadAdjFactors(void*,const char*,FuncReadFactors)override{return false;}
};
Config config(const char* storage,const char* url=nullptr,uint32_t live=480,uint32_t slices=8){
 Config cfg(WTSVariant::createObject());auto daily=WTSVariant::createObject();daily->append("path",storage);cfg->append("daily",daily);daily->release();
 if(!url){auto native=WTSVariant::createObject();native->append("path",storage);cfg->append("minute_native",native);native->release();}
 cfg->append("base_url",url?url:"unused-native-url");cfg->append("token_env","NMR_HTTP_TOKEN");cfg->append("policy_id","fixture-policy");
 cfg->append("max_bars",uint32_t(120));cfg->append("max_live_bars",live);cfg->append("max_slices",slices);
 auto symbols=WTSVariant::createArray();auto item=WTSVariant::createObject();item->append("std_code","SSE.STK.600000");item->append("symbol","600000.SH");symbols->append(item);item->release();cfg->append("symbols",symbols);symbols->release();return cfg;
}
}
int main(int argc,char** argv){try{
 check(argc==7||argc==8,"dll/storage/sessions/commodities/contracts/mode/[http url]");
 auto dll=LoadLibraryA(argv[1]);check(dll!=nullptr,"DLL unavailable");
 auto make=(FuncCreateDataReader)GetProcAddress(dll,"createDataReader");auto remove=(FuncDeleteDataReader)GetProcAddress(dll,"deleteDataReader");auto stop=(bool(*)(IDataReader*,uint32_t))GetProcAddress(dll,"stopDataReader");check(make&&remove&&stop,"managed exports missing");
 Sink sink;check(sink.base.loadSessions(argv[3])&&sink.base.loadCommodities(argv[4])&&sink.base.loadContracts(argv[5]),"real base missing");
 unsigned passed=0;
 auto reader=[&](Config& cfg,Loader* loader=nullptr){std::unique_ptr<IDataReader,FuncDeleteDataReader> r(make(),remove);check(bool(r),"create");r->init(cfg.get(),&sink,loader);return r;};
 if(std::string(argv[6])=="http"){
  check(argc==8,"HTTP URL missing");auto cfg=config(argv[2],argv[7]);Loader loader;auto r=reader(cfg,&loader);
  Slice s(r->readKlineSlice("SSE.STK.600000",KP_Minute1,2,202610210933ULL));check(s&&s->size()==2&&s->at(0)->close==10.5,"default HTTP changed");
  Slice day(r->readKlineSlice("SSE.STK.600000",KP_DAY,1));check(day&&day->size()==1&&day->at(0)->date==20261028&&day->at(0)->close==11,"default daily changed");
  check(stop(r.get(),3000),"default stop");r.reset();check(s->at(0)->close==10.5&&day->at(0)->close==11,"default retained copies");passed=1;
 }else{
  {auto cfg=config(argv[2]);auto r=reader(cfg);Slice a(r->readKlineSlice("SSE.STK.600000",KP_Minute1,120,202610290932ULL));check(a&&a->size()==2,"short window");
   check(!r->readKlineSlice("SSE.STK.600000",KP_Minute1,120,202610290930ULL),"empty window");
   check(!r->readKlineSlice("SSE.STK.600000",KP_Minute1,1,202610291131ULL),"future cutoff");
   check(!r->readKlineSlice("SSE.STK.600000",KP_Minute1,121),"request capacity");
   check(!r->readKlineSlice("SSE.STK.600001",KP_Minute1,1),"unmapped symbol");check(stop(r.get(),3000),"normal stop");++passed;}
  for(int bad=0;bad<7;++bad){auto cfg=config(argv[2]);
   if(bad==0)cfg->get("minute_native")->append("extra",uint32_t(1));
   if(bad==1)cfg->get("minute_native")->append("path",uint32_t(1));
   if(bad==2)cfg->get("minute_native")->append("adjust_flag",uint32_t(8));
   if(bad==3)cfg->append("minute_native",true);
   if(bad==4)cfg->append("max_bars",true);
   if(bad==5)cfg->get("symbols")->get(uint32_t(0))->append("symbol","600001.SH");
   if(bad==6){cfg->get("symbols")->get(uint32_t(0))->append("std_code","SSE.STK.999999");cfg->get("symbols")->get(uint32_t(0))->append("symbol","999999.SH");}
   auto r=reader(cfg);check(!r->readKlineSlice("SSE.STK.600000",KP_Minute1,1),"invalid config accepted");check(stop(r.get(),3000),"failed-init stop");++passed;}
  for(int bad=0;bad<5;++bad){auto cfg=config(argv[2]);auto native=cfg->get("minute_native");
   if(bad==0){native->append("path",std::string(233,'p').c_str());native->append("his_path","h");} // RT filename 256 incl no NUL.
   if(bad==1){native->append("path",std::string(230,'p').c_str());native->append("his_path",std::string(230,'h').c_str());}
   if(bad==2){native->append("path","p");native->append("his_path",std::string(438,'h').c_str());} // Init log 512 incl no NUL.
   if(bad==3)native->append("adjfactor",std::string(500,'a').c_str());
   if(bad==4)cfg->get("daily")->append("path",std::string(300,'p').c_str());
   const auto before=sink.initialized;auto r=reader(cfg);check(sink.initialized==before,"unsafe path reached upstream init");
   check(!r->readKlineSlice("SSE.STK.600000",KP_Minute1,1)&&stop(r.get(),3000),"unsafe path accepted");++passed;}
  for(int edge=0;edge<2;++edge){auto cfg=config(argv[2]);auto native=cfg->get("minute_native");
   if(edge==0){native->append("path",std::string(232,'p').c_str());native->append("his_path","h");} // RT filename 255 plus NUL.
   else{native->append("path","p");native->append("his_path",std::string(437,'h').c_str());} // Init log 511 plus NUL.
   Loader loader;loader.minute=[]{};const auto before=sink.initialized;auto r=reader(cfg,&loader);
   Slice s(r->readKlineSlice("SSE.STK.600000",KP_Minute1,1,202610290931ULL));
   check(sink.initialized==before+2&&s&&s->size()==1&&s->at(0)->close==11,"safe upstream path boundary rejected");check(stop(r.get(),3000),"path boundary stop");++passed;}
  {auto cfg=config(argv[2],nullptr,240,8);auto r=reader(cfg);Slice a(r->readKlineSlice("SSE.STK.600000",KP_Minute1,120));Slice b(r->readKlineSlice("SSE.STK.600000",KP_Minute1,120));check(a&&b&&!r->readKlineSlice("SSE.STK.600000",KP_Minute1,1),"live copy budget");a.reset();Slice c(r->readKlineSlice("SSE.STK.600000",KP_Minute1,1));check(bool(c),"release quota");check(stop(r.get(),3000),"copy stop");r.reset();check(b->size()==120&&c->size()==1,"post-delete copy");++passed;}
  {auto cfg=config(argv[2],nullptr,480,1);auto r=reader(cfg);Slice a(r->readKlineSlice("SSE.STK.600000",KP_Minute1,1));check(a&&!r->readKlineSlice("SSE.STK.600000",KP_Minute1,1),"slice count budget");check(stop(r.get(),3000),"slice stop");++passed;}
  {auto cfg=config(argv[2]);Loader loader;auto r=reader(cfg,&loader);Slice day(r->readKlineSlice("SSE.STK.600000",KP_DAY,1));check(day&&day->at(0)->close==11&&r->getAdjFactorByDate("SSE.STK.600000")==1,"native daily unchanged");check(stop(r.get(),3000),"day stop");++passed;}
  {auto cfg=config(argv[2]);auto r=reader(cfg);Slice warm(r->readKlineSlice("SSE.STK.600000",KP_Minute1,1,202610290931ULL));check(bool(warm),"callback warmup");bool result=true;bool reentered=true;
   sink.callback=[&]{if(sink.events==1){reentered=r->readKlineSlice("SSE.STK.600000",KP_Minute1,1)!=nullptr;result=stop(r.get(),20);}};
   r->onMinuteEnd(20261029,1130);check(!result&&!reentered,"callback stop/reentry");sink.callback={};check(stop(r.get(),3000),"callback control stop");r.reset();check(warm->size()==1,"callback held slice");++passed;}
  {sink.events=0;auto cfg=config(argv[2]);auto r=reader(cfg);Slice warm(r->readKlineSlice("SSE.STK.600000",KP_Minute1,1,202610290931ULL));check(bool(warm),"flight warmup");std::mutex mutex;std::condition_variable cv;bool entered=false,released=false;
   sink.callback=[&]{if(sink.events==1){std::unique_lock<std::mutex> lock(mutex);entered=true;cv.notify_all();cv.wait(lock,[&]{return released;});}};
   std::thread event([&]{r->onMinuteEnd(20261029,1130);});{std::unique_lock<std::mutex> lock(mutex);check(cv.wait_for(lock,std::chrono::seconds(2),[&]{return entered;}),"flight admission");}
   check(!stop(r.get(),20),"inflight stop falsely complete");std::thread release([&]{std::this_thread::sleep_for(std::chrono::milliseconds(50));std::lock_guard<std::mutex> lock(mutex);released=true;cv.notify_all();});
   check(stop(r.get(),3000),"control did not drain native callback");release.join();event.join();sink.callback={};r.reset();check(warm->size()==1,"flight copy lost");++passed;}
  {auto cfg=config(argv[2]);Loader loader;std::mutex mutex;std::condition_variable cv;bool entered=false,released=false;
   loader.minute=[&]{std::unique_lock<std::mutex> lock(mutex);entered=true;cv.notify_all();cv.wait(lock,[&]{return released;});};auto r=reader(cfg,&loader);WTSKlineSlice* result=nullptr;
   std::thread read([&]{result=r->readKlineSlice("SSE.STK.600000",KP_Minute1,1,202610290931ULL);});
   {std::unique_lock<std::mutex> lock(mutex);check(cv.wait_for(lock,std::chrono::seconds(2),[&]{return entered;}),"native read admission");}
   check(!stop(r.get(),20),"inflight native read falsely complete");{std::lock_guard<std::mutex> lock(mutex);released=true;cv.notify_all();}
   read.join();check(result==nullptr&&stop(r.get(),3000),"native read drain failed");++passed;}
  {auto cfg=config(argv[2]);cfg->append("timeout_ms",uint32_t(10));Loader loader;loader.minute=[]{std::this_thread::sleep_for(std::chrono::milliseconds(25));};auto r=reader(cfg,&loader);
   check(!r->readKlineSlice("SSE.STK.600000",KP_Minute1,1,202610290931ULL),"late native read accepted");check(stop(r.get(),3000),"late read stop");++passed;}
 }
 std::cout<<"{\"passed\":true,\"cases\":"<<passed<<",\"orders\":0}"<<std::endl;return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<std::endl;return 2;}}
