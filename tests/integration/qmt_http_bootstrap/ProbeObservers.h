#pragma once
#include "WTSTools/WTSLogger.h"
#include "Includes/ILogHandler.h"
#include <condition_variable>
#include <mutex>
#include <vector>

// 屏障位于真实BaseData虚调用内：结果已出队，WTS构造尚未完成，稳定覆盖交付前越界。
struct MappingGateData : WTSBaseDataMgr
{
    unsigned contract_calls=0, gate_at=0, gate_ms=0;
    bool gate_crossed=false;
    WTSContractInfo* getContract(const char* code,const char* exchange="",uint32_t date=0) override
    {
        if(++contract_calls==gate_at){
            std::mutex mutex;std::condition_variable cv;std::unique_lock<std::mutex> lock(mutex);
            cv.wait_until(lock,std::chrono::steady_clock::now()+std::chrono::milliseconds(gate_ms),[]{return false;});
            gate_crossed=true;
        }
        return WTSBaseDataMgr::getContract(code,exchange,date);
    }
};

struct NativeLogObserver : wtp::ILogHandler
{
    std::vector<std::string> lines;
    void handleLogAppend(WTSLogLevel,const char* text) override {lines.emplace_back(text);}
};

// 只复制进入原SPI的值，再调用固定上游实现；不读取private、不维护生产统计。
struct NativeAdapterObserver : wtp::TraderAdapter
{
    struct Order {std::string id,tag,code;unsigned direction,offset,state,flag;bool error,alive;double quantity,filled,left;};
    struct Trade {std::string id,order,code;unsigned direction,offset;double quantity;};
    std::vector<Order> order_rows;std::vector<Trade> trade_rows;
    unsigned position_calls=0,order_calls=0,trade_calls=0,login_calls=0,connect_calls=0,slow_connect_ms=0;
    void handleEvent(WTSTraderEvent event,int32_t error) override
    {
        if(event==wtp::WTE_Connect){
            ++connect_calls;
            if(slow_connect_ms){std::mutex mutex;std::condition_variable cv;std::unique_lock<std::mutex> lock(mutex);cv.wait_until(lock,std::chrono::steady_clock::now()+std::chrono::milliseconds(slow_connect_ms),[]{return false;});}
        }
        TraderAdapter::handleEvent(event,error);
    }
    void onLoginResult(bool success,const char* message,uint32_t date) override
    {++login_calls;TraderAdapter::onLoginResult(success,message,date);}
    void onRspPosition(const WTSArray* rows) override {++position_calls;TraderAdapter::onRspPosition(rows);}
    void onRspOrders(const WTSArray* rows) override
    {
        ++order_calls;
        if(rows)for(auto it=rows->begin();it!=rows->end();++it){auto p=static_cast<wtp::WTSOrderInfo*>(*it);order_rows.push_back({p->getOrderID(),p->getUserTag(),p->getCode(),unsigned(p->getDirection()),unsigned(p->getOffsetType()),unsigned(p->getOrderState()),unsigned(p->getOrderFlag()),p->isError(),p->isAlive(),p->getVolume(),p->getVolTraded(),p->getVolLeft()});}
        TraderAdapter::onRspOrders(rows);
    }
    void onRspTrades(const WTSArray* rows) override
    {
        ++trade_calls;
        if(rows)for(auto it=rows->begin();it!=rows->end();++it){auto p=static_cast<wtp::WTSTradeInfo*>(*it);trade_rows.push_back({p->getTradeID(),p->getRefOrder(),p->getCode(),unsigned(p->getDirection()),unsigned(p->getOffsetType()),p->getVolume()});}
        TraderAdapter::onRspTrades(rows);
    }
    void write(const std::filesystem::path& root,const NativeLogObserver& log)
    {
        rapidjson::Document d;d.SetObject();auto& a=d.GetAllocator();rapidjson::Value orders(rapidjson::kArrayType),trades(rapidjson::kArrayType),logs(rapidjson::kArrayType);
        for(const auto& p:order_rows){rapidjson::Value v(rapidjson::kObjectType);v.AddMember("id",rapidjson::Value(p.id.c_str(),a),a);v.AddMember("tag",rapidjson::Value(p.tag.c_str(),a),a);v.AddMember("code",rapidjson::Value(p.code.c_str(),a),a);v.AddMember("direction",p.direction,a);v.AddMember("offset",p.offset,a);v.AddMember("state",p.state,a);v.AddMember("flag",p.flag,a);v.AddMember("error",p.error,a);v.AddMember("alive",p.alive,a);v.AddMember("quantity",p.quantity,a);v.AddMember("filled",p.filled,a);v.AddMember("left",p.left,a);orders.PushBack(v,a);}
        for(const auto& p:trade_rows){rapidjson::Value v(rapidjson::kObjectType);v.AddMember("id",rapidjson::Value(p.id.c_str(),a),a);v.AddMember("order",rapidjson::Value(p.order.c_str(),a),a);v.AddMember("code",rapidjson::Value(p.code.c_str(),a),a);v.AddMember("direction",p.direction,a);v.AddMember("offset",p.offset,a);v.AddMember("quantity",p.quantity,a);trades.PushBack(v,a);}
        for(const auto& line:log.lines)logs.PushBack(rapidjson::Value(line.c_str(),a),a);
        d.AddMember("orders",orders,a);d.AddMember("trades",trades,a);d.AddMember("native_logs",logs,a);d.AddMember("position_calls",position_calls,a);d.AddMember("order_calls",order_calls,a);d.AddMember("trade_calls",trade_calls,a);d.AddMember("connect_calls",connect_calls,a);d.AddMember("login_calls",login_calls,a);
        rapidjson::StringBuffer b;rapidjson::Writer<rapidjson::StringBuffer> w(b);d.Accept(w);std::ofstream(root/"native-observer.json")<<b.GetString();
    }
};
