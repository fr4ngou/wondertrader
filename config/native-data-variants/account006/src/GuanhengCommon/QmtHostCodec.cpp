#include "QmtHostCodec.h"
#include <rapidjson/stringbuffer.h>
#include <rapidjson/writer.h>
#include <algorithm>
#include <cstring>
#include <vector>

namespace guanheng { namespace qmt_host_codec {
using Value=rapidjson::Value;
std::string text(const Value& value) { return {value.GetString(),value.GetStringLength()}; }
bool string(const Value& value,std::size_t maximum)
{ return value.IsString()&&value.GetStringLength()>0&&value.GetStringLength()<=maximum
    &&!std::memchr(value.GetString(),0,value.GetStringLength()); }
bool field(const Value& value,const char* name,std::size_t maximum)
{ return value.IsObject()&&value.HasMember(name)&&string(value[name],maximum); }
bool keys(const Value& value,std::initializer_list<const char*> expected)
{
    if(!value.IsObject()||value.MemberCount()!=expected.size())return false;
    for(auto key:expected)if(!value.HasMember(key))return false;
    return true;
}
bool hex(const Value& value,std::size_t length)
{
    return string(value,length)&&value.GetStringLength()==length
        &&std::all_of(value.GetString(),value.GetString()+length,[](char c){return(c>='0'&&c<='9')||(c>='a'&&c<='f');});
}
template<class Writer>void write(const Value& value,Writer& writer)
{
    if(value.IsObject()){
        std::vector<const Value::Member*> members;
        for(auto it=value.MemberBegin();it!=value.MemberEnd();++it)members.push_back(&*it);
        std::sort(members.begin(),members.end(),[](auto a,auto b){return text(a->name)<text(b->name);});
        writer.StartObject();for(auto item:members){writer.Key(item->name.GetString(),item->name.GetStringLength());write(item->value,writer);}writer.EndObject();
    }else if(value.IsArray()){writer.StartArray();for(const auto& item:value.GetArray())write(item,writer);writer.EndArray();}
    else value.Accept(writer);
}
std::string encode(const Value& value)
{
    rapidjson::StringBuffer buffer;rapidjson::Writer<rapidjson::StringBuffer> writer(buffer);write(value,writer);
    std::string output{buffer.GetString(),buffer.GetSize()};
    // Python canonical使用小写unicode转义；只改真正的转义，不改字面量"\\u"文本。
    for(std::size_t i=0;i<output.size();++i)if(output[i]=='\\'&&i+1<output.size()){
        if(output[++i]=='u'&&i+4<output.size())for(unsigned n=0;n<4;++n){auto& c=output[++i];if(c>='A'&&c<='F')c=static_cast<char>(c-'A'+'a');}
    }
    return output;
}
std::string base64(const std::string& input)
{
    const char* alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    std::string output;output.reserve((input.size()+2)/3*4);
    for(std::size_t i=0;i<input.size();i+=3){
        const auto a=static_cast<unsigned char>(input[i]);
        const auto b=i+1<input.size()?static_cast<unsigned char>(input[i+1]):0;
        const auto c=i+2<input.size()?static_cast<unsigned char>(input[i+2]):0;
        output+=alphabet[a>>2];output+=alphabet[((a&3)<<4)|(b>>4)];
        output+=i+1<input.size()?alphabet[((b&15)<<2)|(c>>6)]:'=';output+=i+2<input.size()?alphabet[c&63]:'=';
    }return output;
}
bool unbase64(const Value& value,std::size_t maximum,std::string& output)
{
    if(!value.IsString()||value.GetStringLength()>(maximum+2)/3*4||value.GetStringLength()%4)return false;
    auto digit=[](char c)->int{if(c>='A'&&c<='Z')return c-'A';if(c>='a'&&c<='z')return c-'a'+26;if(c>='0'&&c<='9')return c-'0'+52;if(c=='+')return 62;if(c=='/')return 63;return -1;};
    output.clear();output.reserve(std::min(maximum,std::size_t(value.GetStringLength()/4*3)));
    for(std::size_t i=0;i<value.GetStringLength();i+=4){
        int a=digit(value.GetString()[i]),b=digit(value.GetString()[i+1]);
        int c=value.GetString()[i+2]=='='?0:digit(value.GetString()[i+2]);
        int d=value.GetString()[i+3]=='='?0:digit(value.GetString()[i+3]);
        if(a<0||b<0||c<0||d<0)return false;
        output+=static_cast<char>((a<<2)|(b>>4));
        if(value.GetString()[i+2]!='=')output+=static_cast<char>((b<<4)|(c>>2));
        if(value.GetString()[i+3]!='=')output+=static_cast<char>((c<<6)|d);
    }return output.size()<=maximum&&base64(output)==text(value);
}
bool uuid(const Value& value)
{
    if(!string(value,36)||value.GetStringLength()!=36)return false;
    for(unsigned i=0;i<36;++i){char c=value.GetString()[i];if(i==8||i==13||i==18||i==23){if(c!='-')return false;}
        else if(!((c>='0'&&c<='9')||(c>='a'&&c<='f')))return false;}
    return true;
}
bool binding(const Value& value,SourceSession* source,const char* expected_version)
{
    if(!expected_version||(std::strcmp(expected_version,"1.0")!=0&&std::strcmp(expected_version,"2.0")!=0
        &&std::strcmp(expected_version,"3.0")!=0))return false;
    if(!keys(value,{"schema_version","route","transport_generation","host_instance_id","journal_generation","observation_identity","capability_sha256"})
        ||!field(value,"schema_version")||text(value["schema_version"])!=expected_version
        ||!hex(value["transport_generation"],32)||!hex(value["host_instance_id"],32)||!hex(value["capability_sha256"],64)
        ||!value["journal_generation"].IsNull()||!value["observation_identity"].IsNull())return false;
    const auto& route=value["route"];
    // 原identity限制Unicode字符数128；SAX已验UTF8，不能把它误改为128字节。
    auto route_text=[](const Value& item){
        if(!item.IsString()||!item.GetStringLength()||item.GetStringLength()>512)return false;
        std::size_t characters=0;for(unsigned i=0;i<item.GetStringLength();++i)
            if((static_cast<unsigned char>(item.GetString()[i])&0xc0)!=0x80)++characters;
        return characters<=128;
    };
    if(!keys(route,{"route_id","executor_id","route_epoch"})||!route_text(route["route_id"])||!route_text(route["executor_id"])
        ||!route["route_epoch"].IsUint64()||route["route_epoch"].GetUint64()>=(1ULL<<53))return false;
    if(encode(value).size()>4096)return false;
    if(source)*source={ProviderKind::Qmt,text(value["host_instance_id"]),text(value["transport_generation"]),route["route_epoch"].GetUint64()+1};
    return true;
}
} }
