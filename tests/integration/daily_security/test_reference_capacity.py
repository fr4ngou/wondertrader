"""完整名册遇到受理前容量拒绝时沿原槽等待；来源未知继续交回原owner。"""
from pathlib import Path
import json,tempfile,time,unittest

from integrations.guanheng.daily_data_update import _save
from integrations.guanheng.source_reference_capture import capture_reference,UNIVERSE,DETAILS
from guanheng_qmt_shm.read_retention_client import RetainedReadPending


class ReferenceCapacityTests(unittest.TestCase):
    def source(self,reason):
        class Source:
            def __init__(self):self.calls=[];self.catalogs=0
            def capabilities(self,**kwargs):
                return dict(state='ready',metadata=dict(binding=dict(synthetic_epoch='A'),
                    profile=dict(operation_profiles={UNIVERSE:{},DETAILS:{}})))
            def universe(self,request,slot,**kwargs):
                slot=Path(slot)
                if not slot.exists():_save(slot,dict(request_id='original-universe',binding=dict(synthetic_epoch='A')))
                self.calls.append((slot.name,json.loads(slot.read_bytes())['request_id']))
                if len(self.calls)==1:raise RetainedReadPending(reason)
                self.catalogs+=1
                page=dict(schema='qmt.security-universe.v1',catalog_id='a'*64,captured_at='2026-11-04T01:00:00Z',
                    source_as_of=None,markets=['SH'],security_types=['stock'],state='complete',total_count=1,
                    groups=[dict(market='SH',security_type='stock',state='complete',expected_count=1,
                        observed_count=1,source_groups=['synthetic'],reason_code=None)],
                    items=[dict(symbol='600000.SH',market='SH',security_type='stock',source_groups=['synthetic'])],next_cursor=None)
                return dict(state='observed',result=dict(binding=dict(synthetic_epoch='A'),reply=dict(data=page)))
            def details(self,request,slot,**kwargs):
                _save(Path(slot),dict(request_id='original-details'))
                item=dict(symbol='600000.SH',market='SH',status='observed',name='合成证券',listed_on=None,
                    expires_on=None,trading_status='unknown',observed_at='2026-11-04T01:00:00Z',field_reasons={},raw_fields={})
                return dict(state='observed',result=dict(binding=dict(synthetic_epoch='A'),reply=dict(data=dict(
                    schema='qmt.security-details.v1',catalog_id='a'*64,captured_at='2026-11-04T01:00:00Z',source_as_of=None,items=[item]))))
        return Source()

    def test_capacity_rejection_completes_same_catalog_with_same_original_slot(self):
        with tempfile.TemporaryDirectory()as directory:
            source=self.source('read_retention_capacity_rejected')
            result=capture_reference(source,dict(markets=['SH'],security_types=['stock'],limit=256),
                Path(directory)/'capture',deadline=time.monotonic()+3)
            self.assertEqual(result['observed_count'],1)
            self.assertEqual(source.calls,[('universe-000.json','original-universe')]*2)
            self.assertEqual(source.catalogs,1)

    def test_transport_unknown_keeps_original_slot_and_returns_to_owner(self):
        with tempfile.TemporaryDirectory()as directory:
            source=self.source('read_transport_unresolved')
            with self.assertRaises(RetainedReadPending):
                capture_reference(source,dict(markets=['SH'],security_types=['stock'],limit=256),
                    Path(directory)/'capture',deadline=time.monotonic()+3)
            self.assertEqual(len(source.calls),1)
            self.assertEqual(source.catalogs,0)
            self.assertTrue((Path(directory)/'capture/universe-000.json').exists())
