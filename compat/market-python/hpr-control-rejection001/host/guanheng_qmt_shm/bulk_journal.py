"""显式bulk owner复用原通信事务；原body、来源和终态留在同一张表。"""
from dataclasses import dataclass
import math
import time

from guanheng_qmt_shm_agent.bulk_capabilities import BULK_OPERATION, validate_bulk_read_profile
from guanheng_qmt_shm_agent.protocol import canonical, decode
from guanheng_qmt_shm_agent.trade_clock import deadline_seconds
from .bound import validate_response
from .bound_journal import BoundReadJournal
from .bulk_contracts import validate_bulk_request, validate_bulk_result, make_bulk_result
from .journal import JournalConflict


@dataclass(frozen=True)
class _BulkRequest:
    request_id: str
    operation_id: str
    _arguments_bytes: bytes

    @property
    def arguments(self):
        return decode(self._arguments_bytes)


class BulkBoundReadJournal(BoundReadJournal):
    """clock显式提供共享uptime秒；monotonic参数只约束本次持久I/O。"""
    def __setattr__(self, name, value):
        if name == '_bulk_clock' and hasattr(self,name):
            raise AttributeError('bulk Journal clock owner is frozen')
        super().__setattr__(name,value)

    def __init__(self, path, route, *, max_records, max_result_bytes,
                 max_request_bytes, max_journal_bytes, read_profile, clock):
        profile=validate_bulk_read_profile(read_profile,max_result_bytes=max_result_bytes)
        if not callable(getattr(clock,'seconds',None)):
            raise ValueError('bulk Journal requires explicit shared clock')
        # 父构造可能立即恢复dispatching；所有恢复依赖在进入父构造前就绪。
        self._bulk_clock=clock
        super().__init__(path,route,max_records=max_records,max_result_bytes=max_result_bytes,
            max_request_bytes=max_request_bytes,max_journal_bytes=max_journal_bytes,read_profile=profile)

    def _shared_now(self):
        try:
            now=self._bulk_clock.seconds()
            if type(now) not in (int,float) or not math.isfinite(now) or now<0:
                raise ValueError('invalid shared clock')
            return now
        except Exception:
            raise ValueError('bulk_clock_unavailable') from None

    def _validate_bound_request(self, raw_request):
        if not isinstance(raw_request,dict) or raw_request.get('operation_id') != BULK_OPERATION:
            return super()._validate_bound_request(raw_request)
        request=validate_bulk_request(raw_request,self.admission_profile,max_result_bytes=self.max_result_bytes)
        return _BulkRequest(request['request_id'],request['operation_id'],canonical(request['arguments']))

    def _admit_new_bound(self, raw_request, queue_timeout_ms):
        if raw_request['operation_id'] != BULK_OPERATION:
            return super()._admit_new_bound(raw_request,queue_timeout_ms)
        now=self._shared_now()
        remaining=deadline_seconds(raw_request['deadline_ms'])-now
        queued=deadline_seconds(raw_request['queue_deadline_ms'])-now
        profile=self.admission_profile['bulk_profile']
        if (remaining<=0 or queued<=0 or remaining>profile['total_timeout_ms']/1000
                or queued>profile['queue_timeout_ms']/1000):
            raise ValueError('bulk request is outside original admission window')
        return time.time()+min(queue_timeout_ms/1000,queued)

    def _queued_bound_failure(self, raw_request):
        if raw_request['operation_id'] != BULK_OPERATION:
            return super()._queued_bound_failure(raw_request)
        now=self._shared_now()
        if now>=deadline_seconds(raw_request['deadline_ms']):
            return 'expired'
        if now>=deadline_seconds(raw_request['queue_deadline_ms']):
            return 'queue_timeout'
        return None

    def _interrupted_result(self, request_id, operation_id, code):
        if operation_id != BULK_OPERATION:
            return super()._interrupted_result(request_id,operation_id,code)
        return make_bulk_result(request_id,error_code=code,max_result_bytes=self.max_result_bytes)

    def _normalize_bound_result(self, result):
        if not isinstance(result,dict) or result.get('operation_id') != BULK_OPERATION:
            return super()._normalize_bound_result(result)
        return validate_bulk_result(result,max_result_bytes=self.max_result_bytes)

    def _validate_bound_projection(self, request, result, actual_binding):
        if request['operation_id'] != BULK_OPERATION:
            return super()._validate_bound_projection(request,result,actual_binding)
        if result.get('ok') is True and actual_binding is None:
            raise JournalConflict('bulk success requires recorded result provenance')
        return validate_bulk_result(result,request,max_result_bytes=self.max_result_bytes,
            actual_binding=actual_binding)

    def _validate_bound_response(self, value, request):
        if request['operation_id'] != BULK_OPERATION:
            return super()._validate_bound_response(value,request)
        return validate_response(value,max_result_bytes=self.max_result_bytes,
            control_version=self.binding_control_version,request=request,
            result_projection=lambda original,result:self._validate_bound_projection(
                original,result,value['result_binding']))
