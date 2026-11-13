#include "AccountMapping.h"
#include "JsonBoundary.h"
#include "GuanhengCommon/QmtAccountFields.h"
#include "Includes/WTSTradeDef.hpp"
#include "Includes/WTSContractInfo.hpp"
#include "Includes/IBaseDataMgr.h"
#include <Windows.h>
#include <bcrypt.h>
#include <array>
#include <cmath>
#include <map>
#include <tuple>
#include <cstring>
#include <cstdio>
#include <initializer_list>
namespace guanheng { namespace bootstrap {
namespace {
using V=rapidjson::Value;using A=rapidjson::Document::AllocatorType;
// append(false)成功前数组尚未拥有新对象；扩容抛出时由临时owner调用release。
struct MappedObjectRelease {void operator()(wtp::WTSObject* value)const{if(value)value->release();}};
template<class T>T* append_owned(wtp::WTSArray& array,T* value){
 std::unique_ptr<T,MappedObjectRelease> owner(value);
 array.append(owner.get(),false);
 return owner.release();
}
const V& get(const V& v,const char* key){check(v.IsObject()&&v.HasMember(key),"HTTP来源缺少必需字段");return v[key];}
std::string str(const V& v,const char* k,std::size_t cap=63){const auto& x=get(v,k);check(x.IsString()&&x.GetStringLength()>0&&x.GetStringLength()<=cap,"HTTP字段文本类型或长度错误");std::string s(x.GetString(),x.GetStringLength());for(std::size_t i=0;i<s.size();++i){unsigned char c=s[i];check(c>=32&&c!=127&&!(c==0xc2&&i+1<s.size()&&static_cast<unsigned char>(s[i+1])>=0x80&&static_cast<unsigned char>(s[i+1])<=0x9f),"HTTP标识含控制字符");}return s;}
bool equal(const V& v,const char* k,const std::string& s){return v.IsObject()&&v.HasMember(k)&&v[k].IsString()&&s==std::string(v[k].GetString(),v[k].GetStringLength());}
double num(const V& v,const char* k,bool integer=false,bool nonnegative=false){const auto& n=get(v,k);check(n.IsNumber(),"HTTP数值类型错误");double x=n.GetDouble();check(std::isfinite(x)&&(!integer||(std::abs(x)<=9007199254740991.0&&std::floor(x)==x))&&(!nonnegative||x>=0),"HTTP数值范围错误");return x;}
void add(V& v,const char* k,const std::string& s,A& a){v.AddMember(V(k,a),V(s.data(),static_cast<unsigned>(s.size()),a),a);}
void add(V& v,const char* k,double n,A& a){v.AddMember(V(k,a),n,a);}
void fact(V& facts,const V& row,const char* k,A& a,bool numeric=true){
 V f(rapidjson::kObjectType);std::string availability="unknown",reason="来源未提供";V value;
 if(row.HasMember(k)&&!row[k].IsNull()){
  bool valid=numeric?row[k].IsNumber()&&std::isfinite(row[k].GetDouble()):row[k].IsString();
  availability=valid?"present":"invalid";reason=valid?"":"来源字段类型或数值非法";if(valid)value.CopyFrom(row[k],a);
 }
 add(f,"availability",availability,a);f.AddMember("value",value,a);add(f,"reason",reason,a);facts.AddMember(V(k,a),f,a);
}
std::optional<std::string> currency_value(const V& row,const std::string& expected){
 const char* key=::guanheng::account_fields::money;
 if(!row.HasMember(key))return {};
 check(row[key].IsString()&&(row[key].GetStringLength()==0||equal(row,key,expected)),"行币种与显式绑定冲突");
 return std::string(row[key].GetString(),row[key].GetStringLength());
}
void currency_fact(V& facts,const V& row,const std::string& expected,A& a){
 const char* key=::guanheng::account_fields::money;
 // SDK空串保持在原DTO；观察事实只表达来源未知，ABI仍由部署声明负责。
 const auto value=currency_value(row,expected);
 if(value&&!value->empty()){fact(facts,row,key,a,false);return;}
 V f(rapidjson::kObjectType);add(f,"availability","unknown",a);f.AddMember("value",V(),a);
 add(f,"reason",row.HasMember(key)?"来源币种为空字符串":"来源未提供币种",a);facts.AddMember(V(key,a),f,a);
}
void abi(V& v,const char* k,double n,const char* why,A& a){V f(rapidjson::kObjectType);f.AddMember("value",n,a);add(f,"mapping",why,a);v.AddMember(V(k,a),f,a);}
void abi(V& v,const char* k,const std::string& s,const char* why,A& a){V f(rapidjson::kObjectType);add(f,"value",s,a);add(f,"mapping",why,a);v.AddMember(V(k,a),f,a);}
bool digits(const std::string& s){return !s.empty()&&s.find_first_not_of("0123456789")==std::string::npos;}
bool valid_date(unsigned n){unsigned y=n/10000,m=n/100%100,d=n%100;if(y<1||y>9999||m<1||m>12)return false;unsigned ds[]={31,28,31,30,31,30,31,31,30,31,30,31};if(y%4==0&&(y%100!=0||y%400==0))ds[1]=29;return d>=1&&d<=ds[m-1];}
unsigned date(const std::string& s){std::string d=s;if(s.size()==10){check(s[4]=='-'&&s[7]=='-',"HTTP日期格式错误");d=s.substr(0,4)+s.substr(5,2)+s.substr(8,2);}check(d.size()==8&&digits(d),"HTTP日期格式错误");unsigned n=std::stoul(d);check(valid_date(n),"HTTP日期无效");return n;}
unsigned event_time(const std::string& s){
 auto dot=s.find('.');std::string base=s.substr(0,dot),frac=dot==std::string::npos?"":s.substr(dot+1);
 if(base.size()==8){check(base[2]==':'&&base[5]==':',"HTTP时间格式错误");base=base.substr(0,2)+base.substr(3,2)+base.substr(6,2);}
 // QMT成交回报使用数值式HHMMSS字符串，早盘09:53:02实际返回95302。
 // 仅在解释时间时左补零；原raw_time、原回报及委托/成交身份全部保持。
 check(base.size()>=1&&base.size()<=6&&digits(base)
  &&((dot==std::string::npos)||(!frac.empty()&&frac.size()<=3&&digits(frac))),"HTTP时间格式错误");
 base.insert(0,6-base.size(),'0');
 unsigned h=std::stoul(base.substr(0,2)),m=std::stoul(base.substr(2,2)),sec=std::stoul(base.substr(4,2));
 check(h<24&&m<60&&sec<60,"HTTP时间无效");while(frac.size()<3)frac+='0';return (h*10000+m*100+sec)*1000+std::stoul(frac);
}

// 同一解码器服务完整映射与部分检查。每字段只捕获既有事实校验异常；
// bad_alloc等资源异常继续传播，不能伪装成已完成的Invalid金融观察。
AccountRowInspection decode_trade_row(unsigned stage,const V& row,const AccountBinding& binding){
 using namespace ::guanheng::account_fields;
 using F=AccountFactField;
 AccountRowInspection out;auto& f=out.facts;
 auto bit=[](F field){return account_fact_bit(field);};
 for(auto field:{F::Code,F::Exchange,F::Order,F::Side,F::Date,F::Time,F::Quantity,F::Price})out.required|=bit(field);
 if(stage==1)for(auto field:{F::Filled,F::Remaining,F::State})out.required|=bit(field);
 else out.required|=bit(F::Trade)|bit(F::Amount);
 const auto optional=bit(F::Account)|bit(F::Currency)|(stage==1?bit(F::Cancel):0);
 if(!row.IsObject()){out.kind=AccountInspectionKind::Invalid;out.missing=out.required;out.unknown=optional;return out;}
 auto admit=[&](F field,const char* key,auto read){
  const auto flag=bit(field);if(!row.HasMember(key))return;
  out.present|=flag;
  try{if(read())out.valid|=flag;}catch(const std::runtime_error&){out.invalid|=flag;}
 };
 admit(F::Code,code,[&]{auto value=str(row,code);check(value.size()==6&&digits(value),"HTTP证券代码非法");f.code=std::move(value);return true;});
 admit(F::Exchange,exchange,[&]{auto value=str(row,exchange);check(value=="SH"||value=="SZ","HTTP证券市场非法");f.exchange=value=="SH"?"SSE":"SZSE";f.raw_exchange=std::move(value);return true;});
 admit(F::Account,account,[&]{check(equal(row,account,binding.account),"行账户与观察不符");f.account=std::string(row[account].GetString(),row[account].GetStringLength());return true;});
 admit(F::Currency,money,[&]{f.currency=currency_value(row,binding.currency);return !f.currency->empty();});
 admit(F::Order,order,[&]{f.order=str(row,order);return true;});
 if(stage==2)admit(F::Trade,trade,[&]{f.trade=str(row,trade);return true;});
 admit(F::Side,side,[&]{auto value=num(row,side,true,true);check(value==48||value==49,"HTTP股票买卖值未知");f.side=static_cast<unsigned>(value);return true;});
 const char* day_key=stage==1?insert_date:trade_date;const char* time_key=stage==1?insert_time:trade_time;
 admit(F::Date,day_key,[&]{auto raw=str(row,day_key,10);auto value=date(raw);f.raw_date=std::move(raw);f.date=value;return true;});
 admit(F::Time,time_key,[&]{auto raw=str(row,time_key,12);auto value=event_time(raw);f.raw_time=std::move(raw);f.time=value;return true;});
 const char* qty_key=stage==1?quantity:volume;const char* price_key=stage==1?limit_price:price;
 admit(F::Quantity,qty_key,[&]{auto value=num(row,qty_key,true,true);check(value>0,"HTTP委托或成交量必须正数");f.quantity=value;return true;});
 admit(F::Price,price_key,[&]{auto value=num(row,price_key,false,stage==1);check(stage==1||value>0,"HTTP成交价格必须正数");f.price=value;return true;});
 if(stage==1){
  admit(F::Filled,filled,[&]{f.filled=num(row,filled,true,true);return true;});
  admit(F::Remaining,remaining,[&]{f.remaining=num(row,remaining,true,true);return true;});
  // QMT 48为已创建但尚未报出的正常委托；原字段完整保留，不能按非法值或终态丢弃。
  admit(F::State,state,[&]{auto value=num(row,state,true,true);check(value>=48&&value<=57,"HTTP委托状态错误");f.state=static_cast<unsigned>(value);return true;});
  admit(F::Cancel,cancel,[&]{if(row[cancel].IsNull())return false;f.cancel=num(row,cancel,true,true);return true;});
 }else admit(F::Amount,amount,[&]{f.amount=num(row,amount,false,true);return true;});
 auto has=[&](std::initializer_list<F> fields){for(auto field:fields)if(!(out.valid&bit(field)))return false;return true;};
 if(stage==1){
  if(has({F::Quantity,F::Filled})&&*f.filled>*f.quantity)out.relations|=FilledExceedsQuantity;
  if(has({F::Quantity,F::Filled,F::Remaining})&&*f.remaining!=*f.quantity-*f.filled)out.relations|=RemainingMismatch;
  if(has({F::Quantity,F::Filled,F::State})&&*f.state==56&&*f.filled!=*f.quantity)out.relations|=AllTradedMismatch;
  if(has({F::Quantity,F::Filled,F::State,F::Cancel})){
   const bool canceled=*f.state==53||*f.state==54||*f.state==57;
   if(*f.cancel!=(canceled?*f.quantity-*f.filled:0))out.relations|=CancelMismatch;
  }
 }
 out.missing=out.required&~out.present;out.unknown=optional&~(out.valid|out.invalid);
 out.kind=out.invalid||out.relations?AccountInspectionKind::Invalid:out.missing?AccountInspectionKind::MissingRequired:AccountInspectionKind::Complete;
 out.locator_complete=out.kind!=AccountInspectionKind::Invalid&&has({F::Code,F::Exchange,F::Order})
  &&(stage==1||has({F::Trade,F::Date}));
 return out;
}

std::string utc(const std::string& s){check(s.size()>=20&&s[10]=='T',"执行区间缺少UTC语义");date(s.substr(0,10));check(s[13]==':'&&s[16]==':',"执行区间格式错误");auto end=s.find_first_of("Z+",19);check(end!=std::string::npos&&(s.substr(end)=="Z"||s.substr(end)=="+00:00"),"执行区间必须UTC");event_time(s.substr(11,8));if(end>19){check(s[19]=='.'&&end>=21&&end<=26&&digits(s.substr(20,end-20)),"执行区间小数精度非法");}return s.substr(0,19)+"Z";}
void integer_fact(V& facts,const V& row,const char* key,A& a){fact(facts,row,key,a);if(row.HasMember(key)&&!row[key].IsNull()&&(!row[key].IsNumber()||std::floor(row[key].GetDouble())!=row[key].GetDouble()||row[key].GetDouble()<0||row[key].GetDouble()>9007199254740991.0)){auto& f=facts[key];f["availability"].SetString("invalid",a);f["value"].SetNull();f["reason"].SetString("来源数量不是有效非负精确整数",a);}}
bool present(const V& row,const char* k){return row.HasMember(k)&&row[k].IsNumber()&&std::isfinite(row[k].GetDouble());}
std::array<unsigned char,32> financial_digest(const std::string& input){
 check(input.size()<=0xffffffffULL,"规范事实摘要字节容量超限");
 BCRYPT_ALG_HANDLE alg=nullptr;BCRYPT_HASH_HANDLE hash=nullptr;
 // CNG要求pbHashObject存储晚于hash句柄释放；先声明缓冲区，再声明guard，使正常/异常退栈均先DestroyHash。
 std::vector<unsigned char> object;
 struct Cleanup{BCRYPT_ALG_HANDLE& a;BCRYPT_HASH_HANDLE& h;~Cleanup(){if(h)BCryptDestroyHash(h);if(a)BCryptCloseAlgorithmProvider(a,0);}} cleanup{alg,hash};
 check(BCryptOpenAlgorithmProvider(&alg,BCRYPT_SHA256_ALGORITHM,nullptr,0)>=0,"派生成交ID算法失败");DWORD bytes=0,received=0;check(BCryptGetProperty(alg,BCRYPT_OBJECT_LENGTH,reinterpret_cast<PUCHAR>(&bytes),sizeof(bytes),&received,0)>=0&&bytes<=65536,"派生成交ID容量失败");object.resize(bytes);std::array<unsigned char,32> digest{};
 check(BCryptCreateHash(alg,&hash,object.data(),bytes,nullptr,0,0)>=0&&BCryptHashData(hash,reinterpret_cast<PUCHAR>(const_cast<char*>(input.data())),static_cast<ULONG>(input.size()),0)>=0&&BCryptFinishHash(hash,digest.data(),32,0)>=0,"派生成交ID失败");
 return digest;
}
// 绑定域由caller提供；显式输出先沿现JSON编码边界校验UTF-8，避免跨域key歧义。
void canonical_admission(unsigned stage,const AccountBinding& binding,const AccountCanonicalLimits& limits){
 check((stage==1||stage==2)&&limits.max_records>=1&&limits.max_records<=protocol::max_rows
  &&limits.max_bytes>=1&&limits.max_bytes<=protocol::hard_view_bytes,"规范金融输出类型或容量非法");
 check((binding.environment=="live"||binding.environment=="simulation")&&binding.currency=="CNY"
  &&binding.profile==protocol::profile,"规范金融输出绑定非法");
 check(!binding.account.empty()&&binding.account.size()<=63,"规范金融输出账户长度非法");
 rapidjson::Document value;value.SetObject();add(value,"account",binding.account,value.GetAllocator());
 str(value,"account",63);rapidjson::Document validated;parse_json(validated,json_text(value),1024);
}
void canonical_record(AccountBatch& batch,const AccountCanonicalLimits* limits,unsigned stage,
 const AccountBinding& binding,const std::string& exchange,const std::string& code,unsigned day,
 const std::string& order,const std::string& trade,const std::string& normalized){
 if(!limits)return;
 check(batch.canonical_records.size()<limits->max_records,"规范金融输出记录容量超限");
 char date_text[9];check(std::snprintf(date_text,sizeof(date_text),"%08u",day)==8,"规范金融输出日期非法");
 rapidjson::Document key;key.SetArray();auto& a=key.GetAllocator();
 for(const auto& text:{std::string("guanheng.account-financial-key.v1"),std::string(stage==1?"order":"deal"),
  binding.account,binding.environment,binding.currency,binding.profile,exchange,code,std::string(date_text),order})
  key.PushBack(V(text.data(),static_cast<unsigned>(text.size()),a),a);
 if(stage==2)key.PushBack(V(trade.data(),static_cast<unsigned>(trade.size()),a),a);
 auto encoded=json_text(key);
 // 只计两个输出字符串和逻辑NUL；先减后比，失败时仍由局部batch回收全部WTS对象。
 check(encoded.size()<=limits->max_bytes&&limits->max_bytes-encoded.size()>=66,"规范金融输出字节容量超限");
 const auto bytes=encoded.size()+66;
 check(batch.canonical_bytes<=limits->max_bytes&&bytes<=limits->max_bytes-batch.canonical_bytes,"规范金融输出字节容量超限");
 const auto digest=financial_digest(normalized);static const char hex[]="0123456789abcdef";
 std::string fingerprint;fingerprint.reserve(64);for(auto value:digest){fingerprint+=hex[value>>4];fingerprint+=hex[value&15];}
 batch.canonical_records.push_back({std::move(encoded),std::move(fingerprint)});batch.canonical_bytes+=bytes;
}
}

AccountRowInspection inspect_account_row(unsigned stage,const std::string& raw,const AccountBinding& binding,
 const AccountInspectionLimits& limits){
 check((stage==1||stage==2)&&limits.max_input_bytes>=1&&limits.max_input_bytes<=protocol::fixture_bytes
  &&limits.max_output_bytes>=1&&limits.max_output_bytes<=4096,"部分事实检查参数或容量非法");
 check(raw.size()<=limits.max_input_bytes,"部分事实输入字节容量超限");
 // 复用原绑定准入，不产生规范摘要，也不触及WT/BaseData。
 canonical_admission(stage,binding,{1,limits.max_output_bytes});
 rapidjson::Document row;parse_json(row,raw,limits.max_input_bytes);
 auto out=decode_trade_row(stage,row,binding);
 out.source="guanheng.account-row-inspection.v1";out.binding=binding;out.input_bytes=raw.size();
 std::size_t used=256;
 auto charge=[&](const std::string& value){
  check(used<=limits.max_output_bytes&&value.size()<limits.max_output_bytes-used,"部分事实输出字节容量超限");
  used+=value.size()+1;
 };
 check(used<=limits.max_output_bytes,"部分事实输出字节容量超限");
 for(const auto* text:{&out.source,&out.binding.account,&out.binding.environment,&out.binding.currency,&out.binding.profile})charge(*text);
 for(const auto* value:{&out.facts.code,&out.facts.exchange,&out.facts.raw_exchange,&out.facts.account,&out.facts.currency,
   &out.facts.order,&out.facts.trade,&out.facts.raw_date,&out.facts.raw_time})if(*value)charge(**value);
 out.output_bytes=used;
 return out;
}

void initialize_account(wtp::WTSAccountInfo* p){p->setBalance(0);p->setPreBalance(0);p->setMargin(0);p->setFrozenMargin(0);p->setFrozenCommission(0);p->setCloseProfit(0);p->setDynProfit(0);p->setDeposit(0);p->setWithdraw(0);p->setCommission(0);p->setAvailable(0);}
std::string scoped_trade_id(const std::string& exchange,const std::string& code,unsigned date,const std::string& raw){
 // 固定原Adapter以TradeID单键检查自成交；命名空间排除order_id，保留同证券同日跨订单检测。
 char day[9];check(std::snprintf(day,sizeof(day),"%08u",date)==8,"派生成交日期超出规范");
 std::string input="guanheng.nqh.trade-id.v1";input+='\0';for(const auto& s:{exchange,code,std::string(day),raw}){unsigned n=static_cast<unsigned>(s.size());for(int shift=24;shift>=0;shift-=8)input+=static_cast<char>(n>>shift);input+=s;}
 const auto digest=financial_digest(input);
 static const char alphabet[]="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";std::string out="nqh1.";unsigned bits=0,value=0;for(unsigned char c:digest){value=(value<<8)|c;bits+=8;while(bits>=6){bits-=6;out+=alphabet[(value>>bits)&63];}}if(bits)out+=alphabet[(value<<(6-bits))&63];return out;
}
static AccountBatch map_account_rows_impl(unsigned stage,const rapidjson::Value& rows,
 const AccountBinding& binding,wtp::IBaseDataMgr* base,
 const AccountBatchMetadata* metadata,unsigned view_version,const AccountCanonicalLimits* canonical_limits,
 std::optional<std::size_t> selected={}){
 using namespace ::guanheng::account_fields;
 // 数组account_fields与外层Common命名空间同名；块内声明保持原循环无歧义。
 using ::guanheng::account_fields::account_fields;
 if(canonical_limits)canonical_admission(stage,binding,*canonical_limits);
 check(stage<4&&base,"HTTP批次或基础资料非法");
 check(view_version==2||view_version==3,"账户视图版本不支持");
 check(rows.IsArray()&&rows.Size()<=binding.row_limit&&(stage!=3||rows.Size()==1),"HTTP记录类型或数量非法");
 // 选择只改变取原行的下标，字段解码、金融去重和WT构造仍使用下面唯一循环。
 // 下标与所选对象在创建WT数组前验证；全批原准入顺序保持。
 if(selected)check((stage==1||stage==2)&&*selected<rows.Size()
  &&rows[static_cast<rapidjson::SizeType>(*selected)].IsObject(),"查询选择原行下标或类型非法");
 const rapidjson::SizeType count=selected?1:rows.Size();
 AccountBatch batch;batch.source_rows=count;
 // query由原UTC准入负责；event没有查询执行区间，不构造占位metadata。
 if(metadata){
  batch.source=metadata->source;batch.request_id=metadata->request_id;batch.result_sha=metadata->result_sha;
  batch.started=metadata->started;batch.finished=metadata->finished;
  utc(batch.started);batch.seconds=utc(batch.finished);
 }
 batch.array.reset(wtp::WTSArray::create());
 std::map<std::string,std::pair<std::string,std::size_t>> seen;
 std::map<std::string,std::string> reverse_ids;unsigned index=0;
 batch.source_to_output.reserve(count);
 for(rapidjson::SizeType ordinal=0;ordinal<count;++ordinal){
  const auto& row=rows[selected?static_cast<rapidjson::SizeType>(*selected):ordinal];
  check(row.IsObject(),"HTTP记录不是对象");
  AccountRowInspection decoded;
  if(stage==1||stage==2){decoded=decode_trade_row(stage,row,binding);check(decoded.kind==AccountInspectionKind::Complete,"HTTP委托或成交必需事实缺失或非法");}
  else if(row.HasMember(account))check(equal(row,account,binding.account),"行账户与观察不符");
  rapidjson::Document v;v.SetObject();auto& a=v.GetAllocator();v.AddMember("version",view_version,a);v.AddMember("view",stage+1,a);v.AddMember("index",index,a);V identity(rapidjson::kObjectType),facts(rapidjson::kObjectType),slots(rapidjson::kObjectType);
  currency_fact(facts,row,binding.currency,a);
  if(stage==3){
   for(auto k:account_fields)if(k!=money)fact(facts,row,k,a,k!=account&&k!=money);double total=num(row,balance),cash=num(row,available);
   auto p=append_owned(*batch.array,wtp::WTSAccountInfo::create());initialize_account(p);p->setCurrency("CNY");p->setBalance(total);p->setAvailable(cash);
   abi(slots,"currency",std::string("CNY"),"显式绑定配置",a);abi(slots,"balance",total,"原值",a);abi(slots,"available",cash,"原值",a);abi(slots,"dynProfit",0.0,"中性：总资产已含盈亏",a);
   // 冻结现金没有WT对应保证金槽。保留原事实，永远不以现金冻结冒充保证金。
   for(auto k:{previous,commission,frozen_margin,frozen_commission}){double n=present(row,k)?row[k].GetDouble():0;if(k==previous){p->setPreBalance(n);abi(slots,"preBalance",n,present(row,k)?"原值":"中性：unknown",a);}else if(k==commission){p->setCommission(n);abi(slots,"commission",n,present(row,k)?"原值":"中性：unknown",a);}else if(k==frozen_margin){p->setFrozenMargin(n);abi(slots,"frozenMargin",n,present(row,k)?"原值":"中性：unknown",a);}else{p->setFrozenCommission(n);abi(slots,"frozenCommission",n,present(row,k)?"原值":"中性：unknown",a);}}
   for(auto k:{"margin","closeProfit","deposit","withdraw"})abi(slots,k,0.0,"中性：unknown",a);
  }else{
   std::string code_value=stage==0?str(row,code):*decoded.facts.code,raw_exchange=stage==0?str(row,exchange):*decoded.facts.raw_exchange;
   if(stage==0)check(code_value.size()==6&&digits(code_value)&&(raw_exchange=="SH"||raw_exchange=="SZ"),"HTTP证券或市场非法");
   std::string exch=stage==0?(raw_exchange=="SH"?"SSE":"SZSE"):*decoded.facts.exchange;auto c=base->getContract(code_value.c_str(),exch.c_str());check(c&&std::string(c->getCode())==code_value&&std::string(c->getExchg())==exch,"HTTP合约缺失或市场冲突");add(identity,code,code_value,a);add(identity,exchange,raw_exchange,a);
   abi(slots,"code",code_value,"原值",a);abi(slots,"exchange",exch,"SH/SZ显式映射",a);
   if(stage==0){
    for(auto k:position_fields)if(k!=money)fact(facts,row,k,a,k!=code&&k!=exchange&&k!=account&&k!=money);for(auto k:{volume,available_volume,yesterday,frozen_volume,onroad}){facts.RemoveMember(k);integer_fact(facts,row,k,a);}
    double total=num(row,volume,true,true),sellable=num(row,available_volume,true,true);check(sellable<=total,"HTTP可卖超过总量");std::string key=exch+":"+code_value;check(seen.emplace(key,std::make_pair(std::string(),index)).second,"HTTP持仓证券重复");
    auto p=append_owned(*batch.array,wtp::WTSPositionItem::create(c->getCode(),"CNY",c->getExchg()));p->setContractInfo(c);p->setDirection(wtp::WDT_LONG);p->setPrePosition(total);p->setNewPosition(0);p->setAvailPrePos(sellable);p->setAvailNewPos(0);p->setAvgPrice(present(row,avg)?row[avg].GetDouble():0);p->setPositionCost(0);p->setMargin(0);p->setDynProfit(0);
    abi(slots,"prePosition",total,"aggregate",a);abi(slots,"newPosition",0.0,"aggregate",a);abi(slots,"availPrePos",sellable,"aggregate",a);abi(slots,"availNewPos",0.0,"aggregate",a);abi(slots,"averagePrice",p->getAvgPrice(),present(row,avg)?"原值":"中性：unknown",a);abi(slots,"positionCost",0.0,"中性：unknown",a);abi(slots,"currency",std::string("CNY"),"显式绑定配置",a);abi(slots,"direction",double(wtp::WDT_LONG),"股票现金持仓",a);abi(slots,"margin",0.0,"中性：unknown",a);abi(slots,"dynProfit",0.0,"中性：unknown",a);
   }else{
    for(auto k:(stage==1?std::vector<const char*>(std::begin(order_fields),std::end(order_fields)):std::vector<const char*>(std::begin(trade_fields),std::end(trade_fields))))if(k!=money)fact(facts,row,k,a,k!=code&&k!=exchange&&k!=account&&k!=money&&k!=order&&k!=trade&&k!=insert_date&&k!=insert_time&&k!=trade_date&&k!=trade_time);
    const auto& decoded_facts=decoded.facts;
    std::string oid=*decoded_facts.order;double side_value=*decoded_facts.side;
    const bool buy=side_value==48;const auto offset=buy?wtp::WOT_OPEN:wtp::WOT_CLOSE;
    std::string raw_date=*decoded_facts.raw_date,raw_time=*decoded_facts.raw_time;unsigned day=*decoded_facts.date,time=*decoded_facts.time;add(identity,order,oid,a);add(identity,stage==1?insert_date:trade_date,raw_date,a);add(identity,stage==1?insert_time:trade_time,raw_time,a);
    abi(slots,"direction",double(wtp::WDT_LONG),"股票现金买卖",a);abi(slots,"offsetType",double(offset),"OffsetFlag48/49",a);abi(slots,"userTag",std::string(),"未授本地管理资格",a);
    // 规范事实去重忽略日期/时间文本等价形式，元数据仍保留首次原文本。
    V canonical(rapidjson::kObjectType);add(canonical,"code",code_value,a);add(canonical,"exchange",exch,a);add(canonical,"order",oid,a);add(canonical,"side",side_value,a);add(canonical,"date",double(day),a);add(canonical,"time",double(time),a);
    V comparable(facts,a);
    for(auto it=comparable.MemberBegin();it!=comparable.MemberEnd();++it){auto& value=it->value["value"];if(value.IsNumber())value.SetDouble(value.GetDouble());}
    comparable[stage==1?insert_date:trade_date]["value"].SetDouble(day);comparable[stage==1?insert_time:trade_time]["value"].SetDouble(time);comparable[exchange]["value"].SetString(exch.c_str(),a);
    canonical.AddMember("facts",comparable,a);
    if(stage==1){
     double qty=*decoded_facts.quantity,filled_value=*decoded_facts.filled,left=*decoded_facts.remaining,state_value=*decoded_facts.state,quote=*decoded_facts.price;unsigned state_num=*decoded_facts.state;bool active=(state_num>=48&&state_num<=52)||state_num==55;bool canceled=state_num==53||state_num==54||state_num==57;
     if(decoded_facts.cancel)add(canonical,"cancel",*decoded_facts.cancel,a);else canonical.AddMember("cancel",V(),a);
     for(auto pair:{std::make_pair("quantity",qty),{"filled",filled_value},{"remaining",left},{"state",state_value},{"price",quote}})add(canonical,pair.first,pair.second,a);std::string normalized=json_text(canonical);auto inserted=seen.emplace(oid,std::make_pair(normalized,index));if(!inserted.second){check(inserted.first->second.first==normalized,"HTTP委托同ID事实冲突");batch.source_to_output.push_back(inserted.first->second.second);continue;}
     canonical_record(batch,canonical_limits,stage,binding,exch,code_value,day,oid,std::string(),normalized);
     auto p=append_owned(*batch.array,wtp::WTSOrderInfo::create());p->setCode(c->getCode());p->setExchange(c->getExchg());p->setContractInfo(c);p->setDirection(wtp::WDT_LONG);p->setOffsetType(offset);p->setPriceType(wtp::WPT_LIMITPRICE);p->setOrderFlag(wtp::WOF_NOR);p->setBusinessType(wtp::BT_CASH);p->setOrderID(oid.c_str());p->setEntrustID(oid.c_str());p->setUserTag("");p->setVolume(qty);p->setVolTraded(filled_value);p->setVolLeft(active?left:0);p->setPrice(quote);p->setOrderDate(day);p->setOrderTime(time);p->setError(state_num==57);
     // WT账户消费者同时读取多空/开平和净方向，全部从同一原OffsetFlag初始化。
     p->setNetDirection(buy);
     p->setOrderState(state_num==56?wtp::WOS_AllTraded:canceled?wtp::WOS_Canceled:(state_num==51||state_num==52)?wtp::WOS_Cancelling:filled_value>0?wtp::WOS_PartTraded_Queuing:wtp::WOS_NotTraded_Queuing);
     abi(slots,"orderID",oid,"原值",a);abi(slots,"entrustID",oid,"原合同号ABI承载",a);abi(slots,"orderState",double(p->getOrderState()),"原状态映射",a);abi(slots,"orderFlag",double(wtp::WOF_NOR),"中性：统计通道",a);abi(slots,"businessType",double(wtp::BT_CASH),"显式cash profile",a);abi(slots,"volume",qty,"原值",a);abi(slots,"volTraded",filled_value,"原值",a);abi(slots,"volLeft",active?left:0,"原状态活动余量",a);abi(slots,"price",quote,"原值",a);abi(slots,"priceType",double(wtp::WPT_LIMITPRICE),"中性：unknown价格类型，限统计",a);
     V unknown(rapidjson::kObjectType);add(unknown,"availability","unknown",a);unknown.AddMember("value",V(),a);add(unknown,"reason","源未公开价格类型",a);v.AddMember("price_type",unknown,a);
    }else{
     std::string raw_id=*decoded_facts.trade,id=scoped_trade_id(exch,code_value,day,raw_id);double qty=*decoded_facts.quantity,pvalue=*decoded_facts.price,amount_value=*decoded_facts.amount;std::string tuple=exch+"\n"+code_value+"\n"+std::to_string(day)+"\n"+raw_id;auto reverse=reverse_ids.emplace(id,tuple);check(reverse.second||reverse.first->second==tuple,"派生成交身份冲突");
     add(canonical,"trade",id,a);add(canonical,"quantity",qty,a);add(canonical,"price",pvalue,a);add(canonical,"amount",amount_value,a);std::string normalized=json_text(canonical),key=id+"\n"+oid;auto inserted=seen.emplace(key,std::make_pair(normalized,index));if(!inserted.second){check(inserted.first->second.first==normalized,"HTTP成交同ID事实冲突");batch.source_to_output.push_back(inserted.first->second.second);continue;}
     canonical_record(batch,canonical_limits,stage,binding,exch,code_value,day,oid,id,normalized);
     add(identity,trade,raw_id,a);add(identity,"derived_trade_id",id,a);add(identity,"mapping_version",protocol::mapping_version,a);
     auto p=append_owned(*batch.array,wtp::WTSTradeInfo::create(c->getCode(),c->getExchg()));p->setContractInfo(c);p->setDirection(wtp::WDT_LONG);p->setOffsetType(offset);p->setTradeID(id.c_str());p->setRefOrder(oid.c_str());p->setUserTag("");p->setVolume(qty);p->setPrice(pvalue);p->setAmount(amount_value);p->setTradeDate(day);p->setTradeTime(time);
     p->setNetDirection(buy);
     abi(slots,"tradeID",id,protocol::mapping_version,a);abi(slots,"refOrder",oid,"原值",a);abi(slots,"volume",qty,"原值",a);abi(slots,"price",pvalue,"原值",a);abi(slots,"amount",amount_value,"原值",a);
    }
    abi(slots,"eventDate",double(day),"Asia/Shanghai来源日期",a);abi(slots,"eventTime",double(time),"Asia/Shanghai HHMMSSmmm",a);
   }
  }
  v.AddMember("identity",identity,a);v.AddMember("facts",facts,a);v.AddMember("abi",slots,a);auto serialized=json_text(v);batch.view_bytes+=serialized.size()+1;batch.views.push_back(std::move(serialized));batch.source_to_output.push_back(index);++index;
 }
 return batch;
}
AccountBatch map_account_rows(unsigned stage,const rapidjson::Value& rows,
 const AccountBinding& binding,wtp::IBaseDataMgr* base,const AccountBatchMetadata& metadata,unsigned view_version){
 return map_account_rows_impl(stage,rows,binding,base,&metadata,view_version,nullptr);
}
AccountBatch map_account_rows(unsigned stage,const rapidjson::Value& rows,
 const AccountBinding& binding,wtp::IBaseDataMgr* base,const AccountBatchMetadata& metadata,unsigned view_version,
 const AccountCanonicalLimits& limits){
 return map_account_rows_impl(stage,rows,binding,base,&metadata,view_version,&limits);
}
AccountSelectedRowBatch map_account_row_at(unsigned stage,const rapidjson::Value& rows,
 std::size_t row_index,const AccountBinding& binding,wtp::IBaseDataMgr* base,
 const AccountBatchMetadata& metadata,const AccountCanonicalLimits& limits){
 AccountSelectedRowBatch selected;
 selected.batch=map_account_rows_impl(stage,rows,binding,base,&metadata,3,&limits,row_index);
 selected.original_row_index=row_index;selected.original_row_count=rows.Size();
 return selected;
}
AccountBatch map_trade_event_rows(unsigned stage,const rapidjson::Value& rows,
 const AccountBinding& binding,wtp::IBaseDataMgr* base,const AccountCanonicalLimits& limits){
 check((stage==1||stage==2)&&rows.IsArray()&&rows.Size()==1,"事件金融行类型或数量非法");
 return map_account_rows_impl(stage,rows,binding,base,nullptr,3,&limits);
}
}}
