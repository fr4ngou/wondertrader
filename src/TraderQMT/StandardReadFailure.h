#pragma once
#include <rapidjson/document.h>
#include <cstring>

namespace guanheng { namespace standard_read_failure {
// 仅解释Common已验证的原Host终态；纯值函数不创建请求、不推导账户事实或委托结果。
inline bool text_is(const rapidjson::Value& object,const char* key,const char* expected)
{
 return object.IsObject()&&object.HasMember(key)&&object[key].IsString()
  &&object[key].GetStringLength()==std::strlen(expected)
  &&std::memcmp(object[key].GetString(),expected,std::strlen(expected))==0;
}
inline bool interrupted_account_read(const rapidjson::Value& native,const rapidjson::Value& envelope)
{
 if(!text_is(native,"operation_id","account.trade_detail")
  ||!text_is(envelope,"operation_id","account.trade_detail")
  ||!text_is(native,"error_code","operation_interrupted")
  ||!native.HasMember("ok")||!native["ok"].IsBool()||native["ok"].GetBool()
  ||!native.HasMember("data")||!native["data"].IsNull()
  ||!native.HasMember("request_id")||!native["request_id"].IsString()
  ||!envelope.HasMember("request_id")||!envelope["request_id"].IsString()
  ||native["request_id"].GetStringLength()!=envelope["request_id"].GetStringLength()
  ||std::memcmp(native["request_id"].GetString(),envelope["request_id"].GetString(),native["request_id"].GetStringLength())!=0)
  return false;
 // 原请求已派发、Host已结束原观察且没有SDK终态绑定；是否曾执行查询保持未知。
 // 此资格只允许下一轮读取，不授予重发下单、撤单或把失败投影为成功数组。
 return envelope.HasMember("dispatch_binding")&&envelope["dispatch_binding"].IsObject()
  &&envelope.HasMember("result_binding")&&envelope["result_binding"].IsNull();
}
}}
