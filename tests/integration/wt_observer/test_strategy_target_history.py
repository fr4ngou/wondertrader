"""原生目标设置记录的行为回归；合成日志及运行身份，不接触交易账户。"""
import base64
import hashlib
import json
from pathlib import Path
from time import monotonic
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from guanheng_app.reading import BoundedReader
from guanheng_app.strategy_target_history import read_signal_history, read_target_history, TargetHistoryChanged
from guanheng_app.strategy_target_history_routes import router
from guanheng_app.wt_runtime_observation import RuntimeObservationConfig


HEADER = b'code,target,sigprice,gentime,usertag\n'


def line(target, seconds='01', symbol='510300'):
    return f'SSE.ETF.{symbol},{target},4.25,202611050930{seconds}123,gh_rt\n'.encode()


def read(path, limit=20, cursor=None):
    return read_signal_history(path, 'synthetic-instance', 'synthetic-strategy', limit, cursor, monotonic()+3)


def test_native_changes_keep_round_trip_first_unknown_and_zero_distinct(tmp_path):
    p=tmp_path/'signals.csv';p.write_bytes(HEADER+line(100)+line(100,'02')+line(300,'03')+line(100,'04')+line(0,'05'))
    source,items,cursor=read(p)
    assert [x['target_quantity']for x in items]==[0,100,300,100]
    assert [x['change_quantity']for x in items]==[-100,-200,200,None]
    assert items[-1]['previous_target_quantity'] is None and items[-1]['kind']=='initial'
    assert items[0]['changed_at']=='2026-11-05T09:30:05.123+08:00'
    assert source['raw_count']==5 and source['changed_count']==3 and source['unchanged_count']==1 and source['initial_count']==1
    assert all(x['reason']is None and x['target_weight']is None and x['strategy_version']is None for x in items)
    assert cursor is None


def test_paging_is_fixed_during_native_append_and_initial_rows_are_not_lost(tmp_path):
    p=tmp_path/'signals.csv';p.write_bytes(HEADER+b''.join(line(i*100,f'{i+1:02}')for i in range(5)))
    source,items,cursor=read(p,2);p.write_bytes(p.read_bytes()+line(1000,'09'))
    source2,items2,cursor2=read(p,2,cursor);_,items3,last=read(p,2,cursor2)
    assert source['snapshot_sha256']==source2['snapshot_sha256']
    assert [x['sequence']for x in items+items2+items3]==[5,4,3,2,1]
    assert last is None and read(p)[0]['raw_count']==6


@pytest.mark.parametrize('change',('overwrite','truncate','replace','invalid-prefix','delete'))
def test_old_prefix_change_requires_refresh(tmp_path,change):
    p=tmp_path/'signals.csv';p.write_bytes(HEADER+line(100)+line(200,'02'))
    _,_,cursor=read(p,1)
    if change=='overwrite':p.write_bytes(HEADER+line(900)+line(200,'02'))
    elif change=='truncate':p.write_bytes(HEADER+line(100))
    elif change=='invalid-prefix':p.write_bytes(HEADER+line('NaN')+line(200,'02'))
    elif change=='delete':p.unlink()
    else:
        replacement=tmp_path/'replacement';replacement.write_bytes(p.read_bytes());replacement.replace(p)
    with pytest.raises(TargetHistoryChanged):read(p,1,cursor)


def test_incomplete_append_is_explicit_and_completed_on_refresh(tmp_path):
    p=tmp_path/'signals.csv';tail=line(200,'02');p.write_bytes(HEADER+line(100)+tail[:-4])
    source,items,_=read(p);assert source['incomplete_tail'] and len(items)==1
    with p.open('ab')as f:f.write(tail[-4:])
    assert read(p)[0]['changed_count']==1 and not read(p)[0]['incomplete_tail']


@pytest.mark.parametrize('raw',(b'bad,header\n',HEADER+line('-1'),HEADER+line('NaN'),HEADER+b'x'*2050))
def test_invalid_native_rows_fail_without_fabricating_records(tmp_path,raw):
    p=tmp_path/'signals.csv';p.write_bytes(raw)
    with pytest.raises(ValueError):read(p)


def test_native_scientific_price_has_bounded_expansion(tmp_path):
    from guanheng_app.strategy_target_history import _number
    assert _number('1e-6')=='0.000001' and _number('1e+6',quantity=True)==1000000
    for value in ('1e-1000000','0e+1000000','0e-1000000'):
        with pytest.raises(ValueError):_number(value)


def test_cursor_changed_during_parsing_has_conflict_precedence(tmp_path):
    import guanheng_app.strategy_target_history as module
    p=tmp_path/'signals.csv';p.write_bytes(HEADER+line(100)+line(200,'02'))
    _,_,cursor=read(p,1)
    def change_and_fail(*_args):
        p.write_bytes(HEADER+line('NaN')+line(200,'02'))
        raise ValueError('changed native prefix')
    with patch.object(module,'_row',side_effect=change_and_fail),pytest.raises(TargetHistoryChanged):
        read(p,1,cursor)


def test_exact_selected_strategy_and_native_configuration_sha(tmp_path):
    import guanheng_app.strategy_target_history as module
    output=tmp_path/'financial';folder=output/'outputs/selected';folder.mkdir(parents=True)
    (folder/'signals.csv').write_bytes(HEADER+line(100))
    control=tmp_path/'control';control.mkdir();raw=json.dumps(dict(output_directory=str(output),strategies=[dict(id='selected')])).encode()
    (control/'execution.json').write_bytes(raw)
    reference=dict(path=str(control/'strategies.json'),config_sha256=hashlib.sha256(raw).hexdigest())
    config=RuntimeObservationConfig(tmp_path/'status.json','control','instance','a'*64)
    runtime=SimpleNamespace(value=dict(components=dict(execution=dict(business_observation=reference))))
    with patch.object(module.RuntimeObservationConfig,'from_settings',return_value=config),patch.object(module,'read_business',return_value=({'selected':{}},reference,'ready')),patch.object(module,'published_identity',return_value=(dict(strategy_version='1.2.2'),())),patch.object(module,'read_runtime_snapshot',return_value=runtime):
        result=read_target_history(SimpleNamespace(),'selected','1.2.2',deadline=monotonic()+3)
        assert result['state']=='available' and len(result['items'])==1
        wrong=read_target_history(SimpleNamespace(),'selected','different',deadline=monotonic()+3)
        assert wrong['state']=='not_current' and wrong['items']==[] and wrong['source'] is None
        (control/'execution.json').write_bytes(raw+b' ')
        with pytest.raises(ValueError):read_target_history(SimpleNamespace(),'selected','1.2.2',deadline=monotonic()+3)


def test_http_uses_original_reader_strict_query_and_no_mutations():
    settings=SimpleNamespace(wt_current_file='',wt_status_file='',wt_control_id='',wt_instance_id='',wt_configuration_sha256='')
    app=FastAPI();app.include_router(router(settings));reader=BoundedReader();reader.start();app.state.reader=reader
    try:
        with TestClient(app)as client:
            url='/v1/ui/strategy-target-history?strategy_id=selected&strategy_version=1.2.2'
            response=client.get(url);assert response.status_code==200 and response.json()['state']=='waiting'
            for suffix in ('&limit=101','&private=x','&strategy_id=another','&cursor=invalid'):
                assert client.get(url+suffix).status_code==422
            assert client.post(url).status_code==405
            with patch('guanheng_app.strategy_target_history_routes.read_target_history',side_effect=TargetHistoryChanged()):
                assert client.get(url).status_code==409
    finally:assert reader.close(3)
