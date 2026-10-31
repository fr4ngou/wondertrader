"""Join independent observed calendars; never interpolate a monthly numerator."""


def attach_daily_context(tables, datasets, definitions, mapping):
    """Configuration selects the daily price source and its display role.

    Overlay rows use the union of actual dates. The primary field remains absent
    on price-only days; its schema is explicitly optional. This keeps sparse
    monthly observations drawable without inventing daily market-cap/GDP values.
    Price-above rows retain the interest-rate calendar and exact same-day OHLC.
    """
    for metric, spec in mapping.items():
        if metric not in datasets or metric not in definitions:
            continue
        prices = {r['date']: r for r in tables.get('market.' + spec['symbol'], [])}
        definition = definitions[metric]
        primary = definition['primary_field']
        original = datasets[metric]
        # Drop previously derived price-only rows and rebuild from current facts.
        rows = {r['date']: {k: v for k, v in r.items() if not k.startswith('sse_')}
                for r in original if spec['mode'] != 'overlay' or r.get(primary) is not None}
        if spec['mode'] == 'overlay':
            rows.update({day: rows.get(day, dict(date=day, available_at=None)) for day in prices
                         if not original or day >= original[0]['date']})
            definition['field_schema'][primary]['required'] = False
        for day, row in rows.items():
            if day in prices:
                row.update({'sse_' + field: prices[day].get(field)
                            for field in ('open', 'close', 'low', 'high')})
        observed = [r['date'] for r in rows.values() if r.get(primary) is not None]
        definition['primary_coverage'] = dict(start=min(observed, default=None),
            end=max(observed, default=None), observations=len(observed))
        price_days = [day for day in rows if day in prices]
        definition['context_coverage'] = dict(start=min(price_days,default=None),
            end=max(price_days,default=None),observations=len(price_days))
        definition['context_source'] = dict(symbol=spec['symbol'],label=spec['label'],table='market.'+spec['symbol'])
        schema = definition['field_schema']
        for field, name in (('open', '开盘'), ('close', '收盘'), ('low', '最低'), ('high', '最高')):
            schema['sse_' + field] = dict(label=spec['label'] + name, unit='指数点',
                nullable=True, required=False, missing='同日真实行情缺失时为空；不跨日补值')
        line = dict(key='sse_close', name=spec['label'] + ('日K' if spec['mode'] == 'price_above' else '每日收盘'),
            unit='指数点', color='#c65761', panel='context', shown=True, kind='source',
            formula='同一观察日的公开指数OHLC原值', reading='指数有独立日频，缺失保持空值。',
            value_kind='reported_source', value_kind_label='提供方值')
        if spec['mode'] == 'price_above':
            definition['price_above'] = True
            line.update(chart_type='candlestick', candle_fields=['sse_open','sse_close','sse_low','sse_high'])
            definition['how_to_read'] = dict(purpose='对照上证指数走势与银行短中期资金成本。',
                signals=['上图是上证真实日K，红涨绿跌，单位为指数点。','下图是隔夜、一周、三月Shibor年化利率，单位为%。','两图日期联动；指数缺失日保留空值。'],
                boundary='相关走势仅供观察；利率与股价受多种因素影响。')
        else:
            definition['frequency'] = '市值/GDP保留原统计频率；上证指数交易日日频'
            definition['reading'] = '蓝线为实际市值/GDP观察点，红线为上证每日收盘；两者保持各自原始频率。'
            definition['term_notes'] = [
                dict(term='GDP更新频率',note='官方GDP按季度、年度公布，年度值另有最终核实修订。本图分母为上年全年名义GDP；新季度累计值不直接替换全年分母。'),
                dict(term='市值/GDP',note='沪深源总市值除以上年全年名义GDP，两个金额使用相同单位；蓝线只连接实际观察点。'),
                dict(term='红曲线 / 红虚线',note=spec['label']+'每日收盘读左轴；1.00红虚线为市值/GDP倍数参考，读右轴。'),
                dict(term='双轴显示位置',note='指数点与倍数分别读轴，红蓝曲线的视觉交叉随刻度变化；比值水平应对照倍数参考线。')]
            definition['limitations'] = [
                '市值来源为沪深含B、不含北交所；月末与已核关键日保持各自观察身份，连续日频总市值仍缺。',
                'GDP为上年全年名义值；历史当时可得的GDP修订版本及公布时间尚未逐条认证。',
                '月末值包含月内后续涨跌，不能当作月中某日的估值。',
                f"{spec['label']}真实日线覆盖{min(price_days,default='暂无')}至{max(price_days,default='暂无')}；覆盖外保持空值。"]
            for existing in definition['lines']:
                if existing['key'] == primary:
                    existing['observed_dates_only'] = True
            definition['how_to_read'] = dict(purpose='用真实市值/GDP观察点与上证每日走势对照市场位置。',
                signals=['蓝线读右侧倍数轴，只连接实际月末或已核关键日。','红线读左侧指数点轴，使用上证实际交易日收盘。','主指标末期与指数末期分别列示；季度GDP公布不会直接替换上年全年分母。'],
                boundary='两个轴单位不同，红蓝线的视觉交叉受轴刻度影响；估值参考应读取蓝线与倍数水平线。')
        definition['lines'] = [l for l in definition['lines']
                               if l['key'] != 'sse_close' and not (spec['mode'] == 'overlay' and l['panel'] == 'context')] + [line]
        definition['definition_version'] = 'observed-frequency-daily-context/1'
        datasets[metric] = [rows[day] for day in sorted(rows)]
