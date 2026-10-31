"""Broker v1 注入门面；复用上游 DTO，不建立 HTTP、IPC 或执行账本。"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Protocol

from .models import Capability, IntegrationUnavailable
from .dependencies import REGISTRY


def strict_json(body: bytes):
    """入站原文统一校验重复键和有限值，验证过程保留原 bytes。"""
    if not isinstance(body, bytes) or not 1 <= len(body) <= 1048576:
        raise ValueError("Broker 正文必须为有界原始 bytes")

    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise ValueError("Broker 正文存在重复字段")
            result[key] = value
        return result

    def number(text):
        value = float(text)
        if not math.isfinite(value):
            raise ValueError("Broker 正文包含非有限数")
        return value

    def invalid(unused):
        raise ValueError("Broker 正文包含非有限数")

    value = json.loads(body.decode("utf-8"), object_pairs_hook=pairs, parse_float=number, parse_constant=invalid)
    if not isinstance(value, dict):
        raise ValueError("Broker 正文必须为 JSON 对象")
    return value


class BrokerClient(Protocol):
    """上游业务客户端的只读面；调用行为由注入对象及部署 owner 提供。"""
    def health(self): ...
    def state(self): ...
    def events(self, after_seq: int, limit: int): ...
    def execute_operation(self, request): ...


@dataclass(frozen=True)
class SignedCommand:
    command_id: str
    original_bytes: bytes
    sha256: str

    @classmethod
    def validate(cls, original_bytes: bytes, command_type):
        """用原 OrderCommand 检查结构，保留签名原文；验签/许可由上游唯一 owner 处理。"""
        data = strict_json(original_bytes)
        command = command_type.model_validate(data)
        if not command.signature or not command.signature.strip():
            raise ValueError("命令缺少原签名")
        if command.expires_at.tzinfo is None:
            raise ValueError("原命令有效期必须包含时区")
        return cls(str(command.command_id), original_bytes, hashlib.sha256(original_bytes).hexdigest())


class BrokerV1Facade:
    """当前受限 Host 的实际能力投影；连接成功不开放订阅、下载或命令。

    broker_types 来自 ExternalQmt.broker_types 的已校验上游 DTO；传输显式注入，
    每次单尝试交换且原 body bytes 不重写。typed_client 负责已有业务模型/恢复语义。
    本门面不根据调用者提供的 capability 开放当前 Host 尚未接线的写入口。
    """

    _READ_EXCHANGES = frozenset(("health.read", "state.read", "events.read", "sync.read", "operation.result"))
    _UNAVAILABLE = frozenset(("subscription", "download", "trading", "history_universe"))

    def __init__(self, *, typed_client: BrokerClient, transport, broker_types, read_operations,
                 capabilities: dict[str, Capability], timeout_seconds: float):
        if type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 30:
            raise ValueError("Broker 交换期限必须为 (0,30] 有限秒数")
        read_operations = tuple(read_operations)
        if any(not isinstance(item, str) or not item for item in read_operations):
            raise ValueError("读取 operation 必须显式登记")
        frozen = json.loads(REGISTRY.read_text(encoding="utf-8"))["broker_dependency"]["read_operation_ids"]
        if not set(read_operations) <= set(frozen):
            raise IntegrationUnavailable("读取清单包含当前 Host 未开放的 operation", "read")
        self.client, self.transport, self.types = typed_client, transport, broker_types
        self.read_operations = frozenset(read_operations)
        self.capabilities = dict(capabilities)
        self.timeout_seconds = timeout_seconds

    def capability(self, name: str) -> Capability:
        if name in self._UNAVAILABLE:
            return Capability(reason="当前固定 Host 切片尚未开放此能力")
        return self.capabilities.get(name, Capability(reason="未登记此项能力"))

    def health(self):
        return self.client.health()

    def state(self):
        self.capability("state").require("state")
        return self.client.state()

    def events(self, after_seq: int = 0, limit: int = 100):
        self.capability("events").require("events")
        if type(after_seq) is not int or after_seq < 0 or type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("可靠事件游标或分页不合格")
        return self.client.events(after_seq=after_seq, limit=limit)

    def _read(self, operation_id, arguments):
        if operation_id not in self.read_operations:
            raise IntegrationUnavailable("operation 尚未登记为合格读取", operation_id)
        if not isinstance(arguments, dict):
            raise ValueError("operation 参数必须为对象")
        # 与原受限 Host read fence 一致，避免读取参数偷偷扩大订阅或补数能力。
        if operation_id == "market.market_data_ex":
            for flag in ("subscribe", "fill_data"):
                if flag in arguments and arguments[flag] is not False:
                    raise IntegrationUnavailable("受限读取不开放订阅或历史填补", operation_id)
        self.capability(operation_id).require(operation_id)

    def read_operation(self, request):
        self._read(request.operation_id, request.arguments)
        if (request.policy_id != "qmt.standard-read.v1" or request.policy_version != "1.0"
                or request.priority_class != "normal"):
            raise IntegrationUnavailable("当前 Host 只接受标准普通优先级读取", request.operation_id)
        return self.client.execute_operation(request)

    def exchange(self, operation: str, *, body: bytes = b"", parameters=None):
        """提供上游 typed Transport 接缝，原文原样运输；拒绝当前未开放的写 operation。"""
        if operation not in self._READ_EXCHANGES and operation != "operation.submit":
            raise IntegrationUnavailable("当前 Host 未开放此 Broker operation", operation)
        if operation == "operation.submit":
            # 原 v1 JSON 用于准入检查，Transport 仍接收调用者的同一个 bytes 对象。
            data = strict_json(body)
            self._read(data["operation_id"], data["arguments"])
            if (data.get("policy_id") != "qmt.standard-read.v1" or data.get("policy_version") != "1.0"
                    or data.get("priority_class") != "normal"):
                raise IntegrationUnavailable("当前 Host 只接受标准普通优先级读取", operation)
            if (parameters or {}).get("operation_id") != data["operation_id"]:
                raise ValueError("Broker operation 参数与原文身份不符")
        elif operation in ("state.read", "events.read", "sync.read"):
            self.capability("state" if operation == "state.read" else "events").require(operation)
        request = self.types.BrokerRequest(operation, body=body, parameters=parameters or {})
        response = self.transport.request(request, timeout_seconds=self.timeout_seconds)
        if not isinstance(response, self.types.BrokerResponse):
            raise ValueError("Broker Transport 必须返回已校验的上游 BrokerResponse")
        return response

    def submit_command(self, command: SignedCommand):
        self.capability("trading").require("trading")
        # 当前冻结切片必然在准入处返回 unavailable；后续命令接线先更新公共契约。
        raise IntegrationUnavailable("等待上游命令 RPC 与单执行权资格", "trading")
