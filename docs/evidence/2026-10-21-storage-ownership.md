# 2026-10-21 原生存储与业务职责核查

类型：源码审计证据。状态：审计完成，替代调用链 pending-verification。本记录不授予交易、部署或数据删除资格。

## 输入与方法

WT固定上游 `08b230dd05facf6d650d949bfe51054115a2ecb1` 与当前下游工作区分别核对。观衡适配worktree基线 `4ee6d8accbcdd413358385f188ef2ac57b1268da`，包含未提交候选；交易审计另核只读QMT主工作区，观察HEAD `9c085e07fbc04d38e47e00c5d363abcd11859c8a`。提交身份不表示当前生产部署。

三个独立只读调查分别追踪行情、观衡业务及原生交易模块，原报告位于本机 `build/native/storage-ownership-audit/{market-map,business-map,execution-map}.md`。Root复核实际TraderAdapter记录条件、历史Writer路径、SDK传输与reader契约、原业务地图及现职责定义。未连接账户，未启动数据库、清理归档或调用交易。

## 确认结果

| 结论 | 源码依据 | 边界 |
|---|---|---|
| WT已有原生历史/实时行情文件 | WtDataWriter的his/min1与rt/min1，WtDtHelper/Reader | 现自有Store每次整文件处理、DSB/sidecar跨文件恢复仍需容量和故障验收 |
| savedata提供订单成交与快照 | TraderAdapter::initSaveData/logOrder/logTrade/saveData | orders仅终态推送，trades仅成交推送；初始化查询不回填CSV，rtdata未用来恢复账户 |
| WT已有策略及执行状态保存 | CtaStraBaseCtx::load_data/save_data/load_userdata/save_userdata、WtDiffExecuter | 观衡止损/迟滞/资本分配等字段需要逐项映射 |
| 旧PG行情链不是新底座必需 | 原MarketData save_bar/recent_bars/feature链对照WT Store/StrategyMarket/reader HTTP | 可改读接缝，不使用no-op store冒充持久成功 |
| 观衡存在需保留的独有事实 | Control配置激活/回滚，Research报告，Replay/Operations任务，Portfolio审批资本 | 必要持久化尚不决定采用PG；用户功能保持 |
| 当前TraderQMT尚未打通原生委托 | Factory返回ManagedTrader，其裸orderInsert/orderAction拒绝 | 已编译插件和查询测试不能证明原执行器能够交易 |
| 强四快照和保留消费者恢复是自有机制 | ITraderApi对照ManagedTrader bootstrap/confirm_resume | 真实快照/增量交接问题仍在，替代恢复先证明后切换 |
| 原PG业务职责超出订单审计 | Bridge::commit_signed_command事务分配序号、签名、消费审批；Agent SQLite journal去重 | 保留未决命令及现安全owner，不能把CSV当未知结果核查 |

## 当前实施与验证范围

已修订[业务地图](../migration/business-adaptation-map.md)、[ADR-0003](../architecture/adr/0003-native-runtime-and-business-state.md)及[原生行情消费者规格](../specs/native-market-consumers.md)。PG分钟候选暂停接线；首先实现独立reader客户端以接同一原生行情服务，随后改图表与特征消费者。框架差异、生产实例和已有数据保持。

上述结果证明职责及可复用代码，不证明新图表/交易链已运行。仍需真实样本、原用户入口、策略状态映射、每个执行动作授权、快照/回报交接、独立审查及制品验证。后续客户端验证另记录，不把其结果扩大为完整系统完成。
