#include "NativeHistoryReader.h"
#include "NativeBarFile.h"
#include "../Includes/IRdmDtReader.h"
#include "../Includes/WTSContractInfo.hpp"
#include "../Includes/WTSDataDef.hpp"
#include "../Includes/WTSSessionInfo.hpp"
#include "../Includes/WTSVariant.hpp"
#include "../Share/CodeHelper.hpp"
#include "../Share/DLLHelper.hpp"
#include "../WTSTools/WTSBaseDataMgr.h"
#include "../WTSTools/WTSDataFactory.h"
#include "../WTSTools/WTSHotMgr.h"
#include <rapidjson/document.h>
#include <algorithm>
#include <array>
#include <atomic>
#include <fstream>
#include <limits>
#include <map>
#include <mutex>
#include <set>
#include <stdexcept>
#include <thread>

namespace guanheng
{
namespace
{
constexpr std::uint64_t native_last_minute = 203012312359ULL;
constexpr std::size_t configuration_limit = 64U * 1024U * 1024U;
constexpr std::size_t configuration_depth = 32;
std::uint64_t minute(const wtp::WTSBarStruct& bar)
{
    return bar.time + 19900000ULL * 10000;
}
template<class T> struct Release
{
    void operator()(T* object) const { if (object) object->release(); }
};
using VariantPtr = std::unique_ptr<wtp::WTSVariant, Release<wtp::WTSVariant>>;
using SlicePtr = std::unique_ptr<wtp::WTSKlineSlice, Release<wtp::WTSKlineSlice>>;
using KlinePtr = std::unique_ptr<wtp::WTSKlineData, Release<wtp::WTSKlineData>>;
// 原 Session 小节列表首次填充使用函数 static；本适配入口跨实例统一串行提取。
std::mutex factory_mutex;

bool standard_day_session(wtp::WTSSessionInfo* session)
{
    if (!session || session->getOffsetMins() != 0 || session->getOpenTime() != 930
        || session->getCloseTime() != 1500 || session->getTradingMins() != 240)
        return false;
    // 验证真实对象的全部分钟映射，不调用具有跨实例静态缓存的 getSecMinList。
    for (std::uint32_t index = 1; index <= 240; ++index)
    {
        const auto elapsed = index <= 120 ? 570 + index : 780 + index - 120;
        const auto hhmm = elapsed / 60 * 100 + elapsed % 60;
        if (session->minuteToTime(index) != hhmm || session->timeToMinutes(hhmm) != index)
            return false;
    }
    return session->timeToMinutes(930) == 0 && session->timeToMinutes(1300) == 120;
}

std::string configuration_bytes(const std::filesystem::path& path)
{
    if (!path.is_absolute() || !std::filesystem::is_regular_file(path) || path.extension() != ".json")
        throw std::invalid_argument("原生 Reader 基础资料必须是存在的绝对 .json 文件路径");
    const auto size = std::filesystem::file_size(path);
    if (size == 0 || size > configuration_limit)
        throw std::invalid_argument("原生 Reader 基础资料为空或超过读取预算");
    std::string result(static_cast<std::size_t>(size), '\0');
    std::ifstream input(path, std::ios::binary);
    if (!input.read(result.data(), static_cast<std::streamsize>(result.size())))
        throw std::runtime_error("原生 Reader 基础资料读取失败");
    return result;
}

// 原配置转换器递归处理对象/数组，根标量会触发 GetArray 断言；先在适配入口限定安全结构。
void validate_json_tree(const rapidjson::Value& value, std::size_t depth)
{
    if (depth > configuration_depth) throw std::invalid_argument("原生基础资料 JSON 嵌套超过预算");
    if (value.IsString())
    {
        if (std::string(value.GetString(), value.GetStringLength()).find('\0') != std::string::npos)
            throw std::invalid_argument("原生基础资料 JSON 字符串含零字符");
    }
    else if (value.IsObject())
    {
        std::set<std::string> names;
        for (auto it = value.MemberBegin(); it != value.MemberEnd(); ++it)
        {
            const std::string name(it->name.GetString(), it->name.GetStringLength());
            if (name.find('\0') != std::string::npos || !names.insert(name).second)
                throw std::invalid_argument("原生基础资料 JSON 含重复键或零字符键");
            validate_json_tree(it->value, depth + 1);
        }
    }
    else if (value.IsArray())
    {
        for (const auto& item : value.GetArray()) validate_json_tree(item, depth + 1);
    }
}

void require_object(const rapidjson::Value& value)
{
    if (!value.IsObject()) throw std::invalid_argument("原生基础资料对应层级必须是 JSON 对象");
}

void string_fields(const rapidjson::Value& object, std::initializer_list<const char*> fields)
{
    for (const auto* field : fields)
    {
        const auto found = object.FindMember(field);
        if (found != object.MemberEnd() && !found->value.IsString())
            throw std::invalid_argument(std::string("原生基础资料字段必须是字符串: ") + field);
    }
}

void require_numeric(const rapidjson::Value& value)
{
    // 原 WTSVariant 接受数值及数值字符串；对象/数组不能交给其标量转换方法。
    if (!value.IsNumber() && !value.IsString())
        throw std::invalid_argument("原生基础资料数值字段必须是数值或数值字符串");
}

void numeric_fields(const rapidjson::Value& object, std::initializer_list<const char*> fields)
{
    for (const auto* field : fields)
    {
        const auto found = object.FindMember(field);
        if (found != object.MemberEnd()) require_numeric(found->value);
    }
}

void validate_section(const rapidjson::Value& value)
{
    require_object(value);
    for (const auto* field : {"from", "to"})
    {
        const auto found = value.FindMember(field);
        if (found == value.MemberEnd()) throw std::invalid_argument("交易时段缺少起止时间");
        require_numeric(found->value);
    }
}

void validate_commodity(const rapidjson::Value& value)
{
    require_object(value);
    string_fields(value, {"name", "session", "holiday"});
    numeric_fields(value, {"pricetick", "volscale", "category", "covermode", "pricemode", "trademode", "lotstick", "minlots"});
}

std::string native_identifier(const rapidjson::Value& value, std::size_t capacity)
{
    if (!value.IsString() || value.GetStringLength() == 0 || value.GetStringLength() >= capacity)
        throw std::invalid_argument("原生基础资料标识为空或超过固定缓冲区长度");
    return std::string(value.GetString(), value.GetStringLength());
}

void validate_product_identity(const std::string& exchange, const std::string& product)
{
    // 原 getCommodity 先格式化组合代码；CodeInfo::_fullpid 只有 MAX_INSTRUMENT_LENGTH 字节。
    if (exchange.size() + 1 + product.size() >= MAX_INSTRUMENT_LENGTH)
        throw std::invalid_argument("原生交易所与品种组合代码超过固定缓冲区长度");
}

void validate_configuration_json(const std::string& bytes, std::size_t kind, std::set<std::string>& holidays)
{
    if (bytes.find('\0') != std::string::npos)
        throw std::invalid_argument("原生基础资料 JSON 含原始零字符");
    rapidjson::Document document;
    document.Parse<rapidjson::kParseValidateEncodingFlag | rapidjson::kParseIterativeFlag>(bytes.data(), bytes.size());
    if (document.HasParseError() || !document.IsObject() || document.MemberCount() == 0)
        throw std::invalid_argument("原生 Reader 基础资料必须是非空 UTF-8 JSON 对象");
    validate_json_tree(document, 0);
    for (auto top = document.MemberBegin(); top != document.MemberEnd(); ++top)
    {
        const auto& value = top->value;
        if (kind == 0)
        {
            require_object(value);
            string_fields(value, {"name"});
            numeric_fields(value, {"offset"});
            const auto sections = value.FindMember("sections");
            if (sections == value.MemberEnd() || !sections->value.IsArray() || sections->value.Empty())
                throw std::invalid_argument("交易时段必须包含非空 sections 数组");
            for (const auto& section : sections->value.GetArray()) validate_section(section);
            const auto auction = value.FindMember("auction");
            if (auction != value.MemberEnd()) validate_section(auction->value);
            const auto auctions = value.FindMember("auctions");
            if (auctions != value.MemberEnd())
            {
                if (!auctions->value.IsArray()) throw std::invalid_argument("auctions 必须是交易时段数组");
                for (const auto& section : auctions->value.GetArray()) validate_section(section);
            }
        }
        else if (kind == 1 || kind == 2)
        {
            require_object(value);
            const auto exchange = native_identifier(top->name, MAX_EXCHANGE_LENGTH);
            for (auto entry = value.MemberBegin(); entry != value.MemberEnd(); ++entry)
            {
                const auto& item = entry->value;
                require_object(item);
                const auto identifier = native_identifier(entry->name, MAX_INSTRUMENT_LENGTH);
                if (kind == 1)
                {
                    validate_product_identity(exchange, identifier);
                    validate_commodity(item);
                }
                else
                {
                    string_fields(item, {"name", "exchg", "product"});
                    const auto declared_exchange = item.FindMember("exchg");
                    if (declared_exchange == item.MemberEnd()
                        || native_identifier(declared_exchange->value, MAX_EXCHANGE_LENGTH) != exchange)
                        throw std::invalid_argument("原生合约交易所标识缺失或与所属交易所不一致");
                    const auto product = item.FindMember("product");
                    if (product != item.MemberEnd())
                        validate_product_identity(exchange, native_identifier(product->value, MAX_INSTRUMENT_LENGTH));
                    numeric_fields(item, {"maxmarketqty", "maxlimitqty", "minmarketqty", "minlimitqty",
                        "opendate", "expiredate", "longmarginratio", "shortmarginratio"});
                    const auto rules = item.FindMember("rules");
                    if (rules != item.MemberEnd())
                    {
                        validate_commodity(rules->value);
                        if (product == item.MemberEnd()) validate_product_identity(exchange, identifier);
                    }
                }
            }
        }
        else
        {
            if (!value.IsArray()) throw std::invalid_argument("休市模板必须是日期数组");
            for (const auto& date : value.GetArray()) require_numeric(date);
            holidays.insert(std::string(top->name.GetString(), top->name.GetStringLength()));
        }
    }
}

struct Module
{
    DllHandle handle = nullptr;
    wtp::FuncCreateRdmDtReader create = nullptr;
    wtp::FuncDeleteRdmDtReader destroy = nullptr;
    explicit Module(const std::filesystem::path& library)
    {
        if (!library.is_absolute() || !std::filesystem::is_regular_file(library))
            throw std::invalid_argument("原生 Reader 模块必须是存在的绝对文件路径");
#ifdef _WIN32
        handle = ::LoadLibraryExW(library.c_str(), nullptr, LOAD_WITH_ALTERED_SEARCH_PATH);
#else
        handle = DLLHelper::load_library(library.string().c_str());
#endif
        if (!handle) throw std::runtime_error("原生 Reader 模块加载失败");
        create = reinterpret_cast<wtp::FuncCreateRdmDtReader>(DLLHelper::get_symbol(handle, "createRdmDtReader"));
        destroy = reinterpret_cast<wtp::FuncDeleteRdmDtReader>(DLLHelper::get_symbol(handle, "deleteRdmDtReader"));
        if (!create || !destroy)
        {
            DLLHelper::free_library(handle);
            handle = nullptr;
            throw std::runtime_error("原生 Reader 模块缺少创建或释放工厂");
        }
    }
    ~Module() { DLLHelper::free_library(handle); }
};

struct Dataset
{
    std::string content_id;
    std::size_t rows = 0;
    std::uint64_t first = 0, last = 0;
};

// 每个代际独占 sink/base/hot；退休线程仅释放自己的实例，不接触新代际。
struct Generation : wtp::IRdmDtReaderSink
{
    std::shared_ptr<Module> module;
    WTSBaseDataMgr base;
    WTSHotMgr hot;
    VariantPtr settings;
    wtp::IRdmDtReader* reader = nullptr;
    std::map<std::string, Dataset> datasets;
    std::size_t bytes = 0;
    bool failed = false;

