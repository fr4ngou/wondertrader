"""大陆行情只消费A的原SDK；完整替换后重算，避免跨供应商量字段混用。"""
from datetime import date,timedelta,datetime,timezone
from .source_fetch import SourceFailure
from .storage import encode
from .refresh_models import merge


def prepare_table(key, old, rows, effective):
    """按消费字段接纳原日线；返回完整行、修订及本次未返回的保留日期。

    中证全指背景只消费date/close，旧官方收盘的有效性独立于原生OHLC
    覆盖。其余行情表保持完整替换，原成交量窗口继续使用同一批来源。
    effective为来源截止ISO日期；未来已接纳行与原表谱系均由collection保留。
    """
    incoming={row['date'] for row in rows}
    missing=sorted({row['date'] for row in old if row['date']<=effective}-incoming)
    if key=='source.csi_all':
        prepared,revisions=merge(old,rows)
        return prepared,revisions,missing
    if missing:raise SourceFailure('market_existing_coverage_missing')
    prepared,revisions=merge([row for row in old if row['date']>effective],rows)
    return prepared,revisions,[]


def query_daily(fetch, exchange, code, start, end, client_factory):
    """读取一段未指定形成中视图的归档日线，并保留 SDK 原响应。"""
    fetch.budget.request(kind='sdk')
    client=client_factory(min(fetch.timeout,fetch.budget.remaining()))
    response=client.source_daily_history_query(dict(exchange=exchange,code=code,
        **{'from':int(start.replace('-','')),'to':int(end.replace('-','')),'limit':2000}))
    body=encode(response);fetch.budget.consume(len(body))
    sha=fetch.objects.put(body)
    fetch.records.append(dict(sha256=sha,source_host='wondertrader',kind='source_daily_history',status=200,
        retrieved_at=datetime.now(timezone.utc).isoformat(),media_type='application/json'))
    if response['status']['code']!='Ok':raise SourceFailure('market_source_unavailable')
    return response['data']


def history(fetch, config, start, end, client_factory):
    output={}
    for symbol in config['symbols']:
        key='source.csi_all' if symbol=='sh000985' else 'market.'+symbol
        rows=[];current=date.fromisoformat(start);last=date.fromisoformat(end);unit=None
        while current<=last:
            stop=min(last,current+timedelta(days=729))
            data=query_daily(fetch,'SSE' if symbol.startswith('sh') else 'SZSE',symbol[2:],
                current.isoformat(),stop.isoformat(),client_factory)
            metadata=data['metadata'];volume_unit=metadata['volume_unit']
            # 来源日线允许未知量单位；价格和原量照实归档，量指标单独核资格。
            if key!='source.csi_all':
                if volume_unit not in ('share','lot','unknown'):raise SourceFailure('market_volume_unit_invalid')
                if unit is not None and unit!=volume_unit:raise SourceFailure('market_volume_unit_changed')
            unit=volume_unit
            for bar in data['bars']:
                day=datetime.strptime(str(bar['date']),'%Y%m%d').date().isoformat()
                if key=='source.csi_all':
                    # date为原交易日期，close为原收盘点数；历史首次可知时间未知。
                    rows.append(dict(date=day,close=bar['close'],available_at=None))
                else:
                    rows.append(dict(date=day,open=bar['open'],close=bar['close'],high=bar['high'],low=bar['low'],
                        provider_volume=bar['volume'],provider_volume_unit=volume_unit,available_at=None))
            fetch.budget.remaining();current=stop+timedelta(days=1)
        if not rows:raise SourceFailure('market_no_observations')
        output[key]=rows
    return output
