"""慢来源与页面分责、最近值恢复和有界worker的生命周期回归。"""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from threading import Event
from time import monotonic
from fastapi.testclient import TestClient
from guanheng_app.settings import ConsoleSettings
from guanheng_app.strategy_position_quotes import PositionQuoteOwner,project_latest_position_values
from guanheng_market_client import API_VERSION,MAX_SYMBOLS,MarketUnavailable


def reply(symbols, *, date=20261113, clock=163000000):
    return dict(api_version=API_VERSION,status=dict(code='Ok',reason=''),data=dict(
        metadata=dict(qualification='NativeVerified',profile_version='qa',source_license='qa',
            timezone='Asia/Shanghai',price_unit='CNY',volume_unit='share',amount_unit='CNY',
            volume_to_shares=1,amount_to_yuan=1),
        snapshots=[dict(source=dict(provider='Qmt',instance_id='test',session_id='test',generation=1),
            symbol=s,date=date,action_time=clock,price=.744,open=.743,high=.745,low=.741,
            pre_close=.742,total_volume=100,total_turnover=74.4,full_cumulative=True,source_time_verified=True) for s in symbols]))


def settings():
    return ConsoleSettings(position_quote_url='http://127.0.0.1:18150',position_quote_token='synthetic',
                           wondertrader_market_timeout_seconds=5)


def strategy(symbol='159780.SZ',quantity=213100):
    return dict(owned_valuation=dict(state='unavailable'),positions=[dict(symbol=symbol,broker_quantity=quantity)])


def test_last_quote_after_restart_prices_only_owned_positions_and_preserves_clock():
    calls=[]
    def factory(url,token,*,timeout):
        class Client:
            def quotes_query(self,symbols):calls.append(symbols);return reply(symbols)
        return Client()
    owner=PositionQuoteOwner(settings(),factory);owner.start()
    value=strategy();value['positions'].append(dict(symbol='510500.SH',broker_quantity=0))
    try:
        project_latest_position_values(value,owner);owner.future.result(2)
        project_latest_position_values(value,owner)
        assert value['positions'][0]==dict(symbol='159780.SZ',broker_quantity=213100,
            market_value_cny='158546.40',market_value_observed_at='2026-11-13T16:30:00+08:00',market_value_basis='last-quote')
        assert 'market_value_cny' not in value['positions'][1]
        assert value['owned_valuation']==dict(state='unavailable') and all(x==['SZSE.159780'] for x in calls)
        owner.future.result(2)
        def unavailable(*a,**kw):raise MarketUnavailable('synthetic source unavailable')
        owner.factory=unavailable
        project_latest_position_values(value,owner);owner.future.result(2)
        project_latest_position_values(value,owner)
        assert value['positions'][0]['market_value_cny']=='158546.40'
        assert value['positions'][0]['market_value_observed_at']=='2026-11-13T16:30:00+08:00'
    finally:assert owner.close(2)
    assert owner.live_threads==0


def test_slow_quote_http_returns_core_before_source_then_refreshes_price(monkeypatch):
    from guanheng_app.app import create_app
    from guanheng_app import observer_strategy_details as details
    started,release=Event(),Event()
    def factory(url,token,*,timeout):
        class Client:
            def quotes_query(self,symbols):
                started.set();assert release.wait(timeout)
                return reply(symbols)
        return Client()
    original=strategy('510050.SH',10000)
    original['positions'][0].update(market_value_cny='28750.00',market_value_observed_at='2026-11-13T15:00:00+08:00',market_value_basis='last-quote')
    def observe(settings,configuration,deadline,sid,securities,client_factory,quote_owner):
        value=deepcopy(original);project_latest_position_values(value,quote_owner)
        return dict(strategy_id=sid,calculation=value)
    monkeypatch.setattr(details,'observe_details',observe)
    app=create_app(settings(),market_client_factory=factory)
    try:
        with TestClient(app) as client:
            response=client.get('/v1/ui/strategy-details?strategy_id=synthetic-alpha')
            assert response.status_code==200 and response.json()['calculation']==original
            assert started.wait(1) and not release.is_set()  # 主HTTP完成时来源仍明确在途。
            release.set();app.state.position_quotes.future.result(2)
            second=client.get('/v1/ui/strategy-details?strategy_id=synthetic-beta')
            assert second.status_code==200 and second.json()['strategy_id']=='synthetic-beta'
            row=second.json()['calculation']['positions'][0]
            assert row['market_value_cny']=='7440.00' and row['market_value_observed_at']=='2026-11-13T16:30:00+08:00'
    finally:release.set()
    assert app.state.shutdown_complete and app.state.position_quotes.live_threads==0


