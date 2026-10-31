"""显式v5运行时；共享原HTTP、Journal和完整关闭所有权。"""
import math
import sqlite3
import time
from guanheng_qmt_shm_agent.bulk_capabilities import BULK_OPERATION, profile_descriptor
from guanheng_qmt_shm_agent.protocol import canonical, decode
from guanheng_qmt_shm_agent.read_capabilities import operation_descriptor
from .bound import SCHEMA, binding, digest, metadata_bytes, sha256_text, unb64, request_id
from .bulk_clock import WindowsBulkUptimeClock
from .bulk_contracts import validate_bulk_request
from .journal import JournalConflict, JournalFull
from .runtime import HostReadRuntime, HostRequest, HostResponse, error


class BulkHostRequest(HostRequest):
    """仅显式bulk门面选择此DTO；旧DTO继续拒绝新操作。"""
    def __post_init__(self):
        if self.operation=='bound.submit' and self.operation_id==BULK_OPERATION:
            if type(self.body) is not bytes or self.request_id is not None:
                raise ValueError('invalid bulk HTTP request')
        else:
            super().__post_init__()


class HostBulkReadRuntime(HostReadRuntime):
    bulk_requests_enabled=True

    def __init__(self,journal,*,bulk_settings,bulk_clock=None,bulk_mono=time.monotonic,**kwargs):
        from .bulk_bootstrap import validate_bulk_settings
        self._bulk_settings=canonical(validate_bulk_settings(bulk_settings,journal.admission_profile,
            max_result_bytes=journal.max_result_bytes))
        self.bulk_clock=WindowsBulkUptimeClock() if bulk_clock is None else bulk_clock
        if not callable(getattr(self.bulk_clock,'seconds',None)) or not callable(bulk_mono):
            raise ValueError('explicit bulk clocks required')
        self.bulk_mono=bulk_mono
        super().__init__(journal,**kwargs)

    @property
    def bulk_settings(self):
        return decode(self._bulk_settings)

    def _admit_operation_policies(self,profile,policies,max_result_bytes):
        profile_descriptor(profile,max_result_bytes=max_result_bytes)
        from guanheng_qmt_shm_agent.bulk_configuration import _require
        _require(profile,self.control_profile)
        result={}
        for op in profile['read_operations']:
            if op==BULK_OPERATION:
                continue
            desc=operation_descriptor(profile,op,max_result_bytes=max_result_bytes)
            policy=policies.require(desc['policy_id'],op)
            if policy.execution_timeout_ms!=desc['execution_timeout_ms']:
                raise ValueError('operation native policy differs')
            self.control_profile.require_roundtrip(policy.queue_timeout_ms,policy.execution_timeout_ms)
            result[op]=(policy.execution_timeout_ms,policy.queue_timeout_ms)
        return result

    def _make_control(self,session,actual_binding):
        from .bulk_host_control import BulkHostControlLoop
        return BulkHostControlLoop(self,session,actual_binding)

    def _io_deadline(self,deadline=None):
        own=self.bulk_mono()+self.budget.io_seconds
        if deadline is None:
            return own
        if type(deadline) not in (int,float) or not math.isfinite(deadline):
            raise ValueError('finite original IO deadline required')
        return min(own,deadline)

    def bound_result(self,rid):
        try:
            request_id(rid)
        except ValueError:
            return error(400,'invalid_arguments')
        deadline=self._io_deadline()
        try:
            value=self.journal.get_bound(rid,deadline=deadline)
            answer=error(404,'unknown_operation') if value is None else self._result_response(value)
            if self.bulk_mono()>=deadline:
                raise TimeoutError('bulk result deadline')
            return answer
        except (TimeoutError,sqlite3.Error,RuntimeError,ValueError,TypeError):
            self.fail('journal_unavailable')
            return error(503,'journal_unavailable')

    def _result_response(self,value):
        encoded=canonical(value)
        if len(encoded)>self._limits['max_http_response_bytes']:
            raise ValueError('bound result exceeds capacity')
        return HostResponse(200 if value['state']=='terminal' else 202,encoded)

    def claim_bound(self,channel_binding,*,deadline=None):
        deadline=self._io_deadline(deadline)
        encoded=canonical(binding(channel_binding,control_version=self.binding_control_version))
        if not self._binding_lock.acquire(timeout=max(0,deadline-self.bulk_mono())):
            raise TimeoutError('bulk claim deadline')
        try:
            if self.bulk_mono()>=deadline:
                raise TimeoutError('bulk claim deadline')
            if not self.connected.is_set() or self.admission_stopped or encoded!=self._binding_bytes:
                return None
            return self.journal.claim_bound(channel_binding,deadline=deadline)
        finally:
            self._binding_lock.release()

    def bound_submit(self,operation,raw):
        if operation!=BULK_OPERATION:
            return super().bound_submit(operation,raw)
        deadline=self._io_deadline()
        try:
            if type(raw) is not bytes or len(raw)>self.max_frame:
                raise ValueError('bounded original HTTP bytes required')
            value=decode(raw)
            if (type(value) is not dict or set(value)!={'schema_version','binding_sha256',
                    'request_body_b64','request_body_sha256'} or value['schema_version']!=SCHEMA):
                raise ValueError('bound envelope differs')
            metadata_bytes(value,'request_body_b64')
            sha256_text(value['binding_sha256']);sha256_text(value['request_body_sha256'])
            body=unb64(value['request_body_b64'],self._limits['max_request_bytes'])
            if digest(body)!=value['request_body_sha256']:
                raise ValueError('original request SHA differs')
            validate_bulk_request(decode(body),self.profile,max_result_bytes=self.journal.max_result_bytes)
            queue_ms=profile_descriptor(self.profile,max_result_bytes=self.journal.max_result_bytes)['queue_timeout_ms']
            if not self._binding_lock.acquire(timeout=max(0,deadline-self.bulk_mono())):
                raise TimeoutError('bulk submission deadline')
            try:
                if self.bulk_mono()>=deadline:
                    raise TimeoutError('bulk submission deadline')
                if (not self.connected.is_set() or self.admission_stopped or self._binding_bytes is None
                        or value['binding_sha256']!=digest(self._binding_bytes)):
                    return error(409,'source_binding_changed')
                rid=self.journal.submit_bound(body,decode(self._binding_bytes),
                    queue_timeout_ms=queue_ms,deadline=deadline)
            finally:
                self._binding_lock.release()
            self._control.notify_read()
            # POST回复沿同一I/O截止；晚返回已提交时只由调用方GET原ID核事实。
            value=self.journal.get_bound(rid,deadline=deadline)
            answer=self._result_response(value)
            if self.bulk_mono()>=deadline:
                raise TimeoutError('bulk submission deadline')
            return answer
        except JournalConflict:
            return error(409,'idempotency_conflict')
        except JournalFull:
            return error(503,'queue_full')
        except (TimeoutError,sqlite3.Error,RuntimeError):
            self.fail('journal_unavailable')
            return error(503,'journal_unavailable')
        except (ValueError,TypeError,KeyError):
            return error(400,'invalid_arguments')
