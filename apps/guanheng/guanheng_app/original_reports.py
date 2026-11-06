"""ORR原件准入和只读投影；归一化原模型独立于WT人民币/撮合报告族。"""
from __future__ import annotations

from datetime import date
from hashlib import sha256
import json
import math
import re

ALGORITHM = 'resonance-original-351f9d5-stable'
VERSION = '0.1.0a1'
COMMIT = '351f9d58152e10efd2447c997b8ee4db66b5ac6a'
SOURCE_MANIFEST_SHA = '5c85a8ee3838d3cbcc83158986b223ed3943640cb0b62cb250faded78ca8ad11'
REPORT_SCHEMA = 'guanheng.resonance-original-report.v1'
RECEIPT_SCHEMA = 'orr-completed-archive-v1'
FAMILY = 'resonance-original'
SCOPE = 'original-stable-research; normalized-equity; execution/PIT-unqualified'
MAX_BYTES = 32 * 1024 * 1024
MAX_DAYS = 4096
MAX_TRADES = 65536
_SHA = re.compile(r'[a-f0-9]{64}')
_ID = re.compile(r'[a-f0-9]{32}')
_CODE = re.compile(r'[0-9]{6}')


def require(ok, message='原版研究报告或绑定原件未通过校验'):
    if not ok:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def digest(value):
    return sha256(canonical(value)).hexdigest()


def _pairs(items):
    value = {}
    for key, item in items:
        require(key not in value)
        value[key] = item
    return value


def decode(raw):
    """有限JSON，拒绝重复键和非有限数；原件字节摘要另由归档reader拥有。"""
    require(len(raw) <= MAX_BYTES)
    def finite(text):
        value = float(text)
        require(math.isfinite(value))
        return value
    return json.loads(raw, object_pairs_hook=_pairs, parse_float=finite,
                      parse_constant=lambda _value: require(False))


def number(value, *, lower=0, upper=1e20):
    return type(value) in (int, float) and lower <= value <= upper and (type(value) is int or math.isfinite(value))


def day(value):
    require(type(value) is str and len(value) == 10)
    parsed = date.fromisoformat(value)
    require(parsed.isoformat() == value and 1900 <= parsed.year < 3000)
    return int(value.replace('-', ''))


def _text(value, maximum=512):
    return type(value) is str and len(value) <= maximum and all(ord(c) >= 32 for c in value)


def strategy():
    return dict(id=ALGORITHM,  # 独立只读研究策略ID，不能作为交易安装选择。
                version=VERSION,  # 自有接缝版本，与固定上游提交分别标识。
                algorithm_id=ALGORITHM)  # 原stable路由计算身份。


def configuration(report, label):
    history = report['portfolio']['history']
    return dict(label=label,  # 维护者给出的研究报告名称。
                name='original',  # 通用目录配置名，不提供执行入口。
                start=day(history[0]['date']) * 10000,  # 中国交易日期首日00:00。
                end=day(history[-1]['date']) * 10000 + 2359,  # 尾日23:59，展示窗口。
                session_sha256=report['input_sha256'],  # 原冻结输入canonical摘要。
                max_seconds=30)  # 页面单次读取期限秒，不是原版运行耗时。


