"""迁移原Scan纯配置与IPC解码；只验证运输身份，金融事实由原投影解释。"""
from dataclasses import dataclass, field, InitVar
import hashlib
import json
import math
from pathlib import Path

FRAME_BYTES = 20 * 1024 * 1024
STDERR_BYTES = 64 * 1024
ERROR_CODES = {"ok", "configuration", "source", "close", "internal"}
DATATYPES = ("position", "order", "deal", "account")

class AccountProtocolError(ValueError):
    """运输错误只返回固定原因，不携带私有原文。"""

def require(condition):
    if not condition:
        raise AccountProtocolError("invalid_protocol")

def integer(value, minimum=0, maximum=2**53 - 1):
    return type(value) is int and minimum <= value <= maximum

def text(value, maximum=512):
    return isinstance(value, str) and 0 < len(value) <= maximum and all(ord(c) >= 32 and ord(c) != 127 for c in value)

def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result)
        result[key] = value
    return result


def decode_json(data):
    """长度由调用者先准入；解析前限制嵌套深度，JSON只接收有限值。"""
    depth, quoted, escaped = 0, False, False
    for byte in data:
        if quoted:
            if escaped:
                escaped = False
            elif byte == 92:
                escaped = True
            elif byte == 34:
                quoted = False
        elif byte == 34:
            quoted = True
        elif byte in (91, 123):
            depth += 1
            require(depth <= 32)
        elif byte in (93, 125):
            depth -= 1
            require(depth >= 0)
    try:
        result = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_object,
                            parse_constant=lambda _value: require(False))
    except (ValueError, UnicodeError, RecursionError):
        raise AccountProtocolError("invalid_protocol") from None
    pending = [result]
    while pending:
        value = pending.pop()
        if isinstance(value, dict):
            pending.extend(value.values())
        elif isinstance(value, list):
            pending.extend(value)
        elif isinstance(value, float):
            require(math.isfinite(value))
    require(isinstance(result, dict))
    return result



@dataclass(frozen=True)
class AccountScanConfig:
    """旧六字段构造兼容；新来源事实只取递归不可变configuration快照。

    配置事实只由不可变快照拥有；schema2的原body摘要在准入时一次捕获。
    安装句柄/SHA归native，进程回收归运行owner，每轮父端不重读配置文件。
    schema2运行由WT唯一ManagedAccountScan持有；来源可用性以本轮查询结果为准。
    """

    executable: str
    config_path: str
    account: str
    environment: str
    total_seconds: float = 15.0
    max_rows: int = 4096
    configuration: object = field(default=None, repr=False)
    raw_configuration: InitVar[bytes | None] = field(default=None, repr=False)
    configuration_sha256: str | None = field(default=None, init=False, repr=False)

    @classmethod
    def from_paths(cls, executable, config_path):
        from .account_scan_config import validate_account_scan_configuration
        if not executable and not config_path:
            return None
        executable_path, binding_path = Path(executable), Path(config_path)
        require(executable_path.is_absolute() and binding_path.is_absolute() and executable_path.is_file() and binding_path.is_file())
        try:
            with binding_path.open("rb") as stream:
                data = stream.read(65537)
        except OSError:
            raise AccountProtocolError("invalid_configuration") from None
        require(len(data) <= 65536)
        binding = validate_account_scan_configuration(decode_json(data))
        trader, budget = binding["trader"], binding["budget"]
        return cls(str(executable_path), str(binding_path), trader["expected_account"], trader["environment"],
                   budget.get("total_ms", 15000) / 1000, trader.get("max_rows", 4096), binding, raw_configuration=data)

    def __post_init__(self, raw_configuration):
        from .account_scan_config import validate_account_scan_configuration
        if self.configuration is not None:
            # 新快照的兼容字段只接普通标量，等值运算不接受自定义转换/比较。
            require(type(self.executable) is str and type(self.config_path) is str
                    and type(self.account) is str and type(self.environment) is str
                    and type(self.total_seconds) in (int, float))
        require(Path(self.executable).is_absolute() and Path(self.config_path).is_absolute())
        require(text(self.account) and text(self.environment) and not isinstance(self.total_seconds, bool)
                and 1 <= self.total_seconds <= 30 and integer(self.max_rows, 1, 4096))
        if self.configuration is not None:
            snapshot = validate_account_scan_configuration(self.configuration)
            trader, budget = snapshot["trader"], snapshot["budget"]
            require(self.account == trader["expected_account"] and self.environment == trader["environment"]
                    and self.max_rows == trader.get("max_rows", 4096)
                    and self.total_seconds == budget.get("total_ms", 15000) / 1000)
            if snapshot["schema_version"] == 2:
                # 原文件body只参与本次纯准入；不存raw，不接受调用方自报digest。
                require(type(raw_configuration) is bytes and 0 < len(raw_configuration) <= 65536)
                from_raw = validate_account_scan_configuration(decode_json(raw_configuration))
                require(from_raw == snapshot)
                object.__setattr__(self, "configuration_sha256", hashlib.sha256(raw_configuration).hexdigest())
            object.__setattr__(self, "configuration", snapshot)

    @property
    def schema_version(self):
        return self.configuration["schema_version"] if self.configuration is not None else 1

    @property
    def source(self):
        return self.configuration["trader"]["source"] if self.configuration is not None else "qmt_http"

    @property
    def read_profile_version(self):
        return self.configuration["trader"]["read_profile_version"] if self.schema_version == 2 else None

    @property
    def ipc_schema(self):
        return "guanheng.account-scan.v2" if self.schema_version == 2 else "guanheng.account-scan.v1"

    @property
    def inspection_version(self):
        return 3 if self.schema_version == 2 else 2

    @property
    def public_schema_version(self):
        return "2.0" if self.schema_version == 2 else "1.0"

    @property
    def runtime_available(self):
        """已实现的配置版本；真实账户是否可读取由本轮有界查询确认。"""
        return self.schema_version in (1, 2)

