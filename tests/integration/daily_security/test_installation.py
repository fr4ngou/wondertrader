"""安装复制边界回归；使用进程替身，验证实际安装入口拒绝错误字节。"""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch


class InstallationTests(unittest.TestCase):
    def exercise(self, fault):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = root / 'artifact'
            (artifact / 'native').mkdir(parents=True)
            (artifact / 'native/Helper.dll').write_bytes(b'declared-native')
            (artifact / 'requirements.lock').write_bytes(b'')
            base = root / 'base'
            base.mkdir()
            python = base / 'python.exe'
            python.write_bytes(b'fixed-test-python')
            sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
            (artifact / 'base.json').write_text(json.dumps({'python.exe': sha(python)}), 'utf8')
            files = {p.relative_to(artifact).as_posix(): sha(p) for p in artifact.rglob('*') if p.is_file()}
            manifest = dict(schema='guanheng.daily-data-artifact.v1', version='test', files=files,
                runtime=dict(python_sha256=sha(python), base_files='base.json',
                    base_files_sha256=sha(artifact / 'base.json'), version='3.12.13'))
            (artifact / 'ARTIFACT.json').write_text(json.dumps(manifest), 'utf8')
            identity = sha(artifact / 'ARTIFACT.json')
            destination = root / 'installed'
            path = Path(__file__).resolve().parents[3] / 'scripts/runtime_templates/unified_daily_install.py'
            spec = importlib.util.spec_from_file_location('daily_test_installer', path)
            installer = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(installer)
            copytree = installer.shutil.copytree

            def copy(source, target):
                if fault == 'source-during-copy':
                    (Path(source) / 'Helper.dll').write_bytes(b'changed-source')
                return copytree(source, target)

            def child(command, **kwargs):
                if 'venv' in [str(x) for x in command]:
                    scripts = destination / 'venv/Scripts'
                    scripts.mkdir(parents=True)
                    (scripts / 'python.exe').write_bytes(b'launcher')
                    (scripts / 'pythonw.exe').write_bytes(b'hidden-launcher')
                    site = destination / 'venv/Lib/site-packages'
                    (site / 'guanheng_daily_data').mkdir(parents=True)
                    (site / 'guanheng_daily_data/ORIGINS.json').write_bytes(b'{}')
                    entries = site / 'integrations/guanheng'
                    entries.mkdir(parents=True)
                    for name in ('source_market_service.py', 'daily_data_service.py'):
                        (entries / name).write_bytes(b'# test entry')
                if fault == 'target-after-copy' and '-c' in command:
                    (destination / 'native/Helper.dll').write_bytes(b'changed-target')
                return json.dumps(dict(version='3.12.13 test', distributions=[])), ''

            with patch.dict('sys.modules', native=types.SimpleNamespace(run=child)), \
                    patch.object(installer.shutil, 'copytree', copy):
                if fault:
                    with self.assertRaisesRegex(ValueError, 'installed native bytes differ'):
                        installer.install(artifact, identity, destination, python, seconds=60)
                    self.assertFalse((destination / 'INSTALLATION.json').exists())
                else:
                    result = installer.install(artifact, identity, destination, python, seconds=60)
                    self.assertEqual(result['native'], {'Helper.dll': files['native/Helper.dll']})
                    self.assertTrue((destination / 'INSTALLATION.json').exists())
            self.assertEqual(sha(artifact / 'ARTIFACT.json'), identity)

    def test_source_change_during_copy_rejects_installation(self):
        self.exercise('source-during-copy')

    def test_target_change_after_copy_rejects_installation(self):
        self.exercise('target-after-copy')

    def test_matching_native_bytes_get_installation_receipt(self):
        self.exercise(None)
