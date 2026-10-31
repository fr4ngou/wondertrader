#pragma once
#include <rapidjson/document.h>
#include <rapidjson/reader.h>
#include <rapidjson/memorystream.h>
#include <rapidjson/writer.h>
#include <rapidjson/stringbuffer.h>
#include <set>
#include <string>
#include <vector>
#include <stdexcept>
#include <cstring>
namespace guanheng { namespace bootstrap {
namespace protocol {
constexpr unsigned max_rows=4096, max_nodes=65536, max_depth=12;
constexpr std::size_t fixture_bytes=1024*1024, envelope_bytes=2*1024*1024;
constexpr std::size_t default_view_bytes=16*1024*1024, hard_view_bytes=64*1024*1024;
constexpr const char* operation="account.trade_detail";
constexpr const char* schema="qmt.account-query.v1";
constexpr const char* profile="cny_cash_shsz_v1";
constexpr const char* datatypes[]={"position","order","deal","account"};
constexpr const char* mapping_version="nqh.trade-id.v1";
}
inline void check(bool yes,const char* why){if(!yes)throw std::runtime_error(why);}
// DOM前的迭代SAX拥有唯一结构预算；极深输入先拒绝，不能依靠递归后的检查保护调用栈。
struct JsonBudget:rapidjson::BaseReaderHandler<rapidjson::UTF8<>,JsonBudget> {
 struct Frame{bool object;unsigned count=0;std::set<std::string> keys;};
 std::vector<Frame> frames;unsigned nodes=0;const char* reason="JSON解析失败";
 bool reject(const char* s){reason=s;return false;}
 bool value(){if(frames.size()>protocol::max_depth)return reject("JSON深度超限");if(++nodes>protocol::max_nodes)return reject("JSON节点超限");if(!frames.empty()&&!frames.back().object&&++frames.back().count>protocol::max_rows)return reject("JSON数组超限");return true;}
 bool Null(){return value();}bool Bool(bool){return value();}bool Int(int){return value();}bool Uint(unsigned){return value();}bool Int64(std::int64_t){return value();}bool Uint64(std::uint64_t){return value();}bool Double(double){return value();}
 bool String(const char*,rapidjson::SizeType n,bool){if(n>262144)return reject("JSON字段文本超限");return value();}
 bool StartObject(){if(!value())return false;frames.push_back({true});return true;}bool StartArray(){if(!value())return false;frames.push_back({false});return true;}
 bool EndObject(rapidjson::SizeType){frames.pop_back();return true;}bool EndArray(rapidjson::SizeType){frames.pop_back();return true;}
 bool Key(const char* p,rapidjson::SizeType n,bool){if(n>256||std::memchr(p,0,n))return reject("JSON字段名非法");auto& f=frames.back();if(++f.count>protocol::max_rows)return reject("JSON对象超限");if(!f.keys.emplace(p,n).second)return reject("JSON重复字段");return true;}
};
inline void parse_json(rapidjson::Document& d,const std::string& s,std::size_t cap=protocol::fixture_bytes){
 check(s.size()<=cap&&s.find('\0')==std::string::npos,"JSON字节容量或编码非法");
 // 来源值和 inspection 会再次经过本边界；完整精度防止重复解析累积末位偏移。
 constexpr unsigned flags=rapidjson::kParseIterativeFlag|rapidjson::kParseValidateEncodingFlag|rapidjson::kParseFullPrecisionFlag;
 rapidjson::MemoryStream input(s.data(),s.size());rapidjson::Reader r;JsonBudget b;check(bool(r.Parse<flags>(input,b)),b.reason);d.Parse<flags>(s.data(),s.size());check(!d.HasParseError(),"JSON解析失败");
}
inline std::string json_text(const rapidjson::Value& v){rapidjson::StringBuffer b;rapidjson::Writer<rapidjson::StringBuffer> w(b);check(v.Accept(w),"JSON编码失败");return {b.GetString(),b.GetSize()};}
}}
