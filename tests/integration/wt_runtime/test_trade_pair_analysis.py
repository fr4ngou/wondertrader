"""父端公开配对身份：原版本保持，单项及批量分析沿显式版本。"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from guanheng_wt_runtime.trade_host_process import TradeHostProcess, TradeHostProcessConfig


class TradePairAnalysisTests(unittest.TestCase):
    def validate(self, manifest):
        raw = json.dumps(manifest).encode()
        config = TradeHostProcessConfig('E:/example/pythonw.exe', 'a'*64, 'E:/example/pair',
            hashlib.sha256(raw).hexdigest(), 'E:/example/agent', 'E:/example/control', 10, 10, 8192)
        owner = TradeHostProcess(config)
        owner._directory = Path('E:/example/control/not-created')
        with patch('guanheng_wt_runtime.trade_host_process._inspect'), patch.object(owner, '_verify_file'), \
                patch('guanheng_wt_runtime.trade_host_process._read', return_value=raw), patch.object(owner, '_check'):
            owner._validate_inputs(10.)

    def original(self):
        return dict(schema_version='qmt.trade-product-pair.v1', qualified_in_qmt=False, order_ready=False,
            strategy_name='GH_WT_MEMORY_VERIFY', agent_package='E:/example/agent',
            host_python='E:/example/pythonw.exe', host_python_sha256='a'*64, config_sha256='b'*64)

    def test_original_pair_versions_and_explicit_analysis_pair_are_admitted(self):
        value = self.original()
        self.validate(value)
        value.update(schema_version='qmt.trade-product-pair.v2',
            source_runtime=dict(schema_version='qmt.source-runtime.v1', mode='thread'))
        self.validate(value)
        value['source_runtime']['mode'] = 'strategy_tick'
        self.validate(value)
        value.update(schema_version='qmt.trade-product-pair.v3', analysis_read=dict(settings_sha256='c'*64,
            profile=dict(read_profile_version='qmt.read-profile.v7', read_operations=['market.divid_factors', 'market.market_data'])))
        self.validate(value)
        for altered in (dict(value, analysis_read=None), dict(value, source_runtime=dict(schema_version='qmt.source-runtime.v1', mode='thread'))):
            with self.assertRaises(ValueError):
                self.validate(altered)
        altered = deepcopy(value)
        altered['analysis_read']['profile']['read_operations'].append('account.trade_detail')
        with self.assertRaises(ValueError):
            self.validate(altered)

    def test_batch_pair_supports_batch_only_and_composed_analysis(self):
        value = self.original()
        value.update(schema_version='qmt.trade-product-pair.v4',
            source_runtime=dict(schema_version='qmt.source-runtime.v1', mode='strategy_tick'),
            analysis_batch_read=dict(settings_sha256='d'*64,
                profile=dict(read_profile_version='qmt.read-profile.v8', read_operations=['market.market_data'])))
        self.validate(value)
        value['analysis_read'] = dict(settings_sha256='c'*64,
            profile=dict(read_profile_version='qmt.read-profile.v7',
                read_operations=['market.divid_factors', 'market.market_data']))
        self.validate(value)
        alterations = [dict(value, analysis_batch_read=None), dict(value, analysis_read=None),
            dict(value, source_runtime=dict(schema_version='qmt.source-runtime.v1', mode='thread'))]
        missing = deepcopy(value)
        del missing['analysis_batch_read']
        alterations.append(missing)
        for field, replacement in [('read_profile_version', 'qmt.read-profile.v7'),
                ('read_operations', ['account.trade_detail'])]:
            altered = deepcopy(value)
            altered['analysis_batch_read']['profile'][field] = replacement
            alterations.append(altered)
        for altered in alterations:
            with self.subTest(manifest=altered), self.assertRaises(ValueError):
                self.validate(altered)


    def reference(self):
        value = self.original()
        value.update(schema_version='qmt.trade-product-pair.v5',
            source_runtime=dict(schema_version='qmt.source-runtime.v1', mode='strategy_tick'),
            security_reference_read=dict(settings_sha256='e'*64,
                profile=dict(read_profile_version='qmt.read-profile.v9',
                    read_operations=['market.security_details', 'market.security_universe'])))
        return value

    def test_reference_v5_accepts_optional_prior_analysis_connections(self):
        # 四种原分析连接组合均保持：无v7/v8、仅v7、仅v8及两者并存。
        for single, batch in ((False, False), (True, False), (False, True), (True, True)):
            value = self.reference()
            if single:
                value['analysis_read'] = dict(settings_sha256='c'*64,
                    profile=dict(read_profile_version='qmt.read-profile.v7',
                        read_operations=['market.divid_factors', 'market.market_data']))
            if batch:
                value['analysis_batch_read'] = dict(settings_sha256='d'*64,
                    profile=dict(read_profile_version='qmt.read-profile.v8', read_operations=['market.market_data']))
            with self.subTest(single=single, batch=batch):
                self.validate(value)
                for key in ('analysis_read', 'analysis_batch_read'):
                    if key in value:
                        altered = deepcopy(value)
                        altered[key]['profile']['read_profile_version'] = 'qmt.read-profile.v9'
                        with self.assertRaises(ValueError):
                            self.validate(altered)
                        altered = deepcopy(value)
                        altered[key] = None
                        with self.assertRaises(ValueError):
                            self.validate(altered)

    def test_reference_v5_rejects_wrong_profile_operations_thread_and_identity(self):
        value = self.reference()
        missing = deepcopy(value)
        del missing['security_reference_read']
        alterations = [missing, dict(value, security_reference_read=None),
            dict(value, source_runtime=dict(schema_version='qmt.source-runtime.v1', mode='thread')),
            dict(value, source_runtime=None), dict(value, schema_version='qmt.trade-product-pair.v6')]
        for field, replacement in [('read_profile_version', 'qmt.read-profile.v8'),
                ('read_operations', ['market.security_details']),
                ('read_operations', ['market.security_universe', 'market.security_details']),
                ('read_operations', ['market.security_details', 'market.security_universe', 'account.trade_detail'])]:
            altered = deepcopy(value)
            altered['security_reference_read']['profile'][field] = replacement
            alterations.append(altered)
        altered = deepcopy(value)
        altered['security_reference_read']['settings_sha256'] = 'bad'
        alterations.append(altered)
        altered = deepcopy(value)
        altered['security_reference_read']['unexpected'] = True
        alterations.append(altered)
        for altered in alterations:
            with self.subTest(manifest=altered), self.assertRaises(ValueError):
                self.validate(altered)

    def test_reference_connection_requires_explicit_v5(self):
        # 新连接不借旧schema取得资格；旧无资料连接用原测试保持行为。
        for version in range(1, 5):
            value = self.reference()
            value['schema_version'] = 'qmt.trade-product-pair.v' + str(version)
            with self.subTest(version=version), self.assertRaises(ValueError):
                self.validate(value)


if __name__ == '__main__':
    unittest.main()
