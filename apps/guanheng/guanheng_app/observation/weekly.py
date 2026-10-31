"""Completed-week continuation using frozen weekly inputs and admitted daily bars."""
import math
import statistics
from datetime import date,timedelta

def continue_weekly(markets,datasets,definitions,ema,as_of):
    baseline=datasets.get('system_c.weekly.oversold',[])
    if not baseline:return
    end=date.fromisoformat(as_of);weeks={r['week_monday']:dict(r) for r in baseline}
    grouped={}
    symbols=('sh000001','hkHSI','hkHSTECH')
    if any(not markets.get(symbol) for symbol in symbols):return
    coverage_start=max(min(markets[symbol]) for symbol in symbols)
    for symbol in symbols:
        grouped[symbol]={}
        for day,bar in sorted(markets.get(symbol,{}).items()):
            observed=date.fromisoformat(day);monday=(observed-timedelta(days=observed.weekday())).isoformat()
            if monday<coverage_start or date.fromisoformat(monday)+timedelta(days=4)>end:continue
            found=grouped[symbol].setdefault(monday,dict(date=day,open=bar['open'],close=bar['close'],high=bar['high'],low=bar['low'],provider_volume=0))
            found.update(date=day,close=bar['close'],high=max(found['high'],bar['high']),low=min(found['low'],bar['low']),provider_volume=found['provider_volume']+bar['provider_volume'])
    common=set(grouped['sh000001'])&set(grouped['hkHSI'])&set(grouped['hkHSTECH'])
    if not common:return
    for week in sorted(common):
        a,h,t=(grouped[s][week] for s in ('sh000001','hkHSI','hkHSTECH'))
        weeks[week]=dict(date=max(a['date'],h['date'],t['date']),week_monday=week,source_sse_date=a['date'],source_hsi_date=h['date'],source_hstech_date=t['date'],open=a['open'],close=a['close'],high=a['high'],low=a['low'],hsi_close=h['close'],hstech_close=t['close'],hstech_provider_volume=t['provider_volume'])
    rows=[weeks[w] for w in sorted(weeks)]
    h=[r['hsi_close'] for r in rows];t=[r['hstech_close'] for r in rows];v=[r['hstech_provider_volume'] for r in rows]
    center=ema(h,20);oversold=ema([max(0,math.log(e/p)) for e,p in zip(center,h)],3);volume=ema(v,20)
    returns=[None]+[math.log(t[i]/t[i-1]) for i in range(1,len(t))];raw=[None]*len(t)
    for i in range(21,len(t)):
        sd=statistics.pstdev(returns[i-20:i])
        if sd>1e-10 and volume[i-1]>0:raw[i]=max(0,-math.log(t[i]/t[i-5])/(sd*math.sqrt(5)))*v[i]/volume[i-1]
    pressure=ema(raw,5)
    for i,row in enumerate(rows):
        row.update(oversold=oversold[i],pressure=pressure[i])
    for key in ('system_c.weekly.oversold','system_c.weekly.pressure'):
        datasets[key]=[dict(r) for r in rows]
        definitions[key]['definition_version']='weekly-revision-consistent/3'
        definitions[key]['weekly_continuation']=dict(method='完整覆盖的实际日线汇成已完成周，修订后重算全部后续EMA；覆盖之前的冻结周输入保持',first_daily_week=min(common),partial_week='等待所属周周五后再接纳',historical_availability='unverified')
