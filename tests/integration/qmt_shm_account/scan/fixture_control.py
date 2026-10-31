"""ATI私有测试控制：单轮有限原子发布，真实Agent不读取这些文件。"""
import json
import math
import os
import stat
from pathlib import Path
import time
from uuid import UUID

VERSION = "qar.test-control.v1"
LIMIT = 4096
KINDS = ("position", "order", "deal", "account")


def require(value, message="invalid test control"):
    if not value:
        raise ValueError(message)


def check(deadline, clock=time.monotonic):
    now = clock()
    require(type(deadline) in (int, float) and math.isfinite(deadline)
            and type(now) in (int, float) and math.isfinite(now) and now < deadline, "original deadline")


MAX_IO_BYTES = 1024 * 1024 * 1024


class Deadline:
    """只传递原截止；单步晚返回挡下一动作，短stream仍在异常路径关闭。"""
    def __init__(self, deadline, checker=None):
        self.deadline = deadline
        self.checker = checker

    def check(self):
        # 默认每次解析模块check，保留调用方纯时钟替身；不缓存monotonic值。
        (check if self.checker is None else self.checker)(self.deadline)

    def call(self, operation, *args, **kwargs):
        """仅用于不转移长期owner的动作；资源factory由调用方先接管再核截止。"""
        self.check()
        result = operation(*args, **kwargs)
        self.check()
        return result

    def iter(self, values, maximum):
        require(type(maximum) is int and maximum >= 0, "runtime item limit")
        iterator = self.call(iter, values)
        count = 0
        while True:
            self.check()
            try:
                item = next(iterator)
            except StopIteration:
                self.check()
                return
            self.check()
            count += 1
            require(count <= maximum, "runtime item limit")
            yield item
            self.check()

    def _stream(self, path, mode, operation):
        """open已返回就持有；早退close，enter成功后的所有异常仍走with退出。"""
        self.check()
        opened = path.open(mode)
        return self._context(opened, operation)

    def _context(self, opened, operation):
        """已由调用方取得的短context；同一清理逻辑也用于内存wheel。"""
        entered = False
        failure = failure_tb = None
        try:
            self.check()
            with opened as stream:
                entered = True
                try:
                    self.check()
                    result = operation(stream)
                except BaseException as error:
                    failure, failure_tb = error, error.__traceback__
                    raise
            if failure is not None:
                raise failure.with_traceback(failure_tb)
            self.check()
            return result
        except BaseException as error:
            if not entered:
                # open迟到或enter失败：with尚未接管；close失败也保留原异常。
                try:
                    opened.close()
                except BaseException:
                    error.add_note("测试短文件清理失败；原异常保留")
            if failure is not None and error is not failure:
                failure.add_note("测试短文件退出失败；原异常保留")
                raise failure.with_traceback(failure_tb)
            raise

    def read_bytes(self, path, maximum):
        require(type(maximum) is int and 0 <= maximum <= MAX_IO_BYTES, "file byte budget")
        def read(stream):
            raw = self.call(stream.read, maximum + 1)
            require(type(raw) is bytes and len(raw) <= maximum, "file byte budget")
            return raw
        return self._stream(self.call(Path, path), "rb", read)

    def write_bytes(self, path, raw, mode="wb", sync=False):
        require(type(raw) is bytes and len(raw) <= MAX_IO_BYTES, "file byte budget")
        require(type(mode) is str and mode in ("wb", "xb") and type(sync) is bool, "file write mode")
        def write(stream):
            written = self.call(stream.write, raw)
            require(type(written) is int and written == len(raw), "short file write")
            if sync:
                self.call(stream.flush)
                descriptor = self.call(stream.fileno)
                self.call(os.fsync, descriptor)
            return written
        return self._stream(self.call(Path, path), mode, write)


def uuid_text(value):
    require(type(value) is str and str(UUID(value)) == value, "canonical run id")
    return value


def pairs(values):
    result = {}
    for key, value in values:
        require(key not in result, "duplicate key")
        result[key] = value
    return result


def decode(raw):
    def nonfinite(value):
        raise ValueError("nonfinite control")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=nonfinite)


