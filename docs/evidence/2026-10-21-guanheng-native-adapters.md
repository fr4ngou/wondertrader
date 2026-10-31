# 2026-10-21 观衡原生接入与隔离验证

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：验证记录。结果：pass（可确定模块实现、独立审查和隔离开发包）；实际端点/终端/服务切换仍 pending-verification。关联规格：[GNA-R1–R6](../specs/guanheng-native-adapters.md)；上位范围：[R1–R13](../migration/guanheng-qmt-tdx.md)。本记录与上一阶段原生工具链证据分开，原始输入、结果和审查见冻结证据索引（外部历史/待归仓路径：`guanheng-native-2026-10-21/README.md`）。

## 输入与权限边界

仓库 `E:\workspace\wondertrader`，分支 `codex/qmt-migration-plan`，上游 HEAD `08b230dd05facf6d650d949bfe51054115a2ecb1`，实现含未提交文件。使用已有 MSVC x64、锁定的离线依赖和 `D:\workspace\qmt\.venv\Scripts\python.exe`。外部观衡代码只读按逐文件 SHA 加载，身份见 upstream-contracts.json（外部历史/待归仓路径：`../../integrations/guanheng/upstream-contracts.json`）。

最终源码输入摘要为 `2c10699a1671027924f17229e3275141efed6bc7063846423ec7f640dfb91e4f`，完整文件及构建输出摘要见构建身份（外部历史/待归仓路径：`guanheng-native-2026-10-21/built-source.json`）。MSVC toolset 14.51.36231、CMake 4.3.1、Ninja 1.13.2；Boost 1.85.0、spdlog 1.9.2、rapidjson 1.1.0 使用上一阶段已核查的固定离线缓存，最终流程再次校验变化文件。

收尾只读确认 QMT 主干推进至 `1f564b6496b0942545783567acb0003ebf19b245`，通信候选为 `d425cc97541e707bef5c5ed7fb22ddc0c1b297e2`。首次刷新两者工作树均干净；最终复核主干另有原会话的过程/任务文档改动，状态原样保留，见最终工作树快照（外部历史/待归仓路径：`guanheng-native-2026-10-21/worktree-identity.json`）。原固定业务/Broker 运行依赖逐文件仍匹配；控制 RPC 已集成且当前契约仍未开放命令 HTTP/RPC，Host order_ready=False，详见上游刷新（外部历史/待归仓路径：`guanheng-native-2026-10-21/upstream-refresh.json`）。本次没有修改或集成该工程。

运行使用 E 盘隔离目录、合成行情与账户端点。未连接真实账户、调用真实委托/撤单、变更原 QMT 工作树或部署服务。工厂缺少后端时 unavailable；Simulation 与测试校验器只取得开发验证资格。

## 当前验证

| 入口 | 已观察结果 | 证明范围 |
|---|---|---|
| `GuanhengmarketTests.exe` | 最终 13 项通过且独立复验；原并发场景修复后开发者重复 300 次、独立重复 100 次 | 原生历史、单位/元数据、有界读取、补数、冻结及并发认领；实际跨进程 gate 分类/恢复另有 14 次调用 |
| `GuanhengexecutionTests.exe` | 最新源码重新构建后 10 组通过 | 授权原字节、唯一 Host 执行、查询边界、幂等、未知状态、回调重入 |
| `GuanhengRuntimeProbe.exe --self-test` | 最新源码重新构建后 7 组通过且独立复验 | 真实 WT ParserAdapter/TraderAdapter，合成市场及原子账户/事件/恢复端点 |
| business unittest | 30 项通过且独立复验 | 原 DTO/Portfolio/Bridge/Console callable、固定原核心、原生 DSB、时间与覆盖语义 |
| `GuanhengMinuteProbe.exe` | 5 根实际闭合 Bar、六类映射过期/重建、文件占用失败停机、异步队列/重绑通过且独立复验 | 原生 Writer/Reader 累计差分、量额、午休、重连与消费者隔离 |
| `wt_strategy_replay.py` | 实际 WtBtPorter 驱动 139 根闭合日线、2 个当期目标，与原核心整段比较通过 | 固定 140 根 DSB、1 根预热、真实 WT 回放时钟及完整字段；无委托 |
| `scripts/project.py check` | pass | 本地文档导航与技能清单完整性 |
| 最终 `scripts/native.py all --offline --jobs 4 --qmt-source D:/workspace/qmt` | 退出 0；全部 13 个阶段 passed | 当前源码绑定 configure/build/CTest/流水线/制品校验及全部搬迁包调用链 |

