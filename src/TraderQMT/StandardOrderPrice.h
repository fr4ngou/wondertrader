#pragma once
#include <algorithm>
#include <charconv>
#include <cmath>
#include <limits>
#include <string>
#include <stdexcept>
namespace guanheng {
// 复用原Standard限价文本编码，仅消除已处在原品种tick附近的double噪声。
inline void standard_price_require(bool value,const char* reason){if(!value)throw std::runtime_error(reason);}
inline std::string standard_order_price_text(double value,double tick)
{standard_price_require(std::isfinite(value)&&value>0,"qmt_standard_price_invalid");
 char buffer[128];const auto out=std::to_chars(buffer,buffer+sizeof(buffer),value,std::chars_format::general);
 standard_price_require(out.ec==std::errc{},"qmt_standard_price_encoding_failed");const std::string original(buffer,out.ptr);
 // 原股票执行器以整数档位乘double tick，2.885可产生2.8850000000000002。
 // 仅消除已落在WT合约档位附近的浮点运算误差；真实离档价格保持原文，由Source原规则核验。
 if(!std::isfinite(tick)||tick<=0)return original;
 const double steps=std::round(value/tick),canonical=steps*tick;
 const double tolerance=4*std::numeric_limits<double>::epsilon()*(std::max)(value,std::fabs(canonical));
 if(!std::isfinite(steps)||steps<1||steps>9007199254740991.0||!std::isfinite(canonical)
  ||tolerance>=tick/4||std::fabs(value-canonical)>tolerance)return original;
 const auto encoded_tick=std::to_chars(buffer,buffer+sizeof(buffer),tick,std::chars_format::general);
 standard_price_require(encoded_tick.ec==std::errc{},"qmt_standard_price_encoding_failed");const std::string text(buffer,encoded_tick.ptr);
 const auto e=text.find_first_of("eE"),dot=text.find('.');const auto end=e==std::string::npos?text.size():e;
 int exponent=0;
 if(e!=std::string::npos){const char* first=text.data()+e+1;if(*first=='+')++first;
  const auto parsed=std::from_chars(first,text.data()+text.size(),exponent);
  if(parsed.ec!=std::errc{}||parsed.ptr!=text.data()+text.size())return original;}
 const int precision=(std::max)(0,(dot!=std::string::npos?static_cast<int>(end-dot-1):0)-exponent);
 if(precision>18)return original;
 const auto normalized=std::to_chars(buffer,buffer+sizeof(buffer),canonical,std::chars_format::fixed,precision);
 standard_price_require(normalized.ec==std::errc{},"qmt_standard_price_encoding_failed");return {buffer,normalized.ptr};}
}
