"""显式只读常驻部署合同；纯准入，不构造Agent、Host或运输owner。"""
import math
from guanheng_qmt_shm_agent.protocol import canonical, decode


def validate_connection_lifecycle(value):
    """None保留原单代入口；新值按完整封闭结构冻结，禁止静默默认或回退。"""
    if value is None:
        return None
    if (type(value) is not dict
            or set(value) != {'schema_version', 'mode', 'reconnect_seconds'}
            or type(value['schema_version']) is not str or type(value['mode']) is not str
            or value['schema_version'] != 'qmt.read-resident.v1'
            or value['mode'] != 'resident-read'):
        raise ValueError('invalid explicit read connection lifecycle')
    seconds = value['reconnect_seconds']
    if (type(seconds) not in (int, float) or not 0.1 <= seconds <= 60
            or not math.isfinite(seconds)):
        raise ValueError('read reconnect interval must be 0.1..60 seconds')
    return decode(canonical(value))
