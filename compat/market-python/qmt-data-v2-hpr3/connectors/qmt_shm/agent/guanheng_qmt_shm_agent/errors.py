# -*- coding: utf-8 -*-
"""Original read, JSON and authentication errors; no execution branch."""

class GatewayError(Exception):
    def __init__(self, code, message, status_code=400):
        Exception.__init__(self, message)
        self.code = code
        self.message = message
        self.status_code = int(status_code)

    def as_dict(self):
        return {"error_code": self.code, "error_message": self.message}


class AuthenticationError(GatewayError):
    def __init__(self, code, message, status_code=401):
        GatewayError.__init__(self, code, message, status_code)


class ReplayError(AuthenticationError):
    def __init__(self, message="nonce has already been used"):
        AuthenticationError.__init__(self, "replay_detected", message, 409)


class UnknownOperationError(GatewayError):
    def __init__(self, operation_id):
        GatewayError.__init__(
            self,
            "unknown_operation",
            "operation is not registered: {0}".format(operation_id),
            404,
        )


class InvalidArgumentsError(GatewayError):
    def __init__(self, message):
        GatewayError.__init__(self, "invalid_arguments", message, 400)


class CapabilityUnavailableError(GatewayError):
    def __init__(self, operation_id, reason="operation is unavailable"):
        GatewayError.__init__(
            self,
            "capability_unavailable",
            "{0}: {1}".format(operation_id, reason),
            503,
        )


class SafeJSONError(GatewayError):
    def __init__(self, message):
        GatewayError.__init__(self, "unsafe_json_value", message, 500)
