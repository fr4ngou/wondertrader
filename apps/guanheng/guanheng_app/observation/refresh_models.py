"""完整历史下的保留观察计算；采集和发布由单独owner调度。"""
import math
import statistics
from datetime import date,timedelta
from .query import validate_rows
from .providers import SourceFailure
from .weekly import continue_weekly
from .pcr_context import attach_pcr_context
from .calendars import comparison_calendars

def merge(old, new, *, tenor=False):
    def key(r): return (r['date'],r['tenor_years']) if tenor else r['date']
    items={key(r):dict(r) for r in old}; revisions=[]; seen=set()
    for row in new:
        identity=key(row)
        if identity in seen: raise SourceFailure('duplicate_source_observation')
        seen.add(identity)
        if identity in items:
            changed={k:(items[identity].get(k),v) for k,v in row.items() if items[identity].get(k)!=v}
            if changed: revisions.append(dict(date=row['date'],fields=list(changed)))
            items[identity].update(row)
        else: items[identity]=dict(row)
    result=sorted(items.values(),key=key); validate_rows(result,tenor=tenor)
    return result,revisions

def ema(values, period):
    result=[]; state=None
    for value in values:
        if value is not None: state=value if state is None else state+2/(period+1)*(value-state)
        result.append(state if value is not None else None)
    return result

def comparison_model(tables, datasets, definitions, config):
    """Rebuild only the two-market comparison from its independent calendars."""
    markets={k[7:]:{r['date']:r for r in v} for k,v in tables.items() if k.startswith('market.')}
    if not {'sh000001','hkHSCEI'} <= set(markets): return
    base=config['base_date']; own_activity={}
    calendars, calendar_metadata = comparison_calendars(tables, markets, config)
    for symbol,table in markets.items():
        prior=[]; activity={}; previous_unit=None
        for day,row in sorted(table.items()):
            if day not in calendars['hk' if symbol.startswith('hk') else 'cn']: continue
            # 显式unknown只影响量指标，价格与原量继续可读。保留既有未带
            # 单位字段的归档口径；已声明单位变更时重新积累同单位预热窗口。
            unit=row.get('provider_volume_unit')
            if unit=='unknown':
                activity[day]=None;prior=[];previous_unit=unit;continue
            if unit!=previous_unit:prior=[]
            previous_unit=unit
            volume=row['provider_volume']; activity[day]=volume/statistics.mean(prior[-20:]) if len(prior)>=20 and statistics.mean(prior[-20:])>0 else None
            prior.append(volume)
        own_activity[symbol]=activity
    common=sorted(set(markets['sh000001']) & set(markets['hkHSCEI']) & calendars['cn'] & calendars['hk'])
    old={r['date']:r for r in datasets['crossmarket.hk_a']}; result=[]
    for day in common:
        if day<base or day in config.get('closed_dates',{}).get('hk',[]): continue
        row=dict(old.get(day,dict(date=day,available_at=None)))
        for symbol,prefix in [('sh000001','a'),('hkHSCEI','hscei'),('hkHSI','hsi'),('hkHSTECH','hstech')]:
            value=markets.get(symbol,{}).get(day); first=markets.get(symbol,{}).get(base)
            # 同日价格、原量和量窗口属于本日事实；固定基价只决定重定基列。
            # 独立赋值会清除旧快照中已失去本轮资格的量活跃度。
            if value:
                row.update({prefix+'_close':value['close'],prefix+'_provider_volume':value['provider_volume'],prefix+'_activity':own_activity[symbol].get(day)})
                if first:row[prefix+'_rebased']=100*value['close']/first['close']
        result.append(row)
    datasets['crossmarket.hk_a']=result
    definition=definitions['crossmarket.hk_a']; definition['definition_version']='crossmarket-official-own-trading-days/4'
    definition['market_calendars']=calendar_metadata
    definition['comparison_modes']=['fixed_base','window_return','raw_panels']
    for line in definition['lines']:
        if line['key'].endswith('_activity'): line['formula']='当日同源量字段 / 各市场自身此前20个同单位实际交易日均量；显式unknown单位时为空'

