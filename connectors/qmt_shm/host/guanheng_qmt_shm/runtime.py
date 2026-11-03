"""认证只读Host：ready/binding同锁，Journal持久事实与I/O各有owner。"""
from __future__ import annotations
from dataclasses import dataclass
import math
import sqlite3
import threading
import time
from uuid import uuid4
from guanheng_qmt_shm_agent.control_messages import host_binding
from guanheng_qmt_shm_agent.control_profile import ControlProfile
from guanheng_qmt_shm_agent.protocol import TransportBudget, canonical, decode
from guanheng_qmt_shm_agent.transport import LocalTransport
from guanheng_qmt_shm_agent.read_capabilities import known_operation, validate_read_profile, operation_descriptor
from .bound import (SCHEMA, MAX_PROFILE_BYTES, MAX_METADATA_BYTES, binding, digest,
    b64, limits, decode_submission, request_id as validate_request_id)
from .control import HostControlLoop
from .journal import JournalConflict, JournalFull


@dataclass(frozen=True)
class HostResponse:
    status_code: int
    content: bytes


@dataclass(frozen=True)
class HostRequest:
    operation: str
    body: bytes = b''
    operation_id: str | None = None
    request_id: str | None = None

    def __post_init__(self):
        if not isinstance(self.body,bytes):
            raise ValueError('original HTTP body bytes required')
        if self.operation=='binding.read':
            valid=not self.body and self.operation_id is None and self.request_id is None
        elif self.operation=='bound.submit':
            valid=known_operation(self.operation_id) and self.request_id is None
        elif self.operation=='bound.result':
            validate_request_id(self.request_id)
            valid=not self.body and self.operation_id is None
        else:
            valid=False
        if not valid:
            raise ValueError('unsupported read-only Host request')


def response(status, value):
    return HostResponse(status,canonical(value))


def error(status, code):
    return response(status,{'error_code':code,'error_message':'只读接入未就绪或请求未通过准入；保留原请求标识核查'})


