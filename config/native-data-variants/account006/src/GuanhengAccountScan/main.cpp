// 观衡一次账户采集产品入口。原 Adapter/插件指针只属于本线程，stdout 只承载值协议。
#include "GuanhengQmtBootstrap/ReadOnlyTrader.h"
#include <boost/noncopyable.hpp>
#include "WtCore/TraderAdapter.h"
#include "WtCore/ITrdNotifySink.h"
#include "WTSTools/WTSBaseDataMgr.h"
#include "WTSTools/WTSLogger.h"
#include "WTSUtils/WTSCfgLoader.h"
#include "Includes/WTSVariant.hpp"
#include <rapidjson/document.h>
#include <rapidjson/reader.h>
#include <rapidjson/memorystream.h>
#include <rapidjson/stringbuffer.h>
#include <rapidjson/writer.h>
#include <Windows.h>
#include <bcrypt.h>
#include <io.h>
#include <fcntl.h>
#include <direct.h>
#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <memory>
#include <set>
#include <string>
#include <thread>
#include <vector>

namespace fs = std::filesystem;
namespace rj = rapidjson;
using namespace guanheng::bootstrap;
namespace {
using Clock = std::chrono::steady_clock;
constexpr unsigned config_bytes = 64 * 1024;
constexpr unsigned frame_bytes = 20 * 1024 * 1024;
constexpr unsigned view_bytes = 16 * 1024 * 1024;
const char* scan_schema(unsigned version)
{ return version == 2 ? "guanheng.account-scan.v2" : "guanheng.account-scan.v1"; }
constexpr const char* datatypes[] = {"position", "order", "deal", "account"};

struct Failure { const char* code; };
void require(bool condition, const char* code = "configuration")
{ if (!condition) throw Failure{code}; }

// 所有配置、装载和发布沿原started收窄总期限；单步晚回后不再启动下一步。
// 清理保留原绝对截止，硬回收由父Job负责。
struct Deadline
{
    Clock::time_point started, until;
    explicit Deadline(Clock::time_point value) : started(value), until(value + std::chrono::milliseconds(30000)) {}
    void configure(unsigned total_ms) { until = started + std::chrono::milliseconds(total_ms); check(); }
    bool active() const { return Clock::now() < until; }
    void check() const { require(active(), "source"); }
    unsigned remaining() const
    {
        const auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(until - Clock::now()).count();
        return ms > 0 ? static_cast<unsigned>(ms) : 0;
    }
    template<class Operation> auto work(Operation operation) const -> decltype(operation())
    { check(); auto value = operation(); check(); return value; }
};

// SAX 先约束深度/节点/重复键，再建 DOM，避免配置的深嵌套先耗尽解析栈。
struct JsonGuard : rj::BaseReaderHandler<rj::UTF8<>, JsonGuard>
{
    struct Level { bool object; std::set<std::string> keys; };
    std::vector<Level> levels;
    unsigned nodes = 0;
    Deadline* budget = nullptr;
    bool scalar() { if (budget) budget->check(); return ++nodes <= 65536; }
    bool Null() { return scalar(); }
    bool Bool(bool) { return scalar(); }
    bool Int(int) { return scalar(); }
    bool Uint(unsigned) { return scalar(); }
    bool Int64(std::int64_t) { return scalar(); }
    bool Uint64(std::uint64_t) { return scalar(); }
    bool Double(double value) { return std::isfinite(value) && scalar(); }
    bool String(const char*, rj::SizeType, bool) { return scalar(); }
    bool Key(const char* text, rj::SizeType size, bool)
    { if (budget) budget->check(); return !levels.empty() && levels.back().object && levels.back().keys.emplace(text, size).second; }
    bool start(bool object)
    { if (levels.size() >= 12 || !scalar()) return false; levels.push_back({object, {}}); return true; }
    bool StartObject() { return start(true); }
    bool StartArray() { return start(false); }
    bool EndObject(rj::SizeType) { levels.pop_back(); return true; }
    bool EndArray(rj::SizeType) { levels.pop_back(); return true; }
};

rj::Document parse(const std::string& body, const char* error, Deadline& budget)
{
    budget.check();
    require(!body.empty() && body.find('\0') == std::string::npos, error);
    rj::MemoryStream input(body.data(), body.size());
    rj::Reader reader;
    JsonGuard guard;
    guard.budget = &budget;
    require(reader.Parse<rj::kParseValidateEncodingFlag>(input, guard), error);
    budget.check();
    rj::Document value;
    // view 复制也会重新解析 JSON；保持原 double，避免扫描输出再次引入末位偏移。
    value.Parse<rj::kParseValidateEncodingFlag | rj::kParseFullPrecisionFlag>(body.data(), body.size());
    require(!value.HasParseError(), error);
    budget.check();
    return value;
}

template<class OutputEncoding>
std::string encode_json(const rj::Value& value, Deadline* budget)
{
    if (budget) budget->check();
    rj::StringBuffer buffer;
    rj::Writer<rj::StringBuffer, rj::UTF8<>, OutputEncoding> writer(buffer);
    require(value.Accept(writer), "internal");
    if (budget) budget->check();
    return {buffer.GetString(), buffer.GetSize()};
}

std::string encode(const rj::Value& value, Deadline* budget = nullptr)
{ return encode_json<rj::UTF8<>>(value, budget); }

std::string encode_wt_config(const rj::Value& value, Deadline* budget)
{
    // 原WT loader会在Windows转换非ASCII字节；标准Unicode转义保留UTF-8值，沿原预算装配。
    return encode_json<rj::ASCII<>>(value, budget);
}

void keys(const rj::Value& value, std::initializer_list<const char*> allowed)
{
    require(value.IsObject());
    for (auto it = value.MemberBegin(); it != value.MemberEnd(); ++it) {
        bool found = false;
        for (auto key : allowed) if (it->name == key) { found = true; break; }
        require(found);
    }
}

const rj::Value& member(const rj::Value& object, const char* key, const char* error = "configuration")
{ require(object.IsObject() && object.HasMember(key), error); return object[key]; }

std::string text(const rj::Value& object, const char* key, unsigned limit = 2048)
{
    const auto& value = member(object, key);
    require(value.IsString() && value.GetStringLength() && value.GetStringLength() <= limit);
    std::string result(value.GetString(), value.GetStringLength());
    for (unsigned char c : result) require(c >= 32 && c != 127);
    return result;
}

void fixed(const rj::Value& object, const char* key, const char* expected)
{ require(text(object, key) == expected); }

unsigned number(const rj::Value& object, const char* key, unsigned fallback, unsigned low, unsigned high)
{
    if (!object.HasMember(key)) { require(fallback >= low && fallback <= high); return fallback; }
    const auto& value = object[key];
    require(value.IsUint() && value.GetUint() >= low && value.GetUint() <= high);
    return value.GetUint();
}

void set_number(rj::Value& object, const char* key, unsigned value, rj::Document::AllocatorType& allocator)
{
    if (object.HasMember(key)) object[key].SetUint(value);
    else object.AddMember(rj::Value(key, allocator), value, allocator);
}

bool identifier(const std::string& value, unsigned limit)
{ return !value.empty() && value.size() <= limit && value.find_first_not_of("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-") == std::string::npos; }

bool uuid(const std::string& value)
{
    if (value.size() != 36) return false;
    for (unsigned i = 0; i < value.size(); ++i) {
        if (i == 8 || i == 13 || i == 18 || i == 23) { if (value[i] != '-') return false; }
        else if (!((value[i] >= '0' && value[i] <= '9') || (value[i] >= 'a' && value[i] <= 'f') || (value[i] >= 'A' && value[i] <= 'F'))) return false;
    }
    return true;
}

std::string utf8(const std::wstring& value)
{
    int size = WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, value.data(), static_cast<int>(value.size()), nullptr, 0, nullptr, nullptr);
    require(size > 0);
    std::string result(size, '\0');
    require(WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, value.data(), static_cast<int>(value.size()), &result[0], size, nullptr, nullptr) == size);
    return result;
}

