"""完整名册遇到受理前容量拒绝时沿原槽等待；来源未知继续交回原owner。"""
from pathlib import Path
import json,tempfile,time,unittest
from unittest.mock import patch

from integrations.guanheng.daily_data_update import _save, _descriptor
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

    def test_archived_same_day_membership_requires_exact_complete_stock_groups(self):
        from integrations.guanheng.source_reference_capture import UNIVERSE, qualify_archived_stock_membership
        from integrations.guanheng_market_client.daily_facts import FIELDS, STATS

        day = '2026-11-10'
        facts = dict(schema='guanheng.daily-source-facts.v1', date=day,
                     members=['BSE.920001', 'SSE.600000', 'SZSE.000001'], fields=FIELDS, rows=[],
                     units=dict(close_reference='CNY', preclose='CNY', volume='share', turn='percent_of_float'),
                     stats=dict.fromkeys(STATS, 0),
                     provenance=dict(packet_sha256='a'*64, universe_sha256='b'*64,
                                     source_received_at=day+'T08:00:00Z'))
        clock = day+'T07:30:00Z'
        groups = [dict(market=market, security_type='stock', state='complete', expected_count=1, observed_count=1)
                  for market in ('SH', 'SZ', 'BJ')]
        items = [dict(symbol=symbol, market=market, security_type='stock')
                 for symbol, market in (('600000.SH', 'SH'), ('000001.SZ', 'SZ'), ('920001.BJ', 'BJ'))]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            saved = dict(binding={'original': 'A'}, request=dict(arguments=dict(cursor=None)))
            slot_path = root/'universe-000.json'
            _save(slot_path, saved)
            slot = _descriptor(slot_path)
            metadata = dict(captured_at=clock, source_as_of=None, catalog_id='c'*64, groups=groups)
            page = dict(metadata, items=items, next_cursor=None)
            reference = dict(schema='guanheng.security-reference.v2', provenance=dict(metadata, evidence=[slot]))
            reference_path = root/'REFERENCE.json'
            _save(reference_path, reference)
            descriptor = _descriptor(reference_path)
            response = dict(ok=True, operation_id=UNIVERSE, data=page)
            with patch('guanheng_qmt_shm.read_retention_client.inspect_saved_result', return_value=response):
                verified = qualify_archived_stock_membership(facts, descriptor, check=lambda: None)
                self.assertEqual(verified['qualification']['membership_source_sha256'], descriptor['sha256'])
                self.assertEqual(verified['qualification']['membership_method'], 'same_day_qmt')
                self.assertIsNone(verified['qualification']['turnover_method'])
                self.assertEqual({k: v for k, v in verified.items() if k != 'qualification'}, facts)
                with self.assertRaisesRegex(ValueError, 'does not cover facts'):
                    qualify_archived_stock_membership(dict(facts, members=['SSE.600000']), descriptor, check=lambda: None)
                page['next_cursor'] = 'another-page'
                with self.assertRaisesRegex(ValueError, 'does not cover facts'):
                    qualify_archived_stock_membership(facts, descriptor, check=lambda: None)
                reference['provenance']['captured_at'] = day+'T06:59:00Z'
                _save(reference_path, reference)
                descriptor = _descriptor(reference_path)
                with self.assertRaisesRegex(ValueError, 'clock differs'):
                    qualify_archived_stock_membership(facts, descriptor, check=lambda: None)

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
