# 上游差异登记

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：维护台账。权威范围：需要长期保留的核心覆盖及退出条件；实际 Git 差异由对应上下游基线生成。

当前任务约束（2026-10-21，含后续澄清）：用户要求保持 WT 原架构、通过适配接入。确需修改框架源码时，先提交必要性、替代方案、范围、风险、验证与回滚说明，经用户明确批准后实施；批准前相关文件只读。以下 CORE-001–006 涉及的 12 个既有上游源码差异已冻结，归属、必要性及外置/退出方式待逐项复核并提交用户决定。登记和既有测试结果分别证明当前实现及行为，架构接受状态仍为待审。活动范围见[当前目标](../roadmap/TARGET.md)。

每项记录：上游文件/符号、需要保留的行为、现有接口不足、最小修改、下游提交、回归入口、关联规格/ADR、上游提案或已修复版本、退出条件与维护者。

2026-10-21 后续批准：用户明确批准仅保留 CORE-004 构造初始化 `_check_time(false)` 一行；普通配置行为保持。批准依据及验收见[本项决策](../migration/current-approval.md)。其余项仍冻结，首轮统一冻结描述由此处作该单项例外更新。

当前逐项技术调查见[框架差异审阅](../migration/core-change-review.md)。调查已列出公开接口替代限制、待补原样上游复现和回归/回滚要求，申请范围与用户批准状态继续分别登记。

已有上游自身的功能属于上游基线；文档、规则和维护工具的下游差异另通过 Git 识别。核心兼容修改登记如下，实际发行关联其已验提交。

| ID | 上游文件/符号 | 下游要求与依据 | 回归入口 | 上游状态与退出条件 | 维护者 |
|---|---|---|---|---|---|
| CORE-001 | `src/Includes/WTSDataDef.hpp` 全局命名空间 | C++17 与 Windows RPC `byte` 共存；移除全局 std 导入，将 min/max 限定到 wtp，vector 明确命名；WtExeFact 两个 VWap 源文件及头文件显式使用 std 类型/函数 | `tests/native/test_header_namespace.cpp` 及实际 WtCore 构建 | 未提交上游；上游提供等价修复并经回归后退出自有差异 | 原生构建维护者 |
| CORE-002 | `src/WtDtHelper/WtDtHelper.cpp::store_bars` | 历史发布须得到真实写入结果；校验输入并传播目录创建/写入失败 | `tests/integration/market/test_market.cpp` 磁盘失败与原生回读 | 未提交上游；等价错误传播经回归后退出 | 数据维护者 |
| CORE-003 | `src/WtDtHelper/WtDtHelper.h/.cpp::read_dsb_bars_limited` | 不可信历史在解压/分配前校验格式、ZSTD 声明大小和 Bar 预算；保留既有 ABI，新增有界入口供 C++/Python 共用 | market 超大声明负向与 business 原生跨语言回读 | 未提交上游；上游提供等价有界 ABI 并迁移消费者后退出 | 数据维护者 |
| CORE-004 | `src/WtCore/ParserAdapter.cpp::ParserAdapter` | initExt 路径需要确定的时间检查默认值；构造时初始化 `_check_time=false`，普通 init 继续读取配置 | `tests/integration/runtime/` 真实 WT adapter 快照链路 | 未提交上游；等价完整初始化经回归后退出 | 运行维护者 |
| CORE-005 | `src/WtDataStorage/WtDataWriter.h/.cpp` 映射与线程生命周期 | 映射创建/写入/活动时间、checker 过期/释放、归档及停止清理共用递归生命周期门；块指针在保护内验证；先关闭准入/唤醒队列，门外回收 task/archive/checker 后清理；原子终止标记、重复停止与工厂派生删除保持资源释放完整；初始化配置固定过期及检查预算并严格校验原值；清理重试每轮关闭映射、锁外可停止唤醒等待 | `tests/integration/minute/` 实际六类映射过期/重映射、并发写入/停止、占用文件导致清理失败时及时停止、清理后重映射、配置异常原值及原生分钟场景 | 未提交上游；上游提供等价生命周期互斥、队列退出和资源释放并经回归后退出 | 数据维护者 |
| CORE-006 | `src/WtCore/TraderAdapter.h/.cpp::restoreRetainedChannel/invalidateRetainedChannel` | 保留原运行投影，同交易日、原完整初始化及连续补发后恢复真实ready；统一非虚资格撤销与Close lost，ready/lost以快照列表分发，成功lost不重送、异常lost保留待重试，未确认期间禁止恢复；isReady结合实际在线状态。保持ITraderApi/Spi ABI，原持仓/统计归约器唯一，WtCore对象布局变更须匹配重编 | `tests/integration/runtime/` 真实 ready/lost/补发/ready2、初始及恢复ready重入隔离、lost异常/重试和stop幂等链 | 未提交上游；上游提供等价受管恢复/隔离接缝并验证后退出；来源连续性证明由接入层提供，lost为幂等控制通知而非恰好一次 | 执行维护者 |

