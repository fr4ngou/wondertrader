"""Compatibility imports; the independent SDK owns the only runner implementation."""
from ..guanheng_market_client import history_runner as _implementation
from ..guanheng_market_client.history_runner import *  # noqa: F403


def __getattr__(name):
    return getattr(_implementation, name)
