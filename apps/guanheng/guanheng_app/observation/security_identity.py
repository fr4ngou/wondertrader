"""公开证券编号、报告期及公司身份准入；高管与全市场股票池共用。"""
from datetime import date
import re
from .source_fetch import SourceFailure


def require(value,code):
    """身份源已公开的错误码保持，新增消费者复用同一事实约束。"""
    if not value:raise SourceFailure('executive_'+code)


def company_id(value):
    require(type(value) is str and re.fullmatch(r'[A-Za-z0-9_-]{1,40}',value),'company_identity')
    return value


def security_code(row,field,*,filing=False):
    code=row.get(field)
    pattern=r'[A-Z0-9]{6}\.(SH|SZ|BJ)' if filing else r'\d{6}\.(SH|SZ|BJ)'
    require(type(code) is str and re.fullmatch(pattern,code),'security_identity')
    require(row.get('SECURITY_CODE')==code[:6],'security_identity')
    return code[-2:].lower()+'.'+code[:6]


def canonical(code,aliases):
    return 'bj.'+aliases.get(code[3:],code[3:]) if code.startswith('bj.') else code


def report_rows(rows,periods,aliases,*,check):
    """先核原两处证券号，再核换码身份；类别和公司归属由使用者分别准入。"""
    require(len(rows)<=40000 and 1<=len(periods)<=5,'capacity')
    seen,canonical_seen=set(),set()
    for row in rows:
        check()
        value=row.get('REPORT_DATE')
        require(type(value) is str and re.fullmatch(r'\d{4}-\d{2}-\d{2}(?: 00:00:00)?',value),'date')
        try:period=date.fromisoformat(value[:10]).isoformat()
        except ValueError:raise SourceFailure('executive_date') from None
        require(period in periods,'identity_report_period')
        code=security_code(row,'SECUCODE',filing=True)
        require((code,period) not in seen,'identity_duplicate')
        seen.add((code,period))
        code=canonical(code,aliases)
        require((code,period) not in canonical_seen,'identity_duplicate')
        canonical_seen.add((code,period))
        yield code,period,row


def security_type(row):
    value=row.get('SECURITY_TYPE_CODE')
    return value if value in ('058001001','058001008') else None
