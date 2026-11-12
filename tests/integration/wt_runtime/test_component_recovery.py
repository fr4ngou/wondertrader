"""运行期只读组件换代使用原 Runtime 健康核查入口。"""
from threading import Event, Lock
from time import monotonic
from types import SimpleNamespace
from uuid import uuid4

import pytest

from guanheng_wt_runtime.analysis_window_process import AnalysisWindowProcess
from guanheng_wt_runtime.managed_local_process import ManagedLocalProcess
from guanheng_wt_runtime.thread_owner import ThreadOwner
from guanheng_wt_runtime.runtime import ComponentConfig, Runtime, RuntimeConfig


class Owner:
    startup_seconds = 5
    shutdown_seconds = 3

    def __init__(self, pid):
        self.pid = pid
        self.ready = self.pending = False
        self.error = None
        self.starts = 0

    def start(self, deadline):
        self.starts += 1
        self.ready = self.error is None
        return self.ready

    def status(self):
        return dict(ready=self.ready, pending=self.pending, error_code=self.error, pid=self.pid)

    def exit(self, pending=False):
        self.ready = False
        self.error = 'unexpected_exit'
        self.pending = pending

    def request_close(self):
        self.ready = False

    def close(self, timeout):
        return not self.pending


@pytest.fixture
def active_runtime(tmp_path):
    configs = tuple((name, ComponentConfig(kind, str(tmp_path / name), '0' * 64))
                    for name, kind in [('trade_host', 'qmt_trade'), ('account_host', 'qmt_read'),
                                       ('account_observation', 'native_account_observation'),
                                       ('execution', 'execution')])
    owners = {cfg.kind: [] for _, cfg in configs}

    def factory(cfg):
        assert cfg in dict(configs).values()
        owner = Owner(1000 + sum(map(len, owners.values())))
        owners[cfg.kind].append(owner)
        return owner

    runtime = Runtime(RuntimeConfig(str(uuid4()), configs, 10, 10), factory=factory, clock=lambda: 10.0)
    assert runtime.start(20)
    return runtime, owners


def complete_recovery(runtime, index=1):
    assert runtime.check()
    assert runtime._recoveries[index][0].join_until(monotonic() + 5)
    return runtime.check()


def test_account_host_restarts_only_after_reap_and_keeps_trade_components(active_runtime, tmp_path):
    runtime, owners = active_runtime
    initial = runtime.status()
    old = owners['qmt_read'][0]
    host = ManagedLocalProcess(SimpleNamespace(control_root=tmp_path, stop_seconds=3, startup_seconds=5))
    finished = Event()
    host._monitor = ThreadOwner(target=finished.set, daemon=True, name='test-account-host-monitor')
    host._monitor.start()
    assert finished.wait(3)
    host._state, host._error, host._host_pid = 'faulted', 'unexpected_exit', old.pid
    runtime._owners[1] = ('account_host', host)
    assert host.status()['pending']
    assert complete_recovery(runtime)
    assert runtime.check()
    current = runtime.status()
    assert current['ready']
    assert current['instance_id'] == initial['instance_id']
    assert current['components']['account_host']['pid'] != old.pid
    assert not host.status()['pending']
    assert [item.starts for item in owners['qmt_read']] == [1, 1]
    for name in ('trade_host', 'account_observation', 'execution'):
        assert current['components'][name] == initial['components'][name]
    assert runtime.close(5)
    assert not owners['qmt_read'][-1].ready


def test_stop_prevents_a_new_account_host(active_runtime):
    runtime, owners = active_runtime
    owners['qmt_read'][0].exit()
    runtime.request_close()
    assert runtime.check()
    assert len(owners['qmt_read']) == 1
    assert runtime.close(5)


def test_unconfirmed_reap_preserves_original_owner(active_runtime):
    runtime, owners = active_runtime
    host = owners['qmt_read'][0]
    host.exit(pending=True)
    assert not complete_recovery(runtime)
    assert runtime.status()['error_code'] == 'component_runtime_account_host'
    assert len(owners['qmt_read']) == 1


def test_trade_host_fault_uses_original_stop_path(active_runtime):
    runtime, owners = active_runtime
    owners['qmt_trade'][0].exit()
    assert not runtime.check()
    assert runtime.status()['error_code'] == 'component_runtime_trade_host'
    assert len(owners['qmt_trade']) == 1

def test_stop_during_old_host_cleanup_prevents_replacement(active_runtime, monkeypatch):
    runtime, owners = active_runtime
    host = owners['qmt_read'][0]
    host.exit()
    original_close = host.close

    def stop_while_closing(timeout):
        runtime.request_close()
        return original_close(timeout)

    monkeypatch.setattr(host, 'close', stop_while_closing)
    assert runtime.check()
    assert runtime._recoveries[1][0].join_until(monotonic() + 5)
    assert len(owners['qmt_read']) == 1
    assert runtime.close(5)


def test_failed_replacement_preserves_original_fault_shutdown(active_runtime, monkeypatch):
    runtime, owners = active_runtime
    owners['qmt_read'][0].exit()
    successor = Owner(2000)
    successor.error = 'startup_timeout'
    monkeypatch.setattr(runtime, '_factory', lambda _: successor)
    assert not complete_recovery(runtime)
    assert successor.starts == 1
    assert runtime.status()['error_code'] == 'component_runtime_account_host'
    assert runtime.close(5)


