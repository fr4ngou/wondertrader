# -*- coding: utf-8 -*-
"""显式v5只读Agent；复用原运输和普通读取，额外保留bulk采集owner。"""
import threading
import time

from .restricted import RestrictedReadAgent
from .bulk_configuration import validate_bulk_configuration
from .bulk_service import SourceBulkHistoryService
from .control_bulk_agent import BulkAgentControlLoop


class RestrictedBulkReadAgent(RestrictedReadAgent):
    def __init__(self, context, *, trusted_bootstrap, trade_detail_query=None,
                 clock=None, monotonic=None, as_of_date_provider=None):
        admitted = validate_bulk_configuration(trusted_bootstrap)
        self.bulk = SourceBulkHistoryService(context, admitted.profile, admitted.value['max_result_bytes'],
            clock=clock, monotonic=monotonic, as_of_date_provider=as_of_date_provider)
        self._initialize(context, admitted, trade_detail_query)

    def _make_control(self, session):
        return BulkAgentControlLoop(self, session)

    def tick(self, allow_heavy=True):
        if threading.get_ident() != self._thread_id:
            raise RuntimeError('bulk execution requires the original strategy thread')
        if type(allow_heavy) is not bool:
            raise ValueError('native task permission must be a literal bool')
        self.bulk.expire()
        if not self._stop.is_set() and self.connected.is_set() and self.bulk.tick(allow_heavy):
            self.last_tick = time.time()
            return True
        return RestrictedReadAgent.tick(self, allow_heavy)

    def _run(self):
        try:
            RestrictedReadAgent._run(self)
        finally:
            # 连接尚未建立或control构造失败时，也冻结本代排队采集。
            self.bulk.request_close()

    def request_close(self):
        try:
            self.bulk.request_close()
        finally:
            RestrictedReadAgent.request_close(self)

    def close(self, deadline):
        RestrictedReadAgent.close(self, deadline)
        if not self.bulk.drained:
            raise RuntimeError('bulk source ownership is still pending; retain agent')
