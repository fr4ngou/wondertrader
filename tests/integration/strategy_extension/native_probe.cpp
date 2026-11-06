// 隔离探针直接消费最终CtaProcess实现；合成金融文件，无Source/交易服务。
#include "GuanhengExecution/CtaProcess.cpp"
#include <iostream>
int main(int argc,char** argv){
    try{
        need(argc==2);auto request=parse(read(absolute(argv[1]),1024*1024));
        const auto mode=text(request,"mode");
        if(mode=="compare")need(compatible_model(member(request,"previous"),member(request,"current")));
        else if(mode=="state")transition_state_identity(absolute(text(request,"output")),member(request,"current"),member(request,"previous"));
        else if(mode=="admit"){
            const auto& current=member(request,"current");
            admit_reconciled(member(current,"recovery"),current,absolute(text(current,"output_directory")),member(current,"strategies"),
                text(request,"installation"),text(request,"id"),text(request,"configuration"),absolute(text(request,"control")));
        }else need(false);
        std::cout<<"{\"ok\":true}";return 0;
    }catch(const std::exception& error){std::cout<<"{\"ok\":false,\"error\":\""<<error.what()<<"\"}";return 2;}
}
