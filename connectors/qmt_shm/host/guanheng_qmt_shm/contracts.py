"""Restricted public read DTOs extracted without legacy business imports.

The only result observation value admitted by this full-tick-only package is
None. This narrows capability without changing the complete full-tick wire DTO.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID, uuid4
from guanheng_qmt_shm_agent.read_capabilities import known_operation, ACCOUNT
from guanheng_qmt_shm_agent.account_query import POLICY_VERSION, IDENTITY_POLICY_VERSION, LIMITS_SCHEMA
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=False)


class OperationPolicy(StrictModel):
    """Versioned deadline, retry, and checkpoint policy for one operation family."""

    schema_version: Literal["1.0"] = "1.0"
    policy_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{2,99}$")
    operation_ids: list[str] = Field(min_length=1)
    queue_timeout_ms: int = Field(ge=100, le=300_000)
    execution_timeout_ms: int = Field(ge=100, le=300_000)
    response_grace_ms: int = Field(ge=0, le=60_000)
    total_timeout_ms: int = Field(ge=100, le=600_000)
    max_attempts: int = Field(ge=1, le=10)
    retry_backoff_initial_ms: int = Field(ge=0, le=300_000)
    retry_backoff_max_ms: int = Field(ge=0, le=300_000)
    retryable_error_codes: list[str] = Field(default_factory=list)
    checkpoint_scope: Literal["none", "symbol", "segment"]
    terminal_proof_window_ms: int = Field(ge=0, le=600_000)
    max_concurrency: int = Field(ge=1, le=128)

    @field_validator("operation_ids", "retryable_error_codes")
    @classmethod
    def validate_operation_policy_lists(cls, value: list[str]) -> list[str]:
        normalized = [item.strip() for item in value]
        if any(not item for item in normalized) or normalized != sorted(set(normalized)):
            raise ValueError("operation policy lists must be non-empty, unique, and sorted")
        return normalized

    @model_validator(mode="after")
    def validate_operation_policy(self):
        minimum_total = self.queue_timeout_ms + self.execution_timeout_ms + self.response_grace_ms
        if self.total_timeout_ms < minimum_total:
            raise ValueError("operation total timeout is smaller than its deadline budget")
        if self.retry_backoff_max_ms < self.retry_backoff_initial_ms:
            raise ValueError("operation retry backoff bounds are reversed")
        if self.max_attempts == 1 and self.retryable_error_codes:
            raise ValueError("single-attempt operation cannot declare retryable errors")
        return self


class OperationResultRef(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    request_id: UUID
    operation_id: str = Field(min_length=1)
    result_sha256: str = Field(min_length=64, max_length=64)
    result_endpoint: str = Field(pattern=r"^/internal/v1/operation-results/[0-9a-f-]{36}$")
    completed_at: datetime

    @field_validator("result_sha256")
    @classmethod
    def validate_operation_result_hash(cls, value: str) -> str:
        normalized = value.lower()
        if any(character not in "0123456789abcdef" for character in normalized):
            raise ValueError("operation result SHA-256 must be hexadecimal")
        return normalized


class OperationProgress(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    request_id: UUID
    operation_id: str = Field(min_length=1)
    request_sha256: str = Field(min_length=64, max_length=64)
    status: Literal["queued", "executing", "succeeded", "failed", "cancelled"]
    queued_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    attempt: int = Field(default=1, ge=1, le=10)
    queue_wait_ms: int | None = Field(default=None, ge=0)
    execution_ms: int | None = Field(default=None, ge=0)
    result_ref: OperationResultRef | None = None
    error_code: str | None = None
    error_message: str | None = None

    @field_validator("request_sha256")
    @classmethod
    def validate_operation_request_hash(cls, value: str) -> str:
        normalized = value.lower()
        if any(character not in "0123456789abcdef" for character in normalized):
            raise ValueError("operation request SHA-256 must be hexadecimal")
        return normalized

    @model_validator(mode="after")
    def validate_operation_progress(self):
        terminal = self.status in ("succeeded", "failed", "cancelled")
        if terminal != (self.completed_at is not None):
            raise ValueError("operation completion time does not match status")
        if self.status == "succeeded" and self.result_ref is None:
            raise ValueError("successful operation requires a result reference")
        if self.status != "succeeded" and self.result_ref is not None:
            raise ValueError("only successful operations may carry a result reference")
        if self.status == "failed" and not self.error_code:
            raise ValueError("failed operation requires an error code")
        return self


class GatewayOperationRequest(StrictModel):
    request_id: UUID = Field(default_factory=uuid4)
    correlation_id: UUID = Field(default_factory=uuid4)
    operation_id: str = Field(strict=True)

    @field_validator('operation_id')
    @classmethod
    def require_known_operation(cls,value):
        if not known_operation(value):raise ValueError('unknown read operation')
        return value
    arguments: dict[str, Any] = Field(default_factory=dict)
    timeout_ms: int = Field(default=5000, ge=100, le=30000)
    policy_id: str = Field(default="qmt.standard-read.v1", pattern=r"^[a-z0-9][a-z0-9._-]{2,99}$")
    policy_version: Literal["1.0"] = "1.0"
    priority_class: Literal["normal"] = "normal"



class BoundGatewayOperationRequest(GatewayOperationRequest):
    """Bound owner在实际profile准入之后使用；旧无profile DTO仍仅接受1.0。"""
    policy_version: Literal[POLICY_VERSION, IDENTITY_POLICY_VERSION] = POLICY_VERSION

    @model_validator(mode="after")
    def validate_account_projection_policy(self):
        if (self.policy_version == IDENTITY_POLICY_VERSION
                and (self.operation_id != ACCOUNT or self.policy_id != LIMITS_SCHEMA)):
            raise ValueError('identity projection requires the account policy')
        return self


class GatewayOperationResult(StrictModel):
    request_id: UUID
    operation_id: str = Field(strict=True)

    @field_validator('operation_id')
    @classmethod
    def require_known_operation(cls,value):
        if not known_operation(value):raise ValueError('unknown read operation')
        return value
    ok: bool
    completed_at: datetime = Field(default_factory=utc_now)
    data: Any | None = None
    error_code: str | None = None
    error_message: str | None = None
    result_sha256: str | None = Field(default=None, min_length=64, max_length=64)
    request_admission_ms: int = Field(default=0, ge=0)
    queue_wait_ms: int | None = Field(default=None, ge=0)
    execution_ms: int | None = Field(default=None, ge=0)
    result_persistence_ms: int = Field(default=0, ge=0)
    response_wakeup_ms: int = Field(default=0, ge=0)
    response_handler_ms: int = Field(default=0, ge=0)
    observation: None = None

