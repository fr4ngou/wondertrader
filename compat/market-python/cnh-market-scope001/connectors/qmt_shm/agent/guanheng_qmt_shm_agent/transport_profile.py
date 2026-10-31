# -*- coding: utf-8 -*-
"""运输配置的唯一纯分派；版本选择不创建对象、不回退到另一种后端。"""


def validate_transport_profile(config, route, max_frame, business_profile):
    """返回已冻结布局；旧shm和本仓builtin配对分别拥有配置及互操作资格。"""
    if type(config) is not dict:
        raise ValueError("explicit local transport profile required")
    kind = config.get("kind")
    if kind == "shm":
        from .shm_codec import SharedMemoryProfile
        return SharedMemoryProfile(config, route, max_frame, business_profile)
    if kind == "builtin-shm":
        from .builtin_shm import BuiltinMemoryProfile
        return BuiltinMemoryProfile(config, route, max_frame, business_profile)
    raise ValueError("unsupported local transport kind")
