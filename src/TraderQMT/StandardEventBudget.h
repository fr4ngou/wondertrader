#pragma once
#include "GuanhengCommon/ProviderTypes.h"
#include "GuanhengQmtBootstrap/AccountEventMatch.h"
#include <cstddef>
#include "GuanhengQmtBootstrap/JsonBoundary.h"
#include "GuanhengCommon/QmtHostTradeClient.h"
#include <algorithm>
#include <limits>
#include <initializer_list>
#include <string>
#include <vector>
#include <stdexcept>

namespace guanheng { namespace standard_event_budget {
// 固定x64/Release COFF基线；公共布局漂移必须在编译时阻断并重核银行。
static_assert(sizeof(void*)==8&&sizeof(std::string)==32&&sizeof(wchar_t)==2,"standard event bank ABI");
static_assert(sizeof(rapidjson::Document)==96&&sizeof(rapidjson::Value)==16,"standard event JSON bank ABI");
// 当前查询结果包含快照消费及提交阶段标志；账户DTO为392B，原票据仍为136B。
// 内存银行继续按下文sizeof计量，所有自有消费者须同批重编。
static_assert(sizeof(QmtAccountResult)==392&&sizeof(QmtBoundReceipt)==136,"standard account DTO bank ABI");
static_assert(sizeof(QmtHttpConfig)==120,"standard HTTP configuration bank ABI");
static_assert(sizeof(QmtTradeOrderReference)==632&&sizeof(QmtTradeReadDescriptor)==96,"standard trade DTO bank ABI");
static_assert(sizeof(bootstrap::AccountRowInspection)==736,"standard inspection bank ABI");
// 私有纯checked算术。只在events_enabled域使用；所有尺寸为逻辑有效载荷，非arena/RSS。
// 失败固定Backpressure/空reason，out保持原值；不分配、不读取配置文件或调用Common。
struct Inputs {
 std::size_t http=0,queue=0,pending=0,rows=0,identity=0,lookup=0,view=0,index=0;
 std::size_t configuration_text=0;
};
struct Layout {
 std::size_t impl=0,task=0,completion=0,chain=0,query_evidence=0;
 std::size_t identity_entry=0,pending_entry=0,candidate_entry=0,owner_callback=0;
};
struct InstanceBanks {
 std::size_t fixed=0,clients=0,http_slots=0,owner_peak=0,worker_peak=0;
 std::size_t total_static=0,ordinary_advance=0;
};
struct ContextInputs {std::size_t result=0,page=0,event_bytes=0,command=0,call_result=0;};
struct ContextBanks {
 std::size_t context=0,chain=0,query_extra=0,query_result=0,query_data=0,observation=0;
 std::size_t minimum_identity_work=0;
 bootstrap::AccountEventMatchLimits match{};
};
struct OrdinaryBanks {std::size_t query=0,pair=0;};
Status instance(const Inputs&,const Layout&,InstanceBanks&)noexcept;
Status context(const Inputs&,const Layout&,const ContextInputs&,ContextBanks&)noexcept;
Status ordinary(const Inputs&,unsigned stage,std::size_t data_bytes,std::size_t rows,
 OrdinaryBanks&)noexcept;

namespace detail {
struct Arithmetic {
 bool ok=true;
 std::size_t add(std::size_t a,std::size_t b)noexcept {if(b>(std::numeric_limits<std::size_t>::max)()-a){ok=false;return 0;}return a+b;}
 std::size_t mul(std::size_t a,std::size_t b)noexcept {if(a&&b>(std::numeric_limits<std::size_t>::max)()/a){ok=false;return 0;}return a*b;}
 std::size_t sum(std::initializer_list<std::size_t> xs)noexcept {std::size_t n=0;for(auto x:xs)n=add(n,x);return n;}
 std::size_t text(std::size_t n)noexcept{return add(n,1);}
 std::size_t b64(std::size_t n)noexcept{return mul(add(n/3,n%3?1:0),4);}
 std::size_t nodes(std::size_t x)noexcept{return (std::min<std::size_t>)(1000000,add(x,1)/2);}
 std::size_t tree(std::size_t x)noexcept{return mul(9,add(x,1));}
 std::size_t dom(std::size_t x)noexcept{return add(sizeof(rapidjson::Document),tree(x));}
 std::size_t wire(std::size_t x)noexcept{return add(mul(6,x),mul(24,nodes(x)));}
 std::size_t parse(std::size_t x)noexcept {
  const auto keys=(std::min<std::size_t>)(1000000,add(x,1)/4);
  const auto sax=sum({sizeof(rapidjson::Reader),40,32*24,mul(keys,sizeof(std::string)),x,keys,text(x),66*sizeof(rapidjson::SizeType)});
  const auto build=sum({dom(x),mul(sizeof(rapidjson::Value),nodes(x)),text(x),66*sizeof(rapidjson::SizeType),sizeof(rapidjson::Reader)});
  return (std::max)(sax,build);
 }
 std::size_t encode(std::size_t x)noexcept {
  // 当前一次排序Writer的Buffer+返回string；节点指针、两临时key、层栈另计。
  return sum({mul(2,text(wire(x))),mul(8,nodes(x)),2*4097,32*2*sizeof(std::size_t),25,
   sizeof(rapidjson::StringBuffer),sizeof(rapidjson::Writer<rapidjson::StringBuffer>)});
 }
 Status status()const noexcept {Status result;if(!ok)result.code=ErrorCode::Backpressure;return result;}
};
inline Status capacity()noexcept{Status out;out.code=ErrorCode::Backpressure;return out;}
inline std::size_t result_cap(const Inputs& in)noexcept
{return in.http<16384?0:(std::min<std::size_t>)(2097152,3*((in.http-16384)/4));}
inline std::size_t data_cap(std::size_t result)noexcept
{return result<4096?0:(std::min<std::size_t>)(1048576,result-4096);}
inline std::size_t query_payload(Arithmetic& a,std::size_t r,std::size_t d)noexcept
{
 // 原DTO和显式AAR票据（至多256B）+Completion operation Status。
 return a.sum({a.text(d),a.text(a.add(a.b64(r),16384)),37,20,61,4097,327,4097,257,a.text(r),129,61});
}
inline std::size_t pair_payload(Arithmetic& a,const Inputs& in,unsigned stage,std::size_t d,std::size_t rows)noexcept
{
 const std::size_t minimum[]={87,254,213,33},fmax[]={2305,3301,2849,2045},base[]={2196,2688,2110,1936},mu[]={1,4,3,1},wt[]={176,400,352,152};
 const auto n=stage==3?std::size_t{1}:(std::min)(rows,d?((d-1)/(minimum[stage]+1)):0);
 const auto financial=(std::min)(a.mul(n,fmax[stage]),a.add(a.mul(n,base[stage]),a.mul(mu[stage],d)));
 const auto groups=stage==1||stage==2?n:0;
 const auto view=groups?a.add(d,a.mul(groups,stage==1?987:907)):0;
 const auto used=a.sum({d,financial,a.mul(8,n),a.mul(64,groups),
  (std::min)(in.lookup,a.mul(groups,in.http)),(std::min)(in.view,view)});
 const auto cumulative=(std::min)(in.identity,used);
 const std::size_t g0=stage==1?80:128,g1=stage==1?312:297;
 // 固定P8私有体来自目标COFF表；两个Group向量与共享rows/transport各只记真实一份。
 const auto fixed=std::size_t{3*8+312+16+256+216+48+176};
 return a.sum({fixed,a.mul(16,d?(d-1)/3:0),d,a.tree(4096),4504+190,167,
  a.mul(groups,296+g0),a.mul(groups,296+g1),a.mul(n,wt[stage]+8+sizeof(std::string)+1),
  a.mul(groups,2*(sizeof(std::string)+1)),141,cumulative>d?cumulative-d:0});
}
inline std::size_t mapper_owner(Arithmetic& a,const Inputs& in,unsigned stage,std::size_t d,std::size_t r)noexcept
{
 const std::size_t minimum[]={87,254,213,33},fmax[]={2305,3301,2849,2045},base[]={2196,2688,2110,1936},mu[]={1,4,3,1},wt[]={176,400,352,152};
 const auto cap=stage==3?std::size_t{1}:(std::min)(in.rows,d?((d-1)/(minimum[stage]+1)):0);
 const auto outer=a.sum({a.dom(d),a.dom(4096),a.dom(4096),3*8+312+16+256+216,167});
 const auto admission=a.sum({outer,a.dom(r),a.dom(326),a.dom(4096),a.dom(d),a.dom(4096),
  a.parse(4096),a.mul(2,a.text(4504)),65536+32});
 std::size_t loop=0;
 for(std::size_t j=0;j<=cap;++j){
  const auto consumed=a.mul(minimum[stage]-2,j);
  if(!d||consumed>d-1)break;
  const auto n=stage==3?std::size_t{1}:(std::min)(in.rows,(d-1-consumed)/3);
  if(j>n)break;
  const auto financial=(std::min)(a.mul(j,fmax[stage]),a.add(a.mul(j,base[stage]),a.mul(mu[stage],d)));
  const auto normalized=stage==1?(std::min)(a.mul(1945,j),a.add(a.mul(1584,j),a.mul(2,d))):
   stage==2?(std::min)(a.mul(1796,j),a.add(a.mul(1309,j),a.mul(2,d))):0;
  const auto seen=stage==0?a.mul(j,85):stage==1?a.add(a.mul(j,137),normalized):
   stage==2?a.sum({a.mul(j,186),normalized,a.mul(j,198)}):0;
  const std::size_t current=stage==0?2347:stage==3?2069:fmax[stage];
  const std::size_t normalized_one=stage==1?1945:stage==2?1796:0;
  const std::size_t inspection_text=stage==2?235:171;
  const std::size_t reverse_scratch=stage==2?63+48+84+112+4:0;
  // 金融v与尚未挂入v的子树、canonical/comparable及其双编码；只计当前一行。
  const auto row=a.sum({sizeof(bootstrap::AccountRowInspection),inspection_text,
   a.dom(current),a.dom(normalized_one),a.mul(2,a.text(current)),a.mul(2,a.text(normalized_one)),
   14*sizeof(void*),6+4+63+10+12+7,reverse_scratch,wt[stage],65536+32+123});
  loop=(std::max)(loop,a.sum({outer,a.dom(d),4504+169,4504+190,48,a.mul(8,n),financial,
   a.mul(j,sizeof(std::string)+1+8+wt[stage]),seen,row}));
 }
 const auto copy=a.sum({outer,a.dom(d),a.parse(d),pair_payload(a,in,stage,d,in.rows)});
 return (std::max)({admission,loop,copy});
}
} // detail
inline Status ordinary(const Inputs& in,unsigned stage,std::size_t d,std::size_t rows,OrdinaryBanks& out)noexcept
{
 if(stage>3||rows>in.rows||d>1048576||!in.identity)return detail::capacity();
 detail::Arithmetic a;OrdinaryBanks next;
 next.query=detail::query_payload(a,detail::result_cap(in),detail::data_cap(detail::result_cap(in)));
 next.pair=detail::pair_payload(a,in,stage,d,rows);
 if(!a.ok)return detail::capacity();out=next;return {};
}

namespace detail {
inline std::size_t closed_encode(Arithmetic& a,std::size_t input,std::size_t output,unsigned copies=2)noexcept
{return a.sum({a.mul(copies,a.text(output)),a.mul(8,a.nodes(input)),2*4097,32*2*sizeof(std::size_t),25,
 sizeof(rapidjson::StringBuffer),sizeof(rapidjson::Writer<rapidjson::StringBuffer>),sizeof(std::vector<const rapidjson::Value*>)});}
inline std::size_t scalar_frame(Arithmetic& a)noexcept
{
 // safe_text(string,128)：原scalar、encode返回、checked DOM与raw都在当前同步辅助调用中。
 return a.sum({a.dom(130),a.parse(770),a.text(770),129,2*sizeof(std::string)});
}
inline std::size_t phase(Arithmetic& a,std::initializer_list<std::size_t> trees,std::size_t text,std::size_t operation)noexcept
{
 std::size_t total=0,parse_extra=0;
 for(auto x:trees){const auto d=a.dom(x);total=a.add(total,d);const auto p=a.parse(x);parse_extra=(std::max)(parse_extra,p>d?p-d:0);}
 return a.sum({total,text,(std::max)({parse_extra,operation,scalar_frame(a)})});
}
inline std::size_t account_worker(Arithmetic& a,const Inputs& in)noexcept
{
 const auto r=result_cap(in),e=a.add(a.b64(r),16384),d=data_cap(r);
 const auto receipt=a.sum({4097,327,4097,257});
 const auto base=a.sum({a.mul(3,receipt),670,a.mul(2,37),20,61});
 const auto profile=a.sum({a.mul(2,16385),4097,4099,65,a.mul(2,a.b64(4096))});
 const auto terminal=a.sum({base,a.mul(2,a.text(e)),a.text(a.add(r,2)),a.mul(2,a.b64(r)),4097,a.text(d)});
 const auto binding_encode=closed_encode(a,4096,6493,3);
 return (std::max)({
  phase(a,{16384,4096,4096},profile,closed_encode(a,4096,4096)),
  phase(a,{64,64,16384,4096,4096},a.add(base,profile),binding_encode),
  phase(a,{64,64,326},base,closed_encode(a,326,326)),
  phase(a,{326,4096,16384,4096,4096},a.add(base,profile),binding_encode),
  phase(a,{326,326,4096,4096,669,4096,4096},base,binding_encode),
  phase(a,{326,326,4096,4096,669,e},terminal,binding_encode),
  phase(a,{326,326,4096,4096,926,e,r,16384,4096,4096},a.add(terminal,profile),binding_encode),
  // 票据UUIDv5共用原CNG；256B票据、512B规范name、64KiB hash对象均有界。
  phase(a,{326,4096,4096,256,512},a.sum({base,profile,257,513,65536,20,37}),closed_encode(a,512,512)),
  // 原完整结果持有期间核容量/consumed响应；HTTP仍由原同步和closing银行拥有。
  phase(a,{326,4096,e,r,256,16384},a.sum({terminal,257,257}),closed_encode(a,256,256))});
}
inline std::size_t trade_worker(Arithmetic& a,const Inputs& in,std::size_t k,std::size_t s,std::size_t page)noexcept
{
 const auto A=(std::min)(in.http,a.sum({a.b64(k),s,16384}));
 const auto L=(std::min)(in.http,a.sum({a.b64(k),s,32768}));
 const auto T=(std::min<std::size_t>)(in.http,page);
 const auto R=a.sum({4097,a.text(k),4097}),G=std::size_t{4097+129},ctx=a.sum({G,4097,65});
 const auto O=a.sum({R,2*4097,782}),lookup_out=a.sum({a.mul(2,a.text(L)),O,39});
 const auto native_encode=closed_encode(a,322,322),meta_encode=closed_encode(a,A,13215);
 const auto bencode=closed_encode(a,4096,6493,3),kencode=closed_encode(a,k,k,3);
 const auto rawdecode=a.sum({a.text(a.add(k,2)),a.mul(2,a.b64(k)),129});
 const auto refresh=a.sum({2*16385,4099,2*129,4097});
 const auto prepare=(std::max)(phase(a,{16384,4096,4096},a.sum({16385,4097,4099,65,a.mul(2,a.b64(4096))}),bencode),
  phase(a,{16384,16384},refresh,closed_encode(a,16384,a.wire(16384),3)));
 const auto receipt=(std::max)(phase(a,{4096,4096,4096},65,bencode),phase(a,{4096,k},65,kencode));
 const auto lookup=(std::max)({receipt,
  phase(a,{341,L,k},a.sum({342,129,a.mul(2,a.text(k)),323}),a.encode(L)),
  phase(a,{341,L,L,k},a.sum({342,129,rawdecode}),meta_encode),
  phase(a,{341,L,k},a.sum({342,129,323,a.text(k)}),closed_encode(a,k,k))});
 const auto insert=phase(a,{1634},a.sum({1635,37,R}),closed_encode(a,1634,1634));
 const auto cancel=phase(a,{k,1047},a.sum({1048,R}),closed_encode(a,1047,1047));
 const auto before_write=(std::max)({a.add(prepare,G),insert,a.add(lookup,lookup_out),a.sum({lookup_out,R,cancel})});
 const auto write_base=a.sum({a.mul(2,R),2*37,65});
 const auto submit=(std::max)({
  phase(a,{k,4096,4096,4096},write_base,bencode),phase(a,{k,k,4096},write_base,kencode),
  phase(a,{k,k,16384},a.add(write_base,refresh),closed_encode(a,16384,a.wire(16384),3)),
  phase(a,{k,k,k,2484,A,A},a.sum({write_base,2485,a.text(A),rawdecode}),meta_encode),
  phase(a,{k,k,k,2484,16384},a.sum({write_base,2485,16385}),0)});
 const auto resume=(std::max)(phase(a,{k,k,k,A,A},a.sum({write_base,64,a.text(A),rawdecode}),meta_encode),receipt);
 const auto cancel_lookup=(std::max)({receipt,
  phase(a,{k,201,L},a.sum({37,65,202,a.text(k)}),a.encode(L)),
  phase(a,{k,k,201,L,L},a.sum({37,65,202,rawdecode,323}),closed_encode(a,L,13215)),
  phase(a,{k,k,201,L},a.sum({37,65,202,323}),closed_encode(a,L,a.add(a.b64(k),13215+23)))});
 const auto resume_cancel=(std::max)({resume,
  phase(a,{k,k,A,A},a.sum({323,65,rawdecode}),meta_encode),
  phase(a,{k,A,66},323+65,closed_encode(a,66,66))});
 const auto event=(std::max)(phase(a,{4096,66},ctx,0),
  phase(a,{4096,4544,T},a.sum({ctx,4545,129}),a.encode(T)));
 // Standard原U/2H/Started仍由原charge保有。本函数仅当前同步额外值；未建Pending前返回组单列。
 return (std::max)({before_write,submit,resume,cancel_lookup,resume_cancel,event,
  phase(a,{k,322},61+27,native_encode),phase(a,{326,326},0,0)});
}
inline std::size_t worker_fixed(Arithmetic& a)noexcept
{
 // 同步调用栈固定控制体的有限并集上界；Document已在各D，队列不复制此银行。
 const auto account=a.sum({sizeof(QmtAccountPreparation),sizeof(QmtPreparedAccountRead),192,
  sizeof(QmtAccountResult),2*sizeof(QmtBoundReceipt),sizeof(SignedHttpResult),sizeof(SignedHttpDeadline),sizeof(QmtAccountReadControlResult)});
 const auto trade=a.sum({sizeof(QmtTradePreparation),sizeof(QmtPreparedTrade),2*sizeof(QmtTradeReceipt),
  sizeof(QmtTradeResult),sizeof(QmtTradeLookupResult),sizeof(QmtTradeCancelLookupResult),
  sizeof(QmtTradeOrderReference),sizeof(QmtTradeCancelReference),sizeof(QmtTradeReadDescriptor),sizeof(SignedHttpResult),sizeof(SignedHttpDeadline)});
 const auto event=a.sum({sizeof(QmtTradeEventReadContext),sizeof(QmtTradeEventPage),sizeof(QmtTradeEventReadFailure),
  sizeof(SignedHttpResult),sizeof(SignedHttpDeadline),2*sizeof(Status)});
 // prepare checked/admitted/status、observed conflict/pending等局部最多5个非嵌入Status；有限具名文本按相位表计正文。
 return a.sum({(std::max)({account,trade,event}),5*(sizeof(Status)+61),14*sizeof(std::string)});
}
inline std::size_t initialization_scratch(Arithmetic& a)noexcept
{
 // 只含当前初始化局部：两个env变量名、UUID、四个binding返回控制体与当前最长复制。
 // 已存入Impl的配置正文归fixed.configuration_text，不在此重复。
 return a.sum({3*sizeof(std::string),129,129,37,4*sizeof(std::string),4097,
  sizeof(std::runtime_error),42});
}
inline std::size_t initialization_rejection_bound(Arithmetic& a,const Layout& layout)noexcept
{
 // 正文cap逐项：instance/account/env/currency/profile/expected.account/binding/hash/url/key/secret。
 // 在预算尚未完整准入的拒绝窗口，所有新复制也有此固定上界；cfg本体仍归调用者。
 return a.sum({layout.impl,49,64,11,4,65,64,129,65,2049,129,4097,initialization_scratch(a)});
}
inline std::size_t http_sync(Arithmetic& a)noexcept
{
 // 单个exchange当前签名/CNG/URL帧。128个closing槽的upload/header/buffer在HttpSlots内。
 return a.sum({3215,769,2*(2048+64+1)*sizeof(wchar_t),2049,65,5,37,21,65,65,65,
  65536,32,12*sizeof(std::string),4*sizeof(std::wstring),sizeof(SignedHttpResult)});
}
} // detail
inline Status instance(const Inputs& in,const Layout& layout,InstanceBanks& out)noexcept
{
 if(in.http<8192||in.http>16u*1024u*1024u||!in.queue||in.queue>1024||!in.pending||in.pending>4096
  ||!in.rows||in.rows>4096||!in.identity||in.identity>64u*1024u*1024u||in.lookup>in.identity||in.view>in.identity)return detail::capacity();
 detail::Arithmetic a;InstanceBanks next;const auto r=detail::result_cap(in),d=detail::data_cap(r);
 next.fixed=a.sum({layout.impl,a.mul(a.add(in.queue,1),layout.completion),
  a.mul(a.add(in.queue,1),layout.task),layout.completion,
  a.mul(in.pending,a.add(layout.pending_entry,13)),
  a.mul(a.add(in.rows,in.pending),a.add(layout.identity_entry,5)),a.mul(in.queue,layout.candidate_entry),in.configuration_text,
  3*141,37,38,49}); // Impl三个错误正文、last_command/entrust_prefix及registry实例key。
 const auto slot_account=a.sum({65848,16,927,928,a.text(in.http),33});
 const auto slot_trade=a.sum({65848,16,5061,928,a.text(in.http),33});
 // 回调length_text[32]、declared wchar[32]等固定局部另保128份；65536 buffer已在Exchange中。
 next.http_slots=a.add(a.mul(64,a.add(slot_account,slot_trade)),a.mul(128,32+64+sizeof(unsigned long)));
 // 当前x64 Release实测：账户Impl616、两份HTTP Impl各752、交易Core392。
 // HTTP配置新增批量字段及本轮交易首硬错指针均计入；外层unique_ptr对象另计。
 next.clients=a.sum({8,8,616,8,752,8,392,8,752,
  a.mul(2,2049+129+4097),a.mul(2,64),129+65,
  4097+4097+129+a.text(r),64+4+4,4097+4097+129+65+37});
 std::size_t mapper=0,pair=0,cache_view=0;
 for(unsigned stage=0;stage<4;++stage){
  mapper=(std::max)(mapper,detail::mapper_owner(a,in,stage,d,r));
  pair=(std::max)(pair,detail::pair_payload(a,in,stage,d,in.rows));
  if(stage==1||stage==2){
   const auto n=(std::min)(in.rows,d?((d-1)/(stage==1?255:214)):0),v=a.add(d,stage==1?987:907);
   const auto current=a.sum({a.dom(v),a.encode(v),a.text(v),a.text(d),632,4097+65537+4097+4097+129+4097+569+64+32});
   cache_view=(std::max)(cache_view,a.sum({16,a.mul(n,496+731),current}));
  }
 }
 // mapped Result/SPI前当前identity observation也是owner独立阶段，不能提前退票据。
 next.owner_peak=(std::max)({a.add(mapper,detail::query_payload(a,r,d)),layout.owner_callback,detail::initialization_scratch(a)});
 const auto common=(std::max)(detail::account_worker(a,in),detail::trade_worker(a,in,65536,2097152,(std::min<std::size_t>)(in.http,4190208)));
 next.worker_peak=a.sum({common,cache_view,detail::worker_fixed(a),detail::http_sync(a)});
 next.ordinary_advance=a.sum({detail::query_payload(a,r,d),pair,512});
 next.total_static=a.sum({next.fixed,next.clients,next.http_slots,next.owner_peak,next.worker_peak});
 if(!a.ok)return detail::capacity();out=next;return {};
}
inline Status context(const Inputs& in,const Layout& layout,const ContextInputs& c,ContextBanks& out)noexcept
{
 if(c.result<8192||c.result>2097152||c.page>in.http||!c.page||!c.event_bytes||c.event_bytes>c.page)return detail::capacity();
 detail::Arithmetic a;ContextBanks next;const auto d=detail::data_cap(c.result);
 next.context=a.sum({sizeof(QmtTradeEventReadContext),4097,129,4097,65});
 next.query_data=d;next.query_result=detail::query_payload(a,detail::result_cap(in),detail::data_cap(detail::result_cap(in)));
 const auto event=(std::min<std::size_t>)(c.event_bytes,1048576),row=(std::min<std::size_t>)(1048576,a.wire(d));
 const auto work=a.sum({128,next.query_result,a.text(event),4096,(std::max)(a.mul(2,a.text(row)),a.add(a.text(row),4096))});
 if(work>64u*1024u*1024u)return detail::capacity();
 next.match={event,next.query_result,in.rows,work};
 // B预检仍以唯一B算法为准；本必要下界先保matcher逻辑额度及其三次同时活跃DOM。
 next.minimum_identity_work=a.sum({work,a.dom(d),a.dom(event),a.dom(row)});
 // B的封闭字段产生式常量6440；两个原scalar合计<=d+50（两个double最大各25）。
 const auto v=(std::min)(in.view,a.add(d,6490));
 // signature六个有限字符串+九个数字+array标点最多1418B；不重编码整个identity view。
 next.observation=a.sum({152,a.parse(v),a.text(d),a.dom(1418),detail::closed_encode(a,1418,1418),113,2*65,141});
 // 原page/group持有一次，validated两个DOM、一个原payload双编码/inspection及旧Event P8沿原I预留。
 next.chain=a.sum({layout.chain,a.text(c.page),4097+129+4097,a.mul(2,a.dom(c.page)),
  a.mul(2,next.context),a.mul(3,in.identity),next.observation,a.mul(2,a.text(event)),sizeof(bootstrap::AccountRowInspection),4096,2048});
 next.query_extra=a.sum({layout.query_evidence,4097+327+4097,next.query_result,next.context,a.text(event),
  4*61});
 if(!a.ok||next.minimum_identity_work>64u*1024u*1024u)return detail::capacity();out=next;return {};
}
}}
