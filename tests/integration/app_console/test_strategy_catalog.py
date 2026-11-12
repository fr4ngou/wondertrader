"""覆盖未启用、WT不可读及同身份发布的目录合并。"""
import json

from fastapi.testclient import TestClient

from guanheng_app.app import create_app
from guanheng_app.settings import ConsoleSettings
from guanheng_app import wt_business_observation


def test_registered_strategy_remains_visible_and_merges_with_runtime(monkeypatch):
    original = dict(strategy_id='resonance-original-wt-351f9d5-stable',
        strategy_version='0.2.0a1', display_name='共振原版')
    other = dict(strategy_id='new-strategy', strategy_version='1.0.0', display_name='另一策略')
    monkeypatch.setenv('GUANHENG_STRATEGY_REGISTRATIONS', json.dumps([original, other]))
    published = [dict(strategy_id='resonance-regime-v1', strategy_version='1.2.2', status_label='等待策略所需行情')]

    def observe(*_args, include_activity=False):
        assert include_activity
        if published is None:
            raise RuntimeError('当前WT发布不可读')
        return dict(strategy=None, strategies=published, running=published[:1])

    monkeypatch.setattr(wt_business_observation, 'observe_strategy', observe)
    settings = ConsoleSettings.from_environment()
    with TestClient(create_app(settings)) as client:
        def strategies():
            response = client.get('/v1/ui/strategy-catalog')
            assert response.status_code == 200
            return response.json()['strategies']

        entries = strategies()
        assert entries[0]['strategy_id'] == 'resonance-regime-v1'
        assert entries[1]['display_name'] == original['display_name']
        assert entries[1]['strategy_version'] == '0.2.0a1'
        assert entries[1]['catalog_status'] == entries[2]['catalog_status'] == 'registered'
        assert entries[3]['strategy_version'] == '0.1.0a2'
        assert entries[3]['display_name'] == entries[1]['display_name']
        running = client.get('/v1/ui/strategy-catalog').json()['running']
        assert len(running) == 1
        assert running[0]['strategy_id'] == entries[0]['strategy_id']
        assert running[0]['status_label'] == '等待策略所需行情'

        published.append(original)
        entries = strategies()
        matching = [row for row in entries if row['strategy_id'] == original['strategy_id']
            and row['strategy_version'] == original['strategy_version']]
        assert len(matching) == 1 and 'catalog_status' not in matching[0]
        assert matching[0]['display_name'] == original['display_name']

        published = None
        entries = strategies()
        assert [row['strategy_id'] for row in entries if row.get('catalog_status') == 'registered'] == [
            original['strategy_id'], other['strategy_id']]
        assert client.get('/v1/ui/strategy-catalog').json()['running'] is None
