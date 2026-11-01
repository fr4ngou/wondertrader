import hashlib
import json

from fastapi.testclient import TestClient

from guanheng_app.app import create_app
from guanheng_app.settings import ConsoleSettings


def catalog(tmp_path):
    securities = [
        dict(symbol="000001.SH", code="000001", exchange="SH", name="上证综合指数",
             security_type="index", pinyin_initials="szzhzs", pinyin_full="shangzhengzonghezhishu"),
        dict(symbol="510300.SH", code="510300", exchange="SH", name="沪深300ETF",
             security_type="etf", pinyin_initials="hs300etf", pinyin_full="hushen300etf"),
        dict(symbol="600000.SH", code="600000", exchange="SH", name="浦发银行",
             security_type="stock", pinyin_initials="pfyh", pinyin_full="pufayinhang"),
        dict(symbol="688170.SH", code="688170", exchange="SH", name="德龙激光",
             security_type="stock", pinyin_initials="dljg", pinyin_full="delongjiguang"),
        dict(symbol="688171.SH", code="688171", exchange="SH", name="纬德信息",
             security_type="stock", pinyin_initials="wdxx", pinyin_full="weidexinxi"),
    ]
    payload = json.dumps(securities, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    value = {"schema_version": "guanheng.security-catalog.v1",
             "catalog_id": hashlib.sha256(payload).hexdigest(),
             "generated_at": "2026-11-01T00:00:00Z", "source": {"fixture": True},
             "securities": securities}
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return path


def test_searches_real_identity_by_code_name_and_both_pinyin_forms(tmp_path):
    settings = ConsoleSettings(security_catalog_file=str(catalog(tmp_path)))
    with TestClient(create_app(settings, static_directory=tmp_path / "absent")) as client:
        code = client.get("/v1/ui/securities/search", params={"query": "68817"})
        assert code.status_code == 200
        assert [item["symbol"] for item in code.json()["results"]] == ["688170.SH", "688171.SH"]
        assert all(item["match"] == "code" for item in code.json()["results"])
        assert client.get("/v1/ui/securities/search", params={"query": "浦发"}).json()["results"][0]["symbol"] == "600000.SH"
        assert client.get("/v1/ui/securities/search", params={"query": "pfy"}).json()["results"][0]["symbol"] == "600000.SH"
        assert client.get("/v1/ui/securities/search", params={"query": "pufayin"}).json()["results"][0]["symbol"] == "600000.SH"


def test_search_supports_stock_etf_index_and_never_guesses(tmp_path):
    settings = ConsoleSettings(security_catalog_file=str(catalog(tmp_path)))
    with TestClient(create_app(settings, static_directory=tmp_path / "absent")) as client:
        types = {}
        for query in ("600000", "510300", "000001"):
            item = client.get("/v1/ui/securities/search", params={"query": query}).json()["results"][0]
            types[item["symbol"]] = item["security_type"]
        assert types == {"600000.SH": "stock", "510300.SH": "etf", "000001.SH": "index"}
        assert client.get("/v1/ui/securities/search", params={"query": "688174"}).json()["results"] == []
        capability = client.get("/v1/ui/capabilities").json()["features"]["security_search"]
        assert capability == {"available": True, "read_only": True,
                              "types": ["stock", "etf", "index"], "reason": None}


def test_missing_or_tampered_catalog_closes_capability(tmp_path):
    path = catalog(tmp_path)
    value = json.loads(path.read_text(encoding="utf-8"))
    value["securities"][0]["name"] = "被修改"
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    with TestClient(create_app(ConsoleSettings(security_catalog_file=str(path)),
                               static_directory=tmp_path / "absent")) as client:
        assert client.get("/v1/ui/capabilities").json()["features"]["security_search"]["available"] is False
        assert client.get("/v1/ui/securities/search", params={"query": "000001"}).status_code == 503
