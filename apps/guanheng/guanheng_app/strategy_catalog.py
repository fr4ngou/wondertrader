"""只读展示描述；具体版本来自WT活动结果或各份已保存报告，不从安装包推断。"""

ORIGINAL_WT_ID = 'resonance-original-wt-351f9d5-stable'
ORIGINAL_WT_VERSION = '0.1.0a1'
_RETIRED_REFERENCE_ID = 'resonance-original-351f9d5-stable'


def strategy_definition(identity, version):
    """返回展示描述；version=None表示WT尚未发布版本事实。"""
    if (type(identity) is not str or not 1 <= len(identity) <= 64 or not identity.isascii()
            or any(ord(c)<33 for c in identity)):
        raise ValueError('策略身份格式无效')
    if version is not None and (type(version) is not str or not 1 <= len(version) <= 64
            or not version.isascii() or any(ord(c)<33 for c in version)):
        raise ValueError('策略版本格式无效')
    known=identity=='resonance-regime-v1'
    original_wt=identity==ORIGINAL_WT_ID and version==ORIGINAL_WT_VERSION
    return dict(strategy_id=identity,  # WT或归档发布的策略身份；仅用于展示归属。
        strategy_version=version,  # 同一来源发布的版本；None保持缺失，不读取App计算包版本。
        display_name='共振原版（WT回测）' if original_wt else '共振市场状态 ETF 策略' if known else identity,  # 稳定中文展示描述，不授运行资格。
        description='固定原版BUY/SELL信号通过WT框架回放，人民币本金、整手和费用口径按该份报告。' if original_wt else '结合八只 ETF 的日线走势与实际持仓周期，计算目标仓位和止损。' if known else 'WT已发布的策略结果。',  # 稳定业务说明；不作为可执行版本登记。
        historical_versions=[])  # 历史版本由已保存报告选择器汇合，不维护版本允许清单。


def strategy_catalog(published=()):
    """保留WT动态版本/缺失事实；末项登记独立原版研究身份。"""
    definitions={}
    for value in published:
        if value and value['strategy_id'] != _RETIRED_REFERENCE_ID:
            definition=strategy_definition(value['strategy_id'],value['strategy_version'])
            definitions[(definition['strategy_id'],definition['strategy_version'])]=definition
    definitions[(ORIGINAL_WT_ID,ORIGINAL_WT_VERSION)]=strategy_definition(ORIGINAL_WT_ID,ORIGINAL_WT_VERSION)
    return dict(schema='guanheng.strategy-catalog.v1',read_only=True,scope='registered-definitions',
        strategies=list(definitions.values()))