def read_value(path, deadline, maximum=LIMIT):
    budget = Deadline(deadline)
    # 捕获、UTF8/JSON解析沿同原截止；只解析单次原bytes。
    raw = budget.read_bytes(path, maximum)
    return budget.call(decode, raw)


def validate(value, kind, run_id):
    uuid_text(run_id)
    require(kind in ("ready", "stop", "closed") and type(value) is dict)
    expected = {"version", "fixture_run_id", "kind"}
    if kind == "closed": expected |= {"closed", "calls", "owner_thread"}
    require(set(value) == expected and value["version"] == VERSION
            and value["fixture_run_id"] == run_id and value["kind"] == kind)
    if kind == "closed":
        require(type(value["closed"]) is bool and type(value["owner_thread"]) is bool)
        require(type(value["calls"]) is list and len(value["calls"]) <= 4)
        for call in value["calls"]:
            require(type(call) is list and len(call) == 3 and type(call[0]) is str
                    and 1 <= len(call[0].encode("utf-8")) <= 63
                    and call[1] == "stock" and call[2] in KINDS)
    return value


def directory(path, run_id, deadline):
    budget = Deadline(deadline)
    path = budget.call(Path, path)
    require(budget.call(path.is_absolute) and budget.call(getattr, path, "name") == budget.call(uuid_text, run_id))
    require(budget.call(path.is_dir))
    require(not budget.call(path.is_symlink) and not budget.call(path.is_junction), "private directory alias")
    return path


def message(kind, run_id, **extra):
    return validate(dict(version=VERSION, fixture_run_id=run_id, kind=kind, **extra), kind, run_id)


def publish(root, kind, run_id, deadline, **extra):
    budget = Deadline(deadline)
    root = directory(root, run_id, deadline)
    value = budget.call(message, kind, run_id, **extra)
    text = budget.call(json.dumps, value, ensure_ascii=True, separators=(",", ":"), allow_nan=False)
    raw = budget.call(text.encode, "utf-8")
    require(len(raw) <= LIMIT)
    temporary, target = root / (kind + ".tmp"), root / (kind + ".json")
    # 独占有限tmp；write/flush/fileno/fsync各有准入，清理不受超期短路。
    budget.write_bytes(temporary, raw, mode="xb", sync=True)
    budget.call(os.link, temporary, target)
    return value


def receive(root, kind, run_id, deadline):
    budget = Deadline(deadline)
    root = directory(root, run_id, deadline)
    path = root / (kind + ".json")
    if not budget.call(path.exists):
        return None
    require(not budget.call(path.is_symlink) and not budget.call(path.is_junction), "marker alias")
    value = read_value(path, deadline)
    return budget.call(validate, value, kind, run_id)


# Host Journal以固定.owner旁文件持有单写者OS锁；其普通文件也属于本轮有限集合。
MEMBERS = {"fixture-input.json", "policies.json", "host-communication.sqlite", "host-communication.sqlite.owner", "host-communication.sqlite-wal",
    "host-communication.sqlite-shm", "host-communication.sqlite-journal", "scan.json", "alias.json",
    "alias-replacement.json", "sessions.json", "commodities.json", "contracts.json",
    "host-source.json", "host-source.tmp"}
MEMBERS |= {kind + suffix for kind in ("ready", "stop", "closed") for suffix in (".json", ".tmp")}


def check_members(root, run_id, deadline):
    budget = Deadline(deadline)
    root = directory(root, run_id, deadline)
    size, count = 0, 0
    values = budget.call(root.iterdir)
    for path in budget.iter(values, len(MEMBERS)):
        count += 1
        name = budget.call(getattr, path, "name")
        require(count <= len(MEMBERS) and name in MEMBERS, "unexpected fixture member")
        require(not budget.call(path.is_symlink) and not budget.call(path.is_junction), "fixture member alias")
        try:
            observed = budget.call(path.stat)
        except FileNotFoundError:
            budget.check()
            # SQLite正常关闭可移除自己的临时文件；有限白名单不扩大。
            require(name in {"host-communication.sqlite-wal", "host-communication.sqlite-shm", "host-communication.sqlite-journal"})
        else:
            require(stat.S_ISREG(observed.st_mode), "fixture member directory")
            size += observed.st_size
        require(size <= 64 * 1024 * 1024, "fixture retained capacity")
    budget.check()
