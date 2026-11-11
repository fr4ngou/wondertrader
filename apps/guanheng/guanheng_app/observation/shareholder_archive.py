"""重要股东公告历史的离线准入，复用观察内容仓和当前目录 CAS。"""
from bisect import bisect_right
from collections import defaultdict
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import json
from pathlib import Path
import re

from .admission import admit_dataset, register_standard_asset, register_standard_assets
from .contracts import ObservationError
from .metadata import computation_identity
from .publication import adopt_snapshot, check_deadline
from .storage import ContentStore, digest, encode

METRIC = 'shareholder.net.ashare'
INDEXES = {'000985.SH': 'csi_close', '000001.SH': 'sse_close', '399006.SZ': 'chinext_close', '000688.SH': 'star_close'}
MARKETS = {'二级市场', '大宗交易', '二级市场以及大宗交易'}
REPORT_KEY = ('NOTICE_DATE', 'SECURITY_CODE', 'HOLDER_NAME', 'END_DATE', 'START_DATE', 'CHANGE_NUM_SYMBOL', 'MARKET', 'EITIME')
DAY = timedelta(days=1)
FIRST = date(2018, 1, 1)


def _need(condition, detail):
    if not condition:
        raise ObservationError('invalid_shareholder_capture', detail, 422)


def _date(value):
    return date.fromisoformat(value[:10])


def _price(value):
    if value is None:
        return None
    number = Decimal(str(value))
    return number if number.is_finite() and number > 0 else None


def _json(raw):
    return json.loads(raw, parse_float=Decimal)


def _capture_pages(path, store, parents, check, host):
    manifest = json.loads(path.read_bytes())
    captures = manifest['captures']
    _need(bool(captures), '来源原件记录为空')
    for receipt in captures:
        check()
        _need(receipt['source_host'] == host and receipt['status'] == 200, '来源主机或响应状态无效')
        sha = receipt['sha256']
        parents.add(sha)
        if receipt.get('parent_sha256'):
            parents.add(receipt['parent_sha256'])
        if receipt['kind'] != 'http_wire':
            yield _json(store.get(sha))


