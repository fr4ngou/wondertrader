from datetime import datetime, timedelta, timezone
from time import monotonic

from guanheng_app.settings import ConsoleSettings
from guanheng_app.strategy_position_quotes import project_latest_position_values
from guanheng_market_client import API_VERSION, MarketUnavailable


def test_last_quote_after_restart_prices_only_owned_positions_and_preserves_clock():
    strategy = dict(owned_valuation=dict(state='unavailable'), positions=[
        dict(symbol='159780.SZ', broker_quantity=213100),
        dict(symbol='510500.SH', broker_quantity=0),
    ])
    calls = []
    def factory(url, token, *, timeout):
        calls.append((url, token, timeout))
        class Client:
            def quotes_query(self, symbols):
                assert symbols == ['SZSE.159780']
                return dict(api_version=API_VERSION, status=dict(code='Ok', reason=''), data=dict(
                    metadata=dict(qualification='NativeVerified', profile_version='qa', source_license='qa',
                        timezone='Asia/Shanghai', price_unit='CNY', volume_unit='share',
                        amount_unit='CNY', volume_to_shares=1, amount_to_yuan=1),
                    snapshots=[dict(source=dict(provider='Qmt', instance_id='test', session_id='test', generation=1),
                        symbol='SZSE.159780', date=20261113, action_time=163000000, price=.744,
                        open=.743, high=.745, low=.741, pre_close=.742, total_volume=100,
                        total_turnover=74.4, full_cumulative=True, source_time_verified=True)]))
        return Client()
    # Use a past fixed date so the fixture runs independently of the market calendar.
    from unittest.mock import patch
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return (datetime(2026, 11, 14, tzinfo=timezone.utc) + timedelta(hours=2)).astimezone(tz)
    settings = ConsoleSettings(position_quote_url='http://127.0.0.1:18150', position_quote_token='test')
    with patch('guanheng_app.strategy_position_quotes.datetime', Clock):
        project_latest_position_values(strategy, settings, monotonic() + 2, factory)
    assert len(calls) == 1
    assert strategy['positions'][0] == dict(symbol='159780.SZ', broker_quantity=213100,
        market_value_cny='158546.40', market_value_observed_at='2026-11-13T16:30:00+08:00',
        market_value_basis='last-quote')
    assert 'market_value_cny' not in strategy['positions'][1]
    assert strategy['owned_valuation'] == dict(state='unavailable')

    def unavailable(*_args, **_kwargs):
        raise MarketUnavailable('quote service unavailable')
    project_latest_position_values(strategy, settings, monotonic() + 2, unavailable)
    assert strategy['positions'][0]['market_value_cny'] == '158546.40'
