# 统一策略行情、分钟消费与 SDK 0.6.0

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：本切片开发验收。日期：2026-10-21。要求：[SMA-R1–R5](../specs/strategy-market-access.md)。状态：隔离实现及制品验证通过；真实来源、受管运行和完整系统验收 pending-verification。

## 最终行为及根因修复

策略通过 `StrategyMarket` 按权威分钟网格组合显式档案和活动来源，按需从活动源补齐、获取报价、拉取已闭合分钟并确认消费。服务端新增 `history.read` 在单次调用内使用私有有界准备队列，保留原作业、来源和事实所有者。独立客户端 wheel 升级0.6.0，基础运行仍仅标准库。

独立 full 审查发现：活动源真实 `Pending/data={}` 响应导致缺失分钟汇总提前退出；此前测试替身使用 Ok/Gaps，遗漏真实返回形态。修复在同一剩余预算内回查一次已持久数据，经原严格校验和合并规则计算各窗口缺口。部分数据持续保留在来源端，策略错误结果 bars 为空。新增真实形态、部分发布、跨窗缺口、错误、资格和截止回归。

原观衡分钟消费者薄适配使用原 `save_bar`、原 `MarketBar` 和受管发布函数：历史/恢复分钟预热，当前分钟进入原 feature 链；先验证整个批次，成功后确认，失败保持未确认。不新增账户或交易账本。

## 验证与审查

| 范围 | 实际结果 |
|---|---|
| 策略接口与消费单元 | 43项通过：网格、资格、版本、来源冲突、预算、不可变结果、ACK重投、历史/恢复/当前分类及整批预检 |
| 原生服务history.read | 10项真实隔离HTTP/native/DSB通过：部分发布、同实例恢复、离线命中、Unknown无源、队列隔离、丢回复、超时和会话冲突 |
| 独立full/delta | full发现1项P2；delta关闭SMA-F1，无新增发现。最终30个审查输入摘要全部匹配 |
| 原生完整回归 | 57项启用CTest通过；已知全天时段用例仍Disabled，未计为通过 |
| 构建流水线 | 32项通过；configure/build/client-sdk/测试/安装/搬迁调用链共20阶段通过 |
| 搬迁包统一业务调用链 | 离仓wheel-only→真实loopback/native→DSB→原分钟消费者；20根档案预热、2根恢复、1根当前，原feature窗口20；全部通过 |
| 兼容回归 | 原历史runner/worker/calendar/import、策略回放及旧HTTP调用包含在本次CTest与包内链中通过 |
| 框架保护 | 原12个差异文件SHA与观察记录一致；CORE-004一行已获批准，其他11文件差异保持冻结 |

独立 reviewer 对R1–R3给出本切片complete；其未执行的完整旧回归/搬迁包标记unknown。本任务随后通过上述原生all及制品调用链补齐本次运行证据，各自资格分开保存。

## 身份与命令

WT 基线 `08b230dd05facf6d650d949bfe51054115a2ecb1`，分支 `codex/qmt-migration-plan`，带自有未提交实现。原QMT是受控只读源码输入，原服务与数据未切换；原日历owner使用独立服务适配工作树。机器收据绑定全部编译输入、依赖、外部契约及DLL摘要。

```powershell
D:/workspace/qmt/.venv/Scripts/python.exe -B scripts/native.py all --offline --qmt-source D:/workspace/qmt --calendar-owner-source E:/workspace/qmt-worktrees/wondertrader-service-adapters
```

开发包 `dev-20261021T091343Z-61c238d2.zip`，5,067,433字节，SHA-256 `67638582efea32982d4319b973a8accdea059a58368f02cda64cd403ab03a162`。

独立 `guanheng_market_client-0.6.0-py3-none-any.whl` SHA-256 `0ec75da19e6c262cd51451f3d1f0bf416ea38b816cdaa1027f32fdaec26be50c`，显式六源码清单。打包使用当前开发工作区的DLL；其中包含仍冻结的框架差异，包只用于开发验证，不能据此授予生产发布或其他框架差异的批准资格。原样上游DLL审计另见[原生设计复核](2026-10-21-wondertrader-design-audit.md)。

附件：完整收据（外部历史/待归仓路径：`strategy-market-2026-10-21/receipt.json`）、CTest（外部历史/待归仓路径：`strategy-market-2026-10-21/ctest.xml`）、独立full（外部历史/待归仓路径：`strategy-market-2026-10-21/full-review.json`）、独立delta（外部历史/待归仓路径：`strategy-market-2026-10-21/delta-review.json`）、当前审查身份匹配（外部历史/待归仓路径：`strategy-market-2026-10-21/review-input-check.json`）、包内业务流（外部历史/待归仓路径：`strategy-market-2026-10-21/package-flow.json`）。

## 剩余范围

输入行情为合成数据，原事实owner在内存中运行；真实国信1m、实际18010、PostgreSQL/NATS持久化、生产日历及页面尚未验收。原生策略同实例历史可见性已有[reader边界证据](2026-10-21-reader-visibility.md)，正式插件/完整宿主/当前分钟事件仍需接线。跨会话活动根发现、独立监督、交易恢复及其他业务模块沿总目标推进。共享内存绑定和通达信交易维持暂缓。
