"""部分/空来源经原窗口继续恢复；可选固定原生制品跑Importer与标准Reader。

MCC_NATIVE_FIXTURE显式指向已验证producer.json；测试只读该配置，工作区始终另建E盘。
来源传输由可控替身承担，持久窗口、导入、原生读取和最终来源选择使用正式实现。
"""
from contextlib import nullcontext
from copy import deepcopy
from datetime import datetime
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'integrations'), str(ROOT / 'connectors/qmt_shm/agent'),
               str(ROOT / 'connectors/qmt_shm/host'), str(ROOT / 'apps/wt_runtime')]
from integrations.guanheng import source_history_preparation as preparation
from guanheng_market_client import API_VERSION


class SourceFixture:
    """同一来源逐步补齐；时间可推进，模拟未知读仍持有原请求身份。"""
    def __init__(self):
        self.now = 1000.  # 本机启动秒；重建业务对象继续使用同一时钟。
        self.uptime = self
        self.rows = []  # 当前来源可读原值，按Source毫秒时间排序。
        self.pending_once = False  # 下一次新读取在保存身份后返回未知。
        self.hold_pending = True  # 故障窗口持续至业务对象重建，期间只核原请求。
        self.pending_ids = []  # 已发生未知结果的原读取UUID，供恢复核验。
        self.observed_ids = []  # 每次观察使用的原读取UUID。
        self.prepares = 0  # 实际准备调用计数，后继只读须保持一次。
        limits = dict(max_rows=2000, max_calendar_days=3)
        self.metadata = dict(binding=dict(host_instance_id='synthetic-recovery'),
            profile=dict(operation_profiles={'market.history_1m':dict(limits=limits)}),
            limits=dict(max_request_bytes=65536, max_result_bytes=524288))

    def seconds(self):
        return self.now

    def binding(self, deadline):
        return deepcopy(self.metadata)

    def rpc_budget(self, seconds):
        return nullcontext()

    def prepare_arguments(self, symbol, start, end, metadata, deadline):
        return dict(symbol=symbol, period='1m', start_time=start, end_time=end)


class ReadFixture:
    """观察结果存回正式窗口收据；重建后仍核同一UUID及已完成结果。"""
    def __init__(self, source, root, *, retained):
        self.source = source

    def plan(self, operation, arguments, metadata, deadline, directory):
        return dict(request=dict(operation_id=operation, arguments=arguments, request_id=str(uuid4())),
            binding=deepcopy(metadata['binding']), profile=deepcopy(metadata['profile']),
            limits=deepcopy(metadata['limits']), result=None, attempted=False)

    def saved_reply(self, record):
        return record['result']

    def observe(self, record, save, deadline):
        source = self.source
        rid = record['request']['request_id']; source.observed_ids.append(rid)
        if record['result'] is not None:
            return record['result']
        if rid in source.pending_ids and source.hold_pending:
            raise preparation.SourcePending('fixture original read remains unknown')
        if not record['attempted']:
            record['attempted'] = True; save()
            if source.pending_once:
                source.pending_once = False; source.pending_ids.append(rid)
                raise preparation.SourcePending('fixture original read outcome unknown')
        request = record['request']
        if request['operation_id'] == 'market.history_prepare':
            source.prepares += 1
            result = dict(ok=True, data={})
        else:
            args = request['arguments']
            result = dict(ok=True, data=dict(schema_version='qmt.history-1m.v1', symbol=args['symbol'],
                period='1m', start_time=args['start_time'], end_time=args['end_time'], max_rows=args['max_rows'],
                rows=deepcopy(source.rows), coverage='unknown',
                source_options=dict(dividend_type='none', fill_data=False, subscribe=False)))
        record['result'] = result; save()
        return result


