# -*- coding: utf-8 -*-
"""One memory completion shared by read and command queue owners.

Producers publish once and transfer their already-frozen result to the caller.
Owners outside the strategy thread may wait; explicit control cycles use poll.
Importing this module creates no worker, socket or file.
"""
import threading


class MemoryCompletion(object):
    def __init__(self):
        self._ready, self._lock = threading.Event(), threading.Lock()
        self._value, self._cancelled = None, False

    def publish(self, value):
        with self._lock:
            if not self._ready.is_set():
                self._value = value
                self._ready.set()

    def wait(self, seconds):
        """External-owner wait, in seconds; timeout grants no business fact."""
        if not self._ready.wait(seconds):
            raise TimeoutError("strategy work did not complete within its budget")
        return self._result()

    def _result(self):
        if self._cancelled:
            raise OSError("work binding closed before completion")
        return self._value

    def cancel(self):
        with self._lock:
            if not self._ready.is_set():
                self._cancelled = True
                self._ready.set()

    def poll(self):
        """Nonblocking control-owner read; None means no completion yet."""
        with self._lock:
            return self._result() if self._ready.is_set() else None
