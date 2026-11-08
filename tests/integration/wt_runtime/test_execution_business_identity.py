"""运行时长切换回归：库存业务身份沿已绑定原件，金融模型保持原约束。"""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from datetime import datetime, timezone
from unittest.mock import patch

from guanheng_wt_runtime.execution_process import ManagedExecutionProcess

from guanheng_wt_runtime.execution_recovery import (
    _same_business,
    compatible_business_configuration,
    market_origin_configuration,
    predecessor_configuration,
)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("ascii")


class ExecutionBusinessIdentityTests(unittest.TestCase):
    def fixture(self, root, duration):
        origin = {
            "budget": {"start_ms": 25000, "stop_ms": 10000, "run_ms": duration},
            "trader": {"account": "SYNTHETIC", "writes_enabled": False},
            "output_directory": str(root / "financial"),
            "takeover": {"input_file": str(root / "inventory.json"), "input_sha256": "1" * 64},
            "recovery": {"mode": "record_clean"},
            "strategies": [{"parameters": {"python_strategy": {"input_file": str(root / "input.json"), "input_sha256": "2" * 64}}}],
            "data": {"store": {"daily": {"root": str(root / "daily")}}},
        }
        raw = canonical(origin)
        path = root / "execution.json"
        path.write_bytes(raw)
        current = deepcopy(origin)
        current.pop("takeover")
        current["recovery"] = {"mode": "resume_reconciled"}
        current["market_input_origin"] = {
            "schema": "guanheng.market-input-origin.v1",
            "file": str(path),
            "sha256": sha256(raw).hexdigest(),
        }
        window = root / "window.json"
        current["strategies"][0]["parameters"]["python_strategy"]["market_window"] = {"path": str(window), "max_age_seconds": 3600}
        current["data"]["store"]["daily"]["publication"] = {
            "status_file": str(root / "status.json"), "publication_file": str(window), "cache_root": str(root / "cache")}
        current["data"]["store"]["daily"]["adjustment"] = "front_ratio"
        return current

    def test_inventory_origin_survives_duration_change_in_both_directions(self):
        # 原BASELINE对业务投影取哈希；切换预算时必须保持该哈希，且不改实际执行预算。
        for old, new in ((70000, 0), (0, 70000)):
            with self.subTest(old=old, new=new), tempfile.TemporaryDirectory() as directory:
                current = self.fixture(Path(directory), old)
                before = market_origin_configuration(current)
                current["budget"]["run_ms"] = new
                after = market_origin_configuration(current)
                self.assertEqual(sha256(canonical(before)).digest(), sha256(canonical(after)).digest())
                self.assertEqual(after["budget"]["run_ms"], old)
                self.assertEqual(current["budget"]["run_ms"], new)

    def test_financial_model_changes_are_still_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            current = self.fixture(Path(directory), 70000)
            for field in ("account", "output_directory"):
                with self.subTest(field=field):
                    changed = deepcopy(current)
                    changed["budget"]["run_ms"] = 0
                    if field == "account":
                        changed["trader"][field] = "OTHER-SYNTHETIC"
                    else:
                        changed[field] = str(Path(directory) / "other-financial")
                    with self.assertRaises(ValueError):
                        market_origin_configuration(changed)

    def test_materialized_configuration_changes_only_duration(self):
        old = {"budget": {"run_ms": 70000}, "trader": {"account": "SYNTHETIC"}}
        new = deepcopy(old)
        new["budget"]["run_ms"] = 0
        self.assertTrue(compatible_business_configuration(new, old))
        for invalid in (True, 999, -1, 86400001):
            with self.subTest(duration=invalid):
                new["budget"]["run_ms"] = invalid
                with self.assertRaises(ValueError):
                    compatible_business_configuration(new, old)

    def test_retained_parser_port_change_preserves_business_identity(self):
        original = {"budget": {"run_ms": 0}, "parsers": [{"module": "ParserQMTHostRetainedV6",
            "qmt": {"base_url": "http://127.0.0.1:50885", "key_id_env": "FIXTURE_KEY"}}]}
        changed = deepcopy(original)
        qmt = changed["parsers"][0]["qmt"]
        qmt["base_url"] = "http://127.0.0.1:18149/"
        self.assertTrue(compatible_business_configuration(changed, original))
        for endpoint in ("http://127.0.0.1:0", "http://127.0.0.1:65536", "http://localhost:18149",
                         "https://127.0.0.1:18149", "http://127.0.0.1:18149/path"):
            with self.subTest(endpoint=endpoint):
                qmt["base_url"] = endpoint
                self.assertFalse(compatible_business_configuration(changed, original))
        qmt.update(base_url="http://127.0.0.1:18149", key_id_env="OTHER_KEY")
        self.assertFalse(compatible_business_configuration(changed, original))


