"""当前资本配置和只读现金约束；金融状态继续由WT持有。"""
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from fractions import Fraction
from hashlib import sha256
from pathlib import Path
import math
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
    return dict(total_cny=total, source=value['source'])


def baseline(value, policy=None):
    _require(type(value) is dict and set(value) == {
        'schema', 'total_cny', 'source', 'baseline_at', 'historical_initial_capital_cny'}
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
    """原账户现金约束，绝不作为策略资本来源；冻结现金不与保证金/冻结佣金相加。"""
    available_cny: str
    frozen_cash_cny: str
    observed_at: str
    source_sha256: str


class AccountCashReader:
    """只读原NAP当前定位和同一完整原帧；失败保留最后值及原接收时点。"""
    def __init__(self, value, max_age):
        _require(type(value) is dict and set(value) == {'path', 'config_sha256', 'account', 'environment'})
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
            current = AccountCash(*amounts, stamp.isoformat(), sha256(raw).hexdigest())
            qualified = value['state'] in ('ready', 'refreshing') and now < stamp+timedelta(seconds=self.max_age)
            if time.monotonic() >= deadline:
                raise TimeoutError('account_cash_deadline')
            self.last = current
            return self.last, qualified
        except (ValueError, OSError, KeyError, TypeError, TimeoutError):
            return self.last, False


def observe_capital(origin, pnl, market_value, observed_at, account, qualified, *, max_age_seconds=60,
                    position_observed_at=None):
    """复用WT损益；现金余额=NAV−库存市值，账户冻结仅作保守现金约束。

    账户可用上限已经含券商冻结影响；以min合并，冻结现金只减一次。fee_reserve
    仍由NSQ对新增买入组核算。缺当前账户来源时可用值为unknown，不使用旧值交易。
    """
    origin = baseline(origin)
    nav = rational(origin['total_cny']) + pnl
    cash = nav - market_value
    spendable = None
    if account is not None and qualified:
        spendable = min(max(Fraction(0), cash-rational(account.frozen_cash_cny)),
                        rational(account.available_cny))
    return dict(schema='guanheng.strategy-capital-observation.v1', currency='CNY',
        baseline=origin, observed_at=observed_at, native_pnl_cny=_decimal(pnl),
        position_observed_at=position_observed_at, market_value_source='broker-position+raw-CTA-price',
        nav_cny=_decimal(nav), market_value_cny=_decimal(market_value), cash_balance_cny=_decimal(cash),
        spendable_cash_cny=None if spendable is None else _decimal(spendable),
        account_observation_qualified=bool(qualified),
        account_observed_at=None if account is None else account.observed_at,
        account_valid_until=None if account is None else (
            datetime.fromisoformat(account.observed_at)+timedelta(seconds=max_age_seconds)).isoformat(),
        account_available_cny=None if account is None else account.available_cny,
        account_frozen_cash_cny=None if account is None else account.frozen_cash_cny,
        account_source_sha256=None if account is None else account.source_sha256,
        cash_constraint_scope='account-wide-conservative-limit', historical_return_pct=None)
