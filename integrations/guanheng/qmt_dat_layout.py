"""已核QMT DAT计数字段布局；原生ABI与通用来源数值规则保持独立。"""
import struct

MAGIC = bytes.fromhex("feffffffffffff7f")
RECORD_BYTES = 64
DATASET_VERSION = "qmt-local-dat-layout.v2"
LEGACY_DATASET_VERSION = "qmt-local-dat-layout.v1"
# 24..27为有符号成交量，28..31不由本路径消费，32..39为有符号成交额。
COUNTERS = struct.Struct("<i4xq")
MAX_VOLUME = (1 << 31) - 1
AMOUNT_FLOAT_BOUNDARY = float(1 << 63)


def local_dat_counters_valid(dataset_version, volume, amount):
    """旧v1的高位回绕不可作为正数消费；其他来源不套用DAT字段范围。

    v1金额double到达2**63时，已无法区分符号回绕与边界舍入，保持拒绝。
    v2在原整数解码阶段已拒绝负值，允许合法int64上界转double后的舍入。
    """
    dataset_version = dataset_version.partition(':')[0]
    if dataset_version not in (LEGACY_DATASET_VERSION, DATASET_VERSION):
        return True
    if not 0 <= volume <= MAX_VOLUME or amount < 0:
        return False
    return amount < AMOUNT_FLOAT_BOUNDARY if dataset_version == LEGACY_DATASET_VERSION else amount <= AMOUNT_FLOAT_BOUNDARY
