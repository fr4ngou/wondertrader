"""本地CI真实Git/子进程回归：成功合入、过期输入、失败结果及验证范围。"""
from pathlib import Path
import importlib.util
import json
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('local_ci', ROOT / 'scripts/local_ci.py')
ci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci)


def repository(tmp_path, failing=False):
    master = tmp_path / 'master'
    master.mkdir()
    ci.git(master, 'init', '-b', 'master')
    ci.git(master, 'config', 'user.email', 'local-ci@example.invalid')
    ci.git(master, 'config', 'user.name', 'Local CI Fixture')
    (master / '.gitignore').write_text('/build/\n', encoding='utf-8')
    (master / 'config').mkdir()
    stage = {'name': 'synthetic-command', 'argv': ['{python}', '-c',
             'raise SystemExit(3)' if failing else 'print("LOCAL_CI_SYNTHETIC_PASS")'], 'seconds': 20}
    config = {'schema': 1, 'profiles': {key: [stage] for key in ('documentation', 'software', 'execution')}}
    (master / 'config/local-ci.json').write_text(json.dumps(config), encoding='utf-8')
    ci.git(master, 'add', '.gitignore', 'config/local-ci.json')
    ci.git(master, 'commit', '-m', 'synthetic base')
    candidate = tmp_path / 'candidate'
    ci.git(master, 'worktree', 'add', '-b', 'codex/candidate', str(candidate), 'master')
    (candidate / 'value.py').write_text('value = 1\n', encoding='utf-8')
    ci.git(candidate, 'add', 'value.py')
    ci.git(candidate, 'commit', '-m', 'synthetic candidate')
    return master, candidate


def test_local_command_and_fast_forward(tmp_path):
    master, candidate = repository(tmp_path)
    receipt = ci.run_check(candidate, candidate / 'build/result', tmp_path / 'unused.json')
    assert json.loads(receipt.read_bytes())['status'] == 'passed'
    assert 'LOCAL_CI_SYNTHETIC_PASS' in (receipt.parent / 'synthetic-command.log').read_text()
    result = ci.integrate(candidate, master, receipt)
    assert ci.git(master, 'rev-parse', 'HEAD').decode().strip() == result
    assert (master / 'value.py').read_text() == 'value = 1\n'


def test_failure_retained_without_master_change(tmp_path):
    master, candidate = repository(tmp_path, failing=True)
    before = ci.git(master, 'rev-parse', 'HEAD')
    output = candidate / 'build/result'
    with pytest.raises(RuntimeError):
        ci.run_check(candidate, output, tmp_path / 'unused.json')
    receipt = json.loads((output / 'RESULT.json').read_bytes())
    assert receipt['status'] == receipt['stages'][0]['status'] == 'failed'
    assert ci.git(master, 'rev-parse', 'HEAD') == before
    with pytest.raises(ValueError, match='成功'):
        ci.integrate(candidate, master, output / 'RESULT.json')


def test_changed_source_rejects_old_receipt(tmp_path):
    master, candidate = repository(tmp_path)
    receipt = ci.run_check(candidate, candidate / 'build/result', tmp_path / 'unused.json')
    (candidate / 'value.py').write_text('value = 2\n', encoding='utf-8')
    with pytest.raises(ValueError, match='不一致'):
        ci.integrate(candidate, master, receipt)


def test_master_advance_rejects_untested_combination(tmp_path):
    master, candidate = repository(tmp_path)
    receipt = ci.run_check(candidate, candidate / 'build/result', tmp_path / 'unused.json')
    (master / 'other.txt').write_text('synthetic independent change', encoding='utf-8')
    ci.git(master, 'add', 'other.txt')
    ci.git(master, 'commit', '-m', 'advance master')
    with pytest.raises(ValueError, match='master已推进'):
        ci.integrate(candidate, master, receipt)


def test_scopes_follow_changed_module():
    assert ci.profiles_for(['docs/runbooks/example.md']) == ['documentation']
    assert ci.profiles_for(['apps/guanheng/guanheng_app/app.py']) == ['software']
    assert ci.profiles_for(['src/TraderQMT/StandardQmtTrader.cpp']) == ['software', 'execution']
    assert ci.profiles_for(['config/native-reader-overlays/runtime/src/WtExeFact/WtStockMinImpactExeUnit.cpp']) == ['software', 'execution']
    assert ci.profiles_for(['integrations/wondertrader_stock_reference/stock-reference.patch']) == ['software', 'execution']


def test_staged_then_reverted_working_source_cannot_reuse_receipt(tmp_path):
    master, candidate = repository(tmp_path)
    original = ci.git(candidate, 'rev-parse', 'HEAD:value.py').decode().strip()
    path = candidate / 'value.py'
    path.write_text('value = 2\n', encoding='utf-8')
    ci.git(candidate, 'add', 'value.py')
    path.write_text('value = 1\n', encoding='utf-8')
    # HEAD=A、索引=B、工作文件=A：测试必须绑定实际执行的A。
    assert ci.snapshot(candidate)['files']['value.py'].split(':')[1] == original
    receipt = ci.run_check(candidate, candidate / 'build/result', tmp_path / 'unused.json')
    ci.git(candidate, 'commit', '-m', 'commit staged synthetic B')
    path.write_text('value = 2\n', encoding='utf-8')
    with pytest.raises(ValueError, match='不一致'):
        ci.integrate(candidate, master, receipt)


def test_same_content_commit_after_check_reuses_receipt(tmp_path):
    master, candidate = repository(tmp_path)
    path = candidate / 'value.py'
    path.write_text('value = 2\n', encoding='utf-8')
    receipt = ci.run_check(candidate, candidate / 'build/result', tmp_path / 'unused.json')
    ci.git(candidate, 'add', 'value.py')
    ci.git(candidate, 'commit', '-m', 'commit tested synthetic B')
    ci.integrate(candidate, master, receipt)
    assert (master / 'value.py').read_text() == 'value = 2\n'
