#pragma once

#include "../WtDtHelper/WtDtHelper.h"
#include "../Includes/WTSStruct.h"
#include <filesystem>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

namespace guanheng
{
class NativePathLease;
class NativeOutputFile;
class NativeFileBusy : public std::runtime_error
{
public: NativeFileBusy():std::runtime_error("历史输入正被写入或替换，请稍后重试"){}
};

class NativeBarBudget : public std::runtime_error
{
public: NativeBarBudget():std::runtime_error("原生历史超过缓存字节预算"){}
};

// 将本地固定盘解析为稳定卷 GUID；后续原生重开须使用返回路径。
std::filesystem::path native_physical_path(const std::filesystem::path& path);

// 本地 NTFS 物理路径：逐层固定祖先及最终文件，拒绝 reparse 路径和并发写入/替换。
// 调用者保持租约至原生路径读取结束；read 从同一句柄读取有界字节。
class NativeFileLease
{
public:
    explicit NativeFileLease(const std::filesystem::path& path);
    ~NativeFileLease();
    NativeFileLease(const NativeFileLease&) = delete;
    NativeFileLease& operator=(const NativeFileLease&) = delete;
    std::string read(std::size_t maximum) const;
private:
    std::unique_ptr<NativePathLease> namespace_;
    void* handle_ = nullptr;
};

// 原 Helper 解压前唯一的 V2 帧及容量准入；期望类型仅限 1m/5m/1d，默认 m1。
std::size_t native_bar_rows(const std::string& bytes,std::size_t maximum,std::size_t raw_budget,std::uint16_t expected_type=21);
std::string native_bar_digest(const std::string& bytes);

// 已验证的同一字节写入私有新文件并保持拒绝写/替换的句柄，原 Helper 同步解码。
// callback 指针仅在原调用期间有效，异常在回调边界截获；返回数组归调用者所有。
// reader 只作为原 ABI 的依赖注入接缝，生产默认使用原 read_dsb_bars。
std::vector<wtp::WTSBarStruct> read_native_bar_bytes(const std::string& bytes,
    std::size_t maximum,std::size_t raw_budget,std::uint16_t expected_type=21,decltype(&read_dsb_bars) reader=read_dsb_bars);

// 受保护父目录中的随机 CREATE_NEW 文件；失败清理仅作用于本次创建句柄。
// 原 bool 仅作信息，成功由原生回读逐字节核对决定；发布限定同父目录。
class NativeBarOutput
{
public:
    NativeBarOutput(const std::filesystem::path& parent,const std::vector<wtp::WTSBarStruct>& bars,
        std::size_t maximum,decltype(&store_bars) writer=store_bars);
    ~NativeBarOutput();
    NativeBarOutput(const NativeBarOutput&) = delete;
    NativeBarOutput& operator=(const NativeBarOutput&) = delete;
    const std::filesystem::path& path() const { return path_; }
    const std::string& bytes() const { return bytes_; }
    void publish_to(const std::filesystem::path& destination);
private:
    std::filesystem::path path_;
    std::string bytes_;
    std::unique_ptr<NativeOutputFile> file_;
};
}