def _completion(frame, scan_id, *, schema="guanheng.account-scan.v1"):
    require(schema in ("guanheng.account-scan.v1", "guanheng.account-scan.v2"))
    require(set(frame) == {"schema", "scan_id", "kind", "closed", "joined", "worker_live", "queued", "elapsed_ms", "error_code"})
    require(frame["schema"] == schema and frame["scan_id"] == scan_id and frame["kind"] == "completion")
    require(all(type(frame[key]) is bool for key in ("closed", "joined", "worker_live")))
    require(integer(frame["queued"]) and integer(frame["elapsed_ms"], maximum=60000) and frame["error_code"] in ERROR_CODES)
    return frame



def validate_transport_observation(frame, scan_id, binding):
    """核帧边界及四批运输交付；原字段值、ABI、来源与金融资格交C唯一validator。"""
    require(type(frame) is dict and set(frame) == {"schema", "scan_id", "kind", "summary", "rows"})
    require(frame["schema"] == binding.ipc_schema and frame["scan_id"] == scan_id
            and frame["kind"] == "observation")
    summary, rows = frame["summary"], frame["rows"]
    require(type(summary) is dict and type(rows) is dict and set(rows) == set(DATATYPES))
    require(type(summary.get("version")) is int and summary["version"] == binding.inspection_version
            and type(summary.get("view")) is int and summary["view"] == 0
            and summary.get("source_kind") == binding.source
            and summary.get("profile") == "cny_cash_shsz_v1"
            and type(summary.get("observation_qualified")) is bool)
    batches = summary.get("batches")
    require(type(batches) is list and len(batches) == 4)
    for name, batch in zip(DATATYPES, batches, strict=True):
        require(type(batch) is dict and batch.get("datatype") == name
                and type(batch.get("delivered")) is bool
                and type(rows[name]) is list and len(rows[name]) <= binding.max_rows)
        if batch["delivered"]:
            require(integer(batch.get("delivered_row_count"), maximum=binding.max_rows)
                    and batch["delivered_row_count"] == len(rows[name]))
        else:
            require(not rows[name])
    return frame

def transport_complete(frame):
    return bool(frame is not None and frame["summary"]["observation_qualified"]
                and all(batch["delivered"] for batch in frame["summary"]["batches"]))
