"""当前资本配置和只读现金约束；金融状态继续由WT持有。"""
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from fractions import Fraction
from hashlib import sha256
from pathlib import Path
import math
import json
import os
import time
from uuid import UUID

from guanheng_market_client.runtime_status import _open_status_file, _check, _identity
from guanheng_strategy_native._numbers import number, rational, text
from .execution_facts import _decimal
from .managed_local_process import _json, _inspect, _require


def current_capital(value):
    """声明总资本包含库存；旧历史本金未知，模板金额不作为历史事实。"""
    _require(type(value) is dict and set(value) == {'total_cny', 'source'})
    total = number(value['total_cny'], 'current_total_capital')
    _require(rational(total) > 0)
    text(value['source'], 'capital_source')
    return dict(
        total_cny=total,  # 当前策略总资本，含库存；CNY十进制字符串，来自显式声明，必填且大于0。
        source=value['source'])  # 资本声明的来源标识；非空文本，不代表券商历史本金或查询时点。


def baseline(value, policy=None):
    _require(type(value) is dict and set(value) == {
        'schema',  # 当前资本基准的协议版本；固定非空文本，由准备入口写入。
        'total_cny',  # 含初始库存的当前总资本；CNY十进制字符串，来自显式配置，必填且大于0。
        'source',  # 当前总资本的声明来源；非空文本，与数量policy的来源一致。
        'baseline_at',  # 首次启用时点；带时区ISO8601字符串，准备入口写入UTC，恢复时保留。
        'historical_initial_capital_cny'}  # 迁入前的历史本金，单位CNY；当前固定None表示未知，不能按0解释。
        and value['schema'] == 'guanheng.current-capital-baseline.v1'
        and value['historical_initial_capital_cny'] is None)
    result = dict(value, **current_capital({k: value[k] for k in ('total_cny', 'source')}))
    stamp = datetime.fromisoformat(value['baseline_at'])
    _require(stamp.utcoffset() is not None and stamp <= datetime.now(timezone.utc))
    if policy is not None:
        _require(policy.initial_capital_cny == result['total_cny'] and policy.capital_source == result['source'])
    return result


@dataclass(frozen=True)
class AccountCash:
    """券商原现金事实；available+frozen为现金差口径，不合并保证金/冻结佣金。"""
    # 四个字段均必填；没有成功来源时由整个AccountCash对象的None表达未知。
    available_cny: str  # 券商账户可用资金；CNY十进制字符串，来自原account批m_dAvailable，0为已知零。
    frozen_cash_cny: str  # 券商账户冻结现金；CNY十进制字符串，来自同批m_dFrozenCash，0为已知零。
    observed_at: str  # 原account批execution_finished_at；带时区ISO8601字符串，沿来源时点保留，不取读取时间。
    source_sha256: str  # 完整NAP观察帧原字节的SHA256；必填，用于绑定来源，不能代替资金新鲜度。
    binding_sha256: str | None = None  # 账户/环境/CNY绑定的规范SHA；原读取器生成，新现金原点必填，旧调用可省略。

    def __post_init__(self):
        for key in ('available_cny','frozen_cash_cny'):
            value=getattr(self,key)
            _require(type(value) is str and rational(number(value,key)) >= 0)
        stamp=datetime.fromisoformat(self.observed_at)
        _require(stamp.utcoffset() is not None)
        for value in (self.source_sha256,self.binding_sha256):
            _require(value is None or type(value) is str and len(value)==64
                and all(c in '0123456789abcdef'for c in value))
        _require(self.source_sha256 is not None)


def _digest(value):
    return sha256(json.dumps(value, ensure_ascii=True, sort_keys=True,
                             separators=(',', ':'), allow_nan=False).encode('ascii')).hexdigest()


