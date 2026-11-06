"""公开市场补充事实适配；请求、预算、缓存及原件存储由注入的 get 拥有。"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, localcontext
import hashlib
import io
import json
import re
import xml.etree.ElementTree as ET
import zipfile
import zlib


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


def _number(value):
    if type(value) not in (str, int, Decimal):
        _fail('source_value_invalid')
    text = str(value)
    if len(text) > 256:
        _fail('source_value_invalid')
    if ',' in text:
        if not re.fullmatch(r'[0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]+)?', text):
            _fail('source_value_invalid')
        text = text.replace(',', '')
    try:
        result = Decimal(text)
    except InvalidOperation:
        _fail('source_value_invalid')
    # 原字段解析有界，避免有限但极端指数被展开为无界的目录字符串。
    if not result.is_finite() or result < 0 or abs(result.adjusted()) > 128:
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


def _fact(value, unit, source, receipts):
    with localcontext() as context:
        context.prec = 300
        text = format(value, 'f')
    if '.' in text:
        text = text.rstrip('0').rstrip('.')
    if value == 0:
        text = '0'
    # 缩放后的标准值必须在持久化前满足目录容量；超界原件保留为可重取缺口。
    if len(text) > 128 or re.fullmatch(r'[0-9]+(?:\.[0-9]+)?', text) is None:
        _fail('source_value_invalid')
    return {
        'value': text,  # 非负有限十进制原精度值；单位缩放后无指数形式。
        'unit': unit,  # 基金份额 share 或人民币元 CNY。
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
        if _integer(meta.get('pageNo'), _MAX_PAGES) != page or page_count < 1:
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
    if any(re.fullmatch(r'[0-9]{6}', row[1]) is None for row in rows):_fail('source_symbol_mismatch')
    if len({row[1] for row in rows}) != len(rows):_fail('source_duplicate_record')
    selected = [row for row in rows if row[1] == code]
    if len(selected) != 1:_fail('source_record_missing')
    return _fact(_number(selected[0][3]), 'share', 'SZSE', [(parent, received)])


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


def _margin(day, get):
    # 原报表统计覆盖未知，以 CN.MARGIN_REPORT 标识；不拼接另一报表 RZYE。
    params = dict(reportName='RPTA_WEB_MARGIN_DAILYTRADE', columns='STATISTICS_DATE,FIN_BALANCE',
                  pageNumber='1', pageSize='10', sortColumns='STATISTICS_DATE', sortTypes='-1',
                  filter="(STATISTICS_DATE='" + day + "')")
    data, parent, received = _read(get, _EM, params, 'https://data.eastmoney.com/rzrq/zhtjday.html')
    if type(data) is not dict or data.get('success') is not True or type(data.get('result')) is not dict:
        _fail('source_schema_invalid')
    result = data['result']
    rows = result.get('data')
    if type(rows) is not list:
        _fail('source_schema_invalid')
    if _integer(result.get('count')) != len(rows) or _integer(result.get('pages'), _MAX_PAGES) != 1:
        _fail('source_pagination_incomplete')
    if any(type(row) is not dict or row.get('STATISTICS_DATE') not in (day, day + ' 00:00:00') for row in rows):
        _fail('source_date_mismatch')
    if len(rows) != 1:
        _fail('source_record_missing' if not rows else 'source_duplicate_record')
    with localcontext() as context:
        context.prec = 300
        value = _number(rows[0].get('FIN_BALANCE')) * 100000000  # 发布方表头为亿，原值直接展示。
    return _fact(value, 'CNY', 'Eastmoney', [(parent, received)])


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
    if metric == 'margin_balance' and symbol == 'CN.MARGIN_REPORT':
        return _margin(day, get)
    _fail('source_metric_unavailable')
