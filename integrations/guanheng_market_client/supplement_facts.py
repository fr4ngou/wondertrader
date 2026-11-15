"""MSF补充事实的唯一纯标准库合同；当前总股本和账户融资均不替代历史市场事实。"""
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
import re

from . import MarketProtocolError, _object, _list, _integer
from .market_snapshot import _day as _snapshot_day, _hash, _clock


INDEX_TURNOVER = 'index_turnover'
SMALL_CAP_INDEX = 'SSE.932000'
INDEX_FREE_FLOAT_CAP = 'index_free_float_market_cap'
CSI300_INDEX = 'SSE.000300'
MARGIN_PURCHASE = 'margin_purchase'
MARGIN_REPORT = 'CN.MARGIN_REPORT'
MARGIN_DAILY_SUMMARY = 'CN.MARGIN_DAILY_SUMMARY'  # 东方财富历史汇总原报表范围。
MARGIN_SUMMARY_FIELDS = {
    'margin_summary_fin_balance': 'fin_balance',  # 融资余额，人民币元。
    'margin_summary_fin_buy': 'fin_buy',  # 融资买入额，人民币元。
    'margin_summary_fin_net_reported': 'fin_net_reported',  # 报表披露的融资净买入额，人民币元，可为负。
    'margin_summary_fin_repay': 'fin_repay',  # 融资偿还额，人民币元。
    'margin_summary_short_balance': 'short_balance',  # 融券余额，人民币元。
    'margin_summary_total_balance': 'total_balance',  # 两融余额，人民币元。
}
SIGNED_MARGIN_SUMMARY = 'margin_summary_fin_net_reported'
IPO_PROCEEDS = 'ipo_gross_proceeds'
SHAREHOLDER_REDUCTION = 'shareholder_reduction_gross'
BUYBACK_EXECUTION = 'buyback_execution_disclosed'
GOV10Y_YIELD = 'government_bond_10y_yield'
GOV10Y_SCOPE = 'CN.GOV10Y'
SHENWAN_SCOPE = 'SW.801003'
SHENWAN_FIELDS = {
    'shenwan_market_pe': ('pe', 'pe', 'multiple'),  # 表示市盈率倍数，保留有符号原值。
    'shenwan_market_pb': ('weighted_pb', 'pb', 'multiple'),  # 申万市场表征日表市净率，倍。
    'shenwan_market_close': ('reference', 'closeindex', 'point'),  # 申万 A 指收盘指数点。
    'shenwan_market_amount': ('bargainamount', 'bargainamount', 'unknown'),  # 保留原成交额数字，单位待核。
    'shenwan_market_turnover': ('turnoverrate', 'turnoverrate', 'pct'),  # 原换手率百分数。
}
SIGNED_REPORT_METRICS = (SIGNED_MARGIN_SUMMARY, 'shenwan_market_pe', 'shenwan_market_pb')
SH_SZ_SCOPE = 'CN.SH_SZ'
LEGACY_METRICS = ('etf_total_shares', 'margin_balance', 'market_turnover', 'market_turnover_proxy')
INDEX_SCOPES = {
    INDEX_TURNOVER: (SMALL_CAP_INDEX, 'BigQuant'),
    INDEX_FREE_FLOAT_CAP: (CSI300_INDEX, 'CSI'),
}
METRICS = LEGACY_METRICS + tuple(INDEX_SCOPES) + (
    MARGIN_PURCHASE, IPO_PROCEEDS, SHAREHOLDER_REDUCTION, BUYBACK_EXECUTION, GOV10Y_YIELD,
    *MARGIN_SUMMARY_FIELDS, *SHENWAN_FIELDS,
)
MAX_CELLS = 60000
MAX_CATALOG_BYTES = 32 * 1024 * 1024
SOURCES = ('QMT', 'SSE', 'SZSE', 'SSE+SZSE', 'Eastmoney', 'BigQuant', 'CSI', 'CNINFO', 'ChinaBond', 'Shenwan')
# 以下字段是MSF03的公开模型，原单位和来源时间逐项保留。
ROW_FIELDS = (
    'date',  # 原事实交易日期，ISO日历日，不表示该日开盘已知。
    'symbol',  # ETF或指数的WT标识，或市场报表及CN.GOV10Y国债收益率范围。
    'metric',  # 补充事实类别；官方、指数及双指数代理各有身份。
    'value',  # 有限十进制字符串，保留原精度；融资净买入额允许负数，零表示已知零。
    'unit',  # share/CNY/pct/multiple/point/unknown。unknown只保留来源原值。
    'source',  # 实际来源标识；SSE+SZSE显式保留两市合并归属。
    'source_sha256',  # 源proof清单SHA，清单字段同本行并引用父原始字节。
    'received_at',  # 本次实收UTC带时区时刻，与历史首次可知分别保存。
    'available_at',  # 历史首次可知UTC时刻；来源没有证明时为None。
)
GAP_FIELDS = (
    'date',  # 缺失事实对应的交易日期。
    'symbol',  # 缺失证券或市场范围。
    'metric',  # 缺失事实类别。
    'reason',  # 固定ASCII原因码，区别未知、空缓存和来源能力不足。
)
CATALOG_FIELDS = (
    'schema',  # 固定不可变目录协议。
    'raw_store',  # 原ContentStore本地绝对目录，属于服务内部引用，不进入查询响应。
    'targets',  # 最多64项metric/symbol/from请求范围。
    'dates',  # 最多2000个已显式声明的升序交易日。
    'policy',  # 显式QMT优先规则，来源资格仍按各原件。
    'qmt_evidence',  # 本轮无凭据能力投影的原件摘要及接缝决策。
    'rows',  # 最多60000条标准事实。
    'gaps',  # 请求范围中尚未取得的单元，不前填或补零。
    'complete',  # 请求单元全部有值；与单位/PIT资格分别判断。
)
REQUEST_FIELDS = (
    'snapshot_id',  # 固定价格、资料及补充目录所属WT快照。
    'metric',  # 本次选择的一种事实类别。
    'symbols',  # 最多64项唯一升序标识。
    'from',  # ISO交易日期下界，闭区间。
    'to',  # ISO交易日期上界，闭区间。
    'offset',  # rows和gaps合并排序后的0..60000偏移。
    'limit',  # 单页最多2000个事实/缺口单元。
)


