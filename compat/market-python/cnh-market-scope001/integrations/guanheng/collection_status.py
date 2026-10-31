"""兼容导入：本地状态读写唯一实现随独立SDK发行，保留原模块对象与诊断类型身份。"""
import sys
from guanheng_market_client import runtime_status as _implementation

sys.modules[__name__] = _implementation
