"""原生现金ETF回放的共同事实投影；策略求值、数量阶段和撮合由各自owner承担。"""
from dataclasses import dataclass, asdict, fields, is_dataclass
from datetime import date, datetime
from fractions import Fraction
from hashlib import sha256
from pathlib import Path
import json
import math

from guanheng_strategy_core.contracts import canonical_bytes
from guanheng_strategy_native import Basis, NativePosition, Observation, Price
from .strategy_porter import Bar, Funds, Position

_MODEL = "original-CtaMocker:flat-single-context-cash-long-absolute-setter-v1"

class SessionError(ValueError):
    """回放准入或原生事实失配。"""

def _public(value):
    if is_dataclass(value):
        return {item.name: _public(getattr(value, item.name)) for item in fields(value)
                if item.metadata.get("wire", True)
                and not (item.metadata.get("omit_none") and getattr(value, item.name) is None)}
    if type(value) is tuple:
        return [_public(item) for item in value]
    if type(value) is dict:
        return {key: _public(item) for key, item in value.items()}
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _json(value):
    return json.dumps(_public(value), ensure_ascii=True, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def _digest(value):
    return sha256(_json(value).encode("ascii")).hexdigest()



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


def _quantity(value):
    if (type(value) not in (int, float) or not math.isfinite(value)
            or not 0 <= value <= 2**53 - 1 or int(value) != value):
        raise SessionError("原生数量必须为非负精确整数")
    return int(value)


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


@dataclass(frozen=True, slots=True)
class NativeSeries:
    """显式原生代码的完整raw日线；所有证券共享闭合交易日集合。"""
    symbol: str
    bars: tuple[Bar, ...]


@dataclass(frozen=True, slots=True)
class NativeCapture:
    """同owner无setter区间的原值；不等同于通用柜台持仓或通用成交证明。"""
    session_id: str
    sequence: int
    trading_date: int
    minute: int
    projection: tuple[tuple[str, float], ...]
    positions: tuple[Position, ...]
    prices: tuple[tuple[str, float], ...]
    funds: Funds
    observation: Observation
    basis: Basis


def capture_native(self, porter, day, minute, input_sha, *, check=None):
    self._owner_porter(porter)
    if not self._initialized:
        raise SessionError("原生初始flat资格未取得")

    def read(operation, *args):
        # 读取本身遵循原生同步契约；返回后到期就停止，保留同一回调截止。
        if check is not None:
            check()
        value = operation(*args)
        if check is not None:
            check()
        return value

    before = read(porter.targets)
    if type(before) is not tuple or len(dict(before)) != len(before):
        raise SessionError("原生枚举重复或类型异常")
    allowed = {self._mapping[symbol] for symbol in self._execution}
    if any(symbol not in allowed or _quantity(quantity) != quantity for symbol, quantity in before):
        raise SessionError("原生枚举存在额外持仓/目标")
    projection = dict(before)
    positions, raw_positions, prices, raw_prices = [], [], [], []
    for symbol in self._execution:
        native = self._mapping[symbol]
        raw = read(porter.position, native)
        if type(raw) is not Position or raw.symbol != native:
            raise SessionError("原生持仓证券/类型失配")
        total, valid = _quantity(raw.total), _quantity(raw.valid)
        if (type(raw.first_entry) is not int or type(raw.last_entry) is not int
                or raw.first_entry < 0 or raw.last_entry < raw.first_entry
                or (raw.first_entry == 0) != (raw.last_entry == 0)):
            raise SessionError("原生entry未知或不一致")
        if raw.first_entry:
            for entry in (raw.first_entry, raw.last_entry):
                if len(str(entry)) != 12 or entry > day * 10000 + minute:
                    raise SessionError("原生entry日期未知或越截止")
                self._clock(entry // 10000, entry % 10000)
            if total == 0 or valid > total:
                raise SessionError("原生持仓entry/可卖与总量不一致")
        elif total != projection.get(native, 0) or valid > total:
            raise SessionError("flat原total与pending投影不一致")
        actual = total if raw.first_entry else 0
        target = _quantity(projection.get(native, actual))
        if actual and native not in projection:
            raise SessionError("实际持仓缺少完整原生枚举")
        positions.append(NativePosition(symbol, actual, valid if actual else 0,
                                        target if target != actual else None))
        raw_positions.append(raw)
        price = read(porter.get_price, native)
        if type(price) not in (int, float) or not math.isfinite(price) or price <= 0:
            raise SessionError("原生raw价格未知")
        expected = next((bar for bar in self._series[native] if bar.date == day), None)
        if expected is None or price != expected.close:
            raise SessionError("原生raw价格与本帧冻结执行原价失配")
        raw_prices.append((native, price))
        prices.append(Price(symbol, repr(float(price)), self._inputs.market_manifest_source))
    funds = read(porter.funds)
    if type(funds) is not Funds or any(type(v) not in (int, float) or not math.isfinite(v) for v in asdict(funds).values()):
        raise SessionError("原生资金字段未知")
    if funds.fees < 0 or read(porter.targets) != before:
        raise SessionError("采集期间原生枚举变化或费用无效")
    self._sequence += 1
    raw_identity = (self._session_id, self._sequence, day, minute, before,
                    tuple(raw_positions), tuple(raw_prices), funds)
    identity = _digest(raw_identity)
    nav = Fraction(self._inputs.policy.initial_capital_cny) + Fraction(repr(float(funds.net)))
    cash = nav - sum((position.actual * Fraction(price.raw_cny_per_share)
                     for position, price in zip(positions, prices, strict=True)), Fraction(0))
    observed_at = self._clock(day, minute).isoformat()
    observation = Observation(observed_at, _MODEL, tuple(positions), True, identity)
    basis = Basis(observed_at, input_sha, _decimal(nav), repr(float(funds.net)), _decimal(cash),
                  self._inputs.fee_reserve_cny, _MODEL + ":genesis+flag0",
                  "same-capture:NAV-minus-complete-actual-raw-market-value", self._inputs.fee_source,
                  tuple(prices), True, identity)
    return NativeCapture(self._session_id, self._sequence, day, minute, before,
                         tuple(raw_positions), tuple(raw_prices), funds, observation, basis)


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
    return tuple(identities), frozen_bytes

