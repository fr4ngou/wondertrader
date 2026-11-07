"""Native回调内ASA自有组合的只读原价估值；不改经济账或金融准入。"""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from fractions import Fraction
from time import monotonic

from .profile_facts import quote_value, digest
from .execution_facts import _decimal


@dataclass(frozen=True)
class OwnedQuote:
    symbol: str  # 原ctx已核标准WT证券。
    quantity: int  # 同一ASA快照自有实际份额；零仓不需要报价。
    price_cny: str  # 经原tick校验的每份未复权原价，CNY/份，保持原tick精度。
    observed_at: str  # 原报价上海clock规范化UTC，非本次刷新时间。


def _fixed(value, places=2):
    """整数比率ROUND_HALF_UP，不受调用者Decimal精度影响。"""
    value=Fraction(value);scale=10**places
    whole,left=divmod(abs(value.numerator)*scale,value.denominator)
    if 2*left>=value.denominator:whole+=1
    sign='-'if value<0 and whole else''
    return f'{sign}{whole//scale}.{whole%scale:0{places}d}'


def owned_valuation(context, observation, ticks, *, baseline_cny, baseline_source, max_age, deadline, baseline_at=None):
    """只读原借用内quote getter；baseline单位元、max_age单位秒、deadline沿调用者绝对单调D。
    返回独立字典，异常/缺价只影响展示；本线上角色已知费用沿ASA-5实际Source合同，不接受模型费作实费。"""
    now=datetime.now(timezone.utc)
    result=dict(
        schema='guanheng.owned-valuation.v1',  # 自有原价估值协议，非账户资产快照。
        strategy_id=None if observation is None else observation.strategy.strategy_id,  # 原ASA策略身份。
        strategy_version=None if observation is None else observation.strategy.version,  # 原ASA经济版本。
        book_scope_sha256=None if observation is None else observation.book_scope_sha256,  # 原账身份摘要。
        revision=None if observation is None else observation.strategy.revision,  # 此次自有数量/现金事务水位。
        observed_at=now.isoformat(),  # 原策略本次估值UTC时刻。
        cash_observed_at=None if observation is None else observation.observed_at,  # 自有现金原owner读取clock。
        state='unavailable',  # actual/reference-fee-pending/unavailable分别表达资格。
        reason='allocation_unavailable',  # 固定缺失分类，未知不补金额。
        cash_cny=None,  # 原确定现金；实际费用未齐为None。
        reference_cash_cny=None,  # 只扣已知费用的ledger现金，费用未齐时仅作参考。
        market_value_cny=None,  # 完整正持仓原价市值，ROUND_HALF_UP到分。
        nav_cny=None,  # 费用已知且报价齐备的实际自有净值，CNY。
        reference_nav_cny=None,  # 未扣未知费用的参考净值，绝不标实际。
        unknown_fee_count=None if observation is None else observation.strategy.unknown_fee_count,  # 原未确认费用数量。
        baseline_cny=None,  # 仅原策略配置资本声明，不是账户总资产。
        baseline_at=baseline_at,  # 原资本声明时刻；配置未给出为None，不用估值clock代替。
        baseline_source=baseline_source,  # 配置声明字段的固定公开名称，无私有路径。
        baseline_sha256=None,  # 配置声明{金额,来源}摘要，用于隔离变更基准。
        reference_change_cny=None,  # 相对配置资本变化额，非现金流调整投资损益。
        reference_return_pct=None,  # 相对配置资本变化率%，不是投资收益率。
        price_observed_at=None,  # 估值所用最早报价clock；现金空仓为None。
        price_latest_at=None,  # 同批最晚报价clock；不替换最早报价。
        price_valid_until=None,  # 同批最早失效时刻；仅说明估值生成时准入。
        quotes=[],  # 仅实际正持仓原报价证据；不读账户同码总量。
        source='ASA-owned+Native-raw-quote',  # 唯一账与原价getter的来源口径。
        source_sha256=None)  # 本次全部原输入及资格的规范摘要，不是交易命令。
    try:
        baseline=Fraction(baseline_cny)
        if baseline<=0:raise ValueError('baseline')
        result['baseline_cny']=_fixed(baseline)
        result['baseline_sha256']=digest(dict(amount_cny=result['baseline_cny'],source=baseline_source,baseline_at=baseline_at))
        if observation is None:return _finish(result)
        own=observation.strategy
        if observation.observed_at is None or observation.book_scope_sha256 is None:
            result['reason']='allocation_clock_unavailable';return _finish(result)
        market=Fraction(0);stamps=[]
        for position in own.positions:
            if not position.quantity:continue
            if monotonic()>=deadline:
                result['reason']='valuation_deadline';return _finish(result)
            if position.symbol not in ticks:
                result['reason']='position_price_unavailable';return _finish(result)
            value=quote_value(context,position.symbol,ticks[position.symbol],now=now,max_age=max_age)
            if value is None:
                result['reason']='position_price_unavailable';return _finish(result)
            price,quote=value
            from datetime import timedelta
            from zoneinfo import ZoneInfo
            clock=quote.action_time
            stamp=datetime.strptime(str(quote.action_date),'%Y%m%d').replace(hour=clock//10000000,
                minute=clock//100000%100,second=clock//1000%100,microsecond=clock%1000*1000,
                tzinfo=ZoneInfo('Asia/Shanghai')).astimezone(timezone.utc)
            market+=position.quantity*price;stamps.append(stamp)
            result['quotes'].append(asdict(OwnedQuote(position.symbol,position.quantity,_decimal(price),stamp.isoformat())))
        from datetime import timedelta
        result.update(market_value_cny=_fixed(market),price_observed_at=min(stamps).isoformat()if stamps else None,
            price_latest_at=max(stamps).isoformat()if stamps else None,
            price_valid_until=(min(stamps)+timedelta(seconds=max_age)).isoformat()if stamps else None)
        value=Fraction(own.ledger_cash_cny)+market
        if own.unknown_fee_count:
            result.update(state='reference-fee-pending',reason='actual_fees_unconfirmed',
                reference_cash_cny=_fixed(own.ledger_cash_cny),reference_nav_cny=_fixed(value))
        elif own.cash_cny is not None:
            value=Fraction(own.cash_cny)+market
            result.update(state='actual',reason=None,cash_cny=_fixed(own.cash_cny),nav_cny=_fixed(value))
        else:
            result['reason']='cash_unavailable';return _finish(result)
        result.update(reference_change_cny=_fixed(value-baseline),reference_return_pct=_fixed((value-baseline)*100/baseline,6))
        return _finish(result)
    except Exception:
        # 展示依赖错误局限在本投影；原交易数学/报价检查仍按原路径执行。
        result.update(state='unavailable',reason='valuation_input_unavailable',cash_cny=None,reference_cash_cny=None,
            nav_cny=None,reference_nav_cny=None,market_value_cny=None,reference_change_cny=None,reference_return_pct=None)
        return _finish(result)


def _finish(result):
    result['source_sha256']=digest({k:v for k,v in result.items()if k!='source_sha256'})
    return result
