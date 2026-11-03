"""Strict parsers for public report and HTML-table sources."""
import json
import re
from html.parser import HTMLParser
from .providers import SourceFailure, number

class Tables(HTMLParser):
    def __init__(self):
        super().__init__(); self.tables=[]; self.table=None; self.row=None; self.cell=None
    def handle_starttag(self,tag,attrs):
        if tag=='table': self.table=[]
        if tag=='tr' and self.table is not None: self.row=[]
        if tag in ('td','th') and self.row is not None: self.cell=[]
    def handle_data(self,data):
        if self.cell is not None: self.cell.append(data.strip())
    def handle_endtag(self,tag):
        if tag in ('td','th') and self.cell is not None:
            self.row.append(''.join(self.cell)); self.cell=None
        if tag=='tr' and self.row is not None:
            self.table.append(self.row); self.row=None
        if tag=='table' and self.table is not None:
            self.tables.append(self.table); self.table=None

def gov10y(fetch,config,start,end):
    body=fetch.get(config['url'],dict(startDate=start,endDate=end,gjqx='0',qxId='ycqx',locale='cn_ZH'),config['referer'])
    parser=Tables(); parser.feed(body.decode('utf8'))
    output=[]
    for table in parser.tables:
        for index,header in enumerate(table):
            columns=[i for i,v in enumerate(header) if re.fullmatch(r'10(?:年|Y)',v,re.I)]
            if len(columns)!=1: continue
            column=columns[0]
            for row in table[index+1:]:
                if len(row)<=column: continue
                if not row or row[0] != '中债国债收益率曲线': continue
                observed=next((re.search(r'\d{4}-\d{2}-\d{2}',cell) for cell in row if re.search(r'\d{4}-\d{2}-\d{2}',cell)),None)
                if not observed: continue
                day=observed[0]; value=number(row[column])
                if value is None or not 0<=value<20: raise SourceFailure('gov10y_invalid_value')
                if start<=day<=end: output.append(dict(date=day,gov10y_pct=value))
    if not output: raise SourceFailure('gov10y_table_schema_changed_or_not_published')
    unique={}
    for row in output:
        if row['date'] in unique and unique[row['date']]!=row:
            raise SourceFailure('gov10y_conflicting_source_date')
        unique[row['date']]=row
    return {'source.gov10y':sorted(unique.values(),key=lambda r:r['date'])}

def repo_fixing(fetch,config,start,end):
    # 官网历史表使用只读POST；GET在同一公开地址返回403，不能据此判定资料需登录。
    # 表单日期是本次闭合区间，lang固定官方中文查询；原Fetcher记录方法和原始正文。
    raw=json.loads(fetch.post_readonly(config['url'],dict(startDate=start,endDate=end,lang='CN'),
        referer=config.get('referer')))
    rows=[]
    for row in raw.get('records',[]):
        day=row['lfiProducDate']; values=row['frValueMap']
        if start<=day<=end:
            rows.append(dict(date=day,fr007=number(values['FR007']),fdr007=number(values['FDR007']),available_at=None))
    if not rows: raise SourceFailure('repo_schema_changed_or_not_published')
    return {'liquidity_repo_fixing':sorted(rows,key=lambda r:r['date'])}
