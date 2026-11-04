"""策略资金的只读白名单；金额由WT运行侧发布，页面不推定账户分配。"""
from datetime import datetime, timezone
from fractions import Fraction
from hashlib import sha256
import json
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
    _need(type(value) is dict and fields <= set(value) <= fields | {
        'price_observed_at','cash_anchor','pnl_source','native_theoretical_pnl_cny'}
        and value['schema'] == 'guanheng.strategy-capital-observation.v1'
        and value['currency'] == 'CNY' and project_baseline(value['baseline']) == origin
        # 首次加载可由当前QMT快照估值；后续沿CTA原报价，两个来源都由WT明确声明。
        and value['market_value_source'] in ('broker-position+raw-CTA-price', 'broker-position+raw-QMT-snapshot')
        and value['historical_return_pct'] is None and type(value['account_observation_qualified']) is bool
        and value['cash_constraint_scope'] == 'account-wide-conservative-limit')
    amounts = {k: _amount(value[k]) for k in ('native_pnl_cny','nav_cny','market_value_cny','cash_balance_cny')}
    _need(amounts['nav_cny'] == _amount(origin['total_cny'])+amounts['native_pnl_cny']
        and abs(amounts['cash_balance_cny']-(amounts['nav_cny']-amounts['market_value_cny'])) <= Fraction(1,100000000)
        and amounts['market_value_cny'] >= 0)
    if 'cash_anchor' in value:
        # 券商现金差投影只读核验；保留原NSQ字段名，本次盈亏取实际NAV−新基准。
        anchor=value['cash_anchor']
        _need(value.get('pnl_source')=='broker-cash-delta'
            and _amount(value['native_theoretical_pnl_cny']) is not None
            and type(anchor) is dict and set(anchor)=={
                'schema','baseline_sha256','allocated_cash_cny','market_value_cny',
                'account_cash_cny','account_observed_at','account_source_sha256',
                'account_binding_sha256','position_source_sha256','price_source_sha256'}
            and anchor['schema']=='guanheng.broker-cash-anchor.v1'
            and anchor['baseline_sha256']==sha256(json.dumps(origin,ensure_ascii=True,
                sort_keys=True,separators=(',',':'),allow_nan=False).encode('ascii')).hexdigest()
            and _amount(anchor['allocated_cash_cny'])+_amount(anchor['market_value_cny'])==_amount(origin['total_cny'])
            and _amount(anchor['account_cash_cny'])>=0 and _amount(anchor['market_value_cny'])>=0)
        for key in ('account_source_sha256','account_binding_sha256','position_source_sha256','price_source_sha256'):
            _need(type(anchor[key]) is str and re.fullmatch('[a-f0-9]{64}',anchor[key]))
        anchor_stamp=datetime.fromisoformat(anchor['account_observed_at'])
        _need(anchor_stamp.utcoffset() is not None
            and 0 <= (datetime.fromisoformat(origin['baseline_at'])-anchor_stamp).total_seconds() <= 3600)
        _need(value['account_available_cny'] is not None and value['account_frozen_cash_cny'] is not None
            and _amount(value['cash_balance_cny'])==_amount(anchor['allocated_cash_cny'])
                +_amount(value['account_available_cny'])+_amount(value['account_frozen_cash_cny'])-_amount(anchor['account_cash_cny'])
            and datetime.fromisoformat(value['account_observed_at'])>=anchor_stamp)
    else:
        _need('pnl_source' not in value and 'native_theoretical_pnl_cny' not in value)
    stamp = datetime.fromisoformat(value['observed_at'])
    _need(stamp.utcoffset() is not None and stamp <= datetime.now(timezone.utc))
    position_stamp = datetime.fromisoformat(value['position_observed_at'])
    _need(position_stamp.utcoffset() is not None and position_stamp <= stamp)
    # 报价事件时间与本次估值、持仓和账户时间分别拥有；旧发布可不提供。
    if value.get('price_observed_at') is not None:
        price_stamp = datetime.fromisoformat(value['price_observed_at'])
        _need(price_stamp.utcoffset() is not None and price_stamp <= stamp)
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
