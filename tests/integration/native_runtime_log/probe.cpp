#include "GuanhengExecution/NativeRuntimeLog.h"
#include <windows.h>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>

namespace fs = std::filesystem;
using guanheng::NativeRuntimeLog;
void require(bool value, const char* reason) {
    if (!value) throw std::runtime_error(reason);
}
std::string read(const fs::path& path) {
    std::ifstream input(path, std::ios::binary);
    return std::string(std::istreambuf_iterator<char>(input), {});
}
void emit(const std::string& text) {
    // 原执行器使用此动态分类；没有dyn_pattern时沿原root回退并转发ILogHandler。
    WTSLogger::log_dyn_raw("executer", "fixture-executer", wtp::LL_INFO, text.c_str());
}
int main(int argc, char** argv) {
    try {
        require(argc == 3, "mode and output required");
        const std::string mode = argv[1];
        const fs::path directory = fs::u8path(argv[2]);
        fs::create_directories(directory);
        NativeRuntimeLog log;
        if (mode == "open-failure") {
            // 真实文件占据预期目录，原sink的打开失败必须保持业务代码继续执行。
            const auto blocked = directory / "blocked";
            std::ofstream(blocked) << "fixture";
            log.start(blocked);
            int business_progress = 0;
            emit("business-before"); ++business_progress;
            WTSLogger::log_raw(wtp::LL_ERROR, "business-after"); ++business_progress;
            const auto status = log.status();
            require(business_progress == 2 && status.initialized && !status.file_opened, "open failure must preserve control flow");
            require(status.attempted_records == 2 && status.write_failures >= 3, "open failure counters");
        } else {
            log.start(directory);
            require(log.status().initialized && log.status().file_opened, "logger ready");
            if (mode == "runtime-failure") {
                log.failure("CTA failure stage=configuration_permission exception=synthetic_business_mismatch");
                require(log.status().first_error_saved, "native exceptions must preserve first error");
                require(read(directory / "native-first-error.log").find("synthetic_business_mismatch") != std::string::npos,
                    "native failure reason must be durable");
            } else if (mode == "first-error-failure") {
                const auto blocked = directory / "native-first-error.log";
                fs::create_directory(blocked);
                WTSLogger::log_raw(wtp::LL_ERROR, "first-copy-unavailable");
                require(!log.status().first_error_saved && log.status().write_failures >= 1,
                    "failed first-error copy must not report success");
                require(read(directory / "native.log").find("first-copy-unavailable") != std::string::npos,
                    "first-error copy failure must preserve ordinary logging");
                fs::remove(blocked);
                WTSLogger::log_raw(wtp::LL_ERROR, "first-copy-recovered");
                require(log.status().first_error_saved, "first-error copy can recover without blocking business");
            } else if (mode == "first-error-concurrent") {
                std::thread first([]{ WTSLogger::log_raw(wtp::LL_ERROR, "concurrent-first-error"); });
                std::thread second([]{ WTSLogger::log_raw(wtp::LL_ERROR, "concurrent-first-error"); });
                first.join(); second.join();
                require(log.status().first_error_saved && log.status().write_failures == 0,
                    "concurrent error callbacks must complete");
            } else if (mode == "first-error-utf8") {
                WTSLogger::log_raw(wtp::LL_ERROR, (std::string(8191, 'a') + u8"中").c_str());
                require(log.status().first_error_saved && log.status().truncated_records == 1,
                    "first-error copy must use the same bounded UTF-8 record");
            } else if (mode == "normal") {
                emit(u8"动态执行器真实日志");
                WTSLogger::log_raw(wtp::LL_DEBUG, "hidden-debug");
                WTSLogger::log_raw(wtp::LL_ERROR, "root-error");
                require(read(directory / "native.log").find("root-error") != std::string::npos,
                    "critical record must be visible before close");
                const auto status = log.status();
                require(status.attempted_records == 2 && status.write_failures == 0, "real callback must receive info and error");
                log.start(directory / "duplicate");
                require(!fs::exists(directory / "duplicate"), "duplicate start must preserve owner identity");
            } else if (mode == "rotation") {
                // 足量真实回调越过四个文件，验证原spdlog的轮转及旧记录淘汰。
                WTSLogger::log_raw(wtp::LL_ERROR, "earliest-source-failure");
                const std::string body(NativeRuntimeLog::message_bytes, 'x');
                for (int round = 0; round < 10; ++round) {
                    for (int index = 0; index < 100; ++index) emit(body);
                    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(2);
                    while (log.status().flushes <= static_cast<std::uint64_t>(round)
                           && std::chrono::steady_clock::now() < deadline) Sleep(5);
                    require(log.status().flushes > static_cast<std::uint64_t>(round), "background rotation flush");
                }
                emit("rotation-tail");
                WTSLogger::log_raw(wtp::LL_ERROR, "later-source-failure");
                require(log.status().attempted_records == 1003 && log.status().write_failures == 0, "rotation callbacks");
            } else if (mode == "utf8") {
                emit(std::string(8191, 'a') + u8"中");
                emit(std::string(8190, 'b') + u8"中文");
                emit(std::string(9000, 'c'));
                const auto status = log.status();
                require(status.attempted_records == 3 && status.truncated_records == 3 && status.write_failures == 0, "utf8 truncation counters");
            } else if (mode == "write-failure") {
                // 实际读句柄允许追加而拒绝rename；真实轮转写路径报错后业务继续。
                const auto held = CreateFileW((directory / "native.log").c_str(), GENERIC_READ,
                    FILE_SHARE_READ | FILE_SHARE_WRITE, nullptr, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
                require(held != INVALID_HANDLE_VALUE, "file sharing fixture");
                const std::string body(NativeRuntimeLog::message_bytes, 'x');
                int business_progress = 0;
                while (business_progress < 180) {
                    emit(body); ++business_progress;
                }
                const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(2);
                while (!log.status().write_failures && std::chrono::steady_clock::now() < deadline) Sleep(5);
                require(log.status().write_failures > 0, "real rotation failure must be counted without throwing");
                CloseHandle(held);
                emit("after-write-failure"); ++business_progress;
                require(log.status().attempted_records == static_cast<std::uint64_t>(business_progress), "write failure control flow");
            } else if (mode == "batch") {
                for (int index = 0; index < 100; ++index) emit("ordinary-" + std::to_string(index));
            } else {
                require(false, "unknown mode");
            }
        }
        const auto before_close = log.status();
        log.close(); log.close();
        WTSLogger::log_raw(wtp::LL_INFO, "after-close-ignored");
        log.start(directory / "after-close");
        require(!fs::exists(directory / "after-close"), "closed object must retain generation");
        require(log.status().attempted_records == before_close.attempted_records, "close must detach handler");
        if (mode == "normal") {
            const auto content = read(directory / "native.log");
            require(content.find(u8"动态执行器真实日志") != std::string::npos, "dynamic executor must persist");
            require(content.find("hidden-debug") == std::string::npos, "info floor");
        }
        if (mode == "rotation") {
            const auto first = read(directory / "native-first-error.log");
            require(first.find("earliest-source-failure") != std::string::npos,
                "first source error must survive ordinary log rotation");
            require(first.find("later-source-failure") == std::string::npos,
                "later errors must preserve the original first error");
            for (const auto* name : {"native.log", "native.1.log", "native.2.log", "native.3.log"})
                require(read(directory / name).find("earliest-source-failure") == std::string::npos,
                    "fixture must actually rotate the original source error away");
        }
        if (mode == "write-failure") require(read(directory / "native.log").find("after-write-failure") != std::string::npos, "write recovery");
        const auto status = log.status();
        if (mode == "batch") {
            std::ifstream input(directory / "native.log");
            for (int index = 0; index < 100; ++index) {
                std::string line;
                const auto text = "] ordinary-" + std::to_string(index);
                require(static_cast<bool>(std::getline(input, line)) && line.size() >= text.size()
                    && line.compare(line.size() - text.size(), text.size(), text) == 0, "ordered drain");
            }
            require(input.peek() == std::char_traits<char>::eof(), "each ordinary log written once");
            require(status.dropped_records == 0 && status.flushes < 10, "ordinary log flush must be coalesced");
        }
        std::cout << "PASS " << mode << " attempted=" << status.attempted_records
            << " failures=" << status.write_failures << " truncated=" << status.truncated_records
            << " dropped=" << status.dropped_records << " flushes=" << status.flushes << '\n';
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
