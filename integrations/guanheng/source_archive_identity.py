"""固定archive视图的只读身份与调用内已核行；不持久化缓存或拥有Source请求。"""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

# 全市场清单每证券包含多段来源。64 MiB 覆盖实测 7952 证券的 17.6 MB 清单，
# 并给最多 20000 个归档条目保留同量级的来源分段空间。
DAILY_ARCHIVE_MANIFEST_BYTES = 64 * 1024 * 1024


@dataclass(frozen=True)
class StaticArchiveIdentity:
    symbol: str  # 原WT证券身份；该owner实际首层命中的证券。
    adjustment: str  # 该静态DSB的none/front_ratio口径。
    path: str  # 已约束于清单目录内的原DSB绝对路径。
    sha256: str  # 原DSB完整字节摘要；使用前与原Helper仍重新核验。
    rows: int  # 原DSB完整行数，区别查询limit及本次新增条数。
    first: int  # 完整原档首交易日期YYYYMMDD，不授可知时刻。
    last: int  # 完整原档末交易日期YYYYMMDD。
    provenance_sha256: str  # 全部连续原来源分段规范JSON摘要，包含原单位和参考。
    archive_sha256: str  # 已由所属Reader准入的不可变清单原字节摘要。


@dataclass(frozen=True)
class PreloadedArchiveRows:
    identity: StaticArchiveIdentity  # 已Native核读的原文件/完整范围/来源身份。
    rows: dict  # 同线程本次调用独占的date→(原行,metadata)，复用期间只读，不持久化。
    rows_sha256: str  # 原六数值/日期规范摘要；原helper仍负责全部WTSBar核同。
    provenance: tuple  # 同一原entry的连续分段，保留原边界；调用内只读，不另造来源。


def archive_entry_identity(descriptor, entry):
    """从已准入清单的实际entry形成身份；选源优先级只由Reader owner决定。"""
    root=Path(descriptor['path']).parent.resolve(strict=True)
    path=(root/entry['path']).resolve(strict=True)
    if not path.is_relative_to(root):
        raise ValueError('static archive path escaped')
    basis=entry['provenance'][0]['metadata']['adjustment']
    raw=json.dumps(entry['provenance'],ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf8')
    return StaticArchiveIdentity(entry['symbol'],basis,str(path),entry['sha256'],entry['rows'],
        entry['first'],entry['last'],hashlib.sha256(raw).hexdigest(),descriptor['sha256'])
