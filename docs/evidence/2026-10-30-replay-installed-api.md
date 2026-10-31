# 原生逐日窗口的正式安装入口

类型：验证证据。日期：2026-10-30。状态：安装与原值消费通过；正式策略 CLI 和完整回测分别验收。

## 原因与实现

原401日目录已包含回放库，正式安装的消费者缺少可导入入口。`scripts/native_support/native_replay.py` 以固定 core a1 wheel 为输入，逐字保持11份既有代码，新增原 `qmt_native_replay.py` 及公开转发模块，生成 `guanheng-native-analysis-core==0.1.0a2`。`guanheng-market-client==0.15.0` 的14份原代码保持。公开类与原实现为同一对象，价格与因子算法沿用原实现。

构建根：`build/root-native-replay-sdk-001`。输入身份和冻结集由 `INPUTS.json`、`FROZEN-001.json` 记录；对外接线以 `INTERFACE-001.json` 为准。新 wheel SHA-256 为 `fa3fe6d65239694fb1684c577b68e9c8046b473c50eb00c19adb54db8111b56f`。

## 实际验收

在独立 `ordinary001` 环境离线安装两份 wheel，执行依赖检查及 `tests/integration/qmt_native_replay_sdk/main.py`，隔离导入 `guanheng_market_client.qmt_native_replay.ReplayCatalog`。原冻结目录覆盖2025-03-05至2026-10-28，共401日；安装 API 的644,808个日期证券配对逐值等于原目录库，返回容器修改互不影响，错误清单摘要和日期明确拒绝。输入文件前后摘要保持。

`API-RESULT.json` 记录全部原值比较；`INSTALLATION.json` 记录安装与原文件保持。外层 `CONTROL.json` 显示约36.1秒正常完成，退出码0，进程树、管道、读线程和句柄正常回收。消费阶段无来源请求或子进程调用。

限定独立 Standards/Spec 审查记录于同根 `REVIEW-001.json`（SHA-256 `58cf9d36c262b43286419c2612fe6053b0a8a56211575bf779def245dbe5f421`），30项输入绑定，开放发现0。审查独立核原 core/SDK wheel 与安装文件、新 wheel 成员/RECORD及原84份目录文件；未重复运行业务或来源。间接构建 helper/工具链未全部逐文件进行运行前后冻结，完整可复现构建资格保持独立范围。

## 范围与后继

本项提供可安装的纯值回放入口。原数据仍属于当前可见重建；历史首次可见性保持 unknown。正式400日策略 CLI、RT/BT比较、持续分析窗口和最终系统包使用独立结果，不由本项安装通过推导。无账户、下单、撤单、生产切换或 WT 框架修改。
