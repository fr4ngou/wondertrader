#include "../GuanhengData/QmtPollingParser.h"
#include "../GuanhengData/QmtHostEndpoint.h"

extern "C"
{
EXPORT_FLAG wtp::IParserApi* createParser()
{
    try {
        return new guanheng::QmtPollingParser([](const guanheng::QmtHttpConfig& config,
            const guanheng::QmtHttpProfile& profile,guanheng::Status& status)->std::shared_ptr<guanheng::IMarketEndpoint>{
            auto client=std::make_shared<guanheng::QmtHostReadClient>(config,guanheng::QmtReadProfileVersion::FullTickV6);
            auto endpoint=std::make_shared<guanheng::QmtHostEndpoint>(std::move(client),profile,config.full_tick_batch_size);
            status=endpoint->prepare(config.timeout_ms);
            return endpoint;
        },true);
    } catch (...) { return nullptr; }
}
EXPORT_FLAG void deleteParser(wtp::IParserApi*& parser)
{
    auto owned=dynamic_cast<guanheng::QmtPollingParser*>(parser);
    if(owned&&owned->stop().ok()){owned->release();delete owned;parser=nullptr;}
}
EXPORT_FLAG bool stopParser(wtp::IParserApi* parser,std::uint32_t timeout_ms)
{
    auto owned=dynamic_cast<guanheng::QmtPollingParser*>(parser);
    return owned&&owned->stop(timeout_ms).ok();
}
}
