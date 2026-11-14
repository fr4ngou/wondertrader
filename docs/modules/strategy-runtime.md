# 策略与组合运行

类型：模块说明。所有者角色：策略运行维护者。状态：框架运行源码已存在；策略及其部署资格分别登记。

## 职责与入口

负责策略上下文、数据窗口、调度时钟、内部状态和目标输出。主要源码为 [WtCore](../../src/WtCore/CMakeLists.txt)、[WtUftCore](../../src/WtUftCore/CMakeLists.txt)；原生启动入口为 [WtRunner](../../src/WtRunner/WtRunner.cpp)。

`CtaStraBaseCtx`、`SelStraBaseCtx`、`HftStraBaseCtx` 管理对应上下文；`WtEngine` 维护组合运行状态。以具体引擎及接口定义为准，运行类型分别声明调度和数据可见性。

## 策略编写入口

1. 按[WT 策略能力](wondertrader-strategy-capabilities.md)选择与调度及数据粒度匹配的原生策略接口。原生 CTA 的策略实现和工厂登记可参考 [DualThrust](../../src/WtCtaStraFact/WtStraDualThrust.cpp)及[策略工厂](../../src/WtCtaStraFact/WtCtaStraFact.cpp)。维护现有共振策略时，沿[保留版规格](../specs/retained-resonance.md)或[原版回测规格](../specs/original-native-backtest.md)定位对应版本的受管接缝。
2. 策略规则归策略自身，明确输入来源、知晓时刻、预热、缺数行为、信号到目标映射和策略状态。需要在线运行的策略复用同一套计算规则，在回测和实时上下文分别验证调度、撮合及恢复。
3. 按[验证规范](../development/verification.md#按影响选择验证)和[回测手册](../runbooks/native-backtest.md#研究回测与查看)验证。观衡登记和回测报告交付沿[开发流程](../development/workflow.md#策略开发与回测交付)，运行及执行资格沿本模块分别验证。

## 状态与边界

策略新增跨重启状态时，沿[策略持久化契约](../specs/wt-private-persistence.md#persist-03-策略如何保存自己的数据)声明字段、版本、初始化和升级。开发及迁移分别验证原 WT 加载和回测隔离。

策略理论持仓、组合目标、内部资金统计和外部实际持仓分别命名。运行状态保存与加载沿现有上下文实现；新增状态定义版本、重启恢复和兼容性。策略拥有自身信号与止损规则，系统公共层承担其声明的权限与风险边界。

相同策略在同一作用范围内具有明确的活动调度者。预热、补发、重放和恢复事件标识时钟及作用，防止历史输入误触发当前执行。目标到委托复用原生执行及已配置风险规则，策略预算通过显式配置输入；当前不增加逐单人工审批环节。

## 失败与验证

按[SDO](../specs/strategy-data-and-observability.md)输出逐角色输入覆盖、调度/计算及无交易原因。合法None与正常无信号分别解释；诊断复用实际依赖与数学，不修改信号、目标或执行行为。

### 实时诊断的只读公开链

V1纯核将统一诊断写入`core_result.diagnostics`，WT原执行发布者沿同一策略观察发布结果。观衡`strategy_runtime_projection.project_strategy`复用V1的`validate_diagnostics`及`contextualize_diagnostics`，只增加原NSQ已观察到的执行阶段；字段覆盖、角色依赖、信号和目标状态保持原结果。原`wt_business_observation.observe_strategy`和`observer_strategy_details.observe_details`共用这一投影，分别提供`strategy.diagnostics`及`calculation.diagnostics`，无第二套诊断或金融存储。

无实际计算及旧观察缺诊断字段均投影null；原等待状态与决策时间保持。诊断独立携带available/absent/unavailable状态及稳定原因，未计算和旧未记录分别为not_calculated/not_recorded；坏诊断为unavailable/invalid_diagnostics。后端复用V1准入，格式/版本/角色错误只清空诊断并记录单条脱敏告警，不影响已核资金、持仓和策略状态。

浏览器`strategyRuntimeApi`拥有有界线协议校验和诊断独立降级，策略详情复用并采用同一归一化结果；旧响应缺字段仍可读，非空诊断须匹配当前策略证券。直接读到的坏诊断只影响诊断值及其状态，核心保持；真正核心错误继续沿原读取失败/同查询成功保持规则。无附加持久存储，原账户事实与读取预算保持。该链只提供公开数据，不改变页面布局、运行包或信号数学。

浏览器的完整字段/分支及角色映射来自[生成元数据](../../apps/guanheng/console/src/workspace/strategyDiagnosticWire.generated.ts)，由[生成工具](../../scripts/generate-strategy-diagnostic-wire.py)直接读取V1现有协议声明并绑定两份所有者源码摘要；更新后运行生成器与`--check`，不复制信号数学或另定证券范围。覆盖日期受所属范围约束，角色计算日期受实际评估范围约束。显式absent原因按原decision_at核实：无计算为not_calculated、已有计算旧未记录为not_recorded；矛盾只降级附加字段。详情共用相同校验及归一化。

回归入口为[实时投影与原HTTP链](../../tests/integration/strategy_diagnostics/test_runtime_projection.py)及[浏览器消费者与失败保持](../../apps/guanheng/console/src/workspace/StrategyRuntimeSummary.test.tsx)。隔离冻结行情的模型重放、已安装发布合同的路由读取和浏览器消费者分别留证，现场自然调度资格单独核实。

覆盖冷启动、状态缺失/损坏、重复调度、跨日、数据不足、策略异常和资源超限。验证相同冻结输入下的信号与目标，分别记录模拟、隔离运行及实际运行证据。

实际委托交由[交易执行](execution.md)，模拟行为见[回测](backtest.md)，用户入口和策略配置见[业务集成](business-integration.md)。

## 受管 CTA 进程生命周期

`WtRunner` 的 `env.managed_stop` 默认关闭。启用时要求 CTA、内嵌 parser 配置、空 traders/executers、未启用独立 risk monitor 和 notifier，并在创建插件前验证停止及删除导出。相应接口与资格见[NCS](../specs/native-cta-shutdown.md)。配置一次、运行一次；同步run等待普通退出信号，异步run由控制线程轮询stop_requested()并负责stop，后台任务失败也通过该入口触发停止。

策略回调仅调用宿主 `request_stop()`，控制线程负责等待。停止顺序为请求ticker结束、确认parser排空、ticker join、pool wait、base任务排空、reader停止，随后策略、上下文、缓存和插件实例依次释放。控制线程等待时保留全部依赖；插件未确认停止会报告具体阶段并继续等待。正常退出与整体严格截止分别声明，长时间不返回的策略回调会延长等待。

任务准入与关闭由同一队列锁保护；任务在锁外执行。已接纳任务正常排空，首次异常保留未知副作用和未执行数量并返回失败状态，不自动重放。策略析构可释放其持有的上下文相关资源，此时业务准入已关闭，应避免发起新业务。DLL保留到进程生命周期末端，外部保留的结果对象可以完成最后release；动态卸载另有资格要求。

## 原生实时策略桥接

[RealtimeBridge](../../src/GuanhengRealtime/RealtimeBridge.h)以C ABI承载原CtaStrategy/Runner回调及独立值复制。控制线程拥有configure/run/最终stop；回调期间以owner token、线程与epoch限定facts/bars/position/target借用，跨线程及过期调用拒绝。回调仅发布停止请求，控制线程完成原生停止。调用方保持CFUNCTYPE/user/DLL存活至真实回收，跨ABI异常由本层失败路径收敛。

实时[组合Reader](../../src/ReaderGuanhengRealtime/Factory.cpp)衔接已配置分钟源与原生历史日线。分钟调度继续由原ticker负责，策略核只消费在回调原时刻可见的独立输入。已安装唯一策略核与回测复用；真实源覆盖、actual/pending/T+1事实、目标setter执行和正式生产宿主分别验收，接口存在与资格完成分别记录。依据[实时策略规格](../specs/native-realtime-strategy.md)，限定实际运行见[证据](../evidence/2026-10-25-native-realtime-build.md)。

正式受管Python入口的configured与V2固定profile共用原Session、策略上下文、NSQ及用户变量恢复；V2直接调用原V2Binding，固定窗口及超配规则按[NRT-R13](../specs/native-realtime-strategy.md#nrt-r13-固定v2同核实时接线)。自有观察文件是可重建投影，发布失败沿health停止并拒clean，持仓和资金持续归WT。当前同核BT/RT、两代恢复及安装资格见[V2证据](../evidence/2026-10-29-v2-native-bridge.md)。

[NRT-R15当前完整App组合](../evidence/2026-10-29-current-app-native-composition.md)将Appa19/core a7/signals a5/V2 a4及35依赖普通安装，configured/V2原生主链、两代恢复、同安装BT/RT和离线搬迁已验。严格实时构造器在原生装载前拒绝非空historical_model，研究回放继续沿HEM owner。V2包资源仅在隔离候选更新，根App公共资源由C集成；其他算法原生资格和全真实输入继续独立验收。

同一Session已按[NRT-R14](../specs/native-realtime-strategy.md#nrt-r14-安装行情插件与原生分钟的正式宿主组合)组合安装ParserQMTHostV6与显式minute_native Reader。实际活动分钟只读、原自然调度、configured双策略净额及完整关闭已验；[组合证据](../evidence/2026-10-29-native-market-cta-composition.md)逐项标记实际分钟与合成日线/报价/券商，完整真实来源和统一App安装继续后继验收。
