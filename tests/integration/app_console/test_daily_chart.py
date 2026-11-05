"""来源日线App投影；SDK替身只证明合同，固定真实来源与安装SPA由组合另验。"""

from copy import deepcopy
from datetime import datetime, timezone
import time

from fastapi.testclient import TestClient
import pytest

from guanheng_app.app import create_app
from guanheng_app.contracts.market import MarketChartBundle
from guanheng_app.native_chart import build_native_chart
from guanheng_app.settings import ConsoleSettings


NOW = datetime(2026, 10, 28, 2, tzinfo=timezone.utc)
BEFORE = datetime(2026, 10, 23, 7, tzinfo=timezone.utc)


def settings(**changes):
    return ConsoleSettings(wondertrader_market_url="http://invalid.example", wondertrader_market_token="isolated-secret",
        wondertrader_market_timeout_seconds=.5, wondertrader_history_semantics="source", **changes)


def daily_response(request, *, empty=False):
    return {"status": {"code": "Ok"}, "data": {
        "metadata": {"source": {"provider": "Qmt", "instance_id": "isolated-instance", "session_id": "isolated-session", "generation": 1},
            "dataset_version": "isolated-daily-v1", "content_id": "a" * 64, "qualification": "DevelopmentVerified",
            "source_license": "unknown", "period": "1d", "adjustment": "none", "factor_version": "", "minute_boundary": "unknown",
            "timezone": "Asia/Shanghai", "value_semantics": "source", "timestamp_semantics": "source_date",
            "price_unit": "unknown", "volume_unit": "unknown", "amount_unit": "unknown"},
        "selection": {"period": "1d", "limit": request["limit"]}, "coverage": "Unknown", "missing_dates": [],
        "bars": [] if empty else [{"symbol": request["exchange"] + "." + request["code"], "date": date,
            "open": 10.1, "high": 10.5, "low": 9.9, "close": 10.3, "volume": 12.5, "amount": 12360.5}
            for date in (20261022, 20261023)],
    }}


class DailyFactory:
    def __init__(self, behavior=None):
        self.calls = []
        self.behavior = behavior

    def __call__(self, _url, _token, **options):
        owner = self

        class Client:
            def source_daily_history_query(self, request):
                owner.calls.append((dict(request), options))
                return owner.behavior(request) if owner.behavior else daily_response(request)

        return Client()


def chart(factory=None, **changes):
    return build_native_chart(symbol="510300.SH", period="1d", limit=2, before=BEFORE, settings=settings(), now=NOW,
        client_factory=factory or DailyFactory(), **changes)


def test_main_daily_single_sdk_preserves_source_date_and_units():
    factory = DailyFactory()
    value = chart(factory, timeout_seconds=.125)
    assert value.data_available and value.schema_version == "1.6" and value.period == value.source_period == "1d"
    assert value.source_bar_count == 2 and not value.derived
    assert value.as_of.isoformat() == "2026-10-22T16:00:00+00:00"
    assert value.candles[-1].model_dump() == {"occurred_at": value.as_of, "open": 10.1, "high": 10.5, "low": 9.9, "close": 10.3, "volume": 12.5}
    source = value.native_source
    assert source.timestamp_semantics == source.chart_minute_boundary == "source_date"
    assert source.source_minute_boundary == "unknown" and source.coverage == "Unknown"
    assert source.price_unit == source.volume_unit == source.amount_unit == "unknown"
    assert factory.calls == [({"exchange": "SSE", "code": "510300", "from": 20040101, "to": 20261023, "limit": 2, "view":"current"}, {"timeout": .125})]
    assert MarketChartBundle.model_validate_json(value.model_dump_json()) == value


