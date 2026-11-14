"""科创50与沪深IPO减持供给回购比的WT快照投影。"""
from decimal import Decimal

from guanheng_market_client.supplement_facts import BUYBACK_EXECUTION, IPO_PROCEEDS, SHAREHOLDER_REDUCTION, SH_SZ_SCOPE

from .calendars import official_calendar
from .etf_flow import snapshot_reader, TEMPORARY_STATUS
from .source_fetch import SourceFailure

KIND = 'wt_ipo_supply'
METRIC = 'structure.ipo_supply'
LABEL = 'IPO减持供给压强与科创50折价'
STAR50 = 'SSE.000688'
PERIOD = 20
YUAN_PER_YI = 100_000_000
INPUTS = {'ipo':IPO_PROCEEDS,'reduction':SHAREHOLDER_REDUCTION,'buyback':BUYBACK_EXECUTION}
GAP_FIELDS = {field:f'{field}_window_missing' for field in INPUTS}


def calculate(days, closes, inputs, start, *, check=lambda: None):
    """仅使用当前交易日和之前的完整窗口，保留已确认零值。"""
    rows = []
    for i,day in enumerate(days):
        check()
        if day < start:
            continue
        ratio = None
        window = days[max(0,i-PERIOD+1):i+1]
        series = {field:[inputs[field].get(d) for d in window] for field in INPUTS}
        gaps = {GAP_FIELDS[field]:PERIOD-len(values)+values.count(None) for field,values in series.items()}
        if not any(gaps.values()):
            ratio = float((sum(series['ipo'])+sum(series['reduction'])) /
                          max(sum(series['buyback']), PERIOD*YUAN_PER_YI))
        amounts = {field:float(inputs[field][day]/YUAN_PER_YI) if day in inputs[field] else None for field in INPUTS}
        rows.append(dict(date=day,  # 交易日。
                         close=closes.get(day),  # 科创50原始收盘点位。
                         ratio=ratio,  # 20日供给回购比，缺输入为空。
                         **amounts,  # 当日三项金额，亿元。
                         **gaps))  # 每项输入在20日窗口中的缺日数。
    return rows


def history(fetch, start, end, client_factory, *, calendar, snapshot_dates):
    check = fetch.budget.remaining
    if not calendar['coverage_start'] <= start <= end <= min(snapshot_dates) <= max(snapshot_dates) <= calendar['coverage_end']:
        raise SourceFailure('official_calendar_outside_coverage')
    sessions,_ = official_calendar(calendar,check=check)
    opened = [row['date'] for row in sessions if row['is_open'] and row['date']<=end]
    display = [day for day in opened if day>=start]
    if not display:
        return {METRIC:[]}
    days = [day for day in opened if day<start][-(PERIOD-1):]+display
    date_map = {int(day.replace('-','')):day for day in days}
    snapshot,request = snapshot_reader(fetch,client_factory,snapshot_dates)
    identity = snapshot['snapshot_id']
    reply = request('wt_source_daily_history_batch',lambda c:c.source_daily_history_batch_query(dict(
        symbols=[STAR50], **{'from':min(date_map),'to':max(date_map)}, limit=len(days), adjustment='none',snapshot_id=identity)))
    result, = reply['results']
    status = result['status']['code']
    closes = {}
    if status == 'Ok':
        data = result['data']
        if data['source_snapshot_id'] != identity or data['metadata']['adjustment'] != 'none':
            raise SourceFailure('wt_market_snapshot_price_differs')
        closes = {date_map[bar['date']]:bar['close'] for bar in data['bars'] if bar['date'] in date_map}
    elif status not in TEMPORARY_STATUS:
        raise SourceFailure('wt_ipo_supply_prices_unavailable')
    amounts = {field:{} for field in INPUTS}
    expected = snapshot.get('provenance',{}).get('supplement_facts_sha256')
    if expected:
        for field,metric in INPUTS.items():
            data = request(f'wt_supplement_{metric}',lambda c:c.source_supplement_query(dict(
                snapshot_id=identity,metric=metric,symbols=[SH_SZ_SCOPE],**{'from':days[0],'to':days[-1]},offset=0,limit=2000)),
                absent=('NotSupported','InvalidInput',*TEMPORARY_STATUS))
            if data is None:
                continue
            if data['source_snapshot_id'] != identity or data['source_sha256'] != expected:
                raise SourceFailure('wt_market_snapshot_date_differs')
            amounts[field] = {row['date']:Decimal(row['value']) for row in data['rows'] if row['unit']=='CNY'}
    return {METRIC:calculate(days,closes,amounts,start,check=check)}


def row_complete(row):
    return row.get('ratio') is not None and row.get('close') is not None


def missing_inputs(row):
    """返回使该观察日缺值的输入身份，旧行保留可核实的当前日缺项。"""
    missing = [f'{METRIC}.close'] if row.get('close') is None else []
    if row.get('ratio') is not None:
        return missing
    if not any(field in row for field in INPUTS):
        return [METRIC]
    missing_amounts = [f'{METRIC}.{field}' for field, gap in GAP_FIELDS.items()
                       if row.get(gap) or row.get(field) is None]
    return missing + (missing_amounts or [METRIC])


def definition():
    formula = '（IPO募资20日均值＋重要股东减持毛额20日均值）÷ max（披露回购增量20日均值，1亿元）'
    labels = {'date':('交易日','日期'),'close':('科创50','指数点'),'ratio':('IPO减持供给回购比','倍'),
              'ipo':('IPO募资额','亿元'),'reduction':('重要股东减持毛额','亿元'),'buyback':('披露回购执行增量','亿元')}
    lines = [dict(key=key,name=labels[key][0],unit=labels[key][1],color=color,panel=panel,shown=True,
                  formula=reading,reading=reading) for key,color,panel,reading in (
                     ('close','#238568','main','科创50原始收盘。'),('ratio','#835bb1','context',formula))]
    schema = {key:dict(label=label,unit=unit) for key,(label,unit) in labels.items()}
    schema.update({gap:dict(label=f'{labels[field][0]}20日窗口缺日数',unit='条',data_type='integer')
                   for field,gap in GAP_FIELDS.items()})
    return dict(id=METRIC,board=METRIC,label=LABEL,definition_version=METRIC+'/2',frequency='交易日日终',
        unit='倍',parameters=False,primary_field='ratio',overlay=True,source='WT 日线与沪深补充事实',source_url='',
        formula=formula,reading='比例与科创50收盘同屏。完整20个交易日的三项金额用于计算比例。',
        limitations=['采用沪深口径和1亿元分母下限。股东减持含参考价格估算，回购按披露日计增量。'],
        field_schema=schema,lines=lines)
