// 原WtDataStorage/IDataReader拥有复权计算。本探针只复制有界切片，不写来源store。
#include <windows.h>
#include "Includes/IDataReader.h"
#include "Includes/WTSDataDef.hpp"
#include "Includes/WTSVariant.hpp"
#include "WTSTools/WTSBaseDataMgr.h"
#include "WTSUtils/WTSCfgLoader.h"
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

using namespace wtp;
template<class T>struct Release{void operator()(T* p)const{if(p)p->release();}};
struct Sink final:IDataReaderSink{
 WTSBaseDataMgr base;uint32_t basis=0;unsigned errors=0;
 IBaseDataMgr* get_basedata_mgr()override{return &base;}
 IHotMgr* get_hot_mgr()override{return nullptr;}
 uint32_t get_date()override{return basis;}
 uint32_t get_min_time()override{return 1500;}
 uint32_t get_secs()override{return 0;}
 void reader_log(WTSLogLevel ll,const char*)override{if(ll==LL_ERROR)++errors;}
 void on_bar(const char*,WTSKlinePeriod,WTSBarStruct*)override{throw std::runtime_error("unexpected live event");}
 void on_all_bar_updated(uint32_t)override{throw std::runtime_error("unexpected live update");}
};
std::vector<WTSBarStruct> copy(WTSKlineSlice* ptr){
 std::unique_ptr<WTSKlineSlice,Release<WTSKlineSlice>> slice(ptr);
 if(!slice||slice->size()<=0||slice->size()>20000)throw std::runtime_error("native slice count");
 std::vector<WTSBarStruct> values;
 for(uint32_t b=0;b<slice->get_block_counts();++b){
  auto count=slice->get_block_size(b);auto first=slice->get_block_addr(b);
  if(count>20000-values.size()||(count&&!first))throw std::runtime_error("native slice block");
  values.insert(values.end(),first,first+count);
 }
 if(values.size()!=slice->size())throw std::runtime_error("native slice total");
 return values;
}
void rows(std::ostream& out,const std::vector<WTSBarStruct>& values){
 out<<'[';uint32_t previous=0;
 for(size_t i=0;i<values.size();++i){const auto& b=values[i];
  if(b.date<=previous||!std::isfinite(b.close)||!std::isfinite(b.open)||!std::isfinite(b.high)
    ||!std::isfinite(b.low)||!std::isfinite(b.vol)||!std::isfinite(b.money))throw std::runtime_error("native bar values");
  previous=b.date;if(i)out<<',';out<<'['<<b.date<<','<<b.open<<','<<b.high<<','<<b.low<<','<<b.close<<','<<b.vol<<','<<b.money<<']';
 }out<<']';
}
int main(int argc,char** argv){
 try{
  if(argc!=4)throw std::runtime_error("expected dll/request/output");
  HMODULE module=LoadLibraryA(argv[1]);if(!module)throw std::runtime_error("native reader load");
  auto make=(FuncCreateDataReader)GetProcAddress(module,"createDataReader");
  auto destroy=(FuncDeleteDataReader)GetProcAddress(module,"deleteDataReader");
  if(!make||!destroy)throw std::runtime_error("native reader exports");
  std::unique_ptr<WTSVariant,Release<WTSVariant>> cfg(WTSCfgLoader::load_from_file(argv[2]));
  if(!cfg)throw std::runtime_error("native request");
  Sink sink;sink.basis=cfg->getUInt32("basis_date");
  if(!sink.base.loadSessions(cfg->getCString("sessions"))||!sink.base.loadCommodities(cfg->getCString("commodities"))
    ||!sink.base.loadContracts(cfg->getCString("contracts")))throw std::runtime_error("native base data");
  std::unique_ptr<IDataReader,FuncDeleteDataReader> reader(make(),destroy);
  reader->init(cfg.get(),&sink);
  std::ofstream out(argv[3],std::ios::binary);if(!out)throw std::runtime_error("native output");
  out<<std::setprecision(17)<<"{\"schema\":\"guanheng.native-adjusted-read.v1\",\"securities\":{";
  auto symbols=cfg->get("symbols");if(!symbols||symbols->size()!=8)throw std::runtime_error("native eight symbols");
  for(uint32_t i=0;i<symbols->size();++i){
   const std::string symbol=symbols->get(i)->asCString();
   if(symbol.size()!=9)throw std::runtime_error("native symbol");
   const std::string code=(symbol.substr(7)=="SH"?"SSE.ETF.":"SZSE.ETF.")+symbol.substr(0,6);
   auto raw=copy(reader->readKlineSlice(code.c_str(),KP_DAY,20000,uint64_t(sink.basis)*10000+1500));
   auto front=copy(reader->readKlineSlice((code+"-").c_str(),KP_DAY,20000,uint64_t(sink.basis)*10000+1500));
   if(i)out<<',';out<<'"'<<symbol<<"\":{\"raw\":";rows(out,raw);out<<",\"front\":";rows(out,front);out<<'}';
  }
  reader.reset();
  out<<"},\"reader_deleted\":true,\"slices_released\":true,\"reader_errors\":"<<sink.errors<<'}';out.close();
  if(!out||sink.errors)throw std::runtime_error("native read errors");
  if(!FreeLibrary(module))throw std::runtime_error("native unload");return 0;
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}
}
