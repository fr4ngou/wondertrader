#include "QmtHistoryFiles.h"
#include <csignal>
#include <iostream>
#include <ctime>
#include <cstdlib>
#include <cstdio>

using namespace guanheng;
namespace hc=guanheng::history_cli;
namespace
{
QmtHistoryControl stop_control;
void stopped(int) { stop_control.request_stop(); }
struct Summary
{
    std::string status="failed",reason="历史读取尚未开始",run_id,plan_sha,manifest;
    std::uint64_t completed=0,pending=0,rows=0;int drained=-1,code=2;
};
void publish(const Summary& s)
{
    hc::Doc d;d.SetObject();auto& a=d.GetAllocator();hc::add(d,"schema","qmt.history-cli-result.v1");
    hc::add(d,"status",s.status);hc::add(d,"reason",s.reason);
    for(const auto& p:std::initializer_list<std::pair<const char*,const std::string*>>{{"run_id",&s.run_id},{"plan_sha256",&s.plan_sha},{"output_manifest",&s.manifest}})
        if(p.second->empty())d.AddMember(hc::Val(p.first,a),hc::Val(),a);else hc::add(d,p.first,*p.second);
    d.AddMember("pages_completed",s.completed,a);d.AddMember("pages_pending",s.pending,a);d.AddMember("rows_observed",s.rows,a);
    hc::add(d,"coverage","unknown");hc::add(d,"source_qualification","not-qualified");
    if(s.drained<0)d.AddMember("callbacks_drained",hc::Val(),a);else d.AddMember("callbacks_drained",s.drained==1,a);
    const auto raw=hc::json(d);hc::require(raw.size()<=16384);std::cout<<raw<<std::endl;
}
std::pair<hc::PageTask,hc::PageTask> split(const hc::PageTask& p,unsigned first)
{
    auto stamp=[](const std::string& s){std::tm t{};t.tm_year=std::stoi(s.substr(0,4))-1900;t.tm_mon=std::stoi(s.substr(4,2))-1;
        t.tm_mday=std::stoi(s.substr(6,2));t.tm_hour=std::stoi(s.substr(8,2));t.tm_min=std::stoi(s.substr(10,2));return _mkgmtime64(&t);};
    const auto start=stamp(p.request.start_time),end=stamp(p.request.end_time);
    hc::require(start>=0&&start<end,"单分钟历史窗口仍饱和",3);
    const auto middle=start+((end-start)/60/2)*60;
    auto string=[](__time64_t n){std::tm t{};hc::require(_gmtime64_s(&t,&n)==0);char buffer[32];hc::require(std::strftime(buffer,sizeof(buffer),"%Y%m%d%H%M00",&t)>0);return std::string(buffer);};
    auto left=p.request,right=p.request;left.end_time=string(middle);right.start_time=string(middle+60);
    return {{left,"page-"+std::to_string(first),p.name},{right,"page-"+std::to_string(first+1),p.name}};
}
struct Observed {std::string symbol;QmtHistoryRow row;};
// Rebuild the exact persisted plan before contacting the Host. A crash between
// planning two children and persisting either receipt leaves an explicit gap.
std::set<std::string> restore_plan(hc::Plan& plan,hc::Store& store,const hc::Limits& limits,SignedHttpDeadline& end)
{
    std::set<std::string> expected,branches;
    for(const auto& task:plan.tasks)expected.insert(task.name);
    for(std::size_t i=0;i<plan.tasks.size();++i){
        hc::check(end,stop_control);const auto task=plan.tasks[i];const auto path=store.path("pages/"+task.name+"/split.json");
        if(!hc::fs::exists(path))continue;
        hc::require(plan.split&&plan.tasks.size()+2<=limits.pages,"历史分页计划不合格");
        const auto link=hc::parse(hc::read(path,4096,end,stop_control),4096);
        hc::require(hc::keys(link,{"schema","left","right"})&&hc::text(link["schema"])=="qmt.history-split.v1");
        const auto left=hc::text(link["left"],32),right=hc::text(link["right"],32);
        const unsigned first=static_cast<unsigned>(plan.tasks.size()+1);const auto parts=split(task,first);
        hc::require(left==parts.first.name&&right==parts.second.name&&expected.insert(left).second&&expected.insert(right).second,"历史分页身份不合格");
        branches.insert(task.name);plan.tasks.push_back(parts.first);plan.tasks.push_back(parts.second);
    }
    for(const auto& entry:hc::fs::directory_iterator(store.path("pages"))){
        hc::check(end,stop_control);hc::no_reparse(entry.path());
        hc::require(entry.is_directory()&&expected.count(entry.path().filename().u8string()),"历史保留页不属于原计划");
    }
    return branches;
}
QmtBoundReceipt restore_receipt(const hc::Doc& durable,const hc::PageTask& task)
{
    auto out=hc::receipt(durable);
    hc::require(hc::text(durable["page"],32)==task.name&&durable["parent"].IsString()
        &&std::string(durable["parent"].GetString(),durable["parent"].GetStringLength())==task.parent,"历史回执分页身份不匹配");
    const auto body=hc::parse(out.request_body,65536);
    hc::require(body.IsObject()&&body.HasMember("arguments"),"历史回执请求不合格");
    const auto request=hc::window(body["arguments"]);
    hc::require(request.symbol==task.request.symbol&&request.start_time==task.request.start_time
        &&request.end_time==task.request.end_time&&request.max_rows==task.request.max_rows,"历史回执窗口不属于原计划");
    return out;
}
void export_qmi(hc::Store& store,const std::string& attempt,const hc::Config& config,const SourceSession& source,
                std::vector<Observed>& all,SignedHttpDeadline& end)
{
    const auto& p=config.source;
    if(all.empty())return;
    if(!config.source_values&&(p["minute_boundary"].IsNull()||p["volume_to_shares"].IsNull()||p["amount_to_yuan"].IsNull()))return;
    hc::require(!source.instance_id.empty()&&!source.session_id.empty()&&source.generation,"历史来源身份不可用",3);
    hc::check(end,stop_control);
    std::sort(all.begin(),all.end(),[](const auto& a,const auto& b){return a.symbol<b.symbol||(a.symbol==b.symbol&&a.row.time<b.row.time);});
    hc::check(end,stop_control);store.directory(attempt+"/csv");
    hc::Doc manifest;manifest.SetObject();auto& allocator=manifest.GetAllocator();manifest.AddMember("schema_version",config.source_values?2:1,allocator);
    hc::Doc profile;profile.SetObject();hc::add(profile,"provider","Qmt");hc::add(profile,"instance_id",source.instance_id);
    hc::add(profile,"session_id",source.session_id);profile.AddMember("generation",source.generation,profile.GetAllocator());
    // 两种 manifest 共用出口；四项来源身份仅由此处及真实会话生成，asset_class 留在配置。
    auto copy=[&](const char* key){profile.AddMember(hc::Val(key,profile.GetAllocator()),hc::Val(p[key],profile.GetAllocator()),profile.GetAllocator());};
    for(auto key:{"dataset_version","source_license","input_kind","timezone","minute_boundary"})copy(key);
    if(config.source_values)for(auto key:{"value_semantics","price_unit","volume_unit","amount_unit"})copy(key);
    else for(auto key:{"volume_to_shares","amount_to_yuan"})copy(key);
    for(auto key:{"adjustment","factor_version"})copy(key);
    manifest.AddMember("profile",hc::Val(profile,allocator),allocator);hc::Val securities(rapidjson::kArrayType);
    for(std::size_t i=0;i<all.size();){
        hc::check(end,stop_control);const auto symbol=all[i].symbol;std::ostringstream csv;csv.imbue(std::locale::classic());
        csv<<"timestamp,open,high,low,close,volume,amount\n"<<std::setprecision(std::numeric_limits<double>::max_digits10);
        std::uint64_t previous=0;
        for(;i<all.size()&&all[i].symbol==symbol;++i){
            hc::check(end,stop_control);const auto& r=all[i].row;hc::require(!previous||r.time>previous,"历史分页时间重复或冲突",3);previous=r.time;
            __time64_t seconds=static_cast<__time64_t>(r.time/1000+8*3600);std::tm t{};hc::require(_gmtime64_s(&t,&seconds)==0);
            char time[40];hc::require(std::strftime(time,sizeof(time),"%Y-%m-%dT%H:%M:00+08:00",&t)>0);
            csv<<time<<','<<r.open<<','<<r.high<<','<<r.low<<','<<r.close<<','<<r.volume<<','<<r.amount<<'\n';
            hc::require(csv.tellp()>=0&&static_cast<std::size_t>(csv.tellp())<=config.limits.bytes,"历史CSV超过输出容量");
        }
        const auto raw=csv.str(),relative="csv/"+symbol+".csv";store.write(attempt+"/"+relative,raw);
        hc::Val security(rapidjson::kObjectType),chunks(rapidjson::kArrayType),chunk(rapidjson::kObjectType);
        security.AddMember("symbol",hc::Val(symbol.c_str(),allocator),allocator);chunk.AddMember("path",hc::Val(relative.c_str(),allocator),allocator);
        const auto digest=hc::hash(raw);chunk.AddMember("sha256",hc::Val(digest.c_str(),allocator),allocator);chunks.PushBack(chunk,allocator);
        security.AddMember("chunks",chunks,allocator);securities.PushBack(security,allocator);
    }
    manifest.AddMember("securities",securities,allocator);store.write_json(attempt+"/qmi-manifest.json",manifest);
}
int run(int argc,wchar_t** argv)
{
    const auto started=std::chrono::steady_clock::now();SignedHttpDeadline end(started+std::chrono::milliseconds(300000));
    Summary summary;std::unique_ptr<QmtHostHistoryClient> client;std::unique_ptr<hc::Store> store_owner;bool had_receipt=false,active_unknown=false;
    try{
        if(argc==2&&std::wstring(argv[1])==L"--help"){
            summary.status="help";summary.reason="固定历史读取入口：fetch 使用受管配置、请求文件和新运行根；resume 只核查原编号";summary.code=0;publish(summary);return 0;
        }
        hc::require(argc>=2);const std::wstring mode=argv[1];hc::require(mode==L"fetch"||mode==L"resume");
        const bool fresh=mode==L"fetch";hc::require(argc==(fresh?8:6));
        std::map<std::wstring,std::wstring> flags;
        for(int i=2;i<argc;i+=2){const std::wstring key=argv[i];hc::require(key==L"--config"||key==L"--request"||key==L"--run-root");hc::require(flags.emplace(key,argv[i+1]).second);}
        hc::require(flags.count(L"--config")&&flags.count(L"--run-root")&&(fresh?flags.count(L"--request")==1:flags.count(L"--request")==0));
        const auto cfg=hc::config(hc::absolute(flags[L"--config"]),end,stop_control);
        end.end=started+std::chrono::milliseconds(cfg.limits.total_ms);hc::check(end,stop_control);
        const auto root=hc::absolute(flags[L"--run-root"]);hc::require(hc::under(root,cfg.runs_root),"历史运行目录超出受管根");
        hc::Plan plan;std::string raw_plan;hc::Doc saved;
        if(fresh){const auto file=hc::absolute(flags[L"--request"]);hc::require(hc::under(file,cfg.request_root),"历史请求文件超出受管根");
            raw_plan=hc::read(file,1024*1024,end,stop_control);auto parsed=hc::parse(raw_plan,1024*1024);plan=hc::plan(parsed,cfg.limits.pages,end,stop_control);
            summary.run_id=hc::uuid();summary.plan_sha=hc::hash(raw_plan);
        }else{
            // The original UTF8 plan is <=1MiB. Its ASCII JSON string form can
            // expand up to threefold; the fixed metadata adds less than 4KiB.
            constexpr std::size_t saved_plan_cap=3*1024*1024+4096;
            hc::no_reparse(root);saved=hc::parse(hc::read(root/L"plan.json",saved_plan_cap,end,stop_control),saved_plan_cap);
            hc::require(hc::keys(saved,{"schema","run_id","config_sha256","plan_sha256","plan_body"})&&hc::text(saved["schema"])=="qmt.history-run.v1"
                &&hc::text(saved["config_sha256"])==cfg.sha,"历史运行配置或身份不匹配");
            raw_plan=hc::text(saved["plan_body"],1024*1024);summary.plan_sha=hc::hash(raw_plan);hc::require(summary.plan_sha==hc::text(saved["plan_sha256"]));
            summary.run_id=hc::text(saved["run_id"],64);hc::require(hc::uuid_shape(summary.run_id));
            auto parsed=hc::parse(raw_plan,1024*1024);plan=hc::plan(parsed,cfg.limits.pages,end,stop_control);
        }
        store_owner.reset(new hc::Store(root,cfg.limits,end,stop_control,fresh));auto& store=*store_owner;
        if(fresh){hc::Doc metadata;metadata.SetObject();hc::add(metadata,"schema","qmt.history-run.v1");hc::add(metadata,"run_id",summary.run_id);
            hc::add(metadata,"config_sha256",cfg.sha);hc::add(metadata,"plan_sha256",summary.plan_sha);hc::add(metadata,"plan_body",raw_plan);
            store.write_json("plan.json",metadata);store.directory("pages");store.directory("attempts");
        }
        const auto branches=fresh?std::set<std::string>{}:restore_plan(plan,store,cfg.limits,end);
        // Receipt-to-plan association is a local admission check, before any I/O.
        if(!fresh)for(const auto& task:plan.tasks){
            hc::check(end,stop_control);const auto file=store.path("pages/"+task.name+"/receipt.json");
            if(hc::fs::exists(file))restore_receipt(hc::parse(hc::read(file,1024*1024,end,stop_control),1024*1024),task);
        }
        const auto attempt="attempts/"+hc::uuid();store.directory(attempt);
        // 版本来自受管配置；省略保持原 Legacy/v2，握手失败不自动降级。
        client.reset(new QmtHostHistoryClient(cfg.http,&stop_control,cfg.read_profile_version));const auto prepared=client->prepare(end);
        if(fresh&&!prepared.ok())throw hc::Failure("历史来源尚未就绪或能力不匹配",
            stop_control.stop_requested()?130:prepared.code==ErrorCode::Timeout?124:3);
        std::vector<Observed> observed;bool failed=false,unknown=false;std::size_t scheduled=plan.tasks.size();unsigned sequence=static_cast<unsigned>(scheduled);
        auto consume=[&](const std::string& name,const QmtHistoryResult& result){
            store.directory(attempt+"/"+name);hc::save_result(store,attempt+"/"+name,result);
            if(result.bound.result.status.ok()){
                hc::require(result.page.rows.size()<=cfg.limits.rows-summary.rows,"历史累计行数超过容量");
                for(const auto& row:result.page.rows){hc::check(end,stop_control);observed.push_back({result.page.request.symbol,row});}
                summary.rows+=result.page.rows.size();++summary.completed;
            }else if(result.remote_error_code!="history_window_limit"){
                failed=true;if(!result.bound.result.terminal){unknown=true;++summary.pending;}
            }
        };
        if(fresh){
            for(std::size_t i=0;i<plan.tasks.size();++i){
                hc::check(end,stop_control);const auto task=plan.tasks[i];auto p=client->create_request(task.request,end);
                if(!p.status.ok()||!p.request)throw hc::Failure("历史请求未通过能力或窗口准入",
                    stop_control.stop_requested()?130:p.status.code==ErrorCode::Timeout?124:2);
                store.directory("pages/"+task.name);
                auto durable=hc::receipt_json(*p.request,task);store.write_json("pages/"+task.name+"/receipt.json",durable);
                had_receipt=true;active_unknown=true;
                auto result=client->submit_once(std::move(p.request),end);
                active_unknown=result.bound.result.status.code==ErrorCode::SubmissionUnknown||!result.bound.result.terminal;
                consume(task.name,result);
                if(result.remote_error_code=="history_window_limit"){
                    if(!plan.split){failed=true;continue;}
                    hc::require(plan.tasks.size()+2<=cfg.limits.pages,"历史分页数量预算耗尽",3);
                    const auto parts=split(task,sequence+1);sequence+=2;plan.tasks.push_back(parts.first);plan.tasks.push_back(parts.second);scheduled=plan.tasks.size();
                    hc::Doc link;link.SetObject();hc::add(link,"schema","qmt.history-split.v1");hc::add(link,"left",parts.first.name);hc::add(link,"right",parts.second.name);
                    store.write_json("pages/"+task.name+"/split.json",link);
                }
                if(!result.bound.result.status.ok()&&result.remote_error_code!="history_window_limit"){
                    summary.pending+=plan.tasks.size()-i-1;break; // No automatic retry or new identity after unknown/failure.
                }
            }
        }else{
            for(const auto& task:plan.tasks){
                hc::check(end,stop_control);const auto file=store.path("pages/"+task.name+"/receipt.json");
                if(!hc::fs::exists(file)){failed=true;++summary.pending;continue;}
                auto durable=hc::parse(hc::read(file,1024*1024,end,stop_control),1024*1024);auto receipt=restore_receipt(durable,task);
                had_receipt=true;active_unknown=true;auto result=client->resume(receipt,end);
                active_unknown=result.bound.result.status.code==ErrorCode::SubmissionUnknown||!result.bound.result.terminal;
                if(branches.count(task.name)){
                    store.directory(attempt+"/"+task.name);hc::save_result(store,attempt+"/"+task.name,result);
                    if(result.remote_error_code!="history_window_limit"){
                        failed=true;if(active_unknown){unknown=true;++summary.pending;}
                    }
                }else{
                    consume(task.name,result);
                    if(result.remote_error_code=="history_window_limit")failed=true; // GET only; never creates a child POST.
                }
            }
        }
        hc::check(end,stop_control);
        // Duplicates across pages must be rejected even when units are unknown.
        std::sort(observed.begin(),observed.end(),[](const auto& a,const auto& b){return a.symbol<b.symbol||(a.symbol==b.symbol&&a.row.time<b.row.time);});
        for(std::size_t i=1;i<observed.size();++i){hc::check(end,stop_control);hc::require(observed[i-1].symbol!=observed[i].symbol||observed[i-1].row.time!=observed[i].row.time,"历史分页时间重复或冲突",3);}
        if(!failed&&!unknown)export_qmi(store,attempt,cfg,client->session(),observed,end);
        hc::Doc report;report.SetObject();hc::add(report,"schema","qmt.history-observation.v1");hc::add(report,"run_id",summary.run_id);
        hc::add(report,"plan_sha256",summary.plan_sha);hc::add(report,"coverage","unknown");hc::add(report,"qualification","DevelopmentVerified");
        report.AddMember("pages",static_cast<std::uint64_t>(scheduled),report.GetAllocator());report.AddMember("rows",summary.rows,report.GetAllocator());
        hc::add(report,"status",unknown?"unknown":failed?"partial":summary.rows?"observed":"empty");store.write_json(attempt+"/observation.json",report);
        summary.manifest=attempt+"/observation.json";summary.status=unknown?"unknown":failed?"partial":summary.rows?"observed":"empty";
        summary.reason=unknown?"历史结果未知，仅按原编号核查":failed?"历史计划存在失败或未完成页":"历史页观察已保存，覆盖与真实来源资格仍为未知";
        summary.code=unknown?4:failed?3:0;
    }catch(const hc::Failure& e){summary.reason=e.reason;summary.code=e.code;
        summary.status=e.code==130?"interrupted":e.code==124?"timeout":active_unknown?"unknown":had_receipt?"partial":"failed";
        if(e.code!=130&&e.code!=124){if(active_unknown)summary.code=4;else if(had_receipt)summary.code=3;}
        if(had_receipt)summary.pending=std::max<std::uint64_t>(1,summary.pending);
    }catch(...){summary.reason="历史读取未正常完成，原编号保留供核查";summary.status=active_unknown?"unknown":had_receipt?"partial":"failed";summary.code=active_unknown?4:had_receipt?3:2;}
    if(client){const auto drained=client->drain_callbacks(end.remaining());summary.drained=drained.ok()?1:0;
        if(!drained.ok()){
            summary.status="unknown";summary.reason="历史请求回调尚未确认排空，保留原编号";if(!summary.code)summary.code=4;
            // Keep the HTTP owner and code alive to process end, rather than invoking
            // its unbounded last-resort destructor and claiming graceful shutdown.
            client.release();publish(summary);std::_Exit(summary.code);
        }
        client.reset(); // The root lock remains held until all callbacks and the HTTP owner are gone.
    }
    publish(summary);return summary.code;
}
}
int wmain(int argc,wchar_t** argv)
{
    std::signal(SIGINT,stopped);std::signal(SIGTERM,stopped);
#ifdef SIGBREAK
    std::signal(SIGBREAK,stopped);
#endif
    try{return run(argc,argv);}catch(...){std::fputs("{\"schema\":\"qmt.history-cli-result.v1\",\"status\":\"failed\",\"reason\":\"history_output_failed\",\"run_id\":null,\"plan_sha256\":null,\"pages_completed\":0,\"pages_pending\":0,\"rows_observed\":0,\"coverage\":\"unknown\",\"source_qualification\":\"not-qualified\",\"callbacks_drained\":null,\"output_manifest\":null}\n",stdout);return 2;}
}
