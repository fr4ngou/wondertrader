"""辅助来源原件与修订归档；日期指针原子提交，历史版本保持不可变。"""
from __future__ import annotations

from datetime import date, datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4
from typing import TypedDict

from .source import write_json

MAX_BODY_BYTES = 4 * 1024 * 1024
CAPTURE_SCHEMA = 'guanheng.official-auxiliary-capture.v1'
SOURCES = ('sse-shares', 'sse-turnover', 'szse-turnover', 'sse-margin', 'szse-margin')


class CaptureRecord(TypedDict):
    """日期指针及原件版本的纯值合同；旧种子缺新增字段时按旧布局读取。"""
    schema: str  # 回执协议版本，固定guanheng.official-auxiliary-capture.v1。
    source: str  # 已核来源种类，不含账户或认证信息。
    statistic_date: str  # 来源统计日，ISO日期；用于核原文和归档键。
    url: str  # 固定公开报表URL，包含统计日参数。
    received_at: str  # 本系统首次取得这个原文版本的真实带时区时刻。
    checked_at: str  # 最近一次成功重核同日来源的实际时刻，不刷新首次取得时间。
    effective_received_at: str  # 本次修订首次被观察的时刻；同内容重查保持原值。
    body_sha256: str  # 解压原文字节摘要，绑定日期、字段和来源单位。
    historical_first_available: str  # 历史首次发布时间未知，固定unknown。
    available_at: None  # 未取得历史发布时间依据，明确保持空值。
    values: str | dict[str, str]  # 规范十进制数；份额亿份，成交额/融资余额亿元。
    archive_layout: str  # 新归档为content-addressed-v1，旧种子未提供此字段。


def validate_key(source, day):
    """来源和日期是唯一归档键，同时限定路径及请求范围。"""
    if source not in SOURCES or type(day) is not str or date.fromisoformat(day).isoformat() != day:
        raise ValueError('auxiliary_source_key')


def aware_time(value):
    """核对实际时间为带时区ISO值，返回可比较的时间对象。"""
    parsed = datetime.fromisoformat(value)
    if parsed.utcoffset() is None:
        raise ValueError('auxiliary_source_clock')
    return parsed


def _archive_path(directory, day, record):
    return (directory / 'versions' / day / (record['body_sha256'] + '.json.gz')
            if record.get('archive_layout') == 'content-addressed-v1'
            else directory / (day + '.json.gz'))


def capture_signature(root, source, day, record):
    """缓存同时绑定日期指针和原文元数据；任何一侧变化重新核原文字节。"""
    directory = Path(root) / source
    return tuple((path.stat().st_mtime_ns, path.stat().st_size)
                 for path in (directory / (day + '.json'), _archive_path(directory, day, record)))


def read_capture(root, source, day, parser):
    """读取已提交版本并核原文；兼容既有只读种子，缺少回执表示尚未取得。"""
    validate_key(source, day)
    directory = Path(root) / source
    receipt = directory / (day + '.json')
    if not receipt.exists():
        return None
    if receipt.stat().st_size > 1024 * 1024:
        raise ValueError('auxiliary_receipt_capacity')
    record = json.loads(receipt.read_bytes())
    if (record.get('schema') != CAPTURE_SCHEMA or record.get('source') != source
            or record.get('statistic_date') != day):
        raise ValueError('auxiliary_cache_identity')
    digest = record.get('body_sha256', '')
    if len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
        raise ValueError('auxiliary_cache_identity')
    # 版本路径由已核日期及摘要构造；回执中的任意路径不进入文件系统。
    archive = _archive_path(directory, day, record)
    with gzip.open(archive, 'rb') as stream:
        body = stream.read(MAX_BODY_BYTES + 1)
    if len(body) > MAX_BODY_BYTES or hashlib.sha256(body).hexdigest() != digest:
        raise ValueError('auxiliary_cache_identity')
    symbols = set(record['values']) if source == 'sse-shares' else set()
    if parser(source, day, body, symbols) != record['values']:
        raise ValueError('auxiliary_cache_values')
    received = aware_time(record['received_at'])
    effective = aware_time(record.get('effective_received_at', record['received_at']))
    if not received <= effective <= datetime.now(timezone.utc):
        raise ValueError('auxiliary_source_clock')
    return record


def commit_capture(root, source, day, body, values, received, previous=None, *, url):
    """先归档原文和版本回执，再更新日期指针；相同原文保留首次实际取得时间。"""
    validate_key(source, day)
    directory = Path(root) / source
    digest = hashlib.sha256(body).hexdigest()
    versions = directory / 'versions' / day
    versions.mkdir(parents=True, exist_ok=True)
    archive = versions / (digest + '.json.gz')
    if archive.exists():
        with gzip.open(archive, 'rb') as stream:
            if stream.read(MAX_BODY_BYTES + 1) != body:
                raise ValueError('auxiliary_archive_conflict')
    else:
        # 内容和指针均完整换名，中断不会留下同名的半份压缩原文。
        temporary = versions / (digest + '.' + uuid4().hex + '.tmp')
        try:
            with temporary.open('xb') as stream:
                stream.write(gzip.compress(body, mtime=0))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, archive)
        finally:
            temporary.unlink(missing_ok=True)
    first_received = (previous['received_at'] if previous is not None
                      and previous['body_sha256'] == digest else received)
    effective = (previous.get('effective_received_at', previous['received_at'])
                 if previous is not None and previous['body_sha256'] == digest else received)
    record = CaptureRecord(schema=CAPTURE_SCHEMA, source=source, statistic_date=day, url=url,
                  received_at=first_received, checked_at=received, body_sha256=digest,
                  effective_received_at=effective,
                  historical_first_available='unknown', available_at=None, values=values,
                  archive_layout='content-addressed-v1')
    version_receipt = versions / (digest + '.json')
    if version_receipt.exists():
        version = json.loads(version_receipt.read_bytes())
        # A→B→A修订仍回到已取得版本，不能把原版本的首次取得时间改为今晚。
        record['received_at'] = version['received_at']
    else:
        write_json(version_receipt, record)
    write_json(directory / (day + '.json'), record)
    return record
