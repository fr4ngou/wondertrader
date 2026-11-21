"""公开市场补充事实适配；请求、预算、缓存及原件存储由注入的 get 拥有。"""
from __future__ import annotations

from bisect import bisect_left
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, localcontext
import hashlib
import io
import json
import re
import xml.etree.ElementTree as ET
import zipfile
import zlib

from ..guanheng_market_client.supplement_facts import (
    CSI300_INDEX, INDEX_FREE_FLOAT_CAP, INDEX_TURNOVER, IPO_PROCEEDS, MARGIN_PURCHASE, MARGIN_REPORT,
    MARGIN_SUMMARY_FIELDS, SHENWAN_FIELDS, SH_SZ_SCOPE, SIGNED_MARGIN_SUMMARY, SIGNED_REPORT_METRICS, SMALL_CAP_INDEX,
)

class SourceUnavailable(RuntimeError):
    """固定原因的缺事实结果；调用者保留缺口，原供应商正文不进入异常。"""

    def __init__(self, code: str):
        self.code = code  # 固定 ASCII 原因，供采集 owner 写入缺口；不含原始响应。
        super().__init__(code)


_SSE = 'https://query.sse.com.cn/commonQuery.do'
_SZSE = 'http://www.szse.cn/api/report/ShowReport/data'
_EM = 'https://datacenter-web.eastmoney.com/api/data/v1/get'
_SSE_REF = 'https://www.sse.com.cn/'
_SZSE_REF = 'https://www.szse.cn/market/fund/volume/etf/index.html'
_MAX_PAGES = 100
_MAX_ROWS = 20000
_SZSE_EXPORT = 'http://www.szse.cn/api/report/ShowReport'
_XLSX_XML_BYTES = 16 * 1024 * 1024
_CSI_DAILY_REPORT = ('https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/'
                     'researches/files/zh_CN/csiindexdailyreport{}.pdf')
_CSI_PERFORMANCE = 'https://www.csindex.com.cn/csindex-home/perf/index-perf'


def _fail(code):
    raise SourceUnavailable(code) from None


def _integer(value, maximum=_MAX_ROWS):
    if type(value) is int:
        result = value
    elif type(value) is str and re.fullmatch(r'[0-9]{1,8}', value):
        result = int(value)
    else:
        _fail('source_pagination_invalid')
    if not 0 <= result <= maximum:
        _fail('source_pagination_invalid')
    return result


def _number(value, *, signed=False):
    if type(value) not in (str, int, Decimal):
        _fail('source_value_invalid')
    text = str(value)
    if len(text) > 256:
        _fail('source_value_invalid')
    if ',' in text:
        if not re.fullmatch(r'-?[0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]+)?', text):
            _fail('source_value_invalid')
        text = text.replace(',', '')
    try:
        result = Decimal(text)
    except InvalidOperation:
        _fail('source_value_invalid')
    # 原字段解析有界，避免有限但极端指数被展开为无界的目录字符串。
    if not result.is_finite() or (not signed and result < 0) or abs(result.adjusted()) > 128:
        _fail('source_value_invalid')
    return result


def _utc(value):
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
            raise ValueError
        return parsed
    except (TypeError, ValueError, AttributeError):
        _fail('source_receipt_invalid')


def _constant(value):
    raise ValueError


def _receipt(get, url, params, referer):
    # 运输异常由 owner 分类；这里不截获其取消、总截止及未知请求语义。
    receipt = get(url, params, referer)
    if type(receipt) is not dict or type(receipt.get('body')) is not bytes:
        _fail('source_receipt_invalid')
    raw, parent = receipt['body'], receipt.get('sha256')
    if (type(parent) is not str or re.fullmatch(r'[0-9a-f]{64}', parent) is None
            or hashlib.sha256(raw).hexdigest() != parent):
        _fail('source_receipt_invalid')
    received = receipt.get('received_at')
    _utc(received)
    return raw, parent, received


def _read(get, url, params, referer):
    raw, parent, received = _receipt(get, url, params, referer)
    try:
        data = json.loads(raw.decode('utf-8'), parse_float=Decimal, parse_constant=_constant)
    except (UnicodeError, ValueError):
        _fail('source_json_invalid')
    return data, parent, received


