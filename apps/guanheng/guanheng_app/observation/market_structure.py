"""以固定交易日历计算两张市场结构观察图。"""
from statistics import fmean, pstdev

from .market_structure_source import INDEX_TABLES, STOCK_TABLE

STAR = 'structure.star50'
SMALL = 'structure.csi2000'
LABELS = {
    STAR: '成交集中度、市场宽度与科创承接',
    SMALL: '小盘弹性独强，但成交未接力',
}
EVENTS = {
    STAR: [('成交集中与宽度同步', '#258566'), ('窄基拥挤', '#c27724'), ('承接不足', '#b85662')],
    SMALL: [('小盘弹性独强，但成交未接力', '#c27724')],
}
PERIOD = 252


def _window(values, end, count):
    start = end - count + 1
    if start < 0:
        return None
    result = values[start:end + 1]
    return None if None in result else result


def _zscore(values, end):
    window = _window(values, end, PERIOD)
    if window is None:
        return None
    deviation = pstdev(window)
    return (window[-1] - fmean(window)) / deviation if deviation else None


def _return(values, end, count):
    window = _window(values, end, count + 1)
    return 100 * (window[-1] / window[0] - 1) if window else None


def _active_amount(values, end):
    recent = _window(values, end, 5)
    prior = _window(values, end - 5, 20)
    if recent is None or prior is None:
        return None
    baseline = fmean(prior)
    return fmean(recent) / baseline if baseline > 0 else None


def _difference(left, right):
    return left - right if left is not None and right is not None else None


def calculate(metric, days, price, benchmark, *, amounts=None, stocks=None, check=lambda: None):
    """日历含缺行情日。先计算完整历史，查询窗口只切显示结果。"""
    result = []
    prior_state = None
    relative, activity, concentration, breadth = [], [], [], []
    small = metric == SMALL
    for i, day in enumerate(days):
        check()
        period = 5 if small else 20
        price_return = _return(price, i, period)
        benchmark_return = _return(benchmark, i, period)
        relative.append(_difference(price_return, benchmark_return))
        z_relative = _zscore(relative, i)
        state = None
        row = dict(date=day, close=price[i], benchmark_close=benchmark[i], available_at=None,
                   benchmark_return_pct=benchmark_return, index_return_pct=price_return,
                   relative_pp=relative[-1], relative_z=z_relative)
        if small:
            activity.append(_active_amount(amounts, i))
            z_activity = _zscore(activity, i)
            components = (z_relative, z_activity)
            if relative[-1] is not None and activity[-1] is not None:
                state = int(price_return > 0 and relative[-1] >= 2 and activity[-1] <= 1)
            row.update(amount_100m_cny=amounts[i], amount_ratio=activity[-1], amount_z=z_activity)
        else:
            stock = stocks.get(day, {})
            concentration.append(stock.get('top5_pct'))
            breadth.append(stock.get('median_return_pct'))
            provider = stock.get('provider') or 'Tushare'
            # WT 已统一股票池及聚合定义，供应方名称变化保留历史窗口。
            z_concentration = _zscore(concentration, i)
            z_breadth = _zscore(breadth, i)
            components = (z_concentration, z_breadth, z_relative)
            if None not in components:
                state = 0
                if z_concentration >= 1 and z_relative <= 0:
                    state = 3
                elif z_concentration >= 1 and z_breadth < 0 and z_relative > 0:
                    state = 2
                elif min(components) > 0:
                    state = 1
            row.update(top5_pct=concentration[-1], median_return_pct=breadth[-1],
                       sample_count=stock.get('sample_count'), concentration_z=z_concentration, breadth_z=z_breadth,
                       stock_provider=provider if stock.get('sample_count') is not None else None,
                       stock_source_sha256=stock.get('source_sha256'))
        row['score'] = fmean(components) if None not in components else None
        # 未知之后的首个状态不能确认是新触发，连续确认后才画事件。
        row['event_code'] = None if state is None else 0
        if state is not None and prior_state is not None and prior_state != state:
            row['event_code'] = state
        row['event_state'] = state
        prior_state = state
        result.append(row)
    return result


