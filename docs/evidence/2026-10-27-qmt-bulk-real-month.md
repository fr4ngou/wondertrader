# 2026-10-27 真实月度分钟线批量导入

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：验证记录。结果：单证券月窗真实主路径通过；整体迁移继续。

## 已跑通的功能

国信 QMT 内的 GH_WT_MEMORY_VERIFY → Windows 命名共享内存 → 本仓 Host 分页 CSV/QMI → 原生 C++ GuanhengQmtBulkHistory → 既有 Importer/WtDtHelper → WT DSB → 原生 source Reader，已使用实际供应商数据贯通。证券为 000001.SZ，查询范围为 2021-11-01 至 2021-11-30，返回 **5258 行、6 页**。

C++ fetch 正常完成，耗时约 3.02 秒；原生文件导入及全部行回读约 1.30 秒。回读的时间及 open/high/low/close/volume/amount 六字段逐行相等。数据保留来源值；单位、分钟边界和覆盖范围仍按原 source metadata 记录为 unknown，本结果证明传输和存储一致性，完整市场覆盖和标准股数语义继续核实。

## 实际入口与产物

- 真实运行摘要（外部历史/待归仓路径：`../../build/qmt-bulk-live-main-001/MONTH-RESULT.json`）：包括实际根句柄、控制器结果、CLI 与回读摘要。
- 配对准备（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-bulk-live-month-002/PREPARED.json`）：显式 v5/control3，只读，order_ready=false。
- 原生程序：build/bhc-001/cmake/bin/GuanhengQmtBulkHistory.exe，SHA256 ed7d26f8e03396fedc0045d23092c1acb0889902d4a506e1f62c53443eb65aa2。
- QMI manifest SHA256：1012eefc19c01219abab0dff4fb5b27a86b8abb3e36e80d625ba85ad036764aa。
- 原生存储（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-bulk-live-month-002/private/wt-month-001/store`）与逐行回读摘要（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-bulk-live-month-002/private/wt-month-001/RESULT.json`）。

QMT 正文安装前已逐字备份原文件，当前安装 SHA256 为 460dba00bbe6f681a15d427928aac8810f487b4b937cf01a8653ae6c3d92754c。根自行在界面启停该只读策略；其余策略和 TRIN 编辑器保持原状。Host 先启动等待，真实认证配对后才提交该历史请求；Host 停止请求被确认，观察线程已 join。Host、CLI、回读三个受控进程均 exit0，无强制终止，Job 树为零、双管道 EOF、读线程 join 与资源关闭均由各自控制器确认。

## 本轮实现与范围

新增自有 C++ 批量 CLI、显式 bulk Host 配对入口及 Host 控制/落文件调度，默认旧入口保持。实际生成暴露 bulk settings 校验未传 max_result_bytes，已在调用层传实际配置额度后重新生成；首轮失败材料保留。本轮无新增 WT 框架修改，无旧 QMT 项目执行依赖，无真实下单或撤单。

按[主路径优先](../development/workflow.md#主路径优先)，后续先推进单证券全历史、批量证券与策略/观衡实际读取。新主链的边界、故障恢复和独立代码评审在整体模块主路径完成后集中进行；本记录不授生产发布资格。常驻跨实际重连、账户四查询、查询优先交易恢复、保留策略/观衡和独立发布仍属于总目标。