@pytest.mark.parametrize('provider', ['Qmt', 'Tdx', 'BaoStock', 'Tencent', 'CSI', 'CNI'])
def test_sdk017_daily_provider_roundtrip(provider):
    """公开CNI与旧提供者沿同一日线投影，日期和单位保持原声明。"""
    def behavior(request):
        value = daily_response(request)
        value['data']['metadata']['source']['provider'] = provider
        return value
    value = chart(DailyFactory(behavior))
    assert value.data_available
    assert value.native_source.provider == provider
    assert value.native_source.volume_unit == 'unknown'
    assert MarketChartBundle.model_validate_json(value.model_dump_json()) == value


def test_bse_daily_routes_to_original_exchange_without_shenzhen_substitution():
    factory = DailyFactory()
    value = build_native_chart(symbol='920002.bj', period='1d', limit=2, before=BEFORE,
        settings=settings(), now=NOW, client_factory=factory)
    assert value.data_available and value.symbol == '920002.BJ'
    assert factory.calls[0][0]['exchange'] == 'BSE'
    assert MarketChartBundle.model_validate_json(value.model_dump_json()) == value
    unsupported = build_native_chart(symbol='920002.BJ', period='1m', limit=2, before=BEFORE,
        settings=settings(), now=NOW, client_factory=factory)
    assert not unsupported.data_available and len(factory.calls) == 1


def test_sdk017_cni_response_reaches_real_app_http(monkeypatch):
    import guanheng_app.native_chart as projection
    monkeypatch.setattr(projection, 'utc_now', lambda: NOW)
    def behavior(request):
        value = daily_response(request)
        value['data']['metadata']['source']['provider'] = 'CNI'
        return value
    app = create_app(settings(), DailyFactory(behavior))
    with TestClient(app) as client:
        value = client.get('/v1/ui/market/chart/399303.SZ', params={'period':'1d','limit':2}).json()
        assert value['data_available'] and value['native_source']['provider'] == 'CNI'
    assert app.state.shutdown_complete


def test_bse_daily_benchmark_uses_same_symbol_boundary(monkeypatch):
    import guanheng_app.native_chart as projection
    monkeypatch.setattr(projection, 'utc_now', lambda: NOW)
    app = create_app(settings(), DailyFactory())
    with TestClient(app) as client:
        response = client.get('/v1/ui/market/chart/510300.SH',
            params={'period':'1d','limit':2,'benchmark_symbol':'920002.BJ'})
        assert response.status_code == 200
        assert response.json()['benchmark']['symbol'] == '920002.BJ'
        assert response.json()['benchmark']['data_available']


def test_main_daily_actual_app_http_and_shutdown(monkeypatch):
    import guanheng_app.native_chart as projection
    monkeypatch.setattr(projection, "utc_now", lambda: NOW)
    factory = DailyFactory()
    app = create_app(settings(), factory)
    with TestClient(app) as client:
        # 页面沿服务器的实际来源截止读取，不复用旧HTTP桥的固定短截止。
        assert client.get('/v1/ui/capabilities').json()['features']['minute_chart']['timeout_seconds'] == .5
        response = client.get("/v1/ui/market/chart/510300.SH", params={"period": "1d", "limit": 2, "before": BEFORE.isoformat()})
        assert response.status_code == 200
        value = response.json()
        assert value["schema_version"] == "1.6" and value["data_available"]
        assert value["as_of"] == "2026-10-22T16:00:00Z" and len(value["candles"]) == 2
        assert value["overlay_unavailable_sources"] == ["bridge", "strategy"]
    assert len(factory.calls) == 1 and 0 < factory.calls[0][1]["timeout"] <= .5
    assert app.state.shutdown_complete and app.state.reader.live_threads == 0


