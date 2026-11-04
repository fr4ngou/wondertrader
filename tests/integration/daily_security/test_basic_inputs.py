"""计划与快照共享原IPO事实；合成资料只区分未知、上市前和来源时刻。"""
import hashlib
from pathlib import Path
import tempfile
import unittest

from integrations.guanheng.market_generation import encode
from integrations.guanheng.market_snapshot_prepare import load_snapshot_basics
from integrations.guanheng.security_reference import SecurityReference


class BasicInputTests(unittest.TestCase):
    def test_original_ipo_and_missing_basic_reach_the_same_security_view(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            body = encode(dict(symbol='001232.SZ', received_wall_ms=1793678400000,
                value=dict(InstrumentID='001232', ExchangeID='SZ', InstrumentName='合成资料',
                           OpenDate=20260804, ExpireDate=0, FloatVolumn=12345, TotalVolumn=34567))) + b'\n'
            (root / 'rows.jsonl').write_bytes(body)
            identity = hashlib.sha256(body).hexdigest()
            (root / 'RESULT.json').write_bytes(encode(dict(state='completed', rows_sha256=identity)))
            basics, actual_sha = load_snapshot_basics(['SZSE.001232', 'SZSE.001381'], root)
            self.assertEqual(actual_sha, identity)
            self.assertEqual(basics['SZSE.001232']['listed_on'], '2026-08-04')
            self.assertIsNone(basics['SZSE.001381'])
            reference = SecurityReference()
            try:
                security = reference.security(dict(basics=basics), 'SZSE.001232')
                self.assertEqual(security['listed_on'], '2026-08-04')
                self.assertEqual(security['name'], '合成资料')
            finally:
                reference.close()
            (root / 'rows.jsonl').write_bytes(body.replace(b'20260804', b'20260805'))
            with self.assertRaises(ValueError):
                load_snapshot_basics(['SZSE.001232'], root)


if __name__ == '__main__':
    unittest.main()
