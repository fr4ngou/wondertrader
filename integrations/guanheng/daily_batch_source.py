"""闭合日日线批读的通信代接续；原SDK继续拥有请求、结果和消费确认。"""
import hashlib
from pathlib import Path

from guanheng_qmt_shm.analysis_batch_source import BatchAnalysisSource
from guanheng_qmt_shm.read_retention_client import RetainedReadClient, RetainedReadBindingChanged

from ..guanheng_market_client import strict_json
from .daily_gap_update import _hpr_business_identity
from .market_generation import encode, read_fixed


class _DailyBatchClient(RetainedReadClient):
    """只为同一业务来源选择通信代；原槽的UUID、票据和截止始终保持。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._capture_context = None  # 本调用线程的新槽准入上下文(anchor, generation目录)；SDK返回时释放。

    def _binding(self, deadline, *, require_retention=True):
        metadata = super()._binding(deadline, require_retention=require_retention)
        if self._capture_context is not None:
            anchor, generations = self._capture_context
            if _hpr_business_identity(metadata) != _hpr_business_identity(anchor):
                raise RetainedReadBindingChanged('daily_batch_business_identity_changed')
            # 核原SDK实际交给plan的完整metadata，避免预检与新槽准入之间换代。
            from guanheng_qmt_shm.market_daily_preparation import _original
            generations.mkdir(exist_ok=True)
            digest = hashlib.sha256(encode(metadata['binding'])).hexdigest()
            _original(generations / (digest + '.json'), metadata)
        return metadata

    def read(self, operation, arguments, slot, *, deadline, expected_binding=None, **kwargs):
        slot = Path(slot)
        anchor = strict_json(read_fixed(slot.parent.parent / 'BINDING.json', maximum=1048576))
        if operation != 'market.market_data' or anchor['binding'] != expected_binding:
            raise ValueError('daily batch original capture identity differs')
        generations = slot.parent.parent / 'read-generations'
        if slot.exists():
            original = strict_json(read_fixed(slot, maximum=16777216))
            binding = original['binding']
            if binding == anchor['binding']:
                selected = anchor
            else:
                digest = hashlib.sha256(encode(binding)).hexdigest()
                selected = strict_json(read_fixed(generations / (digest + '.json'), maximum=1048576))
            if (selected['binding'] != binding or selected['profile'] != original['profile']
                    or selected['limits'] != original['limits']):
                raise ValueError('daily batch original slot generation differs')
            if _hpr_business_identity(selected) != _hpr_business_identity(anchor):
                raise RetainedReadBindingChanged('daily_batch_business_identity_changed')
            expected = selected['binding']
        else:
            expected = None  # 新槽的实际metadata由上面的SDK准入钩子统一认证、比较和保存。
        self._capture_context = (anchor, generations)
        try:
            # 已存在槽交原SDK续核原身份；未知结果不生成后继请求。
            return super().read(operation, arguments, slot, deadline=deadline,
                                expected_binding=expected, **kwargs)
        finally:
            self._capture_context = None


class DailyBatchAnalysisSource(BatchAnalysisSource):
    """日线owner显式选择；批次分片、数值验证、manifest和SDK默认行为沿原实现。

    同一capture的来源路由、权限、profile、额度及业务参数保持一致，
    Host/运输代次允许变化。每个批次仍单独保存实际binding和原始结果。
    """

    def __init__(self, transport, *, lifetime_ms=30000):
        self.client = _DailyBatchClient(transport, lifetime_ms=lifetime_ms)  # 原SDK请求owner，随调用线程关闭transport。
