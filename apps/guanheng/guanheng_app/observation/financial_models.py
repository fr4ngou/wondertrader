"""年报均值与五年历史分位的业务定义；原观察目录和Shell直接消费。"""

from .financial_source import METRICS as FIELDS, ASHARE_METRICS
from .source_fetch import SourceFailure


METRICS = {
    'earnings.eps.shsz': ('平均EPS · 沪深年报', '元', '基本每股收益'),
    'earnings.roe.shsz': ('平均ROE · 沪深年报', '%', '加权平均净资产收益率'),
}
METRICS.update({key.replace('.shsz','.ashare'):(label.replace('沪深','沪深北'),unit,field)
    for key,(label,unit,field) in list(METRICS.items())})
LABELS = {
    'mean': ('有效样本平均值', None), 'complete_market_mean': ('完整股票池平均值', None),
    'historical_percentile': ('近五年历史分位', '%'), 'rank_periods': ('分位有效年数', '年'),
    'rank_start': ('分位起始报告期', '日期'), 'market_count': ('当年末沪深股票数', '只'),
    'eligible_count': ('参考股票池数量', '只'), 'valid_count': ('有效样本数量', '只'),
    'missing_count': ('尚缺数量', '只'), 'cdr_excluded_count': ('已排除存托凭证数', '只'),
    'alias_excluded_count': ('同公司重复证券数', '只'),
    'missing_report_count': ('缺报告且身份待核数', '只'), 'not_available_count': ('披露或修订晚于截止日', '只'),
    'currency_missing_count': ('人民币币种未确认数', '只'), 'empty_value_count': ('财务值缺失数', '只'),
    'latest_announcement_day': ('样本最新公告日', '日期'), 'latest_revision_day': ('样本最新修订日', '日期'),
}


def definition(metric):
    label, unit, field = METRICS[metric]
    scope='ashare' if metric.endswith('.ashare') else 'shsz'
    market='沪深北' if scope=='ashare' else '沪深'
    formula = f'平均值=当年末{market}普通A股中有效人民币年报{field}之和/有效样本数量；负值保留。'
    rank_formula = '近五年分位=100×(低于本年均值的年数+0.5×等于本年均值的年数)/有效年数，含本年；每年一条。'
    reading = '查看企业年度盈利与回报的整体变化。请同时核对有效数和尚缺数；样本不足时完整股票池均值留空。'
    schema = {'date': dict(label='年度报告期', unit='日期')}
    for key, (name, field_unit) in LABELS.items():
        schema[key] = dict(label=name, unit=field_unit or unit,
            **({'data_type': 'integer'} if field_unit in ('只', '年') else {}))
    if scope=='ashare':
        schema['market_count']['label']='当年末沪深北股票数'
        for key,name in [('shsz_market_count','沪深股票数'),('bse_market_count','北交所股票数')]:
            schema[key]=dict(label=name,unit='只',data_type='integer')
        schema['universe_confirmed_through']=dict(label='上市区间资料核验截止日',unit='日期')
    return dict(id=metric, board='earnings', label=label, definition_version=metric+'/1',
        frequency='年度年报', source='东方财富年报财务摘要；BaoStock历史上市证券表'+('；北交所名单、代码表及退出公告' if scope=='ashare' else ''),
        source_url='https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/Index?type=web&code=SH600000',
        unit=unit, parameters=False, primary_field='mean', field_schema=schema, default_preset='all',
        lines=[dict(key='mean', name='有效样本平均值', unit=unit, color='#267b86', panel='main', shown=True,
                    formula=formula, reading=reading),
               dict(key='historical_percentile', name='近五年历史分位', unit='%', color='#b87935', panel='context', shown=True,
                    formula=rank_formula, reading='分位越高，本年均值在此前五个年度中的相对位置越高；有效年数不足五年时按实际年数。')],
        formula=formula+' '+rank_formula, reading=reading, universe_id=scope+'-annual-ordinary-a-share',
        universe_table='source.financial_'+scope+'_universe', provider_field={**FIELDS,**ASHARE_METRICS}[metric],
        limitations=[('范围为当年末沪深北普通A股；北交所按已核当前名单、上市与退出区间重建，资料核验截止日逐行显示。' if scope=='ashare'
            else '范围为当年末沪深上市普通A股；北交所覆盖待补，当前结果只代表此范围。'),
            'EPS为人民币基本每股收益，ROE为公司加权平均净资产收益率；跨公司均采用等权算术平均。',
            '存托凭证每份与普通股每股基准不同，单列排除；缺值和币种未确认保持未知。',
            '同公司多个证券编号在报告字段完全一致时计一次，重复数量单列；财务事实冲突时保留上次结果。',
            '参考股票池仅扣除已确认的存托凭证及重复公司；缺报告证券的公司和类型待核，继续保守计入。',
            '每个报告期一条，历史采用本次截止日可得的修订年报及当年股票池；当时可得性尚未核实。',
            '公告和修订只核实到日；本次截止日之后的公告或修订不进入样本。'],
        how_to_read=dict(purpose=reading, signals=[], boundary='结合实际股票池、尚缺数和分位年数阅读；历史曲线含后续财报修订。'))


def prepare_definitions(definitions, datasets, sources):
    for source in sources:
        if source['kind'] != 'financial_annual':
            continue
        for metric in source['datasets']:
            if metric not in definitions:
                definitions[metric] = definition(metric)
                datasets[metric] = []


def refresh_ranks(datasets, *, check=lambda: None):
    """合并年报后统一重算，历史分母只含该报告期及此前四个年度。"""
    for metric in METRICS:
        rows = datasets.get(metric, [])
        if len(rows)>111 or any(not '1990-12-31'<=row['date']<='2100-12-31' or row['date'][4:]!='-12-31' for row in rows):
            raise SourceFailure('financial_history_periods')
        for row in rows:
            check()
            year = int(row['date'][:4])
            sample = [item for item in rows if year-4 <= int(item['date'][:4]) <= year and item['mean'] is not None]
            row['rank_periods'] = len(sample)
            row['rank_start'] = sample[0]['date'] if sample else None
            value = row['mean']
            row['historical_percentile'] = (100 * (sum(item['mean'] < value for item in sample)
                + .5 * sum(item['mean'] == value for item in sample)) / len(sample)) if value is not None and sample else None


def attach_boards(candidate, datasets):
    if not set(METRICS) & set(datasets):
        return
    if not any(board['id']=='earnings' for board in candidate['boards']):
        candidate['boards'].append(dict(id='earnings', label='盈利与回报'))
    candidate['preferences']['default_datasets'].setdefault('earnings', next(key for key in METRICS if key in datasets))
    if not candidate['preferences']['default_board']:
        candidate['preferences']['default_board'] = 'earnings'
