#include "History.h"
#include "NativeHistoryReader.h"
#include "NativeBarFile.h"
#include "../WtDtHelper/WtDtHelper.h"
#include "../WtDataStorage/DataDefine.h"
#include "../WTSUtils/zstdlib/zstd.h"
#include <rapidjson/document.h>
#include <rapidjson/writer.h>
#include <rapidjson/stringbuffer.h>
#include <algorithm>
#include <cmath>
#include <chrono>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <limits>
#include <map>
#include <sstream>
#include <type_traits>
#ifdef _WIN32
#include <windows.h>
#include <bcrypt.h>
#endif

namespace guanheng
{
namespace
{
Status invalid(const std::string& why) { return { ErrorCode::InvalidInput, why }; }
Status io(const std::string& why) { return { ErrorCode::IoError, why }; }
unsigned days_in_month(unsigned year,unsigned month)
{
    const unsigned days[] = {31,28,31,30,31,30,31,31,30,31,30,31};
    return days[month-1]+(month==2 && (year%4==0 && (year%100!=0 || year%400==0)));
}
bool valid_date(std::uint32_t date)
{
    unsigned y = date / 10000, m = date / 100 % 100, d = date % 100;
    if (y < 2004 || y > 2099 || m < 1 || m > 12 || !d) return false;
    return d <= days_in_month(y,m);
}
bool valid_minute(std::uint64_t value)
{
    return valid_date(static_cast<std::uint32_t>(value / 10000))
        && value % 10000 / 100 < 24 && value % 100 < 60;
}
bool valid_symbol(const std::string& exchange, const std::string& code)
{
    return (exchange == "SSE" || exchange == "SZSE") && code.size() == 6
        && std::all_of(code.begin(), code.end(), [](char c) { return c >= '0' && c <= '9'; });
}
// 输入已由请求准入校验。逐日进位最多受行数预算限制，不依赖宿主时区或 DST。
std::uint64_t window_end(std::uint64_t first,std::uint64_t elapsed,std::uint64_t ceiling)
{
    auto date=first/10000;
    auto minute=first%10000/100*60+first%100;
    while(elapsed>=1440-minute)
    {
        if(date>=ceiling/10000)return ceiling; // 先裁剪，避免越过支持的最后日期。
        elapsed-=1440-minute;minute=0;
        auto y=date/10000,m=date/100%100,d=date%100;
        if(++d>days_in_month(static_cast<unsigned>(y),static_cast<unsigned>(m)))
        {d=1;if(++m>12){m=1;++y;}}
        date=y*10000+m*100+d;
    }
    minute+=elapsed;
    return (std::min)(ceiling,date*10000+minute/60*100+minute%60);
}
std::uint64_t full_time(const wtp::WTSBarStruct& bar)
{
    return bar.time + 19900000ULL * 10000;
}
Status validate_metadata(const HistoryMetadata& m)
{
    if ((m.source.provider!=ProviderKind::Qmt && m.source.provider!=ProviderKind::Tdx)
        || static_cast<int>(m.qualification)<1 || static_cast<int>(m.qualification)>3
        || m.source.instance_id.empty() || m.source.session_id.empty() || !m.source.generation
        || m.dataset_version.empty() || m.source_license.empty()
        || m.qualification == Qualification::Unavailable)
        return invalid("历史来源、许可、版本及资格必须显式声明");
    if (m.timezone != "Asia/Shanghai" || m.minute_boundary != "right" || m.adjustment != "none"
        || !m.factor_version.empty()) return invalid("当前仅接收上海时区、右端、未复权分钟");
    if (!std::isfinite(m.volume_to_shares) || m.volume_to_shares <= 0
        || !std::isfinite(m.amount_to_yuan) || m.amount_to_yuan <= 0)
        return invalid("必须显式声明成交量和金额换算系数");
    return {};
}
Status validate_bars(const std::vector<wtp::WTSBarStruct>& bars, std::size_t maximum)
{
    if (bars.empty() || bars.size() > maximum) return invalid("分钟数量为空或超过预算");
    std::uint64_t previous = 0;
    for (const auto& b : bars)
    {
        if (!valid_minute(full_time(b)) || b.date != full_time(b) / 10000 || b.time <= previous
            || b.time!=(std::uint64_t(b.date)-19900000)*10000+full_time(b)%10000)
            return invalid("分钟日期非法、乱序或重复");
        const double fields[] = {b.open,b.high,b.low,b.close,b.settle,b.money,b.vol,b.hold,b.add};
        for (double v : fields) if (!std::isfinite(v)) return invalid("分钟含非有限数");
        if (b.open <= 0 || b.low <= 0 || b.high < b.low || b.open < b.low || b.open > b.high
            || b.close < b.low || b.close > b.high || b.vol < 0 || b.money < 0)
            return invalid("分钟 OHLC 或量额非法");
        previous = b.time;
    }
    return {};
}
std::string read_file(const std::filesystem::path& path, std::size_t limit)
{
    auto size = std::filesystem::file_size(path);
    if (size > limit) throw std::runtime_error("文件超过预算");
    std::ifstream stream(path, std::ios::binary);
    std::string data(static_cast<std::size_t>(size), '\0');
    if (!stream.read(data.data(), static_cast<std::streamsize>(size))) throw std::runtime_error("文件读取失败");
    return data;
}
void write_file(const std::filesystem::path& path, const std::string& data)
{
    std::ofstream stream(path, std::ios::binary | std::ios::trunc);
    stream.write(data.data(), static_cast<std::streamsize>(data.size()));
    stream.flush();
    if (!stream) throw std::runtime_error("文件写入失败");
}
std::string content_id(const std::string& data) { return native_bar_digest(data); }
std::string metadata_json(const HistoryMetadata& m)
{
    rapidjson::StringBuffer buffer;
    rapidjson::Writer<rapidjson::StringBuffer> w(buffer);
    w.StartObject();
    auto text = [&](const char* name, const std::string& value) { w.Key(name); w.String(value.data(), static_cast<rapidjson::SizeType>(value.size())); };
    w.Key("format"); w.Int(1);
    w.Key("provider"); w.Int(static_cast<int>(m.source.provider));
    text("instance_id",m.source.instance_id); text("session_id",m.source.session_id);
    w.Key("generation"); w.Uint64(m.source.generation);
    w.Key("qualification"); w.Int(static_cast<int>(m.qualification));
    text("dataset_version",m.dataset_version); text("source_license",m.source_license);
    text("adjustment",m.adjustment); text("factor_version",m.factor_version);
    text("minute_boundary",m.minute_boundary); text("timezone",m.timezone);
    w.Key("volume_to_shares"); w.Double(m.volume_to_shares);
    w.Key("amount_to_yuan"); w.Double(m.amount_to_yuan);
    text("content_id",m.content_id); w.EndObject();
    return buffer.GetString();
}
HistoryMetadata parse_metadata(const std::string& json)
{
    rapidjson::Document d; d.Parse(json.data(), json.size());
    if (d.HasParseError() || !d.IsObject()) throw std::runtime_error("历史来源元数据非法");
    auto number = [&](const char* key) -> double { if (!d.HasMember(key) || !d[key].IsNumber()) throw std::runtime_error("元数据缺少数值"); return d[key].GetDouble(); };
    auto integer = [&](const char* key) -> std::uint64_t { if (!d.HasMember(key) || !d[key].IsUint64()) throw std::runtime_error("元数据缺少整数"); return d[key].GetUint64(); };
    auto text = [&](const char* key) -> std::string { if (!d.HasMember(key) || !d[key].IsString()) throw std::runtime_error("元数据缺少文本"); return std::string(d[key].GetString(), d[key].GetStringLength()); };
    if (integer("format") != 1 || integer("provider") > 1 || integer("qualification") > 3)
        throw std::runtime_error("元数据版本或枚举非法");
    HistoryMetadata m;
    m.source.provider=static_cast<ProviderKind>(integer("provider"));
    m.source.instance_id=text("instance_id"); m.source.session_id=text("session_id"); m.source.generation=integer("generation");
    m.qualification=static_cast<Qualification>(integer("qualification"));
    m.dataset_version=text("dataset_version"); m.source_license=text("source_license");
    m.adjustment=text("adjustment"); m.factor_version=text("factor_version");
    m.minute_boundary=text("minute_boundary"); m.timezone=text("timezone");
    m.volume_to_shares=number("volume_to_shares"); m.amount_to_yuan=number("amount_to_yuan"); m.content_id=text("content_id");
    auto status=validate_metadata(m); if (!status.ok()) throw std::runtime_error(status.reason);
    return m;
}
bool same_metadata(HistoryMetadata a, HistoryMetadata b)
{
    a.content_id.clear(); b.content_id.clear();
    return metadata_json(a) == metadata_json(b);
}
class RootBusy : public std::runtime_error
{
public: RootBusy():std::runtime_error("历史根目录正在使用，遗留锁需恢复核查"){}
};
class RootLease
{
public:
    explicit RootLease(const std::filesystem::path& root) : path_(root/".guanheng-writer")
    {
#ifdef _WIN32
        // Keep this file permanently: deleting an exclusion object can race its next
        // acquisition on Windows (a directory pending deletion reports AccessDenied).
        // The exclusive handle serializes marker creation, work and marker removal.
        auto gate_path=root/".guanheng-lease-lock";
        gate_=CreateFileW(gate_path.c_str(),GENERIC_READ|GENERIC_WRITE,0,nullptr,
            OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);
        if(gate_==INVALID_HANDLE_VALUE)
        {
            const DWORD error=GetLastError();
            if(error==ERROR_SHARING_VIOLATION || error==ERROR_LOCK_VIOLATION)throw RootBusy();
            throw std::filesystem::filesystem_error("open history root lease gate",gate_path,
                std::error_code(static_cast<int>(error),std::system_category()));
        }
        try
        {
            if(!std::filesystem::create_directory(path_))throw RootBusy();
        }
        catch(...){CloseHandle(gate_);gate_=INVALID_HANDLE_VALUE;throw;}
#else
        if(!std::filesystem::create_directory(path_))throw RootBusy();
#endif
    }
    ~RootLease()
    {
        std::error_code ec;std::filesystem::remove(path_,ec);
#ifdef _WIN32
        CloseHandle(gate_);
#endif
    }
    RootLease(const RootLease&)=delete;
    RootLease& operator=(const RootLease&)=delete;
private:
    std::filesystem::path path_;
#ifdef _WIN32
    HANDLE gate_=INVALID_HANDLE_VALUE;
#endif
};
std::vector<wtp::WTSBarStruct> read_native(const std::string& bytes, std::size_t maximum)
{
    auto bars=read_native_bar_bytes(bytes,maximum,maximum*sizeof(wtp::WTSBarStruct));
    auto status=validate_bars(bars,maximum);
    if(!status.ok())throw std::runtime_error(status.reason);
    return bars;
}
struct VerifiedDataset
{
    std::unique_ptr<NativeFileLease> source_lease;
    HistoryMetadata metadata;
    std::string metadata_bytes;
    std::string bytes;
    std::vector<wtp::WTSBarStruct> bars;
};
VerifiedDataset load_verified_envelope(const std::filesystem::path& path,
    const std::filesystem::path& root,std::size_t maximum)
{
    VerifiedDataset data;
    data.source_lease=std::make_unique<NativeFileLease>(path);
    data.metadata_bytes=read_file(path.string()+".metadata.json",65536);
    data.metadata=parse_metadata(data.metadata_bytes);
    data.bytes=data.source_lease->read(maximum*sizeof(wtp::WTSBarStruct)+65536);
    if(content_id(data.bytes)!=data.metadata.content_id)
        throw std::runtime_error("历史内容与来源摘要不一致，需恢复核查");
    auto frozen=root/".guanheng-frozen";
    if(std::filesystem::exists(frozen)
        && read_file(frozen,256)!=data.metadata.content_id+"\n"+content_id(data.metadata_bytes)+"\n")
        throw std::runtime_error("冻结历史或来源身份发生变化");
    return data;
}
VerifiedDataset load_verified_dataset(const std::filesystem::path& path,
    const std::filesystem::path& root,std::size_t maximum)
{
    auto data=load_verified_envelope(path,root,maximum);
    data.bars=read_native(data.bytes,maximum);
    return data;
}
std::size_t native_rows(const std::string& bytes,std::size_t maximum,std::size_t cache_bytes)
{
    const auto rows=native_bar_rows(bytes,maximum,cache_bytes);
    const auto compressed=bytes.size()-sizeof(BlockHeaderV2);
    // 固定上游count索引在截止早于首条时会回退begin。只预读第一条以核前置条件，
    // 完整解码和索引仍交原Reader；固定输出与窗口上限避免为检查再建全量历史数组。
    using Stream=std::unique_ptr<ZSTD_DStream,decltype(&ZSTD_freeDStream)>;
    Stream stream(ZSTD_createDStream(),ZSTD_freeDStream);
    if(!stream || ZSTD_isError(ZSTD_initDStream(stream.get()))
        || ZSTD_isError(ZSTD_DCtx_setParameter(stream.get(),ZSTD_d_windowLogMax,27)))
        throw std::runtime_error("原生分钟前置检查无法初始化");
    wtp::WTSBarStruct first{};
    ZSTD_inBuffer input{bytes.data()+sizeof(BlockHeaderV2),compressed,0};
    ZSTD_outBuffer output{&first,sizeof first,0};
    while(output.pos<output.size)
    {
        const auto before=input.pos;
        const auto produced=output.pos;
        const auto remaining=ZSTD_decompressStream(stream.get(),&output,&input);
        if(ZSTD_isError(remaining) || (before==input.pos && produced==output.pos)
            || (!remaining && output.pos<output.size))
            throw std::runtime_error("原生分钟首条前置检查失败");
    }
    auto first_status=validate_bars({first},maximum);
    if(!first_status.ok() || full_time(first)>203012312359ULL)
        throw std::runtime_error("原生分钟首条非法或超出Reader支持截止");
    return rows;
}
Status merge_sequences(const std::vector<wtp::WTSBarStruct>& existing,
    const std::vector<wtp::WTSBarStruct>& incoming,std::size_t maximum,std::vector<wtp::WTSBarStruct>& result)
{
    std::map<std::uint64_t,wtp::WTSBarStruct> merged;
    for(const auto& b:existing)merged.emplace(b.time,b);
    for(const auto& b:incoming)
    {
        auto it=merged.find(b.time);
        if(it!=merged.end() && std::memcmp(&it->second,&b,sizeof b))
            return {ErrorCode::Conflict,"历史同分钟内容冲突"};
        merged[b.time]=b;
        if(merged.size()>maximum)return {ErrorCode::Backpressure,"历史合并或暂存超过预算"};
    }
    result.clear();result.reserve(merged.size());
    for(const auto& item:merged)result.push_back(item.second);
    return {};
}
void replace_file(const std::filesystem::path& from, const std::filesystem::path& to)
{
#ifdef _WIN32
    if (!MoveFileExW(from.c_str(), to.c_str(), MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH))
        throw std::runtime_error("原生文件原子替换失败");
#else
    std::filesystem::rename(from, to);
#endif
}
Status claim_new_root(const std::filesystem::path& target)
{
    auto root=std::filesystem::absolute(target);
    std::filesystem::create_directories(root.parent_path());
    std::error_code error;
    // 目标目录创建本身是排他认领；既有目录或另一调用的认领均不得继续写入。
    if(!std::filesystem::create_directory(root,error))
    {
        if(!error || error==std::errc::file_exists)
            return {ErrorCode::Conflict,"目标根目录已存在或已被其他调用认领"};
        return io(error.message());
    }
    return {};
}
Status validate_request(const MinuteRequest& r)
{
    if (!valid_symbol(r.exchange,r.code) || !valid_minute(r.from) || !valid_minute(r.to) || r.from > r.to)
        return invalid("证券或分钟范围非法");
    if (r.expected_minutes.size()>1000000) return invalid("预期分钟超过预算");
    if (!r.expected_minutes.empty() && r.calendar_version.empty()) return invalid("预期分钟缺少日历版本依据");
    std::uint64_t previous=0;
    for (auto t:r.expected_minutes)
    {
        if (!valid_minute(t) || t < r.from || t > r.to || t <= previous) return invalid("预期分钟非法或乱序");
        previous=t;
    }
    return {};
}
}

Status validate_history_bars(const std::vector<wtp::WTSBarStruct>& bars,std::size_t maximum)
{
    return validate_bars(bars,maximum);
}

Status decode_lc1(const std::vector<std::uint8_t>& bytes, const HistoryMetadata& metadata,
    std::vector<wtp::WTSBarStruct>& bars)
{
    bars.clear();
    auto status=validate_metadata(metadata); if (!status.ok()) return status;
    if (metadata.source.provider != ProviderKind::Tdx) return invalid("LC1 来源须为 TDX");
    if (bytes.empty() || bytes.size()%32 || bytes.size()/32>1000000) return invalid("LC1 记录截断、为空或超过预算");
    auto u16=[](const std::uint8_t* p) { return static_cast<std::uint16_t>(p[0] | (p[1]<<8)); };
    auto u32=[](const std::uint8_t* p) { return std::uint32_t(p[0]) | (std::uint32_t(p[1])<<8) | (std::uint32_t(p[2])<<16) | (std::uint32_t(p[3])<<24); };
    auto f32=[&](const std::uint8_t* p) { auto n=u32(p); float f; std::memcpy(&f,&n,4); return double(f); };
    for (std::size_t i=0;i<bytes.size();i+=32)
    {
        const auto* p=bytes.data()+i;
        auto encoded=u16(p), minutes=u16(p+2);
        auto year=encoded/2048+2004, month=encoded%2048/100, day=encoded%2048%100;
        if (minutes>=1440) { bars.clear(); return invalid("LC1 分钟越界"); }
        wtp::WTSBarStruct b;
        b.date=year*10000+month*100+day;
        b.time=(std::uint64_t(b.date)-19900000)*10000 + (minutes/60)*100 + minutes%60;
        b.open=f32(p+4); b.high=f32(p+8); b.low=f32(p+12); b.close=f32(p+16);
        b.money=f32(p+20)*metadata.amount_to_yuan;
        b.vol=u32(p+24)*metadata.volume_to_shares;
        bars.push_back(b);
    }
    status=validate_bars(bars,1000000);
    if (!status.ok()) bars.clear();
    return status;
}

NativeHistoryStore::NativeHistoryStore(std::filesystem::path root,std::size_t max_bars)
    :root_(native_physical_path(root)), max_bars_(max_bars)
{
    if (!max_bars || max_bars>1000000) throw std::invalid_argument("历史条数预算须为 1..1000000");
}
NativeHistoryStore::NativeHistoryStore(std::filesystem::path root,std::size_t max_bars,
    const NativeHistoryReaderConfig& reader_config) : NativeHistoryStore(std::move(root),max_bars)
{
    reader_=std::make_unique<NativeHistoryReader>(root_,max_bars_,reader_config);
    native_cache_bytes_=reader_config.cache_bytes;
}
NativeHistoryStore::~NativeHistoryStore()=default;
std::filesystem::path NativeHistoryStore::bar_path(const std::string& exchange,const std::string& code) const
{
    if (!valid_symbol(exchange,code)) throw std::invalid_argument("证券代码非法");
    return root_/"his"/"min1"/exchange/(code+".dsb");
}
Status NativeHistoryStore::publish(const std::string& exchange,const std::string& code,
    const std::vector<wtp::WTSBarStruct>& bars, HistoryMetadata metadata)
{
    return publish_impl(exchange,code,bars,std::move(metadata),false);
}
Status NativeHistoryStore::merge_bars(const std::string& exchange,const std::string& code,
    const std::vector<wtp::WTSBarStruct>& bars,HistoryMetadata metadata)
{
    return publish_impl(exchange,code,bars,std::move(metadata),true);
}
Status NativeHistoryStore::publish_impl(const std::string& exchange,const std::string& code,
    const std::vector<wtp::WTSBarStruct>& bars,HistoryMetadata metadata,bool merge)
{
    std::lock_guard<std::mutex> lock(mutex_);
    if (!valid_symbol(exchange,code)) return invalid("证券代码非法");
    auto status=validate_metadata(metadata); if (!status.ok()) return status;
    status=validate_bars(bars,max_bars_); if (!status.ok()) return status;
    try
    {
        if(std::filesystem::exists(root_/".guanheng-frozen"))
            return {ErrorCode::Conflict,"冻结历史根目录拒绝修订"};
        auto path=bar_path(exchange,code); std::filesystem::create_directories(path.parent_path());
        RootLease lease(root_);
        auto sidecar=path; sidecar+=".metadata.json";
        std::vector<wtp::WTSBarStruct> final_bars=bars;
        if(std::filesystem::exists(path))
        {
            auto previous=load_verified_dataset(path,root_,max_bars_);
            if(merge)
            {
                if(!same_metadata(previous.metadata,metadata))
                    return {ErrorCode::Conflict,"历史来源或版本变更需显式全量修订"};
                status=merge_sequences(previous.bars,bars,max_bars_,final_bars);
                if(!status.ok())return status;
            }
        }
        else if(std::filesystem::exists(sidecar))
            throw std::runtime_error("已发布历史文件缺失，保留来源与上一版等待恢复");
        NativeBarOutput output(path.parent_path(),final_bars,max_bars_);
        metadata.content_id=content_id(output.bytes());
        auto staged_meta=sidecar; staged_meta+=".pending";
        write_file(staged_meta,metadata_json(metadata));
        // 保留可恢复上一版；两文件之间崩溃时摘要不匹配会关闭读取资格。
        if (std::filesystem::exists(path)) std::filesystem::copy_file(path,path.string()+".previous",std::filesystem::copy_options::overwrite_existing);
        if (std::filesystem::exists(sidecar)) std::filesystem::copy_file(sidecar,sidecar.string()+".previous",std::filesystem::copy_options::overwrite_existing);
        output.publish_to(path); replace_file(staged_meta,sidecar);
        return {};
    }
    catch (const NativeFileBusy& e){return {ErrorCode::Backpressure,e.what()};}
    catch (const RootBusy& e){return {ErrorCode::Backpressure,e.what()};}
    catch (const std::exception& e)
    {
        return io(e.what());
    }
}
Status NativeHistoryStore::import_lc1(const std::string& exchange,const std::string& code,
    const std::vector<std::uint8_t>& bytes,HistoryMetadata metadata)
{
    std::vector<wtp::WTSBarStruct> bars;
    auto status=decode_lc1(bytes,metadata,bars);
    return status.ok()?publish(exchange,code,bars,std::move(metadata)):status;
}
MinuteResult NativeHistoryStore::query(const MinuteRequest& request)
{
    return query_impl(HistoryQuery{request},false);
}
MinuteResult NativeHistoryStore::query(const HistoryQuery& selection)
{
    return query_impl(selection,true);
}
MinuteResult NativeHistoryStore::query_impl(const HistoryQuery& selection,bool require_native)
{
    const auto& request=selection.window;
    std::lock_guard<std::mutex> lock(mutex_);
    MinuteResult result; result.status=validate_request(request); if (!result.status.ok()) return result;
    if(selection.period_minutes!=1 && selection.period_minutes!=5 && selection.period_minutes!=15
        && selection.period_minutes!=30 && selection.period_minutes!=60)
    {result.status={ErrorCode::NotSupported,"原生历史周期尚未取得接入资格"};return result;}
    if(selection.limit>10000)
    {result.status=invalid("历史窗口条数超过预算");return result;}
    const bool extended=selection.period_minutes!=1 || selection.limit;
    if((require_native || extended) && (!request.expected_minutes.empty() || !request.calendar_version.empty()))
    {result.status=invalid("周期或尾部窗口不能沿用m1覆盖网格");return result;}
    if(require_native && !reader_)
    {result.status={ErrorCode::NotSupported,"窗口选择需要显式原生Reader配置"};return result;}
    try
    {
        auto path=bar_path(request.exchange,request.code);
        if (std::filesystem::exists(path)||std::filesystem::exists(path.string()+".metadata.json"))
        {
            RootLease lease(root_);
            auto data=load_verified_envelope(path,root_,max_bars_);result.metadata=data.metadata;
            if(reader_)
            {
                result.status=reader_->query(selection,data.metadata.content_id,
                    native_rows(data.bytes,max_bars_,native_cache_bytes_),result.bars);
                if(!result.status.ok())return result;
            }
            else
            {
                // 未接线的旧开发候选保持兼容；原生配置失败绝不进入这条分支。
                data.bars=read_native(data.bytes,max_bars_);
                for(const auto& bar:data.bars)if(full_time(bar)>=request.from && full_time(bar)<=request.to)
                    result.bars.push_back(bar);
            }
        }
        if (!request.calendar_version.empty() && !request.expected_minutes.empty())
        {
            result.coverage=Coverage::Complete;
            for (auto expected:request.expected_minutes)
                if (!std::binary_search(result.bars.begin(),result.bars.end(),expected,
                    [](const auto& a,const auto& b) {
                        if constexpr (std::is_same_v<std::decay_t<decltype(a)>,wtp::WTSBarStruct>) return full_time(a)<b;
                        else return a<full_time(b);
                    })) result.missing_minutes.push_back(expected);
            if (!result.missing_minutes.empty()) result.coverage=Coverage::Gaps;
        }
    }
    catch (const NativeFileBusy& e){result.status={ErrorCode::Backpressure,e.what()};}
    catch (const RootBusy& e){result.status={ErrorCode::Backpressure,e.what()};}
    catch (const NativeBarBudget& e){result.status={ErrorCode::Backpressure,e.what()};}
    catch (const std::exception& e) { result.status=io(e.what()); result.bars.clear(); result.coverage=Coverage::Unknown; }
    return result;
}
Status NativeHistoryStore::freeze(const std::string& exchange,const std::string& code,const std::filesystem::path& snapshot_root)
{
    std::lock_guard<std::mutex> lock(mutex_);
    if (!valid_symbol(exchange,code)) return invalid("证券代码非法");
    try
    {
        RootLease lease(root_);
        auto source=bar_path(exchange,code);
        auto data=load_verified_dataset(source,root_,max_bars_);
        auto claimed=claim_new_root(snapshot_root);if(!claimed.ok())return claimed;
        auto destination=std::filesystem::absolute(snapshot_root)/"his"/"min1"/exchange/(code+".dsb");
        std::filesystem::create_directories(destination.parent_path());
        write_file(destination,data.bytes); write_file(destination.string()+".metadata.json",data.metadata_bytes);
        if (content_id(read_file(destination,max_bars_*sizeof(wtp::WTSBarStruct)+65536))!=data.metadata.content_id)
            return io("冻结副本校验失败");
        write_file(std::filesystem::absolute(snapshot_root)/".guanheng-frozen",
            data.metadata.content_id+"\n"+content_id(data.metadata_bytes)+"\n");
        return {};
    }
    catch (const NativeFileBusy& e) { return {ErrorCode::Backpressure,e.what()}; }
    catch (const RootBusy& e) { return {ErrorCode::Backpressure,e.what()}; }
    catch (const std::exception& e) { return io(e.what()); }
}
Status NativeHistoryStore::recover_into(const std::string& exchange,const std::string& code,const std::filesystem::path& new_root)
{
    std::lock_guard<std::mutex> lock(mutex_);
    if(!valid_symbol(exchange,code))return invalid("证券代码非法");
    try
    {
        auto source=bar_path(exchange,code);
        auto metadata=parse_metadata(read_file(source.string()+".metadata.json.previous",65536));
        auto bytes=read_file(source.string()+".previous",max_bars_*sizeof(wtp::WTSBarStruct)+65536);
        if(content_id(bytes)!=metadata.content_id)return io("上一版历史与元数据不一致，保留原件等待核查");
        auto claimed=claim_new_root(new_root);if(!claimed.ok())return claimed;
        auto bars=read_native(bytes,max_bars_);
        NativeHistoryStore recovered(new_root,max_bars_);
        return recovered.publish(exchange,code,bars,metadata);
    }
    catch(const std::exception& e){return io(e.what());}
}

HistoryPreparationQueue::HistoryPreparationQueue(NativeHistoryStore& store,std::shared_ptr<IHistoryEndpoint> endpoint,
    std::size_t capacity,std::size_t page_limit,std::uint32_t deadline_ms,std::size_t staging_limit)
    :store_(store),endpoint_(std::move(endpoint)),capacity_(capacity),page_limit_(page_limit),staging_limit_(staging_limit),deadline_ms_(deadline_ms)
{
    if (!capacity || !page_limit || page_limit>1000000 || !deadline_ms || !staging_limit || staging_limit>1000000)
        throw std::invalid_argument("历史工作预算非法");
}
Preparation HistoryPreparationQueue::request(const MinuteRequest& request)
{
    std::lock_guard<std::mutex> lock(mutex_);
    auto status=validate_request(request); if (!status.ok()) return {0,PreparationState::Failed,status};
    for (const auto& task:tasks_)
        if (task.result.state==PreparationState::Pending && task.request.exchange==request.exchange && task.request.code==request.code && task.request.from==request.from
            && task.request.to==request.to && task.request.expected_minutes==request.expected_minutes
            && task.request.calendar_version==request.calendar_version) return task.result;
    if (tasks_.size()>=capacity_) return {0,PreparationState::Failed,{ErrorCode::Backpressure,"历史待办预算已满"}};
    auto current=store_.query(request);
    Preparation p; p.id=next_id_++;
    if (!current.status.ok()) {p.state=current.status.code==ErrorCode::Backpressure?PreparationState::Pending:PreparationState::Failed;p.status=current.status;}
    else if (current.coverage==Coverage::Complete) {p.state=PreparationState::Complete;p.status={};}
    else if (current.coverage==Coverage::Unknown) {p.status={ErrorCode::Pending,"缺少适用日历/停牌依据"};}
    else if (!endpoint_ || !endpoint_->history_capability().supported
        || endpoint_->history_capability().qualification==Qualification::Unavailable)
        {p.state=PreparationState::Unavailable;p.status={ErrorCode::Unavailable,"历史端点能力尚未具备"};}
    tasks_.push_back({request,p}); return p;
}
Preparation HistoryPreparationQueue::inspect(std::uint64_t id) const
{
    std::lock_guard<std::mutex> lock(mutex_);
    for (const auto& t:tasks_) if (t.result.id==id) return t.result;
    return {id,PreparationState::Failed,invalid("历史待办不存在")};
}
Status HistoryPreparationQueue::release(std::uint64_t id)
{
    std::lock_guard<std::mutex> lock(mutex_);
    if(!id)return invalid("历史待办 id 不能为零");
    // worker 在门外持有 tasks_ 的位置；所有 erase 都等它回写后再执行。
    if(running_)return {ErrorCode::Backpressure,"历史 worker 运行期间不能释放待办"};
    auto found=std::find_if(tasks_.begin(),tasks_.end(),[&](const Task& task){return task.result.id==id;});
    if(found!=tasks_.end())tasks_.erase(found);
    return {};
}
Preparation HistoryPreparationQueue::work_one(std::uint64_t id)
{
    std::unique_lock<std::mutex> lock(mutex_);
    auto runnable=[](const Task& t){return t.result.state==PreparationState::Pending
        && !t.request.calendar_version.empty() && !t.request.expected_minutes.empty();};
    auto found=tasks_.end();
    if(id)
    {
        found=std::find_if(tasks_.begin(),tasks_.end(),[&](const Task& task){return task.result.id==id;});
        if(found==tasks_.end())return {id,PreparationState::Failed,invalid("历史待办不存在")};
        if(!runnable(*found))return found->result;
    }
    if(running_)return {id,PreparationState::Failed,{ErrorCode::Backpressure,"历史 worker 已运行"}};
    if(!id)found=std::find_if(tasks_.begin(),tasks_.end(),runnable);
    if(found==tasks_.end())return {0,PreparationState::Unavailable,{ErrorCode::Unavailable,"当前没有可准备的缺口"}};
    auto index=static_cast<std::size_t>(found-tasks_.begin());
    Task task=*found;
    running_=true;lock.unlock();
    auto& p=task.result;
    const auto& request=task.request;
    try
    {
        auto advance=[&]() -> Status {
            auto current=store_.query(request);
            if(!current.status.ok())return current.status;
            if(current.coverage==Coverage::Complete && !task.active_window)
                {p.state=PreparationState::Complete;return {};}
            if(current.coverage==Coverage::Unknown)
                return {ErrorCode::Pending,"缺少适用日历/停牌依据"};
            if(task.metadata_bound && !current.bars.empty()
                && !same_metadata(task.staged_metadata,current.metadata))
                return {ErrorCode::Conflict,"已发布历史已修订，暂存页不能覆盖新版本"};
            if(!task.source_complete)
            {
                if(!endpoint_)return {ErrorCode::Unavailable,"历史端点缺失"};
                auto capability=endpoint_->history_capability();
                if(!capability.supported || capability.qualification==Qualification::Unavailable)
                    return {ErrorCode::Unavailable,"历史端点资格已丢失"};
                if(!task.active_window)
                {
                    auto first=std::upper_bound(current.missing_minutes.begin(),current.missing_minutes.end(),task.scanned_through);
                    if(first==current.missing_minutes.end())
                    {task.scanned_through=0;return {ErrorCode::Pending,"本轮扫描结束，后续调用重查剩余缺口"};}
                    const auto limits=endpoint_->fetch_limits();
                    auto limit=(std::min)(page_limit_,staging_limit_);
                    if(limits.max_rows)limit=(std::min)(limit,*limits.max_rows);
                    if(!limit)return invalid("历史来源行数上限须为正数");
                    std::uint64_t elapsed=limit-1;
                    if(limits.max_elapsed_minutes)elapsed=(std::min)(elapsed,*limits.max_elapsed_minutes);
                    MinuteRequest window=request;window.from=*first;window.to=window_end(*first,elapsed,request.to);
                    window.expected_minutes.assign(std::lower_bound(request.expected_minutes.begin(),request.expected_minutes.end(),window.from),
                        std::upper_bound(request.expected_minutes.begin(),request.expected_minutes.end(),window.to));
                    task.active_window=std::move(window);task.active_limit=limit;
                }
                // partial 页持续使用原窗口；已暂存的尾部不能使较早缺口被跳过。
                const auto& gaps=*task.active_window;
                auto started=std::chrono::steady_clock::now();
                auto page=endpoint_->fetch(gaps,task.active_limit,deadline_ms_);
                if(std::chrono::steady_clock::now()-started>std::chrono::milliseconds(deadline_ms_))
                    return {ErrorCode::Timeout,"历史端点超出截止时间"};
                if(!page.status.ok())return page.status;
                if(page.bars.size()>task.active_limit)return {ErrorCode::Backpressure,"源返回超额历史页"};
                auto status=validate_metadata(page.metadata);if(!status.ok())return status;
                if(static_cast<int>(page.metadata.qualification)>static_cast<int>(capability.qualification))
                    return invalid("历史页资格超过端点声明");
                if(!page.bars.empty())
                {
                    status=validate_bars(page.bars,task.active_limit);if(!status.ok())return status;
                    for(const auto& b:page.bars)if(full_time(b)<gaps.from || full_time(b)>gaps.to)
                        return invalid("历史页超出请求范围");
                }
                if((!current.bars.empty() && !same_metadata(current.metadata,page.metadata))
                    || (task.metadata_bound && !same_metadata(task.staged_metadata,page.metadata)))
                    return {ErrorCode::Conflict,"历史来源或版本变更需显式全量修订"};
                std::vector<wtp::WTSBarStruct> staged;
                status=merge_sequences(task.staged,page.bars,staging_limit_,staged);
                if(!status.ok())return status;
                task.staged=std::move(staged);task.staged_metadata=page.metadata;task.metadata_bound=true;
                task.source_complete=page.complete;
                if(!task.source_complete)return {ErrorCode::Pending,"历史源页尚未结束，数据仅在有界待办内暂存"};
            }
            // Store 在同一根 lease 内读取最新版并合并，避免查询后发布覆盖其他写入。
            if(!task.staged.empty())
            {
                auto status=store_.merge_bars(request.exchange,request.code,task.staged,task.staged_metadata);
                if(!status.ok())return status; // 发布背压保留已结束源页，下次只重试发布。
            }
            task.scanned_through=task.active_window->to;
            task.active_window.reset();task.active_limit=0;task.staged.clear();task.source_complete=false;
            auto verified=store_.query(request);if(!verified.status.ok())return verified.status;
            if(verified.coverage==Coverage::Complete){p.state=PreparationState::Complete;return {};}
            // 空片或未齐片也结束本轮的这个范围；后片完成后才回头重查，避免饥饿。
            if(std::upper_bound(verified.missing_minutes.begin(),verified.missing_minutes.end(),task.scanned_through)==verified.missing_minutes.end())
                task.scanned_through=0;
            return {ErrorCode::Pending,"本片已结束，覆盖仍有缺口，等待下一次有界推进"};
        };
        p.status=advance();
    }
    catch(const std::exception& e){p.status=io(e.what());}
    if(!p.status.ok() && p.status.code!=ErrorCode::Pending && p.status.code!=ErrorCode::Backpressure)
        p.state=(p.status.code==ErrorCode::Unavailable || p.status.code==ErrorCode::NotSupported)
            ?PreparationState::Unavailable:PreparationState::Failed;
    lock.lock();tasks_[index]=std::move(task);running_=false;return tasks_[index].result;
}
bool NativeHistoryLoader::loadRawHisBars(void* obj,const char* code,wtp::WTSKlinePeriod period,wtp::FuncReadBars cb)
{
    if (!code || !cb || period!=wtp::KP_Minute1) return false;
    std::string symbol=code; auto first=symbol.find('.');auto last=symbol.rfind('.');
    if (first==std::string::npos) return false;
    MinuteRequest request;request.exchange=symbol.substr(0,first);request.code=symbol.substr(last+1);
    request.from=200401010000ULL;request.to=209912312359ULL;
    auto result=store_.query(request);
    if (!result.status.ok() || result.bars.empty()) return false;
    cb(obj,result.bars.data(),static_cast<std::uint32_t>(result.bars.size())); return true;
}
}
