"""大陆行情只消费A的原SDK；完整替换后重算，避免跨供应商量字段混用。"""
from datetime import date,timedelta,datetime,timezone
from .source_fetch import SourceFailure
from .storage import encode


def history(fetch, config, start, end, client_factory):
    output={}
    for symbol in config['symbols']:
        rows=[];current=date.fromisoformat(start);last=date.fromisoformat(end);unit=None
        while current<=last:
            stop=min(last,current+timedelta(days=729))
            fetch.budget.request()
            client=client_factory(min(fetch.timeout,fetch.budget.remaining()))
            response=client.source_daily_history_query(dict(exchange='SSE' if symbol.startswith('sh') else 'SZSE',
                code=symbol[2:],**{'from':int(current.strftime('%Y%m%d')),'to':int(stop.strftime('%Y%m%d')),'limit':2000}))
            body=encode(response);fetch.budget.consume(len(body))
            sha=fetch.objects.put(body)
            fetch.records.append(dict(sha256=sha,source_host='wondertrader',kind='source_daily_history',status=200,
                retrieved_at=datetime.now(timezone.utc).isoformat(),media_type='application/json'))
            if response['status']['code']!='Ok':raise SourceFailure('market_source_unavailable')
            data=response['data'];metadata=data['metadata'];volume_unit=metadata['volume_unit']
            if volume_unit not in ('share','lot'):raise SourceFailure('market_volume_unit_unknown')
            if unit is not None and unit!=volume_unit:raise SourceFailure('market_volume_unit_changed')
            unit=volume_unit
            for bar in data['bars']:
                day=datetime.strptime(str(bar['date']),'%Y%m%d').date().isoformat()
                rows.append(dict(date=day,open=bar['open'],close=bar['close'],high=bar['high'],low=bar['low'],
                    provider_volume=bar['volume'],provider_volume_unit=volume_unit,available_at=None))
            fetch.budget.remaining();current=stop+timedelta(days=1)
        if not rows:raise SourceFailure('market_no_observations')
        key='source.csi_all' if symbol=='sh000985' else 'market.'+symbol
        output[key]=rows
    return output
