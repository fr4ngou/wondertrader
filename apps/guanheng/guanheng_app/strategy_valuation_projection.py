"""原profile估值白名单；只验身份/资格/clock，不查价或计算策略净值。"""
from datetime import datetime
from decimal import Decimal
import hashlib
import json

from .strategy_allocation_projection import _need, _time, _money, _sha, _quantity, security

FIELDS = set('schema strategy_id strategy_version book_scope_sha256 revision observed_at cash_observed_at state reason cash_cny reference_cash_cny market_value_cny nav_cny reference_nav_cny unknown_fee_count baseline_cny baseline_source baseline_at baseline_sha256 reference_change_cny reference_return_pct price_observed_at price_latest_at price_valid_until quotes source source_sha256'.split())
CURRENT_FEE_FIELDS = {'provisional_fee_count'}  # 当前费用暂记资格；旧已确认费用发布保留原字节/摘要。


def project_owned_valuation(identity, report, allocation):
    """附加估值独立降级；格式失效不遮住已核持仓/成交，不授金融权限。"""
    value=report.get('owned_valuation')
    if value is None:return None,'absent','not_published'
    try:
        _need(type(value)is dict and set(value) in (FIELDS, FIELDS|CURRENT_FEE_FIELDS)
              and value['schema']=='guanheng.owned-valuation.v1')
        proof={k:v for k,v in value.items()if k!='source_sha256'}
        expected=hashlib.sha256(json.dumps(proof,ensure_ascii=True,allow_nan=False,sort_keys=True,separators=(',',':')).encode('ascii')).hexdigest()
        _need(_sha(value['source_sha256'])==expected and value['source']=='ASA-owned+Native-raw-quote')
        state=value['state'];_need(state in ('actual','reference-fee-pending','unavailable'))
        if value.get('provisional_fee_count') is not None:_quantity(value['provisional_fee_count'])
        observed=_time(value['observed_at']);cash_at=_time(value['cash_observed_at'])
        _need(observed is not None and (cash_at is None or cash_at<=observed))
        _need(value['baseline_source']in ('original-profile.initial_capital_cny','retained.capital_baseline.total_cny','retained.policy.initial_capital_cny'))
        for name in ('cash_cny','reference_cash_cny','market_value_cny','nav_cny','reference_nav_cny','baseline_cny','reference_change_cny','reference_return_pct'):
            _money(value[name],optional=True)
        _time(value['baseline_at'])
        if value['baseline_cny'] is not None:
            _need(Decimal(value['baseline_cny'])>0)
            raw=json.dumps(dict(amount_cny=value['baseline_cny'],source=value['baseline_source'],baseline_at=value['baseline_at']),ensure_ascii=True,sort_keys=True,separators=(',',':')).encode('ascii')
            _need(_sha(value['baseline_sha256'])==hashlib.sha256(raw).hexdigest())
        _need(type(value['quotes'])is list and len(value['quotes'])<=64)
        clocks=[];seen=set()
        for row in value['quotes']:
            _need(type(row)is dict and set(row)=={'symbol','quantity','price_cny','observed_at'})
            symbol=security(row['symbol']);_need(symbol not in seen);seen.add(symbol)
            _need(type(row['quantity'])is int and 0<row['quantity']<=9007199254740991 and Decimal(_money(row['price_cny']))>0)
            clock=_time(row['observed_at']);_need(clock is not None and clock<=observed);clocks.append(clock)
        if state=='unavailable':
            _need(value['nav_cny'] is None and value['reference_nav_cny'] is None)
        else:
            _need(allocation is not None and value['strategy_id']==identity and value['strategy_version']==allocation['strategy_version']
                and value['book_scope_sha256']==allocation['book_scope_sha256'] and value['revision']==allocation['revision']
                and value['unknown_fee_count']==allocation['unknown_fee_count'] and cash_at==allocation['observed_at'])
            pending=value.get('provisional_fee_count',0)
            _need(type(pending)is int and pending>=0 and pending==allocation.get('provisional_fee_count',0))
            held={p['symbol']:p['quantity']for p in allocation['positions']if p['quantity']}
            _need({security(r['symbol']):r['quantity']for r in value['quotes']}==held)
            _need(value['market_value_cny']is not None and Decimal(value['market_value_cny'])>=0)
            if clocks:
                _need(_time(value['price_observed_at'])==min(clocks) and _time(value['price_latest_at'])==max(clocks))
                until=datetime.fromisoformat(value['price_valid_until']);_need(until.utcoffset()is not None and datetime.fromisoformat(observed)<until)
            else:_need(all(value[k]is None for k in ('price_observed_at','price_latest_at','price_valid_until')))
            if state=='actual':
                _need(allocation['unknown_fee_count']==0 and Decimal(value['cash_cny'])==Decimal(allocation['cash_cny']) and value['nav_cny']is not None
                    and value['reference_nav_cny']is None and value['reference_cash_cny']is None)
            else:
                _need(allocation['unknown_fee_count']>0 and value['cash_cny']is None and value['nav_cny']is None
                    and Decimal(value['reference_cash_cny'])==Decimal(allocation['ledger_cash_cny']) and value['reference_nav_cny']is not None)
        return dict(value),state,value['reason']
    except (ValueError,TypeError,KeyError,ArithmeticError,OverflowError):
        return None,'unavailable','invalid_owned_valuation'