def market_models(tables, datasets, definitions, config,as_of):
    attach_pcr_context(tables,datasets,definitions,config.get('pcr_underlyings',{}))
    markets={k[7:]:{r['date']:r for r in v} for k,v in tables.items() if k.startswith('market.')}
    for prod,symbol in dict(if_='sh000300',ih='sh000016',ic='sh000905',im='sh000852').items():
        prod=prod.rstrip('_'); rows=datasets.get('cffex_'+prod,[]); previous=None
        for row in rows:
            spot=markets.get(symbol,{}).get(row['date'],{}).get('close')
            # 期货披露可先于现货；派生列显式为空，后继同日现货抵达再统一重算。
            row.update(spot_close=spot,
                basis_points=row['front_close']-spot if spot is not None else None,
                basis_pct=(row['front_close']/spot-1)*100 if spot is not None else None)
            row['roll_changed']=float(previous is not None and previous!=row['front_contract']); previous=row['front_contract']
        if rows: datasets['basis_'+prod]=[dict(r) for r in rows]
        if rows and 'basis_'+prod in definitions:
            definitions['basis_'+prod]['field_schema']['sse_reference']=dict(label='上证指数',unit='指数点',missing='同日来源缺失时为null')
    if markets.get('sh000300'):
        old=datasets.get('csi300_daily.reference',[])
        datasets['csi300_daily.reference']=merge(old,[dict(r,available_at=None) for r in markets['sh000300'].values()])[0]
    comparison_model(tables,datasets,definitions,config)
    if {'sh000001','hkHSCEI'}<=set(markets):
        base=config['base_date']
        # Keep the existing System C input calendar independent from the comparison change.
        system_dates=sorted(set(markets.get('sh000001',{})) & set(markets.get('hkHSTECH',{})) & set(markets.get('hkHSI',{})))
        system_dates=[d for d in system_dates if d>=base and d not in config.get('closed_dates',{}).get('hk',[])]
        if system_dates:
            a=[markets['sh000001'][d]['close'] for d in system_dates]; h=[markets['hkHSTECH'][d]['close'] for d in system_dates]; v=[markets['hkHSTECH'][d]['provider_volume'] for d in system_dates]
            ra=[None]+[math.log(a[i]/a[i-1]) for i in range(1,len(a))]; rh=[None]+[math.log(h[i]/h[i-1]) for i in range(1,len(h))]
            ve=ema(v,20); pressure=[]; repair=[]
            for i in range(len(a)):
                if i<21: pressure.append(None); repair.append(None); continue
                sh=statistics.pstdev(rh[i-20:i]); sd=statistics.pstdev([rh[j]-ra[j] for j in range(i-20,i)])
                h5=math.log(h[i]/h[i-5]); a5=math.log(a[i]/a[i-5]); q=v[i]/ve[i-1] if ve[i-1]>0 else None
                pressure.append(max(0,-h5/(sh*math.sqrt(5)))*q if sh>1e-10 and q is not None else None)
                repair.append(max(0,(h5-a5)/(sd*math.sqrt(5)))*q*int(a[i]<statistics.mean(a[i-20:i])) if sd>1e-10 and q is not None else None)
            old={r['date']:r for r in datasets['system_c.research']}; smoothed=ema(pressure,5); repaired=ema(repair,5)
            broad={r['date']:r.get('a_all_volume_field') for r in old.values()}
            broad.update({r['date']:r.get('bargainamount') for r in tables.get('source.shenwan',[])})
            activities=[]
            for i,day in enumerate(system_dates):
                previous=[broad.get(d) for d in system_dates[max(0,i-20):i]]
                activities.append(broad[day]/statistics.mean(previous) if broad.get(day) is not None and len(previous)==20 and all(x is not None for x in previous) and statistics.mean(previous)>0 else None)
            dual=ema([p*math.sqrt(activities[i]) if p is not None and activities[i] is not None else None for i,p in enumerate(pressure)],5)
            # Recompute this candidate from its admitted inputs, including revisions.
            # The repository retains the preceding immutable snapshot unchanged.
            for i,day in enumerate(system_dates):
                old[day]=dict(old.get(day,{}),date=day,pressure=smoothed[i],repair=repaired[i],dual_activity_pressure=dual[i],reference=a[i],hstech_close=h[i],hstech_volume=v[i],a_provider_volume=markets['sh000001'][day]['provider_volume'],a_all_volume_field=broad.get(day),a_all_activity=activities[i],available_at=None)
            datasets['system_c.research']=sorted(old.values(),key=lambda r:r['date'])
            definitions['system_c.research']['definition_version']='system-c-revision-consistent/3'
        continue_weekly(markets,datasets,definitions,ema,as_of)

