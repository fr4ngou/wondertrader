"""已披露高管本人买卖：原事件、同日上市池及公司身份共同决定聚合资格。"""
from datetime import date, timedelta
from decimal import Decimal
from fractions import Fraction
import math
import re

from .baostock_source import BaostockClient
from .provider_reports import report_pages
from .source_fetch import SourceFailure
from .stock_universe import shsz_listings, listed_codes
from .storage import digest, encode
from .executive_models import rows_for_metrics
from .financial_source import REPORT as COMPANY_REPORT
from .security_identity import company_id as _company, security_code as _security, canonical as _canonical_security, report_rows, security_type

REPORT = 'RPT_EXECUTIVE_HOLD_DETAILS'
COLUMNS = ('SECURITY_CODE,DERIVE_SECURITY_CODE,CHANGE_DATE,CHANGE_SHARES,CHANGE_AMOUNT,CHANGE_REASON,'
           'HOLD_TYPE,POSITION_NAME,PERSON_DSE_RELATION,ORG_CODE,GGEID')
COMPANY_COLUMNS = 'SECURITY_CODE,SECUCODE,ORG_CODE,SECURITY_TYPE_CODE,REPORT_DATE'
EXECUTIVE_ROLES = {'高管', '高级管理人员', '总经理', '副总经理', '总裁', '副总裁', '董秘',
                   '董事会秘书', '财务总监', '财务负责人', '总会计师', '首席执行官', '首席财务官'}
OTHER_ROLES = {'董事', '董事长', '副董事长', '独立董事', '职工董事', '监事', '监事会主席',
               '职工监事', '核心技术人员'}
PAID_REASONS = {'集中竞价', '竞价交易', '二级市场买卖', '大宗交易', '协议转让', '盘后定价', '询价转让'}
NONCASH_REASONS = {'送转', '送股', '转增', '继承', '赠与', '无偿划转', '股权激励', '股权激励实施', '限制性股票授予'}
NONSELF_RELATIONS = {'配偶', '兄弟姐妹', '其他组织', '受控法人'}
# 有界十进制系数/指数限制有理数构造成本；128位系数覆盖披露金额及大额抵消。
MAX_NUMBER_DIGITS = 128
MAX_NUMBER_EXPONENT = 512


def _need(value, code):
    if not value:
        raise SourceFailure('executive_'+code)


def _day(value):
    _need(type(value) is str and re.fullmatch(r'\d{4}-\d{2}-\d{2}(?: 00:00:00)?', value), 'date')
    try:
        return date.fromisoformat(value[:10]).isoformat()
    except ValueError:
        raise SourceFailure('executive_date') from None


def _number(value):
    if value is None:
        return None
    _need(type(value) in (int, float, Decimal), 'number')
    if type(value) is int:
        _need(value.bit_length() <= 426, 'number')
        result = Decimal(value)
    else:
        result = Decimal(str(value))
    _need(result.is_finite(), 'number')
    parts = result.as_tuple()
    _need(len(parts.digits) <= MAX_NUMBER_DIGITS and abs(parts.exponent) <= MAX_NUMBER_EXPONENT, 'number')
    projected = float(result)
    _need(math.isfinite(projected) and (result == 0 or projected != 0), 'number')
    return Fraction(result)


def _project(value):
    """完成精确聚合后投影；溢出及非零下溢沿原来源失败语义保旧。"""
    try:
        result = float(value)
    except OverflowError:
        raise SourceFailure('executive_aggregate_nonfinite') from None
    _need(math.isfinite(result) and (value == 0 or result != 0), 'aggregate_nonfinite')
    return result


def _role(value):
    if type(value) is not str or not value or len(value) > 200:
        return None
    roles = set(re.split('[,，、;；]', value))
    if roles & EXECUTIVE_ROLES:
        return True
    return False if roles <= OTHER_ROLES else None


