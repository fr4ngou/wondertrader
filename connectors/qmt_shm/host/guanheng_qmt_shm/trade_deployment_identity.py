"""原Source部署材料的无秘密身份投影；不打开Journal、网络、SDK或运行owner。"""
import hashlib
from pathlib import Path
from guanheng_qmt_shm_agent.protocol import canonical
from guanheng_qmt_shm_agent.trading_contract import validate_trade_binding
from .trade_pair import _decode_reference_deployment


def reference_deployment_identity(raw):
    """沿完整原decoder取Host，供恢复核原Journal；完整Source准入另归原工厂。"""
    if type(raw)is not bytes or not 1<=len(raw)<=16*1024*1024:
        raise ValueError('source deployment identity bytes invalid')
    decoded=_decode_reference_deployment(raw);host=decoded[0]
    if type(host)is not dict or type(host.get('journal_path'))is not str or not Path(host['journal_path']).is_absolute():
        raise ValueError('source deployment journal identity invalid')
    binding=validate_trade_binding(host['trade_binding'])
    return dict(
        schema='qmt.trade-deployment-origin.v1',  # 原部署提取协议，不代表Source已启动或scope已采用。
        deployment_sha256=hashlib.sha256(raw).hexdigest(),  # 原部署完整字节SHA，不复制或发布凭据。
        journal_path=str(Path(host['journal_path'])),  # 原Host声明的绝对Journal位置；备份属于不同owner。
        trade_binding_sha256=hashlib.sha256(canonical(binding)).hexdigest())  # 原Source唯一交易绑定规范身份；账户正文不出投影。
