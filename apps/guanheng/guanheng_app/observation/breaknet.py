"""破净观察的唯一口径；原始股票归档、日更和查询共用。"""
import math
import re

from .contracts import ObservationError

METRIC = 'valuation.breaknet'
BOARD = 'breaknet'
SEGMENTS = {'main': '沪深主板', 'chinext': '创业板', 'star': '科创板'}
COUNTS = {'universe': '有当日PB记录股票数', 'valid': '正PB有效样本数',
          'broken': '破净家数', 'missing': 'PB缺失家数', 'nonpositive': '非正PB剔除家数'}


def segment(code):
    """只接纳沪深普通A股；科创CDR及B股不进入股票分母。"""
    if re.fullmatch(r'(sh|sz)\.\d{6}', code) is None:
        raise ObservationError('breaknet_stock_identity', '破净统计股票身份无效', 503)
    if code.startswith(('sh.60', 'sz.00')):
        return 'main'
    if code.startswith('sz.30'):
        return 'chinext'
    if code.startswith('sh.688'):
        return 'star'
    return None


def empty_day(day):
    return dict(date=day, **{f'{s}_{key}': 0 for s in SEGMENTS for key in COUNTS})


def add_stock(result, code, pb):
    """PB保留提供方当日口径；包含ST及有当日PB的停牌股票，不沿用缺失值。"""
    s = segment(code)
    if s is None:
        return
    result[s+'_universe'] += 1
    if pb in (None, '', '--'):
        result[s+'_missing'] += 1
        return
    try:
        value = float(pb)
    except (ValueError, TypeError):
        raise ObservationError('breaknet_pb_invalid', '破净统计PB数值无效', 503) from None
    if not math.isfinite(value):
        raise ObservationError('breaknet_pb_invalid', '破净统计PB数值无效', 503)
    if value <= 0:
        result[s+'_nonpositive'] += 1
    else:
        result[s+'_valid'] += 1
        result[s+'_broken'] += int(value < 1)


def stock_day(fields, rows, day, *, eligible=None, check=lambda: None):
    """完整同日日线已经由原PB采集校验；此处核日期、重复和必要字段。"""
    if len(fields) != len(set(fields)) or not {'date', 'code', 'pbMRQ'} <= set(fields):
        raise ObservationError('breaknet_schema', '破净统计缺少日期、股票或PB字段', 503)
    result = empty_day(day)
    seen = set()
    for values in rows:
        check()
        row = dict(zip(fields, values))
        if len(values) != len(fields) or row['date'] != day or row['code'] in seen:
            raise ObservationError('breaknet_stock_day', '破净统计日期不符或股票重复', 503)
        seen.add(row['code'])
        if eligible is None or row['code'] in eligible:
            add_stock(result, row['code'], row['pbMRQ'])
    return result


def selected_segments(value):
    selected = value.split(',')
    if not selected or len(set(selected)) != len(selected) or set(selected)-SEGMENTS.keys():
        raise ValueError('板块需为main、chinext、star的非空不重复组合')
    return [key for key in SEGMENTS if key in selected]


def project(rows, selection, *, check=lambda: None):
    """多选合并家数及分母再算比例；全历史先预热，缺一个交易日即中断5日变化。"""
    selected = selected_segments(selection)
    result = []
    for original in rows:
        check()
        row = dict(original)
        totals = {key: sum(row.get(f'{s}_{key}') or 0 for s in selected) for key in COUNTS}
        known = all(row.get(f'{s}_{key}') is not None for s in selected for key in COUNTS)
        valid = totals['valid'] if known else None
        ratio = 100*totals['broken']/valid if valid else None
        row.update(broken_count=totals['broken'] if known else None,
                   sample_count=valid, universe_count=totals['universe'] if known else None,
                   missing_count=totals['missing'] if known else None,
                   excluded_count=totals['nonpositive'] if known else None,
                   ratio=ratio, change5=None)
        if len(result) >= 5 and ratio is not None and all(r['ratio'] is not None for r in result[-5:]):
            row['change5'] = ratio-result[-5]['ratio']
        result.append(row)
    return result


