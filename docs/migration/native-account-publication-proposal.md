# 原生账户四查询的WT只读发布接线

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：跨模块接口规格。状态：accepted，独立WT生产者实施中；公共装配及C消费按同一合同接线。范围：模块B实际账户发布缺口；A集成WT公共生命周期，C只读消费。职责沿[ADR-0016](../architecture/adr/0016-independent-wt-runtime-and-observer.md)，金融事实沿[系统架构](../architecture/overview.md)，不改变WT账本或框架行为。

## 目标与已证实缺口

观衡在策略尚未接管持仓时，也能查看券商资金、持仓/可卖、活动委托和当日成交；启动、刷新和关闭原生消费者均由WT持有。依据为[三模块计划B-01及C账户入口](parallel-system-delivery.md)。

复用[原生能力目录](../development/wondertrader-capabilities.md)的WT-T01标准查询、WT-T08通道记录及现有Scan接缝；原Adapter/插件继续拥有来源观察，发布层只承担受管运输和生命周期。

根已交付真实QMT精度修正版Scan/TraderQMTReadOnly，四组4P/0O/0D/1A、67事实/39ABI/24浮点严格一致，正常关闭及原探针恢复。B复核22份原件、两个实际制品及三源SHA，新增查询0；SUCCESSOR002（外部历史/待归仓路径：`../../build/ms-real-account-consumer-001/SUCCESSOR-002.json`）保留准确范围：Host诊断包装、旧中断unknown、真实同四owner和v4交易执行另验。

现有[execution_process.py](../../apps/wt_runtime/guanheng_wt_runtime/execution_process.py)的business_observation定位到原CTA strategies.json；[execution_configured.py](../../apps/wt_runtime/guanheng_wt_runtime/execution_configured.py)在原策略调度发布broker_observation，仅含当前持仓及balance/available等观察，不提供四查询原字段集合。其INIT还需核策略实际周期和原WT初值，实际账户查看不能依赖这些策略输入齐备。

原生GuanhengAccountScan（外部历史/待归仓路径：`../../src/GuanhengAccountScan/main.cpp`）已提供有界v2 observation/completion帧。[观衡原投影](../../apps/guanheng/guanheng_app/account_projection.py)已能消费完整四组并保留present/unknown/invalid及来源身份；[原受管单轮](../../apps/guanheng/guanheng_app/account_scan_runtime.py)目前由App持有。当前A的account_host=qmt_read管理只读通信Host，普通只读页面仍缺WT持有的原生轮询结果定位。这是生命周期和结果运输接缝。

## 唯一链路

QMT原四查询 → 原只读Host（A原account_host）→ 原TraderQMTReadOnly/TraderAdapter/Scan（B固定新制品）→ WT持有原生单轮及观察发布 → C只读文件读取 → C原validate_observation/project_account → 原账户DTO/HTTP/页面。

观察发布保持原observation帧和原completion。发布者核固定协议、scan_id、配置/制品身份、容量和真实完成/回收；四组事实及字段语义继续由原Native与C投影负责。它保存可覆盖的最新观察投影，不记独立持仓、费用、资金或成交账。

R20继续发布策略理论状态及策略所见的券商观察。新账户发布保留完整账户事实，两个入口分别标明来源；配置明确选择账户页的来源，不在页面自动拼接两份账户或用策略理论数量填充未知券商字段。

## 公共接线

新增可选WT组件account_observation，kind=native_account_observation，依赖原account_host。B提供固定工厂及安装后入口；A在公共runtime中注册依赖、启动和逆序关闭。省略该组件保持原配置。WT ready表示受管入口就绪，首轮账户事实以观察状态单独表达。

guanheng.account-observation-reference.v1固定为schema及path、ready_path、control_id、config_sha256、pid六字段。原IPC/inspection/read-profile版本及预期账户/环境随受控本地观察材料中的binding提供；凭据、Host启动命令及私有配对留在WT配置。字段集合沿下述NAP-v1合同。

观察文件包装原完整v2帧及completion、scan_id、发布UTC、当前查询状态和最后成功时间。每轮成功须同时具备原事实帧、成功completion、实际exit0及Job/管道/线程/句柄回收；成功空order/deal是已知空集合。初始无结果、更新中、失败保留旧值、源认证换代和关闭分别表达，旧值标原时间与当前错误，不冒充本轮成功。

部署显式给出同安装Scan/插件清单及SHA、原只读配置、单轮原总期限/行数/字节预算、刷新间隔、停止预算和E盘独占输出根。刷新沿单一owner顺序推进；上一轮未收口时保持busy，不叠加新轮。停止先关新轮准入，当前轮沿原预算排空；超时/强杀保持该轮失败并完成物理回收，成功观察保持最后已核版本。源Journal/权限/保留由A原Host负责，发布者不删除Journal、不重开旧Journal或更换未知请求身份。

## 文件与责任

| 范围 | owner及实施约束 |
| --- | --- |
| Scan、原读插件、v2事实/完成帧 | B；复用已验精度制品，保持金融计算与来源映射 |
| WT固定观察工厂、单轮监督及原帧发布 | B；复用原ProcessJob/ThreadOwner和受管单轮接缝，金融投影留原实现 |
| WT公共组件注册、account_host依赖、统一离线安装与版本 | A；保留当前公共改动，按新公共合同组合 |
| 原App单轮owner退出、只读locator消费、原投影/HTTP/页面 | C；B提供精确兼容候选，C在同候选完成接线 |
| 真实QMT正文、私有配对启停、现场与现存WT数据服务 | 根统一协调；本提案无现场操作 |

