"""主要ETF使用同版WT总份额、原始收盘及官方交易日。"""

from datetime import datetime, timezone
from decimal import Decimal

from guanheng_market_client import MarketHTTPError, MarketUnavailable
from guanheng_market_client.supplement_facts import CSI300_INDEX, INDEX_FREE_FLOAT_CAP

from .calendars import official_calendar
from .market_structure_source import wt_snapshot
from .source_fetch import SourceFailure
from .storage import encode

KIND = 'wt_etf_flow'
CAP_KIND = 'wt_csi300_etf_cap'
ETF_KINDS = (KIND, CAP_KIND)
BOARD = 'etf_flow'
CAP_BOARD = 'csi300_etf_cap'
CAP_METRIC = CAP_BOARD + '.ratio'
CAP_FUNDS = ('SSE.510300', 'SSE.510310', 'SSE.510330', 'SZSE.159919')
CAP_LABEL = '沪深300 ETF 市值占比'
TEMPORARY_STATUS = ('Unavailable', 'IoError', 'Timeout', 'Backpressure')
LABEL = '主要 ETF 净申赎'
FUNDS = {
    'SSE.512890': '红利低波 ETF',
    'SSE.510050': '上证50 ETF',
    'SSE.510300': '沪深300 ETF',
    'SSE.588000': '科创50 ETF',
    'SZSE.159949': '创业板50 ETF',
    'SZSE.159781': '双创50 ETF',
}


def metric(symbol):
    return f"{BOARD}.{symbol.split('.')[1]}"


def definition(symbol):
    identifier = metric(symbol)
    label = f"{FUNDS[symbol]}（{symbol.split('.')[1]}）"
    formula = '（当日总份额－前一交易日总份额）×当日未复权收盘价 ÷ 1亿。'
    return dict(
        id=identifier, board=BOARD, label=label, definition_version=identifier + '/1',
        frequency='交易日日终', unit='亿元', parameters=False, primary_field='flow', overlay=True,
        source='WT 日线与 ETF 总份额', source_url='', formula=formula,
        reading='正值为估算净申购，负值为估算净赎回。',
        limitations=['收盘价估算申赎金额。任一相邻交易日份额缺失时留空。基金发生份额折算时需结合公告解释。'],
        field_schema={
            'date': dict(label='交易日', unit='日期'),
            'close': dict(label='ETF未复权收盘价', unit='元'),
            'shares': dict(label='ETF总份额', unit='份'),
            'flow': dict(label='估算净申赎额', unit='亿元'),
        },
        lines=[
            dict(key='close', name='ETF收盘价', unit='元', color='#238568', panel='main',
                 shown=True, formula='WT同日未复权收盘价。', reading='场内价格。'),
            dict(key='flow', name='估算净申赎额', unit='亿元', color='#a56c24', panel='context',
                 axis='right', chart_type='bar', signed=True, shown=True, formula=formula,
                 reading='份额日变化的收盘价估值。'),
        ],
    )


def cap_definition():
    formula = '四只沪深300 ETF 的同日总份额分别乘未复权收盘价后合计，除以沪深300自由流通市值，再乘100。'
    reading = '四只基金为510300、510310、510330和159919。'
    return dict(id=CAP_METRIC, board=CAP_BOARD, label=CAP_LABEL, definition_version=CAP_METRIC+'/1',
        frequency='交易日日终', unit='%', parameters=False, primary_field='ratio', overlay=True,
        source='WT 日线、两交易所总份额与中证指数日报', source_url='',
        formula=formula, reading=reading,
        limitations=['分母沿中证指数日报的自由流通市值。任一输入缺失时占比留空。'],
        field_schema={
            'date': dict(label='交易日', unit='日期'),
            'index_close': dict(label='沪深300', unit='指数点'),
            'etf_cap': dict(label='四只ETF合计市值', unit='亿元'),
            'index_free_float_cap': dict(label='沪深300自由流通市值', unit='亿元'),
            'ratio': dict(label='四只ETF市值占比', unit='%'),
        },
        lines=[
            dict(key='index_close', name='沪深300', unit='指数点', color='#238568', panel='main',
                shown=True, formula='WT同日指数收盘点位。', reading='指数点位。'),
            dict(key='ratio', name='四只ETF市值占比', unit='%', color='#a56c24', panel='context',
                axis='right', shown=True, formula=formula, reading=reading),
        ])


def cap_rows(days, close, shares, denominators):
    rows=[]
    scale=Decimal(100_000_000)
    for day in days:
        inputs=[(close[symbol].get(day),shares[symbol].get(day)) for symbol in CAP_FUNDS]
        numerator=sum(Decimal(str(price))*units for price,units in inputs) if all(
            price is not None and units is not None for price,units in inputs) else None
        denominator=denominators.get(day)
        rows.append(dict(date=day,index_close=close[CSI300_INDEX].get(day),
            etf_cap=float(numerator/scale) if numerator is not None else None,
            index_free_float_cap=float(denominator/scale) if denominator is not None else None,
            ratio=float(100*numerator/denominator) if numerator is not None and denominator is not None else None))
    return rows


def cap_row_complete(row):
    return row.get('ratio') is not None and row.get('index_close') is not None


def calculate(days, first, close, shares):
    """相邻交易日都取得有效份额时才计算当日估算额。"""
    result = []
    previous = None
    for day in days:
        current = shares.get(day)
        price = close.get(day)
        flow = None
        if current is not None and previous is not None and price is not None:
            flow = float((current - previous) * Decimal(str(price)) / Decimal(100_000_000))
        if day >= first:
            result.append(dict(date=day, close=price, shares=float(current) if current is not None else None, flow=flow))
        previous = current
    return result


