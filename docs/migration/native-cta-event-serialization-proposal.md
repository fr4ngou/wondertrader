# 受管CTA行情与调度串行接缝提案

类型：已撤回的核心行为扩展提案。状态：superseded。用户本轮明确要求继续使用WT原有行情与CTA调度方式，撤回本串行方案；相关核心改动未实施。关联：模块B/B-07、NRT-R9/R10及[配置分流规则](../development/upstream.md#框架行为的配置分流)。

## 当前决定

行情更新及原生理论信号推进继续沿原WT机制。实验只证明人为交错下同一回调的前后观察可以变化，尚未证明正式业务算法因此产生错误目标或委托。持仓归属、字段语义及真实执行结果分别验证；不把回调期间所有行情冻结、跨字段事务快照或managed_serial_events作为运行准入条件。模块B继续复用原生账本和绩效。

下文保留此前设计及实验出处，属于已撤回资料，配置、实施范围和验收矩阵均不再作为当前实施要求。

## 历史提案的目标与实验

为受管CTA的同一次策略计算提供稳定的原生理论仓位、可卖、pending与收益观察，继续使用原上下文和组合账本。原默认行为保持。

固定已批准核心及实际安装DLL的`build/ms-python-003/public-race-005`已复现：A的同一原SCHEDULE回调、同一epoch7内，先set目标600，读取raw_position=600/raw_valid=600/entry=0；另一个来源线程的下一笔quote完整进入并返回后，再读为raw_position=600/raw_valid=0/entry=202610291001。合约trademode=2是原TM_LongT1。该变化来自原理论信号触发，不是券商成交回报；SDK替身整链仍单笔买1000，A/B原状态600/400，关闭完整。原件为callback-position-race.json、callback-position-observed.json和POSTFLIGHT.json。

源码触发链为Parser SPI→WtCtaRtTicker::on_tick→trigger_price→原CtaStraBaseCtx::on_tick；timer线程持_mtx执行Reader分钟闭合和engine.on_schedule。现on_tick只有自身触发分钟切换的局部段获取_mtx，普通同分钟/迟到tick可在timer的策略回调和汇总期间更新原上下文。poolsize=0约束策略任务池，并未为来源线程和timer建立完整互斥。epoch约束调用线程和借用期，不能单独授予多次读取的一致快照。

## 原生接缝及替代方案

原ticker已有_mtx并且分钟调度尾部继续执行原目标汇总、组合记录和执行器提交。需要把可选串行范围放在这一原事件所有者中。

仅在Python回调周围加锁无法约束已经进入原上下文的quote，也不能覆盖回调返回后的原持仓枚举/组合尾部。读取前后比较、重试或复制策略JSON都缺少可靠的原内存快照证明；维护另一个实际量/现金账本会重复原生职责。这些方式不进入实施。

## 最小拟议范围与配置

| 文件 | 拟议变化 |
|---|---|
| src/WtCore/WtCtaTicker.h | init增加缺省false的串行选择，记录本实例初始化后固定的模式；保留原_mtx作为唯一事件门 |
| src/WtCore/WtCtaTicker.cpp | 显式串行模式下，整个quote处理与timer的状态读取、分钟闭合、全部策略回调及汇总尾部共用_mtx；原有局部锁收敛到同一取得逻辑，避免嵌套锁死；等待/唤醒及join在事件门外进行 |
| src/WtCore/WtCtaEngine.cpp | 从原env读取显式managed_serial_events并在原ticker init传入；缺省false保持原生选择 |

配置位于env.managed_serial_events，作用于单个CTA实例，在初始化时固定。键缺省或显式false选择原生路径；显式true选择串行路径，并要求poolsize=0。自有Session在进入原代码、创建线程前按JSON原类型校验；null、数值、字符串、数组和对象均为非法值，显式null保持非法，读取时保留字段存在性。新受管数量观察profile仅以显式true且poolsize=0准入。模式变更通过停止和重启生效。普通native和现有冻结组件保持原路径。本次不改策略记账、价格/费用、撮合、订单、ITraderApi、持久格式或恢复判断。

配置验收分别覆盖以下输入，每项记录实际选择及启动副作用：

| 输入 | 预期结果 |
|---|---|
| 字段缺省 | 普通CTA选择原生路径，与固定上游行为比较 |
| 显式false | 普通CTA选择原生路径，与缺省行为一致 |
| 显式true且poolsize=0 | 选择串行路径，执行完整策略/汇总/执行器调用链 |
| null、0、1、字符串、数组、对象 | 启动准入拒绝，核心入口与线程创建均为0 |
| 显式true且poolsize>0 | 依赖条件不满足，启动准入拒绝，核心入口与线程创建均为0 |
| 新受管数量观察profile使用缺省或false | 缺少稳定观察所需模式，启动准入拒绝 |

任何来源线程的quote可在一次完整分钟事务之前或之后执行，不能插入受管策略计算和本批原汇总中。原Parser/Reader仍承担来源和数据能力；串行模式不授跨原生日志、异步任务、账户查询或多个进程的全局事务。控制线程继续原request_stop、外层Job及关闭总截止。

## 风险与验证标准

长回调会对quote形成背压；沿原有限计算预算和外层Job截止，阻塞/未知关闭标incomplete。不得在持事件门时等待可反向进入该门的生产者、stop或join。所有内部C++消费者按同一头/库身份重编，禁止热替换。

1. 同一原触发条件在默认模式继续观察到回调中quote返回；显式模式中回调未退出时quote保持在途，整个schedule尾部结束后才返回并触发理论明细。
2. 以原回调观察flat、pending echo、actual+pending、T+1冻结/次日释放、平仓和已存在0条目的差异；核原CSV/JSON及组合目标，不新增实际量账本。再准入NSQ原阶段推进及原PnL派生NAV/现金模型。
3. 实际configured核/NSQ双策略整链、默认五组合及原NRT分别回归；持续多轮、分钟切换/迟到quote、回调请求停止、quote等待时停止、Parser/Reader pending及父死亡分别核原总期限与资源关闭。
4. 来源字段及三层绩效按原接口核对；真实费用、券商资金和交易日资格仍分别验收。源时延及完整性不会由本串行模式授予。

实施前独立审查方案及固定原源码；实施后独立full/delta、输入SHA、安装搬迁及失败回收留证。回退使用现有冻结DLL及缺省false模式，原状态/命令身份保留，不删除状态、不换空根重发。该批准范围仅为上述三份核心文件及相应自有配置/测试；真实下撤单和生产切换沿另外明确授权。
