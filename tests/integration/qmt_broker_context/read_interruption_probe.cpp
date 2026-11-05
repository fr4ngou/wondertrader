#include "TraderQMT/StandardReadFailure.h"
#include <fstream>
#include <iterator>
#include <stdexcept>
#include <string>
#include <iostream>

int main(int argc,char** argv)
{
 if(argc!=2)return 2;
 std::ifstream input(argv[1],std::ios::binary);std::string raw((std::istreambuf_iterator<char>(input)),{});
 rapidjson::Document fixture;fixture.Parse(raw.data(),raw.size());
 if(fixture.HasParseError()||!fixture.IsObject()||!fixture.HasMember("native")||!fixture.HasMember("envelope"))return 3;
 const auto& native=fixture["native"];const auto& envelope=fixture["envelope"];
 using guanheng::standard_read_failure::interrupted_account_read;
 unsigned passed=0;
 auto check=[&](bool condition){if(!condition)throw std::runtime_error("read interruption qualification failed");++passed;};
 check(interrupted_account_read(native,envelope));
 auto rejected=[&](const char* field,const char* replacement){
  rapidjson::Document changed;changed.CopyFrom(native,changed.GetAllocator());
  changed[field].SetString(replacement,changed.GetAllocator());check(!interrupted_account_read(changed,envelope));
 };
 rejected("error_code","qmt_call_failed");rejected("error_code","source_shape_invalid");
 rejected("error_code","queue_timeout");rejected("operation_id","trade.submit");
 rejected("request_id","different-original-request");
 rapidjson::Document changed;changed.CopyFrom(envelope,changed.GetAllocator());
 changed["result_binding"].CopyFrom(envelope["dispatch_binding"],changed.GetAllocator());
 check(!interrupted_account_read(native,changed));
 changed.CopyFrom(envelope,changed.GetAllocator());changed["dispatch_binding"].SetNull();
 check(!interrupted_account_read(native,changed));
 changed.CopyFrom(native,changed.GetAllocator());changed["ok"].SetBool(true);check(!interrupted_account_read(changed,envelope));
 changed.CopyFrom(native,changed.GetAllocator());changed["data"].SetObject();check(!interrupted_account_read(changed,envelope));
 std::cout<<"{\"passed\":"<<passed<<",\"actual_interrupted_query\":true,\"other_failure_and_write_rejected\":true}\n";
 return 0;
}