def _xlsx_table(raw):
    """读取官方XLSX表格；按份直接保留十进制，ZIP/XML容量在解压前准入。

    不执行公式或解压到文件系统。inline/shared文本及数字单元共用一条路径，
    来源表头决定业务单位，基金规模(份)与JSON万份各有独立合同。
    """
    ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            members = archive.infolist()
            names = [m.filename for m in members]
            if (len(members) > 64 or len(set(names)) != len(names)
                    or sum(m.file_size for m in members) > _XLSX_XML_BYTES
                    or any(m.flag_bits & 1 for m in members)):
                _fail('source_xlsx_capacity')
            def xml(name):
                body = archive.read(name)
                if b'<!DOCTYPE' in body or b'<!ENTITY' in body:
                    _fail('source_xlsx_invalid')
                return ET.fromstring(body)
            if 'xl/workbook.xml' not in names or 'xl/worksheets/sheet1.xml' not in names:
                _fail('source_xlsx_invalid')
            strings = []
            if 'xl/sharedStrings.xml' in names:
                strings = [''.join(node.itertext()) for node in xml('xl/sharedStrings.xml').findall('s:si', ns)]
                if len(strings) > _MAX_ROWS * 4 or any(len(s) > 512 for s in strings):
                    _fail('source_xlsx_capacity')
            sheet = xml('xl/worksheets/sheet1.xml')
            result = []
            for row in sheet.findall('s:sheetData/s:row', ns):
                values = {}
                for cell in row.findall('s:c', ns):
                    ref = cell.get('r', '')
                    match = re.fullmatch(r'([A-Z]{1,2})[0-9]+', ref)
                    if match is None or cell.find('s:f', ns) is not None:
                        _fail('source_xlsx_invalid')
                    column = 0
                    for char in match[1]:column = column * 26 + ord(char) - 64
                    if column > 16 or column in values:
                        _fail('source_xlsx_invalid')
                    kind = cell.get('t')
                    text = cell.findtext('s:v', default='', namespaces=ns)
                    if kind == 'inlineStr':
                        inline = cell.find('s:is', ns)
                        text = ''.join(inline.itertext()) if inline is not None else ''
                    elif kind == 's':
                        index = int(text)
                        if not 0 <= index < len(strings):_fail('source_xlsx_invalid')
                        text = strings[index]
                    elif kind not in (None, 'n', 'str'):
                        _fail('source_xlsx_invalid')
                    if len(text) > 512:_fail('source_xlsx_capacity')
                    values[column] = text
                if values and any(values.values()):
                    result.append([values.get(i, '') for i in range(1, max(values) + 1)])
                if len(result) > _MAX_ROWS + 1:_fail('source_xlsx_capacity')
            return result
    except SourceUnavailable:
        raise
    except (zipfile.BadZipFile, ET.ParseError, KeyError, ValueError, OSError, RuntimeError, NotImplementedError, zlib.error, EOFError):
        _fail('source_xlsx_invalid')


def _fact(value, unit, source, receipts, *, signed=False):
    with localcontext() as context:
        context.prec = 300
        text = format(value, 'f')
    if '.' in text:
        text = text.rstrip('0').rstrip('.')
    if value == 0:
        text = '0'
    # 缩放后的标准值必须在持久化前满足目录容量；超界原件保留为可重取缺口。
    pattern = r'-?[0-9]+(?:\.[0-9]+)?' if signed else r'[0-9]+(?:\.[0-9]+)?'
    if len(text) > 128 or re.fullmatch(pattern, text) is None:
        _fail('source_value_invalid')
    return {
        'value': text,  # 有限十进制原精度值；只对已声明允许负数的金额保留负号。
        'unit': unit,  # 基金份额 share、人民币元 CNY 或年化百分数 pct。
        'source': source,  # 具体供应商；双市场合成保留两个原件身份。
        'parents': [item[0] for item in receipts],  # 原始字节 SHA256，顺序为实际依赖顺序。
        'received_at': max((item[1] for item in receipts), key=_utc),  # 全部输入收到后的 UTC 时刻。
    }


def _sse_page(data, day):
    if (type(data) is not dict or data.get('actionErrors') or data.get('fieldErrors')
            or type(data.get('result')) is not list):
        _fail('source_schema_invalid')
    rows = data['result']
    if len(rows) > _MAX_ROWS or any(type(row) is not dict for row in rows):
        _fail('source_schema_invalid')
    if any(row.get('STAT_DATE') != day for row in rows):
        _fail('source_date_mismatch')
    return rows