def _need(condition, reason):
    if not condition:
        raise MarketProtocolError(reason)


def validate_metric_scope(metric, symbol):
    """同一组事实类型和范围同时约束采集计划及公开查询。"""
    _need(type(metric) is str and metric in METRICS, 'supplement metric invalid')
    if metric == 'etf_total_shares':
        _need(type(symbol) is str and re.fullmatch(r'(SSE|SZSE)\.[0-9]{6}', symbol) is not None,
              'supplement ETF identity invalid')
    elif metric in INDEX_SCOPES:
        _need(symbol == INDEX_SCOPES[metric][0], 'supplement index identity invalid')
    elif metric == GOV10Y_YIELD:
        _need(symbol == GOV10Y_SCOPE, 'supplement bond yield scope invalid')
    elif metric in SHENWAN_FIELDS:
        _need(symbol == SHENWAN_SCOPE, 'supplement Shenwan scope invalid')
    elif metric in MARGIN_SUMMARY_FIELDS:
        _need(symbol == MARGIN_DAILY_SUMMARY, 'supplement margin summary scope invalid')
    else:
        expected = MARGIN_REPORT if metric in ('margin_balance',MARGIN_PURCHASE) else SH_SZ_SCOPE
        _need(symbol == expected, 'supplement market scope invalid')


def _reason(value):
    _need(type(value) is str and re.fullmatch(r'[a-z][a-z0-9_]{0,95}', value) is not None,
          'supplement reason code invalid')


