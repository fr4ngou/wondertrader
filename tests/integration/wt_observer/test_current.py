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


@pytest.mark.parametrize('phase,label', [
    ('waiting_source', '等待QMT连接，策略执行尚未启动'),
    ('starting_execution', '正在启动策略执行器'),
])
def test_source_wait_reports_strategy_not_started(strategy_publication, phase, label):
    settings, values, files, write = strategy_publication
    values['runtime']['components']['execution'].update(
        pid=None, business_observation=None, execution_ready=False, source_wait_state=phase)
    write()
    original = {key: path.read_bytes() for key, path in files.items()}
    with TestClient(create_app(settings)) as client:
        for path in ('/v1/ui/wt-runtime', '/v1/ui/wt-instances'):
            response = client.get(path)
            assert response.status_code == 200
            value = response.json()
            runtime = value['runtime'] if path.endswith('wt-runtime') else value['instances'][0]['runtime']
            execution = next(c for c in runtime['components'] if c['name'] == 'execution')
            assert execution['state'] == 'ready' and execution['ready'] is True
            assert execution['label'] == label
        response = client.get('/v1/ui/strategy-details')
        assert response.status_code == 200
        execution = response.json()['execution']
        assert execution['state'] == 'starting' and execution['label'] == label
        assert execution['started_at']['value'] is None
    assert {key: path.read_bytes() for key, path in files.items()} == original


def test_runtime_fault_takes_precedence_over_source_wait(strategy_publication):
    settings, values, _files, write = strategy_publication
    values['runtime'].update(state='faulted', ready=False)
    values['runtime']['components']['execution'].update(
        pid=None, business_observation=None, execution_ready=False, source_wait_state='waiting_source')
    write()
    with TestClient(create_app(settings)) as client:
        execution = client.get('/v1/ui/strategy-details').json()['execution']
        assert execution['state'] == 'faulted' and execution['label'] == '策略运行失败'


@pytest.mark.parametrize('phase,ready', [('waiting_source', True), ('private-invalid-phase', False)])
def test_inconsistent_source_wait_is_unknown(strategy_publication, phase, ready):
    settings, values, _files, write = strategy_publication
    values['runtime']['components']['execution'].update(
        pid=None, business_observation=None, execution_ready=ready, source_wait_state=phase)
    write()
    with TestClient(create_app(settings)) as client:
        response = client.get('/v1/ui/strategy-details')
        execution = response.json()['execution']
        assert execution['state'] == 'unavailable'
        assert execution['label'] == '策略执行启动状态待核实'
        assert 'private-invalid-phase' not in response.text


def test_same_app_follows_source_wait_to_started_execution(strategy_publication):
    from copy import deepcopy
    settings, values, _files, write = strategy_publication
    original = deepcopy(values['runtime']['components']['execution'])
    values['runtime']['components']['execution'].update(
        pid=None, business_observation=None, execution_ready=False, source_wait_state='waiting_source')
    write()
    with TestClient(create_app(settings)) as client:
        assert client.get('/v1/ui/strategy-details').json()['execution']['state'] == 'starting'
        values['runtime']['components']['execution'] = dict(original,
            execution_ready=True, source_wait_state='execution_started')
        write()
        execution = client.get('/v1/ui/strategy-details').json()['execution']
        assert execution['state'] == 'ready'
        assert execution['label'] != '等待QMT连接，策略执行尚未启动'


def test_source_wait_ignores_previous_lifecycle_and_strategy():
    from guanheng_app.observer_strategy_details import project_execution
    runtime = dict(state='ready', components=dict(execution=dict(state='ready', ready=True,
        execution_ready=False, source_wait_state='waiting_source', pid=None, business_observation=None)))
    result = project_execution(runtime, dict(status='waiting_market_input'),
        dict(execution_started_at='2026-01-05T01:30:00+00:00'))
    assert result['state'] == 'starting'
    assert result['started_at']['value'] is None and result['duration_seconds']['value'] is None