    explicit Generation(std::shared_ptr<Module> library) : module(std::move(library)) {}
    ~Generation() { if (reader) module->destroy(reader); }
    wtp::IBaseDataMgr* get_basedata_mgr() override { return &base; }
    wtp::IHotMgr* get_hot_mgr() override { return &hot; }
    void reader_log(wtp::WTSLogLevel, const char*) override {}
};

std::vector<wtp::WTSBarStruct> copy_slice(wtp::WTSKlineSlice* slice, std::size_t maximum)
{
    if (!slice) throw std::runtime_error("原生 Reader 未返回已存在历史的切片");
    if (slice->size() > maximum) throw std::runtime_error("原生切片声明数量超过预算");
    std::size_t actual = 0;
    for (std::size_t index = 0; index < slice->get_block_counts(); ++index)
    {
        const auto count = slice->get_block_size(index);
        if ((count && !slice->get_block_addr(index)) || count > maximum - actual)
            throw std::runtime_error("原生切片数据块无效或超过预算");
        actual += count;
    }
    if (actual != slice->size()) throw std::runtime_error("原生切片声明数量与实际数据块不一致");
    std::vector<wtp::WTSBarStruct> result;
    result.reserve(actual);
    for (std::size_t index = 0; index < slice->get_block_counts(); ++index)
    {
        const auto count = slice->get_block_size(index);
        if (count)
        {
            const auto* bars = slice->get_block_addr(index);
            result.insert(result.end(), bars, bars + count);
        }
    }
    return result;
}
}

class NativeHistoryReader::Impl
{
public:
    std::filesystem::path root;
    std::size_t maximum;
    NativeHistoryReaderConfig config;
    std::array<std::filesystem::path, 4> files;
    std::array<std::string, 4> file_bytes;
    std::set<std::string> holiday_templates;
    std::shared_ptr<Module> module;
    std::unique_ptr<Generation> current;
    std::thread retirement;
    std::atomic<bool> retired { true };
    std::size_t retiring_bytes = 0;

