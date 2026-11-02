"""策略资金的只读白名单；金额由WT运行侧发布，页面不推定账户分配。"""
from datetime import datetime, timezone
from fractions import Fraction
import re


def _need(value):
    if not value:
        raise ValueError('策略资金发布无效')


def _amount(value):
    _need(type(value) is str and len(value) <= 128 and re.fullmatch(r'-?[0-9]+(?:\.[0-9]+)?', value))
    return Fraction(value)


def project_baseline(value):
    if value is None:
        return None
    _need(type(value) is dict and set(value) == {'schema', 'total_cny', 'source', 'baseline_at',
        'historical_initial_capital_cny'} and value['schema'] == 'guanheng.current-capital-baseline.v1'
        and value['historical_initial_capital_cny'] is None and _amount(value['total_cny']) > 0
        and type(value['source']) is str and 1 <= len(value['source']) <= 256)
    stamp = datetime.fromisoformat(value['baseline_at'])
    _need(stamp.utcoffset() is not None and stamp <= datetime.now(timezone.utc))
    return dict(value)


def project_capital(value, origin, *, runtime_state='ready'):
    if value is None:
        return None
    fields = {'schema', 'currency', 'baseline', 'observed_at', 'native_pnl_cny', 'nav_cny', 'market_value_cny',
        'position_observed_at','market_value_source',
        'cash_balance_cny', 'spendable_cash_cny', 'account_observation_qualified', 'account_observed_at', 'account_valid_until',
        'account_available_cny', 'account_frozen_cash_cny', 'account_source_sha256',
        'cash_constraint_scope', 'historical_return_pct'}
    _need(type(value) is dict and set(value) == fields and value['schema'] == 'guanheng.strategy-capital-observation.v1'
        and value['currency'] == 'CNY' and project_baseline(value['baseline']) == origin
        and value['market_value_source'] == 'broker-position+raw-CTA-price'
        and value['historical_return_pct'] is None and type(value['account_observation_qualified']) is bool
        and value['cash_constraint_scope'] == 'account-wide-conservative-limit')
    amounts = {k: _amount(value[k]) for k in ('native_pnl_cny','nav_cny','market_value_cny','cash_balance_cny')}
    _need(amounts['nav_cny'] == _amount(origin['total_cny'])+amounts['native_pnl_cny']
        and amounts['cash_balance_cny'] == amounts['nav_cny']-amounts['market_value_cny']
        and amounts['market_value_cny'] >= 0)
    stamp = datetime.fromisoformat(value['observed_at'])
    _need(stamp.utcoffset() is not None and stamp <= datetime.now(timezone.utc))
    position_stamp = datetime.fromisoformat(value['position_observed_at'])
    _need(position_stamp.utcoffset() is not None and position_stamp <= stamp)
    if value['account_observed_at'] is not None:
        account_stamp = datetime.fromisoformat(value['account_observed_at'])
        until = datetime.fromisoformat(value['account_valid_until'])
        _need(account_stamp.utcoffset() is not None and account_stamp <= datetime.now(timezone.utc)
            and until.utcoffset() is not None and 0 < (until-account_stamp).total_seconds() <= 3600
            and _amount(value['account_available_cny']) >= 0 and _amount(value['account_frozen_cash_cny']) >= 0
            and type(value['account_source_sha256']) is str
            and re.fullmatch('[a-f0-9]{64}',value['account_source_sha256']))
    else:
        _need(all(value[k] is None for k in ('account_available_cny','account_frozen_cash_cny','account_source_sha256','account_valid_until')))
    if value['spendable_cash_cny'] is not None:
        available = _amount(value['spendable_cash_cny'])
        _need(value['account_observation_qualified'] and value['account_observed_at'] is not None
            and 0 <= available <= max(Fraction(0),amounts['cash_balance_cny']-_amount(value['account_frozen_cash_cny']))
            and available <= _amount(value['account_available_cny']))
    result = dict(value)
    if runtime_state != 'ready' or value['account_valid_until'] is None or datetime.now(timezone.utc) >= until:
        result.update(account_observation_qualified=False, spendable_cash_cny=None)
    return result
