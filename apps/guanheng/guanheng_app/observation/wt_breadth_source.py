"""广度类指标只消费同一WT版本的价格与定日参考事实，沿原计算公式。"""
from datetime import datetime,timezone
from decimal import Decimal
from .source_fetch import SourceFailure
from .storage import encode
from .t2108_feed import observation_day
from .calendars import official_calendar
from .market_breadth import stock_day
from .breadth_models import ASHARE_METRICS,rows_for_metrics,universe_row


def history(fetch,source,start,end,client_factory,*,calendar,snapshot_date):
    """日期窗口内的RAW价格一次分片读取，逐日事实经原对象库暂存，复用原stock_day。

    价格缓存仅保留date/close、总条数100万，函数返回后释放；HTTP响应与单日事实
    每次只持有一份。来源原件沿原对象库保留；读取失败保旧，未登记保持真实缺项。
    snapshot_date为本来源的有效截止日，绑定当前WT版本；start/end只限定本批历史窗口。
    """
    last=observation_day(calendar,start,end,check=fetch.budget.remaining)
    calendar_rows,_=official_calendar(calendar,check=fetch.budget.remaining)
    days=[r['date']for r in calendar_rows if r['is_open']==1 and start<=r['date']<=last]
    if not 1<=len(days)<=366:raise SourceFailure('wt_market_daily_range_capacity')
    def request(kind,call,*,allow_missing=False):
        from guanheng_market_client import MarketUnavailable
        fetch.budget.request();client=client_factory(min(fetch.timeout,fetch.budget.remaining()))
        try:response=call(client)
        except MarketUnavailable:raise SourceFailure('wt_market_transport_unavailable')from None
        body=encode(response);fetch.budget.consume(len(body));identity=fetch.objects.put(body)
        fetch.records.append(dict(kind=kind,sha256=identity,source_host='wondertrader',status=200,
            retrieved_at=datetime.now(timezone.utc).isoformat(),media_type='application/json'))
        if allow_missing and response['status']['code']=='Unavailable':return None,identity
        if response['status']['code']!='Ok':raise SourceFailure('wt_market_daily_facts_unavailable')
        return response['data'],identity
    snapshot,_=request('wt_market_snapshot',lambda c:c.source_market_snapshot_query(snapshot_date))
    if snapshot['observation_date']!=snapshot_date or last>snapshot_date:
        raise SourceFailure('wt_market_snapshot_date_differs')
    references={};members=set()
    for day in days:
        facts,identity=request('wt_daily_facts',lambda c:c.source_day_facts_query(day,snapshot['snapshot_id']),allow_missing=day!=last)
        if facts is None:continue
        if day==snapshot['observation_date'] and facts['members']!=snapshot['members']:
            raise SourceFailure('wt_daily_facts_universe_differs')
        references[day]=identity;members.update(facts['members'])
    selected_members=sorted(members);prices={};count=0
    lower=int(min(references).replace('-',''));upper=int(last.replace('-',''))
    for first in range(0,len(selected_members),64):
        selected=selected_members[first:first+64]
        data,_=request('wt_source_daily_history_batch',lambda c:c.source_daily_history_batch_query(dict(
            symbols=selected,**{'from':lower,'to':upper,'limit':2000},adjustment='none',snapshot_id=snapshot['snapshot_id'])))
        for item in data['results']:
            if item['status']['code']not in ('Ok','Unavailable'):
                raise SourceFailure('wt_market_history_read_failed',diagnostic=dict(provider='wondertrader',stage='daily_history_read',failed_symbols_count=1))
            symbol=item['symbol'];closes={}
            if item['status']['code']=='Ok':
                native=item['data']
                if native['source_snapshot_id']!=snapshot['snapshot_id']or native['metadata']['adjustment']!='none':
                    raise SourceFailure('wt_market_snapshot_price_differs')
                for bar in native['bars']:
                    count+=1
                    if count>1000000:raise SourceFailure('wt_market_history_capacity')
                    closes[bar['date']]=bar['close']
            prices[symbol]=closes
    result={key:[]for key in ASHARE_METRICS};result['source.ashare_day_universe']=[]
    market_symbol=lambda s:{'SSE':'sh','SZSE':'sz','BSE':'bj'}[s.split('.')[0]]+'.'+s.split('.')[1]
    fields=['date','code','close','preclose','volume','turn','tradestatus','qualification']
    import json
    for day,identity in sorted(references.items()):
        fetch.budget.remaining();facts=json.loads(fetch.objects.get(identity))['data'];rows=[];stamp=int(day.replace('-',''))
        for original in facts['rows']:
            fact=dict(zip(facts['fields'],original));symbol=fact['symbol'];close=''
            raw=prices.get(symbol,{}).get(stamp);reference=fact['close_reference']
            if raw is not None and reference:
                observed=Decimal(str(raw))
                # 同日原价核对仅容许浮点表示误差；差异保留缺价，不替换成公开源价格。
                if abs(observed-Decimal(reference))<=max(Decimal('1e-8'),abs(observed)*Decimal('1e-9')):close=str(observed)
            rows.append([day,market_symbol(symbol),close,*[fact[k]for k in ('preclose','volume','turn','tradestatus','qualification')]])
        universe=[market_symbol(s)for s in facts['members']]
        value=stock_day(fields,rows,universe,day,scope='ashare',check=fetch.budget.remaining)
        value.update(facts['stats'],known_market_count=len(universe)-facts['stats']['identity_unverified_count'],missing_quote_count=value['missing_stock_count'])
        for key,row in rows_for_metrics(value,ASHARE_METRICS).items():result[key].append(row)
        result['source.ashare_day_universe'].append(universe_row(day,universe,facts['provenance']['universe_sha256']))
    return result