def _sse_shares(code, day, get):
    receipts, rows = [], []
    expected = None
    pages = 1
    for page in range(1, _MAX_PAGES + 1):
        if page > pages:
            break
        params = dict(isPagination='true', sqlId='COMMON_SSE_ZQPZ_ETFZL_XXPL_ETFGM_SEARCH_L', STAT_DATE=day)
        params.update({'pageHelp.pageSize': '10000', 'pageHelp.pageNo': str(page),
                       'pageHelp.beginPage': str(page), 'pageHelp.cacheSize': '1',
                       'pageHelp.endPage': str(page)})
        data, parent, received = _read(get, _SSE, params, _SSE_REF)
        part = _sse_page(data, day)
        meta = data.get('pageHelp')
        if type(meta) is not dict:
            _fail('source_pagination_invalid')
        total = _integer(meta.get('total'))
        page_count = _integer(meta.get('pageCount'), _MAX_PAGES)
        if _integer(meta.get('pageNo'), _MAX_PAGES) != page:
            _fail('source_pagination_invalid')
        if page_count == 0:
            # 上交所目标日暂无记录时，第 1 页返回零总页数与空结果。
            if page == 1 and total == 0 and not part:
                _fail('source_record_missing')
            _fail('source_pagination_invalid')
        if expected is not None and (total, page_count) != expected:
            _fail('source_pagination_changed')
        expected, pages = (total, page_count), page_count
        rows.extend(part)
        if len(rows) > _MAX_ROWS:
            _fail('source_pagination_invalid')
        receipts.append((parent, received))
    if expected is None or len(rows) != expected[0]:
        _fail('source_pagination_incomplete')
    codes = [row.get('SEC_CODE') for row in rows]
    if any(type(value) is not str for value in codes) or len(codes) != len(set(codes)):
        _fail('source_duplicate_record')
    selected = [row for row in rows if row['SEC_CODE'] == code]
    if len(selected) != 1:
        _fail('source_record_missing')
    with localcontext() as context:
        context.prec = 300
        value = _number(selected[0].get('TOT_VOL')) * 10000  # 官方万份转换为基金份额。
    return _fact(value, 'share', 'SSE', receipts)


def _szse_tab(data):
    if type(data) is not list or len(data) > 20:
        _fail('source_schema_invalid')
    tabs = [tab for tab in data if type(tab) is dict and type(tab.get('metadata')) is dict
            and tab['metadata'].get('tabkey') == 'tab1']
    if len(tabs) != 1 or type(tabs[0].get('data')) is not list:
        _fail('source_schema_invalid')
    if any(type(row) is not dict for row in tabs[0]['data']):
        _fail('source_schema_invalid')
    return tabs[0]['metadata'], tabs[0]['data']


def _szse_shares(code, day, get):
    # 2026-11-06相同请求实证：HTTPS响应头前断连，官方HTTP导出200且无跳转。
    # 采用已验证的原版AkShare导出合同，不再把失败的HTTPS JSON当唯一入口。
    params = dict(SHOWTYPE='xlsx', CATALOGID='scsj_fund_jjgm', TABKEY='tab1',
                  txtStart=day, txtEnd=day, jjlb='ETF')
    raw, parent, received = _receipt(get, _SZSE_EXPORT, params, _SZSE_REF)
    table = _xlsx_table(raw)
    if not table or table[0] != ['日期', '基金代码', '基金简称', '基金规模(份)']:
        _fail('source_unit_unverified')
    rows = table[1:]
    if any(len(row) != 4 for row in rows):_fail('source_schema_invalid')
    if any(row[0] != day for row in rows):_fail('source_date_mismatch')
    shares_by_code = {}
    for _, raw_code, _, shares in rows:
        # 官方 XLSX 可用 ASCII 空格填充基金代码；重复和选择均按规范代码判断。
        fund_code = raw_code.strip(' ')
        if re.fullmatch(r'[0-9]{6}', fund_code) is None:
            _fail('source_symbol_mismatch')
        if fund_code in shares_by_code:
            _fail('source_duplicate_record')
        shares_by_code[fund_code] = shares
    if code not in shares_by_code:
        _fail('source_record_missing')
    return _fact(_number(shares_by_code[code]), 'share', 'SZSE', [(parent, received)])


