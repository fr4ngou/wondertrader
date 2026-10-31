"""股票日终派生指标的唯一登记和行投影；采集与发布沿原观察owner。"""

import copy

from .contracts import ObservationError
from .storage import digest, encode


METRICS = {
    'breadth.shsz': dict(board='breadth', label='市场广度 · 沪深A股', primary='advancing_pct', unit='%',
        keys=('advancing_pct','advancing_count','declining_count','flat_count','net_advances','suspended_count',
              'market_count','classified_count','unclassified_count'),
        formula='上涨占比=100×上涨家数/(上涨+下跌+平盘家数)；净上涨=上涨家数−下跌家数。',
        reading='查看上涨范围和净上涨家数；停牌与缺失股票分别列出。'),
    'trin.shsz': dict(board='breadth', label='阿姆氏 TRIN · 沪深A股', primary='trin', unit='无量纲',
        keys=('trin','advancing_count','declining_count','advancing_volume','declining_volume',
              'market_count','unclassified_count','missing_volume_count'),
        formula='TRIN=(上涨家数/下跌家数)/(上涨股票成交股数/下跌股票成交股数)。',
        reading='将上涨和下跌的股票数量比，与各自成交股数之比一起比较。缺组、缺量或零分母保持空值。'),
    'rana.shsz': dict(board='breadth', label='RANA · 沪深A股', primary='rana', unit='无量纲',
        keys=('rana','advancing_count','declining_count','flat_count','market_count','unclassified_count'),
        formula='RANA=1000×(上涨家数−下跌家数)/(上涨家数+下跌家数)；平盘另列。',
        reading='正值表示上涨家数较多，负值表示下跌家数较多；这是净上涨比例，未计算震荡器。'),
    'turnover.gt5.shsz': dict(board='turnover', label='换手率大于5% · 已确认市场占比',
        primary='turnover_confirmed_lower_bound_pct', unit='%',
        keys=('turnover_confirmed_lower_bound_pct','turnover_gt5_pct','turnover_sample_pct',
              'turnover_gt5_count','market_count','turnover_known_count','turnover_missing_count','suspended_count'),
        formula='已确认占比=100×换手率严格大于5%的股票数/当日股票池数量。分类尚缺时为下界，完整占比留空；样本占比以已确认阈值分类数为分母。',
        reading='大于5%计入，等于5%不计入。明确停牌且量和换手为空或零时确认未超5%，原数值空值保留；分类尚缺时主图显示下界，完整市场占比留空。'),
}

SHSZ_METRICS = dict(METRICS)
ASHARE_METRICS = {key.replace('.shsz', '.ashare'): {**value,
    'label': value['label'].replace('沪深A股', '沪深北普通A股') +
        (' · 沪深北普通A股' if key == 'turnover.gt5.shsz' else '')}
    for key, value in SHSZ_METRICS.items()}
COVERAGE_FIELDS = {
    'known_market_count':'已核普通A股数量', 'reported_count':'已取得行情数量',
    'missing_quote_count':'行情尚缺数量', 'identity_unverified_count':'股票池资格待核数量',
    'state_unverified_count':'交易状态待核数量', 'missing_float_count':'可用非限售股本尚缺数量',
    'special_reference_count':'首日或新增交易参考价数量',
    'halted_with_trades_count':'停牌标志且当日有成交数量', 'missing_price_count':'涨跌比较价尚缺数量',
}
for item in ASHARE_METRICS.values():
    item['keys']=tuple(dict.fromkeys((*item['keys'],*COVERAGE_FIELDS)))
ASHARE_METRICS['turnover.gt5.ashare'].update(label='换手率超过5% · 沪深北A股',primary='turnover_gt5_pct',
    formula='完整占比=100×换手率严格大于5%的股票数/当日股票池数量；全部股票阈值资格已确认时提供。',
    reading='大于5%计入，等于5%不计入。主图显示完整市场占比；分类尚缺时主值留空，缺口说明单列已确认下界。')
METRICS.update(ASHARE_METRICS)

