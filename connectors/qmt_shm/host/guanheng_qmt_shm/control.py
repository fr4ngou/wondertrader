"""原base control调度：持久派发在发送前，原终态与来源提交后才ACK。"""
from __future__ import annotations
import base64
import hashlib
from datetime import datetime, timezone
import threading
import time
from guanheng_qmt_shm_agent.control_peer import ControlPeer
from guanheng_qmt_shm_agent.builtin_shm import PendingIO
from guanheng_qmt_shm_agent.protocol import ProtocolError, canonical, decode
from .domain import HostDomainWorker


class _ReadClaim(tuple):
    """保留原(rid,body,queue_remaining_ms,queue_expiry_utc)四元组；关闭/Bulk仍按原合同消费。"""
    def __new__(cls, active, queue_deadline, reply_deadline, wait_error=None):
        value=super().__new__(cls,active)
        object.__setattr__(value,'queue_deadline',queue_deadline)  # 领取时冻结的原排队monotonic截止，单位秒。
        object.__setattr__(value,'reply_deadline',reply_deadline)  # 原票据monotonic上界，单位秒；无票据为None，跨域不续期。
        object.__setattr__(value,'wait_error',wait_error)  # 元数据核查异常，原ID仍由四元组持有，先接管再向业务传播。
        return value

    def __setattr__(self,name,value):
        raise AttributeError('original read claim is immutable')


