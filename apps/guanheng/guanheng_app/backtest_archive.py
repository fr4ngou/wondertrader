"""完成回测的只读原件索引；不拥有执行、线程或第二份报告存储。"""
from __future__ import annotations

from hashlib import sha256
import json
import logging
import math
import os
from pathlib import Path
import re
import stat
from threading import Lock
from time import monotonic
from uuid import uuid4

from .strategy_host import HostError as HostError, HostResult, SCHEMA as HOST_SCHEMA, _path, _json
from .backtest_reports import (validate_report_dict, project_session_record,
                               normalize_session, report_schema_for_input, PER_DATE_REPORT_SCHEMA,
                               project_input_business_diagnostics, ORIGINAL_REPORT_SCHEMA, ORIGINAL_INPUT_SCHEMA,
                               verify_original_native_input)
from .backtest_performance import build_performance, build_comparison, MAX_RESPONSE, _fraction, _money

SCHEMA = "nbw-completed-archive-v1"
SCOPE = "isolated-raw-BT; real-source/RT/broker/production-unqualified"
RECEIPT = "completed-archive.json"
MAX_RECEIPT = 16384
MAX_RUNS = 128
MAX_FILES = 8192
MAX_NATIVE = 128 * 1024 * 1024
MAX_RUN_BYTES = 192 * 1024 * 1024
MAX_READ = 192 * 1024 * 1024
ID = re.compile(r"[a-f0-9]{32}")
SHA = re.compile(r"[a-f0-9]{64}")
UNAVAILABLE = "归档或原件未通过完整性校验，请保留原目录并核查；本次没有重新执行回测"
PUBLISH_FAILED = "回测已完成，归档尚未确认；重启后可能无法从页面读取，请在退出前重试归档并保留原件"


class ArchiveError(ValueError):
    def __init__(self, reason=UNAVAILABLE, code=503):
        super().__init__(reason)
        self.code = code


def _require(ok, reason=UNAVAILABLE, code=503):
    if not ok:
        raise ArchiveError(reason, code)


def _wire(value, *, sort_keys=True):
    return json.dumps(value, ensure_ascii=True, sort_keys=sort_keys, separators=(",", ":"), allow_nan=False).encode("ascii")


def _sha(raw):
    return sha256(raw).hexdigest()


def _id(value):
    return type(value) is str and ID.fullmatch(value) is not None


def _digest(value):
    return type(value) is str and SHA.fullmatch(value) is not None


def _same(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


class _Read:
    """一次归档操作共用原D和累计读取额度；OS单次操作仍有不可抢占边界。"""
    def __init__(self, deadline):
        self.deadline = deadline
        self.used = 0
        self.admitted_input = None

    def check(self):
        _require(monotonic() < self.deadline, "归档读取或发布超时，请刷新状态核查后重试")

    def directory(self, path):
        self.check()
        path = _path(path)
        _require(stat.S_ISDIR(path.lstat().st_mode))
        return path

    def raw(self, path, maximum, *, checksum=False):
        self.check()
        path = _path(path)
        before = path.lstat()
        _require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= maximum)
        output = None if checksum else bytearray()
        hasher, observed = sha256(), 0
        with path.open("rb") as stream:
            opened = os.fstat(stream.fileno())
            _require(_same(opened) == _same(before) and opened.st_nlink == 1)
            while True:
                self.check()
                part = stream.read(min(65536, maximum + 1 - observed))
                if not part:
                    break
                observed += len(part)
                self.used += len(part)
                _require(observed <= maximum and self.used <= MAX_READ)
                if output is not None:
                    output.extend(part)
                hasher.update(part)
            _require(_same(os.fstat(stream.fileno())) == _same(before))
        after = _path(path).lstat()
        _require(_same(after) == _same(before) and after.st_nlink == 1)
        self.check()
        return hasher.hexdigest() if checksum else bytes(output)

    def value(self, path, maximum):
        raw = self.raw(path, maximum)
        return _json(raw, maximum, self.deadline), raw

    def session(self, request, report):
        """同一操作只复用完全相同的输入准入；顺序摘要保留来源日期顺序约束。"""
        self.check()
        value = request['session']
        identity = (_sha(_wire(value, sort_keys=False)), request['session_sha256'])
        if identity != self.admitted_input:
            _require(request['session_sha256'] == _sha(_wire(value)))
            if request['report_schema'] == PER_DATE_REPORT_SCHEMA:
                normalized = normalize_session(value)
                _require(_wire(normalized) == _wire(value))
            elif request['report_schema'] == ORIGINAL_REPORT_SCHEMA:
                _require(value.get('schema') == ORIGINAL_INPUT_SCHEMA)
                _require(_wire(normalize_session(value)) == _wire(value))
        if request['report_schema'] == PER_DATE_REPORT_SCHEMA:
            _require(value['source'] == report.get('per_date_source'))
            value = value['session']
        self.check()
        return value, identity


