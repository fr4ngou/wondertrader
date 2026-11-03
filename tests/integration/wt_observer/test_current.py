"""CURRENT原子换代经原SDK/App实际读取；文件均为隔离fixture，无WT进程操作。"""
import json
from pathlib import Path
import sys
from time import monotonic
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'apps/guanheng'), str(ROOT/'integrations')]
from guanheng_app.app import create_app
from guanheng_app.settings import ConsoleSettings
from guanheng_app.wt_runtime_observation import RuntimeObservationConfig, resolve_runtime_configuration
from guanheng_market_client.runtime_status import replace_status

FIXTURES = Path(__file__).with_name('current-fixtures')


@pytest.fixture
def account_publication(tmp_path):
    # 冻结的原SDK替身NAP样本，来源沿旧account-publication.fixture；无真实账户。
    value = json.loads((FIXTURES/'account.json').read_bytes())
    folder = tmp_path/value['control_id']; folder.mkdir()
    identity = {key:value[key] for key in ('control_id','config_sha256','pid')}
    ready = dict(schema='guanheng.account-observation.ready.v1', **identity)
    reference = dict(schema='guanheng.account-observation-reference.v1', path=str(folder/'observation.json'),
        ready_path=str(folder/'ready.json'), **identity)
    runtime = dict(schema='guanheng.wt-runtime-status.v1',control_id=str(uuid4()),instance_id=str(uuid4()),
        configuration_sha256='a'*64,pid=value['pid'],state='ready',ready=True,
        components=dict(account_observation=dict(pid=value['pid'],state='ready',ready=True,pending=False,
            forced=False,account_observation=reference)))
    files = dict(runtime=tmp_path/'status.json',ready=folder/'ready.json',publication=folder/'observation.json')
    values = dict(runtime=runtime,ready=ready,publication=value)
    def write():
        for key,path in files.items(): publish(path,values[key])
    write()
    settings = ConsoleSettings(account_source='wt_account_publication',wt_status_file=str(files['runtime']),
        wt_control_id=runtime['control_id'],wt_instance_id=runtime['instance_id'],wt_configuration_sha256='a'*64)
    return settings,values,files,write


@pytest.fixture
def strategy_publication(tmp_path):
    # 原retained-observation SDK替身报告；业务值与NAP样本分属各自发布者。
    control,instance,execution = str(uuid4()),str(uuid4()),str(uuid4())
    folder = tmp_path/execution; folder.mkdir()
    identity = dict(control_id=execution,config_sha256='b'*64,pid=777)
    reference = dict(schema='guanheng.execution-observation-reference.v1',path=str(folder/'strategies.json'),
        ready_path=str(folder/'ready.json'), **identity)
    runtime = dict(schema='guanheng.wt-runtime-status.v1',control_id=control,instance_id=instance,
        configuration_sha256='a'*64,pid=555,state='ready',ready=True,
        components=dict(execution=dict(state='ready',ready=True,pending=True,forced=False,pid=777,business_observation=reference)))
    ready = dict(schema='guanheng.execution.ready.v1',closed=False, **identity)
    result = dict(schema='guanheng.configured-cta-observation.v2',
        strategies={'resonance-regime-v1':json.loads((FIXTURES/'strategy.json').read_bytes())}, **identity)
    files = dict(runtime=tmp_path/'status.json',ready=folder/'ready.json',result=folder/'strategies.json')
    values = dict(runtime=runtime,ready=ready,result=result)
    def write():
        for key,path in files.items(): publish(path,values[key])
    write()
    settings = ConsoleSettings(wt_status_file=str(files['runtime']),wt_control_id=control,
        wt_instance_id=instance,wt_configuration_sha256='a'*64)
    return settings,values,files,write


def publish(path, value):
    candidate = path.with_suffix('.next')
    candidate.write_text(json.dumps(value), encoding='utf8')
    replace_status(candidate, path)


