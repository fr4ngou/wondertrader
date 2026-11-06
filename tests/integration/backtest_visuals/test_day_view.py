"""轻量日期索引沿完整原件身份复用，变更/追加/串报仍在原owner拒绝。"""
from hashlib import sha256
from dataclasses import replace
import json
from time import monotonic

import pytest

from guanheng_app.backtest_day_view import build_day_view
from guanheng_app.backtest_archive import BacktestArchive,ArchiveError
from backtest_archive_fixture import example,publish


def view(*,trades=None,positions=None,report=None,receipt=None,receipt_sha='a'*64,proof=()):
    receipt=receipt or dict(run_id='b'*32,report_sha256='c'*64)
    report=report or dict(records=[dict(trading_date=20240103,capture={}),dict(trading_date=20240104,capture=None)])
    return build_day_view(receipt=receipt,receipt_sha=receipt_sha,report=report,trades=trades,positions=positions,
        proof=proof,visuals=dict(schema='nbw-visuals-v1'),check=lambda:None)


def trade(index,quantity,side='buy'):
    return dict(index=index,date=20240103,time='202401031500',symbol='SSE.ETF.510300',side=side,
        direction='LONG',action='OPEN',price='1.00',quantity=quantity,fee_cny='0.00')


def test_summary_exact_aggregate_unknown_and_no_capture():
    known=view(trades=[trade(0,'0.1'),trade(1,'0.2'),trade(2,'100','sell'),trade(3,'1','unknown')],positions=[])
    points=json.loads(known.summary_json)['points']
    assert points[0]==[20240103,[],[['SSE.ETF.510300','0.3']],[['SSE.ETF.510300','100']],1]
    assert points[1]==[20240104,None,[],[],0]
    assert json.loads(view().summary_json)['points'][0]==[20240103,None,None,None,None]
    assert known.ledger(20240104,0,50)['positions_available'] is False
    assert known.ledger(20240103,0,50)['positions_available'] is True


def test_ledger_is_independent_copy_and_original_order_pagination():
    cached=view(trades=[trade(4,'100'),trade(5,'200','sell')],positions=[])
    response=cached.ledger(20240103,0,1);response['trades'][0]['quantity']='forged'
    assert cached.ledger(20240103,0,1)['trades'][0]['quantity']=='100'
    assert cached.ledger(None,1,1)['trades'][0]['index']==5
    with pytest.raises(TypeError):cached.by_day[20240103]=()


def archived_cache(tmp_path):
    # 原归档合成原件完成准入；单独注入派生索引来验证热读完整性边界。
    # 冷加载/真实WT金融值已由1415日HTTP/原件主链另验。
    root,run,fact,config,report=example(tmp_path);archive=BacktestArchive(root)
    receipt_sha=publish(archive,fact,config,report)
    receipt=json.loads((run/'completed-archive.json').read_bytes())
    proof=[(p.relative_to(run).as_posix(),sha256(p.read_bytes()).hexdigest(),32*1024*1024)
        for p in run.rglob('*') if p.is_file() and p.name!='completed-archive.json']
    archive._day_view=view(receipt=receipt,receipt_sha=receipt_sha,report=report,trades=[],positions=[],proof=proof)
    return archive,run,receipt_sha,report['records'][0]['trading_date']


def test_hot_date_bypasses_full_report_json_and_keeps_sha_proof(tmp_path,monkeypatch):
    archive,run,receipt,day=archived_cache(tmp_path)
    def forbidden(*args,**kwargs):raise AssertionError('full_report_read_on_hot_date')
    monkeypatch.setattr(archive,'_originals',forbidden)
    first=archive.visual(run.name,receipt,monotonic()+5,ledger=True,day=day)
    second=archive.visual(run.name,receipt,monotonic()+5,ledger=True,day=day)
    assert first==second and first['date']==day


def test_model_projection_reuses_same_day_proof_and_returns_own_copy(tmp_path, monkeypatch):
    archive, run, receipt, _day = archived_cache(tmp_path)
    expected = dict(schema='fixture-model-projection', run_id=run.name, receipt_sha256=receipt,
                    policy=dict(initial_capital_cny='100000'))
    archive._day_view = replace(archive._day_view, configuration_json=json.dumps(expected))
    monkeypatch.setattr(archive, '_originals', lambda *_args, **_kwargs: pytest.fail('model reparsed the full report'))
    value = archive.read(run.name, receipt, monotonic()+5, configuration=True)
    assert value == expected
    value['policy']['initial_capital_cny'] = 'forged'
    assert archive.read(run.name, receipt, monotonic()+5, configuration=True) == expected
    target = run/'basefiles/fees.json'
    target.write_bytes(b'changed')
    with pytest.raises(ArchiveError):
        archive.read(run.name, receipt, monotonic()+5, configuration=True)


@pytest.mark.parametrize('relative',['request.json','result.json','installation.json','basefiles/fees.json','session-basefiles/contracts.json','outputs/test.trades.csv'])
def test_hot_cache_rejects_changed_original_even_same_size(tmp_path,relative):
    archive,run,receipt,day=archived_cache(tmp_path)
    target=run/relative;before=target.read_bytes();target.write_bytes(bytes([before[0]^1])+before[1:])
    with pytest.raises(ArchiveError):archive.visual(run.name,receipt,monotonic()+5,ledger=True,day=day)


def test_hot_cache_rejects_missing_output_and_new_unbound_output(tmp_path):
    archive,run,receipt,day=archived_cache(tmp_path)
    target=run/'outputs/test.trades.csv';body=target.read_bytes();target.unlink()
    with pytest.raises(ArchiveError):archive.visual(run.name,receipt,monotonic()+5,ledger=True,day=day)
    target.write_bytes(body);(run/'outputs/new.csv').write_text('unbound')
    with pytest.raises(ArchiveError):archive.visual(run.name,receipt,monotonic()+5,ledger=True,day=day)


def test_hot_cache_wrong_receipt_and_unknown_day_remain_rejected(tmp_path):
    archive,run,receipt,day=archived_cache(tmp_path)
    with pytest.raises(ArchiveError) as changed:archive.visual(run.name,'f'*64,monotonic()+5,ledger=True,day=day)
    assert changed.value.code==409
    with pytest.raises(ArchiveError) as unknown:archive.visual(run.name,receipt,monotonic()+5,ledger=True,day=20991231)
    assert unknown.value.code==404
