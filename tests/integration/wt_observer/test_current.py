"""CURRENT原子换代经原SDK/App实际读取；文件均为隔离fixture，无WT进程操作。"""
import json
from time import monotonic
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from test_account_publication import published as account_publication
from test_business import publication as strategy_publication
from guanheng_app.app import create_app
from guanheng_app.settings import ConsoleSettings
from guanheng_app.wt_runtime_observation import RuntimeObservationConfig, resolve_runtime_configuration
from guanheng_market_client.runtime_status import replace_status


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
