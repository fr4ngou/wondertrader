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
        self.input_records = []

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
        self.input_records.append(record)
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
                # hqgxsj是逐证券最后更新时间；停牌证券可早于收盘。整批闭市资格由
                # 同日结算日期和收盘后原件接收时刻确认，不强求每只股票15:30成交。
                _need(re.fullmatch('[0-9]{6}', clock) and '000000' <= clock <= '235959',
                      'ashare_source_clock')
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


def bse_numbers(quote, basic):
    """数值准入同时用于定日部件归档与完整统计，避免坏部件永久复用。"""
    def optional(value,kind):
        if value in (None,''):return None
        if kind=='quantity':return _integer(value)
        _need(type(value) in (int,Decimal))
        number=Decimal(value)
        _need(number.is_finite() and 0<=number<=Decimal('1e15'))
        return number
    _need(quote.get('xxhbzl')=='人民币' and basic.get('xxhbzl','00')=='00')
    volume=optional(quote.get('hqcjsl'),'quantity')
    shares=optional(basic.get('xxfxsgb'),'quantity')
    total=optional(basic.get('xxzgb'),'quantity')
    if shares is not None and total is not None:_need(shares<=total)
    return volume,shares,optional(quote.get('hqzjcj'),'price'),optional(quote.get('hqzrsp'),'price')


def validate_daily(table,day,check):
    """原日线部件与完整准入共用结构、日期、唯一证券和数值容量规则。"""
    from .market_breadth import _number
    _need(type(table) is dict and type(table.get('fields')) is list and type(table.get('rows')) is list)
    fields,rows=table['fields'],table['rows']
    _need(len(rows)<=20000 and len(fields)<=64 and len(set(fields))==len(fields) and set(FIELDS)<=set(fields))
    seen=set()
    for values in rows:
        check()
        _need(type(values) is list and len(values)==len(fields) and all(type(v) is str for v in values))
        row=dict(zip(fields,values));code=row['code']
        _need(re.fullmatch(r'(sh|sz)\.[0-9]{6}',code) and code not in seen and row['date']==day)
        seen.add(code)
        numbers={key:_number(row[key]) for key in ('close','preclose','volume','turn')}
        volume,turn=numbers['volume'],numbers['turn']
        _need(volume is None or volume>=0 and volume==volume.to_integral_value())
        _need(turn is None or turn>=0)


def history(fetch, config, start, end):
    """一个同日股票池合并两地来源后只调用一次统一计算owner。

    此入口接收显式采集包，日期或完整性失败保旧；部分字段缺失按股票及指标资格
    单列。固定原件消费与公开采集复用同一准入实现。
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
    return normalize(capture, manifest, start, end)


def normalize(capture, manifest, start, end):
    """固定文件包与公开源归档共用全部同日、字段和统一计算准入。"""
    fetch = capture.fetch
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
    validate_daily(daily,day,fetch.budget.remaining)
    _need(type(daily) is dict and type(daily['fields']) is list and type(daily['rows']) is list
          and len(daily['rows']) <= 20000 and len(daily['fields']) <= 64
          and len(set(daily['fields'])) == len(daily['fields']) and set(FIELDS) <= set(daily['fields']))
    normalized, seen = [], set()
    eligible = set(members)
    unverified=universe.get('unverified_members',{})
    _need(type(unverified) is dict and set(unverified)<=eligible)
    _need(not universe.get('unresolved_identity_count',0) or
        universe['unresolved_identity_count']==len(unverified),'ashare_legacy_universe_unqualified')
    stats=dict(identity_unverified_count=len(unverified),state_unverified_count=0,
        missing_float_count=0,special_reference_count=0,halted_with_trades_count=0)
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
            qualification='identity_unverified' if code in unverified else 'qualified'
            if row['tradestatus'] not in ('0','1') and qualification=='qualified':
                qualification='state_unverified';stats['state_unverified_count']+=1
            normalized.append([*[row[field] for field in FIELDS],qualification])
    quotes = _pages(capture, manifest['bse_quotes'], 'bse_quote_original', 'hqzqdm', day)
    basics = _pages(capture, manifest['bse_static'], 'bse_security_original', 'xxzqdm', day)
    excluded=universe.get('excluded_members',{})
    _need(type(excluded) is dict)
    for code in set(quotes)|set(basics):
        _need('bj.'+code in eligible or 'bj.'+code in excluded,'ashare_source_coverage')
    text=lambda value:'' if value is None else str(value)
    for code, quote in sorted(quotes.items()):
        fetch.budget.remaining()
        symbol='bj.'+code
        if symbol not in eligible:continue
        basic=basics.get(code,{})
        volume,shares,close,prior=bse_numbers(quote,basic)
        paused=basic.get('xxtpbz') in ('T','H')
        trading=basic.get('xxzrzt') in ('N','Y','D') and basic.get('xxtpbz') in ('F','T','H')
        status='0' if trading and paused and volume in (None,0) else '1' if trading else '?'
        qualification='identity_unverified' if symbol in unverified else 'qualified'
        if status=='?' and qualification=='qualified':
            qualification='state_unverified';stats['state_unverified_count']+=1
        turn=None
        if status=='1':
            if not shares:stats['missing_float_count']+=1
            if volume is not None and shares:
                with localcontext() as context:
                    context.prec=40;turn=Decimal(volume)*100/shares
                _need((turn>5)==(100*volume>5*shares))
            if qualification=='qualified':
                if paused and volume:stats['halted_with_trades_count']+=1
                if basic.get('xxzrzt') in ('Y','D') and close and prior:stats['special_reference_count']+=1
        normalized.append([day,symbol,text(close),text(prior),text(volume),text(turn),status,qualification])
    # 原接收时间必须在该观察日闭市以后；它不是历史公布时间。
    for record in capture.input_records:
        if 'retrieved_at' in record:
            _need(_clock(record['retrieved_at']) >= closed, 'ashare_source_clock')
    result = stock_day([*FIELDS,'qualification'], normalized, members, day, scope='ashare', check=fetch.budget.remaining)
    result.update(stats,missing_quote_count=result['missing_stock_count'],
        known_market_count=len(members)-len(unverified))
    return {**{key: [row] for key, row in rows_for_metrics(result, ASHARE_METRICS).items()},
            UNIVERSE: [universe_row(day, members, manifest['universe']['sha256'])]}
