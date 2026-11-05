"""采集投影的唯一字节预算与发布接缝；ACL和原子替换沿原实现。"""
import json
import os
from uuid import uuid4

from guanheng_qmt_shm.private_files import write_private_new
from .collection_status import replace_status


PROJECTION_LIMITS = {
    'ready.json': 65536, 'closed.json': 65536, 'failure.json': 65536,  # 原父子进程收据预算保持。
    'status.json': 65536,  # 原65秒观察合同及页面只消费此小投影。
    'coverage.json': 8388608,  # 全证券资料/订阅/报价时间及计数，最大8MiB。
    'minute-maintenance.json': 16777216,  # 全证券乘维护日期的完整进度字段，最大16MiB。
    'current-day-status.json': 65536,  # 原Writer盘中值投影状态，不携带全量行情。
}


def publish_projection(directory, name, value, replace=False):
    """同一明确预算贯穿序列化和原私有创建；关闭临时句柄后才发布完整名字。

    写入或预算校验失败保持原最终文件；本次临时文件在本次调用结束后回收。
    替换复用独立SDK的共享删除协议，不复制ACL或另造替换逻辑。
    """
    maximum = PROJECTION_LIMITS[name]
    raw = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('ascii')
    if not 0 < len(raw) <= maximum:
        raise ValueError('collection projection exceeds its declared budget')
    temporary = directory / (name + '-' + str(uuid4()) + '.tmp')
    try:
        write_private_new(temporary, raw, maximum_bytes=maximum)
        if replace:
            replace_status(temporary, directory / name)
        else:
            os.rename(temporary, directory / name)
    finally:
        temporary.unlink(missing_ok=True)
