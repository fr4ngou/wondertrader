"""已审ContextInfo日线单位的纯值合同；不读取文件、来源或运行环境。"""
from dataclasses import dataclass
import hashlib
import re

from . import strict_json

PROFILE_ID = "qmt-contextinfo-day-etf-index.v1"
SOURCE_API = "ContextInfo.get_market_data_ex/1d/get_market_data2"
VENDOR_SHA256 = "5f0fa76bddac5c182a7195175a32e78ff550dc5d1e0c09d2e31ca4c2e374b469"
# 内容摘要属于已审profile；网页后继变化需新证据版本，不静默承接。
DOCUMENTS = (
    ("qmt_bar_fields", "https://knowledge.thinktrader.net/docs/cloud/data_structure.html",
     "69eac0d2d9186839786f25c038a029607eea055e746ffa067a93a5bad67246f6"),
    ("qmt_context_api", "https://knowledge.thinktrader.net/docs/python/data_function.html",
     "f8d94a2185e1fd8018a8db03169fec340bdee27fa30d5f087b560d31072736c7"),
    ("sse_etf_unit", "https://www.sse.com.cn/assortment/fund/etf/question/c/c_20240118_5734754.shtml",
     "5c7dd646ae433a8a09f4752ceeb37c4c7ef2ac584c1a6ff929348ca75d737efe"),
    ("szse_rules", "https://docs.static.szse.cn/www/lawrules/rule/trade/W020260424690713155663.pdf",
     "9b66f8b0db70f84a25ef1ccb4ee2351001724e408117552d75f6d8993483c586"),
    ("csi300_methodology", "https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/indices/detail/files/zh_CN/000300_Index_Methodology_cn.pdf",
     "de6491e03e5d57ecf1aca104b1412543643a59e387a5343c9bd21ecbbdeba5b6"),
)
ETF_SYMBOLS = frozenset(("510050.SH", "510300.SH", "510500.SH", "512100.SH",
                         "515080.SH", "588000.SH", "159780.SZ", "589680.SH", "159352.SZ",
                         "512890.SH", "159949.SZ", "159781.SZ", "510330.SH", "159919.SZ", "510310.SH"))
INDEX_SYMBOL = "000300.SH"


@dataclass(frozen=True)
class UnitProof:
    name: str  # 已审证据角色；同一profile内唯一。
    uri: str  # 官方来源URL或本机安装入口标识；不代表另发请求。
    path: str  # 部署所有者配置的原件绝对路径，纯解析不读文件。
    sha256: str  # 对应HTML/PDF/包装函数原始文件字节SHA256。


@dataclass(frozen=True)
class UnitEvidence:
    profile_id: str  # 固定已审单位语义版本，区别于供应商数据修订版。
    source_business_sha256: str  # 原SDK业务身份去运输代后的规范摘要。
    reference_capture_sha256: str  # 参考核验的不可变manifest摘要；后继capture各自另绑。
    source_api: str  # 明确内置ContextInfo日线入口，不承接外部xtquant单位。
    vendor_wrapper: UnitProof  # 已核本机包装函数原件；不复制执行该源码。
    documents: tuple[UnitProof, ...]  # 已审五件官方原件，角色和摘要固定。
    sha256: str  # 显式证据文件本身的原始字节摘要。


@dataclass(frozen=True)
class PriceUnits:
    price_unit: str  # SDK20公开价格单位CNY/unknown；ETF为每份基金价格。
    volume_unit: str  # lot为原API手单位；unknown保持未证明。
    amount_unit: str  # 本profile固定unknown，真实0与单位未知分别表达。
    semantic_price_unit: str  # 明确消费者可用的CNY/index-point/unknown量纲。


UNKNOWN_UNITS = PriceUnits("unknown", "unknown", "unknown", "unknown")


def _sha(value):
    if type(value) is not str or re.fullmatch("[0-9a-f]{64}", value) is None:
        raise ValueError("source_unit_evidence_invalid")
    return value


def _proof(value, name, uri, digest):
    if (type(value) is not dict or set(value) != {"name", "uri", "path", "sha256"}
            or value["name"] != name or value["uri"] != uri or value["sha256"] != digest
            or type(value["path"]) is not str or not 1 <= len(value["path"]) <= 4096
            or "\x00" in value["path"]):
        raise ValueError("source_unit_evidence_invalid")
    return UnitProof(name, uri, value["path"], _sha(value["sha256"]))