def _read_report(path, store, parents, lo, hi, check):
    pages = list(_capture_pages(path, store, parents, check, 'datacenter-web.eastmoney.com'))
    count = pages[0]['result']['count']
    _need(count > 0 and len(pages) == (count + 499) // 500, '股东公告分页数量不一致')
    for index, page in enumerate(pages):
        data = page['result']
        _need(page['success'] is True and data['count'] == count and data['pages'] == len(pages)
              and len(data['data']) == min(500, count - index * 500), '股东公告分页缺行或计数漂移')
        for row in data['data']:
            _need(lo <= _date(row['NOTICE_DATE']) <= hi, '股东公告日期超出原查询窗口')
            yield row


def _read_prices(root, store, parents, check):
    indexes, stocks = {}, defaultdict(dict)
    for path in sorted((root / 'prices').glob('*.json')):
        code = path.stem
        (page,) = _capture_pages(path, store, parents, check, 'push2his.eastmoney.com')
        data = page['data']
        market = 1 if code.endswith('.SH') or code.startswith('6') else 0
        _need(page['rc'] == 0 and (data is None or data['code'] == code.split('.')[0]
                                 and data['market'] == market), '历史行情证券身份不一致')
        closes = {}
        for line in (data or {}).get('klines', ()):
            day, _, close = line.split(',')
            value = _price(close)
            _need(value is not None and day not in closes, '历史收盘价无效或重复')
            closes[day] = value
        if code in INDEXES:
            _need(bool(closes), '指数历史收盘序列为空')
            indexes[code] = closes
        else:
            stocks[code].update(closes)
    for path in sorted((root / 'tushare').glob('*.json')):
        (page,) = _capture_pages(path, store, parents, check, 'api.tushare.pro')
        data = page['data']
        _need(page['code'] == 0 and data['fields'] == ['ts_code', 'trade_date', 'close']
              and len(data['items']) < 6000, '补充行情字段或分页容量无效')
        for symbol, day, raw in data['items']:
            code = symbol.split('.')[0]
            close = _price(raw)
            if close is not None:
                iso = datetime.strptime(day, '%Y%m%d').date().isoformat()
                stocks[code].setdefault(iso, close)
    for path in sorted((root / 'fallback').glob('*.json')):
        manifest = json.loads(path.read_bytes())
        code, symbol = manifest['code'], manifest['symbol']
        _need(symbol[2:] == code and path.stem == code + '-' + manifest['end'], '补充行情证券身份无效')
        host = manifest['captures'][0]['source_host']
        _need(host in ('web.ifzq.gtimg.cn', 'q.stock.sohu.com'), '未登记的补充行情来源')
        (page,) = _capture_pages(path, store, parents, check, host)
        if host == 'web.ifzq.gtimg.cn':
            _need(page['code'] == 0, '腾讯历史行情结果无效')
            values = page['data'][symbol]['day']
        else:
            _need(len(page) == 1 and page[0]['code'] == 'cn_'+code and page[0]['status'] == 0, '搜狐历史行情结果无效')
            values = page[0]['hq']
        for day, _, raw, *_ in values:
            close = _price(raw)
            _need(close is not None and manifest['start'] <= day <= manifest['end'], '补充历史行情日期或收盘价无效')
            stocks[code].setdefault(day, close)
    _need(set(indexes) == set(INDEXES), '缺少四条指数历史原件')
    return indexes, {code: (sorted(closes), closes) for code, closes in stocks.items()}


def _reference_close(stocks, code, trade_day):
    dates, closes = stocks.get(code, ((), {}))
    index = bisect_right(dates, trade_day.isoformat()) - 1
    if index >= 0 and trade_day - date.fromisoformat(dates[index]) <= timedelta(days=30):
        return closes[dates[index]]
    return None


def aggregate(rows, start, end, indexes, stocks, check=lambda: None):
    """每公告日累计人民币元，估值、缺价及时间冲突按笔单列。"""
    daily = defaultdict(lambda: dict(net_amount_cny=Decimal(0), priced_trade_count=0,
        estimated_count=0, unpriced_count=0, timing_conflict_count=0))
    seen = set()
    for event in rows:
        check()
        identity = tuple(event[key] for key in REPORT_KEY)
        _need(identity not in seen, '股东公告原始分页身份重复')
        seen.add(identity)
        code = event['SECURITY_CODE']
        _need(re.fullmatch(r'(?:00|30|60|68|83|92)\d{4}', code) is not None and event['MARKET'] in MARKETS,
              '股东公告出现未登记的A股代码或成交方式')
        day, trade_day = _date(event['NOTICE_DATE']), _date(event['TRADE_DATE'])
        quantity = Decimal(str(event['CHANGE_NUM_SYMBOL']))
        _need(quantity.is_finite() and quantity != 0 and abs(quantity) == Decimal(str(event['CHANGE_NUM']))
              and event['DIRECTION'] == ('减持' if quantity < 0 else '增持'), '股东公告股份数量和方向不一致')
        values = daily[day]
        if trade_day > day:
            values['timing_conflict_count'] += 1
            continue
        price = _price(event['TRADE_AVERAGE_PRICE'])
        if price is not None:
            values['priced_trade_count'] += 1
        else:
            price = _price(event['CLOSE_PRICE']) or _reference_close(stocks, code, trade_day)
            values['estimated_count' if price is not None else 'unpriced_count'] += 1
        if price is not None:
            values['net_amount_cny'] += quantity * price * 10_000
    result = []
    for offset in range((end - start).days + 1):
        day = start + offset * DAY
        key = day.isoformat()
        values = daily[day]
        values['net_amount_cny'] = float(values['net_amount_cny'])
        for symbol, field in INDEXES.items():
            value = indexes[symbol].get(key)
            values[field] = float(value) if value is not None else None
        result.append(dict(date=key, **values))
    return result


def definition():
    labels = {
        'date': ('公告日', '日期'), 'net_amount_cny': ('可计价净增持额', '元'),
        'priced_trade_count': ('成交均价计价', '笔'), 'estimated_count': ('历史收盘价估算', '笔'),
        'unpriced_count': ('缺少合格历史价格', '笔'), 'timing_conflict_count': ('变动日期晚于公告日待核', '笔'),
        'csi_close': ('中证全指', '指数点'), 'sse_close': ('上证指数', '指数点'),
        'chinext_close': ('创业板指', '指数点'), 'star_close': ('科创50', '指数点'),
    }
    formula = '有成交均价按均价乘变动股数；缺失时用历史收盘价估算。周度净减持为日净增持求和后取反。'
    reading = '按东方财富 Choice 股东增减持明细公告日汇总二级市场及大宗交易，保留估算和缺价计数。'
    return dict(id=METRIC, board='executive', label='重要股东净减持 · 沪深北', default_preset='all',
        frequency='自然日公告 · 按周汇总', source='东方财富 Choice 股东增减持明细及指数行情',
        source_url='https://data.eastmoney.com/executive/gdzjc.html', unit='元', parameters=False,
        definition_version=METRIC+'/1', primary_field='net_amount_cny',
        field_schema={key: dict(label=label, unit=unit) for key, (label, unit) in labels.items()},
        lines=[dict(key='net_amount_cny', name='可计价净增持额', unit='元', color='#80a5cf',
                    panel='main', shown=True, formula=formula, reading=reading)],
        formula=formula, reading=reading, limitations=[
            '成交均价缺失时使用来源历史参考价，或交易截止日及其之前30日内最后未复权收盘价估算。',
            '缺少合格历史价格时金额不计入小计；日期冲突记录单列。当前归档按公告日回溯，历史当时可得性未知。',
        ])


def publish_archive(reader, root, end, expected, deadline):
    """核固定原页与历史行情，再在原观察目录下一次采用。"""
    root = Path(root)
    check = lambda: check_deadline(deadline)
    store = ContentStore(root)
    parents = set()
    indexes, stocks = _read_prices(root, store, parents, check)
    for symbol, closes in indexes.items():
        last = max(closes)
        first = min(closes)
        _need(last >= (end - timedelta(days=7)).isoformat() and
              first <= ('2020-07-24' if symbol == '000688.SH' else '2018-01-05'), '指数首尾覆盖不足')
    indexes['000688.SH'] = {day: close for day, close in indexes['000688.SH'].items() if day >= '2020-07-22'}
    rows = []
    lo = FIRST
    while lo <= end:
        next_month = (lo.replace(day=28) + timedelta(days=4)).replace(day=1)
        hi = min(end, next_month - DAY)
        rows.extend(_read_report(root / (lo.isoformat()[:7]+'.json'), store, parents, lo, hi, check))
        lo = next_month
    values = aggregate(rows, FIRST, end, indexes, stocks, check)
    with reader.repository.collection_lease() as acquired:
        if not acquired or reader.repository.current() != expected:
            raise ObservationError('publication_conflict', '观察目录正在更新或当前版本已变化', 409)
        _, previous = reader.snapshot(expected)
        candidate = deepcopy(previous)
        for sha in sorted(parents):
            check()
            reader.objects.put(store.get(sha))
        capture = reader.objects.put(encode(dict(start=FIRST.isoformat(), end=end.isoformat(),
            rows=len(rows), raw_objects=sorted(parents))), kind='standard')
        register_standard_asset(reader.objects, candidate, METRIC+'.capture', capture, parents,
                                'archive.shareholder-history', media_type='application/json')
        candidate['datasets'][METRIC] = admit_dataset(reader.objects, definition(), values, [capture])
        candidate['preferences']['default_datasets']['executive'] = METRIC
        for board in candidate['boards']:
            if board['id'] == 'executive':
                board['label'] = '股东与高管增减持'
        register_standard_assets(reader.objects, candidate)
        candidate.update(published_at=datetime.now(timezone.utc).isoformat(),
                         computation_identity=computation_identity(), parent_snapshot=expected)
        result = adopt_snapshot(reader, candidate, digest(encode(candidate)), expected, deadline)
    return dict(**result, shareholder_rows=len(rows),
                **{name: sum(row[name] for row in values)
                   for name in ('priced_trade_count', 'estimated_count', 'unpriced_count', 'timing_conflict_count')})
