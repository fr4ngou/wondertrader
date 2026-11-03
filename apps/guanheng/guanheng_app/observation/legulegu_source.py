"""原乐咕乐股ALL报告值的持续快照；不重算或替换供应商股票池。"""
from datetime import date,datetime
from html.parser import HTMLParser
import hashlib,json,math
from zoneinfo import ZoneInfo
from .source_fetch import SourceFailure


class _PageSession(HTMLParser):
    """只取得当前公开页面会话字段，不执行页面脚本或读取账户资料。"""
    def __init__(self):
        super().__init__()
        self.csrf=None # 本次页面的公开CSRF文本；缺失时拒绝API查询，不作持久配置。

    def handle_starttag(self,tag,attributes):
        if tag=='meta':
            values=dict(attributes)
            if values.get('name')=='_csrf':self.csrf=values.get('content')


def history(fetch,config,start,end):
    """同一Fetcher公开会话取得原ALL快照；返回原pb_all字段及真实观察日。

    start/end是来源窗口的ISO日期；认证日期使用当前上海日历日，独立于查询日。
    API不接受历史日期参数，原完整响应先归档后按窗口选择，缺失日期不填值。
    """
    page=fetch.get(config['referer'])
    parser=_PageSession();parser.feed(page.decode('utf8'))
    if not parser.csrf:raise SourceFailure('pb_all_public_session_missing')
    today=datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat()
    # 供应商公开客户端定义的当日请求标识；不承载个人账户或秘密凭据。
    token=hashlib.md5(today.encode('ascii')).hexdigest()
    raw=fetch.get(config['url'],dict(marketId='ALL',token=token),referer=config['referer'],
        public_headers={'X-CSRF-Token':parser.csrf})
    try:
        payload=json.loads(raw);data=payload['data']
        if type(data) is not list or not data:raise ValueError('empty data')
        result=[];seen=set()
        for row in data:
            day=row['date']
            if type(day) is not str or date.fromisoformat(day).isoformat()!=day or day in seen:raise ValueError('date')
            seen.add(day)
            # date为提供方观察日；三数值为原倍数/指数点；首次可知时间未知。
            values=[row[key] for key in ('equalWeightAveragePB','middlePB','close')]
            if any(type(value) not in (int,float) or not math.isfinite(value) for value in values):raise ValueError('value')
            if start<=day<=end:
                result.append(dict(date=day,equal_pb=values[0],median_pb=values[1],reference=values[2],available_at=None))
        if not result:raise ValueError('no window data')
        return {'pb_all':sorted(result,key=lambda row:row['date'])}
    except (KeyError,TypeError,ValueError,UnicodeError) as exc:
        raise SourceFailure('pb_all_provider_schema') from exc
