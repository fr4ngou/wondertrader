"""应用拥有的固定读取线程；有界队列与绝对截止不随排队或基准查询续期。"""

from concurrent.futures import Future
from queue import Empty, Full, Queue
from threading import Lock, Thread
from time import monotonic

from .thread_owner import ThreadOwner


class ReadCapacityError(RuntimeError):
    pass


class BoundedReader:
    def __init__(self, workers=2, capacity=4):
        self._queue = Queue(maxsize=capacity)
        self._lock = Lock()
        self._accepting = self._started = self._closing = False
        # 构造阶段只分配普通对象，应用先发布owner，再在受保护启动阶段start。
        self._threads = [ThreadOwner(target=self._work, name=f"guanheng-read-{n}",
                                     daemon=True, thread_factory=Thread) for n in range(workers)]

    def start(self):
        """显式启动一次；部分启动失败时关准入，已发布owner由应用finally回收。"""
        with self._lock:
            if self._started or self._closing:
                raise ReadCapacityError("读取执行器已经启动或正在关闭")
            self._started = self._accepting = True
            try:
                for thread in self._threads:
                    thread.start()
            except BaseException:
                self._accepting = False
                raise

    def submit(self, operation, deadline):
        future = Future()
        with self._lock:
            if not self._accepting:
                raise ReadCapacityError("读取执行器已停止")
            try:
                self._queue.put_nowait((future, operation, deadline))
            except Full:
                raise ReadCapacityError("读取队列已满") from None
        return future

    def _work(self):
        while True:
            try:
                future, operation, deadline = self._queue.get(timeout=0.025)
            except Empty:
                with self._lock:
                    if not self._accepting:
                        return
                continue
            try:
                if future.set_running_or_notify_cancel():
                    remaining = deadline - monotonic()
                    if remaining <= 0:
                        future.set_exception(TimeoutError("读取截止已到"))
                    else:
                        try:
                            future.set_result(operation(remaining))
                        except BaseException as exc:
                            future.set_exception(exc)
            finally:
                self._queue.task_done()

    def close(self, timeout):
        deadline = monotonic() + max(0, timeout)
        cancel_errors, pending = [], []
        # 锁只保护准入和出队；Future取消回调在锁外执行，允许回调读取关闭状态。
        with self._lock:
            self._accepting = False
            self._closing = True
            while True:
                try:
                    future, _, _ = self._queue.get_nowait()
                except Empty:
                    break
                pending.append(future)
        for future in pending:
            try:
                future.cancel()
            except BaseException as exc:
                cancel_errors.append(exc)
            finally:
                try:
                    self._queue.task_done()
                except BaseException as exc:
                    cancel_errors.append(exc)
        # 逐个续核；一个unknown不能跳过其他已启动线程的回收。
        joined = [thread.join_until(deadline) for thread in self._threads]
        if len(cancel_errors) == 1:
            raise cancel_errors[0]
        if cancel_errors:
            raise BaseExceptionGroup("读取队列关闭异常", cancel_errors)
        return all(joined)

    @property
    def live_threads(self):
        return sum(thread.pending for thread in self._threads)
