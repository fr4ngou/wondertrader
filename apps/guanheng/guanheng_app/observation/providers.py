"""保留专用来源解析；原字节及总预算由统一Fetcher持有。"""
import csv,io,json,math,re
from datetime import date,datetime,timedelta,timezone
from .calculations import equal_pb
from .pcr_quantities import official_quantities
from .source_fetch import SourceFailure
from .baostock_source import BaostockClient

def number(value):
    if value in ('',None,'--','-','null'): return None
    result=float(str(value).replace(',',''))
    if not math.isfinite(result): raise SourceFailure('nonfinite_value')
    return result

def quantity(value):
    value=number(value)
    if value is None or value<0 or not value.is_integer(): raise SourceFailure('invalid_contract_quantity')
    return int(value)

def dates(start,end):
    current=date.fromisoformat(start); last=date.fromisoformat(end)
    while current<=last:
        yield current.isoformat(); current+=timedelta(days=1)


def shsz_daily_pb(fields, rows, listings, day, *, check, minimum_universe=1):
    """沪深估值沿 BaoStock 的完整日线与原上市证券表计算。"""
    from .stock_universe import listed_codes

    required = {'date', 'code', 'tradestatus', 'pbMRQ', 'peTTM'}
    if not required <= set(fields):
        raise SourceFailure('pb_day_schema')
    if not rows:
        raise SourceFailure('pb_day_not_published')
    date_position, code_position, pb_position, pe_position = (
        fields.index(field) for field in ('date', 'code', 'pbMRQ', 'peTTM'))
    returned = set()
    for row in rows:
        check()
        if row[date_position] != day:
            raise SourceFailure('pb_date_mismatch')
        number(row[pb_position])
        number(row[pe_position])
        returned.add(row[code_position])
    active = listed_codes(listings, day, check=check)
    if not active or active - returned:
        raise SourceFailure('pb_missing_eligible_stocks')
    value = equal_pb(fields, rows, set(listings))
    if value['universe_count'] < minimum_universe:
        raise SourceFailure('pb_day_incomplete')
    return value, active


def tencent(fetch, config, start, end):
    updates={}
    for symbol in config['symbols']:
        raw=json.loads(fetch.get(config['url'],dict(param=f'{symbol},day,{start},{end},640,')))
        if raw.get('code') != 0 or symbol not in raw.get('data',{}): raise SourceFailure('market_identity_mismatch')
        rows=[]
        for r in raw['data'][symbol].get('day',[]):
            if not start<=r[0]<=end: continue
            values=[number(x) for x in r[1:6]]
            if any(v is None for v in values[:4]) or min(values[:4])<=0: raise SourceFailure('market_invalid_price')
            rows.append(dict(zip(['date','open','close','high','low','provider_volume'],[r[0],*values])))
        if not rows: raise SourceFailure('market_no_observations')
        updates['market.'+symbol]=rows
    return updates

def baostock_daily(fetch, config, start, end):
    from .breadth_models import SHSZ_METRICS as METRICS,rows_for_metrics,universe_row
    from .market_breadth import stock_day
    from .stock_universe import shsz_listings
    selected=set(config.get('datasets',[])) & set(METRICS)
    derived={key:[] for key in sorted(selected)};universes=[]
    with BaostockClient(fetch,min(fetch.timeout,config.get('timeout_seconds',fetch.timeout))) as client:
        fields,rows=client.table('stock_basic')
        basic_sha=next((record['sha256'] for record in reversed(fetch.records)
                        if record.get('kind')=='stock_basic'),None)
        if selected and basic_sha is None:raise SourceFailure('stock_universe_parent_missing')
        listings=shsz_listings(fields,rows,check=fetch.budget.remaining)
        universe=set(listings)
        if len(universe)<config['minimum_universe']: raise SourceFailure('pb_universe_incomplete')
        fields,rows=client.table('calendar',start,end)
        calendar=[]
        for values in rows:
            row=dict(zip(fields,values));day=row['calendar_date'];flag=row['is_trading_day']
            if flag not in ('0','1') or date.fromisoformat(day).isoformat()!=day:raise SourceFailure('pb_calendar_schema')
            calendar.append(dict(date=day,is_open=int(flag)))
        if [row['date'] for row in calendar]!=list(dates(start,end)):raise SourceFailure('pb_calendar_incomplete')
        trade_dates=[row['date'] for row in calendar if row['is_open']==1]
        result=[]
        for day in trade_dates:
            fields,rows=client.table('stock_daily_batch',day)
            value, expected = shsz_daily_pb(fields, rows, listings, day, check=fetch.budget.remaining,
                                          minimum_universe=config['minimum_universe'])
            if selected:
                calculated=stock_day(fields,rows,sorted(expected),day,check=fetch.budget.remaining)
                for key,row in rows_for_metrics(calculated,selected).items():derived[key].append(row)
                universes.append(universe_row(day,expected,basic_sha))
            result.append(dict(date=day,**value,available_at=None,sse_reference=None))
        updates={'pb_shsz_daily':result,'source.cn_calendar':calendar,**derived}
        if selected:updates['source.shsz_universe']=universes
        return updates