def snapshot_reader(fetch, client_factory, snapshot_dates):
    """记录同一 WT 快照及该版本下的读取原件。"""
    check = fetch.budget.remaining
    def request(kind, call, *, absent=()):
        fetch.budget.request(kind='sdk')
        try:
            response = call(client_factory(min(fetch.timeout, check())))
        except MarketHTTPError as error:
            response = error.response
            if response['status']['code'] not in absent:
                raise
        body = encode(response)
        fetch.budget.consume(len(body))
        sha = fetch.objects.put(body)
        fetch.records.append(dict(kind=kind, sha256=sha, source_host='wondertrader', status=200,
                                  retrieved_at=datetime.now(timezone.utc).isoformat(), media_type='application/json'))
        if response['status']['code'] in absent:
            return None
        if response['status']['code'] != 'Ok':
            raise SourceFailure('wt_market_snapshot_input_unavailable')
        return response['data']

    snapshot = wt_snapshot(lambda day: request('wt_market_snapshot',
        lambda c: c.source_market_snapshot_query(day), absent=('Unavailable',)), snapshot_dates)
    return snapshot,request


def history(fetch, source, start, end, client_factory, *, calendar, snapshot_dates):
    """先冻结WT快照，再读取已声明ETF的原价及定日总份额。"""
    check = fetch.budget.remaining
    calendar_rows, _ = official_calendar(calendar, check=check)
    if not calendar['coverage_start'] <= start <= end <= min(snapshot_dates) <= max(snapshot_dates) <= calendar['coverage_end']:
        raise SourceFailure('official_calendar_outside_coverage')
    open_days = [row['date'] for row in calendar_rows if row['is_open'] and row['date'] <= end]
    cap = source.get('kind') == CAP_KIND
    previous = start if cap else max((day for day in open_days if day < start), default=start)
    days = [day for day in open_days if day >= previous]
    if not days:
        return {}
    snapshot,request=snapshot_reader(fetch,client_factory,snapshot_dates)
    identity = snapshot['snapshot_id']
    symbols = source['symbols']
    price_symbols = sorted([*symbols,CSI300_INDEX]) if cap else symbols
    dates = {int(day.replace('-', '')): day for day in days}
    prices = request('wt_source_daily_history_batch', lambda c: c.source_daily_history_batch_query(dict(
        symbols=price_symbols, **{'from': min(dates), 'to': max(dates)}, limit=len(dates), adjustment='none',
        snapshot_id=identity)))
    close = {symbol: {} for symbol in price_symbols}
    for item in prices['results']:
        if item['status']['code'] in (TEMPORARY_STATUS if cap else ('Unavailable',)):
            continue
        if item['status']['code'] != 'Ok':
            raise SourceFailure('wt_etf_flow_input_unavailable')
        data = item['data']
        if data['source_snapshot_id'] != identity or data['metadata']['adjustment'] != 'none':
            raise SourceFailure('wt_market_snapshot_price_differs')
        bars = data['bars']
        parts = data.get('provenance', [dict(offset=0, count=len(bars), metadata=data['metadata'])])
        for part in parts:
            if item['symbol']==CSI300_INDEX or part['metadata']['price_unit'] == 'CNY':
                close[item['symbol']].update({dates[row['date']]: row['close']
                    for row in bars[part['offset']:part['offset'] + part['count']] if row['date'] in dates})

    supplement_id = snapshot.get('provenance', {}).get('supplement_facts_sha256')
    def facts(kind, metric_id, symbols, unit, absent):
        values={symbol:{} for symbol in symbols}
        offset=0 if supplement_id else None
        while offset is not None:
            try:
                data=request(kind,lambda c:c.source_supplement_query(dict(snapshot_id=identity,metric=metric_id,
                    symbols=symbols,**{'from':days[0],'to':days[-1]},offset=offset,limit=2000)),absent=absent)
            except MarketUnavailable as error:
                if isinstance(error,MarketHTTPError):
                    raise
                break
            if data is None:
                break
            if data['source_snapshot_id']!=identity or data['source_sha256']!=supplement_id:
                raise SourceFailure('wt_market_snapshot_date_differs')
            for row in data['rows']:
                if row['unit']==unit and Decimal(row['value'])>0:
                    values[row['symbol']][row['date']]=Decimal(row['value'])
            offset=data['selection']['next_offset']
        return values
    unavailable=('NotSupported',*TEMPORARY_STATUS)
    shares=facts('wt_supplement_etf_shares','etf_total_shares',symbols,'share',unavailable)
    if cap:
        denominator=facts('wt_supplement_index_free_float_cap',INDEX_FREE_FLOAT_CAP,[CSI300_INDEX],
                          'CNY',(*unavailable,'InvalidInput'))
        return {CAP_METRIC:cap_rows(days,close,shares,denominator[CSI300_INDEX])}
    return {metric(symbol): calculate(days, start, close[symbol], shares[symbol]) for symbol in symbols}


def attach_board(candidate):
    metrics = [metric(symbol) for symbol in FUNDS if metric(symbol) in candidate['datasets']]
    if metrics:
        if not any(board['id'] == BOARD for board in candidate['boards']):
            candidate['boards'].append(dict(id=BOARD, label=LABEL))
        candidate['preferences']['default_datasets'][BOARD] = metrics[0]
    if CAP_METRIC in candidate['datasets']:
        if not any(board['id']==CAP_BOARD for board in candidate['boards']):
            candidate['boards'].append(dict(id=CAP_BOARD,label=CAP_LABEL))
        candidate['preferences']['default_datasets'][CAP_BOARD]=CAP_METRIC
