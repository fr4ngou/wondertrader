"""从已发布证券资料生成现有 WT Reader 和 Native ETF 合约配置。"""

import argparse
from hashlib import sha256
from pathlib import Path
import re

from guanheng_market_client import MarketProtocolError
from guanheng_market_client.security import validate_security_identity

from .managed_local_process import _json, _path, _read, _sha


# 当前 Reader 源的交易所代码协议。具体证券及品种由资料原件确认。
MARKET_SUFFIX = {"SSE": "SH", "SZSE": "SZ"}
REFERENCE_SCHEMAS = {f"guanheng.security-reference.v{version}" for version in (1, 2, 3)}
NO_EXPIRY_DATE = 20991231  # WT Native 合约的无到期日约定。


def etf_mapping_and_contract(catalog, identity):
    """返回一个证券的 Reader 映射和 Native 合约，输入资料及其原行保持只读。"""
    if type(identity) is not str or re.fullmatch(r"(?:SSE|SZSE|BSE)\.[0-9]{6}", identity) is None:
        raise ValueError("证券标识应为交易所.六位代码")
    if type(catalog.get("schema")) is not str or catalog["schema"] not in REFERENCE_SCHEMAS:
        raise ValueError("证券资料版本无效")
    securities = catalog.get("securities")
    if type(securities) is not dict or identity not in securities:
        raise ValueError(f"{identity} 缺少证券资料")
    try:
        security = validate_security_identity(securities[identity])
    except (MarketProtocolError, TypeError, ValueError) as exc:
        raise ValueError(f"{identity} 证券资料无效") from exc
    market, code = identity.split(".")
    if security["symbol"] != identity:
        raise ValueError(f"{identity} 与证券资料原行冲突")
    if market not in MARKET_SUFFIX or security["security_type"] != "etf":
        raise ValueError(f"{identity} 缺少当前市场或品种的执行规则")
    name, listed_on, expires_on = (security[key] for key in ("name", "listed_on", "expires_on"))
    if not name or not name.strip() or listed_on is None:
        raise ValueError(f"{identity} 缺少证券名称或上市日")
    if expires_on is not None and expires_on < listed_on:
        raise ValueError(f"{identity} 到期日早于上市日")

    mapping = {
        "std_code": f"{market}.ETF.{code}",  # WT Reader 内部标准合约代码。
        "symbol": f"{code}.{MARKET_SUFFIX[market]}",  # 行情来源代码。
    }
    contract = {
        "exchg": market,  # Native 交易所身份，来自同一目录原行。
        "product": "ETF",  # 已核品种对应的现有 Native 商品配置键。
        "name": name,  # 原资料发布的证券名称。
        "opendate": int(listed_on.replace("-", "")),  # 上市日，YYYYMMDD。
        "expiredate": NO_EXPIRY_DATE if expires_on is None else int(expires_on.replace("-", "")),  # 到期日，YYYYMMDD。
    }
    return mapping, contract


def generate_etf_execution_security(reference_path, reference_sha256, identities):
    """读取固定证券资料并生成候选配置。重复证券合并，结果按证券标识排序。"""
    raw = _read(_path(str(reference_path)), 16 * 1024 * 1024)
    if sha256(raw).hexdigest() != _sha(reference_sha256):
        raise ValueError("证券资料 SHA256 不匹配")
    catalog = _json(raw)
    if not identities or any(type(identity) is not str for identity in identities):
        raise ValueError("至少需要一个证券标识")
    mappings, contracts = [], {}
    for identity in sorted(set(identities)):
        mapping, contract = etf_mapping_and_contract(catalog, identity)
        market, code = identity.split(".")
        mappings.append(mapping)
        contracts.setdefault(market, {})[code] = contract
    return {
        "schema": "guanheng.etf-execution-security.v1",  # 候选材料版本，发布资格由原执行入口核验。
        "security_reference_sha256": reference_sha256,  # 已校验的证券资料原字节 SHA256。
        "reader_mappings": mappings,  # 可加入 data.store.symbols 的 Reader 映射。
        "contracts": contracts,  # 按 Native 交易所和六位代码组织的合约行。
    }


def main():
    """离线生成一个新候选文件，输入异常时原配置和已有候选保持原样。"""
    from .service_control import _write_exclusive

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--security-reference", type=Path, required=True)
    parser.add_argument("--security-reference-sha256", required=True)
    parser.add_argument("--security", action="append", required=True, help="交易所.六位代码，可重复指定")
    parser.add_argument("--output", type=Path, required=True, help="全新的候选文件路径")
    args = parser.parse_args()
    try:
        candidate = generate_etf_execution_security(
            args.security_reference, args.security_reference_sha256, args.security,
        )
        _write_exclusive(args.output, candidate)
    except (ValueError, OSError) as exc:
        parser.exit(2, f"生成 ETF 执行资料失败：{exc}\n")


if __name__ == "__main__":
    main()
