"""WT日更的本地原价缺日准备，复用DAT解析与WT会话聚合。"""
from pathlib import Path
import time
from types import SimpleNamespace

from .analysis_price_capture import original_price_quality
from .daily_data_update import _descriptor, _load, _save
from .qmt_local_dat import CacheExportError, read_cache_dates
from .qmt_minute_daily import FIELDS, aggregate_native, select_sessions
from .qmt_minute_import import _Native
from ..guanheng_market_client.source_history import validate_source_metadata


def validate_local_dat_root(path):
    """本地缓存根由部署已有数据路径声明；这里只核固定绝对路径形状。"""
    if type(path) is not str or not Path(path).is_absolute() or '..' in Path(path).parts:
        raise ValueError('daily local QMT DAT root invalid')


def _read(cache_root, symbol, days, period, check):
    try:
        return read_cache_dates(cache_root, symbol, days, period=period, check=check)
    except (TimeoutError, InterruptedError):
        raise
    except (OSError, CacheExportError):
        return [], None  # 本地文件暂缺、未稳定或不合格，让原日线来源继续核实。


def _metadata(digest, method):
    return validate_source_metadata(dict(
        source=dict(provider='Qmt', instance_id='local-dat',
                    session_id='local-dat:'+digest[:32], generation=1),
        qualification='DevelopmentVerified', dataset_version=method, source_license='unknown',
        adjustment='none', factor_version='', minute_boundary='unknown', timezone='Asia/Shanghai',
        content_id=digest, value_semantics='source', timestamp_semantics='source_date',
        price_unit='unknown', volume_unit='unknown', amount_unit='unknown', period='1d'), period='1d')


def prepare_local_prices(cache_root, selection, output, helper, *, deadline, cancelled):
    """每证券固定六字段与DAT摘要；分钟只在原价仍缺时走WT原Helper。"""
    def check():
        if cancelled():
            raise InterruptedError('daily local prices stopped')
        if time.monotonic() >= deadline:
            raise TimeoutError('daily local prices deadline')

    validate_local_dat_root(cache_root)
    output.mkdir(exist_ok=False)
    native = None
    files = []
    try:
        for symbol, days in selection.items():
            check()
            if not days:
                continue
            daily, digest = _read(cache_root, symbol, days, '1d', check)
            rows = []
            for label, *fields in daily:
                bar = dict(zip(FIELDS, fields))
                if original_price_quality(bar) == 'qualified':
                    rows.append(dict(date=label.date().isoformat(), bar=bar))
            groups = [dict(metadata=_metadata(digest,'qmt.local-dat-day.v1'),rows=rows)] if rows else []
            missing = days - {row['date'] for row in rows}
            if missing:
                minutes, minute_digest = _read(cache_root, symbol, missing, '1m', check)
                decoded = [(label,dict(zip(FIELDS,fields))) for label,*fields in minutes]
                invalid = {label.date() for label,bar in decoded if original_price_quality(bar)!='qualified'}
                bars = [SimpleNamespace(occurred_at=label, **bar) for label,bar in decoded
                        if label.date() not in invalid]
                sessions, _ = select_sessions(bars, min(missing), max(missing))
                if sessions:
                    if native is None:
                        native = _Native(helper['path'], helper['sha256'])
                    # 同次准备仅保留最终日线；WT临时分钟输入属于该本地计算。
                    temporary = output/(symbol+'.dsb')
                    daily = aggregate_native(native, temporary, sessions)
                    temporary.unlink()
                    derived=[]
                    for item in daily:
                        day=item.pop('date')
                        if original_price_quality(item)=='qualified':
                            derived.append(dict(date=day,bar=item))
                    if derived:
                        groups.append(dict(metadata=_metadata(minute_digest,'qmt.local-dat-minute-day.v1'),rows=derived))
            if groups:
                path=output/(symbol+'.json')
                _save(path, dict(symbol=symbol, groups=groups))
                files.append(_descriptor(path))
        path=output/'catalog.json'
        _save(path,dict(schema='guanheng.daily-local-prices.v1',files=files))
        return _descriptor(path)
    finally:
        if native is not None:
            native.close()


def local_price_groups(descriptor, *, check):
    """以固定目录/逐证券SHA读回本地原价，准备和归档共用。"""
    catalog=_load(descriptor)
    if catalog['schema'] != 'guanheng.daily-local-prices.v1':
        raise ValueError('daily local prices catalog invalid')
    for entry in catalog['files']:
        check()
        item=_load(entry)
        for group in item['groups']:
            yield item['symbol'],group['metadata'],group['rows']
