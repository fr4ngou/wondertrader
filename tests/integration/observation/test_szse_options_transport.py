"""SZSE实际断开响应前连接的原故障，以及原预算内后继成功。"""
import json
from pathlib import Path
import tempfile
from time import monotonic
import unittest
from unittest.mock import patch

import httpx

from guanheng_app.observation.providers import exchange_options
from guanheng_app.observation.source_fetch import CollectionBudget, Fetcher, SourceFailure
from guanheng_app.observation.storage import ContentStore


SOURCE = dict(kind='szse', url='https://investor.szse.cn/api/report/ShowReport/data',
    referer='https://investor.szse.cn/market/option/day/index.html', products=['159915'])


def official_shape():
    # 依据实际官方日表字段构造最小夹具；完整官方原件另存受控验证目录。
    return [dict(metadata=dict(conditions=[dict(name='txtQueryDate', defaultValue='2026-11-05')]),
        data=[dict(bddm='159915', wpcrchys='1,311,163', wpcrphys='730,391', wpchyzs='2,041,554',
                   rccjl='1,580,007', rpcjl='1,112,618', cjl='2,692,625')])]


class SzseOptionsTransportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.store = ContentStore(Path(self.temporary.name))

    def tearDown(self):
        self.temporary.cleanup()

    def fetcher(self, handler):
        budget = CollectionBudget(monotonic() + 30, max_requests=2, max_bytes=1024*1024)
        return Fetcher(self.store, ['investor.szse.cn'], budget=budget,
            client=httpx.Client(transport=httpx.MockTransport(handler)))

    def test_response_header_disconnect_is_bounded_transport_failure(self):
        calls = []
        def handler(request):
            calls.append(request)
            raise httpx.RemoteProtocolError('Server disconnected without sending a response.')
        fetch = self.fetcher(handler)
        try:
            with patch.object(fetch, '_wait') as wait, self.assertRaises(SourceFailure) as caught:
                exchange_options(fetch, SOURCE, '2026-11-05', '2026-11-05')
            self.assertEqual(caught.exception.code, 'source_network_timeout')
            self.assertEqual(len(calls), 2)
            wait.assert_called_once_with(1)
            self.assertEqual(fetch.budget.requests, 2)
            self.assertEqual(fetch.records, [])
        finally:
            fetch.close()

    def test_existing_retry_then_official_table_parses_without_quantity_changes(self):
        calls = []
        def handler(request):
            calls.append(request)
            if len(calls) == 1:
                raise httpx.RemoteProtocolError('Server disconnected without sending a response.')
            return httpx.Response(200, stream=httpx.ByteStream(json.dumps(official_shape()).encode()),
                headers={'Content-Type': 'application/json'}, request=request)
        fetch = self.fetcher(handler)
        try:
            with patch.object(fetch, '_wait'):
                result = exchange_options(fetch, SOURCE, '2026-11-05', '2026-11-05')
            self.assertEqual(len(calls), 2)
            row = result['pcr_159915'][0]
            self.assertEqual((row['call_oi'], row['put_oi']), (1311163, 730391))
            self.assertEqual((row['call_volume'], row['put_volume']), (1580007, 1112618))
            self.assertEqual(row['official_oi_quality'], 'complete_reconciled')
            self.assertEqual(row['official_volume_quality'], 'complete_reconciled')
            self.assertEqual([item['kind'] for item in fetch.records], ['http_wire', 'http_body'])
        finally:
            fetch.close()

    def test_original_stop_takes_precedence_over_network_retry(self):
        cancelled = False
        def handler(request):
            nonlocal cancelled
            cancelled = True
            raise httpx.RemoteProtocolError('Server disconnected without sending a response.')
        fetch = self.fetcher(handler)
        fetch.budget.cancelled = lambda: cancelled
        try:
            with patch.object(fetch, '_wait') as wait, self.assertRaises(SourceFailure) as caught:
                exchange_options(fetch, SOURCE, '2026-11-05', '2026-11-05')
            self.assertEqual(caught.exception.code, 'collection_stopped')
            self.assertEqual(fetch.budget.requests, 1)
            wait.assert_not_called()
        finally:
            fetch.close()


if __name__ == '__main__':
    unittest.main()
