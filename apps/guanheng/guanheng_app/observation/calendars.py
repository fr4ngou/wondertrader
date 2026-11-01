"""Versioned exchange calendars, separate from provider rows and legacy models."""
from datetime import date, timedelta
import hashlib
from .storage import digest, encode
from .providers import SourceFailure


def _configuration(config,check):
    check()
    start = date.fromisoformat(config['coverage_start'])
    end = date.fromisoformat(config['coverage_end'])
    through = date.fromisoformat(config['verified_through'])
    if not start <= through <= end:
        raise SourceFailure('official_calendar_coverage_invalid')
    closures = set(config['closed_dates'])
    if len(closures) != len(config['closed_dates']):
        raise SourceFailure('official_calendar_duplicate_closure')
    for day in closures:
        check()
        date.fromisoformat(day)
    return start,end,through,closures


def _days(start,end,check):
    day=start
    while day<=end:
        check();yield day
        if day==end:return
        day+=timedelta(days=1)


def _is_open(day,closures):
    return day.weekday()<5 and day.isoformat() not in closures


def _verify(config,start,through,closures,check):
    """保持原开放日JSON摘要，逐日送入哈希，不物化历史列表。"""
    identity=hashlib.sha256();identity.update(b'[');first=True
    for day in _days(start,through,check):
        if _is_open(day,closures):
            if not first:identity.update(b',')
            identity.update(encode(day.isoformat()));first=False
    identity.update(b']')
    if identity.hexdigest()!=config['verified_open_dates_sha256']:
        raise SourceFailure('official_calendar_verification_mismatch')


def last_open_day(config,end,*,check=lambda:None):
    """核同原开放日摘要后按原规则回看；原check约束迭代，内存与覆盖年数无关。"""
    start,last,through,closures=_configuration(config,check)
    day=date.fromisoformat(end)
    if not start<=day<=last:raise SourceFailure('official_calendar_outside_coverage')
    _verify(config,start,through,closures,check)
    while day>=start:
        check()
        if _is_open(day,closures):return day.isoformat()
        if day==start:break
        day-=timedelta(days=1)
    raise SourceFailure('official_calendar_outside_coverage')


def official_calendar(config,*,check=lambda:None):
    start,end,through,closures=_configuration(config,check)
    _verify(config,start,through,closures,check)
    rows=[dict(date=day.isoformat(),is_open=int(_is_open(day,closures))) for day in _days(start,end,check)]
    metadata = dict(id=config['id'], version=digest(encode(config)),
                    coverage_start=start.isoformat(), coverage_end=end.isoformat(),
                    verified_through=through.isoformat(), method=config['method'],
                    official_history_verified=True, evidence=config['evidence'])
    return rows, metadata


def comparison_calendars(tables, markets, config):
    """A configured official calendar fails closed outside its admitted coverage."""
    calendars = {}
    metadata = {}
    for market, symbol in (('cn', 'sh000001'), ('hk', 'hkHSCEI')):
        source = config.get('calendars', {}).get(market, {})
        if source.get('kind') == 'official-exchange-calendar/v1':
            rows, meta = official_calendar(source)
            start, end = source['coverage_start'], source['coverage_end']
            active = {r['date'] for r in rows if r['is_open']}
            observed = {d for d in markets[symbol] if d >= config['base_date']}
            if any(d < start or d > end for d in observed):
                raise SourceFailure('official_calendar_outside_coverage')
            latest = max(observed, default=config['base_date'])
            missing = {d for d in active if config['base_date'] <= d <= latest} - observed
            if missing:
                raise SourceFailure('official_calendar_price_days_missing')
            meta.update(excluded_provider_dates=sorted(observed-active),
                        observed_through=latest,
                        official_history_verified=latest <= source['verified_through'],
                        qualification=source['method'] if latest <= source['verified_through'] else 'official_annual_schedule_with_provider_days')
            calendars[market] = active
            metadata[market] = meta
        else:
            closed = set(config.get('closed_dates', {}).get(market, []))
            if market == 'cn':
                closed.update(r['date'] for r in tables.get('source.cn_calendar', []) if not r['is_open'])
            calendars[market] = set(markets[symbol]) - closed
            metadata[market] = dict(id=source.get('id', market+'.provider-days'),
                version=digest(encode(sorted(calendars[market]))), source=source,
                official_history_verified=False, qualification='provider_days_with_verified_closure_overrides')
    return calendars, metadata


def admit_calendars(objects, manifest, tables, config):
    """Raw originals must already be admitted; a missing original blocks publication."""
    from .admission import register_standard_asset
    from .query import parquet_bytes
    for market, source in config.get('calendars', {}).items():
        if source.get('kind') != 'official-exchange-calendar/v1':
            continue
        rows, _ = official_calendar(source)
        parents = []
        for record in source['evidence']:
            body = objects.get(record['sha256'])
            if len(body) != record['bytes']:
                raise SourceFailure('official_calendar_evidence_size_mismatch')
            parents.append(record['sha256'])
            register_standard_asset(objects, manifest, source['id']+'.original', record['sha256'], [],
                'source.official-calendar', provider=record['url'], retrieved_at=record.get('fetched_at'),
                media_type=record.get('content_type'))
        key = 'source.'+market+'_official_calendar'
        sha = objects.put(parquet_bytes(rows), kind='standard')
        tables[key] = rows
        manifest.setdefault('source_tables', {})[key] = sha
        manifest.setdefault('source_table_parents', {})[key] = sorted(set(parents))
