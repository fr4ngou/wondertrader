"""批量分析来源的持久消费方；原运输注入，原批次身份始终保留。"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from .read_retention_client import RetainedReadClient, _save
from guanheng_qmt_shm_agent.protocol import canonical
from guanheng_qmt_shm_agent.analysis_batch import POLICY, RESULT_SCHEMA

SCHEMA = 'guanheng.observation-qas-batch-capture.v1'


def request_batches(symbols, *, max_rows, max_data_bytes, max_symbols):
    """按显式行额度和浮点JSON最坏长度预分片；原编码器仍核实际总字节。

    每行六个有限double按各25字节，加字段名46字节、日期/分隔符至多19字节，预留224字节；
    极端数值仍由实际完整编码拒绝，调用方可显式缩小原业务窗口。
    """
    if (type(symbols) is not list or not symbols or len(symbols) != len(set(symbols))
            or type(max_rows) is not int or max_rows < 1):
        raise ValueError('batch_symbol_plan')
    size = min(max_symbols, (max_data_bytes-4096)//(max_rows*224+256))
    if size < 1:
        raise ValueError('batch_result_budget_requires_shorter_window')
    return [symbols[i:i+size] for i in range(0, len(symbols), size)]


class BatchAnalysisSource:
    """调用线程持有 transport；一个目录/原slot构成一次可续核capture。

    所有原结果沿RetainedReadClient先保存再consumed。profile换代发生时
    原未知ID仍续核，完整binding不同则拒绝组合；旧成功包保持可读。
    """
    def __init__(self, transport, *, lifetime_ms=30000):
        self.client = RetainedReadClient(transport, lifetime_ms=lifetime_ms)

    def capture(self, request, directory, *, deadline, on_result=None, minimum_new_request_seconds=0):
        """新请求准入余量单位为秒；默认0沿旧调用，已有slot始终按原ID续核。"""
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        original = directory/'REQUEST.json'
        if original.exists():
            if json.loads(original.read_bytes()) != request:
                raise ValueError('batch_capture_identity_changed')
        else:
            _save(original, request)
        binding_file = directory/'BINDING.json'
        if binding_file.exists():
            metadata = json.loads(binding_file.read_bytes())
        else:
            with self.client.transport.rpc_budget(min(30., self.client.transport.timeout)):
                metadata = self.client._binding(deadline)
            _save(binding_file, metadata)
        profile = metadata['profile']
        descriptor = profile['operation_profiles']['market.market_data']
        if profile['read_profile_version'] != 'qmt.read-profile.v8' or descriptor['policy_id'] != POLICY:
            raise ValueError('explicit_batch_profile_required')
        scope = descriptor['limits']
        batches = self._batches(directory, request, scope)
        records, securities = [], {s: {} for s in request['symbols']}
        source_dates = {s: {} for s in request['symbols']}
        for index, symbols in enumerate(batches):
            for adjustment in ('none', 'front_ratio'):
                args = dict(symbols=symbols, start_date=request['start_date'], end_date=request['end_date'],
                    max_rows=request['max_rows'], adjustment=adjustment)
                # 完整arguments准入交原Host/Agent；消费前再次核同批来源和结构。
                batch_id = '%04d-%s' % (index, adjustment)
                slot = self._slot(directory, batch_id, args, deadline)
                returned = self.client.read('market.market_data', args, slot, deadline=deadline,
                    expected_binding=metadata['binding'], minimum_new_request_seconds=minimum_new_request_seconds)
                reply = returned['reply']
                data = reply['data']
                if (data['schema'] != RESULT_SCHEMA or data['adjustment'] != adjustment
                        or set(data['securities']) != set(symbols)):
                    raise ValueError('batch_result_projection')
                record = json.loads(slot.read_bytes())
                records.append(dict(batch_id=batch_id, slot=str(slot.relative_to(directory)).replace('\\','/'),
                    sha256=hashlib.sha256(slot.read_bytes()).hexdigest(), request_id=returned['request_id'],
                    request_body_sha256=record['request_body_sha256'], result_body_sha256=record['result']['result_body_sha256'],
                    binding=record['binding'], requested_at=returned['requested_at'], received_at=returned['received_at'],
                    completed_at=reply['completed_at'], queue_wait_ms=reply['queue_wait_ms'], execution_ms=reply['execution_ms'],
                    symbols=symbols, adjustment=adjustment))
                for symbol in symbols:
                    value = data['securities'][symbol]
                    if value['status'] not in ('observed','empty','missing','invalid','requires_partition'):
                        raise ValueError('batch_security_status')
                    securities[symbol][adjustment] = dict(batch_id=batch_id, status=value['status'],
                        data_pointer='/data/securities/'+symbol)
                    source_dates[symbol][adjustment] = set(value['data'])
                if on_result is not None:
                    on_result(batch_id, returned, record)
        comparison = {}
        for symbol, references in securities.items():
            dates = sorted(source_dates[symbol]['none'] & source_dates[symbol]['front_ratio'])
            comparison[symbol] = dict(common_dates=dates,basis=dates[-1] if dates else None,rows=len(dates),
                at_least_40=len(dates)>=40,adjustment_qualified=False,closed_basis_qualified=False,factors='not_requested')
        manifest = dict(schema=SCHEMA, universe=request.get('universe'), request=request,
            generated_at=datetime.now(timezone.utc).isoformat(),batches=records,securities=securities,comparison=comparison,
            source_kind=request['source_kind'])
        _save(directory/'manifest.json',manifest)
        return manifest

    def _slot(self, directory, batch_id, arguments, deadline):
        """批次原持久位置；专用读取owner可选后继观察，默认路径和恢复行为保持。"""
        return directory/'slots'/(batch_id+'.json')

    def _batches(self, directory, request, scope):
        """普通SDK入口沿原始顺序和来源资源额度分片。"""
        return request_batches(request['symbols'], max_rows=request['max_rows'],
            max_data_bytes=scope['max_data_bytes'], max_symbols=scope['max_symbols'])


def read_capture(directory):
    """C离线消费入口，核每个原slot字节/身份后返回批次和证券引用。"""
    from . import bound
    directory = Path(directory)
    manifest = json.loads((directory/'manifest.json').read_bytes())
    if manifest['schema'] != SCHEMA:
        raise ValueError('batch_capture_schema')
    for batch in manifest['batches']:
        path = Path(batch['slot'])
        if path.is_absolute() or '..' in path.parts:
            raise ValueError('batch_slot_path')
        raw = (directory/path).read_bytes()
        if hashlib.sha256(raw).hexdigest() != batch['sha256']:
            raise ValueError('batch_slot_digest')
        slot = json.loads(raw)
        bound.validate_response(slot['result'],max_result_bytes=slot['limits']['max_result_bytes'],request=slot['request'])
        request = slot['request']
        native = json.loads(bound.unb64(slot['result']['result_body_b64'], slot['limits']['max_result_bytes']))
        if (request['arguments']['symbols'] != batch['symbols'] or request['arguments']['adjustment'] != batch['adjustment']
                or native['ok'] is not True or native['data']['schema'] != RESULT_SCHEMA
                or set(native['data']['securities']) != set(batch['symbols'])
                or native['data']['adjustment'] != batch['adjustment']):
            raise ValueError('batch_slot_projection')
        if (slot['consumed'] is not True or slot['request']['request_id'] != batch['request_id']
                or slot['binding'] != batch['binding'] or slot['request_body_sha256'] != batch['request_body_sha256']
                or slot['result']['result_body_sha256'] != batch['result_body_sha256']):
            raise ValueError('batch_slot_identity')
    return manifest