完整 CTest：32 项启用通过、0 失败、0 skipped，另 1 项上游全天用例 Disabled，21.20 秒；流水线：24 项通过，14.365 秒。业务 30 项、执行 10 组和运行时 7 组分别包含在相应集成入口内，不与 CTest 个数相加。全天 0/2400 的已知隔离原因及恢复条件保留[上一阶段记录](2026-10-21-native-build-automation.md)。

搬迁包逐项通过：Runner --help、原生 CTA 模拟开平、四工厂缺端点拒绝、真实 WT adapter 运行时、实际 Writer/Reader 闭合分钟、LC1→DSB→Python 量额、原 Console callable/Portfolio shadow 零委托，以及原核心在实际 WT 时钟下的 139 根闭合日线与 2 个非预热目标对照。完整阶段收据见receipt（外部历史/待归仓路径：`guanheng-native-2026-10-21/receipt.json`），Python 中文结果已经按 UTF-8 正确保存。

## 开发制品

制品为 `E:\workspace\wondertrader\build\native\packages\dev-20261021T011337Z-02b67464.zip`，4,698,169 字节，清单含 45 个文件；SHA-256 为 `c70222ef9a413ec4698b813323ae26ad3b432b8863b9b240ccdaa64b5a6d2611`。包标识 development，保留未提交源码状态，尚未正式发行。

清单的源码摘要与成功构建、测试及最终源码一致。独立接收端 `native.py verify` 使用正确外部摘要退出 0，错误摘要退出 1 并报告 archive checksum mismatch；验证使用独立生成根，没有覆盖最终完整流程的收据。见制品身份（外部历史/待归仓路径：`guanheng-native-2026-10-21/artifact.json`）、清单（外部历史/待归仓路径：`guanheng-native-2026-10-21/manifest.json`）及接收端记录（外部历史/待归仓路径：`guanheng-native-2026-10-21/README.md`）。

所有包级场景运行后再次验证解包目录，文件集合及摘要仍与清单完全一致。最终文档导航、Ruff 和按上游 CRLF 语义的 diff 空白检查通过；当前源码与 built-source、收据及制品来源保持匹配，见最终检查（外部历史/待归仓路径：`guanheng-native-2026-10-21/final-checks.json`）。

## 审查及修复

独立审查分别覆盖行情/历史、执行/运行时、业务和构建/包级接线。历史补数的部分页发布、并发合并、冻结身份与代际/目标认领问题已修复并回归。业务来源与时间边界的三项发现已通过独立 delta 复验。

交易恢复与消费者隔离、分钟映射生命周期/重绑、文件占用清理失败停止，以及构建来源选择均已通过对应独立复验。首次完整 CTest 发现 Windows 历史 lease 目录删除/重建竞争产生 AccessDenied，候选在此停止；随后使用稳定文件独占句柄串行化整个 lease 生命周期，普通竞争统一返回 Backpressure，权限/磁盘错误仍返回 IoError。遗留 marker 保留核查，恢复写入全新根。原始失败、开发者复现、独立跨进程与重复回归均已冻结。

最终适用源码审查无剩余 P1/P2；57 个已列明代码输入按各自最新适用报告与最终文件摘要核对，全部匹配，见源码对齐（外部历史/待归仓路径：`guanheng-native-2026-10-21/review-source-alignment.json`）。跨模块接线以 full 审查为基础，来源选择和 Python 编码随后做 delta；执行/分钟/历史根改动分别做适用 full 或 delta。较早报告的二进制身份只证明当时输入；最终统一构建和搬迁包结果另绑定本记录的完整源码摘要。

## 范围审计

| 要求 | 当前实现及验收入口 | 尚缺条件 |
|---|---|---|
| GNA-R1 | 独立来源/历史/执行端点及共同身份，四个实际工厂与搬迁验证通过 | 真实后端绑定按统一决策及适用资格接入 |
| GNA-R2 | MarketParser、ManagedRuntime、MinutePipeline；真实 WT 接线、故障与包级验证通过 | 真实来源采样 OHLCV/coverage 资格待定 |
| GNA-R3 | NativeHistoryStore、HistoryPreparationQueue、LC1→DSB、有界读取、冻结恢复与并发验证通过 | 实际十年历史 profile/许可与覆盖证据待定 |
| GNA-R4 | ManagedTrader/Adapter；原子基线、连续回报、恢复证明及真实通道隔离验证通过 | 真实 Host 相应接缝与终端资格待定 |
| GNA-R5 | 原服务 DTO/业务门面、实际原核心 WT 回放及搬迁包通过 | 真实服务切换与页面发布验收后续实施 |
| GNA-R6 | 所有权、关闭的扩展接缝、正负向回归、独立审查、完整制品与统一决策包已交付 | 本次隔离开发范围已验；整体迁移继续按待定项与运行资格推进 |