@pytest.mark.parametrize('phase,ready', [
    ('waiting_source', False), ('starting_execution', False), ('waiting_source', True),
])
def test_source_wait_cannot_reuse_live_pid_as_online(phase, ready):
    from guanheng_app.live_strategy_performance import execution_process_state
    runtime = dict(state='ready', ready=True, pid=101, components=dict(execution=dict(
        state='ready', ready=True, execution_ready=ready, source_wait_state=phase,
        pid=102, business_observation=dict(pid=102))))
    probes = []
    def probe(pid, started):
        probes.append(pid)
        return True
    current, active = execution_process_state(runtime, dict(pid=102),
        dict(execution_started_at='2026-01-05T01:30:00+00:00'), probe=probe)
    assert current is False and active is None
    assert probes == []


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


@pytest.mark.parametrize('enabled', [True, False])
def test_runtime_exposes_verified_native_order_switch_without_private_configuration(strategy_publication, enabled):
    import hashlib
    settings, values, files, write = strategy_publication
    configuration = files['ready'].with_name('execution.json')
    raw = json.dumps(dict(schema_version='guanheng.cta-execution.v1',
        trader=dict(writes_enabled=enabled, account='private-account', key_env='PRIVATE_KEY'))).encode('utf8')
    configuration.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    for item in (values['ready'], values['result'], values['runtime']['components']['execution']['business_observation']):
        item['config_sha256'] = digest
    write()
    with TestClient(create_app(settings)) as client:
        for path in ('/v1/ui/wt-runtime', '/v1/ui/wt-instances'):
            response = client.get(path)
            assert response.status_code == 200
            value = response.json()
            runtime = value['runtime'] if path.endswith('wt-runtime') else value['instances'][0]['runtime']
            execution = next(c for c in runtime['components'] if c['name'] == 'execution')
            control = execution['execution_control']
            assert control['state'] == 'available' and control['writes_enabled'] is enabled
            assert control['label'] == ('WT下单开关已开启' if enabled else 'WT下单开关已关闭')
            assert 'private-account' not in response.text and 'PRIVATE_KEY' not in response.text
            assert str(configuration) not in response.text
    assert configuration.read_bytes() == raw


@pytest.fixture
def verified_switch(strategy_publication):
    import hashlib
    settings, values, files, write = strategy_publication
    configuration = files['ready'].with_name('execution.json')
    def configure(value):
        raw = value if type(value) is bytes else json.dumps(value).encode('utf8')
        configuration.write_bytes(raw)
        digest = hashlib.sha256(raw).hexdigest()
        for item in (values['ready'], values['result'], values['runtime']['components']['execution']['business_observation']):
            item['config_sha256'] = digest
        write()
        return raw
    raw = configure(dict(schema_version='guanheng.cta-execution.v1', trader=dict(writes_enabled=True)))
    return settings, values, files, write, configuration, configure, raw


@pytest.mark.parametrize('failure', [
    'missing', 'digest', 'json', 'duplicate', 'schema', 'flag_integer', 'flag_text', 'flag_null',
    'trader_array', 'ready_pid', 'ready_digest', 'ready_closed', 'reference_pid', 'reference_path', 'old_publisher',
])
def test_invalid_order_switch_is_local_unknown_not_false_or_runtime_failure(verified_switch, failure):
    settings, values, files, write, configuration, configure, _raw = verified_switch
    if failure == 'missing': configuration.unlink()
    elif failure == 'digest': configuration.write_bytes(configuration.read_bytes()+b' ')
    elif failure == 'json': configure(b'{invalid-private-body')
    elif failure == 'duplicate': configure(b'{"schema_version":"guanheng.cta-execution.v1","trader":{"writes_enabled":true,"writes_enabled":false}}')
    elif failure in ('schema', 'flag_integer', 'flag_text', 'flag_null', 'trader_array'):
        value = dict(schema_version='guanheng.cta-execution.v1', trader=dict(writes_enabled=True))
        if failure == 'schema': value['schema_version'] = 'private-invalid-schema'
        elif failure == 'trader_array': value['trader'] = []
        else: value['trader']['writes_enabled'] = {'flag_integer':1, 'flag_text':'true', 'flag_null':None}[failure]
        configure(value)
    elif failure.startswith('ready_'):
        values['ready'][{'ready_pid':'pid','ready_digest':'config_sha256','ready_closed':'closed'}[failure]] = {
            'ready_pid':778,'ready_digest':'c'*64,'ready_closed':True}[failure]
        write()
    else:
        execution = values['runtime']['components']['execution']
        if failure == 'reference_pid': execution['business_observation']['pid'] = 778
        elif failure == 'reference_path': execution['business_observation']['path'] = str(files['ready'].parent.parent/'strategies.json')
        else: execution.pop('business_observation')
        write()
    with TestClient(create_app(settings)) as client:
        response = client.get('/v1/ui/wt-runtime')
        assert response.status_code == 200
        value = response.json()
        assert value['runtime']['state'] == 'ready'
        execution = next(c for c in value['runtime']['components'] if c['name'] == 'execution')
        assert execution['ready'] is True
        assert execution['execution_control'] == dict(state='unavailable', writes_enabled=None, label='WT下单开关暂不可核实')
        assert 'private' not in response.text and str(configuration) not in response.text