def pointer(settings):
    return dict(schema='guanheng.wt-current.v1', **settings.model_dump(include={
        'wt_status_file', 'wt_control_id', 'wt_instance_id', 'wt_configuration_sha256'}))


def dynamic_settings(settings, path):
    return settings.model_copy(update=dict(wt_current_file=str(path)))


def test_same_app_follows_nap_generation_without_fixed_fallback(account_publication, tmp_path):
    settings, values, _files, write = account_publication
    current = tmp_path/'CURRENT.json'
    dynamic = dynamic_settings(settings, current)
    app = create_app(dynamic)
    with TestClient(app) as client:
        # 旧固定四项仍有效；显式CURRENT缺失时也必须报错，随后原App自动恢复。
        assert client.get('/v1/ui/account/overview').status_code == 503
        assert client.get('/v1/ui/capabilities').json()['features']['account']['available']
        publish(current, pointer(settings))
        first = client.get('/v1/ui/account/overview').json()
        first_details = client.get('/v1/ui/strategy-details').json()
        assert first_details['account']['publication']['scope_id'] == first['publication']['scope_id']
        values['runtime']['control_id'] = str(uuid4())
        values['runtime']['configuration_sha256'] = 'd'*64
        write()
        changed = settings.model_copy(update=dict(wt_control_id=values['runtime']['control_id'],
            wt_configuration_sha256='d'*64))
        publish(current, pointer(changed))
        second = client.get('/v1/ui/account/overview').json()
        assert second['publication']['scope_id'] != first['publication']['scope_id']
        assert client.get('/v1/ui/strategy-details').json()['runtime_scope_id'] != first_details['runtime_scope_id']
        assert second['groups'] == first['groups']
        assert client.get('/v1/ui/wt-runtime').status_code == 200
        assert client.get('/v1/ui/wt-instances').json()['instances'][0]['state'] == 'available'
        publish(current, {'schema':'invalid'})
        assert client.get('/v1/ui/strategy-details').status_code == 503
        assert client.get('/v1/ui/account/overview').status_code == 503
        assert client.get('/v1/ui/wt-instances').json()['instances'][0]['state'] == 'unavailable'
        publish(current, pointer(changed))
        assert client.get('/v1/ui/account/overview').json()['publication']['scope_id'] == second['publication']['scope_id']
    assert app.state.shutdown_complete and app.state.reader.live_threads == app.state.backtest_reader.live_threads == 0


@pytest.mark.parametrize('change', [
    lambda v: v.update(schema='wrong'), lambda v: v.update(extra='private'),
    lambda v: v.pop('wt_control_id'), lambda v: v.update(wt_control_id=str(uuid4()).upper()),
    lambda v: v.update(wt_instance_id=17), lambda v: v.update(wt_configuration_sha256='Z'*64),
    lambda v: v.update(wt_status_file='relative/status.json'), lambda v: v.update(wt_status_file='E:/other.json'),
    lambda v: v.update(wt_status_file='', wt_control_id='', wt_instance_id='', wt_configuration_sha256=''),
])
def test_invalid_current_never_uses_valid_fixed_binding(account_publication, tmp_path, change):
    settings, _values, _files, _write = account_publication
    path = tmp_path/'CURRENT.json'
    value = pointer(settings); change(value); publish(path, value)
    with TestClient(create_app(dynamic_settings(settings, path))) as client:
        for route in ('/v1/ui/wt-runtime','/v1/ui/account/overview','/v1/ui/strategy-runtime','/v1/ui/strategy-details'):
            response = client.get(route)
            assert response.status_code == 503
            assert str(path) not in response.text and 'private' not in response.text


