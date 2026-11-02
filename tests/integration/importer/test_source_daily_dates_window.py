"""来源日线日期域、固定标签及显式窗口的根因回归。"""
import csv,hashlib,io,json,os,struct,tempfile,unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch
from integrations.guanheng import qmt_local_dat as cache,qmt_minute_import as importer,native_history as history
from integrations.guanheng.models import SourceSession
from integrations.guanheng_market_client import MarketProtocolError
from integrations.guanheng_market_client.source_history import _date


class SourceDateTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.profile=dict(provider='Qmt',instance_id='fixture-source-date',session_id='fixture',generation=1,dataset_version='source-date-fixture',source_license='synthetic-only',input_kind='synthetic',timezone='Asia/Shanghai',minute_boundary='unknown',adjustment='none',factor_version='',value_semantics='source',price_unit='unknown',volume_unit='unknown',amount_unit='unknown')

    def row(self,stamp):return ('timestamp,open,high,low,close,volume,amount\n'+stamp+',10,12,9,11,73,91234\n').encode()

    def test_daily_domain_follows_eight_digit_integer_and_datetime_representation(self):
        for label in ('1000-01-01','1990-12-19','1991-07-01','2106-02-07','9999-12-31'):
            rows,first,last=importer._rows(self.row(label+'T00:00:00+08:00'),self.profile,None,1,period='1d')
            self.assertEqual((rows[0].date,rows[0].time),(int(label.replace('-','')),0))
            self.assertEqual(first.isoformat(),label+'T00:00:00+08:00')
            self.assertEqual(_date(int(label.replace('-',''))),rows[0].date)
        for label in ('0001-01-01','0999-12-31'):
            with self.assertRaises(importer.ImportFailure):importer._rows(self.row(label+'T00:00:00+08:00'),self.profile,None,1,period='1d')
        for value in (1991123,19910230,10000000,100000000,True):
            with self.assertRaises(MarketProtocolError):_date(value)

    def test_source_date_timezone_is_fixed_while_canonical_resolver_retains_iana(self):
        with patch.object(history,'ZoneInfo',return_value=timezone(timedelta(hours=9))) as resolver:
            self.assertEqual(history.shanghai_time(datetime(1991,7,1)).utcoffset(None),timedelta(hours=9))
            self.assertEqual(history.source_date_label(datetime(1991,7,1)).utcoffset(),timedelta(hours=8))
            self.assertEqual(resolver.call_count,1)
        with self.assertRaises(ValueError):history.source_date_label(datetime(1991,7,1,15))

    def test_canonical_and_source_minute_supported_years_are_unchanged(self):
        profiles=[self.profile,dict(self.profile,value_semantics='canonical',minute_boundary='right',volume_to_shares=1,amount_to_yuan=1)]
        for profile in profiles:
            for label in ('1991-07-01','2100-01-04'):
                with self.assertRaises(importer.ImportFailure):importer._rows(self.row(label+'T09:31:00+08:00'),profile,None,1)
            rows,first,last=importer._rows(self.row('1992-01-02T09:31:00+08:00'),profile,None,1)
            self.assertEqual(rows[0].time,(19920102-19900000)*10000+931)

    def test_real_native_daily_readback_at_representation_edges_uses_no_iana(self):
        helper=os.environ.get('QMT_DAILY_HELPER');library=os.environ.get('QMT_DAILY_READER')
        if not helper or not library:self.skipTest('explicit native dependency paths required')
        helper,library=Path(helper),Path(library);sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
        labels=['1000-01-01','1991-07-01','2106-02-07','9999-12-31']
        csvpath=self.root/'sample.csv'
        csvpath.write_bytes(b'timestamp,open,high,low,close,volume,amount\n'+b''.join((label+'T00:00:00+08:00,10,12,9,11,73,91234\n').encode() for label in labels))
        manifest=self.root/'manifest.json';manifest.write_text(json.dumps(dict(schema_version=3,period='1d',profile=self.profile,securities=[dict(symbol='123456.SH',chunks=[dict(path='sample.csv',sha256=sha(csvpath))])])),encoding='utf8')
        receipt=importer.import_dataset(manifest,self.root/'store',helper,sha(helper))
        native=history.NativeHistory(library,sha(library),max_bars=10,max_file_bytes=1024*1024)
        try:
            with patch.object(history,'shanghai_time',side_effect=AssertionError('source-date must not resolve actual time')):
                result=native.read_source_store(self.root/'store','SSE','123456',expected_import_sha256=sha(self.root/'store/qmt-import.json'))
            self.assertEqual([bar.occurred_at.isoformat() for bar in result.bars],[label+'T00:00:00+08:00' for label in labels])
            # 同一原文件改用canonical元数据，只核原15:00/IANA路径保持。
            metadata=history.HistoryMetadata(SourceSession('Qmt','fixture','fixture',1),'DevelopmentVerified','fixture',receipt['securities'][0]['sha256'],'synthetic-only','1d',4,1,1)
            with patch.object(history,'shanghai_time',return_value=timezone(timedelta(hours=9))):
                canonical=native.read(self.root/'store'/receipt['securities'][0]['path'],'123456.SH',metadata)
            self.assertTrue(all(b.occurred_at.hour==15 and b.occurred_at.utcoffset()==timedelta(hours=9) for b in canonical.bars))
        finally:native.close()


class DateWindowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.cache=self.root/'cache'
        for period in ('60','86400'):(self.cache/'SH'/period).mkdir(parents=True,exist_ok=True)

    def record(self,label,volume=73,amount=91234):
        raw=bytearray(64);stamp=int(datetime.fromisoformat(label+'T00:00:00+08:00').timestamp())
        struct.pack_into('<5I',raw,0,stamp,1234,1300,1200,1250);struct.pack_into('<i4xq',raw,24,volume,amount);return bytes(raw)

    def write(self,rows,period='86400'):
        p=self.cache/'SH'/period/'123456.DAT';p.write_bytes(cache.MAGIC+b''.join(rows));return p

    def test_old_daily_dates_and_unsigned_epoch_whole_day_edges_are_inventory_visible(self):
        self.write([self.record('1970-01-02'),self.record('1990-12-19'),self.record('1991-07-01'),self.record('2106-02-07')])
        result=cache.inspect_cache(self.cache,['123456.SH'],self.root/'inventory',period='1d')
        self.assertEqual(result['estimated_rows'],4);self.assertEqual(result['sampled_files'],1)
        self.assertEqual(result['securities'][0]['first_label'],'1970-01-02T00:00:00+08:00')
        self.assertEqual(result['securities'][0]['last_label'],'2106-02-07T00:00:00+08:00')
        self.write([self.record('1991-07-01')],period='60')
        minute=cache.inspect_cache(self.cache,['123456.SH'],self.root/'minute-inventory')
        self.assertEqual(minute['unavailable_files'],1)

    def test_explicit_window_counts_and_hash_cover_the_entire_original(self):
        path=self.write([self.record('2014-12-31',-1),self.record('2015-01-02'),self.record('2015-01-05')]);original=path.read_bytes()
        result=cache.export_cache(self.cache,['123456.SH'],self.root/'window',period='1d',from_date='2015-01-01',to_date='2015-01-02',max_rows=1,max_total_rows=1)
        entry=result['securities'][0]
        self.assertEqual((entry['scanned_rows'],entry['selected_rows'],entry['excluded_rows']),(3,1,2))
        self.assertEqual(entry['source_sha256'],hashlib.sha256(original).hexdigest())
        with (self.root/'window/csv/123456.SH.csv').open(encoding='utf8') as stream:rows=list(csv.DictReader(stream))
        self.assertEqual(rows[0]['timestamp'],'2015-01-02T00:00:00+08:00')
        self.assertEqual(rows[0]['volume'],'73');self.assertEqual(path.read_bytes(),original)

    def test_default_full_and_window_containing_negative_still_fail(self):
        self.write([self.record('2014-12-31',-1),self.record('2015-01-02')])
        for name,kwargs in [('full',{}),('selected-bad',dict(from_date='2014-12-31',to_date='2015-01-02'))]:
            with self.assertRaises(cache.CacheExportError) as caught:cache.export_cache(self.cache,['123456.SH'],self.root/name,period='1d',**kwargs)
            self.assertEqual(caught.exception.category,'quantity')
            self.assertFalse((self.root/name/'export.json').exists())

    def test_scan_budget_is_separate_and_bounded_even_for_empty_windows(self):
        self.write([self.record('2015-01-02'),self.record('2015-01-05'),self.record('2015-01-06')])
        with self.assertRaises(cache.CacheExportError) as caught:
            cache.export_cache(self.cache,['123456.SH'],self.root/'scan-budget',period='1d',to_date='2014-12-31',max_scan_rows=2)
        self.assertEqual(caught.exception.category,'budget')
        self.assertFalse((self.root/'scan-budget/export.json').exists())

    def test_empty_window_reports_complete_scan_without_importing(self):
        self.write([self.record('2015-01-02'),self.record('2015-01-05')])
        with patch.object(importer,'_Native',side_effect=AssertionError('empty selection must not load helper')):
            result=cache.convert_cache(self.cache,['123456.SH'],self.root/'empty',period='1d',helper='unused',helper_sha256='0'*64,to_date='2014-12-31')
        self.assertEqual(result['status'],'empty');self.assertEqual((result['scanned_rows'],result['selected_rows'],result['excluded_rows']),(2,0,2))
        self.assertFalse((self.root/'empty/store/qmt-import.json').exists())

    def test_window_boundaries_and_invalid_selection(self):
        self.write([self.record('2015-01-02'),self.record('2015-01-05')])
        for name,kwargs in [('from-only',dict(from_date='2015-01-05')),('to-only',dict(to_date='2015-01-02')),('closed-one',dict(from_date='2015-01-02',to_date='2015-01-02'))]:
            result=cache.export_cache(self.cache,['123456.SH'],self.root/name,period='1d',**kwargs)
            self.assertEqual(result['total_rows'],1)
        for kwargs in (dict(from_date='20150102'),dict(from_date='2015-02-30'),dict(from_date='2015-01-05',to_date='2015-01-02')):
            with self.assertRaises((ValueError,cache.CacheExportError)):cache.export_cache(self.cache,['123456.SH'],self.root/'bad-window',period='1d',**kwargs)


if __name__=='__main__':unittest.main()