// 原始配置body与文件制品共用一个摘要owner；构造晚失败也由State回收CNG句柄。
struct Sha256
{
    struct State {
        BCRYPT_ALG_HANDLE algorithm = nullptr;
        BCRYPT_HASH_HANDLE hash = nullptr;
        ~State() { if (hash) BCryptDestroyHash(hash); if (algorithm) BCryptCloseAlgorithmProvider(algorithm, 0); }
    } state;
    Deadline& budget;
    explicit Sha256(Deadline& value) : budget(value)
    {
        require(budget.work([&] { return BCryptOpenAlgorithmProvider(&state.algorithm, BCRYPT_SHA256_ALGORITHM, nullptr, 0); }) >= 0);
        require(budget.work([&] { return BCryptCreateHash(state.algorithm, &state.hash, nullptr, 0, nullptr, 0, 0); }) >= 0);
    }
    Sha256(const Sha256&) = delete;
    Sha256& operator=(const Sha256&) = delete;
    void update(const unsigned char* bytes, ULONG size)
    { require(budget.work([&] { return BCryptHashData(state.hash, const_cast<PUCHAR>(bytes), size, 0); }) >= 0); }
    std::string finish()
    {
        std::array<unsigned char, 32> digest;
        require(budget.work([&] { return BCryptFinishHash(state.hash, digest.data(), static_cast<ULONG>(digest.size()), 0); }) >= 0);
        const char* hex = "0123456789abcdef";
        std::string result;
        for (auto byte : digest) { result += hex[byte >> 4]; result += hex[byte & 15]; }
        budget.check();
        return result;
    }
};