def cffex(fetch,config,start,end):
    output={k:[] for k in ['pcr_ho','pcr_io','pcr_mo',*[f'cffex_{p}' for p in ('if','ih','ic','im')]]}
    for day in dates(start,end):
        if date.fromisoformat(day).weekday()>4: continue
        compact=day.replace('-','')
        url=config['url'].format(month=compact[:6],day=compact[6:],date=compact)
        try: body=fetch.get(url,referer=config['referer'])
        except SourceFailure as exc:
            if exc.code=='source_http_404': continue
            raise
        table=list(csv.reader(io.StringIO(body.decode('gbk'))))
        if not table or table[0][:1]!=['合约代码'] or table[0][4]!='成交量' or table[0][6]!='持仓量':
            raise SourceFailure('cffex_schema_changed')
        contracts={p:[] for p in ('IF','IH','IC','IM')}
        options={p:{cp:dict(oi=0,volume=0) for cp in ('C','P')} for p in ('HO','IO','MO')}; counts={p:0 for p in options}; seen=set()
        for row in table[1:]:
            code=row[0].strip()
            f=re.fullmatch(r'(IF|IH|IC|IM)\d{4}',code)
            option=re.fullmatch(r'(HO|IO|MO)\d{4}-([CP])-\d+(?:\.\d+)?',code)
            if not f and not option: continue
            if code in seen: raise SourceFailure('cffex_duplicate_contract')
            seen.add(code)
            if f: contracts[f[1]].append(dict(contract=code,volume=quantity(row[4]),oi=quantity(row[6]),oi_change=number(row[7]),close=number(row[8]),settlement=number(row[9])))
            if option:
                group=options[option[1]][option[2]]; group['oi']+=quantity(row[6]); group['volume']+=quantity(row[4]); counts[option[1]]+=1
        for product,group in contracts.items():
            if not group: continue
            front=min(group,key=lambda r:r['contract'])
            output['cffex_'+product.lower()].append(dict(date=day,total_oi=sum(r['oi'] for r in group),total_volume=sum(r['volume'] for r in group),total_oi_change=sum(r['oi_change'] for r in group),front_contract=front['contract'],front_oi=front['oi'],front_volume=front['volume'],front_close=front['close'],front_settlement=front['settlement'],available_at=None))
        for product,group in options.items():
            if counts[product]:
                output['pcr_'+product.lower()].append(dict(date=day,call_oi=group['C']['oi'],put_oi=group['P']['oi'],call_volume=group['C']['volume'],put_volume=group['P']['volume'],available_at=None))
    return output

def exchange_options(fetch,config,start,end):
    def statistics(official):
        values={}; partial=False
        for kind in ('oi','volume'):
            counts,quality=official_quantities(official,kind)
            values.update(counts)
            values['official_'+kind+'_quality']=quality
            if quality!='complete_reconciled':
                partial=True
        return dict(values,available_at=None,source_status='官方日末统计；部分口径待核' if partial else '官方日末统计')
    result={}
    for day in dates(start,end):
        if date.fromisoformat(day).weekday()>4: continue
        if config['kind']=='sse':
            raw=json.loads(fetch.get(config['url'],dict(isPagination='false',sqlId=config['sql_id'],tradeDate=day.replace('-','')),config['referer']))
            for row in raw.get('result',[]):
                code=str(row['SECURITY_CODE'])
                if code not in config['products']: continue
                observed=str(row['TRADE_DATE']).replace('-','')[:8]
                if observed!=day.replace('-',''): raise SourceFailure('options_date_mismatch')
                result.setdefault('pcr_'+code,[]).append(dict(date=day,**statistics(row)))
        else:
            raw=json.loads(fetch.get(config['url'],dict(SHOWTYPE='JSON',CATALOGID='ysprdzb',TABKEY='tab1',txtQueryDate=day),config['referer']))
            for tab in raw:
                conditions=tab.get('metadata',{}).get('conditions',[])
                if next((c.get('defaultValue') for c in conditions if c.get('name')=='txtQueryDate'),None)!=day:
                    raise SourceFailure('options_date_mismatch')
                for row in tab.get('data',[]):
                    code=str(row.get('bddm'))
                    if code not in config['products']: continue
                    official={key:row.get(field) for key,field in dict(LEAVES_CALL_QTY='wpcrchys',LEAVES_PUT_QTY='wpcrphys',
                        CALL_VOLUME='rccjl',PUT_VOLUME='rpcjl',LEAVES_QTY='wpchyzs',TOTAL_VOLUME='cjl').items()}
                    result.setdefault('pcr_'+code,[]).append(dict(date=day,**statistics(official)))
    return result

