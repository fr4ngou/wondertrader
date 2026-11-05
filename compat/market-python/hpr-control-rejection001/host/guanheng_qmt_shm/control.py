"""原base control调度：持久派发在发送前，原终态与来源提交后才ACK。"""
from __future__ import annotations
import base64
import hashlib
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
        self._read_commit_payload=None  # 原结果与持久截止，保持到域任务确认完成。
        self._abandoned_read_commit=None  # 关闭核清的原任务；不补发来源ACK。
        self._read_rejection=None  # 最近合法控制拒绝的固定枚举、状态及计数。
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
            self._persist_read_outcome(payload,payload['deadline'])
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
            if self._read_commit_payload is not None and 'control_rejection' in self._read_commit_payload:
                self._read_rejection=dict(self._read_rejection,persistence='committed')
            self._read_commit=None
            self._read_commit_payload=None
            # 先消除active再ACK；收据丢失不能用中断覆盖已提交成功。
            self.active=None
            if self.read_future is not None:
                self.read_future.ack()

    def _admit(self):
        self._progress_domain()
        if (self.read_future is not None and self.read_future.retired and self.active is None
                and self._read_commit is None and self._read_finish is None):
            # 本地not_sent可先退休运输；持久交接完成前继续持有原Future，禁止再发原ID。
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
            if slot['payload']['request_id'] is None:
                raise ProtocolError('control read lacks an original native terminal')
            if reply['ok'] is False:
                error=reply.get('error');delivery=reply.get('delivery')
                if (reply.get('payload') is not None or type(error) is not dict
                        or set(error)!={'code','message'} or type(error['code']) is not str
                        or error['code'] not in self.peer.profile.contract.ERROR_CODES
                        or type(error['message']) is not str
                        or not 1<=len(error['message'].encode('utf8'))<=self.peer.profile.contract.CONSTANTS['max_error_text_bytes']
                        or delivery not in ('replied','not_sent','unknown')):
                    raise ProtocolError('control read failure lacks a validated delivery')
                request=decode(self.active[1])
                # 合法RPC拒绝不冒充SDK终态；同一原请求交原Journal中断规则，HPR保持未知。
                rejected=dict(
                    code=error['code'],  # 原grammar的拒绝枚举，不保留来源message或异常正文。
                    delivery=delivery,  # 原ControlFuture的replied/not_sent/unknown交付事实，不升级SDK资格。
                    operation_id=request['operation_id'],  # 原持久请求操作，用于核对同一个dispatch。
                    request_sha256=hashlib.sha256(self.active[1]).hexdigest())  # 原完整请求字节SHA，不能由回复重建请求。
                slot['payload']['control_rejection']=rejected
                prior=getattr(self,'_read_rejection',None)
                self._read_rejection=dict(
                    code=error['code'],  # 最近一次合法控制拒绝码；没有原message或请求资料。
                    delivery=delivery,  # 原交付状态，单独区别原生调用与通信结果。
                    persistence='pending',  # pending等待原Journal；committed表示原持久状态已核实。
                    count=min(9007199254740991,1 if prior is None else prior['count']+1))  # 本控制代拒绝累计次数，饱和于精确JSON整数上限。
            elif reply['ok'] is True:
                result=reply['payload']
                if type(result) is not dict:
                    raise ProtocolError('control read lacks a complete native payload')
                slot['payload']['result']=result
            else:
                raise ProtocolError('control read lacks a literal outcome')
            slot['ready']=True
        return slot['payload']

    @property
    def read_rejection_diagnostic(self):
        """跨线程只复制最近固定纯值；无I/O、业务锁或请求正文，不累积事件列表。"""
        value=self._read_rejection
        return None if value is None else dict(value)

    def _persist_read_outcome(self,payload,deadline):
        """唯一域线程保存原生结果或控制拒绝；原ID/正文/派发绑定分别核验。

        拒绝没有SDK返回值，不能交finish_bound伪造原生证明。原事务已完成时只核
        已有终态，不覆盖其实际结果；正常与关闭共用此入口，提交前后异常仍保留owner。
        """
        journal=self.runtime.journal
        if 'control_rejection' not in payload:
            return journal.finish_bound(payload['request_id'],payload['result'],self.binding,deadline=deadline)
        rejected=payload['control_rejection'];rid=payload['request_id']
        record=journal.get_bound(rid,deadline=deadline)
        if (record is None or record['dispatch_binding']!=self.binding
                or record['operation_id']!=rejected['operation_id']
                or record['request_body_sha256']!=rejected['request_sha256']):
            raise ProtocolError('control rejection differs from its original dispatch')
        if record['state']=='executing':
            journal.interrupt_bound(rid,rejected['operation_id'],deadline=deadline)
        elif record['state']!='terminal':
            raise ProtocolError('control rejection has no owned dispatch state')

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
            if 'control_rejection' in payload:
                outcome='original_rejection_already_terminal'
            else:
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
            self._persist_read_outcome(pending,min(deadline,pending['deadline']))
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
