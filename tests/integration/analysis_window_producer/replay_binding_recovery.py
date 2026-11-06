"""Frozen source-generation recovery replay, using the real retained client and AWP owner.
Run with the installed runtime Python (-I -B); no live connection or operation is used.
"""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import sys
import threading
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / 'apps/analysis_window_producer'), str(ROOT)]
from guanheng_analysis_window_producer.source import (
    BoundAnalysisClient, AnalysisSnapshotProvider, SourcePending, SourceUnavailable)
from guanheng_analysis_window_producer.runtime import AnalysisWindowProducer
from guanheng_qmt_shm.read_retention_client import RetainedReadBindingChanged, RetainedReadPending, RetainedReadFailure
from integrations.guanheng.source_history_transport import BoundHistorySource


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frozen', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=False)
    frozen = json.loads((args.frozen / 'FROZEN.json').read_bytes())
    assert all(sha(args.frozen / name) == digest for name, digest in frozen['frozen_files'].items())
    metadata = json.loads((args.frozen / 'current-source/BINDING.json').read_bytes())
    configuration = dict(base_url='http://127.0.0.1:1', key_id='isolated-analysis-replay',
        secret_env='ANALYSIS_REPLAY_SECRET', timeout=1, read_retention=metadata['profile']['read_retention'])
    environment = {'ANALYSIS_REPLAY_SECRET': 'isolated-analysis-replay-secret-000000'}
    calls, failures = [], []

    def exchange(owner, method, path, body, deadline):
        calls.append((method, path))
        if path.endswith('/read-retention-status'):
            return 200, dict(retained=0, capacity=1024)
        if path.endswith('/read-binding'):
            return 200, {k: v for k, v in metadata.items() if k != 'profile'}
        if path.endswith('/lookup'):
            return 404, {}
        raise AssertionError('new source operation forbidden in replay')

    def client():
        result = BoundAnalysisClient(configuration, environ=environment)
        original = result.retained.read
        def checked(*a, **kw):
            try:
                return original(*a, **kw)
            except (RetainedReadFailure, RetainedReadPending) as error:
                failures.append((type(error).__name__, str(error)))
                raise
        result.retained.read = checked
        return result

    old = args.work / 'old'
    shutil.copytree(args.frozen / 'old-source', old)
    original_files = {p.name: sha(p) for p in old.glob('*.json')}
    request = json.loads((args.frozen / 'OLD-REQUEST.json').read_bytes())
    with patch.object(BoundHistorySource, 'exchange', exchange):
        try:
            AnalysisSnapshotProvider(client(), {}).capture(request, old, deadline=time.monotonic() + 30)
        except SourceUnavailable as error:
            assert str(error) == 'analysis_source_terminal_failure'
        else:
            raise AssertionError('changed binding must stop this capture')
    assert failures == [('RetainedReadBindingChanged', 'read_source_binding_changed')]
    assert {p.name: sha(p) for p in old.glob('*.json')} == original_files
    assert len([p for p in old.glob('*.json') if 'request' in json.loads(p.read_bytes())]) == 30
    assert not (old / '588030.SH-reference-none.json').exists()
    assert not (old / '588030.SH-reference-front_ratio.json').exists()

    # 新capture已有32份完整原件：原client逐项验证，保持全部原接收时刻，不访问来源。
    current = args.work / 'current'
    shutil.copytree(args.frozen / 'current-source', current)
    snapshot = current / 'SNAPSHOT.json'
    original_snapshot = json.loads(snapshot.read_bytes())
    snapshot.unlink()
    records = {p.name: sha(p) for p in current.glob('*.json')}
    current_request = json.loads((args.frozen / 'CURRENT-REQUEST.json').read_bytes())
    before = len(calls)
    with patch.object(BoundHistorySource, 'exchange', exchange):
        result = AnalysisSnapshotProvider(client(), original_snapshot['source']).capture(
            current_request, current, deadline=time.monotonic() + 30)
    assert len(calls) == before
    replayed = json.loads(result.read_bytes())
    assert replayed == original_snapshot
    assert all(sha(current / name) == digest for name, digest in records.items())

    # 未知原责任即使当前Host换代，也先lookup同ID，不创建新请求或释放capture。
    unknown = args.work / 'unknown'
    shutil.copytree(args.frozen / 'old-source', unknown)
    first = unknown / '159780.SZ-raw.json'
    value = json.loads(first.read_bytes())
    value.update(result=None, received_at=None, consumed=False)
    first.write_text(json.dumps(value), encoding='utf8')
    unknown_hash = sha(first)
    before = len(calls)
    with patch.object(BoundHistorySource, 'exchange', exchange):
        try:
            AnalysisSnapshotProvider(client(), {}).capture(request, unknown, deadline=time.monotonic() + 30)
        except SourcePending as error:
            assert str(error) == 'analysis_original_request_unresolved'
        else:
            raise AssertionError('unknown original must stay pending')
    assert sha(first) == unknown_hash
    assert calls[before:] == [('POST', '/internal/v1/read-results/' + value['request']['request_id'] + '/lookup')]
    assert all('/bound-operations/' not in path for method, path in calls)

    # 实际owner状态转换：确认换代换capture；Pending持续同capture；旧发布文件保持原字节。
    for pending in (False, True):
        directory = args.work / ('owner-pending' if pending else 'owner-changed')
        publication = args.work / ('publication-pending.json' if pending else 'publication-changed.json')
        publication.write_bytes(b'{"old_publication":true}')
        publication_hash = sha(publication)
        ready = threading.Event()
        ids, states = [], []
        class Provider:
            def capture(self, capture, output, *, deadline):
                ids.append(capture['capture_id'])
                if len(ids) >= 2:
                    ready.set()
                if pending or len(ids) >= 2:
                    raise SourcePending('analysis_original_request_unresolved')
                raise SourceUnavailable('analysis_source_terminal_failure')
        artifact = args.work / 'not-executed-artifact'
        artifact.write_bytes(b'isolated-owner-never-enters-native')
        artifacts = {name: dict(path=str(artifact), sha256=sha(artifact)) for name in ('helper', 'reader', 'probe')}
        owner = AnalysisWindowProducer(Provider(), directory=directory, publication=publication,
            artifacts=artifacts, interval_seconds=.05, refresh_seconds=3,
            source_identity=dict(provider='isolated-binding-recovery-v1'))
        original_save = owner._save_state
        def save(**changes):
            if 'error' in changes:
                states.append(changes['error'])
            original_save(**changes)
        owner._save_state = save
        owner.start(deadline=time.monotonic() + 3)
        try:
            assert ready.wait(3)
            assert (ids[0] == ids[1]) is pending
            if not pending:
                assert 'analysis_source_terminal_failure' in states
            assert sha(publication) == publication_hash
        finally:
            assert owner.close(3)

    import guanheng_qmt_shm.read_retention_client as retained_module
    result = dict(passed=True, input_manifest_sha256=sha(args.frozen / 'FROZEN.json'),
        actual_retained_client_sha256=sha(Path(retained_module.__file__)), original_slots=30, original_slots_unchanged=True,
        inner_failure=failures[0], current_capture_slots=32, current_snapshot_identical=True,
        unknown_same_id=True, owner_binding_changed_new_capture=True, owner_pending_same_capture=True,
        new_source_operation_posts=0, publication_bytes_unchanged=True,
        source_sha256={name: sha(ROOT / name) for name in (
            'apps/analysis_window_producer/guanheng_analysis_window_producer/source.py',
            'apps/analysis_window_producer/guanheng_analysis_window_producer/runtime.py',
            'apps/analysis_window_producer/guanheng_analysis_window_producer/preparation.py')})
    (args.work / 'RESULT.json').write_text(json.dumps(result, indent=2), encoding='utf8')
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()
