"""回测业务owner：原宿主拥有进程，本层只拥有有界请求投影与一个报告缓存。"""

from dataclasses import dataclass, replace
from hashlib import sha256
import json
from pathlib import Path
import re
from threading import Event, Lock, Thread
from time import monotonic
from uuid import uuid4

from .strategy_host import (
    HostBudgets,
    HostError,
    InstallationBinding,
    StrategyHost,
    _bytes,
    _json,
    _path,
)
from .strategy_porter import AdmissionError, validate_backtest_window
from .thread_owner import ThreadOwner
from .backtest_reports import project_session_record, validate_report_dict
from .backtest_archive import BacktestArchive, ArchiveError, PUBLISH_FAILED

ID = re.compile(r"[a-f0-9]{32}")
SHA = re.compile(r"[a-f0-9]{64}")
SCOPE = "isolated-raw-BT; real-source/RT/broker/production-unqualified"


class WorkspaceError(ValueError):
    """业务入口安全原因及明确HTTP状态；不带磁盘或原输入细节。"""

    def __init__(self, code, reason):
        super().__init__(reason)
        self.code = code


def _require(condition, reason="回测工作区配置无效", code=422):
    if not condition:
        raise WorkspaceError(code, reason)


def _digest(data):
    return sha256(data).hexdigest()


def _wire(value):
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("ascii")


@dataclass(frozen=True)
class WorkspaceConfig:
    """固定部署输入；请求不能改变安装、回放或会话。摘要变化须显式重新配置。"""

    binding: InstallationBinding
    work_root: Path
    session: Path
    session_sha256: str
    start: int
    end: int
    name: str
    label: str
    max_seconds: float

    @classmethod
    def load(cls, path, expected):
        if not path and not expected:
            return None
        try:
            _require(type(expected) is str and SHA.fullmatch(expected))
            deadline = monotonic() + 5
            raw = _bytes(Path(path), 65536, deadline)
            _require(_digest(raw) == expected)
            value = _json(raw, 65536, deadline)
            _require(
                type(value) is dict
                and set(value)
                == {
                    "schema",
                    "binding",
                    "work_root",
                    "session",
                    "start",
                    "end",
                    "name",
                    "label",
                    "max_seconds",
                }
            )
            _require(value["schema"] == "nbw-config-v1")
            for key in ("binding", "session"):
                _require(
                    type(value[key]) is dict and set(value[key]) == {"path", "sha256"}
                )
                _require(
                    type(value[key]["sha256"]) is str
                    and SHA.fullmatch(value[key]["sha256"])
                )
            validate_backtest_window(value["start"], value["end"])
            _require(
                type(value["name"]) is str
                and re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,30}", value["name"])
            )
            _require(
                type(value["label"]) is str
                and 1 <= len(value["label"]) <= 100
                and all(ord(c) >= 32 for c in value["label"])
            )
            seconds = value["max_seconds"]
            _require(type(seconds) in (int, float) and 0.1 <= seconds <= 1800)
            root = _path(Path(value["work_root"]))
            _require(root.is_dir())
            return cls(
                InstallationBinding(
                    _path(Path(value["binding"]["path"])), value["binding"]["sha256"]
                ),
                root,
                _path(Path(value["session"]["path"])),
                value["session"]["sha256"],
                value["start"],
                value["end"],
                value["name"],
                value["label"],
                seconds,
            )
        except (OSError, ValueError, TypeError, KeyError, AdmissionError):
            raise WorkspaceError(
                503, "回测配置或摘要未通过准入，请检查受管部署配置"
            ) from None


