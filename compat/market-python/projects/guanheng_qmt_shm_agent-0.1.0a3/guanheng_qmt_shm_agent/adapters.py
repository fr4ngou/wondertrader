# -*- coding: utf-8 -*-
"""Original parameter/order semantics for the sole admitted full-tick adapter."""
from .errors import CapabilityUnavailableError, InvalidArgumentsError, UnknownOperationError
_MISSING = object()

class QMTBindings(object):
    def __init__(self, context_info):
        self.context_info = context_info

def _identity(value):
    return value


def _string_list(value):
    if isinstance(value, str):
        value = [item.strip() for item in value.split(",") if item.strip()]
    if not isinstance(value, (list, tuple)):
        raise ValueError("expected a list of strings")
    if len(value) > 200:
        raise ValueError("list may contain at most 200 items")
    result = []
    for item in value:
        if not isinstance(item, str) or not item:
            raise ValueError("list items must be non-empty strings")
        result.append(item)
    return result


class Parameter(object):
    def __init__(self, name, default=_MISSING, transform=None, aliases=()):
        self.name = name
        self.default = default
        self.transform = transform or _identity
        self.aliases = tuple(aliases)


class OperationAdapter(object):
    def __init__(self, operation_id, invoke, parameters=()):
        self.operation_id = operation_id
        self.invoke = invoke
        self.parameters = tuple(parameters)
        accepted = set()
        for parameter in self.parameters:
            accepted.add(parameter.name)
            accepted.update(parameter.aliases)
        self.accepted_arguments = accepted

    def bind_arguments(self, arguments):
        if arguments is None:
            arguments = {}
        if not isinstance(arguments, dict):
            raise InvalidArgumentsError("arguments must be a JSON object")
        unknown = set(arguments) - self.accepted_arguments
        if unknown:
            raise InvalidArgumentsError(
                "unknown arguments for {0}: {1}".format(
                    self.operation_id, ", ".join(sorted(unknown))
                )
            )
        values = []
        for parameter in self.parameters:
            present_names = [
                name for name in (parameter.name,) + parameter.aliases if name in arguments
            ]
            if len(present_names) > 1:
                raise InvalidArgumentsError("argument supplied more than once: {0}".format(parameter.name))
            if present_names:
                value = arguments[present_names[0]]
            elif parameter.default is not _MISSING:
                value = parameter.default
            else:
                raise InvalidArgumentsError("missing argument: {0}".format(parameter.name))
            try:
                values.append(parameter.transform(value))
            except (TypeError, ValueError) as exc:
                raise InvalidArgumentsError(
                    "invalid {0}: {1}".format(parameter.name, str(exc))
                )
        return values

    def execute(self, bindings, arguments):
        return self.invoke(bindings, *self.bind_arguments(arguments))


def _p(name, default=_MISSING, transform=None, aliases=()):
    return Parameter(name, default=default, transform=transform, aliases=aliases)


def _context_method(operation_id, name):
    def invoke(bindings, *args):
        context = bindings.context_info
        method = getattr(context, name, None) if context is not None else None
        if not callable(method):
            raise CapabilityUnavailableError(operation_id, "ContextInfo method is unavailable")
        return method(*args)
    return invoke


class StockOperationAdapters(object):
    def __init__(self, history_adapter=None, *, account_adapter=None):
        self._history = history_adapter
        self._account = account_adapter
        self._adapter = OperationAdapter("market.full_tick",
            _context_method("market.full_tick", "get_full_tick"),
            (_p("stocks", transform=_string_list),))

    def operation_ids(self):
        return (["market.full_tick"] + (["market.history_1m"] if self._history is not None else [])
            + (["account.trade_detail"] if self._account is not None else []))

    def execute(self, operation_id, bindings, arguments=None, *, deadline=None):
        if operation_id == 'account.trade_detail' and self._account is not None:
            return self._account.execute(arguments, deadline)
        if operation_id == 'market.history_1m' and self._history is not None:
            return self._history.execute(arguments,deadline)
        if operation_id != "market.full_tick":
            raise UnknownOperationError(operation_id)
        if not isinstance(bindings, QMTBindings):
            bindings = QMTBindings(bindings)
        return self._adapter.execute(bindings, arguments or {})
