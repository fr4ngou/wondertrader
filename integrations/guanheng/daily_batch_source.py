"""闭合日日线批读的通信代接续；原SDK继续拥有请求、结果和消费确认。"""
from datetime import datetime
import hashlib
import os
from pathlib import Path
import time
from uuid import uuid4

from guanheng_qmt_shm.analysis_batch_source import BatchAnalysisSource
from guanheng_qmt_shm.read_retention_client import RetainedReadClient, RetainedReadBindingChanged

from ..guanheng_market_client import strict_json
from .daily_gap_update import _hpr_business_identity
from .market_generation import encode, read_fixed


def _validate_capture_metadata(metadata):
    """离线复用原SDK能力校验函数，核落盘metadata完整性，不访问来源或创建请求。"""
    from guanheng_qmt_shm import bound
    from guanheng_qmt_shm_agent.protocol import canonical, decode
    from guanheng_qmt_shm_agent.read_capabilities import validate_read_profile
    from guanheng_qmt_shm_agent.read_retention import retention
    limits = metadata['limits']
    if (type(limits) is not dict or set(limits) != {'max_request_bytes', 'max_result_bytes',
            'max_http_request_bytes', 'max_http_response_bytes'}
            or any(type(value) is not int for value in limits.values())
            or not 1 <= limits['max_request_bytes'] <= bound.MAX_REQUEST_BYTES
            or not 1024 <= limits['max_result_bytes'] <= 2097152
            or not 8192 <= limits['max_http_request_bytes'] <= 4194304
            or limits != bound.limits(max_frame=limits['max_http_request_bytes'],
                max_result_bytes=limits['max_result_bytes'], native_body_limit=limits['max_request_bytes'])):
        # 范围沿原Runtime/BoundJournal，字段关系沿原bound.limits，不引入新的来源额度。
        raise ValueError('daily capture source limits invalid')
    checked = bound.binding(metadata['binding'])
    raw = bound.unb64(metadata['read_profile_body_b64'], 4096)
    if (metadata['schema_version'] != bound.SCHEMA or metadata['order_ready'] is not False
            or bound.digest(canonical(checked)) != metadata['binding_sha256']
            or bound.digest(raw) != metadata['read_profile_body_sha256']
            or bound.digest(raw) != checked['capability_sha256']):
        raise ValueError('daily capture source metadata invalid')
    profile = validate_read_profile(decode(raw), max_result_bytes=metadata['limits']['max_result_bytes'])
    retention(profile.get('read_retention'))
    if metadata['profile'] != profile:
        raise ValueError('daily capture source profile differs')


def capture_source_binding(capture, batches):
    """验证已落盘批次的同一业务来源，返回原capture的anchor摘要。

    Host会话可跨代；每个批次仍由Native谱系保留实际binding和原slot摘要。
    快照中的单一摘要表示原capture anchor，不替代逐批来源记录。
    """
    capture = Path(capture)
    anchor = strict_json(read_fixed(capture / 'BINDING.json', maximum=1048576))
    _validate_capture_metadata(anchor)
    bindings = {hashlib.sha256(encode(batch['binding'])).hexdigest(): batch['binding'] for batch in batches}
    if not bindings:
        raise ValueError('daily capture source bindings missing')
    anchor_digest = hashlib.sha256(encode(anchor['binding'])).hexdigest()
    if anchor['binding_sha256'] != anchor_digest:
        raise ValueError('daily capture anchor digest differs')
    for digest, binding in bindings.items():
        metadata = anchor if digest == anchor_digest else strict_json(
            read_fixed(capture / 'read-generations' / (digest + '.json'), maximum=1048576))
        if metadata is not anchor:
            _validate_capture_metadata(metadata)
        if (metadata['binding'] != binding or metadata['binding_sha256'] != digest
                or _hpr_business_identity(metadata) != _hpr_business_identity(anchor)):
            raise ValueError('daily capture business source differs')
    return anchor_digest


def _capture_slot_metadata(slot, original, anchor):
    """原槽和跳过的中断槽共用来源准入，缺原代记录或业务身份变化明确失败。"""
    binding = original['binding']
    if binding == anchor['binding']:
        selected = anchor
    else:
        digest = hashlib.sha256(encode(binding)).hexdigest()
        selected = strict_json(read_fixed(slot.parent.parent/'read-generations'/(digest+'.json'), maximum=1048576))
    if (selected['binding'] != binding or selected['profile'] != original['profile']
            or selected['limits'] != original['limits']):
        raise ValueError('daily batch original slot generation differs')
    if _hpr_business_identity(selected) != _hpr_business_identity(anchor):
        raise RetainedReadBindingChanged('daily_batch_business_identity_changed')
    return selected


