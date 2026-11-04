"""原观察日历调用共享纯计算；来源采集及比较投影保持原接口。"""
from guanheng_market_client.exchange_calendar import official_calendar as _official_calendar, last_open_day as _last_open_day, CalendarFailure
from datetime import timedelta, timezone
from .storage import digest, encode
from .providers import SourceFailure


def closed_day_cutoff(now):
    """返回原日线输入15:30闭合窗口的北京时间日期上界（YYYY-MM-DD）。

    调用方提供有时区的实际时钟；这里只判断来源闭合窗口，开市日仍由
    对应日历核实，已过窗口也不授予来源价格完整或已发布资格。
    """
    if now.utcoffset() is None:
        raise ValueError('daily closed-day clock requires timezone')
    local = now.astimezone(timezone(timedelta(hours=8)))
    cutoff = local.date()
    if (local.hour, local.minute) < (15, 30):
        cutoff -= timedelta(days=1)
    return cutoff.isoformat()


def official_calendar(config, *, check=lambda: None):
    try:
        return _official_calendar(config, check=check)
    except CalendarFailure as error:
        raise SourceFailure(str(error)) from error


def last_open_day(config, end, *, check=lambda: None):
    try:
        return _last_open_day(config, end, check=check)
    except CalendarFailure as error:
        raise SourceFailure(str(error)) from error


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
