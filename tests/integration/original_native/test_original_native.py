"""使用普通安装WT包验证独立协议；-I -B直接运行，不依赖联网或私有路径。"""
from copy import deepcopy
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import unittest

try:
    from guanheng_wt_runtime.original_native_contracts import (
        ALGORITHM_ID,UPSTREAM_COMMIT,build_input,normalize_input,_digest,
        validate_report,project_record,MODEL,
        verify_report_input,
    )
except ModuleNotFoundError as error:
    raise unittest.SkipTest('需要已普通安装含original-native族的WT环境') from error


def frozen_sources():
    days=['2024-01-02','2024-01-03','2024-01-04']
    snapshot=dict(schema='guanheng.resonance-original-input.v1',calendar=['2023-12-29',*days,'2024-01-05'],
        daily={'510300':[dict(date=day,code='510300',open_price=10,high_price=12,low_price=9,close_price=11,volume=1000) for day in days]},
        source={'price_basis':'synthetic-raw'})
    report=dict(schema='guanheng.resonance-original-report.v1',algorithm_id=ALGORITHM_ID,upstream_commit=UPSTREAM_COMMIT,
        input_sha256=_digest(snapshot,original=True),trades_by_code={'510300':[
            dict(action='BUY',date=days[1],price=11,reason='synthetic frozen signal')]},
        portfolio={'history':[{'date':day} for day in days[1:]]})
    return snapshot,report


class InputContracts(unittest.TestCase):
    def test_preparation_argument_failure_does_not_echo_unknown_values(self):
        from guanheng_wt_runtime.original_native_cli import main
        output=io.StringIO()
        with redirect_stdout(output):code=main(['--unknown','synthetic-private-marker'])
        self.assertEqual(code,2)
        self.assertEqual(json.loads(output.getvalue())['status'],'failed')
        self.assertNotIn('synthetic-private-marker',output.getvalue())

    @unittest.skipUnless(os.name=='nt','Windows x64 Porter admission')
    def test_existing_eight_symbol_profile_remains_default(self):
        from guanheng_wt_runtime.strategy_porter import BacktestPorter,Callbacks,AdmissionError
        symbols=tuple('SSE.ETF.'+str(510000+i) for i in range(9))
        args=(Path('E:/nonexistent/oracle.dll'),'0'*64,Path('E:/nonexistent/oracle.json'),'0'*64)
        kwargs=dict(symbols=symbols,execution_symbols=symbols,loader=lambda *a:(),callbacks=Callbacks(lambda *a:None,lambda *a:None,lambda *a:None))
        with self.assertRaisesRegex(AdmissionError,'profile容量'):BacktestPorter(*args,**kwargs)
        with self.assertRaisesRegex(AdmissionError,'制品文件缺失'):BacktestPorter(*args,**kwargs,max_execution_symbols=9)

    def test_full_reference_window_and_true_preceding_warmup_are_preserved(self):
        snapshot,report=frozen_sources();value=build_input(snapshot,report)
        self.assertEqual(value['calendar'],['2024-01-02','2024-01-03','2024-01-04'])
        self.assertEqual(value['evaluation_window'],{'warmup_date':'2024-01-02','from':'2024-01-03','to':'2024-01-04'})
        self.assertEqual(value['source_snapshot_sha256'],_digest(snapshot,original=True))
        self.assertEqual(value['reference_report']['trades_by_code'],report['trades_by_code'])
        self.assertEqual(value['history']['510300'][1]['open'],10)
        self.assertEqual(value['history']['510300'][1]['close'],11)

    def test_source_hash_is_checked_before_native_preparation(self):
        snapshot,report=frozen_sources();snapshot['daily']['510300'][1]['open_price']=9.5
        with self.assertRaises(ValueError):build_input(snapshot,report)

    def test_evaluation_missing_price_is_rejected_without_cropping_or_filling(self):
        snapshot,report=frozen_sources();snapshot['daily']['510300'].pop(1)
        report['input_sha256']=_digest(snapshot,original=True)
        with self.assertRaises(ValueError):build_input(snapshot,report)

    def test_reference_payload_change_requires_its_exact_digest(self):
        value=build_input(*frozen_sources());value['reference_report']['trades_by_code']['510300'][0]['action']='SELL'
        with self.assertRaises(ValueError):normalize_input(value)

    def test_altered_invalid_signal_is_rejected_even_with_new_digest(self):
        value=build_input(*frozen_sources());value['reference_report']['trades_by_code']['510300'][0]['action']='SHORT'
        value['reference_report_sha256']=_digest(value['reference_report'],original=True)
        with self.assertRaises(ValueError):normalize_input(value)

    def test_integer_share_lot_and_explicit_capital_contract(self):
        for field,bad in [('lot',100.0),('initial_capital_cny','1'),('quantity_unit','lot')]:
            with self.subTest(field=field):
                value=build_input(*frozen_sources());value['policy'][field]=bad
                with self.assertRaises(ValueError):normalize_input(value)

    def test_malformed_ohlc_and_nonfinite_values_fail_before_dll(self):
        for bad in (-1,float('nan')):
            value=build_input(*frozen_sources());value['history']['510300'][1]['open']=bad
            with self.assertRaises(ValueError):normalize_input(value)

    def test_normalized_input_does_not_alias_mutable_reference(self):
        snapshot,report=frozen_sources();value=build_input(snapshot,report)
        report['trades_by_code']['510300'][0]['action']='SELL'
        self.assertEqual(value['reference_report']['trades_by_code']['510300'][0]['action'],'BUY')


class NativeReportContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path=Path(__file__).parent/'fixtures/manual-wt-report.json'
        if not path.exists():raise unittest.SkipTest('合成真实WT报告夹具尚未生成')
        cls.report=json.loads(path.read_bytes())
        cls.inputs=json.loads(path.with_name('manual-wt-input.json').read_bytes())

    def test_independent_manual_native_cash_and_fee_oracle(self):
        report=validate_report(self.report);last=project_record(report,report.record_count-1)['record']['capture']
        self.assertEqual(report.record_count,4)
        self.assertAlmostEqual(float(last['basis']['nav_cny']),1396908.30,places=6)
        self.assertAlmostEqual(last['funds']['fees'],491.70,places=6)
        remaining={p['symbol']:p['total'] for p in last['positions'] if p['first_entry']}
        self.assertEqual(remaining,{'SSE.ETF.510050':24800.0})

    def test_cash_flag_is_boolean_and_financial_fields_are_bound(self):
        for key,bad in [('cash_deficit',0),('cash_deficit',1)]:
            value=deepcopy(self.report);value['records'][0][key]=bad
            with self.assertRaises(ValueError):validate_report(value)
        value=deepcopy(self.report);value['records'][-1]['capture']['basis']['cash_cny']='0'
        with self.assertRaises(ValueError):validate_report(value)

    def test_frozen_t1_quantity_floor_is_enforced(self):
        value=deepcopy(self.report);row=value['records'][0]
        row['capture']['positions'][0].update(total=100,valid=0,first_entry=202401031500,last_entry=202401031500)
        # 先维持捕获资金恒等式，保证失败覆盖冻结目标而不是现金算式。
        row['capture']['basis']['cash_cny']=str(1000000-100*dict(row['capture']['prices'])[row['capture']['positions'][0]['symbol']])
        row['submit_vector'][0]['quantity']=0
        with self.assertRaises(ValueError):validate_report(value)

    def test_window_model_and_source_qualifications_fail_closed(self):
        for field,bad in [('source_qualified',True),('execution_model',{}),('evaluation_window',{})]:
            value=deepcopy(self.report);value[field]=bad
            with self.assertRaises(ValueError):validate_report(value)

    def test_caller_stop_exception_identity_survives_validation(self):
        stopped=RuntimeError('synthetic caller stop')
        def check():raise stopped
        with self.assertRaises(RuntimeError) as result:validate_report(self.report,check=check)
        self.assertIs(result.exception,stopped)

    def test_validated_report_snapshot_is_immutable_from_caller(self):
        value=deepcopy(self.report);admitted=validate_report(value)
        value['records'][-1]['capture']['basis']['nav_cny']='0'
        self.assertNotEqual(admitted.to_dict()['records'][-1]['capture']['basis']['nav_cny'],'0')

    def test_cross_original_signal_and_capital_binding_is_required(self):
        self.assertEqual(verify_report_input(self.report,self.inputs)['strategy']['algorithm_id'],ALGORITHM_ID)
        changed=deepcopy(self.report);changed['records'][0]['signals'][0]['reason']='tampered source reason'
        validate_report(changed)  # 结构与原生资金仍可通过，跨原件身份必须另外核验。
        with self.assertRaises(ValueError):verify_report_input(changed,self.inputs)
        changed=deepcopy(self.report);changed['policy']['capital_source']='different explicit model'
        with self.assertRaises(ValueError):verify_report_input(changed,self.inputs)

    def test_first_listed_bar_is_usable_without_an_extra_opening_gate(self):
        self.assertEqual(self.inputs['history']['510050'][0]['date'],'2024-01-03')
        first=self.report['records'][0]
        self.assertEqual(dict(first['capture']['prices'])['SSE.ETF.510050'],20)
        self.assertEqual({x['symbol']:x['quantity'] for x in first['submit_vector']}['SSE.ETF.510050'],24800)


if __name__=='__main__':unittest.main(verbosity=2)
