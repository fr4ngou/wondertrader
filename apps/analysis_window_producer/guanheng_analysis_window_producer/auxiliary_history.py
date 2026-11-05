"""核定官方历史事实快照；只补完整事实键缺口，原公式与生效仍归唯一辅助模块。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from typing import TypedDict

from guanheng_strategy_v1.auxiliary import AuxiliaryPublication, _validate

MAX_BYTES = 32 * 1024 * 1024
MAX_PUBLICATIONS = 65536
SCHEMA = 'guanheng.auxiliary-history-publications.v1'
FIELDS = {'schema', 'qualification', 'historical_first_available', 'publications',
          'source_delivery_sha256', 'generated_at'}
PUBLICATION_FIELDS = {'kind', 'statistic_date', 'value', 'available_at', 'received_at',
                      'source_sha256', 'symbol'}


class SnapshotReference(TypedDict):
    """部署者核定的不可变官方快照引用，进入原AWP配置身份。"""
    path: str  # 普通本地文件绝对路径，读取完整同一代字节。
    sha256: str  # 完整快照字节SHA256；换代需新配置及正常交接。


class HistoryCoverage(TypedDict):
    """历史补齐与当前持续来源分列，所有数量为事实数，均不表示已生效行情行。"""
    snapshot_sha256: str  # 本轮核定完整快照字节摘要。
    source_delivery_sha256: str  # 导出所依赖的历史来源交付摘要。
    generated_at: str  # 快照实际导出时刻，带时区。
    snapshot_publications: int  # 快照全部已核事实数量。
    applicable_publications: int  # 当前实际窗口日期及证券适用的快照事实数量。
    current_publications: int  # 当前来源已形成的完整事实数量，保持优先。
    imported_publications: int  # 实际填入的当前完整事实键缺口数量。
    qualification: str  # 固定official_observed，不接研究资格。
    historical_first_available: str  # 固定unknown，历史首次可知保持未知。
    continuous_source_updated: bool  # 固定False，历史快照不授持续来源更新资格。


class HistoryFailure(TypedDict):
    """快照失败的公开诊断，保留稳定原因，不回显原文或文件异常正文。"""
    type: str  # 原异常类别，区分校验与读取不可用。
    reason: str  # 固定校验原因码；读取异常统一history_snapshot_unavailable。


def history_failure(error):
    """沿唯一快照边界收敛固定原因，供原AWP状态和日志消费。"""
    reason = (str(error) if type(error) is ValueError
              and str(error).startswith('auxiliary_history_snapshot_') else 'history_snapshot_unavailable')
    return HistoryFailure(type=type(error).__name__, reason=reason)


@dataclass(frozen=True, slots=True)
class HistorySnapshot:
    """只读核定事实；当前来源覆盖情况与实际生效资格由后续合并另算。"""
    reference: SnapshotReference  # 核定路径与完整字节摘要，拒绝研究资格。
    publications: tuple[AuxiliaryPublication, ...]  # 原七字段事实，实际时钟保持，最多65536项。
    source_delivery_sha256: str  # 已核历史来源交付材料的完整字节摘要。
    generated_at: str  # 实际导出时刻，带时区；不是历史统计日或生效时间。


def _hash(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def snapshot_reference(value):
    """只规范配置引用；路径和摘要共同进入Owner身份，读取不改来源文件。"""
    if (type(value) is not dict or set(value) != {'path', 'sha256'}
            or type(value['path']) is not str or not value['path']
            or not Path(value['path']).is_absolute() or not _hash(value['sha256'])):
        raise ValueError('auxiliary_history_snapshot_reference')
    return SnapshotReference(path=os.path.normcase(str(Path(value['path']).resolve(strict=True))),
                             sha256=value['sha256'])


def _object(pairs):
    value = {}
    for name, item in pairs:
        if name in value:
            raise ValueError('auxiliary_history_snapshot_duplicate_field')
        value[name] = item
    return value


def _time(value):
    if type(value) is not str or not 1 <= len(value) <= 64:
        raise ValueError('auxiliary_history_snapshot_time')
    result = datetime.fromisoformat(value)
    if result.utcoffset() is None:
        raise ValueError('auxiliary_history_snapshot_time')
    return result


def _nonfinite(value):
    raise ValueError('auxiliary_history_snapshot_number')


def load_history_snapshot(reference):
    """有界核完整字节及严格协议；研究、未来时钟、重复事实和字段漂移均拒绝。

    调用者独占AWP线程；每轮读取固定摘要，任何失败保留原成功发布文件。
    """
    reference = snapshot_reference(reference)
    from guanheng_wt_runtime.managed_local_process import _open_read
    with _open_read(Path(reference['path'])) as stream:
        before = os.fstat(stream.fileno())
        if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
                or getattr(before, 'st_file_attributes', 0) & 0x400
                or not 0 < before.st_size <= MAX_BYTES):
            raise ValueError('auxiliary_history_snapshot_file')
        raw = stream.read(MAX_BYTES + 1)
        after = os.fstat(stream.fileno())
        if (len(raw) != before.st_size or (before.st_size, before.st_mtime_ns) !=
                (after.st_size, after.st_mtime_ns) or hashlib.sha256(raw).hexdigest() != reference['sha256']):
            raise ValueError('auxiliary_history_snapshot_identity')
    try:
        value = json.loads(raw, object_pairs_hook=_object, parse_constant=_nonfinite)
        if (type(value) is not dict or set(value) != FIELDS or value['schema'] != SCHEMA
                or value['qualification'] != 'official_observed'
                or value['historical_first_available'] != 'unknown'
                or not _hash(value['source_delivery_sha256'])
                or type(value['publications']) is not list
                or not 0 < len(value['publications']) <= MAX_PUBLICATIONS):
            raise ValueError('auxiliary_history_snapshot_protocol')
        generated = _time(value['generated_at'])
        if generated > datetime.now(timezone.utc):
            raise ValueError('auxiliary_history_snapshot_time')
        publications = []
        for item in value['publications']:
            if (type(item) is not dict or set(item) != PUBLICATION_FIELDS
                    or item['available_at'] is not None
                    or type(item['statistic_date']) is not str or len(item['statistic_date']) != 10
                    or (item['kind'] == 'shares' and (type(item['symbol']) is not str
                        or re.fullmatch(r'[0-9]{6}\.(?:SH|SZ)', item['symbol']) is None))):
                raise ValueError('auxiliary_history_snapshot_publication')
            day = date.fromisoformat(item['statistic_date'])
            received = _time(item['received_at'])
            if str(day) != item['statistic_date'] or received > generated:
                raise ValueError('auxiliary_history_snapshot_time')
            publications.append(AuxiliaryPublication(item['kind'], day, item['value'], None,
                received, item['source_sha256'], item['symbol']))
        publications = tuple(publications)
        _validate(publications, {p.symbol for p in publications if p.kind == 'shares'})
        return HistorySnapshot(reference, publications, value['source_delivery_sha256'], value['generated_at'])
    except ValueError as error:
        if str(error).startswith('auxiliary_history_snapshot_'):
            raise
        raise ValueError('auxiliary_history_snapshot_protocol') from error
    except (TypeError, KeyError, OverflowError, RecursionError, UnicodeError) as error:
        raise ValueError('auxiliary_history_snapshot_protocol') from error


def fill_history(current, snapshot, *, days, symbols):
    """按完整(kind,symbol,date)填缺；当前总额/份额及修订优先，快照不拆拼沪深分量。"""
    current = tuple(current)
    _validate(current, set(symbols))
    selected = {(p.kind, p.symbol, p.statistic_date): p for p in current}
    added = 0
    applicable = 0
    for item in snapshot.publications:
        if item.statistic_date not in days or item.kind == 'shares' and item.symbol not in symbols:
            continue
        applicable += 1
        key = (item.kind, item.symbol, item.statistic_date)
        if key not in selected:
            selected[key] = item
            added += 1
    return tuple(selected.values()), HistoryCoverage(snapshot_sha256=snapshot.reference['sha256'],
        source_delivery_sha256=snapshot.source_delivery_sha256, generated_at=snapshot.generated_at,
        snapshot_publications=len(snapshot.publications), applicable_publications=applicable,
        current_publications=len(current), imported_publications=added,
        qualification='official_observed', historical_first_available='unknown',
        continuous_source_updated=False)
