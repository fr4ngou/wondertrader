#pragma once

#ifdef _WIN32
#define GH_MARKET_EXPORT __declspec(dllexport)
#else
#define GH_MARKET_EXPORT __attribute__((visibility("default")))
#endif

// UTF-8 JSON ABI v1，供独立行情进程使用；不暴露 C++ 布局和交易入口。
// 创建/调用/销毁由同一线程拥有。返回字符串有效至下一次调用，调用方必须复制。
// 创建只校验配置并分配对象，不连接终端；失败返回 nullptr，异常不跨 ABI。
extern "C"
{
GH_MARKET_EXPORT void* gh_market_create(const char* config_json) noexcept;
GH_MARKET_EXPORT const char* gh_market_call(void* handle, const char* request_json) noexcept;
GH_MARKET_EXPORT void gh_market_destroy(void* handle) noexcept;
}
