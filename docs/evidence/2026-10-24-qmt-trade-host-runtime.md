# QMT共享内存Host组合交易验证

类型：开发验证记录。日期：2026-10-24。状态：Host开发切片通过，完整交易接入pending-verification。要求见[QST-R17至R20](../specs/qmt-shm-trading.md)，源码入口见[模块说明](../modules/qmt-shm-connector.md)。整体迁入目标active。

## 实现与事实归属

新增显式HostTradingRuntime及组合控制，沿原读Runtime/ControlLoop复用一个Session、I/O循环、绑定锁和有界域worker。v4/control2绑定由可信配置选择版本，原1.0默认保持。build_trade_runtime在完整配置、policy与凭证快照校验后取得唯一HostTradingJournal；旧只读工厂和CLI维持其版本边界。

原回报字节、持久前沿和源ACK意图放入同一个通信文件，不增加资金、持仓、订单业务账本。SDK原结果提交后才RPC ACK；事件页提交后再业务ACK，并持久其原确认。unknown阻止新命令派发，已有查询和回报交接继续。HTTP入池前固定I/O截止，原业务截止沿共享启动时钟传入Journal，等待锁/SQL/域队列不刷新。

本轮修正四类根因：最大RPC寿命转为datetime时向上舍入；较早空页跨后续SDK事实被复用为关闭依据；HTTP取到unknown后发布锁及编码丢失原I/O截止；源结果已发布但原tick尚未finally时，completed/executing合法重叠被Host误拒绝。对应验证分别固定UTC精度、旧页/SDK交错、真实锁等待/晚编码以及真实源发布后阻塞窗口。SDK生命周期保持原设计，计数校验按实际语义收敛。

## 实际验证

最终输入及原件索引位于`build/guanheng-workspace/qmt-trade-host-runtime-002/`。最终组合回归由该目录run-regression.py执行，覆盖交易目录及原control、bound Journal、账户配置/配对、历史纯链等受影响测试。

| 验证 | 结果 | 原件 |
|---|---|---|
| 最终受影响完整回归 | 466 passed，14.95s | `account-runtime-install-001/build-qmt-trade-host-regression-002/driver.log` |
| 真TCP/HMAC→Host→Win32 builtin-shm→原线程替身 | passed，包含于466；insert/cancel各1次、重复提交无额外调用 | `test_host_trade_transport.py`及同次日志 |
| 原回报保存/源确认 | 3条原事件连续保存并被源ACK，HTTP按原来源读回 | 同次运输场景断言 |
| 资金、持仓、委托、成交、快照查询 | 5次源查询均在构造策略线程；资产1行、其余账户三类空批及合成行情 | 同次运输场景断言 |
| 隐藏执行与资源回收 | passed；退出0、无强制终止、tree0/EOF/reader join/resources closed | `account-runtime-install-001/build-qmt-trade-host-regression-002/result.json` |

表中运行原件均相对`build/guanheng-workspace/`。原SDK全部为明确替身，实际券商SDK调用0；真实运输场景采用随机命名内存、隔离loopback端口及临时通信文件，未连接正在运行的QMT。源运行于开发解释器；此前目标3.6.8与禁文件完整策略验证保持[源端原证据](2026-10-24-qmt-trade-source-runtime.md)的精确范围，本轮不替它授新安装资格。

首次组合测试、真实运输夹具两次失败及中间回归全部保留。账户空批不满足原账户单行契约、快照夹具symbols不满足既有stocks参数，均修正新测试输入；未为夹具修改旧接口。最终运输测试用ExitStack在临时目录清理前登记并收口每个已构造owner，业务异常和关闭异常分别保留。

## 独立审查与剩余范围

运行器/HTTP/工厂主审原件为`qmt-trade-host-runtime-review-001/`；首报F1原HTTP截止P2及运输测试T1生命周期P2按后继delta逐项复核，最终DELTA-004静态关闭T1并确认无新增P1/P2。通信存储/DTO/状态与可信版本接缝的本轮增量独审原件为`qmt-trade-host-journal-review-001/`及`002/`，源计数HJ-F1在002复核关闭，无新增P1/P2。旧主体只作上下文，不将审查者历史作者关联记为全主体独立full。静态审查者执行0，动态结果由根线程实际运行证明。

根线程逐项回核最终两份来源清单15与34项，共40项去重来源；49次摘要核对全部匹配，漂移0，原件为同次`REVIEW-ROOT-CHECK.json`。中间候选的输入漂移按各自原报告保留，不把最终零漂移回写为整个开发过程零漂移。完整源码快照、原运行收据与汇总保存于最终输入索引；该目录不构成正式安装包。

当前没有需要用户先解决的新阻塞。下一段完成标准C++ TraderQMT的orderInsert/orderAction及SPI，退出自有逐单签名、production_trusted与四查询同水位前置；自动命令身份与WT标准EntrustID/OrderID/userTag继续保留。WT应用确认、重启后原委托关联查询、完整独立配对安装、实时CTA/保留业务完整入口及发行仍未完成。

本轮未改WonderTrader核心、旧QMT工程、运行终端或生产配置；未执行真实下单撤单。记录中的通过属于开发链，完整迁入及生产交付继续验收。