LABELS = {
    'advancing_pct': ('上涨股票占比','%'), 'advancing_count': ('上涨家数','只'),
    'declining_count': ('下跌家数','只'), 'flat_count': ('平盘家数','只'), 'net_advances': ('净上涨家数','只'),
    'suspended_count': ('停牌家数','只'), 'market_count': ('沪深股票池数量','只'),
    'classified_count': ('有效涨跌分类数','只'), 'unclassified_count': ('涨跌尚缺数','只'),
    'advancing_volume': ('上涨股票成交股数','股'), 'declining_volume': ('下跌股票成交股数','股'),
    'missing_volume_count': ('涨跌组缺量数','只'), 'trin': ('阿姆氏TRIN','无量纲'), 'rana': ('RANA','无量纲'),
    'turnover_confirmed_lower_bound_pct': ('已确认市场占比下界','%'),
    'turnover_gt5_pct': ('完整市场占比','%'), 'turnover_sample_pct': ('有效样本占比','%'),
    'turnover_gt5_count': ('换手率大于5%的数量','只'),
    'turnover_known_count': ('换手有效数','只'), 'turnover_missing_count': ('换手尚缺数','只'),
}


def definition(metric):
    """明确沪深范围、原股数量及部分覆盖，页面仅展示中文业务字段。"""
    if metric in ASHARE_METRICS:
        result = definition(metric.replace('.ashare', '.shsz'))
        result.update(id=metric, label=ASHARE_METRICS[metric]['label'], definition_version=metric+'/2',
            source='BaoStock沪深日线与北交所公开行情、证券表同日原件',
            source_url='https://www.bse.cn/nq/quotation.html',
            universe_id='ashare-ordinary-listed-day', universe_table='source.ashare_day_universe')
        result['field_schema']['market_count']['label']='股票池数量（含待核候选）'
        for key,label in COVERAGE_FIELDS.items():
            result['field_schema'][key]=dict(label=label,unit='只',data_type='integer')
        if metric=='turnover.gt5.ashare':
            result['primary_field']='turnover_gt5_pct'
            item=ASHARE_METRICS[metric]
            result.update(formula=item['formula'],reading=item['reading'])
            result['how_to_read']['purpose']=item['reading']
            result['lines'][0].update(key='turnover_gt5_pct',name='完整市场占比',formula=item['formula'],reading=item['reading'])
        result['limitations'] = ['范围为定日普通A股股票池，覆盖沪、深、北三所；沪深历史单独保留。',
            '沪深使用同日来源参考价与原始股数；北交所换手=成交股数×100/非限售股本。',
            '当前数据为同日收盘统计；来源读取时间与首次公布时间分别记录，历史首次公布时间仍待核。',
            '首日或新增交易沿来源参考价；有成交的停牌标志证券仍计入当日统计。未知状态及资格单列，完整市场比例保持未知。',
            '沪深沿来源交易状态及流通股换手字段；北交所已核状态且明确停牌、当日无成交时单列停牌。',
            '缺失数值保持空值。换手阈值分类尚缺时完整市场占比留空，已确认下界在缺口说明中单列。']
        return result
    item = METRICS[metric]
    schema = dict(date=dict(label='观察日', unit='日期'),
                  available_at=dict(label='来源公布时间', unit='时间，未知留空'))
    for key in item['keys']:
        label, unit = LABELS[key]
        schema[key] = dict(label=label, unit=unit, data_type='integer' if unit=='只' else 'number')
    if metric=='turnover.gt5.shsz':
        schema['turnover_known_count']['label']='换手分类已确认数'
        schema['turnover_missing_count']['label']='换手分类尚缺数'
    primary = item['primary']
    line = dict(key=primary, name=LABELS[primary][0], unit=item['unit'], color='#267b86',
                panel='top', shown=True, formula=item['formula'], reading=item['reading'])
    return dict(id=metric, board=item['board'], label=item['label'], definition_version=metric+('/2' if metric=='turnover.gt5.shsz' else '/1'),
                frequency='交易日日终', source='BaoStock已归档原始股票日线及证券表',
                source_url='https://www.baostock.com/mainContent?file=stockKData.md',
                unit=item['unit'], parameters=False, primary_field=primary,
                field_schema=schema, lines=[line], formula=item['formula'], reading=item['reading'],
                universe_id='shsz-listed-a-share', universe_table='source.shsz_universe',
                limitations=['范围为沪深A股，北交所覆盖另验。',
                    '涨跌使用同日来源参考前收盘；成交量为未复权原始股数，换手率为流通股百分数。',
                    '股票池按该日上市和退市日期过滤；来源历史修订及当时可得时间仍需分别核验。',
                    ('停牌单列；缺失的数值保持空值，阈值分类资格按下一条说明。' if metric=='turnover.gt5.shsz'
                     else '停牌单列；缺行、缺价格、缺量、缺换手保持未知。'),
                    *(['明确停牌且量与换手字段为空或零时，确认未超过5%；原数值空值保留。矛盾的正值与正常交易缺换手继续未知。']
                      if metric=='turnover.gt5.shsz' else [])],
                how_to_read=dict(purpose=item['reading'], signals=[],
                    boundary='请连同有效数、缺失数和实际市场范围阅读。'))



