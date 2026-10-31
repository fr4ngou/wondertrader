"""沪深北同日公开原件准入；股票池、采集和展示继续沿独立观察目录。"""

from collections import Counter
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, DecimalException, localcontext
import json
from pathlib import Path
import re

from .breadth_models import ASHARE_METRICS, rows_for_metrics, universe_row
from .market_breadth import stock_day
from .source_fetch import SourceFailure
from .storage import digest

UNIVERSE = 'source.ashare_day_universe'
ZONE = timezone(timedelta(hours=8))
FIELDS = ['date', 'code', 'close', 'preclose', 'volume', 'turn', 'tradestatus']


def _need(value, code='ashare_source_schema'):
    if not value:
        raise SourceFailure(code)


def _decode(body):
    """JSONP只移除有限标识符包装；逐层拒绝重复键和非有限数字。"""
    def unique(pairs):
        result = {}
        for key, value in pairs:
            _need(key not in result)
            result[key] = value
        return result

    def reject(_):
        raise SourceFailure('ashare_source_schema')

    text = body.decode('utf-8').strip()
    if not text.startswith(('[', '{')):
        match = re.fullmatch(r'[A-Za-z_$][A-Za-z0-9_$]{0,127}\((.*)\);?\s*', text, re.S)
        _need(match is not None)
        text = match[1]
    return json.loads(text, object_pairs_hook=unique, parse_float=Decimal, parse_constant=reject)


def _day(value):
    _need(type(value) is str and date.fromisoformat(value).isoformat() == value)
    return value


def _clock(value):
    _need(type(value) is str)
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    _need(parsed.tzinfo is not None and parsed.utcoffset() is not None
          and parsed <= datetime.now(timezone.utc), 'ashare_source_clock')
    return parsed


class Capture:
    """输入包是不可变原件引用；逐件核SHA，原接收时间与入库时间分离。"""
    def __init__(self, fetch, manifest):
        self.fetch = fetch
        self.root = manifest.resolve(strict=True).parent

    def read(self, descriptor, kind, *, timed=True):
        keys = {'path', 'sha256', 'received_at'} if timed else {'path', 'sha256'}
        _need(type(descriptor) is dict and set(descriptor) == keys)
        name, identity = descriptor['path'], descriptor['sha256']
        _need(type(name) is str and 0 < len(name) <= 512
              and not Path(name).is_absolute() and '..' not in Path(name).parts
              and type(identity) is str and re.fullmatch('[a-f0-9]{64}', identity))
        path = (self.root / name).resolve(strict=True)
        _need(path.is_relative_to(self.root), 'ashare_source_path')
        self.fetch.budget.remaining()
        with path.open('rb') as stream:
            body = stream.read(self.fetch.budget.response_bytes + 1)
        _need(len(body) <= self.fetch.budget.response_bytes, 'ashare_source_capacity')
        self.fetch.budget.consume(len(body))
        _need(digest(body) == identity, 'ashare_source_identity')
        record = dict(kind=kind, sha256=identity, media_type='application/json')
        if timed:
            _clock(descriptor['received_at'])
            record['retrieved_at'] = descriptor['received_at']
        self.fetch.objects.put(body)
        self.fetch.records.append(record)
        value = _decode(body)
        self.fetch.budget.remaining()
        return value


