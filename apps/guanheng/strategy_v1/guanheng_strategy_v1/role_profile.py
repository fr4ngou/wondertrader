"""新版本固定角色选择：同一证券绑定信号、执行、实际周期和前复权历史。"""
from types import MappingProxyType

# 八角色物理证券；科创角色使用博时科创100，其余七个保持原证券身份。
ROLE_SYMBOLS = MappingProxyType({
    'csi300': '510300.SH', 'sh50': '510050.SH', 'zz500': '510500.SH',
    'zz1000': '512100.SH', 'kc50': '588000.SH', 'kc_composite': '588030.SH',
    'sc50': '159780.SZ', 'dividend': '515080.SH',
})
# 科创100分析与执行使用同一实物基金，绝不借其他ETF行情作为止损参考。
KC_SYMBOL = ROLE_SYMBOLS['kc_composite']
# 本次替换的前代实物基金；仅用于已核零持仓角色交接，旧历史和计划保持此身份。
PREVIOUS_KC_SYMBOL = '589680.SH'
# 该版本唯一公开算法标识；安装、目标与显示共同使用。
STRATEGY_ID, STRATEGY_VERSION = 'resonance-regime-v1', '1.2.2'
ALGORITHM_ID = STRATEGY_ID + '@' + STRATEGY_VERSION + '/ledger-front-ratio-v1'
SYMBOLS = tuple(sorted(ROLE_SYMBOLS.values()))
