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
            if (mode == "normal") {
                emit(u8"动态执行器真实日志");
                WTSLogger::log_raw(wtp::LL_DEBUG, "hidden-debug");
                WTSLogger::log_raw(wtp::LL_ERROR, "root-error");
                const auto status = log.status();
                require(status.attempted_records == 2 && status.write_failures == 0, "real callback must receive info and error");
                log.start(directory / "duplicate");
                require(!fs::exists(directory / "duplicate"), "duplicate start must preserve owner identity");
            } else if (mode == "rotation") {
                // 足量真实回调越过四个文件，验证原spdlog的轮转及旧记录淘汰。
                const std::string body(NativeRuntimeLog::message_bytes, 'x');
                for (int index = 0; index < 1000; ++index) emit(body);
                emit("rotation-tail");
                require(log.status().attempted_records == 1001 && log.status().write_failures == 0, "rotation callbacks");
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
                while (!log.status().write_failures && business_progress < 200) {
                    emit(body); ++business_progress;
                }
                require(log.status().write_failures > 0 && business_progress < 200, "real rotation failure must be counted without throwing");
                CloseHandle(held);
                emit("after-write-failure"); ++business_progress;
                require(log.status().attempted_records == static_cast<std::uint64_t>(business_progress), "write failure control flow");
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
        if (mode == "write-failure") require(read(directory / "native.log").find("after-write-failure") != std::string::npos, "write recovery");
        const auto status = log.status();
        std::cout << "PASS " << mode << " attempted=" << status.attempted_records
            << " failures=" << status.write_failures << " truncated=" << status.truncated_records << '\n';
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
