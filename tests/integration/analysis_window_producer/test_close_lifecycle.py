"""停止时保持原请求、阻止下一次来源准入；仅隔离替身，无 QMT。"""
import importlib.util,json,threading,time,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from guanheng_analysis_window_producer.source import BoundAnalysisClient,SourcePending,AnalysisSnapshotProvider
from guanheng_analysis_window_producer.preparation import DailyHistoryPreparation
from integrations.guanheng.source_history_transport import BoundHistorySource
P=Path("E:/workspace/wondertrader/tests/integration/analysis_window_producer/test_bound_client.py")
s=importlib.util.spec_from_file_location("existing_bound_fixture",P);fixture=importlib.util.module_from_spec(s);s.loader.exec_module(fixture)
CONFIG=dict(base_url="http://127.0.0.1:1",key_id="sdk-fixture",secret_env="TEST_ONLY",timeout=1)
ENV={"TEST_ONLY":"isolated-test-key-"*4}
class CloseLifecycle(unittest.TestCase):
 def client(self):return BoundAnalysisClient(CONFIG,environ=ENV)
 def test_stop_during_original_post_preserves_identity_and_new_owner_only_gets(self):
  original=fixture.Transport();entered=threading.Event();release=threading.Event();errors=[]
  def exchange(owner,method,path,body,deadline):
   if method=="POST":entered.set();self.assertTrue(release.wait(3))
   return original.exchange(method,path,body,deadline)
  with tempfile.TemporaryDirectory()as d,patch.object(BoundHistorySource,"exchange",exchange):
   client=self.client();slot=Path(d)/"slot.json"
   def read():
    try:client.read("market.divid_factors",dict(symbol="510300.SH"),slot,deadline=time.monotonic()+10)
    except BaseException as e:errors.append(type(e))
   t=threading.Thread(target=read);t.start();self.assertTrue(entered.wait(3));client.request_close(deadline=time.monotonic()+1);release.set();t.join(2);self.assertFalse(t.is_alive());self.assertEqual(errors,[SourcePending]);raw=slot.read_bytes();rid=json.loads(raw)["request"]["request_id"]
   with self.assertRaises(SourcePending):client.read("market.divid_factors",dict(symbol="510300.SH"),slot,deadline=time.monotonic()+10)
   self.assertEqual(slot.read_bytes(),raw);self.assertEqual((original.posts,original.gets),(1,0))
   resumed=self.client().read("market.divid_factors",dict(symbol="510300.SH"),slot,deadline=time.monotonic()+10)
   self.assertEqual(resumed["request_id"],rid);self.assertEqual((original.posts,original.gets,original.sdk_calls),(1,1,1))
 def test_stop_during_binding_prevents_plan_and_post(self):
  original=fixture.Transport();client=self.client()
  def exchange(owner,method,path,body,deadline):
   reply=original.exchange(method,path,body,deadline);client.request_close(deadline=time.monotonic()+1);return reply
  with tempfile.TemporaryDirectory()as d,patch.object(BoundHistorySource,"exchange",exchange):
   slot=Path(d)/"slot.json"
   with self.assertRaises(SourcePending):client.read("market.divid_factors",dict(symbol="510300.SH"),slot,deadline=time.monotonic()+10)
   self.assertFalse(slot.exists());self.assertEqual(original.posts,0)
 def test_retained_stop_before_consumed_keeps_result_for_same_id_resume(self):
  original_dir=Path(__file__).parent/"fixtures/close_retained"
  record=json.loads((original_dir/"159780.SZ-factor.json").read_bytes());terminal=record["result"];record["result"]=None;record["received_at"]=None;record["consumed"]=False;calls=[]
  configuration=dict(CONFIG,read_retention=dict(schema="qmt.read-retention.v1",max_lifetime_ms=300000));client=BoundAnalysisClient(configuration,environ=ENV)
  def exchange(owner,method,path,body,deadline):
   calls.append(path)
   if path.endswith("/lookup"):
    client.request_close(deadline=time.monotonic()+1);return 200,terminal
   self.assertTrue(path.endswith("/consumed"))
   return 200,dict(schema="qmt.read-consumed-result.v1",request_id=record["request"]["request_id"],consumed=True)
  with tempfile.TemporaryDirectory()as d,patch.object(BoundHistorySource,"exchange",exchange):
   root=Path(d);slot=root/"slot.json";slot.write_text(json.dumps(record));(root/"BINDING.json").write_bytes((original_dir/"BINDING.json").read_bytes());args=record["request"]["arguments"]
   with self.assertRaises(SourcePending):client.read("market.divid_factors",args,slot,deadline=time.monotonic()+10)
   saved=json.loads(slot.read_bytes());self.assertEqual(saved["request"],record["request"]);self.assertEqual(saved["result"],terminal);self.assertFalse(saved["consumed"]);self.assertEqual(len(calls),1)
   resumed=BoundAnalysisClient(configuration,environ=ENV).read("market.divid_factors",args,slot,deadline=time.monotonic()+10)
   self.assertEqual(resumed["request_id"],record["request"]["request_id"]);self.assertEqual(len(calls),2);self.assertTrue(json.loads(slot.read_bytes())["consumed"])
 def test_repeated_stop_keeps_first_deadline_for_both_source_owners(self):
  import os
  os.environ["TEST_ONLY"]=ENV["TEST_ONLY"]
  with tempfile.TemporaryDirectory()as d:
   prep=DailyHistoryPreparation(dict(connection=CONFIG,refresh_interval_seconds=1),checkpoint=Path(d)/"prep.json")
   client=self.client();provider=AnalysisSnapshotProvider(client,{},preparation=prep);first=time.monotonic()+1
   provider.request_close(deadline=first);provider.request_close(deadline=first+30)
   self.assertEqual(client.transport._close_deadline,first);self.assertEqual(prep.source._close_deadline,first)
   for transport in (client.transport,prep.source):
    with self.assertRaises(SourcePending):transport.exchange("GET","/unused",b"",first+30)
if __name__=="__main__":unittest.main()
