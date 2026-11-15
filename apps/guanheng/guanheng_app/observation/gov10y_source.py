"""中债公开表的十年国债收益率，供原观察及 WT 事实采集共用。"""

from datetime import date
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
import re

from .source_fetch import SourceFailure

URL = 'https://yield.chinabond.com.cn/cbweb-pbc-web/pbc/historyQuery'
REFERER = 'https://yield.chinabond.com.cn/'
TABLE = 'source.gov10y'
WT_KIND = 'wt_gov10y'


class _Tables(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables = []
        self.table = self.row = self.cell = None

    def handle_starttag(self, tag, attrs):
        if tag == 'table':
            self.table = []
        if tag == 'tr' and self.table is not None:
            self.row = []
        if tag in ('td', 'th') and self.row is not None:
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data.strip())

    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self.cell is not None:
            self.row.append(''.join(self.cell))
            self.cell = None
        if tag == 'tr' and self.row is not None:
            self.table.append(self.row)
            self.row = None
        if tag == 'table' and self.table is not None:
            self.tables.append(self.table)
            self.table = None


def query_params(start, end):
    return dict(startDate=start, endDate=end, gjqx='0', qxId='ycqx', locale='cn_ZH')


def parse_yields(body, start, end):
    """以报告实际日期返回年化百分数，选中同名曲线且日期不可冲突。"""
    parser = _Tables()
    try:
        parser.feed(body.decode('utf8'))
    except UnicodeError:
        raise SourceFailure('gov10y_table_schema_changed_or_not_published') from None
    values = {}
    for table in parser.tables:
        for index, header in enumerate(table):
            columns = [i for i, cell in enumerate(header) if re.fullmatch(r'10(?:年|Y)', cell, re.I)]
            if len(columns) != 1:
                continue
            column = columns[0]
            for row in table[index+1:]:
                if len(row) <= column or row[0] != '中债国债收益率曲线':
                    continue
                dates = (re.search(r'\d{4}-\d{2}-\d{2}', cell) for cell in row)
                found = next((match for match in dates if match), None)
                if found is None:
                    continue
                observed = found[0]
                try:
                    if date.fromisoformat(observed).isoformat() != observed:
                        raise ValueError('report date')
                    value = Decimal(row[column].replace(',', ''))
                except (ValueError, InvalidOperation):
                    raise SourceFailure('gov10y_invalid_value') from None
                if (not value.is_finite() or not 0 <= value < 20
                        or len(value.as_tuple().digits) > 120 or value.as_tuple().exponent < -120):
                    raise SourceFailure('gov10y_invalid_value')
                if start <= observed <= end:
                    if observed in values and values[observed] != value:
                        raise SourceFailure('gov10y_conflicting_source_date')
                    values[observed] = value
    if not values:
        raise SourceFailure('gov10y_table_schema_changed_or_not_published')
    return values
