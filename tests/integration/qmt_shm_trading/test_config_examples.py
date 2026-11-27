"""仓库示例必须通过正式配置准入；可选实机 SDK 用例覆盖真实 CLI 配对/核验。"""
from contextlib import redirect_stdout
from copy import deepcopy
import io
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / 'connectors/qmt_shm/agent'), str(ROOT / 'connectors/qmt_shm/host')]
from guanheng_qmt_shm.trade_cli import main
from guanheng_qmt_shm.trade_pair import _admit_pair_storage, _require_pair_volume, _snapshot, verify_product_pair
from guanheng_qmt_shm_agent.protocol import canonical

EXAMPLES = ROOT / 'connectors/qmt_shm/examples'


@unittest.skipUnless(os.name == 'nt', '示例面向 Windows QMT，使用 Windows 绝对路径')
class ConfigExampleTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((EXAMPLES / 'qmt-trade-config.example.json').read_bytes())
        self.policy = (EXAMPLES / 'qmt-operation-policy.example.json').read_bytes()
        self.credentials = dict(ipc_secret=b'synthetic-example-ipc-secret-0001',
            http_keys={self.config['http_key_id']: 'synthetic-independent-http-secret'})

    def test_example_has_complete_host_and_product_configuration(self):
        admitted = _snapshot(self.config, self.credentials, self.policy, .2)[5]
        self.assertFalse(admitted.writes_enabled)
        self.assertEqual(admitted.profile['read_operations'], ['account.trade_detail'])

    def test_changed_account_requires_matching_read_binding_and_digest(self):
        changed = deepcopy(self.config)
        changed['trade_binding']['account_id'] = 'OTHER-SYNTHETIC'
        with self.assertRaises(ValueError):
            _snapshot(changed, self.credentials, self.policy, .2)
        changed['trade_profile']['binding_sha256'] = sha256(canonical(changed['trade_binding'])).hexdigest()
        with self.assertRaises(ValueError):
            _snapshot(changed, self.credentials, self.policy, .2)
        changed['operation_profiles']['account.trade_detail']['limits']['account_binding']['account_id'] = 'OTHER-SYNTHETIC'
        self.assertEqual(_snapshot(changed, self.credentials, self.policy, .2)[5].trade_binding['account_id'],
                         'OTHER-SYNTHETIC')

    def test_missing_event_storage_is_rejected_by_product_pair(self):
        changed = deepcopy(self.config)
        del changed['event_storage']
        del changed['event_poll_seconds']
        with self.assertRaises(ValueError):
            _snapshot(changed, self.credentials, self.policy, .2)

    def test_standalone_pair_accepts_fixed_volume_and_keeps_read_only_boundary(self):
        pair = Path('F:/instance/pair')
        cfg = dict(writes_enabled=False, listen_host='127.0.0.1', journal_path='F:/instance/journal.sqlite')
        with patch('guanheng_qmt_shm.private_files.ctypes.WinDLL') as win:
            drive_type = win.return_value.GetDriveTypeW
            drive_type.return_value = 3  # DRIVE_FIXED
            get_volume_info = win.return_value.GetVolumeInformationW

            def volume_info(_root, _volume_name, _volume_size, _serial, _max_component, flags, _fs_name, _fs_size):
                flags._obj.value = 0x00000008  # FILE_PERSISTENT_ACLS
                return True

            get_volume_info.side_effect = volume_info
            _require_pair_volume(pair)
            drive_type.assert_called_with(pair.anchor)
            _admit_pair_storage(pair, cfg)
            for change in (dict(writes_enabled=True), dict(listen_host='0.0.0.0'),
                           dict(journal_path='H:/instance/journal.sqlite')):
                with self.subTest(change=change), self.assertRaises(ValueError):
                    _admit_pair_storage(pair, cfg | change)
            for volume_type in (1, 2, 4):
                drive_type.return_value = volume_type
                with self.subTest(volume_type=volume_type), self.assertRaisesRegex(ValueError, 'fixed volume'):
                    _require_pair_volume(pair)
            drive_type.return_value = 3
            get_volume_info.side_effect = None
            get_volume_info.return_value = True  # 固定卷报告成功，但没有持久 ACL 能力。
            with patch('guanheng_qmt_shm.trade_pair._inspect') as inspect:
                with self.assertRaisesRegex(ValueError, 'persistent ACLs'):
                    verify_product_pair(pair)
                inspect.assert_not_called()

    @unittest.skipUnless(os.environ.get('QMT_EXAMPLE_SDK_MANIFEST') and os.environ.get('QMT_EXAMPLE_LICENSE'),
                         '完整 CLI 回归需要已核 SDK 清单和 CPython 许可证')
    def test_cli_pair_and_verify_using_real_sdk_without_starting_services(self):
        import guanheng_qmt_shm_agent
        # 默认沿 Windows 临时目录，可传本机固定卷上的既有私有父目录。
        parent = os.environ.get('QMT_EXAMPLE_PAIR_PARENT')
        with tempfile.TemporaryDirectory(prefix='qmt-example-', dir=parent) as folder:
            root = Path(folder)
            policy = root / 'input-policy.json'
            policy.write_bytes(self.policy)
            self.config['operation_policies_path'] = str(policy)
            self.config['journal_path'] = str(root / 'must-not-create.sqlite')
            config = root / 'input-config.json'
            config.write_text(json.dumps(self.config), encoding='utf-8')
            pair = root / 'pair'
            environment = {self.config['ipc_secret_env']: self.credentials['ipc_secret'].hex(),
                self.config['http_secret_env']: self.credentials['http_keys'][self.config['http_key_id']]}
            with patch.dict(os.environ, environment), redirect_stdout(io.StringIO()):
                self.assertEqual(main(['pair', '--config', str(config), '--memory-sdk-manifest',
                    os.environ['QMT_EXAMPLE_SDK_MANIFEST'], '--stdlib-license', os.environ['QMT_EXAMPLE_LICENSE'],
                    '--reconnect-seconds', '.2', '--source-mode', 'strategy_tick', '--output', str(pair)]), 0)
                self.assertEqual(main(['verify', '--directory', str(pair), '--installed-agent',
                    str(Path(guanheng_qmt_shm_agent.__file__).resolve().parent)]), 0)
            self.assertTrue((pair / 'strategy.py').is_file())
            deployment = json.loads((pair / 'deployment.json').read_bytes())
            self.assertFalse(deployment['host']['writes_enabled'])
            self.assertFalse(Path(self.config['journal_path']).exists())


if __name__ == '__main__':
    unittest.main()
