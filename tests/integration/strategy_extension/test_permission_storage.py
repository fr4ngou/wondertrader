"""持久化迁移后的执行权限接续，在 Python 与真实 Native 使用相同业务身份。"""
from copy import deepcopy
from hashlib import sha256
import json
import os
import subprocess
from uuid import uuid4

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


@pytest.mark.parametrize('change', [None, 'queue', 'missing_queue', 'claim', 'permission', 'state', 'started'])
def test_clean_live_initialization_abort_python_and_native(tmp_path, change):
    """真实准入函数核正常关闭→零执行初始化失败→后继，保留原金融文件并拒绝重放。"""
    binary = os.environ.get('GH_STRATEGY_EXTENSION_PROBE')
    if not binary:
        pytest.skip('执行链 CI 显式提供真实 Native 准入探针')
    output = tmp_path/'financial'
    origin, aborted, successor = (tmp_path/str(uuid4()) for _ in range(3))
    successor.mkdir()
    model = dict(output_directory=str(output), budget=dict(run_ms=0),
                 trader=dict(writes_enabled=True, account='SYNTHETIC'), strategies=[dict(id='synthetic-cta')])
    source = dict(model, recovery=dict(mode='record_clean'))
    source_ref = put(origin/'execution.json', source)
    identity_request = tmp_path/'source-identity.json'
    put(identity_request, dict(mode='configuration-identity', configuration=source))
    encoded = subprocess.run([binary, str(identity_request)], capture_output=True, text=True, timeout=20)
    assert encoded.returncode == 0, (encoded.stdout, encoded.stderr)
    source_model_sha = json.loads(encoded.stdout)['sha256']
    binding = put(origin/'python-binding.json', dict(files=[]))
    source_identity = dict(control_id=origin.name, config_sha256=source_ref['sha256'], pid=4294967294)
    put(origin/'ready.json', dict(source_identity, schema='guanheng.execution.ready.v1'))
    put(origin/'closed.json', dict(source_identity, schema='guanheng.execution.closed.v2',
        closed=True, ok=True, recovery_ready=True, resources_closed=True, exit_code=0, error_code=None))
    files = {}
    for name in ('stradata/synthetic-cta.json', 'userdata/ud_synthetic-cta.json', 'portfolio/datas.json'):
        files[name] = put(output/name, dict(synthetic='original financial state'))['sha256']
    snapshot = dict(schema='guanheng.execution-recovery-transition.v1',
        predecessor_configuration=source_ref['file'], predecessor_configuration_sha256=source_ref['sha256'],
        predecessor_control_directory=str(origin), predecessor_installation_sha256='a'*64,
        successor_installation_sha256='b'*64, predecessor_python_binding_sha256=binding['sha256'],
        successor_python_code_identity='d'*64, state_files=files)
    snapshot_ref = put(tmp_path/'source-transition.json', snapshot)
    failed = dict(model, recovery=dict(mode='resume_reconciled', transition=snapshot_ref))
    failed_ref = put(aborted/'execution.json', failed)
    identity = dict(control_id=aborted.name, config_sha256=failed_ref['sha256'], pid=4294967294)
    failed_binding = put(aborted/'python-binding.json', dict(files=[]))
    admission = dict(identity, schema='guanheng.cta-reconciled.v1', admission_kind='clean_transition',
        transition_sha256=snapshot_ref['sha256'], predecessor_control_id=origin.name,
        successor_installation_sha256='b'*64, state_files=files)
    admission_ref = put(aborted/'reconciled.json', admission)
    claim = output/('.cta-reconciled-'+snapshot_ref['sha256']+'.json')
    put(claim, admission)
    put(output/'.cta-clean.consumed.json', dict(source_identity, schema='guanheng.cta-clean.v2',
        closed=True, installation_sha256='a'*64, closed_config_sha256=source_ref['sha256'],
        config_sha256=source_model_sha, closed_receipt=str(origin/'closed.json'), files=files))
    queue = dict(fault=0, accepting=False, inflight=False, accepted=0, entered=0,
                 delivered=0, rejected=0, queued_commands=0, payload_bytes=0)
    failure = dict(identity, schema='guanheng.execution.failure.v1', stage='cta', closed=False, execution_queue=queue)
    put(aborted/'close-prepared.json', dict(identity, schema='guanheng.execution.close-prepared.v1',
        closed=True, ok=False, recovery_ready=False))
    transition = dict(snapshot, predecessor_configuration=failed_ref['file'],
        predecessor_configuration_sha256=failed_ref['sha256'], predecessor_control_directory=str(aborted),
        predecessor_installation_sha256='b'*64, successor_installation_sha256='c'*64,
        predecessor_python_binding_sha256=failed_binding['sha256'], initialization_abort=admission_ref)
    current = dict(model)
    if change == 'queue': queue['entered'] = 1
    elif change == 'missing_queue': queue.pop('accepted')
    elif change == 'claim': put(claim, {})
    elif change == 'permission': current['trader'] = dict(model['trader'], writes_enabled=False)
    elif change == 'state': put(output/'portfolio/datas.json', dict(synthetic='changed financial state'))
    elif change == 'started': put(aborted/'lifecycle-started.json', {})
    put(aborted/'failure.json', failure)
    current['recovery'] = dict(mode='resume_reconciled', transition=put(tmp_path/'transition.json', transition))
    accepted = change is None
    # 文件正文的总摘要由公开transition装配入口及Native复核；本函数核原接收证明。
    if change == 'state':
        assert recovery.initialization_abort_origin(transition, current=current)['configuration'] == source
    elif accepted:
        assert recovery.initialization_abort_origin(transition, current=current)['configuration'] == source
    else:
        with pytest.raises((ValueError, KeyError)):
            recovery.initialization_abort_origin(transition, current=current)
    request = dict(mode='admit', current=current, installation='c'*64, id=successor.name,
                   configuration='e'*64, control=str(successor))
    original = {name: (output/name).read_bytes() for name in files}
    request_path = tmp_path/'request.json'
    put(request_path, request)
    def run():
        result = subprocess.run([binary, str(request_path)], capture_output=True, text=True, timeout=20)
        return result.returncode == 0, result.stdout, result.stderr
    result = run()
    assert result[0] is accepted, result
    assert all((output/name).read_bytes() == raw for name, raw in original.items())
    if accepted:
        assert json.loads((successor/'reconciled.json').read_bytes())['admission_kind'] == 'initialization_abort_reconciled'
        assert run()[0] is False
    else:
        assert not (successor/'reconciled.json').exists()
        assert not (output/('.cta-initialization-abort-'+aborted.name+'.json')).exists()
