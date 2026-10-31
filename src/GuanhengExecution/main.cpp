// 命令行与Python受管入口共用同一个原生运行体。
#include "CtaProcess.h"
int wmain(int argc,wchar_t** argv){
    return gh_cta_run(static_cast<uint32_t>(argc),argv,nullptr,nullptr);
}
