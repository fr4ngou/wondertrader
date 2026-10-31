"""可选已确认读取回收的薄接缝；身份、持久结果与 consumed 归公共客户端。"""
from copy import deepcopy


def transport(configuration, *, environ=None):
    """仅剥离 AWP 连接声明的可选能力，其余四字段由原 transport 校验。"""
    from .lifecycle import AnalysisReadTransport
    connection=deepcopy(configuration)
    capability=None
    if 'read_retention' in connection:
        from guanheng_qmt_shm_agent.read_retention import retention
        capability=retention(connection.pop('read_retention'))
    original=AnalysisReadTransport(connection,environ=environ)
    client=None
    if capability is not None:
        from guanheng_qmt_shm.read_retention_client import RetainedReadClient
        client=RetainedReadClient(original)
    return original,capability,client


def check_capability(metadata, capability):
    """部署声明与认证 profile 同一能力，避免旧 profile 被当作已启用回收。"""
    if metadata['profile'].get('read_retention') != capability:
        raise ValueError('analysis_read_retention_capability')
