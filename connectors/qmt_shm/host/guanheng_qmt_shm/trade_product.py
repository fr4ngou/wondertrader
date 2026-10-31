"""交易产品严格材料工厂；正式入口不执行生成host.py或动态选交易实现。"""
from .trade_pair import create_product_pair, verify_product_pair, _verified
from .trade_resident import build_service


def build_product_runtime(directory, *, installed_agent=None):
    """离线核验后的同一私有快照构造；start才取得Journal及通信owner。"""
    identity, snapshot = _verified(directory, installed_agent)
    config, credentials, unused_settings, policies, public, admitted, lifecycle = snapshot
    runtime = build_service(config, credentials, policies, public, admitted.profile,
        lifecycle['reconnect_seconds'])
    return runtime, dict(credentials['http_keys']), identity
