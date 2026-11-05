"""原Writer当前值与归档的职责回归；真实Native/HTTP链另持实际来源证据。"""
from contextlib import nullcontext
from copy import deepcopy
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import sys
import time
from unittest.mock import patch
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT),str(ROOT/'integrations'),str(ROOT/'connectors/qmt_shm/host'),str(ROOT/'connectors/qmt_shm/agent')]
import pytest
from integrations.guanheng.current_day import CurrentDayMarket,publish_current_day,publish_current_day_observation,SHANGHAI
from integrations.guanheng.daily_overlay import _metadata
from integrations.guanheng_market_client.source_history import validate_source_daily_request,validate_source_daily_data


class Archive:
    """已发布历史与Unavailable均为原事实；本替身不生成当前行。"""
    def __init__(self,today,*,empty=False,unavailable=False):
        self.today=today  # 历史末日，用于区分原归档同日优先与上一日。
        self.empty=empty  # 原归档实际返回零行。
        self.unavailable=unavailable  # 原目录没有该证券，允许当前值单独可见。
        self.closed=False  # 原Reader关闭责任。

    def read_scope(self):return nullcontext()

    def call(self,request):
        if self.unavailable:return dict(api_version='guanheng.market.v1',status=dict(code='Unavailable',reason='missing'),data={})
        profile=dict(source_license='archive',price_unit='CNY',volume_unit='lot',amount_unit='CNY')
        metadata=_metadata(dict(provider='Qmt',instance_id='archive',session_id='fixture',generation=1),'a'*64,'archive',profile)
        row=dict(symbol='SSE.588170',date=self.today,open=9,high=10,low=8,close=9,volume=123,amount=1111)
        return dict(api_version='guanheng.market.v1',status=dict(code='Ok',reason=''),data=dict(
            metadata=metadata,bars=[] if self.empty else [row],coverage='Unknown',missing_dates=[],
            selection=dict(period='1d',limit=request['request']['limit'])))

    def close(self):self.closed=True


def setup(tmp_path,*,row_day=None,archive_today=False,empty=False,unavailable=False):
    today=datetime.now(SHANGHAI).date()
    prior=int((today-timedelta(days=1)).strftime('%Y%m%d'))
    day=int(today.strftime('%Y%m%d'))
    source_day=day if row_day is None else row_day
    row=dict(symbol='SSE.588170',trading_date=source_day,action_date=source_day,action_time=1,
        open=11.,high=14.,low=10.,close=13.,volume=987.,amount=3210.)
    publish_current_day(tmp_path,[row],control_id=str(uuid4()),configuration_sha256='b'*64,observed_at=time.time())
    base=Archive(day if archive_today else prior,empty=empty,unavailable=unavailable)
    config=dict(mode='source-current-day',base={},current_day=dict(path=str(tmp_path/'current-day.json'),
        source_license='writer',price_unit='CNY',volume_unit='unknown',amount_unit='CNY'))
    with patch('integrations.guanheng.source_market.create_native_source_market',return_value=base):
        market=CurrentDayMarket(config,max_response_bytes=8*1024*1024)
    query=dict(api_version='guanheng.market.v1',action='history.source-daily-query',
        request=dict(exchange='SSE',code='588170',**{'from':prior,'to':day,'limit':60}))
    return market,base,query,row


def test_current_day_keeps_raw_values_times_and_original_units(tmp_path):
    market,base,request,row=setup(tmp_path)
    request['request']['view']='current'
    result=market.call(request)['data']
    assert len(result['bars'])==2 and result['bars'][-1]['close']==13
    assert result['bars'][-1]['volume']==987
    assert result['metadata']['volume_unit']=='unknown'
    assert result['provenance'][0]['metadata']['volume_unit']=='lot'
    assert result['current_day']['source_at'].endswith('00:00:00.001000+08:00')
    assert result['current_day']['closed'] is False
    validate_source_daily_data(result,request['request'])
    market.close();assert base.closed


@pytest.mark.parametrize('view',[None,'archive'])
def test_strategy_default_and_frozen_archive_do_not_read_current_day(tmp_path,view):
    market,base,request,row=setup(tmp_path)
    if view is not None:request['request']['view']=view
    result=market.call(request)['data']
    assert len(result['bars'])==1 and result['bars'][-1]['close']==9
    assert 'current_day' not in result
    market.close()


def test_same_day_archive_wins_over_earlier_writer_snapshot(tmp_path):
    market,base,request,row=setup(tmp_path,archive_today=True)
    request['request']['view']='current'
    data=market.call(request)['data']
    assert data['bars'][-1]['close']==9 and 'current_day' not in data
    market.close()


@pytest.mark.parametrize('unavailable',[False,True])
def test_current_day_can_be_only_bar_for_new_security(tmp_path,unavailable):
    market,base,request,row=setup(tmp_path,empty=True,unavailable=unavailable)
    request['request']['view']='current'
    response=market.call(request)
    assert response['status']['code']=='Ok' and len(response['data']['bars'])==1
    assert response['data']['bars'][0]['date']==row['trading_date']
    market.close()


@pytest.mark.parametrize('broken',[b'{}',b'not-json',None])
def test_current_snapshot_failure_preserves_known_archive(tmp_path,broken):
    market,base,request,row=setup(tmp_path)
    file=tmp_path/'current-day.json'
    if broken is None:file.unlink()
    else:file.write_bytes(broken)
    request['request']['view']='current'
    response=market.call(request)
    assert response['status']['code']=='Ok'
    assert response['data']['bars'][-1]['close']==9
    market.close()


def test_old_cache_does_not_become_current_day(tmp_path):
    previous=int((datetime.now(SHANGHAI).date()-timedelta(days=2)).strftime('%Y%m%d'))
    market,base,request,row=setup(tmp_path,row_day=previous)
    request['request']['view']='current'
    assert 'current_day' not in market.call(request)['data']
    market.close()


def test_query_before_current_date_keeps_previous_history(tmp_path):
    market,base,request,row=setup(tmp_path)
    request['request'].update(view='current',to=request['request']['from'])
    assert 'current_day' not in market.call(request)['data']
    market.close()


def test_atomic_publish_failure_keeps_previous_file_without_temporary_growth(tmp_path):
    market,base,request,row=setup(tmp_path)
    before=(tmp_path/'current-day.json').read_bytes()
    with patch('integrations.guanheng.collection_status.replace_status',side_effect=OSError):
        with pytest.raises(OSError):
            publish_current_day(tmp_path,[dict(row,close=12.)],control_id=str(uuid4()),configuration_sha256='c'*64,observed_at=time.time())
    assert (tmp_path/'current-day.json').read_bytes()==before
    assert not list(tmp_path.glob('*.tmp'))
    market.close()


def test_frozen_snapshot_cannot_request_live_values(tmp_path):
    market,base,request,row=setup(tmp_path)
    request['request'].update(view='current',snapshot_id='a'*64)
    with pytest.raises(ValueError):validate_source_daily_request(request['request'])
    market.close()


def test_both_projection_and_diagnostic_failures_stay_outside_writer_lifecycle(tmp_path):
    """单独的诊断文件共享冲突曾逃出旁路，触发原collection.close。"""
    class Writer:
        def current_days(self):raise OSError('isolated current read failure')
    with patch('integrations.guanheng.collection_projection.replace_status',side_effect=OSError):
        result=publish_current_day_observation(Writer(),tmp_path,tmp_path,
            control_id=str(uuid4()),configuration_sha256='a'*64)
    assert result=='OSError'
    assert not list(tmp_path.glob('*.tmp'))