def validate_report(report, snapshot, manifest, check=lambda: None):
    """验证固定原版身份、模型及被页面消费的日线/成交事实；不提升来源/PIT资格。"""
    check()
    require(type(report) is dict and set(report) - {'research_diagnostics'} == {
        'schema', 'algorithm_id', 'upstream_commit', 'input_sha256', 'data_kind', 'source',
        'execution_qualified', 'point_in_time_qualified', 'strategy_results', 'trades_by_code',
        'resonance', 'turnover_percentiles', 'margin_percentiles', 'portfolio', 'data_audit',
        'model', 'source_manifest_sha256'})
    require(report['schema'] == REPORT_SCHEMA and report['algorithm_id'] == ALGORITHM
            and report['upstream_commit'] == COMMIT and report['execution_qualified'] is False
            and report['point_in_time_qualified'] is False)
    require(type(snapshot) is dict and snapshot.get('schema') == 'guanheng.resonance-original-input.v1'
            and snapshot.get('upstream_commit') == COMMIT and report['input_sha256'] == digest(snapshot)
            and report['source'] == snapshot.get('source') and type(report['source']) is dict
            and report['data_kind'] == snapshot.get('data_kind')
            and report['data_kind'] in ('synthetic', 'historical-final'))
    require(type(manifest) is dict and manifest.get('commit') == COMMIT
            and digest(manifest) == SOURCE_MANIFEST_SHA == report['source_manifest_sha256'])
    for key in ('description', 'alignment', 'market_turnover_model', 'price_basis', 'historical_available_at'):
        if key in report['source']:
            require(report['source'][key] is None or _text(report['source'][key], 2048))
    if 'units_qualified' in report['source']:
        require(type(report['source']['units_qualified']) is bool)
    model = report['model']
    expected = dict(signal_version='stable', execution='next-trading-day-close', fees=0,
                    fractional_shares=True, allocation='new-buy-equal-weight-full-equity',
                    sell_rebalance=False, historical_features='as-stored-final-rows', initial_equity=1.0,
                    historical_availability='unknown', warmup='original-function-behaviour',
                    prefix_stability='not-guaranteed-by-upstream-minimum-length-guards')
    require(type(model) is dict and set(model) == set(expected) | {'calendar_fallback'}
            and all(model[k] == value and type(model[k]) is type(value) for k, value in expected.items())
            and type(model['calendar_fallback']) is bool)
    codes = snapshot.get('codes')
    require(type(codes) is list and 1 <= len(codes) <= 17 and len(set(codes)) == len(codes)
            and all(type(c) is str and _CODE.fullmatch(c) for c in codes))
    for key in ('strategy_results', 'trades_by_code', 'resonance'):
        require(type(report[key]) is dict and set(report[key]) == set(codes))
    signal_count = 0
    for rows in report['trades_by_code'].values():
        require(type(rows) is list)
        previous_signal = None
        for row in rows:
            check()
            signal_count += 1
            require(signal_count <= MAX_TRADES and type(row) is dict
                    and set(row) == {'date', 'action', 'price', 'reason'})
            current_signal = day(row['date'])
            require((previous_signal is None or current_signal >= previous_signal)
                    and row['action'] in ('BUY', 'SELL') and number(row['price'], lower=1e-15)
                    and _text(row['reason'], 2048))
            previous_signal = current_signal
    require(type(report['data_audit']) is dict and type(report['turnover_percentiles']) is dict
            and type(report['margin_percentiles']) is dict)
    coverage = report['data_audit'].get('coverage', {})
    require(type(coverage) is dict and len(coverage) <= 17)
    for code, row in coverage.items():
        check()
        require(type(code) is str and _CODE.fullmatch(code) and type(row) is dict)
        for key in ('first', 'last'):
            if key in row and row[key] is not None:
                day(row[key])
        for key in ('rows', 'pre_evaluation_rows', 'calendar_gap_count'):
            if key in row:
                require(type(row[key]) is int and 0 <= row[key] <= 60000)
        if 'missing' in row:
            require(type(row['missing']) is dict and len(row['missing']) <= 64
                    and all(_text(key, 64) and type(count) is int and 0 <= count <= 60000
                            for key, count in row['missing'].items()))
    portfolio = report['portfolio']
    require(type(portfolio) is dict and set(portfolio) == {'history', 'trade_log', 'final_equity',
        'total_return_pct', 'max_drawdown_pct', 'empty_days', 'empty_days_pct', 'open_positions'})
    history = portfolio['history']
    require(type(history) is list and 1 <= len(history) <= MAX_DAYS)
    previous, dates = None, set()
    for row in history:
        check()
        require(type(row) is dict and set(row) == {'date', 'equity', 'invested', 'position_pct'})
        current = day(row['date'])
        require(previous is None or current > previous)
        require(number(row['equity'], lower=1e-15) and number(row['invested'])
                and number(row['position_pct'], upper=100.001))
        previous = current
        dates.add(row['date'])
    require(history[0]['equity'] == 1 and portfolio['final_equity'] == history[-1]['equity'])
    require(number(portfolio['total_return_pct'], lower=-100, upper=1e20)
            and number(portfolio['max_drawdown_pct'], upper=100)
            and type(portfolio['empty_days']) is int and 0 <= portfolio['empty_days'] <= len(history)
            and number(portfolio['empty_days_pct'], upper=100))
    logs = portfolio['trade_log']
    require(type(logs) is list and len(logs) <= MAX_TRADES)
    previous = None
    for row in logs:
        check()
        require(type(row) is dict and set(row) == {'date', 'signal_date', 'code', 'kind', 'price', 'amount', 'weight_pct'})
        current = day(row['date'])
        require(row['date'] in dates and day(row['signal_date']) < current
                and (previous is None or current >= previous) and row['code'] in codes
                and row['kind'] in ('BUY', 'REFILL', 'TRIM', 'SELL')
                and number(row['price'], lower=1e-15) and number(row['amount'])
                and number(row['weight_pct'], upper=100.001)
                and number(row['amount'] / row['price']))
        previous = current
    require(type(portfolio['open_positions']) is list and len(portfolio['open_positions']) <= len(codes))
    opened = set()
    for row in portfolio['open_positions']:
        check()
        require(type(row) is dict and set(row) == {'buy_date', 'code', 'shares'}
                and row['code'] in codes and row['code'] not in opened and number(row['shares'], lower=1e-15))
        require(day(row['buy_date']) <= day(history[-1]['date']))
        opened.add(row['code'])
    check()
    return report


