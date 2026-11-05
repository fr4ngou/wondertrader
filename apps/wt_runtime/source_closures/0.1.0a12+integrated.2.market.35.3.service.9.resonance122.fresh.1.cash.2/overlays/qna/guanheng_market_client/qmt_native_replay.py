"""SDK 的逐日回放公开入口；计算和校验统一使用原回放实现。

本文件由原生分析 core 制品映射到 guanheng_market_client.qmt_native_replay。
基础行情 SDK 的既有文件保持；仅安装回放能力的消费者取得此可选子模块。
"""
from integrations.guanheng.qmt_native_replay import ReplayCatalog

__all__ = ["ReplayCatalog"]