@unittest.skipUnless(os.environ.get('MCC_NATIVE_FIXTURE'), 'requires explicit fixed native fixture')
class NativePartialRecoveryTests(unittest.TestCase):
    def test_new_authenticated_generation_reads_complete_day_without_downloading_again(self):
        parent = Path('E:/workspace/wondertrader-qa/minute-collection-regressions')
        parent.mkdir(parents=True, exist_ok=True)
        configuration = json.loads(Path(os.environ['MCC_NATIVE_FIXTURE']).read_bytes())
        source = SourceFixture()
        with tempfile.TemporaryDirectory(dir=parent) as root:
            c = configuration['preparation']
            c['workspace'] = str(Path(root) / 'recovery')
            c['follow_up'] = dict(enabled=True, max_attempts=15, interval_seconds=60, total_seconds=86400,
                                  rpc_timeout_seconds=10, journal_records=1024, journal_bytes=1073741824)
            with patch.object(preparation, 'BoundHistorySource', lambda *a, **k: source), \
                    patch.object(preparation, 'HistoryReadOperations', ReadFixture):
                market = preparation.SourcePreparingMarket(configuration,
                    wall_clock=lambda: 1700000000 + source.now)
                try:
                    grid = market.base.expected_minutes('SSE.510300', '2026-11-03')
                    complete = [dict(time=int(preparation.stamp(m).timestamp() * 1000),
                                     open=4., high=4., low=4., close=4., volume=100., amount=400.) for m in grid]
                    query = dict(exchange='SSE', code='510300', **{'from': grid[0], 'to': grid[-1]}, limit=len(grid))
                    request = dict(api_version=API_VERSION, action='history.source-query', request=query)
                    source.rows = complete[:-1]
                    # 初次读取和HPR已返回，首轮after断连留原读取身份。
                    original_observe = market.reads.observe

                    def interrupted_after(record, save, deadline):
                        if source.prepares and record['request']['operation_id'] == 'market.history_1m':
                            record['attempted'] = True
                            save()
                            raise preparation.SourcePending('fixture disconnect during first readback')
                        return original_observe(record, save, deadline)

                    with patch.object(market.reads, 'observe', side_effect=interrupted_after):
                        market.call(request)
                    _, _, prior = market._state(query)
                    self.assertIsNone(prior['published'])
                    self.assertTrue(prior['after']['pages'][0]['attempted'])
                    prior_preparation = prior['prepare']['request']['request_id']
                    source.now += 61
                    source.metadata['binding'] = dict(host_instance_id='replacement', capability_sha256='changed')
                    source.rows = complete
                    with self.assertRaises(ValueError):
                        market._window(query, preparation.time.monotonic() + 10)
                    self.assertEqual(market._state(query)[2], prior)
                    source.metadata['binding'] = dict(host_instance_id='replacement')
                    response = market.call(request)
                    _, _, resumed = market._state(query)
                    self.assertEqual([row['minute'] for row in response['data']['bars']], grid)
                    self.assertEqual(resumed['prepare']['request']['request_id'], prior_preparation)
                    self.assertEqual(resumed['after'], prior['after'])
                    capture = resumed['follow_up']['reads'][-1]['capture']
                    self.assertEqual(capture['binding'], source.metadata['binding'])
                    self.assertEqual(source.prepares, 1)
                finally:
                    market.close()

    def test_partial_and_empty_recover_after_unknown_read_and_restart(self):
        parent = Path('E:/workspace/wondertrader-qa/minute-collection-regressions')
        parent.mkdir(parents=True, exist_ok=True)
        original = json.loads(Path(os.environ['MCC_NATIVE_FIXTURE']).read_bytes())
        for initial_count in (200, 0, 'wrong-labels'):
            with self.subTest(initial_count=initial_count), tempfile.TemporaryDirectory(dir=parent) as root:
                source = SourceFixture(); configuration = deepcopy(original)
                c = configuration['preparation']; c['workspace'] = str(Path(root) / 'recovery')
                c['max_import_attempts'] = 16
                c['follow_up'] = dict(enabled=True, max_attempts=15, interval_seconds=60, total_seconds=86400,
                    rpc_timeout_seconds=10, journal_records=1024, journal_bytes=1073741824)
                patches = [patch.object(preparation, 'BoundHistorySource', lambda *a, **k:source),
                           patch.object(preparation, 'HistoryReadOperations', ReadFixture)]
                with patches[0], patches[1]:
                    def open_market():
                        return preparation.SourcePreparingMarket(configuration,
                            wall_clock=lambda:1700000000 + source.now)
                    market = open_market()
                    try:
                        grid = market.base.expected_minutes('SSE.510300', '2026-11-03')
                        self.assertEqual(len(grid), 240)
                        complete = [dict(time=int(preparation.stamp(m).timestamp()*1000),
                            open=4.01, high=4.05, low=4., close=4.03, volume=100.+i, amount=403.+i)
                            for i, m in enumerate(grid)]
                        source.rows = complete[:initial_count] if isinstance(initial_count, int) else deepcopy(complete)
                        if initial_count == 'wrong-labels':
                            source.rows[1]['time'] = int(preparation.stamp(202611031131).timestamp()*1000)
                            source.rows.sort(key=lambda r:r['time'])
                        query = dict(exchange='SSE', code='510300', **{'from':grid[0], 'to':grid[-1]}, limit=len(grid))
                        request = dict(api_version=API_VERSION, action='history.source-query', request=query)
                        # 首次部分值可能与真实Writer边界冲突；后续仍须推进恢复。
                        if initial_count == 'wrong-labels':
                            # 240条且尾为15:00，但用11:31替代09:32，不能据条数认定该日完整。
                            original = market.base.call(request)
                            native = deepcopy(original)
                            native['data']['bars'] = [dict(symbol='SSE.510300',
                                minute=preparation.label(datetime.fromtimestamp(r['time']/1000, preparation.SHANGHAI)),
                                **{k:r[k] for k in ('open','high','low','close','volume','amount')}) for r in source.rows]
                            with patch.object(market.base, 'call', return_value=native):
                                market.call(request)
                        else:
                            market.call(request)
                        _, _, state = market._state(query)
                        self.assertEqual(source.prepares, 1)
                        self.assertEqual(state['published']['count'] if state['published'] else 0,
                            initial_count if isinstance(initial_count, int) else 240)
                        self.assertIsNone((state['published'] or {}).get('reconciled_day'))
                        original_prepare = state['prepare']['request']['request_id']
                        source.now += 61; source.rows = complete; source.pending_once = True
                        market.call(request)
                        _, _, waiting = market._state(query)
                        pending_id = source.pending_ids[-1]
                        self.assertEqual(waiting['follow_up']['runs'], 1)
                        self.assertFalse(waiting['follow_up']['reads'][-1]['verified'])
                        market.close(); source.hold_pending = False; market = open_market()
                        result = market.call(request)
                        _, _, final = market._state(query)
                        self.assertEqual(result['status']['code'], 'Ok')
                        self.assertEqual(len(result['data']['bars']), 240)
                        self.assertEqual([r['minute'] for r in result['data']['bars']], grid)
                        self.assertEqual(result['data']['bars'][-1]['volume'], 339.)
                        self.assertEqual(final['published']['count'], 240)
                        self.assertIn('reconciled_day', final['published'])
                        self.assertEqual(final['prepare']['request']['request_id'], original_prepare)
                        self.assertEqual(source.prepares, 1)
                        self.assertEqual(final['follow_up']['runs'], 1)
                        self.assertGreaterEqual(source.observed_ids.count(pending_id), 2)
                        self.assertEqual(final['follow_up']['reads'][-1]['capture']['pages'][0]['request']['request_id'], pending_id)
                    finally:
                        market.close()


if __name__ == '__main__':
    unittest.main()
