# 独立WT运行装配

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：模块说明。范围：外部组件进程和本地等待线程的生命周期。要求及状态语义以[WRI规格](../specs/independent-wt-runtime.md)为准，操作见[独立WT手册](../runbooks/wt-independent-runtime.md)。

## 输入与所有者

[`RuntimeConfig`与`Runtime`](../../apps/wt_runtime/guanheng_wt_runtime/runtime.py)校验实例、组件部署描述及原字节SHA。固定工厂组合通信、账户发布、历史、采集和执行，沿依赖顺序启动、逆序关闭。每个原组件继续拥有自己的进程、配置、控制收据、来源和业务事实；装配层不计算持仓、委托和资金。

[`SourceWaitingExecution`](../../apps/wt_runtime/guanheng_wt_runtime/execution_source_wait.py)只在执行组件显式选择`wait_for_source=true`时使用。它持有一个原执行owner和一个本地线程。线程通过`TradeSourceProbe`读取本实例本地交易Host的原状态，来源就绪后只调用一次原执行`start`。默认路径直接使用原工厂，不经过等待适配。

可选[`AnalysisWindowProcess`](../../apps/wt_runtime/guanheng_wt_runtime/analysis_window_process.py)组合[持续策略分析数据](analysis-window-producer.md)的原发布owner，依赖同一WT的analysis_host。原Host进程负责接入，发布者在WT侧进行只读请求和原Native作业；ready、data_ready、最后成功及来源等待分别表达。停止先收执行，再收发布者及其Job，最后关闭分析通信。省略新增组件时原相对顺序保持。

可选 analysis_batch_host 持有[批量行情来源](qmt-analysis-batch-source.md)的原 v8 Host，与 v7 analysis_host 分别配对，统一由 WT 启停。它继续使用 qmt_read 工厂与 QmtHostProcess，在分析通信之后、所有消费者之前启动，逆序停止。省略此项时原装配及相对顺序保持；观衡只消费结果或只读接口。

## 状态与截止

原Host的认证状态是等待依据。只读GET使用原执行`trader`中的地址、凭据环境变量名、超时和容量，复用固定行情SDK的绝对截止TCP、头部及正文读取。每次GET不触发券商查询；来源缺席可以持续等待，认证拒绝、协议错误或Host硬故障形成明确失败。

本地owner的`ready`与原生执行的`execution_ready`分别表达；`source_wait_state`说明等待、原执行初始化和已经启动。`status`只读取内存快照及原owner的安全DTO。已启动执行器的故障与未知委托沿原组件负责，等待适配不创建第二代执行、不重发委托、不维护金融账本。

停止先通知本地线程及原owner，再沿首次共享截止join本地线程，最后由原owner确认原生资源关闭。线程启动交接期间关闭会等待该次交接，防止把尚未尝试启动的线程误判为已回收。缺少实际join或原owner关闭证明时保留未完成状态。

## 验证入口

原装配回归位于`test_runtime.py`（外部历史/待归仓路径：`../../tests/integration/wt_runtime/test_runtime.py`），晚来源及等待中停止位于`test_execution_source_wait.py`（外部历史/待归仓路径：`../../tests/integration/wt_runtime/test_execution_source_wait.py`）。普通安装的同实例七组件、晚到来源、独立观衡、实际源端及交易资格分别通过对应运行证据确认；单项测试不代替完整运行资格。

## 执行之前启动失败的续接

ServiceController按[WSC-R1](../specs/wt-service-control.md#wsc-r1-执行组件之前的启动失败)核固定依赖顺序、同代failure/status身份及execution已关闭且资源为空，证明原执行start尚未到达。该代原descriptor、Native配置及已准备transition继续使用，保留最后实际Native身份与原账；Runtime生成新控制代。其它来源owner保留各自关闭结论与恢复责任。缺失证据或execution启动失败继续原实际Native恢复核查。固定源码与普通wheel入口见[本模块发行](../../apps/wt_runtime/source_closures/0.1.0a12+integrated.2.market.35.3.service.9.resonance122.fresh.1.cash.2.startrecovery.1/README.md)。