    Impl(std::filesystem::path directory, std::size_t max_bars, NativeHistoryReaderConfig options)
        : root(native_physical_path(directory)), maximum(max_bars), config(std::move(options)),
          files {config.sessions, config.commodities, config.contracts, config.holidays}
    {
        if (!maximum || maximum > 1000000 || config.cache_bytes < sizeof(wtp::WTSBarStruct)
            || config.cache_bytes > 1024ULL * 1024ULL * 1024ULL)
            throw std::invalid_argument("原生 Reader 条数或缓存预算无效");
        for (std::size_t i = 0; i < files.size(); ++i)
        {
            file_bytes[i] = configuration_bytes(files[i]);
            validate_configuration_json(file_bytes[i], i, holiday_templates);
        }
        ensure_history_root();
        module = std::make_shared<Module>(config.library);
        current = make_generation();
    }

    ~Impl()
    {
        // 先结束当前实例，再等唯一退休线程；两者的 sink/base/module 均保持有效。
        current.reset();
        if (retirement.joinable()) retirement.join();
    }

    void ensure_history_root() const
    {
        if (std::filesystem::exists(root / "rt"))
            throw std::runtime_error("原生历史 Reader 根出现实时目录，历史独占约束失效");
    }

    std::unique_ptr<Generation> make_generation()
    {
        // 配置在创建时冻结；文件发生变化必须重建整个适配对象，避免同身份换日历。
        for (std::size_t i = 0; i < files.size(); ++i)
            if (configuration_bytes(files[i]) != file_bytes[i])
                throw std::runtime_error("原生 Reader 基础资料已变化，须重新创建实例");
        auto value = std::make_unique<Generation>(module);
        if (!value->base.loadSessions(config.sessions.string().c_str())
            || !value->base.loadCommodities(config.commodities.string().c_str())
            || !value->base.loadContracts(config.contracts.string().c_str())
            || !value->base.loadHolidays(config.holidays.string().c_str()))
            throw std::runtime_error("原生 Reader 基础资料加载失败");
        for (std::size_t i = 0; i < files.size(); ++i)
            if (configuration_bytes(files[i]) != file_bytes[i])
                throw std::runtime_error("原生 Reader 加载期间基础资料发生变化");
        value->settings.reset(wtp::WTSVariant::createObject());
        value->settings->append("path", root.string().c_str());
        value->reader = module->create();
        if (!value->reader) throw std::runtime_error("原生 Reader 创建失败");
        value->reader->init(value->settings.get(), value.get());
        return value;
    }

