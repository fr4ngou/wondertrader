"""完整标签、缺分钟与原WT聚合的根因回归。"""
from datetime import datetime,timedelta,timezone
from pathlib import Path
from types import SimpleNamespace
import hashlib,json,tempfile,unittest
from integrations.guanheng.qmt_minute_daily import MANDATORY_LABELS,select_sessions,aggregate_native,convert
from integrations.guanheng.qmt_minute_import import _Native


def bars(day='2026-10-29',auction=False):
    result=[]
    for i,minute in enumerate(sorted(MANDATORY_LABELS|({570} if auction else set()))):
        stamp=datetime.fromisoformat(day).replace(tzinfo=timezone(timedelta(hours=8)))+timedelta(minutes=minute)
        result.append(SimpleNamespace(occurred_at=stamp,open=10.+i,high=12.+i,low=9.+i,close=11.+i,volume=float(i+1),amount=float((i+1)*17)))
    return result


class AdmissionTests(unittest.TestCase):
    def test_full_sessions_with_optional_auction(self):
        for auction in (False,True):
            accepted,excluded=select_sessions(bars(auction=auction),'2026-10-01','2026-10-30')
            self.assertEqual(len(accepted),1);self.assertEqual(excluded,[])
            self.assertEqual(len(next(iter(accepted.values()))),240+int(auction))

    def test_incomplete_first_day_and_internal_missing_minute(self):
        for values in (bars()[200:],bars()[:50]+bars()[51:]):
            accepted,excluded=select_sessions(values,'2026-10-01','2026-10-30')
            self.assertEqual(accepted,{})
            self.assertTrue(excluded[0]['missing_labels'])

    def test_unexpected_midday_label(self):
        values=bars();extra=SimpleNamespace(**vars(values[120]));extra.occurred_at=extra.occurred_at.replace(hour=13,minute=0)
        values.insert(120,extra)
        accepted,excluded=select_sessions(values,'2026-10-01','2026-10-30')
        self.assertEqual(accepted,{})
        self.assertEqual(excluded[0]['unexpected_labels'],[780])

    def test_duplicate_date_label_and_reverse_selection(self):
        with self.assertRaises(ValueError):select_sessions(bars()+bars()[-1:],'2026-10-01','2026-10-30')
        with self.assertRaises(ValueError):select_sessions(bars(),'2026-10-30','2026-10-01')

    def test_original_receipt_identity_precedes_output(self):
        import os
        configuration=os.environ.get('QMT_DAILY_REGRESSION_CONFIG')
        if not configuration:self.skipTest('explicit frozen real configuration required')
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);value=json.loads(Path(configuration).read_bytes());value['receipt_sha256']='0'*64
            path=root/'config.json';path.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError,'receipt identity'):convert(path,root/'output')
            self.assertFalse((root/'output').exists())

    def test_output_root_is_fresh_and_parent_is_an_ordinary_directory(self):
        import os
        configuration=os.environ.get('QMT_DAILY_REGRESSION_CONFIG')
        if not configuration:self.skipTest('explicit frozen real configuration required')
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);occupied=root/'occupied';occupied.mkdir()
            with self.assertRaises(FileExistsError):convert(configuration,occupied)
            parent=root/'file-parent';parent.write_bytes(b'not a directory')
            with self.assertRaisesRegex(ValueError,'ordinary directory'):convert(configuration,parent/'output')


class NativeTests(unittest.TestCase):
    def test_real_original_resampler_preserves_auction_and_separate_days(self):
        import os
        configuration=os.environ.get('QMT_DAILY_REGRESSION_CONFIG')
        if not configuration:self.skipTest('explicit frozen real configuration required')
        config=json.loads(Path(configuration).read_bytes())
        native=_Native(config['helper']['library'],config['helper']['sha256'])
        try:
            with tempfile.TemporaryDirectory() as directory:
                source=bars('2026-10-28',auction=True)+bars('2026-10-29',auction=False)
                admitted,excluded=select_sessions(source,'2026-10-01','2026-10-30')
                output=aggregate_native(native,Path(directory)/'input.dsb',admitted)
                self.assertEqual(excluded,[]);self.assertEqual(len(output),2)
                self.assertEqual(output[0]['open'],10.)
                self.assertEqual(output[0]['close'],251.)
                self.assertEqual(output[0]['volume'],sum(range(1,242)))
                self.assertEqual(output[1]['volume'],sum(range(1,241)))
                self.assertEqual(output[0]['amount'],17*sum(range(1,242)))
        finally:native.close()


if __name__=='__main__':unittest.main()
