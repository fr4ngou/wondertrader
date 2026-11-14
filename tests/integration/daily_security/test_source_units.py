"""来源单位契约回归；合成证据只在测试内替换已审摘要，不连接Source或账户。"""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import time

import pytest

from integrations.guanheng import analysis_price_capture as capture
from integrations.guanheng import analysis_price_units as owner
from integrations.guanheng.daily_gap_update import _hpr_business_identity
from integrations.guanheng.market_generation import encode
from integrations.guanheng_market_client import source_units as units
from integrations.guanheng_market_client.source_history import validate_source_metadata


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = encode(value)
    path.write_bytes(raw)
    return dict(path=str(path), sha256=digest(raw))


@pytest.fixture
def material(tmp_path, monkeypatch):
    """合成完整原件/slot形态；原SDK准入边界用明确替身，真实20槽主链另存QA。"""
    proofs = []
    documents = []
    for name, uri, _ in units.DOCUMENTS:
        path = tmp_path / (name + ".original")
        path.write_bytes(("synthetic official-original stand-in: " + name).encode())
        sha = digest(path.read_bytes())
        proofs.append((name, uri, sha))
        documents.append(dict(name=name, uri=uri, path=str(path), sha256=sha))
    monkeypatch.setattr(units, "DOCUMENTS", tuple(proofs))
    wrapper = tmp_path / "wrapper.py"
    wrapper.write_bytes(b"# synthetic wrapper original")
    monkeypatch.setattr(units, "VENDOR_SHA256", digest(wrapper.read_bytes()))
    anchor = dict(binding_sha256="1"*64, binding=dict(host_instance_id="old-host",
        transport_generation="old-transport", route=dict(route_id="synthetic-route", route_epoch=1)),
        profile=dict(read_profile_version="qmt.read-profile.v8", operation_profiles={
            "market.market_data": dict(policy_id="qmt.daily-batch-read.v1", policy_version="1.0")}))
    evidence = dict(schema="qmt.source-unit-evidence.v1", profile_id=units.PROFILE_ID,
        source_business_sha256=digest(encode(_hpr_business_identity(anchor))),
        reference_capture_sha256="2"*64, source_api=units.SOURCE_API,
        vendor_wrapper=dict(name="vendor_wrapper", uri=units.SOURCE_API, path=str(wrapper),
                            sha256=units.VENDOR_SHA256), documents=documents)
    evidence_descriptor = save(tmp_path / "evidence.json", evidence)
    root = tmp_path / "capture"
    save(root / "BINDING.json", anchor)
    args = dict(symbols=["510300.SH", "000300.SH"], start_date="20261105", end_date="20261106",
                max_rows=2, adjustment="none")
    slot = dict(request=dict(operation_id="market.market_data", policy_id="qmt.daily-batch-read.v1",
                             policy_version="1.0", arguments=args))
    slot_descriptor = save(root / "slots/0.json", slot)
    manifest = dict(source_kind="actual-qmt", request=dict(source_kind="actual-qmt", capture_id="fixed-capture",
        symbols=args["symbols"], start_date=args["start_date"], end_date=args["end_date"], max_rows=2),
        batches=[dict(slot="slots/0.json", sha256=slot_descriptor["sha256"],
                      symbols=args["symbols"], adjustment="none")])
    capture_descriptor = dict(directory=str(root), sha256=save(root/"manifest.json", manifest)["sha256"])
    monkeypatch.setattr(capture, "load_price_capture", lambda d: deepcopy(manifest))
    from integrations.guanheng import daily_batch_source
    monkeypatch.setattr(daily_batch_source, "capture_source_binding", lambda p, b: anchor["binding_sha256"])
    return dict(evidence=evidence, evidence_descriptor=evidence_descriptor, capture=capture_descriptor,
                manifest=manifest, anchor=anchor, slot=slot, root=root)


def admitted(m):
    end = time.monotonic()+5
    evidence = owner.load_unit_evidence(m["evidence_descriptor"], deadline=end)
    qualified = owner.qualify_capture_units(m["capture"], evidence, deadline=end)
    assert qualified is not None
    return evidence, qualified


