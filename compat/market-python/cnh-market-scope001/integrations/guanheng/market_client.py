"""Compatibility imports; the sole implementation is guanheng_market_client."""
from .. import guanheng_market_client as _implementation
from ..guanheng_market_client import *  # noqa: F403 - preserve the existing public imports.


def __getattr__(name):
    # The native service also imports the original private wire helpers.
    return getattr(_implementation, name)
