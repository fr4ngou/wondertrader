"""保留策略的展示登记；不推导运行状态，也不公开配置或算法参数。"""

# 中文名称及简介沿旧QMT策略目录/definition，版本沿本仓保留算法规格。
# 登记本身不表示已启用；运行事实继续由对应策略宿主拥有。
_STRATEGIES = (
    ('resonance-regime-v1', '1.1.2', '共振市场状态 ETF 策略',
     '结合八只 ETF 的日线走势与实际持仓周期，计算目标仓位和止损。', ()),
)


def strategy_catalog():
    """返回独立只读登记值；名称/简介/算法版本与实际运行资格分别解释。"""
    return {'schema': 'guanheng.strategy-catalog.v1', 'read_only': True,
            'scope': 'registered-definitions', 'strategies': [
                dict(strategy_id=identity, strategy_version=version, display_name=name,
                     description=description, historical_versions=list(history))
                for identity, version, name, description, history in _STRATEGIES]}