class AccountPublicationBusinessIdentityTests(unittest.TestCase):
    """同账户发布程序升级只改变接线；账户事实及全部金融模型继续保持原身份。"""
    def fixture(self):
        return {
            'budget': {'start_ms': 25000, 'stop_ms': 10000, 'run_ms': 70000},
            'trader': {'expected_account': 'SYNTHETIC', 'environment': 'simulation',
                       'writes_enabled': False, 'currency': 'CNY', 'profile': 'cny_cash_shsz_v1'},
            'output_directory': 'E:/synthetic/financial',
            'takeover': {'input_file': 'E:/synthetic/inventory.json', 'input_sha256': '1' * 64},
            'strategies': [dict(id='synthetic-' + str(index), parameters=dict(python_strategy=dict(
                input_file='E:/synthetic/input-' + str(index) + '.json', input_sha256='2' * 64,
                main_symbol='SYNTHETIC', evaluation_seconds=2,
                capital_account=dict(path='E:/synthetic/account-' + str(index) + '/current.json',
                    config_sha256='a' * 64, account='SYNTHETIC', environment='simulation'),
                capital_market=dict(base_url='http://127.0.0.1:18000', timeout_seconds=5)))) for index in (1, 2)],
            'fees': {'commission_rate': 0.0003},
        }

    @staticmethod
    def account(value, index=0):
        return value['strategies'][index]['parameters']['python_strategy']['capital_account']

    def test_same_account_publication_path_and_digest_upgrade_all_strategies(self):
        old = self.fixture()
        new = deepcopy(old)
        new['budget']['run_ms'] = 0
        for index in (0, 1):
            self.account(new, index).update(path='E:/synthetic/new-' + str(index) + '/current.json',
                                             config_sha256='b' * 64)
        old_bytes, new_bytes = canonical(old), canonical(new)
        self.assertTrue(compatible_business_configuration(new, old))
        self.assertTrue(_same_business(old, new))
        self.assertEqual((canonical(old), canonical(new)), (old_bytes, new_bytes))
        self.assertNotEqual(sha256(old_bytes).digest(), sha256(new_bytes).digest())

    def test_account_or_environment_change_is_rejected_on_every_strategy(self):
        old = self.fixture()
        for index in (0, 1):
            for field, value in (('account', 'OTHER-SYNTHETIC'), ('environment', 'live')):
                with self.subTest(strategy=index, field=field):
                    new = deepcopy(old)
                    self.account(new, index).update(path='E:/synthetic/upgraded/current.json',
                        config_sha256='b' * 64, **{field: value})
                    self.assertFalse(_same_business(old, new))

    def test_reference_presence_and_no_reference_configuration_keep_original_meaning(self):
        old = self.fixture()
        new = deepcopy(old)
        new['strategies'][0]['parameters']['python_strategy'].pop('capital_account')
        self.assertFalse(_same_business(old, new))
        self.assertFalse(_same_business(new, old))
        for value in (old, new):
            for strategy in value['strategies']:
                strategy['parameters']['python_strategy'].pop('capital_account', None)
        self.assertTrue(_same_business(old, new))
        self.assertTrue(_same_business({'budget': {'run_ms': 70000}}, {'budget': {'run_ms': 0}}))

    def test_malformed_reference_is_rejected_before_wiring_is_removed(self):
        changes = [
            ('path', 'relative/current.json'), ('path', ''), ('path', 'E:/synthetic/../current.json'),
            ('path', 'E:/synthetic/\x00/current.json'), ('config_sha256', 'A' * 64),
            ('config_sha256', 'a' * 63), ('config_sha256', 'g' * 64), ('config_sha256', True),
            ('account', ''), ('account', 123), ('account', 'x' * 64),
            ('environment', None), ('environment', 'paper'),
        ]
        for field, value in changes:
            with self.subTest(field=field, value_type=type(value).__name__):
                old = self.fixture()
                self.account(old)[field] = value
                with self.assertRaises(ValueError):
                    _same_business(old, deepcopy(old))
        for mode in ('missing', 'extra', 'null'):
            with self.subTest(shape=mode):
                old = self.fixture()
                if mode == 'missing':
                    self.account(old).pop('path')
                elif mode == 'extra':
                    self.account(old)['ignored'] = True
                else:
                    old['strategies'][0]['parameters']['python_strategy']['capital_account'] = None
                with self.assertRaises(ValueError):
                    _same_business(old, deepcopy(old))

    def test_other_financial_model_input_and_market_fields_still_compare(self):
        old = self.fixture()
        mutations = [
            (('trader', 'expected_account'), 'OTHER-SYNTHETIC'),
            (('trader', 'environment'), 'live'), (('trader', 'writes_enabled'), True),
            (('output_directory',), 'E:/synthetic/other-financial'),
            (('takeover', 'input_sha256'), '3' * 64), (('fees', 'commission_rate'), 0.0004),
            (('budget', 'stop_ms'), 11000),
            (('strategies', 0, 'parameters', 'python_strategy', 'input_file'), 'E:/synthetic/other-input.json'),
            (('strategies', 0, 'parameters', 'python_strategy', 'input_sha256'), '4' * 64),
            (('strategies', 0, 'parameters', 'python_strategy', 'main_symbol'), 'OTHER-SYNTHETIC'),
            (('strategies', 0, 'parameters', 'python_strategy', 'evaluation_seconds'), 3),
            (('strategies', 0, 'parameters', 'python_strategy', 'capital_market', 'timeout_seconds'), 6),
        ]
        for path, value in mutations:
            with self.subTest(field=path):
                new = deepcopy(old)
                self.account(new).update(path='E:/synthetic/upgraded/current.json', config_sha256='b' * 64)
                owner = new
                for part in path[:-1]:
                    owner = owner[part]
                owner[path[-1]] = value
                self.assertFalse(_same_business(old, new))

    def test_original_configuration_bytes_and_live_cap_digest_binding_remain_strict(self):
        old = self.fixture()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prior = root / 'execution.json'
            prior.write_bytes(canonical(old))
            transition = root / 'transition.json'
            transition.write_bytes(canonical(dict(predecessor_configuration=str(prior),
                predecessor_configuration_sha256=sha256(prior.read_bytes()).hexdigest())))
            native = dict(recovery=dict(transition=dict(file=str(transition),
                sha256=sha256(transition.read_bytes()).hexdigest())))
            self.assertEqual(predecessor_configuration(native), old)
            changed = deepcopy(old)
            self.account(changed)['config_sha256'] = 'b' * 64
            self.assertTrue(_same_business(old, changed))
            prior.write_bytes(canonical(changed))
            with self.assertRaises(ValueError):
                predecessor_configuration(native)
        from guanheng_wt_runtime.strategy_capital import AccountCashReader
        reader = AccountCashReader(self.account(old), 60)
        reference = dict(schema='guanheng.account-observation-reference.v1', control_id='synthetic',
            config_sha256='b' * 64, pid=123, path='E:/synthetic/observation.json', ready_path='E:/synthetic/ready.json')
        with patch.object(AccountCashReader, '_document', return_value=(reference, b'synthetic')) as read:
            self.assertEqual(reader.read(datetime.now(timezone.utc), float('inf')), (None, False))
        self.assertEqual(read.call_count, 1)


