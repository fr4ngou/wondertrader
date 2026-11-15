"""来源单位资格接缝：复用原QAB/SDK身份，只读原件，不发请求或改历史。"""
from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
import time

from ..guanheng_market_client import strict_json
from ..guanheng_market_client.source_units import (
    UnitEvidence, UNKNOWN_UNITS, parse_unit_evidence, resolve_price_units, normalize_unit_symbol,
)
from .market_generation import encode, read_fixed


@dataclass(frozen=True)
class CaptureUnitEvidence:
    evidence: UnitEvidence  # 已核原件的显式证据，含其配置文件及官方原件SHA。
    capture_sha256: str  # 本次实际准入manifest的字节摘要，区别于参考capture。
    source_business_sha256: str  # 当前原SDK业务身份摘要；运输代次不改变它。
    symbols: tuple[str, ...]  # 当前manifest实际请求证券；不补不存在的来源证券。


def _check(deadline, cancelled):
    if type(deadline) not in (int, float) or not math.isfinite(deadline) or not callable(cancelled):
        raise ValueError("source_unit_evidence_budget_invalid")
    if cancelled():
        raise InterruptedError("source unit evidence cancelled")
    if time.monotonic() >= deadline:
        raise TimeoutError("source unit evidence deadline")


def load_unit_evidence(descriptor, *, deadline, cancelled=lambda: False):
    """核配置SHA及全部官方/安装原件；明确损坏报错，默认调用方可保持不选证据。"""
    _check(deadline, cancelled)
    if type(descriptor) is not dict or set(descriptor) != {"path", "sha256"}:
        raise ValueError("source_unit_evidence_descriptor_invalid")
    path = Path(descriptor["path"])
    if not path.is_absolute():
        raise ValueError("source_unit_evidence_path_invalid")
    raw = read_fixed(path, maximum=1048576, identity=descriptor["sha256"])
    evidence = parse_unit_evidence(raw)
    for proof in (evidence.vendor_wrapper, *evidence.documents):
        _check(deadline, cancelled)
        original = Path(proof.path)
        if not original.is_absolute():
            raise ValueError("source_unit_evidence_path_invalid")
        read_fixed(original, maximum=8388608, identity=proof.sha256)
    _check(deadline, cancelled)
    return evidence


def qualify_capture_units(descriptor, evidence, *, deadline, cancelled=lambda: False):
    """一次核整份capture，返回绑定资格；合法非适用来源返回None，原件损坏失败。

    复用原capture_source_binding和业务身份比较；完整结果仍归原SDK。此资格可在
    同次归档逐证券复用，避免每个证券重复读整批原件。调用方拥有总截止和取消。
    """
    _check(deadline, cancelled)
    if evidence is None:
        return None
    if not isinstance(evidence, UnitEvidence):
        raise ValueError("source_unit_evidence_invalid")
    from .analysis_price_capture import load_price_capture
    from .daily_batch_source import capture_source_binding
    from .daily_gap_update import _hpr_business_identity
    manifest = load_price_capture(descriptor)
    _check(deadline, cancelled)
    request = manifest["request"]
    if manifest["source_kind"] != "actual-qmt" or request.get("source_kind") != "actual-qmt":
        return None
    root = Path(descriptor["directory"])
    capture_source_binding(root, manifest["batches"])
    anchor = strict_json(read_fixed(root / "BINDING.json", maximum=1048576))
    business_sha = hashlib.sha256(encode(_hpr_business_identity(anchor))).hexdigest()
    if business_sha != evidence.source_business_sha256:
        return None
    profile = anchor["profile"]
    operation = profile.get("operation_profiles", {}).get("market.market_data", {})
    if (profile.get("read_profile_version") != "qmt.read-profile.v8"
            or operation.get("policy_id") != "qmt.daily-batch-read.v1"
            or operation.get("policy_version") != "1.0"):
        return None
    symbols = request["symbols"]
    for batch in manifest["batches"]:
        _check(deadline, cancelled)
        slot = strict_json(read_fixed(root / batch["slot"], maximum=16777216, identity=batch["sha256"]))
        original = slot["request"]
        args = original["arguments"]
        window = {key:request[key] for key in ("start_date","end_date","max_rows")}
        if batch["adjustment"] == "none" and "raw_ranges" in request:
            planned = [request["raw_ranges"].get(symbol) for symbol in batch["symbols"]]
            if any(item != {key:args.get(key) for key in window} for item in planned):
                raise ValueError("source_unit_capture_parameters_differ")
            window = planned[0]
        if (original["operation_id"] != "market.market_data"
                or original["policy_id"] != "qmt.daily-batch-read.v1"
                or original["policy_version"] != "1.0"
                or set(args) != {"symbols", "start_date", "end_date", "max_rows", "adjustment"}
                or any(args[key] != value for key,value in window.items())
                or args["symbols"] != batch["symbols"]
                or args["adjustment"] != batch["adjustment"]
                or args["adjustment"] not in ("none", "front_ratio")
                or not set(args["symbols"]) <= set(symbols)):
            raise ValueError("source_unit_capture_parameters_differ")
    _check(deadline, cancelled)
    return CaptureUnitEvidence(evidence, descriptor["sha256"], business_sha, tuple(symbols))


def capture_price_units(manifest, capture_sha256, symbol, unit_evidence):
    """将资格限制于同一完整capture与证券；缺资格/错capture/无symbol维持unknown。"""
    symbol = normalize_unit_symbol(symbol)
    if (not isinstance(unit_evidence, CaptureUnitEvidence)
            or unit_evidence.capture_sha256 != capture_sha256
            or manifest.get("source_kind") != "actual-qmt"
            or manifest.get("request", {}).get("source_kind") != "actual-qmt"
            or symbol not in unit_evidence.symbols):
        return UNKNOWN_UNITS
    return resolve_price_units(unit_evidence.evidence, symbol)