def test_default_profile_preserves_original_byte_contract(material):
    m = material["manifest"]
    result = capture.capture_profile(m, "a"*64, "none")
    expected = ('{"provider":"Qmt","instance_id":"qmt-batch-source:'+"a"*32+
        '","session_id":"fixed-capture","generation":1,"dataset_version":"qmt.batch-native-day.v1",'
        '"source_license":"unknown","input_kind":"qmt_export","timezone":"Asia/Shanghai",'
        '"minute_boundary":"unknown","adjustment":"none","factor_version":"","value_semantics":"source",'
        '"price_unit":"unknown","volume_unit":"unknown","amount_unit":"unknown"}')
    assert json.dumps(result, separators=(",", ":")) == expected
    _, qualified = admitted(material)
    assert capture.capture_profile(m, "a"*64, "none", unit_evidence=qualified) == result


def test_admitted_etf_and_index_share_one_interpretation(material):
    evidence, qualified = admitted(material)
    for symbol, public, semantic in [("510300.SH", "CNY", "CNY"), ("000300.SH", "unknown", "index-point")]:
        for basis in ("none", "front_ratio"):
            metadata = capture.capture_metadata(material["manifest"], material["capture"]["sha256"],
                basis, symbol=symbol, unit_evidence=qualified)
            assert (metadata["price_unit"], metadata["volume_unit"], metadata["amount_unit"]) == (public, "lot", "unknown")
            assert units.resolve_price_units(evidence, symbol).semantic_price_unit == semantic
            validate_source_metadata(metadata, period="1d")  # SDK20合同继续接受指数unknown。
            assert evidence.sha256 in metadata["dataset_version"]
    assert units.resolve_price_units(evidence, "SSE.510300") == units.resolve_price_units(evidence, "510300.SH")


@pytest.mark.parametrize("symbol", ["159352.SZ", "589680.SH", "159780.SZ", "512890.SH", "159949.SZ",
                                   "159781.SZ", "510330.SH", "159919.SZ", "510310.SH"])
def test_fixed_new_etf_domain_is_supported_by_same_resolver(material, symbol):
    evidence, _ = admitted(material)
    assert units.resolve_price_units(evidence, symbol) == units.PriceUnits("CNY", "lot", "unknown", "CNY")


@pytest.mark.parametrize("symbol", [None, "510300", "600000.SH", "000300.SZ", "SSE.159352",
                                   "SZSE.512890", "SSE.159949"])
def test_unknown_or_wrong_security_identity_remains_unknown(material, symbol):
    evidence, qualified = admitted(material)
    assert units.resolve_price_units(evidence, symbol) == units.UNKNOWN_UNITS
    assert owner.capture_price_units(material["manifest"], material["capture"]["sha256"], symbol, qualified) == units.UNKNOWN_UNITS


def test_wrong_capture_and_unrequested_security_do_not_acquire_units(material):
    _, qualified = admitted(material)
    for sha, symbol in [("f"*64, "510300.SH"), (material["capture"]["sha256"], "159352.SZ")]:
        result = capture.capture_profile(material["manifest"], sha, "none", symbol=symbol, unit_evidence=qualified)
        assert (result["price_unit"], result["volume_unit"], result["amount_unit"]) == ("unknown",)*3


@pytest.mark.parametrize("kind", ["sdk-synthetic", "foreign-route"])
def test_non_applicable_business_keeps_unknown(material, kind):
    evidence, _ = admitted(material)
    if kind == "sdk-synthetic":
        material["manifest"]["source_kind"] = kind
        material["manifest"]["request"]["source_kind"] = kind
    else:
        anchor = deepcopy(material["anchor"])
        anchor["binding"]["route"]["route_id"] = "foreign-business"
        save(material["root"]/"BINDING.json", anchor)
    assert owner.qualify_capture_units(material["capture"], evidence, deadline=time.monotonic()+3) is None


def test_transport_restart_and_new_capture_reuse_business_evidence(material):
    evidence, _ = admitted(material)
    anchor = deepcopy(material["anchor"])
    anchor["binding"]["host_instance_id"] = "new-host"
    anchor["binding"]["transport_generation"] = "new-transport"
    anchor["binding_sha256"] = "3"*64
    save(material["root"]/"BINDING.json", anchor)
    later = dict(material["capture"], sha256="4"*64)
    result = owner.qualify_capture_units(later, evidence, deadline=time.monotonic()+3)
    assert result is not None and result.capture_sha256 == "4"*64
    assert result.source_business_sha256 == evidence.source_business_sha256
    assert evidence.reference_capture_sha256 != result.capture_sha256


