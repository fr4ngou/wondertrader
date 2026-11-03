"""SGX A50原官方月末持仓与整月成交；公开目录及原PDF列为唯一数字来源。"""
import calendar
from datetime import date, datetime
import io
import json
import re
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from .source_fetch import SourceFailure


CONFIG_URL = 'https://www.sgx.com/config/appconfig.json'
CMS_URL = 'https://api2.sgx.com/content-api'
ZONE = ZoneInfo('Asia/Singapore')
MONTHS = ('January February March April May June July August September October November December').split()
ABBREVIATIONS = [month[:3] for month in MONTHS]
COLUMNS = re.compile(r'FY\d{4}\s+Q[1-4]|(?:' + '|'.join(ABBREVIATIONS)
                     + r')\s+\d{4}|[FC]YTD\s+\d{4}|YoY%')
TABLES = {'oi': 'Equity Index Futures Month-End Open Interest', 'volume': 'Equity Index Futures Volume'}


def _json(fetch, url, params=None):
    try:
        data = json.loads(fetch.get(url, params))
        if type(data) is not dict or data.get('errors'):
            raise ValueError('response')
        return data
    except (ValueError, TypeError, UnicodeError) as exc:
        raise SourceFailure('sgx_monthly_response') from exc


def report_period(title):
    """官方目录英文月份标题决定统计月末；目录发布日期独立于该期次。"""
    match = re.fullmatch(r'(' + '|'.join(MONTHS) + r') (\d{4})', title)
    if match is None:
        raise SourceFailure('sgx_monthly_report_identity')
    month, year = MONTHS.index(match[1]) + 1, int(match[2])
    try:
        return date(year, month, calendar.monthrange(year, month)[1]).isoformat()
    except ValueError as exc:
        raise SourceFailure('sgx_monthly_report_identity') from exc


def table_value(text, table, title):
    """目标月份列与整数合约数逐项配对，季度/年度/上年同期列保持独立。"""
    lines = [' '.join(line.split()) for line in text.splitlines() if line.strip()]
    if f'SGX Monthly Market Statistics {title}' not in lines or table not in lines:
        return None
    start = lines.index(table) + 1
    if start >= len(lines):
        raise SourceFailure('sgx_monthly_table_schema')
    header = lines[start]
    columns = COLUMNS.findall(header)
    if not columns or ''.join(header.split()) != ''.join(''.join(c.split()) for c in columns):
        raise SourceFailure('sgx_monthly_table_schema')
    month, year = title.split()
    target = month[:3] + ' ' + year
    columns = [' '.join(column.split()) for column in columns]
    if columns.count(target) != 1:
        raise SourceFailure('sgx_monthly_table_schema')
    matches = [line for line in lines[start+1:] if line.startswith('SGX FTSE China A50 Index Futures ')]
    # 同一表跨多页重复表头；整份PDF必须各找到一次A50行，续页可无该产品。
    if not matches:
        return None
    if len(matches) != 1:
        raise SourceFailure('sgx_monthly_table_schema')
    cells = matches[0].removeprefix('SGX FTSE China A50 Index Futures ').split()
    if len(cells) != len(columns):
        raise SourceFailure('sgx_monthly_table_schema')
    value = cells[columns.index(target)]
    if re.fullmatch(r'(?:\d{1,3}(?:,\d{3})+|\d+)', value) is None:
        raise SourceFailure('sgx_monthly_contract_quantity')
    quantity = int(value.replace(',', ''))
    if quantity > 2**53 - 1:
        raise SourceFailure('sgx_monthly_contract_quantity')
    return quantity