def aggregate_changes(rows, listings, company_rows, periods, start, end, *, check=lambda: None, aliases=None):
    """按变动日回溯已披露事件；有界金额内部按精确有理数求和。

    本人/高管/有偿交易三个条件同时成立才计入。未确认关系、职务和交易原因单列；
    缺金额不补价。公司比例仅在同日股票池全部确认公司身份时提供。当前抓取
    的修订报告用于身份映射，历史当时可得性不在此接口授予。
    """
    check()
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    _need(0 <= (last-first).days < 366 and len(rows) <= 8000 and len(company_rows) <= 40000, 'capacity')
    _need(1 <= len(periods) <= 5, 'identity_report_period')
    aliases = aliases or {}
    companies, types = {}, {}
    for code, _period, row in report_rows(company_rows,periods,aliases,check=check):
        company = _company(row.get('ORG_CODE'))
        kind = security_type(row)
        _need(kind is not None, 'security_type')
        if code in companies:
            _need(companies[code] == company and types[code] == kind, 'identity_company_conflict')
        companies[code] = company
        types[code] = kind
    events, ids = {}, set()
    for row in rows:
        check()
        identity = row.get('GGEID')
        # Python整数原样验证；原GGEID常大于JS安全整数，聚合输出不携带该ID。
        _need(type(identity) is int and 0 < identity < 2**127 and identity not in ids, 'event_identity')
        ids.add(identity)
        day = _day(row.get('CHANGE_DATE'))
        _need(start <= day <= end, 'event_range')
        code = _security(row, 'DERIVE_SECURITY_CODE')
        code = _canonical_security(code, aliases)
        _need(row.get('HOLD_TYPE') == 'A股', 'holding_type')
        company = _company(row.get('ORG_CODE'))
        if code in companies:
            _need(companies[code] == company, 'company_conflict')
        else:
            companies[code] = company
        events.setdefault(day, []).append((row, code, company))
    output, universes = [], []
    for offset in range((last-first).days+1):
        check()
        day = (first+timedelta(days=offset)).isoformat()
        members = listed_codes(listings, day, check=check)
        _need(bool(members), 'universe_empty')
        cdr = {code for code in members if types.get(code) == '058001008'}
        members -= cdr
        unknown = members-companies.keys()
        market_companies = {companies[code] for code in members if code in companies}
        counts = dict(reported_event_count=0, eligible_event_count=0, nonself_count=0, other_role_count=0,
            unknown_relation_count=0, unknown_role_count=0, noncash_count=0, unknown_reason_count=0,
            missing_amount_count=0, outside_pool_count=0)
        buy, sell = Fraction(0), Fraction(0)
        buyers, sellers = set(), set()
        for row, code, company in events.get(day, []):
            check()
            counts['reported_event_count'] += 1
            if code not in members:
                counts['outside_pool_count'] += 1
                continue
            relation = row.get('PERSON_DSE_RELATION')
            if relation != '本人':
                nonself = type(relation) is str and relation in NONSELF_RELATIONS
                counts['nonself_count' if nonself else 'unknown_relation_count'] += 1
                continue
            role = _role(row.get('POSITION_NAME'))
            if role is not True:
                counts['other_role_count' if role is False else 'unknown_role_count'] += 1
                continue
            reason = row.get('CHANGE_REASON')
            if reason not in PAID_REASONS:
                counts['noncash_count' if reason in NONCASH_REASONS else 'unknown_reason_count'] += 1
                continue
            shares, amount = _number(row.get('CHANGE_SHARES')), _number(row.get('CHANGE_AMOUNT'))
            _need(shares is not None and shares != 0, 'share_direction')
            counts['eligible_event_count'] += 1
            (buyers if shares > 0 else sellers).add(company)
            if amount is None or amount == 0:
                counts['missing_amount_count'] += 1
                continue
            _need((amount > 0) == (shares > 0), 'amount_direction')
            if shares > 0:
                buy += amount
            else:
                sell -= amount
        denominator = len(market_companies) if not unknown else None
        total, net = buy+sell, buy-sell
        has_unknown = any(counts[key] for key in ('missing_amount_count', 'unknown_relation_count',
            'unknown_role_count', 'unknown_reason_count'))
        known_amount_events = counts['eligible_event_count']-counts['missing_amount_count']
        row = dict(date=day, buy_amount_cny=_project(buy), sell_amount_cny=_project(sell),
            net_amount_cny=_project(net) if known_amount_events or not has_unknown else None,
            net_amount_pct=_project(100*net/total) if total and not counts['missing_amount_count'] else None,
            complete_net_amount_cny=_project(net) if not has_unknown else None,
            buy_company_count=len(buyers), sell_company_count=len(sellers), changed_company_count=len(buyers|sellers),
            buy_company_pct=100*len(buyers)/denominator if denominator else None,
            sell_company_pct=100*len(sellers)/denominator if denominator else None,
            changed_company_pct=100*len(buyers|sellers)/denominator if denominator else None,
            market_stock_count=len(members), known_market_company_count=len(market_companies),
            market_company_count=denominator, unresolved_market_identity_count=len(unknown), cdr_excluded_count=len(cdr), **counts)
        _need(all(not isinstance(value, float) or math.isfinite(value) for value in row.values()), 'aggregate_nonfinite')
        output.append(row)
        universes.append(dict(date=day, market_count=len(members), known_company_count=len(market_companies),
            unresolved_identity_count=len(unknown), members=sorted(members),
            universe_version=digest(encode(dict(date=day, members=sorted(members),
                companies={code:companies.get(code) for code in sorted(members)})))))
    return output, universes