def admit_definition(metric, previous, prior, incoming):
    """方法升级只接纳完整历史重算；增量缺口保留原定义与原分区。"""
    current = definition(metric)
    if previous is None:
        return current
    old_version = previous.get('definition_version')
    if old_version == current['definition_version']:
        admitted=copy.deepcopy(previous)
        if metric in ASHARE_METRICS:
            # 同方法的展示勘误沿定义owner更新；业务字段、历史和计算版本保持。
            for field in ('formula','reading','limitations','how_to_read'):
                admitted[field]=copy.deepcopy(current[field])
            descriptions={line['key']:line for line in current['lines']}
            for line in admitted['lines']:
                if line['key'] in descriptions:
                    for field in ('formula','reading'):
                        line[field]=descriptions[line['key']][field]
        return admitted
    if (metric in ASHARE_METRICS and old_version==metric+'/1' and current['definition_version']==metric+'/2'
            and {row['date'] for row in prior}<={row['date'] for row in incoming}):
        return {**copy.deepcopy(previous), **current}
    if (metric == 'turnover.gt5.shsz' and old_version == metric+'/1'
            and current['definition_version'] == metric+'/2'
            and {row['date'] for row in prior} <= {row['date'] for row in incoming}):
        return {**copy.deepcopy(previous), **current}
    raise ObservationError('stock_method_mismatch', '统计口径变更须使用完整历史原件重新计算', 409)


def rows_for_metrics(result, selected):
    return {key: dict(date=result['date'], available_at=result['available_at'],
                      **{field: result[field] for field in METRICS[key]['keys']}) for key in selected}


def universe_row(day, codes, basic_sha256):
    """同一快照保留逐日股票池版本与证券表父对象；不把技术身份推入页面表格。"""
    return dict(date=day, universe_version=digest(encode(dict(date=day,codes=sorted(codes)))),
                market_count=len(codes), source_basic_sha256=basic_sha256)


def prepare_definitions(definitions, datasets, sources):
    requested={metric for source in sources if source['kind'] in ('baostock','ashare_snapshot','ashare_public')
               for metric in source.get('datasets',[]) if metric in METRICS}
    for metric in sorted(requested):
        if metric not in definitions:
            definitions[metric]=definition(metric)
            datasets[metric]=[]


def attach_boards(candidate, datasets):
    """仅在首批实际数据已入目录后登记入口；原观察偏好继续沿用。"""
    labels={'breadth':'市场广度','turnover':'换手活跃度'}
    for metric in METRICS:
        if metric not in datasets:
            continue
        board=METRICS[metric]['board']
        if not any(item['id']==board for item in candidate['boards']):
            candidate['boards'].append(dict(id=board,label=labels[board]))
        candidate['preferences']['default_datasets'].setdefault(board,metric)
    if not candidate['preferences']['default_board'] and datasets:
        candidate['preferences']['default_board']=next(iter(datasets.values()))['definition']['board']