上位范围逐项审计如下。表中的“实现”指当前可确定前端与隔离链；待定真实来源及生产切换仍保留对应缺项。

| 上位要求 | 当前源码与证据入口 | 剩余范围与依赖 |
|---|---|---|
| R1 观衡与事实所有者 | 业务门面、原服务只读导入；ADR-0001、GLOSSARY；Host 唯一提交权威、WT 原归约器 | 原服务实际来源切换及原实现退出需独立切换验收 |
| R2 四插件 | ParserQMT/TDX、TraderQMT/TDX 实际 DLL 工厂及默认拒绝探针 | QMT 端点绑定 DEC-001、TDX 真实后端 DEC-002 |
| R3 历史/实时/存储 | History/MinutePipeline、WtDtHelper/Storage、C++→Python fixture、补数/覆盖/冻结测试 | 实际十年数据与许可/单位/日历 DEC-003；真实来源分钟完整性待采样 |
| R4 QMT 行情 | MarketParser、BrokerV1Facade、QmtResultProjector；订阅/时钟/代际/容量隔离测试 | 实际 Broker 订阅能力、原 MarketData 共享订阅/租约接线及源资格依 DEC-001/上游正式交付 |
| R5 TDX 行情 | ParserTDX 与 LC1 导入、源身份和量额元数据 | 真实在线协议/许可、源时间/延迟与实际 profile 依 DEC-003，不能用合成快照授资格 |
| R6 QMT 交易 | ManagedTrader/Adapter；原签名字节、强原子基线、连续回报与未知状态测试 | 上游命令 RPC/许可/Journal 恢复及正式快照水位/重连证明；实际终端按独立授权验收 |
| R7 TDX 交易 | 同一受管前端、能力与裸交易拒绝 | 实际 DLL/SDK/受管桥和可靠回报尚缺，DEC-002；当前不可实盘 |
| R8 观衡入口兼容 | 原 DTO、MarketData 界面、Console callable 正常/空/异常/恢复、Portfolio/Bridge 原业务构造 | 服务发行归属 DEC-004；Research/Portfolio/Bridge/Console 运行路由与线上页面未切换 |
| R9 同核心回测 | 固定 DSB→实际 WtBtPorter 回放时钟→原纯核心→影子目标，整段/增量比较 | 实际数据费用/复权/涨跌停/成交等价及实盘策略逐项 shadow，不能从合成回放推广 |
| R10 扩展与资源 | 共同身份/能力、独立强类型端点、任务暂存/订阅/映射预算、poll 截止与背压 | 真实 SDK/ABI/权限 profile、生产资源极值和进程监督资格待实际绑定 |
| R11 构建/ABI/依赖 | 锁定离线依赖、Windows x64 SDK-independent 原生构建、实际工厂和跨语言布局；CORE-001–006；当前完整开发包通过 | 真实券商 SDK、32位独立进程、其它平台矩阵各需新资格 |
| R12 阶段/异常/回滚 | P0/P1 与 P2/P3/P4 的隔离前端切片、异常回归、原生包校验；原系统保持运行 | P2/P3 真实接线、P4 实际受控执行、P5 后端与 P6 单路由切换尚未执行；生产 supervisor/升级/回滚演练后续验收 |
| R13 QMT 通信依赖 | 固定 Broker/Transport 基线、原字节门面且无新帧/文件轮询；收尾只读确认控制 RPC 已合入新主干，原固定运行文件 SHA 仍匹配 | 当前控制 RPC 仍只读；实际客户端绑定、受限终端/命令/单执行权/迁移恢复联合验收依原工程交付，缺项禁写 |

以上证明本轮可确定模块与隔离开发交付；账户及页面生产切换的缺项继续保留，整个移植尚未完成。

## 待定与后继

[统一决策清单](../migration/decisions.md)集中 QMT 绑定方式、TDX 交易、真实历史 profile 和私有业务发行归属。真实 Host 默认缺少原子快照已吸收水位与同消费者重连证明时保持禁写。现有服务、生产数据、账户持仓及执行 Journal 保持原权威，未建立第二套实际持仓或命令账本。

后继实施按决策和上游正式交付选择实际端点，再完成终端资格、生产 supervisor/路由、逐策略 shadow、受控模拟及真实用户入口验收。该后继范围与本次确定模块隔离实现分别记录。
