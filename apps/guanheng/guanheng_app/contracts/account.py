"""账户只读显示值；逐批观察时间与未知字段随来源保留。"""

import math
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AccountModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class AccountField(AccountModel):
    availability: Literal["present", "unknown", "invalid"]
    value: Any = None
    reason: str | None = None

    @field_validator("value")
    @classmethod
    def scalar_value(cls, value):
        if value is not None and type(value) not in {str, int, float}:
            raise ValueError("账户字段仅接受文本或有限数值")
        if type(value) in {int, float} and not math.isfinite(value):
            raise ValueError("账户数值必须有限")
        return value

    @model_validator(mode="after")
    def availability_matches_value(self):
        if (self.availability == "present") != (self.value is not None):
            raise ValueError("账户字段资格和值不一致")
        return self


class AccountSource(AccountModel):
    kind: Literal["qmt_http"] = "qmt_http"
    account_label: str
    agent_id: str
    environment: str
    session_id: str
    generation: int


class AccountRow(AccountModel):
    identity: dict[str, str] = Field(default_factory=dict)
    fields: dict[str, AccountField]


class AccountGroup(AccountModel):
    datatype: Literal["position", "order", "deal", "account"]
    status: Literal["complete", "unavailable"]
    rows: list[AccountRow] = Field(default_factory=list)
    source: AccountSource | None = None
    execution_started_at: str | None = None
    execution_finished_at: str | None = None
    request_id: str | None = None
    result_sha256: str | None = None
    reason: str | None = None


class AccountClose(AccountModel):
    status: Literal["complete", "forced", "failed", "not_started"] = "not_started"
    closed: bool = False
    joined: bool = False
    worker_live: bool = False
    queued: int = 0
    exit_code: int | None = None
    error_code: str = "unconfigured"


class AccountOverview(AccountModel):
    schema_version: Literal["1.0"] = "1.0"
    scan_id: str | None = None
    status: Literal["complete", "partial", "unavailable"]
    read_only: Literal[True] = True
    aggregate_only: Literal[True] = True
    trade_date: AccountField
    close: AccountClose = Field(default_factory=AccountClose)
    groups: dict[str, AccountGroup]
    reason: str


# DTO2使用独立source类型；旧DTO1序列化不增加任何占位字段。
class AccountTransportRoute(AccountModel):
    route_id: str = Field(min_length=1, max_length=128)
    executor_id: str = Field(min_length=1, max_length=128)
    route_epoch: int = Field(strict=True, ge=0, le=2**53 - 1)


class AccountTransport(AccountModel):
    host_instance_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    transport_generation: str = Field(pattern=r"^[0-9a-f]{32}$")
    route: AccountTransportRoute
    capability_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class AccountBrokerSession(AccountModel):
    availability: Literal["unknown"] = "unknown"
    value: None = None
    reason: Literal["未取得券商登录会话证据"] = "未取得券商登录会话证据"


class ShmAccountSource(AccountModel):
    kind: Literal["qmt_shm_bound"] = "qmt_shm_bound"
    account_label: str
    environment: Literal["simulation", "live"]
    transport: AccountTransport
    broker_session: AccountBrokerSession


class AccountGroupV2(AccountGroup):
    source: ShmAccountSource | None = None


class AccountOverviewV2(AccountOverview):
    schema_version: Literal["2.0"] = "2.0"
    groups: dict[str, AccountGroupV2]


class NativeAccountSource(AccountModel):
    """WT已发布券商副本；scope仅隔离展示缓存，不代表已知账号或券商登录。"""
    kind: Literal['wt_native_observation'] = 'wt_native_observation'
    scope_id: str = Field(pattern=r'^[a-f0-9]{64}$')


class AccountGroupV3(AccountGroup):
    source: NativeAccountSource | None = None
    received_at: str | None = None
    published_at: str | None = None
    revision: int | None = None


class AccountOverviewV3(AccountOverview):
    schema_version: Literal['3.0'] = '3.0'
    groups: dict[str, AccountGroupV3]
    runtime_state: str
    observed_at: str


class AccountPublication(AccountModel):
    scope_id: str | None = Field(pattern=r'^[a-f0-9]{64}$')
    state: Literal['waiting','refreshing','ready','degraded','stopped','unconfigured']
    revision: int = Field(strict=True,ge=0,le=2**53-1)
    updated_at: str | None
    last_success_at: str | None
    runtime_state: str


class AccountOverviewV4(AccountOverviewV2):
    """原DTO2金融值及来源保持；持续发布状态单独表达。"""
    schema_version: Literal['4.0'] = '4.0'
    publication: AccountPublication


AccountOverviewResponse = Annotated[AccountOverview | AccountOverviewV2 | AccountOverviewV3 | AccountOverviewV4, Field(discriminator="schema_version")]
