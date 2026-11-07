"""线上观察复用真实App读池与生命周期；只用本地owner替身，不读取账户。"""
from contextlib import closing
import importlib
import sqlite3
import threading
from time import monotonic
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from guanheng_app.contracts.watchlist import WatchlistSnapshot, encode_snapshot
from guanheng_app.settings import ConsoleSettings

app_module = importlib.import_module('guanheng_app.app')


class Preference:
    def __init__(self, _root): pass
    def start(self, deadline): return None
    def close(self, timeout): return True


@pytest.mark.parametrize('shared', [False, True])
def test_history_storage_keeps_existing_watchlist_readable(monkeypatch, tmp_path, shared):
    preference = tmp_path / 'watchlist'
    preference.mkdir()
    history = preference if shared else tmp_path / 'strategy-observations'
    history.mkdir(exist_ok=True)
    saved = WatchlistSnapshot(str(uuid4()), 5, ('510300.SH',), '2026-11-04T07:00:00Z')
    original = encode_snapshot(saved)
    (preference / 'watchlist.json').write_bytes(original)
    (preference / '.watchlist.lock').write_bytes(bytes((0,)))
    monkeypatch.setenv('GUANHENG_WATCHLIST_ROOT', str(preference))
    monkeypatch.setenv('GUANHENG_LIVE_STRATEGY_HISTORY_ROOT', str(history))
    loaded = ConsoleSettings.from_environment()
    app = app_module.create_app(ConsoleSettings(watchlist_root=loaded.watchlist_root,
        live_strategy_history_root=loaded.live_strategy_history_root,
        wt_current_file=str(tmp_path / 'synthetic-current.json')), static_directory=tmp_path / 'absent')

    for _ in range(2):
        with TestClient(app) as client:
            assert client.get('/v1/ui/capabilities').json()['features']['personal_watchlist']['editable']
            result = client.get('/v1/ui/watchlists/default')
            assert result.status_code == 200
            assert result.json()['watchlist_id'] == saved.watchlist_id
            assert result.json()['version'] == saved.version
            assert result.json()['symbols'] == list(saved.symbols)
        assert app.state.shutdown_complete

    assert (preference / 'watchlist.json').read_bytes() == original
    assert {item.name for item in preference.iterdir()} == {'watchlist.json', '.watchlist.lock'}
    database = history / 'live-strategy-observations.sqlite3'
    if shared:
        assert app.state.live_observation_error == 'ValueError'
        assert not database.exists()
    else:
        assert app.state.live_observation_error is None
        with closing(sqlite3.connect(database)) as connection:
            assert connection.execute('pragma quick_check').fetchone() == ('ok',)
            assert connection.execute("select name from sqlite_master where type='table' order by name").fetchall() == [
                ('deals',), ('observations',)]


def test_background_capture_runs_without_browser_and_is_reaped_before_owner_close(monkeypatch, tmp_path):
    captured = threading.Event()
    observations = []

    class Owner:
        def __init__(self, _settings, **_kwargs): self.closed = False
        def initialize(self, deadline):
            assert monotonic() < deadline
            observations.append(('initialize', threading.current_thread().name))
        def capture_current(self, deadline):
            assert monotonic() < deadline
            observations.append(('capture', threading.current_thread().name));captured.set()
        def close(self):
            self.closed = True
            assert not any(t.name.startswith('guanheng-read-') for t in threading.enumerate())
            observations.append(('close', threading.current_thread().name))

    monkeypatch.setattr(app_module, 'LiveStrategyPerformanceOwner', Owner)
    monkeypatch.setattr(app_module, 'LIVE_OBSERVATION_SECONDS', .01)
    app = app_module.create_app(ConsoleSettings(live_strategy_history_root=str(tmp_path), wt_current_file=str(tmp_path/'synthetic-current.json')),
                              watchlist_owner_factory=Preference, static_directory=tmp_path/'absent')
    with TestClient(app):
        assert captured.wait(2), '后台观察不应依赖打开策略页面'
        task = app.state.live_observation_task
    assert task.done() and app.state.shutdown_complete
    assert app.state.live_strategy_performance.closed
    assert all(name.startswith('guanheng-read-') for action,name in observations if action in ('capture','initialize'))
    assert observations[-1][0] == 'close'


def test_optional_capture_failure_preserves_web_and_next_observation(monkeypatch, tmp_path):
    captured = threading.Event()

    class Owner:
        def __init__(self, _settings, **_kwargs): self.calls = 0
        def initialize(self, deadline): raise OSError('synthetic local observation failure')
        def capture_current(self, deadline): self.calls += 1;captured.set()
        def close(self): pass

    monkeypatch.setattr(app_module, 'LiveStrategyPerformanceOwner', Owner)
    monkeypatch.setattr(app_module, 'LIVE_OBSERVATION_SECONDS', .01)
    app = app_module.create_app(ConsoleSettings(live_strategy_history_root=str(tmp_path), wt_current_file=str(tmp_path/'synthetic-current.json')),
                              watchlist_owner_factory=Preference, static_directory=tmp_path/'absent')
    with TestClient(app) as client:
        assert client.get('/health').status_code == 200
        assert captured.wait(2)
    assert app.state.shutdown_complete and app.state.live_strategy_performance.calls >= 1
