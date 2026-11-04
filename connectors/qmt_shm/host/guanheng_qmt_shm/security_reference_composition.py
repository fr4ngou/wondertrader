"""证券资料显式只读连接接入唯一正文；复用原配对、材料及生命周期责任。"""
from guanheng_qmt_shm_agent.security_reference import OPERATIONS,PROFILE_VERSION
from guanheng_qmt_shm_agent.read_configuration import validate_read_configuration
from .account_read_composition import _read_material,_load_read_pair
from .lifecycle import validate_connection_lifecycle


def admit_security_reference_read(value):
    """纯准入原v9设置；同Context独立连接，不创建SDK/SHM/HTTP资源。"""
    if type(value)is not dict or set(value)!={'agent','reconnect_seconds'}:
        raise ValueError('explicit security reference composition fields differ')
    admitted=validate_read_configuration(value['agent'])
    if (admitted.value.get('read_profile_version')!=PROFILE_VERSION
            or admitted.profile['read_operations']!=sorted(OPERATIONS)
            or admitted.value['transport']['kind']!='builtin-shm'
            or admitted.profile.get('read_retention',{}).get('max_lifetime_ms',0)<30000):
        raise ValueError('security reference requires its original retained builtin v9 profile')
    interval=validate_connection_lifecycle(dict(schema_version='qmt.read-resident.v1',
        mode='resident-read',reconnect_seconds=value['reconnect_seconds']))['reconnect_seconds']
    return dict(
        agent=dict(admitted.value,secret=admitted.secret),  # 已认证原配置和IPC bytes；仅进入私有正文。
        reconnect_seconds=interval,  # 原resident代际重连间隔秒；不改变原请求截止或重派资格。
    ),admitted.profile


def security_reference_read_material(value,*,decode_secrets=False):
    """沿原私有JSON secret_hex边界；公开结果不返回IPC身份。"""
    return _read_material(value,admit_security_reference_read,decode_secrets=decode_secrets)


def load_security_reference_read_pair(directory,*,installed_agent=None):
    """核同次原resident配对后导出设置；不运行来源或改写原配对。"""
    return _load_read_pair(directory,admit_security_reference_read,installed_agent=installed_agent)