def sgx(fetch,config,start,end):
    if config.get('datasets')==['sgx_a50_monthly']:
        from .sgx_reports import monthly
        return monthly(fetch,config,start,end)
    raw=json.loads(fetch.get(config['url'],dict(days='1y',category='futures',params='base-date,total-volume,open-interest')))
    if str(raw.get('meta',{}).get('code'))!='200': raise SourceFailure('sgx_schema_changed')
    rows=[]
    for r in raw['data']:
        day=datetime.strptime(r['base-date'],'%Y%m%d').date().isoformat()
        if not start<=day<=end: continue
        values={k:number(r[v]) for k,v in dict(oi='open-interest',volume='total-volume').items()}
        row=dict(date=day,**values,basis_points=None,available_at=None)
        for key,value in values.items():
            if value is not None and (value<0 or not value.is_integer()):
                row[key]=None; row['source_'+key+'_raw']=value; row['source_'+key+'_status']='官方源非整手值，单位待核'
            elif value is not None: row[key]=int(value)
        rows.append(row)
    if not rows: raise SourceFailure('sgx_no_observations')
    return {'sgx_a50_daily':rows}

def eastmoney(fetch,config,start,end):
    output={}
    for report in config['reports']:
        rows=[]
        for page in range(1,config.get('max_pages',8)+1):
            params=dict(reportName=report['report'],columns='ALL',pageNumber=page,pageSize=500,
                        sortColumns=report['date_field'],sortTypes=-1,source='WEB',client='WEB')
            if report.get('filter'): params['filter']=report['filter']
            raw=json.loads(fetch.get(config['url'],params)); data=raw.get('result')
            if not data or not isinstance(data.get('data'),list): raise SourceFailure('macro_schema_changed')
            for row in data['data']:
                day=row[report['date_field']][:10]
                if start<=day<=end:
                    mapped={key:number(row.get(field))/report.get('divisor',1) if row.get(field) is not None else None for key,field in report['fields'].items()}
                    rows.append(dict(date=day,**mapped,available_at=None))
            if page>=data['pages'] or not data['data'] or data['data'][-1][report['date_field']][:10]<start: break
        else: raise SourceFailure('macro_page_budget_exceeded')
        current={r['date']:r for r in output.get(report['dataset'],[])}
        for row in rows: current.setdefault(row['date'],{}).update(row)
        output[report['dataset']]=sorted(current.values(),key=lambda r:r['date'])
    return output

def shenwan(fetch,config,start,end):
    rows=[]
    for page in range(1,config.get('max_pages',15)+1):
        raw=json.loads(fetch.get(config['url'],dict(page=page,page_size=1000,index_type='市场表征',start_date=start,end_date=end,type='DAY',swindexcode='all'),config['referer']))
        data=raw['data']; selected=data.get('results',[])
        for row in selected:
            if str(row.get('swindexcode'))!='801003': continue
            day=str(row['bargaindate'])[:10]
            rows.append(dict(date=day,pe=number(row['pe']),weighted_pb=number(row['pb']),reference=number(row['closeindex']),bargainamount=number(row['bargainamount']),turnoverrate=number(row['turnoverrate'])))
        if page*1000>=int(data['count']): break
    else: raise SourceFailure('sw_page_budget_exceeded')
    return {'source.shenwan':rows}

def irs(fetch,config,start,end):
    raw=json.loads(fetch.get(config['url'],config['params'])); day=raw['data']['showDateCN'][:10].replace('/','-')
    rows=[]; history={'date':day,'available_at':None}
    for r in raw['records']:
        tenor=r['tl']; normalized=tenor.lower(); years=number(tenor[:-1])/(12 if normalized.endswith('m') else 1)
        row=dict(date=day,tenor=tenor,tenor_years=years,bid=number(r['optimalBid']),mid=number(r['optimalAvg']),ask=number(r['optimalAsk']),available_at=None)
        rows.append(row); history['mid_'+normalized]=row['mid']
    if len(rows)!=9: raise SourceFailure('irs_tenors_changed')
    return {'swap.mid_history':[history],'liquidity_shibor3m_swap':sorted(rows,key=lambda r:r['tenor_years'])}

def disclosure_check(fetch,config,start,end):
    # New disclosure bytes are retained. An unqualified parser never invents observations.
    fetch.get(config['url'])
    return {}
ADAPTERS=dict(tencent=tencent,baostock=baostock_daily,cffex=cffex,sse=exchange_options,szse=exchange_options,sgx=sgx,eastmoney=eastmoney,shenwan=shenwan,irs=irs,disclosure=disclosure_check)
