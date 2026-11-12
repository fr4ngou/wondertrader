"""发行身份接缝：显式同业务transition接纳NSQ，其他事实维持原身份核验。"""
from pathlib import Path
import unittest

from guanheng_wt_runtime.execution_recovery import _compatible_python


def binding(relative, digest):
    root = Path('E:/synthetic-runtime/venv')
    site = root/'Lib/site-packages'
    return dict(python=str(root/'Scripts/pythonw.exe'), site_root=str(site),
        files=[(str(site/relative), digest)])


class QuantityReleaseIdentityTests(unittest.TestCase):
    def test_quantity_change_requires_verified_business_transition(self):
        old = binding('guanheng_strategy_native/planner.py', 'a'*64)
        new = binding('guanheng_strategy_native/planner.py', 'b'*64)
        with self.assertRaises(ValueError):
            _compatible_python(old, new)
        with self.assertRaises(ValueError):
            _compatible_python(old, new, strategy_upgrade=True)
        _compatible_python(old, new, strategy_upgrade=True)

    def test_new_quantity_member_and_metadata_are_covered_by_transition(self):
        old = binding('guanheng_strategy_native-0.1.0a1.dist-info/METADATA', 'a'*64)
        new = binding('guanheng_strategy_native-0.1.0a2.dist-info/METADATA', 'b'*64)
        new['files'].append((str(Path(new['site_root'])/'guanheng_strategy_native/legacy_planner.py'), 'c'*64))
        _compatible_python(old, new, strategy_upgrade=True)

    def test_core_change_stays_rejected_during_quantity_release(self):
        old = binding('guanheng_strategy_core/model.py', 'a'*64)
        new = binding('guanheng_strategy_core/model.py', 'b'*64)
        with self.assertRaises(ValueError):
            _compatible_python(old, new, strategy_upgrade=True)

    def test_interpreter_file_change_stays_rejected(self):
        old = binding('placeholder.py', 'a'*64)
        new = binding('placeholder.py', 'a'*64)
        old['files'].append(('E:/fixed-python/python312.dll', 'b'*64))
        new['files'].append(('E:/fixed-python/python312.dll', 'c'*64))
        with self.assertRaises(ValueError):
            _compatible_python(old, new, strategy_upgrade=True)
