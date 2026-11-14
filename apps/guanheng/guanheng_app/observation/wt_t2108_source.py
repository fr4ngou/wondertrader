"""T2108只消费WT统一快照和批量日线；来源补齐、QMT和原件路径由数据侧拥有。"""
from datetime import datetime,timezone
from decimal import Decimal
from types import SimpleNamespace

from guanheng_market_client import MarketHTTPError

from .market_structure_source import wt_snapshot
from .source_fetch import SourceFailure
from .storage import encode
from .t2108_feed import observation_day
from .t2108_source import METRIC, _aggregate


def history(fetch,source,start,end,client_factory,*,calendar,snapshot_dates=None):
    """固定同一WT快照读全市场40期前复权收盘；原T2108/2计算和缺失口径保持。"""
    day=observation_day(calendar,start,end,check=fetch.budget.remaining)
    def request(kind,call,*,allow_missing=False):
        fetch.budget.request();client=client_factory(min(fetch.timeout,fetch.budget.remaining()))
        try:
            response=call(client)
        except MarketHTTPError as error:
            if not allow_missing or error.response['status']['code']!='Unavailable':
                raise
            response=error.response
        body=encode(response)
        fetch.budget.consume(len(body));identity=fetch.objects.put(body)
        fetch.records.append(dict(kind=kind,sha256=identity,source_host='wondertrader',status=200,
            retrieved_at=datetime.now(timezone.utc).isoformat(),media_type='application/json'))
        if allow_missing and response['status']['code']=='Unavailable':return None
        if response['status']['code']!='Ok':raise SourceFailure('wt_market_snapshot_unavailable')
        return response['data']
    candidates=[candidate for candidate in snapshot_dates or [day] if candidate>=day]
    snapshot=wt_snapshot(lambda candidate:request('wt_market_snapshot',
        lambda c:c.source_market_snapshot_query(candidate),allow_missing=True),candidates)
    universe=snapshot['members']
    universe_sha=snapshot['provenance']['universe_sha256']
    received_at=snapshot['source_received_at']
    if snapshot['observation_date']>day:
        facts=request('wt_daily_facts',lambda c:c.source_day_facts_query(day,snapshot['snapshot_id']),
                      allow_missing=True)
        if facts is None:
            raise SourceFailure('wt_t2108_historical_universe_missing')
        if facts['date']!=day or facts['source_snapshot_id']!=snapshot['snapshot_id']:
            raise SourceFailure('wt_market_snapshot_date_differs')
        quality=facts.get('qualification',{})
        if quality.get('membership_method')!='same_day_public' or quality.get('membership_as_of')!=day:
            raise SourceFailure('wt_t2108_historical_universe_unqualified')
        universe=facts['members']
        universe_sha=facts['provenance']['universe_sha256']
        received_at=max((received_at,facts['provenance']['source_received_at']),key=datetime.fromisoformat)
    members=[{'SSE':'sh','SZSE':'sz','BSE':'bj'}[s.split('.')[0]]+'.'+s.split('.')[1]for s in universe]
    entries=[];last=int(day.replace('-',''))
    for first in range(0,len(universe),64):
        selected=universe[first:first+64]
        data=request('wt_source_daily_history_batch',lambda c:c.source_daily_history_batch_query(dict(
            symbols=selected,  # 原WT定日股票池分片；无客户端证券替换。
            **{'from':10000101,'to':last,'limit':40},  # 最后40条实际记录；缺日/新股不填充。
            adjustment='front_ratio',  # 供应商当前可见分析价，经WT原生存储读取。
            snapshot_id=snapshot['snapshot_id'])))  # 全部批次固定同一资料与价格目录版本。
        for result in data['results']:
            symbol=result['symbol'];code,exchange=symbol.split('.')[1],symbol.split('.')[0]
            if result['status']['code']not in ('Ok','Unavailable'):
                raise SourceFailure('wt_market_history_read_failed',diagnostic=dict(
                    provider='wondertrader',stage='daily_history_read',failed_symbols_count=1))
            adjusted={};status='empty'
            if result['status']['code']=='Ok':
                facts=result['data']
                if facts['source_snapshot_id']!=snapshot['snapshot_id']or facts['metadata']['adjustment']!='front_ratio':
                    raise SourceFailure('wt_market_snapshot_price_differs')
                for bar in facts['bars']:
                    value=str(bar['date']);label=value[:4]+'-'+value[4:6]+'-'+value[6:]
                    adjusted[label]=Decimal(str(bar['close']))
                status='observed'if adjusted else'empty'
            entries.append(dict(symbol=code+'.'+{'SSE':'SH','SZSE':'SZ','BSE':'BJ'}[exchange],adjusted=adjusted,
                received=[received_at],status=status))
        fetch.budget.remaining()
    capture=SimpleNamespace(fetch=fetch,source_kind=snapshot['source_kind'])
    manifest=dict(source_binding_sha256=snapshot['provenance']['source_binding_sha256'])
    result=_aggregate(capture,manifest,members,dict(sha256=universe_sha),entries,day)
    if snapshot['observation_date']>day:
        result[METRIC][0]['reconstruction_as_of']=snapshot['observation_date']
    return result
