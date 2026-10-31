"""股票供应商原始字符串表的唯一准入；传输、归档重读共用同一合同。"""
import json
import re
from .source_fetch import SourceFailure
from .storage import encode

MAX_ROWS=100000
MAX_COLUMNS=64
MAX_CELL_BYTES=1024*1024
MAX_TABLE_BYTES=16*1024*1024


class StringTable:
    def __init__(self,fields,required=(),*,limit=MAX_TABLE_BYTES,check=lambda:None):
        check()
        if (type(fields) is not list or not 1<=len(fields)<=MAX_COLUMNS
                or any(type(key) is not str or re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,127}',key) is None for key in fields)
                or len(set(fields))!=len(fields) or not set(required)<=set(fields)):
            raise SourceFailure('provider_table_fields')
        self.fields=list(fields);self.rows=[];self.check=check;self.limit=min(limit,MAX_TABLE_BYTES)
        self.size=len(b'{"fields":'+encode(self.fields)+b',"rows":[]}')
        if self.size>self.limit:raise SourceFailure('provider_table_bytes')

    def append(self,row):
        self.check()
        if type(row) is not list or len(row)!=len(self.fields) or any(type(value) is not str for value in row):
            raise SourceFailure('provider_table_row')
        if len(self.rows)>=MAX_ROWS:raise SourceFailure('provider_table_rows')
        try:
            if any(len(value)>MAX_CELL_BYTES or len(value.encode('utf8'))>MAX_CELL_BYTES for value in row):
                raise SourceFailure('provider_table_cell')
            size=len(encode(row))+(1 if self.rows else 0)
        except UnicodeError:raise SourceFailure('provider_table_encoding') from None
        if self.size+size>self.limit:raise SourceFailure('provider_table_bytes')
        self.rows.append(list(row));self.size+=size

    def body(self):
        self.check();body=encode(dict(fields=self.fields,rows=self.rows));self.check()
        if len(body)!=self.size:raise SourceFailure('provider_table_changed')
        return body


def parse_json(body):
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise SourceFailure('provider_table_fields')
            result[key]=value
        return result
    try:return json.loads(body,object_pairs_hook=unique)
    except (ValueError,UnicodeError,RecursionError):raise SourceFailure('provider_table_encoding') from None


def load_table(body,required=(),*,limit=MAX_TABLE_BYTES,check=lambda:None):
    check()
    if type(body) is not bytes or len(body)>min(limit,MAX_TABLE_BYTES):raise SourceFailure('provider_table_bytes')
    raw=parse_json(body)
    if type(raw) is not dict or set(raw)!={'fields','rows'} or type(raw['rows']) is not list:
        raise SourceFailure('provider_table_row')
    table=StringTable(raw['fields'],required,limit=limit,check=check)
    for row in raw['rows']:table.append(row)
    return table
