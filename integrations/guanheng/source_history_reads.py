"""历史准备复用既有保留客户端；旧协议显式保留，新协议不再自行提交或消费结果。"""
import json
from pathlib import Path
import re
from uuid import uuid4

from .source_history_transport import SourcePending, require


class HistoryReadOperations:
    """原SourcePreparingMarket单线程拥有；本地slot文件不另造Host请求身份。"""
    def __init__(self, transport, root, *, retained=False):
        self.transport = transport  # 原唯一签名HTTP连接及Source绑定校验。
        self.root = Path(root)  # 原准备workspace；slots只写已有窗口目录下的retained-reads。
        self.client = None  # 显式旧协议保持原transport；新协议采用原保留客户端。
        if retained:
            from guanheng_qmt_shm.read_retention_client import RetainedReadClient
            self.client = RetainedReadClient(transport, lifetime_ms=300000)

    def plan(self, operation, arguments, metadata, deadline, directory):
        """保存待观察参数；新协议的真实请求ID/票据由原客户端在首次准入时固定。"""
        if self.client is None:
            return self.transport.plan(operation, arguments, metadata, deadline)
        directory = Path(directory)
        self._directory(directory)
        slots = directory / 'retained-reads'
        slots.mkdir(exist_ok=True)
        return dict(
            request=dict(operation_id=operation, arguments=arguments, request_id=None),  # 尚未生成Host身份，参数由原client准入。
            binding=metadata['binding'], profile=metadata['profile'], limits=metadata['limits'],  # 原认证事实，禁止换代偷换。
            attempted=False, result=None,  # 尚未派发，原结果未知。
            retained_slot=str(slots / (uuid4().hex + '.json')))  # 仅本地原slot名称，传输ID仍由唯一客户端生成。

    def observe(self, record, save, deadline):
        """无论成功或Pending均将原slot身份同步回窗口；重启续核同一原请求。"""
        if self.client is None:
            return self.transport.observe(record, save, deadline)
        from guanheng_qmt_shm.read_retention_client import RetainedReadPending, RetainedReadFailure
        slot = Path(record['retained_slot'])
        self._directory(slot.parent.parent)
        require(slot.parent.name == 'retained-reads' and re.fullmatch(r'[0-9a-f]{32}\.json', slot.name) is not None)
        operation, arguments = record['request']['operation_id'], record['request']['arguments']
        require(operation in ('market.history_1m', 'market.history_prepare'))
        try:
            result = self.client.read(operation, arguments, slot, deadline=deadline, expected_binding=record['binding'])
            return result['reply']
        except RetainedReadPending as error:
            raise SourcePending('retained original history observation pending') from error
        except RetainedReadFailure as error:
            raise ValueError('retained original history observation failed') from error
        finally:
            if slot.exists():
                # 唯一客户端已先持久保存真实ID/票据/结果/消费确认；窗口只保存其同一投影。
                original = json.loads(slot.read_bytes())
                require(original['request']['operation_id'] == operation and original['request']['arguments'] == arguments
                        and original['binding'] == record['binding'])
                location = record['retained_slot']
                record.clear()
                record.update(original, retained_slot=location)
                save()

    def _directory(self, directory):
        parts = directory.relative_to(self.root).parts
        require(len(parts) in (1, 2) and re.fullmatch('[0-9a-f]{64}', parts[-1]) is not None
                and (len(parts) == 1 or re.fullmatch(r'(SSE|SZSE)\.[0-9]{6}', parts[0]) is not None))