新增核心差异前核对[上游规范](../development/upstream.md)，随实际提交登记；升级时逐项复核。退休项保留历史记录与后继依据。

## CORE-007：受管 CTA 生命周期

用户条件授权经固定上游和独立复查满足后实施，最终要求见[NCS](../specs/native-cta-shutdown.md)。Runner三文件、CTA/ticker四文件、base两文件、parser两文件、DtMgr两文件与CtaStrategyMgr.h共14文件。复用现有stop/join及pool语义，新增配置默认false；仅受管CTA空交易取得本轮验收资格。类布局变化要求全体消费者重编，插件虚接口/导出ABI保持。回归见tests/integration/runner_shutdown/，原负例保留在runner_host。上游提供等价完整关闭链后复验并退出该覆盖。已完成[开发隔离验收](../evidence/2026-10-21-native-cta-shutdown.md)，生产未发布。

## CORE-008：随机Reader空历史输出计数

用户明确批准[NRC单项修正](../specs/native-reader-empty-count.md)并要求中文注释。仅`WtRdmDtReader.cpp::indexBarFromCacheByCount`空分支设置count=0、原因注释和括号；不改变正常索引、类布局、线程/锁或文件格式。原样51通过/21失败，修正72通过；正式CTest与原生回测通过，428条真实回读保持。证据见[空计数修正](../evidence/2026-10-21-native-reader-empty-count.md)。未发布、未提交上游；上游获得等价修正且空/混合/正常回归通过后退出此覆盖。维护者：数据接入。

## CORE-009：券商订单完整查询同步

用户2026-10-27明确批准[订单同步两文件方案](../migration/native-order-query-sync-proposal.md)。仅TraderAdapter.h/.cpp增加order_context=query_first路径，要求既有已批准position_by_query；缺省/native保持。完整查询发布原订单表/余量和订单统计，迟到成交不再扣查询余量，自有独立订单投影退出。原cancel/doCancel正文、频率缓存及ITraderApi虚接口保持。类布局变化要求同批重编所有消费者；候选组成仅含固定上游及明确批准的差异，其他冻结代码保持。主路径证据见[订单同步验收](../evidence/2026-10-27-qmt-native-order-query-sync.md)，完整恢复与发布仍待完成。上游提供等价可选查询权威模式并通过全部相关链路回归后退出此覆盖。维护者：执行接入。

## CORE-010：显式Writer生命周期与映射同步

用户2026-10-28明确回复“你改吧”，批准[WLC规格](../specs/native-writer-lifecycle.md)及[两核心文件方案](../migration/native-writer-lifecycle-proposal.md)的L＋M开发和隔离验收。仅WtDataWriter.h/.cpp相对固定原版形成自有受控覆盖，旧CORE005工作树差异保持冻结。默认WtDataStorage原DLL保留，显式WtDataStorageLifecycle选择适配；原聚合与文件格式沿用。统一覆盖入口为`integrations/wondertrader_lifecycle/writer-lifecycle.patch`。固定候选已通过6982证券主链、原600秒过期、八种短模式及独立审查，具体输入和范围见[隔离证据](../evidence/2026-10-28-writer-lifecycle-afternoon.md)；非allday、其他映射和生产资格分别核实，尚未生产切换。上游提供等价生命周期/映射同步且对应主路径和并发回归通过后退出覆盖。维护者：行情存储接入。

## CORE-011：显式股票执行单元借用引用配对

用户2026-10-30明确回复“批准这3个框架文件，按配置选择修正版”，原始回复及限定授权见APPROVAL-001（外部历史/待归仓路径：`../../build/ms-stock-reference-fix-001/APPROVAL-001.json`）。唯一方案为[SCMR](../migration/native-stock-metadata-ownership-proposal.md)：仅WtStockMinImpactExeUnit.h/.cpp、WtExeFact.cpp新增同类构造模式和工厂名WtStockMinImpactBorrowedExeUnit；集中覆盖为[stock-reference.patch](../../integrations/wondertrader_stock_reference/stock-reference.patch)，已在三文件原字节的LF副本上实际应用并逐内容核对；原名和缺省构造保持原行为。适配路径对get_minOrderQty临时借用的基础资料不再release，原init/destructor长期引用仍按原逻辑配对；执行量价、策略账本、订单和调度算法保持。

类布局改变，同批重编两个直接头消费者及全部工厂单元，自有Host/运行体重新链接；真实应用还需按SCMR-06核完整安装和消费者。自有Host在交易API初始化前核实际工厂能力，唯一1.1.2桥只接受精确的原名或适配名。回归入口为tests/integration/qmt_cta_product的正式受管策略、stock_factory_admission及diagnostics/stock_commodity_modes；当前开发和隔离验证正在进行，真实下撤单和生产切换未授权。原完整制品及配置保留回退，原路径的已知退出故障单列。上游提供等价借用引用配对并经相同生命周期及业务回归后退出本覆盖。维护者：模块B执行接入。
