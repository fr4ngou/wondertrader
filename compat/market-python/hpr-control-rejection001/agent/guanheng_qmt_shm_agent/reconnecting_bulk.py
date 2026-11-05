# -*- coding: utf-8 -*-
"""显式v5常驻入口；原QMT tick只在前代实际退出后认领下一代。"""
from .bulk_agent import RestrictedBulkReadAgent
from .bulk_configuration import validate_bulk_configuration
from .reconnecting_read import ReconnectingReadAgent


class ReconnectingBulkReadAgent(ReconnectingReadAgent):
    """复用原重连生命周期；旧range不进入新代的SDK队列。

    clock是已核共享uptime对象，monotonic属于本地控制期限；可信测试可
    显式注入。构造只冻结配置，第一次原线程tick才创建单代agent。
    """
    def __init__(self, context, *, trusted_bootstrap, reconnect_seconds,
                 enabled=False, trade_detail_query=None, clock=None,
                 monotonic=None, as_of_date_provider=None):
        if clock is not None and not callable(getattr(clock, 'seconds', None)):
            raise ValueError('explicit bulk shared clock object required')
        if monotonic is not None and not callable(monotonic):
            raise ValueError('explicit bulk local monotonic clock required')
        if as_of_date_provider is not None and not callable(as_of_date_provider):
            raise ValueError('explicit bulk date provider required')
        self._bulk_clock = clock
        self._bulk_monotonic = monotonic
        self._bulk_as_of = as_of_date_provider
        ReconnectingReadAgent.__init__(self, context,
            trusted_bootstrap=trusted_bootstrap, reconnect_seconds=reconnect_seconds,
            enabled=enabled, trade_detail_query=trade_detail_query)

    def _admit_configuration(self, trusted_bootstrap):
        return validate_bulk_configuration(trusted_bootstrap)

    def _make_agent(self):
        return RestrictedBulkReadAgent(self._context,
            trusted_bootstrap=self._bootstrap, trade_detail_query=self._read,
            clock=self._bulk_clock, monotonic=self._bulk_monotonic,
            as_of_date_provider=self._bulk_as_of)