std::string config_sha256(const std::string& body, Deadline& budget)
{
    Sha256 digest(budget);
    digest.update(reinterpret_cast<const unsigned char*>(body.data()), static_cast<ULONG>(body.size()));
    return digest.finish();
}

struct File
{
    HANDLE handle = INVALID_HANDLE_VALUE;
    Deadline& budget;
    File(const fs::path& path, Deadline& value) : budget(value)
    {
        budget.check();
        handle = CreateFileW(path.c_str(), GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
        require(handle != INVALID_HANDLE_VALUE);
        try { budget.check(); }
        catch (...) { CloseHandle(handle); handle = INVALID_HANDLE_VALUE; throw; }
    }
    ~File() { if (handle != INVALID_HANDLE_VALUE) CloseHandle(handle); }
    File(const File&) = delete;
    File& operator=(const File&) = delete;
    std::string read_config()
    {
        LARGE_INTEGER size;
        require(budget.work([&] { return GetFileSizeEx(handle, &size); }) && size.QuadPart > 0 && size.QuadPart <= config_bytes);
        std::string body(static_cast<std::size_t>(size.QuadPart), '\0');
        DWORD got = 0;
        require(budget.work([&] { return ReadFile(handle, &body[0], static_cast<DWORD>(body.size()), &got, nullptr); }) && got == body.size());
        return body;
    }
    std::string sha256()
    {
        Sha256 digest(budget);
        std::array<unsigned char, 65536> block;
        DWORD got;
        for (;;) {
            require(budget.work([&] { return ReadFile(handle, block.data(), static_cast<DWORD>(block.size()), &got, nullptr); }));
            if (!got) break;
            digest.update(block.data(), got);
        }
        return digest.finish();
    }
};

fs::path absolute_path(const std::string& value)
{
    fs::path path = fs::u8path(value);
    require(path.is_absolute());
    return fs::canonical(path);
}

struct Config
{
    rj::Document json;
    fs::path installation, library;
    std::array<fs::path, 3> base;
    std::vector<std::unique_ptr<File>> locked_files;
    unsigned total_ms = 15000, close_ms = 2000, max_rows = 4096, view_limit = view_bytes;
    unsigned version = 1, inspection_version = 2;
    std::string adapter_id, instance_id;
    Deadline& budget;

    fs::path bound_file(const rj::Value& value)
    {
        keys(value, {"path", "sha256"});
        auto path = budget.work([&] { return absolute_path(text(value, "path", 8192)); });
        auto expected = text(value, "sha256", 64);
        require(expected.size() == 64 && expected.find_first_not_of("0123456789abcdef") == std::string::npos);
        auto file = std::make_unique<File>(path, budget);
        require(file->sha256() == expected);
        // 保持只读共享句柄至装载结束，防止摘要核验后文件被写入或替换。
        locked_files.emplace_back(std::move(file));
        return path;
    }

