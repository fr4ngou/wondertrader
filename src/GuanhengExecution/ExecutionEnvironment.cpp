#include "ExecutionEnvironment.h"
#include "Includes/IBaseDataMgr.h"
#include "Includes/WTSContractInfo.hpp"
#include "Share/CodeHelper.hpp"
#include "Share/TimeUtils.hpp"
#include <ctime>
#include <cstring>
#include <limits>
#include <stdexcept>
#include <utility>

namespace guanheng {
namespace {
std::string session_name(const char* value) {
    if(!value)throw std::invalid_argument("execution_environment_session");
    std::size_t size=0;while(size<64&&value[size])++size;
    if(!size||size==64)throw std::invalid_argument("execution_environment_session");
    return {value,size};
}
// 原解析器接收已成形的标准代码；在本接入入口核2/3段及原定长缓冲容量。
bool standard_code(const char* code) {
    if(!code)return false;
    std::size_t size=0,segment=0,dots=0;
    while(size<MAX_INSTRUMENT_LENGTH&&code[size]) {
        const auto c=static_cast<unsigned char>(code[size]);
        if(c<=32||c>=127)return false;
        if(c=='.'){if(!segment||++dots>2)return false;segment=0;}else ++segment;
        ++size;
    }
    if(!size||size==MAX_INSTRUMENT_LENGTH||!segment||dots==0)return false;
    return dots!=2||(code[size-1]!='+'&&code[size-1]!='-')||segment>1;
}
std::uint64_t system_epoch_ms() {
    const auto value=TimeUtils::getLocalTimeNow();
    if(value<=0)throw std::runtime_error("execution_environment_clock");
    return static_cast<std::uint64_t>(value);
}
}
ExecutionEnvironment::ExecutionEnvironment(wtp::IBaseDataMgr& base,const char* reference_session,wtp::IHotMgr* hot,Clock clock)
    :base_(base),session_(session_name(reference_session)),hot_(hot),clock_(clock?std::move(clock):Clock(system_epoch_ms)),owner_(std::this_thread::get_id()) {
    if(!base_.getSession(session_.c_str()))throw std::invalid_argument("execution_environment_session");
}
void ExecutionEnvironment::assert_owner() const {
    if(owner_!=std::this_thread::get_id())throw std::runtime_error("execution_environment_wrong_owner");
}
ExecutionTimeObservation ExecutionEnvironment::observe() const {
    assert_owner();ExecutionTimeObservation value;value.epoch_ms=clock_();
    if(!value.epoch_ms||value.epoch_ms>static_cast<std::uint64_t>((std::numeric_limits<std::int64_t>::max)()))
        throw std::runtime_error("execution_environment_clock");
    const auto seconds=static_cast<std::time_t>(value.epoch_ms/1000);std::tm local={};
#ifdef _WIN32
    if(localtime_s(&local,&seconds)!=0)throw std::runtime_error("execution_environment_clock");
#else
    if(!localtime_r(&seconds,&local))throw std::runtime_error("execution_environment_clock");
#endif
    const auto year=local.tm_year+1900;
    if(year<1970||year>9999)throw std::runtime_error("execution_environment_clock");
    value.date=static_cast<std::uint32_t>(year*10000+(local.tm_mon+1)*100+local.tm_mday);
    value.time_ms=static_cast<std::uint32_t>(local.tm_hour*10000000+local.tm_min*100000+local.tm_sec*1000+value.epoch_ms%1000);
    // 原ticker也使用reference session及同一原生计算；不读取CTA线程的_cur_*字段。
    value.trading_day=base_.calcTradingDate(session_.c_str(),value.date,value.time_ms/100000,true);
    if(!value.trading_day)throw std::runtime_error("execution_environment_trading_day");
    return value;
}
std::uint64_t ExecutionEnvironment::get_real_time() { return observe().epoch_ms; }
wtp::WTSCommodityInfo* ExecutionEnvironment::get_comm_info(const char* code) {
    assert_owner();if(!standard_code(code))return nullptr;
    const auto key=CodeHelper::extractStdCode(code,nullptr);return base_.getCommodity(key._exchg,key._product);
}
wtp::WTSSessionInfo* ExecutionEnvironment::get_sess_info(const char* code) {
    auto* commodity=get_comm_info(code);return commodity?commodity->getSessionInfo():nullptr;
}
wtp::IHotMgr* ExecutionEnvironment::get_hot_mon() { assert_owner();return hot_; }
std::uint32_t ExecutionEnvironment::get_trading_day() { return observe().trading_day; }
}
