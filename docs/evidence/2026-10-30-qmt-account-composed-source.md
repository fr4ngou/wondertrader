# QAC 单正文四连接验收

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

日期：2026-10-30。规格：[QAC](../specs/qmt-account-composed-source.md)。范围：只读账户 owner 与原交易/QST/HPR 正文组合；SDK 替身运行、原生只读 Scanner、原 Writer 和真实 Reader 基准。现场 QMT、下载和采集保持。

## 实际结果

`build/qmt-account-composed-source-001/main005` 使用 ZIP 搬迁后普通离线重建的 `installation003`。无观衡包/SPA，Host 与 WT 各自普通安装。无诊断包装的独立 WT CLI 同时管理 HPR、交易、只读账户、历史、采集五个组件；一个实际 Python3.6.8 进程运行正式生成/核验的四 owner 正文。

账户原生 Scanner 沿原 DLL、WT Adapter 和 read v3 完成两轮四查询，每轮 2 持仓、1 订单、1 成交、1 资金。原 Journal 的 130 项事实及 60 个 ABI 槽逐值相同，浮点按 IEEE 位比较；只读连接两代认证，原代 I/O/句柄已退休，交易与 HPR 的绑定和五组件 PID 保持。

同一正文还完成交易账户四查询、一次下单→查单→撤单 SDK 替身、原 HPR 补齐与回读、QST→原 Writer 的两根 DSB 分钟，以及真实 Reader 五根既有历史前后对照。QMT 受限正文的文件/网络守卫调用 0、一个 timer、一次 QST 订阅/取消、SDK 原线程成立。

外层控制 24.9048488 秒 exit0。源码、材料与运行输入 1253 项前后相同；Source、Scanner、独立 WT、五组件均正常关闭，整树为 0、双 EOF、线程 join、句柄释放均成立。`main004` 是同链诊断包装证据，27.2564726 秒正常；业务期间未捕获异常，停源后 OSError 单列。

纯生成/快照回归共 13 项通过，包含原默认 deployment、单交易/三 owner 正文及内存闭包逐字相同、新快照及凭据角色、只读原准入、旧 decoder 显式拒绝新第五项。ZIP 含 179 项源/离线 wheel/后端输入和一份 manifest，解压后沿原 ATI 构建及普通安装，使用新安装完成上述实际调用链。

## 保留的失败

`main002` 在只读第二代及原生第二轮查询成功后，交易插单及查单成功，撤单阶段交易 Host 超时退出。原有限故障为 `retirement_unconfirmed / TimeoutError / poll_stage=page / domain_jobs=2`。2 表示原调度槽数。原冷 Journal 完整性正常且只读前后 SHA 相同：insert 为 `sdk_returned`，cancel 为 `dispatching` 且没有源回执；SDK 替身 cancel 调用 0。原命令未重发。

这次故障的原首异常帧与排队/锁/文件 I/O 耗时没有保留。后继定向诊断未重现业务故障，具体根因仍为 unknown。原失败及冷审计完整保留，后继通过结果分别记录；本交付保留该已知恢复风险。

`main003` 是 QA 诊断父目录遗漏导致的启动失败；补齐受控私有目录后 `main004` 正常。首次离线安装缺少显式 wheel cache，失败原件为 `installation001`；`installation002` 和搬迁后 `installation003` 使用已声明离线输入正常安装。原件保留。

## 交付与资格

最终源、安装、ZIP、QA、配置和独审身份集中在 DELIVERY-001.json（外部历史/待归仓路径：`../../build/qmt-account-composed-source-001/DELIVERY-001.json`）。源码差异限 Host 三个原生成/配对/CLI 文件与一个新组合准入文件；Agent、WT 框架和金融算法保持原实现。

本结果授 SDK 合成组合与本机离线安装资格。真实 QMT 四 owner、真实下撤单、完整恢复、实际策略、观衡页面、生产及外发再分发继续由相应完整链验收。旧真实账户中断原因与本组合验收分别记录。