def test_week_month_use_real_daily_window_and_natural_calendar_ohlcv():
    rows = [
        (20260129, 10, 11, 9, 10, 1), (20260130, 10, 12, 8, 11, 2),
        (20260202, 20, 22, 19, 21, 3), (20260203, 21, 23, 18, 20, 4),
        (20260227, 21, 24, 17, 23, 5), (20260302, 30, 32, 29, 31, 6),
    ]
    def behavior(request):
        response = daily_response(request, empty=True)
        response['data']['bars'] = [{"symbol":request['exchange']+'.'+request['code'],"date":date,
            "open":op,"high":high,"low":low,"close":close,"volume":volume,"amount":volume*close}
            for date,op,high,low,close,volume in rows]
        return response
    weekly_factory = DailyFactory(behavior)
    weekly = build_native_chart(symbol='510300.SH',period='1w',limit=2000,daily_limit=6,
        before=None,settings=settings(),now=NOW,client_factory=weekly_factory)
    assert weekly.schema_version == '1.8' and weekly.derived and weekly.source_period == '1d'
    assert weekly.source_bar_count == 6 and len(weekly.candles) == 4
    assert weekly.candles[0].model_dump(exclude={'occurred_at'}) == {
        'open':10.0,'high':12.0,'low':8.0,'close':11.0,'volume':3.0}
    monthly_factory = DailyFactory(behavior)
    monthly = build_native_chart(symbol='510300.SH',period='1mo',limit=2,daily_limit=6,
        before=None,settings=settings(),now=NOW,client_factory=monthly_factory)
    assert monthly.schema_version == '1.8' and monthly.derived and monthly.source_bar_count == 4
    assert [row.model_dump(exclude={'occurred_at'}) for row in monthly.candles] == [
        {'open':20.0,'high':24.0,'low':17.0,'close':23.0,'volume':12.0},
        {'open':30.0,'high':32.0,'low':29.0,'close':31.0,'volume':6.0},
    ]
    assert weekly_factory.calls[0][0]['limit'] == monthly_factory.calls[0][0]['limit'] == 6


def test_week_month_http_contract_and_daily_limit_scope():
    app = create_app(settings(), DailyFactory())
    with TestClient(app) as client:
        capabilities = client.get('/v1/ui/capabilities').json()['features']
        assert capabilities['daily_chart']['periods'] == ['1d','1w','1mo']
        value = client.get('/v1/ui/market/chart/510300.SH',
            params={'period':'1w','limit':2000,'daily_limit':5}).json()
        assert value['schema_version'] == '1.8' and value['period'] == '1w'
        assert value['source_period'] == '1d' and value['source_bar_count'] == 2
        assert client.get('/v1/ui/market/chart/510300.SH',
            params={'period':'1d','daily_limit':5}).status_code == 422
        assert client.get('/v1/ui/market/chart/510300.SH',
            params={'period':'1w','daily_limit':5,'years':1}).status_code == 422
    assert app.state.shutdown_complete and app.state.reader.live_threads == 0


def test_calendar_year_window_uses_last_actual_source_date_before_aggregation():
    dates=(20241029,20251029,20251030,20261030)
    def behavior(request):
        response=daily_response(request,empty=True)
        response['data']['bars']=[{'symbol':request['exchange']+'.'+request['code'],'date':date,
            'open':float(i),'high':float(i+1),'low':float(i)-.5,'close':float(i)+.5,
            'volume':float(i),'amount':float(i*i)} for i,date in enumerate(dates,1)]
        return response
    daily=build_native_chart(symbol='510300.SH',period='1d',limit=2000,years=1,
        before=None,settings=settings(),now=datetime(2026,11,1,tzinfo=timezone.utc),
        client_factory=DailyFactory(behavior))
    assert daily.source_bar_count==2
    assert [row.occurred_at.astimezone(timezone.utc).date().isoformat() for row in daily.candles] == [
        '2025-10-29','2026-10-29']
    monthly=build_native_chart(symbol='510300.SH',period='1mo',limit=2000,years=1,
        before=None,settings=settings(),now=datetime(2026,11,1,tzinfo=timezone.utc),
        client_factory=DailyFactory(behavior))
    assert monthly.source_bar_count==2 and len(monthly.candles)==2


