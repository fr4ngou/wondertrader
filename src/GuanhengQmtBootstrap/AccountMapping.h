#pragma once
#include "Includes/WTSCollection.hpp"
#include <rapidjson/document.h>
#include <cstddef>
#include <cstdint>
#include <optional>
#include <memory>
#include <string>
#include <vector>

namespace wtp {class IBaseDataMgr;class WTSAccountInfo;}
namespace guanheng { namespace bootstrap {
struct AccountBinding {std::string account,environment,currency,profile;unsigned row_limit=4096;};

enum class AccountInspectionKind { Complete, MissingRequired, Invalid };
enum class AccountFactField : unsigned {
 Code=0, Exchange=1, Account=2, Currency=3, Order=4, Trade=5, Side=6, Date=7,
 Time=8, Quantity=9, Filled=10, Remaining=11, State=12, Price=13, Amount=14, Cancel=15
};
constexpr std::uint64_t account_fact_bit(AccountFactField field){return std::uint64_t{1}<<static_cast<unsigned>(field);}
enum AccountFactRelation : std::uint32_t {
 FilledExceedsQuantity=1, RemainingMismatch=2, AllTradedMismatch=4, CancelMismatch=8
};
// optional区分来源缺失/未知与真实0；合法原日期时间文本保留，规范值供精确比较。
struct AccountRowFacts {
 std::optional<std::string> code,exchange,raw_exchange,account,currency,order,trade,raw_date,raw_time;
 std::optional<unsigned> side,date,time,state;
 std::optional<double> quantity,filled,remaining,price,amount,cancel;
};
struct AccountInspectionLimits {std::size_t max_input_bytes,max_output_bytes;};
struct AccountRowInspection {
 std::string source;
 AccountBinding binding;
 AccountRowFacts facts;
 AccountInspectionKind kind=AccountInspectionKind::Complete;
 std::uint64_t required=0,present=0,valid=0,invalid=0,missing=0,unknown=0;
 std::uint32_t relations=0;
 bool locator_complete=false;
 std::size_t input_bytes=0,output_bytes=0;
};
// 只检查stage1/2原单行，返回独立纯值，不调用WT/BaseData/CNG。
// 结构/UTF8/预算/资源失败抛异常，未完成检查不产生金融分类；caller继续拥有原D。
AccountRowInspection inspect_account_row(unsigned stage,const std::string& raw_row_utf8,
 const AccountBinding&,const AccountInspectionLimits&);

struct ArrayRelease{void operator()(wtp::WTSArray* p)const{if(p)p->release();}};
// 运输caller已验证完整source JSON/原请求/摘要/执行区间；这里不认证、不改写来源。
struct AccountBatchMetadata {
 std::string source,request_id,result_sha,started,finished;
};
// 仅order/deal显式请求；每最终WTS下标一项，摘要为本mapper规范事实的派生值。
struct AccountCanonicalRecord {std::string canonical_key,derived_facts_sha256;};
// 普通有效载荷额度：记录1..4096，字节1..64MiB；不含vector/分配器开销。
struct AccountCanonicalLimits {std::size_t max_records,max_bytes;};
// owner一次构造完整WTS批次；异常由RAII释放，worker不能保留SPI/BaseData/WTS引用。
struct AccountBatch {
 std::unique_ptr<wtp::WTSArray,ArrayRelease> array;
 std::vector<std::string> views;
 // query来源字段；event入口六项全空，真实事件来源由上层独立值持有。
 std::string source,started,finished,seconds,request_id,result_sha;
 unsigned source_rows=0;std::size_t view_bytes=0;
 // 每个原输入行对应最终数组下标；直接复用本mapper金融去重决定。
 std::vector<std::size_t> source_to_output;
 // 旧入口为空/0；新输出只计key/hash字符串及各一个逻辑NUL，不改变view_bytes。
 std::vector<AccountCanonicalRecord> canonical_records;
 std::size_t canonical_bytes=0;
};
// 单行选择的本地batch只有1行/映射{0}；原完整数组下标和数量独立保留。
// 原下标0有效，不能用本地输出0替换R21Q或来源proof的原下标。
struct AccountSelectedRowBatch {
 AccountBatch batch;
 std::size_t original_row_index=0,original_row_count=0;
};
// stage1/2、固定view3及canonical；借用完整rows，只构造所选原行，不复制DOM。
// caller另核完整R5c匹配/来源关系；本入口不授未选行有效性或唯一身份。
// 异常沿原mapper传播并释放完整临时批次，返回值不保留rows借用。
AccountSelectedRowBatch map_account_row_at(unsigned stage,const rapidjson::Value& original_rows,
 std::size_t row_index,const AccountBinding&,wtp::IBaseDataMgr*,
 const AccountBatchMetadata&,const AccountCanonicalLimits&);
// 本owner完成金融行/UTC共同约束，无SPI与I/O。rows仅本调用借用，返回值持有独立值。
// view_version显式且仅2/3；上层在SPI前继续结算累计view容量和整轮截止。
AccountBatch map_account_rows(unsigned stage,const rapidjson::Value& rows,
 const AccountBinding&,wtp::IBaseDataMgr*,const AccountBatchMetadata&,unsigned view_version);
// 显式启用规范输出；其余金融/UTC/owner语义与原入口相同，失败释放整批并抛出。
AccountBatch map_account_rows(unsigned stage,const rapidjson::Value& rows,
 const AccountBinding&,wtp::IBaseDataMgr*,const AccountBatchMetadata&,unsigned view_version,
 const AccountCanonicalLimits&);
// 仅一条真实order/deal行（stage=1/2），固定view3并显式生成规范输出。
// query provenance六字段保持空；事件B/session/sequence由上层独立owner持有。
// rows仅调用期借用，返回金融值独立；无查询封套、伪UTC、I/O或SPI。
AccountBatch map_trade_event_rows(unsigned stage,const rapidjson::Value& rows,
 const AccountBinding&,wtp::IBaseDataMgr*,const AccountCanonicalLimits&);
std::string scoped_trade_id(const std::string& exchange,const std::string& code,unsigned date,const std::string& raw_id);
// 显式初始化原Adapter读取的全部资金槽；固定上游构造函数的margin未初始化。
void initialize_account(wtp::WTSAccountInfo*);
}}
