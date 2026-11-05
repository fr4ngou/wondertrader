"""现金ETF原生资料准入与精确金额编码；由原回放接缝迁入。"""
from fractions import Fraction
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
import json
import math
from types import MappingProxyType

class SessionError(ValueError):
    """回放准入或原生事实失配。"""


def buy_fee_basis(target, policy, basis, observation, mapping, fees, source, *, split_fills):
    """按本次目标和原WT费表装配买入费用，显式预留作为最低值。

    split_fills=True为实盘异步成交：逐份向上取分覆盖任意整数份拆分的舍入；
    回放单次原撮合用整笔费率及最低费，再按原WT规则四舍五入到分。
    此函数只提供现金准入事实，目标权重/份数、NSQ阶段及实际记费保持原owner。
    """
    from guanheng_strategy_native import target_quantities
    if type(split_fills) is not bool:
        raise SessionError('native_fee_fill_model')
    total = Fraction(0)
    for wanted, position, price in zip(target_quantities(target, policy, basis),
                                       observation.positions, basis.prices, strict=True):
        delta = max(0, wanted.shares-position.actual)
        if not delta:
            continue
        exchange, product, unused = mapping[wanted.symbol].split('.')
        # 原WT calc_fee在费表没有此品种时返回0；保持该明确配置语义。
        fee = fees.get(exchange+'.'+product, {'open': 0, 'byvolume': True})
        rate = Fraction(str(fee['open']))
        minimum = Fraction(str(fee.get('minfee', 0))) if rate > 0 else Fraction(0)
        unit = rate if fee['byvolume'] else rate*Fraction(price.raw_cny_per_share)
        if split_fills:
            cents = max(unit, minimum)*100
            amount = delta*Fraction((cents.numerator+cents.denominator-1)//cents.denominator, 100)
        else:
            cents = max(unit*delta, minimum)*100
            amount = Fraction((2*cents.numerator+cents.denominator)//(2*cents.denominator), 100)
        total += amount
    floor = Fraction(basis.fee_reserve_cny) if basis.fee_reserve_cny is not None else Fraction(0)
    return replace(basis, fee_reserve_cny=_decimal(max(floor, total)),
        fee_source=source+(':open-integer-share-cent-upper' if split_fills else ':open-original-single-match-cent')+
            ':configured-minimum')


def native_price_ticks(mapping, frozen):
    """由已准入且SHA绑定的WT commodities生成原生代码→CNY/份最小报价档位。

    WT的parseCommodity/getPriceTick与此处消费同一品种pricetick；不是成交均价、
    手续费或金额的小数位。返回不可变本代快照，不读取新文件或猜测ETF统一精度。
    """
    commodities = _native_json(frozen['commodities'])
    result = {}
    for code in mapping.values():
        exchange, product, unused = code.split('.')
        tick = commodities[exchange][product]['pricetick']
        if type(tick) not in (int, float) or not math.isfinite(tick) or tick <= 0:
            raise SessionError('native_price_tick_invalid')
        result[code] = Fraction(repr(tick))
    return MappingProxyType(result)


def canonical_raw_price(value, tick):
    """将原报价恢复为精确整数档位，返回CNY/份Fraction；真实离档明确报错。

    value来自WT/QMT double，或原报告保存的同一报价十进制文本。仅消除距本代
    合约档位不超过4*double epsilon*价格尺度的表示尾差；界限须严格小于1/4档，
    整数档数在double精确整数范围内，沿StandardQmtTrader::price_text同一数值界。
    不改调用者原值；原快照/捕获身份和审计保留。此接口不用于均价、费率或资金。
    """
    if type(value) not in (int, float, str) or type(tick) is not Fraction or tick <= 0:
        raise SessionError('native_raw_price_invalid')
    try:
        floating = float(value)
        if not math.isfinite(floating) or floating <= 0:
            raise ValueError('nonpositive_or_nonfinite')
        raw = Fraction(value if type(value) is str else repr(value))
    except (ValueError, OverflowError, ZeroDivisionError):
        raise SessionError('native_raw_price_invalid') from None
    steps = raw/tick
    nearest = (2*steps.numerator+steps.denominator)//(2*steps.denominator)
    if nearest < 1:
        raise SessionError('native_raw_price_off_tick')
    if nearest > 9007199254740991:
        raise SessionError('native_raw_price_tick_ambiguous')
    canonical = nearest*tick
    # 先通过现有C++委托转换的double判定；精确十进制归一化只可收紧其集合。
    try:
        native_tick = float(tick)
    except OverflowError:
        raise SessionError('native_price_tick_invalid') from None
    if not math.isfinite(native_tick) or native_tick <= 0:
        raise SessionError('native_price_tick_invalid')
    scaled = floating/native_tick
    if not math.isfinite(scaled):
        raise SessionError('native_raw_price_tick_ambiguous')
    native_steps = math.floor(scaled+0.5)
    native_canonical = native_steps*native_tick
    native_bound = 4*(2.0**-52)*max(floating,abs(native_canonical))
    if not math.isfinite(native_canonical) or native_bound >= native_tick/4:
        raise SessionError('native_raw_price_tick_ambiguous')
    if native_steps != nearest or abs(floating-native_canonical) > native_bound:
        raise SessionError('native_raw_price_off_tick')
    # epsilon=2^-52；用精确分式计算既有double表示误差界，不向现金比较传播容差。
    bound = Fraction(4, 2**52)*max(raw, canonical)
    if bound >= tick/4:
        raise SessionError('native_raw_price_tick_ambiguous')
    if abs(raw-canonical) > bound:
        raise SessionError('native_raw_price_off_tick')
    return canonical


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


