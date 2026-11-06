"""MSF03查询主链：固定文件、快照、真实HTTP及SDK，不启动QMT/交易。"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import queue
import tempfile
import threading
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'apps/guanheng'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'market_supplement'))
from msf_fixture import capture_metadata
from guanheng_app.observation.storage import ContentStore

from integrations.guanheng.market_service import MarketHTTPServer
from integrations.guanheng.market_snapshot import SnapshotSourceMarket
from integrations.guanheng.market_snapshot_prepare import prepare_market_snapshot
from integrations.guanheng.market_supplement_store import MarketSupplementStore
from integrations.guanheng_market_client import API_VERSION, MarketClient, MarketProtocolError, MarketUnavailable
from integrations.guanheng_market_client.market_snapshot import snapshot_identity, validate_market_snapshot
from integrations.guanheng_market_client.supplement_facts import (
    MAX_CATALOG_BYTES, validate_supplement_catalog, validate_supplement_request, validate_supplement_data,
)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf8')


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    body = encoded(value)
    path.write_bytes(body)
    return dict(path=str(path.absolute()), sha256=hashlib.sha256(body).hexdigest())


def fact(day, symbol, value='175001.25', metric='etf_total_shares', unit='share'):
    return dict(date=day, symbol=symbol, metric=metric, value=value, unit=unit, source='SSE',
                source_sha256='a' * 64, received_at='2020-01-04T00:00:00+00:00', available_at=None)


def catalog(raw_store=None):
    return dict(
        schema='guanheng.market-supplement-catalog.v1',
        raw_store=str(raw_store or Path(tempfile.gettempdir()) / 'msf-fixture-root'),
        targets=[dict(metric='etf_total_shares', symbol=s, **{'from': '2020-01-02'})
                 for s in ['SSE.510050', 'SSE.510300']],
        dates=['2020-01-02', '2020-01-03'], policy='qmt_preferred',
        qmt_evidence=dict(source_sha256='b' * 64, profile_version='qmt.read-profile.v7',
            operations=['market.divid_factors', 'market.market_data'],
            decisions=[dict(metric='etf_total_shares', reason='not_exposed_by_bound_profile')]),
        rows=[fact('2020-01-02', 'SSE.510050'), fact('2020-01-03', 'SSE.510050', '175002.75'),
              fact('2020-01-03', 'SSE.510300', '200100')],
        gaps=[dict(date='2020-01-02', symbol='SSE.510300', metric='etf_total_shares', reason='source_not_published')],
        complete=False)


def bind_sources(value):
    """完整原件夹具；两行可共享父原件，proof逐事实绑定原值。"""
    objects = ContentStore(value['raw_store'])
    parent = objects.put(b'isolated synthetic original ETF disclosure')
    value['qmt_evidence']['source_sha256'] = objects.put(encoded(dict(
        profile_version='qmt.read-profile.v7', operations=['market.divid_factors', 'market.market_data'], order_ready=False)))
    for row in value['rows']:
        proof = {key: row[key] for key in ('date', 'symbol', 'metric', 'value', 'unit', 'source')}
        proof.update(schema='guanheng.supplement-source-proof.v1', parents=[parent])
        row['source_sha256'] = objects.put(encoded(proof))
    return value


def snapshot(base, supplement=None):
    value = dict(schema='guanheng.market-source-snapshot.v1', snapshot_id='0' * 64,
        observation_date='2020-01-03', members=['SSE.600000'], source_kind='sdk-synthetic',
        source_received_at='2020-01-04T00:00:00+00:00', price_bases=['none', 'front_ratio'],
        price_reference=dict(kind='supplier_current_front_ratio', capture_sha256='c' * 64,
            requested_from='20200101', requested_to='20200103', reference_date=None, independent_factors=None),
        basics={'SSE.600000': None}, provenance=dict(capture_sha256='c' * 64,
            source_binding_sha256='d' * 64, universe_sha256='e' * 64, basics_sha256='f' * 64,
            base_configuration_sha256=hashlib.sha256(encoded(base)).hexdigest()))
    if supplement is not None:
        value['provenance']['supplement_facts_sha256'] = supplement['sha256']
    value['snapshot_id'] = snapshot_identity(value)
    return validate_market_snapshot(value)


def request(identity, **updates):
    value = dict(snapshot_id=identity, metric='etf_total_shares', symbols=['SSE.510050', 'SSE.510300'],
                 **{'from': '2020-01-02', 'to': '2020-01-03'}, offset=0, limit=2)
    value.update(updates)
    return value


class BaseMarket:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class SupplementTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.descriptor = write(self.root / 'catalog.json', bind_sources(catalog(self.root / 'raw')))
        self.base = dict(mode='source-catalog')

    def tearDown(self):
        self.temporary.cleanup()

    def config(self, supplement=True):
        descriptor = self.descriptor if supplement else None
        value = snapshot(self.base, descriptor)
        config = dict(mode='source-market-snapshot', base=self.base,
                      snapshot=write(self.root / ('with.json' if supplement else 'old.json'), value))
        if supplement:
            config['supplement_facts'] = descriptor
        return value, config

    def market(self, config):
        with patch('integrations.guanheng.source_market.create_native_source_market', return_value=BaseMarket()):
            return SnapshotSourceMarket(config, max_response_bytes=8 * 1024 * 1024)

    def test_http_sdk_pages_facts_and_gaps_in_single_sequence(self):
        value, config = self.config()
        ready = queue.Queue()
        stopped = threading.Event()
        failures = []

        def serve():
            server = None
            try:
                server = MarketHTTPServer(('127.0.0.1', 0), self.market(config), 'isolated-msf-test-token')
                server.timeout = .05
                ready.put(server.server_port)
                while not stopped.is_set():
                    server.handle_request()
            except BaseException as error:
                failures.append(error)
                ready.put(None)
            finally:
                if server is not None:
                    server.server_close()

        thread = threading.Thread(target=serve)
        thread.start()
        try:
            port = ready.get(timeout=5)
            self.assertIsNotNone(port, failures)
            client = MarketClient(f'http://127.0.0.1:{port}', 'isolated-msf-test-token')
            first = client.source_supplement_query(request(value['snapshot_id']))
            second = client.source_supplement_query(request(value['snapshot_id'], offset=2))
            self.assertEqual(first['status']['code'], 'Ok')
            self.assertEqual(first['data']['rows'][0]['value'], '175001.25')
            self.assertEqual(len(first['data']['gaps']), 1)
            self.assertEqual(first['data']['selection'], dict(offset=0, limit=2, total=4, next_offset=2))
            self.assertEqual([r['symbol'] for r in second['data']['rows']], ['SSE.510050', 'SSE.510300'])
            self.assertIsNone(second['data']['selection']['next_offset'])
            conflict = client.source_supplement_query(request('9' * 64))
            self.assertEqual(conflict['status']['code'], 'Conflict')
        finally:
            stopped.set()
            thread.join(timeout=5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(failures, [])

    def test_missing_corrupt_empty_and_conflict_are_distinct(self):
        old, config = self.config(False)
        market = self.market(config)
        try:
            self.assertEqual(self.call(market, request(old['snapshot_id']))['status']['code'], 'NotSupported')
        finally:
            market.close()
        current, config = self.config()
        market = self.market(config)
        try:
            empty = self.call(market, request(current['snapshot_id'], symbols=['SSE.588000']))
            self.assertEqual(empty['status']['code'], 'Ok')
            self.assertEqual(empty['data']['selection']['total'], 0)
            beyond = self.call(market, request(current['snapshot_id'], offset=60000))
            self.assertEqual(beyond['data']['rows'], [])
            self.assertIsNone(beyond['data']['selection']['next_offset'])
            # 已准入后源文件被破坏也必须显式报IoError，不能隐藏源损坏。
            Path(self.descriptor['path']).write_bytes(b'{}')
            damaged = self.call(market, request(current['snapshot_id']))
            self.assertEqual(damaged['status']['code'], 'IoError')
            self.assertEqual(damaged['data'], {})
        finally:
            market.close()

    @staticmethod
    def call(market, query):
        return market.call(dict(api_version=API_VERSION, action='market.source-supplement-query', request=query))

    def test_catalog_rejects_ambiguous_coverage_units_values_and_identity(self):
        variants = []
        for field, value in [('value', 'NaN'), ('value', '-1'), ('unit', 'CNY'),
                             ('received_at', '2020-01-04T08:00:00+08:00'),
                             ('available_at', '2020-01-05T00:00:00+00:00')]:
            bad = catalog()
            bad['rows'][0][field] = value
            variants.append(bad)
        bad = catalog(); bad['rows'].append(deepcopy(bad['rows'][0])); variants.append(bad)
        bad = catalog(); bad['gaps'] = []; variants.append(bad)
        bad = catalog(); bad['complete'] = True; variants.append(bad)
        bad = catalog(); bad['dates'].reverse(); variants.append(bad)
        bad = catalog(); bad['qmt_evidence']['secret'] = 'forbidden'; variants.append(bad)
        bad = catalog(); bad['qmt_evidence']['decisions'] = []; variants.append(bad)
        for index, bad in enumerate(variants):
            with self.subTest(index=index), self.assertRaises(MarketProtocolError):
                validate_supplement_catalog(bad)
        unknown = catalog(); unknown['rows'][0]['unit'] = 'unknown'
        validate_supplement_catalog(unknown)

    def test_request_and_response_contract_reject_bad_pages_and_wrong_scope(self):
        good = request('1' * 64)
        for updates in [dict(offset=True), dict(limit=2001), dict(symbols=['SSE.510300', 'SSE.510050']),
                        dict(symbols=['SSE.510050', 'SSE.510050']),
                        dict(metric='margin_balance', symbols=['CN.SH_SZ']), dict(to='2020-13-40')]:
            with self.subTest(updates=updates), self.assertRaises(MarketProtocolError):
                validate_supplement_request(dict(good, **updates))
        validate_supplement_request(dict(good, metric='margin_balance', symbols=['CN.MARGIN_REPORT']))
        store = MarketSupplementStore(self.descriptor)
        try:
            page = store.query(good)
            wrong = deepcopy(page); wrong['selection']['next_offset'] = None
            with self.assertRaises(MarketProtocolError):
                validate_supplement_data(wrong, good)
            wrong = deepcopy(page); wrong['source_snapshot_id'] = '2' * 64
            with self.assertRaises(MarketProtocolError):
                validate_supplement_data(wrong, good)
            page['rows'][0]['value'] = '0'
            self.assertEqual(store.query(good)['rows'][0]['value'], '175001.25')
        finally:
            store.close()

    def test_fixed_file_budget_sha_dates_thread_and_close(self):
        bad = dict(self.descriptor, sha256='0' * 64)
        with self.assertRaises(ValueError):
            MarketSupplementStore(bad)
        with self.assertRaises(ValueError):
            MarketSupplementStore(self.descriptor, observation_date='2020-01-02')
        store = MarketSupplementStore(self.descriptor)
        errors = []
        thread = threading.Thread(target=lambda: self.foreign_query(store, errors))
        thread.start(); thread.join(timeout=5)
        self.assertEqual(errors, [MarketUnavailable])
        store.close()
        with self.assertRaises(MarketUnavailable):
            store.query(request('1' * 64))
        # 容量按实际文件长度拒绝，未解析超额正文。
        huge = self.root / 'oversized.json'
        with huge.open('wb') as stream:
            stream.truncate(MAX_CATALOG_BYTES + 1)
        with self.assertRaises(ValueError):
            MarketSupplementStore(dict(path=str(huge), sha256='0' * 64))

    def test_proof_parent_and_qmt_object_integrity_and_page_deduplication(self):
        store = MarketSupplementStore(self.descriptor)
        try:
            query = request('1' * 64, offset=2)
            with patch.object(store._objects, 'get', wraps=store._objects.get) as get:
                page = store.query(query)
            self.assertEqual(len(page['rows']), 2)
            identities = [item.args[0] for item in get.call_args_list]
            self.assertEqual(len(identities), len(set(identities)))
            proof_identity = page['rows'][0]['source_sha256']
            proof_body = store._objects.get(proof_identity)
            parent = json.loads(proof_body)['parents'][0]
            for identity in [proof_identity, parent, page['qmt_evidence']['source_sha256']]:
                with self.subTest(identity=identity):
                    path = store._objects.path(identity)
                    original = path.read_bytes()
                    path.write_bytes(b'damaged source object')
                    try:
                        with self.assertRaises(ValueError):
                            store.query(query)
                    finally:
                        path.write_bytes(original)
            self.assertNotIn('raw_store', page)
        finally:
            store.close()

    def test_proof_value_mismatch_is_rejected(self):
        value = bind_sources(catalog(self.root / 'raw'))
        objects = ContentStore(value['raw_store'])
        row = value['rows'][0]
        proof = json.loads(objects.get(row['source_sha256']))
        proof['value'] = '99999'
        row['source_sha256'] = objects.put(encoded(proof))
        descriptor = write(self.root / 'wrong-proof.json', value)
        store = MarketSupplementStore(descriptor)
        try:
            with self.assertRaises(MarketProtocolError):
                store.query(request('1' * 64))
        finally:
            store.close()

    def test_whole_catalog_verification_rejects_off_page_damage_and_honors_owner_check(self):
        store = MarketSupplementStore(self.descriptor)
        try:
            checks = []
            store.verify_sources(check=lambda: checks.append(True))
            self.assertGreaterEqual(len(checks), 4)
            def cancelled():
                raise InterruptedError('isolated owner cancellation')
            with self.assertRaises(InterruptedError):
                store.verify_sources(check=cancelled)
            # 第0页查询可用，仍要在发布整目录时发现第1页proof原件被破坏。
            proof = store.catalog['rows'][-1]['source_sha256']
            path = store._objects.path(proof)
            original = path.read_bytes()
            path.write_bytes(b'damaged off-page proof')
            try:
                self.assertEqual(len(store.query(request('1' * 64))['rows']), 1)
                with self.assertRaises(ValueError):
                    store.verify_sources()
            finally:
                path.write_bytes(original)
        finally:
            store.close()

    def test_two_market_source_keeps_both_exchange_identity(self):
        turnover = fact('2020-01-02', 'CN.SH_SZ', '301002003.12', 'market_turnover', 'CNY')
        turnover['source'] = 'SSE+SZSE'
        value = catalog(self.root / 'raw')
        value.update(targets=[dict(metric='market_turnover', symbol='CN.SH_SZ', **{'from': '2020-01-02'})],
                     dates=['2020-01-02'], rows=[turnover], gaps=[], complete=True)
        value['qmt_evidence']['decisions'] = [dict(metric='market_turnover', reason='not_exposed_by_bound_profile')]
        value = bind_sources(value)
        store = MarketSupplementStore(write(self.root / 'two-markets.json', value))
        try:
            page = store.query(request('1' * 64, metric='market_turnover', symbols=['CN.SH_SZ']))
            self.assertEqual(page['rows'][0]['source'], 'SSE+SZSE')
            self.assertEqual(page['rows'][0]['value'], '301002003.12')
        finally:
            store.close()

    @staticmethod
    def foreign_query(store, errors):
        try:
            store.query(request('1' * 64))
        except BaseException as error:
            errors.append(type(error))

    def test_snapshot_descriptor_binding_and_old_identity(self):
        old, old_config = self.config(False)
        self.assertNotIn('supplement_facts_sha256', old['provenance'])
        self.assertEqual(snapshot_identity(old), old['snapshot_id'])
        current, config = self.config()
        self.assertNotEqual(current['snapshot_id'], old['snapshot_id'])
        omitted = deepcopy(config); omitted.pop('supplement_facts')
        with self.assertRaises(ValueError):
            self.market(omitted)
        changed = deepcopy(config); changed['supplement_facts']['sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            self.market(changed)

    def test_prepare_snapshot_includes_optional_catalog_and_preserves_legacy_bytes(self):
        native = self.root / 'native'
        native.mkdir()
        metadata = capture_metadata()
        binding = metadata['binding']
        universe = self.root / 'universe.json'
        universe_desc = write(universe, dict(members=['sh.600000'], market_count=1,
            unresolved_identity_count=0, date='2020-01-03'))
        capture = self.root / 'capture'
        write(capture / 'BINDING.json', metadata)
        imported = native / 'IMPORT.json'
        write(imported, dict(schema='guanheng.qmt-analysis-native-import.v1', state='completed',
            capture_sha256='c' * 64, securities=1, observation_date='20200103', stores=[],
            source_kind='sdk-synthetic', source_received_at='2020-01-04T00:00:00+00:00'))
        write(native / 'PROVENANCE.json', dict(capture_sha256='c' * 64, capture=str(capture),
            request=dict(universe=universe_desc, start_date='20200101', end_date='20200103'),
            batches=[dict(binding=binding)]))
        basic = self.root / 'basic'; basic.mkdir()
        body = encoded(dict(symbol='600000.SH', value=None)) + b'\n'
        (basic / 'rows.jsonl').write_bytes(body)
        write(basic / 'RESULT.json', dict(state='completed', rows_sha256=hashlib.sha256(body).hexdigest()))
        base = dict(mode='source-catalog', stores=[])
        outputs = [self.root / name for name in ['legacy-omitted', 'legacy-none', 'supplement']]
        prepare_market_snapshot(base, imported, universe, basic, outputs[0])
        prepare_market_snapshot(base, imported, universe, basic, outputs[1], supplement_facts=None)
        prepare_market_snapshot(base, imported, universe, basic, outputs[2], supplement_facts=self.descriptor)
        self.assertEqual((outputs[0] / 'snapshot.json').read_bytes(), (outputs[1] / 'snapshot.json').read_bytes())
        legacy = json.loads((outputs[0] / 'snapshot.json').read_bytes())
        updated = json.loads((outputs[2] / 'snapshot.json').read_bytes())
        self.assertNotEqual(legacy['snapshot_id'], updated['snapshot_id'])
        self.assertEqual(updated['provenance']['supplement_facts_sha256'], self.descriptor['sha256'])
        prepared_config = json.loads((outputs[2] / 'source.json').read_bytes())
        market = self.market(prepared_config)
        try:
            self.assertEqual(self.call(market, request(updated['snapshot_id']))['status']['code'], 'Ok')
        finally:
            market.close()
        # 发布准备必须核全部原件；当前页以外的proof损坏也不能写出候选snapshot。
        objects = ContentStore(catalog(self.root / 'raw')['raw_store'])
        retained = json.loads(Path(self.descriptor['path']).read_bytes())
        path = objects.path(retained['rows'][-1]['source_sha256'])
        original = path.read_bytes()
        path.write_bytes(b'corrupt publication proof')
        rejected = self.root / 'rejected-snapshot'
        try:
            with self.assertRaises(ValueError):
                prepare_market_snapshot(base, imported, universe, basic, rejected, supplement_facts=self.descriptor)
            self.assertFalse(rejected.exists())
        finally:
            path.write_bytes(original)


if __name__ == '__main__':
    unittest.main()