def _pages(capture, descriptors, kind, code_key, day):
    """北交所每页20行；页号、总数、唯一证券及同一交易日共同闭合。"""
    _need(type(descriptors) is list and 1 <= len(descriptors) <= 100)
    rows, total = {}, None
    for number, descriptor in enumerate(descriptors):
        capture.fetch.budget.remaining()
        raw = capture.read(descriptor, kind)
        _need(type(raw) is list and len(raw) == 1 and type(raw[0]) is dict)
        value = raw[0]
        if total is None:
            total = value['totalElements']
            _need(type(total) is int and 1 <= total <= 2000
                  and len(descriptors) == (total + 19) // 20)
        _need(all(type(value[key]) is int for key in
                  ('number', 'size', 'totalElements', 'totalPages', 'numberOfElements'))
              and value['number'] == number and value['size'] == 20
              and value['totalElements'] == total and value['totalPages'] == len(descriptors)
              and value['firstPage'] is (number == 0)
              and value['lastPage'] is (number == len(descriptors) - 1)
              and type(value['content']) is list
              and len(value['content']) == value['numberOfElements'] == min(20, total - 20 * number))
        for row in value['content']:
            capture.fetch.budget.remaining()
            _need(type(row) is dict)
            code = row[code_key]
            _need(type(code) is str and re.fullmatch('[0-9]{6}', code) and code not in rows)
            source_day = row['hqjsrq' if code_key == 'hqzqdm' else 'xxjsrq']
            _need(str(source_day) == day.replace('-', ''), 'ashare_source_date')
            if code_key == 'hqzqdm':
                clock = str(row['hqgxsj']).zfill(6)
                _need(re.fullmatch('[0-9]{6}', clock) and '153000' <= clock <= '235959',
                      'ashare_source_not_closed')
                source_time = datetime.combine(date.fromisoformat(day),
                    datetime.strptime(clock, '%H%M%S').time(), ZONE)
                _need(source_time <= _clock(descriptor['received_at']), 'ashare_source_clock')
            rows[code] = row
    _need(len(rows) == total)
    return rows


def _integer(value, *, positive=False):
    _need(type(value) in (int, Decimal))
    if type(value) is Decimal:
        _need(value.is_finite())
    _need((value > 0 if positive else value >= 0) and value <= 10**15)
    # 先用Decimal范围比较拒绝巨大指数，整数展开只发生在已核有限范围内。
    _need(value == int(value))
    return int(value)


def _price(value):
    _need(type(value) in (int, Decimal))
    if type(value) is Decimal:
        _need(value.is_finite())
    number = Decimal(value)
    _need(0 < number <= Decimal('1e15'))
    return number


def history(fetch, config, start, end):
    """一个同日股票池合并两地来源后只调用一次统一计算owner。

    此入口接收显式采集包，来源缺失或尚未闭市整批保旧；输入包更新由采集部署
    持有，读取App不推定来源已连接。证券表F/N为已核正常状态，其余状态拒绝冒算。
    """
    try:
        return _history(fetch, config, start, end)
    except SourceFailure:
        raise
    except (OSError, ValueError, KeyError, TypeError, IndexError, OverflowError,
            RecursionError, DecimalException):
        raise SourceFailure('ashare_source_schema') from None


def _history(fetch, config, start, end):
    path = Path(config['input_manifest'])
    capture = Capture(fetch, path)
    manifest = capture.read(dict(path=path.name, sha256=config['input_sha256']),
                            'ashare_public_inputs', timed=False)
    _need(type(manifest) is dict and set(manifest) ==
          {'schema', 'date', 'closed_at', 'universe', 'shsz_daily', 'bse_quotes', 'bse_static'}
          and manifest['schema'] == 'guanheng.ashare-public-inputs.v1')
    day = _day(manifest['date'])
    _need(start <= day == end, 'ashare_source_date')
    closed = _clock(manifest['closed_at']).astimezone(ZONE)
    _need(closed.date().isoformat() == day and (closed.hour, closed.minute) >= (15, 30),
          'ashare_source_not_closed')
    universe = capture.read(manifest['universe'], 'stock_universe', timed=False)
    members = universe['members']
    _need(universe['date'] == day and type(members) is list and 3 <= len(members) <= 20000
          and all(type(code) is str and re.fullmatch(r'(sh|sz|bj)\.[0-9]{6}', code) for code in members)
          and len(set(members)) == len(members) and type(universe['market_count']) is int
          and universe['market_count'] == len(members))
    counts = dict(Counter(code[:2] for code in members))
    _need(set(counts) == {'sh', 'sz', 'bj'} and universe['exchange_counts'] == counts)
    daily = capture.read(manifest['shsz_daily'], 'stock_daily_batch')
    _need(type(daily) is dict and type(daily['fields']) is list and type(daily['rows']) is list
          and len(daily['rows']) <= 20000 and len(daily['fields']) <= 64
          and len(set(daily['fields'])) == len(daily['fields']) and set(FIELDS) <= set(daily['fields']))
    normalized, seen = [], set()
    eligible = set(members)
    for values in daily['rows']:
        fetch.budget.remaining()
        _need(type(values) is list and len(values) == len(daily['fields'])
              and all(type(value) is str for value in values))
        row = dict(zip(daily['fields'], values))
        code = row['code']
        _need(re.fullmatch(r'(sh|sz)\.[0-9]{6}', code) and code not in seen
              and row['date'] == day)
        seen.add(code)
        if code in eligible:
            normalized.append([row[field] for field in FIELDS])
    _need(eligible - {code for code in eligible if code.startswith('bj.')} <= seen,
          'ashare_source_coverage')
    quotes = _pages(capture, manifest['bse_quotes'], 'bse_quote_original', 'hqzqdm', day)
    basics = _pages(capture, manifest['bse_static'], 'bse_security_original', 'xxzqdm', day)
    _need(set(quotes) == set(basics) == {code[3:] for code in members if code.startswith('bj.')},
          'ashare_source_coverage')
    for code, quote in sorted(quotes.items()):
        fetch.budget.remaining()
        basic = basics[code]
        _need(quote['xxhbzl'] == '人民币' and basic['xxhbzl'] == '00'
              and type(basic['xxsldw']) is int and basic['xxsldw'] == 1)
        _need(basic['xxtpbz'] == 'F' and basic['xxzrzt'] == 'N', 'ashare_source_status_unqualified')
        shares = _integer(basic['xxfxsgb'], positive=True)
        _need(shares <= _integer(basic['xxzgb'], positive=True))
        volume = _integer(quote['hqcjsl'])
        close, prior = _price(quote['hqzjcj']), _price(quote['hqzrsp'])
        with localcontext() as context:
            context.prec = 40
            turn = Decimal(volume) * 100 / shares
        _need((turn > 5) == (100 * volume > 5 * shares))
        normalized.append([day, 'bj.' + code, str(close), str(prior), str(volume), str(turn), '1'])
    # 原接收时间必须在该观察日闭市以后；它不是历史公布时间。
    for record in fetch.records:
        if 'retrieved_at' in record:
            _need(_clock(record['retrieved_at']) >= closed, 'ashare_source_clock')
    result = stock_day(FIELDS, normalized, members, day, scope='ashare', check=fetch.budget.remaining)
    return {**{key: [row] for key, row in rows_for_metrics(result, ASHARE_METRICS).items()},
            UNIVERSE: [universe_row(day, members, manifest['universe']['sha256'])]}