    void reap()
    {
        if (retirement.joinable() && retired.load(std::memory_order_acquire))
        {
            retirement.join();
            retiring_bytes = 0;
        }
    }

    void retire_current()
    {
        if (!current) return;
        if (retirement.joinable()) throw std::logic_error("原生历史只能保留一个待释放实例");
        const auto bytes = current->bytes;
        retired.store(false, std::memory_order_release);
        retirement = std::thread([this, previous = std::move(current)]() mutable {
            previous.reset();
            retired.store(true, std::memory_order_release);
        });
        retiring_bytes = bytes;
    }

    Status select_generation(const std::string& key, const std::string& identity, std::size_t rows)
    {
        reap();
        const auto needed = rows * sizeof(wtp::WTSBarStruct);
        if (needed > config.cache_bytes)
            return {ErrorCode::Backpressure, "原生历史超过缓存字节预算"};
        bool replace = current && current->failed;
        bool known = false;
        if (current)
        {
            const auto found = current->datasets.find(key);
            known = found != current->datasets.end();
            if (known && (found->second.content_id != identity || found->second.rows != rows)) replace = true;
            if (!known && needed > config.cache_bytes - current->bytes) replace = true;
        }
        if (replace)
        {
            if (retirement.joinable())
                return {ErrorCode::Backpressure, "上一原生历史代际仍在释放，请稍后重试"};
            if (needed > config.cache_bytes - current->bytes)
            {
                // 紧预算先退出旧代际，重试在释放完成后继续，避免永久无法换代。
                retire_current();
                return {ErrorCode::Backpressure, "原生历史代际正在释放缓存容量，请稍后重试"};
            }
            auto replacement = make_generation();
            retire_current();
            current = std::move(replacement);
            known = false;
        }
        const auto used = retiring_bytes + (current ? current->bytes : 0);
        if (!known && needed > config.cache_bytes - used)
            return {ErrorCode::Backpressure, "原生历史在用及待释放缓存已达预算"};
        if (!current) current = make_generation();
        return {};
    }