def receipt(report, label, run_id, report_raw, input_raw, manifest_raw):
    require(type(run_id) is str and _ID.fullmatch(run_id) and _text(label, 100) and bool(label))
    return dict(schema=RECEIPT_SCHEMA,  # 独立导入完成证明，不冒充WT执行证明。
                run_id=run_id,  # 显式维护导入身份，32位hex。
                report_family=FAMILY,  # 原版报告族，驱动只读分流。
                report_sha256=sha256(report_raw).hexdigest(),  # 原报告字节摘要。
                input_file_sha256=sha256(input_raw).hexdigest(),  # 原冻结输入文件字节摘要。
                source_manifest_file_sha256=sha256(manifest_raw).hexdigest(),  # 算法清单原字节摘要。
                record_count=len(report['portfolio']['history']),  # 原每日权益记录数。
                configuration=configuration(report, label),  # 只读通用目录窗口。
                strategy=strategy(),  # 独立原版展示身份。
                scope=SCOPE)  # 研究、归一化及未获执行/PIT资格。


def validate_receipt(value, run_id):
    require(type(value) is dict and set(value) == {'schema', 'run_id', 'report_family', 'report_sha256',
        'input_file_sha256', 'source_manifest_file_sha256', 'record_count', 'configuration', 'strategy', 'scope'})
    require(value['schema'] == RECEIPT_SCHEMA and value['run_id'] == run_id
            and type(run_id) is str and _ID.fullmatch(run_id) and value['report_family'] == FAMILY
            and value['strategy'] == strategy() and value['scope'] == SCOPE)
    require(all(type(value[k]) is str and _SHA.fullmatch(value[k]) for k in
                ('report_sha256', 'input_file_sha256', 'source_manifest_file_sha256')))
    require(type(value['record_count']) is int and 1 <= value['record_count'] <= MAX_DAYS)
    config = value['configuration']
    require(type(config) is dict and set(config) == {'label', 'name', 'start', 'end', 'session_sha256', 'max_seconds'}
            and _text(config['label'], 100) and bool(config['label']) and config['name'] == 'original'
            and type(config['start']) is int and type(config['end']) is int
            and type(config['session_sha256']) is str and _SHA.fullmatch(config['session_sha256'])
            and type(config['max_seconds']) is int and config['max_seconds'] == 30)
    return value


def load(read, directory, value):
    """复核三份固定命名原件；归档reader统一防链接、容量和截止。"""
    objects = []
    for name, key in (('original-report.json', 'report_sha256'), ('original-input.json', 'input_file_sha256'),
                      ('source-manifest.json', 'source_manifest_file_sha256')):
        raw = read.raw(directory / name, MAX_BYTES)
        require(sha256(raw).hexdigest() == value[key])
        objects.append(decode(raw))
    report = validate_report(*objects, check=read.check)
    require(value['record_count'] == len(report['portfolio']['history'])
            and value['configuration'] == configuration(report, value['configuration']['label']))
    return report


