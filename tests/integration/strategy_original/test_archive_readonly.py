"""ORR原件导入及HTTP族分流，合成金融算例与实际冻结主链分别留证。"""
from hashlib import sha256
import json
import os
from pathlib import Path
from time import monotonic

import pytest
from fastapi.testclient import TestClient

from guanheng_app import original_reports as o
from guanheng_app.original_report_import import import_report
from guanheng_app.backtest_archive import BacktestArchive, ArchiveError
from guanheng_app.app import create_app
from guanheng_app.settings import ConsoleSettings
from guanheng_app.strategy_catalog import strategy_catalog

ROOT = Path(__file__).resolve().parents[3]


def fixture(tmp_path, *, run_id='d' * 32):
    """初值1→1.1，BUY1/2=.5份，SELL1.1/2.2=.5份；日期为合成开市日。"""
    model = dict(signal_version='stable', execution='next-trading-day-close', fees=0,
        fractional_shares=True, allocation='new-buy-equal-weight-full-equity', sell_rebalance=False,
        calendar_fallback=False, historical_features='as-stored-final-rows', initial_equity=1.0,
        historical_availability='unknown', warmup='original-function-behaviour',
        prefix_stability='not-guaranteed-by-upstream-minimum-length-guards')
    snapshot = dict(schema='guanheng.resonance-original-input.v1', upstream_commit=o.COMMIT,
        source=dict(description='合成归档算例', notes=dict(source_path='private-path-must-not-project')),
        data_kind='synthetic', codes=['510300'])
    manifest = json.loads((ROOT/'apps/guanheng/strategy_original/guanheng_strategy_original/source_manifest.json').read_bytes())
    dates = ['2026-01-05', '2026-01-06', '2026-01-07']
    report = dict(schema=o.REPORT_SCHEMA, algorithm_id=o.ALGORITHM, upstream_commit=o.COMMIT,
        input_sha256=o.digest(snapshot), source_manifest_sha256=o.digest(manifest), source=snapshot['source'],
        data_kind='synthetic', execution_qualified=False, point_in_time_qualified=False, model=model,
        strategy_results={'510300': {}}, resonance={'510300': {}}, turnover_percentiles={}, margin_percentiles={},
        data_audit={'coverage': {}}, trades_by_code={'510300':[
            dict(date=dates[0], action='BUY', price=2, reason='合成买入'),
            dict(date=dates[1], action='SELL', price=2.2, reason='合成卖出')]},
        portfolio=dict(history=[dict(date=d, equity=e, invested=i, position_pct=p) for d,e,i,p in
            zip(dates,[1.0,1.0,1.1],[0.,1.,0.],[0.,100.,0.])], final_equity=1.1,
            total_return_pct=10., max_drawdown_pct=0., empty_days=2, empty_days_pct=66.7, open_positions=[],
            trade_log=[dict(date=dates[1],signal_date=dates[0],code='510300',kind='BUY',price=2,amount=1,weight_pct=100),
                       dict(date=dates[2],signal_date=dates[1],code='510300',kind='SELL',price=2.2,amount=1.1,weight_pct=0)]))
    paths = [tmp_path/name for name in ('report.json','input.json','source.json')]
    for path, value in zip(paths, (report,snapshot,manifest)):
        path.write_bytes(o.canonical(value))
    request = dict(schema='guanheng.original-report-import.v1',run_id=run_id,label='合成原版归档算例',
        report_path=str(paths[0]),input_path=str(paths[1]),source_manifest_path=str(paths[2]),
        report_sha256=sha256(paths[0].read_bytes()).hexdigest(), input_file_sha256=sha256(paths[1].read_bytes()).hexdigest(),
        source_manifest_file_sha256=sha256(paths[2].read_bytes()).hexdigest())
    request_path=tmp_path/'import.json'
    request_path.write_bytes(o.canonical(request))
    root=tmp_path/'archive'
    root.mkdir()
    return request_path,root,report,snapshot,manifest