    Config(const fs::path& path, Deadline& value, unsigned& protocol_version, const std::string& expected_config_sha) : budget(value)
    {
        require(path.is_absolute());
        File input(path, budget);
        const auto body = input.read_config();
        // 校验同一次读取的body，路径别名后续变化不能切换父端已准入配置。
        if (!expected_config_sha.empty()) require(config_sha256(body, budget) == expected_config_sha);
        json = parse(body, "configuration", budget);
        const auto& encoded_version = member(json, "schema_version");
        require(encoded_version.IsUint() && (encoded_version.GetUint() == 1 || encoded_version.GetUint() == 2));
        version = encoded_version.GetUint();
        require((version == 2) == !expected_config_sha.empty());
        protocol_version = version;
        inspection_version = version == 2 ? 3 : 2;
        keys(json, {"schema_version", "installation_root", "library", "base_data", "trader", "budget"});
        require(json.MemberCount() == 6);
        const auto& limits = member(json, "budget");
        keys(limits, {"total_ms"});
        total_ms = number(limits, "total_ms", 15000, 1000, 30000);
        budget.configure(total_ms);
        installation = budget.work([&] { return absolute_path(text(json, "installation_root", 8192)); });
        require(budget.work([&] { return fs::is_directory(installation) && fs::equivalent(fs::current_path(), installation); }));
        // 固定原 WtHelper 用 255 字节 _getcwd 接口生成插件目录；先核其路径容量。
        char adapter_cwd[256] = {};
        require(budget.work([&] { return _getcwd(adapter_cwd, 255); }) != nullptr);
        require(budget.work([&] { return fs::equivalent(fs::path(adapter_cwd), installation); }));
        std::array<wchar_t, 32768> executable;
        DWORD size = budget.work([&] { return GetModuleFileNameW(nullptr, executable.data(), static_cast<DWORD>(executable.size())); });
        require(size > 0 && size < executable.size());
        require(budget.work([&] { return fs::equivalent(fs::path(std::wstring(executable.data(), size)).parent_path(), installation); }));
        member(json, "trader");
        auto& trader = json["trader"];
        if (version == 2) {
            keys(trader, {"module", "adapter_id", "instance_id", "enabled", "savedata", "source", "base_url", "key_id_env", "hmac_secret_env", "request_ms", "round_ms", "max_rows", "timeout_ms", "max_response_bytes", "close_ms", "expected_account", "environment", "currency", "profile", "view_bytes", "read_profile_version"});
            fixed(trader, "source", "qmt_shm_bound");
            fixed(trader, "read_profile_version", "qmt.read-profile.v3");
        } else {
            keys(trader, {"module", "adapter_id", "instance_id", "enabled", "savedata", "source", "base_url", "key_id_env", "hmac_secret_env", "request_ms", "round_ms", "max_rows", "timeout_ms", "max_response_bytes", "close_ms", "expected_account", "environment", "currency", "profile", "view_bytes"});
            fixed(trader, "source", "qmt_http");
        }
        fixed(trader, "module", "TraderQMTReadOnly");
        fixed(trader, "profile", "cny_cash_shsz_v1");
        fixed(trader, "currency", "CNY");
        require(member(trader, "enabled").IsBool() && trader["enabled"].GetBool());
        require(member(trader, "savedata").IsBool() && !trader["savedata"].GetBool());
        adapter_id = text(trader, "adapter_id", 24);
        instance_id = text(trader, "instance_id", 48);
        require(identifier(adapter_id, 24));
        const auto expected_account = text(trader, "expected_account", version == 2 ? 63 : 128);
        if (version == 2) {
            // parse已核合法UTF-8；补齐账户C1控制码，避免把码点范围误作单字节范围。
            for (std::size_t i = 0; i + 1 < expected_account.size(); ++i)
                require(!(static_cast<unsigned char>(expected_account[i]) == 0xc2
                    && static_cast<unsigned char>(expected_account[i + 1]) >= 0x80
                    && static_cast<unsigned char>(expected_account[i + 1]) <= 0x9f));
        }
        auto environment = text(trader, "environment", 16);
        require(environment == "simulation" || environment == "live");
        auto url = text(trader, "base_url");
        require(url.rfind("http://", 0) == 0 || url.rfind("https://", 0) == 0);
        for (auto key : {"key_id_env", "hmac_secret_env"}) {
            auto name = text(trader, key, 128);
            require(name.find_first_not_of("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_") == std::string::npos && !(name[0] >= '0' && name[0] <= '9'));
            const char* value = std::getenv(name.c_str());
            require(value && *value);
        }
        auto& allocator = json.GetAllocator();
        unsigned request = number(trader, "request_ms", (std::min)(2000u, total_ms), 1, total_ms);
        unsigned round = number(trader, "round_ms", (std::min)(10000u, total_ms), request, total_ms);
        close_ms = number(trader, "close_ms", (std::min)(2000u, total_ms), 1, total_ms);
        max_rows = number(trader, "max_rows", 4096, 1, 4096);
        view_limit = number(trader, "view_bytes", view_bytes, 1, view_bytes);
        set_number(trader, "request_ms", request, allocator);
        set_number(trader, "round_ms", round, allocator);
        set_number(trader, "close_ms", close_ms, allocator);
        set_number(trader, "max_rows", max_rows, allocator);
        set_number(trader, "view_bytes", view_limit, allocator);
        set_number(trader, "timeout_ms", number(trader, "timeout_ms", request, 1, request), allocator);
        if (version == 2) {
            // wrapper联合下限取认证profile公布值，原Core.prepare负责最后准入。
            require(trader.HasMember("max_response_bytes"));
            set_number(trader, "max_response_bytes", number(trader, "max_response_bytes", 0, 1, 16777216), allocator);
            const auto parent_deadline = std::chrono::duration_cast<std::chrono::nanoseconds>(
                budget.until.time_since_epoch()).count();
            require(parent_deadline > 0);
            // 与插件处于同一进程/steady-clock域；只注入原截止，不能在worker重新起算。
            trader.AddMember("runtime_deadline_ns", static_cast<std::uint64_t>(parent_deadline), allocator);
        } else {
            set_number(trader, "max_response_bytes", number(trader, "max_response_bytes", 2097152, 1, 2097152), allocator);
        }
        trader.AddMember("user", "", allocator);
        trader.AddMember("password", "", allocator);
        library = bound_file(member(json, "library"));
        require(budget.work([&] { return fs::equivalent(installation / "traders/TraderQMTReadOnly.dll", library); }));
        const auto& bd = member(json, "base_data");
        keys(bd, {"sessions", "commodities", "contracts"});
        const char* names[] = {"sessions", "commodities", "contracts"};
        for (unsigned i = 0; i < 3; ++i) base[i] = bound_file(member(bd, names[i]));
        budget.check();
    }
};

struct Plugin
{
    HMODULE module = nullptr;
    decltype(&findReadOnlyTrader) find = nullptr;
    decltype(&pumpReadOnlyTrader) pump = nullptr;
    decltype(&waitReadOnlyTrader) wait = nullptr;
    decltype(&stopReadOnlyTrader) stop = nullptr;
    decltype(&inspectReadOnlyTrader) inspect = nullptr;
    decltype(&inspectReadOnlyTraderView) view = nullptr;
    void (*destroy)(wtp::ITraderApi*&) = nullptr;