def test_strategy_chain_and_projection_share_one_resolved_generation(strategy_publication, tmp_path, monkeypatch):
    settings, _values, _files, _write = strategy_publication
    current = tmp_path/'CURRENT.json'; publish(current, pointer(settings))
    dynamic = dynamic_settings(settings, current)
    import guanheng_app.wt_business_observation as business
    original = business.read_runtime_snapshot
    seen = []
    def switch_after_first_root(configuration, deadline):
        seen.append(configuration)
        snapshot = original(configuration, deadline)
        if len(seen) == 1:
            # 回调读取期间发生运行换代：本次保持已选的完整旧代，下轮读取新指针。
            publish(current, pointer(settings) | dict(wt_control_id=str(uuid4())))
        return snapshot
    monkeypatch.setattr(business, 'read_runtime_snapshot', switch_after_first_root)
    with TestClient(create_app(dynamic)) as client:
        first = client.get('/v1/ui/account/overview')
        assert first.status_code == 200
        assert first.json()['groups']['account']['status'] == 'complete'
        assert len(seen) == 2 and seen[0] == seen[1]
        assert client.get('/v1/ui/account/overview').status_code == 503


def test_current_strategy_result_follows_changed_business_reference(strategy_publication, tmp_path):
    settings, values, _files, write = strategy_publication
    current = tmp_path/'CURRENT.json'; publish(current, pointer(settings))
    with TestClient(create_app(dynamic_settings(settings, current))) as client:
        first = client.get('/v1/ui/strategy-runtime').json()
        assert first['strategy']['status'] == 'selling'
        values['runtime']['control_id'] = str(uuid4())
        values['runtime']['configuration_sha256'] = 'e'*64
        values['result']['strategies']['resonance-regime-v1']['broker_observation']['available'] = 12345
        write()
        publish(current, pointer(settings) | dict(wt_control_id=values['runtime']['control_id'], wt_configuration_sha256='e'*64))
        result = client.get('/v1/ui/account/overview').json()
        assert result['groups']['account']['rows'][0]['fields']['available']['value'] == 12345
        assert client.get('/v1/ui/strategy-runtime').status_code == 200


def test_pending_pointer_uses_original_deadline(account_publication, tmp_path, monkeypatch):
    from guanheng_market_client.runtime_status import CollectionStatusPending
    import guanheng_app.wt_runtime_observation as runtime
    settings, _values, _files, _write = account_publication
    current = tmp_path/'CURRENT.json'; publish(current, pointer(settings))
    original = runtime.read_status_snapshot
    calls = []
    def pending_then_ready(path, maximum=65536):
        calls.append(path)
        if len(calls) == 1: raise CollectionStatusPending()
        return original(path, maximum)
    monkeypatch.setattr(runtime, 'read_status_snapshot', pending_then_ready)
    config = RuntimeObservationConfig.from_settings(dynamic_settings(settings, current))
    assert resolve_runtime_configuration(config, monotonic()+2).control_id == settings.wt_control_id
    assert calls == [current, current]
    with pytest.raises(TimeoutError): resolve_runtime_configuration(config, monotonic()-1)


def test_environment_reads_current_without_retired_owner_configuration(monkeypatch, tmp_path):
    current = str(tmp_path/'CURRENT.json')
    monkeypatch.setenv('GUANHENG_WT_CURRENT_FILE', current)
    assert ConsoleSettings.from_environment().wt_current_file == current


def test_new_generation_details_exposes_new_scope_even_while_account_is_invalid(account_publication, tmp_path):
    settings, values, files, write = account_publication
    current = tmp_path/'CURRENT.json'; publish(current, pointer(settings))
    with TestClient(create_app(dynamic_settings(settings, current))) as client:
        first = client.get('/v1/ui/strategy-details').json()
        values['runtime']['control_id'] = str(uuid4()); write()
        publish(current, pointer(settings) | dict(wt_control_id=values['runtime']['control_id']))
        publish(files['publication'], {'invalid':True})
        second = client.get('/v1/ui/strategy-details')
        assert second.status_code == 200
        assert second.json()['account'] is None
        assert second.json()['runtime_scope_id'] != first['runtime_scope_id']
