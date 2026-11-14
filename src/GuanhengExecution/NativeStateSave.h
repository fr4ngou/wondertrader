#pragma once

#include <Windows.h>

#include <filesystem>
#include <map>
#include <mutex>
#include <string>
#include <string_view>
#include <system_error>
#include <utility>

namespace guanheng {

class NativeStateSave {
public:
    static NativeStateSave& instance() {
        static NativeStateSave state;
        return state;
    }

    // 受管 CTA 在工作线程启动前固定模式，正常停止后随进程释放。
    void enable() noexcept { enabled_ = true; }
    bool enabled() const noexcept { return enabled_; }

    bool healthy() {
        std::lock_guard<std::mutex> lock(mutex_);
        for (const auto& entry : states_)
            if (entry.second.error) return false;
        return true;
    }

    std::error_code save(const std::filesystem::path& target, std::string_view bytes) {
        std::lock_guard<std::mutex> lock(mutex_);
        auto& state = states_[target];
        if (!state.error && state.committed && state.bytes == bytes
            && same_file(state.identity, file_identity(target)))
            return {};

        // 替换前准备内存副本，只有原子发布成功才更新已提交身份。
        std::string next(bytes);
        auto temporary = target;
        temporary += L".guanheng-pending";
        // 上一代异常退出可留下未发布的临时文件，由当前唯一写入者清理。
        if (!DeleteFileW(temporary.c_str()) && GetLastError() != ERROR_FILE_NOT_FOUND)
            return state.error = last_error();
        const auto file = CreateFileW(temporary.c_str(), GENERIC_WRITE,
            0, nullptr, CREATE_NEW, FILE_ATTRIBUTE_NORMAL, nullptr);
        if (file == INVALID_HANDLE_VALUE) return state.error = last_error();

        BY_HANDLE_FILE_INFORMATION identity{};
        DWORD written = 0;
        DWORD failure = ERROR_SUCCESS;
        if (bytes.size() > MAXDWORD) failure = ERROR_FILE_TOO_LARGE;
        else if (!WriteFile(file, bytes.data(), static_cast<DWORD>(bytes.size()), &written, nullptr))
            failure = GetLastError();
        else if (written != bytes.size()) failure = ERROR_WRITE_FAULT;
        else if (!FlushFileBuffers(file)) failure = GetLastError();

        if (!CloseHandle(file) && !failure) failure = GetLastError();
        if (!failure) {
            // Windows 在写句柄关闭后才保证最后写入时间更新。
            identity = file_identity(temporary);
            if (!MoveFileExW(temporary.c_str(), target.c_str(), MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH))
                failure = GetLastError();
        }
        if (failure) {
            DeleteFileW(temporary.c_str());
            return state.error = std::error_code(failure, std::system_category());
        }

        state.bytes = std::move(next);
        state.identity = identity;
        state.committed = true;
        return state.error = {};
    }

private:
    struct State {
        std::string bytes; // 本代最近一次成功发布的完整原生 JSON。
        BY_HANDLE_FILE_INFORMATION identity{}; // 同一已提交文件的卷、文件号、长度与最后写入时间。
        bool committed = false; // 当前代至少成功发布过一次。
        std::error_code error; // 上次写入失败的系统错误，原保存入口下次重试。
    };

    static std::error_code last_error() {
        return {static_cast<int>(GetLastError()), std::system_category()};
    }

    static BY_HANDLE_FILE_INFORMATION file_identity(const std::filesystem::path& path) {
        BY_HANDLE_FILE_INFORMATION result{};
        const auto file = CreateFileW(path.c_str(), FILE_READ_ATTRIBUTES,
            FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, nullptr, OPEN_EXISTING,
            FILE_FLAG_OPEN_REPARSE_POINT, nullptr);
        if (file != INVALID_HANDLE_VALUE) {
            if (!GetFileInformationByHandle(file, &result)
                || (result.dwFileAttributes & (FILE_ATTRIBUTE_REPARSE_POINT | FILE_ATTRIBUTE_DIRECTORY)))
                result = {};
            CloseHandle(file);
        }
        return result;
    }

    static bool same_file(const BY_HANDLE_FILE_INFORMATION& a, const BY_HANDLE_FILE_INFORMATION& b) {
        return (a.nFileIndexHigh || a.nFileIndexLow)
            && a.dwVolumeSerialNumber == b.dwVolumeSerialNumber
            && a.nFileIndexHigh == b.nFileIndexHigh && a.nFileIndexLow == b.nFileIndexLow
            && a.nFileSizeHigh == b.nFileSizeHigh && a.nFileSizeLow == b.nFileSizeLow
            && CompareFileTime(&a.ftLastWriteTime, &b.ftLastWriteTime) == 0;
    }

    bool enabled_ = false; // 启动期写一次，工作线程只读。
    std::mutex mutex_; // 串行化已提交记录和同路径原子替换。
    std::map<std::filesystem::path, State> states_; // 每个成熟保存路径最多一份正文。
};

} // namespace guanheng