    Plugin(const fs::path& library, Deadline& budget)
    {
        module = budget.work([&] { return LoadLibraryExW(library.c_str(), nullptr, LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_DEFAULT_DIRS); });
        require(module != nullptr);
        std::array<wchar_t, 32768> actual;
        DWORD size = budget.work([&] { return GetModuleFileNameW(module, actual.data(), static_cast<DWORD>(actual.size())); });
        require(size > 0 && size < actual.size() && budget.work([&] { return fs::equivalent(fs::path(std::wstring(actual.data(), size)), library); }));
        require(GetProcAddress(module, "gh_nqh_test_notify_wait") == nullptr);
        find = reinterpret_cast<decltype(find)>(GetProcAddress(module, "findReadOnlyTrader"));
        pump = reinterpret_cast<decltype(pump)>(GetProcAddress(module, "pumpReadOnlyTrader"));
        wait = reinterpret_cast<decltype(wait)>(GetProcAddress(module, "waitReadOnlyTrader"));
        stop = reinterpret_cast<decltype(stop)>(GetProcAddress(module, "stopReadOnlyTrader"));
        inspect = reinterpret_cast<decltype(inspect)>(GetProcAddress(module, "inspectReadOnlyTrader"));
        view = reinterpret_cast<decltype(view)>(GetProcAddress(module, "inspectReadOnlyTraderView"));
        destroy = reinterpret_cast<decltype(destroy)>(GetProcAddress(module, "deleteTrader"));
        require(find && pump && wait && stop && inspect && view && destroy);
        budget.check();
    }
    // 原 Adapter 自持另一模块引用。进程退出由 OS 回收全部引用，产品不做热卸载。
};

struct Sink final : wtp::ITrdNotifySink
{
    const std::thread::id owner = std::this_thread::get_id();
    bool ready = false;
    void own() const { require(owner == std::this_thread::get_id(), "internal"); }
    void on_trade(uint32_t, const char*, bool, double, double) override { own(); }
    void on_order(uint32_t, const char*, bool, double, double, double, bool) override { own(); }
    void on_position(const char*, bool, double, double, double, double, uint32_t) override { own(); }
    void on_channel_ready() override { own(); ready = true; }
    void on_channel_lost() override { own(); }
    void on_account(const char*, double, double, double, double, double, double, double, double, double, double) override { own(); }
};

// 未 join 时整个 owner 留在堆上，API、sink、资料、配置和 DLL 都保留到进程回收。
struct Owner
{
    Deadline& budget;
    Config config;
    Plugin plugin;
    WTSBaseDataMgr data;
    Sink sink;
    wtp::TraderAdapter adapter;
    struct VariantRelease { void operator()(wtp::WTSVariant* value) const { if (value) value->release(); } };
    std::unique_ptr<wtp::WTSVariant, VariantRelease> variant;
    wtp::ITraderApi* api = nullptr;
    bool initialized = false, init_attempted = false;