def test_missing_configuration_recovers_without_app_restart_and_does_not_gate_strategy_reads(verified_switch):
    settings, _values, _files, _write, configuration, _configure, raw = verified_switch
    configuration.unlink()
    with TestClient(create_app(settings)) as client:
        first = client.get('/v1/ui/wt-runtime').json()
        assert first['runtime']['components'][0]['execution_control']['writes_enabled'] is None
        assert client.get('/v1/ui/strategy-runtime').status_code == 200
        configuration.write_bytes(raw)
        assert client.get('/v1/ui/wt-runtime').json()['runtime']['components'][0]['execution_control']['writes_enabled'] is True
        assert client.get('/v1/ui/strategy-runtime').status_code == 200
    assert configuration.read_bytes() == raw


def test_reference_changed_during_configuration_read_yields_unknown(verified_switch, monkeypatch):
    import guanheng_app.wt_runtime_observation as runtime
    settings, values, _files, write, _configuration, _configure, _raw = verified_switch
    original = runtime.read_runtime_snapshot
    calls = []
    def changed(configuration, deadline):
        snapshot = original(configuration, deadline)
        calls.append(configuration)
        if len(calls) == 1:
            values['runtime']['components']['execution']['business_observation']['config_sha256'] = 'd'*64
            write()
        return snapshot
    monkeypatch.setattr(runtime, 'read_runtime_snapshot', changed)
    with TestClient(create_app(settings)) as client:
        response = client.get('/v1/ui/wt-runtime')
        assert response.status_code == 200
        assert response.json()['runtime']['components'][0]['execution_control']['writes_enabled'] is None
        assert len(calls) == 2 and calls[0] == calls[1]


def test_ready_replacement_pending_reuses_original_deadline(verified_switch, monkeypatch):
    from guanheng_market_client.runtime_status import CollectionStatusPending
    import guanheng_app.wt_runtime_observation as runtime
    settings, _values, files, _write, _configuration, _configure, _raw = verified_switch
    original = runtime.read_status_snapshot
    calls = []
    def pending_once(path, maximum=65536):
        if path == files['ready']:
            calls.append(path)
            if len(calls) == 1: raise CollectionStatusPending()
        return original(path, maximum)
    monkeypatch.setattr(runtime, 'read_status_snapshot', pending_once)
    with TestClient(create_app(settings)) as client:
        response = client.get('/v1/ui/wt-runtime')
        assert response.status_code == 200
        assert response.json()['runtime']['components'][0]['execution_control']['writes_enabled'] is True
    assert len(calls) == 2



def test_order_switch_pending_read_obeys_original_deadline(verified_switch, monkeypatch):
    from guanheng_market_client.runtime_status import CollectionStatusPending
    import guanheng_app.wt_runtime_observation as runtime
    settings, _values, files, _write, configuration, _configure, raw = verified_switch
    original = runtime.read_status_snapshot
    calls = []
    def pending(path, maximum=65536):
        if path == files['ready']:
            calls.append(path)
            raise CollectionStatusPending()
        return original(path, maximum)
    monkeypatch.setattr(runtime, 'read_status_snapshot', pending)
    started = monotonic()
    with pytest.raises(TimeoutError):
        runtime.observe_runtime(RuntimeObservationConfig.from_settings(settings), started+.03)
    assert calls and monotonic()-started < 1
    assert configuration.read_bytes() == raw