def _turnover(day, get):
    params = dict(sqlId='COMMON_SSE_SJ_GPSJ_CJGK_MRGK_C', PRODUCT_CODE='01,02,03,11,17',
                  type='inParams', SEARCH_DATE=day)
    data, sh_parent, sh_time = _read(get, _SSE, params, 'https://www.sse.com.cn/market/stockdata/overview/day/')
    if (type(data) is not dict or data.get('actionErrors') or data.get('fieldErrors')
            or type(data.get('result')) is not list or len(data['result']) > _MAX_ROWS):
        _fail('source_schema_invalid')
    rows = data['result']
    if any(type(row) is not dict or row.get('TRADE_DATE') != day.replace('-', '') for row in rows):
        _fail('source_date_mismatch')
    stock = [row for row in rows if row.get('PRODUCT_CODE') == '17']
    if len(stock) != 1:
        _fail('source_record_missing')
    sh_amount = _number(stock[0].get('TRADE_AMT'))
    params = dict(SHOWTYPE='JSON', CATALOGID='1803', txtQueryDate=day, tab1PAGENO='1')
    data, sz_parent, sz_time = _read(get, _SZSE, params, 'https://www.szse.cn/')
    meta, rows = _szse_tab(data)
    if meta.get('subname') != day:
        _fail('source_date_mismatch')
    stock = [row for row in rows if row.get('zbmc') == '股票成交金额（亿元）']
    if len(stock) != 1:
        _fail('source_unit_unverified')
    with localcontext() as context:
        context.prec = 300
        value = (sh_amount + _number(stock[0].get('brsz'))) * 100000000  # 两市亿元同口径相加后转元。
    return _fact(value, 'CNY', 'SSE+SZSE', [(sh_parent, sh_time), (sz_parent, sz_time)])


def _daily_margin_report(first, last, get, *, report, day_field, columns):
    date_filter = (f"({day_field}='{first}')" if first == last else
                   f"({day_field}>='{first}')({day_field}<='{last}')")
    params = dict(reportName=report, columns=','.join((day_field, *columns)),
                  pageNumber='1', pageSize='10' if first == last else '500',
                  sortColumns=day_field, sortTypes='-1', filter=date_filter)
    data, parent, received = _read(get, _EM, params, 'https://data.eastmoney.com/rzrq/zhtjday.html')
    # 原报表按目标日尚无数据时返回9201/null；缺事实与协议损坏保持独立。
    if (type(data) is dict and data.get('success') is False
            and type(data.get('code')) is int and data['code'] == 9201
            and 'result' in data and data['result'] is None):
        _fail('source_record_missing')
    if type(data) is not dict or data.get('success') is not True or type(data.get('result')) is not dict:
        _fail('source_schema_invalid')
    result = data['result']
    rows = result.get('data')
    if type(rows) is not list:
        _fail('source_schema_invalid')
    if _integer(result.get('count')) != len(rows) or _integer(result.get('pages'), _MAX_PAGES) != 1:
        _fail('source_pagination_incomplete')
    if len(rows) > 500:
        _fail('source_pagination_invalid')
    selected = {}
    for row in rows:
        day = _report_day(row, day_field, first, last)
        if day in selected:
            _fail('source_duplicate_record')
        selected[day] = row
    return selected, (parent, received)


def _margin_rows(first, last, get, field):
    # 原报表统计覆盖未知，以 CN.MARGIN_REPORT 标识；历史汇总另有事实身份。
    selected, receipt = _daily_margin_report(first, last, get, report='RPTA_WEB_MARGIN_DAILYTRADE',
                                             day_field='STATISTICS_DATE', columns=(field,))
    result = {}
    for day, row in selected.items():
        with localcontext() as context:
            context.prec = 300
            amount = _number(row.get(field)) * 100_000_000
        result[day] = _fact(amount, 'CNY', 'Eastmoney', [receipt])
    return result


_MARGIN_SUMMARY_COLUMNS = {
    'fin_balance': 'RZYE',  # 融资余额，原报表人民币元。
    'fin_buy': 'RZMRE',  # 融资买入额，原报表人民币元。
    'fin_net_reported': 'RZJME',  # 披露的融资净买入额，原报表人民币元，可为负。
    'fin_repay': 'RZCHE',  # 融资偿还额，原报表人民币元。
    'short_balance': 'RQYE',  # 融券余额，原报表人民币元。
    'total_balance': 'RZRQYE',  # 两融余额，原报表人民币元。
}

MARGIN_REGIONAL_HOST = 'datapc.eastmoney.com'
_MARGIN_REGIONS = (
    ('sh', '007', '融资融券_沪证'),
    ('sz', '001', '融资融券_深证'),
    ('bj', '002', '融资融券_京证'),
)


def margin_summary_history(first, last, get):
    """一次读回原两融历史汇总，按交易日和指标返回合格事实及无效字段原因。"""
    selected, receipt = _daily_margin_report(first, last, get, report='RPTA_RZRQ_LSHJ',
                                             day_field='DIM_DATE', columns=_MARGIN_SUMMARY_COLUMNS.values())
    result, invalid = {}, {}
    for day, row in selected.items():
        for metric, field in MARGIN_SUMMARY_FIELDS.items():
            value = row.get(_MARGIN_SUMMARY_COLUMNS[field])
            if value is not None:
                signed = metric == SIGNED_MARGIN_SUMMARY
                try:
                    result[day, metric] = _fact(_number(value, signed=signed), 'CNY', 'Eastmoney', [receipt], signed=signed)
                except SourceUnavailable as error:
                    invalid[day, metric] = error.code
    return result, invalid


