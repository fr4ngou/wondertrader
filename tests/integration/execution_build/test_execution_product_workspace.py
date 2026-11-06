"""构建位置与准备来源准入；只写E/D隔离夹具，不启动工具链/构建/服务。"""
from pathlib import Path
import importlib.util
import json
import shutil
import subprocess
import uuid

import pytest

SCRIPT = Path(__file__).resolve().parents[3]/'scripts/execution_product.py'
spec = importlib.util.spec_from_file_location('execution_product_workspace_candidate', SCRIPT)
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


@pytest.fixture
def sources(tmp_path, monkeypatch):
    root = tmp_path/'source'
    (root/'config').mkdir(parents=True)
    (root/'build').mkdir()
    recipe = dict(owned_files=['config/execution-product-build.json', 'config/native-dependencies.json', 'source.h'],
                  owned_directories=[], overlays=[])
    (root/'config/execution-product-build.json').write_text(json.dumps(recipe), encoding='utf8')
    (root/'config/native-dependencies.json').write_text('{"dependencies":[]}', encoding='utf8')
    (root/'source.h').write_bytes(b'permanent synthetic source\n')
    monkeypatch.setattr(build, 'ROOT', root)
    return root, recipe


def prepare(work, recipe):
    build.validate_workspace(work)
    work.mkdir()
    owned = build.source_files(recipe)
    build.write_snapshot(work/'inputs/owned', owned)
    build.save(work/'PREPARED.json', build.prepared_identity(work, owned))


@pytest.fixture
def d_leaf():
    root = Path('D:/wt-build')
    root.mkdir(exist_ok=True)
    path = root/('qa-execution-build-'+uuid.uuid4().hex)
    build.validate_workspace(path)
    yield path
    if path.exists():
        # 本fixture唯一生成的直属新叶；删除前核绝对范围，保留其他构建根。
        assert path.name.startswith('qa-execution-build-') and path.resolve().parent == root.resolve()
        shutil.rmtree(path)


def test_explicit_d_and_existing_e_phase_use_same_prepared_source_guard(sources, d_leaf, monkeypatch):
    root, recipe = sources
    called = []
    monkeypatch.setattr(build.native, 'dependencies', lambda work, **kw: called.append((work, kw)))
    for work in (root/'build'/'default-e', d_leaf):
        prepare(work, recipe)
        build.phase('_dependencies', work)
        assert called[-1] == (work, dict(offline=True, audit=True))
        with pytest.raises(ValueError, match='new workspace'):
            build.validate_workspace(work)
    assert len(called) == 2


@pytest.mark.parametrize('value', ['C:/wt-build/no', 'F:/wt-build/no', 'D:wt-build/no',
                                  'D:/unrelated/no', 'E:/wt-build/no', 'D:/wt-build/a/b', 'D:/wt-build',
                                  'D:/wt-build/a/../no', 'relative/no'])
def test_unauthorized_roots_rejected_before_writing(value):
    with pytest.raises(ValueError):
        build.validate_workspace(Path(value))


def test_prepared_phase_rejects_unprepared_d_before_tool(sources, d_leaf, monkeypatch):
    d_leaf.mkdir()
    called = []
    monkeypatch.setattr(build.native, 'dependencies', lambda *a, **kw: called.append(True))
    with pytest.raises(FileNotFoundError):
        build.phase('_dependencies', d_leaf)
    assert not called


@pytest.mark.parametrize('change', ['source', 'snapshot', 'snapshot_rehashed', 'entry', 'relocated_receipt'])
def test_phase_rejects_changed_source_or_preparation(sources, d_leaf, monkeypatch, change):
    root, recipe = sources
    prepare(d_leaf, recipe)
    if change == 'source':
        (root/'source.h').write_bytes(b'changed permanent source')
    elif change.startswith('snapshot'):
        (d_leaf/'inputs/owned/source.h').write_bytes(b'changed isolated source')
        if change == 'snapshot_rehashed':
            path = d_leaf/'inputs/owned/input.json'
            value = json.loads(path.read_bytes())
            value['files']['source.h']['sha256'] = build.digest(b'changed isolated source')
            build.save(path, value)
    else:
        path = d_leaf/'PREPARED.json'
        value = json.loads(path.read_bytes())
        value['entry_sha256' if change == 'entry' else 'work_directory'] = 'a'*64
        build.save(path, value)
    called = []
    monkeypatch.setattr(build.native, 'dependencies', lambda *a, **kw: called.append(True))
    with pytest.raises(ValueError):
        build.phase('_dependencies', d_leaf)
    assert not called


def test_wt_header_mirroring_keeps_original_owned_receipt_valid(sources, d_leaf, monkeypatch):
    unused, recipe = sources
    prepare(d_leaf, recipe)
    source = d_leaf/'inputs/owned/src/Includes/synthetic.h'
    source.parent.mkdir(parents=True)
    source.write_bytes(b'fixed upstream header mirror')
    path = d_leaf/'inputs/owned/input.json'
    value = json.loads(path.read_bytes())
    value['files']['src/Includes/synthetic.h'] = dict(sha256=build.digest(source.read_bytes()))
    build.save(path, value)
    called = []
    monkeypatch.setattr(build.native, 'dependencies', lambda *a, **kw: called.append(True))
    build.phase('_dependencies', d_leaf)
    assert called == [True]


def test_parent_junction_rejected_without_following_or_creating(sources, tmp_path):
    root, unused = sources
    target = tmp_path/'target'
    target.mkdir()
    link = root/'build'/'linked'
    result = subprocess.run(['cmd.exe', '/c', 'mklink', '/J', str(link), str(target)], capture_output=True,
                            timeout=10, **build.native.background_process_options())
    assert result.returncode == 0
    try:
        with pytest.raises(ValueError, match='linked'):
            build.validate_workspace(link/'new-leaf')
        assert not(target/'new-leaf').exists()
    finally:
        # 只移除本次junction目录项，不递归进入其目标。
        link.rmdir()


def test_toolchain_phase_uses_prepared_root_and_filters_environment(sources, d_leaf, monkeypatch):
    unused, recipe = sources
    prepare(d_leaf, recipe)
    monkeypatch.setattr(build.native, 'environment', lambda work: (dict(PATH='synthetic', TEMP='C:/not-for-build',
        TMP='C:/not-for-build', UNEXPECTED_PROBE_ONLY='not-propagated'), dict(probe='synthetic')))
    build.phase('_toolchain', d_leaf)
    result = json.loads((d_leaf/'TOOLCHAIN.json').read_bytes())
    assert set(result['environment']) == {'PATH', 'TEMP', 'TMP'}
    assert result['environment']['TEMP'] == str(d_leaf/'temp')
