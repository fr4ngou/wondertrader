"""采集配置原字节准入；普通读取不加载来源部署文件。"""
from datetime import date
import hashlib
import json
import math
from pathlib import Path
import re
from urllib.parse import urlsplit,parse_qsl
from .contracts import ObservationError
from .market_structure_source import CSI_KIND, CSI_URL, FIRST_DAY, INDEX_TABLES, STOCK_KIND, STOCK_TABLE, TUSHARE_URL, WT_INDEX_KIND, WT_STOCK_KIND
from . import broker_heat, etf_flow, ipo_supply, wt_margin_summary
from .gov10y_source import TABLE as GOV10Y_TABLE, WT_KIND as WT_GOV10Y

WT_DERIVED = {broker_heat.KIND:broker_heat, ipo_supply.KIND:ipo_supply}

KINDS = {'tencent','wondertrader','baostock','cffex','sse','szse','sgx','eastmoney','shenwan','irs',
         'disclosure','gov10y','repo_fixing','northbound','marketcap_gdp','fund_allocation','pbc_bank','financial_annual','executive_changes','qmt_t2108','ashare_snapshot','ashare_public','legulegu_pb','nfra_insurance','legulegu_gdp',
         'pbc_custody','wealth_allocation','citic_broker','chinabond_wealth','wt_t2108','wt_breadth','shareholder_changes',
         CSI_KIND, STOCK_KIND, WT_INDEX_KIND, WT_STOCK_KIND, WT_GOV10Y, wt_margin_summary.KIND, *WT_DERIVED, *etf_flow.ETF_KINDS}
STRUCTURE_KINDS = {CSI_KIND, STOCK_KIND, WT_INDEX_KIND, WT_STOCK_KIND}
WT_LOCAL_KINDS = {'wt_breadth', 'wt_t2108', WT_INDEX_KIND, WT_STOCK_KIND, WT_GOV10Y, wt_margin_summary.KIND, *WT_DERIVED, *etf_flow.ETF_KINDS}
SOURCE_FIELDS = {'id','kind','url','referer','tables','datasets','derived_metrics','window_mode',
    'minimum_sample_count','symbols','minimum_universe','timeout_seconds','overlap_days','max_pages',
    'sql_id','products','reports','params','qualification','replace_tables','scope','bse_history','minimum_bse_universe',
    'input_manifest','input_sha256','input_directory','bse_verify_disclosures','date_policy','history_from'}


def _need(value):
    if not value:
        raise ObservationError('invalid_collection_configuration','观察采集配置或内容身份无效',422)


def _secret_key(key):
    return re.sub(r'[-_.]','',key).lower() in {
        'token','accesstoken','apikey','password','secret','authorization','credentials'}


def _url(value,hosts=None):
    _need(type(value) is str and 0<len(value)<=2048 and not any(ord(c)<33 for c in value))
    try:
        parts=urlsplit(value)
        _need(parts.scheme in ('http','https') and parts.hostname is not None and not parts.fragment
            and (hosts is None or parts.hostname in hosts) and parts.username is None
            and parts.password is None and parts.port in (None,80,443)
            and not any(_secret_key(key) for key,_ in parse_qsl(parts.query,keep_blank_values=True)))
    except (ValueError,UnicodeError):_need(False)


def _public_json(value):
    count=0
    def visit(node,depth=0):
        nonlocal count
        count+=1;_need(count<=30000 and depth<=32)
        if type(node) is dict:
            _need(len(node)<=10000)
            for key,item in node.items():
                _need(type(key) is str and 0<len(key)<=200 and not _secret_key(key))
                visit(item,depth+1)
        elif type(node) is list:
            _need(len(node)<=10000)
            for item in node:visit(item,depth+1)
        elif type(node) is float:_need(math.isfinite(node))
        elif type(node) is int:_need(-(2**63)<=node<2**63)
        elif type(node) is str:
            _need(len(node)<=10000)
            if node.startswith(('http://','https://')):_url(node)
        else:_need(node is None or type(node) is bool)
    visit(value)


