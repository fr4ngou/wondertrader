"""补齐复用同一bound Journal；已派发中断永远按未知结果保留。"""
import time
from guanheng_qmt_shm_agent.history_preparation import OPERATION, require_live, now_ms
from .bound_journal import BoundReadJournal


class HistoryPreparationJournal(BoundReadJournal):
    def __init__(self, *args, clock, **kwargs):
        self.preparation_clock = clock
        self.preparation_scope = kwargs['read_profile']['operation_profiles'][OPERATION]['limits']
        super().__init__(*args, **kwargs)

    def _admit_new_bound(self, request, queue_timeout_ms):
        if request['operation_id'] == OPERATION:
            remaining = require_live(request['arguments'], self.preparation_scope, self.preparation_clock)
            return time.time() + min(queue_timeout_ms, remaining) / 1000
        return super()._admit_new_bound(request, queue_timeout_ms)

    def _queued_bound_failure(self, request):
        if request['operation_id'] == OPERATION and now_ms(self.preparation_clock) >= request['arguments']['deadline_ms']:
            return 'preparation_not_executed'
        return super()._queued_bound_failure(request)

    def _interrupted_result(self, rid, operation, code):
        if operation == OPERATION:
            # 只准原领取前的三项事实授未执行；其余中断原因保守保持未知。
            code = ('preparation_not_executed' if code in
                ('queue_timeout', 'source_binding_changed', 'preparation_not_executed') else 'preparation_unknown')
            result = super()._interrupted_result(rid, operation, code)
            result['error_message'] = ('历史补齐结果未知；保留原ID，先回读核查，禁止自动重试'
                if code == 'preparation_unknown' else '历史补齐在派发前结束，未执行下载')
            return result
        return super()._interrupted_result(rid, operation, code)
