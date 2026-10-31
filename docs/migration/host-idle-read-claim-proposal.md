# Host空闲通信轮的读领取推进

类型：模块B提交A的自有通信层候选方案。状态：proposed / isolated-validation。关联[B完整目标](parallel-system-delivery.md)、[THP职责](../specs/qmt-trade-host-product.md)及[原同请求测量](../evidence/2026-10-31-sri006-execution-failure.md)。生产源码、安装和发行由A单一owner处理；本候选在build副本验证。WT账本、策略、执行器与核心源码保持原职责。

## 目标与根因假设

在原SDK工作量、Source100毫秒回调、持久派发/确认和原截止内完成完整调仓。full019普通无诊断候选实际41笔SDK、39100/50400份，原70秒目标仍失败；输入一致、正常关闭与完整回收已取得。full018同请求测量的Host受理后领取等待中位52.207毫秒、领取后派发58.537毫秒，为下一责任层的直接依据。

Host先发起异步read.claim，随即准备并发送本轮原帧。若claim尚未完成且本轮没有其它通信责任，空帧可能占用一次Source回调，读请求等待下一轮。此前stage005无条件等待claim会拖住已就绪的trade/event/ACK，已退出。stage006发送ACK后提前准入的有限行为已验，完整业务收益仍未证。

本候选假设：仅在peer完全空闲时等待原claim，并在等待中继续原准入，可将已持久领取的读放进本轮；已有或新就绪的通信责任应立即进入发送路径。这个假设由真实peer、原域任务和完整主链验证，不预先授予性能结论。

## 所有者与接口

| 事实或行为 | 唯一所有者与接缝 |
|---|---|
| CALL/REPLY/ACK、原D、信用和阶段 | 原ControlPeer；新增只读`is_idle()`，不改变选择、过期、序号、退休或额度 |
| read.claim及结果持久保存 | 原HostDomainWorker与Journal；任务、原future及原请求身份保持 |
| 本轮准备/发送 | 原HostControlLoop；新增私有`_prepare_send()`，返回原batch和本次发送绝对D |
| trade/bulk/关闭推进 | 原子类`_admit()`及runtime.shutdown_started；等待期间继续调用原准入，停止依旧由原owner处理 |
| SDK、持仓、成交与绩效 | 原Source单线程SDK、WT账本/执行器与策略核；本候选不保存金融事实 |

`ControlPeer.is_idle()`在原短锁内检查：当前处于send阶段、没有已准备batch、`_out`与`_incoming`均为空。任一保留调用（包括已发送待回复、已回复待确认）、回复、ACK或未完成阶段都会返回false。已关闭沿原_open错误。查询不调用expire，不释放或借用信用，不生成准备收据，也不复制消息选择器。

`HostControlLoop._prepare_send()`只在read.scan存在、peer空闲且runtime尚未shutdown时进入等待。进入时冻结本次I/O绝对D；等待上限为该D之前保留原io_seconds一半的时点，轮询仍按原poll_seconds分片。每次clear后先重查stop/shutdown，再调用原_admit消费已完成域任务；scan结束、peer出现任何责任、shutdown或上限到达立即结束等待。物理stop返回空值使原run退出。准备后发送继续使用同一冻结D；未进入等待的路径沿原准备后建立发送D。所有默认参数、请求D、Source回调周期与SDK准入保持。

新增方法属于自有Python通信包，不改变WT公开接口、ABI、金融状态格式或原恢复协议。原生能力沿[WT-T01/T02及WT-S01/S05](../development/wondertrader-capabilities.md)复用；本次缺口位于Host/Source运输推进，WT无需承担新的调度职责。

## 实施与验证标准

1. 冻结最终DIO.2的Host/Agent原文件，在build形成Source两份既有修正、只读peer接口和Host准备方法的精确差异；共享live保持。
2. HIR-R1：真实ControlPeer证明空闲查询的阶段/已关闭语义，以及保留CALL、回复、ACK和准备帧均阻止等待；信用、D和身份不因查询改变。
3. HIR-R2：真实Host方法以同一原future覆盖claim在检查间完成、完成后同轮派发、无结果到上限、原域失败、clear间stop和shutdown；等待与发送共享单一D。
4. HIR-R3：原stage005对照在已有短D调用/ACK或等待中新就绪通信时应复现阻塞；新候选立即发送，原命令、确认与先行D保持。收到shutdown后退出新增等待。
5. HIR-R4：复用实际HostTrading/SQLite/SourceTradingService向量，通过原`_prepare_send()`运行交易、部分/拒绝/未知、事件确认和停止；补默认read/bulk适用调用链。独立审查核最终源码身份及异常责任。
6. HIR-R5：先在独立普通候选运行原完整70秒/三轮/同根恢复及清理；若仍失败，按同请求阶段解释后继续修责任层。A接受后重建匹配发行，B消费最终普通安装与搬迁；当前不授真实交易或发布。

方案只选择空闲通信轮。已有责任的推进顺序仍归原peer选择器；共享准入/关闭错误沿原runtime交接。候选失败保留原件并回到冻结制品，不改变未决命令身份或重建金融目录。
