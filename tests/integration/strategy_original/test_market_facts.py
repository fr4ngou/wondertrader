"""原版已发布读取的窗口、单位与同快照边界；固定合成API不启动来源采集。"""
from copy import deepcopy
from datetime import date, datetime, timezone
from pathlib import Path
import importlib.util
import sys

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'apps/guanheng/strategy_original'))
SPEC = importlib.util.spec_from_file_location('original_market_facts_candidate', ROOT / 'apps/wt_runtime/guanheng_wt_runtime/original_market_facts.py')
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

IDENTITY = '1' * 64
REFERENCE = 'qmt-front-ratio-reference:' + '2' * 64
NOW = datetime(2026, 11, 7, tzinfo=timezone.utc)


class Published:
    def __init__(self):
        self.calls = []
        self.changed = False
        self.reference_mismatch = False
        self.mixed_units = False
        self.repeat_cursor = False

    @staticmethod
    def ok(data):
        return dict(status=dict(code='Ok'), data=data)

    def source_market_snapshot_query(self, day):
        self.calls.append(('snapshot', day))
        return self.ok(dict(observation_date=day, snapshot_id=('3' * 64 if self.changed and len(self.calls) > 1 else IDENTITY), provenance={}))

    def source_daily_history_batch_query(self, request):
        self.calls.append(('history', deepcopy(request)))
        results = []
        for symbol in request['symbols']:
            bars = [dict(date=d, open=2., high=2.1, low=1.9, close=2., volume=100.)
                    for d in (20231229, 20261106) if request['from'] <= d <= request['to']]
            unit = 'unknown' if self.mixed_units and request['from'] > 20240101 else 'CNY'
            reference = REFERENCE if request['adjustment'] == 'front_ratio' else ''
            if self.reference_mismatch and symbol == 'SSE.000300' and reference:
                reference = 'qmt-front-ratio-reference:' + '4' * 64
            metadata = dict(adjustment=request['adjustment'], price_unit=unit,
                            volume_unit='unknown' if unit == 'unknown' else 'lot', factor_version=reference)
            results.append(dict(symbol=symbol, status=dict(code='Ok'), data=dict(source_snapshot_id=IDENTITY, metadata=metadata, bars=bars)))
        return self.ok(dict(results=results))

    def source_supplement_query(self, request):
        self.calls.append(('supplement', deepcopy(request)))
        offset = request['offset']
        rows = []
        for symbol in request['symbols']:
            rows.append(dict(date='2023-12-29' if offset == 0 else '2026-11-06', value='100',
                             unit='share' if request['metric'] == 'etf_total_shares' else 'CNY',
                             symbol=symbol, source_sha256='5' * 64, received_at=NOW.isoformat(), available_at=None))
        following = (offset if self.repeat_cursor else 1) if offset == 0 else None
        return self.ok(dict(source_snapshot_id=IDENTITY, source_sha256='6' * 64, rows=rows, gaps=[], selection=dict(next_offset=following)))


def collect(client, **kwargs):
    return MODULE.collect_current_facts(client, observation_date='2026-11-06', history_from='2019-01-01',
                                        codes=('510300',), utcnow=lambda: NOW, **kwargs)


def test_complete_prefix_read_is_bounded_and_never_prepares_source():
    client = Published()
    result = collect(client)
    assert result.facts['calendar'] == ['2023-12-29', '2026-11-06']
    assert len(result.facts['shares']) == 2
    assert result.facts['analysis']['510300']['price_unit'] == 'CNY/share'
    assert result.facts['analysis']['000300']['price_unit'] == 'index-point'
    assert result.facts['analysis']['510300']['factor_version'] == REFERENCE
    for kind, request in client.calls:
        if kind == 'history':
            first = date.fromisoformat(str(request['from'])[:4] + '-' + str(request['from'])[4:6] + '-' + str(request['from'])[6:])
            last = date.fromisoformat(str(request['to'])[:4] + '-' + str(request['to'])[4:6] + '-' + str(request['to'])[6:])
            assert (last - first).days < request['limit'] == 2000
            assert request['snapshot_id'] == IDENTITY
    assert result.diagnostics['source_operations'] == 0
    assert {kind for kind, _ in client.calls} == {'history', 'snapshot', 'supplement'}


def test_unknown_unit_downgrades_packet_and_preserves_original_labels():
    client = Published(); client.mixed_units = True
    result = collect(client)
    assert result.facts['analysis']['510300']['price_unit'] == 'unknown'
    assert result.diagnostics['history']['analysis:510300']['unit_uncertainty']
    assert result.diagnostics['history']['analysis:510300']['volume_scale_continuity_qualified'] is False


def test_empty_early_window_does_not_bind_a_price_reference():
    client = Published()
    result = MODULE.collect_current_facts(client, observation_date='2026-11-06', history_from='2010-01-01', codes=('510300',), utcnow=lambda: NOW)
    assert [b['date'] for b in result.facts['analysis']['510300']['bars']] == ['2023-12-29', '2026-11-06']


def test_front_reference_differs_between_securities_is_rejected():
    client = Published(); client.reference_mismatch = True
    with pytest.raises(MODULE.OriginalFactsUnavailable, match='analysis_reference_changed'):
        collect(client)


def test_unknown_middle_window_preserves_earlier_known_unit():
    class ThreeWindows(Published):
        def source_daily_history_batch_query(self, request):
            reply = super().source_daily_history_batch_query(request)
            unit_by_date = {20200102: 'share', 20220104: 'unknown', 20261106: 'lot'}
            for row in reply['data']['results']:
                dates = [day for day in unit_by_date if request['from'] <= day <= request['to']]
                row['data']['bars'] = [dict(date=day, open=2., high=2.1, low=1.9, close=2., volume=100.) for day in dates]
                if dates:
                    row['data']['metadata']['volume_unit'] = unit_by_date[dates[0]]
            return reply
    with pytest.raises(MODULE.OriginalFactsUnavailable, match='history_basis_changed'):
        MODULE.collect_current_facts(ThreeWindows(), observation_date='2026-11-06', history_from='2010-01-01', codes=('510300',), utcnow=lambda: NOW)


def test_snapshot_changed_during_collection_is_rejected():
    client = Published(); client.changed = True
    with pytest.raises(MODULE.OriginalFactsUnavailable, match='publication_changed_during_read'):
        collect(client)


def test_nonadvancing_supplement_cursor_is_rejected():
    client = Published(); client.repeat_cursor = True
    with pytest.raises(MODULE.OriginalFactsUnavailable, match='supplement_cursor_invalid'):
        collect(client)


def test_single_total_deadline_applies_after_request():
    ticks = iter((0., 0., 2.))
    with pytest.raises(TimeoutError, match='deadline'):
        collect(Published(), seconds=1., clock=lambda: next(ticks))