    Owner(const fs::path& path, Deadline& value, unsigned& protocol_version, const std::string& expected_config_sha)
        : budget(value), config(path, value, protocol_version, expected_config_sha), plugin(config.library, value)
    {
        require(budget.work([&] { return data.loadSessions(config.base[0].string().c_str()); }));
        require(budget.work([&] { return data.loadCommodities(config.base[1].string().c_str()); }));
        require(budget.work([&] { return data.loadContracts(config.base[2].string().c_str()); }));
        const auto trader_text = encode_wt_config(config.json["trader"], &budget);
        budget.check();
        variant.reset(WTSCfgLoader::load_from_content(trader_text));
        require(variant != nullptr);
        budget.check();
        adapter.addSink(&sink);
        budget.check();
    }

    Diagnostics diagnostics()
    {
        Diagnostics value;
        require(api && plugin.inspect(api, &value) == 0, "internal");
        return value;
    }

    rj::Document copy_view(unsigned which, unsigned index, unsigned& bytes)
    {
        std::uint32_t needed = 0;
        require(budget.work([&] { return plugin.view(api, config.inspection_version, which, index, nullptr, 0, &needed); }) == Capacity, "internal");
        require(needed > 1 && needed <= config.view_limit && bytes <= config.view_limit - needed, "internal");
        std::vector<char> body(needed);
        std::uint32_t received = 0;
        require(budget.work([&] { return plugin.view(api, config.inspection_version, which, index, body.data(), needed, &received); }) == 0 && received == needed && body.back() == 0, "internal");
        bytes += needed;
        return parse(std::string(body.data(), needed - 1), "internal", budget);
    }

