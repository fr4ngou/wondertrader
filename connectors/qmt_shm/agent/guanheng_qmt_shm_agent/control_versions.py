# -*- coding: utf-8 -*-
"""按显式版本选 grammar；只读配置仍单独锁定原 base 1.0。"""
from . import control_wire

def control_contract(version):
    if type(version) is str and version == control_wire.CONTRACT_VERSION:
        return control_wire
    if type(version) is str and version == '2.0':
        from . import control_wire_trade
        return control_wire_trade
    if type(version) is str and version == '3.0':
        from . import control_wire_bulk
        return control_wire_bulk
    raise ValueError("unsupported explicit control version")
