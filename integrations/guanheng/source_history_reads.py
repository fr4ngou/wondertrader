"""历史准备复用既有保留客户端；旧协议显式保留，新协议不再自行提交或消费结果。"""
import json
from pathlib import Path
import re
from uuid import uuid4

from .source_history_transport import SourcePending, require


READ_TICKET_ENDED = 'read_ticket_ended_unretained'


def retained_resume_state(state, request_id=None, scanned_windows=0):
    """原读取责任接续的有界观察；业务成功及分钟完整性仍由原窗口持有。"""
    return dict(
        state=state,  # ticket_ended 表示原只读结果已不可领取，其余值描述原消费交接进度。
        request_id=request_id,  # 正在续核的原Host请求ID；无原请求时为None，不生成新ID。
        scanned_windows=scanned_windows)  # 本次管理步已检查的窗口数，不是全库总数。


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

    def saved_reply(self, record):
        """投影本地已核终态，无网络、确认或新请求；未交接的保留结果继续显示待定。"""
        if self.client is None:
            if record.get('result') is None:
                return None
            # 原协议 result 已持久存在时 observe 只校验与解码。
            return self.transport.observe(record, lambda: None, float('inf'))
        from guanheng_qmt_shm.read_retention_client import inspect_saved_result
        return inspect_saved_result(record)

    def can_replace_local_plan(self, record):
        """原保留槽生成后拥有固定请求身份，窗口中的尚未同步投影不能覆盖它。"""
        if self.client is None or record['attempted'] or record['request']['request_id'] is not None:
            return False
        slot = Path(record['retained_slot'])
        self._directory(slot.parent.parent)
        require(slot.parent.name == 'retained-reads' and re.fullmatch(r'[0-9a-f]{32}\.json', slot.name) is not None)
        return not slot.exists()

    def observe(self, record, save, deadline):
        """无论成功或Pending均将原slot身份同步回窗口；重启续核同一原请求。"""
        if self.client is None:
            return self.transport.observe(record, save, deadline)
        from guanheng_qmt_shm.read_retention_client import (
            RetainedReadPending, RetainedReadFailure, RetainedReadTicketEnded)
        slot = Path(record['retained_slot'])
        self._directory(slot.parent.parent)
        require(slot.parent.name == 'retained-reads' and re.fullmatch(r'[0-9a-f]{32}\.json', slot.name) is not None)
        operation, arguments = record['request']['operation_id'], record['request']['arguments']
        require(operation in ('market.history_1m', 'market.history_prepare'))
        read_end = record.get('read_end')
        if read_end == READ_TICKET_ENDED:
            raise SourcePending(read_end)
        if record.get('consumed') is True:
            from guanheng_qmt_shm.read_retention_client import inspect_saved_result
            # 原窗口已经保存完整响应；成功页复用相同严格校验，避免分页恢复反复读旧slot。
            reply = inspect_saved_result(record)
            if reply is not None and reply['ok'] is True:
                return reply
        try:
            result = self.client.read(operation, arguments, slot, deadline=deadline, expected_binding=record['binding'])
            return result['reply']
        except RetainedReadTicketEnded as error:
            if operation == 'market.history_1m':
                read_end = READ_TICKET_ENDED
            raise SourcePending(READ_TICKET_ENDED) from error
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
                if read_end is not None:
                    record['read_end'] = read_end
                save()

    def resume_existing(self, record, save, deadline):
        """只交接已派发的原slot；从不创建slot或提交bound-operation。"""
        if self.client is None or record.get('retained_slot') is None or record.get('read_end') == READ_TICKET_ENDED:
            return None
        slot = Path(record['retained_slot'])
        self._directory(slot.parent.parent)
        require(slot.parent.name == 'retained-reads' and re.fullmatch(r'[0-9a-f]{32}\.json', slot.name) is not None)
        if not slot.exists():
            return None
        original = json.loads(slot.read_bytes())
        require(original['request']['operation_id'] == record['request']['operation_id']
                and original['request']['arguments'] == record['request']['arguments']
                and original['binding'] == record['binding'])
        rid = record['request'].get('request_id')
        require(rid is None or rid == original['request']['request_id'])
        from guanheng_qmt_shm.read_retention_client import inspect_saved_result
        inspect_saved_result(original)  # 原请求、票据、profile及已有结果沿唯一客户端验证器校验。
        if not original['attempted'] or original.get('admission_rejection') is not None:
            return None
        # 读取前已核原slot且只有本owner写入，client必走lookup或已有完整结果的确认路径。
        try:
            self.observe(record, save, deadline)
        except (SourcePending, ValueError):
            if record.get('read_end') == READ_TICKET_ENDED:
                return retained_resume_state('ticket_ended', original['request']['request_id'])
            if record.get('consumed') is not True:
                raise
            # 业务失败/未知也已完整交接，原窗口语义由原调用链继续判断。
        return retained_resume_state('consumed' if record.get('consumed') is True else 'pending',
                                     original['request']['request_id'])

    def _directory(self, directory):
        parts = directory.relative_to(self.root).parts
        require(len(parts) in (1, 2) and re.fullmatch('[0-9a-f]{64}', parts[-1]) is not None
                and (len(parts) == 1 or re.fullmatch(r'(SSE|SZSE)\.[0-9]{6}', parts[0]) is not None))