def parse_unit_evidence(raw):
    """只解析受控配置已选择的证据字节；Data owner另核原件和实际capture业务身份。"""
    if type(raw) is not bytes or len(raw) > 1048576:
        raise ValueError("source_unit_evidence_invalid")
    value = strict_json(raw)
    if (type(value) is not dict or set(value) != {"schema", "profile_id", "source_business_sha256",
            "reference_capture_sha256", "source_api", "vendor_wrapper", "documents"}
            or value["schema"] != "qmt.source-unit-evidence.v1"
            or value["profile_id"] != PROFILE_ID or value["source_api"] != SOURCE_API
            or type(value["documents"]) is not list or len(value["documents"]) != len(DOCUMENTS)):
        raise ValueError("source_unit_evidence_invalid")
    wrapper = _proof(value["vendor_wrapper"], "vendor_wrapper", SOURCE_API, VENDOR_SHA256)
    documents = tuple(_proof(item, *expected) for item, expected in zip(value["documents"], DOCUMENTS))
    return UnitEvidence(PROFILE_ID, _sha(value["source_business_sha256"]),
                        _sha(value["reference_capture_sha256"]), SOURCE_API, wrapper, documents,
                        hashlib.sha256(raw).hexdigest())


def normalize_unit_symbol(symbol):
    """仅归一已有QMT/公开证券命名；裸码与未支持格式返回None。"""
    if type(symbol) is not str:
        return None
    # 同一证券两种已有命名只在本处归一；六位裸码没有交易所身份。
    if symbol.startswith(("SSE.", "SZSE.")):
        market, code = symbol.split(".", 1)
        symbol = code + (".SH" if market == "SSE" else ".SZ")
    return symbol if re.fullmatch("[0-9]{6}\\.(SH|SZ)", symbol) else None


def resolve_price_units(evidence, symbol):
    """解释已准入证据的固定证券域；调用者负责将证据绑定到实际来源，未知返回原unknown。"""
    if not isinstance(evidence, UnitEvidence) or evidence.profile_id != PROFILE_ID:
        return UNKNOWN_UNITS
    symbol = normalize_unit_symbol(symbol)
    if symbol in ETF_SYMBOLS:
        return PriceUnits("CNY", "lot", "unknown", "CNY")
    if symbol == INDEX_SYMBOL:
        return PriceUnits("unknown", "lot", "unknown", "index-point")
    return UNKNOWN_UNITS


def resolve_source_price_units(evidence, symbol, packet):
    """解释已验SDK数据包的全部实际来源段；旧unknown来源维持unknown。

    packet为history.source-daily-query的data。公开SourceSelection元数据可能合并
    来源，资格须覆盖每条实际bar的连续provenance；本函数不替代SDK数值校验。
    """
    units = resolve_price_units(evidence, symbol)
    if units == UNKNOWN_UNITS or type(packet) is not dict:
        return UNKNOWN_UNITS
    bars = packet.get("bars")
    if type(bars) is not list or not bars:
        return UNKNOWN_UNITS
    parts = packet.get("provenance")
    if parts is None:
        parts = [dict(offset=0, count=len(bars), metadata=packet.get("metadata"))]
    if type(parts) is not list or not parts:
        return UNKNOWN_UNITS
    expected = "qmt.batch-native-day.v2:" + evidence.profile_id + ":" + evidence.sha256
    covered = 0
    for part in parts:
        if (type(part) is not dict or type(part.get("offset")) is not int
                or part["offset"] != covered or type(part.get("count")) is not int
                or not 1 <= part["count"] <= len(bars) - covered):
            return UNKNOWN_UNITS
        metadata = part.get("metadata")
        if (type(metadata) is not dict or metadata.get("dataset_version") != expected
                or type(metadata.get("source")) is not dict or metadata["source"].get("provider") != "Qmt"
                or (metadata.get("price_unit"), metadata.get("volume_unit"), metadata.get("amount_unit"))
                != (units.price_unit, units.volume_unit, units.amount_unit)):
            return UNKNOWN_UNITS
        covered += part["count"]
    return units if covered == len(bars) else UNKNOWN_UNITS