def load_configuration(path, expected_sha256):
    _need(type(expected_sha256) is str and re.fullmatch('[a-f0-9]{64}',expected_sha256) is not None)
    try:
        with Path(path).open('rb') as stream:
            body=stream.read(1024*1024+1)
        _need(len(body)<=1024*1024 and hashlib.sha256(body).hexdigest()==expected_sha256)
        def unique(pairs):
            value={}
            for key,item in pairs:
                _need(key not in value);value[key]=item
            return value
        def reject(_): raise ValueError('nonfinite')
        value=json.loads(body,object_pairs_hook=unique,parse_constant=reject)
        validate_configuration(value)
        return value
    except (OSError,UnicodeError,ValueError,TypeError,KeyError,OverflowError,RecursionError):
        raise ObservationError('invalid_collection_configuration','观察采集配置或内容身份无效',422) from None


def validate_configuration(value):
    _public_json(value)
    _need(type(value) is dict and set(value)=={'schema_version','timeout_seconds','max_days_per_batch',
        'allowed_hosts','models','schedule','sources','budget','retry_seconds','max_window_attempts'})
    _need(value['schema_version']=='guanheng.observation-sources.v1')
    _need(type(value['timeout_seconds']) in (int,float) and 0<value['timeout_seconds']<=60)
    _need(type(value['max_days_per_batch']) is int and 1<=value['max_days_per_batch']<=366)
    hosts=value['allowed_hosts']
    _need(type(hosts) is list and len(hosts)<=64 and all(type(h) is str for h in hosts)
        and len(set(hosts))==len(hosts))
    _need(all(type(h) is str and re.fullmatch(r'[a-z0-9-]+(?:\.[a-z0-9-]+)+',h)
        and not h.replace('.','').isdigit() for h in hosts))
    schedule=value['schedule']
    _need(type(schedule) is dict and {'timezone','times','poll_seconds'}<=set(schedule)
        and set(schedule)<={'timezone','times','poll_seconds','start_date','date_policy','wt_repair_enabled'})
    if 'wt_repair_enabled' in schedule:
        _need(type(schedule['wt_repair_enabled']) is bool and schedule.get('date_policy')=='source-aware-v1')
    from .schedule_policy import valid_schedule_times
    _need(schedule['timezone']=='Asia/Shanghai' and valid_schedule_times(schedule['times']))
    _need('date_policy' not in schedule or schedule['date_policy']=='source-aware-v1')
    _need(len(schedule['times'])==1 or schedule.get('date_policy')=='source-aware-v1')
    _need(type(schedule['poll_seconds']) in (int,float) and 1<=schedule['poll_seconds']<=60)
    if 'start_date' in schedule:
        _need(date.fromisoformat(schedule['start_date']).isoformat()==schedule['start_date'])
    _need(type(value['retry_seconds']) in (int,float) and 1<=value['retry_seconds']<=3600)
    _need(type(value['max_window_attempts']) is int and 1<=value['max_window_attempts']<=8)
    budget=value['budget']
    _need(type(budget) is dict and set(budget)=={'seconds','max_requests','max_bytes','response_bytes'})
    for key,maximum in [('seconds',600),('max_requests',1024),('max_bytes',256*1024*1024),('response_bytes',16*1024*1024)]:
        _need(type(budget[key]) is int and 1<=budget[key]<=maximum)
    # 原观察来源保留32个名额。WT结构、ETF和复合图各使用已登记的独立回执。
    _need(type(value['models']) is dict and type(value['sources']) is list and 1<=len(value['sources'])<=38)
    _need(all(type(source) is dict and type(source.get('kind')) is str for source in value['sources']))
    _need(sum(source['kind'] not in STRUCTURE_KINDS | {*etf_flow.ETF_KINDS,*WT_DERIVED}
              for source in value['sources'])<=32)
    _need(hosts or all(type(source) is dict and source.get('kind') in WT_LOCAL_KINDS | {'qmt_t2108','ashare_snapshot'}
                       for source in value['sources']))
    for alternatives in ((STOCK_KIND, WT_STOCK_KIND), (CSI_KIND, WT_INDEX_KIND)):
        _need(sum(isinstance(source, dict) and source.get('kind') in alternatives for source in value['sources']) <= 1)
    identities=set()
    for source in value['sources']:
        _need(type(source) is dict and {'id','kind'}<=set(source) and not set(source)-SOURCE_FIELDS
            and type(source['kind']) is str and source['kind'] in KINDS)
        _need('history_from' not in source or source['kind'] in STRUCTURE_KINDS | {WT_GOV10Y,wt_margin_summary.KIND,*etf_flow.ETF_KINDS,*WT_DERIVED})
        if schedule.get('date_policy')=='source-aware-v1':
            _need(source.get('date_policy') in ('calendar-day','cn-closed-day','hk-closed-day','cn-prior-day'))
            # 允许保守的前日口径只用于已接入的 WT 事实；其他登记来源沿各自截止。
            if source['date_policy']=='cn-prior-day':_need(source['kind'] in WT_LOCAL_KINDS)
            markets=('cn','hk') if source['date_policy']=='hk-closed-day' else ('cn',)
            _need(all(value['models'].get('calendars',{}).get(market,{}).get('kind')=='official-exchange-calendar/v1' for market in markets))
        else:_need('date_policy' not in source)
        identity=source['id'];_need(type(identity) is str and re.fullmatch('[a-zA-Z0-9_.-]{1,100}',identity) and identity not in identities)
        identities.add(identity)
        for key in ('url','referer'):
            if key not in source:continue
            _url(source[key],hosts)
        _need('url' in source or source['kind'] in WT_LOCAL_KINDS | {'baostock','wondertrader','qmt_t2108','ashare_snapshot'})
        if source['kind'] in (CSI_KIND, STOCK_KIND):
            stock=source['kind']==STOCK_KIND
            fields={'id','kind','url','tables','overlap_days','date_policy','history_from'}
            if stock:fields.add('minimum_sample_count')
            _need(set(source)==fields and source['date_policy']=='cn-closed-day'
                and source['url']==(TUSHARE_URL if stock else CSI_URL)
                and source['tables']==([STOCK_TABLE] if stock else list(INDEX_TABLES.values()))
                and date.fromisoformat(source['history_from']).isoformat()==source['history_from']
                and source['history_from']>=FIRST_DAY
                and 0<source['overlap_days']<value['max_days_per_batch'])
            if stock:_need(type(source['minimum_sample_count']) is int and 1<=source['minimum_sample_count']<6000)
            _need(sum(item.get('kind')==source['kind'] for item in value['sources'] if type(item) is dict)==1)
        elif source['kind'] in (WT_INDEX_KIND, WT_STOCK_KIND):
            tables = [STOCK_TABLE] if source['kind'] == WT_STOCK_KIND else list(INDEX_TABLES.values())
            _need(set(source)=={'id','kind','tables','date_policy','history_from','overlap_days'}
                and source['date_policy']=='cn-prior-day' and source['tables']==tables
                and date.fromisoformat(source['history_from']).isoformat()==source['history_from']
                and source['history_from']>=FIRST_DAY
                and 0<=source['overlap_days']<value['max_days_per_batch'])
        elif source['kind'] == WT_GOV10Y:
            _need(set(source)=={'id','kind','tables','date_policy','history_from','overlap_days'}
                and source['tables']==[GOV10Y_TABLE] and source['date_policy']=='cn-closed-day'
                and date.fromisoformat(source['history_from']).isoformat()==source['history_from']
                and 0<=source['overlap_days']<value['max_days_per_batch']
                and sum(GOV10Y_TABLE in item.get('tables', []) for item in value['sources'] if type(item) is dict) == 1)
        elif source['kind'] == wt_margin_summary.KIND:
            _need(set(source) == {'id','kind','tables','datasets','date_policy','history_from','overlap_days'}
                and source['tables'] == [wt_margin_summary.TABLE]
                and source['datasets'] == list(wt_margin_summary.DATASETS)
                and source['date_policy'] == 'cn-closed-day'
                and date.fromisoformat(source['history_from']).isoformat() == source['history_from']
                and 0 <= source['overlap_days'] < value['max_days_per_batch']
                and sum(bool(set(item.get('datasets', [])) & set(wt_margin_summary.DATASETS))
                        for item in value['sources'] if type(item) is dict) == 1)
        elif source['kind'] in etf_flow.ETF_KINDS:
            cap=source['kind']==etf_flow.CAP_KIND
            symbols=list(etf_flow.CAP_FUNDS) if cap else sorted(etf_flow.FUNDS)
            metrics=[etf_flow.CAP_METRIC] if cap else [etf_flow.metric(symbol) for symbol in symbols]
            _need(set(source)=={'id','kind','symbols','datasets','date_policy','history_from','overlap_days'}
                and source['date_policy']=='cn-prior-day'
                and source['symbols']==symbols and source['datasets']==metrics
                and date.fromisoformat(source['history_from']).isoformat()==source['history_from']
                and 0<=source['overlap_days']<value['max_days_per_batch']
                and sum(item.get('kind')==source['kind'] for item in value['sources'] if type(item) is dict)==1)
        elif source['kind'] in WT_DERIVED:
            _need(set(source)=={'id','kind','datasets','date_policy','history_from','overlap_days'}
                and source['date_policy']=='cn-prior-day' and source['datasets']==[WT_DERIVED[source['kind']].METRIC]
                and date.fromisoformat(source['history_from']).isoformat()==source['history_from']
                and 0<=source['overlap_days']<value['max_days_per_batch']
                and sum(item.get('kind')==source['kind'] for item in value['sources'] if type(item) is dict)==1)
        elif source['kind']=='wt_breadth':
            from .breadth_models import ASHARE_METRICS
            _need(set(source.get('datasets',[]))==set(ASHARE_METRICS)and source.get('tables')==['source.ashare_day_universe'])
            _need(not {'url','referer','symbols','input_manifest','input_sha256','input_directory','scope','bse_history','replace_tables','window_mode'}&set(source))
            calendar=value['models'].get('calendars',{}).get('cn',{})
            _need(type(calendar)is dict and calendar.get('kind')=='official-exchange-calendar/v1')
        elif source['kind']=='wt_t2108':
            from .t2108_models import METRIC,UNIVERSE
            _need(source.get('datasets')==[METRIC] and source.get('tables')==[UNIVERSE])
            _need(not {'url','referer','symbols','input_manifest','input_sha256','input_directory','scope','bse_history','replace_tables','window_mode'} & set(source))
            calendar=value['models'].get('calendars',{}).get('cn',{})
            _need(type(calendar)is dict and calendar.get('kind')=='official-exchange-calendar/v1')
        elif source['kind']=='shareholder_changes':
            from .shareholder_archive import METRIC
            from .shareholder_source import URL
            _need(set(source)=={'id','kind','url','datasets','date_policy','overlap_days','max_pages'}
                and source['url']==URL and source['datasets']==[METRIC]
                and source['date_policy']=='calendar-day'
                and type(source['max_pages']) is int and 1<=source['max_pages']<=16
                and type(source['overlap_days']) is int and 0<=source['overlap_days']<value['max_days_per_batch'])
            _need(sum(item.get('kind')=='shareholder_changes' for item in value['sources'] if type(item) is dict)==1)
        elif source['kind']=='qmt_t2108':
            from .t2108_models import METRIC,UNIVERSE
            if 'input_directory' in source:
                _need(not {'input_manifest','input_sha256'} & set(source)
                    and type(source['input_directory']) is str and Path(source['input_directory']).is_absolute())
                _need(type(value['models']) is dict)
                calendars=value['models'].get('calendars',{});_need(type(calendars) is dict)
                calendar=calendars.get('cn',{})
                _need(type(calendar) is dict and calendar.get('kind')=='official-exchange-calendar/v1')
            else:
                _need(type(source.get('input_manifest')) is str and Path(source['input_manifest']).is_absolute()
                    and type(source.get('input_sha256')) is str and re.fullmatch('[a-f0-9]{64}',source['input_sha256']))
            _need(source.get('datasets')==[METRIC] and source.get('tables')==[UNIVERSE])
            _need(not {'url','referer','symbols','replace_tables','window_mode','scope','bse_history'} & set(source))
        elif source['kind'] in ('pbc_custody','wealth_allocation','citic_broker','chinabond_wealth'):
            from . import institution_reports, bond_mtm
            # 修复原报告数值入口，范围和URL固定；各自报告游标不被其它机构最新日遮盖。
            url,metrics,tables={
                'pbc_custody':(institution_reports.PBC_URL,['bond.custody'],[]),
                'wealth_allocation':(institution_reports.WEALTH_URL,['holdings_wealth'],[]),
                'citic_broker':(institution_reports.CITIC_URL,['holdings_broker'],[]),
                'chinabond_wealth':(bond_mtm.URL,[],[bond_mtm.TABLE]),
            }[source['kind']]
            _need(source.get('url')==url and source.get('datasets',[])==metrics
                and source.get('tables',[])==tables and source.get('window_mode')=='report_latest')
            _need(source.get('overlap_days')==0)
            _need(not {'input_manifest','input_sha256','input_directory','symbols','replace_tables','scope','bse_history','params','referer','reports'} & set(source))
            if source['kind']=='citic_broker':
                _need(type(source.get('max_pages')) is int and 1<=source['max_pages']<=8)
            else:_need('max_pages' not in source)
            _need(source.get('derived_metrics',[])==([bond_mtm.METRIC] if source['kind']=='chinabond_wealth' else []))
        elif source['kind']=='nfra_insurance':
            # 固定官方原寿险/财险口径；季度窗口沿原报告游标，分页容量显式登记。
            _need(source.get('datasets')==['holdings_life','holdings_property'] and not source.get('tables')
                and source.get('url')=='https://www.nfra.gov.cn/'
                and source.get('window_mode')=='report_latest'
                and type(source.get('max_pages')) is int and 3<=source['max_pages']<=20)
            _need(not {'input_manifest','input_sha256','input_directory','symbols','replace_tables','scope','bse_history','params','referer'} & set(source))
        elif source['kind']=='legulegu_gdp':
            # 只接原全A页面快照，月末模型和observed归属保持独立。
            _need(source.get('datasets')==['valuation_marketcap_gdp_latest'] and not source.get('tables')
                and source.get('url')=='https://legulegu.com/stockdata/marketcap-gdp'
                and source.get('window_mode')=='report_latest')
            _need(not {'input_manifest','input_sha256','input_directory','symbols','replace_tables','scope','bse_history','params','referer','derived_metrics'} & set(source))
        elif source['kind']=='legulegu_pb':
            # 固定原报告值口径；配置不接受其他市场或独立计算器的输出身份。
            _need(source.get('datasets')==['pb_all'] and not source.get('tables')
                and source.get('url')=='https://legulegu.com/api/stock-data/market-index-pb'
                and source.get('referer')=='https://legulegu.com/stockdata/all-pb'
                and source.get('window_mode')=='report_latest')
            _need(not {'input_manifest','input_sha256','input_directory','symbols','replace_tables','scope','bse_history','params'} & set(source))
        elif source['kind']=='ashare_snapshot':
            _need('input_directory' not in source)
            from .breadth_models import ASHARE_METRICS
            from .ashare_source import UNIVERSE
            _need(type(source.get('input_manifest')) is str and Path(source['input_manifest']).is_absolute()
                and type(source.get('input_sha256')) is str and re.fullmatch('[a-f0-9]{64}',source['input_sha256'])
                and set(source.get('datasets',[]))==set(ASHARE_METRICS) and source.get('tables')==[UNIVERSE])
            _need(not {'url','referer','symbols','replace_tables','window_mode','scope','bse_history'} & set(source))
        elif source['kind']=='ashare_public':
            _need('input_directory' not in source)
            from .breadth_models import ASHARE_METRICS
            from .ashare_source import UNIVERSE
            _need(set(source.get('datasets',[]))==set(ASHARE_METRICS) and source.get('tables')==[UNIVERSE]
                and source.get('max_pages')==16 and 'www.bse.cn' in hosts)
            _need(not {'input_manifest','input_sha256','symbols','replace_tables','window_mode','scope','bse_history','reports'} & set(source))
        else:_need(not {'input_manifest','input_sha256','input_directory'} & set(source))
        for key in ('tables','datasets','derived_metrics','symbols','products'):
            if key in source:
                _need(type(source[key]) is list and 1<=len(source[key])<=128
                    and all(type(item) is str and 0<len(item)<=100 for item in source[key])
                    and len(set(source[key]))==len(source[key]))
        if source['kind']=='baostock':
            from .breadth_models import SHSZ_METRICS as METRICS
            if set(source.get('datasets',[])) & set(METRICS):
                _need({'source.cn_calendar','source.shsz_universe'}<=set(source.get('tables',[]))
                    and 'pb_shsz_daily' in source['datasets'])
        if source['kind'] in ('financial_annual','executive_changes'):
            scope=source.get('scope','shsz');_need(scope in ('shsz','ashare'))
            if scope=='ashare':
                _need('www.bse.cn' in hosts and type(source.get('minimum_bse_universe')) is int
                    and 1<=source['minimum_bse_universe']<=2000)
                _bse_history(source.get('bse_history'),hosts)
            else:_need(not {'bse_history','minimum_bse_universe'} & set(source))
        elif {'scope','bse_history','minimum_bse_universe'} & set(source):_need(False)
        if 'bse_verify_disclosures' in source:
            _need(source['kind']=='executive_changes' and source.get('scope')=='ashare'
                and type(source['bse_verify_disclosures']) is bool)
        if source['kind']=='financial_annual':
            from .financial_models import METRICS
            years=source.get('reports')
            _need(type(years) is list and 1<=len(years)<=5
                and all(type(year) is int and 1990<=year<=2100 for year in years)
                and years==list(range(years[0],years[-1]+1)))
            _need(source.get('window_mode')=='report_latest' and type(source.get('max_pages')) is int
                and 1<=source['max_pages']<=16 and type(source.get('minimum_universe')) is int
                and 1<=source['minimum_universe']<=10000
                and set(source.get('datasets',[]))=={key for key in METRICS if key.endswith('.'+scope)}
                and source.get('tables')==['source.financial_'+scope+'_universe'])
        if source['kind']=='executive_changes':
            from .executive_models import SCOPES
            years=source.get('reports')
            _need(type(years) is list and 1<=len(years)<=5
                and all(type(year) is int and 1990<=year<=2100 for year in years)
                and years==list(range(years[0],years[-1]+1))
                and source.get('window_mode')=='report_latest' and type(source.get('max_pages')) is int
                and 1<=source['max_pages']<=16 and type(source.get('minimum_universe')) is int
                and 1<=source['minimum_universe']<=10000 and set(source.get('datasets',[]))==set(SCOPES[scope])
                and source.get('tables')==['source.executive_'+scope+'_universe'])
        if source['kind']=='tencent':
            _need('symbols' in source and all(re.fullmatch(r'hk[A-Z0-9]+',s) for s in source['symbols']))
        if source['kind']=='wondertrader':
            _need(source.get('replace_tables') is True and 'symbols' in source and 1<=len(source['symbols'])<=32
                and all(re.fullmatch(r'(?:sh|sz)\d{6}',s) for s in source['symbols']))
        for key,maximum in [('max_pages',16),('minimum_universe',10000),('minimum_sample_count',100000),('overlap_days',366)]:
            if key in source:_need(type(source[key]) is int and 0<=source[key]<=maximum)
        if 'reports' in source:_need(type(source['reports']) is list and len(source['reports'])<=32)
        if 'timeout_seconds' in source:
            _need(type(source['timeout_seconds']) in (int,float) and 0<source['timeout_seconds']<=60)
        if 'replace_tables' in source:_need(type(source['replace_tables']) is bool)
        if 'window_mode' in source:_need(source['window_mode']=='report_latest')
    return value


