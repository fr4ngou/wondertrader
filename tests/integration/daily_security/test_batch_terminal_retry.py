"""闭合日日线回读只对已确认的调用前拒绝创建后继槽。"""
import json
import time

import pytest

from integrations.guanheng.daily_batch_source import DailyBatchAnalysisSource
from guanheng_qmt_shm import read_retention_client
from guanheng_qmt_shm_agent.analysis_batch import POLICY


@pytest.mark.parametrize(('reply', 'expected'), [
    (dict(ok=False, error_code='queue_timeout'), '0000-none.r1.json'),
    (dict(ok=False, error_code='operation_interrupted'), '0000-none.r1.json'),
    (dict(ok=False, error_code='invalid_arguments'), '0000-none.json'),
    (None, '0000-none.json'),
])
def test_daily_readback_uses_new_slot_only_after_verified_retryable_result(
        tmp_path, monkeypatch, reply, expected):
    metadata = dict(binding=dict(host_instance_id='original', transport_generation='original'),
                    binding_sha256='fixture', profile={}, limits={})
    (tmp_path / 'BINDING.json').write_text(json.dumps(metadata), encoding='ascii')
    slots = tmp_path / 'slots'
    slots.mkdir()
    slot = slots / '0000-none.json'
    arguments = dict(symbols=['510300.SH'], adjustment='none')
    request = dict(operation_id='market.market_data', arguments=arguments, policy_id=POLICY)
    original = json.dumps(dict(metadata, request=request)).encode('ascii')
    slot.write_bytes(original)
    monkeypatch.setattr(read_retention_client, 'inspect_saved_result', lambda record: reply)
    source = object.__new__(DailyBatchAnalysisSource)

    selected = source._slot(tmp_path, '0000-none', arguments, time.monotonic() + 5)

    assert selected.name == expected
    assert slot.read_bytes() == original
    if selected != slot:
        monkeypatch.setattr(read_retention_client, 'inspect_saved_result',
                            lambda record: None if record.get('pending') else reply)
        selected.write_text(json.dumps(dict(metadata, request=request, pending=True)), encoding='ascii')
        assert source._slot(tmp_path, '0000-none', arguments, time.monotonic() + 5) == selected


def test_readback_prepares_only_batches_with_hpr_symbols(tmp_path):
    from hashlib import sha256
    from pathlib import Path
    from integrations.guanheng.daily_batch_source import seed_unaffected_readback_batches

    prior = tmp_path/'original'
    (prior/'slots').mkdir(parents=True)
    binding = {'host_instance_id': 'fixture'}
    body = b'{"binding":{"host_instance_id":"fixture"}}'
    (prior/'BINDING.json').write_bytes(body)
    batches = []
    for index, symbol in enumerate(('600000.SH','000001.SZ','000002.SZ')):
        for adjustment in ('none','front_ratio'):
            batch_id = f'{index:04d}-{adjustment}'
            path = Path('slots')/(batch_id+'.json')
            payload = batch_id.encode()
            (prior/path).write_bytes(payload)
            batches.append(dict(batch_id=batch_id, slot=path.as_posix(), binding=binding,
                                symbols=[symbol], sha256=sha256(payload).hexdigest()))
    readback = tmp_path/'readback'
    changed = {'000001.SZ'}
    seed_unaffected_readback_batches(readback,prior,dict(batches=batches),changed,check=lambda: None)
    assert (readback/'BINDING.json').read_bytes() == body
    copied = {path.name:path.read_bytes() for path in (readback/'slots').iterdir()}
    assert copied == {f'{i:04d}-{a}.json':f'{i:04d}-{a}'.encode() for i in (0,2) for a in ('none','front_ratio')}

    last = readback/'slots'/'0001-none.json'
    last.write_bytes(b'existing-resume-slot')
    seed_unaffected_readback_batches(readback,prior,dict(batches=batches),changed,check=lambda: None)
    assert last.read_bytes() == b'existing-resume-slot'
    assert (prior/'slots'/'0001-none.json').read_bytes() == b'0001-none'


