#pragma once
#include "ProviderTypes.h"
#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <winhttp.h>
#include <array>
#include <chrono>
#include <exception>

namespace guanheng
{
// 调用方串行拥有此表，并保证 session 先于表析构关闭。表不调用用户代码。
// 预留固定槽，确保请求异常/取消时不依赖动态分配来保存卸载屏障。
// UNLOAD_NOTIFY_EVENT 置位表示 session 最后回调已返回；事件此前必须保持有效。
class WinHttpSessionDrain
{
public:
    static constexpr std::size_t capacity = 64;
    WinHttpSessionDrain() = default;
    WinHttpSessionDrain(const WinHttpSessionDrain&) = delete;
    WinHttpSessionDrain& operator=(const WinHttpSessionDrain&) = delete;
    ~WinHttpSessionDrain() noexcept
    {
        // 兼容没有可返回关闭状态的旧析构。受管宿主应在其外层调用有界 drain。
        for (auto& event : events_)
        {
            if (!event) continue;
            if (WaitForSingleObject(event, INFINITE) != WAIT_OBJECT_0) std::terminate();
            CloseHandle(event); event = nullptr;
        }
    }

    // 必须在创建新 session 之前检查，避免已满时继续产生异步资源。
    bool available() noexcept
    {
        reap();
        for (auto event : events_) if (!event) return true;
        return false;
    }

    // 在创建 connection/request、注册 callback 之前调用。失败时尚无用户回调，
    // 调用方关闭 session；成功时表拥有事件，session 仍由调用方关闭。
    Status track(HINTERNET session)
    {
        reap();
        for (auto& slot : events_)
        {
            if (slot) continue;
            HANDLE event = CreateEventW(nullptr, TRUE, FALSE, nullptr);
            if (!event) return {ErrorCode::IoError, "http_unload_event_create_failed"};
            if (!WinHttpSetOption(session, WINHTTP_OPTION_UNLOAD_NOTIFY_EVENT, &event, sizeof(event)))
            {
                CloseHandle(event);
                return {ErrorCode::IoError, "http_unload_event_setup_failed"};
            }
            slot = event;
            return {};
        }
        return {ErrorCode::Backpressure, "http_pending_session_limit"};
    }

    Status drain(std::uint32_t timeout_ms)
    {
        if (timeout_ms > 300000) return {ErrorCode::InvalidInput, "http_drain_budget_invalid"};
        const auto until = std::chrono::steady_clock::now() + std::chrono::milliseconds(timeout_ms);
        for (auto& event : events_)
        {
            if (!event) continue;
            auto waited = WaitForSingleObject(event, 0);
            if (waited == WAIT_TIMEOUT && timeout_ms)
            {
                const auto now = std::chrono::steady_clock::now();
                const auto left = now < until ? std::chrono::duration_cast<std::chrono::milliseconds>(until-now).count() : 0;
                if (left) waited = WaitForSingleObject(event, static_cast<DWORD>(left));
            }
            if (waited == WAIT_TIMEOUT)
                return {timeout_ms ? ErrorCode::Timeout : ErrorCode::Pending, "http_callbacks_not_drained"};
            if (waited != WAIT_OBJECT_0) return {ErrorCode::IoError, "http_drain_wait_failed"};
            CloseHandle(event); event = nullptr;
        }
        return {};
    }
private:
    void reap() noexcept
    {
        for (auto& event : events_)
            if (event && WaitForSingleObject(event, 0) == WAIT_OBJECT_0)
            { CloseHandle(event); event = nullptr; }
    }
    std::array<HANDLE, capacity> events_{};
};
}
#endif