def cash_anchor(value, origin):
    """核固定券商现金原点；只读配置，不滚动记账或调用交易接口。"""
    origin = baseline(origin)
    _require(type(value) is dict and set(value) == {
        'schema', 'baseline_sha256', 'allocated_cash_cny', 'market_value_cny',
        'account_cash_cny', 'account_observed_at', 'account_source_sha256',
        'account_binding_sha256', 'position_source_sha256', 'price_source_sha256'}
        and value['schema'] == 'guanheng.broker-cash-anchor.v1'
        and value['baseline_sha256'] == _digest(origin))
    for key in ('baseline_sha256', 'account_source_sha256', 'account_binding_sha256',
                'position_source_sha256', 'price_source_sha256'):
        _require(type(value[key]) is str and len(value[key]) == 64
                 and all(c in '0123456789abcdef' for c in value[key]))
    for key in ('allocated_cash_cny', 'market_value_cny', 'account_cash_cny'):
        _require(type(value[key]) is str)
        number(value[key], key, signed=key == 'allocated_cash_cny')
    _require(rational(value['market_value_cny']) >= 0 and rational(value['account_cash_cny']) >= 0
             and rational(value['allocated_cash_cny'])+rational(value['market_value_cny'])
             == rational(origin['total_cny']))
    stamp = datetime.fromisoformat(value['account_observed_at'])
    at = datetime.fromisoformat(origin['baseline_at'])
    _require(stamp.utcoffset() is not None and 0 <= (at-stamp).total_seconds() <= 3600)
    return dict(value)


def create_cash_anchor(origin, market_value, account, *, position_source_sha256, price_source_sha256):
    """新启用入口：总预算包含实际库存，账户当前现金作为固定差额原点。

    调用者冻结同次已合格券商P、原价和AccountCash；只有一个策略，当前账户
    全部持仓与冻结归它。原点仅新建一次，重启沿原输入复用；金额不舍入。
    """
    origin = baseline(origin)
    _require(type(account) is AccountCash and account.binding_sha256 is not None and market_value >= 0)
    return cash_anchor(dict(
        schema='guanheng.broker-cash-anchor.v1',  # 固定只读现金原点协议。
        baseline_sha256=_digest(origin),  # 本次含库存预算基准规范SHA；与新基准绑定。
        allocated_cash_cny=_decimal(rational(origin['total_cny'])-market_value),  # 新分配现金，CNY；总预算减实际初始市值，可为负。
        market_value_cny=_decimal(market_value),  # 初始实际数量乘原价的市值，CNY；沿原输入精度。
        account_cash_cny=_decimal(rational(account.available_cny)+rational(account.frozen_cash_cny)),  # 原账户available+frozen，CNY；后续仅使用净变化。
        account_observed_at=account.observed_at,  # 原账户批完成时点；带时区ISO8601。
        account_source_sha256=account.source_sha256,  # 冻结原NAP帧SHA；新原点的现金依据。
        account_binding_sha256=account.binding_sha256,  # 原账户/环境/CNY身份摘要；不传播账号。
        position_source_sha256=position_source_sha256,  # 冻结初始持仓输入SHA；实际数量owner引用。
        price_source_sha256=price_source_sha256), origin)  # 冻结初始原价输入SHA；与原持仓估值共同绑定。


def broker_cash_balance(anchor, account):
    """当前策略现金由券商净变化投影；理论目标、PnL和模型费用不参与。"""
    _require(type(account) is AccountCash and account.binding_sha256 == anchor['account_binding_sha256']
             and datetime.fromisoformat(account.observed_at) >= datetime.fromisoformat(anchor['account_observed_at']))
    return (rational(anchor['allocated_cash_cny'])+rational(account.available_cny)
            +rational(account.frozen_cash_cny)-rational(anchor['account_cash_cny']))