def summary():
    return dict(strategy={k: v for k, v in strategy().items() if k != 'algorithm_id'},  # 原版登记身份。
                initial_equity=1,  # 归一化初始权益，无人民币本金。
                unit='normalized-equity',  # 禁止套用CNY金额格式。
                report_family=FAMILY)  # summary的独立报告族。


def _base(value, receipt_sha):
    return dict(run_id=value['run_id'],  # 原件导入身份。
                receipt_sha256=receipt_sha,  # 当前完成证明原字节摘要。
                report_sha256=value['report_sha256'])  # 原报告原字节摘要。


def _source(report):
    # 白名单去除原source中机器路径、巨大notes及其他未声明业务字段。
    return {k: report['source'][k] for k in ('description', 'alignment', 'market_turnover_model',
        'price_basis', 'historical_available_at', 'units_qualified') if k in report['source']}


def performance(value, receipt_sha, report, check=lambda: None):
    points, peak, maximum = [], 1.0, 0.0
    for row in report['portfolio']['history']:
        check()
        peak = max(peak, row['equity'])
        maximum = max(maximum, (1 - row['equity'] / peak) * 100)
        points.append([day(row['date']), row['equity']])
    return {**_base(value, receipt_sha), 'schema': 'orr-performance-v1',  # ORR独立绩效协议。
        'strategy': strategy(),  # 原版策略/算法身份。
        'configuration': value['configuration'],  # 原报告展示窗口及输入身份。
        'unit': 'normalized-equity',  # 权益数值单位，初值1。
        'metrics': dict(initial_equity=1, last_equity=points[-1][1],
            total_return_pct=(points[-1][1] - 1) * 100, observed_max_drawdown_pct=maximum, fees=0),  # 原零费模型。
        'observations': dict(total=len(points), available=len(points), missing=0,
                             last_trading_date=points[-1][0]),  # 原报告可见记录数，非源日历完整性。
        'points': points,  # 中国交易日和原报告已舍入每日权益。
        'model': report['model'],  # 固定原stable/次日收盘/浮点份额模型。
        'source': _source(report),  # 来源公开白名单，原诊断仍保留原件。
        'data_kind': report['data_kind'],  # 合成或历史最终行声明。
        'input_sha256': report['input_sha256'],  # 原完整冻结输入canonical摘要。
        'source_manifest_sha256': report['source_manifest_sha256'],  # 固定算法源码清单摘要。
        'execution_qualified': False,  # 报告展示不提供执行资格。
        'point_in_time_qualified': False,  # 历史首次可知时间未合格。
        'scope': SCOPE}  # 原版独立研究边界。


def trades(report, check=lambda: None):
    result = []
    for index, row in enumerate(report['portfolio']['trade_log']):
        check()
        result.append(dict(index=index,  # 原trade_log序号，全局稳定分页键。
            date=day(row['date']), signal_date=day(row['signal_date']),  # 执行日及前一信号日，中国交易日期。
            symbol=row['code'], side='buy' if row['kind'] in ('BUY', 'REFILL') else 'sell',  # 原六位代码/资金方向。
            action=row['kind'], price=row['price'],  # 保留原BUY/REFILL/TRIM/SELL和原价格。
            quantity=row['amount'] / row['price'],  # 原归一化成交额/价格；浮点模型份额，非账户实际份额。
            amount=row['amount'], weight_pct=row['weight_pct'],  # 归一化成交额和本笔后原目标权重百分数。
            fee=0, reason=''))  # 原零费成交模型；原trade_log缺少reason以空串标识。
    return result


def visuals(value, receipt_sha, report, check=lambda: None):
    counts = {}
    for row in trades(report, check):
        bucket = counts.setdefault(row['date'], [0, 0])
        bucket[0 if row['side'] == 'buy' else 1] += 1
    points, previous, peak = [], None, 1.0
    for row in report['portfolio']['history']:
        check()
        equity, current = row['equity'], day(row['date'])
        peak = max(peak, equity)
        points.append([current, None if previous is None else (equity / previous - 1) * 100,
                       (equity / peak - 1) * 100, *counts.get(current, [0, 0]), 0])
        previous = equity
    return {**_base(value, receipt_sha), 'schema': 'orr-visuals-v1',  # ORR独立曲线辅助协议。
            'trades_available': True, 'points': points}  # 日收益/负回撤/买卖未知数量，沿原模拟成交。