def _day(value):
    try:
        return _snapshot_day(value)
    except (ValueError, TypeError):
        raise MarketProtocolError('supplement ISO date invalid') from None


def _utc(value):
    try:
        _clock(value)
        parsed = datetime.fromisoformat(value)
    except (ValueError, TypeError):
        raise MarketProtocolError('supplement UTC clock invalid') from None
    _need(parsed.utcoffset() == timedelta(0), 'supplement clock must be UTC')
    return parsed


def _value_fields(row):
    value = row['value']
    signed = row['metric'] in SIGNED_REPORT_METRICS
    pattern = r'-?[0-9]+(?:\.[0-9]+)?' if signed else r'[0-9]+(?:\.[0-9]+)?'
    _need(type(value) is str and len(value) <= 128
          and re.fullmatch(pattern, value) is not None, 'supplement decimal invalid')
    number = Decimal(value)
    _need(number.is_finite() and (signed or number >= 0), 'supplement decimal invalid')
    expected_unit = (SHENWAN_FIELDS[row['metric']][2] if row['metric'] in SHENWAN_FIELDS
                     else {'etf_total_shares': 'share', GOV10Y_YIELD: 'pct'}.get(row['metric'], 'CNY'))
    _need(row['unit'] in (expected_unit, 'unknown'), 'supplement unit invalid')
    _need(type(row['source']) is str and row['source'] in SOURCES, 'supplement source invalid')
    if row['metric'] in INDEX_SCOPES:
        allowed_sources = (INDEX_SCOPES[row['metric']][1], 'CSI') if row['metric'] == INDEX_TURNOVER else ('CSI',)
        _need(row['source'] in allowed_sources and row['unit'] == 'CNY' and number > 0,
              'supplement index value invalid')
    elif row['metric'] in (MARGIN_PURCHASE, IPO_PROCEEDS, SHAREHOLDER_REDUCTION, *MARGIN_SUMMARY_FIELDS):
        _need(row['source']=='Eastmoney' and row['unit']=='CNY','supplement public report value invalid')
    elif row['metric'] == BUYBACK_EXECUTION:
        _need(row['source']=='CNINFO' and row['unit']=='CNY','supplement public report value invalid')
    elif row['metric'] == GOV10Y_YIELD:
        _need(row['source'] == 'ChinaBond' and row['unit'] == 'pct' and number < 20,
              'supplement bond yield invalid')
    elif row['metric'] in SHENWAN_FIELDS:
        _need(row['source'] == 'Shenwan' and row['unit'] == expected_unit
              and (row['metric'] != 'shenwan_market_close' or number > 0), 'supplement Shenwan value invalid')
    else:
        _need(row['source'] not in ('BigQuant', 'CSI', 'CNINFO', 'ChinaBond', 'Shenwan'),
              'supplement source invalid for metric')


def validate_source_proof(value, row=None):
    """源proof只引用一层父原始字节；与事实字段逐值相同，不递归解释父协议。"""
    fields = (
        'date',  # 此原件证明的事实交易日。
        'symbol',  # ETF证券或明确市场报告范围。
        'metric',  # 此原件证明的事实枚举。
        'value',  # 与目录行完全一致的十进制值；融资净买入额允许负数。
        'unit',  # 与目录行一致的已知单位或unknown。
        'source',  # 实际来源，合计保留SSE+SZSE标识。
    )
    _object(value, ('schema', 'parents') + fields)
    _need(value['schema'] == 'guanheng.supplement-source-proof.v1', 'supplement proof schema invalid')
    _day(value['date'])
    validate_metric_scope(value['metric'], value['symbol'])
    _value_fields(value)
    parents = _list(value['parents'], 4)  # 1..4个父原始字节SHA，原件对象由原ContentStore拥有。
    _need(bool(parents), 'supplement proof parents empty')
    for identity in parents:
        _hash(identity)
    _need(len(set(parents)) == len(parents), 'supplement proof parents repeated')
    if row is not None:
        _need(all(value[key] == row[key] for key in fields), 'supplement proof differs from fact')
    return value


