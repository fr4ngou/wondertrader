// 独立Common测试制品，真实签名HTTP；不链接Trader/WT，不提交任何SDK请求。
#include "QmtHostTradeClient.h"
#include "QmtHostAccountClient.h"
#include <rapidjson/stringbuffer.h>
#include <rapidjson/writer.h>
#include <chrono>
#include <cstring>
#include <memory>
#include <stdexcept>

// 此专用DLL不链接产品Standard。测试友元只调用产品私有接缝，不修改Core或状态。
namespace guanheng {
class StandardQmtTrader {
public:
    static Status reconcile(QmtHostTradeClient& client, SignedHttpDeadline& deadline)
    { return client.reconcile_observation(deadline); }
};
}
using namespace guanheng;
extern "C" __declspec(dllexport) int gh_qmt_observation_reconcile_case(
    const char* url, const char* binding_sha, const char* selected, char* output, unsigned capacity) noexcept
{
    if(!url||!binding_sha||!selected||!output||capacity<1024)return 2;
    std::unique_ptr<QmtHostTradeClient> client;
    try {
        QmtHttpConfig config;config.base_url=url;config.key_id="fixture";
        config.hmac_secret="synthetic-fault-http-secret";config.max_response_bytes=262144;
        QmtExpectedTrade expected;expected.account={"SYNTHETIC",QmtAccountEnvironment::Live};
        expected.binding_id="synthetic-only";expected.binding_sha256=binding_sha;expected.writes_enabled=true;
        QmtHostAccountClient account_layout(config,expected.account); // 构造无I/O，核同cohort账户Core布局。
        client.reset(new QmtHostTradeClient(config,expected));
        SignedHttpDeadline start(10000);if(!client->prepare(start).ok())throw std::runtime_error("initial_prepare");
        const bool timeout=std::strstr(selected,"timeout")!=nullptr;
        SignedHttpDeadline deadline(timeout?1000:5000);const auto original=deadline.end;
        const auto status=StandardQmtTrader::reconcile(*client,deadline);
        rapidjson::Document report(rapidjson::kObjectType);auto& a=report.GetAllocator();
        report.AddMember("same_deadline",deadline.end==original,a);
        report.AddMember("ok",status.ok(),a);
        report.AddMember("unknown",status.code==ErrorCode::SubmissionUnknown,a);
        report.AddMember("unavailable",status.code==ErrorCode::Unavailable,a);
        report.AddMember("timeout",status.code==ErrorCode::Timeout,a);
        report.AddMember("io_error",status.code==ErrorCode::IoError,a);
        report.AddMember("conflict",status.code==ErrorCode::Conflict,a);
        report.AddMember("stale",status.code==ErrorCode::StaleSession,a);
        report.AddMember("accepting",client->accepting_commands(),a);
        report.AddMember("drained",client->drain_callbacks(2000).ok(),a);
        rapidjson::StringBuffer text;rapidjson::Writer<rapidjson::StringBuffer> writer(text);report.Accept(writer);
        if(text.GetSize()+1>capacity)return 3;
        std::memcpy(output,text.GetString(),text.GetSize()+1);return 0;
    }catch(...){if(client)client->drain_callbacks(2000);return 1;}
}
