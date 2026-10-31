"""Source-specific normalizers with explicit units and disclosure periods."""
import calendar
import json
import re
from urllib.parse import urljoin
from .providers import SourceFailure,number

def report(fetch,config,name,*,filter=None,pages=2):
    rows=[]
    for page in range(1,pages+1):
        params=dict(reportName=name,columns='ALL',pageNumber=page,pageSize=500,sortColumns='TRADE_DATE' if name=='RPT_MUTUAL_DEAL_HISTORY' else 'REPORT_DATE',sortTypes=-1,source='WEB',client='WEB')
        if filter:params['filter']=filter
        raw=json.loads(fetch.get(config['url'],params)); result=raw.get('result')
        if not result or not isinstance(result.get('data'),list):raise SourceFailure('macro_schema_changed')
        rows.extend(result['data'])
        if page>=result['pages']:return rows
    raise SourceFailure('macro_page_budget_exceeded')



def northbound(fetch,config,start,end):
    source=report(fetch,config,'RPT_MUTUAL_DEAL_HISTORY',filter=f'(MUTUAL_TYPE in ("001","003","005"))(TRADE_DATE>=\'{start}\')(TRADE_DATE<=\'{end}\')')
    grouped={}
    for row in source:
        day=row['TRADE_DATE'][:10]; kind=row['MUTUAL_TYPE']
        if not start<=day<=end or kind not in ('001','003','005'):raise SourceFailure('northbound_identity_mismatch')
        if kind in grouped.setdefault(day,{}):raise SourceFailure('duplicate_source_observation')
        grouped[day][kind]=row
    rows=[]
    for day,groups in sorted(grouped.items()):
        if set(groups)!= {'001','003','005'}:raise SourceFailure('northbound_channel_incomplete')
        mapped=dict(date=day,available_at=None)
        for kind,prefix in [('001','sse'),('003','szse'),('005','total')]:
            mapped[prefix+'_turnover']=number(groups[kind]['DEAL_AMT'])/100
            mapped[prefix+'_trades']=number(groups[kind].get('DEAL_NUM'))
        rows.append(mapped)
    if not rows:raise SourceFailure('northbound_not_published')
    return {'northbound_turnover':rows}

def marketcap_gdp(fetch,config,start,end):
    annual={int(r['REPORT_DATE'][:4]):number(r['DOMESTICL_PRODUCT_BASE']) for r in report(fetch,config,'RPT_ECONOMY_GDP') if r['REPORT_DATE'][5:7]=='12'}
    if any(value is None or value<=0 for value in annual.values()):raise SourceFailure('gdp_denominator_invalid')
    rows=[]
    for row in report(fetch,config,'RPT_ECONOMY_STOCK_STATISTICS'):
        year,month=map(int,row['REPORT_DATE'][:7].split('-'))
        day=f'{year:04}-{month:02}-{calendar.monthrange(year,month)[1]:02}'
        sh=number(row['TOTAL_MARKE_SH']);sz=number(row['TOTAL_MARKE_SZ']);gdp=annual.get(year-1)
        # Bounded report pages already contain historical rows. Re-admit these
        # dependencies when annual GDP or an older monthly numerator is revised.
        if day>end or sh is None or sz is None:continue
        if not gdp or gdp<=0 or sh<0 or sz<0:raise SourceFailure('gdp_denominator_invalid')
        rows.append(dict(date=day,ratio=(sh+sz)/gdp,sh_marketcap_yi=sh,sz_marketcap_yi=sz,total_marketcap_yi=sh+sz,gdp_previous_year_yi=gdp,gdp_year=year-1,available_at=None))
    # A mid-month run has no new completed month; the successful raw check remains auditable.
    return {'valuation_marketcap_gdp_monthly':sorted(rows,key=lambda r:r['date']),
            'source.gdp_annual':[dict(date=f'{year}-12-31',value=value,available_at=None)
                                 for year,value in sorted(annual.items()) if f'{year}-12-31'<=end]}


def rebase_gdp_dependencies(tables,datasets):
    """Recompute every known numerator against its revised prior-year fact."""
    annual={int(row['date'][:4]):row['value'] for row in tables.get('source.gdp_annual',[])}
    for metric in ('valuation_marketcap_gdp_monthly','valuation_marketcap_gdp_observed'):
        for row in datasets.get(metric,[]):
            if row.get('ratio') is None:continue
            year=int(row['date'][:4])-1
            denominator=annual.get(year)
            numerator=row.get('total_marketcap_yi')
            if numerator is None and row.get('sh_marketcap_yi') is not None and row.get('sz_marketcap_yi') is not None:
                numerator=row['sh_marketcap_yi']+row['sz_marketcap_yi']
            if denominator is None or numerator is None:continue
            if denominator<=0 or numerator<0:raise SourceFailure('gdp_denominator_invalid')
            row.update(ratio=numerator/denominator,gdp_previous_year_yi=denominator,gdp_year=year)

def fund_allocation(fetch,config,start,end):
    text=fetch.get(config['url'],dict(dt=3,pi=1,pn=1000,mc='zcpzlist',sc='reportdate',st='desc')).decode('utf8')
    found=re.search(r'\bdata\s*:\s*(\[\[.*?\]\])',text,re.S)
    if not found:raise SourceFailure('fund_allocation_schema_changed')
    source=json.loads(found[1]);rows=[];rejected=[]
    for row in source:
        day=row[0];count=number(row[1])
        if not start<=day<=end:continue
        if count is None or count<config['minimum_sample_count']:
            rejected.append(dict(date=day,reason='fund_sample_incomplete',sample_count=count));continue
        stock,bond,cash,total=(number(v) for v in row[2:6])
        if min(stock,bond,cash,total)<0:raise SourceFailure('fund_allocation_invalid_value')
        rows.append(dict(date=day,fund_records=int(count),stock_pct=stock,bond_pct=bond,cash_pct=cash,available_at=None))
    if fetch.records:fetch.records[-1]['excluded_observations']=rejected
    return {'holdings_fund':sorted(rows,key=lambda r:r['date'])}

def pbc_bank(fetch,config,start,end):
    year=int(end[:4]);url=config['url'].format(year=year)
    text=fetch.get(url).decode('utf8')
    anchor=text.find('中资全国性大型银行人民币信贷收支表')
    if anchor<0:raise SourceFailure('pbc_report_directory_changed')
    links=re.findall(r'href=["\']([^"\']+)["\']',text[anchor:anchor+2500])
    selected=next((link for link in links if '.pdf' in link.lower()),None)
    if not selected:raise SourceFailure('pbc_report_not_published')
    body=fetch.get(urljoin(url,selected))
    from .pbc_report import bank_pdf
    rows,metadata=bank_pdf(body,year,start,end,fetch.budget)
    fetch.records[-1]['parsed_document']=metadata
    return {'holdings_bank':rows}