def test_active_restart_does_not_block_stop(active_runtime, monkeypatch):
    runtime, owners = active_runtime
    runtime._clock = monotonic
    owners['qmt_read'][0].exit()
    successor = Owner(2000)
    entered, stop = Event(), Event()

    def wait_for_stop(deadline):
        entered.set()
        stop.wait(max(0, deadline - monotonic()))
        return False

    monkeypatch.setattr(successor, 'start', wait_for_stop)
    monkeypatch.setattr(successor, 'request_close', stop.set)
    monkeypatch.setattr(runtime, '_factory', lambda _: successor)
    assert runtime.check()
    assert entered.wait(3)
    assert runtime.check()
    assert not stop.is_set()
    assert runtime.close(2)
    assert stop.is_set()
    assert not runtime._recoveries[1][0].pending

@pytest.mark.parametrize(('components', 'name', 'error'), [
    ((('host', 'qmt_read'),), 'host', 'unexpected_exit'),
    ((('host', 'qmt_history_preparation'),), 'host', 'unexpected_exit'),
    ((('analysis_host', 'qmt_read'),), 'analysis_host', 'unexpected_exit'),
    ((('analysis_batch_host', 'qmt_read'),), 'analysis_batch_host', 'unexpected_exit'),
    ((('account_host', 'qmt_read'), ('account_observation', 'native_account_observation')),
     'account_observation', 'observation_runtime'),
    ((('analysis_host', 'qmt_read'), ('analysis_window', 'analysis_window')),
     'analysis_window', 'analysis_window_failed'),
    ((('history', 'source_market'),), 'history', 'unexpected_exit'),
    ((('collection', 'quote_collection'),), 'collection', 'unexpected_exit'),
])
def test_read_only_component_restarts_with_same_config(tmp_path, components, name, error):
    configs = tuple((role, ComponentConfig(kind, str(tmp_path / role), '0' * 64))
                    for role, kind in components)
    owners = {}

    def factory(config):
        instances = owners.setdefault(config, [])
        instance = Owner(1000 + sum(map(len, owners.values())))
        instances.append(instance)
        return instance

    runtime = Runtime(RuntimeConfig(str(uuid4()), configs, 10, 10), factory=factory)
    assert runtime.start(monotonic() + 10)
    initial = runtime.status()
    index = [role for role, _ in configs].index(name)
    config = configs[index][1]
    owners[config][0].exit()
    owners[config][0].error = error
    assert complete_recovery(runtime, index)
    recovered = runtime.status()
    assert recovered['instance_id'] == initial['instance_id']
    assert len(owners[config]) == 2
    assert all(len(instances) == (2 if item == config else 1)
               for item, instances in owners.items())
    assert recovered['components'][name]['pid'] == owners[config][-1].pid
    assert runtime.close(5)


def test_publication_requires_positive_close_before_restart(active_runtime, monkeypatch):
    runtime, owners = active_runtime
    publication = owners['native_account_observation'][0]
    publication.exit()
    publication.error = 'observation_runtime'
    monkeypatch.setattr(publication, 'close', lambda _: False)
    assert not complete_recovery(runtime, 2)
    assert runtime.status()['error_code'] == 'component_runtime_account_observation'
    assert len(owners['native_account_observation']) == 1


def test_execution_failure_does_not_use_read_only_restart(active_runtime):
    runtime, owners = active_runtime
    owners['execution'][0].exit()
    assert not runtime.check()
    assert runtime.status()['error_code'] == 'component_runtime_execution'
    assert len(owners['execution']) == 1

def test_analysis_publisher_starting_allows_status_and_stop():
    entered, release, cancelled = Event(), Event(), Event()
    producer_lock = Lock()

    class Producer:
        def start(self, *, deadline):
            with producer_lock:
                entered.set()
                release.wait(max(0, deadline - monotonic()))

        def status(self):
            with producer_lock:
                return dict(phase='waiting_source', last_success=None, published_count=0, error=None)

        def request_close(self, *, deadline):
            with producer_lock:
                cancelled.set()

    process = AnalysisWindowProcess(Producer(), 3)
    task = ThreadOwner(target=process.start, args=(monotonic() + 5,), daemon=True)
    task.start()
    try:
        assert entered.wait(3)
        assert process.status()['state'] == 'starting'
        process.request_close()
        assert not cancelled.is_set()
        assert process.status()['state'] == 'stopping'
    finally:
        release.set()
        assert task.join_until(monotonic() + 5)
    assert cancelled.is_set()


def test_two_read_only_recoveries_are_independent(tmp_path):
    components = (
        ('analysis_host', ComponentConfig('qmt_read', str(tmp_path / 'source'), '0' * 64)),
        ('history', ComponentConfig('source_market', str(tmp_path / 'history'), '1' * 64)),
    )
    created, entered, release = {}, Event(), Event()

    class WaitingHost(Owner):
        def start(self, deadline):
            entered.set()
            return release.wait(max(0, deadline - monotonic())) and super().start(deadline)

    def factory(component):
        row = created.setdefault(component.kind, [])
        owner_type = WaitingHost if row and component.kind == 'qmt_read' else Owner
        owner = owner_type(2000 + sum(map(len, created.values())))
        row.append(owner)
        return owner

    runtime = Runtime(RuntimeConfig(str(uuid4()), components, 5, 5), factory=factory)
    assert runtime.start(monotonic() + 5)
    for owners in created.values():
        owners[0].exit()
    try:
        assert runtime.check()
        assert entered.wait(3)
        assert runtime._recoveries[1][0].join_until(monotonic() + 3)
        assert runtime.check()
        assert set(runtime._recoveries) == {0}
        assert [len(owners) for owners in created.values()] == [2, 2]
    finally:
        release.set()
        assert runtime.close(5)
