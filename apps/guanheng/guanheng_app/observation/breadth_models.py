"""股票日终派生指标的唯一登记和行投影；采集与发布沿原观察owner。"""

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
        formula='已确认占比=100×换手率严格大于5%的股票数/当日股票池数量。缺值时为下界；完整占比留空。样本占比以有效换手数为分母。',
        reading='大于5%计入，等于5%不计入。缺值时主图显示已确认下界，完整市场占比保持空值。'),
}

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
    item = METRICS[metric]
    schema = dict(date=dict(label='观察日', unit='日期'),
                  available_at=dict(label='来源公布时间', unit='时间，未知留空'))
    for key in item['keys']:
        label, unit = LABELS[key]
        schema[key] = dict(label=label, unit=unit, data_type='integer' if unit=='只' else 'number')
    primary = item['primary']
    line = dict(key=primary, name=LABELS[primary][0], unit=item['unit'], color='#267b86',
                panel='top', shown=True, formula=item['formula'], reading=item['reading'])
    return dict(id=metric, board=item['board'], label=item['label'], definition_version=metric+'/1',
                frequency='交易日日终', source='BaoStock已归档原始股票日线及证券表',
                source_url='https://www.baostock.com/mainContent?file=stockKData.md',
                unit=item['unit'], parameters=False, primary_field=primary,
                field_schema=schema, lines=[line], formula=item['formula'], reading=item['reading'],
                universe_id='shsz-listed-a-share', universe_table='source.shsz_universe',
                limitations=['范围为沪深A股，北交所覆盖另验。',
                    '涨跌使用同日来源参考前收盘；成交量为未复权原始股数，换手率为流通股百分数。',
                    '股票池按该日上市和退市日期过滤；来源历史修订及当时可得时间仍需分别核验。',
                    '停牌单列；缺行、缺价格、缺量、缺换手保持未知。'],
                how_to_read=dict(purpose=item['reading'], signals=[],
                    boundary='请连同有效数、缺失数和实际市场范围阅读。'))


def rows_for_metrics(result, selected):
    return {key: dict(date=result['date'], available_at=result['available_at'],
                      **{field: result[field] for field in METRICS[key]['keys']}) for key in selected}


def universe_row(day, codes, basic_sha256):
    """同一快照保留逐日股票池版本与证券表父对象；不把技术身份推入页面表格。"""
    return dict(date=day, universe_version=digest(encode(dict(date=day,codes=sorted(codes)))),
                market_count=len(codes), source_basic_sha256=basic_sha256)


def prepare_definitions(definitions, datasets, sources):
    requested={metric for source in sources if source['kind']=='baostock'
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
