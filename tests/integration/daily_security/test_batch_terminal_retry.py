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
