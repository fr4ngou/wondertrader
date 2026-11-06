"""同一日线owner的持久价格窗口读取；原SDK拥有slot/UUID及通信代恢复。"""
from datetime import datetime
from pathlib import Path
import time

from .analysis_price_capture import load_price_capture
from .daily_data_update import _descriptor
from .daily_batch_source import DailyBatchAnalysisSource
from .source_history_transport import BoundHistorySource


class PriceWindowResource(ValueError):
    """认证来源的真实资源边界；不表示证券业务不支持。"""


def capture_price_window(request, directory, connection, *, deadline, cancelled, environ=None,
                         verify_resources=False):
    """固定请求和原槽读窗口；返回capture描述符，关闭所有本次运输。

    verify_resources仅为显式长窗口预检原profile，原普通窗口默认语义保持。
    已完成捕获只读核验；超时/取消不改原请求或截止，不重置未知UUID。
    """
    root=Path(directory)
    if (root/'manifest.json').exists():
        descriptor=dict(directory=str(root.absolute()),sha256=_descriptor(root/'manifest.json')['sha256'])
        manifest=load_price_capture(descriptor)
        if manifest['request']!=request:raise ValueError('price capture original request differs')
        return descriptor
    if cancelled():raise InterruptedError('price capture stopped')
    transport=BoundHistorySource(connection,environ=environ,reuse_connections=True)
    try:
        source=DailyBatchAnalysisSource(transport,lifetime_ms=30000)
        if verify_resources:
            from guanheng_qmt_shm.analysis_batch_source import request_batches
            metadata=source.client.metadata(deadline=deadline)
            limits=metadata['profile']['operation_profiles']['market.market_data']['limits']
            first=datetime.strptime(request['start_date'],'%Y%m%d').date()
            last=datetime.strptime(request['end_date'],'%Y%m%d').date()
            if request['max_rows']>limits['max_rows']:
                raise PriceWindowResource('source_max_rows_requires_partition')
            if (last-first).days>=limits['max_calendar_days']:
                raise PriceWindowResource('source_calendar_window_requires_partition')
            try:request_batches(request['symbols'],max_rows=request['max_rows'],
                max_data_bytes=limits['max_data_bytes'],max_symbols=limits['max_symbols'])
            except ValueError as error:raise PriceWindowResource('source_result_bytes_requires_partition') from error
        def check(*unused):
            if cancelled():raise InterruptedError('price capture stopped')
            if time.monotonic()>=deadline:raise TimeoutError('price capture deadline')
        source.capture(request,root,deadline=deadline,on_result=check,minimum_new_request_seconds=30)
    finally:transport.close()
    descriptor=dict(directory=str(root.absolute()),sha256=_descriptor(root/'manifest.json')['sha256'])
    load_price_capture(descriptor)
    return descriptor
