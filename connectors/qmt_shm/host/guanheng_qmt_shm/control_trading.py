"""R19 同一 Host I/O 与域 worker 的组合交易控制。

I/O 线程拥有以下有限调度状态；domain 只执行 Journal 方法并返回值。
领取后的回复先保留，再投递持久任务；满队列不消耗原值或重起原截止。
原I/O finally沿首次中断D把原事实交给同一域；管理close只join/取既有Future，不补写交易。
"""
from __future__ import annotations

import base64
import hashlib
from datetime import datetime, timedelta, timezone
import threading
import time

from guanheng_qmt_shm_agent.protocol import ProtocolError, canonical, decode
from guanheng_qmt_shm_agent.trade_clock import CLOCK_SCHEMA, deadline_milliseconds
from .bound import MAX_METADATA_BYTES, unb64
from .control import HostControlLoop
from .domain import HostDomainWorker


class HostTradingControlLoop(HostControlLoop):
    """复用父类 run/读链；每种交易或轮询阶段仅保留一个在途值。"""

    def __init__(self, runtime, session, binding):
        self._limits = runtime.trade_limits
        self._storage = runtime.event_storage
        self._jobs = {}
        self._trade_active = self._trade_future = self._trade_received = None
        self._trade_result_deadline = None
        self._trade_wake = threading.Event()
        self._trade_wake.set()
        self._poll_stage = 'idle'
        self._poll_next = None
        self._poll_future = self._poll_received = None
        self._poll_result_deadline = None
        self._poll_request = None
        self._poll_due = 0.0
        self._poll_drained = False
        self._trade_observation_epoch = object()
        self._poll_observation_epoch = None
        self._status = self._source = self._receipt = None
        self._source_continuity = None
        self._admission = {'unknown_fenced': False, 'hard_fault': None}
        self._interrupted = False
        self._interrupt_deadline = None
        self._interrupt_attempted = self._interrupt_complete = False
        self._interrupt_error = None
        self._abandoned_poll = None  # 已关闭运输上放弃的原观察；不代表域提交或源业务ACK。
        self._io_owner = threading.current_thread()
        self._close_complete = False
        super().__init__(runtime, session, binding)

    def _make_domain(self):
        maximum = max(self.runtime.journal.max_result_bytes + MAX_METADATA_BYTES,
            self._limits['max_call_result_bytes'] + MAX_METADATA_BYTES,
            4 * ((self._limits['max_command_bytes'] + 2) // 3) + MAX_METADATA_BYTES,
            4 * ((self._storage['max_page_bytes'] + 2) // 3) + MAX_METADATA_BYTES)
        return HostDomainWorker(self._journal_call, max_pending=8,
            max_payload_bytes=maximum, wake=self._wake, drain=True,
            name='qmt-host-trade-journal')

    def _journal_call(self, operation, payload):
        if not operation.startswith('trade.'):
            return super()._journal_call(operation, payload)
        deadline = payload['deadline']
        journal = self.runtime.journal
        if operation == 'trade.claim':
            return self.runtime.claim_trade(self.binding, deadline=deadline)
        if operation == 'trade.finish':
            return journal.finish_trade(payload['command_id'], payload['result'],
                self.binding, deadline=deadline)
        if operation == 'trade.interrupt':
            return journal.interrupt_trade(payload['command_id'], deadline=deadline)
        source = payload['source']
        if operation == 'trade.stream':
            receipt = (journal.events.state(source, deadline=deadline)
                if self.runtime.connection_continuity is None else journal.events.resume(source, deadline=deadline))
            facts = journal.trade_admission(deadline=deadline)
            if self.runtime.connection_continuity is not None:
                return dict(facts, **self._receipt_observation(journal, source, receipt, deadline))
            return dict(facts, receipt=receipt)
        if operation == 'trade.events.persist':
            raw = unb64(payload['body'], self._storage['max_page_bytes'])
            receipt = journal.events.ingest(source, raw, after_seq=payload['after_seq'],
                limit=payload['limit'], max_bytes=payload['max_bytes'], deadline=deadline)
            return (receipt if self.runtime.connection_continuity is None else
                self._receipt_observation(journal, source, receipt, deadline))
        if operation == 'trade.events.ack':
            raw = unb64(payload['body'], 1024)
            receipt = journal.events.acknowledge(source, raw,
                through_seq=payload['through_seq'], deadline=deadline)
            return (receipt if self.runtime.connection_continuity is None else
                self._receipt_observation(journal, source, receipt, deadline))
        raise RuntimeError('unsupported trade Journal operation')

    def _receipt_observation(self, journal, source, receipt, deadline):
        """只在原domain内核附属关系；I/O线程消费纯值，不越过唯一SQLite owner。"""
        continuity = (None if receipt is None else dict(schema_version='qmt.trade-source-continuity.v1',
            session_id=source['session_id'], binding_id=receipt['binding_id'],
            current_host_binding_sha256=hashlib.sha256(canonical(source['host_binding'])).hexdigest(),
            origin_host_binding_sha256=receipt['host_binding_sha256'],
            authenticated=journal.events.authenticated(source, deadline=deadline)))
        return dict(receipt=receipt, continuity=continuity)

    def _job(self, slot, operation, payload, deadline):
        # 原回复/active 在调用本方法前已保留；编码或分配异常不能擦除它们。
        if slot in self._jobs:
            return
        frozen = decode(canonical(dict(payload, deadline=deadline)))
        self._jobs[slot] = {'operation': operation, 'payload': frozen, 'future': None,
            'submit_uncertain': False, 'submit_error': None}

    def _interrupt_bound(self):
        deadline = self._interrupt_deadline
        shutdown = self.runtime._shutdown_deadline
        return deadline if shutdown is None else min(deadline, shutdown)

    def _result_deadline(self, original):
        if original is None:
            return self._interrupt_bound() if self._interrupted else time.monotonic() + self.runtime.budget.io_seconds
        return min(original, self._interrupt_bound()) if self._interrupted else original

    def _offer_job(self, job):
        if job['future'] is not None:
            return True
        if job['submit_uncertain']:
            error = job['submit_error']
            if error is not None:
                raise error
            raise RuntimeError('Host domain submission outcome is unconfirmed')
        payload = job['payload']
        deadline = payload['deadline']
        if self._interrupted:
            # 准入检查同时受首次失联D约束；已创建任务实际提交仍携原payload/首次D。
            deadline = min(deadline, self._interrupt_bound())
        if time.monotonic() >= deadline:
            raise TimeoutError('original trade domain deadline elapsed')
        # submit可在queue.append之后notify/return失败；未拿到Future不能等同未入域。
        job['submit_uncertain'] = True
        try:
            future = self._domain.submit(job['operation'], payload)
        except BufferError:
            # 原domain唯一BufferError在入队前容量检查；同槽/同D等待，不重取结果。
            job['submit_uncertain'] = False
            return False
        except BaseException as error:
            job['submit_error'] = error
            raise
        job['future'] = future
        job['submit_uncertain'] = False
        return True

    def _offer_jobs(self):
        for job in self._jobs.values():
            if not self._offer_job(job):
                return

    def _invalidate_trade_observation(self):
        # 旧 status/空页可能晚于新 SDK 结果到达；新的交易事实使整轮候选失效。
        # token 只由本 I/O owner 使用，不加入 wire 或改变源事件前沿。
        self._trade_observation_epoch = object()
        self._poll_drained = False

    def _record(self, record):
        if record is not None:
            self._invalidate_trade_observation()
            if self._interrupted:
                self.runtime.note_trade_record(record, deadline=self._interrupt_bound())
            else:
                self.runtime.note_trade_record(record)
            self._admission['unknown_fenced'] = self._admission['unknown_fenced'] or record['state'] == 'unknown'

    def _finish_job(self, slot, job, value):
        operation = job['operation']
        if operation == 'trade.claim':
            self._trade_active = value
            self._record(value)
        elif operation in ('trade.finish', 'trade.interrupt'):
            self._record(value)
            # 先移除已提交 active，再 ACK；后继运输失败不能把成功改成中断。
            self._trade_active = None
            self._trade_received = None
            self._trade_result_deadline = None
            del self._jobs[slot]
            if self._trade_future is not None:
                self._trade_future.ack()
            return
        elif operation == 'trade.stream':
            self._receipt = value['receipt']
            if self.runtime.connection_continuity is not None:
                self._source_continuity = value['continuity']
            self._admission['unknown_fenced'] = self._admission['unknown_fenced'] or value['unknown_fenced']
            if self._admission['hard_fault'] is None:
                self._admission['hard_fault'] = value['hard_fault']
            if not self._interrupted:
                self.runtime.observe_source(self._status, self._receipt, self._admission,
                    continuity=self._source_continuity)
            self._poll_next = 'ack' if self._needs_ack() else 'page'
        else:
            if self.runtime.connection_continuity is not None:
                self._receipt, self._source_continuity = value['receipt'], value['continuity']
            else:
                self._receipt = value
            if not self._interrupted:
                self.runtime.observe_source(self._status, self._receipt, self._admission,
                    continuity=self._source_continuity)
            self._poll_next = 'ack' if self._needs_ack() else 'finish'
        del self._jobs[slot]
        if slot == 'poll':
            self._poll_stage = 'retiring'
            self._poll_future.ack()

    def _progress_jobs(self, failures=None):
        for slot, job in tuple(self._jobs.items()):
            if failures is not None and slot in failures:
                continue
            try:
                if job['future'] is not None and job['future'].done():
                    value = self._domain_result(job['future'])
                    self._finish_job(slot, job, value)
            except BaseException as error:
                if failures is None:
                    raise
                if slot == 'poll' and self._abandon_timed_out_poll():
                    continue
                failures[slot] = error
                self._retain_interrupt_error(error)

    def _abandon_timed_out_poll(self):
        """仅失联后放弃已退休运输的只读观察，原持久前沿留给同Journal重连核验。"""
        job = self._jobs.get('poll')
        if (not self._interrupted or job is None or self._poll_future is None
                or not self._poll_future.retired or self._poll_received is None
                or self._poll_received.get('ok') is not True):
            return False
        operations = {'status': 'trade.stream', 'page': 'trade.events.persist', 'ack': 'trade.events.ack'}
        if operations.get(self._poll_stage) != job['operation'] or job['submit_uncertain']:
            return False
        future = job['future']
        if future is None:
            if time.monotonic() < job['payload']['deadline']:
                return False
            reason = 'not_admitted_before_deadline'
        else:
            if (not future.done() or future.cancelled()
                    or not isinstance(future.exception(), TimeoutError)):
                return False
            # 域已经结束；事务可能已提交，原Journal是唯一事实，不重做本次事务。
            reason = 'domain_timeout_completed'
        # peer.close已把运输结果标为retired/abandoned。这里不调用Future.ack，
        # 不发送agent.trade.ack，源端事件和既有Host ACK意图均保留供同Journal接续。
        self._abandoned_poll = {'job': job, 'reply': self._poll_received,
            'future': self._poll_future, 'reason': reason}
        del self._jobs['poll']
        self._poll_future = self._poll_received = None
        self._poll_result_deadline = self._poll_request = self._poll_next = None
        self._poll_stage, self._poll_drained = 'idle', False
        return True

    def _progress_domain(self):
        super()._progress_domain()
        self._progress_jobs()

    def _needs_ack(self):
        return (self._receipt is not None
            and self._receipt['source_ack_through'] < self._receipt['ack_intended_through'])

    def notify_trade(self):
        self._trade_wake.set()
        self._wake.set()

    def _retire(self):
        if (self._trade_future is not None and self._trade_active is None
                and 'trade' not in self._jobs and self._trade_future.retired):
            self._trade_future = None
            self.notify_trade()
        if (self._poll_stage == 'retiring' and self._poll_future.retired):
            self._poll_future = self._poll_received = None
            self._poll_result_deadline = None
            next_stage = self._poll_next
            self._poll_next = None
            if next_stage == 'finish':
                self._poll_stage = 'idle'
                self._poll_due = time.monotonic() + self.runtime.event_poll_seconds
            else:
                self._poll_stage = next_stage

    def _call_expiry(self, original_upper=None):
        # 与 peer 寿命校验使用同一个 UTC clock。RFC3339 datetime 只有微秒
        # 精度；向下量化不可表达的上界，避免四舍五入把 max 寿命放大。
        now = self.peer._utc()
        maximum = self.runtime.control_profile.max_call_seconds
        upper = now + maximum
        if original_upper is not None:
            upper = min(upper, original_upper)
        instant = datetime.fromtimestamp(upper, timezone.utc)
        if instant.timestamp() > upper or instant.timestamp() - now > maximum:
            instant -= timedelta(microseconds=1)
        return instant.isoformat()

    def _start_poll(self):
        # 逻辑shutdown仍排空原观察；只有物理关闭/中断停止创建新的观察RPC。
        if self._interrupted or self._poll_future is not None or 'poll' in self._jobs:
            return
        if self._poll_stage == 'idle':
            if time.monotonic() < self._poll_due:
                return
            self._poll_stage = 'status'
        if not self.peer.can_submit():
            return
        stage = self._poll_stage
        if stage == 'status':
            self._poll_observation_epoch = self._trade_observation_epoch
            payload = {}
        elif stage == 'page':
            payload = {'session_id': self._source['session_id'],
                'after_seq': 0 if self._receipt is None else self._receipt['durable_through'],
                'limit': self._limits['max_events'], 'max_bytes': self._storage['max_page_bytes']}
        elif stage == 'ack':
            payload = {'session_id': self._source['session_id'],
                'through_seq': self._receipt['ack_intended_through']}
        else:
            return
        operation = {'status': 'agent.trade.status', 'page': 'agent.trade.events',
                     'ack': 'agent.trade.ack'}[stage]
        self._poll_request = payload
        expires = self._call_expiry()
        self._poll_future = self.peer.submit(operation, payload, expires)
        self._poll_drained = False

    def _start_trade(self):
        if self._trade_future is not None or 'trade' in self._jobs or self._interrupted:
            return
        if self._trade_active is not None:
            record = self._trade_active
            if self.runtime.business_seconds() >= record['deadline']:
                self._job('trade', 'trade.interrupt', {'command_id': record['command_id']},
                    time.monotonic() + self.runtime.budget.io_seconds)
                return
            if self.peer.can_submit():
                payload = {'kind': 'trade', 'body': base64.b64encode(record['body']).decode('ascii'),
                    'clock_schema': CLOCK_SCHEMA, 'deadline_ms': deadline_milliseconds(record['deadline'])}
                # 原业务 D 始终在 payload 中；RPC 寿命只允许收紧原 UTC 上界。
                expires = self._call_expiry(record['expires_at'] + self.runtime.budget.io_seconds)
                self._invalidate_trade_observation()
                self._trade_future = self.peer.submit('agent.trade', payload, expires)
        elif (self._trade_wake.is_set() and (self.runtime.accepting_commands or self.runtime.accepting_cancels)
                and self.peer.can_submit()):
            # 清标记在提交前；并发新受理的 set 不会被空 claim 的结果擦除。
            self._trade_wake.clear()
            self._job('trade', 'trade.claim', {}, time.monotonic() + self.runtime.budget.io_seconds)

    def _collect_trade(self):
        if self._trade_future is None or self._trade_active is None or 'trade' in self._jobs:
            return
        if self._trade_received is None:
            self._trade_received = self._trade_future.take()
            if self._trade_received is None:
                return
            self._trade_result_deadline = self._result_deadline(self._trade_result_deadline)
        received = self._trade_received
        payload = {'command_id': self._trade_active['command_id']}
        operation = 'trade.interrupt'
        if received['ok']:
            operation = 'trade.finish'
            payload['result'] = received['payload']
        self._job('trade', operation, payload, self._result_deadline(self._trade_result_deadline))

    def _collect_poll(self):
        if (self._poll_future is None or 'poll' in self._jobs
                or self._poll_stage == 'retiring'):
            return
        if self._poll_received is None:
            self._poll_received = self._poll_future.take()
            if self._poll_received is None:
                return
            self._poll_result_deadline = self._result_deadline(self._poll_result_deadline)
        received = self._poll_received
        if not received['ok']:
            if not self._interrupted or received['payload'] is not None:
                raise ProtocolError('source trade observation was not delivered')
            # 上面的job守卫保证没有待提交事实；peer.close保留已有成功value，
            # 只为未交付观察生成失败。这里退休RPC，不确认源业务ACK或源排空。
            self._poll_future.ack()
            self._poll_future = self._poll_received = None
            self._poll_result_deadline = self._poll_request = self._poll_next = None
            self._poll_stage = 'idle'
            self._poll_drained = False
            return
        value = received['payload']
        if self._poll_stage == 'status':
            status = self.runtime.validate_source_status(value)
            source = {'host_binding': self.binding, 'session_id': status['session_id']}
            if self._source is not None and canonical(source) != canonical(self._source):
                raise ProtocolError('source trade session changed')
            self._source, self._status = source, status
            self._job('poll', 'trade.stream', {'source': source}, self._result_deadline(self._poll_result_deadline))
        elif self._poll_stage == 'page':
            raw = canonical(value)
            request = self._poll_request
            self._job('poll', 'trade.events.persist', {'source': self._source,
                'body': base64.b64encode(raw).decode('ascii'), 'after_seq': request['after_seq'],
                'limit': request['limit'], 'max_bytes': request['max_bytes']}, self._result_deadline(self._poll_result_deadline))
            # 同一观察轮跨过 claim/SDK/结果提交即失效；晚收旧空页不能覆盖
            # 失效状态。实际交易待办排空后须重新 status→page，随后再核两层 ACK。
            self._poll_drained = (self._poll_observation_epoch is self._trade_observation_epoch
                and self._trade_active is None and self._trade_future is None
                and 'trade' not in self._jobs
                and not value.get('events') and self._status['queued'] == 0
                and not self._status['executing'] and self._status['events']['inflight'] == 0
                and self._status['events']['retained'] == 0)
        elif self._poll_stage == 'ack':
            self._job('poll', 'trade.events.ack', {'source': self._source,
                'body': base64.b64encode(canonical(value)).decode('ascii'),
                'through_seq': self._poll_request['through_seq']}, self._result_deadline(self._poll_result_deadline))

    def _drained(self):
        return (self._poll_drained and self._poll_stage == 'idle' and not self._jobs
            and self._trade_active is None and self._trade_future is None
            and self.active is None and self.read_future is None
            and self._read_scan is None and self._read_commit is None and not self._needs_ack())

    def _admit(self):
        super()._admit()
        self._retire()
        self._offer_jobs()
        self._start_trade()
        self._start_poll()
        self._offer_jobs()

    def _complete(self):
        super()._complete()
        self._collect_trade()
        self._collect_poll()
        self._offer_jobs()
        self._progress_domain()
        self._retire()
        self.runtime.advance_trade_shutdown(self._drained())

    def interrupt_trade(self):
        """异常入口只冻结一次收尾 D；父 runtime 另调用原 interrupt_read。"""
        self._interrupted = True
        if self._interrupt_deadline is None:
            self._interrupt_deadline = time.monotonic() + self.runtime.budget.io_seconds
        self._wake.set()

    def _retain_interrupt_error(self, error):
        if self._interrupt_error is None:
            self._interrupt_error = error

    def _local_interrupt_complete(self):
        # 金融持久交接保持；已退休的只读观察允许明确放弃，不授提交/源排空/ACK。
        return (not self._jobs and self._trade_active is None
            and self._trade_future is None and self._poll_future is None)

    def _interrupt_pending(self, failures):
        if any(slot not in failures for slot in self._jobs):
            return True
        if (self._trade_active is not None and 'trade' not in self._jobs
                and 'trade.collect' not in failures):
            return True
        if (self._poll_future is not None and 'poll' not in self._jobs
                and self._poll_stage != 'retiring' and 'poll.collect' not in failures):
            return True
        return False

    def finalize_interrupt(self):
        """原I/O finally在domain仍可受理时，沿首次D提交原ID的持久收尾。"""
        if threading.current_thread() is not self._io_owner:
            raise RuntimeError('only the original I/O owner can finalize interruption')
        if self._interrupt_attempted:
            if self._interrupt_error is not None:
                raise self._interrupt_error
            return
        self.interrupt_trade()
        self._interrupt_attempted = True
        failures = {}
        try:
            try:
                # 已有成功_value保持；只给没有结果的原Future补运输失败。
                self.peer.close()
            except BaseException as error:
                self._retain_interrupt_error(error)
            while True:
                self._wake.clear()
                self._abandon_timed_out_poll()
                self._progress_jobs(failures)
                job = self._jobs.get('trade')
                if (job is not None and job['operation'] == 'trade.claim'
                        and job['future'] is None and not job['submit_uncertain']):
                    # 明确未受理的claim没有派发责任；未知提交保原槽/domain，绝不猜ID。
                    del self._jobs['trade']
                for slot, collect in (('trade.collect', self._collect_trade),
                        ('poll.collect', self._collect_poll)):
                    if slot not in failures:
                        try:
                            collect()
                        except BaseException as error:
                            failures[slot] = error
                            self._retain_interrupt_error(error)
                if (self._trade_active is not None and self._trade_future is None
                        and 'trade' not in self._jobs and 'trade.collect' not in failures):
                    try:
                        self._job('trade', 'trade.interrupt',
                            {'command_id': self._trade_active['command_id']}, self._interrupt_bound())
                    except BaseException as error:
                        failures['trade.collect'] = error
                        self._retain_interrupt_error(error)
                for slot, job in tuple(self._jobs.items()):
                    if slot in failures:
                        continue
                    try:
                        self._offer_job(job)
                    except BaseException as error:
                        if slot == 'poll' and self._abandon_timed_out_poll():
                            continue
                        failures[slot] = error
                        self._retain_interrupt_error(error)
                self._progress_jobs(failures)
                try:
                    self._retire()
                except BaseException as error:
                    self._retain_interrupt_error(error)
                    failures['retire'] = error
                if self._local_interrupt_complete():
                    break
                if not self._interrupt_pending(failures):
                    break
                remaining = self._interrupt_bound() - time.monotonic()
                if remaining <= 0:
                    self._retain_interrupt_error(TimeoutError('original Host interruption deadline elapsed'))
                    break
                self._wake.wait(min(remaining, self.runtime.control_profile.poll_seconds))
            if not self._local_interrupt_complete() and self._interrupt_error is None:
                self._retain_interrupt_error(RuntimeError('Host interruption retains unconfirmed domain facts'))
        except BaseException as error:
            self._retain_interrupt_error(error)
        try:
            if time.monotonic() >= self._interrupt_bound():
                self._retain_interrupt_error(TimeoutError('original Host interruption deadline elapsed'))
        except BaseException as error:
            self._retain_interrupt_error(error)
        if self._interrupt_error is not None:
            raise self._interrupt_error
        self._interrupt_complete = True

    def request_close(self):
        """仅冻结/通知物理关闭；不在管理线程中运行收尾调度或Journal事务。"""
        first = None
        try:
            self.interrupt_trade()
        except BaseException as error:
            first = error
        for close in (self.peer.close, self._domain.request_close):
            try:
                close()
            except BaseException as error:
                if first is None:
                    first = error
                elif error is not first:
                    first.__cause__ = error
        if first is not None:
            raise first

    def close(self, deadline):
        if self._close_complete:
            return
        parent_failure = None
        try:
            super().close(deadline)
        except BaseException as error:
            parent_failure = error
            try:
                self._domain.close(max(0, deadline - time.monotonic()))
            except BaseException as join_failure:
                # 同域未join时所有原Future/Journal仍有owner，禁止管理线程抢写。
                raise parent_failure from join_failure
        # I/O已经退出，管理close只观察已经完成的原Future；不再collect/submit/补事务。
        failures = {}
        self._progress_jobs(failures)
        failure = self._interrupt_error
        if failure is None and (not self._interrupt_complete or not self._local_interrupt_complete()):
            failure = RuntimeError('trade interruption was not confirmed by the I/O owner')
        if parent_failure is not None:
            if failure is not None:
                raise parent_failure from failure
            raise parent_failure
        if failure is not None:
            raise RuntimeError('trade close retains unconfirmed domain facts') from failure
        self._close_complete = True
