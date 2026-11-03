#pragma once
#include "ProviderTypes.h"
#include <rapidjson/document.h>
#include <cstddef>
#include <initializer_list>
#include <string>

namespace guanheng { namespace qmt_host_codec {
// 共用原协议编码；调用者先用有界 JSON parser 校验 UTF-8 和重复字段。
std::string text(const rapidjson::Value&);
bool string(const rapidjson::Value&, std::size_t maximum = 128);
bool field(const rapidjson::Value&, const char*, std::size_t maximum = 128);
bool keys(const rapidjson::Value&, std::initializer_list<const char*>);
// Host或Source-profile显式声明的同一保留预算；schema固定，期限为100..300000整数毫秒。
inline bool read_retention_capability(const rapidjson::Value& value,std::uint32_t& lifetime)
{
    if(!keys(value,{"schema","max_lifetime_ms"})||!field(value,"schema")
        ||text(value["schema"])!="qmt.read-retention.v1"||!value["max_lifetime_ms"].IsUint()
        ||value["max_lifetime_ms"].GetUint()<100||value["max_lifetime_ms"].GetUint()>300000)return false;
    lifetime=value["max_lifetime_ms"].GetUint();return true;
}
bool hex(const rapidjson::Value&, std::size_t);
bool uuid(const rapidjson::Value&);
std::string encode(const rapidjson::Value&);
std::string base64(const std::string&);
bool unbase64(const rapidjson::Value&, std::size_t, std::string&);
// 版本来自受信入口；原读取默认1.0，交易选2.0，显式bulk入口选3.0。
bool binding(const rapidjson::Value&, SourceSession* source = nullptr,
    const char* expected_version = "1.0");
} }
