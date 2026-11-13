#pragma once

#include <windows.h>
#include <bcrypt.h>
#include <rapidjson/document.h>
#include <filesystem>
#include <functional>
#include <map>

namespace guanheng {

// AWP 拥有发布及不可变原件；本对象只选择原 WtDataReader 的输入目录。
// 调用者持有 daily_mutex，stop 等待全部读取结束后才销毁本对象。
class PublishedDaily final {
    using Clock = std::chrono::steady_clock;
    using Path = std::filesystem::path;
    using Json = rapidjson::Value;
    struct Handle {
        HANDLE value = INVALID_HANDLE_VALUE;
        explicit Handle(HANDLE handle) : value(handle) {
            need(handle != INVALID_HANDLE_VALUE, "daily publication file unavailable");
        }
        ~Handle() { if (value != INVALID_HANDLE_VALUE) CloseHandle(value); }
        Handle(const Handle&) = delete;
        Handle& operator=(const Handle&) = delete;
    };
    struct Generation {
        // 按声明逆序销毁：原 Reader 先释放缓存，再关闭固定原文件的句柄。
        std::vector<std::unique_ptr<Handle>> pins;
        std::set<std::wstring> directories;
        std::size_t bytes = 0;
        std::string identity;
        std::set<std::string> covered_codes; // 已校验本次发布的日线证券，使用 WT 标准代码。
        std::uint32_t basis_date = 0; // 已核原出版物基准日YYYYMMDD；日线输出上界，不重写原日期。
        Path directory;
        std::vector<Path> files, created_directories;
        std::unique_ptr<wtp::WtDataReader> reader;
        bool close() noexcept {
            reader.reset();
            pins.clear();
            // 只删除本 owner 实际创建的原字节副本及空目录，保留任何意外新增文件。
            const auto remove = [](const Path& path) {
                std::error_code error;
                const auto removed = std::filesystem::remove(path, error);
                if (error) return false;
                const auto exists = std::filesystem::exists(path, error);
                return !error && (removed || !exists);
            };
            for (std::size_t i = files.size(); i; --i)
                if (remove(files[i - 1])) files.erase(files.begin() + i - 1);
            for (std::size_t i = created_directories.size(); i; --i)
                if (remove(created_directories[i - 1])) created_directories.erase(created_directories.begin() + i - 1);
            return files.empty() && created_directories.empty();
        }
        ~Generation() { close(); }
    };
    struct CacheDirectory {
        Path path;
        explicit CacheDirectory(Path value) : path(std::move(value)) {}
        bool close() noexcept {
            std::error_code error;
            std::filesystem::remove(path / "owner.lock", error);
            std::filesystem::remove(path, error);
            const auto exists = std::filesystem::exists(path, error);
            return !error && !exists;
        }
        ~CacheDirectory() { close(); }
    };
    Path status_, publication_, owner_, cache_;
    std::map<std::string, std::string> symbols_; // 外部 symbol -> 原 std_code。
    std::uint32_t adjust_flag_;
    wtp::IDataReaderSink* sink_;
    wtp::IHisDataLoader* loader_;
    std::unique_ptr<Generation> current_;
    std::unique_ptr<Generation> pending_;
    std::unique_ptr<CacheDirectory> cache_directory_;
    std::unique_ptr<Handle> cache_lease_;

