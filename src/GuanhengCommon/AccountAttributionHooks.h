#pragma once
#include "AccountAttributionProtocol.h"
#ifdef __cplusplus
#include <rapidjson/document.h>
#include <rapidjson/stringbuffer.h>
#include <rapidjson/writer.h>
#include <mutex>
#include <thread>
#include <stdexcept>
#include <string>
#include <chrono>

namespace guanheng {
class AttributionDeadline final:public std::runtime_error {
public:AttributionDeadline():std::runtime_error("account_attribution_deadline"){}
};
class AttributionRegistration {
    std::mutex mutex_; // 仅保护一次性注册与freeze，不在回调期间持有。
    std::thread::id owner_{}; // 原配置线程，禁止跨线程重新注册。
    AttributionObserver observer_; // 固定函数/user值，不持有任何金融状态。
    bool frozen_=false; // 原创建/run边界关闭注册，进程内不热切。
public:
    int configure(GhAttributionCallbackV1 callback,void* user){
        std::lock_guard<std::mutex> lock(mutex_);
        if(!callback||frozen_||observer_||(owner_!=std::thread::id{}&&owner_!=std::this_thread::get_id()))return -1;
        owner_=std::this_thread::get_id();observer_={callback,user};return 0;
    }
    AttributionObserver freeze(){std::lock_guard<std::mutex> lock(mutex_);
        if(observer_&&owner_!=std::this_thread::get_id())throw std::runtime_error("account_attribution_wrong_owner");
        frozen_=true;return observer_;}
    AttributionObserver value(){std::lock_guard<std::mutex> lock(mutex_);return observer_;}
};
inline void attribution_text(rapidjson::Value& out,const char* key,const std::string& text,rapidjson::Document::AllocatorType& a){
    out.AddMember(rapidjson::Value(key,a),rapidjson::Value(text.data(),static_cast<rapidjson::SizeType>(text.size()),a),a);
}
inline void attribution_number(rapidjson::Value& out,const char* key,double value,rapidjson::Document::AllocatorType& a){
    out.AddMember(rapidjson::Value(key,a),value,a);
}
inline void attribution_uint(rapidjson::Value& out,const char* key,uint64_t value,rapidjson::Document::AllocatorType& a){
    out.AddMember(rapidjson::Value(key,a),value,a);
}
inline int attribution_call(AttributionObserver observer,uint32_t kind,uint32_t role,uint64_t epoch,uint64_t remaining,
                            const rapidjson::Document& value,GhAttributionReplyV1& reply,
                            const std::chrono::steady_clock::time_point* until=nullptr){
    if(!observer)return 0;
    rapidjson::StringBuffer bytes;rapidjson::Writer<rapidjson::StringBuffer> writer(bytes);
    if(!value.Accept(writer)||bytes.GetSize()>2u*1024u*1024u)return -1;
    // 编码也消耗原D；在真正回调前重新核同一absolute截止，0不再代表该阶段可用。
    if(until){const auto left=std::chrono::duration_cast<std::chrono::milliseconds>(*until-std::chrono::steady_clock::now()).count();
        if(left<=0)throw AttributionDeadline{};remaining=static_cast<uint64_t>(left);}
    GhAttributionEventV1 event{sizeof(GhAttributionEventV1),1,kind,role,epoch,remaining,
        static_cast<uint32_t>(bytes.GetSize()),0,bytes.GetString()};
    const auto result=observer.callback(&event,&reply,observer.user);
    if(until&&std::chrono::steady_clock::now()>=*until)throw AttributionDeadline{};
    if(result||reply.size!=sizeof(reply)||reply.version!=1||reply.reserved)return -1;
    return 0;
}
inline void attribution_notify(AttributionObserver observer,uint32_t kind,uint32_t role,const rapidjson::Document& value,
                               uint64_t epoch=0,uint64_t remaining=0){
    if(!observer)return;
    GhAttributionReplyV1 reply{sizeof(reply),1,-1,0,0};
    if(attribution_call(observer,kind,role,epoch,remaining,value,reply)||reply.decision||reply.authorized_quantity!=0)
        throw std::runtime_error("account_attribution_callback_failed");
}
// 原有独立D的worker/source事件；编码、回调和返回均消费同一个until，禁止以0重新开预算。
inline void attribution_notify_until(AttributionObserver observer,uint32_t kind,uint32_t role,const rapidjson::Document& value,
                                     std::chrono::steady_clock::time_point until){
    if(!observer)return;
    GhAttributionReplyV1 reply{sizeof(reply),1,-1,0,0};
    if(attribution_call(observer,kind,role,0,0,value,reply,&until)||reply.decision||reply.authorized_quantity!=0)
        throw std::runtime_error("account_attribution_callback_failed");
}
} // namespace guanheng
#endif
