#pragma once
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include "QmtHttpEndpoint.h"
#include <rapidjson/document.h>
#include <windows.h>
#include <vector>

namespace guanheng
{
namespace qmt_mapping
{
// 纯源profile/时间/量额投影；不执行I/O，不授来源资格。非法输入抛invalid_argument。
Status invalid(const char* reason);
bool same_source(const SourceSession& a,const SourceSession& b);
std::string qmt_symbol(const std::string& code);
std::uint64_t to_epoch(SYSTEMTIME time);
SYSTEMTIME from_epoch(std::uint64_t epoch,bool shanghai);
std::uint64_t request_epoch(std::uint64_t minute);
std::string qmt_time(std::uint64_t epoch);
std::uint32_t date_of(const SYSTEMTIME& time);
const rapidjson::Value& member(const rapidjson::Value& object,const char* key);
double number(const rapidjson::Value& object,const char* key);
std::uint64_t epoch_of(const rapidjson::Value& object);
void validate_prices(double open,double high,double low,double close,double volume,double amount);
rapidjson::Document parse(const std::string& text);
Status check_profile(const QmtHttpProfile& profile);
// 一次解析并完整校验最多 200 证券；任何缺失/重复/额外证券或非法值均失败，
// 返回前不交付部分结果，顺序与请求 codes 一致。
// omit_unformed仅供持续轮询：开盘前未形成OHLC的完整零成交原值不投递。
std::vector<MarketSnapshot> map_ticks(const std::vector<std::string>& codes,const std::string& data_json,
    const QmtHttpProfile& profile,const SourceSession& source,bool omit_unformed=false);
MarketSnapshot map_tick(const std::string& code,const std::string& data_json,
    const QmtHttpProfile& profile,const SourceSession& source);
}
}