def ledger(value, receipt_sha, report, *, day_filter=None, offset=0, limit=50, check=lambda: None):
    require(type(offset) is int and 0 <= offset <= MAX_TRADES and type(limit) is int and 1 <= limit <= 50)
    dates = {day(row['date']) for row in report['portfolio']['history']}
    require(day_filter is None or day_filter in dates, '该报告没有所选日期')
    rows = [r for r in trades(report, check) if day_filter is None or r['date'] == day_filter]
    return {**_base(value, receipt_sha), 'schema': 'orr-ledger-v1',  # ORR原模型成交分页。
        'date': day_filter, 'unit': 'normalized-equity',  # 可选交易日及归一化金额单位。
        'positions_available': False, 'positions': [],  # 原件缺逐日完整持仓快照，空数组不是空仓事实。
        'trades_available': True, 'total': len(rows), 'offset': offset,  # 过滤后原成交总数和分页位置。
        'trades': rows[offset:offset + limit]}  # 至多50笔原模拟成交。


def signals(value, receipt_sha, report, *, day_filter=None, offset=0, limit=50, check=lambda: None):
    """原策略BUY/SELL信号独立分页；信号价格与组合次日模拟成交分别呈现。"""
    require(type(offset) is int and 0 <= offset <= MAX_TRADES and type(limit) is int and 1 <= limit <= 50)
    rows = []
    for code, items in report['trades_by_code'].items():
        for ordinal, row in enumerate(items):
            check()
            rows.append((day(row['date']), code, ordinal, row))
    rows.sort(key=lambda row: row[:3])
    indexed = [dict(index=index, date=current, symbol=code, action=row['action'],
                    price=row['price'], reason=row['reason'])  # 原信号日/六位证券/BUY或SELL/信号收盘价/原理由。
               for index, (current, code, _ordinal, row) in enumerate(rows)]
    selected = [row for row in indexed if day_filter is None or row['date'] == day_filter]
    return {**_base(value, receipt_sha), 'schema': 'orr-signals-v1',  # 原信号独立协议。
        'date': day_filter, 'total': len(selected), 'offset': offset,  # 筛选后的信号日/总数/分页位置。
        'signals': selected[offset:offset + limit], 'scope': SCOPE}  # 至多50个原信号，与模拟调仓分离。


def project(value, receipt_sha, report, *, config=False, perf=False, offset=0, limit=50, index=None, check=lambda: None):
    if perf:
        return performance(value, receipt_sha, report, check)
    base = {**_base(value, receipt_sha), 'scope': SCOPE}  # 共享原件身份与研究边界。
    if config:
        coverage = report['data_audit'].get('coverage', {})
        return {**base, 'schema': 'orr-archive-configuration-v1', 'configuration': value['configuration'],
            'strategy': strategy(), 'model': report['model'], 'unit': 'normalized-equity',
            'input_sha256': report['input_sha256'], 'source_manifest_sha256': report['source_manifest_sha256'],
            'data_kind': report['data_kind'], 'source': _source(report),
            'data_audit': {k: {f: row[f] for f in ('first', 'last', 'rows', 'pre_evaluation_rows',
                'missing', 'calendar_gap_count') if f in row} for k, row in coverage.items()},
            'execution_qualified': False, 'point_in_time_qualified': False}
    history = report['portfolio']['history']
    if index is not None:
        require(type(index) is int and 0 <= index < len(history), '记录索引越界')
        row = history[index]
        return {**base, 'schema': 'orr-day-v1', 'index': index, 'unit': 'normalized-equity',
                'record': {**row, 'trading_date': day(row['date'])},
                'trades': [r for r in trades(report, check) if r['date'] == day(row['date'])],
                'signals': signals(value, receipt_sha, report, day_filter=day(row['date']), check=check)}
    require(type(offset) is int and 0 <= offset <= MAX_DAYS and type(limit) is int and 1 <= limit <= 50)
    return {**base, 'schema': 'orr-records-v1', 'total': len(history), 'offset': offset,
            'records': [dict(trading_date=day(r['date']), minute=1500, status='observed',
                             reason='original-next-close-model') for r in history[offset:offset + limit]]}
