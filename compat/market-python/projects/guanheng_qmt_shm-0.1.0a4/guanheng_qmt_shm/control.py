"""原base control调度：持久派发在发送前，原终态与来源提交后才ACK。"""
from __future__ import annotations
import base64
from datetime import datetime, timezone
import threading
import time
from guanheng_qmt_shm_agent.control_peer import ControlPeer
from guanheng_qmt_shm_agent.protocol import ProtocolError, canonical, decode
from .domain import HostDomainWorker


class HostControlLoop:
    def __init__(self, runtime, session, binding):
        self.runtime,self.session=runtime,session
        self._binding=canonical(binding)
        self.peer=ControlPeer('host',session.generation,runtime.control_profile)
        self.active,self.read_future=None,None
        self._read_scan,self._read_commit=None,None
        self._read_finish=None
        self._read_wake=threading.Event();self._read_wake.set()
        self._wake=runtime._wake
        self.domain_failed=False
        self._domain=self._make_domain()

    def _make_domain(self):
        return HostDomainWorker(self._journal_call,max_pending=2,
            max_payload_bytes=self.runtime.journal.max_result_bytes+1024,wake=self._wake,
            drain=True,name='qmt-host-read-journal')

    @property
    def binding(self):
        return decode(self._binding)

    def _journal_call(self, operation, payload):
        if operation=='read.claim':
            return self.runtime.claim_bound(self.binding)
        if operation=='read.finish':
            self.runtime.journal.finish_bound(payload['request_id'],payload['result'],self.binding,
                                             deadline=payload['deadline'])
        elif operation=='read.interrupt':
            self.runtime.journal.interrupt_bound(payload['request_id'],payload['operation_id'])
        else:
            raise RuntimeError('unsupported read Journal operation')

    def _domain_result(self, future):
        try:
            return future.result()
        except Exception:
            self.domain_failed=True
            raise

    def _progress_domain(self):
        if self._read_scan is not None and self._read_scan.done():
            self.active=self._domain_result(self._read_scan)
            self._read_scan=None
        if self._read_commit is not None and self._read_commit.done():
            self._domain_result(self._read_commit)
            self._read_commit=None
            # 先消除active再ACK；收据丢失不能用中断覆盖已提交成功。
            self.active=None
            if self.read_future is not None:
                self.read_future.ack()

    def _admit(self):
        self._progress_domain()
        if self.read_future is not None and self.read_future.retired:
            self.read_future=None
            self._read_wake.set()
        if self.read_future is None and self.peer.can_submit():
            if self.active is not None:
                unused_id,body,original_ms,expires=self.active
                request=decode(body)
                remaining=max(1,min(original_ms,int((expires-time.time())*1000)))
                call_expiry=datetime.fromtimestamp(expires+request['timeout_ms']/1000
                    +self.runtime.budget.io_seconds,timezone.utc).isoformat()
                self.read_future=self.peer.submit('agent.read',{'kind':'read',
                    'body':base64.b64encode(body).decode('ascii'),'queue_timeout_ms':remaining,
                    'queue_expires_at':expires},call_expiry)
            elif self._read_scan is None and self._read_wake.is_set():
                self._read_wake.clear()
                self._read_scan=self._domain.submit('read.claim')

    def _complete(self):
        if self.read_future is not None and self._read_commit is None and self._read_finish is None:
            # 所有槽分配与取时先于take；取出后仅写已有key/属性，先持有完整原reply。
            slot=self._new_read_finish()
            result=self.read_future.take()
            if result is not None:
                slot['reply']=result
                self._read_finish=slot
        self._submit_read_finish()
        self._progress_domain()

    def _new_read_finish(self):
        # take尚无结果时此预留槽直接丢弃，不改变原未取出/中断路径。
        return {'reply':None,'ready':False,'payload':{
            'request_id':self.active[0] if self.active is not None else None,
            'result':None,'deadline':time.monotonic()+self.runtime.budget.io_seconds}}

    def _read_finish_payload(self):
        slot=self._read_finish
        if not slot['ready']:
            reply=slot['reply']
            if not reply['ok'] or slot['payload']['request_id'] is None:
                raise ProtocolError('control read lacks an original native terminal')
            result=reply['payload']
            if type(result) is not dict:
                raise ProtocolError('control read lacks a complete native payload')
            slot['payload']['result']=result
            slot['ready']=True
        return slot['payload']

    def _submit_read_finish(self):
        if self._read_finish is None or self._read_commit is not None:
            return
        payload=self._read_finish_payload()
        if time.monotonic() >= payload['deadline']:
            raise TimeoutError('original read result persistence deadline elapsed')
        try:
            future=self._domain.submit('read.finish',payload)
        except BufferError:
            # 背压保留同一结果与原D，后续tick重试不重新take源结果。
            return
        self._read_commit=future
        self._read_finish=None

    def notify_read(self):
        self._read_wake.set();self._wake.set()

    def run(self):
        while not self.runtime._stop.is_set():
            self._admit()
            batch=self.peer.prepare()
            self.session.send(batch.packet,time.monotonic()+self.runtime.budget.io_seconds)
            self.peer.sent(batch)
            packet=self.session.receive(time.monotonic()+self.runtime.budget.io_seconds)
            self.runtime.last_tick=self.peer.receive(packet)
            while True:
                call=self.peer.take_call()
                if call is None:
                    break
                if call['operation']=='host.binding.read':
                    self.peer.reply(call['call_seq'],self.binding)
                else:
                    self.peer.reply(call['call_seq'],error={'code':'capability_unavailable','message':'read-only capability unavailable'})
            self._complete()
            self._wake.wait(self.runtime.control_profile.poll_seconds);self._wake.clear()

    def interrupt_read(self):
        if self._read_finish is not None:
            self._submit_read_finish()
            return
        if self.active is not None and self._read_commit is None:
            self._read_commit=self._domain.submit('read.interrupt',
                {'request_id':self.active[0],'operation_id':decode(self.active[1])['operation_id']})

    def request_close(self):
        self.peer.close();self._domain.request_close()

    def close(self, deadline):
        self.request_close()
        self._domain.close(max(0,deadline-time.monotonic()))
        records=[]
        if self._read_finish is not None:
            pending=self._read_finish_payload()
            self.runtime.journal.finish_bound(pending['request_id'],pending['result'],self.binding,
                                             deadline=min(deadline,pending['deadline']))
            self._read_finish=None;self.active=None
        if self._read_commit is not None:
            self._domain_result(self._read_commit)
            self.active=None
        elif self.active is not None:
            records.append(self.active)
        if self._read_scan is not None:
            claimed=self._domain_result(self._read_scan)
            if claimed is not None:
                records.append(claimed)
        for rid,body,unused_ms,unused_expiry in records:
            if time.monotonic()>=deadline:
                raise TimeoutError('retain Journal owner for interrupted dispatch finalization')
            self.runtime.journal.interrupt_bound(rid,decode(body)['operation_id'],deadline=deadline)
        self.active=None;self._read_scan=None;self._read_commit=None
