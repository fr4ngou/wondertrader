"""schema2账户单轮资源owner：固定配置、创建时Job归属、有限IPC及真实回收。

公开schema2入口由AccountScanOwner持有本模块；配置准入和本轮实际结果分别校验。
Job创建/父死亡杀树复用ProcessJob，金融值准入及投影复用account_projection。
"""

import math
import re
import struct
from threading import Event, Lock, Thread
from time import monotonic

from .account_projection import (project_account, require,
                                 unavailable_account, validate_observation)
from .contracts.account import AccountClose
from .thread_owner import ThreadOwner

from .account_scan import AccountScanConfig, FRAME_BYTES, STDERR_BYTES


def _check(deadline, clock):
    if clock() >= deadline:
        raise TimeoutError("账户阶段预算已耗尽")


def _job():
    # Windows API模块只在真正受管启动时装配；纯配置/导入不创建句柄。
    from .strategy_job import ProcessJob
    return ProcessJob()


class _Round:
    """单轮独占资源；未确认回收时由ManagedAccountScan继续强引用。"""

    def __init__(self, scan_id, started, deadline):
        self.scan_id, self.started, self.deadline = scan_id, started, deadline
        self.job = None
        self.threads = []
        self.failed = Event()
        self.stdout_eof = self.stderr_eof = False
        self.observation = self.completion = None
        self.completion_at = None
        self.exit_code = None
        self.forced = False
        self.reaped = False

    def join_readers(self, deadline, clock):
        """逐个收集原reader的标准join证明；False保留全部管道及Job。"""
        joined = True
        for thread in self.threads:
            if not thread.join_until(deadline, clock=clock):
                joined = False
        return joined


def _read_exact(pipe, size, deadline, clock):
    chunks, remaining = [], size
    while remaining:
        _check(deadline, clock)
        chunk = pipe.read(min(remaining, 65536))
        _check(deadline, clock)
        require(type(chunk) is bytes and 0 < len(chunk) <= min(remaining, 65536))
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _discard(pipe):
    # 协议失败即通知owner杀Job；线程只排空已有管道，不创建新的等待期限。
    while pipe.read(65536):
        pass


def _stdout(round_, config, clock):
    from .account_scan import _completion, decode_json
    pipe = round_.job.stdout
    count = 0
    try:
        while True:
            _check(round_.deadline, clock)
            first = pipe.read(1)
            _check(round_.deadline, clock)
            require(type(first) is bytes)
            if not first:
                round_.stdout_eof = True
                require(round_.completion is not None)
                return
            require(len(first) == 1 and count < 2 and round_.completion is None)
            header = first + _read_exact(pipe, 3, round_.deadline, clock)
            size = struct.unpack(">I", header)[0]
            require(0 < size <= FRAME_BYTES)
            body = _read_exact(pipe, size, round_.deadline, clock)
            value = decode_json(body)
            _check(round_.deadline, clock)
            if value.get("kind") == "completion":
                terminal = _completion(value, round_.scan_id, schema=config.ipc_schema)
                received = clock()
                require(terminal["elapsed_ms"] <= config.total_seconds * 1000
                        and terminal["elapsed_ms"] <= int((received - round_.started) * 1000) + 1)
                round_.completion, round_.completion_at = terminal, received
            else:
                require(count == 0)
                observation = validate_observation(value, round_.scan_id, config)
                _check(round_.deadline, clock)
                round_.observation = observation
            count += 1
    except BaseException:
        round_.failed.set()
        try:
            _discard(pipe)
            round_.stdout_eof = True
        except BaseException:
            pass


def _stderr(round_, clock):
    size = 0
    try:
        while True:
            _check(round_.deadline, clock)
            chunk = round_.job.stderr.read(4096)
            _check(round_.deadline, clock)
            require(type(chunk) is bytes)
            if not chunk:
                round_.stderr_eof = True
                return
            size += len(chunk)
            require(size <= STDERR_BYTES)
    except BaseException:
        round_.failed.set()
        try:
            _discard(round_.job.stderr)
            round_.stderr_eof = True
        except BaseException:
            pass


