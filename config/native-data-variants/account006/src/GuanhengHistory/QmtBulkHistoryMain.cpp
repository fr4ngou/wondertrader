#include "QmtHistoryFiles.h"
#include "../GuanhengCommon/QmtHostCodec.h"
#include <csignal>
#include <cstdio>
#include <cstdlib>
#include <ctime>
#include <iostream>

using namespace guanheng;
namespace hc=guanheng::history_cli;
namespace codec=guanheng::qmt_host_codec;
namespace {
constexpr const char* operation="market.history_1m.bulk";
QmtHistoryControl control;
void stopped(int){control.request_stop();}
void need(bool value){hc::require(value,"批量历史合同或身份不匹配");}
bool eq(const hc::Val& value,const char* text){return value.IsString()&&codec::text(value)==text;}
bool same(const hc::Val& a,const hc::Val& b){return codec::encode(a)==codec::encode(b);}
hc::Doc copy(const hc::Val& value){hc::Doc out;out.CopyFrom(value,out.GetAllocator());return out;}
void member(hc::Doc& value,const char* key,const hc::Val& child)
{value.AddMember(hc::Val(key,value.GetAllocator()),hc::Val(child,value.GetAllocator()),value.GetAllocator());}

struct Config {
    QmtHttpConfig http;hc::fs::path requests,runs,artifacts;hc::Limits limits;
    std::string sha,root_id,profile_sha;
};
Config load_config(const hc::fs::path& file,SignedHttpDeadline& end)
{
    const auto raw=hc::read(file,1048576,end,control);const auto d=hc::parse(raw,1048576);Config c;
    need(hc::keys(d,{"schema","http","request_root","runs_root","artifact_root_id","artifact_root","limits","read_profile_sha256"})
        &&eq(d["schema"],"qmt.bulk-history-cli-config.v1")&&codec::uuid(d["artifact_root_id"])
        &&codec::hex(d["read_profile_sha256"],64));
    c.root_id=hc::text(d["artifact_root_id"]);c.profile_sha=hc::text(d["read_profile_sha256"]);c.sha=hc::hash(raw);
    const auto& h=d["http"];need(hc::keys(h,{"base_url","key_id","hmac_secret","timeout_ms","max_response_bytes"}));
    c.http={hc::text(h["base_url"],2048),hc::text(h["key_id"],128),hc::text(h["hmac_secret"],8192),
        static_cast<std::uint32_t>(hc::number(h["timeout_ms"],1,30000)),
        static_cast<std::size_t>(hc::number(h["max_response_bytes"],16384,4194304))};
    c.requests=hc::absolute(hc::fs::u8path(hc::text(d["request_root"],1024)).wstring());
    c.runs=hc::absolute(hc::fs::u8path(hc::text(d["runs_root"],1024)).wstring());
    c.artifacts=hc::absolute(hc::fs::u8path(hc::text(d["artifact_root"],1024)).wstring());
    for(const auto& p:{c.requests,c.runs,c.artifacts}){hc::no_reparse(p);need(hc::fs::is_directory(p));}
    const auto& l=d["limits"];need(hc::keys(l,{"total_ms","max_output_bytes","max_output_files"}));
    c.limits={static_cast<std::uint32_t>(hc::number(l["total_ms"],100,300000)),1,1000000,
        static_cast<std::uint32_t>(hc::number(l["max_output_files"],4,32768)),
        static_cast<std::size_t>(hc::number(l["max_output_bytes"],65536,268435456))};
    return c;
}

// 部署提供完整profile摘要；这里只消费该固定能力的明确v5/3.0字段。
hc::Doc profile(const std::string& raw,const Config& cfg)
{
    need(hc::hash(raw)==cfg.profile_sha);auto p=hc::parse(raw,4096);
    need(hc::keys(p,{"read_profile_version","read_operations","execution_timeout_ms","control_profile","operation_profiles","bulk_profile"})
        &&eq(p["read_profile_version"],"qmt.read-profile.v5")&&p["read_operations"].IsArray()
        &&p["control_profile"].IsObject()&&p["control_profile"].HasMember("schema_version")
        &&eq(p["control_profile"]["schema_version"],"3.0"));
    bool found=false;for(const auto& op:p["read_operations"].GetArray())if(eq(op,operation))found=true;need(found);
    const auto& b=p["bulk_profile"];
    need(hc::keys(b,{"schema_version","policy_id","policy_version","clock_schema","queue_timeout_ms","total_timeout_ms","limits"})
        &&eq(b["policy_id"],"qmt.history-bulk-read.v1")&&eq(b["policy_version"],"1.0")&&eq(b["clock_schema"],"qmt.win-uptime-ms.v1"));
    hc::number(b["queue_timeout_ms"],100,300000);hc::number(b["total_timeout_ms"],100,360000);
    const auto& l=b["limits"];
    need(hc::keys(l,{"max_calendar_days","max_rows","max_row_bytes","max_snapshot_bytes","max_page_rows","max_page_bytes","max_total_bytes","max_pages","max_ranges"}));
    hc::number(l["max_calendar_days"],1,36600);hc::number(l["max_rows"],1,1000000);hc::number(l["max_pages"],1,10000);
    return p;
}
__time64_t stamp(const hc::Val& value)
{
    const auto s=hc::text(value,14);need(s.size()==14&&s.substr(12)=="00"
        &&std::all_of(s.begin(),s.end(),[](char c){return c>='0'&&c<='9';}));
    std::tm t{};t.tm_year=std::stoi(s.substr(0,4))-1900;t.tm_mon=std::stoi(s.substr(4,2))-1;
    t.tm_mday=std::stoi(s.substr(6,2));t.tm_hour=std::stoi(s.substr(8,2));t.tm_min=std::stoi(s.substr(10,2));
    const auto n=_mkgmtime64(&t);need(n>=0);char out[32];need(std::strftime(out,sizeof(out),"%Y%m%d%H%M00",&t)>0&&s==out);
    need(s>="20211101000000"&&s<="20991231235900");return n;
}
void arguments(const hc::Val& args,const hc::Val& p)
{
    need(hc::keys(args,{"symbol","start_time","end_time","max_rows"}));
    const auto symbol=hc::text(args["symbol"],9);need(symbol.size()==9&&(symbol.substr(6)==".SZ"||symbol.substr(6)==".SH")
        &&std::all_of(symbol.begin(),symbol.begin()+6,[](char c){return c>='0'&&c<='9';}));
    const auto first=stamp(args["start_time"]),last=stamp(args["end_time"]);need(first<=last);
    const auto& l=p["bulk_profile"]["limits"];need(static_cast<std::uint64_t>(last/86400-first/86400+1)<=l["max_calendar_days"].GetUint64());
    hc::number(args["max_rows"],1,l["max_rows"].GetUint64());
}
void source_profile(const hc::Val& s)
{
    need(hc::keys(s,{"dataset_version","source_license","input_kind","asset_class","timezone","minute_boundary","adjustment","factor_version","value_semantics","price_unit","volume_unit","amount_unit"}));
    hc::label(s["dataset_version"]);hc::label(s["source_license"]);
    need((eq(s["input_kind"],"synthetic")||eq(s["input_kind"],"qmt_export"))&&eq(s["asset_class"],"cash-equity")
        &&eq(s["timezone"],"Asia/Shanghai")&&eq(s["adjustment"],"none")&&eq(s["factor_version"],"")&&eq(s["value_semantics"],"source")
        &&(eq(s["minute_boundary"],"left")||eq(s["minute_boundary"],"right")||eq(s["minute_boundary"],"unknown"))
        &&(eq(s["volume_unit"],"share")||eq(s["volume_unit"],"lot")||eq(s["volume_unit"],"unknown")));
    for(auto key:{"price_unit","amount_unit"})need(eq(s[key],"CNY")||eq(s[key],"unknown"));
}

struct Receipt {hc::Doc binding,body,profile;std::string body_raw,profile_raw;std::size_t result_cap=0,http_cap=0;};
void validate_receipt(Receipt& r,const Config& cfg)
{
    need(codec::binding(r.binding,nullptr,"3.0")&&hc::text(r.binding["capability_sha256"])==cfg.profile_sha);
    r.profile=profile(r.profile_raw,cfg);r.body=hc::parse(r.body_raw,65536);
    need(hc::keys(r.body,{"schema_version","request_id","correlation_id","operation_id","policy_id","policy_version","arguments","snapshot_id","clock_schema","deadline_ms","queue_deadline_ms","priority_class","read_profile_version"})
        &&eq(r.body["schema_version"],"qmt.history-bulk-request.v1")&&eq(r.body["operation_id"],operation)
        &&eq(r.body["policy_id"],"qmt.history-bulk-read.v1")&&eq(r.body["policy_version"],"1.0")
        &&eq(r.body["clock_schema"],"qmt.win-uptime-ms.v1")&&eq(r.body["priority_class"],"normal")
        &&eq(r.body["read_profile_version"],"qmt.read-profile.v5"));
    for(auto key:{"request_id","correlation_id","snapshot_id"})need(codec::uuid(r.body[key]));
    const auto d=hc::number(r.body["deadline_ms"],1,(1ULL<<32)*1000);
    hc::number(r.body["queue_deadline_ms"],1,d);arguments(r.body["arguments"],r.profile);
    need(r.result_cap>0&&r.result_cap<=2097152&&r.http_cap<=cfg.http.max_response_bytes
        &&r.http_cap>=4*((r.result_cap+2)/3)+16384);
}
Receipt prepare(BoundedSignedHttp& http,const Config& cfg,const hc::Val& args,SignedHttpDeadline& end)
{
    hc::check(end,control);const auto answer=http.exchange("GET","/internal/v1/read-binding","",end,16384);
    need(answer.status.ok()&&answer.code==200&&answer.response_complete);
    auto d=hc::parse(answer.body,16384);
    need(hc::keys(d,{"schema_version","binding","binding_sha256","read_profile_body_b64","read_profile_body_sha256","limits","order_ready"})
        &&eq(d["schema_version"],"qmt.bound-read.v1")&&d["order_ready"].IsFalse()
        &&codec::binding(d["binding"],nullptr,"3.0")&&codec::hex(d["binding_sha256"],64)
        &&hc::hash(codec::encode(d["binding"]))==hc::text(d["binding_sha256"]));
    Receipt r;r.binding=copy(d["binding"]);need(codec::unbase64(d["read_profile_body_b64"],4096,r.profile_raw)
        &&hc::hash(r.profile_raw)==hc::text(d["read_profile_body_sha256"]));
    r.profile=profile(r.profile_raw,cfg);arguments(args,r.profile);
    const auto& limits=d["limits"];need(hc::keys(limits,{"max_request_bytes","max_result_bytes","max_http_request_bytes","max_http_response_bytes"}));
    r.result_cap=static_cast<std::size_t>(hc::number(limits["max_result_bytes"],1,2097152));
    r.http_cap=static_cast<std::size_t>(hc::number(limits["max_http_response_bytes"],16384,cfg.http.max_response_bytes));
    r.body.SetObject();hc::add(r.body,"schema_version","qmt.history-bulk-request.v1");
    for(auto key:{"request_id","correlation_id","snapshot_id"})hc::add(r.body,key,hc::uuid());
    hc::add(r.body,"operation_id",operation);hc::add(r.body,"policy_id","qmt.history-bulk-read.v1");hc::add(r.body,"policy_version","1.0");
    hc::add(r.body,"clock_schema","qmt.win-uptime-ms.v1");hc::add(r.body,"priority_class","normal");hc::add(r.body,"read_profile_version","qmt.read-profile.v5");
    member(r.body,"arguments",args);
    // 先取共享钟、后取原剩余D；映射只缩短原期限，持久化/POST不重授。
    const std::uint64_t now=GetTickCount64();const auto remaining=end.remaining();need(remaining>0);
    const auto total=std::min<std::uint64_t>(remaining,r.profile["bulk_profile"]["total_timeout_ms"].GetUint64());
    const auto queued=std::min<std::uint64_t>(total,r.profile["bulk_profile"]["queue_timeout_ms"].GetUint64());
    r.body.AddMember("deadline_ms",now+total,r.body.GetAllocator());r.body.AddMember("queue_deadline_ms",now+queued,r.body.GetAllocator());
    r.body_raw=codec::encode(r.body);need(r.body_raw.size()<=hc::number(limits["max_request_bytes"],1,65536));
    validate_receipt(r,cfg);hc::check(end,control);return r;
}
hc::Doc durable(const Receipt& r,const Config& cfg)
{
    hc::Doc d;d.SetObject();hc::add(d,"schema","qmt.bulk-history-receipt.v1");hc::add(d,"config_sha256",cfg.sha);
    hc::add(d,"binding_json",codec::encode(r.binding));hc::add(d,"request_body",r.body_raw);hc::add(d,"request_body_sha256",hc::hash(r.body_raw));
    hc::add(d,"read_profile_body",r.profile_raw);d.AddMember("max_result_bytes",static_cast<std::uint64_t>(r.result_cap),d.GetAllocator());
    d.AddMember("max_http_response_bytes",static_cast<std::uint64_t>(r.http_cap),d.GetAllocator());return d;
}
Receipt restore(const hc::Doc& d,const Config& cfg)
{
    need(hc::keys(d,{"schema","config_sha256","binding_json","request_body","request_body_sha256","read_profile_body","max_result_bytes","max_http_response_bytes"})
        &&eq(d["schema"],"qmt.bulk-history-receipt.v1")&&hc::text(d["config_sha256"])==cfg.sha);
    Receipt r;r.binding=hc::parse(hc::text(d["binding_json"],4096),4096);r.body_raw=hc::text(d["request_body"],65536);
    need(hc::hash(r.body_raw)==hc::text(d["request_body_sha256"]));r.profile_raw=hc::text(d["read_profile_body"],4096);
    r.result_cap=static_cast<std::size_t>(hc::number(d["max_result_bytes"],1,2097152));
    r.http_cap=static_cast<std::size_t>(hc::number(d["max_http_response_bytes"],16384,cfg.http.max_response_bytes));validate_receipt(r,cfg);return r;
}

struct Outcome {bool terminal=false,ok=false;std::string native,manifest,manifest_sha;std::uint64_t rows=0,pages=0;};
Outcome inspect(const SignedHttpResult& response,const Receipt& r,const Config& cfg,SignedHttpDeadline& end)
{
    Outcome out;
    // 未取得完整可关联结果时只保原收据，由本轮或后续resume继续GET。
    if(!response.response_complete||(response.code!=200&&response.code!=202))return out;
    auto envelope=hc::parse(response.body,r.http_cap);
    need(hc::keys(envelope,{"schema_version","request_id","operation_id","request_sha256","request_body_sha256","binding_status",
        "admitted_binding","dispatch_binding","result_binding","state","result_body_b64","result_body_sha256"})
        &&eq(envelope["schema_version"],"qmt.bound-read.v1")&&eq(envelope["binding_status"],"recorded")
        &&same(envelope["request_id"],r.body["request_id"])&&eq(envelope["operation_id"],operation)
        &&hc::text(envelope["request_body_sha256"])==hc::hash(r.body_raw)&&same(envelope["admitted_binding"],r.binding));
    hc::Doc semantic;semantic.SetObject();hc::add(semantic,"operation_id",operation);member(semantic,"arguments",r.body["arguments"]);
    need(hc::text(envelope["request_sha256"])==hc::hash(codec::encode(semantic)));
    const auto state=hc::text(envelope["state"]);
    need(state=="queued"||state=="executing"||state=="terminal");
    const auto& dispatch=envelope["dispatch_binding"];const auto& result_binding=envelope["result_binding"];
    need(dispatch.IsNull()||same(dispatch,r.binding));need(result_binding.IsNull()||(!dispatch.IsNull()&&same(result_binding,dispatch)));
    if(state!="terminal"){
        need(response.code==202&&envelope["result_body_b64"].IsNull()&&envelope["result_body_sha256"].IsNull()
            &&result_binding.IsNull()&&(state=="queued"?dispatch.IsNull():!dispatch.IsNull()));return out;
    }
    need(response.code==200&&codec::unbase64(envelope["result_body_b64"],r.result_cap,out.native)
        &&hc::hash(out.native)==hc::text(envelope["result_body_sha256"]));
    auto native=hc::parse(out.native,r.result_cap);
    need(hc::keys(native,{"data","error_code","error_message","observation","request_admission_ms","queue_wait_ms","execution_ms",
        "result_persistence_ms","response_wakeup_ms","response_handler_ms","request_id","operation_id","ok","completed_at","result_sha256"})
        &&same(native["request_id"],r.body["request_id"])&&eq(native["operation_id"],operation)&&native["ok"].IsBool()
        &&native["observation"].IsNull()&&codec::hex(native["result_sha256"],64));
    const auto sha=hc::text(native["result_sha256"]);auto unsigned_result=copy(native);unsigned_result.RemoveMember("result_sha256");
    need(hc::hash(codec::encode(unsigned_result))==sha);
    hc::label(native["completed_at"],64);
    for(auto key:{"request_admission_ms","result_persistence_ms","response_wakeup_ms","response_handler_ms"})need(native[key].IsUint64());
    for(auto key:{"queue_wait_ms","execution_ms"})need(native[key].IsNull()||native[key].IsUint64());
    out.terminal=true;out.ok=native["ok"].GetBool();
    if(!out.ok){
        need(native["data"].IsNull());const auto code=hc::text(native["error_code"]);
        need(code=="operation_interrupted"||code=="source_binding_changed"||code=="queue_timeout"||code=="expired"
            ||code=="source_failed"||code=="storage_failed"||code=="invalid_page");
        need(eq(native["error_message"],"批量历史读取未完成；保留原请求标识核查"));return out;
    }
    need(!result_binding.IsNull()&&native["error_code"].IsNull()&&native["error_message"].IsNull());
    const auto& data=native["data"];
    need(hc::keys(data,{"schema","identity","source_session","source_profile","artifact_root_id","relative_root","manifest_path","manifest_sha256","rows","pages","bytes","importable"})
        &&eq(data["schema"],"qmt.history-bulk-artifact.v1")&&hc::text(data["artifact_root_id"])==cfg.root_id);
    const auto& identity=data["identity"];
    need(hc::keys(identity,{"range_id","session_id","snapshot_id","symbol","start_time","end_time"})
        &&same(identity["range_id"],r.body["request_id"])&&same(identity["snapshot_id"],r.body["snapshot_id"])
        &&same(identity["session_id"],r.binding["transport_generation"]));
    for(auto key:{"symbol","start_time","end_time"})need(same(identity[key],r.body["arguments"][key]));
    const auto& session=data["source_session"];
    need(hc::keys(session,{"provider","instance_id","session_id","generation"})&&eq(session["provider"],"Qmt")
        &&same(session["instance_id"],r.binding["host_instance_id"])&&same(session["session_id"],r.binding["transport_generation"])
        &&session["generation"].IsUint64()&&session["generation"].GetUint64()==r.binding["route"]["route_epoch"].GetUint64()+1);
    source_profile(data["source_profile"]);
    const auto relative=hc::text(r.body["request_id"])+"--"+hc::text(r.body["snapshot_id"]);
    need(hc::text(data["relative_root"])==relative);
    out.rows=hc::number(data["rows"],0,r.body["arguments"]["max_rows"].GetUint64());
    out.pages=hc::number(data["pages"],1,r.profile["bulk_profile"]["limits"]["max_pages"].GetUint64());
    const auto bytes=hc::number(data["bytes"],0,(out.pages+1)*2097152);
    need(data["importable"].IsBool()&&data["importable"].GetBool()==(out.rows>0));
    if(!out.rows){need(data["manifest_path"].IsNull()&&data["manifest_sha256"].IsNull()&&!bytes);return out;}
    need(eq(data["manifest_path"],"qmi-manifest.json")&&codec::hex(data["manifest_sha256"],64)&&bytes>0);
    const auto path=cfg.artifacts/hc::fs::u8path(relative)/L"qmi-manifest.json";
    need(hc::under(path,cfg.artifacts));out.manifest=path.u8string();out.manifest_sha=hc::text(data["manifest_sha256"]);
    const auto raw=hc::read(path,2097152,end,control);need(hc::hash(raw)==out.manifest_sha);
    // 本机路径由固定root UUID映射；Manifest仍由原Importer逐chunk读取/核验。
    const auto manifest=hc::parse(raw,2097152);need(hc::keys(manifest,{"schema_version","profile","securities"})
        &&manifest["schema_version"].IsInt()&&manifest["schema_version"].GetInt()==2
        &&manifest["securities"].IsArray()&&manifest["securities"].Size()==1
        &&manifest["securities"][0].IsObject()&&manifest["securities"][0].HasMember("symbol")
        &&same(manifest["securities"][0]["symbol"],identity["symbol"]));
    auto expected=copy(data["source_profile"]);expected.RemoveMember("asset_class");
    for(auto key:{"provider","instance_id","session_id","generation"})member(expected,key,session[key]);
    need(same(manifest["profile"],expected));hc::check(end,control);return out;
}

struct Summary {std::string status="failed",rid,manifest,manifest_sha;std::uint64_t rows=0,pages=0;int code=2,drained=-1;};
void publish(const Summary& s)
{
    hc::Doc d;d.SetObject();hc::add(d,"schema","qmt.bulk-history-cli-result.v1");hc::add(d,"status",s.status);
    hc::add(d,"request_id",s.rid);hc::add(d,"manifest_path",s.manifest);hc::add(d,"manifest_sha256",s.manifest_sha);
    d.AddMember("rows",s.rows,d.GetAllocator());d.AddMember("pages",s.pages,d.GetAllocator());
    if(s.drained<0)d.AddMember("callbacks_drained",hc::Val(),d.GetAllocator());else d.AddMember("callbacks_drained",s.drained==1,d.GetAllocator());
    const auto raw=hc::json(d);need(raw.size()<=16384);std::cout<<raw<<std::endl;
}
int run(int argc,wchar_t** argv)
{
    const auto started=std::chrono::steady_clock::now();SignedHttpDeadline end(started+std::chrono::milliseconds(300000));
    Summary summary;std::unique_ptr<BoundedSignedHttp> http;std::unique_ptr<hc::Store> store;bool saved=false;
    try{
        need(argc>=2);const std::wstring mode=argv[1];need(mode==L"fetch"||mode==L"resume");const bool fresh=mode==L"fetch";
        need(argc==(fresh?8:6));std::map<std::wstring,std::wstring> flags;
        for(int i=2;i<argc;i+=2){const std::wstring key=argv[i];need(key==L"--config"||key==L"--request"||key==L"--run-root");need(flags.emplace(key,argv[i+1]).second);}
        need(flags.count(L"--config")&&flags.count(L"--run-root")&&(fresh?flags.count(L"--request")==1:flags.count(L"--request")==0));
        const auto cfg=load_config(hc::absolute(flags[L"--config"]),end);end.end=started+std::chrono::milliseconds(cfg.limits.total_ms);hc::check(end,control);
        const auto root=hc::absolute(flags[L"--run-root"]);need(hc::under(root,cfg.runs));
        store.reset(new hc::Store(root,cfg.limits,end,control,fresh));Receipt receipt;
        if(!fresh){receipt=restore(hc::parse(hc::read(root/L"receipt.json",1048576,end,control),1048576),cfg);saved=true;}
        http.reset(new BoundedSignedHttp(cfg.http));need(http->check().ok());
        if(fresh){const auto path=hc::absolute(flags[L"--request"]);need(hc::under(path,cfg.requests));
            const auto args=hc::parse(hc::read(path,4096,end,control),4096);receipt=prepare(*http,cfg,args,end);
            store->write_json("receipt.json",durable(receipt,cfg));saved=true;
        }
        summary.rid=hc::text(receipt.body["request_id"]);Outcome outcome;
        if(fresh){
            hc::Doc envelope;envelope.SetObject();hc::add(envelope,"schema_version","qmt.bound-read.v1");
            hc::add(envelope,"binding_sha256",hc::hash(codec::encode(receipt.binding)));
            hc::add(envelope,"request_body_b64",codec::base64(receipt.body_raw));hc::add(envelope,"request_body_sha256",hc::hash(receipt.body_raw));
            hc::check(end,control);
            // 唯一POST点；无论发送回执是否确定，之后只GET原ID。
            const auto answer=http->exchange("POST","/internal/v1/bound-operations/market.history_1m.bulk",codec::encode(envelope),end,receipt.http_cap);
            outcome=inspect(answer,receipt,cfg,end);
        }
        while(!outcome.terminal){
            hc::check(end,control);
            const auto answer=http->exchange("GET","/internal/v1/bound-results/"+summary.rid,"",end,receipt.http_cap);
            outcome=inspect(answer,receipt,cfg,end);
            if(!outcome.terminal){hc::check(end,control);Sleep(std::min<DWORD>(25,end.remaining()));}
        }
        store->write("result-"+hc::uuid()+".json",outcome.native);
        summary.rows=outcome.rows;summary.pages=outcome.pages;summary.manifest=outcome.manifest;summary.manifest_sha=outcome.manifest_sha;
        summary.status=outcome.ok?(outcome.rows?"complete":"empty"):"failed";summary.code=outcome.ok?0:3;
    }catch(const hc::Failure& e){summary.status=saved?"unknown":"failed";summary.code=e.code==130?130:e.code==124?124:saved?4:2;}
    catch(...){summary.status=saved?"unknown":"failed";summary.code=saved?4:2;}
    if(http){const auto drained=http->drain_callbacks(end.remaining());summary.drained=drained.ok()?1:0;
        if(!drained.ok()){summary.status="unknown";if(!summary.code)summary.code=4;http.release();publish(summary);std::_Exit(summary.code);}
        http.reset();
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
    try{return run(argc,argv);}catch(...){std::fputs("{\"schema\":\"qmt.bulk-history-cli-result.v1\",\"status\":\"failed\",\"reason\":\"output_failed\"}\n",stdout);return 2;}
}
