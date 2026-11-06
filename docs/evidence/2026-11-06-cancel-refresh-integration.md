# 撤单后订单复查切片的合入验证

类型：开发验证。状态：本切片编译、定向回归及独立审查通过，满足本切片源码合入范围；整插件联调、历史委托SHM接入及现场跨日验收未完成，本记录不授线上采用资格。

## 本切片与实际输入

用户授权合入独立worktree中的代码，并要求核实测试充分性。范围为[恢复规格](../specs/execution-fault-recovery.md)EFR-27及[专项方案](../migration/qmt-cancel-reconciliation-proposal.md)已实现的查询调度：撤单完成/业务异常触发原查询；活动单及原提交责任的周期O/P/A；后到请求、读取恢复及已确认业务拒绝处理。WT框架、线上程序和原金融目录均保持。

完整StandardQmtTrader.cpp SHA256为`0b7cda19b61987afc44953756a88c5b521d1e68b1bcea182e9be54f9b99d6ffb`，构建recipe声明一致。实际完整翻译单元使用原已验证编译器、依赖及头文件编译通过；未完成本候选DLL链接、安装及真实SDK调用。编译存在原有size_t到unsigned转换警告，本切片未改这些代码。

## 已执行回归

| 实际源码入口 | 已核结果 | 验证范围 |
|---|---|---|
| Standard完整翻译单元 | 编译通过，源摘要与当前代码一致 | 完整C++语法及声明；未链接 |
| request_order_refresh及原查询调度函数 | 10场景通过 | 真实函数、队列/完成替身，包含后到请求、失败入队和原读取票据 |
| begin_event的error分支 | 通知、查询触发、原订单保留及SPI异常通过 | 真实分支、SPI替身 |
| run_write尾部分类→publish_write_failure | 14场景通过 | 真实分类/通知代码，固定SDK JSON及SPI替身；包含Unknown、运输/身份冲突及原首错 |

独立delta审查首先指出新增撤单业务拒绝分支缺少执行回归；补齐分类及通知场景后，独立编译执行14场景全部通过，P2关闭，最终审查无剩余P1/P2。历史委托及整链边界继续保持。

受控原件为`wondertrader-qa/worktree-audit-20261106-002`的STANDARD-COMPILE、query-scheduler-final、error-trigger及cancel-classification-verified；独立记录为`cancel-refresh-review-20261106-001`。首轮测试夹具缺声明的编译失败及修正后结果分别保留，失败未作为通过证据。当前源摘要分别关联编译及定向结果，调度夹具文本与实际方法一致。

## 未覆盖与后续

- 新候选DLL的完整Host/Source/WT订单表/执行器/NSQ调用链。
- 国信内置历史委托接口的本机可用性、模拟柜台覆盖日期及SHM接线。
- 跨日仅从当前列表消失、部分成交后柜台撤单、回报丢失后的真实收敛。

源码合入与后续线上采用分开记录。原两笔委托身份和资金保持，当前运行实例继续原配置；当前测试真实买卖/撤单次数为0。对未取得的终态继续如实保留原责任，不以测试通过推导未来无bug。
