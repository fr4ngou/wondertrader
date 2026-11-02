"""完整冻结版本准入；校验后只有目录事务能够切换current。"""

from datetime import datetime, timezone
from time import monotonic
from pydantic import ValidationError

from .contracts import ObservationError, SnapshotManifest
from .metadata import validate_fields, field_contract
from .query import ObservationReader, validate_rows
from .storage import digest, encode, valid_sha
from .stock_partitions import validate_stock_partitions

VALIDATION_CONTRACT = 'observation-manifest-validation/1'  # 领域规则变化时升级；既有原全量current继承版本1资格。


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


def _references(manifest):
    """完整准入与前代复用从同一登记结构枚举引用及长度合同。"""
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
    return hashes,sizes


def _previous_validation(reader, previous_snapshot):
    """只信同根目录当前已提交版本；最终提交仍由原CAS重核身份。"""
    if previous_snapshot is None:return None
    if reader.repository.root != reader.objects.root:
        raise ObservationError('invalid_validation_reuse','验证复用需要同一目录与内容仓',422)
    if reader.repository.current()!=previous_snapshot:
        raise ObservationError('publication_conflict','当前观察版本已变化，本次验证复用已停止',409)
    previous=reader.repository.get(previous_snapshot)
    # 既有current由原全量准入发布；未知后继合同回到全量路径。
    if previous.get('validation_contract',VALIDATION_CONTRACT)!=VALIDATION_CONTRACT:return None
    return previous


def _same_metric_contract(item, previous):
    """数据摘要、行数、顺序口径和完整字段合同相同才继承领域准入。"""
    if not previous or item['parser_version']!='observation-admission/2':return False
    if any(item[key]!=previous.get(key) for key in ('partition','parser_version','rows')):return False
    current,old=item['definition'],previous['definition']
    if current.get('axis_type')!=old.get('axis_type'):return False
    try:return field_contract(current)==field_contract(old)
    except ObservationError:return False


def validate_manifest(reader, manifest, deadline, *, previous_snapshot=None):
    """默认全量；采集只复用同根当前已验且内容/字段合同未变的前代引用。

    首次导入、恢复及显式verify不传previous_snapshot，继续完整读验。
    内容查询仍逐次核SHA；此处复用发布资格，最终事务CAS保持原边界。
    """
    check_deadline(deadline)
    try:
        SnapshotManifest.model_validate(manifest, strict=True)
    except (ValidationError, ValueError, TypeError):
        raise ObservationError('invalid_manifest', '观察快照结构、登记资料或身份无效', 422) from None
    previous=_previous_validation(reader,previous_snapshot)
    hashes,sizes=_references(manifest)
    reusable=set()
    if previous is not None:
        old_hashes,old_sizes=_references(previous)
        # 新长度声明也属于合同：与前代已验长度不一致时重新读取并核对。
        reusable={sha for sha in hashes & old_hashes if sha not in sizes or sizes[sha]==old_sizes.get(sha)}
    objects = _ValidationObjects(reader.objects, sizes, deadline)
    # 领域校验读取的正文已经核过摘要和长度；其余对象随后逐一核验。
    # 独立reader保证调用方历史查询缓存不能充当本次对象核验资格。
    checked_reader = ObservationReader(reader.repository, objects)
    count = 0;reused_metrics=[]
    for key, item in manifest['datasets'].items():
        check_deadline(deadline)
        definition = item['definition']
        if key != definition['id']:
            raise ObservationError('definition_mismatch', '观察指标身份与目录不符', 422)
        if previous is not None and _same_metric_contract(item,previous['datasets'].get(key)):
            count+=item['rows'];reused_metrics.append(key);continue
        rows = checked_reader.rows(item['partition'])
        validate_rows(rows, tenor=definition.get('axis_type') == 'tenor')
        if item.get('parser_version') == 'observation-admission/2':
            validate_fields(definition, rows)
        if item.get('rows', len(rows)) != len(rows):
            raise ObservationError('row_count_mismatch', '观察行数与目录不符', 503)
        count += len(rows)
    standard = validate_stock_partitions(objects, manifest.get('stock_pb_partitions'), manifest.get('assets', {}), deadline,
        validated_assets=previous['assets'] if previous is not None else None)
    for sha in sorted(hashes):
        if sha not in objects.lengths and sha not in reusable:
            objects.get(sha)
    check_deadline(deadline)
    result=dict(datasets=len(manifest['datasets']), rows=count, verified_objects=len(hashes), **standard)
    if previous is not None:
        reused=sorted(reusable-set(objects.lengths))
        result.update(validation_contract=VALIDATION_CONTRACT,  # 本次领域校验规则版本；未知前代版本不继承。
            previous_snapshot=previous_snapshot,  # 同根current的已验前代身份；原提交CAS再次核对。
            read_verified_objects=len(objects.lengths),  # 本次实际读取并核摘要/长度的内容对象数。
            reused_objects=len(reused),  # 前代登记引用、长度合同均保持的免重复读取对象数。
            reused_object_set_sha256=digest(encode(reused)),  # 按SHA排序的精确复用集合摘要，可由前后manifest及本规则重算。
            reused_metric_ids=reused_metrics)  # 数据/行数/顺序及字段合同完全相同的指标ID。
    return result


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
