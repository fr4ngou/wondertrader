#ifndef NOMINMAX
#define NOMINMAX
#endif
#include "QmtTickMapping.h"
#include "../GuanhengCommon/BoundedSignedHttp.h"
#include <rapidjson/document.h>
#include <rapidjson/stringbuffer.h>
#include <rapidjson/writer.h>
#include <windows.h>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <stdexcept>
#include <set>

namespace guanheng
{
namespace qmt_mapping
{
using Json = rapidjson::Value;
constexpr std::uint64_t windows_epoch_ms = 11644473600000ULL;
constexpr std::uint64_t china_offset_ms = 8 * 60 * 60 * 1000ULL;
constexpr std::uint64_t maximum_epoch_ms = 4102444799999ULL;
Status invalid(const char* reason){return {ErrorCode::InvalidInput,reason};}
bool same_source(const SourceSession& a,const SourceSession& b)
{return a.provider==b.provider&&a.instance_id==b.instance_id&&a.session_id==b.session_id&&a.generation==b.generation;}
std::string qmt_symbol(const std::string& symbol)
{
    auto dot=symbol.find('.');
    if(dot==std::string::npos || symbol.size()!=dot+7 || (symbol.substr(0,dot)!="SSE"&&symbol.substr(0,dot)!="SZSE")
        || !std::all_of(symbol.begin()+dot+1,symbol.end(),[](char c){return c>='0'&&c<='9';}))
        throw std::invalid_argument("证券必须为 SSE/SZSE 加六位代码");
    return symbol.substr(dot+1)+(symbol.substr(0,dot)=="SSE"?".SH":".SZ");
}
std::uint64_t to_epoch(SYSTEMTIME time)
{
    FILETIME ft{};
    if(time.wYear<2004||time.wYear>2099||time.wMonth<1||time.wMonth>12||time.wDay<1||time.wDay>31
        ||time.wHour>23||time.wMinute>59||time.wSecond>59||time.wMilliseconds>999||!SystemTimeToFileTime(&time,&ft))
        throw std::invalid_argument("源日期超出有效范围");
    ULARGE_INTEGER raw{};raw.LowPart=ft.dwLowDateTime;raw.HighPart=ft.dwHighDateTime;
    SYSTEMTIME check{};FileTimeToSystemTime(&ft,&check);
    if(check.wYear!=time.wYear||check.wMonth!=time.wMonth||check.wDay!=time.wDay)
        throw std::invalid_argument("源日期非法");
    return raw.QuadPart/10000-windows_epoch_ms;
}
SYSTEMTIME from_epoch(std::uint64_t epoch,bool shanghai)
{
    if(epoch>maximum_epoch_ms)throw std::invalid_argument("源时间超出有效范围");
    ULARGE_INTEGER raw{};raw.QuadPart=(epoch+windows_epoch_ms+(shanghai?china_offset_ms:0))*10000;
    FILETIME ft{raw.LowPart,raw.HighPart};SYSTEMTIME time{};
    if(!FileTimeToSystemTime(&ft,&time)||time.wYear<2004||time.wYear>2099)
        throw std::invalid_argument("源时间超出有效范围");
    return time;
}
std::uint64_t request_epoch(std::uint64_t minute)
{
    SYSTEMTIME time{};time.wYear=static_cast<WORD>(minute/100000000);time.wMonth=static_cast<WORD>(minute/1000000%100);
    time.wDay=static_cast<WORD>(minute/10000%100);time.wHour=static_cast<WORD>(minute/100%100);time.wMinute=static_cast<WORD>(minute%100);
    return to_epoch(time)-china_offset_ms;
}
std::string qmt_time(std::uint64_t epoch)
{
    auto time=from_epoch(epoch,true);char text[20];std::snprintf(text,sizeof text,"%04u%02u%02u%02u%02u00",
        time.wYear,time.wMonth,time.wDay,time.wHour,time.wMinute);return text;
}
std::uint32_t date_of(const SYSTEMTIME& time){return time.wYear*10000+time.wMonth*100+time.wDay;}
const Json& member(const Json& object,const char* key)
{
    if(!object.IsObject()||!object.HasMember(key))throw std::invalid_argument("源结果缺少必要字段");
    unsigned occurrences=0;for(auto it=object.MemberBegin();it!=object.MemberEnd();++it)
        if(it->name.IsString()&&it->name.GetStringLength()==std::strlen(key)&&std::memcmp(it->name.GetString(),key,std::strlen(key))==0)++occurrences;
    if(occurrences!=1)throw std::invalid_argument("源结果必要字段重复");
    return object[key];
}
double number(const Json& object,const char* key)
{
    const auto& value=member(object,key);
    if(!value.IsNumber()||!std::isfinite(value.GetDouble()))throw std::invalid_argument("源价格或量额必须为有限数值");
    return value.GetDouble();
}
std::uint64_t epoch_of(const Json& object)
{
    const auto& value=member(object,"time");
    if(!value.IsNumber())throw std::invalid_argument("源 time 必须为 epoch_ms 整数数值");
    const auto milliseconds=value.GetDouble();
    // DataFrame records 可把整毫秒序列化为 .0。有效日期远低于 2^53，
    // 在转换前检查范围与整值，保留毫秒精度并避免浮点到整数溢出。
    if(!std::isfinite(milliseconds)||milliseconds<0||milliseconds>maximum_epoch_ms
        ||std::floor(milliseconds)!=milliseconds)
        throw std::invalid_argument("源 time 必须为有效范围内的整毫秒数值");
    auto epoch=static_cast<std::uint64_t>(milliseconds);from_epoch(epoch,false);return epoch;
}
void validate_prices(double open,double high,double low,double close,double volume,double money)
{
    if(open<=0||low<=0||high<low||open<low||open>high||close<low||close>high||volume<0||money<0
        ||!std::isfinite(volume)||!std::isfinite(money))throw std::invalid_argument("源 OHLC 或归一化量额非法");
}
rapidjson::Document parse(const std::string& text)
{
    rapidjson::Document document;
    if(!parse_bounded_qmt_json(text,document)||!document.IsObject())throw std::invalid_argument("源结果 JSON 非法");
    return document;
}
Status check_profile(const QmtHttpProfile& profile)
{
    if(profile.version.empty()||profile.source_license.empty()||profile.version.size()>256||profile.source_license.size()>4096
        ||profile.time_encoding!="epoch_ms"||(profile.minute_boundary!="left"&&profile.minute_boundary!="right")
        ||!std::isfinite(profile.volume_to_shares)||profile.volume_to_shares<=0
        ||!std::isfinite(profile.amount_to_yuan)||profile.amount_to_yuan<=0)
        return {ErrorCode::Unavailable,"缺少完整且合格的 QMT 源 profile"};
    return {};

}
std::vector<MarketSnapshot> map_ticks(const std::vector<std::string>& codes,const std::string& data_json,
    const QmtHttpProfile& profile,const SourceSession& source,bool omit_unformed)
{
    if(codes.empty()||codes.size()>200)throw std::invalid_argument("快照证券数量非法");
    auto data=parse(data_json);
    if(data.MemberCount()!=codes.size())throw std::invalid_argument("快照证券范围不一致");
    std::vector<MarketSnapshot> snapshots;snapshots.reserve(codes.size());
    std::set<std::string> requested;
    for(const auto& code:codes)
    {
        const auto symbol=qmt_symbol(code);
        if(!requested.insert(symbol).second)throw std::invalid_argument("快照请求证券重复");
        const auto& row=member(data,symbol.c_str());const auto epoch=epoch_of(row);
        const auto time=from_epoch(epoch,true);MarketSnapshot snapshot{};snapshot.source=source;
        snapshot.full_cumulative=true;snapshot.source_time_verified=true;auto& tick=snapshot.tick;
        const auto dot=code.find('.');std::memcpy(tick.exchg,code.data(),dot);std::memcpy(tick.code,code.data()+dot+1,6);
        tick.action_date=tick.trading_date=date_of(time);tick.action_time=(time.wHour*10000+time.wMinute*100+time.wSecond)*1000+time.wMilliseconds;
        tick.price=number(row,"lastPrice");tick.open=number(row,"open");tick.high=number(row,"high");tick.low=number(row,"low");tick.pre_close=number(row,"lastClose");
        tick.total_volume=number(row,"volume")*profile.volume_to_shares;tick.total_turnover=number(row,"amount")*profile.amount_to_yuan;
        if(tick.pre_close<=0)throw std::invalid_argument("昨收价非法");
        // 沪深开盘前完整原快照可能只有昨收区间和竞价参考价，尚无当日OHLC。
        // 仅此精确形状跳过投递；保留原结果消费责任，不生成/修补WT tick。
        if(omit_unformed && time.wHour<10 && (time.wHour<9 || time.wMinute<30)
            && tick.open==0 && tick.total_volume==0 && tick.total_turnover==0
            && tick.price>0 && tick.high==tick.pre_close && tick.low==tick.pre_close)
            continue;
        validate_prices(tick.open,tick.high,tick.low,tick.price,tick.total_volume,tick.total_turnover);
        snapshots.push_back(std::move(snapshot));
    }
    return snapshots;
}
MarketSnapshot map_tick(const std::string& code,const std::string& data_json,
    const QmtHttpProfile& profile,const SourceSession& source)
{
    return map_ticks({code},data_json,profile,source).front();
}
}
}
