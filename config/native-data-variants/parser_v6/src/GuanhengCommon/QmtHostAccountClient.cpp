#include "QmtHostAccountClient.h"
#include "QmtBoundReadCore.h"
#include <stdexcept>
namespace guanheng
{
namespace {
QmtBoundProfile account_profile(QmtAccountReadVersion version)
{
    if(version==QmtAccountReadVersion::V3)return QmtBoundProfile::AccountV3;
    if(version==QmtAccountReadVersion::V4)return QmtBoundProfile::AccountV4;
    throw std::invalid_argument("qmt_account_profile_invalid");
}
}

QmtHostAccountClient::QmtHostAccountClient(QmtHttpConfig config,QmtExpectedAccount expected,const QmtAccountControl* control,QmtAccountReadVersion version)
    :core_(new QmtBoundReadCore(std::move(config),account_profile(version),control,&expected)){}
QmtHostAccountClient::~QmtHostAccountClient()=default;
Status QmtHostAccountClient::prepare(SignedHttpDeadline& end){return core_->prepare(end);}
SourceSession QmtHostAccountClient::session()const{return core_->session();}
Capability QmtHostAccountClient::capability()const{return core_->capability();}
QmtAccountPreparation QmtHostAccountClient::create_request(QmtAccountDatatype type,SignedHttpDeadline& end)
{return core_->create_account(type,end);}
QmtAccountResult QmtHostAccountClient::submit_once(std::unique_ptr<QmtPreparedAccountRead> token,SignedHttpDeadline& end)
{return core_->submit_account(std::move(token),end);}
QmtAccountResult QmtHostAccountClient::resume(const QmtBoundReceipt& receipt,SignedHttpDeadline& end)
{return core_->resume_account(receipt,end);}
Status QmtHostAccountClient::prepare(SignedHttpDeadline& end,QmtAccountReadControlResult* out,const QmtAccountControl* control)
{return core_->prepare(end,out,control);}
QmtAccountPreparation QmtHostAccountClient::create_request(QmtAccountDatatype type,SignedHttpDeadline& end,QmtAccountReadControlResult* out,const QmtAccountControl* control)
{return core_->create_account(type,end,out,control);}
QmtAccountResult QmtHostAccountClient::submit_once(std::unique_ptr<QmtPreparedAccountRead> token,SignedHttpDeadline& end,QmtAccountReadControlResult* out,const QmtAccountControl* control)
{return core_->submit_account(std::move(token),end,out,control);}
QmtAccountResult QmtHostAccountClient::resume(const QmtBoundReceipt& receipt,SignedHttpDeadline& end,QmtAccountReadControlResult* out,const QmtAccountControl* control)
{return core_->resume_account(receipt,end,out,control);}
Status QmtHostAccountClient::drain_callbacks(std::uint32_t milliseconds)noexcept{return core_->drain_callbacks(milliseconds);}
}
