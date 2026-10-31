"""Attach explicitly mapped index OHLC to option statistics in one snapshot."""
FIELDS = {'open':'开盘','close':'收盘','high':'最高','low':'最低'}


def archive_fields(definition):
    schema = definition['field_schema']
    for kind in ('oi', 'volume'):
        for field, label in FIELDS.items():
            schema['pcr_'+kind+'_'+field] = dict(label=('持仓' if kind=='oi' else '累计成交')+'PCR采样'+label,
                unit='倍', data_type='number', nullable=True, required=False)
    fields = [('pcr_sample_count','有效分钟采样数','条'),
        ('pcr_quality','PCR采样质量','文本'), ('pcr_archive_sha','PCR归档身份','文本'),
        ('pcr_oi_quality','持仓PCR质量','文本'),('pcr_volume_quality','累计成交PCR质量','文本'),
        ('official_oi_quality','官方持仓统计质量','文本'),('official_volume_quality','官方成交统计质量','文本'),
        ('pcr_oi_phase','盘中持仓处理阶段','文本'),('pcr_archive_version','PCR归档格式','文本'),
        ('pcr_first_sample','首个采样时点','时间'),('pcr_last_sample','最后采样时点','时间'),
        ('pcr_source_phase_basis','历史来源阶段依据','文本'),('pcr_history_source','历史分钟来源','文本'),
        ('pcr_historical_postclose_source_span_seconds','历史盘后原件来源跨度（秒）',None)]
    for key, label, unit in fields:
        schema[key] = dict(label=label, unit=unit, nullable=True, required=False)


def attach_pcr_context(tables, datasets, definitions, mapping):
    for metric, underlying in mapping.items():
        if metric not in datasets or metric not in definitions:
            continue
        table = {row['date']: row for row in tables.get('market.'+underlying['symbol'], [])}
        for row in datasets[metric]:
            observed = table.get(row['date'], {})
            # Keep a source gap explicit, including when a revision removes OHLC.
            row.update({key: observed.get(key) for key in FIELDS})
        definition = definitions[metric]
        definition['underlying'] = dict(underlying, source_id='tencent.indices',
            source_url='https://web.ifzq.gtimg.cn/', role='对应标的指数参照；ETF价格与指数点位分别读取')
        definition['definition_version'] = 'pcr-with-mapped-index-ohlc/2'
        schema = definition['field_schema']
        archive_fields(definition)
        for key, label in FIELDS.items():
            schema[key] = dict(label=underlying['label']+label, unit='指数点',
                data_type='number', nullable=True, required=False,
                source='腾讯指数日线 · '+underlying['symbol'],
                formula='同日原始指数OHLC；缺源保持null', value_kind='reported_source')
        lines = [line for line in definition['lines'] if line.get('panel') != 'price']
        for line in lines:
            if line['key'] in ('call_count','put_count'):
                line.update(chart_type='bar', color='#c65761' if line['key']=='call_count' else '#24996f')
        definition['lines'] = [dict(key='close',name=underlying['label']+'日K',unit='指数点',
            color='#c65761',panel='price',shown=True,chart_type='candlestick',
            formula='同日指数原始开高低收',reading='红色收盘高于开盘，绿色收盘低于开盘；与下方PCR和数量按日期对照。'),*lines]
        reading = definition.setdefault('how_to_read', {})
        reading['purpose'] = '上图看对应指数涨跌，中图看认沽/认购比值，下图看两边实际数量。'
        reading['signals'] = [
            '上图为对应指数日K：红涨绿跌，竖线表示当日最高和最低。基金期权使用其跟踪指数参照。',
            '中图PCR＝认沽数量÷认购数量。所选持仓或累计成交口径分别核验，通过后显示分钟采样日K；盘后日终参考独立显示。盘中持仓经过收盘后的对冲处理，两个阶段的比值可以不同。',
            '盘中收盘通道只用同阶段合格K线收盘预热；盘后参考通道只用官方日终比值预热。来源阶段未知、缺凭证或数量不符时保留待核原因。',
            '下图红柱为认购Call，绿柱为认沽Put。切换持仓/成交时，PCR和两组柱一起变化。',
            'PCR跳升时结合指数和数量看：分子增加、分母减少都能推高比值。数量包含买卖双方，无法据此判断净买入方向。',
        ]
        reading['boundary'] = 'PCR和通道用于观察情绪，单独触轨或越过1无法确认行情转折。'
