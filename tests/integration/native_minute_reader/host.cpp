// 固定原CTA/WtDtMgr的require_stop装配；不启动ticker/parser/trader或执行器。
#include "WtCore/WtCtaEngine.h"
#include "WtCore/WtDtMgr.h"
#include "WtCore/WtHelper.h"
#include "WTSTools/WTSBaseDataMgr.h"
#include "WTSTools/WTSHotMgr.h"
#include "Includes/WTSVariant.hpp"
#include "Includes/WTSDataDef.hpp"
#include <filesystem>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <vector>
using namespace wtp;
namespace {
void check(bool ok,const char* reason){if(!ok)throw std::runtime_error(reason);}
template<class T>struct Release{void operator()(T* p)const{if(p)p->release();}};
}
int main(int argc,char** argv){try{
 check(argc==8,"plugin directory/storage/base3/day/work");
 auto work=std::filesystem::absolute(argv[7]);std::filesystem::current_path(work);
 auto generated=(work/"generated").string();WtHelper::setGenerateDir(generated.c_str());
 auto plugin=std::filesystem::absolute(argv[1]).generic_string()+"/";WtHelper::setInstDir(plugin.c_str());
 WTSBaseDataMgr base;WTSHotMgr hot;check(base.loadSessions(argv[3])&&base.loadCommodities(argv[4])&&base.loadContracts(argv[5]),"base data load failed");
 std::unique_ptr<WTSVariant,Release<WTSVariant>> engine_cfg(WTSVariant::createObject()),data_cfg(WTSVariant::createObject());
 engine_cfg->append("poolsize",uint32_t(0));
 auto store=WTSVariant::createObject();store->append("module","GuanhengRealtimeReader");
 auto native=WTSVariant::createObject();native->append("path",argv[2]);store->append("minute_native",native);native->release();
 auto daily=WTSVariant::createObject();daily->append("path",argv[2]);store->append("daily",daily);daily->release();
 store->append("max_bars",uint32_t(120));store->append("max_live_bars",uint32_t(480));
 auto mappings=WTSVariant::createArray();
 for(auto pair:std::vector<std::pair<std::string,std::string>>{{"SSE.ETF.510300","510300.SH"},{"SSE.STK.600000","600000.SH"},{"SZSE.STK.000001","000001.SZ"}}){auto item=WTSVariant::createObject();item->append("std_code",pair.first.c_str());item->append("symbol",pair.second.c_str());mappings->append(item);item->release();}
 store->append("symbols",mappings);mappings->release();data_cfg->append("store",store);store->release();
 WtDtMgr data;WtCtaEngine engine;engine.init(engine_cfg.get(),&base,&data,&hot,nullptr);
 engine.set_date_time(uint32_t(std::stoul(argv[6])),1130);engine.set_trading_date(uint32_t(std::stoul(argv[6])));
 check(data.init(data_cfg.get(),&engine,false,true)&&data.supports_stop(),"actual CTA managed reader admission failed");
 std::vector<WTSKlineSlice*> held;
 for(const char* code:{"SSE.ETF.510300","SSE.STK.600000","SZSE.STK.000001"}){
  auto slice=data.get_kline_slice(code,KP_Minute1,1,120);check(slice&&slice->size()==120,"CTA native minute data missing");held.push_back(slice);
 }
 check(engine.stop(),"CTA engine stop failed");check(data.stop(3000),"WtDtMgr did not genuinely stop reader");
 check(!data.reader()->readKlineSlice("SSE.ETF.510300",KP_Minute1,1),"stopped reader accepted CTA read");
 data.release();check(data.reader()==nullptr,"WtDtMgr did not delete reader");
 for(auto slice:held){check(slice->size()==120&&slice->at(0)->time%10000==931&&slice->at(-1)->time%10000==1130,"CTA retained copy lost");slice->release();}
 engine.release_contexts();
 std::cout<<"{\"passed\":true,\"managed_host\":\"original-WtCtaEngine-WtDtMgr\",\"require_stop\":true,\"symbols\":3,\"bars\":120,\"stop_release\":true,\"retained_after_delete\":true,\"orders\":0}"<<std::endl;return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<std::endl;return 2;}}
