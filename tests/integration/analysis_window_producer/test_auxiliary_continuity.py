"""隔离来源与明确模拟时钟的回归；不连接QMT或真实账户，不作为未来行情证据。"""
from datetime import date, datetime, timedelta, timezone
import gzip
import hashlib
import io
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from guanheng_analysis_window_producer.auxiliary_refresh import AuxiliaryRefresh
from guanheng_analysis_window_producer.auxiliary_store import read_capture
from guanheng_analysis_window_producer.official_auxiliary import (capture, parse_source, source_failure,
    observed_publications, capture_dates)
from guanheng_analysis_window_producer.source import SourcePending
from guanheng_strategy_core.models import DailyObservation
from guanheng_strategy_v1.auxiliary import (AuxiliaryPublication, merge_auxiliary,
    merge_auxiliary_research, RESEARCH_EVIDENCE)

DAY = '2020-01-02'
SYMBOL = '510300.SH'


def shares_body(number):
    return json.dumps(dict(result=[dict(SEC_CODE='510300', STAT_DATE=DAY, TOT_VOL=number)])).encode()


class Response(io.BytesIO):
    status = 200


class StoreAndRefresh(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def capture(self, body, **options):
        with patch('guanheng_analysis_window_producer.official_auxiliary.urlopen',
                   return_value=Response(body)):
            return capture('sse-shares', DAY, self.root, {SYMBOL}, **options)

    def test_revision_preserves_both_originals_and_unchanged_refresh_keeps_clock(self):
        first = self.capture(shares_body('1200000'))
        same = self.capture(shares_body('1200000'), refresh=True)
        self.assertEqual(first['received_at'], same['received_at'])
        revised = self.capture(shares_body('1300000'), refresh=True)
        self.assertNotEqual(first['body_sha256'], revised['body_sha256'])
        directory = self.root/'sse-shares/versions'/DAY
        self.assertEqual(len(list(directory.glob('*.json.gz'))), 2)
        self.assertEqual(gzip.decompress((directory/(first['body_sha256']+'.json.gz')).read_bytes()), shares_body('1200000'))
        self.assertEqual(read_capture(self.root,'sse-shares',DAY,parse_source)['values'][SYMBOL], '130')
        self.assertIsNone(revised['available_at'])
        self.assertEqual(revised['historical_first_available'], 'unknown')

    def test_failed_revision_keeps_original_and_clock(self):
        first = self.capture(shares_body('1200000'))
        raw = (self.root/'sse-shares'/(DAY+'.json')).read_bytes()
        with self.assertRaises(ValueError):
            self.capture(b'{"result":[]}', refresh=True)
        self.assertEqual((self.root/'sse-shares'/(DAY+'.json')).read_bytes(), raw)
        self.assertEqual(read_capture(self.root,'sse-shares',DAY,parse_source)['received_at'], first['received_at'])

    def test_failure_after_archive_before_receipt_recovers_same_original(self):
        with patch('guanheng_analysis_window_producer.auxiliary_store.write_json',side_effect=OSError('isolated_disk_fault')):
            with self.assertRaises(OSError):
                self.capture(shares_body('1200000'))
        self.assertFalse((self.root/'sse-shares'/(DAY+'.json')).exists())
        self.capture(shares_body('1200000'))
        self.assertEqual(read_capture(self.root,'sse-shares',DAY,parse_source)['values'][SYMBOL], '120')

    def test_seed_is_readonly_and_new_revision_goes_to_owned_root(self):
        first = self.capture(shares_body('1200000'))
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        owned = self.root/'new-owner'
        with patch('guanheng_analysis_window_producer.official_auxiliary.urlopen', return_value=Response(shares_body('1300000'))):
            revised = capture('sse-shares',DAY,owned,{SYMBOL},refresh=True,seed_root=self.root)
        for name, raw in before.items():
            self.assertEqual((self.root/name).read_bytes(),raw)
        self.assertNotEqual(first['body_sha256'],revised['body_sha256'])

    def test_restart_preserves_retry_and_resume_after_unpublished(self):
        owner = AuxiliaryRefresh(self.root)
        with patch('guanheng_analysis_window_producer.official_auxiliary.urlopen',return_value=Response(b'{"result":[]}')):
            report = owner.refresh([DAY],{SYMBOL},deadline=time.monotonic()+10,check=lambda:None,max_requests=1)
        self.assertEqual(report['source_error_count'],1)
        state = json.loads(owner.path.read_bytes())
        failed = next(iter(state['sources']))
        owner.close()
        resumed = AuxiliaryRefresh(self.root)
        self.addCleanup(resumed.close)
        with patch('guanheng_analysis_window_producer.auxiliary_refresh.capture',side_effect=OSError('test-source-offline')) as fetch:
            resumed.refresh([DAY],{SYMBOL},deadline=time.monotonic()+10,check=lambda:None,max_requests=4)
        self.assertNotIn(failed, [call.args[0]+'/'+call.args[1] for call in fetch.call_args_list])
        self.assertEqual(resumed.state[failed],state['sources'][failed])
        self.assertEqual(failed,'sse-margin/'+DAY)
        resumed.state[failed]['next_retry_at']='2000-01-01T00:00:00+00:00'
        body=json.dumps(dict(result=[dict(opDate='20200102',rzye='200000000')])).encode()
        with patch('guanheng_analysis_window_producer.official_auxiliary.urlopen',return_value=Response(body)):
            recovered=resumed.refresh([DAY],{SYMBOL},deadline=time.monotonic()+10,check=lambda:None,max_requests=1)
        self.assertEqual(resumed.state[failed]['failures'],0)
        self.assertIsNone(resumed.state[failed]['error'])
        self.assertEqual(recovered['sources']['sse-margin']['captured'],1)
        self.assertEqual(read_capture(self.root,'sse-margin',DAY,parse_source)['values'],'2')

    def test_stop_blocks_following_requests_and_persists_first_attempt(self):
        owner = AuxiliaryRefresh(self.root)
        self.addCleanup(owner.close)
        stopped = []
        def fetch(*args,**kwargs):
            stopped.append(True)
            raise OSError('test-source-offline')
        def check():
            if stopped:
                raise SourcePending('isolated_close')
        with patch('guanheng_analysis_window_producer.auxiliary_refresh.capture',fetch):
            with self.assertRaises(SourcePending):
                owner.refresh([DAY],{SYMBOL},deadline=time.monotonic()+10,check=check)
        self.assertEqual(len(owner.state),1)
        self.assertEqual(len(json.loads(owner.path.read_bytes())['sources']),1)

    def test_two_writers_rejected_and_closed_owner_can_restart(self):
        owner = AuxiliaryRefresh(self.root)
        try:
            with self.assertRaises(OSError):
                AuxiliaryRefresh(self.root)
            with self.assertRaises(OSError):
                capture_dates([DAY],{SYMBOL},self.root,workers=1)
        finally:
            owner.close()
        resumed = AuxiliaryRefresh(self.root)
        resumed.close()

    def test_old_holes_do_not_starve_recent_revision(self):
        self.capture(shares_body('1200000'))
        owner=AuxiliaryRefresh(self.root)
        self.addCleanup(owner.close)
        old=datetime(2000,1,1,tzinfo=timezone.utc).isoformat()
        owner.state['sse-shares/'+DAY]=dict(checked_at=old,next_retry_at=None,failures=0,error=None,error_type=None)
        def fetch(source, day, *args, **kwargs):
            self.assertEqual((source,day),('sse-shares',DAY))
            return dict(checked_at=datetime.now(timezone.utc).isoformat())
        # 最后两日缺口仍优先；为其明确设置持久退避，核近期修订胜过更老空日期。
        future=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()
        sources=['sse-shares','sse-turnover','szse-turnover','sse-margin','szse-margin']
        for blocked_day in ['2019-12-26',DAY]:
            for source in sources:
                if blocked_day==DAY and source=='sse-shares':
                    continue
                owner.state[source+'/'+blocked_day]=dict(checked_at=old,next_retry_at=future,failures=1,error='request_failed',error_type='OSError')
        with patch('guanheng_analysis_window_producer.auxiliary_refresh.capture',fetch):
            report=owner.refresh(['2019-12-25','2019-12-26',DAY],{SYMBOL},deadline=time.monotonic()+10,check=lambda:None,max_requests=1)
        self.assertEqual(report['requests'],1)

    def test_schema_unit_date_zero_and_network_errors_remain_distinct(self):
        cases=[(shares_body('0'),'auxiliary_source_zero'),
               (b'{"result":[{}]}','auxiliary_source_symbols_missing'),
               (b'{"result":{}}','auxiliary_source_schema')]
        for body,expected in cases:
            with self.subTest(expected=expected),self.assertRaises(ValueError) as caught:
                parse_source('sse-shares',DAY,body,{SYMBOL})
            self.assertEqual(source_failure(caught.exception)['reason'],expected)
        self.assertEqual(source_failure(OSError('private arbitrary server text'))['reason'],'request_failed')

    def test_warm_cache_rechecks_changed_archive(self):
        record=self.capture(shares_body('1200000'))
        cache={}
        self.assertEqual(len(observed_publications(self.root,[DAY],cache=cache)),1)
        archive=self.root/'sse-shares/versions'/DAY/(record['body_sha256']+'.json.gz')
        archive.write_bytes(gzip.compress(b'{"changed":true}'))
        with self.assertRaisesRegex(ValueError,'auxiliary_cache_identity'):
            observed_publications(self.root,[DAY],cache=cache)

    def test_market_amount_and_financing_units_use_correct_source_columns(self):
        margin=dict(result=[dict(opDate='20200102',rzye='200000000',rzrqye='990000000')])
        self.assertEqual(parse_source('sse-margin',DAY,json.dumps(margin).encode(),set()),'2')
        amount=dict(result=[dict(PRODUCT_CODE='17',TRADE_DATE='20200102',TRADE_AMT='1000')])
        self.assertEqual(parse_source('sse-turnover',DAY,json.dumps(amount).encode(),set()),'1000')
        for source,condition,field in [('szse-turnover','txtQueryDate','cjje'),('szse-margin','txtDate','jrrzye')]:
            body=[dict(metadata=dict(tabkey='tab1',conditions=[dict(name=condition,defaultValue=DAY)],
                cols={field:'金额（亿元）'}),data=[dict(lbmc='股票',**{field:'1,234.5'})])]
            self.assertEqual(parse_source(source,DAY,json.dumps(body).encode(),set()),'1234.5')
            body[0]['metadata']['cols'][field]='万元'
            with self.assertRaisesRegex(ValueError,'auxiliary_source_unit'):
                parse_source(source,DAY,json.dumps(body).encode(),set())


class DerivationAndTime(unittest.TestCase):
    def row(self, day):
        return DailyObservation(SYMBOL,day,1.,1.,1.,1.,100.,100.)

    def publication(self, kind, day, value, available=None):
        return AuxiliaryPublication(kind,day,value,available,
            available or datetime(2026,11,5,20,tzinfo=timezone.utc),hashlib.sha256(str((kind,day,value)).encode()).hexdigest(),
            SYMBOL if kind=='shares' else None)

    def test_unknown_time_never_backfills_and_later_simulated_close_can_apply(self):
        first,second=date(2020,1,1),date(2020,1,2)
        pubs=(self.publication('shares',first,121.515),self.publication('shares',second,131.515))
        rows=(self.row(first),self.row(second))
        self.assertEqual(merge_auxiliary(rows,pubs),rows)
        # 显式模拟后继收盘，只证明纯合并的时间边界，不证明真实未来行情。
        later = self.row(date(2026,11,6))
        merged = merge_auxiliary(rows+(later,),pubs)
        self.assertEqual(merged[-1].shares_delta_yi,10.)
        self.assertEqual(merged[-1].auxiliary_available_at,pubs[-1].received_at)
        self.assertTrue(all(p.available_at is None for p in pubs))

    def test_turnover_full_prefix_uses_64_source_dates_and_midrank(self):
        days=[date(2020,1,1)+timedelta(days=i) for i in range(64)]
        rows=tuple(self.row(day) for day in days)
        pubs=tuple(self.publication('turnover',day,float(i+1),datetime.combine(day,datetime.min.time(),tzinfo=timezone.utc))
                   for i,day in enumerate(days))
        result=merge_auxiliary(rows,pubs)
        self.assertIsNone(result[18].turnover_percentile)
        self.assertAlmostEqual(result[19].turnover_percentile,97.5)
        self.assertAlmostEqual(result[-1].turnover_percentile,59.5/60*100)
        self.assertEqual(result[-1].auxiliary_source_dates,tuple(days))

    def test_source_publish_time_does_not_backfill_later_actual_receipt(self):
        first,second=date(2020,1,1),date(2020,1,2)
        actual=datetime(2026,11,5,20,tzinfo=timezone.utc)
        pubs=tuple(AuxiliaryPublication('shares',day,value,datetime.combine(day,datetime.min.time(),tzinfo=timezone.utc),
                    actual,'1'*64,SYMBOL) for day,value in [(first,100.),(second,105.)])
        rows=(self.row(first),self.row(second))
        self.assertEqual(merge_auxiliary(rows,pubs),rows)

    def test_missing_middle_share_date_does_not_become_one_day_flow(self):
        days=[date(2020,1,1)+timedelta(days=i) for i in range(3)]
        rows=tuple(self.row(day) for day in days)
        pubs=(self.publication('shares',days[0],100.,datetime(2020,1,1,tzinfo=timezone.utc)),
              self.publication('shares',days[2],120.,datetime(2020,1,3,tzinfo=timezone.utc)))
        result=merge_auxiliary(rows,pubs)
        self.assertTrue(all(row.shares_delta_yi is None for row in result))

    def test_research_is_explicit_marked_and_preserves_real_publication_clocks(self):
        days=[date(2020,1,1)+timedelta(days=i) for i in range(3)]
        rows=tuple(self.row(day) for day in days)
        pubs=(self.publication('shares',days[0],120.),self.publication('shares',days[1],125.))
        actual=tuple(pubs)
        result,declaration=merge_auxiliary_research(rows,pubs,data_sha256='1'*64,derivation_sha256='2'*64,
                                                  strategy_id='test-only',strategy_version='1')
        self.assertEqual(pubs,actual)
        self.assertEqual(result[-1].shares_delta_yi,5.)
        self.assertTrue(all(RESEARCH_EVIDENCE in row.evidence_refs for row in result))
        self.assertFalse(declaration['realtime_qualified'])
        self.assertFalse(declaration['historical_causal_qualified'])
        self.assertEqual(declaration['actual_last_received_at'],pubs[-1].received_at.isoformat())


if __name__ == '__main__':
    unittest.main()
