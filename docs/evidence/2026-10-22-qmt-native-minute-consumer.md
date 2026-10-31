# 真实QMT早期分钟历史进入原生文件消费者

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

日期：2026-10-22。类型：执行证据。范围：2021-11-01至05、两只股票的冻结QMT分钟交换文件，经过现有QMI导入、原生DSB回读与原WtBtPorter文件消费者。整体历史覆盖、ETF、精确量额及完整策略资格继续待验。

## 输入、执行与结果

000001.SZ共1195行，600000.SH共1193行，总计2388行；原每日238或239行保留，缺分钟未填充。来源为此前已取得的冻结JSON/CSV，本轮不调用终端HTTP、当前Host、SDK或下载接口，也不读取/执行旧业务工程。

现有导入实现将新交换副本写入全新DSB根，沿原Helper和有界NativeHistory回读；随后固定原`WtBtPorter.dll`（SHA `4726fdb9c48d32ec46fe0793eabb23d120aec8a536dc8dc140b57b636b533b2e`）以bin模式通过原文件Reader消费，没有外部loader、setter、Trader或Parser绑定。2021-11-01 09:32初始化时每证券可见2行，随后1193个闭合分钟与1193次calculate；初始化及各次计算共2388次完整前缀核对，截止当时原生时钟。该探针证明分钟读取和调度，未执行缺少完整证券篮子及预热资料的业务策略。

作者研究和命令（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-offline-history-001/RESEARCH.md`）、运行结果（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-offline-history-001/runs/ac3fec00a216417ca93b7137da9d13e8/result.json`）及Job收据（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-offline-history-001/logs/67317e97a86a4530953b9f2ff7bd7ead/result.json`）保留。实际7.03秒、exit0、nonforced，pid_reaped/pipes_joined为true；Job内存512MiB、总期限90秒。文件输出限制由父进程监测，未声明OS磁盘硬配额。

## 根任务回核与来源边界

根任务核64份冻结原件及14份当前输入身份，并从原始JSON独立构造所有原生字段，逐条重算2388次前缀SHA、可见条数及原生时钟，全部一致；没有复跑SDK或原生进程。回核脚本及收据（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-offline-history-integration-001/integrity.json`）绑定原件清单SHA `71c25bc6d9760867ae3acb23693c3a647587348baa55ba7854d32038bfa122bd`。这项回核验证原件一致性和全部前缀内容，未将其称为完整独立模块full。

原始量额完整保留，开发profile显式volume×100、amount×1；表示转换一致性成立，精确股数和供应商数值宽度继续未取得资格。coverage保持unknown，不能把空或稀疏分钟解释成停牌、无成交或未下载的确定原因。两股五日不代表ETF、全市场或2021-11-01至今覆盖。

静态核实的安装SDK本地接口仍包含连接/原生初始化路径，未发现已证明可直接执行的纯离线DAT入口；本轮没有import SDK。扩大来源采用单独的SHM历史只读能力契约，当前full_tick包继续拒绝历史操作。历史结果将进入既有QMI/原生DSB，存储与读取复用WT，不新增行情数据库。

## 后继：历史1m来源接口的合成原型

最小契约与原型报告（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-shm-history-001/REPORT.md`）定义独立operation/profile：原线程、单证券、既往分钟窗口、最多5日及2000行，达到行上限即拒绝，空和稀疏仍保留coverage unknown。Python3.14.6与实际3.6.8各通过作者同一9组矩阵；候选结果经显式合成CSV/profile进入既有QMI及原DSB/NHA，两条记录回读一致。当前是研究目录中的adapter/序列化与存储组合，未接新operation的真实SHM、三B/Journal、新Host安装或现场。

根核1879份冻结原件、3个最终Job和复用codec身份相符，见原型回核（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-shm-history-checks-001/prototype-integrity.json`）。进一步独立合成检查发现演示`handle()`的完成时间仍取调用前时刻，实际反例（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-shm-history-checks-001/completion-result.json`）保留；原型尚未取得完整验收。现产品tick在调用后更新完成时间，该原型问题不扩大为当前QSW缺陷；后继正式整合应由唯一原线程owner形成时间和终态，避免重复封装。