def _receipt(value, run_id):
    _require(type(value) is dict and set(value) == {
        "schema", "run_id", "owner_id", "request_id", "request_sha256", "installation_sha256",
        "result_sha256", "report_sha256", "record_count", "pid", "exit_code", "forced",
        "pid_reaped", "pipes_joined", "elapsed_ms", "configuration", "scope"})
    _require(value["schema"] == SCHEMA and value["run_id"] == run_id and _id(run_id)
             and _id(value["owner_id"]) and _id(value["request_id"]) and value["scope"] == SCOPE)
    _require(all(_digest(value[k]) for k in ("request_sha256", "installation_sha256", "result_sha256", "report_sha256")))
    _require(type(value["pid"]) is int and 0 < value["pid"] <= 0xffffffff and type(value["exit_code"]) is int
             and value["exit_code"] == 0 and value["forced"] is False
             and value["pid_reaped"] is True and value["pipes_joined"] is True)
    _require(type(value["elapsed_ms"]) is int and 0 <= value["elapsed_ms"] <= 7200000
             and type(value["record_count"]) is int and 0 <= value["record_count"] <= 4096)
    c = value["configuration"]
    _require(type(c) is dict and set(c) == {"label", "name", "start", "end", "session_sha256", "max_seconds"})
    _require(type(c["label"]) is str and 1 <= len(c["label"]) <= 100 and all(ord(x) >= 32 for x in c["label"])
             and type(c["name"]) is str and re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,30}", c["name"])
             and type(c["start"]) is int and type(c["end"]) is int and _digest(c["session_sha256"])
             and type(c["max_seconds"]) in (int, float) and math.isfinite(c["max_seconds"])
             and .1 <= c["max_seconds"] <= 1800)
    from .strategy_porter import validate_backtest_window
    validate_backtest_window(c["start"], c["end"])
    return value


