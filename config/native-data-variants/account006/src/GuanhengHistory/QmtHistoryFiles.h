#pragma once
#include "../GuanhengCommon/QmtHostHistoryClient.h"
#include <rapidjson/document.h>
#include <rapidjson/stringbuffer.h>
#include <rapidjson/writer.h>
#include <windows.h>
#include <algorithm>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <stdexcept>
#include <map>
#include <set>
#include <cmath>
#include <limits>
#include <locale>

// CLI-owned bounded files/plan projection. Network, binding and history data
// admission belong to QmtBoundReadCore; DSB encoding remains the existing QMI.
namespace guanheng { namespace history_cli {
namespace fs=std::filesystem;
using Doc=rapidjson::Document;using Val=rapidjson::Value;
struct Failure:std::exception{const char* reason;int code;Failure(const char* r,int c=2):reason(r),code(c){}const char* what()const noexcept override{return reason;}};
inline void require(bool value,const char* reason="历史读取输入不合格",int code=2){if(!value)throw Failure(reason,code);}
inline void check(SignedHttpDeadline& end,const QmtHistoryControl& control)
{if(control.stop_requested())throw Failure("历史读取已中断，保留原编号供核查",130);if(!end.remaining())throw Failure("历史读取总期限耗尽，保留原编号供核查",124);}
inline bool keys(const Val& v,std::initializer_list<const char*> names)
{if(!v.IsObject()||v.MemberCount()!=names.size())return false;for(auto n:names)if(!v.HasMember(n))return false;return true;}
inline std::string text(const Val& v,std::size_t max=256)
{require(v.IsString()&&v.GetStringLength()>0&&v.GetStringLength()<=max);std::string s(v.GetString(),v.GetStringLength());require(s.find('\0')==std::string::npos);return s;}
inline std::string label(const Val& v,std::size_t max=256)
{auto s=text(v,max);require(std::none_of(s.begin(),s.end(),[](unsigned char c){return c<32||c==127;}));return s;}
inline std::uint64_t number(const Val& v,std::uint64_t min,std::uint64_t max)
{require(v.IsUint64()&&v.GetUint64()>=min&&v.GetUint64()<=max);return v.GetUint64();}
inline std::string json(const Val& v)
{rapidjson::StringBuffer b;rapidjson::Writer<rapidjson::StringBuffer,rapidjson::UTF8<>,rapidjson::ASCII<>> w(b);require(v.Accept(w));return {b.GetString(),b.GetSize()};}
inline void add(Doc& d,const char* k,const std::string& v)
{auto& a=d.GetAllocator();d.AddMember(Val(k,a),Val(v.data(),static_cast<rapidjson::SizeType>(v.size()),a),a);}
inline std::string hash(const std::string& value)
{auto out=signed_http_sha256(value);require(out.size()==64,"历史读取摘要依赖不可用");return out;}
inline void no_reparse(fs::path p,bool final_may_miss=false)
{
    bool first=true;
    while(!p.empty()){
        const auto attrs=GetFileAttributesW(p.c_str());
        if(attrs==INVALID_FILE_ATTRIBUTES){require(first&&final_may_miss&&(GetLastError()==ERROR_FILE_NOT_FOUND||GetLastError()==ERROR_PATH_NOT_FOUND),"历史读取路径不可访问");}
        else require(!(attrs&FILE_ATTRIBUTE_REPARSE_POINT),"历史读取路径含重解析点");
        const auto parent=p.parent_path();if(parent==p)break;p=parent;first=false;
    }
}
inline fs::path absolute(const std::wstring& value)
{fs::path p(value);require(p.is_absolute(),"历史读取路径需要绝对路径");p=p.lexically_normal();require(p.native().size()<240,"历史读取路径超过受管长度");return p;}
inline bool same_path(const fs::path& a,const fs::path& b)
{return CompareStringOrdinal(a.c_str(),-1,b.c_str(),-1,TRUE)==CSTR_EQUAL;}
inline bool under(const fs::path& child,const fs::path& root)
{
    auto c=child.begin(),r=root.begin();for(;r!=root.end();++r,++c)if(c==child.end()||!same_path(*c,*r))return false;
    return c!=child.end();
}
inline std::string read(const fs::path& p,std::size_t cap,SignedHttpDeadline& end,const QmtHistoryControl& control)
{
    check(end,control);no_reparse(p);require(fs::is_regular_file(p),"历史读取需要普通输入文件");
    require(fs::file_size(p)<=cap,"历史读取输入超过容量");std::ifstream in(p,std::ios::binary);require(bool(in),"历史读取输入无法打开");
    std::string out;char chunk[4096];while(in){check(end,control);in.read(chunk,sizeof(chunk));const auto n=in.gcount();require(out.size()+n<=cap,"历史读取输入超过容量");out.append(chunk,static_cast<std::size_t>(n));}
    require(in.eof(),"历史读取输入失败");check(end,control);return out;
}
inline Doc parse(const std::string& raw,std::size_t cap)
{Doc d;require(parse_bounded_qmt_json(raw,d,cap,cap),"历史读取JSON结构不合格");return d;}
struct Limits{std::uint32_t total_ms=0,pages=0,rows=0,files=0;std::size_t bytes=0;};
struct Config{
    QmtHttpConfig http;fs::path request_root,runs_root;Limits limits;Doc source;std::string sha;
    // 配置模式只决定导出语义；线上读取 profile 与真实 SourceSession 独立拥有身份。
    bool source_values=false;
    // CLI 拥有显式版本选择；省略字段沿原 v2，完整 profile 仍由共用客户端核验。
    QmtReadProfileVersion read_profile_version=QmtReadProfileVersion::Legacy;
};
inline Config config(const fs::path& path,SignedHttpDeadline& end,const QmtHistoryControl& control)
{
    const auto raw=read(path,1024*1024,end,control);auto d=parse(raw,1024*1024);Config out;
    require(keys(d,{"schema","http","request_root","runs_root","limits","source_profile"})
        ||keys(d,{"schema","http","request_root","runs_root","limits","source_profile","read_profile_version"}));
    const auto schema=text(d["schema"]);
    require(schema=="qmt.history-cli-config.v1"||schema=="qmt.history-cli-config.v2");
    out.source_values=schema=="qmt.history-cli-config.v2";
    if(d.HasMember("read_profile_version")){
        const auto version=text(d["read_profile_version"],32);
        require(version=="qmt.read-profile.v2"||version=="qmt.read-profile.v3","历史读取配置版本不合格");
        if(version=="qmt.read-profile.v3")out.read_profile_version=QmtReadProfileVersion::AccountV3;
    }
    const auto& h=d["http"];require(keys(h,{"base_url","key_id","hmac_secret","timeout_ms","max_response_bytes"}));
    out.http={text(h["base_url"],2048),text(h["key_id"],128),text(h["hmac_secret"],8192),
        static_cast<std::uint32_t>(number(h["timeout_ms"],1,30000)),static_cast<std::size_t>(number(h["max_response_bytes"],16384,16*1024*1024))};
    out.request_root=absolute(fs::u8path(text(d["request_root"],1024)).wstring());out.runs_root=absolute(fs::u8path(text(d["runs_root"],1024)).wstring());
    no_reparse(out.request_root);no_reparse(out.runs_root);require(fs::is_directory(out.request_root)&&fs::is_directory(out.runs_root));
    const auto& l=d["limits"];require(keys(l,{"total_ms","max_pages","max_total_rows","max_output_bytes","max_output_files"}));
    out.limits={static_cast<std::uint32_t>(number(l["total_ms"],100,300000)),static_cast<std::uint32_t>(number(l["max_pages"],1,4096)),
        static_cast<std::uint32_t>(number(l["max_total_rows"],1,1000000)),static_cast<std::uint32_t>(number(l["max_output_files"],1,32768)),
        static_cast<std::size_t>(number(l["max_output_bytes"],1024,268435456))};
    const auto& s=d["source_profile"];
    if(out.source_values)
        require(keys(s,{"dataset_version","source_license","input_kind","asset_class","timezone","minute_boundary","adjustment","factor_version","value_semantics","price_unit","volume_unit","amount_unit"}));
    else
        require(keys(s,{"dataset_version","source_license","input_kind","asset_class","timezone","minute_boundary","volume_to_shares","amount_to_yuan","adjustment","factor_version"}));
    label(s["dataset_version"]);label(s["source_license"]);
    require(text(s["input_kind"])=="synthetic"||text(s["input_kind"])=="qmt_export");
    require(text(s["asset_class"])=="cash-equity"&&text(s["timezone"])=="Asia/Shanghai"&&text(s["adjustment"])=="none"
        &&s["factor_version"].IsString()&&s["factor_version"].GetStringLength()==0);
    if(out.source_values){
        const auto boundary=text(s["minute_boundary"]),volume=text(s["volume_unit"]);
        require(text(s["value_semantics"])=="source"&&(boundary=="left"||boundary=="right"||boundary=="unknown")
            &&(volume=="share"||volume=="lot"||volume=="unknown"));
        for(auto k:{"price_unit","amount_unit"}){const auto unit=text(s[k]);require(unit=="CNY"||unit=="unknown");}
    }else{
        require(s["minute_boundary"].IsNull()||text(s["minute_boundary"])=="left"||text(s["minute_boundary"])=="right");
        for(auto k:{"volume_to_shares","amount_to_yuan"})require(s[k].IsNull()||(s[k].IsNumber()&&std::isfinite(s[k].GetDouble())&&s[k].GetDouble()>0));
    }
    out.source.CopyFrom(s,out.source.GetAllocator());out.sha=hash(raw);check(end,control);return out;
}
inline QmtHistoryRequest window(const Val& value)
{
    require(keys(value,{"symbol","start_time","end_time","max_rows"}));
    return {text(value["symbol"],9),text(value["start_time"],14),text(value["end_time"],14),static_cast<std::uint32_t>(number(value["max_rows"],1,2000))};
}
inline Doc window_json(const QmtHistoryRequest& r)
{Doc d;d.SetObject();add(d,"symbol",r.symbol);add(d,"start_time",r.start_time);add(d,"end_time",r.end_time);d.AddMember("max_rows",r.max_rows,d.GetAllocator());return d;}
struct PageTask{QmtHistoryRequest request;std::string name,parent;};
struct Plan{std::vector<PageTask> tasks;bool split=false;};
inline Plan plan(const Doc& d,unsigned max_pages,SignedHttpDeadline& end,const QmtHistoryControl& control)
{
    require(keys(d,{"schema","windows","pagination"})&&text(d["schema"])=="qmt.history-plan.v1"&&d["windows"].IsArray()
        &&!d["windows"].Empty()&&d["windows"].Size()<=max_pages);
    const auto kind=text(d["pagination"]);require(kind=="none"||kind=="bisect-saturated-v1");Plan p;p.split=kind!="none";
    std::map<std::string,std::vector<std::pair<std::string,std::string>>> ranges;
    unsigned i=0;for(const auto& r:d["windows"].GetArray()){
        check(end,control);
        auto w=window(r);require(w.symbol.size()==9&&w.start_time.size()==14&&w.end_time.size()==14&&w.start_time<=w.end_time);
        auto& group=ranges[w.symbol];for(const auto& old:group){check(end,control);require(w.end_time<old.first||w.start_time>old.second,"历史请求窗口重叠");}
        group.emplace_back(w.start_time,w.end_time);p.tasks.push_back({std::move(w),"page-"+std::to_string(++i),""});
    }return p;
}
struct Handle{HANDLE value=INVALID_HANDLE_VALUE;Handle()=default;explicit Handle(HANDLE h):value(h){}~Handle(){if(value!=INVALID_HANDLE_VALUE)CloseHandle(value);}Handle(const Handle&)=delete;Handle& operator=(const Handle&)=delete;};
class Store
{
    fs::path root_;Limits limits_;std::uint64_t bytes_=0,files_=0,rows_=0;
    SignedHttpDeadline& end_;const QmtHistoryControl& control_;
    std::uint64_t retained_rows(const fs::path& file,const std::string& raw)
    {
        if(file.filename()!=L"native.json")return 0;
        check(end_,control_);Doc d;
        // Capacity accounting counts repeated retained observations too; it does
        // not grant a raw result any semantic or source qualification.
        if(!parse_bounded_qmt_json(raw,d,2097152,2097152)||!d.IsObject()||!d.HasMember("data")
            ||!d["data"].IsObject()||!d["data"].HasMember("rows")||!d["data"]["rows"].IsArray())return 0;
        check(end_,control_);return d["data"]["rows"].Size();
    }
public:
    Handle lock;
    Store(fs::path root,Limits limits,SignedHttpDeadline& end,const QmtHistoryControl& control,bool fresh)
        :root_(std::move(root)),limits_(limits),end_(end),control_(control)
    {
        no_reparse(root_,fresh);if(fresh)require(CreateDirectoryW(root_.c_str(),nullptr)!=0,"历史运行目录已存在或无法创建");
        require(fs::is_directory(root_),"历史运行目录不可用");
        lock.value=CreateFileW((root_/L"owner.lock").c_str(),GENERIC_READ|GENERIC_WRITE,0,nullptr,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL|FILE_FLAG_OPEN_REPARSE_POINT,nullptr);
        require(lock.value!=INVALID_HANDLE_VALUE,"历史运行正在使用或锁不可用");
        std::vector<fs::path> pending{root_};unsigned dirs=0;
        while(!pending.empty()){
            check(end_,control_);auto current=pending.back();pending.pop_back();require(++dirs<=32768,"历史输出目录超过容量");
            for(const auto& e:fs::directory_iterator(current)){
                check(end_,control_);no_reparse(e.path());
                if(e.is_directory()){
                    require(pending.size()<32768-dirs,"历史输出目录超过容量");pending.push_back(e.path());
                }else{require(e.is_regular_file());bytes_+=e.file_size();++files_;
                    if(e.path().filename()==L"native.json")rows_+=retained_rows(e.path(),read(e.path(),2097152,end_,control_));}
                require(files_<=limits_.files&&bytes_<=limits_.bytes,"历史累计输出超过容量");
                require(rows_<=limits_.rows,"历史累计保留行数超过容量");
            }
        }
    }
    fs::path root()const{return root_;}
    fs::path path(const std::string& relative)const
    {auto p=(root_/fs::u8path(relative)).lexically_normal();require(under(p,root_),"历史输出路径越界");return p;}
    void directory(const std::string& relative)
    {check(end_,control_);auto p=path(relative);no_reparse(p,true);require(CreateDirectoryW(p.c_str(),nullptr)!=0,"历史输出目录已存在或无法创建");}
    void write(const std::string& relative,const std::string& raw)
    {
        check(end_,control_);require(files_+1<=limits_.files&&raw.size()<=limits_.bytes-bytes_,"历史累计输出超过容量");
        const auto target=path(relative);no_reparse(target,true);require(!fs::exists(target),"历史输出原件已存在");
        const auto rows=retained_rows(target,raw);require(rows<=limits_.rows-rows_,"历史累计保留行数超过容量");
        const auto id=signed_http_uuid();require(!id.empty(),"历史文件身份依赖不可用");const auto temp=target.parent_path()/fs::u8path(".pending-"+id);
        {Handle h(CreateFileW(temp.c_str(),GENERIC_WRITE,0,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL|FILE_FLAG_WRITE_THROUGH,nullptr));
            require(h.value!=INVALID_HANDLE_VALUE,"历史原件无法写入");
            std::size_t offset=0;while(offset<raw.size()){
                check(end_,control_);DWORD done=0;const auto n=static_cast<DWORD>(std::min<std::size_t>(65536,raw.size()-offset));
                require(WriteFile(h.value,raw.data()+offset,n,&done,nullptr)&&done==n,"历史原件写入失败");offset+=done;
            }
            require(FlushFileBuffers(h.value)!=0,"历史原件持久确认失败");
        }
        check(end_,control_);require(MoveFileExW(temp.c_str(),target.c_str(),MOVEFILE_WRITE_THROUGH)!=0,"历史原件原子发布失败");
        bytes_+=raw.size();++files_;rows_+=rows;
    }
    void write_json(const std::string& path,const Val& value){write(path,json(value));}
};
inline std::string uuid(){auto id=signed_http_uuid();require(!id.empty(),"历史身份依赖不可用");return id;}
inline bool uuid_shape(const std::string& value)
{if(value.size()!=36)return false;for(std::size_t i=0;i<36;++i){if(i==8||i==13||i==18||i==23){if(value[i]!='-')return false;}
    else if(!((value[i]>='0'&&value[i]<='9')||(value[i]>='a'&&value[i]<='f')))return false;}return true;}
inline Doc receipt_json(const QmtPreparedHistoryRead& token,const PageTask& task)
{
    Doc d;d.SetObject();add(d,"schema","qmt.history-page-receipt.v1");add(d,"page",task.name);add(d,"parent",task.parent);
    add(d,"binding_json",token.receipt().binding_json);add(d,"request_body",token.receipt().request_body);
    add(d,"request_body_sha256",hash(token.receipt().request_body));add(d,"read_profile_body",token.read_profile_body());
    add(d,"read_profile_body_sha256",hash(token.read_profile_body()));return d;
}
inline QmtBoundReceipt receipt(const Doc& d)
{
    require(keys(d,{"schema","page","parent","binding_json","request_body","request_body_sha256","read_profile_body","read_profile_body_sha256"})
        &&text(d["schema"])=="qmt.history-page-receipt.v1");
    const auto body=text(d["request_body"],65536),profile=text(d["read_profile_body"],4096),binding=text(d["binding_json"],4096);
    require(hash(body)==text(d["request_body_sha256"])&&hash(profile)==text(d["read_profile_body_sha256"]));
    auto b=parse(binding,4096);require(b.IsObject()&&b.HasMember("capability_sha256")&&text(b["capability_sha256"])==hash(profile));
    return {binding,body};
}
inline void save_result(Store& store,const std::string& dir,const QmtHistoryResult& value)
{
    Doc d;d.SetObject();add(d,"schema","qmt.history-page-result.v1");
    d.AddMember("code",static_cast<unsigned>(value.bound.result.status.code),d.GetAllocator());
    add(d,"reason",value.bound.result.status.reason);add(d,"request_id",value.bound.result.request_id);
    d.AddMember("terminal",value.bound.result.terminal,d.GetAllocator());d.AddMember("remote_ok",value.bound.result.remote_ok,d.GetAllocator());
    add(d,"remote_error_code",value.remote_error_code);
    if(!value.bound.native_result_json.empty()){store.write(dir+"/native.json",value.bound.native_result_json);add(d,"native_sha256",hash(value.bound.native_result_json));}
    else d.AddMember("native_sha256",Val(),d.GetAllocator());
    if(!value.bound.result.envelope_json.empty()){store.write(dir+"/envelope.json",value.bound.result.envelope_json);add(d,"envelope_sha256",hash(value.bound.result.envelope_json));}
    else d.AddMember("envelope_sha256",Val(),d.GetAllocator());
    store.write_json(dir+"/result.json",d);
}
} }
