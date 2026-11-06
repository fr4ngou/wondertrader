"""显式同账发行的实际材料读取；策略升级与金融/数量核依赖分开处理。"""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'apps/wt_runtime'))
from guanheng_wt_runtime.execution_recovery import _compatible_python, digest, load_transition


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode('ascii')


class StrategyReleaseRecoveryTests(unittest.TestCase):
    def binding(self, root, release):
        site = root / 'Lib/site-packages'
        return dict(schema='guanheng.cta-python-binding.v1', python=str(root / 'Scripts/pythonw.exe'),
            site_root=str(site), files=[
                (str(site / 'guanheng_strategy_v1/latest.py'), release * 64),
                (str(site / ('guanheng_strategy_v1-0.1.0a' + ('10' if release == '1' else '12') + '.dist-info/METADATA')), release * 64),
                (str(site / 'guanheng_strategy_core/contracts.py'), 'a' * 64),
                (str(site / 'guanheng_strategy_native/planner.py'), 'b' * 64),
                (str(root / 'Scripts/pythonw.exe'), 'c' * 64)])

    def test_transition_reads_originals_and_accepts_only_explicit_same_business_release(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            previous, current = self.binding(root / 'old', '1'), self.binding(root / 'new', '2')
            predecessor = root / 'predecessor'
            predecessor.mkdir()
            old = dict(budget=dict(run_ms=0), trader=dict(account='SYNTHETIC'), recovery=dict(mode='record_clean'))
            raw = canonical(old)
            (predecessor / 'execution.json').write_bytes(raw)
            binding_raw = canonical(previous)
            (predecessor / 'python-binding.json').write_bytes(binding_raw)
            identities = dict(current['files'])
            transition = dict(schema='guanheng.execution-recovery-transition.v1',
                predecessor_configuration=str(predecessor / 'execution.json'),
                predecessor_configuration_sha256=hashlib.sha256(raw).hexdigest(),
                predecessor_control_directory=str(predecessor),
                predecessor_installation_sha256='d' * 64, successor_installation_sha256='e' * 64,
                predecessor_python_binding_sha256=hashlib.sha256(binding_raw).hexdigest(),
                successor_python_code_identity=digest(identities), state_files={})
            transition_file = root / 'transition.json'
            transition_file.write_bytes(canonical(transition))
            native = dict(old, recovery=dict(mode='resume_reconciled', transition=dict(file=str(transition_file),
                sha256=hashlib.sha256(transition_file.read_bytes()).hexdigest())))
            admitted, unused = load_transition(native, identities, binding=current)
            self.assertEqual(admitted, transition)
            native['trader'] = dict(account='OTHER-SYNTHETIC')
            with self.assertRaises(ValueError):
                load_transition(native, identities, binding=current)
            native['trader'] = old['trader']
            (predecessor / 'execution.json').write_bytes(raw + b' ')
            with self.assertRaises(ValueError):
                load_transition(native, identities, binding=current)

    def test_default_comparison_and_non_strategy_dependencies_remain_strict(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            previous, current = self.binding(root / 'old', '1'), self.binding(root / 'new', '2')
            with self.assertRaises(ValueError):
                _compatible_python(previous, current)
            _compatible_python(previous, current, strategy_upgrade=True)
            for index in (2, 4):
                with self.subTest(member=current['files'][index][0]):
                    changed = dict(current, files=list(current['files']))
                    name, unused = changed['files'][index]
                    changed['files'][index] = (name, 'f' * 64)
                    with self.assertRaises(ValueError):
                        _compatible_python(previous, changed, strategy_upgrade=True)


if __name__ == '__main__':
    unittest.main()
