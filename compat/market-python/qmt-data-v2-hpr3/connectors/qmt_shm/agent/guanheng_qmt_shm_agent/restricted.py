# -*- coding: utf-8 -*-
"""本发行只读Agent：内存准入、认证I/O、原策略线程执行，各自拥有状态。

原八字段请求及native终态保持v1字节语义。SDK调用只能测量超期，
Python线程无法强制打断QMT原生调用；该边界不会声明调用已撤回。
"""
import base64
from datetime import datetime, timezone
import math
import queue
import threading
import time
from .adapters import QMTBindings, StockOperationAdapters
from .read_configuration import validate_read_configuration
from .control_agent import AgentControlLoop
from .encoding import ConversionBudget, to_json_value
from .errors import GatewayError
from .protocol import ProtocolError, canonical, decode
from .transport import LocalTransport
from .read_capabilities import (validate_read_request, operation_descriptor, HISTORY, ACCOUNT, PREPARATION)
from .history_1m import History1mAdapter
from .account_query import AccountQueryAdapter, account_projection_version
from .results import finalize_result
from .completion import MemoryCompletion as _ReadCompletion

class RestrictedReadAgent(object):
    def __init__(self, context, *, trusted_bootstrap, trade_detail_query=None):
        admitted = validate_read_configuration(trusted_bootstrap)
        self._initialize(context, admitted, trade_detail_query)

    def _initialize(self, context, admitted, trade_detail_query):
        """显式子类复用已准入布局及读owner；公开只读构造仍只接受旧配置。"""
        value, profile = admitted.value, admitted.profile
        self.route, self.budget = admitted.route, admitted.budget
        self.control_profile = admitted.control_profile
        self._profile_bytes = canonical(profile)
        max_frame, max_pending, max_result = value['max_frame'], value['max_pending'], value['max_result_bytes']
        secret = admitted.secret
        history_adapter, account_adapter = None, None
        if HISTORY in profile['read_operations']:
            history_adapter = History1mAdapter(context,
                operation_descriptor(profile, HISTORY, max_result_bytes=max_result)['limits'], max_result)
        if ACCOUNT in profile['read_operations']:
            # 账户权限与固定只读callable缺一不可；在连接及SDK调用前拒绝。
            if not callable(trade_detail_query):
                raise ValueError('account read requires its explicit read-only callable')
            descriptor = operation_descriptor(profile, ACCOUNT, max_result_bytes=max_result)
            account_adapter = AccountQueryAdapter(trade_detail_query, descriptor['limits'], max_result,
                projection_version=account_projection_version(descriptor['policy_version']))
        self.bindings = QMTBindings(context)
        self.adapters = StockOperationAdapters(history_adapter, account_adapter=account_adapter)
        self._thread_id = threading.get_ident()
        self._transport = LocalTransport(route=self.route, secret=secret, max_frame=max_frame,
            profile=self.profile, transport=value["transport"])
        self._max_frame, self._max_result = max_frame, max_result
        self._queue = queue.Queue(maxsize=max_pending)
        self._stop, self.connected = threading.Event(), threading.Event()
        self._worker, self._channel, self._control = None, None, None
        self.last_tick, self.failure = None, None
        self.cleanup_failure = None
        self._retryable_failure = False
        self._io_resources_closed = True
        self._worker_entered = threading.Event()
        self._start_returned = False

    @property
    def profile(self):
        return decode(self._profile_bytes)

    def start(self):
        if self._worker is not None or self._stop.is_set():
            raise RuntimeError("Agent instances have one connection generation")
        # 先持有Thread；constructor失败时尚无线程owner，也未改变资源状态。
        self._worker = threading.Thread(target=self._worker_entry, name="qmt-read-ipc", daemon=True)
        self._io_resources_closed = False
        try:
            self._worker.start()
        except BaseException:
            # start可在OS线程创建后抛错；禁止由ident/is_alive猜测无线程。
            self._stop.set()
            self.connected.clear()
            raise
        self._start_returned = True

    def _worker_entry(self):
        # 标准Thread在调用target前已发布_started；入口仅授权join，不代表退出。
        self._worker_entered.set()
        self._run()

    def _run(self):
        try:
            if self._stop.is_set():
                return
            session = self._transport.connect(time.monotonic() + self.budget.connect_seconds, self._stop)
            self._channel = session
            actual = session.handshake(time.monotonic() + self.budget.io_seconds)
            if actual != self.profile:
                raise ProtocolError("authenticated profile differs from trusted read scope")
            self._control = self._make_control(session)
            self.connected.set()
            self._control.run()
        except Exception as exc:
            self.failure = type(exc).__name__
            # 仅真实内建运输异常授只读重连；认证/协议/未知异常仍失败关闭。
            self._retryable_failure = type(exc) in (OSError, TimeoutError, BrokenPipeError, ConnectionResetError)
        finally:
            self.connected.clear()
            self._stop.set()
            # 同一原I/O线程逐项收口；connect未交回channel时仍关闭半连接owner。
            failed = False
            for resource in (self._control, self._channel, self._transport):
                if resource is not None:
                    try:
                        resource.close()
                    except BaseException as cleanup:
                        failed = True
                        if self.cleanup_failure is None:
                            self.cleanup_failure = type(cleanup).__name__
            self._io_resources_closed = not failed

    def _make_control(self, session):
        return AgentControlLoop(self, session)

    def _decode_read(self, message):
        """共用封套准入；显式补齐子类仅在原队列前登记任务身份。"""
        if (not isinstance(message, dict) or set(message) != {"kind", "body", "queue_timeout_ms", "queue_expires_at"}
                or message["kind"] != "read" or not isinstance(message["body"], str)
                or type(message["queue_timeout_ms"]) is not int
                or not 1 <= message["queue_timeout_ms"] <= 300000
                or type(message["queue_expires_at"]) not in (int, float)
                or not 0 <= message["queue_expires_at"] <= 253402300799
                or not math.isfinite(message["queue_expires_at"])):
            raise ProtocolError("unsupported read message")
        body = base64.b64decode(message["body"], validate=True)
        request = decode(body)
        validate_read_request(request, self.profile, max_result_bytes=self._max_result)
        started = time.monotonic()
        remaining_ms = min(message["queue_timeout_ms"], max(0, int((message["queue_expires_at"] - time.time()) * 1000)))
        return request, started, remaining_ms

    def _enqueue_read(self, message):
        """Both explicit protocols feed this one validated native read queue."""
        request, started, remaining_ms = self._decode_read(message)
        future = _ReadCompletion()
        self._queue.put_nowait((request, started, remaining_ms, future))
        return request, future

    def _execute_request(self, request, deadline):
        """SDK执行接缝仍由原tick拥有；专用子类只扩展显式操作。"""
        return self.adapters.execute(request['operation_id'], self.bindings, request['arguments'], deadline=deadline)

    def tick(self, allow_heavy=True):
        """At most one native read, on the original binding thread, with zero I/O."""
        if threading.get_ident() != self._thread_id:
            raise RuntimeError("native reads belong to the QMT strategy thread")
        self.last_tick = time.time()
        if type(allow_heavy) is not bool:
            raise ValueError("native read heavy-task permission must be a literal bool")
        if self._stop.is_set() or not self.connected.is_set():
            return False
        if not allow_heavy:
            return False
        try:
            request, queued_at, queue_timeout_ms, future = self._queue.get_nowait()
        except queue.Empty:
            return False
        start = time.monotonic()
        deadline = start + request['timeout_ms']/1000.0
        result = {"request_id": request["request_id"], "operation_id": request["operation_id"],
                  "ok": False, "completed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                  "queue_wait_ms": max(0, int((start - queued_at) * 1000)), "execution_ms": 0}
        try:
            if result["queue_wait_ms"] >= queue_timeout_ms:
                result.update(error_code="queue_timeout", error_message="读取在执行前已过期")
            else:
                # Both old and restricted entry points use exactly this adapter.
                validate_read_request(request,self.profile,max_result_bytes=self._max_result)
                data = self._execute_request(request, deadline)
                result["execution_ms"] = max(0, int((time.monotonic() - start) * 1000))
                if result["execution_ms"] > request["timeout_ms"]:
                    result.update(error_code="execution_timeout", error_message="原生读取超过执行预算")
                else:
                    safe_data = to_json_value(data, budget=ConversionBudget(self._max_result, self._max_result))
                    result.update(ok=True, data=safe_data)
        except GatewayError as exc:
            result.update(error_code=exc.code, error_message=exc.message)
        except Exception:
            result.update(error_code="qmt_call_failed", error_message="原生读取失败")
        if request['operation_id'] in (HISTORY, ACCOUNT, PREPARATION):
            result['execution_ms']=max(0,int((time.monotonic()-start)*1000))
        result["completed_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        sealed = finalize_result(result, self._max_result)
        if request['operation_id'] in (HISTORY, ACCOUNT, PREPARATION) and sealed['ok'] and time.monotonic()>=deadline:
            # 封装期间到期：同owner/同finalizer替换尚未发布的成功，SDK不重调。
            result.update(ok=False,data=None,error_code='execution_timeout',error_message=('历史读取已超出同一执行截止，原生调用状态按原ID核查' if request['operation_id']==HISTORY
                    else '账户读取已超出同一执行截止，原生调用状态按原ID核查'),
                completed_at=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
                execution_ms=max(0,int((time.monotonic()-start)*1000)))
            sealed=finalize_result(result,self._max_result)
        future.publish(sealed)
        return True


    def request_close(self):
        """策略stop只关内存准入并唤醒；I/O finally仍独占view/句柄释放。"""
        self._stop.set()
        self.connected.clear()
        if self._control is not None:
            self._control.peer.close()
        if self._channel is not None:
            self._channel.framer.request_close()
        while True:
            try:
                unused_request, unused_time, unused_budget, future = self._queue.get_nowait()
            except queue.Empty:
                break
            future.cancel()

    def close(self, deadline):
        """管理线程使用原绝对单一期限；超时保留worker/channel供后续确认。"""
        if type(deadline) not in (int,float) or not math.isfinite(deadline):
            raise ValueError("close requires an absolute monotonic deadline")
        self.request_close()
        if self._worker is threading.current_thread():
            raise RuntimeError("I/O owner cannot join itself")
        if self._worker is not None:
            if not (self._start_returned or self._worker_entered.is_set()):
                raise RuntimeError("Agent worker start is unconfirmed; retain its owner")
            self._worker.join(max(0, deadline-time.monotonic()))
            if self._worker.is_alive():
                raise TimeoutError("Agent I/O worker is busy; retain its owner")
        if not self._io_resources_closed or self.cleanup_failure is not None:
            # 线程退出不能代替view/句柄释放；管理线程不接管原I/O owner的资源。
            raise RuntimeError("Agent I/O resource release is unconfirmed; retain owner for process-level disposal")

    @property
    def close_requested(self):
        """只读停止准入事实；不代表I/O退出或句柄已经释放。"""
        return self._stop.is_set()

    @property
    def io_exited(self):
        """只读join前置：未知start仍保owner，最终资源证明由原close负责。"""
        worker = self._worker
        if worker is None:
            return True
        if not (self._start_returned or self._worker_entered.is_set()):
            return False
        return not worker.is_alive()

    @property
    def retryable_failure(self):
        """只读异常分类；它不授资源释放或业务请求重放资格。"""
        return self._retryable_failure