@pytest.mark.parametrize("field", ["vendor_wrapper", "documents"])
def test_original_bytes_damage_rejects_explicit_evidence(material, field):
    value = material["evidence"][field]
    proof = value[0] if type(value) is list else value
    Path(proof["path"]).write_bytes(b"changed original")
    with pytest.raises(ValueError):
        owner.load_unit_evidence(material["evidence_descriptor"], deadline=time.monotonic()+3)


def test_evidence_registry_and_descriptor_digest_reject_tampering(material):
    raw = Path(material["evidence_descriptor"]["path"]).read_bytes()
    value = json.loads(raw)
    value["source_api"] = "xtquant.xtdata.get_market_data_ex"
    with pytest.raises(ValueError):
        units.parse_unit_evidence(encode(value))
    Path(material["evidence_descriptor"]["path"]).write_bytes(raw+b" ")
    with pytest.raises(ValueError):
        owner.load_unit_evidence(material["evidence_descriptor"], deadline=time.monotonic()+3)


def test_slot_parameter_change_and_original_digest_damage_fail(material):
    evidence, _ = admitted(material)
    path = material["root"]/"slots/0.json"
    slot = deepcopy(material["slot"])
    slot["request"]["arguments"]["max_rows"] = 999
    descriptor = save(path, slot)
    with pytest.raises(ValueError):
        owner.qualify_capture_units(material["capture"], evidence, deadline=time.monotonic()+3)
    material["manifest"]["batches"][0]["sha256"] = descriptor["sha256"]
    with pytest.raises(ValueError, match="parameters_differ"):
        owner.qualify_capture_units(material["capture"], evidence, deadline=time.monotonic()+3)


def test_cancel_and_deadline_have_explicit_results(material):
    evidence, _ = admitted(material)
    for call in (lambda **kw: owner.load_unit_evidence(material["evidence_descriptor"], **kw),
                 lambda **kw: owner.qualify_capture_units(material["capture"], evidence, **kw)):
        with pytest.raises(InterruptedError):
            call(deadline=time.monotonic()+3, cancelled=lambda: True)
        with pytest.raises(TimeoutError):
            call(deadline=time.monotonic()-1)


def test_semantic_index_unit_requires_all_actual_source_segments(material):
    evidence, qualified = admitted(material)
    metadata = capture.capture_metadata(material['manifest'], material['capture']['sha256'],
        'front_ratio', symbol='000300.SH', unit_evidence=qualified)
    packet = dict(bars=[{'date': 20261105}, {'date': 20261106}],
        metadata=dict(dataset_version='source-daily-selection.v1'), provenance=[
            dict(offset=0, count=1, metadata=metadata), dict(offset=1, count=1, metadata=metadata)])
    assert units.resolve_source_price_units(evidence, '000300.SH', packet).semantic_price_unit == 'index-point'
    single = dict(bars=packet['bars'], metadata=metadata)
    assert units.resolve_source_price_units(evidence, '000300.SH', single).semantic_price_unit == 'index-point'
    old = deepcopy(packet)
    old['provenance'][0]['metadata'] = dict(metadata, dataset_version='qmt-local-dat-layout.v2')
    assert units.resolve_source_price_units(evidence, '000300.SH', old) == units.UNKNOWN_UNITS


@pytest.mark.parametrize('damage', ['missing_tail', 'wrong_evidence', 'foreign_provider'])
def test_semantic_source_binding_cannot_be_partial_or_foreign(material, damage):
    evidence, qualified = admitted(material)
    metadata = capture.capture_metadata(material['manifest'], material['capture']['sha256'],
        'none', symbol='000300.SH', unit_evidence=qualified)
    packet = dict(bars=[{'date': 20261105}, {'date': 20261106}],
                  provenance=[dict(offset=0, count=2, metadata=metadata)])
    if damage == 'missing_tail':
        packet['provenance'][0]['count'] = 1
    elif damage == 'wrong_evidence':
        metadata['dataset_version'] = metadata['dataset_version'][:-64] + 'f'*64
    else:
        metadata['source'] = dict(provider='CSI')
    assert units.resolve_source_price_units(evidence, '000300.SH', packet) == units.UNKNOWN_UNITS
