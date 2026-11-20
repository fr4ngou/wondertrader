#pragma once

#include "WTSTools/WTSLogger.h"
#include "Includes/ILogHandler.h"
#include <spdlog/sinks/basic_file_sink.h>
#include <spdlog/sinks/rotating_file_sink.h>
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <deque>
#include <filesystem>
#include <memory>
#include <mutex>
#include <string>
#include <thread>

namespace guanheng {

struct NativeRuntimeLogStatus {
    bool initialized; // 原WTSLogger是否已初始化；与交易运行是否成功分别表达。
    bool file_opened; // 本代私有轮转文件是否曾成功打开，不代表全部写入成功。
    bool first_error_saved; // 本代首个成功写出的ERROR/FATAL是否已独立刷新，普通日志轮转不删除它。
    std::uint64_t attempted_records; // 进入原日志转发入口的记录数，单位条。
    std::uint64_t write_failures; // 打开、追加或刷新失败次数；只存计数。
    std::uint64_t truncated_records; // 超过单条字节预算而截断的记录数，单位条。
    std::uint64_t dropped_records; // 普通日志因队列已满丢弃的条数，关键日志走同步路径。
    std::uint64_t flushes; // 主动请求刷新轮转文件的次数，包括关键记录和退出刷新。
};

// 复用原WTSLogger转发和spdlog轮转；原生业务日志只进入本代私有目录。
// 普通记录走有界内存队列；WARN及以上在原调用边界写入并刷新。
class NativeRuntimeLog final : private wtp::ILogHandler {
    struct Record {
        spdlog::log_clock::time_point observed_at; // 生产者收到日志的时间，保持原日志时点。
        spdlog::level::level_enum level; // 原日志映射到spdlog的级别。
        std::string message; // 后台线程拥有的有界UTF-8正文。
    };
    std::shared_ptr<spdlog::logger> writer_; // 原线程安全轮转写者；业务生产者与日志线程退出后回收。
    std::filesystem::path first_error_path_; // 当前运行代唯一的首错文件，沿原私有目录保存。
    std::mutex first_error_mutex_; // 只串行首次错误保存；不持有业务或普通日志队列锁。
    std::atomic<bool> first_error_saved_{false}; // 成功刷新后才发布；失败允许后继错误再次尝试。
    std::mutex queue_mutex_; // 只保护队列和关闭标志，文件读写在锁外。
    std::condition_variable available_; // 普通记录到达或退出时通知唯一后台写者。
    std::deque<Record> queue_; // 单进程普通记录队列，达到容量时丢弃并计数。
    std::thread worker_; // 本代普通日志写者，正常退出先排空再回收。
    bool stopping_{false}; // 关闭时停止接收普通记录，已有记录继续写出。
    std::atomic<std::uint64_t> attempted_{0}; // 并发原日志回调的尝试计数。
    std::atomic<std::uint64_t> failures_{0}; // 脱敏固定计数，不保留异常正文。
    std::atomic<std::uint64_t> truncated_{0}; // 有界单行的截断计数。
    std::atomic<std::uint64_t> dropped_{0}; // 普通记录队满次数。
    std::atomic<std::uint64_t> flushes_{0}; // 本日志器主动刷新次数，便于核实批量效果。
    bool started_{false}; // 每对象只准入一次start，保持本代文件与全局handler身份。
    bool initialized_{false}; // 原owner初始化后保持只读，供回调与状态读取。
    bool file_opened_{false}; // 已打开文件的历史事实，close后仍可验真。
    bool finished_{false}; // 原owner的幂等关闭标志。

    void flush() noexcept {
        try { writer_->flush(); } catch (...) { failures_.fetch_add(1, std::memory_order_relaxed); }
        flushes_.fetch_add(1, std::memory_order_relaxed);
    }

    void preserve_first_error(spdlog::log_clock::time_point observed_at,
                              spdlog::level::level_enum level, const char* message, std::size_t size) noexcept {
        if (level < spdlog::level::err || first_error_saved_.load(std::memory_order_acquire)) return;
        try {
            std::lock_guard<std::mutex> lock(first_error_mutex_);
            if (first_error_saved_.load(std::memory_order_relaxed)) return;
            // 本代目录由原执行owner独占。失败重试覆盖未完成文件，体积始终受单条预算约束。
            auto sink = std::make_shared<spdlog::sinks::basic_file_sink_mt>(first_error_path_.u8string(), true);
            bool failed = false;
            spdlog::logger first("native-first-error", sink);
            first.set_pattern("%Y-%m-%dT%H:%M:%S.%e%z [%l] %v");
            first.set_error_handler([&failed](const std::string&) { failed = true; });
            first.log(observed_at, {}, level, spdlog::string_view_t(message, size));
            first.flush();
            if (failed) failures_.fetch_add(1, std::memory_order_relaxed);
            else first_error_saved_.store(true, std::memory_order_release);
        } catch (...) { failures_.fetch_add(1, std::memory_order_relaxed); }
    }