def test_main_import_catalog_actual_http_and_no_overwrite(tmp_path):
    request,root,report,_snapshot,_manifest=fixture(tmp_path)
    result=import_report(request,root)
    run,receipt=result['run_id'],result['receipt_sha256']
    with TestClient(create_app(ConsoleSettings(backtest_archive_root=str(root)))) as client:
        catalog=client.get('/v1/ui/strategy-catalog').json()
        assert catalog['strategies'][-1]['strategy_id']==o.ALGORITHM
        index=client.get('/v1/ui/backtest/archive-summaries').json()
        assert index['schema']=='nbw-archive-summary-index-v1'
        entry=index['runs'][0]
        assert entry['report_family']==o.FAMILY and 'owner_id' not in entry and 'request_id' not in entry
        assert entry['summary']['initial_equity']==1 and 'initial_capital_cny' not in entry['summary']
        prefix=f'/v1/ui/backtest/archive/{run}'
        performance=client.get(prefix+'/performance',params={'receipt_sha256':receipt}).json()
        assert performance['unit']=='normalized-equity'
        assert performance['metrics']['last_equity']==1.1
        assert performance['metrics']['total_return_pct']==pytest.approx(10)
        assert 'private-path-must-not-project' not in json.dumps(performance)
        for route in ('','/visuals','/records','/records/1'):
            response=client.get(prefix+route,params={'receipt_sha256':receipt})
            assert response.status_code==200,response.text
            assert response.json()['schema'].startswith('orr-')
        first=client.get(prefix+'/ledger',params={'receipt_sha256':receipt,'offset':0,'limit':1}).json()
        second=client.get(prefix+'/ledger',params={'receipt_sha256':receipt,'offset':1,'limit':1}).json()
        assert first['total']==2 and first['trades'][0]['quantity']==.5 and second['trades'][0]['quantity']==.5
        assert first['positions_available'] is False
        signal=client.get(prefix+'/signals',params={'receipt_sha256':receipt,'offset':1,'limit':1}).json()
        assert signal['signals'][0]['date']==20260106 and signal['signals'][0]['action']=='SELL'
        assert client.get(prefix+'/ledger',params={'receipt_sha256':receipt,'day':20260104}).status_code==404
        assert client.get(prefix+'/performance',params={'receipt_sha256':'f'*64}).status_code==409
        assert client.get(prefix+'/ledger',params={'receipt_sha256':receipt,'limit':51}).status_code==422
        assert client.post(prefix+'/signals').status_code==405
    before={p.name:p.read_bytes() for p in (root/run).iterdir()}
    with pytest.raises(FileExistsError):
        import_report(request,root)
    assert before=={p.name:p.read_bytes() for p in (root/run).iterdir()}


def test_dynamic_catalog_preserves_wt_unknown_and_saved_versions():
    values=[dict(strategy_id='resonance-regime-v1',strategy_version=None),
            dict(strategy_id='other-saved',strategy_version='7.1')]
    result=strategy_catalog(values)['strategies']
    assert result[0]['strategy_version'] is None
    assert result[1]['strategy_id']=='other-saved' and result[1]['strategy_version']=='7.1'
    assert result[-1]['strategy_id']==o.ALGORITHM


@pytest.mark.parametrize('target', ['original-report.json','original-input.json','source-manifest.json'])
def test_each_bound_original_tamper_rejected_and_summary_unavailable(tmp_path,target):
    request,root,*_=fixture(tmp_path)
    result=import_report(request,root)
    run=root/result['run_id']
    (run/target).write_bytes(b'{}')
    archive=BacktestArchive(root)
    with pytest.raises(ArchiveError):
        archive.read(result['run_id'],result['receipt_sha256'],monotonic()+5,performance=True)
    index=archive.list(monotonic()+5,summaries=True)
    assert index['runs'][0]['summary'] is None


