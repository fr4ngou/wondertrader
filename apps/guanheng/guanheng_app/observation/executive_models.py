"""高管披露聚合的中文图表与字段投影；事件技术身份留在原始来源中。"""

QUALITY = ('reported_event_count', 'eligible_event_count', 'unknown_relation_count', 'unknown_role_count',
           'unknown_reason_count', 'missing_amount_count', 'outside_pool_count')
METRICS = {
    'executive.net.shsz': dict(label='高管净增持额 · 沪深已披露', primary='net_amount_cny', unit='元',
        keys=('buy_amount_cny', 'sell_amount_cny', 'net_amount_cny', 'complete_net_amount_cny', *QUALITY),
        formula='已确认净额=合格增持金额−合格减持金额。缺金额单列；有未确认记录时完整净额留空。',
        reading='正值表示该日已披露、已确认的高管本人买入较多，负值表示卖出较多。'),
    'executive.ratio.shsz': dict(label='高管增减持净占比 · 沪深已披露', primary='net_amount_pct', unit='%',
        keys=('net_amount_pct', 'buy_amount_cny', 'sell_amount_cny', *QUALITY),
        formula='净占比=100×(增持金额−减持金额)/(增持金额+减持金额)。分母为零或合格事件缺金额时留空。',
        reading='比较已确认增减持金额的方向，范围为−100%至100%；未知关系、职务和交易原因的记录单列。'),
    'executive.companies.shsz': dict(label='高管增减持公司占比 · 沪深已披露', primary='changed_company_pct', unit='%',
        keys=('changed_company_pct', 'buy_company_pct', 'sell_company_pct', 'changed_company_count',
            'buy_company_count', 'sell_company_count', 'market_company_count', 'known_market_company_count',
            'unresolved_market_identity_count', 'market_stock_count', 'cdr_excluded_count', *QUALITY),
        formula='公司占比=100×有合格增持/减持/任一变动的去重公司数/同日股票池去重公司总数。公司身份未齐时占比留空。',
        reading='同一公司可同时出现在增持和减持分项，任一变动公司数只计一次。'),
}
ASHARE_METRICS = {key.replace('.shsz', '.ashare'):
    {**item, 'label':item['label'].replace('沪深', '沪深北'),
     'keys':(*item['keys'], 'bse_market_count', 'shsz_market_count', 'universe_confirmed_through')}
    for key, item in METRICS.items()}
SCOPES = {'shsz':METRICS, 'ashare':ASHARE_METRICS}
ALL_METRICS = {**METRICS, **ASHARE_METRICS}
LABELS = {
    'buy_amount_cny': ('已确认增持金额', '元'), 'sell_amount_cny': ('已确认减持金额', '元'),
    'net_amount_cny': ('已确认净增持金额', '元'), 'complete_net_amount_cny': ('无未确认记录的净额', '元'),
    'net_amount_pct': ('已确认增减持净占比', '%'),
    'changed_company_pct': ('任一增减持公司占比', '%'), 'buy_company_pct': ('增持公司占比', '%'),
    'sell_company_pct': ('减持公司占比', '%'), 'changed_company_count': ('任一增减持公司数', '只'),
    'buy_company_count': ('增持公司数', '只'), 'sell_company_count': ('减持公司数', '只'),
    'market_company_count': ('同日股票池公司总数', '只'), 'known_market_company_count': ('已确认公司身份数', '只'),
    'unresolved_market_identity_count': ('公司身份尚缺证券数', '只'), 'market_stock_count': ('同日沪深股票数', '只'),
    'cdr_excluded_count': ('已排除存托凭证数', '只'),
    'reported_event_count': ('来源披露记录数', '笔'), 'eligible_event_count': ('已确认高管本人买卖笔数', '笔'),
    'unknown_relation_count': ('本人关系尚待确认笔数', '笔'),
    'unknown_role_count': ('职务尚待确认笔数', '笔'), 'unknown_reason_count': ('交易性质尚待确认笔数', '笔'),
    'missing_amount_count': ('合格买卖缺金额笔数', '笔'),
    'outside_pool_count': ('范围外披露记录数', '笔'),
    'bse_market_count': ('北交所股票数', '只'), 'shsz_market_count': ('沪深股票数', '只'),
    'universe_confirmed_through': ('上市区间资料核验截止日', '日期'),
}


