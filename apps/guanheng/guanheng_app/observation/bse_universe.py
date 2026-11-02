"""北交所公开名单及历史区间；只提供观察股票池，不拥有交易证券资料。"""
from datetime import date
from html.parser import HTMLParser
import re

from .source_fetch import SourceFailure
from .provider_tables import parse_json
from .storage import digest, encode

LIST_PAGE='https://www.bse.cn/nq/listedcompany.html'
LIST_API='https://www.bse.cn/nqxxController/nqxxCnzq.do?callback=guanhengBseList'
MAPPING='https://www.bse.cn/service/code_mapping.html'


def _day(value):
    if type(value) is not str:raise SourceFailure('bse_listing_date')
    try:
        if re.fullmatch(r'\d{8}',value):result=date(int(value[:4]),int(value[4:6]),int(value[6:]))
        elif re.fullmatch(r'\d{4}/\d{1,2}/\d{1,2}',value):result=date(*map(int,value.split('/')))
        else:
            result=date.fromisoformat(value)
            if result.isoformat()!=value:raise ValueError()
        return result.isoformat()
    except ValueError:raise SourceFailure('bse_listing_date') from None


class _Mapping(HTMLParser):
    def __init__(self,check):
        super().__init__();self.check=check;self.row=None;self.cell=None;self.rows=[]

    def handle_starttag(self,tag,attrs):
        self.check()
        if tag=='tr':self.row=[]
        elif tag in ('td','th') and self.row is not None:self.cell=[]

    def handle_data(self,data):
        if self.cell is not None:self.cell.append(data)

    def handle_endtag(self,tag):
        if tag in ('td','th') and self.cell is not None:
            self.row.append(''.join(self.cell).strip());self.cell=None
        elif tag=='tr' and self.row is not None:
            if len(self.row)==5 and re.fullmatch(r'\d{6}',self.row[3]) and re.fullmatch(r'\d{6}',self.row[4]):
                self.rows.append((self.row[3],self.row[4],_day(self.row[2])))
                if len(self.rows)>2000:raise SourceFailure('bse_mapping_capacity')
            self.row=None


def listings(fetch, history, *, as_of, minimum, verify_disclosures=False):
    """当前全页+已核退出公告重建区间；缺省沿静态核验截止采用。

    history由配置owner持有区间和公告摘要；verify_disclosures=True时，
    超出seed截止须完整复核官方终止上市公告，成功才延长本次原件资格，
    原seed保持。新公司/新公告或登记变化交owner核验，失败保留旧结果。
    原退出公告仍重取并核同SHA；原件及区间进入同次来源链，上市日计入、
    摘牌日退出。本函数只生成候选，调用者拥有最终发布及失败保旧事务。
    """
    check=fetch.budget.remaining;check()
    if type(verify_disclosures) is not bool:raise SourceFailure('bse_history_policy')
    if as_of<history['market_open'] or (as_of>history['verified_through'] and not verify_disclosures):
        raise SourceFailure('bse_history_coverage_expired')
    current={};total=pages=None;page=0
    while pages is None or page<pages:
        check()
        body=fetch.post_readonly(LIST_API,{'page':str(page),'typejb':'T','xxfcbj[]':'2',
            'xxzqdm':'','sortfield':'xxzqdm','sorttype':'asc'},referer=LIST_PAGE,session_handoff=True)
        match=re.fullmatch(rb'guanhengBseList\((.*)\);?\s*',body,re.S)
        if match is None:raise SourceFailure('bse_response_format')
        try:
            raw=parse_json(match[1]);value=raw[0]
            if type(raw) is not list or len(raw)!=1 or type(value) is not dict:raise ValueError()
            if page==0:
                total,pages=value['totalElements'],value['totalPages']
                if (type(total) is not int or not minimum<=total<=2000 or type(pages) is not int
                        or not 1<=pages<=100 or pages!=(total+19)//20):raise ValueError()
            rows=value['content']
            if (any(type(value[key]) is not int for key in ('number','size','totalElements','totalPages','numberOfElements'))
                    or type(rows) is not list or value['number']!=page or value['size']!=20
                    or value['totalElements']!=total or value['totalPages']!=pages
                    or value['firstPage'] is not (page==0) or value['lastPage'] is not (page==pages-1)
                    or value['numberOfElements']!=len(rows) or len(rows)!=min(20,total-page*20)):
                raise ValueError()
            for row in rows:
                check();code=row['xxzqdm']
                if type(code) is not str or re.fullmatch(r'\d{6}',code) is None or code in current:
                    raise ValueError()
                if current and code<=next(reversed(current)):raise ValueError()
                current[code]=_day(row['fxssrq'])
        except (ValueError,TypeError,KeyError,IndexError,RecursionError):
            raise SourceFailure('bse_response_schema') from None
        page+=1
    body=fetch.get(MAPPING);parser=_Mapping(check)
    try:parser.feed(body.decode('utf8'))
    except UnicodeError:raise SourceFailure('bse_mapping_schema') from None
    aliases={};mapped_dates={}
    for old,new,first in parser.rows:
        check()
        if old in aliases or new in mapped_dates:raise SourceFailure('bse_mapping_duplicate')
        aliases[old]=new;mapped_dates[new]=first
        if new in current and current[new]!=first:raise SourceFailure('bse_mapping_date_conflict')
    if not aliases:raise SourceFailure('bse_mapping_empty')
    qualification=None
    if as_of>history['verified_through']:
        from .bse_history_verification import verify_history
        history,qualification=verify_history(fetch,history,as_of,aliases)
    market_open=history['market_open']
    result={'bj.'+code:(max(market_open,first),'') for code,first in current.items()}
    for interval in history['exits']:
        check();code=interval['code']
        if 'bj.'+code in result:raise SourceFailure('bse_exit_still_listed')
        body=fetch.get(interval['source_url'])
        if not body.startswith(b'%PDF-') or digest(body)!=interval['source_sha256']:
            raise SourceFailure('bse_exit_source_changed')
        first=interval['listed_on']
        if code in mapped_dates and max(market_open,mapped_dates[code])!=first:
            raise SourceFailure('bse_exit_listing_conflict')
        result['bj.'+code]=(first,interval['delisted_on'])
    provenance=dict(schema='guanheng.bse-listing-intervals.v1',date=as_of,
        market_open=market_open,verified_through=history['verified_through'],
        current_count=len(current),aliases=aliases,
        intervals={code:list(value) for code,value in sorted(result.items())},history=history)
    if qualification:provenance['history_verification_sha256']=qualification
    identity=fetch.objects.put(encode(provenance))
    fetch.records.append(dict(kind='bse_listing_intervals',sha256=identity,source_host='www.bse.cn',status=200))
    return result,aliases,identity
