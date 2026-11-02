"""公开年报全页适配；原Fetcher、证券表准入和目录继续拥有来源与发布。"""

from datetime import date
from decimal import Decimal, InvalidOperation
import math
import re

from .baostock_source import BaostockClient
from .source_fetch import SourceFailure
from .financial_universe import universes_for_reports
from .provider_reports import report_pages


REPORT = 'RPT_F10_FINANCE_MAINFINADATA'
COLUMNS = ('SECUCODE,SECURITY_CODE,ORG_CODE,REPORT_DATE,NOTICE_DATE,UPDATE_DATE,'
           'CURRENCY,EPSJB,ROEJQ,SECURITY_TYPE_CODE')
METRICS = {'earnings.eps.shsz': 'EPSJB', 'earnings.roe.shsz': 'ROEJQ'}
ASHARE_METRICS = {key.replace('.shsz','.ashare'):value for key,value in METRICS.items()}


def _day(value):
    # 供应商只核实到日期，保留日精度；页面不推定午夜公布。
    if type(value) is not str or re.fullmatch(r'\d{4}-\d{2}-\d{2}(?: 00:00:00)?', value) is None:
        raise SourceFailure('financial_report_date')
    try:
        return date.fromisoformat(value[:10]).isoformat()
    except ValueError:
        raise SourceFailure('financial_report_date') from None


def _number(value):
    if value is None:
        return None
    if type(value) not in (int, float):
        raise SourceFailure('financial_report_number')
    try:
        result = Decimal(str(value))
        if not result.is_finite() or not math.isfinite(float(result)):
            raise ValueError()
        return result
    except (InvalidOperation, ValueError, OverflowError):
        raise SourceFailure('financial_report_number') from None


def annual_values(rows, members, period, as_of, *, check=lambda: None, metrics=None, aliases=None):
    """当年末已准入股票池的人民币普通A股等权年报均值。

    负EPS/ROE保留；缺报告、未披露/未来修订、非人民币及空数值分别计数。
    CDR每份与普通股每股基准不同，明确排除。历史值为本次可得的修订年报，
    当时可得性保持未知，不能用于因果回测。
    """
    check();metrics=METRICS if metrics is None else metrics;aliases=aliases or {}
    if len(rows)>8000 or len(members)>20000:
        raise SourceFailure('financial_report_capacity')
    indexed = {};original_codes=set()
    companies = {}
    for row in rows:
        check()
        if _day(row.get('REPORT_DATE')) != period:
            raise SourceFailure('financial_report_period')
        code = row.get('SECUCODE')
        # 报告全集也含A开头的申报编号；只有权威上市池中的数字证券进入均值。
        if type(code) is not str or re.fullmatch(r'[A-Z0-9]{6}\.(SH|SZ|BJ)', code) is None:
            raise SourceFailure('financial_report_identity')
        if code[:6] != row.get('SECURITY_CODE') or code in original_codes:
            raise SourceFailure('financial_report_duplicate')
        original_codes.add(code)
        # 原始两处身份先严格准入，再换成财务连接身份；保留换码前的冲突证据。
        if code.endswith('.BJ') and code[:6] in aliases:
            symbol=aliases[code[:6]];code=symbol+'.BJ'
            row={**row,'SECURITY_CODE':symbol,'SECUCODE':code}
        if code in indexed:
            raise SourceFailure('financial_report_duplicate')
        indexed[code] = row
    selected = {}
    counts = dict(market_count=len(members), cdr_excluded_count=0, alias_excluded_count=0, missing_report_count=0,
                  not_available_count=0, currency_missing_count=0)
    latest_notice = latest_revision = None
    for member in sorted(members):
        check()
        exchange, symbol = member.split('.')
        row = indexed.get(symbol + '.' + exchange.upper())
        if row is None:
            counts['missing_report_count'] += 1
            continue
        if row.get('SECURITY_TYPE_CODE') == '058001008':
            counts['cdr_excluded_count'] += 1
            continue
        if row.get('SECURITY_TYPE_CODE') != '058001001':
            raise SourceFailure('financial_report_security_type')
        company = row.get('ORG_CODE')
        if type(company) is not str or not company or len(company) > 40:
            raise SourceFailure('financial_report_company_identity')
        facts = {key: row.get(key) for key in COLUMNS.split(',') if key not in ('SECUCODE','SECURITY_CODE')}
        if company in companies:
            if companies[company] != facts:
                raise SourceFailure('financial_report_company_conflict')
            counts['alias_excluded_count'] += 1
            continue
        companies[company] = facts
        notice, revision = _day(row.get('NOTICE_DATE')), _day(row.get('UPDATE_DATE'))
        if notice < period or revision < notice:
            raise SourceFailure('financial_report_date_order')
        if notice > as_of or revision > as_of:
            counts['not_available_count'] += 1
            continue
        if row.get('CURRENCY') != 'CNY':
            counts['currency_missing_count'] += 1
            continue
        selected[member] = {key: _number(row.get(field)) for key, field in metrics.items()}
        latest_notice = max(notice, latest_notice or notice)
        latest_revision = max(revision, latest_revision or revision)
    output = {}
    eligible = len(members) - counts['cdr_excluded_count'] - counts['alias_excluded_count']
    for metric in metrics:
        values = [row[metric] for row in selected.values() if row[metric] is not None]
        mean = float(sum(values) / len(values)) if values else None
        if mean is not None and not math.isfinite(mean):
            raise SourceFailure('financial_mean_nonfinite')
        output[metric] = dict(date=period, mean=mean, complete_market_mean=mean if len(values)==eligible else None,
            valid_count=len(values), eligible_count=eligible, missing_count=eligible-len(values),
            empty_value_count=len(selected)-len(values), latest_announcement_day=latest_notice,
            latest_revision_day=latest_revision, **counts)
    return output


def annual_reports(fetch, config, start, end, *, admitted_rows=()):
    """取当次可得财报；成员由单一年度事实准备层提供，已准入事实按年核同。"""
    from .financial_models import METRICS as DEFINITIONS
    scope=config.get('scope','shsz')
    fields_by_metric=METRICS if scope=='shsz' else ASHARE_METRICS
    periods=[f'{year}-12-31' for year in config['reports']]
    facts=universes_for_reports(fetch,config,periods,end,admitted_rows,basic_client=BaostockClient)
    selected = set(config['datasets']) & set(DEFINITIONS)
    output = {key: [] for key in sorted(selected)}
    universes = []
    for period in periods:
        fetch.budget.remaining()
        fact=facts[period];universe=fact['row'];members=set(universe['members'])
        rows = report_pages(fetch, config['url'], report=REPORT, columns=COLUMNS,
            filters=f'(REPORT_DATE=\'{period}\')(SECURITY_TYPE_CODE in ("058001001","058001008"))',
            sort='SECUCODE', max_pages=config['max_pages'])
        calculated = annual_values(rows, members, period, end, check=fetch.budget.remaining,
            metrics=fields_by_metric,aliases=fact['aliases'])
        if scope=='ashare':
            bse_count=sum(member.startswith('bj.') for member in members)
            for row in calculated.values():
                row.update(bse_market_count=bse_count,shsz_market_count=len(members)-bse_count,
                    universe_confirmed_through=universe['history_confirmed_through'])
        for key in selected:
            output[key].append(calculated[key])
        universes.append(dict(universe))
    return {**output, 'source.financial_'+scope+'_universe': universes}
