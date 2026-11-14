"""根据同一 WT 快照计算券商交易生态过热事件。"""

from decimal import Decimal

from guanheng_market_client import MarketHTTPError, MarketUnavailable
from guanheng_market_client.supplement_facts import CSI300_INDEX, MARGIN_PURCHASE, MARGIN_REPORT

from .calendars import official_calendar
from .etf_flow import snapshot_reader, TEMPORARY_STATUS
from .source_fetch import SourceFailure

KIND = 'wt_broker_heat'
METRIC = 'structure.broker_heat'
LABEL = '交易生态过热后的券商回撤'
BROKER = 'SZSE.300059'
ETF = 'SSE.512880'
PERIOD = 252
RETURN_DAYS = 20


def calculate(days, prices, purchases, first, *, check=lambda: None):
    """按交易日计算滚动指标，仅输出请求区间内的行。"""
    result = []
    previous = None
    for i, day in enumerate(days):
        check()
        heat = relative = support = None
        amount = purchases.get(day)
        if i >= PERIOD-1:
            amounts = [purchases.get(d) for d in days[i-PERIOD+1:i+1]]
            if None not in amounts:
                heat = sum(value <= amount for value in amounts) / PERIOD
        if i >= RETURN_DAYS:
            returns = {}
            for symbol, closes in prices.items():
                window = [closes.get(d) for d in days[i-RETURN_DAYS:i+1]]
                if None not in window:
                    returns[symbol] = 100 * (window[-1] / window[0] - 1)
            support = returns.get(CSI300_INDEX)
            if BROKER in returns and ETF in returns:
                relative = returns[BROKER] - returns[ETF]
        state = None if None in (heat, relative, support) else int(heat >= .7 and relative >= 0 and support >= 0)
        if day >= first:
            result.append(dict(
                date=day,  # 交易日。
                close=prices[CSI300_INDEX].get(day),  # 沪深300指数点位。
                broker_close=prices[BROKER].get(day),  # 东方财富前复权价。
                etf_close=prices[ETF].get(day),  # 证券ETF前复权价。
                purchase=None if amount is None else float(amount / 100_000_000),  # 融资买入额，亿元。
                heat=heat,  # 融资买入额252日经验分位。
                relative=relative,  # 东方财富相对证券ETF的20日收益百分点。
                support=support,  # 沪深300的20日收益百分比。
                event_state=state,  # 0未满足、1过热、空值为条件未知。
                event_code=None if state is None else int(state == 1 and previous == 0),  # 新事件标记。
            ))
        previous = state
    return result


def history(fetch, start, end, client_factory, *, calendar, snapshot_dates):
    check = fetch.budget.remaining
    if not calendar['coverage_start'] <= start <= end <= min(snapshot_dates) <= max(snapshot_dates) <= calendar['coverage_end']:
        raise SourceFailure('official_calendar_outside_coverage')
    sessions, _ = official_calendar(calendar, check=check)
    days = [r['date'] for r in sessions if r['is_open'] and start <= r['date'] <= end]
    if not days:
        return {}
    warmup = [r['date'] for r in sessions if r['is_open'] and r['date'] < days[0]][-PERIOD:]
    dates = {int(day.replace('-', '')): day for day in warmup + days}
    snapshot, request = snapshot_reader(fetch, client_factory, snapshot_dates)
    identity = snapshot['snapshot_id']
    prices = {symbol: {} for symbol in (CSI300_INDEX, BROKER, ETF)}
    for symbols, adjustment in (([CSI300_INDEX], 'none'), (sorted((BROKER, ETF)), 'front_ratio')):
        reply = request('wt_source_daily_history_batch', lambda c: c.source_daily_history_batch_query(dict(
            symbols=symbols, **{'from':min(dates),'to':max(dates)}, limit=len(dates),
            adjustment=adjustment, snapshot_id=identity)))
        for item in reply['results']:
            if item['status']['code'] in TEMPORARY_STATUS:
                continue
            if item['status']['code'] != 'Ok':
                raise SourceFailure('wt_broker_heat_prices_unavailable')
            data = item['data']
            if data['source_snapshot_id'] != identity or data['metadata']['adjustment'] != adjustment:
                raise SourceFailure('wt_market_snapshot_price_differs')
            prices[item['symbol']] = {dates[b['date']]: b['close'] for b in data['bars'] if b['date'] in dates}
    purchases = {}
    supplement = snapshot.get('provenance', {}).get('supplement_facts_sha256')
    if supplement:
        try:
            data = request('wt_supplement_margin_purchase', lambda c: c.source_supplement_query(dict(
                snapshot_id=identity, metric=MARGIN_PURCHASE, symbols=[MARGIN_REPORT],
                **{'from':min(dates.values()),'to':days[-1]}, offset=0, limit=2000)),
                absent=('NotSupported','InvalidInput',*TEMPORARY_STATUS))
        except MarketUnavailable as error:
            if isinstance(error,MarketHTTPError):
                raise
            data = None
        if data is not None:
            if data['source_snapshot_id'] != identity or data['source_sha256'] != supplement:
                raise SourceFailure('wt_market_snapshot_date_differs')
            purchases = {row['date']:Decimal(row['value']) for row in data['rows'] if row['unit']=='CNY'}
    return {METRIC:calculate(warmup + days, prices, purchases, start, check=check)}


def row_complete(row):
    return row.get('event_state') is not None


def missing_inputs(row):
    """用条件的可计算状态区分融资买入额和两组价格窗口。"""
    labels = {'heat':'purchase', 'relative':'relative', 'support':'support'}
    return [f'{METRIC}.{input_id}' for field,input_id in labels.items() if row.get(field) is None] or [METRIC]


def definition():
    formula = '热度为最近252个交易日内融资买入额小于等于当日的比例。热度≥0.7，东方财富相对证券ETF的20日收益≥0，且沪深300的20日收益≥0时为过热。'
    labels = {
        'date':('交易日','日期'), 'close':('沪深300','指数点'),
        'broker_close':('东方财富前复权价','元'), 'etf_close':('证券ETF前复权价','元'),
        'purchase':('融资买入额','亿元'), 'heat':('融资买入热度252日分位','无量纲'),
        'relative':('东方财富相对证券ETF 20日弹性','百分点'), 'support':('沪深300 20日承接','%'),
        'event_state':('过热状态','无量纲'), 'event_code':('新事件标记','无量纲'),
    }
    lines = [
        dict(key=key,name=labels[key][0],unit=labels[key][1],color=color,panel=panel,shown=shown,
             formula=description,reading=description)
        for key,color,panel,shown,description in (
            ('close','#238568','main',True,'沪深300原始收盘。'),
            ('heat','#a56c24','context',True,'融资买入额最近252个交易日的经验分位。'),
            ('relative','#835bb1','context',False,'东方财富20日收益减512880同期收益。'),
            ('support','#287d9c','context',False,'沪深300的20日收益。'),
        )
    ]
    return dict(id=METRIC,board=METRIC,label=LABEL,definition_version=METRIC+'/1',frequency='交易日日终',
        unit='无量纲',parameters=False,primary_field='heat',overlay=True,source='WT 日线与定日融资买入额',
        source_url='',formula=formula,reading='竖线标记过热条件首次同时满足。',
        limitations=['观衡研究口径。使用国泰证券ETF（512880）。历史首次可知时间未知。'],
        field_schema={key:dict(label=label,unit=unit) for key,(label,unit) in labels.items()},lines=lines,
        event_markers=dict(field='event_code',anchor='close',values=[dict(code=1,label=LABEL,color='#a56c24')]))
