# 整套WT重启的事件认证来源定位

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：模块B故障证据。状态：根因已定位，修复副本的完整七组件同根两代通过；公共候选集成、正式安装及其余恢复继续。范围：[STQ-P25](../specs/native-qmt-standard-trader.md)、[七组件主链](2026-10-30-seven-owner-sdk-mainpath.md)。新增文件全部位于E盘；活动QMT和首代封存原件保持。

## 根因与影响

原整套重启失败的`stage=trader`覆盖了Trader就绪后的恢复检查。自有CtaProcess只读细化阶段后，`REPRO-007.json`确认实际失败点为recovery_admission：插件LoggedIn、Host Ready、四查询完成、无活动订单/未决提交/open group，unsafe=1。只读诊断确认worker已完成的EventPage为IoError，原因SHA精确对应Common的`qmt_trade_event_receipt_invalid`；unknown=false。旧stage无法单独证明Trader登录或查询失败。

显式常驻Host按ADR-0017保留事件流的创世binding与原事件，第二代认证只更新附属连接关系。Native事件context使用当前连接binding；原v1页校验要求receipt的创世binding摘要与当前请求binding摘要相同。因此原Host认证接续已成立，Native仍按单连接合同拒绝页，随后恢复检查按unsafe拒绝。这是自有生产者/消费者的合同缺口，定位不涉及WT核心线程行为。

## 实际重放

原件根：`build/ms-seven-recovery-001`。`REPRO-007.json`为完整七组件两代原条件失败，root11096退出1；所有子进程归零、管道EOF、reader join与句柄回收成立。SDK替身保持1次、原委托1条、成交1条，真实下撤单0。

值重放结果（外部历史/待归仓路径：`../../build/ms-seven-recovery-001/value-probe-002/RESULT.json`）读取已关闭`repro-006`通信SQLite，mode=ro/immutable且读前后文件SHA相同。依据原TradeEventRecords._stream/read算法，从原流元数据及两条原始canonical事件重建页；HTTP回复原字节未捕获，重建页不冒充抓包。期望账户/交易binding来自该次执行配置，事件额度来自同次deployment。校验器直接链接SCMR冻结的原Common对象。

| 原生校验输入 | 实际结果 |
| --- | --- |
| 创世连接、原收据和两条原事件 | 接受，next=2 |
| 当前认证连接、同一原收据和原事件 | IoError / receipt_invalid |
| 反事实仅将收据hash改为当前连接 | 接受；用于定位单一失配，原件和生产逻辑保持 |
| 错账户 | 拒绝 |
| 无关连接 | 拒绝 |

两代binding仅host_instance_id和transport_generation不同。实际原生执行约0.231秒；编译55752、链接58160、运行76056均exit0，整树/EOF/join/资源关闭。前一`value-probe-001`编译缺Common include目录、exit2且完整回收，未执行校验；002补足独占探针include后通过。`RESULT.json`绑定源码、原SQLite、deployment、私有输入、exe、原BUILD及所有复用对象SHA。

## 修复与交接边界

候选沿现有认证关系给事件页提供只读续接证明，同时保留原收据及原事件正文。独占副本`continuity-candidate-001`只改变Common事件页校验及Host的TradeEventRecords.read：显式continuity产品返回v2页，默认单连接继续v1。证明在原_find完成当前精确认证检查的同一Journal事务内构造，原事件、receipt、命令及前沿保持。

原生产者重放（外部历史/待归仓路径：`../../build/ms-seven-recovery-001/producer-check-001/RESULT.json`）调用实际旧/新read方法，借用mode=ro/immutable的原SQL连接：旧页v1、新页v2，原receipt与两条原始canonical事件逐字节保持；退休连接、默认模式错连接及证明元数据容量不足均拒绝。该层验证没有建立HTTP或新Journal。其实际新页进入18项原生值校验（外部历史/待归仓路径：`../../build/ms-seven-recovery-001/continuity-check-002/RESULT.json`），含当前/创世hash、session/binding、认证标志、缺/多字段、原D及失败输出保持。候选Common对象同时通过原native_v4_codec及34事件向量（外部历史/待归仓路径：`../../build/ms-seven-recovery-001/native-regression-001/RESULT.json`）。候选安装包另跑33项原默认/续接Journal回归（外部历史/待归仓路径：`../../build/ms-seven-recovery-001/host-regression-001/RESULT.json`），实际临时SQLite、零网络/SDK；模块路径已核为候选安装。

## 完整七组件两代

REPRO-015（外部历史/待归仓路径：`../../build/ms-seven-recovery-001/REPRO-015.json`）在全新`repro-014/main007/sdk`通过完整原七组件、同Source业务进程、同通信Journal及同原生金融根：首代成交、NAP/策略读取、观衡停止期间WT继续、整个WT停止/重启、原策略状态恢复、第二代账户/NAP/采集读取、再次停止及最后只读观衡重开全部保留。实际约224.835秒，outer28676 exit0且整树、EOF、reader join、句柄回收齐全。

业务复核（外部历史/待归仓路径：`../../build/ms-seven-recovery-001/BUSINESS-WITNESS-001.json`）读取实际闭合原件：SDK调用/委托/成交均1，SDK线程等于原策略线程，两代认证保留同一创世流来源，最终durable/intended ACK/source ACK/published均2；24条保留查询均terminal/ok，P9/O9/D2/A4。14份成功closed收据包含两份WRI关闭和两份execution.closed.v2，Native PID5188/28784均exit0、recovery_ready与resources_closed为true。两代WT及三次观衡、Source全部正常关闭；原安装3885文件及原QA摘要保持。浏览器实际操作、真实QMT及真实交易资格均未授予。

该次使用安装副本的明确source overlay，并非新wheel普通安装：仅新Host生产者、重编Common消费者及只读诊断观察进入副本，原安装和共享生产源码保持。`ISOLATION-001`、`ISOLATION-OVERLAY-001`及`ISOLATION-OWNER-DIAG-001`分别绑定基线、源文件/本地文件清单变化与诊断。QA复制目录后按冻结配对材料的安装身份重新接线，保留所有校验；早期路径/清单准入失败保留在008至012等原件，不作业务修复通过依据。

013已完成两代Ready/恢复/SDK1/正常关闭，后段QA短等待仍使用首代预留时间而失败。014继续通过第二代观衡和完整第二代flow，最终第三次App健康检查被原QA统一预留截止提前结束，App随后由QA停止。两次整体均为失败，原记录保持。015修正本地阶段预留，并将完整QA外层总预算由320秒改为420秒、有限Job由330改430秒；各产品启动、请求、交易及关闭截止保持，完整检查条件继续执行。

候选差异的首轮两轴full审查未发现新增P1/P2，报告按实际SHA冻结；完整主链后继另按015原件复核。Common及公共Host发行归A集成，LF集成差异（外部历史/待归仓路径：`../../build/ms-seven-recovery-001/INTEGRATION-001.patch`）已对当前两目标执行git apply --check通过；原候选patch保持，LF处理单独登记。当前WT核心生产修改0、金融账本新增0、真实交易0。公共合入、同批正式wheel/Native安装与搬迁、当前候选新增事件后缀及真正unknown整链继续待验；完整400期RT/BT、正式跨日等模块要求继续。
