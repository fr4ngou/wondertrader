#include "../GuanhengData/NativeBarFile.h"
#include "../WtDataStorage/DataDefine.h"
#include <cstddef>
#include <cstring>

// 自有 ABI 与原 WtDtHelper 分开命名、加载和校验摘要。所有回调同步执行，
// 指针只借用至回调返回；本入口拥有租约/临时文件/数组，异常不跨 DLL 边界。
#ifdef _WIN32
#define GH_BAR_API extern "C" __declspec(dllexport)
#else
#define GH_BAR_API extern "C" __attribute__((visibility("default")))
#endif
GH_BAR_API unsigned gh_native_bar_file_version() { return 1; }
GH_BAR_API unsigned gh_native_bar_file_layout(unsigned index)
{
    const unsigned layout[]={sizeof(wtp::WTSBarStruct),offsetof(wtp::WTSBarStruct,date),
        offsetof(wtp::WTSBarStruct,time),offsetof(wtp::WTSBarStruct,open),
        offsetof(wtp::WTSBarStruct,add)};
    return index<sizeof(layout)/sizeof(layout[0])?layout[index]:0;
}
GH_BAR_API unsigned gh_native_bar_file_read(const wchar_t* path,const char* sha256,
    unsigned maximum,unsigned file_budget,unsigned expected_type,
    FuncGetBarsCallback bars,FuncCountDataCallback count,FuncLogCallback logger)
{
    try
    {
        if(!path || !sha256 || std::strlen(sha256)!=64 || !bars || !count
            || !maximum || maximum>1000000 || file_budget<20 || file_budget>268435456
            || (expected_type!=BT_HIS_Minute1 && expected_type!=BT_HIS_Minute5 && expected_type!=BT_HIS_Day))
            throw std::runtime_error("原生历史参数非法");
        guanheng::NativeFileLease lease(path);
        auto bytes=lease.read(file_budget);
        if(guanheng::native_bar_digest(bytes)!=sha256)throw std::runtime_error("原生历史身份不符");
        auto result=guanheng::read_native_bar_bytes(bytes,maximum,
            std::size_t(maximum)*sizeof(wtp::WTSBarStruct),static_cast<std::uint16_t>(expected_type));
        count(static_cast<unsigned>(result.size()));
        bars(result.data(),static_cast<unsigned>(result.size()),true);
        return static_cast<unsigned>(result.size());
    }
    catch(...)
    {
        try { if(logger)logger("native bar file validation or original ABI read failed"); }
        catch(...) {} // 调用者的诊断回调也属于 ABI 边界，不能改变本次失败返回。
        return 0;
    }
}