def margin_summary_regional(day, get):
    """仅合并三个交易所同日已发布的、与原全国历史汇总同口径的字段。"""
    rows, receipts = [], []
    for market, code, label in _MARGIN_REGIONS:
        base = f'https://{MARGIN_REGIONAL_HOST}/emdatacenter/rzrq'
        data, parent, received = _read(get, base + '/details2', dict(mkt=market, fd=day),
                                       base + '/index?market=' + market)
        if (type(data) is dict and data.get('success') is False
                and type(data.get('code')) is int and data['code'] == 9201
                and 'result' in data and data['result'] is None):
            _fail('margin_regional_report_missing')
        if (type(data) is not dict or data.get('success') is not True or type(data.get('code')) is not int
                or data['code'] != 0 or type(data.get('result')) is not dict):
            _fail('source_schema_invalid')
        result = data['result']
        records = result.get('data')
        if (type(records) is not list or len(records) != 1
                or _integer(result.get('count')) != 1 or _integer(result.get('pages'), _MAX_PAGES) != 1):
            _fail('source_pagination_incomplete')
        row = records[0]
        _report_day(row, 'DIM_DATE', day, day)
        if row.get('SCDM') != code or row.get('XOB_MARKET_0001') != label:
            _fail('margin_regional_identity_invalid')
        rows.append(row)
        receipts.append((parent, received))
    facts, invalid = {}, {}
    for metric, field in MARGIN_SUMMARY_FIELDS.items():
        column = _MARGIN_SUMMARY_COLUMNS[field]
        if any(row.get(column) is None for row in rows):
            invalid[metric] = 'source_record_missing'
            continue
        signed = metric == SIGNED_MARGIN_SUMMARY
        try:
            with localcontext() as context:
                context.prec = 300
                value = sum(_number(row[column], signed=signed) for row in rows)
            facts[metric] = _fact(value, 'CNY', 'Eastmoney', receipts, signed=signed)
        except SourceUnavailable as error:
            invalid[metric] = error.code
    return facts, invalid


def gov10y_history(first, last, get):
    """把中债原日表的年化百分数和返回的同一原件绑定。"""
    from guanheng_app.observation.gov10y_source import REFERER, URL, parse_yields, query_params
    from guanheng_app.observation.source_fetch import SourceFailure

    receipt = get(URL, query_params(first, last), REFERER)
    try:
        values = parse_yields(receipt['body'], first, last)
    except SourceFailure as error:
        raise SourceUnavailable(error.code) from None
    return {day: _fact(value, 'pct', 'ChinaBond', [(receipt['sha256'], receipt['received_at'])])
            for day, value in values.items()}


def shenwan_history(first, last, get):
    """沿原公开日报批取申万 A 指 801003，并为每个定日字段保留原页。"""
    url = 'https://www.swsresearch.com/institute-sw/api/index_analysis/index_analysis_report/'
    referer = 'https://www.swsresearch.com/'
    facts, invalid, seen = {}, {}, set()
    expected_total = None
    for page in range(1, 16):
        params = dict(page=page, page_size=1000, index_type='市场表征', start_date=first, end_date=last,
                      type='DAY', swindexcode='all')
        packet, parent, received = _read(get, url, params, referer)
        data = packet.get('data') if type(packet) is dict and packet.get('code') in ('200', 200) else None
        if type(data) is not dict or type(data.get('results')) is not list:
            _fail('source_schema_invalid')
        total = _integer(data.get('count'), 15000)
        if expected_total is None:
            expected_total = total
        offset = (page - 1) * 1000
        if total != expected_total or len(data['results']) != min(1000, total - offset):
            _fail('source_pagination_incomplete')
        for row in data['results']:
            if type(row) is not dict or 'swindexcode' not in row:
                _fail('source_schema_invalid')
            if str(row['swindexcode']) != '801003':
                continue
            try:
                day = datetime.fromisoformat(row['bargaindate']).date().isoformat()
            except (KeyError, TypeError, ValueError):
                _fail('source_date_mismatch')
            if not first <= day <= last:
                _fail('source_date_mismatch')
            if day in seen:
                _fail('source_duplicate_record')
            seen.add(day)
            for metric, (_, column, unit) in SHENWAN_FIELDS.items():
                if row.get(column) in (None, '', '--', '-'):
                    invalid[day, metric] = 'source_record_missing'
                    continue
                signed = metric in SIGNED_REPORT_METRICS
                try:
                    amount = _number(row[column], signed=signed)
                    if metric == 'shenwan_market_close' and amount <= 0:
                        _fail('source_value_invalid')
                    facts[day, metric] = _fact(amount, unit, 'Shenwan', [(parent, received)], signed=signed)
                except SourceUnavailable as error:
                    invalid[day, metric] = error.code
        if total <= offset + 1000:
            return facts, invalid
    _fail('source_pagination_incomplete')


