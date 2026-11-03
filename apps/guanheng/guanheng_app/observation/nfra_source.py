"""金融监管总局原寿险/财险季度资金运用表；原字段、亿元及债券比例保持。"""
from calendar import monthrange
from datetime import date, datetime
import io
import json
import math
import re
from urllib.parse import urlsplit

from .source_fetch import SourceFailure


BASE = 'https://www.nfra.gov.cn'
LIST_URL = BASE + '/cn/static/data/DocInfo/SelectDocByItemIdAndChild/'
TITLE = re.compile(r'(\d{4})年([一二三四])季度保险公司资金运用情况表')
METRICS = {'财产险公司': 'holdings_property', '人身险公司': 'holdings_life'}


def _json(fetch, url):
    body = fetch.get(url)
    try:
        value = json.loads(body)
        if value['rptCode'] != 200 or type(value['data']) is not dict:
            raise ValueError('response')
        return value['data']
    except (ValueError, KeyError, TypeError, UnicodeError) as exc:
        raise SourceFailure('nfra_response_schema') from exc


def _period(title):
    match = TITLE.fullmatch(title)
    if match is None:
        return None
    year, quarter = int(match[1]), '一二三四'.index(match[2]) + 1
    month = quarter * 3
    return date(year, month, monthrange(year, month)[1]).isoformat()


def parse_workbook(body, title, published, budget):
    """仅接受原官方四列表；金额保留原数值，比例沿原债券/同类余额公式。"""
    try:
        import xlrd
    except ImportError as exc:
        raise SourceFailure('nfra_xls_dependency_missing') from exc
    if len(body) > 2 * 1024 * 1024 or not body.startswith(bytes.fromhex('d0cf11e0a1b11ae1')):
        raise SourceFailure('nfra_workbook_schema')
    book = None
    try:
        budget.remaining()
        book = xlrd.open_workbook(file_contents=body, on_demand=True, logfile=io.StringIO())
        if book.nsheets != 1:
            raise ValueError('sheets')
        sheet = book.sheet_by_index(0)
        if not 15 <= sheet.nrows <= 100 or sheet.ncols != 4:
            raise ValueError('shape')
        rows = [sheet.row_values(i) for i in range(sheet.nrows)]
        clean = lambda value: re.sub(r'\s+', '', str(value))
        if clean(rows[0][0]) != title or clean(rows[1][3]) != '单位：亿元，%':
            raise ValueError('title/unit')
        if [clean(v) for v in rows[3]] != ['机构类别/指标', '', '账面余额', '占比']:
            raise ValueError('columns')
        result, current, totals, bonds = {}, None, {}, {}
        for row in rows[4:]:
            budget.remaining()
            institution, label = clean(row[0]).removeprefix('其中：'), clean(row[1])
            if institution:
                current = METRICS.get(institution)
            if current is None:
                continue
            if label not in ('资金运用余额', '债券'):
                continue
            amount, ratio = row[2:]
            if any(type(v) not in (int, float) or not math.isfinite(v) for v in (amount, ratio)):
                raise ValueError('numbers')
            target = totals if label == '资金运用余额' else bonds
            if current in target or amount <= 0 or not 0 <= ratio <= 1:
                raise ValueError('duplicate/range')
            target[current] = (amount, ratio)
        if set(totals) != set(METRICS.values()) or set(bonds) != set(totals):
            raise ValueError('institutions')
        for metric in totals:
            total, total_ratio = totals[metric]
            bond, official_ratio = bonds[metric]
            ratio = bond / total
            if total_ratio != 1 or bond > total or abs(ratio - official_ratio) > 1e-10:
                raise ValueError('ratio')
            result[metric] = dict(date=_period(title), total=total, bonds=bond,
                                  bond_pct=ratio * 100, available_at=published)
        return result
    except SourceFailure:
        raise
    except (ValueError, TypeError, IndexError, xlrd.XLRDError) as exc:
        raise SourceFailure('nfra_workbook_schema') from exc
    finally:
        if book is not None:
            book.release_resources()


def history(fetch, config, start, end):
    """官网原分页识别期次并读取原XLS；两类原子返回，全部工作服从原批次D。"""
    result = {metric: [] for metric in METRICS.values()}
    seen, publications, total = set(), [], None
    try:
        for page in range(1, config['max_pages'] + 1):
            listing = _json(fetch, LIST_URL + f'data_itemId=954,pageIndex={page},pageSize=18.json')
            count, rows = listing['total'], listing['rows']
            if type(count) is not int or count <= 0 or type(rows) is not list or not rows or len(rows) > 18:
                raise ValueError('listing')
            if total is not None and count != total:
                raise ValueError('listing changed')
            total = count
            for row in rows:
                fetch.budget.remaining()
                doc, title, published = row['docId'], row['docTitle'], row['publishDate']
                if type(doc) is not int or doc <= 0 or doc in seen or type(title) is not str:
                    raise ValueError('document')
                timestamp = datetime.strptime(published, '%Y-%m-%d %H:%M:%S')
                if timestamp.strftime('%Y-%m-%d %H:%M:%S') != published:
                    raise ValueError('publication date')
                if publications and published > publications[-1]:
                    raise ValueError('listing order')
                seen.add(doc)
                publications.append(published)
                period = _period(title)
                if period is None or not start <= period <= end or published[:10] > end:
                    continue
                detail = _json(fetch, BASE + f'/cn/static/data/DocInfo/SelectByDocId/data_docId={doc}.json')
                if (detail['docId'], detail['docTitle'], detail['publishDate']) != (doc, title, published):
                    raise ValueError('detail identity')
                attachments = detail['attachmentInfoVOList']
                candidates = [a for a in attachments if a.get('title') == title + '.xls']
                if len(candidates) != 1:
                    raise ValueError('attachment')
                path = candidates[0]['urlOtherName']
                parts = urlsplit(path)
                if parts.scheme or parts.netloc or parts.query or parts.fragment or not re.fullmatch(
                        r'/chinese/docfile/\d{4}/[a-f0-9]{32}\.xls', path):
                    raise ValueError('attachment path')
                values = parse_workbook(fetch.get(BASE + path), title, published, fetch.budget)
                for metric, value in values.items():
                    if any(old['date'] == period for old in result[metric]):
                        raise ValueError('duplicate period')
                    result[metric].append(value)
            if publications[-1][:10] < start or page * 18 >= total:
                break
        else:
            raise SourceFailure('nfra_listing_coverage_incomplete')
        return {key: sorted(rows, key=lambda row: row['date']) for key, rows in result.items()}
    except SourceFailure:
        raise
    except (KeyError, TypeError, ValueError, UnicodeError) as exc:
        raise SourceFailure('nfra_response_schema') from exc
