"""科创50、WT供给事实与Choice公告回购金额的观察投影。"""
from datetime import date,timedelta
from decimal import Decimal

from guanheng_market_client.supplement_facts import IPO_PROCEEDS, SHAREHOLDER_REDUCTION, SH_SZ_SCOPE

from .calendars import official_calendar
from .etf_flow import snapshot_reader, TEMPORARY_STATUS
from .source_fetch import SourceFailure
from . import buyback_announced

KIND = 'wt_ipo_supply'
METRIC = 'structure.ipo_supply'
LABEL = 'IPO减持供给压强与科创50折价'
STAR50 = 'SSE.000688'
PERIOD = 20
YUAN_PER_YI = 100_000_000
INPUTS = {'ipo':IPO_PROCEEDS,'reduction':SHAREHOLDER_REDUCTION,'buyback':None}
GAP_FIELDS = {field:f'{field}_window_missing' for field in INPUTS}
SOURCE_TABLES = (buyback_announced.TABLE,)
OBSERVER_INPUTS = frozenset((*SOURCE_TABLES,METRIC+'.buyback'))


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
                         buyback_basis=buyback_announced.BASIS,  # 分母使用Choice公告累计金额。
                         **amounts,  # 当日三项金额，亿元。
                         **gaps))  # 每项输入在20日窗口中的缺日数。
    return rows


def history(fetch, start, end, client_factory, *, calendar, snapshot_dates, source_tables=None,completion_check=None):
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
            if field=='buyback':continue
            data = request(f'wt_supplement_{metric}',lambda c:c.source_supplement_query(dict(
                snapshot_id=identity,metric=metric,symbols=[SH_SZ_SCOPE],**{'from':days[0],'to':days[-1]},offset=0,limit=2000)),
                absent=('NotSupported','InvalidInput',*TEMPORARY_STATUS))
            if data is None:
                continue
            if data['source_snapshot_id'] != identity or data['source_sha256'] != expected:
                raise SourceFailure('wt_market_snapshot_date_differs')
            amounts[field] = {row['date']:Decimal(row['value']) for row in data['rows'] if row['unit']=='CNY'}
    previous=next((day for day in reversed(opened) if day<days[0]),None)
    first=date.fromisoformat(previous or days[0])+timedelta(days=bool(previous))
    calendar_days=[(first+timedelta(days=i)).isoformat() for i in range((date.fromisoformat(end)-first).days+1)]
    announced=buyback_announced.history(fetch,calendar_days,
        existing=(source_tables or {}).get(buyback_announced.TABLE,()))
    # 非交易日公告并入下一交易日；当日已有完整查询且无公告时使用已核零值。
    by_day={row['date']:Decimal(str(row['amount_cny'])) for row in announced}
    for day in days:
        prior=opened[opened.index(day)-1] if opened.index(day)>0 else None
        first=date.fromisoformat(prior or day)+timedelta(days=bool(prior))
        required=[(first+timedelta(days=i)).isoformat() for i in range((date.fromisoformat(day)-first).days+1)]
        if all(d in by_day for d in required):amounts['buyback'][day]=sum(by_day[d] for d in required)
    # 来源截止后的已获输入在原发布收束预算内完成投影，仍服从原总D及停止信号。
    return {METRIC:calculate(days,closes,amounts,start,check=completion_check or check),buyback_announced.TABLE:announced}


def versioned_history(rows):
    """旧增量分母保留在旧快照；新快照只复用价格和供给输入，重算分母及比例。"""
    return [dict(row,ratio=None,buyback=None,buyback_window_missing=PERIOD,
                 buyback_basis=buyback_announced.BASIS) if row.get('buyback_basis')!=buyback_announced.BASIS
            else row for row in rows]


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
    formula = '（IPO募资20日均值＋可计价重要股东减持估算额20日均值）÷ max（公告中的已回购金额20日均值，1亿元）'
    labels = {'date':('交易日','日期'),'close':('科创50','指数点'),'ratio':('IPO减持供给回购比','倍'),
              'ipo':('IPO募资额','亿元'),'reduction':('可计价重要股东减持估算额','亿元'),'buyback':('公告中的已回购金额','亿元'),
              'buyback_basis':('回购口径','文本')}
    lines = [dict(key=key,name=labels[key][0],unit=labels[key][1],color=color,panel=panel,shown=True,
                  formula=reading,reading=reading) for key,color,panel,reading in (
                     ('close','#238568','main','科创50原始收盘。'),('ratio','#835bb1','context',formula))]
    schema = {key:dict(label=label,unit=unit) for key,(label,unit) in labels.items()}
    schema.update({gap:dict(label=f'{labels[field][0]}20日窗口缺日数',unit='条',data_type='integer')
                   for field,gap in GAP_FIELDS.items()})
    return dict(id=METRIC,board=METRIC,label=LABEL,definition_version=METRIC+'/4',frequency='交易日日终',
        unit='倍',parameters=False,primary_field='ratio',overlay=True,source='WT供给事实与Choice公告回购金额',source_url=buyback_announced.URL,
        formula=formula,reading='比例与科创50收盘同屏。完整20个交易日的三项金额用于计算比例。',
        limitations=['采用沪深口径和1亿元分母下限。减持缺均价时复用历史参考收盘价；日期冲突明细单列剔除，仍缺价时保留当日缺口。',
                     '回购采用Choice当前整理的累计已回购金额，按来源最新公告日汇总，非交易日并入下一交易日；金额沿供应商显示精度。',
                     '该分母反映公告金额，不代表每天实际新增回购资金；旧披露增量口径保留在历史快照。原图事件条件尚未提供。'],
        field_schema=schema,lines=lines)
