"""同一公开报表服务的完整分页；保留来源计数、原字节及原绝对截止。"""
from decimal import Decimal
import json
import re

from .source_fetch import SourceFailure

SHAREHOLDER_REPORT_MARKETS = frozenset(('二级市场', '大宗交易', '二级市场以及大宗交易'))
SHAREHOLDER_REPORT_KEY = ('NOTICE_DATE', 'SECURITY_CODE', 'HOLDER_NAME', 'END_DATE', 'START_DATE', 'CHANGE_NUM_SYMBOL', 'MARKET', 'EITIME')


def report_pages(fetch, url, *, report, columns, filters, sort, max_pages,
                 allow_empty=False, empty_error=None, decimal_numbers=False, error_prefix='financial_report'):
    """完整返回有限截面；计数/页数漂移、缺行和未知空回复终止本来源。

    金额适配器在JSON边界选择Decimal，避免先经二进制浮点损失原十进制值。
    allow_empty接纳成功零计数；empty_error可登记已核实的供应商空结果码和消息。
    sort为逗号分隔的唯一字段名，各字段统一升序；具体来源负责选择稳定的
    唯一排序组合并核业务身份。排序字段与方向的数量在本适配器统一对齐。
    """
    fields=sort.split(',') if type(sort) is str else []
    if (not fields or not 1<=len(sort)<=1024
            or any(re.fullmatch('[A-Za-z_][A-Za-z0-9_]{0,127}',field) is None for field in fields)
            or len(set(fields))!=len(fields)):
        raise SourceFailure(error_prefix+'_sort')
    order=1 if len(fields)==1 else ','.join('1' for field in fields)
    expected, rows = None, []
    for page in range(1, max_pages+1):
        fetch.budget.remaining()
        raw = json.loads(fetch.get(url, dict(reportName=report, columns=columns, filter=filters,
            sortColumns=sort, sortTypes=order, pageNumber=page, pageSize=500, source='WEB', client='WEB')),
            parse_float=Decimal if decimal_numbers else float)
        result = raw.get('result')
        if (empty_error is not None and page == 1 and raw.get('success') is False
                and 'result' in raw and result is None and (raw.get('code'), raw.get('message')) == empty_error):
            return []
        if raw.get('success') is not True or type(result) is not dict:
            raise SourceFailure(error_prefix+'_unavailable')
        count, pages, data = result.get('count'), result.get('pages'), result.get('data')
        if allow_empty and page == 1 and type(count) is int and count == 0 and type(pages) is int and pages == 0 and data == []:
            return []
        if (type(count) is not int or not 0 < count <= 500*max_pages
                or type(pages) is not int or pages != (count+499)//500
                or type(data) is not list or len(data) != min(500, count-(page-1)*500)
                or any(type(row) is not dict for row in data)):
            raise SourceFailure(error_prefix+'_pagination')
        if expected is not None and expected != (count, pages):
            raise SourceFailure(error_prefix+'_changed')
        expected = count, pages
        rows.extend(data)
        if page == pages:
            return rows
    raise SourceFailure(error_prefix+'_page_budget')
