"""同正文分析连接只导出原v7内存设置；准入及读取仍由原Read实现负责。"""
from guanheng_qmt_shm_agent.analysis_reads import DAILY, FACTORS, PROFILE_VERSION
from guanheng_qmt_shm_agent.read_configuration import validate_read_configuration
from .account_read_composition import _read_material, _load_read_pair
from .lifecycle import validate_connection_lifecycle


def admit_analysis_read(value):
    """仅接原两种分析操作；账户/下载/交易仍由各自原连接授权。"""
    if type(value) is not dict or set(value) != {'agent', 'reconnect_seconds'}:
        raise ValueError('explicit analysis read composition fields differ')
    admitted = validate_read_configuration(value['agent'])
    if (admitted.value.get('read_profile_version') != PROFILE_VERSION
            or set(admitted.profile['read_operations']) != {DAILY, FACTORS}
            or admitted.value['transport']['kind'] != 'builtin-shm'):
        raise ValueError('analysis composition requires its original builtin v7 read profile')
    interval = validate_connection_lifecycle(dict(schema_version='qmt.read-resident.v1',
        mode='resident-read', reconnect_seconds=value['reconnect_seconds']))['reconnect_seconds']
    return dict(agent=dict(admitted.value, secret=admitted.secret), reconnect_seconds=interval), admitted.profile


def analysis_read_material(value, *, decode_secrets=False):
    """原IPC秘密仅进入私有快照，沿只读材料的唯一编解码实现。"""
    return _read_material(value, admit_analysis_read, decode_secrets=decode_secrets)


def load_analysis_read_pair(directory, *, installed_agent=None):
    """原resident配对验证全部安装及正文后，导出同次已核v7快照。"""
    return _load_read_pair(directory, admit_analysis_read, installed_agent=installed_agent)
