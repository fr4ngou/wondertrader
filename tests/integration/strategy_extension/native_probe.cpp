// 隔离探针直接消费最终CtaProcess实现；合成金融文件，无Source/交易服务。
#include "GuanhengExecution/CtaProcess.cpp"
#include "GuanhengExecution/RetiredTargetContext.h"
#include <iostream>

struct RetirementProbe : guanheng::RetiredTargetContext {
    explicit RetirementProbe(const std::vector<std::string>& codes) : RetiredTargetContext(nullptr, "probe", codes) {}
    void prepare(const std::string& code, double quantity) {
        auto& position = _pos_map[code];
        position._volume = quantity;
        position._closeprofit = 25.0;
        position._dynprofit = 100.0;
        _fund_info._total_profit = 25.0;
        _fund_info._total_dynprofit = 100.0;
        _sig_map[code]._volume = quantity;
        _condtions[code];
    }
    void verify_retirement(const std::string& code) {
        retire_loaded_targets();
        const auto& position = _pos_map.at(code);
        need(position._volume == 0 && position._closeprofit == 25.0
            && _fund_info._total_profit == 25.0 && _fund_info._total_dynprofit == 0);
        need(_sig_map.count(code) == 0 && _condtions.count(code) == 0);
    }
    double targets(const std::string& code) {
        double quantity = 0;
        enum_position([&](const char* item, double value){ if (code == item) quantity += value; }, true);
        return quantity;
    }
};

int main(int argc,char** argv){
    try{
        need(argc==2);auto request=parse(read(absolute(argv[1]),1024*1024));
        const auto mode=text(request,"mode");
        if(mode=="configuration-identity"){
            // 使用正式关闭标记的原生编码，避免测试把Python排序编码误作Native原件。
            rj::Document identity;identity.CopyFrom(member(request,"configuration"),identity.GetAllocator());
            identity.RemoveMember("recovery");
            std::cout<<"{\"ok\":true,\"sha256\":\""<<sha(encode(identity))<<"\"}";return 0;
        }
        if(mode=="compare")need(compatible_model(member(request,"previous"),member(request,"current")));
        else if(mode=="source-origin")source_origin(member(request,"source_extension"),text(request,"binding_sha256",64));
        else if(mode=="source-plan")source_plan(member(request,"plan"));
        else if(mode=="state")transition_state_identity(absolute(text(request,"output")),member(request,"current"),member(request,"previous"));
        else if(mode=="observation-write"){
            const auto output=absolute(text(request,"output"));
            std::string committed;
            auto first=parse(R"({"quotes":0})");auto second=parse(R"({"quotes":1})");
            publish_observation(output,first,committed);
            const auto pending=fs::path(output.wstring()+L".pending");
            publish(pending,first);
            publish_observation(output,first,committed); // 同值跳过，不尝试打开已存在的临时文件。
            bool failed=false;
            try{publish_observation(output,second,committed);}catch(const std::exception&){failed=true;}
            need(failed&&committed==encode(first)&&read(output,4096)==committed);
            need(fs::remove(pending));
            publish_observation(output,second,committed);
            need(committed==encode(second)&&read(output,4096)==committed);
            need(fs::remove(output));
            publish_observation(output,second,committed);
            need(read(output,4096)==committed);
        }
        else if(mode=="retire-context"){
            const auto code=text(request,"symbol");
            RetirementProbe retired({code}), active(std::vector<std::string>{});
            retired.prepare(code,188600.0);active.prepare(code,100.0);
            retired.verify_retirement(code);
            need(retired.targets(code)==0&&active.targets(code)==100.0);
        }
        else if(mode=="admit"||mode=="admit-private-storage"){
            const auto& current=member(request,"current");
            const auto output=absolute(text(current,"output_directory"));
            Handle lease;
            if(mode=="admit-private-storage"){
                lease.value=CreateFileW((output/".cta-session.lock").c_str(),GENERIC_READ|GENERIC_WRITE,0,
                    nullptr,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);
                need(lease.value!=INVALID_HANDLE_VALUE);
            }
            admit_reconciled(member(current,"recovery"),current,output,member(current,"strategies"),
                text(request,"installation"),text(request,"id"),text(request,"configuration"),absolute(text(request,"control")));
        }else need(false);
        std::cout<<"{\"ok\":true}";return 0;
    }catch(const std::exception& error){std::cout<<"{\"ok\":false,\"error\":\""<<error.what()<<"\"}";return 2;}
}
