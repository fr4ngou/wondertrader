"""Web维护未知代保护；Windows本机控制契约，不启动App或外部进程。"""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


@unittest.skipUnless(sys.platform == 'win32', 'Windows local process control')
class WebControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[3]
        spec = importlib.util.spec_from_file_location('observer_web_control',
            root / 'scripts/runtime_templates/observer-web.py')
        cls.owner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.owner)

    def test_unknown_dead_process_keeps_original_generation(self):
        owner = self.owner
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original = dict(control_id='SDK-original', pid=123, creation_time=1)
            owner.write(root / 'instance.json', original)
            before = (root / 'instance.json').read_bytes()
            unknown = dict(outcome='unknown', alive=False, instance=original)
            with patch.object(owner, 'observe', return_value=unknown), patch.object(owner, 'launch') as launch:
                actual = owner.start(root / 'unused-profile.json', {}, root, 'a' * 64)
            self.assertIs(actual, unknown)
            launch.assert_not_called()
            self.assertEqual((root / 'instance.json').read_bytes(), before)

    def test_late_original_receipt_adopts_without_launch(self):
        owner = self.owner
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            identifier = str(owner.uuid4())
            directory = root / identifier
            directory.mkdir()
            state = dict(control_id=identifier, profile_sha256='a' * 64,
                directory=str(directory), launcher_pid=123, launcher_creation_time=1)
            owner.write(root / 'instance.json', state)
            owner.write(directory / 'ready.json', dict(control_id=identifier,
                profile_sha256='a' * 64, pid=124, parent_pid=123, creation_time=2))
            with patch.object(owner, 'launch') as launch:
                adopted = owner.adopt_body(root, state)
            launch.assert_not_called()
            self.assertEqual(adopted['pid'], 124)
            self.assertEqual(adopted['control_id'], identifier)
            self.assertEqual(owner.read(root / 'instance.json'), adopted)


if __name__ == '__main__':
    unittest.main()
