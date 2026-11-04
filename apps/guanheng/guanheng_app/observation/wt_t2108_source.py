"""T2108只消费WT统一快照和批量日线；来源补齐、QMT和原件路径由数据侧拥有。"""
from datetime import datetime,timezone
from decimal import Decimal
from types import SimpleNamespace

from .source_fetch import SourceFailure
from .storage import encode
from .t2108_feed import observation_day
from .t2108_source import _aggregate


def history(fetch,source,start,end,client_factory,*,calendar):
    """固定同一WT快照读全市场40期前复权收盘；原T2108/2计算和缺失口径保持。"""
    day=observation_day(calendar,start,end,check=fetch.budget.remaining)
    def request(kind,call):
        fetch.budget.request();client=client_factory(min(fetch.timeout,fetch.budget.remaining()))
        response=call(client);body=encode(response)
        fetch.budget.consume(len(body));identity=fetch.objects.put(body)
        fetch.records.append(dict(kind=kind,sha256=identity,source_host='wondertrader',status=200,
            retrieved_at=datetime.now(timezone.utc).isoformat(),media_type='application/json'))
        if response['status']['code']!='Ok':raise SourceFailure('wt_market_snapshot_unavailable')
        return response['data']
    snapshot=request('wt_market_snapshot',lambda c:c.source_market_snapshot_query(day))
    if snapshot['observation_date']!=day:raise SourceFailure('wt_market_snapshot_date_differs')
    members=[{'SSE':'sh','SZSE':'sz','BSE':'bj'}[s.split('.')[0]]+'.'+s.split('.')[1]for s in snapshot['members']]
    entries=[];last=int(day.replace('-',''))
    for first in range(0,len(snapshot['members']),64):
        selected=snapshot['members'][first:first+64]
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
                received=[snapshot['source_received_at']],status=status))
        fetch.budget.remaining()
    capture=SimpleNamespace(fetch=fetch,source_kind=snapshot['source_kind'])
    manifest=dict(source_binding_sha256=snapshot['provenance']['source_binding_sha256'])
    return _aggregate(capture,manifest,members,dict(sha256=snapshot['provenance']['universe_sha256']),entries,day)