    rj::Document observation(const std::string& scan_id)
    {
        budget.check();
        unsigned bytes = 0;
        auto summary = copy_view(0, 0, bytes);
        require(member(summary, "version", "internal").IsUint() && summary["version"].GetUint() == config.inspection_version, "internal");
        // 先验成功判定依赖的字段，避免RapidJSON缺键/非对象下标越过受控关闭出口。
        require(member(summary, "observation_qualified", "internal").IsBool(), "internal");
        const auto& failure = member(summary, "failure", "internal");
        require(failure.IsObject() && member(failure, "code", "internal").IsInt(), "internal");
        const auto& batches = member(summary, "batches", "internal");
        require(batches.IsArray() && batches.Size() == 4, "internal");
        rj::Document result;
        result.SetObject();
        auto& allocator = result.GetAllocator();
        result.AddMember("schema", rj::Value(scan_schema(config.version), allocator), allocator);
        result.AddMember("scan_id", rj::Value(scan_id.c_str(), allocator), allocator);
        result.AddMember("kind", "observation", allocator);
        rj::Value rows(rj::kObjectType);
        for (unsigned i = 0; i < 4; ++i) {
            const auto& batch = batches[i];
            require(member(batch, "datatype", "internal").IsString() && batch["datatype"] == datatypes[i], "internal");
            require(member(batch, "delivered", "internal").IsBool(), "internal");
            rj::Value group(rj::kArrayType);
            if (batch["delivered"].GetBool()) {
                const auto& count = member(batch, "delivered_row_count", "internal");
                require(count.IsUint() && count.GetUint() <= config.max_rows, "internal");
                for (unsigned index = 0; index < count.GetUint(); ++index) {
                    auto row = copy_view(i + 1, index, bytes);
                    require(member(row, "version", "internal").IsUint() && row["version"].GetUint() == config.inspection_version, "internal");
                    require(member(row, "view", "internal").IsUint() && row["view"].GetUint() == i + 1, "internal");
                    require(member(row, "index", "internal").IsUint() && row["index"].GetUint() == index, "internal");
                    group.PushBack(rj::Value(row, allocator), allocator);
                }
            }
            rows.AddMember(rj::Value(datatypes[i], allocator), group, allocator);
        }
        result.AddMember("summary", rj::Value(summary, allocator), allocator);
        result.AddMember("rows", rows, allocator);
        budget.check();
        return result;
    }
};

// stdout只有一个协议owner。一次发送从编码前即占用槽；半写/flush失败后流永久关闭，
// 失败不能以重发修复长度前缀。即使completion失败，生命周期最终出口也必须照真实closed执行。
// I/O接缝只属于本次输出owner；默认仍为原CRT。借用context的生命周期
// 覆盖整个FrameWriter，调用线程保持原scan线程；接缝不拥有句柄或后台任务。
struct FrameIo
{
    void* context = nullptr;
    using Write = std::size_t (*)(void*, const void*, std::size_t);
    using Flush = int (*)(void*);
    static std::size_t crt_write(void*, const void* bytes, std::size_t size)
    { return std::fwrite(bytes, 1, size, stdout); }
    static int crt_flush(void*) { return std::fflush(stdout); }
    Write write = crt_write;
    Flush flush = crt_flush;
};

struct FrameWriter
{
    FrameIo io;
    explicit FrameWriter(FrameIo value = {}) : io(value)
    { require(io.write != nullptr && io.flush != nullptr, "internal"); }
    bool observation_attempted = false, completion_attempted = false, broken = false;
    void send(const rj::Value& value, bool terminal, Deadline* budget = nullptr)
    {
        require(!broken && !completion_attempted && (terminal || !observation_attempted), "internal");
        if (terminal) completion_attempted = true;
        else observation_attempted = true;
        auto body = encode(value, budget);
        require(body.size() > 0 && body.size() <= frame_bytes, "internal");
        if (budget) budget->check();
        const auto size = static_cast<std::uint32_t>(body.size());
        const unsigned char prefix[] = {static_cast<unsigned char>(size >> 24), static_cast<unsigned char>(size >> 16), static_cast<unsigned char>(size >> 8), static_cast<unsigned char>(size)};
        broken = true;
        require(io.write(io.context, prefix, 4) == 4, "internal");
        if (budget) budget->check();
        require(io.write(io.context, body.data(), body.size()) == body.size(), "internal");
        if (budget) budget->check();
        require(io.flush(io.context) == 0, "internal");
        // 每步晚回都保留broken，不能继续写下一片或重发；已写字节由父协议边界拒绝。
        if (budget) budget->check();
        broken = false;
    }
};

unsigned remaining(Clock::time_point deadline)
{
    const auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(deadline - Clock::now()).count();
    return ms > 0 ? static_cast<unsigned>(ms) : 0;
}

rj::Document make_completion(const std::string& scan_id, const char* error, bool closed, const Diagnostics& diag, Clock::time_point started, unsigned version)
{
    rj::Document value;
    value.SetObject();
    auto& allocator = value.GetAllocator();
    value.AddMember("schema", rj::Value(scan_schema(version), allocator), allocator);
    value.AddMember("scan_id", rj::Value(scan_id.c_str(), allocator), allocator);
    value.AddMember("kind", "completion", allocator);
    value.AddMember("closed", closed, allocator);
    value.AddMember("joined", diag.joined != 0, allocator);
    value.AddMember("worker_live", diag.worker_live != 0, allocator);
    value.AddMember("queued", diag.queued, allocator);
    auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(Clock::now() - started).count();
    value.AddMember("elapsed_ms", static_cast<std::uint64_t>((std::max)(elapsed, static_cast<decltype(elapsed)>(0))), allocator);
    value.AddMember("error_code", rj::Value(error, allocator), allocator);
    return value;
}

int scan(const fs::path& path, const std::string& scan_id, const std::string& expected_config_sha, Clock::time_point started, FrameWriter& output) noexcept
{
    Deadline budget(started);
    Owner* owner = nullptr;
    const char* error = "ok";
    int exit_code = 0;
    unsigned protocol_version = expected_config_sha.empty() ? 1 : 2;
    Diagnostics close;
    try {
        owner = new Owner(path, budget, protocol_version, expected_config_sha);
        auto& o = *owner;
        budget.check();
        o.init_attempted = true;
        o.initialized = o.adapter.init(o.config.adapter_id.c_str(), o.variant.get(), &o.data, nullptr);
        // init可能已经创建插件；先留下可查找身份，再检查晚回，清理才能保留真实依赖。
        o.api = o.plugin.find(o.config.instance_id.c_str());
        budget.check();
        require(o.initialized && o.api, "source");
        require(budget.work([&] { return o.adapter.run(); }), "source");
        // run先返回再pump；原Adapter才已完成AS_LOGINING赋值。
        while (budget.remaining() > 0) {
            auto diag = budget.work([&] { return o.diagnostics(); });
            if (diag.error || o.sink.ready) break;
            int count = budget.work([&] { return o.plugin.pump(o.api, 32); });
            if (count < 0 || o.sink.ready) break;
            require(budget.work([&] { return o.plugin.wait(o.api, PumpReady | StopRequested, budget.remaining()); }) >= 0, "source");
        }
        auto observation = o.observation(scan_id);
        const auto& summary = observation["summary"];
        bool qualified = o.sink.ready && summary["observation_qualified"].IsBool() && summary["observation_qualified"].GetBool()
            && summary["failure"]["code"].IsInt() && summary["failure"]["code"].GetInt() == 0;
        for (const auto& batch : summary["batches"].GetArray()) qualified = qualified && batch["delivered"].GetBool();
        output.send(observation, false, &budget);
        if (!qualified) { error = "source"; exit_code = 3; }
    } catch (const Failure& failure) {
        error = failure.code;
        exit_code = std::strcmp(error, "source") == 0 ? 3 : 2;
    } catch (...) { error = "internal"; exit_code = 2; }

    bool closed = owner == nullptr;
    try {
        if (owner) {
            auto& o = *owner;
            if (!o.api && o.init_attempted) o.api = o.plugin.find(o.config.instance_id.c_str());
            if (o.api) {
                if (o.initialized && !output.observation_attempted && !output.broken && budget.active()) {
                    try { output.send(o.observation(scan_id), false, &budget); }
                    catch (const Failure& failure) { error = failure.code; exit_code = std::strcmp(error, "source") == 0 ? 3 : 2; }
                    catch (...) { error = "internal"; exit_code = 2; }
                }
                require(o.plugin.stop(o.api) == 0, "close");
                o.plugin.pump(o.api, 32);
                const auto deadline = (std::min)(budget.until, Clock::now() + std::chrono::milliseconds(o.config.close_ms));
                const int event = o.plugin.wait(o.api, WorkerDone, remaining(deadline));
                if (event >= 0 && (event & WorkerDone)) o.adapter.release();
                close = o.diagnostics();
                closed = close.phase == static_cast<unsigned>(Phase::Closed) && close.joined && !close.worker_live && !close.queued;
                if (closed) {
                    o.plugin.destroy(o.api);
                    require(!o.api, "close");
                    delete owner;
                    owner = nullptr;
                }
            } else {
                // init曾进入但实例不可核验时保留依赖，不把缺少API身份当成已关闭。
                if (!o.init_attempted) { delete owner; owner = nullptr; closed = true; }
                else { closed = false; }
            }
        }
        if (!closed) { error = "close"; exit_code = 4; }
    } catch (...) { error = "close"; exit_code = 4; closed = false; }

    if (closed && std::strcmp(error, "ok") == 0 && !budget.active()) { error = "source"; exit_code = 3; }
    if (!closed) std::fputs("account_scan:close\n", stderr);
    else if (exit_code) std::fprintf(stderr, "account_scan:%s\n", error);
    try {
        if (!output.broken) {
            auto terminal = make_completion(scan_id, error, closed, close, started, protocol_version);
            output.send(terminal, true, std::strcmp(error, "ok") == 0 ? &budget : nullptr);
        } else if (closed && exit_code == 0) { exit_code = 2; }
    } catch (const Failure& failure) {
        if (closed) exit_code = std::strcmp(failure.code, "source") == 0 ? 3 : 2;
    } catch (...) { if (closed) exit_code = 2; }
    // 唯一最终出口不依赖stdout成功；未知关闭永远不进入析构链，也不产生外层假完成。
    if (!closed) std::_Exit(4);
    return exit_code;
}
} // namespace

