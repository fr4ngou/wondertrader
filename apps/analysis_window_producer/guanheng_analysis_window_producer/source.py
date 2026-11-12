"""八证券分析来源适配；只读请求身份和实收时间归本层，复权归原 QNA。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import time
from uuid import uuid4

from integrations.guanheng.qmt_native_adjustment import SYMBOLS, canonical


class SourcePending(RuntimeError):
    """原请求尚未确认；下一次继续同 capture/请求身份。"""


class SourceUnavailable(RuntimeError):
    """来源已确认缺数据；保留上次窗口，后续可以发起新读取。"""


def utc_now():
    return datetime.now(timezone.utc)


def write_json(path, value):
    """同目录原子发布纯值；文件只供外部 WT 使用，QMT 不读取。"""
    path = Path(path)
    temporary = path.with_name(path.name + '.' + str(uuid4()) + '.tmp')
    raw = canonical(value)
    try:
        with temporary.open('xb') as stream:
            if stream.write(raw) != len(raw):
                raise OSError('analysis_write_incomplete')
            stream.flush()
            os.fsync(stream.fileno())
        if os.name == 'nt' and path.exists():
            # Windows读者可能仍持有上一代文件；ReplaceFileW沿已发布文件的
            # 共享删除语义原子换代，完整旧内容由其读句柄保留。读者应使用_open_read。
            import ctypes
            from ctypes import wintypes
            api = ctypes.WinDLL('kernel32', use_last_error=True)
            replace = api.ReplaceFileW
            replace.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR,
                                wintypes.DWORD, wintypes.LPVOID, wintypes.LPVOID]
            replace.restype = wintypes.BOOL
            if not replace(str(path), str(temporary), None, 0, None, None):
                raise ctypes.WinError(ctypes.get_last_error())
        else:
            os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def closed_through(now):
    """A 股日线在上海 15:00 后闭合；休市日期由实际八证券交集过滤。"""
    local = now.astimezone(timezone(timedelta(hours=8)))
    day = local.date() if (local.hour, local.minute) >= (15, 0) else local.date() - timedelta(days=1)
    return day.isoformat()


class AnalysisSnapshotProvider:
    """client.read 返回原 reply/UTC 实收收据；一个 capture 只完成一次。

    client 必须在原请求 POST 前保存身份，并把未确认结果保存到原目录续核。
    外部 SDK 替身沿相同接口调用真实形态的 SDK 方法，禁止返回预制分析窗口。
    """

    def __init__(self, client, source, *, clock=utc_now, preparation=None):
        self.client, self.source, self.clock = client, dict(source), clock
        self.preparation=preparation

    def request_close(self, *, deadline):
        """停止全部来源准入；当前原请求保持原身份和已保存结果。"""
        for owner in (self.client, self.preparation):
            # 自定义同步 provider/client 保持原 read/capture 协议；部署工厂的
            # 原 Bound 客户端显式实现停止通知，不扩展 SDK 或来源协议。
            close = getattr(owner, 'request_close', None)
            if close is not None:
                close(deadline=deadline)

    def capture(self, request, output_directory, *, deadline):
        directory = Path(output_directory)
        directory.mkdir(parents=True, exist_ok=True)
        if (request.get('schema') != 'guanheng.qna-capture-request.v1'
                or request.get('symbols') != list(SYMBOLS)):
            raise ValueError('analysis_capture_request')
        request_file = directory/'CAPTURE.json'
        if request_file.exists():
            if json.loads(request_file.read_bytes()) != request:
                raise ValueError('analysis_capture_identity')
        else:
            write_json(request_file, request)
        result = directory/'SNAPSHOT.json'
        if result.exists():
            return result
        closure_file = directory/'CLOSURE.json'
        if not closure_file.exists():
            now = self.clock()
            write_json(closure_file, {'closed_through': closed_through(now),
                'closure_evidence': 'Asia/Shanghai regular ETF session ends 15:00; observed-date intersection',
                'observed_at': now.isoformat()})
        closure = json.loads(closure_file.read_bytes())
        if self.preparation is not None:
            self.preparation.prepare(request,directory/'preparation',closure,deadline=deadline)
        end = closure['closed_through'].replace('-', '')
        daily, factors, references = {}, {}, {}
        for symbol in SYMBOLS:
            arguments = dict(symbol=symbol, start_date=request['start_date'].replace('-', ''),
                end_date=end, max_rows=request['max_rows_per_symbol'], adjustment='none')
            daily[symbol] = self.client.read('market.market_data', arguments,
                directory/(symbol+'-raw.json'), deadline=deadline)
            factors[symbol] = self.client.read('market.divid_factors', dict(symbol=symbol),
                directory/(symbol+'-factor.json'), deadline=deadline)
        dates = []
        for symbol in SYMBOLS:
            value = daily[symbol]['reply']['data']
            if type(value) is not dict or set(value) != {symbol} or not value[symbol]:
                raise SourceUnavailable('analysis_daily_missing')
            dates.append({d for d in value[symbol] if d <= end})
        common = set.intersection(*dates)
        if len(common) < 100:
            raise SourceUnavailable('analysis_common_dates_missing')
        basis = max(common)
        for symbol in SYMBOLS:
            references[symbol] = {}
            for adjustment in ('none', 'front_ratio'):
                arguments = dict(symbol=symbol, start_date=basis, end_date=basis,
                    max_rows=1, adjustment=adjustment)
                references[symbol][adjustment] = self.client.read('market.market_data', arguments,
                    directory/(symbol+'-reference-'+adjustment+'.json'), deadline=deadline)
        value = dict(schema='guanheng.qna-source-snapshot.v1', capture_id=request['capture_id'],
            source=self.source, closed_through=closure['closed_through'],
            closure_evidence=closure['closure_evidence'], daily=daily, factors=factors, references=references)
        if len(canonical(value)) > 16*1024*1024:
            raise ValueError('analysis_snapshot_capacity')
        write_json(result, value)
        return result


class BoundAnalysisClient:
    """复用原签名 HTTP/八字段请求，新增 v7 读操作的有身份观察适配。

    每个 slot 在 POST 前保存原 bound envelope；超时恢复只 GET 原 UUID。
    终态及实际 received_at 一起保存，重读旧结果保持原时钟。没有下载和交易入口。
    """

    def __init__(self, configuration, *, environ=None):
        from .retained import transport
        self.transport,self.retention,self.retained=transport(configuration,environ=environ)

    def request_close(self, *, deadline):
        self.transport.request_close(deadline)

    def _binding(self, deadline):
        from guanheng_qmt_shm import bound
        from guanheng_qmt_shm_agent.protocol import canonical as encode, decode
        from guanheng_qmt_shm_agent.read_capabilities import validate_read_profile
        code, value = self.transport.exchange('GET', '/internal/v1/read-binding', b'', deadline)
        if code != 200:
            raise SourcePending('analysis_source_waiting')
        checked = bound.binding(value['binding'])
        raw = bound.unb64(value['read_profile_body_b64'], 4096)
        if (value['schema_version'] != bound.SCHEMA or value['order_ready'] is not False
                or bound.digest(encode(checked)) != value['binding_sha256']
                or not bound.digest(raw) == value['read_profile_body_sha256'] == checked['capability_sha256']):
            raise ValueError('analysis_source_binding')
        profile = validate_read_profile(decode(raw), max_result_bytes=value['limits']['max_result_bytes'])
        if (profile['read_profile_version'] != 'qmt.read-profile.v7'
                or not {'market.market_data', 'market.divid_factors'} <= set(profile['read_operations'])):
            raise ValueError('analysis_source_profile')
        return dict(value, profile=profile)

    def _superseded_read(self, slot, metadata, operation, arguments, deadline):
        # 已持久消费的旧代中断终态可结束本次只读行情捕获。Host仍持有原未知
        # 责任；新捕获使用当前认证，不复派原ID，也不合并两代行情。
        from guanheng_qmt_shm.read_retention_client import inspect_saved_result
        from .retained import check_capability
        if not slot.exists():
            return False
        record = json.loads(slot.read_bytes())
        if (record.get('consumed') is not True
                or record['binding'] != metadata['binding']
                or record['request']['operation_id'] != operation
                or record['request']['arguments'] != arguments):
            return False
        reply = inspect_saved_result(record)
        if reply['ok'] is not False or reply['error_code'] != 'operation_interrupted':
            return False
        current = self._binding(deadline)
        check_capability(current, self.retention)
        old_binding, new_binding = record['binding'], current['binding']
        if old_binding['host_instance_id'] == new_binding['host_instance_id']:
            return False
        epoch_fields = {'host_instance_id', 'transport_generation'}
        if (old_binding.keys() != new_binding.keys()
                or any(old_binding[key] != new_binding[key] for key in old_binding.keys() - epoch_fields)):
            return False
        from guanheng_qmt_shm import bound
        from guanheng_qmt_shm_agent.protocol import canonical as encode
        old_sha = bound.digest(encode(old_binding))
        if old_sha != metadata['binding_sha256']:
            raise ValueError('analysis_original_binding_identity')
        evidence = slot.parent/'SUPERSEDED.json'
        identity = dict(schema='guanheng.analysis-source-superseded.v1',
            request_id=record['request']['request_id'], request_body_sha256=record['request_body_sha256'],
            result_body_sha256=record['result']['result_body_sha256'], old_binding_sha256=old_sha)
        if evidence.exists():
            saved = json.loads(evidence.read_bytes())
            previous_sha = saved.pop('new_binding_sha256')
            if (saved != identity or not isinstance(previous_sha, str) or len(previous_sha) != 64
                    or previous_sha == old_sha or any(c not in '0123456789abcdef' for c in previous_sha)):
                raise ValueError('analysis_superseded_identity')
        else:
            write_json(evidence, dict(identity, new_binding_sha256=current['binding_sha256']))
        return True

    def read(self, operation, arguments, slot, *, deadline):
        from guanheng_qmt_shm import bound
        from guanheng_qmt_shm_agent.protocol import canonical as encode, decode
        from integrations.guanheng.source_history_transport import SourcePending as TransportPending
        if operation not in ('market.market_data', 'market.divid_factors'):
            raise ValueError('analysis_source_operation')
        slot = Path(slot)
        try:
            from .lifecycle import admit_read
            admit_read(self.transport, deadline)
            with self.transport.rpc_budget(min(30., max(.1, deadline-time.monotonic()))):
                # 首次认证查询与后续读取共用原 RPC 总D及传输异常分类。
                if self.retained is not None:
                    from .retained import check_capability
                    from guanheng_qmt_shm.read_retention_client import RetainedReadPending,RetainedReadFailure
                    try:
                        metadata_path=slot.parent/'BINDING.json'
                        if metadata_path.exists(): metadata=json.loads(metadata_path.read_bytes())
                        else:
                            metadata=self._binding(deadline)
                            check_capability(metadata,self.retention)
                            write_json(metadata_path,metadata)
                        check_capability(metadata,self.retention)
                        # 公共客户端先持久保存原结果，再发 consumed；恢复沿原 slot/ID。
                        return self.retained.read(operation,arguments,slot,deadline=deadline,
                            expected_binding=metadata['binding'])
                    except RetainedReadPending:
                        if self._superseded_read(slot, metadata, operation, arguments, deadline):
                            raise SourceUnavailable('analysis_source_epoch_interrupted') from None
                        raise SourcePending('analysis_original_request_unresolved') from None
                    except RetainedReadFailure as error:
                        if str(error) == 'read_admission_rejected':
                            raise SourceUnavailable('analysis_source_admission_rejected') from None
                        raise SourceUnavailable('analysis_source_terminal_failure') from None
                if slot.exists():
                    record = json.loads(slot.read_bytes())
                    if record['request']['operation_id'] != operation or record['request']['arguments'] != arguments:
                        raise ValueError('analysis_original_request_changed')
                else:
                    metadata_path = slot.parent/'BINDING.json'
                    if metadata_path.exists():
                        metadata = json.loads(metadata_path.read_bytes())
                    else:
                        metadata = self._binding(deadline)
                        write_json(metadata_path, metadata)
                    # 一个快照固定同一个原认证绑定；重连不会把不同代的读取混成一份。
                    record = self.transport.plan(operation, arguments, metadata, deadline)
                    record.update(requested_at=utc_now().isoformat(), received_at=None)
                    write_json(slot, record)
                request = record['request']
                raw = encode(request)
                if bound.digest(raw) != record['request_body_sha256']:
                    raise ValueError('analysis_original_request_changed')
                from guanheng_qmt_shm_agent.read_capabilities import validate_read_request
                validate_read_request(request, record['profile'], max_result_bytes=record['limits']['max_result_bytes'])
                if bound.digest(encode(record['profile'])) != record['binding']['capability_sha256']:
                    raise ValueError('analysis_original_profile_changed')
                if record['result'] is None:
                    if not record['attempted']:
                        record['attempted'] = True
                        write_json(slot, record)
                        envelope = encode(dict(schema_version=bound.SCHEMA,
                            binding_sha256=bound.digest(encode(record['binding'])),
                            request_body_b64=bound.b64(raw), request_body_sha256=bound.digest(raw)))
                        code, result = self.transport.exchange('POST', '/internal/v1/bound-operations/'+operation, envelope, deadline)
                    else:
                        code, result = self.transport.exchange('GET', '/internal/v1/bound-results/'+request['request_id'], b'', deadline)
                    while True:
                        if code not in (200, 202):
                            raise SourcePending('analysis_original_request_unresolved')
                        bound.validate_response(result, max_result_bytes=record['limits']['max_result_bytes'], request=request)
                        if (result['request_body_sha256'] != record['request_body_sha256']
                                or result['admitted_binding'] != record['binding']):
                            raise ValueError('analysis_source_result_binding')
                        if result['state'] == 'terminal':
                            record.update(result=result, received_at=utc_now().isoformat())
                            write_json(slot, record)
                            break
                        if time.monotonic()+.02 >= deadline:
                            raise SourcePending('analysis_original_request_pending')
                        time.sleep(.02)
                        code, result = self.transport.exchange('GET', '/internal/v1/bound-results/'+request['request_id'], b'', deadline)
                bound.validate_response(record['result'], max_result_bytes=record['limits']['max_result_bytes'], request=request)
                if (record['result']['request_body_sha256'] != record['request_body_sha256']
                        or record['result']['admitted_binding'] != record['binding']):
                    raise ValueError('analysis_source_result_binding')
                reply = decode(bound.unb64(record['result']['result_body_b64'], record['limits']['max_result_bytes']))
                if reply['ok'] is not True:
                    raise SourceUnavailable('analysis_source_terminal_failure')
                return dict(request_id=request['request_id'], requested_at=record['requested_at'],
                    received_at=record['received_at'], reply=reply)
        except TransportPending as error:
            import http.client
            # 原通用客户端把 HTTPException 也装为 Pending；新只读边界保留协议故障，
            # RemoteDisconnected 同时属于 OSError，继续表示连接结果未确认。
            cause = error.__context__
            if isinstance(cause, http.client.HTTPException) and not isinstance(cause, OSError):
                raise ValueError('analysis_source_http_protocol') from None
            raise SourcePending('analysis_source_waiting') from None