class AccountCashReader:
    """只读原NAP当前定位和同一完整原帧；失败保留最后值及原接收时点。"""
    def __init__(self, value, max_age):
        _require(type(value) is dict and set(value) == {
            'path',  # 原账户owner的current.json绝对路径；由运行配置接线，必填，不归本读取器写入。
            'config_sha256',  # 原Scan配置字节SHA256；由部署描述提供，必填，用于核对同一查询来源。
            'account',  # 明确配置的账户身份；必填敏感文本，仅用于核绑定，不传播至资金展示字段。
            'environment'})  # 账户环境标识；来自原Scan绑定，必填，防止模拟与真实账户混接。
        self.path = Path(value['path'])
        _require(self.path.is_absolute() and self.path.name == 'current.json')
        self.binding, self.max_age, self.last = dict(value), max_age, None

    @staticmethod
    def _document(path, maximum, deadline):
        """定位与正文共用回调原D；超时后仅释放已打开的句柄。"""
        def check():
            if time.monotonic() >= deadline:
                raise TimeoutError('account_cash_deadline')
        check()
        _inspect(path.parent, directory=True); check()
        with _open_status_file(path) as stream:
            check()
            first = os.fstat(stream.fileno()); check()
            _check(first, maximum); check()
            raw = stream.read(maximum+1); check()
            final = os.fstat(stream.fileno()); check()
            _require(len(raw) == first.st_size and _identity(first) == _identity(final))
        check()
        value = _json(raw); check()
        return value, raw

    def read(self, now, deadline):
        try:
            reference, _ = self._document(self.path, 4096, deadline)
            _require(type(reference) is dict and set(reference) == {
                'schema', 'control_id', 'config_sha256', 'pid', 'path', 'ready_path'}
                and reference['schema'] == 'guanheng.account-observation-reference.v1'
                and reference['config_sha256'] == self.binding['config_sha256']
                and type(reference['pid']) is int and 0 < reference['pid'] < 2**32
                and type(reference['control_id']) is str
                and str(UUID(reference['control_id'])) == reference['control_id'])
            path = Path(reference['path'])
            _require(path == self.path.parent / reference['control_id'] / 'observation.json'
                     and Path(reference['ready_path']) == path.parent/'ready.json')
            value, raw = self._document(path, 20*1024*1024+65536, deadline)
            _require(type(value.get('pid')) is int
                     and all(value.get(k) == reference[k] for k in ('control_id', 'config_sha256', 'pid'))
                     and value.get('schema') == 'guanheng.account-observation.v1'
                     and value['binding']['account'] == self.binding['account']
                     and value['binding']['environment'] == self.binding['environment'])
            resources = value['close']['resources']
            _require(value['close']['status'] == 'complete' and type(value['close']['exit_code']) is int
                     and value['close']['exit_code'] == 0
                     and type(resources) is dict and set(resources) == {'member_before_resume', 'tree_reaped', 'stdout_eof',
                         'stderr_eof', 'readers_joined', 'resources_closed'}
                     and all(v is True for v in resources.values())
                     and value['completion']['closed'] is True and value['completion']['joined'] is True)
            observed = value['observation']; summary = observed['summary']
            _require(summary['source_kind'] == 'qmt_shm_bound' and summary['observation_qualified'] is True)
            batches = [b for b in summary['batches'] if b['datatype'] == 'account']
            _require(len(batches) == 1 and batches[0]['delivered'] is True
                     and batches[0]['source']['account_id'] == self.binding['account']
                     and batches[0]['source']['account_environment'] == self.binding['environment'])
            rows = observed['rows']['account']; _require(len(rows) == 1)
            amounts = []
            for name in ('m_dAvailable', 'm_dFrozenCash'):
                item = rows[0]['facts'][name]; _require(type(item) is dict)
                amount = item.get('value')
                _require(item['availability'] == 'present' and type(amount) in (int, float)
                         and amount >= 0 and (type(amount) is int or math.isfinite(amount)))
                amounts.append(number(repr(amount) if type(amount) is float else amount, name))
            _require(type(batches[0]['execution_finished_at']) is str)
            stamp = datetime.fromisoformat(batches[0]['execution_finished_at'].replace('Z', '+00:00'))
            _require(stamp.utcoffset() is not None and stamp <= now)
            binding = _digest(dict(account=self.binding['account'], environment=self.binding['environment'], currency='CNY'))
            current = AccountCash(*amounts, stamp.isoformat(), sha256(raw).hexdigest(), binding)
            qualified = value['state'] in ('ready', 'refreshing') and now < stamp+timedelta(seconds=self.max_age)
            if time.monotonic() >= deadline:
                raise TimeoutError('account_cash_deadline')
            self.last = current
            return self.last, qualified
        except (ValueError, OSError, KeyError, TypeError, TimeoutError):
            return self.last, False