    std::string standard_code(const MinuteRequest& request)
    {
        auto* contract = current->base.getContract(request.code.c_str(), request.exchange.c_str());
        auto* commodity = contract ? contract->getCommInfo() : nullptr;
        if (!contract || !commodity || request.exchange != contract->getExchg()
            || request.code != contract->getCode())
            throw std::runtime_error("证券对应的原生合约或商品配置缺失");
        const std::string product = contract->getProduct();
        if (product.empty() || product.size() >= MAX_INSTRUMENT_LENGTH
            || product.find_first_of(".+-\\/") != std::string::npos)
            throw std::runtime_error("原生证券品种代码非法");
        const auto code = CodeHelper::rawFlatCodeToStdCode(request.code.c_str(), request.exchange.c_str(), product.c_str());
        const auto parsed = CodeHelper::extractStdCode(code.c_str(), &current->hot);
        if (request.exchange != parsed._exchg || request.code != parsed._code
            || std::string(parsed._product) != product || parsed._exright || parsed._ruletag[0]
            || current->base.getCommodity(parsed._exchg, parsed._product) != commodity || !commodity->getSessionInfo()
            || !holiday_templates.count(commodity->getTradingTpl())
            || commodity->getSessionInfo()->getTradingMins() == 0)
            throw std::runtime_error("证券对应的原生商品、合约、交易时段或休市模板不完整");
        return code;
    }