def test_daily_earlier_observed_date_and_deployment_budget_are_respected():
    factory = DailyFactory()
    result = build_native_chart(symbol="159919.sz", period="1d", limit=2,
        before=datetime(2027, 1, 1, tzinfo=timezone.utc), settings=settings(), now=NOW, client_factory=factory, timeout_seconds=30)
    assert result.data_available
    assert factory.calls == [({"exchange": "SZSE", "code": "159919", "from": 20040101, "to": 20261028, "limit": 2, "view":"current"}, {"timeout": .5})]
    # 日期上界只约束原标签，空missing_dates保持Unknown，不提升当天闭合资格。
    assert result.native_source.coverage == "Unknown" and result.native_source.timestamp_semantics == "source_date"


@pytest.mark.parametrize("field,value", [
    ("period", "1m"), ("timestamp_semantics", "source_label"), ("value_semantics", "canonical"),
    ("minute_boundary", "right"), ("timezone", "UTC"), ("qualification", "ProductionQualified"),
    ("price_unit", "USD"), ("volume_unit", "contract"), ("amount_unit", "USD"),
    ("content_id", "bad"), ("adjustment", "front_ratio"), ("factor_version", "unknown"),
])
def test_daily_metadata_invalid_clears_every_value_and_recovers(field, value):
    def invalid(request):
        response = daily_response(request)
        response["data"]["metadata"][field] = value
        return response
    failed = chart(DailyFactory(invalid))
    assert_unavailable(failed)
    assert chart().data_available


def assert_unavailable(value):
    assert not value.data_available and value.schema_version == "1.6" and value.period == value.source_period == "1d"
    assert value.candles == [] and value.as_of is None and value.native_source is None
    assert value.source_bar_count == 0 and not value.derived and value.missing_reason
    assert "isolated-secret" not in value.missing_reason and "private-address" not in value.missing_reason


@pytest.mark.parametrize("case", ["source", "selection-period", "selection-limit", "selection-bool", "coverage", "missing-dates",
    "quantity", "duplicate", "descending", "extra-field", "row-symbol", "date-invalid", "date-bool", "date-string", "date-float", "date-past", "date-future",
    "open-zero", "open-bool", "high-range", "low-range", "close-string", "volume-inf", "volume-negative", "amount-nan", "amount-negative"])
def test_daily_response_boundaries(case):
    def invalid(request):
        response = daily_response(request)
        data = response["data"]
        row = data["bars"][0]
        if case == "source":
            data["metadata"]["source"]["provider"] = "UnsupportedProvider"
        elif case == "selection-period":
            data["selection"]["period"] = "1m"
        elif case == "selection-limit":
            data["selection"]["limit"] = 3
        elif case == "selection-bool":
            data["selection"]["limit"] = True
        elif case == "coverage":
            data["coverage"] = "Complete"
        elif case == "missing-dates":
            data["missing_dates"] = [20261021]
        elif case == "quantity":
            data["bars"] += [deepcopy(row)]
        elif case == "duplicate":
            data["bars"][1]["date"] = row["date"]
        elif case == "descending":
            data["bars"].reverse()
        elif case == "extra-field":
            data["private"] = "private-address"
        elif case == "row-symbol":
            row["symbol"] = "SZSE.159919"
        elif case.startswith("date-"):
            row["date"] = {"invalid": 20260230, "bool": True, "string": "20261022", "float": 20261022., "past": 20031231, "future": 20261024}[case[5:]]
        else:
            field, problem = case.split("-")
            row[field] = {"zero": 0, "bool": True, "range": 1 if field == "high" else 20, "string": "10.3", "inf": float("inf"), "negative": -1, "nan": float("nan")}[problem]
        return response
    assert_unavailable(chart(DailyFactory(invalid)))