def test_order_switch_pins_current_for_one_read_then_follows_next_generation(verified_switch, tmp_path, monkeypatch):
    import guanheng_app.wt_runtime_observation as runtime
    settings, _values, _files, _write, _configuration, _configure, _raw = verified_switch
    current = tmp_path/'CURRENT.json'; publish(current, pointer(settings))
    original = runtime.read_runtime_snapshot
    seen = []
    def changed(configuration, deadline):
        snapshot = original(configuration, deadline)
        seen.append(configuration)
        if len(seen) == 1:
            publish(current, pointer(settings) | dict(wt_control_id=str(uuid4())))
        return snapshot
    monkeypatch.setattr(runtime, 'read_runtime_snapshot', changed)
    with TestClient(create_app(dynamic_settings(settings, current))) as client:
        response = client.get('/v1/ui/wt-runtime')
        assert response.status_code == 200
        assert response.json()['runtime']['components'][0]['execution_control']['writes_enabled'] is True
        assert len(seen) == 2 and seen[0] == seen[1]
        assert client.get('/v1/ui/wt-runtime').status_code == 503


def test_published_targets_survive_unverified_nav_without_replanning(strategy_publication, monkeypatch):
    from copy import deepcopy
    import guanheng_strategy_native.planner as planner

    settings, values, files, write = strategy_publication
    rows = values['result']['strategies']
    report = rows['resonance-regime-v1']
    report['outcome']['state']['basis']['native_nav_verified'] = False
    # 同轮另一策略仍须可读；身份来自发布者，不取安装版本。
    other = deepcopy(report)
    other_id = 'another-published-strategy'
    other['core_result']['strategy_id'] = other_id
    other['outcome']['state']['target']['strategy_id'] = other_id
    other['outcome']['state']['target']['algorithm_id'] = other_id+'@1.1.2/ledger-front-ratio-v1'
    rows[other_id] = other
    write()
    before = {key: path.read_bytes() for key, path in files.items()}
    def unexpected_replanning(*args):
        pytest.fail('展示读取调用了交易规划器')
    monkeypatch.setattr(planner, 'target_quantities', unexpected_replanning)
    with TestClient(create_app(settings)) as client:
        response = client.get('/v1/ui/strategy-runtime')
        assert response.status_code == 200
        value = response.json()
        assert value['strategy']['positions'][2]['stage_target'] == 200
        assert {row['strategy_id'] for row in value['strategies']} == set(rows)
        for identity in rows:
            response = client.get('/v1/ui/live-strategy-performance', params=dict(
                strategy_id=identity, strategy_version='1.1.2', limit=90))
            assert response.status_code == 200
            assert response.json()['summary'] is None
    assert before == {key: path.read_bytes() for key, path in files.items()}


@pytest.mark.parametrize('failure', ['version', 'identity', 'configuration', 'universe', 'quantity', 'duplicate'])
def test_published_target_corruption_is_rejected(strategy_publication, failure):
    from guanheng_app.strategy_runtime_projection import project_strategy

    _settings, values, _files, _write = strategy_publication
    report = values['result']['strategies']['resonance-regime-v1']
    state = report['outcome']['state']
    if failure == 'version': state['version'] = 2
    elif failure == 'identity': state['target']['strategy_id'] = 'other-strategy'
    elif failure == 'configuration': state['target']['config_id'] = 'other-configuration'
    elif failure == 'universe': state['targets'].pop()
    elif failure == 'quantity': state['targets'][0]['shares'] = -1
    else: state['targets'][0] = state['targets'][1]
    with pytest.raises(ValueError):
        project_strategy(dict(schema='guanheng.configured-cta-observation.v1', strategies={
            'resonance-regime-v1': report}))


def test_performance_failure_logs_code_location_without_private_values(strategy_publication, monkeypatch, caplog):
    import guanheng_app.live_strategy_performance as performance

    settings, _values, _files, _write = strategy_publication
    def fail(*args, **kwargs):
        raise ValueError('private-account-and-secret-response')
    monkeypatch.setattr(performance.LiveStrategyPerformanceOwner, 'read', fail)
    with TestClient(create_app(settings)) as client:
        response = client.get('/v1/ui/live-strategy-performance', params=dict(
            strategy_id='resonance-regime-v1', strategy_version='1.1.2'))
    assert response.status_code == 503
    assert 'live_strategy_read_failed error_type=ValueError' in caplog.text
    assert 'test_current.py' in caplog.text and 'fail' in caplog.text
    assert 'private-account-and-secret-response' not in caplog.text + response.text
