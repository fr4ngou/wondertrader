"""覆盖计数验收区分活进程、旧收据和行情缺口；不启动采集/HTTP/来源服务。"""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'integrations'), str(ROOT / 'connectors/qmt_shm/agent'),
               str(ROOT / 'connectors/qmt_shm/host'), str(ROOT / 'apps/wt_runtime')]
from integrations.guanheng.collection_acceptance import accept_coverage


class CoverageAcceptanceTests(unittest.TestCase):
    def setUp(self):
        parent = Path('E:/workspace/wondertrader-qa/minute-adoption-regressions')
        parent.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        control = self.root / 'controls'; control.mkdir()
        self.directory = control / str(uuid4()); self.directory.mkdir()
        self.worker_sha = '1' * 64; self.producer_sha = '2' * 64
        process = self.save(self.root / 'process.json', dict(control_root=str(control)))
        self.selected = self.save(self.root / 'plan.json', dict(quote_count=2,
            files=dict(collection_process=process, worker=dict(sha256=self.worker_sha),
                       producer=dict(sha256=self.producer_sha))))
        self.save(self.directory / 'ready.json', dict(schema='qmt.quote-collector-ready.v1',
            control_id=self.directory.name, pid=os.getpid(), configuration_sha256=self.worker_sha))
        self.publish_status(time.time())
        self.save(self.directory / 'coverage.json', dict(schema='qmt.quote-collector-coverage.v1',
            control_id=self.directory.name, pid=os.getpid(), configuration_sha256=self.worker_sha,
            coverage=dict(observed_at=time.time(), trading_date='2026-11-04', subscribed_count=2,
                symbols=[dict(symbol='SSE.510300', subscribed=True, quote_state='observed_today'),
                         dict(symbol='SZSE.159780', subscribed=True, quote_state='not_received'),
                         dict(symbol='BSE.920001', subscribed=False, quote_state='unsubscribed')],
                groups=[], missing_subscriptions=['BSE.920001'])))
        self.save(self.directory / 'minute-maintenance.json', dict(schema='qmt.collection-minute-maintenance.v1',
            producer_sha256=self.producer_sha, scan_cycles=0, scan_cursor=2, scan_symbols=2,
            rows=[dict(date='2026-11-04', state='awaiting_closed_day', missing_count=2)]))

    def save(self, path, value):
        raw = json.dumps(value).encode(); path.write_bytes(raw)
        return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest())

    def publish_status(self, stamp):
        self.save(self.directory / 'status.json', dict(schema='qmt.quote-collector-status.v1',
            control_id=self.directory.name, pid=os.getpid(), configuration_sha256=self.worker_sha,
            observed_wall_time=stamp, collection=dict(connected=True, phase='running',
                latest_source_time_ms=int(time.time()*1000), observed_wall_time=stamp,
                native_counts=dict(subscribed=2, delivered=3, writer_processed=3),
                generation=1, received_ticks=3, pushed_ticks=3, receiver_heartbeats=1,
                source_heartbeat=None, error=None, receiver_failure=None, receiver_cleanup_failure=None)))

    def test_live_projection_reports_real_gaps_and_partial_scan_separately(self):
        # 使用本测试真实Windows进程身份，报价/扫描投影为固定业务替身。
        result = accept_coverage(self.selected, self.directory)
        self.assertTrue(result['passed'])
        self.assertEqual(result['subscribed_count'], 2)
        self.assertEqual(result['known_and_retained_count'], 3)
        self.assertEqual(result['quote_states']['not_received'], 1)
        self.assertEqual(result['missing_subscriptions'], 1)
        self.assertEqual(result['current_day_missing_labels'], 2)
        self.assertFalse(result['scan_completed'])
        self.assertFalse(result['market_complete_coverage'])

    def test_new_process_reusing_pid_cannot_use_older_ready_receipt(self):
        created_after_ready = self.directory.joinpath('ready.json').stat().st_mtime_ns // 100 + 116444736000000001
        with patch('guanheng_wt_runtime.service_control._process_identity', return_value=created_after_ready):
            with self.assertRaises(ValueError):
                accept_coverage(self.selected, self.directory)

    def test_stale_status_keeps_counts_but_fails_current_observation(self):
        self.publish_status(time.time() - 100)
        result = accept_coverage(self.selected, self.directory)
        self.assertFalse(result['passed'])
        self.assertEqual(result['observation']['status'], 'stale')
        self.assertEqual(result['subscribed_count'], 2)


if __name__ == '__main__':
    unittest.main()