    Status query(const HistoryQuery& selection, const std::string& identity,
        std::size_t rows, std::vector<wtp::WTSBarStruct>& output)
    {
        output.clear();
        const auto& request = selection.window;
        const auto period = selection.period_minutes;
        if (period != 1 && period != 5 && period != 15 && period != 30 && period != 60)
            return {ErrorCode::NotSupported, "原生历史窗口仅支持 1/5/15/30/60 分钟"};
        if (selection.limit > 10000 || ((period != 1 || selection.limit)
            && (!request.expected_minutes.empty() || !request.calendar_version.empty())))
            return {ErrorCode::InvalidInput, "原生历史窗口数量超限或与分钟覆盖依据冲突"};
        if (identity.empty() || rows == 0 || rows > maximum || request.from > request.to)
            return {ErrorCode::InvalidInput, "原生历史内容身份、条数或查询区间无效"};
        if ((request.exchange != "SSE" && request.exchange != "SZSE") || request.code.size() != 6
            || !std::all_of(request.code.begin(), request.code.end(), [](char ch) { return ch >= '0' && ch <= '9'; }))
            return {ErrorCode::InvalidInput, "原生历史仅接受沪深六位证券代码"};
        bool native_started = false;
        try
        {
            ensure_history_root();
            const auto key = request.exchange + "." + request.code;
            // 缺合约属于请求/基础资料错误，先验证以免无效请求淘汰已有缓存。
            if (current) standard_code(request);
            auto status = select_generation(key, identity, rows);
            if (!status.ok()) return status;
            const auto code = standard_code(request);
            auto* contract = current->base.getContract(request.code.c_str(), request.exchange.c_str());
            auto* session = contract->getCommInfo()->getSessionInfo();
            if (period != 1 && !standard_day_session(session))
                return {ErrorCode::NotSupported, "派生周期仅支持标准沪深日间交易时段"};
            auto found = current->datasets.find(key);
            if (found == current->datasets.end())
            {
                // 先计入预算；原生部分加载后失败仍可能占用缓存，该代际统一失效。
                current->bytes += rows * sizeof(wtp::WTSBarStruct);
                native_started = true;
                SlicePtr all(current->reader->readKlineSliceByCount(code.c_str(), wtp::KP_Minute1,
                    static_cast<std::uint32_t>(rows), native_last_minute));
                auto bars = copy_slice(all.get(), rows);
                if (bars.size() != rows) throw std::runtime_error("原生历史实际条数与帧声明不一致或超出支持截止");
                status = validate_history_bars(bars, maximum);
                if (!status.ok()) throw std::runtime_error(status.reason);
                Dataset data {identity, rows, minute(bars.front()), minute(bars.back())};
                found = current->datasets.emplace(key, std::move(data)).first;
            }
            const auto& data = found->second;
            if (request.to < data.first || request.from > data.last) return {};
            const auto requested_from = period == 1 ? request.from : request.from / 10000 * 10000;
            const auto from = (std::max)(requested_from, data.first);
            const auto to = (std::min)(request.to, data.last);
            native_started = true;
            SlicePtr slice;
            if (selection.limit)
            {
                // 派生 tail 读取截止内全部已加载有界基础历史，避免 N×周期漏掉闭合桶。
                const auto count = period == 1 ? (std::min)(selection.limit, rows) : rows;
                slice.reset(current->reader->readKlineSliceByCount(code.c_str(), wtp::KP_Minute1,
                    static_cast<std::uint32_t>(count), to));
            }
            else slice.reset(current->reader->readKlineSliceByRange(code.c_str(), wtp::KP_Minute1, from, to));
            auto candidates = copy_slice(slice.get(), rows);
            if (!candidates.empty())
            {
                status = validate_history_bars(candidates, maximum);
                if (!status.ok()) throw std::runtime_error(status.reason);
            }
            // 原生 range 在内部空档可能带回范围外候选；派生 tail 则保留完整左侧桶上下文。
            const auto raw_from = period != 1 && selection.limit ? data.first : from;
            candidates.erase(std::remove_if(candidates.begin(), candidates.end(), [&](const auto& bar) {
                return minute(bar) < raw_from || minute(bar) > to;
            }), candidates.end());
            if (candidates.empty()) return {};
            if (period == 1)
                output = std::move(candidates);
            else
            {
                for (const auto& bar : candidates)
                {
                    const auto hhmm = static_cast<std::uint32_t>(minute(bar) % 10000);
                    const auto index = session->timeToMinutes(hhmm);
                    if (index < 1 || index > 240 || session->minuteToTime(index) != hhmm)
                        return {ErrorCode::InvalidInput, "派生周期源行不属于标准交易时段的有效右端分钟"};
                }
                SlicePtr source(wtp::WTSKlineSlice::create(code.c_str(), wtp::KP_Minute1, 1,
                    candidates.data(), static_cast<std::int32_t>(candidates.size())));
                KlinePtr derived;
                {
                    std::lock_guard<std::mutex> lock(factory_mutex);
                    WTSDataFactory factory;
                    derived.reset(factory.extractKlineData(source.get(), wtp::KP_Minute1, period, session, false, false));
                }
                if (!derived) throw std::runtime_error("原生周期工厂未返回聚合结果");
                const auto& bars = derived->getDataRef();
                if (!bars.empty())
                {
                    status = validate_history_bars(bars, rows);
                    if (!status.ok()) throw std::runtime_error(status.reason);
                }
                for (const auto& bar : bars)
                    if (minute(bar) >= request.from && minute(bar) <= request.to) output.push_back(bar);
            }
            if (selection.limit && output.size() > selection.limit)
                output.erase(output.begin(), output.end() - static_cast<std::ptrdiff_t>(selection.limit));
            return {};
        }
        catch (const std::exception& error)
        {
            if (current && native_started) current->failed = true;
            output.clear();
            return {ErrorCode::IoError, error.what()};
        }
    }
};

NativeHistoryReader::NativeHistoryReader(std::filesystem::path root, std::size_t max_bars,
    NativeHistoryReaderConfig config)
    : impl_(std::make_unique<Impl>(std::move(root), max_bars, std::move(config))) {}
NativeHistoryReader::~NativeHistoryReader() = default;
Status NativeHistoryReader::range(const MinuteRequest& request, const std::string& content_id,
    std::size_t declared_rows, std::vector<wtp::WTSBarStruct>& output)
{
    return query(HistoryQuery {request}, content_id, declared_rows, output);
}
Status NativeHistoryReader::query(const HistoryQuery& request, const std::string& content_id,
    std::size_t declared_rows, std::vector<wtp::WTSBarStruct>& output)
{
    return impl_->query(request, content_id, declared_rows, output);
}
}