def calendar_rows(rows, calendar):
    """以官方开市日补出未知行，防止漏掉整日时把5条记录误当5个交易日。"""
    if not rows:
        return rows
    by_day = {row['date']: row for row in rows}
    first, last = min(by_day), max(by_day)
    return [by_day.get(session['date'], dict(date=session['date'], **{
        f'{s}_{key}': None for s in SEGMENTS for key in COUNTS}))
        for session in calendar if session['is_open'] and first <= session['date'] <= last]


def definition():
    formula = '破净率=100×(0<PB<1家数)/正PB有效样本数；5日变化=当日破净率−前第5个交易日破净率，单位为百分点。多选按家数与有效样本分别求和后计算。'
    schema = {'date': dict(label='交易日', unit='日期')}
    for s, label in SEGMENTS.items():
        for key, name in COUNTS.items():
            schema[f'{s}_{key}'] = dict(label=label+name, unit='只', nullable=True)
    for key, label, unit in [('ratio', '有效样本破净率', '%'), ('broken_count', '破净家数', '只'),
                             ('change5', '破净率5日变化', '百分点'), ('sample_count', '正PB有效样本数', '只'),
                             ('universe_count', '当日股票记录数', '只'), ('missing_count', 'PB缺失家数', '只'),
                             ('excluded_count', '非正PB剔除家数', '只')]:
        schema[key] = dict(label=label, unit=unit, nullable=True, required=False)
    return dict(id=METRIC, board=BOARD, label='破净率、家数与5日变化', definition_version=METRIC+'/1',
                frequency='交易日日频', unit='%', parameters=False, primary_field='ratio',
                frequency_audit=dict(kind='daily_calculation', daily_ready=True, fields=[
                    dict(key=key, computed_on_query=True) for key in
                    ('ratio','broken_count','change5','sample_count','universe_count','missing_count','excluded_count')]),
                source='BaoStock同日逐股PB及原始股票归档', source_url='http://baostock.com', formula=formula,
                reading='上图曲线看折价范围，柱状图看破净家数；下图大于零表示较5个交易日前破净范围扩大。',
                limitations=['分母为正PB有效样本；PB缺失和非正值家数单列，含ST及有当日PB的停牌股票。',
                             '仅沪深普通A股，不含北交所、B股及科创CDR；供应商历史修订与历史当时可得时间尚未核实。',
                             'PB缺失保持缺口，5日变化使用交易日序列，缺日及未知板块不会跨越计算。'],
                field_schema=schema, lines=[
                    dict(key='ratio', name='破净率', unit='%', color='#296fc2', panel='main', shown=True,
                         formula=formula, reading='正PB样本中破净股票占比。'),
                    dict(key='broken_count', name='破净家数', unit='只', color='#bd9b55', panel='main', axis='right',
                         chart_type='bar', shown=True, formula='所选板块0<PB<1的股票家数合计。', reading='右轴家数。'),
                    dict(key='change5', name='破净率5日变化', unit='百分点', color='#ad5869', panel='context', shown=True,
                         formula='当日破净率−前第5个交易日破净率。', reading='零线上方表示破净范围扩大。',
                         reference_levels=[dict(value=0, name='零线', color='#8a96a3')])])


def attach_board(manifest):
    if METRIC not in manifest['datasets']:
        return
    if not any(board['id'] == BOARD for board in manifest['boards']):
        manifest['boards'].append(dict(id=BOARD, label='破净观察'))
    manifest['preferences']['default_datasets'][BOARD] = METRIC


def update_history(definition, rows):
    """归档重算和每次日更均按最终行重建缺口说明，保留原归档身份。"""
    definition['history_audit'] = dict(missing_dates=[r['date'] for r in rows
        if any(r.get(f'{s}_valid') is None for s in SEGMENTS)])
