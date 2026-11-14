#include "GuanhengExecution/NativeStateSave.h"

#include <fstream>
#include <iostream>
#include <iterator>
#include <stdexcept>

namespace fs = std::filesystem;

static void check(bool ok, const char* message) {
    if (!ok) throw std::runtime_error(message);
}

static std::string read(const fs::path& path) {
    std::ifstream stream(path, std::ios::binary);
    return {std::istreambuf_iterator<char>(stream), std::istreambuf_iterator<char>()};
}

int main(int argc, char** argv) {
    try {
        check(argc == 2, "pass a fresh directory");
        const auto root = fs::absolute(argv[1]);
        check(fs::create_directory(root), "create isolated directory");
        const auto target = root / "state.json";
        auto& writer = guanheng::NativeStateSave::instance();
        check(!writer.enabled() && writer.healthy(), "default is native");
        writer.enable();
        check(!writer.save(target, "old"), "first save");

        // 持有不许删除的读句柄。相同内容应跳过，变化内容应原子替换失败。
        const auto file = CreateFileW(target.c_str(), GENERIC_READ, FILE_SHARE_READ,
            nullptr, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
        check(file != INVALID_HANDLE_VALUE, "hold old target");
        const auto unchanged = writer.save(target, "old");
        const auto changed = writer.save(target, "new");
        CloseHandle(file);
        check(!unchanged, "same bytes skip replace");
        check(changed && !writer.healthy() && read(target) == "old", "failure preserves old file");
        check(!fs::exists(root / "state.json.guanheng-pending"), "failure cleans temporary file");
        check(!writer.save(target, "new") && writer.healthy() && read(target) == "new", "retry commits");
        fs::remove(target);
        check(!writer.save(target, "new") && read(target) == "new", "missing file is recreated");

        const auto replacement = root / "replacement.json";
        std::ofstream(replacement, std::ios::binary) << "bad";
        fs::last_write_time(replacement, fs::last_write_time(target));
        check(MoveFileExW(replacement.c_str(), target.c_str(), MOVEFILE_REPLACE_EXISTING) != 0, "external replace");
        check(!writer.save(target, "new") && read(target) == "new", "new file identity is detected");

        check(fs::remove(target) && fs::remove(root), "clean isolated files");
        std::cout << "Native state save regression passed\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