class HostReadRuntime:
    def __init__(self, journal, *, secret, max_frame, policies, transport,
                 control_profile, connect_seconds, io_seconds, max_http_inflight, read_profile=None,
                 wait_for_agent=False):
        if type(wait_for_agent) is not bool or (wait_for_agent and transport.get('kind')!='builtin-shm'):
            raise ValueError('persistent waiting requires explicit builtin SHM')
        self._wait_for_agent=wait_for_agent
        if type(max_http_inflight) is not int or not 1<=max_http_inflight<=128:
            raise ValueError('invalid explicit HTTP concurrency budget')
        self.max_http_inflight=max_http_inflight
        self.budget=TransportBudget(connect_seconds,io_seconds)
        if type(max_frame) is not int or not 8192<=max_frame<=4194304:
            raise ValueError('invalid frame budget')
        if journal.max_result_bytes>max_frame-4096:
            raise ValueError('result budget exceeds frame budget')
        self.control_profile=ControlProfile(control_profile,max_frame,self.budget)
        self._binding_control_version=self.control_profile.version
        self.control_profile.require_native_budgets(journal.max_result_bytes)
        if read_profile is None:
            policy=policies.require('qmt.standard-read.v1','market.full_tick')
            read_profile={'read_operations':['market.full_tick'],'execution_timeout_ms':policy.execution_timeout_ms,
                'control_profile':self.control_profile.configuration}
        profile=validate_read_profile(read_profile,max_result_bytes=journal.max_result_bytes)
        if canonical(profile['control_profile'])!=canonical(self.control_profile.configuration):
            raise ValueError('read/control profile differ')
        self._operation_policies=self._admit_operation_policies(profile,policies,journal.max_result_bytes)
        if profile['read_operations']!=['market.full_tick'] and journal.admission_profile!=profile:
            raise ValueError('Journal capability differs')
        self._profile_bytes=canonical(profile)
        self._queue_timeout_ms=max(p[1] for p in self._operation_policies.values())
        self._execution_timeout_ms=profile['execution_timeout_ms']
        if len(self._profile_bytes)>MAX_PROFILE_BYTES:
            raise ValueError('complete authenticated profile exceeds capacity')
        self._limits=limits(max_frame=max_frame,max_result_bytes=journal.max_result_bytes,
            native_body_limit=self.control_profile.native_body_limit)
        self._transport=LocalTransport(route=journal.route,secret=secret,max_frame=max_frame,
            profile=self.profile,transport=transport)
        self._secret=secret
        self.journal,self.policies,self.max_frame=journal,policies,max_frame
        self._binding_lock=threading.RLock()
        self._binding_bytes=None
        self.connected,self._stop,self._wake=threading.Event(),threading.Event(),threading.Event()
        self._worker,self._listener,self._session,self._control=None,None,None,None
        self.host_instance_id=uuid4().hex
        self.failure,self.last_tick=None,None
        self._admission_stopped=False
        self._shutdown_state={}
        self._closed_complete=False
        self.cleanup_failure=None
        self.interruption_failure=None
        self._io_resources_closed=True
        self._worker_entered=threading.Event()
        self._start_returned=False

    def _admit_operation_policies(self,profile,policies,max_result_bytes):
        result={}
        for op in profile['read_operations']:
            desc=operation_descriptor(profile,op,max_result_bytes=max_result_bytes)
            policy=policies.require(desc['policy_id'],op)
            if policy.execution_timeout_ms!=desc['execution_timeout_ms']:
                raise ValueError('operation native policy differs')
            self.control_profile.require_roundtrip(policy.queue_timeout_ms,policy.execution_timeout_ms)
            result[op]=(policy.execution_timeout_ms,policy.queue_timeout_ms)
        return result

    @property
    def binding_control_version(self):
        return self._binding_control_version

    def _channel_binding(self, session):
        # profile版本由本owner准入；Session事实及完整profile摘要保持原值。
        return binding(host_binding(route=session.route,generation=session.generation,
            host_instance_id=self.host_instance_id,journal_generation=None,observation_identity=None,
            capability_sha256=digest(self._profile_bytes),schema_version=self.binding_control_version),
            control_version=self.binding_control_version)

    def _make_control(self, session, actual_binding):
        return HostControlLoop(self,session,actual_binding)

    def _interrupt_control(self):
        self._control.interrupt_read()

    def _finalize_control(self):
        """原I/O finally的本地交接钩子；只读默认行为保持为空。"""
        pass

    def begin_shutdown(self):
        # 信号可重入本方法，Python锁可能等待被中断的owner。精确私有dict与
        # 固定内建str/float的setdefault在CPython中一次发布首个截止；后来的
        # 线程或信号只读同一值。此记录同时拥有HTTP关闭与业务停止准入事实，
        # 不能先设另一停止标记，再分开判断/覆盖截止。实际I/O由server唤醒。
        candidate=time.monotonic()+self.budget.io_seconds+1
        return self._shutdown_state.setdefault('deadline',candidate)

    @property
    def _shutdown_deadline(self):
        return self._shutdown_state.get('deadline')

    @property
    def admission_stopped(self):
        return self.shutdown_started or self._admission_stopped or self._stop.is_set()

    @property
    def shutdown_started(self):
        return self._shutdown_deadline is not None

    @property
    def profile(self):
        return decode(self._profile_bytes)

    @property
    def public_limits(self):
        return dict(self._limits)

    def require_http_credentials(self, keys):
        if (not isinstance(keys,dict) or not keys or any(not isinstance(k,str) or not 1<=len(k)<=128
                or not isinstance(v,str) or not v or v.encode('utf-8')==self._secret for k,v in keys.items())):
            raise ValueError('distinct private HTTP credentials required')

    @property
    def closed_complete(self):
        """原close已确认I/O、域线程及Journal全部关闭。"""
        return self._closed_complete

    @property
    def io_resources_closed(self):
        """仅供诊断；完整退出以close成功及closed_complete为准。"""
        return self._io_resources_closed

    @property
    def connection_ended(self):
        """单代终止事实；管理器仍须close确认全部资源关闭。"""
        return self._stop.is_set()

    def start(self):
        if self._worker is not None or self._stop.is_set():
            raise RuntimeError('Host instances have one connection generation')
        self._listener=(self._transport.listen(wait_for_peer=True)
            if self._wait_for_agent else self._transport.listen())
        deadline=time.monotonic()+self.budget.connect_seconds
        self._worker=threading.Thread(target=self._worker_entry,args=(deadline,),name='qmt-host-read-ipc',daemon=True)
        self._io_resources_closed=False
        try:
            self._worker.start()
        except BaseException:
            # OS启动可能已生效；本地停止事实立即发布，未知Thread保留到入口/join证据。
            self._admission_stopped=True
            self._stop.set();self._wake.set();self.connected.clear()
            raise
        self._start_returned=True
        self._listener.wait_ready(deadline)

    def _worker_entry(self, connect_deadline):
        self._worker_entered.set()
        self._run(connect_deadline)

    def _run(self, connect_deadline):
        try:
            if self._stop.is_set():
                return
            session=self._listener.accept(connect_deadline)
            self._session=session
            session.handshake(time.monotonic()+self.budget.io_seconds,self.profile)
            if canonical(session.route)!=canonical(self.journal.route):
                raise ValueError('authenticated Session route differs from its Journal owner')
            actual=self._channel_binding(session)
            self._control=self._make_control(session,actual)
            with self._binding_lock:
                if self.admission_stopped:
                    raise OSError('Host admission is closing')
                self._binding_bytes=canonical(actual)
                self.connected.set()
            self._control.run()
        except Exception as exc:
            if self.failure is None:
                self.failure=type(exc).__name__
            if self._control is not None:
                try:
                    self._interrupt_control()
                except BaseException as interruption:
                    if self.interruption_failure is None:
                        self.interruption_failure=type(interruption).__name__
        finally:
            # 先撤销ready；旧B只作原记录来源，不再发布为可采用快照。
            with self._binding_lock:
                self.connected.clear();self._stop.set()
            # 准入锁已释放；原I/O先交接原事实，之后才关闭domain/运输。
            try:
                self._finalize_control()
            except BaseException as interruption:
                if self.interruption_failure is None:
                    self.interruption_failure=type(interruption).__name__
                if self.failure is None:
                    self.failure='control_interrupt_unconfirmed'
            # 原I/O线程逐项释放；保留原业务failure，关闭异常不能跳过下一owner。
            failed=False
            for resource,method in ((self._control,'request_close'),
                    (self._session,'close'),(self._listener,'close')):
                if resource is not None:
                    try:
                        getattr(resource,method)()
                    except BaseException as cleanup:
                        failed=True
                        if self.cleanup_failure is None:
                            self.cleanup_failure=type(cleanup).__name__
            self._io_resources_closed=not failed

    def claim_bound(self, channel_binding):
        encoded=canonical(binding(channel_binding,control_version=self.binding_control_version))
        # 锁顺序唯一：runtime ready锁→Journal事务；锁不跨SHM等待。
        with self._binding_lock:
            if not self.connected.is_set() or self.admission_stopped or encoded!=self._binding_bytes:
                return None
            return self.journal.claim_bound(channel_binding)

    def read_binding(self):
        with self._binding_lock:
            if not self.connected.is_set() or self.admission_stopped or self._binding_bytes is None:
                return error(503,'strategy_stale')
            value={'schema_version':SCHEMA,'binding':decode(self._binding_bytes),
                'binding_sha256':digest(self._binding_bytes),'read_profile_body_b64':b64(self._profile_bytes),
                'read_profile_body_sha256':digest(self._profile_bytes),'limits':self.public_limits,'order_ready':False}
            raw=canonical(value)
            if len(raw)>MAX_METADATA_BYTES:
                raise ValueError('read binding exceeds capacity')
            return HostResponse(200,raw)

    def bound_result(self, rid):
        try:
            validate_request_id(rid)
        except ValueError:
            return error(400,'invalid_arguments')
        try:
            value=self.journal.get_bound(rid)
            if value is None:
                return error(404,'unknown_operation')
            raw=canonical(value)
            if len(raw)>self._limits['max_http_response_bytes']:
                raise ValueError('bound result exceeds response capacity')
            return HostResponse(200 if value['state']=='terminal' else 202,raw)
        except (sqlite3.Error,RuntimeError,ValueError,TypeError):
            self.fail('journal_unavailable')
            return error(503,'journal_unavailable')

    def bound_submit(self, operation, raw):
        try:
            value,body,request=decode_submission(raw,max_http_bytes=self.max_frame,
                max_request_bytes=self._limits['max_request_bytes'],profile=self.profile,operation=operation,
                max_result_bytes=self.journal.max_result_bytes)
            execution_ms,queue_ms=self._operation_policies[operation]
            if request['timeout_ms']>execution_ms:
                return error(400,'invalid_arguments')
            queue_expires_at=None  # 仅新账户读取HTTP声明原D；None保留旧调用参数与排队语义。
            if 'execution_deadline_uptime_ms' in value:
                from guanheng_qmt_shm_agent.trade_clock import SharedUptimeClock
                # 同机原D由发送者在首POST前冻结；重投只缩短首次排队，原记录查重不改期。
                utc_sample=time.time()  # 先采UTC秒再读同机uptime；采样间暂停只会收紧原D。
                remaining=value['execution_deadline_uptime_ms']-SharedUptimeClock().milliseconds()
                if remaining<=0:
                    return error(408,'request_timeout')
                queue_expires_at=utc_sample+remaining/1000
            with self._binding_lock:
                if (not self.connected.is_set() or self.admission_stopped or self._binding_bytes is None
                        or value['binding_sha256']!=digest(self._binding_bytes)):
                    return error(409,'source_binding_changed')
                options=dict(queue_timeout_ms=queue_ms)
                if queue_expires_at is not None:
                    options['queue_expires_at']=queue_expires_at
                rid=self.journal.submit_bound(body,decode(self._binding_bytes),**options)
            self._control.notify_read()
            return self.bound_result(rid)
        except JournalConflict:
            return error(409,'idempotency_conflict')
        except JournalFull:
            return error(503,'queue_full')
        except (sqlite3.Error,RuntimeError):
            self.fail('journal_unavailable')
            return error(503,'journal_unavailable')
        except (ValueError,TypeError,KeyError):
            return error(400,'invalid_arguments')

    def request(self, request):
        if not isinstance(request,HostRequest):
            raise ValueError('typed read-only Host request required')
        if request.operation=='binding.read':
            return self.read_binding()
        if request.operation=='bound.submit':
            return self.bound_submit(request.operation_id,request.body)
        return self.bound_result(request.request_id)

    def health(self):
        # 无认证诊断字段不得被消费者用作可采用来源身份。
        return {'status':'available' if self.connected.is_set() and not self.admission_stopped else 'unavailable',
            'profile':'restricted-read-only','order_ready':False,'last_tick':self.last_tick,'reason':self.failure}

    def fail(self, reason):
        self.failure=reason
        self.request_close()

    def request_close(self):
        # 先关闭所有公开准入条件并唤醒I/O。正在提交的本地事务可能持锁；
        # 非阻塞请求不能等该事务，close使用同一外层期限确认ready锁收敛。
        self._admission_stopped=True
        self._stop.set()
        self._wake.set()
        if self._binding_lock.acquire(blocking=False):
            try:self.connected.clear()
            finally:self._binding_lock.release()
        if self._session is not None:
            self._session.framer.request_close()
        if self._listener is not None:
            self._listener.request_close()

    def close(self, deadline):
        if type(deadline) not in (int,float) or not math.isfinite(deadline):
            raise ValueError('close requires absolute monotonic deadline')
        if self._closed_complete:
            return
        self.request_close()
        if not self._binding_lock.acquire(timeout=max(0,deadline-time.monotonic())):
            raise TimeoutError('Host admission transaction busy; retain all owners')
        try:self.connected.clear()
        finally:self._binding_lock.release()
        if self._worker is threading.current_thread():
            raise RuntimeError('I/O owner cannot join itself')
        if self._worker is not None:
            if not (self._start_returned or self._worker_entered.is_set()):
                raise RuntimeError('Host worker start is unconfirmed; retain all owners')
            self._worker.join(max(0,deadline-time.monotonic()))
            if self._worker.is_alive():
                raise TimeoutError('Host I/O worker busy; retain Journal and channel owners')
        if (not self._io_resources_closed or self.cleanup_failure is not None
                or self._listener is not None and self._listener.io_resources_closed is False):
            raise RuntimeError('Host I/O release is unconfirmed; retain owners for process-level disposal')
        if self._control is not None:
            self._control.close(deadline)
        if time.monotonic()>=deadline:
            raise TimeoutError('retain Journal owner until close can complete')
        self.journal.close(deadline)
        self._closed_complete=True