def test_pool_change_keeps_matching_original_batches_and_resumes(tmp_path, monkeypatch):
    from datetime import datetime
    from hashlib import sha256
    from integrations.guanheng.daily_batch_source import seed_local_analysis_batches, seed_unaffected_readback_batches

    prior = tmp_path/'old'
    slots = prior/'slots'
    slots.mkdir(parents=True)
    binding = {'host_instance_id': 'fixture'}
    scope = {'max_data_bytes': 10000, 'max_symbols': 2}
    metadata = dict(binding=binding, profile={'operation_profiles': {'market.market_data': {'limits': scope}}})
    (prior/'BINDING.json').write_text(json.dumps(metadata))
    request = dict(source_kind='actual-qmt', start_date='20261109', end_date='20261113', max_rows=5)
    old_groups = [
        ['000001.SZ', '000002.SZ'],
        ['000003.SZ', '000004.SZ'],
        ['000005.SZ', '000006.SZ'],
    ]
    batches = []
    for index, group in enumerate(old_groups):
        for adjustment in ('none', 'front_ratio'):
            batch_id = f'{index:04d}-{adjustment}'
            payload = batch_id.encode()
            relative = f'slots/{batch_id}.json'
            (prior/relative).write_bytes(payload)
            batches.append(dict(batch_id=batch_id, slot=relative, binding=binding, adjustment=adjustment,
                                symbols=group, sha256=sha256(payload).hexdigest(),
                                requested_at='2026-11-15T12:00:00+00:00'))
    manifest = dict(request=dict(request, symbols=sum(old_groups, [])), batches=batches)
    (prior/'manifest.json').write_text(json.dumps(manifest))
    source = dict(directory=str(prior), sha256=sha256((prior/'manifest.json').read_bytes()).hexdigest())
    monkeypatch.setattr('integrations.guanheng.analysis_price_capture.load_price_capture', lambda desc: manifest)
    request['symbols'] = ['000001.SZ', '000003.SZ', '000004.SZ', '000005.SZ', '000006.SZ', '600001.SH']
    root = tmp_path/'new'
    root.mkdir()
    seed_local_analysis_batches(root, request, [source],
        {'000005.SZ': datetime.fromisoformat('2026-11-15T12:15:00+00:00')}, check=lambda: None)

    output = root/'cache'
    plan = [['000003.SZ', '000004.SZ'], ['000001.SZ', '000005.SZ'], ['000006.SZ', '600001.SH']]
    owner = object.__new__(DailyBatchAnalysisSource)
    assert owner._batches(output, request, scope) == plan
    assert {path.name:path.read_bytes() for path in (output/'slots').iterdir()} == {
        '0000-none.json': b'0001-none', '0000-front_ratio.json': b'0001-front_ratio'}
    (output/'slots'/'0000-none.json').unlink()
    (output/'REQUEST.json').write_text(json.dumps(request))
    seed_local_analysis_batches(root, request, [], {}, check=lambda: None)
    assert (output/'slots'/'0000-none.json').read_bytes() == b'0001-none'

    readback = root/'readback'
    completed = dict(batches=[dict(batch, batch_id=batch['batch_id'].replace('0001-', '0000-'),
                                    slot=batch['slot'].replace('0001-', '0000-')) for batch in batches[2:4]])
    seed_unaffected_readback_batches(readback, output, completed, {'600001.SH'}, check=lambda: None)
    assert owner._batches(readback, request, scope) == plan
    assert (readback/'slots'/'0000-none.json').read_bytes() == b'0001-none'

def test_parallel_hpr_planning_shares_only_the_metadata_publication_lock(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier, Lock
    from time import sleep
    from integrations.guanheng import daily_gap_update

    planning = Barrier(4)
    active = 0
    def publish(*args):
        nonlocal active
        active += 1
        assert active == 1
        sleep(.02)
        active -= 1

    class Transport:
        def plan(self, operation, arguments, metadata, deadline):
            planning.wait(timeout=3)
            return arguments

    monkeypatch.setattr('guanheng_qmt_shm.market_daily_preparation._original', publish)
    monkeypatch.setattr(daily_gap_update, '_hpr_business_identity', lambda value: 'same provider')
    lock = Lock()
    clients = [daily_gap_update._GapTransport(Transport(), {}, tmp_path, lock) for _ in range(4)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = [pool.submit(client.plan,'market.history_prepare',i,{'binding':{}},None)
                   for i,client in enumerate(clients)]
        assert [future.result(timeout=5) for future in results] == [0,1,2,3]
