"""同日上市候选与公开证券类别构造股票池；未知资格保留并单列。"""
from collections import Counter
from datetime import date
import re
from .ashare_source import _need
from .bse_universe import _day
from .security_identity import report_rows,security_type
from .storage import digest,encode


def current_pool(basic,daily,basics,quotes,company_rows,periods,aliases,day,*,check):
    """全部来源证券参与核对；已核非股票/未上市/退市/CDR分别记录原因。"""
    types={};type_periods={}
    for code,period,row in report_rows(company_rows,periods,aliases,check=check):
        if period>type_periods.get(code,''):
            types[code]=security_type(row);type_periods[code]=period
    facts={};candidates=set();unverified={};excluded={}
    fields=basic['fields']
    _need(len(set(fields))==len(fields) and {'code','type','ipoDate','outDate'}<=set(fields))
    for values in basic['rows']:
        check()
        _need(len(values)==len(fields) and all(type(v) is str for v in values))
        row=dict(zip(fields,values));code=row['code']
        if not code.startswith(('sh.','sz.')):continue
        _need(re.fullmatch(r'(sh|sz)\.[0-9]{6}',code) and code not in facts)
        facts[code]=row
        if row['type'] in ('2','3','4','5'):excluded[code]='source_nonstock';continue
        first,last=row['ipoDate'],row['outDate']
        for value in (first,last):
            if value:_need(date.fromisoformat(value).isoformat()==value)
        _need(not first or not last or first<last)
        if first and first>day:excluded[code]='not_listed_yet';continue
        if last and last<=day:excluded[code]='delisted';continue
        candidates.add(code)
        if row['type']!='1':unverified[code]='security_category_unverified'
        if not first:unverified[code]='listing_date_missing'
    daily_fields=daily['fields']
    _need(len(set(daily_fields))==len(daily_fields) and {'code','date'}<=set(daily_fields))
    for values in daily['rows']:
        check()
        _need(len(values)==len(daily_fields))
        row=dict(zip(daily_fields,values));code=row['code']
        _need(row['date']==day and type(code) is str and re.fullmatch(r'(sh|sz)\.[0-9]{6}',code))
        if code not in facts:
            candidates.add(code);unverified[code]='security_table_missing'
    for code,row in basics.items():
        check();symbol='bj.'+code
        # 此接口请求股票类别T；异常或缺失返回身份保持候选，等待证券资格核验。
        value=row.get('fxssrq')
        first=_day(value) if value not in ('',None) else None
        if first and first>day:excluded[symbol]='not_listed_yet';continue
        candidates.add(symbol)
        if row.get('xxzqjb')!='T':unverified[symbol]='security_category_unverified'
        if first is None:unverified[symbol]='listing_date_missing'
    for code in quotes:
        symbol='bj.'+code
        if code not in basics:candidates.add(symbol);unverified[symbol]='security_table_missing'
    for code in tuple(candidates):
        check()
        if types.get(code)=='058001008':
            candidates.remove(code);unverified.pop(code,None);excluded[code]='confirmed_cdr'
        elif types.get(code)!='058001001':
            unverified.setdefault(code,'ordinary_security_type_missing')
    members=sorted(candidates)
    return dict(date=day,members=members,market_count=len(members),
        exchange_counts=dict(Counter(code[:2] for code in members)),
        known_market_count=len(members)-len(unverified),unverified_members=unverified,
        unresolved_identity_count=len(unverified),excluded_members=excluded,
        identity_periods=list(periods),security_type_periods=type_periods,
        universe_version=digest(encode(dict(date=day,members=members,unverified=unverified,types=types))))