def spread_and_bond(tables,datasets,config):
    yields={r['date']:r['gov10y_pct'] for r in tables.get('source.gov10y',[])}
    spread={r['date']:dict(r) for r in datasets.get('spread_sw',[])}
    weighted={r['date']:dict(r) for r in datasets.get('pb_sw_daily',[])}
    for day,row in spread.items():
        if day in yields and row.get('pe') and row['pe']>0:
            row.update(gov10y_pct=yields[day],ey_pct=100/row['pe'],spread=100/row['pe']-yields[day])
    for row in tables.get('source.shenwan',[]):
        day=row['date']; pe=row['pe']; y=yields.get(day,spread.get(day,{}).get('gov10y_pct'))
        weighted[day]=dict(date=day,weighted_pb=row['weighted_pb'],reference=row['reference'],sse_reference=None,available_at=None)
        if pe and y is not None:
            spread[day]=dict(date=day,pe=pe,ey_pct=100/pe,gov10y_pct=y,spread=100/pe-y,reference=row['reference'],sse_reference=None,available_at=None)
    if 'spread_sw' in datasets:datasets['spread_sw']=sorted(spread.values(),key=lambda r:r['date'])
    if 'pb_sw_daily' in datasets:datasets['pb_sw_daily']=sorted(weighted.values(),key=lambda r:r['date'])
    if 'bond.erp_rank756' not in datasets:return
    # Scheme two: historical percentile excludes the observation being estimated.
    old={r['date']:dict(r) for r in datasets['bond.erp_rank756']}; rows=sorted(spread.values(),key=lambda r:r['date']); n=config['bond_window']
    calendar={r['date'] for r in datasets.get('csi300_daily.reference',[])}
    prices={r['date']:r['close'] for r in tables.get('source.csi_all',[]) if r['date'] in calendar}
    for i,row in enumerate(rows):
        if i<n: continue
        value=row['spread']; history=[r['spread'] for r in rows[i-n:i]]
        rank=(sum(x<value for x in history)+.5*sum(x==value for x in history))/n
        original=old.get(row['date'],{})
        old[row['date']]=dict(original,date=row['date'],bond_preference=100*(1-rank),spread=value,ey_pct=row['ey_pct'],gov10y_pct=row['gov10y_pct'],csi_all_reference=prices.get(row['date'],original.get('csi_all_reference')),available_at=None)
    datasets['bond.erp_rank756']=sorted(old.values(),key=lambda r:r['date'])

def attach_sse_reference(tables,datasets):
    """同次最终化统一填入期货、基差及估值参考；原源覆盖外归档值保持。"""
    reference={row['date']:row['close'] for row in tables.get('market.sh000001',[])}
    for metric in ('pb_shsz_daily','pb_all','pb_sw_daily','spread_sw',
                   'cffex_if','cffex_ih','cffex_ic','cffex_im',
                   'basis_if','basis_ih','basis_ic','basis_im'):
        for row in datasets.get(metric,[]):
            if row['date'] in reference:row['sse_reference']=reference[row['date']]

def source_window(last,as_of,source,config):
    start=(date.fromisoformat(last)-timedelta(days=source.get('overlap_days',7))).isoformat()
    # Report endpoints have bounded row/page budgets, rather than one request per day.
    # A quarterly source must be able to reach the next disclosure after a 90-day gap.
    end=as_of if source.get('window_mode')=='report_latest' else min(as_of,(date.fromisoformat(start)+timedelta(days=config['max_days_per_batch']-1)).isoformat())
    return start,end

def source_observation_dates(datasets, definitions, metrics):
    """Source cursors follow their observed primary values, never joined prices."""
    return [row['date'] for metric in metrics for row in datasets.get(metric, [])
            if not definitions.get(metric, {}).get('primary_field')
            or row.get(definitions[metric]['primary_field']) is not None]