class BacktestWorkspace:
    """生命周期拥有者，最多一worker、零队列；重复request读取原投影。

    元数据最多128份，完整报告只缓存一个。历史文件仅按先前HostResult证明及
    摘要读取；进程重启更换owner身份，不从旧目录恢复执行或推定完成。
    """

    def __init__(self, config, *, host_factory=StrategyHost):
        self.config = config
        self.owner_id = uuid4().hex
        self._factory = host_factory
        self._lock = Lock()
        self._report_lock = Lock()
        self._accepting = True
        self._active = None
        self._worker = None
        self._entries = {}
        self._cache = None
        self._archive = BacktestArchive(config.work_root) if config is not None else None

    def overview(self):
        with self._lock:
            return {
                "schema": "nbw-workspace-v1",
                "owner_id": self.owner_id,
                "available": self.config is not None and self._accepting,
                "reason": None
                if self.config is not None and self._accepting
                else "尚未配置回测，或工作区正在关闭",
                "configuration": None
                if self.config is None
                else {
                    "label": self.config.label,
                    "start": self.config.start,
                    "end": self.config.end,
                    "session_sha256": self.config.session_sha256,
                    "max_seconds": self.config.max_seconds,
                },
                "runs": [
                    dict(e["view"]) for e in reversed(tuple(self._entries.values()))
                ],
                "scope": SCOPE,
            }

    def _identity(self, owner_id, request_id):
        _require(
            type(owner_id) is str
            and ID.fullmatch(owner_id)
            and type(request_id) is str
            and ID.fullmatch(request_id),
            "运行身份格式无效",
        )
        _require(owner_id == self.owner_id, "工作区已重启，请重新读取当前运行身份", 409)

    def start(self, owner_id, request_id):
        self._identity(owner_id, request_id)
        with self._lock:
            _require(
                self.config is not None and self._accepting, "回测未配置或正在关闭", 503
            )
            if request_id in self._entries:
                return dict(self._entries[request_id]["view"])
            _require(
                self._active is None
                and (self._worker is None or self._worker.join_until(monotonic())),
                "已有回测运行，请等待结束；当前没有排队",
                409,
            )
            _require(
                len(self._entries) < 128,
                "本进程已达128次接纳上限，请由运维处理保留容量",
                429,
            )
            began = monotonic()
            view = {
                "owner_id": self.owner_id,
                "request_id": request_id,
                "run_id": None,
                "status": "running",
                "reason": "已受理，正在进行冻结输入准入与原生回放",
                "elapsed_ms": 0,
                "pid": None,
                "exit_code": None,
                "forced": None,
                "pid_reaped": None,
                "pipes_joined": None,
                "record_count": 0,
                "archive_status": "pending",
                "archive_reason": "完整回放与父端回收后才发布归档证明",
                "archive_receipt_sha256": None,
                "scope": SCOPE,
            }
            entry = {
                "view": view,
                "cancel": Event(),
                "began": began,
                "result": None,
                "report_sha": None,
                "archive_configuration": self._archive_configuration(),
                "archive_retrying": False,
                "thread": None,
                "completed": Event(),
            }
            self._entries[request_id] = entry
            self._active = request_id
            try:
                worker = ThreadOwner(
                    target=self._run,
                    args=(request_id,),
                    name="guanheng-backtest",
                    daemon=True,
                    thread_factory=Thread,
                )
                # start可能已创建真实线程再抛异常；先绑定owner，异常不能释放名额。
                entry["thread"] = self._worker = worker
                worker.start()
            except BaseException:
                entry["cancel"].set()
                if entry["thread"] is None:
                    # 标准Thread构造失败尚无OS线程；该次受理明确失败，保留请求投影。
                    view.update(status="incomplete", reason="回测工作线程构造失败，请检查运行环境",
                                archive_status="not-applicable", archive_reason="工作线程未创建，没有可归档的完成回测")
                    entry["completed"].set()
                    self._active = None
                else:
                    view["reason"] = "线程启动确认未取得，已请求取消；等待原owner收口"
                raise WorkspaceError(
                    503, "回测启动确认未取得，请刷新原运行状态"
                ) from None
            return dict(view)

    def status(self, owner_id, request_id):
        self._identity(owner_id, request_id)
        with self._lock:
            _require(request_id in self._entries, "未找到本进程受理的回测", 404)
            return dict(self._entries[request_id]["view"])

    def cancel(self, owner_id, request_id):
        self._identity(owner_id, request_id)
        with self._lock:
            _require(request_id in self._entries, "未找到本进程受理的回测", 404)
            entry = self._entries[request_id]
            if entry["view"]["status"] == "running":
                entry["cancel"].set()
                entry["view"]["reason"] = "已请求取消，正在等待原宿主确认进程回收"
            return dict(entry["view"])

    def _archive_configuration(self):
        config = self.config
        return {"label": config.label, "name": config.name, "start": config.start, "end": config.end,
                "session_sha256": config.session_sha256, "max_seconds": config.max_seconds}

    def archive(self, *, deadline, run_id=None, receipt_sha=None, **selection):
        _require(self._archive is not None, "尚未配置历史回测根", 503)
        try:
            if run_id is None:
                return self._archive.list(deadline)
            return self._archive.read(run_id, receipt_sha, deadline, **selection)
        except ArchiveError as exc:
            raise WorkspaceError(exc.code, str(exc)) from None

    def comparison(self, left_run_id, left_receipt_sha, right_run_id, right_receipt_sha, *, deadline):
        """只读两份完成原件；读取线程与两侧核验共用调用者的绝对截止。"""
        _require(self._archive is not None, "尚未配置历史回测根", 503)
        try:
            return self._archive.compare(left_run_id, left_receipt_sha, right_run_id, right_receipt_sha, deadline)
        except ArchiveError as exc:
            raise WorkspaceError(exc.code, str(exc)) from None

    def retry_archive(self, owner_id, request_id, *, deadline):
        self._identity(owner_id, request_id)
        with self._lock:
            _require(self._accepting, "回测工作区正在关闭", 503)
            _require(request_id in self._entries, "未找到本进程受理的回测", 404)
            entry = self._entries[request_id]
            _require(entry["completed"].is_set() and entry["view"]["status"] == "completed",
                     "本轮尚无已确认的完整回测，不能归档", 409)
            _require(not entry["archive_retrying"], "归档正在核查，请稍后刷新原状态", 429)
            result, report_sha = entry["result"], entry["report_sha"]
            count = entry["view"]["record_count"]
            entry["archive_retrying"] = True
        status, reason, receipt_sha = "unknown", PUBLISH_FAILED, None
        try:
            receipt_sha = self._archive.publish(result, owner_id, request_id, entry["archive_configuration"],
                                                report_sha, count, deadline)
            status, reason = "available", "完成证明与原件已核实，重启后可从历史归档读取"
        except (Exception, SystemExit):
            pass
        finally:
            with self._lock:
                entry["archive_retrying"] = False
                entry["view"].update(archive_status=status, archive_reason=reason,
                                     archive_receipt_sha256=receipt_sha)
        with self._lock:
            return dict(entry["view"])

    def _run(self, request_id):
        entry = self._entries[request_id]
        config = self.config
        deadline = entry["began"] + config.max_seconds
        result = None
        admitted = None
        headers = None
        report_sha = None
        reason = "回测未完成，请检查受管输入及运行证据"
        status = "incomplete"
        archive_status, archive_reason, archive_sha = "not-applicable", "本轮尚无可归档的完整回测", None
        try:
            payload = _bytes(config.session, 16777216, deadline)
            _require(_digest(payload) == config.session_sha256)
            remaining = deadline - monotonic()
            _require(remaining >= 0.1)
            host = self._factory(
                config.binding,
                config.work_root,
                budgets=HostBudgets(max_seconds=remaining),
            )
            result = host.run(
                payload,
                start=config.start,
                end=config.end,
                name=config.name,
                cancel=entry["cancel"],
            )
            if (
                result.status == "completed"
                and not result.forced
                and result.exit_code == 0
                and result.pid_reaped
                and result.pipes_joined
                and result.report_json is not None
            ):

                def check():
                    if monotonic() >= deadline:
                        raise HostError("报告准入期限耗尽")

                raw = result.report_json.encode("ascii")
                value = _json(raw, 8388608, deadline)
                admitted = validate_report_dict(value, check=check)
                headers = tuple(
                    {k: r[k] for k in ("trading_date", "minute", "status", "reason")}
                    for r in value["records"]
                )
                report_sha = _digest(_wire(value))
                check()
                status, reason = "completed", "原生回测完成，进程与管道均已回收"
                archive_status, archive_reason = "unavailable", PUBLISH_FAILED
                try:
                    archive_sha = self._archive.publish(
                        result, self.owner_id, request_id, entry["archive_configuration"],
                        report_sha, len(headers), deadline,
                    )
                    archive_status, archive_reason = "available", "完成证明与原件已核实，重启后可从历史归档读取"
                except (Exception, SystemExit):
                    # 原回测/回收事实保持；归档写失败不伪造native失败或可持久读取。
                    archive_status, archive_reason = "unknown", PUBLISH_FAILED
            elif result.status == "busy":
                status, reason = "busy", "原生运行根正在使用，请等待原运行结束"
            else:
                reason = "原生回测未完成，原目录保留供核查"
            if entry["cancel"].is_set() and status != "completed":
                reason = "回测已取消；进程回收事实见本轮状态"
        except (Exception, SystemExit):
            reason = "回测准入、运行或报告校验未完成，请检查受管配置与原运行证据"
        finally:
            try:
                with self._lock:
                    view = entry["view"]
                    view.update(
                        status=status,
                        reason=reason,
                        elapsed_ms=int((monotonic() - entry["began"]) * 1000),
                        archive_status=archive_status, archive_reason=archive_reason,
                        archive_receipt_sha256=archive_sha,
                    )
                    if result is not None:
                        view.update(
                            run_id=result.run_id,
                            pid=result.pid,
                            exit_code=result.exit_code,
                            forced=result.forced,
                            pid_reaped=result.pid_reaped,
                            pipes_joined=result.pipes_joined,
                        )
                        entry["result"] = replace(result, report_json=None)
                    if status == "completed":
                        view["record_count"] = len(headers)
                        entry["report_sha"] = report_sha
                if status == "completed":
                    # 缓存竞争只影响命中率；worker不持owner锁等待报告读取。
                    if self._report_lock.acquire(blocking=False):
                        try:
                            self._cache = (request_id, admitted, headers)
                        finally:
                            self._report_lock.release()
            finally:
                # worker出口是唯一的完成确认；启动返回异常不能覆盖尚存的线程。
                with self._lock:
                    entry["completed"].set()
                    if self._active == request_id:
                        self._active = None

    def report(
        self, owner_id, request_id, *, offset=0, limit=50, index=None, deadline=None
    ):
        """有限读取worker调用；同一报告重用唯一准入结果，单日不重复传整个前缀。"""
        self._identity(owner_id, request_id)
        deadline = monotonic() + 5 if deadline is None else deadline
        _require(
            type(offset) is int
            and offset >= 0
            and type(limit) is int
            and 1 <= limit <= 50
        )
        _require(
            self._report_lock.acquire(blocking=False), "报告正在读取，请稍后重试", 429
        )
        try:
            with self._lock:
                _require(request_id in self._entries, "未找到本进程受理的回测", 404)
                entry = self._entries[request_id]
                _require(
                    entry["view"]["status"] == "completed", "本轮尚无完整报告", 409
                )
                result, expected = entry["result"], entry["report_sha"]

            def check():
                _require(monotonic() < deadline, "报告读取超时，请稍后重试", 503)

            if self._cache is None or self._cache[0] != request_id:
                raw = _bytes(Path(result.directory) / "result.json", 33554432, deadline)
                value = _json(raw, 33554432, deadline)["report"]
                _require(
                    _digest(_wire(value)) == expected,
                    "报告内容已改变，停止展示该报告",
                    503,
                )
                admitted = validate_report_dict(value, check=check)
                headers = tuple(
                    {k: r[k] for k in ("trading_date", "minute", "status", "reason")}
                    for r in value["records"]
                )
                self._cache = (request_id, admitted, headers)
            _, admitted, headers = self._cache
            if index is None:
                response = {
                    "request_id": request_id,
                    "report_sha256": expected,
                    "total": len(headers),
                    "offset": offset,
                    "records": [dict(row) for row in headers[offset : offset + limit]],
                    "scope": SCOPE,
                }
            else:
                _require(
                    type(index) is int and 0 <= index < admitted.record_count,
                    "记录索引越界",
                    404,
                )
                # NSB拥有两种报告的共享历史和header结构；页面直接取同版投影，
                # 避免先展开全部前缀，也不在消费者维护另一份字段删除清单。
                projected = project_session_record(admitted, index, check=check)
                response = {
                    "request_id": request_id,
                    "index": index,
                    "report_sha256": expected,
                    "record": projected["record"],
                    "evaluation_summary": projected["evaluation_summary"],
                    "scope": SCOPE,
                }
                # configured响应保持既有字段；新族显式声明版本，消费者按版本
                # 读取实际策略和目标准入，不能从部署展示名称猜测策略。
                if projected["report_schema"] != "nsb-report-v2":
                    response["report_schema"] = projected["report_schema"]
            check()
            _require(len(_wire(response)) <= 524288, "报告页面超过响应容量", 503)
            return response
        except WorkspaceError:
            raise
        except (Exception, SystemExit):
            raise WorkspaceError(
                503, "报告读取或身份校验失败，请检查原运行证据"
            ) from None
        finally:
            self._report_lock.release()

    def close(self, timeout):
        """同一截止核全部已受理owner；启动结果未知保留False与强引用。"""
        deadline = monotonic() + max(0, timeout)
        with self._lock:
            self._accepting = False
            entries = tuple(self._entries.values())
            for entry in entries:
                if not entry["completed"].is_set():
                    entry["cancel"].set()
        # completed是业务出口；标准join另证线程尾声。逐个续核所有已接纳owner。
        joined = [entry["thread"] is None or entry["thread"].join_until(deadline) for entry in entries]
        return all(joined) and all(entry["completed"].is_set() for entry in entries)