class BacktestArchive:
    """仅显式work_root；构造无I/O。不可变run receipt免去全局可变索引/CAS账本。"""
    def __init__(self, root):
        self.root = Path(root)
        self._lock = Lock()
        self._admitted_report = None
        self._day_view = None  # 唯一轻量按日投影；每次复用前仍重新核完整原件SHA。

    def _run(self, read, run_id):
        _require(_id(run_id), "历史运行身份无效", 422)
        root = read.directory(self.root)
        return read.directory(root / run_id)

    def _load(self, read, run_id, receipt_sha=None):
        try:
            directory = self._run(read, run_id)
        except FileNotFoundError:
            # 仅run查找缺失属于404；根目录/总D仍须可用，原件缺失继续沿完整性错误。
            read.directory(self.root)
            raise ArchiveError('历史报告不存在或已移出当前归档，请重新读取报告目录', 404) from None
        value, raw = read.value(directory / RECEIPT, MAX_RECEIPT)
        _require(not (type(value) is dict and value.get('schema') == 'orr-completed-archive-v1'),
                 '该非WT报告族已移出观衡，请读取WT回测报告', 410)
        _receipt(value, run_id)
        if receipt_sha is not None:
            _require(_digest(receipt_sha) and _sha(raw) == receipt_sha, "归档身份已改变，请重新读取历史目录", 409)
        return directory, value, _sha(raw)

    def list(self, deadline, *, summaries=False):
        read = _Read(deadline)
        _require(self._lock.acquire(blocking=False), "归档正在读取，请稍后重试", 429)
        try:
            root = read.directory(self.root)
            runs, invalid, unarchived, count = [], 0, 0, 0
            with os.scandir(root) as entries:
                for entry in entries:
                    read.check()
                    count += 1
                    _require(count <= 256, "历史根目录项已满，请由运维核查保留容量")
                    path = _path(Path(entry.path))
                    info = path.lstat()
                    if stat.S_ISREG(info.st_mode):
                        _require(info.st_nlink == 1)
                        continue  # 原NSH允许根内有受管普通文件，不将其当run。
                    _require(stat.S_ISDIR(info.st_mode))
                    _require(len(runs) + invalid + unarchived < MAX_RUNS, "历史运行已满，请由运维核查保留容量")
                    if not _id(path.name):
                        unarchived += 1
                        continue
                    if not (path / RECEIPT).exists():
                        unarchived += 1
                        continue
                    try:
                        _, value, receipt_sha = self._load(read, path.name)
                        self._capacity(read, path)
                        keys = ("run_id", "owner_id", "request_id", "record_count", "report_sha256", "configuration", "scope")
                        item = {**{k: value[k] for k in keys},
                                "receipt_sha256": receipt_sha}
                        if summaries:
                            # 列表归属与完整绩效分层；单份原件失败只影响本条归属。
                            try:
                                item['summary'] = self._summary(read, path, value)
                            except (Exception, SystemExit) as error:
                                logging.getLogger(__name__).warning('backtest_summary_unavailable run_id=%s error_type=%s',
                                                                   path.name, type(error).__name__)
                                item['summary'] = None
                        runs.append(item)
                    except ArchiveError as error:
                        if error.code != 410:
                            invalid += 1
                    except (Exception, SystemExit):
                        invalid += 1
            read.check()
            runs.sort(key=lambda item: item["run_id"])
            response = {"schema": "nbw-archive-summary-index-v1" if summaries else "nbw-archive-index-v1", "runs": runs, "invalid_receipts": invalid,
                        "unarchived_runs": unarchived, "scope": SCOPE}
            _require(len(_wire(response)) <= 524288)
            read.check()
            return response
        except ArchiveError:
            raise
        except (Exception, SystemExit):
            raise ArchiveError() from None
        finally:
            self._lock.release()

    def _summary(self, read, directory, receipt):
        """只投影完成证明绑定的报告归属及本金，不授完整报告/绩效读取资格。

        每次仍核原请求、结果、安装及报告摘要，沿原文件/容量/截止合同；
        完整来源、领域、原生输出和绩效仍在用户选择该报告时由_originals核验。
        列表不重建全部报告、不缓存第二份完整金融报告，也不从名称推断版本。
        """
        _require(read.raw(directory / 'request.json', 16 * 1024 * 1024, checksum=True) == receipt['request_sha256'])
        result, raw = read.value(directory / 'result.json', 32 * 1024 * 1024)
        _require(_sha(raw) == receipt['result_sha256'])
        _require(read.raw(directory / 'installation.json', 2 * 1024 * 1024, checksum=True) == receipt['installation_sha256'])
        _require(result['schema'] == HOST_SCHEMA and result['run_id'] == receipt['run_id']
                 and result['request_sha256'] == receipt['request_sha256']
                 and result['installation_sha256'] == receipt['installation_sha256'])
        report = result['report']
        _require(_sha(_wire(report)) == receipt['report_sha256']
                 and report['schema'] == result['report_schema']
                 and len(report['records']) == receipt['record_count'])
        from .backtest_reports import RETAINED_REPORT_SCHEMAS
        if report['schema'] in (*RETAINED_REPORT_SCHEMAS, ORIGINAL_REPORT_SCHEMA):
            strategy = dict(id=report['strategy_id'],  # 原报告中的策略业务ID。
                            version=report['strategy_version'])  # 该份原报告的实际策略版本。
            initial = report['policy']['initial_capital_cny']
        else:
            # 旧configured/V2族的身份归冻结输入；保留原已知族，未知族不猜归属。
            _require(report['schema'] in ('nsb-report-v2', 'nsb-v2-report-v1', 'nsb-historical-report-v1'))
            request, _raw = read.value(directory / 'request.json', 16 * 1024 * 1024)
            _require(_sha(_raw) == receipt['request_sha256'])
            session = request['session']
            configured = session.get('strategy', session.get('config'))
            strategy = dict(id=configured['strategy_id'],  # 旧报告族的冻结输入策略ID。
                            version=configured['strategy_version'])  # 旧冻结输入的实际策略版本。
            initial = session['policy']['initial_capital_cny']
        _require(all(type(value) is str and 0 < len(value) <= 256
                     and all(ord(char) >= 32 for char in value) for value in strategy.values()))
        amount = _fraction(initial)
        _require(amount > 0)
        read.check()
        return dict(strategy=strategy,  # 完成证明绑定的原报告/输入策略身份，不取展示名称。
                    initial_capital_cny=_money(amount))  # 原模型初始本金，人民币十进制文本；不表示当前账户资金。

    def _originals(self, read, directory, value, result_raw=None):
        self._capacity(read, directory)
        request, request_raw = read.value(directory / "request.json", 16 * 1024 * 1024)
        if result_raw is None:
            result_raw = read.raw(directory / "result.json", 32 * 1024 * 1024)
        result = _json(result_raw, 32 * 1024 * 1024, read.deadline)
        installation, install_raw = read.value(directory / "installation.json", 2 * 1024 * 1024)
        _require(_sha(request_raw) == value["request_sha256"] and _sha(result_raw) == value["result_sha256"]
                 and _sha(install_raw) == value["installation_sha256"])
        _require(request["schema"] == HOST_SCHEMA and result["schema"] == HOST_SCHEMA
                 and request["run_id"] == result["run_id"] == value["run_id"]
                 and request["installation_sha256"] == result["installation_sha256"] == value["installation_sha256"]
                 and result["request_sha256"] == value["request_sha256"]
                 and request["report_schema"] == result["report_schema"] == installation["report_schema"])
        c = value["configuration"]
        _require(request["backtest"] == {"start": c["start"], "end": c["end"], "name": c["name"]}
                 and request["session_sha256"] == c['session_sha256'])
        report = result["report"]
        _require(report_schema_for_input(request['session'])==request['report_schema'])
        _require(_sha(_wire(report)) == value["report_sha256"])
        # 原请求/结果字节每次重读核SHA；只复用唯一一份深不可变报告的领域准入。
        report_key = (value['request_sha256'], value['result_sha256'])
        cached = self._admitted_report
        if cached is not None and cached[0] == report_key:
            admitted = cached[1]
            read.admitted_input = cached[2]
            session, input_identity = read.session(request, report)
        else:
            session, input_identity = read.session(request, report)
            admitted = validate_report_dict(report, check=read.check)
        _require(admitted.record_count == value["record_count"] and report["schema"] == result["report_schema"])
        if report['schema'] == ORIGINAL_REPORT_SCHEMA:
            if cached is None or cached[0] != report_key:
                verify_original_native_input(report,session,check=read.check)
            for name,identity in report['native_outputs']:
                read.check()
                _require(result['native_outputs'].get(f"outputs/{c['name']}/{name}")==identity)
        bases = ("sessions", "commodities", "contracts", "holidays", "fees")
        _require(dict(report["native_files"]) == {k: installation["basefiles"][k]["sha256"] for k in bases})
        for key in bases:
            for folder in ("basefiles", "session-basefiles"):
                _require(_sha(read.raw(directory / folder / (key + ".json"), 1024 * 1024))
                         == installation["basefiles"][key]["sha256"])
        expected = result["native_outputs"]
        _require(type(expected) is dict and 0 < len(expected) <= MAX_FILES)
        actual, total, entries_seen = {}, 0, 0
        pending = [read.directory(directory / "outputs")]
        while pending:
            folder = pending.pop()
            with os.scandir(folder) as entries:
                for entry in entries:
                    read.check()
                    entries_seen += 1
                    _require(entries_seen <= MAX_FILES)
                    path = _path(Path(entry.path))
                    info = path.lstat()
                    if stat.S_ISDIR(info.st_mode):
                        pending.append(read.directory(path))
                    else:
                        _require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1)
                        total += info.st_size
                        _require(total <= MAX_NATIVE)
                        relative = path.relative_to(directory).as_posix()
                        _require(relative in expected and _digest(expected[relative]))
                        actual[relative] = read.raw(path, MAX_NATIVE, checksum=True)
        _require(actual == expected and any(k.endswith("trades.csv") for k in actual))
        read.check()
        read.admitted_input = input_identity
        self._admitted_report = (report_key, admitted, input_identity)
        return request, admitted, report, session

    def _capacity(self, read, directory, *, reserve=False):
        """整run共用容量/类型准入；只在首次新写时计入额外发布槽位。"""
        extra_files, extra_bytes = (2, MAX_RECEIPT) if reserve else (0, 0)
        pending, files, seen, total = [read.directory(directory)], 0, 0, 0
        while pending:
            folder = pending.pop()
            with os.scandir(folder) as entries:
                for entry in entries:
                    read.check()
                    seen += 1
                    _require(seen + extra_files <= MAX_FILES, "归档目录项已满，请核查保留容量")
                    path = _path(Path(entry.path))
                    info = path.lstat()
                    if stat.S_ISDIR(info.st_mode):
                        pending.append(read.directory(path))
                    else:
                        _require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1)
                        files += 1
                        total += info.st_size
                        _require(files + extra_files <= MAX_FILES and total + extra_bytes <= MAX_RUN_BYTES,
                                 "归档原件或发布预留容量不足，请核查保留容量")
        read.check()

    def publish(self, result, owner_id, request_id, configuration, report_sha, record_count, deadline):
        """调用者持有最终HostResult；发布失败只改变归档资格，禁止重新执行。"""
        read = _Read(deadline)
        _require(self._lock.acquire(blocking=False), PUBLISH_FAILED, 429)
        temporary = None
        identity = None
        try:
            _require(type(result) is HostResult and result.status == "completed" and result.forced is False
                     and result.exit_code == 0 and result.pid_reaped is True and result.pipes_joined is True)
            directory = self._run(read, result.run_id)
            _require(_path(Path(result.directory)) == directory)
            result_raw = read.raw(directory / "result.json", 32 * 1024 * 1024)
            value = {"schema": SCHEMA, "run_id": result.run_id, "owner_id": owner_id, "request_id": request_id,
                     "request_sha256": result.request_sha256, "installation_sha256": result.installation_sha256,
                     "result_sha256": _sha(result_raw), "report_sha256": report_sha, "record_count": record_count,
                     "pid": result.pid, "exit_code": result.exit_code, "forced": result.forced,
                     "pid_reaped": result.pid_reaped, "pipes_joined": result.pipes_joined,
                     "elapsed_ms": result.elapsed_ms, "configuration": dict(configuration), "scope": SCOPE}
            _receipt(value, result.run_id)
            self._originals(read, directory, value, result_raw)
            encoded = _wire(value)
            _require(len(encoded) <= MAX_RECEIPT)
            target = directory / RECEIPT
            if target.exists():
                _require(read.raw(target, MAX_RECEIPT) == encoded, "归档证明冲突，请保留原件并核查")
                digest = _sha(encoded)
                read.check()
                return digest
            self._capacity(read, directory, reserve=True)
            temporary = directory / (".archive-" + uuid4().hex + ".pending")
            read.check()
            with temporary.open("xb") as stream:
                info = os.fstat(stream.fileno())
                identity = info.st_dev, info.st_ino
                _require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1)
                stream.write(encoded)
                stream.flush()
                read.check()
                os.fsync(stream.fileno())
            read.check()
            _require(read.raw(temporary, MAX_RECEIPT) == encoded)
            # 本模块固定Windows本机盘；rename在目标存在时拒绝，禁止replace覆盖。
            _require(os.name == "nt")
            info = temporary.lstat()
            _require((info.st_dev, info.st_ino) == identity and info.st_nlink == 1)
            _path(directory)
            read.check()
            try:
                os.rename(temporary, target)
                temporary = None
            except FileExistsError:
                _require(read.raw(target, MAX_RECEIPT) == encoded, "归档证明冲突，请保留原件并核查")
                # 只删除本调用创建且inode仍相同的冗余pending。
                info = temporary.lstat()
                _require((info.st_dev, info.st_ino) == identity)
                temporary.unlink()
                temporary = None
            read.check()
            _require(read.raw(target, MAX_RECEIPT) == encoded)
            digest = _sha(encoded)
            read.check()
            return digest
        except ArchiveError:
            raise
        except (Exception, SystemExit):
            raise ArchiveError(PUBLISH_FAILED) from None
        finally:
            # 未确认发布/清理不删除其他路径，原pending保留供运维核查。
            self._lock.release()

    def read(self, run_id, receipt_sha, deadline, *, offset=0, limit=50, index=None, configuration=False, performance=False):
        read = _Read(deadline)
        return self._read(read, run_id, receipt_sha, offset=offset, limit=limit, index=index,
                          configuration=configuration, performance=performance)

    def _read(self, read, run_id, receipt_sha, *, offset=0, limit=50, index=None, configuration=False, performance=False):
        """一次操作的上下文沿所有原件和投影传递；锁只保护当前原件访问。"""
        _require(self._lock.acquire(blocking=False), "归档正在读取，请稍后重试", 429)
        try:
            _require(_digest(receipt_sha), "历史读取需要固定归档摘要", 422)
            directory, value, digest = self._load(read, run_id, receipt_sha)
            request, admitted, report, session = self._originals(read, directory, value)
            if performance:
                _require(configuration is False and index is None, "绩效读取参数无效", 422)
                response = build_performance(receipt=value, receipt_sha256=digest, request=request, session=session,
                    report=report, admitted=admitted, check=read.check)
            elif configuration:
                response = {"schema": "nbw-archive-configuration-v1", "run_id": run_id, "receipt_sha256": digest,
                            "request_id": value["request_id"], "configuration": value["configuration"],
                            "report_sha256": value["report_sha256"], "installation_sha256": value["installation_sha256"],
                            "session_configuration": (session["request"]["configuration"]
                                if session.get("schema") == "guanheng.retained-replay-input.v1"
                                else session.get("strategy", session.get("config"))),
                            "policy": session["policy"], "fee_reserve_cny": session["fee_reserve_cny"],
                            "fee_source": session["fee_source"], "scope": SCOPE}
                response['business_diagnostics'] = project_input_business_diagnostics(admitted, session, check=read.check)
                if report['schema'] == ORIGINAL_REPORT_SCHEMA:
                    deficit_dates = []
                    for row in report['records']:
                        read.check()
                        if row['cash_deficit']:
                            deficit_dates.append(row['trading_date'])
                    response['original_native'] = {
                        'signal_algorithm_id': report['signal_algorithm_id'],  # 固定原stable信号算法，不等同WT执行模型。
                        'reference_report_sha256': report['reference_report_sha256'],  # 原ORR规范报告摘要。
                        'source_snapshot_sha256': report['source_snapshot_sha256'],  # 原完整输入规范摘要。
                        'execution_model': report['historical_model']['execution'],  # 沿原报告已校模型的D信号至下一交易日首tick语义。
                        'historical_model': report['historical_model'],  # OHLC、整手、现金缺口等模型事实。
                        'evaluation_window': report['evaluation_window'],  # 原评价首尾及额外前一真实交易日暖机，ISO日期。
                        'cash_deficit_count': len(deficit_dates),  # 已准入逐日WT事实中现金为负的日期数，不推断源缺口。
                        'cash_deficit_dates': deficit_dates,  # 中国交易日YYYYMMDD升序，沿validator核过的cash_deficit。
                        'source_qualified': report['source_qualified'],  # 来源资格，研究输入保持false。
                        'execution_qualified': report['execution_qualified'],  # 只读报告不授交易资格。
                        'point_in_time_qualified': report['point_in_time_qualified']}  # 历史首次可知未合格。
            elif index is None:
                _require(type(offset) is int and 0 <= offset <= 4096 and type(limit) is int and 1 <= limit <= 50, code=422)
                headers = [{k: row[k] for k in ("trading_date", "minute", "status", "reason")} for row in report["records"]]
                response = {"request_id": value["request_id"], "report_sha256": value["report_sha256"],
                            "total": len(headers), "offset": offset, "records": headers[offset:offset + limit], "scope": SCOPE}
            else:
                _require(type(index) is int and 0 <= index < admitted.record_count, "记录索引越界", 404)
                projected = project_session_record(admitted, index, check=read.check)
                response = {"request_id": value["request_id"], "index": index, "report_sha256": value["report_sha256"],
                            "record": projected["record"], "evaluation_summary": projected["evaluation_summary"], "scope": SCOPE}
                if projected["report_schema"] != "nsb-report-v2":
                    response["report_schema"] = projected["report_schema"]
                if 'diagnostics' in projected:
                    response['diagnostics'] = projected['diagnostics']
            read.check()
            _require(len(_wire(response)) <= MAX_RESPONSE, "归档页面超过响应容量")
            read.check()
            return response
        except ArchiveError:
            raise
        except (Exception, SystemExit):
            raise ArchiveError() from None
        finally:
            self._lock.release()

    def _verify_day_view(self, read, directory, view):
        """重复日期仍核全部原字节及输出集合；省去已绑定原件的大JSON/CSV重解析。"""
        self._capacity(read,directory)
        expected={path for path,_,_ in view.proof if path.startswith('outputs/')}
        actual=set();pending=[read.directory(directory/'outputs')]
        while pending:
            with os.scandir(pending.pop()) as entries:
                for entry in entries:
                    read.check();path=_path(Path(entry.path));info=path.lstat()
                    if stat.S_ISDIR(info.st_mode):pending.append(read.directory(path))
                    else:
                        _require(stat.S_ISREG(info.st_mode) and info.st_nlink==1)
                        actual.add(path.relative_to(directory).as_posix())
        _require(actual==expected)
        for relative,expected_sha,maximum in view.proof:
            _require(read.raw(directory/relative,maximum,checksum=True)==expected_sha)

    def visual(self, run_id, receipt_sha, deadline, *, ledger=False, summaries=False, day=None, offset=0, limit=50):
        """曲线辅助与日期明细复用完整原件校验、同一锁/预算；不写归档。"""
        from .backtest_visuals import native_tables, build_visuals
        from .backtest_day_view import build_day_view
        read = _Read(deadline)
        _require(self._lock.acquire(blocking=False), '归档正在读取，请稍后重试', 429)
        try:
            directory, value, digest = self._load(read, run_id, receipt_sha)
            identity=(run_id,digest,value['report_sha256']);view=self._day_view
            if view is not None and view.identity==identity:
                self._verify_day_view(read,directory,view)
            else:
                result_raw = read.raw(directory / 'result.json', 32 * 1024 * 1024)
                request, admitted, report, session = self._originals(read, directory, value, result_raw=result_raw)
                result = _json(result_raw, 32 * 1024 * 1024, deadline)
                trades, positions = native_tables(read, directory, value, result)
                performance = build_performance(receipt=value, receipt_sha256=digest, request=request, session=session,
                    report=report, admitted=admitted, check=read.check)
                visuals=build_visuals(performance,trades,check=read.check)
                proof=[('request.json',value['request_sha256'],16*1024*1024),
                    ('result.json',value['result_sha256'],32*1024*1024),
                    ('installation.json',value['installation_sha256'],2*1024*1024)]
                installation,installation_raw=read.value(directory/'installation.json',2*1024*1024)
                _require(_sha(installation_raw)==value['installation_sha256'])
                proof.extend((folder+'/'+name+'.json',installation['basefiles'][name]['sha256'],1024*1024)
                    for name in ('sessions','commodities','contracts','holidays','fees') for folder in ('basefiles','session-basefiles'))
                proof.extend((relative,expected,MAX_NATIVE) for relative,expected in result['native_outputs'].items())
                view=build_day_view(receipt=value,receipt_sha=digest,report=report,trades=trades,positions=positions,
                    proof=proof,visuals=visuals,check=read.check)
                self._day_view=view
            _require(type(offset) is int and 0<=offset<=65536 and type(limit) is int and 1<=limit<=50,'分页参数无效',422)
            if ledger:
                _require(day is None or day in view.dates,'该报告没有所选日期',404)
                response=view.ledger(day,offset,limit)
            else:
                response=json.loads(view.summary_json if summaries else view.visuals_json)
            _require(len(_wire(response)) <= MAX_RESPONSE, '日期明细超出响应容量')
            read.check()
            return response
        except ArchiveError:
            raise
        except (Exception, SystemExit):
            raise ArchiveError() from None
        finally:
            self._lock.release()

    def compare(self, left_run_id, left_receipt_sha, right_run_id, right_receipt_sha, deadline):
        """两次完整原件读取串行共用一次绝对D；一份失败即整对拒绝。"""
        read = _Read(deadline)
        _require(_id(left_run_id) and _id(right_run_id) and left_run_id != right_run_id
                 and _digest(left_receipt_sha) and _digest(right_receipt_sha), "比较需要两个不同的固定归档身份", 422)
        try:
            read.check()
            left = self._read(read, left_run_id, left_receipt_sha, performance=True)
            read.check()
            right = self._read(read, right_run_id, right_receipt_sha, performance=True)
            read.check()
            response = build_comparison(left, right, SCOPE)
            _require(len(_wire(response)) <= MAX_RESPONSE, "比较页面超过响应容量")
            read.check()
            return response
        except ArchiveError:
            raise
        except (Exception, SystemExit):
            raise ArchiveError() from None
