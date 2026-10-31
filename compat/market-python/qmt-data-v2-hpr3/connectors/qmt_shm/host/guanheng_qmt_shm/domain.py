"""有界Host域队列；SQLite事务属于域线程，I/O与QMT线程只交换内存。"""
from __future__ import annotations
from collections import deque
from concurrent.futures import Future
from datetime import datetime, timezone
import threading
from guanheng_qmt_shm_agent.timestamps import source_timestamp_ns
from guanheng_qmt_shm_agent.protocol import canonical, decode


class DomainCallExpired(ValueError):
    pass


class HostDomainWorker:
    def __init__(self, handler, *, max_pending, max_payload_bytes, wake, drain, name):
        if (type(max_pending) is not int or not 1 <= max_pending <= 1024
                or type(max_payload_bytes) is not int or not 4 <= max_payload_bytes <= 4194304
                or type(drain) is not bool):
            raise ValueError('invalid bounded Host domain queue')
        self._handler,self._limit,self._bytes=handler,max_pending,max_payload_bytes
        self._wake,self._drain=wake,drain
        self._condition,self._queue,self._closed=threading.Condition(),deque(),False
        self._thread=threading.Thread(target=self._run,name=name,daemon=True)
        self._thread.start()

    def submit(self, operation, payload=None, expires_at=None):
        encoded=canonical(payload)
        if len(encoded)>self._bytes:
            raise ValueError('complete Host domain input exceeds byte budget')
        if expires_at is not None:
            source_timestamp_ns(expires_at)
        future=Future()
        with self._condition:
            if self._closed:
                raise OSError('Host domain queue is closed')
            if len(self._queue)>=self._limit:
                raise BufferError('Host domain queue is full')
            self._queue.append((future,operation,encoded,expires_at))
            self._condition.notify()
        return future

    def _run(self):
        while True:
            with self._condition:
                self._condition.wait_for(lambda:self._closed or self._queue)
                if not self._queue:
                    return
                future,operation,encoded,expires_at=self._queue.popleft()
                if not future.set_running_or_notify_cancel():
                    continue
            try:
                if (expires_at is not None and source_timestamp_ns(expires_at)
                        <=source_timestamp_ns(datetime.now(timezone.utc).isoformat())):
                    raise DomainCallExpired('original local-message deadline expired')
                result=self._handler(operation,decode(encoded))
            except BaseException as exc:
                if not isinstance(exc,Exception):
                    failure=RuntimeError('Host domain callback exited unexpectedly')
                    failure.__cause__=exc
                    future.set_exception(failure)
                    self.request_close()
                else:
                    future.set_exception(exc)
            else:
                future.set_result(result)
            finally:
                self._wake.set()

    def request_close(self):
        with self._condition:
            self._closed=True
            if not self._drain:
                while self._queue:
                    self._queue.popleft()[0].cancel()
            self._condition.notify_all()

    def close(self, timeout):
        self.request_close()
        self._thread.join(timeout=timeout)
        if self._thread.is_alive():
            raise TimeoutError('Host domain worker is busy; retain its Journal owner')
