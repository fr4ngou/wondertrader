#pragma once

#include "WTSTools/WTSLogger.h"
#include "Includes/ILogHandler.h"
#include <spdlog/sinks/rotating_file_sink.h>
#include <atomic>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <memory>

namespace guanheng {

struct NativeRuntimeLogStatus {
    bool initialized; // 原WTSLogger是否已初始化；与交易运行是否成功分别表达。
    bool file_opened; // 本代私有轮转文件是否曾成功打开，不代表全部写入成功。
    std::uint64_t attempted_records; // 进入原日志转发入口的记录数，单位条。
    std::uint64_t write_failures; // 打开、追加或刷新失败次数；只存计数。
    std::uint64_t truncated_records; // 超过单条字节预算而截断的记录数，单位条。
};

// 复用原WTSLogger转发和spdlog轮转；原生业务日志只进入本代私有目录。
// 业务生产者全部关闭后由原owner调用close，不新增线程、队列或交易行为。
class NativeRuntimeLog final : private wtp::ILogHandler {
    std::shared_ptr<spdlog::logger> writer_; // 原生同步轮转写者，不注册额外全局logger。
    std::atomic<std::uint64_t> attempted_{0}; // 并发原日志回调的尝试计数。
    std::atomic<std::uint64_t> failures_{0}; // 脱敏固定计数，不保留异常正文。
    std::atomic<std::uint64_t> truncated_{0}; // 有界单行的截断计数。
    bool started_{false}; // 每对象只准入一次start，保持本代文件与全局handler身份。
    bool initialized_{false}; // 原owner初始化后保持只读，供回调与状态读取。
    bool file_opened_{false}; // 已打开文件的历史事实，close后仍可验真。
    bool finished_{false}; // 原owner的幂等关闭标志。

    void handleLogAppend(wtp::WTSLogLevel level, const char* message) override {
        attempted_.fetch_add(1, std::memory_order_relaxed);
        if (!writer_ || !message) { failures_.fetch_add(1, std::memory_order_relaxed); return; }
        try {
            auto size = strnlen_s(message, message_bytes + 1);
            if (size > message_bytes) {
                size = message_bytes;
                // UTF-8后续字节不作为记录末尾，避免截断后的中文无法读取。
                while (size && (static_cast<unsigned char>(message[size]) & 0xc0) == 0x80) --size;
                truncated_.fetch_add(1, std::memory_order_relaxed);
            }
            const auto mapped = level == wtp::LL_DEBUG ? spdlog::level::debug
                : level == wtp::LL_WARN ? spdlog::level::warn
                : level == wtp::LL_ERROR ? spdlog::level::err
                : level == wtp::LL_FATAL ? spdlog::level::critical : spdlog::level::info;
            writer_->log(mapped, "{}", spdlog::string_view_t(message, size));
        } catch (...) { failures_.fetch_add(1, std::memory_order_relaxed); }
    }
public:
    static constexpr std::size_t file_bytes = 1024 * 1024; // 单文件预算，单位字节。
    static constexpr std::size_t backup_files = 3; // 数字备份数；加当前文件共4份。
    static constexpr std::size_t message_bytes = 8192; // 每条原始正文的最大UTF-8字节数。

    NativeRuntimeLog() = default;
    NativeRuntimeLog(const NativeRuntimeLog&) = delete;
    NativeRuntimeLog& operator=(const NativeRuntimeLog&) = delete;
    ~NativeRuntimeLog() { close(); }

    void start(const std::filesystem::path& directory) noexcept {
        if (started_ || finished_) return;
        started_ = true;
        try {
            auto sink = std::make_shared<spdlog::sinks::rotating_file_sink_mt>(
                (directory / "native.log").u8string(), file_bytes, backup_files);
            writer_ = std::make_shared<spdlog::logger>("native-private", sink);
            writer_->set_level(spdlog::level::info);
            writer_->set_pattern("%Y-%m-%dT%H:%M:%S.%e%z [%l] %v");
            writer_->flush_on(spdlog::level::info);
            writer_->set_error_handler([this](const std::string&) {
                failures_.fetch_add(1, std::memory_order_relaxed);
            });
            file_opened_ = true;
        } catch (...) { failures_.fetch_add(1, std::memory_order_relaxed); }
        try {
            // 原root仅用于统一等级和转发；动态执行/交易分类沿原root回退进入同一handler。
            WTSLogger::init(R"({"root":{"async":false,"level":"info","sinks":[]}})", false, this);
            initialized_ = true;
        } catch (...) { failures_.fetch_add(1, std::memory_order_relaxed); }
    }
    NativeRuntimeLogStatus status() const noexcept {
        return {initialized_, file_opened_, attempted_.load(std::memory_order_relaxed),
            failures_.load(std::memory_order_relaxed), truncated_.load(std::memory_order_relaxed)};
    }
    void close() noexcept {
        if (finished_) return;
        finished_ = true;
        if (initialized_) {
            try { WTSLogger::registerHandler(nullptr); WTSLogger::stop(); }
            catch (...) { failures_.fetch_add(1, std::memory_order_relaxed); }
        }
        if (writer_) {
            try { writer_->flush(); } catch (...) { failures_.fetch_add(1, std::memory_order_relaxed); }
            writer_.reset();
        }
    }
};
}
