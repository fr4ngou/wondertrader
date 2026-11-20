"""持久化迁移后的执行权限接续，在 Python 与真实 Native 使用相同业务身份。"""
from copy import deepcopy
from hashlib import sha256
import json
import os
import subprocess

import pytest
from guanheng_wt_runtime import execution_recovery as recovery


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = recovery.canonical(value)
    path.write_bytes(raw)
    return dict(file=str(path), sha256=sha256(raw).hexdigest())


def configurations(root, enabled):
    target = root / 'private'
    proof = dict(schema='guanheng.wt-private-storage-copy.v1', predecessor_control=str(root / 'prior'),
                 predecessor_configuration_sha256='a' * 64, predecessor_closed_sha256='b' * 64,
                 original_output=str(root / 'original'), target_output=str(target / 'native'),
                 native_files={}, databases={'allocation': {'target': str(target / 'allocation/account-allocation.sqlite3')}},
                 compaction_sha256='c' * 64)
    before = dict(output_directory=proof['target_output'], budget={'run_ms': 0},
                  trader=dict(account='SYNTHETIC', writes_enabled=enabled),
                  shared_account_storage={'allocation_root': str(target / 'allocation')},
                  private_storage_origin=put(target / 'verified.json', proof))
    after = deepcopy(before)
    after['trader']['writes_enabled'] = not enabled
    after['execution_permission_origin'] = dict(schema='guanheng.execution-permission-origin.v1',
                                               **put(root / 'prior/execution.json', before))
    return before, after


def native(root, before, after, expected):
    binary = os.environ.get('GH_STRATEGY_EXTENSION_PROBE')
    if not binary:
        pytest.skip('执行链 CI 显式提供真实 Native 比较探针')
    request = root / 'request.json'
    put(request, dict(mode='compare', previous=before, current=after))
    result = subprocess.run([binary, str(request)], capture_output=True, text=True, timeout=20)
    assert (result.returncode == 0) is expected, (result.stdout, result.stderr)
    assert json.loads(result.stdout)['ok'] is expected


@pytest.mark.parametrize('enabled', [False, True])
def test_permission_change_after_storage_keeps_original_business(tmp_path, enabled):
    before, after = configurations(tmp_path, enabled)
    originals = {p: p.read_bytes() for p in tmp_path.rglob('*.json')}
    assert recovery.compatible_business_configuration(after, before)
    native(tmp_path, before, after, True)
    assert all(path.read_bytes() == raw for path, raw in originals.items())


@pytest.mark.parametrize('change', ['account', 'output', 'proof'])
def test_permission_change_preserves_financial_and_proof_checks(tmp_path, change):
    before, after = configurations(tmp_path, False)
    if change == 'account':
        after['trader']['account'] = 'DIFFERENT-SYNTHETIC'
    elif change == 'output':
        after['output_directory'] = str(tmp_path / 'different')
    else:
        after['private_storage_origin']['sha256'] = 'c' * 64
    with pytest.raises(ValueError):
        recovery.compatible_business_configuration(after, before)
    native(tmp_path, before, after, False)
