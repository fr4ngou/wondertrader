from hashlib import sha256
import json

import pytest

from guanheng_wt_runtime.execution_security import generate_etf_execution_security


def security(symbol, *, name, security_type="etf", listed_on="2024-10-15", expires_on=None):
    return dict(symbol=symbol, name=name, market=symbol.split(".")[0], security_type=security_type,
                listed_on=listed_on, expires_on=expires_on, observed_at=None)


def reference(tmp_path, rows):
    path = tmp_path / "reference.json"
    raw = json.dumps(dict(schema="guanheng.security-reference.v3", securities=rows)).encode("ascii")
    path.write_bytes(raw)
    return path, sha256(raw).hexdigest()


def test_generates_two_exchange_mappings_and_contracts_from_one_reference(tmp_path):
    first, second = "SZSE.159352", "SSE.510300"
    path, digest = reference(tmp_path, {
        first: security(first, name="A500"),
        second: security(second, name="CSI 300", listed_on="2012-05-28", expires_on="2030-12-31"),
    })

    result = generate_etf_execution_security(path, digest, [first, second, first])

    assert result == generate_etf_execution_security(path, digest, [second, first])
    assert result["security_reference_sha256"] == digest
    assert result["reader_mappings"] == [
        dict(std_code="SSE.ETF.510300", symbol="510300.SH"),
        dict(std_code="SZSE.ETF.159352", symbol="159352.SZ"),
    ]
    assert result["contracts"] == {
        "SSE": {"510300": dict(exchg="SSE", product="ETF", name="CSI 300", opendate=20120528, expiredate=20301231)},
        "SZSE": {"159352": dict(exchg="SZSE", product="ETF", name="A500", opendate=20241015, expiredate=20991231)},
    }
    assert sha256(path.read_bytes()).hexdigest() == digest


@pytest.mark.parametrize("rows,message", [
    ({}, "缺少证券资料"),
    ({"SZSE.159352": security("SSE.510300", name="Wrong row")}, "与证券资料原行冲突"),
    ({"SZSE.159352": security("SZSE.159352", name="Index", security_type="index")}, "缺少当前市场或品种"),
    ({"SZSE.159352": security("SZSE.159352", name="ETF", listed_on=None)}, "缺少证券名称或上市日"),
])
def test_invalid_reference_names_the_affected_security(tmp_path, rows, message):
    path, digest = reference(tmp_path, rows)

    with pytest.raises(ValueError, match=f"SZSE.159352 {message}"):
        generate_etf_execution_security(path, digest, ["SZSE.159352"])


def test_reference_digest_mismatch_rejects_generation(tmp_path):
    path, _ = reference(tmp_path, {})

    with pytest.raises(ValueError, match="SHA256 不匹配"):
        generate_etf_execution_security(path, "0" * 64, ["SZSE.159352"])
