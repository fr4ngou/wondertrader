"""当前观察快照的直接输入目录；完整历史资产归其原不可变快照持有。"""

from .contracts import USAGE
from .metadata import asset_contract
from .storage import digest, encode


# 这些登记随当前数据索引更新；固定导入资料继续保留，旧分区版本归原快照。
_DYNAMIC_GROUPS = frozenset(('standard.metric', 'standard.source-table',
    'standard.capture-manifest', 'source.capture', 'standard.snapshot-input', 'standard.stock-pb'))


def references(manifest):
    """发布校验和目录收敛共同枚举完整直接引用及已声明的字节数。"""
    hashes = {item['sha256'] for item in manifest.get('assets', {}).values()}
    hashes.update(item['partition'] for item in manifest['datasets'].values())
    for item in manifest['datasets'].values():
        hashes.update(item['parents'])
    hashes.update(manifest.get('source_tables', {}).values())
    for parents in manifest.get('source_table_parents', {}).values():
        hashes.update(parents)
    hashes.update(manifest[key] for key in ('migration_aliases', 'source_payload') if manifest.get(key))
    hashes.update(item['object_sha256'] for item in manifest.get('references', {}).values() if item.get('object_sha256'))
    for part in (manifest.get('stock_pb_partitions') or {}).get('partitions', {}).values():
        hashes.add(part['sha256'])
        hashes.update(part.get('parent_assets', []))
    sizes = {}
    for item in manifest.get('assets', {}).values():
        hashes.update(item.get('parent_assets', []))
        sizes.setdefault(item['sha256'], set()).add(item.get('byte_size', item.get('bytes')))
    return hashes, sizes


def compact_assets(objects, manifest, previous, previous_snapshot, *, active_asset_ids=()):
    """保留本轮活动目录、固定资料及全部直接输入，旧元数据沿原快照查阅。

    只改变候选目录，不删除内容对象或历史快照。当前直接输入缺少资产登记时，
    保存指向前代快照的叶子登记；历史递归关系由前代持有，避免每轮展开历史图。
    """
    old_assets = previous.get('assets', {})
    assets = manifest['assets']
    before = len(assets)
    current = set()
    for key, item in manifest['datasets'].items():
        current.add(digest(encode(dict(dataset=key, sha256=item['partition'],
            parents=sorted(set(item['parents']) - {item['partition']})))))
    for key, sha in manifest.get('source_tables', {}).items():
        current.add(digest(encode(dict(dataset=key, sha256=sha,
            parents=sorted(set(manifest.get('source_table_parents', {}).get(key, [])) - {sha})))))
    for key, part in (manifest.get('stock_pb_partitions') or {}).get('partitions', {}).items():
        current.add(digest(encode(dict(dataset=key, sha256=part['sha256']))))
    active = current | set(active_asset_ids)
    retained = {key: item for key, item in assets.items()
        if item.get('group') not in _DYNAMIC_GROUPS or key in active}
    for key in current:
        if key in retained:
            # 分区正文可能未变；显式前代快照仍保留原成功采集及旧谱系的查阅入口。
            retained[key]['previous_snapshot'] = previous_snapshot
    manifest['assets'] = retained
    required, _ = references(manifest)
    represented = {item['sha256'] for item in retained.values()}
    old_by_hash = {item['sha256']: item for item in old_assets.values()}
    for sha in sorted(required - represented):
        old = old_by_hash.get(sha)
        size = old.get('byte_size', old.get('bytes')) if old else len(objects.get(sha))
        identity = digest(encode(dict(sha256=sha, snapshot=previous_snapshot)))
        retained[identity] = asset_contract(dict(
            asset_id=identity,  # 本次叶子登记身份，由实际内容及前代快照确定。
            sha256=sha,  # 原内容摘要；正文保持原字节。
            bytes=size,  # 原声明字节数；完整发布校验仍核实际内容长度。
            group='standard.snapshot-input',  # 当前直接输入，其历史解释归前代快照。
            source_ref='snapshot:' + previous_snapshot,  # 可按原snapshot参数查阅来源登记。
            previous_snapshot=previous_snapshot,  # 原不可变快照身份；不复制或改写历史元数据。
            parent_assets=[],  # 在快照边界停止展开历史图，当前直接输入仍全部登记和校验。
            qualification='prior_snapshot_input',  # 仅声明前代输入，保持首次可知时间未知。
            usage=USAGE))  # 只读研究用途，保持交易资格关闭。
    manifest['asset_index_policy'] = 'current-input-closure/1'  # 当前目录按直接输入闭包组织。
    return dict(previous_assets=before, current_assets=len(retained),
        previous_snapshot=previous_snapshot)
