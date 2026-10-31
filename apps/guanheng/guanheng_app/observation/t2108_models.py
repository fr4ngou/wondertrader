"""A股T2108方法的唯一登记；全市场、合格样本与缺项分列。"""

METRIC = 't2108.ashare'
UNIVERSE = 'source.t2108_ashare_universe'
FIELDS = {
    'above_sma40_pct': ('40期均线上方占合格样本', '%'),
    'market_above_sma40_pct': ('完整市场占比', '%'),
    'confirmed_market_lower_bound_pct': ('已确认市场占比下界', '%'),
    'coverage_pct': ('合格样本覆盖率', '%'),
    'above_count': ('40期均线上方数量', '只'),
    'equal_count': ('等于40期均线数量', '只'),
    'below_count': ('40期均线下方数量', '只'),
    'market_count': ('沪深北股票池数量', '只'),
    'eligible_count': ('合格样本数量', '只'),
    'missing_count': ('日线缺失数量', '只'),
    'stale_count': ('日线过期数量', '只'),
    'insufficient_count': ('不足40期数量', '只'),
    'adjustment_unverified_count': ('前复权待核或不可用数量', '只'),
    'empty_count': ('缺失中原始日线空结果', '只'),
    'invalid_count': ('缺失中原始日线无效帧', '只'),
    'partition_count': ('缺失中原始日线需分段', '只'),
}


def definition():
    """公式包含当期；缺项使完整市场占比留空，样本占比单独命名。"""
    formula = ('SMA40=含当期在内的最近40个有效同基准收盘价之和/40；'
        '合格样本占比=100×收盘价严格大于SMA40的数量/合格样本数量。'
        '等于均线不计入；完整市场占比仅在所有股票合格时提供。')
    reading = '衡量股价处于40期均线上方的范围；请同时查看合格样本覆盖率和四类缺项。'
    schema = dict(date=dict(label='观察日', unit='日期'),
        available_at=dict(label='历史首次可知时间', unit='时间，未知留空'),
        source_received_at=dict(label='本批来源最晚接收时间', unit='时间，未知留空'),
        source_kind=dict(label='来源类型',data_type='string',unit='文本'),
        method_version=dict(label='计算口径',data_type='string',unit='文本'))
    schema.update({key: dict(label=label, unit=unit, data_type='integer' if unit=='只' else 'number')
        for key,(label,unit) in FIELDS.items()})
    return dict(id=METRIC, board='breadth', label='40期均线上方比例 · A股T2108方法',
        definition_version='t2108.ashare/2', frequency='交易日日终',
        source='QMT同批等比前复权日线收盘', source_url='https://dict.thinktrader.net/innerApi/data_function.html', unit='%',
        parameters=False, primary_field='above_sma40_pct', field_schema=schema,
        lines=[dict(key='above_sma40_pct',name=FIELDS['above_sma40_pct'][0],unit='%',
            color='#267b86',panel='top',shown=True,formula=formula,reading=reading)],
        formula=formula, reading=reading, universe_id='dated-ashare-source-universe', universe_table=UNIVERSE,
        limitations=['这是A股适配计算，原T2108的美国股票池与本指标分别定义。',
            '股票池覆盖沪深北；合格样本包含同日收盘及至少40期正值的QMT等比前复权序列。',
            '均线按实际日线观察计算；缺行与停牌不填价、不延用旧价，历史首次可知时间保持未知。',
            '当期收盘与均线取同一QMT前复权序列，直接使用供应商值；逐股除权因子核算不参与本指标准入。',
            '这是当前可见数据的观察统计；历史当时可得、原生分析及交易资格沿各自来源，SDK演示数据单独标明。',
            '历史点保留各自计算口径：原核验口径的待核数和供应商序列口径的不可用数分别解释，历史点未按新口径重算。'],
        how_to_read=dict(purpose=reading,signals=[],boundary='合格表示同一当前前复权序列满足40期计算条件；历史当时可得时间保持未知。部分覆盖时完整市场占比留空。'))


def prepare_definitions(definitions, datasets, sources):
    if any(source['kind']=='qmt_t2108' for source in sources) and METRIC not in definitions:
        definitions[METRIC]=definition();datasets[METRIC]=[]


def versioned_history(rows, version):
    """历史值保持，仅补原定义版本；新定义随本次来源数据一并成功准入。"""
    return [dict(row,method_version=row.get('method_version') or version) for row in rows]


def attach_board(candidate):
    if METRIC not in candidate['datasets']:
        return
    if not any(board['id']=='breadth' for board in candidate['boards']):
        candidate['boards'].append(dict(id='breadth',label='市场广度'))
    candidate['preferences']['default_datasets'].setdefault('breadth',METRIC)
    if not candidate['preferences']['default_board']:
        candidate['preferences']['default_board']='breadth'