def margin_purchase_history(first, last, get):
    """有界历史回填，源缺日保持为空。"""
    return _margin_rows(first,last,get,'FIN_BUY_AMT')


def _report_day(row, field, first, last):
    value = row.get(field) if type(row) is dict else None
    match = re.fullmatch(r'(\d{4}-\d{2}-\d{2})(?: 00:00:00)?', value) if type(value) is str else None
    if match is None or not first <= match[1] <= last:
        _fail('source_date_mismatch')
    try:
        return date.fromisoformat(match[1]).isoformat()
    except ValueError:
        _fail('source_date_mismatch')


def ipo_proceeds_history(days, get):
    """沿完整区间报表按上市日汇总沪深新股的实际募资。"""
    first, last = days[0], days[-1]
    params = dict(reportName='RPTA_APP_IPOAPPLY', columns='SECUCODE,LISTING_DATE,TOTAL_RAISE_FUNDS,SECURITY_TYPE_CODE',
                  pageNumber='1', pageSize='500', sortColumns='LISTING_DATE,SECUCODE', sortTypes='-1,1',
                  filter=f"(LISTING_DATE>='{first}')(LISTING_DATE<='{last}')")
    data, parent, received = _read(get, _EM, params, 'https://data.eastmoney.com/xg/xg/')
    if (type(data) is dict and data.get('success') is False
            and type(data.get('code')) is int and data['code'] == 9201
            and 'result' in data and data['result'] is None):
        rows = []
    else:
        result = data.get('result') if type(data) is dict and data.get('success') is True else None
        if type(result) is not dict or type(result.get('data')) is not list:
            _fail('source_schema_invalid')
        rows = result['data']
        if (not 1 <= len(rows) <= 500 or _integer(result.get('count')) != len(rows)
                or _integer(result.get('pages'), _MAX_PAGES) != 1):
            _fail('source_pagination_incomplete')

    amounts = dict.fromkeys(days, Decimal(0))
    incomplete, securities = set(), set()
    for row in rows:
        day = _report_day(row, 'LISTING_DATE', first, last)
        symbol = row.get('SECUCODE')
        if (type(symbol) is not str or re.fullmatch(r'[0-9]{6}\.(SH|SZ|BJ)', symbol) is None
                or row.get('SECURITY_TYPE_CODE') != '058001001'):
            _fail('source_symbol_mismatch')
        if symbol in securities:
            _fail('source_duplicate_record')
        securities.add(symbol)
        if symbol.endswith('.BJ') or day not in amounts:
            continue
        amount = row.get('TOTAL_RAISE_FUNDS')
        amount = _number(amount) if amount is not None else Decimal(0)
        if amount == 0:
            incomplete.add(day)
            continue
        with localcontext() as context:
            context.prec = 300
            amounts[day] += amount * 100_000_000
    return {day: _fact(value, 'CNY', 'Eastmoney', [(parent, received)])
            for day, value in amounts.items() if day not in incomplete}


def _shareholder_report(first, last, get):
    from guanheng_app.observation.provider_reports import SHAREHOLDER_REPORT_KEY, SHAREHOLDER_REPORT_MARKETS

    markets = ','.join(f'"{market}"' for market in sorted(SHAREHOLDER_REPORT_MARKETS))
    params = dict(reportName='RPT_SHARE_HOLDER_INCREASE', columns='ALL', pageSize='500',
                  sortColumns=','.join(SHAREHOLDER_REPORT_KEY), sortTypes=','.join('1' for _ in SHAREHOLDER_REPORT_KEY),
                  filter=f"(NOTICE_DATE>='{first}')(NOTICE_DATE<='{last}')(MARKET in ({markets}))")
    rows, receipts = [], []
    expected = None
    for page in range(1, 5):
        data, parent, received = _read(get, _EM, dict(params,pageNumber=str(page)),
                                       'https://data.eastmoney.com/executive/gdzjc.html')
        receipts.append((parent,received))
        if (page == 1 and type(data) is dict and data.get('success') is False and data.get('code') == 9201
                and 'result' in data and data['result'] is None and data.get('message') == '返回数据为空'):
            return [], receipts
        result = data.get('result') if type(data) is dict and data.get('success') is True else None
        if type(result) is not dict or type(result.get('data')) is not list:
            _fail('source_schema_invalid')
        count, pages = _integer(result.get('count'),2000), _integer(result.get('pages'),4)
        if page == 1 and count == pages == 0 and result['data'] == []:
            return [], receipts
        if (pages != (count+499)//500 or not 1 <= page <= pages
                or len(result['data']) != min(500,count-(page-1)*500)
                or (expected is not None and count != expected)):
            _fail('source_pagination_incomplete')
        expected = count
        rows.extend(result['data'])
        if page == pages:
            return rows, receipts
    _fail('source_pagination_incomplete')


