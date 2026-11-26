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
from guanheng_qmt_shm.trade_pair import _snapshot
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

    @unittest.skipUnless(os.environ.get('QMT_EXAMPLE_SDK_MANIFEST') and os.environ.get('QMT_EXAMPLE_LICENSE'),
                         '完整 CLI 回归需要已核 SDK 清单和 CPython 许可证')
    def test_cli_pair_and_verify_using_real_sdk_without_starting_services(self):
        import guanheng_qmt_shm_agent
        # 正式生成器要求 E 盘新目录；本用例仅用合成账户和临时密钥，关闭时删除自有材料。
        with tempfile.TemporaryDirectory(prefix='qmt-example-', dir='E:/') as folder:
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
