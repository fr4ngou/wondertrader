"""Load the versioned operation policy registry shared by platform clients."""

from __future__ import annotations

import json
from pathlib import Path

from .contracts import OperationPolicy




class OperationPolicyRegistry:
    def __init__(self, policies: list[OperationPolicy]):
        self._policies = {item.policy_id: item for item in policies}
        if len(self._policies) != len(policies):
            raise ValueError("operation policy IDs must be unique")

    @classmethod
    def load(cls, path: str | Path):
        source = Path(path)
        payload = json.loads(source.read_text(encoding="utf-8"))
        if payload.get("schema_version") != "1.0":
            raise ValueError("unsupported operation policy registry")
        return cls([OperationPolicy.model_validate(item) for item in payload["policies"]])

    def require(self, policy_id: str, operation_id: str) -> OperationPolicy:
        item = self._policies.get(policy_id)
        if item is None:
            raise ValueError("unknown operation policy: {0}".format(policy_id))
        if "*" not in item.operation_ids and operation_id not in item.operation_ids:
            raise ValueError("operation is not allowed by selected policy")
        return item
