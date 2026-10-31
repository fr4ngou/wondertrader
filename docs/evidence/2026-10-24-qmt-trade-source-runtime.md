# QMT 同策略交易装配与关闭验证

类型：开发验证记录。日期：2026-10-24。状态：源端开发切片验证通过；完整交易接入 pending-verification。对应[QST-R16](../specs/qmt-shm-trading.md)。整体迁入继续开发。

## 根因与实现

源端原线程执行服务、交易控制分派、账户回调和显式策略生成已接通。复用现有读 owner、ControlPeer、TradingKernel 和事件缓冲；原只读生成结果按固定字节样本保持。生成入口在账户订阅前发布同一个 owner，定时入口执行 SDK，handlebar 保持检查职责，stop 发关闭通知。

用户要求取消额外的“实盘资格”。本次移除 SourceTradingService/RestrictedTradingAgent 的 live_authorized 参数与状态；正常 writes_enabled 配置及终端非回测模式决定写开关。WT EntrustID、OrderID、userTag 保留标准含义；command_id 是通信内部自动去重身份，用户无需填写或审批。

退出过程中可能发布拒绝结果失败、收到迟到 ACK，或在最终时钟读取期间收到晚到回报。统一修正为先冻结原关闭期限，源发布失败时停止 I/O 并保留未确认 owner；确认与资源回收共用原期限。最终时钟在锁外读取，随后非阻塞取得关闭锁、service 锁和 event 锁，核当前期限、失败和实际排空，再提交完成事实。锁忙保持未确认；成功关闭后的重复调用只核当前事实。晚回报仍形成 gap，实际券商回调整体终止需真实宿主验证。

## 当前输入与验证

最终源码身份：`build/guanheng-workspace/qmt-trade-source-runtime-004/REVIEW-INPUTS.json`，共 15 项规格、源码和测试输入。完整内存闭包与正文身份：`build/guanheng-workspace/qmt-trading-memory-probe-007/runtime-identity.json`。

| 验证 | 实际结果 | 原件 |
|---|---|---|
| 开发端交易、原只读控制/账户/历史受影响回归 | 334 passed，7.85s | `account-runtime-install-001/build-qmt-trade-runtime-regression-004/driver.log` |
| 国信 Python 3.6.8 源端/控制/回调/期限/配置回归 | 167 passed，0.272s | `account-runtime-install-001/build-qmt-trade-runtime-sdk-regression-004/driver.log` |
| 完整生成策略与 91 模块内存闭包 | passed；文件与外部导入尝试 0；实际 SDK 0 | `qmt-trading-memory-probe-007/result.json` |

表内原件均位于 `build/guanheng-workspace/`。进程由隐藏、创建时加入 Windows Job 的有界 owner 执行；最终测试、内存准备/运行与文档检查五份收据均已核实：控制台未创建、创建时 Job 归属、进程树清空、管道 EOF/读取线程 join、资源关闭全部通过，无强制终止。文档导航检查通过，其范围不覆盖业务运行。

内存探针使用完整 render_trade_strategy 正文，走 init、账户订阅、定时入口、订单/成交/错误回调及 stop。运输启动明确使用替身，实际交易 SDK 使用替身；共 4 次 SDK 替身调用，其中源端下单/撤单 2 次，源端 4 条事件完成显式 ACK。该轮验证闭包、开关和策略调用链；Host 持久提交及真实 QMT 交易尚未验证。

## 独立审查与限制

旧候选和中间失败收据保留原身份。两份最终 full 静态审查分别覆盖源服务/事件（`qmt-trade-source-service-review-003/`）及 Agent/控制/生成入口（`qmt-trade-source-agent-review-004/`），各自 complete、P1/P2=0；根线程逐项回核 23 与 35 项来源，共 39 项去重来源，漂移 0。审查者未执行测试，动态结果由本记录的运行收据单独证明。

汇总保存在 `qmt-trade-source-evidence-001/result.json` 及 `SOURCES.sha256.json`：共 61 项实际源码/工具/材料/收据摘要，输入漂移 0。期限、结果发布及最终确认竞争的中间发现均以对应回归和后继源码核实，旧绿灯不替代最终候选证据。此汇总不构成正式安装包；源来源清单与完整交易安装材料需在后续打包时统一更新。

当前自有 ManagedTrader 的标准 orderInsert/orderAction 仍拒绝，额外 SignedCommand、production_trusted 和四查询同水位证明尚待退出。独立源码调查保存在 `qmt-native-trader-seams-001/`。目标使用原生 `TraderAdapter → ITraderApi → SDK/SPI`；正常账户查询、身份映射、未知结果和防重继续保留。此处记录当前差额，不宣称已完成 C++ 写链。

尚未完成：正式 Host 交易派发与事件持久 ACK、标准 C++ TraderQMT/SPI、查询与回报交接、完整独立安装/发行、真实委托和撤单验收。旧 QMT 项目、正在运行的终端策略及生产配置保持，WT 框架本轮无新增修改。