    static void need(bool ok, const char* reason) {
        if (!ok) throw std::runtime_error(reason);
    }
    static void check(Clock::time_point deadline) {
        need(Clock::now() < deadline, "daily publication deadline");
    }
    static std::string text(const Json& value) {
        need(value.IsString() && value.GetStringLength() && value.GetStringLength() <= 2048,
            "daily publication string");
        std::string result(value.GetString(), value.GetStringLength());
        need(std::all_of(result.begin(), result.end(), [](unsigned char c) { return c >= 32 && c < 127; }),
            "daily publication ASCII path or identity required");
        return result;
    }
    static const Json& field(const Json& object, const char* name) {
        need(object.IsObject(), "daily publication object");
        const Json* result = nullptr;
        for (auto it = object.MemberBegin(); it != object.MemberEnd(); ++it)
            if (std::string(it->name.GetString(), it->name.GetStringLength()) == name) {
                need(!result, "daily publication duplicate field");
                result = &it->value;
            }
        need(result != nullptr, "daily publication field missing");
        return *result;
    }
    static rapidjson::Document document(const std::string& raw) {
        rapidjson::Document result;
        result.Parse<rapidjson::kParseValidateEncodingFlag>(raw.data(), raw.size());
        need(!result.HasParseError() && result.IsObject(), "daily publication JSON");
        return result;
    }
    static Path absolute(const std::string& value) {
        Path path(value);
        need(path.is_absolute() && path == path.lexically_normal(), "daily publication absolute normalized path");
        return path;
    }
    static void beneath(const Path& path, const Path& root) {
        const auto relative = path.lexically_relative(root);
        need(!relative.empty() && !relative.is_absolute() && *relative.begin() != L"..",
            "daily publication path outside owner");
    }
    static std::string hash(const std::string& raw) {
        BCRYPT_ALG_HANDLE algorithm = nullptr;
        need(BCryptOpenAlgorithmProvider(&algorithm, BCRYPT_SHA256_ALGORITHM, nullptr, 0) >= 0,
            "daily publication hash provider");
        struct Algorithm { BCRYPT_ALG_HANDLE value; ~Algorithm() { BCryptCloseAlgorithmProvider(value, 0); } } guard{algorithm};
        ULONG size = 0, received = 0;
        need(BCryptGetProperty(algorithm, BCRYPT_OBJECT_LENGTH, reinterpret_cast<PUCHAR>(&size), sizeof(size), &received, 0) >= 0 &&
            size > 0 && size <= 65536, "daily publication hash allocation");
        std::vector<unsigned char> object(size);
        BCRYPT_HASH_HANDLE handle = nullptr;
        need(BCryptCreateHash(algorithm, &handle, object.data(), size, nullptr, 0, 0) >= 0, "daily publication hash creation");
        struct Hash { BCRYPT_HASH_HANDLE value; ~Hash() { BCryptDestroyHash(value); } } hash_guard{handle};
        unsigned char bytes[32]{};
        need(BCryptHashData(handle, reinterpret_cast<PUCHAR>(const_cast<char*>(raw.data())), static_cast<ULONG>(raw.size()), 0) >= 0 &&
            BCryptFinishHash(handle, bytes, sizeof(bytes), 0) >= 0, "daily publication hash");
        static constexpr char digits[] = "0123456789abcdef";
        std::string result;
        for (auto byte : bytes) { result += digits[byte >> 4]; result += digits[byte & 15]; }
        return result;
    }
    static std::uint64_t known_millisecond(const Json& value) {
        // QNA原ISO8601时点转沪深会话本地毫秒标签；来源精度超过毫秒时保留已知完整毫秒。
        const auto stamp = text(value);
        need(stamp.size() >= 20 && stamp.size() <= 64 && stamp[4]=='-' && stamp[7]=='-' &&
            stamp[10]=='T' && stamp[13]==':' && stamp[16]==':', "daily publication known_at format");
        auto digits = [&](std::size_t at, std::size_t count) {
            need(at+count<=stamp.size(), "daily publication known_at length");
            unsigned result=0;
            for(std::size_t i=at;i<at+count;++i) {
                need(stamp[i]>='0' && stamp[i]<='9', "daily publication known_at digits");
                result=result*10+static_cast<unsigned>(stamp[i]-'0');
            }
            return result;
        };
        SYSTEMTIME source{};
        source.wYear=digits(0,4);source.wMonth=digits(5,2);source.wDay=digits(8,2);
        source.wHour=digits(11,2);source.wMinute=digits(14,2);source.wSecond=digits(17,2);
        need(source.wYear>=2000 && source.wYear<=2099, "daily publication known_at year");
        std::size_t cursor=19;
        if(stamp[cursor]=='.') {
            const auto begin=++cursor;
            while(cursor<stamp.size() && stamp[cursor]>='0' && stamp[cursor]<='9')++cursor;
            need(cursor>begin && cursor-begin<=9, "daily publication known_at fraction");
            source.wMilliseconds=digits(begin,std::min<std::size_t>(3,cursor-begin));
            for(auto n=cursor-begin;n<3;++n)source.wMilliseconds*=10;
        }
        int offset=0;
        if(cursor+1==stamp.size() && stamp[cursor]=='Z') {}
        else {
            need(cursor+6==stamp.size() && (stamp[cursor]=='+' || stamp[cursor]=='-') &&
                stamp[cursor+3]==':', "daily publication known_at timezone");
            const auto hour=digits(cursor+1,2), minute=digits(cursor+4,2);
            need(hour<=23 && minute<60, "daily publication known_at timezone range");
            offset=static_cast<int>(hour*60+minute)*(stamp[cursor]=='+'?1:-1);
        }
        FILETIME encoded{};
        need(SystemTimeToFileTime(&source,&encoded)!=0, "daily publication known_at invalid");
        ULARGE_INTEGER ticks{};ticks.LowPart=encoded.dwLowDateTime;ticks.HighPart=encoded.dwHighDateTime;
        // 已准入市场仅SH/SZ，交易session使用UTC+08:00；先消除原偏移，再转换会话时区。
        ticks.QuadPart=static_cast<std::uint64_t>(static_cast<std::int64_t>(ticks.QuadPart)+
            static_cast<std::int64_t>(480-offset)*60*10000000);
        encoded.dwLowDateTime=ticks.LowPart;encoded.dwHighDateTime=ticks.HighPart;
        SYSTEMTIME local{};
        need(FileTimeToSystemTime(&encoded,&local)!=0, "daily publication known_at conversion");
        const auto date=static_cast<std::uint64_t>(local.wYear)*10000+local.wMonth*100+local.wDay;
        return (date*10000+local.wHour*100+local.wMinute)*100000+local.wSecond*1000+local.wMilliseconds;
    }
    static std::vector<std::unique_ptr<Handle>> parents(const Path& path, Generation* generation) {
        // 固定父目录防止读入原文件后路径被整体移动，原 Reader 随后仍按同一路径打开。
        std::vector<Path> chain;
        for (auto directory = path.parent_path(); !directory.empty(); directory = directory.parent_path()) {
            // 本代已固定的目录和其祖先仍持有句柄，后续读取只需核新增路径段。
            if (generation && generation->directories.count(directory.native())) break;
            chain.push_back(directory);
            if (directory == directory.root_path()) break;
        }
        std::vector<std::unique_ptr<Handle>> temporary;
        // 从根到叶依次固定，后一层 open 经过的祖先已经持有不可改名句柄。
        for (auto it = chain.rbegin(); it != chain.rend(); ++it) {
            const auto& directory = *it;
            auto handle = std::make_unique<Handle>(CreateFileW(directory.c_str(), FILE_READ_ATTRIBUTES,
                FILE_SHARE_READ | FILE_SHARE_WRITE, nullptr, OPEN_EXISTING,
                FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT, nullptr));
            BY_HANDLE_FILE_INFORMATION info{};
            need(GetFileInformationByHandle(handle->value, &info) && !(info.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT),
                "daily publication parent unavailable or redirected");
            if (generation) {
                need(generation->pins.size() < 1024, "daily publication directory capacity");
                generation->directories.insert(directory.native());
                generation->pins.push_back(std::move(handle));
            }
            else temporary.push_back(std::move(handle));
        }
        return temporary;
    }
    static std::string read(const Path& path, std::size_t maximum, Clock::time_point deadline, Generation* generation = nullptr) {
        check(deadline);
        const auto directory_guards = parents(path, generation);
        auto file = std::make_unique<Handle>(CreateFileW(path.c_str(), GENERIC_READ,
            FILE_SHARE_READ | (generation ? 0 : FILE_SHARE_WRITE | FILE_SHARE_DELETE), nullptr,
            OPEN_EXISTING, FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_SEQUENTIAL_SCAN, nullptr));
        BY_HANDLE_FILE_INFORMATION info{};
        need(GetFileType(file->value) == FILE_TYPE_DISK && GetFileInformationByHandle(file->value, &info) &&
            !(info.dwFileAttributes & (FILE_ATTRIBUTE_DIRECTORY | FILE_ATTRIBUTE_REPARSE_POINT)) &&
            info.nNumberOfLinks == 1 && info.nFileSizeHigh == 0 && info.nFileSizeLow > 0 && info.nFileSizeLow <= maximum,
            "daily publication file type or size");
        if (generation) {
            need(generation->pins.size() < 1024 && info.nFileSizeLow <= 64 * 1024 * 1024 - generation->bytes,
                "daily publication input capacity");
            generation->bytes += info.nFileSizeLow;
        }
        std::string raw(info.nFileSizeLow, '\0');
        DWORD received = 0;
        need(ReadFile(file->value, raw.data(), static_cast<DWORD>(raw.size()), &received, nullptr) && received == raw.size(),
            "daily publication incomplete read");
        char tail; DWORD extra = 0;
        need(ReadFile(file->value, &tail, 1, &extra, nullptr) && extra == 0, "daily publication growing input");
        check(deadline);
        if (generation) generation->pins.push_back(std::move(file));
        return raw;
    }
    std::string pinned(const Json& artifact, Generation& next, Clock::time_point deadline, std::size_t maximum = 4 * 1024 * 1024) {
        const auto path = absolute(text(field(artifact, "path")));
        beneath(path, owner_);
        const auto raw = read(path, maximum, deadline, &next);
        need(hash(raw) == text(field(artifact, "sha256")), "daily publication artifact hash");
        return raw;
    }
    static void stage(const Path& target, const std::string& raw, Generation& next, Clock::time_point deadline) {
        std::vector<Path> missing;
        for (auto path = target.parent_path(); path != next.directory; path = path.parent_path()) missing.push_back(path);
        for (auto it = missing.rbegin(); it != missing.rend(); ++it)
            if (!std::filesystem::exists(*it)) {
                need(std::filesystem::create_directory(*it), "daily publication projection directory");
                next.created_directories.push_back(*it);
            }
        {
            Handle output(CreateFileW(target.c_str(), GENERIC_WRITE, 0, nullptr, CREATE_NEW, FILE_ATTRIBUTE_NORMAL, nullptr));
            next.files.push_back(target);
            DWORD written = 0;
            need(WriteFile(output.value, raw.data(), static_cast<DWORD>(raw.size()), &written, nullptr) && written == raw.size(),
                "daily publication projection write");
        }
        need(read(target, raw.size(), deadline, &next) == raw, "daily publication projection changed");
    }
public:
    PublishedDaily(wtp::WTSVariant* config, std::uint32_t flag, wtp::IDataReaderSink* sink,
        wtp::IHisDataLoader* loader, std::map<std::string, std::string> symbols)
        : symbols_(std::move(symbols)), adjust_flag_(flag), sink_(sink), loader_(loader) {
        need(config && config->type() == wtp::WTSVariant::VT_Object &&
            (config->memberNames().size() == 3 || config->memberNames().size() == 4),
            "daily publication configuration");
        for (const auto& name : config->memberNames())
            need(name == "status_file" || name == "publication_file" || name == "source_root" || name == "cache_root", "daily publication unknown setting");
        for (const char* name : {"status_file", "publication_file", "cache_root"})
            need(config->get(name) && config->get(name)->type() == wtp::WTSVariant::VT_String,
                "daily publication path type");
        status_ = absolute(config->getCString("status_file"));
        publication_ = absolute(config->getCString("publication_file"));
        cache_ = absolute(config->getCString("cache_root"));
        owner_ = status_.parent_path();
        if (config->has("source_root")) {
            need(config->get("source_root")->type() == wtp::WTSVariant::VT_String, "daily publication source root type");
            owner_ = absolute(config->getCString("source_root"));
        }
        // 此模式的全部日线来自已发布 DSB，避免 loader 再注入另一份原件。
        need(loader_ == nullptr, "daily publication external loader unsupported");
        // 独占目录只容纳本 Reader 的原件投影，源端额外 +/- 缓存不会进入原 Reader。
        const auto directory_guards = parents(cache_, nullptr);
        need(std::filesystem::create_directory(cache_), "daily publication cache root must be new");
        cache_directory_ = std::make_unique<CacheDirectory>(cache_);
        cache_lease_ = std::make_unique<Handle>(CreateFileW((cache_ / "owner.lock").c_str(), GENERIC_READ | GENERIC_WRITE,
            0, nullptr, CREATE_NEW, FILE_ATTRIBUTE_NORMAL, nullptr));
    }
    ~PublishedDaily() {
        close();
    }
    bool close() noexcept {
        const auto current_closed = !current_ || current_->close();
        const auto pending_closed = !pending_ || pending_->close();
        if (!current_closed || !pending_closed) return false;
        current_.reset(); pending_.reset(); cache_lease_.reset();
        return !cache_directory_ || cache_directory_->close();
    }
    wtp::WtDataReader& select(const char* code, Clock::time_point deadline, std::uint32_t cutoff_date,
        const std::function<void(wtp::WTSVariant*)>& validate_paths,
        std::uint64_t session_close_ms=0, std::uint64_t known_cutoff_ms=0) {
        // 两个可选参数为沪深本地YYYYMMDDHHMMSSmmm标签；0保留只读取日期之前日线的合同。
        // 切换或失败新代的删除责任保持在 owner，短时文件占用释放后可继续同次清理。
        if (pending_) {
            need(pending_->close(), "daily publication retirement pending");
            pending_.reset();
            check(deadline);
        }
        auto status = document(read(status_, 128 * 1024, deadline));
        need(text(field(status, "schema")) == "guanheng.qna-producer-status.v1", "daily publication status schema");
        const auto& success = field(status, "last_success");
        const auto identity = text(field(success, "publication_sha256"));
        const auto work = absolute(text(field(success, "work")));
        beneath(work, owner_);
        const auto publication_raw = read(publication_, 32 * 1024 * 1024, deadline);
        need(hash(publication_raw) == identity, "daily publication replacement pending");
        auto publication = document(publication_raw);
        const auto& analysis = field(publication, "analysis");
        std::string signature = identity + "|" + work.string();
        for (const char* key : {"basis_date", "source_revision", "factor_revision"}) {
            const auto value = text(field(success, key));
            need(text(field(analysis, key)) == value, "daily publication revision mismatch");
            signature += "|" + value;
        }
        const auto output_sha = text(field(success, "native_output_sha256"));
        need(text(field(publication, "native_output_sha256")) == output_sha, "daily publication output identity");
        signature += "|" + output_sha;
        const auto basis = text(field(success, "basis_date"));
        need(basis.size() == 10 && basis[4] == '-' && basis[7] == '-', "daily publication basis");
        auto digits = basis; digits.erase(7, 1); digits.erase(4, 1);
        need(std::all_of(digits.begin(), digits.end(), [](char c) { return c >= '0' && c <= '9'; }),
            "daily publication basis digits");
        const auto basis_date=static_cast<std::uint32_t>(std::stoul(digits));
        const auto known=(basis_date==cutoff_date && session_close_ms)
            ? known_millisecond(field(analysis,"known_at")) : 0;
        need(basis_date < cutoff_date || (basis_date == cutoff_date && session_close_ms &&
            session_close_ms<=known && known<=known_cutoff_ms), "daily publication day not closed");
        std::string requested(code);
        if (!requested.empty() && (requested.back()=='+' || requested.back()=='-')) requested.pop_back();
        if (current_ && current_->identity == signature) {
            check(deadline);
            need(current_->covered_codes.count(requested)!=0, "daily publication symbol unavailable");
            return *current_->reader;
        }
        pending_ = std::make_unique<Generation>();
        auto* next = pending_.get();
        next->basis_date=basis_date;
        unsigned char random[12]{};
        need(BCryptGenRandom(nullptr, random, sizeof(random), BCRYPT_USE_SYSTEM_PREFERRED_RNG) >= 0,
            "daily publication generation identity");
        next->directory = cache_ / hash(std::string(reinterpret_cast<char*>(random), sizeof(random))).substr(0, 24);
        need(std::filesystem::create_directory(next->directory), "daily publication new projection");
        next->created_directories.push_back(next->directory);
        auto receipt = document(read(work / "NATIVE-READ.json", 128 * 1024, deadline, next));
        auto request = document(pinned(field(receipt, "request"), *next, deadline));
        auto inputs = document(pinned(field(receipt, "inputs"), *next, deadline));
        need(text(field(publication, "input_sha256")) == text(field(field(receipt, "inputs"), "sha256")) &&
            text(field(publication, "native_output_sha256")) == text(field(success, "native_output_sha256")) &&
            text(field(field(receipt, "output"), "sha256")) == text(field(success, "native_output_sha256")),
            "daily publication native identity");
        pinned(field(receipt, "output"), *next, deadline, 32 * 1024 * 1024);
        for (const char* key : {"source_revision", "factor_revision"})
            need(text(field(inputs, key)) == text(field(success, key)), "daily publication input revision mismatch");
        need(field(request, "basis_date").IsUint(),
            "daily publication basis");
        need(std::all_of(digits.begin(), digits.end(), [](char c) { return c >= '0' && c <= '9'; }) &&
            basis_date == field(request, "basis_date").GetUint(), "daily publication request basis mismatch");
        need(field(request, "adjust_flag").IsUint() && field(request, "adjust_flag").GetUint() == adjust_flag_,
            "daily publication adjusting flag mismatch");
        const auto store = absolute(text(field(request, "path")));
        beneath(store, work);
        const auto factor = absolute(text(field(request, "adjfactor")));
        beneath(factor, work);
        const auto factor_raw = read(factor, 4 * 1024 * 1024, deadline, next);
        need(hash(factor_raw) == text(field(inputs, "factor_file_sha256")),
            "daily publication factor hash");
        stage(next->directory / "adjfactors.json", factor_raw, *next, deadline);
        const auto& securities = field(inputs, "securities");
        need(securities.IsObject(), "daily publication securities");
        for (const auto& symbol : symbols_) {
            if (!securities.HasMember(symbol.first.c_str())) continue;
            const auto& artifact = field(securities, symbol.first.c_str());
            need(field(artifact, "count").IsUint() && field(artifact, "count").GetUint() <= 4096,
                "daily publication bar capacity");
            const auto first = symbol.second.find('.');
            const auto last = symbol.second.rfind('.');
            const auto expected = store / "his/day" / symbol.second.substr(0, first) / (symbol.second.substr(last + 1) + ".dsb");
            need(absolute(text(field(artifact, "path"))) == expected, "daily publication DSB mapping mismatch");
            const auto raw = pinned(artifact, *next, deadline);
            stage(next->directory / "his/day" / symbol.second.substr(0, first) / (symbol.second.substr(last + 1) + ".dsb"),
                raw, *next, deadline);
            next->covered_codes.insert(symbol.second);
        }
        const auto& metadata = field(receipt, "metadata");
        need(metadata.IsArray() && metadata.Size() == 3, "daily publication metadata");
        for (const auto& artifact : metadata.GetArray()) pinned(artifact, *next, deadline);
        // 原 Reader 从这些配置读取原 DSB/因子；不转换 K 线、不计算复权。
        auto* cfg = wtp::WTSVariant::createObject();
        struct Config { wtp::WTSVariant* value; ~Config() { value->release(); } } guard{cfg};
        cfg->append("path", next->directory.string().c_str());
        cfg->append("adjfactor", (next->directory / "adjfactors.json").string().c_str());
        cfg->append("adjust_flag", adjust_flag_);
        validate_paths(cfg);
        next->reader = std::make_unique<wtp::WtDataReader>();
        next->reader->init(cfg, sink_);
        check(deadline);
        next->identity = signature;
        current_.swap(pending_);
        if (pending_) {
            need(pending_->close(), "daily publication retirement pending");
            pending_.reset();
        }
        check(deadline);
        need(current_->covered_codes.count(requested)!=0, "daily publication symbol unavailable");
        return *current_->reader;
    }
    std::uint32_t basis_date() const {
        // 调用者沿daily_mutex读取已准入代际；用于核原DSB日期不越过其声明基准。
        need(current_!=nullptr, "daily publication selection missing");
        return current_->basis_date;
    }
};

} // namespace guanheng
