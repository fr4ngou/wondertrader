"""年末成员事实的唯一准备层；复用已准入原件或沿原来源首次完整建池。"""
from datetime import date
import re

from .bse_universe import listings as bse_listings
from .provider_tables import load_table,parse_json
from .source_fetch import SourceFailure
from .stock_universe import shsz_listings,listed_codes
from .storage import digest,encode


def _need(value,code='financial_universe_identity'):
    if not value:raise SourceFailure(code)


def _day(value):
    _need(type(value) is str and date.fromisoformat(value).isoformat()==value)
    return value


class _AdmittedInputs:
    """每次调用只缓存已核原件；原D、读取额度和旧来源时间保持。"""
    def __init__(self,fetch):
        self.fetch=fetch;self.raw={};self.basics={};self.bse={}

    def read(self,identity,*,pdf=False):
        _need(type(identity) is str and re.fullmatch('[a-f0-9]{64}',identity))
        if identity not in self.raw:
            self.fetch.budget.remaining();body=self.fetch.objects.get(identity)
            _need(len(body)<=self.fetch.budget.response_bytes,'financial_universe_capacity')
            self.fetch.budget.consume(len(body))
            self.fetch.records.append(dict(kind='admitted_financial_universe',sha256=identity,
                media_type='application/pdf' if pdf else 'application/json'))
            self.raw[identity]=body
        self.fetch.budget.remaining();return self.raw[identity]

    def basic(self,identity,minimum):
        if identity not in self.basics:
            table=load_table(self.read(identity),('code','type','ipoDate','outDate'),
                limit=self.fetch.budget.response_bytes,check=self.fetch.budget.remaining)
            listings=shsz_listings(table.fields,table.rows,check=self.fetch.budget.remaining)
            _need(len(listings)>=minimum,'financial_universe_incomplete')
            self.basics[identity]=listings
        return self.basics[identity]

    def beijing(self,identity,minimum,current_history):
        if identity not in self.bse:
            value=parse_json(self.read(identity))
            _need(type(value) is dict and value.get('schema')=='guanheng.bse-listing-intervals.v1')
            through=_day(value['verified_through']);observed=_day(value['date']);opened=_day(value['market_open'])
            _need(opened<=observed<=through)
            history=value['history']
            _need(type(history) is dict and history.get('schema_version')=='guanheng.bse-history.v1'
                and history.get('verified_through')==through and history.get('market_open')==opened)
            # 当前配置可撤回/修正旧资格；只允许已核历史作为当前声明的完整前缀。
            _need(through<=_day(current_history['verified_through']),'bse_history_coverage_expired')
            _need(current_history['market_open']==opened)
            previous_exits={item['code']:item for item in history['exits']}
            approved_exits={item['code']:item for item in current_history['exits'] if item['delisted_on']<=through}
            _need(previous_exits==approved_exits)
            intervals=value['intervals'];aliases=value['aliases'];count=value['current_count']
            _need(type(intervals) is dict and 1<=len(intervals)<=2000
                and type(count) is int and minimum<=count<=2000
                and type(aliases) is dict and 1<=len(aliases)<=2000)
            for old,new in aliases.items():
                self.fetch.budget.remaining()
                _need(type(old) is str and re.fullmatch('[0-9]{6}',old)
                    and type(new) is str and re.fullmatch('[0-9]{6}',new))
            normalized={}
            for code,pair in intervals.items():
                self.fetch.budget.remaining()
                _need(type(code) is str and re.fullmatch(r'bj\.[0-9]{6}',code)
                    and type(pair) is list and len(pair)==2)
                first,last=pair;_day(first)
                _need(opened<=first and type(last) is str)
                if last:_need(first<_day(last)<=through)
                normalized[code]=(first,last)
            _need(sum(not last for first,last in normalized.values())==count)
            exits=history['exits'];_need(type(exits) is list and len(exits)<=2000)
            exited=set()
            for item in exits:
                self.fetch.budget.remaining();code=item['code']
                _need(type(code) is str and re.fullmatch('[0-9]{6}',code) and code not in exited)
                _need(normalized.get('bj.'+code)==(item['listed_on'],item['delisted_on']))
                _need(self.read(item['source_sha256'],pdf=True).startswith(b'%PDF-'))
                exited.add(code)
            _need(exited=={code[3:] for code,(first,last) in normalized.items() if last})
            self.bse[identity]=dict(listings=normalized,aliases=aliases,through=through,observed=observed)
        return self.bse[identity]

    def fact(self,row,scope,config):
        _need(type(row) is dict)
        period=_day(row['date']);members=row['members']
        _need(type(members) is list and 1<=len(members)<=20000
            and all(type(code) is str and re.fullmatch(r'(sh|sz|bj)\.[0-9]{6}',code) for code in members)
            and len(set(members))==len(members) and type(row['market_count']) is int
            and row['market_count']==len(members))
        listings=dict(self.basic(row['source_basic_sha256'],config['minimum_universe']));aliases={}
        if scope=='ashare':
            bse=self.beijing(row['source_bse_sha256'],config['minimum_bse_universe'],config['bse_history'])
            _need(period<=bse['observed'] and row['history_confirmed_through']==bse['through'])
            listings.update(bse['listings']);aliases=bse['aliases']
            _need(type(row['bse_market_count']) is int
                and row['bse_market_count']==sum(code.startswith('bj.') for code in members))
        else:_need(not any(code.startswith('bj.') for code in members))
        expected=listed_codes(listings,period,check=self.fetch.budget.remaining)
        _need(set(members)==expected and row['universe_version']==digest(encode(dict(date=period,codes=sorted(expected)))))
        return dict(row=dict(row,members=list(members)),aliases=dict(aliases))