def shareholder_reduction_history(days, calendar, get, *, reference_close=None, reference_receipts=()):
    """可计价减持毛额复用原股东图的计价资格，未知明细单列；非交易日向后归属。"""
    from guanheng_app.observation.provider_reports import SHAREHOLDER_REPORT_KEY, SHAREHOLDER_REPORT_MARKETS

    first_index = bisect_left(calendar, days[0])
    if first_index == 0:
        _fail('source_notice_calendar_unavailable')
    first = (date.fromisoformat(calendar[first_index-1])+timedelta(days=1)).isoformat()
    last = days[-1]
    rows, receipts = _shareholder_report(first,last,get)
    amounts = dict.fromkeys(days,Decimal(0))
    quality={day:dict(
        priced_count=0,  # 使用公告成交均价的减持笔数。
        estimated_count=0,  # 使用原报表或已核本地参考收盘价的减持笔数。
        unpriced_count=0,  # 仍缺价格、未计入可计价金额的减持笔数。
        timing_conflict_count=0,  # 交易日晚于公告日、单列剔除的明细笔数。
    )for day in days}
    seen = set()
    for row in rows:
        notice = _report_day(row,'NOTICE_DATE',first,last)
        day = calendar[bisect_left(calendar,notice)]
        code = row.get('SECURITY_CODE')
        if (type(code) is not str or re.fullmatch(r'(?:00|30|60|68|83|92)\d{4}',code) is None
                or row.get('MARKET') not in SHAREHOLDER_REPORT_MARKETS):
            _fail('source_symbol_mismatch')
        identity = tuple(row.get(field) for field in SHAREHOLDER_REPORT_KEY)
        if (all(field in row for field in SHAREHOLDER_REPORT_KEY)
                and all(value is None or type(value) in (str,int,Decimal) for value in identity)
                and identity not in seen):
            seen.add(identity)
        else:
            _fail('source_duplicate_record')
        if code.startswith(('83','92')) or day not in amounts:
            continue
        quantity = _number(row.get('CHANGE_NUM'))
        signed = str(row.get('CHANGE_NUM_SYMBOL'))
        direction = row.get('DIRECTION')
        if (direction not in ('增持','减持') or quantity <= 0 or signed.startswith('-') != (direction=='减持')
                or _number(signed.removeprefix('-')) != quantity):
            _fail('source_value_invalid')
        if direction == '增持':
            continue
        trade = _report_day(row,'TRADE_DATE','1990-01-01','9999-12-31')
        if trade > notice:
            quality[day]['timing_conflict_count']+=1
            continue
        price = _number(row.get('TRADE_AVERAGE_PRICE') or 0)
        if price:
            quality[day]['priced_count']+=1
        else:
            price = _number(row.get('CLOSE_PRICE') or 0)
            if not price and reference_close is not None:
                price=_number(reference_close(code,date.fromisoformat(trade)) or 0)
            quality[day]['estimated_count'if price else 'unpriced_count']+=1
        if not price:continue
        with localcontext() as context:
            context.prec = 300
            amounts[day] += quantity * price * 10_000
    return {day:dict(_fact(value,'CNY','Eastmoney',[*receipts,*reference_receipts]),
        calculation=dict(schema='guanheng.shareholder-reduction-estimate.v1',  # 可计价减持估算证据版本。
            date=day,  # 非交易日披露归入的后继交易日。
            method='known_priced_disclosures; average_then_reference_close; timing_conflicts_excluded',  # 计价及未知明细处理。
            **quality[day]))
        for day,value in amounts.items() if quality[day]['unpriced_count']==0}


