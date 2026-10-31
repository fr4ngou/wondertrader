"""显式bulk页调度复用原peer与唯一域线程；文件提交决定页ACK资格。"""
from datetime import datetime, timezone
import math
import time

from guanheng_qmt_shm_agent.bulk_capabilities import BULK_OPERATION
from guanheng_qmt_shm_agent.protocol import ProtocolError, canonical, decode
from guanheng_qmt_shm_agent.trade_clock import deadline_seconds
from .bulk_contracts import bulk_identity, bulk_open_payload
from .bulk_file_domain import BulkFileDomain
from .control import HostControlLoop
from .domain import HostDomainWorker


class BulkHostControlLoop(HostControlLoop):
    def __init__(self, runtime, session, binding):
        if runtime.control_profile.version!='3.0':
            raise ValueError('bulk Host requires explicit control 3.0')
        self._bulk=None
        self._bulk_future=self._bulk_job=self._bulk_pending=None
        self._files=None
        self._closing=False
        self._cleanup_future=self._cleanup_scan=None
        super().__init__(runtime,session,binding)

    def _make_domain(self):
        # 原队列仍唯一；完整base64页加请求及原D受原4MiB硬上限约束。
        return HostDomainWorker(self._journal_call,max_pending=2,max_payload_bytes=4194304,
            wake=self._wake,drain=True,name='qmt-host-bulk-domain')

    def _file_owner(self):
        if self._files is None:
            self._files=BulkFileDomain(self.runtime,self.binding)
        return self._files

    def _journal_call(self, operation, payload):
        if operation=='bulk.page':
            return self._file_owner().accept(payload)
        if operation=='bulk.close':
            requests=payload['requests']
            first=None
            if self._cleanup_scan is not None:
                try:
                    claimed=self._cleanup_scan.result()
                    if claimed is not None: requests.append(decode(claimed[1]))
                except Exception as error:
                    first=error
            if payload['page'] is not None:
                try:
                    self._file_owner().accept(payload['page'])
                except Exception:
                    # 域owner已保首因；继续GET核事实和原线程资源收口，不发送ACK。
                    pass
            if payload['read_finish'] is not None:
                pending=payload['read_finish']
                try:
                    self.runtime.journal.finish_bound(pending['request_id'],pending['result'],self.binding,
                        deadline=min(payload['deadline'],pending['deadline']))
                except Exception as error:
                    if first is None: first=error
            try:
                result=self._file_owner().close(payload['deadline'],requests)
            except Exception as error:
                if first is None: first=error
            if first is not None:
                raise first
            return result
        return super()._journal_call(operation,payload)

    def _clocks(self):
        local=self.runtime.bulk_mono()
        shared=self.runtime.bulk_clock.seconds()
        if any(type(value) not in (int,float) or not math.isfinite(value) or value<0
               for value in (local,shared)):
            raise ValueError('bulk_clock_unavailable')
        return local,shared

    def _begin_bulk(self):
        if self._bulk is not None or self.active is None:
            return
        request=decode(self.active[1])
        if request['operation_id']!=BULK_OPERATION:
            return
        # local0先于shared1；映射等待期间只消耗原共享D，不加新的业务TTL。
        local,shared=self._clocks()
        deadline=local+max(0,deadline_seconds(request['deadline_ms'])-shared)
        queue=min(deadline,local+max(0,deadline_seconds(request['queue_deadline_ms'])-shared))
        self._bulk=dict(request=request,identity=bulk_identity(request,self.binding),
                        deadline=deadline,queue_deadline=queue,phase='open',page_index=0)

    def _remaining(self, queue=False):
        local,shared=self._clocks()
        item=self._bulk
        shared_deadline=deadline_seconds(item['request']['queue_deadline_ms' if queue else 'deadline_ms'])
        local_deadline=item['queue_deadline'] if queue else item['deadline']
        remaining=min(local_deadline-local,shared_deadline-shared)
        if remaining<=0:
            raise TimeoutError('original bulk deadline elapsed')
        return remaining

    def _expiry(self):
        # UTC只供原peer编码；业务双钟在每阶段及ACK资格处独立核对。
        remaining=min(self._remaining(),self.runtime.control_profile.max_call_seconds)
        stamp=math.floor((time.time()+remaining)*1000000)/1000000
        return datetime.fromtimestamp(stamp,timezone.utc).isoformat()

    def _progress_bulk(self):
        if self._bulk_job is not None and self._bulk_job.done():
            receipt=self._domain_result(self._bulk_job)
            self._remaining()
            if (receipt['page_index']!=self._bulk['page_index'] or not receipt['durable']
                    or receipt['final'] and not receipt['terminal_committed']):
                raise ProtocolError('bulk durable completion differs')
            self._bulk_job=None
            if receipt['final']:
                self.active=None
                self._bulk['phase']='final_retire'
            else:
                self._bulk['phase']='page_retire'
            self._remaining()
            self._bulk_future.ack()
        if self._bulk_future is not None and self._bulk_future.retired:
            phase=self._bulk['phase']
            if phase not in ('open_retire','page_retire','final_retire'):
                raise ProtocolError('bulk source delivery retired without domain acknowledgement')
            self._bulk_future=None
            if phase=='final_retire':
                self._bulk=None
                self._read_wake.set()
            else:
                if phase=='page_retire': self._bulk['page_index']+=1
                self._bulk['phase']='page'

    def _admit(self):
        if self._closing:
            return
        self._progress_domain()
        self._begin_bulk()
        if self._bulk is None:
            # 扫描完成与普通父_admit之间不能再收取一次尚未分类的bulk请求。
            if self._read_scan is not None:
                return
            return super()._admit()
        self._progress_bulk()
        if self._bulk is None:
            return
        self._remaining()
        if self._bulk_future is not None or self._bulk_job is not None or not self.peer.can_submit():
            return
        request=self._bulk['request']
        if self._bulk['phase']=='open':
            self._remaining(queue=True)
            operation='agent.bulk.open'
            payload=bulk_open_payload(request,self.binding)
        elif self._bulk['phase']=='page':
            operation='agent.bulk.page'
            payload=dict(request_id=request['request_id'],identity=self._bulk['identity'],
                         page_index=self._bulk['page_index'])
        else:
            return
        self._bulk_future=self.peer.submit(operation,payload,self._expiry())

    def _submit_bulk_page(self):
        if self._bulk_pending is None or self._bulk_job is not None:
            return
        self._remaining()
        try:
            self._bulk_job=self._domain.submit('bulk.page',self._bulk_pending)
        except BufferError:
            return
        self._bulk_pending=None

    def _complete(self):
        if self._closing:
            return
        if self._bulk is None:
            return super()._complete()
        self._progress_bulk()
        if self._bulk is None:
            return
        self._remaining()
        if self._bulk_future is not None and self._bulk_job is None and self._bulk_pending is None:
            reply=self._bulk_future.take()
            if reply is not None:
                if not reply['ok'] or type(reply['payload']) is not dict:
                    raise ProtocolError('bulk source failed before durable completion')
                value=reply['payload']
                if self._bulk['phase']=='open':
                    if (set(value)!=set('schema request_id identity stage snapshot error_code'.split())
                            or value['schema']!='qmt.history-bulk-open.v1'
                            or value['request_id']!=self._bulk['request']['request_id']
                            or value['identity']!=self._bulk['identity']
                            or value['stage']!='snapshot' or value['error_code'] is not None):
                        raise ProtocolError('bulk open lacks original successful snapshot')
                    self._remaining()
                    self._bulk_future.ack()
                    self._bulk['phase']='open_retire'
                elif self._bulk['phase']=='page':
                    if (value.get('schema')!='qmt.history-bulk-delivery.v1'
                            or value.get('page_index')!=self._bulk['page_index']):
                        raise ProtocolError('bulk source page differs')
                    self._bulk_pending=dict(request=self._bulk['request'],delivery=value,
                                            deadline=self._bulk['deadline'])
                else:
                    raise ProtocolError('bulk source delivered an unexpected result')
        self._submit_bulk_page()
        self._progress_bulk()

    def _queue_cleanup(self):
        if self._cleanup_future is not None:
            return
        requests=[]
        if self.active is not None: requests.append(decode(self.active[1]))
        if self._bulk is not None: requests.append(self._bulk['request'])
        self._cleanup_scan=self._read_scan
        payload=dict(requests=requests,page=self._bulk_pending,
            read_finish=None if self._read_finish is None else self._read_finish_payload(),
            deadline=time.monotonic()+self.runtime.budget.io_seconds)
        self._cleanup_future=self._domain.submit('bulk.close',payload)
        self._bulk_pending=None

    def interrupt_read(self):
        # 原I/O finally只排域收口；原页/COMMIT失败不在管理线程碰collector。
        self._closing=True
        self._queue_cleanup()

    def request_close(self):
        self._closing=True
        self.peer.close()
        self._queue_cleanup()

    def close(self, deadline):
        self.request_close()
        # 先等待原线程释放实际资源，再停止域；未知资源仍保活原线程和owner。
        self._cleanup_future.result(timeout=max(0,deadline-time.monotonic()))
        self._domain.request_close()
        self._domain.close(max(0,deadline-time.monotonic()))
        if time.monotonic()>=deadline:
            raise TimeoutError('retain bulk control owner until original close completes')
        self.active=self._read_scan=self._read_commit=self._read_finish=None
        self._bulk=self._bulk_future=self._bulk_job=self._bulk_pending=None
