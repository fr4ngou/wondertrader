# 当前持仓、新预算与cash.3实际运行

日期：2026-11-04。承接[此前启动记录](2026-11-04-current-strategy-restart.md)，保留其失败阶段，补充后继实际结果。

## 用户目标与结果

按用户要求停止追溯旧策略金额，以当前实际持仓及新的100万元总预算开始。最新共振市场状态ETF策略1.2.1已由WT运行，观衡独立只读展示。当前预算包含现有持仓；实际资金为现金721311.1元、3个非零持仓市值约278688.9元，总资产约100万元。仅使用用户已确认的模拟账户尾号1314，本轮未新增下单或重复提交，原通信命令仍为49条。

运行版本为service.9.resonance121.fresh.1.cash.3，稳定入口E:/workspace/wondertrader-data/wt-service；当前WRI fc51a9ee、Native PID43156及五组件就绪。initial-inventory008及financial-state008保持同一资金起点，旧006和失败007原件保留。

## 根因与实现

初始化失败首先来自组装过程预先创建Reader要求自行创建的缓存目录，已按原组件契约调整。其后自有持续日线Reader把当前交易日全部排除，导致收盘后已经发布的当日闭合日线也无法通过核对。现按映射会话实际收盘时间、请求截止及来源known_at共同判定当前日闭合，普通冻结目录保持原日期规则；沿用原WT文件格式及读取算法。

账户首帧晚到时，原后台刷新跳过尚未初始化的资金对象，后续账户数据恢复仍无法补出资金。cash.3保存初始化时已核定的估值与序号，账户线程在合格账户快照到达后完成同一资金起点的投影；资金依据券商现金原点差和实际持仓估值，原CTA理论统计单独保留。两个修正均位于自有组件，未新增WT框架修改。

## 验证证据

- E:/workspace/wondertrader-qa/daily-mainline-20261103-001/daily-window-native-match001/MAIN-PATH-RESULT.json：八证券各406交易日，原生读取与发布窗口3248行逐字段一致；收盘前、未来时间及冻结模式的定向验证另存同目录。
- E:/workspace/wondertrader-qa/daily-mainline-20261103-001/capital-initial-recovery001/MAIN-PATH-RESULT.json：实际账户首帧晚到后恢复资金，初始化估值和序号保持，未调用Native资金修改接口。
- E:/workspace/wondertrader-qa/daily-mainline-20261103-001/CASH3-ACTUAL-POSTFLIGHT.json：实际五组件、当前策略及资金，reason为awaiting_first_strategy_calculation。
- E:/workspace/wondertrader-qa/daily-mainline-20261103-001/CASH3-PRIOR-STOP.json：最近一次停止exit0，随后同账恢复。此前一次停止超时及进程退出恢复原证据继续保留，原因尚未确定。
- E:/workspace/wondertrader-qa/daily-mainline-20261103-001/CASH3-LIVE-UI.json：已安装独立观衡109，策略、持仓和系统状态三页实际刷新及截图通过，未发现页面或控制台错误，资金等待错误消失。

## 剩余边界

当前已收盘，策略等待首次自然计算。本代策略首次自动下单、589680实际模拟柜台受理、成交和撤单仍需交易时段验证。持续分析统一启停、全市场日线正式发布、分钟Source切换、SDK17消费者及最终无引用产物清理继续。页面中的旧辅助服务状态仍有配置维护余项，本记录不将全站所有状态认定为已解决。

源码采用：Reader 1ec31a8，cash.2永久源码0720fed，cash.3永久源码984e197。独立观衡入口：http://127.0.0.1:18143/strategies。
