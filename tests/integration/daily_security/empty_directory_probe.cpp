// 在精确原实现所在翻译单元中控制“父目录已打开、最终文件尚未创建”的窗口。
// 生产路径不增加测试钩子；原NtCreateFile/句柄检查保持原样。
#include "GuanhengData/NativeBarFile.cpp"
#include <fstream>
#include <iostream>

namespace fs=std::filesystem;

DWORD junction(const fs::path& path,const fs::path& target)
{
    auto handle=CreateFileW(path.c_str(),GENERIC_WRITE,FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,
        nullptr,OPEN_EXISTING,FILE_FLAG_BACKUP_SEMANTICS|FILE_FLAG_OPEN_REPARSE_POINT,nullptr);
    if(handle==INVALID_HANDLE_VALUE)return GetLastError();
    const auto substitute=L"\\??\\"+fs::absolute(target).wstring(),print=fs::absolute(target).wstring();
    const auto first=substitute.size()*2,second=print.size()*2;
    std::vector<unsigned char> bytes(16+first+2+second+2);
    const DWORD tag=0xa0000003;const WORD size=static_cast<WORD>(bytes.size()-8),zero=0;
    const WORD sub_size=static_cast<WORD>(first),print_offset=static_cast<WORD>(first+2),print_size=static_cast<WORD>(second);
    std::memcpy(bytes.data(),&tag,4);std::memcpy(bytes.data()+4,&size,2);std::memcpy(bytes.data()+8,&zero,2);
    std::memcpy(bytes.data()+10,&sub_size,2);std::memcpy(bytes.data()+12,&print_offset,2);std::memcpy(bytes.data()+14,&print_size,2);
    std::memcpy(bytes.data()+16,substitute.c_str(),first+2);std::memcpy(bytes.data()+18+first,print.c_str(),second+2);
    DWORD returned=0;
    const auto ok=DeviceIoControl(handle,0x900a4,bytes.data(),static_cast<DWORD>(bytes.size()),nullptr,0,&returned,nullptr);
    const auto error=ok?ERROR_SUCCESS:GetLastError();CloseHandle(handle);return error;
}

int main(int argc,char** argv)
{
    try
    {
        if(argc!=2)throw std::runtime_error("expected private test root");
        const auto root=fs::absolute(argv[1]);
        if(fs::exists(root))throw std::runtime_error("test root must be new");
        fs::create_directory(root);const auto empty=root/"empty",outside=root/"outside";
        fs::create_directory(empty);fs::create_directory(outside);
        {std::ofstream marker(outside/"marker");marker<<"owned-test-marker";}
        bool rejected=false;
        {
            guanheng::NativePathLease lease(empty);
            const auto changed=junction(empty,outside);
            if(changed!=ERROR_SUCCESS)throw std::runtime_error("empty directory conversion did not reach race window");
            try
            {
                auto file=lease.file(L"candidate.dsb",GENERIC_READ|GENERIC_WRITE|DELETE,FILE_SHARE_READ,true);
            }
            catch(const std::exception&){rejected=true;}
            if(!rejected)throw std::runtime_error("converted parent reached native helper boundary");
        }
        std::ifstream in(outside/"marker");std::string marker;in>>marker;
        if(marker!="owned-test-marker"||fs::exists(outside/"candidate.dsb"))
            throw std::runtime_error("conversion modified outside object");
        // 仅移除本测试创建的junction叶项；目标目录和标记保留作验证证据。
        if(!RemoveDirectoryW(empty.c_str()))throw std::runtime_error("test junction release failed");
        std::cout<<"{\"passed\":true,\"empty_conversion_observed\":true,\"rejected_before_helper\":true,\"outside_unchanged\":true}\n";
        return 0;
    }
    catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 1;}
}