class ManagedAccountScan:
    """一个应用账户owner的一轮资源；没有全局孤儿表或客户端恢复文件。

    run由唯一工作线程调用；close/reap只做当前owner的有限回收。旧成员等待未知、
    读线程未退出或句柄关闭失败时保留整个Round，下一轮立即繁忙。
    """

    def __init__(self, *, job_factory=_job, clock=monotonic):
        self._job_factory, self._clock = job_factory, clock
        self._lock, self._round = Lock(), None

    @property
    def live_threads(self):
        round_ = self._round
        return sum(thread.pending for thread in round_.threads) if round_ else 0

    @property
    def pending(self):
        return self._round is not None

    def _reap(self, deadline):
        round_ = self._round
        if round_ is None:
            return True
        job = round_.job
        try:
            if job is not None:
                # 请求终止后保留原Job句柄；wait核整树活动数归零及root退出。
                if job.handle is not None:
                    job.close_job()
                round_.exit_code = job.wait(max(0, deadline - self._clock()))
            # 即便Job尚未建立或已关闭，清Round前也必须拥有全部reader join证明。
            if not round_.join_readers(deadline, self._clock):
                return False
            if job is not None:
                # 创建晚回/读线程未启动也必须取得两管道EOF；此时整树已wait，
                # 没有活writer，逐块排空只沿同一个剩余截止，超期继续保留句柄。
                for pipe, attribute in ((job.stdout, "stdout_eof"), (job.stderr, "stderr_eof")):
                    if pipe is not None and not getattr(round_, attribute):
                        while True:
                            _check(deadline, self._clock)
                            chunk = pipe.read(65536)
                            _check(deadline, self._clock)
                            require(type(chunk) is bytes)
                            if not chunk:
                                setattr(round_, attribute, True)
                                break
                job.close_reaped()
                round_.job = None
                round_.reaped = True
            self._round = None
            return True
        except BaseException:
            return False

    def reap(self, deadline):
        """同一调用截止内续核本owner资源；锁忙立即失败，不等待另一轮锁。"""
        if type(deadline) not in (int, float) or not math.isfinite(deadline):
            return False
        if not self._lock.acquire(blocking=False):
            return False
        try:
            return self._reap(deadline)
        finally:
            self._lock.release()

    def run(self, config, scan_id, deadline, stop):
        require(type(config) is AccountScanConfig and config.schema_version == 2 and config.configuration is not None
                and type(scan_id) is str and re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", scan_id)
                and type(deadline) in (int, float) and math.isfinite(deadline))
        if not self._lock.acquire(blocking=False):
            return unavailable_account("上一轮账户读取正在回收，请稍后刷新", scan_id, schema_version="2.0")
        began = self._clock()
        try:
            if self._round is not None and not self._reap(began):
                return unavailable_account("上一轮账户读取正在回收，请稍后刷新", scan_id, schema_version="2.0")
            round_ = _Round(scan_id, began, deadline)
            self._round = round_
            # 沿strategy_host原则在同一总预算内保留最多20%供杀树/wait/排空。
            # 采集阶段截止更早；最终回收仍使用传入deadline，任何阶段都不重新起算。
            reserve = min(config.configuration["trader"]["close_ms"] / 1000, config.total_seconds * .2)
            work_deadline = deadline - reserve
            reason = "internal"
            normal = False
            try:
                _check(work_deadline, self._clock)
                require(not stop.is_set())
                # 准入实例已拥有原body摘要；所有本轮文件IO只在受管native内。
                configuration_sha256 = config.configuration_sha256
                require(type(configuration_sha256) is str and re.fullmatch(r"[0-9a-f]{64}", configuration_sha256))
                _check(work_deadline, self._clock)
                require(not stop.is_set())
                round_.job = self._job_factory()
                _check(work_deadline, self._clock)
                round_.job.start((config.executable, "--config", config.config_path, "--scan-id", scan_id,
                                  "--config-sha256", configuration_sha256),
                                 config.configuration["installation_root"], deadline=work_deadline, clock=self._clock)
                _check(work_deadline, self._clock)
                require(round_.job.member_before_resume is True)
                for target, args in ((_stdout, (round_, config, self._clock)), (_stderr, (round_, self._clock))):
                    thread = ThreadOwner(target=target, args=args, daemon=True, name="guanheng-account-pipe",
                                         thread_factory=Thread)
                    round_.threads.append(thread)
                    thread.start()
                    _check(work_deadline, self._clock)
                while True:
                    require(not round_.failed.is_set() and not stop.is_set())
                    _check(work_deadline, self._clock)
                    # 正常循环也主动零等待join，不以target返回或is_alive=False授退出。
                    readers_joined = round_.join_readers(self._clock(), self._clock)
                    root_done = round_.job.poll() is not None
                    if root_done and round_.job.active_processes() == 0 and readers_joined:
                        break
                    stop.wait(min(.01, max(0, work_deadline - self._clock())))
                round_.exit_code = round_.job.poll()
                require(round_.stdout_eof and round_.stderr_eof and round_.completion is not None)
                terminal = round_.completion
                reason = terminal["error_code"]
                if round_.exit_code != {"ok": 0, "configuration": 2, "internal": 2, "source": 3, "close": 4}[reason]:
                    round_.failed.set()
                    require(False)
                closed = terminal["closed"] and terminal["joined"] and not terminal["worker_live"] and terminal["queued"] == 0
                observation = round_.observation
                normal = bool(reason == "ok" and closed and observation is not None and observation.qualified
                              and all(group.status == "complete" for group in observation.groups.values()))
                if reason == "ok" and not normal:
                    round_.failed.set()
                    require(False)
                _check(deadline, self._clock)
            except BaseException as exc:
                round_.forced = round_.job is not None
                reason = "collection_timeout" if isinstance(exc, TimeoutError) else "protocol" if round_.failed.is_set() else "interrupted"
                normal = False
            finally:
                reclaimed = self._reap(deadline)
            # 任何晚回、协议异常或未收口都会撤销完整成功；只有有效已交付批可作partial。
            timely = self._clock() < deadline
            normal = normal and reclaimed and timely and not round_.failed.is_set()
            terminal = round_.completion
            close = AccountClose(status="complete" if normal else "forced" if round_.forced else "failed",
                                 closed=bool(terminal and terminal["closed"] and not round_.forced),
                                 joined=bool(terminal and terminal["joined"] and not round_.forced),
                                 worker_live=bool(terminal and terminal["worker_live"]),
                                 queued=terminal["queued"] if terminal else 0, exit_code=round_.exit_code,
                                 error_code="ok" if normal else reason if reason != "ok" else "close")
            observation = None if round_.failed.is_set() or not timely else round_.observation
            result = project_account(scan_id, observation, close, schema_version="2.0")
            if self._clock() >= deadline:
                return unavailable_account("账户读取总期限已耗尽，请稍后刷新", scan_id, close, schema_version="2.0")
            if reason == "collection_timeout":
                result.reason = "账户采集阶段预算已耗尽，剩余总预算用于回收，请稍后刷新"
            return result
        finally:
            self._lock.release()
