#include "GuanhengCommon/QmtHostReadClient.h"
#include <iostream>
using namespace guanheng;
int main(int argc,char**argv){QmtHttpConfig c;c.base_url=argv[1];c.key_id="synthetic";c.hmac_secret="synthetic";QmtHostReadClient client(c,QmtReadProfileVersion::FullTickRetainedV6);
auto prep=client.prepare(2000);if(!prep.ok()){std::cout<<"{\"prepare_error\":\""<<prep.reason<<"\"}";return 2;}auto origin=client.session();
auto a=client.read_full_tick("{\"stocks\":[\"000001.SZ\"]}",1500);bool invalid=!client.capability().supported;
auto b=client.read_full_tick("{\"stocks\":[\"000001.SZ\"]}",1500);auto now=client.session();
bool restored=client.capability().supported;bool same=origin.instance_id==now.instance_id&&origin.session_id==now.session_id&&origin.generation==now.generation;
const bool old_result=b.result.status.reason=="qmt_host_transport_replaced_after_result";
bool receipt_same=true;if(!old_result && !b.receipt.request_body.empty()){auto r=client.resume(b.receipt,1500);receipt_same=r.receipt.request_body==b.receipt.request_body&&r.receipt.binding_json==b.receipt.binding_json&&r.receipt.retention_ticket_json==b.receipt.retention_ticket_json;}
bool after_rebind_receipt=false;
if(b.result.status.reason=="qmt_host_transport_replaced_before_submit"){
    auto c=client.read_full_tick("{\"stocks\":[\"000001.SZ\"]}",1500);
    after_rebind_receipt=!c.receipt.request_body.empty();
}
bool old_result_consumed=false, old_result_retried=false;
if(old_result && b.snapshot_consumption_ready && !b.result.data_json.empty()){
    auto ack=client.confirm_full_tick(b,1500);
    if(!ack.ok()){old_result_retried=true;ack=client.confirm_full_tick(b,1500);}
    old_result_consumed=ack.ok();
}
auto drain=client.drain_callbacks(2000);
std::cout<<"{\"prepare\":true,\"first_empty\":"<<a.receipt.request_body.empty()<<",\"invalidated\":"<<invalid<<",\"second_receipt\":"<<!b.receipt.request_body.empty()<<",\"second_code\":"<<int(b.result.status.code)<<",\"second_reason\":\""<<b.result.status.reason<<"\",\"restored\":"<<restored<<",\"same_origin\":"<<same<<",\"receipt_same\":"<<receipt_same<<",\"after_rebind_receipt\":"<<after_rebind_receipt<<",\"old_result_consumed\":"<<old_result_consumed<<",\"old_result_retried\":"<<old_result_retried<<",\"drained\":"<<drain.ok()<<"}";}
