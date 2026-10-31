"""停止发生在首次POST之前：原slot准入继续一次派发，恢复只核同ID。"""
from pathlib import Path
import json,tempfile,time,unittest
from unittest.mock import patch
from guanheng_analysis_window_producer.source import BoundAnalysisClient,SourcePending
from guanheng_analysis_window_producer.preparation import DailyHistoryPreparation
from integrations.guanheng.source_history_transport import BoundHistorySource,SourcePending as TransportPending
from guanheng_qmt_shm import bound
from guanheng_qmt_shm_agent.protocol import canonical,decode
CONFIG=dict(base_url="http://127.0.0.1:1",key_id="close-fixture",secret_env="CLOSE_FIXTURE_SECRET",timeout=1)
ENV={"CLOSE_FIXTURE_SECRET":"isolated-close-admission-secret-00000"};CAP=dict(schema="qmt.read-retention.v1",max_lifetime_ms=300000)
class Wire:
 def __init__(self,kind,retained):
  self.metadata=json.loads((Path(__file__).parent/"fixtures"/kind/"BINDING.json").read_bytes());self.posts=[];self.lookups=[];self.results={}
  if not retained:
   profile=self.metadata["profile"];profile.pop("read_retention",None);raw=canonical(profile);self.metadata["read_profile_body_b64"]=bound.b64(raw);self.metadata["read_profile_body_sha256"]=bound.digest(raw);self.metadata["binding"]["capability_sha256"]=bound.digest(raw);self.metadata["binding_sha256"]=bound.digest(canonical(self.metadata["binding"]))
 def exchange(self,owner,method,path,body,deadline):
  if path.endswith("read-binding"):return 200,{k:v for k,v in self.metadata.items()if k!="profile"}
  if path.endswith("read-retention-status"):return 200,dict(retained=0,capacity=8)
  if path.startswith("/internal/v1/bound-operations/"):
   envelope=decode(body);raw=bound.unb64(envelope["request_body_b64"],8192);request=decode(raw);rid=request["request_id"];self.posts.append(rid);data={}
   if request["operation_id"]=="market.history_prepare":
    a=request["arguments"];data=dict(schema="qmt.history-preparation-result.v1",symbol=a["symbol"],period="1d",start_time=a["start_time"],end_time=a["end_time"],effect="call_returned",coverage="unknown")
   reply=dict(request_id=rid,operation_id=request["operation_id"],ok=True,error_code=None,data=data);reply["result_sha256"]=bound.digest(canonical(reply));reply_raw=canonical(reply)
   self.results[rid]=dict(schema_version=bound.SCHEMA,request_id=rid,operation_id=request["operation_id"],request_sha256=bound.digest(raw),request_body_sha256=bound.digest(raw),binding_status="recorded",admitted_binding=self.metadata["binding"],dispatch_binding=self.metadata["binding"],result_binding=self.metadata["binding"],state="terminal",result_body_b64=bound.b64(reply_raw),result_body_sha256=bound.digest(reply_raw))
   raise TransportPending("reply lost after one source call")
  if path.endswith("/consumed"):
   rid=path.split("/")[-2];return 200,dict(schema="qmt.read-consumed-result.v1",request_id=rid,consumed=True)
  rid=path.split("/")[-2]if path.endswith("/lookup")else path.split("/")[-1];self.lookups.append(rid);return (200,self.results[rid])if rid in self.results else(404,{})
class AdmissionBoundary(unittest.TestCase):
 def test_current_first_post_keeps_first_close_deadline_and_one_dispatch(self):
  client=BoundAnalysisClient(CONFIG,environ=ENV);transport=client.transport;original=time.monotonic()+10;first=time.monotonic()+1;seen=[]
  transport.admit_read(original);client.request_close(deadline=first);client.request_close(deadline=first+20)
  with patch.object(BoundHistorySource,"exchange",lambda owner,method,path,body,deadline:(seen.append(deadline)or(202,{}))):
   transport.exchange("POST","/internal/v1/bound-operations/market.divid_factors",b"{}",original)
   self.assertEqual(seen,[first])
   with self.assertRaises(SourcePending):transport.exchange("POST","/internal/v1/bound-operations/market.divid_factors",b"{}",original)
   with self.assertRaises(SourcePending):transport.admit_read(original)
 def test_analysis_legacy_and_retained_stop_after_plan(self):
  for retained in(False,True):
   with self.subTest(retained=retained),tempfile.TemporaryDirectory()as d:
    wire=Wire("close_retained",retained);configuration=dict(CONFIG,**(dict(read_retention=CAP)if retained else{}));client=BoundAnalysisClient(configuration,environ=ENV);slot=Path(d)/"slot.json";original_plan=BoundHistorySource.plan;cancel=[True]
    def plan(owner,*args):
     record=original_plan(owner,*args)
     if cancel[0]:cancel[0]=False;client.request_close(deadline=time.monotonic()+1)
     return record
    with patch.object(BoundHistorySource,"exchange",lambda owner,*a:wire.exchange(owner,*a)),patch.object(BoundHistorySource,"plan",plan):
     with self.assertRaises(SourcePending):client.read("market.divid_factors",dict(symbol="159780.SZ"),slot,deadline=time.monotonic()+5)
     record=json.loads(slot.read_bytes());rid=record["request"]["request_id"];self.assertEqual(wire.posts,[rid]);self.assertTrue(record["attempted"])
     resumed=BoundAnalysisClient(configuration,environ=ENV).read("market.divid_factors",dict(symbol="159780.SZ"),slot,deadline=time.monotonic()+5)
     self.assertEqual(resumed["request_id"],rid);self.assertEqual(wire.posts,[rid]);self.assertEqual(wire.lookups,[rid])
 def test_HPR_legacy_and_retained_stop_after_plan(self):
  import os
  os.environ.update(ENV)
  for retained in(False,True):
   with self.subTest(retained=retained),tempfile.TemporaryDirectory()as d:
    root=Path(d);wire=Wire("close_hpr",retained);connection=dict(CONFIG,**(dict(read_retention=CAP)if retained else{}));cfg=dict(connection=connection,refresh_interval_seconds=1);owner=DailyHistoryPreparation(cfg,checkpoint=root/"checkpoint.json");request=dict(capture_id="same-capture",symbols=["159780.SZ"]);closure=dict(closed_through="2026-10-29");original_plan=BoundHistorySource.plan;cancel=[True]
    def plan(transport,*args):
     record=original_plan(transport,*args)
     if cancel[0]:cancel[0]=False;owner.request_close(deadline=time.monotonic()+1)
     return record
    with patch.object(BoundHistorySource,"exchange",lambda transport,*a:wire.exchange(transport,*a)),patch.object(BoundHistorySource,"plan",plan):
     with self.assertRaises(SourcePending):owner.prepare(request,root/"capture",closure,deadline=time.monotonic()+5)
     slot=root/"capture/159780.SZ.json";record=json.loads(slot.read_bytes());rid=record["request"]["request_id"];self.assertEqual(wire.posts,[rid]);self.assertTrue(record["attempted"])
     resumed=DailyHistoryPreparation(cfg,checkpoint=root/"checkpoint.json");resumed.prepare(request,root/"capture",closure,deadline=time.monotonic()+5)
     self.assertEqual(wire.posts,[rid]);self.assertEqual(wire.lookups,[rid]);self.assertEqual(json.loads(slot.read_bytes())["request"],record["request"]);self.assertTrue((root/"checkpoint.json").exists())
if __name__=="__main__":unittest.main()
