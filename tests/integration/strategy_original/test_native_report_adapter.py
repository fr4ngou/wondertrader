"""新WT报告纯读取：人工现金算例、原异常身份与防执行接口。真实DLL主链另留原件。"""
from copy import deepcopy
import pytest

contracts=pytest.importorskip('guanheng_wt_runtime.original_native_contracts')
from guanheng_app import backtest_reports as app_reports


def example():
    symbol='SSE.ETF.510300';identity='1'*64
    row=dict(trading_date=20260105,minute=1500,status='holding',reason='synthetic read-only oracle',
        signals=[],submit_vector=[],readback=[],cash_deficit=False,result=None,outcome=None,previous_status=None,
        capture=dict(session_id=identity,sequence=1,trading_date=20260105,minute=1500,projection=[],
            positions=[dict(symbol=symbol,total=0.0,valid=0.0,first_entry=0,last_entry=0)],prices=[[symbol,1.0]],
            funds=dict(net=0.0,realized=0.0,dynamic=0.0,fees=0.0),
            basis=dict(observed_at='2026-01-05T15:00:00+08:00',input_sha256='2'*64,nav_cny='1000000',cash_cny='1000000',
                pnl_cny='0.0',capital_source='synthetic-explicit-capital',cash_source='synthetic-native-NAV-minus-position',
                price_basis='synthetic-OHLC')))
    return dict(schema=contracts.REPORT_SCHEMA,session_id=identity,input_sha256='2'*64,configuration_sha256='3'*64,
        strategy_id=contracts.STRATEGY_ID,strategy_version=contracts.STRATEGY_VERSION,signal_algorithm_id=contracts.ALGORITHM_ID,
        reference_report_sha256='4'*64,source_snapshot_sha256='5'*64,scope=contracts.REPORT_SCOPE,status='holding',
        policy=dict(initial_capital_cny='1000000',capital_source='synthetic-explicit-capital',currency='CNY',quantity_unit='share',multiplier=1,lot=100),
        historical_model=deepcopy(contracts.MODEL),execution_model=deepcopy(contracts.MODEL),
        evaluation_window={'warmup_date':'2026-01-02','from':'2026-01-05','to':'2026-01-05'},
        native_files=[[name,str(index)*64] for index,name in enumerate(['sessions','commodities','contracts','holidays','fees'])],
        native_outputs=[['trades.csv','6'*64]],callback_counts=[['init',1],['calculate',1]],records=[row],
        source_qualified=False,execution_qualified=False,point_in_time_qualified=False)


def test_original_native_admission_projection_freezes_and_does_not_export_execution():
    raw=example();admitted=app_reports.validate_report_dict(raw)
    assert type(admitted) is contracts.ValidatedOriginalNativeReport and admitted.record_count==1
    raw['records'][0]['capture']['basis']['nav_cny']='999'
    projected=app_reports.project_session_record(admitted,0)
    assert projected['report_schema']==contracts.REPORT_SCHEMA
    assert projected['record']['capture']['basis']['nav_cny']=='1000000'
    projected['record']['capture']['basis']['nav_cny']='888'
    assert app_reports.project_session_record(admitted,0)['record']['capture']['basis']['nav_cny']=='1000000'
    assert not hasattr(contracts,'OriginalNativeSession') and not hasattr(contracts,'BacktestPorter')


def test_gap_cash_is_explicit_and_exactly_agrees_with_native_position_value():
    raw=example();row=raw['records'][0]
    row['capture']['positions'][0].update(total=1100000.0,valid=1100000.0,first_entry=202601051500,last_entry=202601051500)
    row['capture']['basis']['cash_cny']='-100000';row['cash_deficit']=True
    projected=app_reports.project_session_record(app_reports.validate_report_dict(raw),0)
    assert projected['evaluation_summary']['cash_deficit'] is True
    assert projected['record']['capture']['basis']['cash_cny']=='-100000'
    row['cash_deficit']=False
    with pytest.raises(ValueError):app_reports.validate_report_dict(raw)


