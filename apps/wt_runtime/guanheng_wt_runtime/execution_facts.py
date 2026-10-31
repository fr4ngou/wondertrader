"""现金ETF原生资料准入与精确金额编码；由原回放接缝迁入。"""
from fractions import Fraction
from hashlib import sha256
from pathlib import Path
import json
import math

class SessionError(ValueError):
    """回放准入或原生事实失配。"""


def _native_json(data):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise SessionError("原生基础资料JSON键重复")
            value[key] = item
        return value

    def invalid_constant(value):
        raise SessionError("原生基础资料含非有限JSON值")

    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=unique, parse_constant=invalid_constant)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise SessionError("原生基础资料JSON格式无效") from exc


def _decimal(value: Fraction):
    """有限十进制Fraction以整数分解格式化，完全独立于Decimal上下文。"""
    if type(value) is not Fraction or max(value.numerator.bit_length(), value.denominator.bit_length()) > 4096:
        raise SessionError("派生资本超过有界精确表示容量")
    denominator, twos, fives = value.denominator, 0, 0
    while denominator % 2 == 0:
        denominator //= 2
        twos += 1
    while denominator % 5 == 0:
        denominator //= 5
        fives += 1
    places = max(twos, fives)
    if denominator != 1 or places > 1024:
        raise SessionError("派生资本无法有界精确十进制表示")
    coefficient = abs(value.numerator) * 2 ** (places - twos) * 5 ** (places - fives)
    digits = str(coefficient).zfill(places + 1)
    result = digits if not places else (digits[:-places] + "." + digits[-places:]).rstrip("0").rstrip(".")
    return ("-" if value < 0 else "") + result


def admit_native_files(mapping, config):
    identities, contents, frozen_bytes = [], {}, {}
    for name in ("sessions", "commodities", "contracts", "holidays", "fees"):
        path = Path(getattr(config, name))
        if not path.is_absolute() or not path.is_file() or not 0 < path.stat().st_size <= 1024 * 1024:
            raise SessionError("原生基础资料需要绝对路径及有界文件")
        data = path.read_bytes()
        if len(data) > 1024 * 1024:
            raise SessionError("原生基础资料读取越界")
        contents[name] = _native_json(data)
        if type(contents[name]) is not dict:
            raise SessionError("原生基础资料格式无效")
        identities.append((name, sha256(data).hexdigest()))
        frozen_bytes[name] = data
    for native in mapping.values():
        exchange, product, code = native.split(".")
        if exchange+"."+product not in contents["fees"]:
            raise SessionError("实时费用模板缺少已配置品种")
        commodities = contents["commodities"].get(exchange, {})
        contracts = contents["contracts"].get(exchange, {})
        if type(commodities) is not dict or type(contracts) is not dict:
            raise SessionError("原生交易所资料类型无效")
        commodity = commodities.get(product, {})
        contract = contracts.get(code, {})
        if (type(commodity) is not dict or type(contract) is not dict
                or any(type(commodity.get(key)) not in (int, float) or commodity.get(key) != value for key, value in (
                ("category", 0), ("volscale", 1), ("lotstick", 100), ("minlots", 100), ("covermode", 3), ("pricemode", 0)))
                or type(commodity.get("trademode")) is not int or commodity["trademode"] not in (1, 2)
                or type(commodity.get("pricetick")) not in (int, float) or not math.isfinite(commodity["pricetick"])
                or commodity["pricetick"] <= 0
                or any(key in contract for key in ("rules", "longmarginratio", "shortmarginratio"))
                or contract.get("exchg") != exchange or contract.get("product") != product
                or commodity.get("session") not in contents["sessions"]
                or commodity.get("holiday") not in contents["holidays"]):
            raise SessionError("原生合约/品种未满足固定现金ETF多头单位模型")
        session = contents["sessions"][commodity["session"]]
        # 此首模型只授上海现金市场的本地闭合日线；跨夜时段另行准入。
        if (type(session) is not dict or session.get("offset") != 0
                or session.get("sections") != [{"from": 930, "to": 1130}, {"from": 1300, "to": 1500}]
                or type(contents["holidays"][commodity["holiday"]]) is not list):
            raise SessionError("原生session/holiday超出本地15:00闭合日线模型")
    for item in contents["fees"].values():
        if (type(item) is not dict or type(item.get("byvolume")) is not bool
                or set(item) - {"byvolume", "open", "close", "closetoday", "minfee"}
                or any(type(item.get(key)) not in (int, float) or not math.isfinite(item[key]) or item[key] < 0
                       for key in ("open", "close", "closetoday"))
                or ("minfee" in item and (type(item["minfee"]) not in (int, float)
                    or not math.isfinite(item["minfee"]) or item["minfee"] < 0))):
            raise SessionError("原生费用模板存在未知或无效数值")
        # 原实时商品只接收费率；BT重放器的最低费用字段不在该运行能力中。
        if item.get("minfee", 0) > 0:
            raise SessionError("当前原生实时费用不支持正minfee最低费用")
    return tuple(identities), frozen_bytes