def test_concurrent_refresh_is_single_flight_and_cache_pending_are_bounded():
    started,release=Event(),Event();calls=[]
    def factory(url,token,*,timeout):
        class Client:
            def quotes_query(self,symbols):
                calls.append(symbols);started.set();assert release.wait(timeout);return reply(symbols)
        return Client()
    owner=PositionQuoteOwner(settings(),factory);owner.start()
    try:
        owner.project(strategy('510000.SH',100));assert started.wait(1)
        for n in range(MAX_SYMBOLS+10):owner.project(strategy(str(510001+n)+'.SH',100))
        assert len(calls)==1 and len(owner.pending)<=MAX_SYMBOLS
        release.set();owner.future.result(2)
        owner.project(strategy('510075.SH',200));owner.future.result(2)
        assert len(owner.cache)<=MAX_SYMBOLS and all(len(x)<=MAX_SYMBOLS for x in calls)
        latest=strategy('510075.SH',200);owner.project(latest)
        assert latest['positions'][0]['market_value_cny']=='148.80'  # 淘汰只影响缓存，后继请求仍可刷新。
    finally:release.set();assert owner.close(2)


def test_future_clock_does_not_poison_last_quote_or_block_later_valid_quote():
    dates=[20261113]
    def factory(url,token,*,timeout):
        class Client:
            def quotes_query(self,symbols):return reply(symbols,date=dates[0])
        return Client()
    owner=PositionQuoteOwner(settings(),factory);owner.start()
    try:
        owner.project(strategy());owner.future.result(2)
        original=deepcopy(owner.cache)
        dates[0]=int((datetime.now(timezone.utc)+timedelta(days=5)).strftime('%Y%m%d'))
        owner.project(strategy());owner.future.result(2)
        assert owner.cache==original
        dates[0]=20261114
        owner.project(strategy());owner.future.result(2)
        value=strategy();owner.project(value)
        assert value['positions'][0]['market_value_observed_at']=='2026-11-14T16:30:00+08:00'
    finally:assert owner.close(2)


def test_close_retains_inflight_owner_until_source_returns():
    started,release=Event(),Event()
    def factory(url,token,*,timeout):
        class Client:
            def quotes_query(self,symbols):started.set();assert release.wait(timeout);return reply(symbols)
        return Client()
    owner=PositionQuoteOwner(settings(),factory);owner.start()
    try:
        owner.project(strategy());assert started.wait(1)
        assert not owner.close(0) and owner.live_threads==1
        owner.project(strategy('510050.SH',100))
        assert not owner.pending
        release.set();assert owner.close(2) and owner.live_threads==0
        assert not owner.cache  # 关闭期间晚回报价不再发布，原在途责任正常回收。
    finally:release.set();owner.close(2)


def test_extreme_finite_price_keeps_core_http_and_other_security_value(monkeypatch,caplog):
    """协议允许的极大有限价会使Decimal量化失败，不能令详情从200变500。"""
    from guanheng_app.app import create_app
    from guanheng_app import observer_strategy_details as details
    bad='SSE.510050'
    def factory(url,token,*,timeout):
        class Client:
            def quotes_query(self,symbols):
                value=reply(symbols)
                for q in value['data']['snapshots']:
                    if q['symbol']==bad:
                        q.update(price=1e308,open=1e308,high=1e308,low=1e308,pre_close=1e308,total_turnover=1e308)
                return value
        return Client()
    original=strategy('510050.SH',100)
    original['positions'][0].update(market_value_cny='287.50',market_value_observed_at='2026-11-13T15:00:00+08:00',market_value_basis='last-quote')
    original['positions'].append(dict(symbol='159780.SZ',broker_quantity=200))
    def observe(settings,configuration,deadline,sid,securities,client_factory,quote_owner):
        value=deepcopy(original);project_latest_position_values(value,quote_owner)
        return dict(calculation=value)
    monkeypatch.setattr(details,'observe_details',observe)
    app=create_app(settings(),market_client_factory=factory)
    with TestClient(app,raise_server_exceptions=False) as client:
        assert client.get('/v1/ui/strategy-details').status_code==200
        app.state.position_quotes.future.result(2)
        for _ in range(2):
            response=client.get('/v1/ui/strategy-details');assert response.status_code==200
            rows=response.json()['calculation']['positions']
            assert rows[0]==original['positions'][0] and rows[1]['market_value_cny']=='148.80'
        assert len([r for r in caplog.records if 'position_quote_projection_unavailable' in r.message])==1
    assert app.state.shutdown_complete
