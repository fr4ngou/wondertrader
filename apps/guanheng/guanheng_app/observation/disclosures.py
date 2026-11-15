"""Strict parsers for public report and HTML-table sources."""
import json
from .providers import SourceFailure, number
from .gov10y_source import TABLE, parse_yields, query_params

def gov10y(fetch,config,start,end):
    body = fetch.get(config['url'], query_params(start, end), config['referer'])
    values = parse_yields(body, start, end)
    return {TABLE: [dict(date=day, gov10y_pct=float(value)) for day, value in sorted(values.items())]}

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
