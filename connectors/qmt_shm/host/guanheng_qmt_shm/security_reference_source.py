"""证券资料Source消费接缝；复用原保留客户端/slot，不创建终端外SDK或新数据账本。"""
import json
from pathlib import Path
from guanheng_qmt_shm_agent.security_reference import (
    UNIVERSE, DETAILS, POLICY, CONFIRMED_ERRORS, arguments, validate_result)
from .read_retention_client import RetainedReadClient, RetainedReadFailure
from guanheng_qmt_shm_agent.security_price_roles import source_price_role


class SecurityReferenceFailure(RetainedReadFailure):
    def __init__(self, code):
        self.code = code  # 已保存原终态的固定分类；目录过期后由数据owner明确结束本次捕获。
        super().__init__(code)


class SecurityReferenceSource:
    """单调用线程持有原transport；slot为原请求持久文件，deadline为单调绝对秒。"""
    def __init__(self, transport, *, wait_for_active_capacity=False):
        """批捕获可等待原准入额度；缺省保留单次观察行为，未知责任始终交回owner。"""
        self.client = RetainedReadClient(transport, lifetime_ms=30000,
            wait_for_active_capacity=wait_for_active_capacity)  # 原30秒票据/nonce额度及原结果持久owner。

    def capabilities(self, *, deadline):
        """认证metadata发现两操作及30秒保留额度；不生成业务请求、slot或SDK调用。"""
        metadata = self.client.metadata(deadline=deadline)
        entries = metadata['profile'].get('operation_profiles', {})
        ready = all(op in entries and entries[op]['policy_id'] == POLICY and entries[op]['policy_version'] == '1.0'
                    for op in (UNIVERSE, DETAILS))
        # 本消费接缝使用原30秒ticket；有操作名但没有相应保留额度仍等待能力交付。
        retention = metadata['profile'].get('read_retention', {})
        ready = ready and retention.get('max_lifetime_ms', 0) >= 30000
        return dict(
            state='ready' if ready else 'waiting_reference_capability',  # 能力状态；原价格通道继续独立服务。
            metadata=metadata,  # 原认证metadata及已校验profile，不把当前绑定冒充旧slot绑定。
        )

    def _read(self, operation, request, slot, deadline, expected_binding):
        path = Path(slot)
        if path.exists():
            # 旧slot即使Source换代也先沿原UUID续核，不以新metadata替换尚未知的原请求。
            profile = json.loads(path.read_bytes())['profile']
            binding = None
        else:
            found = self.capabilities(deadline=deadline)
            if found['state'] != 'ready':
                return dict(
                    state='waiting_reference_capability',  # 新能力尚未交付，本次未产生请求或slot。
                    result=None,  # 尚无原结果；调用方保留既有成功数据。
                )
            profile = found['metadata']['profile']
            # 整次捕获的绑定由数据owner固定；最终准入仍由原客户端在创建slot前原子核验。
            binding = expected_binding if expected_binding is not None else found['metadata']['binding']
        descriptor = profile['operation_profiles'][operation]
        arguments(operation, request, descriptor['limits'])
        try:
            result = self.client.read(operation, request, path, deadline=deadline, expected_binding=binding)
        except RetainedReadFailure:
            if not path.exists():
                raise  # 绑定换代等准入拒绝尚未创建原slot，保留原分类。
            record = json.loads(path.read_bytes())
            saved = record.get('result')
            if saved is not None:
                from .bound import unb64
                reply = json.loads(unb64(saved['result_body_b64'], record['limits']['max_result_bytes']))
                if reply.get('error_code') in CONFIRMED_ERRORS:
                    raise SecurityReferenceFailure(reply['error_code']) from None
            raise
        validate_result(dict(operation_id=operation, arguments=request), result['reply'])
        # 原slot经保留客户端完整校验；返回原Source绑定，不从当前metadata重建旧请求。
        result['binding'] = json.loads(path.read_bytes())['binding']
        return dict(
            state='observed',  # 本次原结果已保存及确认消费，资料完整性仍由data逐组表达。
            result=result,  # 原UUID、绑定、请求/接收时刻及reply；原bytes/SHA继续保存在同一slot。
        )

    def universe(self, request, slot, *, deadline, expected_binding=None):
        """单页原请求；expected_binding为整次捕获的原绑定，旧slot始终沿原身份。"""
        return self._read(UNIVERSE, request, slot, deadline, expected_binding)

    def details(self, request, slot, *, deadline, expected_binding=None):
        """逐只缺项仍保留证券；expected_binding约束新slot，返回原binding/UUID。"""
        return self._read(DETAILS, request, slot, deadline, expected_binding)
