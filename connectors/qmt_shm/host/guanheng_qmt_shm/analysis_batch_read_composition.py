"""同正文批量分析只组合原 v8 设置；请求、SDK及批次结果仍由 QAB 拥有。"""
from guanheng_qmt_shm_agent.analysis_batch import PROFILE_VERSION
from guanheng_qmt_shm_agent.analysis_reads import DAILY
from guanheng_qmt_shm_agent.read_configuration import validate_read_configuration
from .account_read_composition import _read_material, _load_read_pair
from .lifecycle import validate_connection_lifecycle


def admit_analysis_batch_read(value):
    """沿原能力准入，仅接显式 v8 批量日线，不改变原 v7 分析设置。"""
    if type(value) is not dict or set(value) != {'agent', 'reconnect_seconds'}:
        raise ValueError('explicit batch analysis composition fields differ')
    admitted = validate_read_configuration(value['agent'])
    if (admitted.value.get('read_profile_version') != PROFILE_VERSION
            or admitted.profile['read_operations'] != [DAILY]
            or admitted.value['transport']['kind'] != 'builtin-shm'):
        raise ValueError('batch analysis composition requires original builtin v8 profile')
    interval = validate_connection_lifecycle(dict(schema_version='qmt.read-resident.v1',
        mode='resident-read', reconnect_seconds=value['reconnect_seconds']))['reconnect_seconds']
    return dict(agent=dict(admitted.value, secret=admitted.secret), reconnect_seconds=interval), admitted.profile


def analysis_batch_read_material(value, *, decode_secrets=False):
    """原 IPC 身份沿统一私有材料边界编码；QMT 内恢复原 bytes。"""
    return _read_material(value, admit_analysis_batch_read, decode_secrets=decode_secrets)


def load_analysis_batch_read_pair(directory, *, installed_agent=None):
    """原 resident 验证器拥有完整来源核验，只导出同次已核内存快照。"""
    return _load_read_pair(directory, admit_analysis_batch_read, installed_agent=installed_agent)