class _DailyBatchClient(RetainedReadClient):
    """只为同一业务来源选择通信代；原槽的UUID、票据和截止始终保持。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._capture_context = None  # 本调用线程的新槽准入上下文(anchor, generation目录)；SDK返回时释放。

    def _binding(self, deadline, *, require_retention=True):
        metadata = super()._binding(deadline, require_retention=require_retention)
        if self._capture_context is not None:
            anchor, generations = self._capture_context
            if _hpr_business_identity(metadata) != _hpr_business_identity(anchor):
                raise RetainedReadBindingChanged('daily_batch_business_identity_changed')
            # 核原SDK实际交给plan的完整metadata，避免预检与新槽准入之间换代。
            from guanheng_qmt_shm.market_daily_preparation import _original
            generations.mkdir(exist_ok=True)
            digest = hashlib.sha256(encode(metadata['binding'])).hexdigest()
            _original(generations / (digest + '.json'), metadata)
        return metadata

    def read(self, operation, arguments, slot, *, deadline, expected_binding=None, **kwargs):
        slot = Path(slot)
        anchor = strict_json(read_fixed(slot.parent.parent / 'BINDING.json', maximum=1048576))
        if operation != 'market.market_data' or anchor['binding'] != expected_binding:
            raise ValueError('daily batch original capture identity differs')
        generations = slot.parent.parent / 'read-generations'
        if slot.exists():
            original = strict_json(read_fixed(slot, maximum=16777216))
            selected = _capture_slot_metadata(slot, original, anchor)
            expected = selected['binding']
        else:
            expected = None  # 新槽的实际metadata由上面的SDK准入钩子统一认证、比较和保存。
        self._capture_context = (anchor, generations)
        try:
            # 已存在槽交原SDK续核原身份；未知结果不生成后继请求。
            return super().read(operation, arguments, slot, deadline=deadline,
                                expected_binding=expected, **kwargs)
        finally:
            self._capture_context = None


def seed_unaffected_readback_batches(directory, original, manifest, changed_symbols, *, check, partition=None,
                                     adjustments=('none','front_ratio')):
    """同次补数只重读受影响的批次；其余批次沿原本地只读回包及绑定。"""
    root, prior = Path(directory), Path(original)
    if (root/'manifest.json').exists():
        return
    root.mkdir(parents=True, exist_ok=True)
    binding = read_fixed(prior/'BINDING.json', maximum=1048576)
    anchor = root/'BINDING.json'
    if anchor.exists() and read_fixed(anchor, maximum=1048576) != binding:
        return  # 已开始的旧回读保留原绑定和所有原槽。
    def publish(path, body, *, source=None):
        if path.exists():
            return  # 恢复沿目标目录已存在的原身份。
        path.parent.mkdir(exist_ok=True)
        if source is not None and source.drive.upper() == path.drive.upper():
            try:
                os.link(source,path)  # 原已消费slot保持不可变；续核按另名读取。
                return
            except OSError:
                pass
        staged = path.with_name('.'+uuid4().hex+'.tmp')
        try:
            with staged.open('xb') as output:
                output.write(body)
                output.flush()
                os.fsync(output.fileno())
            os.replace(staged,path)
        finally:
            staged.unlink(missing_ok=True)
    publish(anchor,binding)
    if partition is None and (prior/'BATCHES.json').exists():
        partition = strict_json(read_fixed(prior/'BATCHES.json', maximum=1048576))
    batch_ids = {}
    if partition is not None:
        plan = encode(partition)
        layout = root/'BATCHES.json'
        publish(layout, plan)
        if read_fixed(layout, maximum=1048576) != plan:
            raise ValueError('daily capture partition changed')
        batch_ids = {tuple(group): index for index, group in enumerate(partition)}
    original_binding = strict_json(binding)['binding']
    for batch in manifest['batches']:
        check()
        group = tuple(batch['symbols'])
        adjustment=batch.get('adjustment',batch['batch_id'].split('-',1)[1])
        scoped_raw=adjustment=='none' and 'raw_ranges' in manifest.get('request',{})
        remap=partition is not None and not scoped_raw
        if (adjustment not in adjustments or not changed_symbols.isdisjoint(group)
                or (remap and group not in batch_ids)):
            continue
        relative = Path(batch['slot'])
        batch_id = '%04d-%s' % (batch_ids[group],adjustment) if remap else batch['batch_id']
        target = root/'slots'/(batch_id+'.json')
        if target.exists():
            continue
        # read_capture已核原slot路径；复制前再次核其摘要并保留原字节。
        body = read_fixed(prior/relative, maximum=16777216, identity=batch['sha256'])
        if batch['binding'] != original_binding:
            name = hashlib.sha256(encode(batch['binding'])).hexdigest()+'.json'
            generation = Path('read-generations')/name
            publish(root/generation,read_fixed(prior/generation, maximum=1048576))
        publish(target,body,source=prior/relative)


def seed_local_analysis_batches(root, request, candidates, read_after, *, check):
    """从同口径同日原件固定可用分片；新增或变动的证券沿原SDK补读。"""
    from guanheng_qmt_shm.analysis_batch_source import request_batches
    from .analysis_price_capture import load_price_capture
    from .daily_data_update import _descriptor, _load, _save

    checkpoint = root/'CACHE-REUSE.json'
    output = root/'cache'
    if checkpoint.exists():
        selection = _load(_descriptor(checkpoint))
    elif (output/'REQUEST.json').exists():
        return  # 已开始的计划保留原分片及原槽。
    else:
        needed = set(request['symbols'])
        keys = ('source_kind', 'start_date', 'end_date', 'max_rows')
        for candidate in filter(None, candidates):
            check()
            prior = Path(candidate['directory'])
            manifest = strict_json(read_fixed(prior/'manifest.json', maximum=16777216, identity=candidate['sha256']))
            if any(manifest['request'].get(key) != request[key] for key in keys):
                continue
            stale = {symbol for batch in manifest['batches'] for symbol in batch['symbols']
                     if symbol in read_after and datetime.fromisoformat(batch['requested_at']) < read_after[symbol]}
            groups = [batch['symbols'] for batch in manifest['batches'] if batch['adjustment'] == 'none'
                      and needed.issuperset(batch['symbols']) and stale.isdisjoint(batch['symbols'])]
            if not groups:
                continue
            remaining = sorted(needed.difference(symbol for group in groups for symbol in group))
            if remaining:
                metadata = strict_json(read_fixed(prior/'BINDING.json', maximum=1048576))
                scope = metadata['profile']['operation_profiles']['market.market_data']['limits']
                groups += request_batches(remaining, max_rows=request['max_rows'],
                    max_data_bytes=scope['max_data_bytes'], max_symbols=scope['max_symbols'])
            selection = dict(source=candidate,  # 原manifest目录与内容摘要，重启继续读取。
                             partition=groups,  # 新池的完整固定分片，按序对应原批次号。
                             stale=sorted(stale))  # HPR已更新、旧回包需重读的证券。
            _save(checkpoint, selection)
            break
        else:
            return
    source = selection['source']
    manifest = load_price_capture(source)
    seed_unaffected_readback_batches(output, source['directory'], manifest, set(selection['stale']),
                                     check=check, partition=selection['partition'])


class DailyBatchAnalysisSource(BatchAnalysisSource):
    """日线owner显式选择；批次分片、数值验证、manifest和SDK默认行为沿原实现。

    同一capture的来源路由、权限、profile、额度及业务参数保持一致，
    Host/运输代次允许变化。每个批次仍单独保存实际binding和原始结果。
    """

    def __init__(self, transport, *, lifetime_ms=30000):
        self.client = _DailyBatchClient(transport, lifetime_ms=lifetime_ms)  # 原SDK请求owner，随调用线程关闭transport。

    def _batches(self, directory, request, scope):
        layout = directory/'BATCHES.json'
        if not layout.exists():
            return super()._batches(directory, request, scope)
        batches = strict_json(read_fixed(layout, maximum=1048576))
        max_group_size = len(super()._batches(directory, request, scope)[0])
        if (type(batches) is not list or any(type(group) is not list or not 1 <= len(group) <= max_group_size
                for group in batches) or sorted(symbol for group in batches for symbol in group) != sorted(request['symbols'])):
            raise ValueError('daily capture partition invalid')
        return batches

    def _slot(self, directory, batch_id, arguments, deadline):
        """缓存纯查询的中断终态允许新观察；原结果及未决责任永不覆盖。"""
        from guanheng_qmt_shm.read_retention_client import inspect_saved_result, RetainedReadPending
        from guanheng_qmt_shm_agent.analysis_batch import POLICY
        anchor = strict_json(read_fixed(directory/'BINDING.json', maximum=1048576))
        revision = 0
        while True:
            if time.monotonic() >= deadline:
                raise RetainedReadPending('read_new_request_budget_exhausted')
            suffix = '' if revision == 0 else '.r%d' % revision
            slot = directory/'slots'/(batch_id + suffix + '.json')
            if not slot.exists():
                return slot
            original = strict_json(read_fixed(slot, maximum=16777216))
            request = original['request']
            if (request['operation_id'] != 'market.market_data' or request['arguments'] != arguments
                    or request['policy_id'] != POLICY):
                raise ValueError('daily batch original observation differs')
            _capture_slot_metadata(slot, original, anchor)
            reply = inspect_saved_result(original)  # 原SDK核请求/票据、完整响应及consumed，无网络或文件修改。
            if (reply is None or reply.get('ok') is not False
                    or reply.get('error_code') not in ('operation_interrupted', 'queue_timeout')):
                return slot  # 未决请求保持原身份；确认中断或在执行前排队超时才允许后继纯读取。
            revision += 1