def universes_for_reports(fetch,config,periods,end,admitted_rows,*,basic_client):
    """已准入年末事实完整时核同复用；缺年沿原首次建池，不延长历史资格。

    返回每期原成员行及其代码映射，不读取财报、不改变业务current。
    原件错误/冲突直接失败；只有缺期可进入原公开建池路径。
    """
    try:
        fetch.budget.remaining();scope=config.get('scope','shsz');_need(scope in ('shsz','ashare'))
        _need(all(_day(period)<end for period in periods),'financial_report_not_completed')
        selected={};wanted=set(periods)
        for row in admitted_rows or ():
            fetch.budget.remaining();_need(type(row) is dict)
            if row.get('date') in wanted:
                _need(row['date'] not in selected);selected[row['date']]=row
        inputs=_AdmittedInputs(fetch)
        facts={period:inputs.fact(row,scope,config) for period,row in selected.items()}
        if set(facts)==wanted:return facts
        with basic_client(fetch,min(fetch.timeout,config.get('timeout_seconds',fetch.timeout))) as client:
            fields,rows=client.table('stock_basic')
            listings=shsz_listings(fields,rows,check=fetch.budget.remaining)
        _need(len(listings)>=config['minimum_universe'],'financial_universe_incomplete')
        basic_sha=next((item['sha256'] for item in reversed(fetch.records) if item.get('kind')=='stock_basic'),None)
        _need(basic_sha is not None,'financial_universe_parent_missing')
        aliases={};bse_sha=None
        if scope=='ashare':
            beijing,aliases,bse_sha=bse_listings(fetch,config['bse_history'],as_of=end,minimum=config['minimum_bse_universe'])
            listings.update(beijing)
        for period in periods:
            if period in facts:continue
            members=listed_codes(listings,period,check=fetch.budget.remaining)
            _need(bool(members),'financial_universe_empty')
            row=dict(date=period,market_count=len(members),members=sorted(members),
                universe_version=digest(encode(dict(date=period,codes=sorted(members)))),source_basic_sha256=basic_sha)
            if scope=='ashare':row.update(source_bse_sha256=bse_sha,
                bse_market_count=sum(code.startswith('bj.') for code in members),history_confirmed_through=config['bse_history']['verified_through'])
            facts[period]=dict(row=row,aliases=dict(aliases))
        return facts
    except SourceFailure:raise
    except (KeyError,ValueError,TypeError,IndexError,OverflowError,RecursionError):
        raise SourceFailure('financial_universe_identity') from None
