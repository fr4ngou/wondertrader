"""标准Thread的启动归属与真实join证明；业务取消和资源释放仍由调用者拥有。"""

import math
from threading import Event, Thread, current_thread
from time import monotonic


class ThreadOwner:
    """一个线程的一次启动，保留启动未知及未确认退出状态。

    调用方在start前保存本对象，并用自己的生命周期锁串行准入与关闭；
    有预算的join_until须在业务锁外调用；锁内仅允许零等待续核。
    pending表示尝试启动后尚未取得join证明，
    包含启动异常、目标已返回及join异常。未调用start的对象没有OS副作用。
    False时保留对象及业务依赖；thread_factory只替换同一标准Thread契约。
    """

    def __init__(self, *, target, args=(), name=None, daemon=False, thread_factory=Thread):
        self._target, self._args = target, args
        self._entered = Event()
        self._attempted = self._start_returned = self._joined = False
        # 标准Thread构造不启动OS线程；构造成功后由调用者先持有本owner再start。
        self._thread = thread_factory(target=self._run, args=(), name=name, daemon=daemon)

    def _run(self):
        # 标准bootstrap已准入，业务target尚未取任何owner锁；可安全等待标准join。
        self._entered.set()
        try:
            self._target(*self._args)
        finally:
            self._target, self._args = None, ()

    def start(self):
        """启动仅尝试一次；异常继续由业务层解释，本对象始终保留潜在线程。"""
        if self._attempted:
            raise RuntimeError("线程owner已经尝试启动")
        self._attempted = True
        self._thread.start()
        self._start_returned = True

    @property
    def pending(self):
        return self._attempted and not self._joined

    def join_until(self, deadline, *, clock=monotonic):
        """同一monotonic绝对截止内取得标准join证明；未知、异常或超期返回False。

        deadline已到仍允许零等待续核。业务target出口只释放其参数引用，
        标准Thread尾声仍须join；本线程重入关闭直接返回False。
        """
        if self._joined or not self._attempted:
            return True
        if type(deadline) not in (int, float) or not math.isfinite(deadline):
            return False
        if current_thread() is self._thread:
            return False

        def remaining():
            now = clock()
            if type(now) not in (int, float) or not math.isfinite(now):
                raise ValueError("线程关闭时钟无效")
            return max(0, deadline - now)

        try:
            # start可在OS创建后、ident/started发布前中断；entry缺席保持未知。
            if not self._start_returned and not self._entered.wait(remaining()):
                return False
            self._thread.join(remaining())
            if self._thread.is_alive():
                return False
            self._target, self._args = None, ()
            self._joined = True
            return True
        except BaseException:
            # 中断join或bootstrap结果未知均保留owner，后续关闭沿原对象续核。
            return False