class HostControlLoop:
    def __init__(self, runtime, session, binding):
        self.runtime,self.session=runtime,session
        self._binding=canonical(binding)
        self.peer=ControlPeer('host',session.generation,runtime.control_profile)
        self.active,self.read_future=None,None
        self._read_queue_deadline=None  # Journal领取时冻结的monotonic原排队上界；UTC跳变不续期。
        self._read_wait_deadline=None  # Journal冻结的原票据monotonic上界；无票据为None，I/O只取min。
        self._read_reply_deadline=None  # 同一RPC提交时冻结的monotonic等待上界；后续周期不得延长。
        self._trade_wait_future=None  # 同一原金融调用对象；只关联等待窗口，不持有或改写命令。
        self._trade_wait_deadline=None  # 原命令业务D映射到monotonic后的保守截止。
        self._read_scan,self._read_commit=None,None
        self._read_finish=None
        self._read_commit_payload=None  # 原finish全文和原持久截止；与Future一起保留到确认完成。
        self._abandoned_read_commit=None  # 关闭时核清的原只读任务；保留Future/原值，不补源ACK。
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
            active=self.runtime.claim_bound(self.binding)
            if active is None:
                return None
            upper=queue_deadline=None
            try:
                sampled=time.monotonic()
                remaining=min(active[2]/1000,max(0,active[3]-time.time()))
                queue_deadline=sampled+remaining
                read_upper=getattr(self.runtime.journal,'read_reply_upper',None)
                if read_upper is not None:
                    upper=read_upper(active[0],active[1],
                        deadline=time.monotonic()+self.runtime.budget.io_seconds)
            except Exception as error:
                # 领取已发生。先交原四元组所有权，避免元数据失败使close丢失原ID。
                return _ReadClaim(active,queue_deadline,upper,error)
            return _ReadClaim(active,queue_deadline,upper)
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
            claimed=self._domain_result(self._read_scan)
            self.active=claimed
            self._read_queue_deadline=None if claimed is None else claimed.queue_deadline
            self._read_wait_deadline=None if claimed is None else claimed.reply_deadline
            self._read_scan=None
            if claimed is not None and claimed.wait_error is not None:
                self.domain_failed=True
                raise claimed.wait_error
        if self._read_commit is not None and self._read_commit.done():
            self._domain_result(self._read_commit)
            self._read_commit=None
            self._read_commit_payload=None
            # 先消除active再ACK；收据丢失不能用中断覆盖已提交成功。
            self.active=None
            self._read_queue_deadline=self._read_wait_deadline=self._read_reply_deadline=None
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
                sampled=time.monotonic()
                remaining=min(original_ms,int((self._read_queue_deadline-sampled)*1000))
                self._read_reply_deadline=self._read_queue_deadline+request['timeout_ms']/1000+self.runtime.budget.io_seconds
                if self._read_wait_deadline is not None:
                    self._read_reply_deadline=min(self._read_reply_deadline,self._read_wait_deadline)
                if remaining<=0 or sampled>=self._read_reply_deadline:
                    raise TimeoutError('original read admission deadline elapsed')
                # UTC仅编码现有RPC期限；本地等待始终沿域线程冻结的monotonic原D。
                utc=time.time()
                duration=min(self._read_reply_deadline-sampled,self.peer.profile.max_call_seconds)
                upper=utc+duration
                call_expiry=datetime.fromtimestamp(upper,timezone.utc)
                if call_expiry.timestamp()>upper:
                    from datetime import timedelta
                    call_expiry-=timedelta(microseconds=1)
                call_expiry=call_expiry.isoformat()
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
        self._read_commit_payload=payload
        self._read_finish=None

    def notify_read(self):
        self._read_wake.set();self._wake.set()

    def _reply_deadline(self, idle_deadline):
        """只等待已送出的原业务调用；多个责任取最早D，停止只能进一步收紧。"""
        ends=[]
        if (self.read_future is not None and self._read_reply_deadline is not None
                and self.read_future.delivery in ('sending','sent')):
            ends.append(self._read_reply_deadline)
        future=getattr(self,'_trade_future',None)
        record=getattr(self,'_trade_active',None)
        if future is not None and record is not None and future.delivery in ('sending','sent'):
            if future is not self._trade_wait_future:
                sampled=time.monotonic()
                self._trade_wait_deadline=sampled+record['deadline']-self.runtime.business_seconds()
                self._trade_wait_future=future
            ends.append(self._trade_wait_deadline)
        else:
            self._trade_wait_future=self._trade_wait_deadline=None
        selected=min(ends) if ends else idle_deadline
        for upper in (getattr(self.runtime,'_shutdown_deadline',None),
                      getattr(self,'_interrupt_deadline',None)):
            if upper is not None:
                selected=min(selected,upper)
        return selected

    def _receive_packet(self):
        """原builtin SHM非阻塞接缝保留单帧身份；等待可被原stop/截止立即收紧。"""
        idle_deadline=time.monotonic()+self.runtime.budget.io_seconds
        attempt=getattr(self.session.framer,'try_receive',None)
        if attempt is None:
            # 旧运输保持原单次I/O预算，不向未提供非阻塞接缝的运输授扩展等待。
            return self.session.receive(idle_deadline)
        while not self.runtime._stop.is_set():
            end=self._reply_deadline(idle_deadline)
            try:
                return self.session.incoming(attempt(end))
            except PendingIO:
                remaining=end-time.monotonic()
                if remaining<=0:
                    raise TimeoutError('original Host reply deadline elapsed')
                self._wake.wait(min(self.runtime.control_profile.poll_seconds,remaining))
                self._wake.clear()
        return None

    def run(self):
        while not self.runtime._stop.is_set():
            self._admit()
            batch=self.peer.prepare()
            self.session.send(batch.packet,time.monotonic()+self.runtime.budget.io_seconds)
            self.peer.sent(batch)
            packet=self._receive_packet()
            if packet is None:
                return
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

    def _reconcile_timed_out_read_finish(self, deadline):
        """原域已join后核同一请求；已落盘原值保留，未落盘沿原中断终态收束。

        这是关闭责任核查预算，不延长原请求/SDK/结果持久D，不重新提交finish。
        无法核清、非Timeout或身份冲突时保留原任务，继续原失败语义。
        """
        future,payload,active=self._read_commit,self._read_commit_payload,self.active
        if (future is None or not future.done() or future.cancelled()
                or not isinstance(future.exception(),TimeoutError) or payload is None or active is None
                or payload['request_id']!=active[0]
                or self.read_future is not None and not self.read_future.retired):
            return False
        rid=active[0];request=decode(active[1]);journal=self.runtime.journal
        record=journal.get_bound(rid,deadline=deadline)
        if (record is None or record['dispatch_binding']!=self.binding
                or record['operation_id']!=request['operation_id']
                or record['request_body_sha256']!=hashlib.sha256(active[1]).hexdigest()):
            return False
        if record['state']=='terminal':
            expected=canonical(payload['result'])
            if (record['result_binding']!=self.binding or record['result_body_b64'] is None
                    or base64.b64decode(record['result_body_b64'],validate=True)!=expected):
                return False
            outcome='original_result_already_terminal'
        elif record['state']=='executing':
            journal.interrupt_bound(rid,request['operation_id'],deadline=deadline)
            outcome='original_request_interrupted'
        else:
            return False
        self._abandoned_read_commit={
            'future':future,  # 原域任务及原异常对象；已经完成且域已join。
            'payload':payload,  # 原结果及原持久截止，保持原对象内容。
            'active':active,  # 原请求ID/请求字节及原SDK时限，不改变提交身份。
            'reply_future':self.read_future,  # 原运输Future；关闭退役，未补发ACK。
            'outcome':outcome}  # 只读终态核查结论，不代表源业务排空或金融完成。
        self._read_commit=self._read_commit_payload=None
        self.active=self.read_future=None
        return True

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
            try:self._domain_result(self._read_commit)
            except TimeoutError:
                if not self._reconcile_timed_out_read_finish(deadline):raise
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