def cash_reconciles(nav, market_value, cash):
    """原WT double与精确原价/成本重建只容许1e-8 CNY表示误差，原值全部保留。"""
    return abs(cash-(nav-market_value)) <= Fraction(1,100000000)


def observe_capital(origin, pnl, market_value, observed_at, account, qualified, *, max_age_seconds=60,
                    position_observed_at=None, market_value_source='broker-position+raw-CTA-price',
                    cash_balance=None, price_observed_at=None):  # 独立原现金依据与原报价时间；均不冒充账户批次时间。
    """复用WT损益；现金余额=NAV−库存市值，账户冻结仅作保守现金约束。

    账户可用上限已经含券商冻结影响；以min合并，冻结现金只减一次。fee_reserve
    仍由NSQ对新增买入组核算。缺当前账户来源时可用值为unknown，不使用旧值交易。
    """
    origin = baseline(origin)
    _require(market_value_source in ('broker-position+raw-CTA-price', 'broker-position+raw-QMT-snapshot'))
    nav = rational(origin['total_cny']) + pnl
    cash = nav - market_value if cash_balance is None else cash_balance
    _require(cash_reconciles(nav,market_value,cash))
    spendable = None
    if account is not None and qualified:
        spendable = min(max(Fraction(0), cash-rational(account.frozen_cash_cny)),
                        rational(account.available_cny))
    # 金额统一为CNY精确十进制字符串，不强制分位舍入；None表示来源未知，数值0表示已知零。
    return dict(
        schema='guanheng.strategy-capital-observation.v1',  # 资金观察协议版本；固定非空文本。
        currency='CNY',  # 本观察所有金额的币种；固定人民币，不进行汇率换算。
        baseline=origin,  # 首次准备owner拥有的当前资本基准；必填，恢复沿原对象内容复用。
        observed_at=observed_at,  # 本次CTA回调估值截止；带时区ISO8601，不冒充账户批次的原时点。
        price_observed_at=price_observed_at,  # 所用报价最旧原事件时间；CTA无法提供时为None，不以读取时间替代。
        native_pnl_cny=_decimal(pnl),  # 本次运行盈亏，CNY；新现金模式由券商现金+实际市值−预算取得，原NSQ字段名保持。
        position_observed_at=position_observed_at,  # 券商P原接收时点；带时区ISO8601，None表示调用方未提供。
        market_value_source=market_value_source,  # 市值来源；实际券商数量乘原CTA未复权报价，或首次原QMT快照，禁止历史收盘代替。
        nav_cny=_decimal(nav),  # 当前净值；预算基准加本次运行盈亏，含当前库存价值。
        market_value_cny=_decimal(market_value),  # 当前实际库存市值；数量为股/份，报价为CNY/股或份。
        cash_balance_cny=_decimal(cash),  # 策略现金余额；净值减实际库存市值，允许负值，不取账户总现金。
        spendable_cash_cny=None if spendable is None else _decimal(spendable),  # 保守可用现金；受账户冻结/可用限制，失效为None。
        account_observation_qualified=bool(qualified),  # 原账户来源当前是否合格且未过期；False时禁止用旧值授可用资金。
        account_observed_at=None if account is None else account.observed_at,  # 原account批完成时间；无成功来源为None，失效保留旧时间。
        account_valid_until=None if account is None else (
            datetime.fromisoformat(account.observed_at)+timedelta(seconds=max_age_seconds)).isoformat(),  # 原账户时间加配置有效秒数；无来源为None。
        account_available_cny=None if account is None else account.available_cny,  # 原全账户可用资金；无成功来源为None，失效保留原值。
        account_frozen_cash_cny=None if account is None else account.frozen_cash_cny,  # 原全账户冻结现金；无来源为None，非策略专属冻结额。
        account_source_sha256=None if account is None else account.source_sha256,  # 原NAP帧SHA256；无成功来源为None，失效保持来源身份。
        cash_constraint_scope='account-wide-conservative-limit',  # 账户级保守上限标识；没有按策略分摊账户冻结额。
        historical_return_pct=None)  # 迁入前历史收益率，单位%；固定None表示未知，不由新运行净值倒算。