def executive_changes(fetch, config, start, end):
    """单批原证券表/公司映射/事件完整页，共用原Fetcher和发布事务。"""
    with BaostockClient(fetch, min(fetch.timeout, config.get('timeout_seconds', fetch.timeout))) as client:
        fields, values = client.table('stock_basic')
        listings = shsz_listings(fields, values, check=fetch.budget.remaining)
    _need(len(listed_codes(listings, end, check=fetch.budget.remaining)) >= config['minimum_universe'], 'universe_incomplete')
    scope = config.get('scope', 'shsz');aliases = {};bse_sha = None
    if scope == 'ashare':
        from .bse_universe import listings as bse_universe
        bse_listings, aliases, bse_sha = bse_universe(fetch, config['bse_history'], as_of=end,
            minimum=config['minimum_bse_universe'])
        listings.update(bse_listings)
    periods = tuple(f'{year}-12-31' for year in config['reports'])
    _need(all(period < end for period in periods), 'identity_report_not_completed')
    # 最新财报列表会移除退市公司；身份同样沿已验证保留退市报告的财务摘要源。
    company_rows = []
    for period in periods:
        company_rows.extend(report_pages(fetch, config['url'], report=COMPANY_REPORT, columns=COMPANY_COLUMNS,
            filters=f'(REPORT_DATE=\'{period}\')(SECURITY_TYPE_CODE in ("058001001","058001008"))',
            sort='SECUCODE', max_pages=config['max_pages'], error_prefix='executive_identity_report'))
    rows = report_pages(fetch, config['url'], report=REPORT, columns=COLUMNS,
        filters=f'(CHANGE_DATE>=\'{start}\')(CHANGE_DATE<=\'{end}\')(HOLD_TYPE="A股")',
        sort='GGEID', max_pages=config['max_pages'], allow_empty=True, decimal_numbers=True, error_prefix='executive_report')
    calculated, universes = aggregate_changes(rows, listings, company_rows, periods, start, end,
        check=fetch.budget.remaining, aliases=aliases)
    if scope == 'ashare':
        for row, universe in zip(calculated, universes):
            bse_count = sum(code.startswith('bj.') for code in universe['members'])
            row.update(bse_market_count=bse_count, shsz_market_count=row['market_stock_count']-bse_count,
                universe_confirmed_through=config['bse_history']['verified_through'])
            universe.update(source_bse_sha256=bse_sha, bse_market_count=bse_count,
                history_confirmed_through=config['bse_history']['verified_through'])
    return {**rows_for_metrics(calculated, scope=scope), 'source.executive_'+scope+'_universe': universes}
