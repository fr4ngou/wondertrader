"""独立更新角色的真实子进程环境及凭据失效回归；不启动调度或交易。"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location(
    'observation_update_owner', ROOT / 'scripts/runtime_templates/observation-update-owner.py')
OWNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(OWNER)


class UpdateEnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='oar-update-env-')
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)

    def prepared(self, values=None, *, raw=None):
        path = self.directory / 'market.private.json'
        path.write_bytes(raw if raw is not None else json.dumps(values).encode())
        return {'profiles': {'live': {'market_environment': {
            'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        }}}}

    def test_default_still_removes_inherited_business_and_market_environment(self):
        with patch.dict(os.environ, {'GUANHENG_MARKET_TOKEN': 'inherited-test',
                                    'guanheng_execution_config': 'inherited-test'}, clear=False):
            environment = OWNER.launch_environment({'profiles': {'live': {}}}, 'live')
        self.assertFalse(any(key.upper().startswith('GUANHENG_') for key in environment))
        self.assertEqual(environment.get('SYSTEMROOT'), os.environ.get('SYSTEMROOT'))

    def test_explicit_connection_reaches_a_real_hidden_child_without_account_environment(self):
        prepared = self.prepared({'GUANHENG_MARKET_URL': 'http://127.0.0.1:18136',
                                  'GUANHENG_MARKET_TOKEN': 'synthetic-test-token',
                                  'GUANHENG_MARKET_TIMEOUT_SECONDS': '30'})
        with patch.dict(os.environ, {'GUANHENG_ACCOUNT_SOURCE': 'inherited-test',
                                    'GUANHENG_MARKET_TOKEN': 'wrong-inherited-test'}, clear=False):
            environment = OWNER.launch_environment(prepared, 'live')
        result = subprocess.run([sys.executable, '-I', '-B', '-c',
            "import os,json;print(json.dumps({'url':os.environ.get('GUANHENG_MARKET_URL'),"
            "'token_matches':os.environ.get('GUANHENG_MARKET_TOKEN')=='synthetic-test-token',"
            "'account_present':'GUANHENG_ACCOUNT_SOURCE' in os.environ}))"],
            env=environment, capture_output=True, check=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW)
        self.assertEqual(json.loads(result.stdout), {
            'url': 'http://127.0.0.1:18136', 'token_matches': True, 'account_present': False})

    def test_changed_or_oversized_private_file_is_rejected(self):
        prepared = self.prepared({'GUANHENG_MARKET_URL': 'http://127.0.0.1',
                                  'GUANHENG_MARKET_TOKEN': 'synthetic-test-token'})
        path = Path(prepared['profiles']['live']['market_environment']['path'])
        path.write_bytes(b'changed')
        with self.assertRaisesRegex(RuntimeError, 'market_environment_identity'):
            OWNER.launch_environment(prepared, 'live')
        path.write_bytes(b' ' * 16385)
        prepared['profiles']['live']['market_environment']['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        with self.assertRaisesRegex(RuntimeError, 'market_environment_identity'):
            OWNER.launch_environment(prepared, 'live')

    def test_only_market_connection_fields_are_consumed(self):
        for values in ({'GUANHENG_MARKET_URL': 'http://127.0.0.1'},
                       {'GUANHENG_MARKET_URL': 'http://127.0.0.1', 'GUANHENG_MARKET_TOKEN': ''},
                       {'GUANHENG_MARKET_URL': 'http://127.0.0.1', 'GUANHENG_MARKET_TOKEN': 42},
                       {'GUANHENG_MARKET_URL': 'http://127.0.0.1', 'GUANHENG_MARKET_TOKEN': 'test',
                        'GUANHENG_ACCOUNT_SOURCE': 'inherited-test'}):
            with self.subTest(values=list(values)):
                with self.assertRaises(RuntimeError):
                    OWNER.launch_environment(self.prepared(values), 'live')
        with self.assertRaisesRegex(RuntimeError, 'market_environment_invalid'):
            OWNER.launch_environment(self.prepared(raw=b'{'), 'live')

    def test_invalid_credentials_leave_no_run_identity_or_launched_process(self):
        # 原故障在启动时发生；先核凭据，避免产生无法归因的待定运行身份。
        state = {'alive': False, 'launcher_alive': False, 'child_alive': False, 'instance': None}
        cases = [({'GUANHENG_MARKET_TOKEN': 'synthetic-test-token'}, 'market_environment_connection_required'),
                 ({'GUANHENG_MARKET_URL': 'http://127.0.0.1',
                   'GUANHENG_MARKET_TOKEN': 'synthetic-test-token\x00'}, 'market_environment_fields')]
        for values, code in cases:
            with self.subTest(code=code):
                prepared = self.prepared(values)
                prepared['expected_current'] = 'baseline'
                profile = prepared['profiles']['live']
                for name in ('sources', 'service', 'deployment'):
                    path = self.directory / (name + '.json')
                    path.write_bytes(b'{}')
                    profile.update({name: str(path), name + '_sha256': hashlib.sha256(b'{}').hexdigest()})
                with patch.object(OWNER, 'control_status', return_value=state), \
                     patch.object(OWNER, 'business_status', return_value={'current': 'baseline'}), \
                     patch.object(OWNER, 'write') as write, \
                     patch.object(OWNER.subprocess, 'Popen') as popen:
                    with self.assertRaisesRegex(RuntimeError, code):
                        OWNER.start(prepared, 'live', None)
                    write.assert_not_called()
                    popen.assert_not_called()

    def test_stop_can_still_operate_when_connection_file_is_missing(self):
        prepared = self.prepared({'GUANHENG_MARKET_TOKEN': 'synthetic-test-token'})
        Path(prepared['profiles']['live']['market_environment']['path']).unlink()
        state = {'alive': False, 'launcher_alive': False, 'child_alive': False, 'instance': None}
        with patch.object(OWNER, 'control_status', return_value=state), \
             patch.object(OWNER, 'launch_environment', side_effect=AssertionError('stop must not read credentials')):
            self.assertTrue(OWNER.stop(prepared, 'live')['stop_deadline_met'])


if __name__ == '__main__':
    unittest.main()
