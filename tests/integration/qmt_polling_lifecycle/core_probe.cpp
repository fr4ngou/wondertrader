#include "GuanhengCommon/QmtHostReadClient.h"
#include <iostream>
using namespace guanheng;
int main(int argc,char**argv){QmtHttpConfig c;c.base_url=argv[1];c.key_id="synthetic";c.hmac_secret="synthetic";QmtHostReadClient client(c,QmtReadProfileVersion::FullTickRetainedV6);
auto prep=client.prepare(2000);if(!prep.ok()){std::cout<<"{\"prepare_error\":\""<<prep.reason<<"\"}";return 2;}auto origin=client.session();
auto a=client.read_full_tick("{\"stocks\":[\"000001.SZ\"]}",1500);bool invalid=!client.capability().supported;
auto b=client.read_full_tick("{\"stocks\":[\"000001.SZ\"]}",1500);auto now=client.session();
bool restored=client.capability().supported;bool same=origin.instance_id==now.instance_id&&origin.session_id==now.session_id&&origin.generation==now.generation;
bool receipt_same=true;if(!b.receipt.request_body.empty()){auto r=client.resume(b.receipt,1500);receipt_same=r.receipt.request_body==b.receipt.request_body&&r.receipt.binding_json==b.receipt.binding_json&&r.receipt.retention_ticket_json==b.receipt.retention_ticket_json;}
auto drain=client.drain_callbacks(2000);
std::cout<<"{\"prepare\":true,\"first_empty\":"<<a.receipt.request_body.empty()<<",\"invalidated\":"<<invalid<<",\"second_receipt\":"<<!b.receipt.request_body.empty()<<",\"second_code\":"<<int(b.result.status.code)<<",\"second_reason\":\""<<b.result.status.reason<<"\",\"restored\":"<<restored<<",\"same_origin\":"<<same<<",\"receipt_same\":"<<receipt_same<<",\"drained\":"<<drain.ok()<<"}";}
