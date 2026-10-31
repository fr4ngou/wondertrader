#include "NativeBarFile.h"
#include "../WtDataStorage/DataDefine.h"
#include "../WTSUtils/zstdlib/zstd.h"
#include <cstring>
#include <algorithm>
#include <iomanip>
#include <limits>
#include <sstream>
#ifdef _WIN32
#include <windows.h>
#include <bcrypt.h>
#endif

namespace guanheng
{
#ifdef _WIN32
namespace
{
class Handle
{
public:
    explicit Handle(HANDLE value=INVALID_HANDLE_VALUE):value_(value){}
    ~Handle(){if(value_!=INVALID_HANDLE_VALUE)CloseHandle(value_);}
    Handle(const Handle&)=delete;
    Handle& operator=(const Handle&)=delete;
    HANDLE get() const {return value_;}
private: HANDLE value_;
};
using HandlePtr=std::unique_ptr<Handle>;
HandlePtr checked_handle(HANDLE value)
{
    if(value==INVALID_HANDLE_VALUE)
    {
        const auto error=GetLastError();
        if(error==ERROR_SHARING_VIOLATION || error==ERROR_LOCK_VIOLATION)throw NativeFileBusy();
        throw std::runtime_error("历史文件或路径租约取得失败");
    }
    // 分配失败时也由此处关闭已经取得的 Windows 资源。
    try{return std::make_unique<Handle>(value);}catch(...){CloseHandle(value);throw;}
}
void validate_kind(HANDLE handle,bool directory)
{
    BY_HANDLE_FILE_INFORMATION info{};
    if(!GetFileInformationByHandle(handle,&info) || GetFileType(handle)!=FILE_TYPE_DISK
        || (info.dwFileAttributes&FILE_ATTRIBUTE_REPARSE_POINT)
        || bool(info.dwFileAttributes&FILE_ATTRIBUTE_DIRECTORY)!=directory)
        throw std::runtime_error("历史仅支持本地 NTFS 物理路径，拒绝 reparse 或错误文件类型");
}
std::string read_handle(HANDLE handle,std::size_t maximum)
{
    LARGE_INTEGER size{},zero{};
    if(!GetFileSizeEx(handle,&size) || size.QuadPart<0 || std::uint64_t(size.QuadPart)>maximum
        || size.QuadPart>268435456 || !SetFilePointerEx(handle,zero,nullptr,FILE_BEGIN))
        throw std::runtime_error("历史输入大小超过预算或无法定位");
    std::string bytes(static_cast<std::size_t>(size.QuadPart),'\0');DWORD read=0;
    if(!ReadFile(handle,bytes.data(),static_cast<DWORD>(bytes.size()),&read,nullptr) || read!=bytes.size())
        throw std::runtime_error("历史输入读取失败");
    return bytes;
}
std::filesystem::path random_file(const std::filesystem::path& parent)
{
    unsigned char random[16];
    if(BCryptGenRandom(nullptr,random,sizeof random,BCRYPT_USE_SYSTEM_PREFERRED_RNG)<0)
        throw std::runtime_error("历史临时文件身份生成失败");
    std::ostringstream name;name<<".guanheng-bars-"<<std::hex<<std::setfill('0');
    for(auto byte:random)name<<std::setw(2)<<unsigned(byte);
    return parent/(name.str()+".dsb");
}
}

std::filesystem::path native_physical_path(const std::filesystem::path& input)
{
    auto name=std::filesystem::absolute(input).lexically_normal().wstring();
    std::replace(name.begin(),name.end(),L'/',L'\\');
    std::wstring root,tail;
    if(name.rfind(L"\\\\?\\Volume{",0)==0)
    {
        const auto end=name.find(L"}\\");
        if(end==std::wstring::npos)throw std::runtime_error("历史卷路径无效");
        root=name.substr(0,end+2);tail=name.substr(end+2);
    }
    else
    {
        if(name.size()<3 || name[1]!=L':' || name[2]!=L'\\')
            throw std::runtime_error("历史路径须为本地固定驱动器或卷 GUID 绝对路径");
        root=name.substr(0,3);tail=name.substr(3);
        if(GetDriveTypeW(root.c_str())!=DRIVE_FIXED)
            throw std::runtime_error("历史路径仅支持本地固定 NTFS 卷");
        wchar_t device[32768]{};
        if(!QueryDosDeviceW(root.substr(0,2).c_str(),device,32768)
            || std::wstring(device).rfind(L"\\Device\\HarddiskVolume",0)!=0)
            throw std::runtime_error("历史路径不支持映射盘或 DOS 别名");
    }
    if(tail.find(L':')!=std::wstring::npos)throw std::runtime_error("历史路径不支持命名流");
    auto handle=checked_handle(CreateFileW(root.c_str(),GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE,
        nullptr,OPEN_EXISTING,FILE_FLAG_BACKUP_SEMANTICS|FILE_FLAG_OPEN_REPARSE_POINT,nullptr));
    validate_kind(handle->get(),true);
    wchar_t volume[32768]{},filesystem[32]{};
    const auto length=GetFinalPathNameByHandleW(handle->get(),volume,32768,VOLUME_NAME_GUID);
    if(!length || length>=32768 || !GetVolumeInformationByHandleW(handle->get(),nullptr,0,nullptr,nullptr,nullptr,filesystem,32)
        || _wcsicmp(filesystem,L"NTFS"))throw std::runtime_error("历史路径无法绑定本地 NTFS 卷身份");
    // 后续原 Helper/Reader 实际使用卷 GUID；盘符映射变化无法改变已选卷。
    return std::filesystem::path(std::wstring(volume,length))/tail;
}

class NativePathLease
{
public:
    explicit NativePathLease(const std::filesystem::path& parent)
        :parent_(native_physical_path(parent))
    {
        const auto name=parent_.wstring();const auto end=name.find(L"}\\");
        auto current=std::filesystem::path(name.substr(0,end+2));paths_.push_back(current);
        for(const auto& part:std::filesystem::path(name.substr(end+2)))
        {current/=part;paths_.push_back(current);}
        // 从根向下逐层 pin；OPEN_REPARSE_POINT 只用于本层，之前各层已拒绝写/删。
        // FILE_READ_ATTRIBUTES 不参与所需共享约束，必须使用真实 GENERIC_READ。
        for(const auto& path:paths_)handles_.push_back(open(path,FILE_SHARE_READ));
    }
    const std::filesystem::path& parent() const {return parent_;}
    void permit_same_parent_publish()
    {
        // 仅在该父目录已有本次不可删除文件后调用。祖先子目录与末级文件均固定，
        // NTFS 不能把非空物理目录转为 junction；deny-delete 仍防止祖先重命名。
        // rename 需临时打开父目录写访问，保留 share_READ 会误阻断合法发布。
        std::vector<HandlePtr> next;
        for(const auto& path:paths_)next.push_back(open(path,FILE_SHARE_READ|FILE_SHARE_WRITE));
        handles_.swap(next);
    }
private:
    static HandlePtr open(const std::filesystem::path& path,DWORD share)
    {
        auto handle=checked_handle(CreateFileW(path.c_str(),GENERIC_READ,share,nullptr,OPEN_EXISTING,
            FILE_FLAG_BACKUP_SEMANTICS|FILE_FLAG_OPEN_REPARSE_POINT,nullptr));
        validate_kind(handle->get(),true);return handle;
    }
    std::filesystem::path parent_;
    std::vector<std::filesystem::path> paths_;
    std::vector<HandlePtr> handles_;
};

namespace
{
class CreatedFile
{
public:
    CreatedFile(const std::filesystem::path& parent,bool output):namespace_(parent),path_(random_file(namespace_.parent()))
    {
        // 原 Helper 写入阶段需要 WRITE 共享；创建者只保留 READ|DELETE，
        // 后续可叠加拒写读句柄，整个过程从不释放本次文件身份。
        handle_=checked_handle(CreateFileW(path_.c_str(),GENERIC_READ|DELETE|(output?0:GENERIC_WRITE),
            output?(FILE_SHARE_READ|FILE_SHARE_WRITE):FILE_SHARE_READ,nullptr,CREATE_NEW,
            FILE_ATTRIBUTE_TEMPORARY|FILE_FLAG_OPEN_REPARSE_POINT,nullptr));
    }
    ~CreatedFile()
    {
        if(!published_ && handle_)
        {
            FILE_DISPOSITION_INFO info{TRUE};
            if(!SetFileInformationByHandle(handle_->get(),FileDispositionInfo,&info,sizeof info))
                OutputDebugStringW(L"Guanheng: owned history file cleanup failed; no path deletion attempted\n");
        }
        handle_.reset(); // 先结束文件/删除，再释放祖先；不按可变化路径递归删除。
    }
    const std::filesystem::path& path() const {return path_;}
    HANDLE handle() const {return handle_->get();}
    void finish()
    {
        FILE_DISPOSITION_INFO info{TRUE};
        if(!SetFileInformationByHandle(handle(),FileDispositionInfo,&info,sizeof info))
            throw std::runtime_error("本次私有历史文件清理失败");
        handle_.reset();
    }
    void publish(const std::filesystem::path& destination)
    {
        const auto absolute=native_physical_path(destination);
        if(absolute.parent_path()!=namespace_.parent() || absolute.filename().wstring().find(L':')!=std::wstring::npos)
            throw std::runtime_error("历史输出只能在已固定的同一父目录内发布");
        namespace_.permit_same_parent_publish();
        const auto name=absolute.wstring();const auto length=name.size()*sizeof(wchar_t);
        std::vector<unsigned char> storage(sizeof(FILE_RENAME_INFO)+length);
        auto* rename=reinterpret_cast<FILE_RENAME_INFO*>(storage.data());
        rename->ReplaceIfExists=TRUE;rename->RootDirectory=nullptr;
        rename->FileNameLength=static_cast<DWORD>(length);std::memcpy(rename->FileName,name.data(),length);
        if(!SetFileInformationByHandle(handle(),FileRenameInfo,rename,static_cast<DWORD>(storage.size())))
        {
            const auto error=GetLastError();
            if(error==ERROR_SHARING_VIOLATION || error==ERROR_LOCK_VIOLATION)throw NativeFileBusy();
            if(error==ERROR_ACCESS_DENIED)
            {
                // Windows 将目标共享冲突也映射为5；仅实际 DELETE 探测32/33可重试。
                auto target=CreateFileW(absolute.c_str(),DELETE,FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,
                    nullptr,OPEN_EXISTING,FILE_FLAG_OPEN_REPARSE_POINT,nullptr);
                if(target==INVALID_HANDLE_VALUE)
                {
                    const auto reason=GetLastError();
                    if(reason==ERROR_SHARING_VIOLATION || reason==ERROR_LOCK_VIOLATION)throw NativeFileBusy();
                }
                else CloseHandle(target);
            }
            throw std::runtime_error("已核验历史输出发布失败");
        }
        published_=true; // 已发布文件明确退出临时删除所有权。
    }
private:
    NativePathLease namespace_;
    std::filesystem::path path_;
    HandlePtr handle_;
    bool published_=false;
};
class Snapshot
{
public:
    explicit Snapshot(const std::string& bytes):file_(std::filesystem::temp_directory_path(),false)
    {
        DWORD written=0;
        if(!WriteFile(file_.handle(),bytes.data(),static_cast<DWORD>(bytes.size()),&written,nullptr)
            || written!=bytes.size() || !FlushFileBuffers(file_.handle()))
            throw std::runtime_error("历史私有快照写入失败");
    }
    const std::filesystem::path& path() const {return file_.path();}
    void finish(){file_.finish();}
private: CreatedFile file_;
};
}
class NativeOutputFile
{
public:
    explicit NativeOutputFile(const std::filesystem::path& parent):file_(parent,true){}
    const std::filesystem::path& path() const {return file_.path();}
    void seal()
    {
        // 原 writer 同步返回后先刷盘，再叠加拒写句柄。身份句柄始终拒绝 DELETE；
        // 第二句柄允许创建者自身 DELETE，二者共同拒绝外部写入和替换。
        {
            auto flush=checked_handle(CreateFileW(path().c_str(),GENERIC_WRITE,FILE_SHARE_READ|FILE_SHARE_DELETE,
                nullptr,OPEN_EXISTING,FILE_FLAG_OPEN_REPARSE_POINT,nullptr));
            if(!FlushFileBuffers(flush->get()))throw std::runtime_error("历史输出刷盘失败");
        }
        locked_=checked_handle(CreateFileW(path().c_str(),GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_DELETE,
            nullptr,OPEN_EXISTING,FILE_FLAG_OPEN_REPARSE_POINT,nullptr));
    }
    std::string read(std::size_t maximum) const {return read_handle(file_.handle(),maximum);}
    void publish(const std::filesystem::path& destination){file_.publish(destination);}
private:
    CreatedFile file_;
    HandlePtr locked_;
};
#else
std::filesystem::path native_physical_path(const std::filesystem::path&)
{throw std::runtime_error("历史文件保护仅取得 Windows NTFS 资格");}
class NativePathLease {};
class NativeOutputFile {};
namespace
{
class Snapshot
{
public:
    explicit Snapshot(const std::string&){throw std::runtime_error("历史文件保护仅取得 Windows NTFS 资格");}
    std::filesystem::path path() const {return {};}
    void finish(){}
};
}
#endif

namespace
{
struct Collection
{
    std::size_t expected=0;
    unsigned counts=0,finals=0;
    bool failed=false;
    std::vector<wtp::WTSBarStruct> bars;
};
thread_local Collection* collecting=nullptr;
class CollectionScope
{
public:
    explicit CollectionScope(Collection& next):previous_(collecting){collecting=&next;}
    ~CollectionScope(){collecting=previous_;}
private: Collection* previous_;
};
void PORTER_FLAG count_callback(WtUInt32 count) noexcept
{
    auto* state=collecting;if(!state)return;
    if(++state->counts!=1 || count!=state->expected || !state->bars.empty())state->failed=true;
}
void PORTER_FLAG bars_callback(wtp::WTSBarStruct* bars,WtUInt32 count,bool last) noexcept
{
    auto* state=collecting;if(!state)return;
    if(state->failed || state->counts!=1 || state->finals || !bars || !count
        || count>state->expected-state->bars.size()) {state->failed=true;return;}
    try
    {
        state->bars.insert(state->bars.end(),bars,bars+count);
        if(last)++state->finals;
    }
    catch(...){state->failed=true;}
}
}

NativeFileLease::NativeFileLease(const std::filesystem::path& path)
{
#ifdef _WIN32
    const auto absolute=native_physical_path(path);
    if(absolute.filename().wstring().find(L':')!=std::wstring::npos)
        throw std::runtime_error("历史输入不支持流或设备别名");
    namespace_=std::make_unique<NativePathLease>(absolute.parent_path());
    auto value=checked_handle(CreateFileW(absolute.c_str(),GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,
        FILE_FLAG_OPEN_REPARSE_POINT,nullptr));
    validate_kind(value->get(),false);
    // 保留普通句柄字段，析构顺序明确先文件、后全部祖先。
    HANDLE duplicate=INVALID_HANDLE_VALUE;
    if(!DuplicateHandle(GetCurrentProcess(),value->get(),GetCurrentProcess(),&duplicate,0,FALSE,DUPLICATE_SAME_ACCESS))
        throw std::runtime_error("历史文件租约保存失败");
    handle_=duplicate;
#else
    throw std::runtime_error("历史文件保护仅取得 Windows NTFS 资格");
#endif
}
NativeFileLease::~NativeFileLease()
{
#ifdef _WIN32
    if(handle_)CloseHandle(handle_);
#endif
}
std::string NativeFileLease::read(std::size_t maximum) const
{
#ifdef _WIN32
    return read_handle(handle_,maximum);
#else
    throw std::runtime_error("历史文件保护仅取得 Windows NTFS 资格");
#endif
}
std::size_t native_bar_rows(const std::string& bytes,std::size_t maximum,std::size_t raw_budget,std::uint16_t expected_type)
{
    if(!maximum || maximum>1000000 || bytes.size()>maximum*sizeof(wtp::WTSBarStruct)+65536
        || bytes.size()<=sizeof(BlockHeaderV2))throw std::runtime_error("原生分钟文件超过预算或头缺失");
    BlockHeaderV2 header{};std::memcpy(&header,bytes.data(),sizeof header);
    const auto compressed=bytes.size()-sizeof header;
    if(std::memcmp(header._blk_flag,BLK_FLAG,FLAG_SIZE) || header._type!=expected_type
        || (expected_type!=BT_HIS_Minute1 && expected_type!=BT_HIS_Minute5 && expected_type!=BT_HIS_Day)
        || header._version!=BLOCK_VERSION_CMP_V2 || header._size!=compressed)
        throw std::runtime_error("原生分钟头、版本或长度不合格");
    const auto raw=ZSTD_getFrameContentSize(bytes.data()+sizeof header,compressed);
    if(raw==ZSTD_CONTENTSIZE_UNKNOWN || raw==ZSTD_CONTENTSIZE_ERROR || !raw
        || raw%sizeof(wtp::WTSBarStruct) || raw/sizeof(wtp::WTSBarStruct)>maximum
        || ZSTD_findFrameCompressedSize(bytes.data()+sizeof header,compressed)!=compressed)
        throw std::runtime_error("原生分钟解压大小或帧边界不合格");
    if(raw>raw_budget)throw NativeBarBudget();
    return static_cast<std::size_t>(raw/sizeof(wtp::WTSBarStruct));
}
std::string native_bar_digest(const std::string& data)
{
#ifdef _WIN32
    BCRYPT_ALG_HANDLE algorithm=nullptr;BCRYPT_HASH_HANDLE hash=nullptr;
    if(BCryptOpenAlgorithmProvider(&algorithm,BCRYPT_SHA256_ALGORITHM,nullptr,0)<0)
        throw std::runtime_error("SHA-256 算法不可用");
    unsigned char digest[32];auto status=BCryptCreateHash(algorithm,&hash,nullptr,0,nullptr,0,0);
    if(status>=0)status=BCryptHashData(hash,reinterpret_cast<PUCHAR>(const_cast<char*>(data.data())),static_cast<ULONG>(data.size()),0);
    if(status>=0)status=BCryptFinishHash(hash,digest,sizeof digest,0);
    if(hash)BCryptDestroyHash(hash);BCryptCloseAlgorithmProvider(algorithm,0);
    if(status<0)throw std::runtime_error("SHA-256 计算失败");
    std::ostringstream out;out<<std::hex<<std::setfill('0');for(auto byte:digest)out<<std::setw(2)<<unsigned(byte);
    return out.str();
#else
    throw std::runtime_error("历史摘要仅取得 Windows 资格");
#endif
}
std::vector<wtp::WTSBarStruct> read_native_bar_bytes(const std::string& bytes,
    std::size_t maximum,std::size_t raw_budget,std::uint16_t expected_type,decltype(&read_dsb_bars) reader)
{
    if(!reader)throw std::invalid_argument("原 Helper 读取入口缺失");
    Collection state;state.expected=native_bar_rows(bytes,maximum,raw_budget,expected_type);
    state.bars.reserve(state.expected);Snapshot snapshot(bytes);CollectionScope scope(state);
    const auto count=reader(snapshot.path().string().c_str(),bars_callback,count_callback,nullptr);
    if(state.failed || state.counts!=1 || state.finals!=1 || count!=state.expected || state.bars.size()!=state.expected)
        throw std::runtime_error("原 Helper 历史回调条数、终态或返回值不一致");
    snapshot.finish();
    return std::move(state.bars);
}
NativeBarOutput::NativeBarOutput(const std::filesystem::path& parent,
    const std::vector<wtp::WTSBarStruct>& bars,std::size_t maximum,decltype(&store_bars) writer)
{
    if(!writer || !maximum || maximum>1000000 || bars.empty() || bars.size()>maximum || !bars.data())
        throw std::runtime_error("原 Helper 写入数量或预算非法");
#ifdef _WIN32
    file_=std::make_unique<NativeOutputFile>(parent);path_=file_->path();
    writer(path_.string().c_str(),const_cast<wtp::WTSBarStruct*>(bars.data()),static_cast<int>(bars.size()),"m1",nullptr);
    file_->seal();bytes_=file_->read(maximum*sizeof(wtp::WTSBarStruct)+65536);
    auto readback=read_native_bar_bytes(bytes_,maximum,maximum*sizeof(wtp::WTSBarStruct));
    if(readback.size()!=bars.size() || std::memcmp(readback.data(),bars.data(),bars.size()*sizeof(wtp::WTSBarStruct)))
        throw std::runtime_error("原 Helper 分钟写入回读不一致");
#else
    throw std::runtime_error("历史文件保护仅取得 Windows NTFS 资格");
#endif
}
void NativeBarOutput::publish_to(const std::filesystem::path& destination)
{
#ifdef _WIN32
    file_->publish(destination);
#else
    throw std::runtime_error("历史文件保护仅取得 Windows NTFS 资格");
#endif
}
NativeBarOutput::~NativeBarOutput()=default;
}
