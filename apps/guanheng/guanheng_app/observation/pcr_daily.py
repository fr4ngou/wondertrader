"""Public daily PCR projection; immutable retired archives remain audit-only."""
def definition_view(definition):
    if definition['board'] != 'pcr':
        return definition
    definition['definition_version'] = 'pcr-daily-ratio/1'
    definition['primary_field'] = 'pcr'
    definition['lines'] = [line for line in definition['lines']
        if line['key'] != 'pcr_reference' and not line['key'].startswith('reference_')]
    for line in definition['lines']:
        if line['key'] == 'pcr':
            line.update(chart_type='line', name='日终PCR',
                formula='所选口径的官方日终认沽数量 ÷ 认购数量',
                reading='每个交易日一个实际比值；持仓和成交口径分别读取，缺少原始数量时保持空值。')
            line.pop('candle_fields', None)
        elif line['key'] in ('upper', 'middle', 'lower'):
            line['name'] = {'upper':'上轨','middle':'中轨','lower':'下轨'}[line['key']]
    definition['field_schema'] = {key:value for key,value in definition['field_schema'].items()
        if not key.startswith(('pcr_', 'reference_', 'official_'))}
    definition['field_schema']['pcr'] = dict(label='日终PCR', unit='倍', nullable=True, required=False)
    definition['how_to_read'] = dict(purpose='上图看对应指数，中图看每日认沽/认购比值，下图看实际数量。',
        signals=['PCR＝认沽数量÷认购数量，每个交易日一个值；持仓和成交口径可以切换。',
            '通道使用完整已归档日终历史预热；改变日期窗口保持计算口径一致。',
            '对应指数保留真实价格日K；下图红柱为认购Call、绿柱为认沽Put。'],
        example='PCR高于1表示所选口径的认沽数量高于认购数量。',
        boundary='PCR用于观察情绪；结合指数与数量判断，单独触轨不能确认转折。')
    return definition
