#include "QmtHostReadClient.h"
#include "QmtBoundReadCore.h"
#include <stdexcept>
namespace guanheng
{
class QmtHostReadClient::Impl
{
public:
    QmtBoundReadCore core;
    explicit Impl(QmtHttpConfig config,QmtReadProfileVersion version):core(std::move(config),
        version==QmtReadProfileVersion::Legacy?QmtBoundProfile::FullTickV1:
        version==QmtReadProfileVersion::FullTickV6?QmtBoundProfile::FullTickV6:QmtBoundProfile::FullTickV3){
        if(version!=QmtReadProfileVersion::Legacy&&version!=QmtReadProfileVersion::AccountV3
            &&version!=QmtReadProfileVersion::FullTickV6)
            throw std::invalid_argument("qmt_bound_profile_invalid");
    }
};
QmtHostReadClient::QmtHostReadClient(QmtHttpConfig config,QmtReadProfileVersion version):impl_(new Impl(std::move(config),version)){}
QmtHostReadClient::~QmtHostReadClient()=default;
Status QmtHostReadClient::prepare(std::uint32_t ms){return impl_->core.prepare(ms);}
SourceSession QmtHostReadClient::session()const{return impl_->core.session();}
Capability QmtHostReadClient::capability()const{return impl_->core.capability();}
QmtBoundResult QmtHostReadClient::read_full_tick(const std::string& args,std::uint32_t ms){return impl_->core.read_full_tick(args,ms);}
QmtBoundResult QmtHostReadClient::resume(const QmtBoundReceipt& receipt,std::uint32_t ms){return impl_->core.resume(receipt,ms);}
Status QmtHostReadClient::drain_callbacks(std::uint32_t ms)noexcept{return impl_->core.drain_callbacks(ms);}
}
