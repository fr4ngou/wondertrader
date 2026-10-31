#include "GuanhengQmtBootstrap/ReadOnlyTrader.h"
#include "WTSUtils/WTSCfgLoader.h"
#include "Includes/WTSVariant.hpp"
#include <Windows.h>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <chrono>
#include <thread>
#define CHECK(x) do{if(!(x))throw std::runtime_error(#x);}while(false)
int main(int argc,char**argv){try{
 CHECK(argc==4);auto dll=LoadLibraryA(argv[1]);CHECK(dll);auto create=reinterpret_cast<wtp::ITraderApi*(*)()>(GetProcAddress(dll,"createTrader"));auto destroy=reinterpret_cast<void(*)(wtp::ITraderApi*&)>(GetProcAddress(dll,"deleteTrader"));auto inspect=reinterpret_cast<int(*)(wtp::ITraderApi*,guanheng::bootstrap::Diagnostics*)>(GetProcAddress(dll,"inspectReadOnlyTrader"));auto view=reinterpret_cast<int(*)(wtp::ITraderApi*,uint32_t,uint32_t,uint32_t,char*,uint32_t,uint32_t*)>(GetProcAddress(dll,"inspectReadOnlyTraderView"));CHECK(create&&destroy&&inspect&&view);
 auto cfg=WTSCfgLoader::load_from_file(argv[2]);CHECK(cfg);auto api=create();CHECK(api);bool expected=std::string(argv[3])=="valid";CHECK(api->init(cfg)==expected);guanheng::bootstrap::Diagnostics before;CHECK(inspect(api,&before)==0&&before.callbacks==0&&before.reads==0);
 auto begin=std::chrono::steady_clock::now();api->release();guanheng::bootstrap::Diagnostics after;do{CHECK(inspect(api,&after)==0);if(after.joined)break;api->release();}while(std::chrono::steady_clock::now()-begin<std::chrono::seconds(2));CHECK(after.phase==static_cast<unsigned>(guanheng::bootstrap::Phase::Closed)&&after.joined&&after.worker_live==0&&after.callbacks==0&&after.reads==0);
 uint32_t required=0;CHECK(view(api,2,0,0,nullptr,0,&required)==guanheng::bootstrap::Capacity);std::string out(required,'x');CHECK(view(api,2,0,0,&out[0],required,&required)==0);std::cout<<out.c_str();destroy(api);CHECK(!api);cfg->release();CHECK(FreeLibrary(dll));CHECK(GetModuleHandleA(argv[1])==nullptr);return 0;
}catch(const std::exception&e){std::cerr<<e.what();return 2;}}
