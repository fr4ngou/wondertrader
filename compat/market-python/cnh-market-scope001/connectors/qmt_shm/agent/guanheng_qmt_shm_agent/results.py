# -*- coding: utf-8 -*-
"""Complete v1 terminal results, shared by memory publication and persistence.

Defaults mirror GatewayOperationResult without importing its non-stdlib runtime.
The contract test verifies that model normalization adds no unbudgeted fields.
"""
import hashlib

from .protocol import canonical


RESULT_DEFAULTS = {
    "data": None, "error_code": None, "error_message": None,
    # 与 DTO 的完整默认集合一致，保证 Host 归一化前后预算和摘要保持一致。
    "observation": None,
    "request_admission_ms": 0, "queue_wait_ms": None, "execution_ms": None,
    "result_persistence_ms": 0, "response_wakeup_ms": 0, "response_handler_ms": 0,
}


def _seal(value):
    result = dict(value)
    result["result_sha256"] = hashlib.sha256(canonical(value)).hexdigest()
    return result


def _error(value, code, message):
    # Keep identity and timing, discard native data and unbounded diagnostics.
    result = dict(value)
    # 整批失败时同时清除数据及其观察资格，避免失败终态仍声明结果完整。
    result.update(ok=False, data=None, observation=None, error_code=code, error_message=message)
    return result


def finalize_result(value, max_bytes):
    """Bound the complete UTF-8 DTO including the digest, never a partial body.

    Hash covers every default/timing field before adding result_sha256. The
    bounded terminal fallback follows the same construction and accounting.
    """
    result = dict(RESULT_DEFAULTS)
    result.update(value)
    result.pop("result_sha256", None)
    try:
        sealed = _seal(result)
    except (ValueError, UnicodeError):
        sealed = _seal(_error(result, "unsafe_json_value", "原生结果无法编码为有效JSON"))
    if len(canonical(sealed)) > max_bytes:
        sealed = _seal(_error(result, "result_too_large", "读取结果超过受管容量"))
    if len(canonical(sealed)) > max_bytes:
        raise ValueError("terminal identity and timing exceed result budget")
    return sealed
