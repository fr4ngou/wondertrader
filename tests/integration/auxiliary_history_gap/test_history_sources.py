"""保护历史原件、来源单位、研究隔离及实际知晓时刻，不调用终端或网络。"""
from dataclasses import replace
from datetime import date, datetime, timezone
from decimal import Decimal
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from integrations.guanheng.auxiliary_history_sources import (
    _fact, _identity, import_legacy_archive, load_facts, publications_from_facts,
    read_legacy_manifest, read_official_capture, read_yearbook_facts,
)


class HistorySourcesTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.root=Path(self.directory.name)
        self.day='2024-01-02'
        self.stamp='2026-11-05T12:00:00+00:00'

    def tearDown(self):
        self.directory.cleanup()

    def official(self,root,value='123.45',source='szse-margin',received=None):
        from guanheng_analysis_window_producer.official_auxiliary import source_request
        data=[dict(metadata=dict(tabkey='tab1',conditions=[dict(name='txtDate',defaultValue=self.day)],
                   cols=dict(jrrzye='融资余额(亿元)')),data=[dict(jrrzye=value,jrrzrjye='999.99')])]
        body=json.dumps(data).encode();p=root/source;p.mkdir(parents=True,exist_ok=True)
        record=dict(schema='guanheng.official-auxiliary-capture.v1',source=source,statistic_date=self.day,
                    url=source_request(source,self.day)[0],received_at=received or self.stamp,
                    historical_first_available='unknown',values=value,body_sha256=hashlib.sha256(body).hexdigest())
        (p/(self.day+'.json')).write_text(json.dumps(record),encoding='utf-8')
        (p/(self.day+'.json.gz')).write_bytes(gzip.compress(body,mtime=0))
        return p/(self.day+'.json'),body

    def test_raw_margin_field_and_received_time_are_preserved(self):
        self.official(self.root)
        fact=read_official_capture(self.root,'szse-margin',self.day,())
        self.assertEqual(fact.values,'123.45')  # 保护融资余额与两融合计的区别。
        self.assertEqual(fact.received_at,datetime.fromisoformat(self.stamp))
        self.assertIsNone(fact.origin_received_at)

    def test_raw_corruption_and_missing_archive_fail_closed(self):
        receipt,_=self.official(self.root)
        archive=receipt.with_suffix('.json.gz');archive.write_bytes(gzip.compress(b'[]'))
        with self.assertRaisesRegex(ValueError,'identity'):
            read_official_capture(self.root,'szse-margin',self.day,())
        archive.unlink()
        with self.assertRaises(FileNotFoundError):
            read_official_capture(self.root,'szse-margin',self.day,())

    def test_unavailable_side_keeps_market_publication_missing(self):
        fact=_fact('sse-margin',self.day,'100',self.stamp,'1'*64,'official_json',())
        bundle=publications_from_facts([fact],[self.day])
        self.assertEqual(bundle.publications,())
        self.assertIn(('szse-margin',self.day),bundle.missing)

    def test_research_is_isolated_from_default_official_publications(self):
        sh=_fact('sse-margin',self.day,'100',self.stamp,'1'*64,'official_json',())
        sz=_fact('szse-margin',self.day,'23.45678901',self.stamp,'2'*64,'research_only',())
        official=publications_from_facts([sh,sz],[self.day])
        research=publications_from_facts([sh,sz],[self.day],research=True)
        self.assertEqual(official.publications,())
        self.assertEqual(research.qualification,'research_only')
        self.assertEqual(research.publications[0].value,123.45678901)
        self.assertEqual(research.publications[0].available_at,datetime.fromisoformat(self.stamp))

    def test_known_clock_uses_shanghai_calendar_not_utc_date(self):
        fact=_fact('sse-margin','2024-01-02','100','2024-01-02T00:30:00+08:00','1'*64,'official_json',())
        self.assertEqual(fact.statistic_date,date(2024,1,2))

    def test_duplicate_facts_and_mutated_identity_are_rejected(self):
        fact=_fact('sse-margin',self.day,'100',self.stamp,'1'*64,'official_json',())
        with self.assertRaisesRegex(ValueError,'duplicate'):
            publications_from_facts([fact,fact],[self.day])
        with self.assertRaisesRegex(ValueError,'identity'):
            publications_from_facts([replace(fact,values='101')],[self.day])

    def test_conflicting_cache_revisions_require_owner_resolution(self):
        a,b=self.root/'a',self.root/'b';self.official(a);self.official(b,value='124.45')
        with self.assertRaisesRegex(ValueError,'revision_requires_owner'):
            load_facts([a,b],[self.day],())

    def test_same_value_cache_reuse_keeps_earliest_received_clock(self):
        a,b=self.root/'a',self.root/'b';self.official(a,received='2026-11-05T11:00:00+00:00');self.official(b)
        fact=load_facts([b,a],[self.day],())[('szse-margin',self.day)]
        self.assertEqual(fact.received_at.hour,11)

    def legacy(self):
        old=self.root/'old';seed=self.root/'seed';seed.mkdir()
        _,body=self.official(self.root/'fixture')
        source='szse-margin-balance';sha=hashlib.sha256(body).hexdigest()
        evidence=dict(schema_version='1.0',parser_version='resonance-official-auxiliary-v3',source_id=source,
            statistic_date=self.day,request_url='https://www.szse.cn/api/report/ShowReport/data?SHOWTYPE=JSON&CATALOGID=1837_xxpl&txtDate='+self.day,
            source_page='https://www.szse.cn/disclosure/margin/margin/index.html',retrieved_at='2026-08-08T04:57:15.784301+08:00',
            status_code=200,content_type='application/json',body_sha256=sha,body_size=len(body),
            object_ref=f'minio://replay-datasets/resonance-regime/raw/{source}/{self.day}/{sha}.json')
        content=dict(evidence,statistic_date=date.fromisoformat(self.day),retrieved_at=datetime.fromisoformat(evidence['retrieved_at']))
        evidence_sha=hashlib.sha256(json.dumps(content,sort_keys=True,separators=(',',':'),ensure_ascii=False,default=str).encode()).hexdigest()
        evidence.update(evidence_sha256=evidence_sha,frozen=True,executable=False)
        raw=old/'raw'/source/self.day/(sha+'.json');raw.parent.mkdir(parents=True);raw.write_bytes(body)
        receipt=old/'evidence'/source/self.day/(evidence_sha+'.json');receipt.parent.mkdir(parents=True);receipt.write_text(json.dumps(evidence))
        return old,seed

    def test_legacy_import_keeps_original_clock_and_current_import_upper_bound(self):
        old,seed=self.legacy();before={str(p.relative_to(old)):p.read_bytes()for p in old.rglob('*')if p.is_file()}
        output=self.root/'import';result=import_legacy_archive(old,seed,[self.day],output)
        self.assertEqual(result['records'],1)
        fact=read_legacy_manifest(output/'ARCHIVE.json')[0]
        self.assertEqual(fact.origin_received_at,datetime.fromisoformat('2026-08-08T04:57:15.784301+08:00'))
        self.assertGreater(fact.received_at,fact.origin_received_at)
        second=import_legacy_archive(old,seed,[self.day],output)
        self.assertTrue(second['reused'])
        self.assertEqual(read_legacy_manifest(output/'ARCHIVE.json')[0].received_at,fact.received_at)
        self.assertEqual(before,{str(p.relative_to(old)):p.read_bytes()for p in old.rglob('*')if p.is_file()})
        with self.assertRaisesRegex(ValueError,'overlap'):
            import_legacy_archive(old,seed,[self.day],seed/'bad')

    def test_after_close_capture_does_not_backfill_historical_share_signal(self):
        from guanheng_strategy_core.models import DailyObservation
        from guanheng_strategy_v1.auxiliary import merge_auxiliary
        facts=[_fact('sse-shares',day,{'510300.SH':number},self.stamp,'1'*64,'official_json',())
               for day,number in [('2024-01-02','100'),('2024-01-03','110')]]
        pubs=publications_from_facts(facts,['2024-01-02','2024-01-03']).publications
        rows=tuple(DailyObservation('510300.SH',date.fromisoformat(day),1,1,1,1,1,1)for day in ['2024-01-02','2024-01-03','2026-11-06'])
        merged=merge_auxiliary(rows,pubs)
        self.assertIsNone(merged[1].shares_delta_yi)
        self.assertEqual(merged[2].shares_delta_yi,10)
        self.assertGreater(merged[2].auxiliary_available_at,datetime(2024,1,3,tzinfo=timezone.utc))

    def yearbook(self):
        pdf=self.root/'2024.pdf';pdf.write_bytes(b'%PDF synthetic source identity fixture')
        cells={name:dict(value=value,page=page,month=1,day=2,bbox=[1,2,3,4])
               for name,value,page in [('main','100.01',132),('chinext','20.02',226)]}
        payload=dict(extraction_version='test-grid',books=[dict(year=2024,file=pdf.name,
            pdf_sha256=hashlib.sha256(pdf.read_bytes()).hexdigest(),
            url='https://docs.static.szse.cn/www/market/periodical/year/synthetic.pdf',
            received_at=self.stamp,unit='yi_CNY',boards=['main','chinext'],pages=dict(main=132,chinext=226),
            daily_cells={self.day:cells})])
        document=dict(schema='guanheng.official-yearbook-turnover.v1',payload=payload,payload_sha256=_identity(payload))
        target=self.root/'yearbook.json';target.write_text(json.dumps(document),encoding='utf-8')
        return target,document

    def test_yearbook_sum_uses_two_stock_boards_and_original_units(self):
        path,_=self.yearbook();fact=read_yearbook_facts(path)[0]
        self.assertEqual(Decimal(fact.values),Decimal('120.03'))
        self.assertEqual(fact.qualification,'official_yearbook')

    def test_yearbook_tampering_and_wrong_units_are_rejected(self):
        path,document=self.yearbook();document['payload']['books'][0]['unit']='million_CNY'
        path.write_text(json.dumps(document))
        with self.assertRaisesRegex(ValueError,'payload'):
            read_yearbook_facts(path)
        document['payload_sha256']=_identity(document['payload']);path.write_text(json.dumps(document))
        with self.assertRaisesRegex(ValueError,'unit'):
            read_yearbook_facts(path)

    def test_yearbook_path_traversal_is_rejected(self):
        path,document=self.yearbook();document['payload']['books'][0]['file']='../other.pdf'
        document['payload_sha256']=_identity(document['payload']);path.write_text(json.dumps(document))
        with self.assertRaisesRegex(ValueError,'path'):
            read_yearbook_facts(path)

    def test_legacy_import_modified_values_cannot_replace_raw(self):
        old,seed=self.legacy();output=self.root/'import';import_legacy_archive(old,seed,[self.day],output)
        path=output/'ARCHIVE.json';document=json.loads(path.read_bytes());document['payload']['records'][0]['values']='999.99'
        document['payload_sha256']=_identity(document['payload']);path.write_text(json.dumps(document))
        with self.assertRaisesRegex(ValueError,'values'):
            read_legacy_manifest(path)

    def test_public_float_overflow_and_underflow_are_rejected(self):
        for number in ('1E+10000','1E-10000'):
            shares=_fact('sse-shares',self.day,{'510300.SH':number},self.stamp,'1'*64,'official_json',())
            with self.assertRaisesRegex(ValueError,'float_range'):
                publications_from_facts([shares],[self.day])
            pair=[_fact(source,self.day,number,self.stamp,str(i)*64,'official_json',())
                  for i,source in enumerate(('sse-margin','szse-margin'),1)]
            with self.assertRaisesRegex(ValueError,'float_range'):
                publications_from_facts(pair,[self.day])

    def test_existing_import_is_bound_to_requested_calendar(self):
        old,seed=self.legacy();output=self.root/'import';import_legacy_archive(old,seed,[self.day],output)
        with self.assertRaisesRegex(ValueError,'job_scope_changed'):
            import_legacy_archive(old,seed,[self.day,'2024-01-03'],output)

    def test_manifest_failure_before_commit_resumes_from_originals(self):
        old,seed=self.legacy();output=self.root/'import'
        with patch('integrations.guanheng.auxiliary_history_sources.os.replace',side_effect=OSError('synthetic_commit_failure')):
            with self.assertRaises(OSError):import_legacy_archive(old,seed,[self.day],output)
        self.assertFalse((output/'ARCHIVE.json').exists())
        self.assertEqual(import_legacy_archive(old,seed,[self.day],output)['records'],1)
        self.assertEqual(read_legacy_manifest(output/'ARCHIVE.json')[0].values,'123.45')

    def test_share_cache_is_verified_completely_then_projected_to_subset(self):
        from guanheng_analysis_window_producer.official_auxiliary import source_request
        root=self.root/'sse-shares';root.mkdir()
        body=json.dumps(dict(result=[dict(SEC_CODE='510300',STAT_DATE=self.day,TOT_VOL='10000'),
                                     dict(SEC_CODE='510050',STAT_DATE=self.day,TOT_VOL='20000')])).encode()
        record=dict(schema='guanheng.official-auxiliary-capture.v1',source='sse-shares',statistic_date=self.day,
            url=source_request('sse-shares',self.day)[0],received_at=self.stamp,historical_first_available='unknown',
            body_sha256=hashlib.sha256(body).hexdigest(),values={'510300.SH':'1','510050.SH':'2'})
        (root/(self.day+'.json')).write_text(json.dumps(record));(root/(self.day+'.json.gz')).write_bytes(gzip.compress(body))
        fact=read_official_capture(self.root,'sse-shares',self.day,['510300.SH'])
        self.assertEqual(fact.values,{'510300.SH':'1'})

    def test_window_identity_uses_exact_first_read_bytes(self):
        from scripts.auxiliary_history_gap import audit
        seed=self.root/'seed';seed.mkdir();(seed/'FAILURES.json').write_text('{}')
        row=dict(symbol='510300.SH',trade_date=self.day,open=1,high=1,low=1,close=1,volume=1,amount=1)
        raw=json.dumps(dict(history=dict(observations=[row]))).encode();window=self.root/'window.json';window.write_bytes(raw)
        original=Path.read_bytes;reads=[]
        def changing(path):
            if path==window:
                reads.append(1)
                return raw if len(reads)==1 else b'changed source bytes'
            return original(path)
        with patch.object(Path,'read_bytes',new=changing):audit(seed,window,self.root/'audit')
        report=json.loads((self.root/'audit/REPORT.json').read_bytes())
        self.assertEqual(len(reads),1)
        self.assertEqual(report['window_sha256'],hashlib.sha256(raw).hexdigest())
        self.assertEqual((self.root/'audit/MARKET-WINDOW.json').read_bytes(),raw)


if __name__=='__main__':
    unittest.main()
