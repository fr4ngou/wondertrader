#pragma once
#include <string>
// QAR/NQH共用原字段命名；金融含义只由账户mapper定义，未登记别名保持停用。
namespace guanheng { namespace account_fields {
// STQ-P2：旧数组及金融解释保持；新键仅为显式账户2.0投影的原值运输。
constexpr const char *policy_version="1.0",*identity_policy_version="2.0";
constexpr const char *schema="qmt.account-batch.v1",*identity_schema="qmt.account-batch.v2";
constexpr const char *fee_policy_version="3.0",*fee_schema="qmt.account-batch.v3";
// 2.0保留原身份投影，3.0在同一身份基础上显式提供逐笔当前费用。
inline bool has_order_identity(const std::string& version){return version==identity_policy_version||version==fee_policy_version;}
constexpr const char *remark="m_strRemark",*order_ref="m_strOrderRef";
constexpr const char* identity_fields[]={remark,order_ref};
// 仅显式账户3.0成交投影允许；SDK版本的三种原费用拼写，不适用于整账户佣金。
constexpr const char* trade_fee_fields[]={"m_dCommission","m_dComission","m_dComssion"};
constexpr const char *code="m_strInstrumentID",*exchange="m_strExchangeID",*account="m_strAccountID",*money="m_strMoneyType";
constexpr const char *volume="m_nVolume",*available_volume="m_nCanUseVolume",*yesterday="m_nYesterdayVolume",*frozen_volume="m_nFrozenVolume",*onroad="m_nOnRoadVolume";
constexpr const char *avg="m_dAvgPrice",*open="m_dOpenPrice",*position_profit="m_dPositionProfit",*float_profit="m_dFloatProfit",*market_value="m_dMarketValue";
constexpr const char *order="m_strOrderSysID",*trade="m_strTradeID",*side="m_nOffsetFlag",*quantity="m_nVolumeTotalOriginal",*filled="m_nVolumeTraded",*remaining="m_nVolumeTotal",*state="m_nOrderStatus",*limit_price="m_dLimitPrice",*cancel="m_dCancelAmount";
constexpr const char *insert_date="m_strInsertDate",*insert_time="m_strInsertTime",*trade_date="m_strTradeDate",*trade_time="m_strTradeTime",*price="m_dPrice",*amount="m_dTradeAmount";
constexpr const char *balance="m_dBalance",*available="m_dAvailable",*previous="m_dPreBalance",*commission="m_dCommission",*frozen_cash="m_dFrozenCash",*frozen_margin="m_dFrozenMargin",*frozen_commission="m_dFrozenCommission";
constexpr const char* position_fields[]={code,exchange,account,money,volume,available_volume,yesterday,frozen_volume,onroad,avg,open,position_profit,float_profit,market_value};
constexpr const char* order_fields[]={code,exchange,account,money,order,side,quantity,filled,remaining,state,limit_price,cancel,insert_date,insert_time};
constexpr const char* trade_fields[]={code,exchange,account,money,order,trade,side,volume,price,amount,trade_date,trade_time};
constexpr const char* account_fields[]={account,money,balance,available,previous,commission,frozen_cash,frozen_margin,frozen_commission,position_profit,float_profit};
}}