def report_pdf(body, title, budget):
    """原PDF有界读取；页面/文本检查共用原D，非协作库调用由原采集Job约束。"""
    budget.remaining()
    if not body.startswith(b'%PDF-') or len(body) > min(16*1024*1024, budget.response_bytes):
        raise SourceFailure('sgx_monthly_pdf_budget_or_format')
    from pypdf import PdfReader
    try:
        with io.BytesIO(body) as stream:
            document = PdfReader(stream, strict=True)
            try:
                budget.remaining()
                if document.is_encrypted:
                    raise SourceFailure('sgx_monthly_pdf_encrypted')
                if sum(len(items) for items in document.xref.values()) + len(document.xref_objStm) > 100000:
                    raise SourceFailure('sgx_monthly_pdf_budget_or_format')
                declared = document.root_object['/Pages'].get('/Count')
                if not isinstance(declared, int) or isinstance(declared, bool) or not 1 <= declared <= 80:
                    raise SourceFailure('sgx_monthly_pdf_budget_or_format')
                result, size, pages = {}, 0, 0
                for pages, page in enumerate(document.pages, 1):
                    budget.remaining()
                    if pages > 80:
                        raise SourceFailure('sgx_monthly_pdf_budget_or_format')
                    text = page.extract_text() or ''
                    budget.remaining()
                    size += len(text.encode('utf8'))
                    if size > 4*1024*1024:
                        raise SourceFailure('sgx_monthly_pdf_text_budget')
                    for field, table in TABLES.items():
                        value = table_value(text, table, title)
                        if value is not None:
                            if field in result:
                                raise SourceFailure('sgx_monthly_table_schema')
                            result[field], result[field+'_page'] = value, pages
                if pages != declared or not {'oi','volume'} <= set(result):
                    raise SourceFailure('sgx_monthly_table_schema')
                period = report_period(title)
                return dict(date=period, **result, report_file='sgx_'+period[:7].replace('-', '')+'.pdf',
                            basis_points=None, available_at=None)
            finally:
                document.close()
    except SourceFailure:
        raise
    except Exception:
        raise SourceFailure('sgx_monthly_pdf_invalid') from None


def monthly(fetch, config, start, end):
    """独立月频游标→官网目录→本期原PDF；不借日频合成整月成交。"""
    if config.get('url') != CONFIG_URL or config.get('datasets') != ['sgx_a50_monthly']:
        raise SourceFailure('sgx_monthly_configuration')
    try:
        application = _json(fetch, CONFIG_URL)
        version = application['CMS_VERSION']
        if (type(version) is not str or re.fullmatch('[a-f0-9]{40}', version) is None
                or application['endpoints']['CMS_API_URL'] != CMS_URL):
            raise SourceFailure('sgx_monthly_configuration')
        rows, seen, count, previous = [], set(), None, None
        limit = 24
        max_pages = config.get('max_pages', 4)
        if type(max_pages) is not int or not 1 <= max_pages <= 16:
            raise SourceFailure('sgx_monthly_configuration')
        for page in range(max_pages):
            variables = dict(lang='EN', limit=limit, offset=page*limit,
                fromStartDate=start+'T00:00:00.000Z', fromStartDateFilterEnabled=True)
            data = _json(fetch, CMS_URL, dict(queryId=version+':market_statistics_reports_list',
                variables=json.dumps(variables, separators=(',', ':'))))['data']['list']
            total, reports = data['count'], data['results']
            if (type(total) is not int or not 0 < total <= 10000 or type(reports) is not list
                    or len(reports) != min(limit, total-page*limit) or not reports
                    or (count is not None and total != count)):
                raise SourceFailure('sgx_monthly_pagination')
            count = total
            for item in reports:
                fetch.budget.remaining()
                report = item['data']
                title = report['title']
                period = report_period(title)
                if period in seen or (previous is not None and period >= previous):
                    raise SourceFailure('sgx_monthly_pagination')
                previous = period
                seen.add(period)
                publication = report['reportDate']
                media = report['report']['data']
                modified = media['date']
                if (type(publication) is not int or type(modified) is not int
                        or publication <= 0 or modified <= 0):
                    raise SourceFailure('sgx_monthly_report_identity')
                known = max(datetime.fromtimestamp(value, ZONE).date().isoformat()
                            for value in (publication, modified))
                if not start <= period <= end or known > end:
                    continue
                file = media['file']['data']
                url = file['url']
                parts = urlsplit(url)
                if (file['filemime'] != 'application/pdf' or parts.scheme != 'https'
                        or parts.netloc != 'api2.sgx.com' or parts.query or parts.fragment
                        or not parts.path.startswith('/sites/default/files/') or not parts.path.endswith('.pdf')):
                    raise SourceFailure('sgx_monthly_report_identity')
                rows.append(report_pdf(fetch.get(url), title, fetch.budget))
            if previous < start or (page+1)*limit >= total:
                return {'sgx_a50_monthly': sorted(rows, key=lambda row: row['date'])}
        raise SourceFailure('sgx_monthly_listing_coverage_incomplete')
    except SourceFailure:
        raise
    except (ValueError, KeyError, TypeError, OverflowError, UnicodeError):
        raise SourceFailure('sgx_monthly_response') from None