目标部署由WT持有扫描生命周期，观衡保持只读；旧App单轮监督源码作为迁移来源，其金融校验/中文DTO与页面复用。实施先检查原受管单轮可移出的纯生命周期代码，通过兼容导出保持旧调用身份，避免另写平行进程监督器。当前不直接修改C文件、A公共runtime或安装版本。

## 验收ID与发布边界

| ID | 必须证明的完整路径 |
| --- | --- |
| NAP-P1 | 普通无App安装WT管理原Host及Scan；C读取已发布结果，页面请求新增Host/Scan进程为0，原四组字段和完整性保持 |
| NAP-P2 | 原IPC原值到C原投影逐字段/浮点精确，实际source/transport/broker身份及已知空集合保持；错误/未知字段保持原语义 |
| NAP-P3 | 首轮等待、两轮更新、失败保留旧值、认证换代、超时/取消及恢复；未知原身份保持、无重叠轮/无Journal改写 |
| NAP-P4 | 每轮原completion/exit/Job/EOF/join/句柄分别核，WT停止和父死亡沿原监督；失败观察与物理回收分别记录 |
| NAP-P5 | 原账户view与R20策略view同时可读且来源分开，旧配置兼容、错绑定/旧帧/旧制品/重解析点和容量在消费前拒绝 |
| NAP-P6 | 同候选真实四查询、实际HTTP/中文页面、源码/安装/帧/配置SHA、独审和回退；真实账户副作用由根协调，真实下撤单为0 |

下一动作是按下述冻结合同完成B生产者、A装配、C消费及同候选验证。标准v4交易账户接线、持仓实际周期接管、完整交易恢复和发布验真继续分别验收；新增WT核心行为为0。

## NAP-v1冻结合同

固定工厂为`guanheng_wt_runtime.account_observation_process.create_process(descriptor_path, expected_sha256)`，返回与原Runtime一致的`start(deadline)`、`status()`、`request_close()`、`close(seconds)`及startup_seconds/shutdown_seconds接口。组件名`account_observation`，kind=`native_account_observation`；A在account_host之后、history/collection/execution之前启动，逆序关闭。account_host必须存在且kind=qmt_read。公共runtime/版本与统一安装由A修改。

descriptor精确字段为`schema=guanheng.account-observation-deployment.v1`、`installation`、`configuration`、`configuration_sha256`、`control_root`、`refresh_seconds`、`startup_seconds`、`stop_seconds`。路径为E盘绝对路径；配置为原schema2 Scan文件，其raw SHA与descriptor一致。installation包含原GuanhengAccountScan.exe、traders/TraderQMTReadOnly.dll和`account-observation-installation.json`，清单精确为`schema=guanheng.account-observation-install.v1,files={两个相对文件名:SHA256}`。原生配置library路径/摘要必须指向同安装。refresh_seconds取0.1..3600；startup_seconds取0.1..60；stop_seconds取原单轮total_seconds+2..120。刷新间隔从前轮收口后起算，不积压轮询队列。

status在`account_observation`字段公开以下locator，六字段精确固定：`schema=guanheng.account-observation-reference.v1`、`control_id`、`config_sha256`、`pid`、`path`、`ready_path`。pid为实际持有扫描Job的WT Python进程，路径位于本次control_root/UUID。locator不含完整账号、密钥、URL或启动命令。ready.json身份精确为`schema=guanheng.account-observation.ready.v1`、control_id/config_sha256/pid，ready表示发布入口可读；首次四查询结果另看观察文件。

path指向原子替换的`observation.json`，schema=`guanheng.account-observation.v1`。其精确字段为schema、control_id、config_sha256、pid、revision、updated_at、state、error_code、last_success_at、binding、scan_id、observation、completion、close、attempt。revision从1递增；UTC为带六位小数Z格式。state取waiting/refreshing/ready/degraded/stopped；error_code仅固定内部码。binding只包含原投影所需account/environment/max_rows/ipc_schema/inspection_version/source/read_profile_version。完整账号只在此受控本地材料核绑定，HTTP由原投影输出掩码。

成功观察保留原生v2的完整observation/completion字典，scan_id对应这次成功；close含原status/closed/joined/worker_live/queued/exit_code/error_code及独立resources证明。resources精确包含member_before_resume/tree_reaped/stdout_eof/stderr_eof/readers_joined/resources_closed。原子文件上限为原20MiB帧加64KiB包装。consumer校验locator和ready身份，再从同一读句柄读取完整观察，使用binding作为原validate_observation的配置来源并交原project_account；金融值验证、单位、掩码和中文DTO继续唯一归C。运行侧只校验原帧运输、行数、批次交付及关闭，不复制金融投影。

resources六项均为bool，True表示取得对应证明；包括busy在内的未确认路径保持False，字段集合固定。原子换名期间短暂未见文件或Windows32/33共享冲突为pending，消费者沿原读取截止获取下一快照；其它协议错误保持失败。

attempt为最近一轮的scan_id/completion/close；初始为null。失败保留上次成功的scan_id/observation/completion/close/last_success_at，更新attempt及degraded；首次失败保持这些成功字段null。refreshing也保留原成功时间。来源换代后的成功整帧替换旧帧，四组保留原共同来源校验；失败期间旧帧始终明确标旧时间，C不得用其证明新代际成功。正常停止不启动新轮，当前轮沿原总D排空，最后状态stopped。停止预算耗尽保留原owner/OS锁和资源引用，待实际join后释放。

原App的schema2配置、严格JSON和单轮监督迁移至WT包；提供C兼容候选使原入口复用新运输owner再调用原投影。旧schema1路径继续保持历史范围。本合同的安装后主链、两轮更新、失败恢复及C实际HTTP按NAP-P1..P6逐项留证；合同冻结本身不授运行资格。