@pytest.mark.parametrize('mutation',['cash-bool','window','model','capture-extra','odd-lot','date','qualification'])
def test_bad_new_family_facts_reject_without_falling_into_retained(mutation):
    raw=example();row=raw['records'][0]
    if mutation=='cash-bool':row['cash_deficit']=0
    if mutation=='window':raw['evaluation_window']['from']='2026-01-06'
    if mutation=='model':raw['execution_model']['execution']='same-day-open'
    if mutation=='capture-extra':row['capture']['observation']={}
    if mutation=='odd-lot':row['submit_vector']=[dict(symbol='SSE.ETF.510300',quantity=101)]
    if mutation=='date':row['capture']['basis']['observed_at']='2026-01-06T15:00:00+08:00'
    if mutation=='qualification':raw['execution_qualified']=True
    with pytest.raises(ValueError):app_reports.validate_report_dict(raw)


def test_control_error_retains_same_object_through_wt_and_app_boundary():
    signal=contracts.SessionError('synthetic caller deadline')
    def stop():raise signal
    with pytest.raises(contracts.SessionError) as found:
        app_reports.validate_report_dict(example(),check=stop)
    assert found.value is signal


def test_T1_frozen_shares_reject_sell_target_and_pending_total_keeps_own_semantics():
    raw=example();row=raw['records'][0];position=row['capture']['positions'][0]
    position.update(total=1000.0,valid=0.0,first_entry=202601051500,last_entry=202601051500)
    row['capture']['basis']['cash_cny']='999000'
    row['submit_vector']=[dict(symbol=position['symbol'],quantity=900)]
    with pytest.raises(ValueError):app_reports.validate_report_dict(raw)
    row['submit_vector'][0]['quantity']=1000
    assert app_reports.validate_report_dict(raw).record_count==1
    # 原接口首次pending可回显total；first_entry=0时尚无真实仓位，不能虚构T+1冻结。
    position.update(first_entry=0,last_entry=0)
    row['capture']['basis']['cash_cny']='1000000';row['submit_vector'][0]['quantity']=0
    assert app_reports.validate_report_dict(raw).record_count==1


def bound_input(report):
    reference=dict(schema='guanheng.resonance-original-report.v1',upstream_commit=contracts.UPSTREAM_COMMIT,
        algorithm_id=contracts.ALGORITHM_ID,input_sha256=report['source_snapshot_sha256'],
        portfolio=dict(history=[dict(date='2026-01-05')]),trades_by_code={'510300':[]})
    history={'510300':[dict(date=d,open=1.,high=1.,low=1.,close=1.,volume=10.,amount=10.)
                       for d in ('2026-01-02','2026-01-05')]}
    value=dict(schema=contracts.INPUT_SCHEMA,strategy=dict(strategy_id=contracts.STRATEGY_ID,
        strategy_version=contracts.STRATEGY_VERSION,algorithm_id=contracts.ALGORITHM_ID),
        reference_report=reference,reference_report_sha256=contracts._digest(reference,original=True),
        source_snapshot_sha256=report['source_snapshot_sha256'],history=history,calendar=['2026-01-02','2026-01-05'],
        evaluation_window=deepcopy(report['evaluation_window']),policy=deepcopy(report['policy']),fee_reserve_cny='5000',
        fee_source='synthetic-WT-bound-fees',market_manifest_source='synthetic-frozen-OHLC',price_basis='synthetic-OHLC')
    report['reference_report_sha256']=value['reference_report_sha256']
    report['input_sha256']=contracts._digest(value)
    report['configuration_sha256']=contracts.configuration_id(value)
    report['records'][0]['capture']['basis']['input_sha256']=report['input_sha256']
    return value


def test_original_report_must_bind_the_same_frozen_input_and_signal_rows():
    report=example();value=bound_input(report)
    assert app_reports.verify_original_native_input(report,value)['evaluation_window']==report['evaluation_window']
    wrong=deepcopy(report);wrong['input_sha256']='f'*64
    with pytest.raises(ValueError):app_reports.verify_original_native_input(wrong,value)
    wrong=deepcopy(report)
    wrong['records'][0]['signals']=[dict(code='510300',date='2026-01-05',action='BUY',price=1.,reason='other-input-signal')]
    # 两份纯值报告分别都合法，跨原件绑定仍须拒绝不同原信号。
    assert app_reports.validate_report_dict(wrong).record_count==1
    with pytest.raises(ValueError):app_reports.verify_original_native_input(wrong,value)