class ExecutionConfigurationSnapshotTests(unittest.TestCase):
    def test_native_receives_same_bytes_as_recovery_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            configuration = root / "deployment.json"
            raw = canonical({"schema": "synthetic-native-configuration", "budget": {"run_ms": 0}})
            configuration.write_bytes(raw)
            control = root / "control"
            control.mkdir()
            process = object.__new__(ManagedExecutionProcess)
            process.config = SimpleNamespace(
                configuration=configuration, configuration_sha256=sha256(raw).hexdigest(), pythonw=root / "pythonw.exe")
            process._directory, process._control_id = control, "synthetic-control"
            command = process._command()
            self.assertEqual((control / "execution.json").read_bytes(), raw)
            self.assertEqual(command[command.index("--config-sha256") + 1], sha256(raw).hexdigest())
            self.assertEqual(process._command(), command)
            # 已物化配置沿原件复用，另一个部署模板不能覆盖原ready将绑定的配置。
            process.config.configuration = control / "execution.json"
            self.assertEqual(process._command()[2], str(control / "execution.json"))
            process.config.configuration = configuration
            (control / "execution.json").write_bytes(canonical({"other": "configuration"}))
            with self.assertRaises(ValueError):
                process._command()




class StockOrderLotsRecoveryTests(unittest.TestCase):
    def fixture(self):
        return dict(budget=dict(run_ms=0), trader=dict(account='SYNTHETIC'),
            output_directory='E:/synthetic/financial', executer=dict(scale=1,policy=dict(default=dict(
                name='WtExeFact.WtStockMinImpactBorrowedExeUnit',byrate=False,lots=1000,min_order=100))))

    def test_explicit_lots_change_preserves_originals(self):
        old=self.fixture();new=deepcopy(old);new['executer']['policy']['default']['lots']=10000
        self.assertTrue(_same_business(old,new));self.assertTrue(_same_business(new,old))
        self.assertEqual(old['executer']['policy']['default']['lots'],1000)
        self.assertEqual(new['executer']['policy']['default']['lots'],10000)

    def test_invalid_lots_rejected(self):
        for invalid in (0,-1,True,'10000',float('inf'),float('nan'),10**400):
            with self.subTest(value=str(invalid)):
                new=self.fixture();new['executer']['policy']['default']['lots']=invalid
                with self.assertRaises(ValueError):_same_business(self.fixture(),new)

    def test_business_constraints_remain_strict(self):
        for field,value in [('byrate',True),('min_order',1000),('name','OtherExecutor')]:
            new=self.fixture();new['executer']['policy']['default'].update(lots=10000)
            new['executer']['policy']['default'][field]=value
            self.assertFalse(_same_business(self.fixture(),new))
        for field,value in [('scale',10)]:
            new=self.fixture();new['executer'][field]=value
            self.assertFalse(_same_business(self.fixture(),new))
        new=self.fixture();new['trader']['account']='OTHER'
        self.assertFalse(_same_business(self.fixture(),new))


if __name__ == "__main__":
    unittest.main()