def definition(metric):
    small = metric == SMALL
    name = '中证2000' if small else '科创50'
    score_name = '小盘价格与成交合力' if small else '成交集中与科创宽度质量'
    horizon = 5 if small else 20
    relative = f'{name}减沪深300的{horizon}日收益百分点，右轴展示其252日Z分数。'
    formula = '等权平均相对弹性和成交接力倍数的252日Z分数。' if small else '等权平均成交集中度、涨跌幅中位数和相对承接的252日Z分数。'
    limits = ['观衡研究口径。标准化使用包含当日的252个连续交易日和总体标准差，零标准差与缺输入留空。',
              '历史首次可知时间未知，连续事件只标首日，未知状态后的第一个观测不推定新触发。']
    event_values = '; '.join(f'{i}={label}' for i, (label, _) in enumerate(EVENTS[metric], 1))
    fields = {
        'date': ('交易日', '日期'), 'available_at': ('历史首次可知时间', '时间'),
        'close': (name, '指数点'), 'benchmark_close': ('沪深300', '指数点'),
        'index_return_pct': (f'{name}{horizon}日涨幅', '%'), 'benchmark_return_pct': (f'沪深300{horizon}日涨幅', '%'),
        'relative_pp': (f'{horizon}日相对收益', '百分点'), 'relative_z': ('相对收益标准分', '无量纲'),
        'score': (score_name, '无量纲'), 'event_code': ('事件标记代码', '无量纲'),
        'event_state': ('当日事件状态代码', '无量纲'),
    }

    def line(key, label, unit, color, description, *, shown=True, price=False):
        return dict(key=key, name=label, unit=unit, color=color, panel='main' if price else 'context',
                    shown=shown, formula=description, reading=description)

    lines = [line('close', name, '指数点', '#238568', '中证指数官方日收盘点位。', price=True),
             line('benchmark_close', '沪深300', '指数点', '#6b7588', '用于计算相对收益的同日收盘点位。', shown=False, price=True),
             line('score', score_name, '无量纲', '#287d9c', formula),
             line('relative_z', '相对弹性标准分' if small else '科创相对承接标准分', '无量纲', '#835bb1', relative, shown=False)]
    if small:
        fields.update(amount_100m_cny=('中证2000成分股成交额', '亿元'), amount_ratio=('成交接力倍数', '倍'),
                      amount_z=('成交接力标准分', '无量纲'))
        lines.append(line('amount_z', '成交接力标准分', '无量纲', '#c17c23',
                          '中证2000近5日均成交额除以前20日均成交额，两个窗口不重叠，再计算252日Z分数。', shown=False))
        signals = ['橙色竖线：中证2000近5日上涨，领先沪深300至少2个百分点，且成交接力倍数不高于1。']
        boundary = '成交额表示交易活跃度，历史日线无法识别短线资金身份。'
    else:
        limits.append('成交集中度与市场宽度使用WT统一定义的合格历史，保留逐日供应方；真实缺值阻断252日窗口。')
        fields.update(top5_pct=('前5%个股成交额占比', '%'), median_return_pct=('个股日涨跌幅中位数', '%'),
                      sample_count=('当日有成交样本数', '只'), concentration_z=('成交集中度标准分', '无量纲'),
                      breadth_z=('市场宽度标准分', '无量纲'), stock_provider=('股票横截面供应方', '文本'),
                      stock_source_sha256=('WT股票横截面原件摘要', '文本'))
        lines.extend([line('concentration_z', '成交集中度标准分', '无量纲', '#c17c23',
                           '按成交额排序取前5%的普通A股，计算成交额占比和252日Z分数。', shown=False),
                      line('breadth_z', '市场宽度标准分', '无量纲', '#5b8da5',
                           '有成交普通A股的日涨跌幅中位数，再计算252日Z分数。', shown=False)])
        signals = ['绿线标记三项标准分均为正。橙线标记成交集中度至少1个标准差、市场宽度为负、相对承接为正。',
                   '红线标记成交集中度至少1个标准差、相对承接不高于零。']
        boundary = '成交集中度描述交易分布，结合涨跌幅中位数判断宽度。'
    schema = {key: dict(label=label, unit=unit) for key, (label, unit) in fields.items()}
    schema['event_code'].update(description='0=无新事件。' + event_values)
    schema['event_state'].update(description='0=未满足。' + event_values)
    return dict(id=metric, board=metric, label=LABELS[metric], definition_version=metric + ('/2' if metric == STAR else '/1'),
                frequency='交易日日终', unit='无量纲', parameters=False, primary_field='score', overlay=True,
                default_preset='all', source='中证指数官方日线' if small else '中证指数官方日线与股票横截面',
                source_url='https://www.csindex.com.cn/', formula=formula, reading=boundary, limitations=limits,
                field_schema=schema,
                lines=lines, how_to_read=dict(purpose=LABELS[metric] + ' · 观衡研究口径', signals=signals, boundary=boundary),
                event_markers=dict(field='event_code', anchor='close', values=[
                    dict(code=i, label=label, color=color) for i, (label, color) in enumerate(EVENTS[metric], 1)]))


def derive(tables, datasets, definitions, *, check=lambda: None):
    """生成指标与直接来源表清单，供原发布owner登记输入谱系。"""
    calendar = tables.get('source.cn_official_calendar', [])
    benchmark = {r['date']: r['close'] for r in tables.get(INDEX_TABLES['000300'], [])}
    if not calendar or not benchmark:
        return {}
    stocks = {r['date']: r for r in tables.get(STOCK_TABLE, [])}
    used = {}
    for metric, code in ((STAR, '000688'), (SMALL, '932000')):
        index_table = INDEX_TABLES[code]
        index = {r['date']: r for r in tables.get(index_table, [])}
        if not index or (metric == STAR and not stocks):
            continue
        first = min(index)
        last = max(index)
        days = [r['date'] for r in calendar if r['is_open'] == 1 and first <= r['date'] <= last]
        if not days:
            continue
        rows = calculate(metric, days, [index.get(day, {}).get('close') for day in days],
            [benchmark.get(day) for day in days], amounts=[index.get(day, {}).get('amount_billion') for day in days],
            stocks=stocks, check=check)
        if metric == STAR:
            # 先用完整价格历史预热20日相对收益，再从首个横截面开始展示。
            first_stock_day = min(stocks)
            rows = [row for row in rows if row['date'] >= first_stock_day]
            if not rows:
                continue
        datasets[metric] = rows
        definitions[metric] = definition(metric)
        available=[row['date']for row in rows if row['score'] is not None]
        definitions[metric]['primary_coverage']=dict(start=min(available,default=None),end=max(available,default=None),observations=len(available))
        if available:
            definitions[metric]['how_to_read']['boundary']+=f' 合成线预热后的首个有效日为{available[0]}，指数点位保留完整历史。'
        used[metric] = ['source.cn_official_calendar', INDEX_TABLES['000300'], index_table]
        if metric == STAR:
            used[metric].append(STOCK_TABLE)
    return used


def attach_boards(candidate):
    for metric, label in LABELS.items():
        if metric not in candidate['datasets']:
            continue
        if not any(board['id'] == metric for board in candidate['boards']):
            candidate['boards'].append(dict(id=metric, label=label))
        candidate['preferences']['default_datasets'][metric] = metric
