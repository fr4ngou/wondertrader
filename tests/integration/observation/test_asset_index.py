"""增量目录保留当前输入和历史查阅，避免每轮复制全部历史元数据。"""
import copy
import tempfile
import unittest
from pathlib import Path
from time import monotonic
from unittest.mock import patch

from guanheng_app.observation import collection
from guanheng_app.observation.admission import admit_dataset, register_standard_asset, register_standard_assets
from guanheng_app.observation.asset_index import compact_assets, references
from guanheng_app.observation.contracts import ObservationError, USAGE
from guanheng_app.observation.metadata import asset_contract
from guanheng_app.observation.publication import adopt_snapshot, validate_manifest
from guanheng_app.observation.runtime import build_reader
from guanheng_app.observation.storage import digest, encode


def fixture(reader):
    definition = dict(id='fixture', board='fixture', label='验证值', definition_version='fixture/1',
        frequency='日频', source='合成资料', source_url='', unit='倍', parameters=False,
        primary_field='value', field_schema={'date': dict(label='日期', data_type='date'),
            'value': dict(label='值', data_type='number', unit='倍')},
        lines=[dict(key='value', name='值', unit='倍', color='#123456', formula='原值', reading='合成资料')],
        limitations=['合成资料'], reading='合成资料', formula='原值')
    item = admit_dataset(reader.objects, definition, [dict(date='2026-11-04', value=1.)], [])
    manifest = dict(schema_version='market-observation/1', published_at='2026-11-05T01:00:00+00:00',
        boards=[dict(id='fixture', label='验证')], preferences=dict(default_board='fixture', default_datasets={}),
        datasets={'fixture': item}, assets={}, usage=USAGE)
    register_standard_assets(reader.objects, manifest)
    return manifest


class AssetIndexTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.reader = build_reader(Path(self.temp.name).resolve())
        self.reader.repository.initialize()

    def tearDown(self):
        self.temp.cleanup()

    def test_refresh_keeps_direct_lineage_and_old_snapshot_download(self):
        reader = self.reader
        original = fixture(reader)
        raw = reader.objects.put(b'old raw capture')
        old_asset = register_standard_asset(reader.objects, original, 'old.capture', raw, [], 'standard.capture-manifest')
        # 累积历史父项曾进入每轮新目录；前代快照继续完整持有这些关系。
        original['datasets']['fixture']['parents'] = [raw]
        register_standard_assets(reader.objects, original)
        previous = digest(encode(original))
        adopt_snapshot(reader, original, previous, None, monotonic() + 30)

        class Fetch:
            def __init__(self, *args, **kwargs): self.records = []
            def close(self): pass

        config = dict(timeout_seconds=1, allowed_hosts=[], max_days_per_batch=2, models={},
            sources=[dict(id='fixture', kind='fixture', datasets=['fixture'])],
            budget=dict(seconds=30, max_requests=2, max_bytes=1024*1024, response_bytes=1024*1024))
        with patch.dict(collection.PARSERS, fixture=lambda *args: {'fixture': [dict(date='2026-11-05', value=2.)]}):
            result = collection.refresh(reader, config, as_of='2026-11-05', deadline=monotonic()+30, fetcher_factory=Fetch)
        self.assertEqual(result['status'], 'success', result)
        current = reader.repository.get(result['current_snapshot'])
        self.assertEqual(reader.rows(current['datasets']['fixture']['partition']),
            [dict(date='2026-11-04', value=1.), dict(date='2026-11-05', value=2.)])
        self.assertNotIn(raw, current['datasets']['fixture']['parents'])
        self.assertIn(original['datasets']['fixture']['partition'], current['datasets']['fixture']['parents'])
        hashes, _ = references(current)
        self.assertTrue(hashes <= {a['sha256'] for a in current['assets'].values()})
        self.assertNotIn(old_asset, current['assets'])
        self.assertTrue(all(a['previous_snapshot'] == previous for a in current['assets'].values()
            if a.get('group') == 'standard.metric'))
        self.assertEqual(reader.repository.get(previous), original)
        self.assertEqual(reader.objects.get(reader.repository.get(previous)['assets'][old_asset]['sha256']), b'old raw capture')
        self.assertEqual(validate_manifest(reader, current, monotonic()+30)['rows'], 2)

    def test_repeated_updates_keep_one_current_dynamic_generation(self):
        reader = self.reader
        previous = fixture(reader)
        raw = reader.objects.put(b'unmodified public response')
        counts = []
        for iteration in range(100):
            previous_id = digest(encode(previous))
            candidate = copy.deepcopy(previous)
            item = candidate['datasets']['fixture']
            item['parents'] = [raw]
            register_standard_asset(reader.objects, candidate, 'capture', raw, [], 'source.capture',
                iteration=iteration)
            # 本轮抓取事件的身份与实际refresh一样包含每次不同的实收时点。
            identity = str(iteration).zfill(64)
            candidate['assets'][identity] = asset_contract(dict(asset_id=identity, sha256=raw,
                bytes=len(reader.objects.get(raw)), group='source.capture', source_ref='fixture'))
            register_standard_assets(reader.objects, candidate)
            compact_assets(reader.objects, candidate, previous, previous_id, active_asset_ids=[identity])
            counts.append(len(candidate['assets']))
            previous = candidate
        self.assertEqual(max(counts[2:]), min(counts[2:]))
        self.assertLess(max(counts), 6)

    def test_missing_direct_input_cannot_be_hidden_by_compaction(self):
        reader = self.reader
        previous = fixture(reader)
        candidate = copy.deepcopy(previous)
        candidate['datasets']['fixture']['parents'] = ['b'*64]
        with self.assertRaises(ObservationError) as error:
            compact_assets(reader.objects, candidate, previous, digest(encode(previous)))
        self.assertEqual(error.exception.code, 'asset_unavailable')

    def test_stock_archive_lists_current_partition_and_keeps_old_version_in_previous(self):
        reader = self.reader
        previous = fixture(reader)
        old_sha = reader.objects.put(b'previous stock partition')
        new_sha = reader.objects.put(b'current stock partition')
        key = 'stock-pb.sh.2026'
        old_id = digest(encode(dict(dataset=key, sha256=old_sha)))
        new_id = digest(encode(dict(dataset=key, sha256=new_sha)))
        previous['assets'][old_id] = asset_contract(dict(asset_id=old_id, sha256=old_sha,
            bytes=len(reader.objects.get(old_sha)), group='standard.stock-pb', source_ref=key))
        candidate = copy.deepcopy(previous)
        candidate['assets'][new_id] = asset_contract(dict(asset_id=new_id, sha256=new_sha,
            bytes=len(reader.objects.get(new_sha)), group='standard.stock-pb', source_ref=key))
        current_metadata = copy.deepcopy(candidate['assets'][new_id])
        candidate['stock_pb_partitions'] = dict(partitions={key: dict(sha256=new_sha, parent_assets=[])})
        compact_assets(reader.objects, candidate, previous, digest(encode(previous)))
        self.assertIn(new_id, candidate['assets'])
        self.assertEqual(candidate['assets'][new_id], current_metadata)
        self.assertNotIn(old_id, candidate['assets'])
        self.assertIn(old_id, previous['assets'])


if __name__ == '__main__':
    unittest.main()