def definition(metric):
    item = ALL_METRICS[metric]
    scope = metric.rsplit('.', 1)[-1]
    schema = {'date': dict(label='股份变动日', unit='日期')}
    for key in item['keys']:
        label, unit = LABELS[key]
        if key == 'market_stock_count' and scope == 'ashare':label = '同日沪深北股票数'
        schema[key] = dict(label=label, unit=unit,
            data_type='date' if unit == '日期' else 'integer' if unit in ('只', '笔') else 'number')
    line_keys = ('changed_company_pct', 'buy_company_pct', 'sell_company_pct') if metric.startswith('executive.companies.') else (item['primary'],)
    return dict(id=metric, board='executive', label=item['label'], definition_version=metric+'/1',
        frequency='按变动日回溯的已披露记录', source='东方财富高管持股明细；BaoStock上市证券表；年报公司身份'
            + ('；北交所上市区间与换码资料' if scope == 'ashare' else ''),
        source_url='https://data.eastmoney.com/executive/list.html', unit=item['unit'], parameters=False,
        primary_field=item['primary'], field_schema=schema,
        lines=[dict(key=key, name=LABELS[key][0], unit=item['unit'], color=color, panel='main', shown=True,
            formula=item['formula'], reading=item['reading']) for key, color in zip(line_keys, ('#267b86', '#b87935', '#87618d'))],
        formula=item['formula'], reading=item['reading'], universe_id=scope+'-listed-ordinary-a-company',
        universe_table='source.executive_'+scope+'_universe',
        limitations=[('范围为沪深北A股已披露记录；历史上市/退出资料及未披露事件覆盖沿来源说明核对。'
            if scope == 'ashare' else '范围为沪深A股已披露记录；北交所及全市场覆盖继续待核。'),
            '仅计本人、已确认高级管理职务及有偿买卖；纯董事、监事、核心技术人员及关联人不计入。',
            '金额采用来源披露值，单位为人民币元；供应商可能按披露均价折算，实际资金流水需以券商记录核对。',
            '缺金额不按零，不以当前股价估算；未知本人关系、未知职务、未知交易性质分别计数。',
            '按股份变动日回溯，实际披露存在滞后，后续抓取可修订历史值；公告日及历史当时可得时间未知。',
            '同日上市池按上市/退市日期过滤，公司身份取已配置年度报表和原事件；身份未齐时公司占比留空。'],
        how_to_read=dict(purpose=item['reading'], signals=[], boundary='结合披露滞后、待确认笔数与公司身份覆盖阅读。'))


def rows_for_metrics(rows, *, scope='shsz'):
    return {metric: [dict(date=row['date'], **{key: row[key] for key in item['keys']}) for row in rows]
            for metric, item in SCOPES[scope].items()}


def prepare_definitions(definitions, datasets, sources):
    metrics = {metric for source in sources if source['kind'] == 'executive_changes'
               for metric in SCOPES[source.get('scope', 'shsz')]}
    for metric in sorted(metrics):
        if metric not in definitions:
            definitions[metric], datasets[metric] = definition(metric), []


def attach_boards(candidate, datasets):
    if not set(ALL_METRICS) & set(datasets):
        return
    if not any(board['id'] == 'executive' for board in candidate['boards']):
        candidate['boards'].append(dict(id='executive', label='高管增减持'))
    candidate['preferences']['default_datasets'].setdefault('executive', next(key for key in ALL_METRICS if key in datasets))
    if not candidate['preferences']['default_board']:
        candidate['preferences']['default_board'] = 'executive'