def cell_key(row):
    """目录和分页共用唯一date/metric/symbol排序，不把rows和gaps分别分页。"""
    return row['date'], row['metric'], row['symbol']


def validate_qmt_evidence(value):
    """能力证据只含无凭据投影身份，不执行QMT探测或复制环境。"""
    _object(value, (
        'source_sha256',  # ContentStore中本轮无凭据binding/profile投影摘要。
        'profile_version',  # 本轮实际认证读profile版本，未来升级保持原标识。
        'operations',  # 实际开放operation列表，不能从产品介绍推造能力。
        'decisions',  # 每种事实的接缝决策，含metric和固定reason。
    ))
    _hash(value['source_sha256'])
    profile = value['profile_version']
    _need(type(profile) is str and len(profile) <= 64
          and re.fullmatch(r'qmt\.read-profile\.v[0-9]+', profile) is not None,
          'supplement QMT profile invalid')
    operations = _list(value['operations'], 64)
    _need(all(type(op) is str and re.fullmatch(r'[a-z][a-z0-9_.]{0,95}', op) for op in operations)
          and len(set(operations)) == len(operations), 'supplement QMT operations invalid')
    decisions = _list(value['decisions'], len(METRICS))
    seen = set()
    for decision in decisions:
        _object(decision, ('metric', 'reason'))  # metric是事实枚举；reason是该事实的接缝原因码。
        metric = decision['metric']
        _need(type(metric) is str and metric in METRICS and metric not in seen,
              'supplement QMT decisions invalid')
        _reason(decision['reason'])
        seen.add(metric)
    return value


def _cells(rows, *, gaps=False):
    previous = None
    for row in _list(rows, MAX_CELLS):
        _object(row, GAP_FIELDS if gaps else ROW_FIELDS)
        _day(row['date'])
        validate_metric_scope(row['metric'], row['symbol'])
        key = cell_key(row)
        _need(previous is None or previous < key, 'supplement cells repeated or unordered')
        previous = key
        if gaps:
            _reason(row['reason'])
            continue
        _value_fields(row)
        _hash(row['source_sha256'])
        received = _utc(row['received_at'])
        if row['available_at'] is not None:
            _need(_utc(row['available_at']) <= received, 'supplement available clock exceeds receipt')
    return rows


def validate_supplement_catalog(value):
    """精确核目标单元=事实与缺口的无重叠并集；complete不提升来源、单位或PIT资格。"""
    _object(value, CATALOG_FIELDS)
    _need(value['schema'] == 'guanheng.market-supplement-catalog.v1'
          and value['policy'] == 'qmt_preferred', 'supplement catalog schema or policy invalid')
    raw_store = value['raw_store']
    _need(type(raw_store) is str and Path(raw_store).is_absolute()
          and not raw_store.startswith(('\\\\', '//')), 'supplement raw store path invalid')
    targets = _list(value['targets'], 64)
    _need(bool(targets), 'supplement targets empty')
    scopes = {}
    for target in targets:
        _object(target, ('metric', 'symbol', 'from'))  # 事实类别、证券/市场、显式历史起日。
        validate_metric_scope(target['metric'], target['symbol'])
        first = _day(target['from'])
        key = target['metric'], target['symbol']
        _need(key not in scopes, 'supplement target repeated')
        scopes[key] = first
    dates = _list(value['dates'], 2000)
    for day in dates:
        _day(day)
    _need(dates == sorted(set(dates)), 'supplement dates repeated or unordered')
    validate_qmt_evidence(value['qmt_evidence'])
    evidence_metrics = {row['metric'] for row in value['qmt_evidence']['decisions']}
    _need({key[0] for key in scopes} <= evidence_metrics, 'supplement QMT decision missing')
    _cells(value['rows'])
    _cells(value['gaps'], gaps=True)
    _need(len(value['rows']) + len(value['gaps']) <= MAX_CELLS, 'supplement cell capacity')
    expected = set()
    for (metric, symbol), first in scopes.items():
        for day in dates:
            if day >= first:
                expected.add((day, metric, symbol))
                _need(len(expected) <= MAX_CELLS, 'supplement target capacity')
    actual = {cell_key(row) for row in value['rows']}
    gaps = {cell_key(row) for row in value['gaps']}
    _need(not actual & gaps and actual | gaps == expected, 'supplement target coverage differs')
    _need(type(value['complete']) is bool and value['complete'] == (not gaps),
          'supplement completeness differs')
    return value