    void write_pending() noexcept {
        std::deque<Record> batch;
        for (;;) {
            {
                std::unique_lock<std::mutex> lock(queue_mutex_);
                available_.wait(lock, [this]{ return stopping_ || !queue_.empty(); });
                if (queue_.empty()) return;
                // 收集同一时间窗的普通日志；退出通知立即结束等待。
                available_.wait_for(lock, std::chrono::milliseconds(100),
                    [this]{ return stopping_ || queue_.size() >= queue_capacity; });
                batch.swap(queue_);
            }
            for (const auto& row : batch) {
                try { writer_->log(row.observed_at, {}, row.level, row.message); }
                catch (...) { failures_.fetch_add(1, std::memory_order_relaxed); }
            }
            flush();
            batch.clear();
        }
    }

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
            const auto observed_at = spdlog::log_clock::now();
            if (mapped >= spdlog::level::warn) {
                preserve_first_error(observed_at, mapped, message, size);
                writer_->log(observed_at, {}, mapped, spdlog::string_view_t(message, size));
                flush();
                return;
            }
            std::lock_guard<std::mutex> lock(queue_mutex_);
            if (stopping_ || queue_.size() == queue_capacity) {
                dropped_.fetch_add(1, std::memory_order_relaxed);
                return;
            }
            queue_.push_back({observed_at, mapped, std::string(message, size)});
            available_.notify_one();
        } catch (...) { failures_.fetch_add(1, std::memory_order_relaxed); }
    }
public:
    static constexpr std::size_t file_bytes = 1024 * 1024; // 单文件预算，单位字节。
    static constexpr std::size_t backup_files = 3; // 数字备份数；加当前文件共4份。
    static constexpr std::size_t message_bytes = 8192; // 每条原始正文的最大UTF-8字节数。
    static constexpr std::size_t queue_capacity = 256; // 两个有界批次合计最多约4 MiB正文。

    NativeRuntimeLog() = default;
    NativeRuntimeLog(const NativeRuntimeLog&) = delete;
    NativeRuntimeLog& operator=(const NativeRuntimeLog&) = delete;
    ~NativeRuntimeLog() { close(); }

    void start(const std::filesystem::path& directory) noexcept {
        if (started_ || finished_) return;
        started_ = true;
        try {
            first_error_path_ = directory / "native-first-error.log";
            auto sink = std::make_shared<spdlog::sinks::rotating_file_sink_mt>(
                (directory / "native.log").u8string(), file_bytes, backup_files);
            writer_ = std::make_shared<spdlog::logger>("native-private", sink);
            writer_->set_level(spdlog::level::info);
            writer_->set_pattern("%Y-%m-%dT%H:%M:%S.%e%z [%l] %v");
            writer_->set_error_handler([this](const std::string&) {
                failures_.fetch_add(1, std::memory_order_relaxed);
            });
            worker_ = std::thread([this]{ write_pending(); });
            file_opened_ = true;
        } catch (...) {
            writer_.reset();
            failures_.fetch_add(1, std::memory_order_relaxed);
        }
        try {
            // 原root仅用于统一等级和转发；动态执行/交易分类沿原root回退进入同一handler。
            WTSLogger::init(R"({"root":{"async":false,"level":"info","sinks":[]}})", false, this);
            initialized_ = true;
        } catch (...) { failures_.fetch_add(1, std::memory_order_relaxed); }
    }
    void request_rejection(const char* message) noexcept { handleLogAppend(wtp::LL_WARN,message); }
    void failure(const char* message) noexcept { handleLogAppend(wtp::LL_ERROR,message); }
    NativeRuntimeLogStatus status() const noexcept {
        return {initialized_, file_opened_, first_error_saved_.load(std::memory_order_acquire),
            attempted_.load(std::memory_order_relaxed),
            failures_.load(std::memory_order_relaxed), truncated_.load(std::memory_order_relaxed),
            dropped_.load(std::memory_order_relaxed), flushes_.load(std::memory_order_relaxed)};
    }
    void close() noexcept {
        if (finished_) return;
        finished_ = true;
        if (initialized_) {
            try { WTSLogger::registerHandler(nullptr); WTSLogger::stop(); }
            catch (...) { failures_.fetch_add(1, std::memory_order_relaxed); }
        }
        if (writer_) {
            {
                std::lock_guard<std::mutex> lock(queue_mutex_);
                stopping_ = true;
            }
            available_.notify_one();
            if (worker_.joinable()) worker_.join();
            flush();
            writer_.reset();
        }
    }
};
}
