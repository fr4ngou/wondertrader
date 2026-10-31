"""同一公开报表服务的完整分页；保留来源计数、原字节及原绝对截止。"""
from decimal import Decimal
import json

from .source_fetch import SourceFailure


def report_pages(fetch, url, *, report, columns, filters, sort, max_pages,
                 allow_empty=False, decimal_numbers=False, error_prefix='financial_report'):
    """完整返回有限截面；计数/页数漂移、缺行和未知空回复终止本来源。

    金额适配器在JSON边界选择Decimal，避免先经二进制浮点损失原十进制值。
    只有服务明确返回success及零计数时，allow_empty才授予已知空结果。
    """
    expected, rows = None, []
    for page in range(1, max_pages+1):
        fetch.budget.remaining()
        raw = json.loads(fetch.get(url, dict(reportName=report, columns=columns, filter=filters,
            sortColumns=sort, sortTypes=1, pageNumber=page, pageSize=500, source='WEB', client='WEB')),
            parse_float=Decimal if decimal_numbers else float)
        result = raw.get('result')
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
