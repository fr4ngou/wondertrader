"""分钟包装保留原日线版本域与资源责任；真实53指数/资料另沿固定包实测。"""
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'integrations'), str(ROOT / 'connectors/qmt_shm/agent'),
               str(ROOT / 'connectors/qmt_shm/host')]
from integrations.guanheng.recovered_history import RecoveredSourceMarket
from integrations.guanheng import source_market
from guanheng_market_client import API_VERSION


class Versions:
    """发布在批次中推进；既有读域决定本批次可见版本，退出后下一请求跟随新版本。"""
    def __init__(self):
        self.latest = 1  # 可见发布版本，模拟原日线owner的后继发布。
        self.fixed = None  # 原read_scope持有的批次版本，域外为空。
        self.closed = 0  # 资源实际关闭次数。

    @contextmanager
    def read_scope(self):
        self.fixed = self.latest
        try:
            yield
        finally:
            self.fixed = None

    def call(self, request):
        selected = self.latest if self.fixed is None else self.fixed
        qualification = dict(supported=False, qualification='Unavailable', reason='fixture')
        return dict(api_version=API_VERSION, status=dict(code='Ok', reason=''), data=dict(
            source=dict(provider='Qmt', instance_id='fixture', session_id=str(selected), generation=1),
            snapshot=qualification, history=qualification, trading=qualification))

    def close(self):
        self.closed += 1


class DailyDelegateTests(unittest.TestCase):
    def wrapper(self, delegate):
        owner = RecoveredSourceMarket.__new__(RecoveredSourceMarket)
        owner.owner = threading.get_ident(); owner.closed = False
        owner.delegate = delegate; owner.base = Versions(); owner.reader = None
        return owner

    def test_batch_keeps_original_version_and_next_request_follows_publication(self):
        delegate = Versions(); owner = self.wrapper(delegate)
        request = dict(api_version=API_VERSION, action='capabilities')
        try:
            with owner.read_scope():
                first = owner.call(request)
                delegate.latest = 2
                second = owner.call(request)
            following = owner.call(request)
            self.assertEqual(first, second)
            self.assertEqual(first['data']['source']['session_id'], '1')
            self.assertEqual(following['data']['source']['session_id'], '2')
        finally:
            owner.close()
        self.assertEqual(delegate.closed, 1)

    def test_legacy_without_delegate_keeps_original_base_and_close_is_idempotent(self):
        owner = self.wrapper(None); original = owner.base
        request = dict(api_version=API_VERSION, action='capabilities')
        with owner.read_scope():
            self.assertEqual(owner.call(request), original.call(request))
        owner.close(); owner.close()
        self.assertEqual(original.closed, 1)

    def test_failed_daily_delegate_construction_closes_already_created_minute_base(self):
        parent = Path('E:/workspace/wondertrader-qa/minute-adoption-regressions')
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as directory:
            base = dict(mode='source-collected', collection={}, minute_native={})
            producer = dict(mode='source-preparing', base=base, preparation=dict(enabled=True,
                retained_reads=True, closed_day_recovery=True, partitioned_receipts=True,
                timeout_seconds=10, max_bytes=8388608, max_windows=100, workspace=directory))
            path = Path(directory) / 'producer.json'
            raw = json.dumps(producer).encode(); path.write_bytes(raw)
            config = dict(mode='source-recovered', base=deepcopy(base),
                producer=dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest()),
                delegate=dict(mode='source-market-current', current_file=str(Path(directory) / 'CURRENT.json')))
            minute = Versions()
            def create(selected, **kwargs):
                if selected['mode'] == 'source-market-current':
                    raise OSError('fixture daily current unavailable after minute base constructed')
                return minute
            with patch.object(source_market, 'create_native_source_market', create):
                with self.assertRaises(OSError):
                    RecoveredSourceMarket(config)
            self.assertEqual(minute.closed, 1)


if __name__ == '__main__':
    unittest.main()
