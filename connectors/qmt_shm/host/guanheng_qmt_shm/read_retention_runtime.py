"""显式票据准入与消费确认 HTTP 门面；源派发仍复用原 HostControlLoop。"""
from dataclasses import dataclass
import sqlite3
from guanheng_qmt_shm_agent.protocol import canonical, decode
from guanheng_qmt_shm_agent.read_retention import ENVELOPE, ReadTicketEnded
from . import bound
from .journal import JournalConflict, JournalFull
from .runtime import HostReadRuntime, HostResponse, error, response
from .trade_runtime import HostTradingRuntime


@dataclass(frozen=True)
class RetainedHostRequest:
    operation: str
    body: bytes = b''
    request_id: str | None = None

    def __post_init__(self):
        if type(self.body) is not bytes:
            raise ValueError('original retention HTTP bytes required')
        if self.operation == 'retention.status':
            if self.body or self.request_id is not None:
                raise ValueError('invalid retention status request')
        elif self.operation in ('retention.lookup', 'retention.consumed'):
            bound.request_id(self.request_id)
        else:
            raise ValueError('unsupported retained read request')


class RetainedReadRuntime(HostReadRuntime):
    read_retention_enabled = True

    def bound_submit(self, operation, raw):
        try:
            if type(raw) is not bytes or len(raw) > self.max_frame:
                raise ValueError('retained submission exceeds frame')
            envelope = decode(raw)
            if (type(envelope) is not dict or set(envelope) != {'schema_version', 'binding_sha256',
                    'request_body_b64', 'request_body_sha256', 'ticket'} or envelope['schema_version'] != ENVELOPE):
                raise ValueError('explicit retained submission required')
            original = dict(envelope)
            ticket = original.pop('ticket')
            original['schema_version'] = bound.SCHEMA
            value, body, request = bound.decode_submission(canonical(original), max_http_bytes=self.max_frame,
                max_request_bytes=self._limits['max_request_bytes'], profile=self.profile, operation=operation,
                max_result_bytes=self.journal.max_result_bytes)
            execution_ms, queue_ms = self._operation_policies[operation]
            if request['timeout_ms'] > execution_ms:
                return error(400, 'invalid_arguments')
            with self._binding_lock:
                if (not self.connected.is_set() or self.admission_stopped or self._binding_bytes is None
                        or value['binding_sha256'] != bound.digest(self._binding_bytes)):
                    return error(409, 'source_binding_changed')
                rid = self.journal.submit_ticket(body, decode(self._binding_bytes), ticket, queue_timeout_ms=queue_ms)
            self._control.notify_read()
            return self.bound_result(rid)
        except JournalConflict:
            return error(409, 'idempotency_conflict')
        except JournalFull:
            return error(503, 'read_retention_capacity_exhausted')
        except ReadTicketEnded:
            return error(400, 'read_ticket_ended')
        except (sqlite3.Error, RuntimeError):
            self.fail('journal_unavailable')
            return error(503, 'journal_unavailable')
        except (ValueError, TypeError, KeyError):
            return error(400, 'invalid_arguments')

    def request(self, request):
        if not isinstance(request, RetainedHostRequest):
            return super().request(request)
        try:
            if request.operation == 'retention.status':
                return response(200, self.journal.retention_status(self.host_instance_id))
            value = decode(request.body)
            if request.operation == 'retention.consumed':
                saved = self.journal.consumed(request.request_id, value, self.host_instance_id)
                return error(410, 'read_result_unretained') if saved is None else response(200, saved)
            code, result = self.journal.lookup(request.request_id, value, self.host_instance_id)
            return response(code, result) if code in (200, 202) else error(code, result)
        except JournalConflict:
            return error(409, 'idempotency_conflict')
        except (ValueError, TypeError, KeyError):
            return error(400, 'invalid_arguments')
        except (sqlite3.Error, RuntimeError):
            self.fail('journal_unavailable')
            return error(503, 'journal_unavailable')


class RetainedTradingRuntime(RetainedReadRuntime, HostTradingRuntime):
    """只读票据门面叠加原交易运行器；交易请求及 control worker 沿原路径。"""