int wmain(int argc, wchar_t** argv)
{
    const auto started = Clock::now();
    _setmode(_fileno(stdout), _O_BINARY);
    // 原框架默认日志可能打印到stdout；装配前停止，只输出固定去敏诊断。
    WTSLogger::stop();
    std::string scan_id, expected_config_sha;
    fs::path config;
    FrameWriter output;
    try {
        require(argc == 5 || argc == 7);
        std::set<std::wstring> options;
        for (int i = 1; i < argc; i += 2) {
            std::wstring key = argv[i];
            require(options.emplace(key).second);
            if (key == L"--config") { require(config.empty()); config = fs::path(argv[i + 1]); }
            else if (key == L"--scan-id") { require(scan_id.empty()); scan_id = utf8(argv[i + 1]); }
            else if (key == L"--config-sha256") {
                expected_config_sha = utf8(argv[i + 1]);
                require(expected_config_sha.size() == 64 && expected_config_sha.find_first_not_of("0123456789abcdef") == std::string::npos);
            }
            else require(false);
        }
        require(!config.empty() && config.is_absolute() && uuid(scan_id));
    } catch (...) {
        std::fputs("account_scan:configuration\n", stderr);
        try { Diagnostics empty; output.send(make_completion(scan_id, "configuration", true, empty, started, expected_config_sha.empty() ? 1 : 2), true); }
        catch (...) {}
        return 2;
    }
    // scan拥有关闭和协议最终出口；其失败不能被外层重新包装为closed=true。
    return scan(config, scan_id, expected_config_sha, started, output);
}
