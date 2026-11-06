# 目标更新两层差异与旧计划资金复算

类型：只读源码对照及实际回测原件复算。状态：定位补充，尚未修改实现或线上安装。承接[阶段阻断重跑](2026-11-06-backtest-rerun-stage-block.md)。

## 之前修复与当前问题

已批准CORE-012修复WT股票执行器set_position在新目标等于当前可卖持仓时提前返回、遗留旧_target_pos的问题，缺省保留原路径、当前配置显式开启。完整42组工厂回放及正式采用见[隔离证据](2026-11-06-stock-target-replacement.md)和[发布记录](../releases/2026-11-06-stock-target-and-read-wait-live.md)。

当前问题位于WT执行器之前的自有retained_evaluation.advance_retained：新经济目标到来，仍优先advance旧state.target，仅prior.status=converged才交接。原NSQ在同一旧代际内递增卖后重算sequence；Limits.max_stages默认16，StageState另有64硬上限。16是内部阶段预算，与委托笔数、证券数、账户额度分别计数。此状态机和限制由自有strategy_native包定义。

原8月21日记录证明旧冻结卖出向量已全部达到、pending0，旧经济目标仍未完整收敛，新目标继续被阻断；调高纯计算上限仍沿旧目标卖出。前次WT内部目标保存修复与本次自有接续问题分别发生，前次修正不能证明后者完成。

## 7月31日资金复算

| 项目 | 回测原值/复算 |
|---|---:|
| 当前现金 | 303179.70元 |
| 旧目标新增买入名义额 | 302415.40元 |
| 模型买入费用预留 | 2108.00元 |
| 旧目标合计需要 | 304523.40元 |
| 相对现金缺口 | 1343.70元 |
| 旧6月26日目标合计权重 | 99.96249137933848% |
| 当前策略输出目标合计权重 | 59.47519813955333% |

复算采用原quantity policy、目标份数、未复权价格及原capture；该waiting_cash由自有纯计算产生，未经过券商委托。它证明旧目标在此模型下资金不足，不证明最新目标或真实券商账户资金不足。当前回测费表SSE.ETF/SZSE.ETF按份收费，买入0.01元/份、卖出0.02元/份；应明确为本次固定模型费用，券商实际费率尚未由此证实。

## 原生源码对照及后续范围

官方WonderTrader固定08b230dd05facf6d650d949bfe51054115a2ecb1的[src/WtExeFact/WtStockMinImpactExeUnit.cpp](https://github.com/wondertrader/wondertrader/blob/08b230dd05facf6d650d949bfe51054115a2ecb1/src/WtExeFact/WtStockMinImpactExeUnit.cpp)已通过官方原文与本地Git对象逐字节核同，17091字节，SHA256 b55e8b4191b6dc0414a45d3ad1e78040b508042534b519ca250506c83df83d22。该原生执行器按目标/实际持仓推进，买入单量沿_avaliable及价格约束；其中没有自有max_stages或stage_budget_exhausted状态机。资金不足具有正常交易含义，本轮288日的具体触发归自有接续实现。

修复需收敛旧阶段实际完成与新目标交接合同，保留真实未决保护、策略资本及费用事实，再复核整组资金判定和阶段预算的适用范围。优先复用WT原生执行职责；当前尚无本项新增WT框架修改方案。历史报告读取会重放原接续数学，后续需显式区分新旧执行模型，保留旧原件，不能直接改写旧报告或阶段计数。

复算原件：E:/workspace/wondertrader-qa/backtest-rerun-20261106-002/CASH-WAIT-RECOMPUTED.json及原session、binding、报告。核验无券商调用、无线上或金融状态写入。
