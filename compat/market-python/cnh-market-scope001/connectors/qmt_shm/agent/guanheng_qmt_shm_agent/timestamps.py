# -*- coding: utf-8 -*-
"""Original exact RFC3339 helpers; owns no account or observation state."""
from datetime import datetime, timedelta, timezone
import re
from .protocol import ProtocolError

def _source_timestamp_parts(value):
    """Parse one original RFC3339 instant, retaining all nine fraction digits.

    The datetime part has Python's microsecond precision; the remaining 0..999
    nanoseconds belong to the same instant, not a rounded subsequent clock tick.
    """
    match = re.fullmatch(r"(\d{4}-\d{2}-\d{2})[Tt](\d{2}:\d{2}:\d{2})(?:\.(\d{1,9}))?([Zz]|[+-]\d{2}:\d{2})", value) if isinstance(value, str) else None
    if match is None:
        raise ProtocolError("observation requires an original aware timestamp")
    day, clock, fraction, offset = match.groups()
    try:
        instant = datetime(*(int(part) for part in day.split("-") + clock.split(":")))
        delta = timedelta(0)
        if offset not in ("Z", "z"):
            hours, minutes = int(offset[1:3]), int(offset[4:6])
            if hours > 23 or minutes > 59:
                raise ValueError("invalid timezone offset")
            delta = timedelta(hours=hours, minutes=minutes) * (1 if offset[0] == "+" else -1)
        nanoseconds = int(((fraction or "") + "000000000")[:9])
        return (instant.replace(microsecond=nanoseconds // 1000, tzinfo=timezone(delta)), nanoseconds % 1000)
    except ValueError as exc:
        raise ProtocolError("invalid original observation timestamp") from exc


def source_timestamp(value):
    """Original aware datetime interface, preserving its microsecond semantics.

    Python 3.6 consumers needing exact future/age comparisons use
    source_timestamp_ns; immutable text provenance uses source_timestamp_text.
    """
    return _source_timestamp_parts(value)[0]


def _source_utc_parts(value):
    instant, remainder = _source_timestamp_parts(value)
    try:
        return instant.astimezone(timezone.utc), remainder
    except (OverflowError, ValueError) as exc:
        raise ProtocolError("source timestamp lies outside the UTC calendar") from exc


def source_timestamp_ns(value):
    """Exact integer UTC nanoseconds since 1970, including negative epochs.

    No float epoch conversion or microsecond truncation participates in a
    strict boundary comparison. Input remains original aware RFC3339 text.
    """
    instant, remainder = _source_utc_parts(value)
    delta = instant - datetime(1970, 1, 1, tzinfo=timezone.utc)
    return ((delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds) * 1000 + remainder


def source_timestamp_text(value):
    """Normalize UTC text without losing an original sub-microsecond instant.

    Microsecond-representable values retain the existing datetime ISO spelling;
    a nonzero remainder adds the final three digits, keeping all provenance.
    """
    instant, remainder = _source_utc_parts(value)
    if not remainder:
        return instant.isoformat()
    text = instant.isoformat(timespec="microseconds")
    return text[:-6] + "{0:03d}".format(remainder) + text[-6:]