@pytest.mark.parametrize('mutation', ['family','execution','pit','input','code','order','same-day','nonfinite','model','coverage','open-position'])
def test_strict_family_model_and_temporal_admission(tmp_path,mutation):
    _request,_root,report,snapshot,manifest=fixture(tmp_path)
    if mutation=='family':report['schema']='nbw-performance-v1'
    if mutation=='execution':report['execution_qualified']=True
    if mutation=='pit':report['point_in_time_qualified']=True
    if mutation=='input':report['input_sha256']='f'*64
    if mutation=='code':report['portfolio']['trade_log'][0]['code']='589000'
    if mutation=='order':report['portfolio']['history'].reverse()
    if mutation=='same-day':report['portfolio']['trade_log'][0]['signal_date']='2026-01-06'
    if mutation=='nonfinite':report['portfolio']['history'][1]['equity']=float('inf')
    if mutation=='model':report['model']['execution']='next-open'
    if mutation=='coverage':report['data_audit']['coverage']={'510300':{'missing':[]}}
    if mutation=='open-position':report['portfolio']['open_positions']=[dict(code='589000',buy_date='2026-01-06',shares=1)]
    with pytest.raises(ValueError):o.validate_report(report,snapshot,manifest)


@pytest.mark.parametrize('raw',[b'{"x":1,"x":2}',b'{"x":NaN}',b'{"x":1e999}'])
def test_duplicate_or_nonfinite_json_rejected(raw):
    with pytest.raises(ValueError):o.decode(raw)


def test_failed_import_does_not_publish_or_create_run(tmp_path):
    request,root,*_=fixture(tmp_path)
    value=json.loads(request.read_bytes())
    value['report_sha256']='0'*64
    request.write_bytes(o.canonical(value))
    with pytest.raises(ValueError):import_report(request,root)
    assert not list(root.iterdir())


def test_hardlinked_source_is_rejected_before_import(tmp_path):
    request,root,*_=fixture(tmp_path)
    source=tmp_path/'report.json'
    os.link(source,tmp_path/'same-report.json')
    with pytest.raises(ArchiveError):import_report(request,root)
    assert not list(root.iterdir())


def test_failed_receipt_publish_leaves_unarchived_originals(tmp_path,monkeypatch):
    request,root,*_=fixture(tmp_path)
    def interrupted(_source,_target):
        raise OSError('synthetic receipt publication interruption')
    monkeypatch.setattr('guanheng_app.original_report_import.os.rename',interrupted)
    with pytest.raises(OSError):import_report(request,root)
    runs=list(root.iterdir())
    assert len(runs)==1 and (runs[0]/'original-report.json').is_file()
    assert not (runs[0]/'completed-archive.json').exists()
    index=BacktestArchive(root).list(monotonic()+5)
    assert not index['runs'] and index['unarchived_runs']==1


def test_refill_trim_keep_model_action_and_side(tmp_path):
    _request,_root,report,*_=fixture(tmp_path)
    report['portfolio']['trade_log'][0]['kind']='REFILL'
    report['portfolio']['trade_log'][1]['kind']='TRIM'
    rows=o.trades(report)
    assert [(r['action'],r['side']) for r in rows]==[('REFILL','buy'),('TRIM','sell')]


def test_original_native_unknown_versions_never_fall_through_legacy():
    from guanheng_app import backtest_reports as dispatch
    from guanheng_app.strategy_replay_facts import SessionError
    with pytest.raises(SessionError):
        dispatch.report_schema_for_input(dict(schema='guanheng.original-native-replay-input.v2'))
    with pytest.raises(SessionError):
        dispatch.validate_report_dict(dict(schema='guanheng.original-native-replay-report.v2'))
    assert dispatch.report_schema_for_input(dict(schema='guanheng.original-native-replay-input.v1')) == dispatch.ORIGINAL_REPORT_SCHEMA
