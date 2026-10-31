# WT独立运行操作

类型：运行手册。状态：独立安装、正式1.1.2首次库存接管、正常调仓、限定未知委托连续性及自有挂单撤清后重算的简版恢复已有SDK替身资格；最终真实QMT来源及生产启用分别验收。当前候选及使用位置见[WT独立交付](../releases/2026-11-01-wt-independent-candidate.md)，业务依据见[完整安装接收](../evidence/2026-11-01-wt-simple-recovery-installed.md)。适用范围：独立WT发行环境。职责及配置唯一正文见[WRI](../specs/independent-wt-runtime.md)。

## 安装和启动

1. 使用发行安装器准备独立WT环境及其原生组件；WT环境不要求安装观衡Web包或SPA。QMT Host使用安装器声明的独立Host环境。
2. 在WT实例配置中声明所需组件，逐项填写原部署descriptor绝对路径及原字节SHA256。host选择只读或HPR组合中的一种；需要交易通信时额外声明trade_host（kind=qmt_trade），保留原补齐Host。当原v3账户查询需与HPR并存时，另声明account_host（kind=qmt_read），填写原只读Host descriptor。需要持续账户观察时，同实例声明account_observation（kind=native_account_observation），填写[NAP-v1](../migration/native-account-publication-proposal.md#nap-v1冻结合同)原生扫描/刷新发布descriptor。三个通信组件各用自己的原配对、映射与Journal，账户扫描及其更新由WT持有，观衡读取已发布文件。历史、采集及执行分别使用原组件描述。配对秘密和账户材料归WT实例管理；完整组合及同QMT正文接线分别验收，现场配置保持原值。
3. 使用安装后WT环境的`pythonw.exe -I -B -m guanheng_wt_runtime`，传入配置、配置摘要、新控制目录及控制UUID。示例见[包说明](../../apps/wt_runtime/README.md#公开入口)。一次启动覆盖已声明组件，后台子进程均隐藏窗口。
4. 在同一个启动截止内等待`ready.json`及可读的`status.json`，再确认控制身份、真实PID及已声明组件。使用独立SDK的`read_status`；文件尚未出现或返回`CollectionStatusPending`时，在剩余预算内等待下一份完整快照。格式、摘要或身份错误按故障处理。ready与status分别发布，ready证明组件初始化/监听；QMT连接、行情时间、历史覆盖和交易资格由各原接口分别确认。

Host保持等待，QMT策略晚于60秒启动仍可配对。每个查询/命令继续使用原业务超时；断线重连创建新认证连接，旧请求和结果身份保持原协议，不自动重发未知委托。

### 同时运行交易组件时等待QMT

同实例托管本地交易Host、且希望先启动WT再启动QMT策略时，在原`components.execution`对象内填写`"wait_for_source": true`。原`kind`、`descriptor`和`sha256`照常填写；缺省`false`继续直接启动原执行器。等待选项只管理原执行器开始初始化的时机，原请求预算、账户权限和委托身份保持。

等待期间WT可以发布`ready.json`；执行组件的`execution_ready=false`、`source_wait_state=waiting_source`、原生`pid=null`明确表示尚未启动交易进程。QMT来源认证后，状态依次到`starting_execution`和`execution_started`，并从原执行owner取得真实`execution_ready`、PID及结果定位。运行状态的读取不查询券商。

等待时间可以超过60秒。此期间可以按下文正常停止WT，无需先运行QMT。已启动的执行组件若故障，沿原故障及恢复流程处理；本选项不自动重启交易进程。

## 只读观察

### 持续策略分析窗口

需要自动更新策略日线分析时，同实例声明 analysis_host（kind=qmt_read）和 analysis_window（kind=analysis_window）。前者使用显式 v7 只读配对和原 Host descriptor；后者使用 `guanheng.analysis-window-deployment.v1` descriptor，其 configuration 由 source_connection、source 和 producer 三项组成，具体参数沿 [AWP](../specs/qmt-analysis-window-producer.md)。原生 Helper/Reader/probe 和工作解释器使用发行实际路径与摘要，凭据通过环境变量注入。

WT 先启动分析通信，再启动持续发布，最后启动执行；没有来源时服务 ready 并等待，data_ready/published_count 单独表示是否已有成功窗口。原 R24 仍核来源时间，不把旧窗口当新数据。停止 WT 时先收执行，再收发布者及其 Native Job，最后关闭分析通信。此接线不要求观衡运行；普通安装、真实 QMT 与现场切换分别沿[实际证据](../evidence/2026-10-30-analysis-source-and-window.md)核对。

需要同时提供批量市场日线时，另声明 analysis_batch_host（kind=qmt_read），填写其 v8 原部署 descriptor 与摘要。它与 v7 analysis_host 各用原配对及通信记录；WT 依次启动两个通信 owner，并在消费者停止后逆序关闭。批量组件省略时继续原配置。该组件的 ready 证明 Host 监听，实际行情日期和复权依据沿[批量来源手册](qmt-analysis-batch-source.md)另核。

观衡只持WT公开查询接口的只读地址及读取凭据，独立启动、停止及更新。观衡关闭或异常退出时，WT运行控制目录、Host、采集和执行owner继续存在；观衡不拥有运行侧停止或下载入口。

`status.json`使用`guanheng.wt-runtime-status.v1`，包括`control_id`、`instance_id`、`configuration_sha256`、真实`pid`、运行`state`及各组件安全状态。状态文件读取沿独立SDK的`guanheng_market_client.runtime_status.read_status`，兼容Windows原子替换，不需导入运行包。该文件的进程ready不代替来源和业务事实。

## 正常停止及故障

向本控制目录原子发布`stop.json`：

```json
{
  "schema": "guanheng.wt-runtime-stop.v1",
  "control_id": "本代控制UUID",
  "instance_id": "配置中的实例UUID",
  "configuration_sha256": "本代配置原字节SHA256"
}
```

入口依次关闭执行、采集、历史、可选账户结果更新、可选账户Host、可选交易Host和原只读/HPR Host，使用首次关闭的共享截止；原组件各自确认进程树、管道、线程和句柄。账户结果更新先停止新轮并收回原Scan，再关闭其账户通信依赖。最终`closed.json`与进程退出码0共同表示正常退出。`failure.json`、组件`pending/forced`或非零退出码保留故障资格，沿相应组件记录核查，不重复下单或覆盖未知状态。

同控制根下同一`instance_id`通过OS锁保持单一运行owner。每代控制目录独占创建，旧记录保留供恢复和审计。升级时先确认旧运行实例正常停止，再使用新发行及新控制身份启动；配置、金融状态和历史文件按各模块恢复协议处理。生产切换另按[发布规范](release.md)验收。