def _csi300_market_cap(raw, day):
    """核日、列表语义和同份报告双收盘点位，返回自由流通市值（亿元）。"""
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError
    if not raw.startswith(b'%PDF-') or len(raw) > 2 * 1024 * 1024:
        _fail('source_csi_report_invalid')
    try:
        report = PdfReader(io.BytesIO(raw), strict=True)
        if not 2 <= len(report.pages) <= 20:
            _fail('source_csi_report_invalid')
        summary, matrix = (report.pages[i].extract_text(extraction_mode='layout') for i in (0, 1))
    except (PdfReadError, ValueError, OSError, RecursionError):
        _fail('source_csi_report_invalid')
    title = re.search(r'沪深300指数\((20\d{2})年(\d{1,2})月(\d{1,2})日\)',
                      re.sub(r'\s+', '', summary).replace('（', '(').replace('）', ')'))
    if title is None or tuple(map(int, title.groups())) != (date.fromisoformat(day).year,
            date.fromisoformat(day).month, date.fromisoformat(day).day):
        _fail('source_date_mismatch')
    header = r'指数代码指数简称基日发布日期基点总市值(?:[（(]亿元[）)])?自由流通市值(?:[（(]亿元[）)])?收盘点位'
    if '规模及行业指数市场数据' not in matrix or not re.search(header,re.sub(r'\s+', '', matrix)):
        _fail('source_schema_invalid')
    rows = [line.split() for line in matrix.splitlines() if re.match(r'^\s*000300\s+', line)]
    if len(rows) != 1 or len(rows[0]) < 9 or rows[0][:5] != ['000300','沪深300','20041231','20050408','1000']:
        _fail('source_symbol_mismatch')
    _, _, _, _, _, total, floating, close, *_ = rows[0]
    summary_close = re.search(r'收盘点位\s+([0-9,.]+)\s+指数涨幅', summary)
    if summary_close is None or _number(summary_close[1]) != _number(close):
        _fail('source_value_invalid')
    floating = _number(floating)
    if not 0 < floating <= _number(total):
        _fail('source_value_invalid')
    return floating


def collect_external(metric, symbol, day, get):
    """读取一个标准事实；get(url,params,referer)返回原件收据，拥有全部 HTTP。

    本适配同步串行、不持有缓存或账户。解析缺项抛 SourceUnavailable 固定原因；
    注入层的总截止/取消/运输异常原样交回 owner。received_at 为全部输入实收 UTC，
    历史首次可知时间由目录 owner 保持 unknown。本函数只执行显式选择的外部源。
    """
    try:
        if type(day) is not str or date.fromisoformat(day).isoformat() != day:
            raise ValueError
    except (ValueError, TypeError):
        _fail('source_target_invalid')
    if not callable(get):
        _fail('source_target_invalid')
    if metric == 'etf_total_shares' and type(symbol) is str and re.fullmatch(r'(SSE|SZSE)\.[0-9]{6}', symbol):
        exchange, code = symbol.split('.')
        return (_sse_shares if exchange == 'SSE' else _szse_shares)(code, day, get)
    if metric == 'market_turnover' and symbol == 'CN.SH_SZ':
        return _turnover(day, get)
    if metric in ('margin_balance',MARGIN_PURCHASE) and symbol == MARGIN_REPORT:
        rows=_margin_rows(day,day,get,'FIN_BUY_AMT' if metric==MARGIN_PURCHASE else 'FIN_BALANCE')
        if day not in rows:
            _fail('source_record_missing')
        return rows[day]
    if metric == IPO_PROCEEDS and symbol == SH_SZ_SCOPE:
        rows = ipo_proceeds_history([day], get)
        if day not in rows:
            _fail('source_record_missing')
        return rows[day]
    if metric == INDEX_FREE_FLOAT_CAP and symbol == CSI300_INDEX:
        raw, parent, received = _receipt(get, _CSI_DAILY_REPORT.format(day.replace('-', '')), {}, None)
        return _fact(_csi300_market_cap(raw, day) * 100_000_000, 'CNY', 'CSI', [(parent, received)])
    if metric == INDEX_TURNOVER and symbol == SMALL_CAP_INDEX:
        stamp = day.replace('-', '')
        data,parent,received = _read(get,_CSI_PERFORMANCE,
            dict(indexCode='932000',startDate=stamp,endDate=stamp),'https://www.csindex.com.cn/')
        if type(data) is not dict or data.get('success') is not True or str(data.get('code')) != '200' or type(data.get('data')) is not list:
            _fail('source_schema_invalid')
        rows = data['data']
        if not rows:
            _fail('source_record_missing')
        row = rows[0]
        if (len(rows)!=1 or type(row) is not dict or row.get('indexCode')!='932000' or row.get('tradeDate')!=stamp
                or _number(row.get('close'))<=0):
            _fail('source_symbol_mismatch')
        amount = _number(row.get('tradingValue'))
        if amount<=0:
            _fail('source_value_invalid')
        return _fact(amount*100_000_000,'CNY','CSI',[(parent,received)])
    _fail('source_metric_unavailable')
