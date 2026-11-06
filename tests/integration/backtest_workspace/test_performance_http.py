"""当前只读归档路由：实际读池、固定身份、失败恢复与资源关闭。"""
from pathlib import Path
from threading import current_thread, Event
from time import monotonic

from fastapi.testclient import TestClient
import pytest

from guanheng_app.app import create_app
from guanheng_app.settings import ConsoleSettings
from guanheng_app.backtest_archive import ArchiveError
from guanheng_app import backtest_readonly

LEFT, RIGHT, SHA = 'a'*32, 'b'*32, 'c'*64
SINGLE = f'/v1/ui/backtest/archive/{LEFT}/performance?receipt_sha256={SHA}'
PAIR = (f'/v1/ui/backtest/comparison?left_run_id={LEFT}&left_receipt_sha256={SHA}'
        f'&right_run_id={RIGHT}&right_receipt_sha256={SHA}')


class ObservingArchive:
    """只替换外部归档I/O；路由、读池及其生命周期采用产品实现。"""
    def __init__(self):
        self.calls = []
        self.error = None

    def read(self, run_id, receipt_sha, deadline, **selection):
        self.calls.append((current_thread().name, monotonic(), deadline,
                           dict(run_id=run_id, receipt_sha=receipt_sha, **selection)))
        if self.error is not None:
            raise self.error
        return {'read_only': True}

    def compare(self, left, left_sha, right, right_sha, deadline):
        self.calls.append((current_thread().name, monotonic(), deadline, (left, left_sha, right, right_sha)))
        if self.error is not None:
            raise self.error
        return {'read_only': True}


def application(tmp_path, monkeypatch, archive):
    def open_archive(root):
        assert Path(root) == tmp_path
        return archive
    monkeypatch.setattr(backtest_readonly, 'BacktestArchive', open_archive)
    return create_app(ConsoleSettings(backtest_archive_root=str(tmp_path)))


def test_new_routes_use_existing_reader_fixed_selection_and_no_cache(tmp_path, monkeypatch):
    archive = ObservingArchive()
    app = application(tmp_path, monkeypatch, archive)
    with TestClient(app) as client:
        for path in (SINGLE, PAIR):
            response = client.get(path)
            assert response.status_code == 200 and response.headers['cache-control'] == 'no-store'
        assert len(archive.calls) == 2
        assert all(name.startswith('guanheng-read-') and 0 < deadline-started <= backtest_readonly.REQUEST_SECONDS
                   for name, started, deadline, _ in archive.calls)
        assert archive.calls[0][-1] == dict(run_id=LEFT, receipt_sha=SHA, configuration=False,
            performance=True, index=None, offset=0, limit=50)
        assert archive.calls[1][-1] == (LEFT, SHA, RIGHT, SHA)
    assert app.state.shutdown_complete and app.state.backtest_reader.live_threads == 0


@pytest.mark.parametrize('path,body', [
    (SINGLE+'&extra=x', None), (SINGLE+'&receipt_sha256='+SHA, None), (SINGLE, b'{}'),
    (PAIR+'&path=x', None), (PAIR+'&left_run_id='+LEFT, None), (PAIR, b'{}'),
    (PAIR.replace('right_run_id='+RIGHT, 'right_run_id='+LEFT), None),
])
def test_invalid_read_does_not_enter_archive(tmp_path, monkeypatch, path, body):
    archive = ObservingArchive()
    with TestClient(application(tmp_path, monkeypatch, archive)) as client:
        assert client.request('GET', path, content=body).status_code == 422
        assert archive.calls == []


def test_invalid_run_id_uses_real_archive_admission_without_touching_files(tmp_path):
    app = create_app(ConsoleSettings(backtest_archive_root=str(tmp_path)))
    with TestClient(app) as client:
        assert client.get(SINGLE.replace(LEFT, 'invalid')).status_code == 422
        assert list(tmp_path.iterdir()) == []
    assert app.state.shutdown_complete


@pytest.mark.parametrize('error,status,detail', [
    (ArchiveError('归档身份已改变', 409), 409, '归档身份已改变'),
    (ArchiveError('原件尚不可读取', 503), 503, '原件尚不可读取'),
    (TimeoutError('private-path'), 503, '历史报告读取繁忙或超时，请重新读取'),
])
def test_read_error_and_same_selection_recovery(tmp_path, monkeypatch, error, status, detail):
    archive = ObservingArchive()
    app = application(tmp_path, monkeypatch, archive)
    with TestClient(app) as client:
        for path in (SINGLE, PAIR):
            archive.error = error
            response = client.get(path)
            assert response.status_code == status and response.json() == {'detail': detail}
            assert 'private-path' not in response.text
            archive.error = None
            recovered = client.get(path)
            assert recovered.status_code == 200 and recovered.json() == {'read_only': True}
        assert archive.calls[0][-1] == archive.calls[1][-1]
        assert archive.calls[2][-1] == archive.calls[3][-1]
    assert app.state.shutdown_complete and app.state.backtest_reader.live_threads == 0


def test_reader_full_returns_controlled_failure_and_recovers(tmp_path, monkeypatch):
    entered, release = Event(), Event()
    archive = ObservingArchive()
    app = application(tmp_path, monkeypatch, archive)
    def block(_remaining):
        entered.set()
        assert release.wait(3)
    with TestClient(app) as client:
        first = app.state.backtest_reader.submit(block, monotonic()+5)
        assert entered.wait(1)
        queued = [app.state.backtest_reader.submit(lambda _remaining: None, monotonic()+5)
                  for _ in range(app.state.backtest_reader._queue.maxsize)]
        try:
            response = client.get(SINGLE)
            assert response.status_code == 503 and archive.calls == []
        finally:
            release.set()
            first.result(timeout=2)
            for future in queued:
                future.result(timeout=2)
        assert client.get(SINGLE).status_code == 200
    assert app.state.shutdown_complete and app.state.backtest_reader.live_threads == 0


def test_missing_root_and_known_empty_archive_are_distinct(tmp_path):
    with TestClient(create_app(ConsoleSettings())) as client:
        assert client.get(SINGLE).status_code == client.get(PAIR).status_code == 503
        assert client.get('/v1/ui/backtest/archive').status_code == 503
    app = create_app(ConsoleSettings(backtest_archive_root=str(tmp_path)))
    with TestClient(app) as client:
        value = client.get('/v1/ui/backtest/archive')
        assert value.status_code == 200 and value.json()['runs'] == []
        assert client.get('/health').status_code == 200
    assert app.state.shutdown_complete


def test_actual_http_deadline_keeps_running_read_until_original_work_finishes(tmp_path, monkeypatch):
    monkeypatch.setattr(backtest_readonly, 'REQUEST_SECONDS', .1)
    entered, release, finished = Event(), Event(), Event()
    class SlowArchive(ObservingArchive):
        def read(self, *args, **kwargs):
            result = super().read(*args, **kwargs)
            entered.set()
            assert release.wait(8)
            finished.set()
            return result
    archive = SlowArchive()
    app = application(tmp_path, monkeypatch, archive)
    with TestClient(app) as client:
        started = monotonic()
        try:
            response = client.get(SINGLE)
            assert response.status_code == 503
            assert .05 <= monotonic()-started < 2
            assert entered.is_set() and not finished.is_set() and len(archive.calls) == 1
            assert archive.calls[0][1] < archive.calls[0][2] <= archive.calls[0][1]+backtest_readonly.REQUEST_SECONDS
        finally:
            release.set()
        assert finished.wait(2)
        assert client.get(SINGLE).status_code == 200
    assert app.state.shutdown_complete and app.state.backtest_reader.live_threads == 0
