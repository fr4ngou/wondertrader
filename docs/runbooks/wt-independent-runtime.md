# WT独立运行操作

类型：运行手册。状态：独立安装、正式1.1.2首次库存接管、正常调仓、限定未知委托连续性及自有挂单撤清后重算的简版恢复已有SDK替身资格；最终真实QMT来源及生产启用分别验收。当前候选及使用位置见[WT独立交付](../releases/2026-11-01-wt-independent-candidate.md)，业务依据见[完整安装接收](../evidence/2026-11-01-wt-simple-recovery-installed.md)。适用范围：独立WT发行环境。职责及配置唯一正文见[WRI](../specs/independent-wt-runtime.md)。

## 日常启动、停止和状态查看

安装多个独立WT角色时，可使用[服务组入口](../specs/wt-service-control.md#多角色同一操作入口)按原服务控制器统一操作，观衡继续独立运行。当前实际安装位置与已验行为见[统一WT入口](../releases/2026-11-05-independent-wt-control-and-observer111.md)；日常无需手改每代控制身份。

安装角色固定`service.json`后，操作员只执行以下三个命令，不编辑控制UUID或配置摘要：

```powershell
E:\guanheng\wt\venv\Scripts\guanheng-wt-service.exe start --service-config E:\guanheng\wt\service.json
E:\guanheng\wt\venv\Scripts\guanheng-wt-service.exe status --service-config E:\guanheng\wt\service.json
E:\guanheng\wt\venv\Scripts\guanheng-wt-service.exe stop --service-config E:\guanheng\wt\service.json
```

成功启动返回`state=ready`；来源尚未具备时返回组件的实际等待状态。重复启动返回`changed=false`并保持同一控制身份。正常停止返回`state=stopped`，重复停止返回`changed=false`。停止完成后再次启动会生成新`control_id`并保持同一`instance_id`，旧代状态和关闭收据继续保留。

纯历史服务升级使用原稳定CURRENT与同instance_id：先准备新安装、固定新history descriptor/Runtime/ServiceConfig及逐级SHA，沿旧service执行stop，确认正常closed且旧owner实际退出，再用支持该动作的新WT安装执行`guanheng-wt-service.exe adopt-bootstrap --service-config <新service.json>`。该动作仅接受前后均只含history/source_market的正常关闭代；运行中、故障/未知、跨实例或含交易/账户等组件时保留原CURRENT并明确失败。它复用原租约和启动链，不自动停止。默认start继续按前代配置恢复，更新bootstrap路径后直接start仍沿前代；采用后普通start沿新代恢复。数据请求和未物化INPUTS/REQUEST迁移须在旧owner退出后再次核查。

`state=faulted`、`process_lost`、`start_timeout`或`stop_timeout`进入故障处理。保留公开`CURRENT.json`、本代控制目录、代际配置和业务原件，沿[故障处理规范](incidents.md)核查。服务入口不会自动重启故障代，也不会按进程名结束外部进程。

固定公开路径`CURRENT.json`供观衡等只读消费者发现当前代。该文件严格为五字段协议，不存储环境、账户、凭证或启动命令。生产安装、配置变更和现场切换仍按[发布规范](release.md)执行。

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

### 策略部署选择

按[策略部署要求](../product/brief.md#策略部署与启用)，用户回测满意后可直接部署对应策略版本、参数及账户并启用。沿本手册原安装和WT启动入口装配策略；部署工具负责生成配置引用及制品身份，日常使用者无需制作审批文件或收集额外资格记录。

观察模式与启用交易是用户的运行选择。切换时保留当前资金、持仓和必要策略记忆，账户及未知委托沿原运行恢复处理。缺少本次必需行情或账户事实时，运行状态展示原因并在恢复后继续；无需用户重新走策略上线审批。发布观衡、补齐非策略必需的市场观察或等待固定观察天数均不属于策略启用前置步骤。

### 持续策略分析窗口

需要自动更新策略日线分析时，同实例声明 analysis_host（kind=qmt_read）和 analysis_window（kind=analysis_window）。前者使用显式 v7 只读配对和原 Host descriptor；后者使用 `guanheng.analysis-window-deployment.v1` descriptor，其 configuration 由 source_connection、source 和 producer 三项组成，具体参数沿 [AWP](../specs/qmt-analysis-window-producer.md)。原生 Helper/Reader/probe 和工作解释器使用发行实际路径与摘要，凭据通过环境变量注入。

WT 先启动分析通信，再启动持续发布，最后启动执行；没有来源时服务 ready 并等待，data_ready/published_count 单独表示是否已有成功窗口。原 R24 仍核来源时间，不把旧窗口当新数据。停止 WT 时先收执行，再收发布者及其 Native Job，最后关闭分析通信。此接线不要求观衡运行；普通安装、真实 QMT 与现场切换分别沿[实际证据](../evidence/2026-10-30-analysis-source-and-window.md)核对。

需要同时提供批量市场日线时，另声明 analysis_batch_host（kind=qmt_read），填写其 v8 原部署 descriptor 与摘要。它与 v7 analysis_host 各用原配对及通信记录；WT 依次启动两个通信 owner，并在消费者停止后逆序关闭。批量组件省略时继续原配置。该组件的 ready 证明 Host 监听，实际行情日期和复权依据沿[批量来源手册](qmt-analysis-batch-source.md)另核。

观衡只持WT公开查询接口的只读地址及读取凭据，独立启动、停止及更新。观衡关闭或异常退出时，WT运行控制目录、Host、采集和执行owner继续存在；观衡不拥有运行侧停止或下载入口。

整套WT进程物理退出而原关闭收据缺失时，使用已安装WT入口的`--record-process-loss`，沿原`--config`、`--config-sha256`、`--control-directory`和`--control-id`核原实例OS租约及全部已登记PID退出。入口保存独立owner-loss故障，将当前状态标为faulted，components_closed=false保留原join凭据未知。执行owner另记原Native进程退出依据，后继显式resume_reconciled沿原账本、安装/Python及当前券商责任复核；契约见[EFR-14](../specs/execution-fault-recovery.md)。原正常关闭收据和clean仍由实际成功关闭生成。使用前核实原件及原Source/Host未决请求，恢复后的真实业务与页面资格分别验收。

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
