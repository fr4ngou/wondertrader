// Isolated QA dependencies only. No prices, signals, callbacks or trading decisions.
#include "Includes/CtaStrategyDefs.h"
#include "Includes/IParserApi.h"
#include "Includes/IDataReader.h"
#include <cstdint>
class QuietStrategy final:public CtaStrategy {
public: explicit QuietStrategy(const char* id):CtaStrategy(id){}
 const char* getName()override{return "Quiet";}
 const char* getFactName()override{return "ReadSourceQA";}
};
class QuietFactory final:public ICtaStrategyFact {
public: const char* getName()override{return "ReadSourceQA";}
 void enumStrategy(FuncEnumStrategyCallback cb)override{cb(getName(),"Quiet",true);}
 CtaStrategy* createStrategy(const char*,const char* id)override{return new QuietStrategy(id);}
 bool deleteStrategy(CtaStrategy* p)override{delete p;return true;}
};
class QuietParser final:public wtp::IParserApi {
public: bool init(wtp::WTSVariant*)override{return true;}
 bool connect()override{return true;}
 bool disconnect()override{return true;}
 bool isConnected()override{return true;}
};
class EmptyReader final:public wtp::IDataReader {
public: void onMinuteEnd(uint32_t,uint32_t,uint32_t)override{}
 wtp::WTSTickSlice* readTickSlice(const char*,uint32_t,uint64_t)override{return nullptr;}
 wtp::WTSKlineSlice* readKlineSlice(const char*,wtp::WTSKlinePeriod,uint32_t,uint64_t)override{return nullptr;}
};
extern "C" {
__declspec(dllexport) ICtaStrategyFact* createStrategyFact(){return new QuietFactory;}
__declspec(dllexport) void deleteStrategyFact(ICtaStrategyFact*& p){delete p;p=nullptr;}
__declspec(dllexport) wtp::IParserApi* createParser(){return new QuietParser;}
__declspec(dllexport) void deleteParser(wtp::IParserApi*& p){delete p;p=nullptr;}
__declspec(dllexport) bool stopParser(wtp::IParserApi*,uint32_t){return true;}
__declspec(dllexport) wtp::IDataReader* createDataReader(){return new EmptyReader;}
__declspec(dllexport) void deleteDataReader(wtp::IDataReader* p){delete p;}
__declspec(dllexport) bool stopDataReader(wtp::IDataReader*,uint32_t){return true;}
}
