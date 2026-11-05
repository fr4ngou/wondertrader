"""终端外采集沪深交易所辅助事实，按来源/日期保存可重用的原文。

本入口只读公开数据，不操作QMT、账户或策略；不推定历史首次发布时间。
实际采集时刻与来源统计日分别落盘，派生与使用资格由消费者明确声明。
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from decimal import Decimal
import gzip
import hashlib
import json
from pathlib import Path
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .source import write_json

MAX_RESPONSE = 4*1024*1024
SOURCES = ('sse-shares', 'sse-turnover', 'szse-turnover', 'sse-margin', 'szse-margin')


def source_request(source, day):
    """固定公开报表及日期参数；单位和结果日期在解析边界再次核对。"""
    if source.startswith('sse-'):
        origin = 'https://query.sse.com.cn'
        referer = 'https://www.sse.com.cn/'
        if source == 'sse-margin':
            path = '/marketdata/tradedata/queryMargin.do'
            params = dict(isPagination='true', beginDate=day.replace('-', ''), endDate=day.replace('-', ''))
        else:
            path = '/commonQuery.do'
            params = {'isPagination': 'true', 'pageHelp.pageSize': '10000', 'pageHelp.pageNo': '1'}
            if source == 'sse-shares':
                params.update(sqlId='COMMON_SSE_ZQPZ_ETFZL_XXPL_ETFGM_SEARCH_L', STAT_DATE=day)
            else:
                params.update(sqlId='COMMON_SSE_SJ_GPSJ_CJGK_MRGK_C', PRODUCT_CODE='01,02,03,11,17',
                              type='inParams', SEARCH_DATE=day)
    else:
        origin, path, referer = 'https://www.szse.cn', '/api/report/ShowReport/data', 'https://www.szse.cn/'
        params = dict(SHOWTYPE='JSON', TABKEY='tab1')
        if source == 'szse-turnover':
            params.update(CATALOGID='1803_sczm', txtQueryDate=day)
        elif source == 'szse-margin':
            params.update(CATALOGID='1837_xxpl', txtDate=day)
        else:
            raise ValueError('unknown_auxiliary_source')
    return origin+path+'?'+urlencode(params), referer


def positive(value):
    number = Decimal(str(value).replace(',', '').strip())
    if not number.is_finite() or number <= 0:
        raise ValueError('auxiliary_source_number')
    return number


def unique(rows):
    if len(rows) != 1:
        raise ValueError('auxiliary_source_unique_row')
    return rows[0]


def parse_source(source, day, body, symbols):
    """返回来源规范值：份额亿份，成交额/融资余额亿元；不混用融资融券合计。"""
    value = json.loads(body)
    if source.startswith('sse-'):
        rows = value.get('result')
        if type(rows) is not list or not rows:
            raise ValueError('auxiliary_source_not_published')
        if source == 'sse-shares':
            found = {}
            for row in rows:
                symbol = str(row.get('SEC_CODE', ''))+'.SH'
                if symbol not in symbols:
                    continue
                if row.get('STAT_DATE') != day or symbol in found:
                    raise ValueError('auxiliary_source_date_or_duplicate')
                # 交易所规模表TOT_VOL为万份；保留十进制，转换成原策略亿份。
                found[symbol] = str(positive(row['TOT_VOL'])/Decimal(10000))
            if not found:
                raise ValueError('auxiliary_source_symbols_missing')
            return found
        if source == 'sse-turnover':
            row = unique([r for r in rows if str(r.get('PRODUCT_CODE')) == '17'])
            if row.get('TRADE_DATE') != day.replace('-', ''):
                raise ValueError('auxiliary_source_date')
            return str(positive(row['TRADE_AMT']))
        row = unique(rows)
        if row.get('opDate') != day.replace('-', ''):
            raise ValueError('auxiliary_source_date')
        return str(positive(row['rzye'])/Decimal(100000000))
    tab = unique([t for t in value if t.get('metadata', {}).get('tabkey') == 'tab1'])
    meta = tab['metadata']
    name = 'txtQueryDate' if source == 'szse-turnover' else 'txtDate'
    condition = unique([c for c in meta.get('conditions', []) if c.get('name') == name])
    if condition.get('defaultValue') != day:
        raise ValueError('auxiliary_source_date')
    field = 'cjje' if source == 'szse-turnover' else 'jrrzye'
    if '亿元' not in meta.get('cols', {}).get(field, ''):
        raise ValueError('auxiliary_source_unit')
    rows = tab['data']
    row = unique([r for r in rows if r.get('lbmc') == '股票']) if source == 'szse-turnover' else unique(rows)
    return str(positive(row[field]))


def capture(source, day, root, symbols, *, timeout=15):
    """每个日期/来源独立缓存；既有原文摘要核对后重用，失败保持可重试。"""
    directory = root/source
    directory.mkdir(exist_ok=True)
    receipt, archive = directory/(day+'.json'), directory/(day+'.json.gz')
    url, referer = source_request(source, day)
    if receipt.exists():
        record = json.loads(receipt.read_bytes())
        body = gzip.decompress(archive.read_bytes())
        if (record.get('url') != url or record.get('statistic_date') != day
                or hashlib.sha256(body).hexdigest() != record.get('body_sha256')):
            raise ValueError('auxiliary_cache_identity')
        record['values'] = parse_source(source, day, body, symbols)
        return record
    request = Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Referer': referer})
    with urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise ValueError('auxiliary_source_http')
        body = response.read(MAX_RESPONSE+1)
    if len(body) > MAX_RESPONSE:
        raise ValueError('auxiliary_source_response_capacity')
    received = datetime.now(timezone.utc).isoformat()
    values = parse_source(source, day, body, symbols)
    # 两个文件只有回执提交后才可消费；异常留下的同名原文由该单写者重试覆盖。
    archive.write_bytes(gzip.compress(body, mtime=0))
    record = dict(schema='guanheng.official-auxiliary-capture.v1', source=source, statistic_date=day,
                  url=url, received_at=received, body_sha256=hashlib.sha256(body).hexdigest(),
                  historical_first_available='unknown', values=values)
    write_json(receipt, record)
    return record


def capture_dates(days, symbols, root, *, workers=2):
    """有界并行的有限补齐；先处理近期日期，每个工作线程串行访问五类来源。"""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    if workers not in (1, 2, 3, 4) or len(days) > 4096:
        raise ValueError('auxiliary_capture_capacity')
    completed, failures = {}, {}

    def one(day):
        records, errors = {}, {}
        for source in SOURCES:
            try:
                records[source] = capture(source, day, root, symbols)
            except Exception as error:
                # 不输出服务器正文；精确来源及异常类别足以重试同一只读日期。
                errors[source] = dict(type=type(error).__name__, reason=str(error)[:160])
            time.sleep(.15)
        return day, records, errors

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(one, day) for day in sorted(set(days), reverse=True)]
        for future in as_completed(futures):
            day, records, errors = future.result()
            completed[day] = records
            if errors:
                failures[day] = errors
            # 仅日期/成功计数写进度，完整数据按独立日期保留，内存与磁盘均有输入上界。
            write_json(root/'PROGRESS.json', dict(schema='guanheng.auxiliary-capture-progress.v1',
                planned_days=len(days), processed_days=len(completed), complete_days=sum(len(v) == len(SOURCES) for v in completed.values()),
                failed_days=len(failures), last_day=day, updated_at=datetime.now(timezone.utc).isoformat(),
                finished=len(completed) == len(days)))
    write_json(root/'FAILURES.json', failures)
    return completed


def observed_publications(root, days, *, cache=None):
    """从已提交原文重建可用于后续决策的事实，使用本系统实际取得时刻。

    历史首次可知未知的记录不会回填历史available_at。一次补齐过去多年数据时，
    历史数值可作为分位计算前缀；策略生效仍在真实采集时刻之后。
    """
    from guanheng_strategy_v1.auxiliary import AuxiliaryPublication
    result = []
    root = Path(root)
    for day in sorted(set(days)):
        records = {}
        for source in SOURCES:
            path = root/source/(day+'.json')
            if not path.exists():
                continue
            archive = path.with_suffix('.json.gz')
            signature = tuple((p.stat().st_mtime_ns, p.stat().st_size) for p in (path, archive))
            cached = cache.get(str(path)) if cache is not None else None
            if cached is not None and cached[0] == signature:
                records[source] = cached[1]
                continue
            record = json.loads(path.read_bytes())
            body = gzip.decompress(archive.read_bytes())
            if (record.get('schema') != 'guanheng.official-auxiliary-capture.v1'
                    or record.get('source') != source or record.get('statistic_date') != day
                    or hashlib.sha256(body).hexdigest() != record.get('body_sha256')):
                raise ValueError('auxiliary_cache_identity')
            # 重新走唯一解析器，缓存中的规范值与原文必须一致。
            symbols = set(record['values']) if source == 'sse-shares' else set()
            if parse_source(source, day, body, symbols) != record['values']:
                raise ValueError('auxiliary_cache_values')
            records[source] = record
            if cache is not None:
                cache[str(path)] = (signature, record)
        statistic_date = date.fromisoformat(day)
        shares = records.get('sse-shares')
        if shares:
            received = datetime.fromisoformat(shares['received_at'])
            for symbol, number in shares['values'].items():
                result.append(AuxiliaryPublication('shares', statistic_date, float(number),
                    received, received, shares['body_sha256'], symbol))
        for kind in ('turnover', 'margin'):
            pair = [records.get(exchange+'-'+kind) for exchange in ('sse', 'szse')]
            if not all(pair):
                continue
            received = max(datetime.fromisoformat(r['received_at']) for r in pair)
            identity = hashlib.sha256(json.dumps([r['body_sha256'] for r in pair], separators=(',', ':')).encode()).hexdigest()
            total = sum(Decimal(r['values']) for r in pair)
            result.append(AuxiliaryPublication(kind, statistic_date, float(total), received, received, identity))
    if cache is not None:
        # 缓存属于该发布Owner，仅保留本次历史范围内的最多5*4096个原件摘要。
        active = {str(root/source/(day+'.json')) for day in days for source in SOURCES}
        for key in tuple(cache):
            if key not in active:
                del cache[key]
    return tuple(result)


def enrich_window(window, root, *, cache=None):
    """将已实际取得的辅助值合并到原值历史；前复权行情保持原Owner结果。"""
    from copy import deepcopy
    from guanheng_strategy_core.models import DailyObservation
    from guanheng_strategy_v1.auxiliary import merge_auxiliary
    rows = window['history']['observations']
    days = sorted({r['trade_date'] for r in rows})
    publications = observed_publications(root, days, cache=cache)

    def observation(raw):
        value = dict(raw)
        value['trade_date'] = date.fromisoformat(value['trade_date'])
        for key in ('market_available_at', 'auxiliary_available_at'):
            if value.get(key):
                value[key] = datetime.fromisoformat(value[key])
        for key in ('auxiliary_source_dates', 'evidence_refs'):
            if key in value:
                value[key] = tuple(date.fromisoformat(d) for d in value[key]) if key.endswith('dates') else tuple(value[key])
        return DailyObservation(**value)

    before = tuple(observation(row) for row in rows)
    after = merge_auxiliary(before, publications)
    names = ('shares_delta_yi', 'share_probability', 'turnover_percentile', 'margin_percentile',
             'auxiliary_available_at', 'auxiliary_source_dates', 'auxiliary_source_sha256', 'evidence_refs')
    updated = deepcopy(window)
    count = 0
    for original, merged, target in zip(before, after, updated['history']['observations']):
        if original == merged:
            continue
        count += 1
        for name in names:
            value = getattr(merged, name)
            if isinstance(value, datetime):
                value = value.isoformat()
            elif isinstance(value, tuple):
                value = [str(v) for v in value]
            target[name] = value
    report = dict(schema='guanheng.auxiliary-window-merge.v1', publications=len(publications), enriched_rows=count,
        availability_basis='actually-received', historical_first_available='unknown',
        first_received_at=min((p.received_at.isoformat() for p in publications), default=None))
    if count:
        identity = hashlib.sha256(json.dumps(updated['history'], sort_keys=True, separators=(',', ':'),
                                            allow_nan=False).encode()).hexdigest()
        updated['references'].append(dict(report, history_sha256=identity))
        updated['input_sha256'] = hashlib.sha256((window['input_sha256']+identity).encode()).hexdigest()
        updated['qualification'] = ('current-visible native price analysis; auxiliary facts actually received; '
                                    'historical first visibility unknown')
    # 报告在AWP状态中展示；原顶层窗口协议和市场来源SHA保持，纯核输入身份包含合并事实。
    return updated, report


def main():
    parser = argparse.ArgumentParser(description='只读采集沪深交易所策略辅助数据')
    parser.add_argument('--market-window', type=Path, required=True)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--recent-days', type=int)
    args = parser.parse_args()
    window = json.loads(args.market_window.read_bytes())
    rows = window['history']['observations']
    days = sorted({row['trade_date'] for row in rows})
    if args.recent_days is not None:
        if args.recent_days < 1:
            parser.error('recent-days需要正整数')
        days = days[-args.recent_days:]
    symbols = {row['symbol'] for row in rows if row['symbol'].endswith('.SH')}
    capture_dates(days, symbols, args.directory, workers=args.workers)


if __name__ == '__main__':
    main()
