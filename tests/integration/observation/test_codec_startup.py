"""Observation readiness owns required codec initialization, before request budgets."""
import sys

import pytest
from fastapi.testclient import TestClient

from guanheng_app.app import create_app
from guanheng_app.settings import ConsoleSettings
from guanheng_app.observation import query


def test_configured_observation_codec_ready_before_first_request(tmp_path):
    app = create_app(ConsoleSettings(observation_root=str(tmp_path)))
    with TestClient(app) as client:
        assert 'pyarrow.parquet' in sys.modules
        assert client.get('/v1/ui/market-observation/catalog').json()['code'] == 'catalog_unavailable'
    assert app.state.shutdown_complete and app.state.reader.live_threads == 0


@pytest.mark.parametrize('failure', [RuntimeError, ImportError, ValueError, TypeError])
def test_codec_failure_is_local_to_observation_and_closes_readers(tmp_path, monkeypatch, failure):
    def failed(_body):
        raise failure('codec unavailable')

    monkeypatch.setattr(query, 'read_parquet', failed)
    app = create_app(ConsoleSettings(observation_root=str(tmp_path)))
    with TestClient(app) as client:
        response = client.get('/v1/ui/market-observation/catalog')
        assert response.status_code == 503
        assert response.json()['code'] == 'observation_runtime_unavailable'
        failure_state = app.state.observation_error.copy()
        for _ in range(20):
            assert client.get('/v1/ui/market-observation/catalog').json() == response.json()
        assert app.state.observation_error == failure_state
        assert all(not isinstance(value, BaseException) for value in failure_state.values())
        assert client.get('/v1/ui/strategy-catalog').status_code == 200
        assert client.get('/v1/ui/account/overview').status_code == 200
        assert client.get('/v1/ui/strategy-runtime').status_code == 200
    assert app.state.shutdown_complete and app.state.reader.live_threads == 0


def test_unconfigured_app_stays_independent_of_observation_codec(monkeypatch):
    def failed(_body):
        pytest.fail('Unconfigured observation must not initialize its codec')

    monkeypatch.setattr(query, 'read_parquet', failed)
    with TestClient(create_app(ConsoleSettings())) as client:
        assert client.get('/v1/ui/market-observation/catalog').json()['code'] == 'not_configured'


@pytest.mark.parametrize('failure', [RuntimeError, ImportError, ValueError, TypeError])
def test_codec_failure_keeps_completed_report_readable(tmp_path, monkeypatch, failure):
    from pathlib import Path
    import importlib.util
    test_folder = Path(__file__).resolve().parents[3] / 'tests/integration/backtest_workspace'
    sys.path.insert(0, str(test_folder))
    spec = importlib.util.spec_from_file_location('codec_report_fixture', test_folder / 'test_archive.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    root, run, fact, config, report = module.example(tmp_path)
    receipt = module.publish(module.BacktestArchive(root), fact, config, report)
    def failed(_body):
        raise failure('synthetic missing codec')
    monkeypatch.setattr(query, 'read_parquet', failed)
    app = create_app(ConsoleSettings(observation_root=str(tmp_path / 'observation'), backtest_archive_root=str(root)))
    with TestClient(app) as client:
        assert client.get('/v1/ui/market-observation/catalog').status_code == 503
        index = client.get('/v1/ui/backtest/archive')
        assert index.status_code == 200 and len(index.json()['runs']) == 1
        detail = client.get('/v1/ui/backtest/archive/' + run.name, params={'receipt_sha256': receipt})
        assert detail.status_code == 200 and detail.json()['configuration'] == config
    assert app.state.shutdown_complete and app.state.reader.live_threads == 0
