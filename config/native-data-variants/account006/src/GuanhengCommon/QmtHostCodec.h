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
bool hex(const rapidjson::Value&, std::size_t);
bool uuid(const rapidjson::Value&);
std::string encode(const rapidjson::Value&);
std::string base64(const std::string&);
bool unbase64(const rapidjson::Value&, std::size_t, std::string&);
// 版本来自受信入口；原读取默认1.0，交易选2.0，显式bulk入口选3.0。
bool binding(const rapidjson::Value&, SourceSession* source = nullptr,
    const char* expected_version = "1.0");
} }