@pytest.mark.parametrize("status", ["Pending", "Backpressure", "StaleSession", "Conflict", "IoError", "Timeout", "NotSupported", "Unavailable", "InvalidInput", "private-address"])
def test_daily_status_is_fixed_unavailable(status):
    assert_unavailable(chart(DailyFactory(lambda _request: {"status": {"code": status, "reason": "isolated-secret private-address"}})))


def test_daily_empty_retains_metadata_without_date_or_coverage_claim():
    value = chart(DailyFactory(lambda request: daily_response(request, empty=True)))
    assert not value.data_available and value.candles == [] and value.as_of is None and value.source_bar_count == 0
    assert value.native_source.coverage == "Unknown" and value.native_source.chart_minute_boundary == "source_date"


def test_daily_budget_before_source_start_and_exception_do_not_leak_or_retry():
    factory = DailyFactory()
    assert_unavailable(chart(factory, timeout_seconds=0))
    assert factory.calls == []
    result = build_native_chart(symbol="510300.SH", period="1d", limit=2, before=datetime(2003, 1, 1, tzinfo=timezone.utc),
        settings=settings(), now=NOW, client_factory=factory)
    assert_unavailable(result)
    assert factory.calls == []
    def failed(_request):
        raise RuntimeError("isolated-secret private-address")
    failed_factory = DailyFactory(failed)
    assert_unavailable(chart(failed_factory))
    assert len(failed_factory.calls) == 1


def test_daily_requires_explicit_source_connection():
    factory = DailyFactory()
    canonical = settings().model_copy(update={"wondertrader_history_semantics": "canonical"})
    result = build_native_chart(symbol="510300.SH", period="1d", limit=2, before=BEFORE, settings=canonical, now=NOW, client_factory=factory)
    assert_unavailable(result)
    assert not factory.calls


@pytest.mark.parametrize("field,value", [("schema_version", "1.4"), ("schema_version", "1.5"), ("period", "1m"), ("source_period", "1m"), ("source_bar_count", None), ("derived", True)])
def test_daily_bundle_cannot_claim_minute_identity(field, value):
    raw = chart().model_dump()
    raw[field] = value
    with pytest.raises(ValueError):
        MarketChartBundle.model_validate(raw)


def test_daily_bundle_date_labels_are_bound_to_shanghai_midnight():
    raw = chart().model_dump()
    raw["candles"][0]["occurred_at"] = datetime(2026, 10, 22, 7, tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        MarketChartBundle.model_validate(raw)


@pytest.mark.parametrize("bad", [None, {}, {"status": {"code": "Ok"}}, {"status": {"code": []}}])
def test_daily_unknown_response_is_unavailable(bad):
    assert_unavailable(chart(DailyFactory(lambda _request: bad)))


def test_daily_http_failure_empty_recovery_and_deadline_close(monkeypatch):
    import guanheng_app.native_chart as projection
    monkeypatch.setattr(projection, "utc_now", lambda: NOW)
    state = ["ok"]
    def behavior(request):
        if state[0] == "failure":
            raise RuntimeError("isolated-secret private-address")
        if state[0] == "slow":
            time.sleep(.8)
        return daily_response(request, empty=state[0] == "empty")
    factory = DailyFactory(behavior)
    app = create_app(settings(), factory)
    with TestClient(app) as client:
        for phase in ("ok", "failure", "empty", "ok", "slow"):
            state[0] = phase
            response = client.get("/v1/ui/market/chart/510300.SH", params={"period": "1d", "limit": 2})
            assert response.status_code == 200
            value = response.json()
            assert value["schema_version"] == "1.6"
            if phase == "ok":
                assert value["data_available"] and value["as_of"]
            else:
                assert not value["data_available"] and value["candles"] == [] and value["as_of"] is None
                assert "isolated-secret" not in value["missing_reason"]
    assert len(factory.calls) == 5 and all(0 < options["timeout"] <= .5 for _request, options in factory.calls)
    assert app.state.shutdown_complete and app.state.reader.live_threads == 0