def _bse_history(value,hosts):
    """显式历史区间与公告身份准入；真实事实由采集配置owner维护。"""
    def day(text):
        try:return type(text) is str and date.fromisoformat(text).isoformat()==text
        except ValueError:return False
    _need(type(value) is dict and set(value)=={'schema_version','market_open','verified_through','exits'}
        and value['schema_version']=='guanheng.bse-history.v1')
    for key in ('market_open','verified_through'):
        _need(day(value[key]))
    _need(value['market_open']<=value['verified_through'] and type(value['exits']) is list and len(value['exits'])<=2000)
    codes=set()
    for row in value['exits']:
        _need(type(row) is dict and set(row)=={'code','listed_on','delisted_on','source_url','source_sha256'})
        _need(type(row['code']) is str and re.fullmatch(r'\d{6}',row['code']) and row['code'] not in codes)
        codes.add(row['code'])
        for key in ('listed_on','delisted_on'):
            _need(day(row[key]))
        _need(value['market_open']<=row['listed_on']<row['delisted_on']<=value['verified_through'])
        _url(row['source_url'],hosts)
        parts=urlsplit(row['source_url'])
        _need(parts.scheme=='https' and parts.hostname=='www.bse.cn' and parts.path.startswith('/disclosure/')
            and parts.path.endswith('.pdf') and not parts.query and type(row['source_sha256']) is str
            and re.fullmatch(r'[a-f0-9]{64}',row['source_sha256']))