def validate_supplement_request(value):
    """只读分页合同：日期闭区间，symbols升序唯一，查询不会补采或前填。"""
    _object(value, REQUEST_FIELDS)
    _hash(value['snapshot_id'])
    symbols = _list(value['symbols'], 64)
    _need(bool(symbols), 'supplement symbols empty')
    for symbol in symbols:
        validate_metric_scope(value['metric'], symbol)
    _need(symbols == sorted(set(symbols)), 'supplement symbols repeated or unordered')
    _need(_day(value['from']) <= _day(value['to']), 'supplement request range invalid')
    _integer(value['offset'], 0, MAX_CELLS)
    _integer(value['limit'], 1, 2000)
    return value


def validate_supplement_data(value, request):
    """核快照身份、统一分页和每条选择范围；空匹配保持Ok空数据。"""
    validate_supplement_request(request)
    _object(value, (
        'schema',  # 固定查询响应协议。
        'source_snapshot_id',  # 同一WT价格、资料及补充事实版本。
        'source_sha256',  # 固定补充目录原字节摘要。
        'rows',  # 当前页取得的事实，值/单位/时间不重新解释。
        'gaps',  # 当前页未取得的目标单元及原因。
        'selection',  # 合并事实及缺口后的统一分页状态。
        'qmt_evidence',  # 原目录本轮QMT能力依据，与行来源分别保存。
    ))
    _need(value['schema'] == 'guanheng.market-supplement-query.v1', 'supplement query schema invalid')
    _hash(value['source_sha256'])
    _hash(value['source_snapshot_id'])
    _need(value['source_snapshot_id'] == request['snapshot_id'], 'supplement snapshot differs')
    _cells(value['rows'])
    _cells(value['gaps'], gaps=True)
    validate_qmt_evidence(value['qmt_evidence'])
    merged = sorted(value['rows'] + value['gaps'], key=cell_key)
    keys = [cell_key(row) for row in merged]
    _need(len(set(keys)) == len(keys), 'supplement query cells overlap')
    for row in merged:
        _need(row['metric'] == request['metric'] and row['symbol'] in request['symbols']
              and request['from'] <= row['date'] <= request['to'], 'supplement query selection differs')
    selection = _object(value['selection'], (
        'offset',  # 合并排序后已跳过单元数。
        'limit',  # 本次请求的最大单元数，含事实和缺口。
        'total',  # 此查询全部匹配的事实及缺口总数。
        'next_offset',  # 下一页偏移；末页或超出范围时为None。
    ))
    _need(_integer(selection['offset'], 0, MAX_CELLS) == request['offset']
          and _integer(selection['limit'], 1, 2000) == request['limit'], 'supplement page differs')
    total = _integer(selection['total'], 0, MAX_CELLS)
    count = min(request['limit'], max(0, total - request['offset']))
    _need(len(merged) == count, 'supplement page size differs')
    expected_next = request['offset'] + count if request['offset'] + count < total else None
    if selection['next_offset'] is not None:
        _integer(selection['next_offset'], 0, MAX_CELLS)
    _need(selection['next_offset'] == expected_next, 'supplement next page differs')
    return value