def observe_broker_capital(origin, anchor, native_theoretical_pnl, market_value, observed_at,
                           account, qualified, **options):
    """唯一策略的实际资金投影；原CTA理论统计仅原样保留供审计。

    native_pnl_cny沿原NSQ字段名承载NAV−本次预算基准；其来源由pnl_source明确。
    账户未知时返回None；旧原帧可展示余额，qualified=False时可用现金保持未知。
    """
    anchor = cash_anchor(anchor, origin)
    if account is None:
        return None
    cash = broker_cash_balance(anchor, account)
    pnl = cash+market_value-rational(origin['total_cny'])
    value = observe_capital(origin, pnl, market_value, observed_at, account, qualified,
                            cash_balance=cash, **options)
    value.update(
        cash_anchor=anchor,  # 固定新现金原点；金额CNY，来源时点与身份沿原输入。
        pnl_source='broker-cash-delta',  # 本次真实策略盈亏来源；与CTA理论flag0分离。
        native_theoretical_pnl_cny=_decimal(native_theoretical_pnl))  # 原CTAflag0原精度统计，CNY；仅审计，不授资金。
    return value


def refresh_account_constraint(value, reader, deadline):
    """续核账户现金并更新差额投影；保留持仓/价格估值及全部原时点。

    reader由同一执行发布owner的账户读取线程独占，沿原NAP身份/有效窗读取。
    读取失败保留上次来源及时间、撤销可用资格；不刷新估值或将未知资金按0处理。
    """
    account,qualified = reader.read(datetime.now(timezone.utc),deadline)
    if account is None and value['account_observed_at'] is not None:
        account = AccountCash(value['account_available_cny'],value['account_frozen_cash_cny'],
            value['account_observed_at'],value['account_source_sha256'],
            value.get('cash_anchor',{}).get('account_binding_sha256'))
    if account is not None and value['account_observed_at'] is not None:
        if datetime.fromisoformat(account.observed_at) < datetime.fromisoformat(value['account_observed_at']):
            return value
    if value.get('cash_anchor') is not None:
        try:
            return observe_broker_capital(value['baseline'],value['cash_anchor'],
                rational(value['native_theoretical_pnl_cny']),rational(value['market_value_cny']),
                value['observed_at'],account,qualified,max_age_seconds=reader.max_age,
                position_observed_at=value['position_observed_at'],market_value_source=value['market_value_source'],
                price_observed_at=value.get('price_observed_at'))
        except ValueError:
            return dict(value,account_observation_qualified=False,spendable_cash_cny=None)
    return observe_capital(value['baseline'],rational(value['native_pnl_cny']),rational(value['market_value_cny']),
        value['observed_at'],account,qualified,max_age_seconds=reader.max_age,
        position_observed_at=value['position_observed_at'],market_value_source=value['market_value_source'],
        cash_balance=rational(value['cash_balance_cny']),price_observed_at=value.get('price_observed_at'))
