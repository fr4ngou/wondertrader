"""完整冻结版本准入；校验后只有目录事务能够切换current。"""

from datetime import datetime, timezone
from time import monotonic
from pydantic import ValidationError

from .contracts import ObservationError, SnapshotManifest
from .metadata import validate_fields
from .query import ObservationReader, validate_rows
from .storage import digest, encode, valid_sha
from .stock_partitions import validate_stock_partitions


def check_deadline(deadline):
    if monotonic() >= deadline:
        raise ObservationError('observation_timeout', '观察读取超过本次时间，请重新读取', 503)


class _ValidationObjects:
    """单次准入复用本次已核摘要的长度；正文随调用释放，资格不跨调用保存。"""
    def __init__(self, objects, sizes, deadline):
        self.objects, self.sizes, self.deadline = objects, sizes, deadline
        self.lengths = {}

    def get(self, sha):
        check_deadline(self.deadline)
        body = self.objects.get(sha)
        check_deadline(self.deadline)
        if self.sizes.get(sha, {len(body)}) != {len(body)}:
            raise ObservationError('asset_size_mismatch', '观察资产大小与目录不符', 503)
        self.lengths[sha] = len(body)
        return body


def validate_manifest(reader, manifest, deadline):
    check_deadline(deadline)
    try:
        SnapshotManifest.model_validate(manifest, strict=True)
    except (ValidationError, ValueError, TypeError):
        raise ObservationError('invalid_manifest', '观察快照结构、登记资料或身份无效', 422) from None
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
    objects = _ValidationObjects(reader.objects, sizes, deadline)
    # 领域校验读取的正文已经核过摘要和长度；其余对象随后逐一核验。
    # 独立reader保证调用方历史查询缓存不能充当本次对象核验资格。
    checked_reader = ObservationReader(reader.repository, objects)
    count = 0
    for key, item in manifest['datasets'].items():
        check_deadline(deadline)
        definition = item['definition']
        if key != definition['id']:
            raise ObservationError('definition_mismatch', '观察指标身份与目录不符', 422)
        rows = checked_reader.rows(item['partition'])
        validate_rows(rows, tenor=definition.get('axis_type') == 'tenor')
        if item.get('parser_version') == 'observation-admission/2':
            validate_fields(definition, rows)
        if item.get('rows', len(rows)) != len(rows):
            raise ObservationError('row_count_mismatch', '观察行数与目录不符', 503)
        count += len(rows)
    standard = validate_stock_partitions(objects, manifest.get('stock_pb_partitions'), manifest.get('assets', {}), deadline)
    for sha in sorted(hashes):
        if sha not in objects.lengths:
            objects.get(sha)
    check_deadline(deadline)
    return dict(datasets=len(manifest['datasets']), rows=count, verified_objects=len(hashes), **standard)


def adopt_snapshot(reader, manifest, snapshot_id, expected, deadline, *, restoring=False):
    """导入和恢复共用完整校验与一次CAS提交，receipt与current同时可见。"""
    valid_sha(snapshot_id)
    if digest(encode(manifest)) != snapshot_id:
        raise ObservationError('snapshot_identity_mismatch', '观察快照身份与指定版本不符', 409)
    if reader.repository.current() != expected:
        raise ObservationError('publication_conflict', '当前观察版本已变化，本次采用已停止', 409)
    try:
        checked = validate_manifest(reader, manifest, deadline)
    except (KeyError, TypeError, ValueError, AttributeError):
        raise ObservationError('invalid_manifest', '观察快照格式或登记内容无效', 422) from None
    receipt = dict(status='version_restored' if restoring else 'snapshot_imported',
                   completed_at=datetime.now(timezone.utc).isoformat(), previous_snapshot=expected,
                   current_snapshot=snapshot_id, **checked)
    check_deadline(deadline)
    reader.repository.publish(manifest, expected, receipt=receipt,deadline=deadline)
    return receipt
