# 策略运行结果与真实前复权历史消费

类型：模块C开发验证。状态：限定切片双轴修正复审、实际用户链及开发交付完成；完整模块继续。规格：[EAM-R6](../specs/execution-app-management.md#eam-r6-策略业务结果只读消费)、[RR112](../specs/retained-resonance.md)、[HPRA](../specs/qmt-history-preparation-app.md)。完整模块保持active，A唯一集成。

## 根因与实现

App原接口仅有执行进程生命周期，B固定Python桥已经原子发布策略结果；当前总览尚未消费该结果。C新增ObservedPythonExecutionProcess只读子类和strategy-runtime路由，沿原受控目录/ready收据/owner身份/有界读池读取4MiB策略发布，前后续核进程状态。B运行桥、原生文件、算法和金融状态保持原owner。公开投影只含固定名称/版本、中文状态、原决策/券商接收时间、完整八目标比例、理论数量/可卖/未决目标、阶段目标及宿主券商查询数量。总览以紧凑表格显示有持仓或目标的证券，失败保留原值/时间、成功空清除。策略目录保持名称/简介/版本。通用进程卡移除pid/强制回收/资源条目，总览补齐状态收敛为状态/原时间/重读。

A真实历史成交量单位为lot；原回放误将读取准入固定为share。RetainedReplayInput接缝接受来源已声明share或lot，历史bar和分析量原值保持，交易数量仍为share及100份整手。价格CNY/share与金额unknown、唯一核和原数量模型保持；没有换算原历史或修改WT。

## 已核主路径

外部原件根`C:/Users/frangou/.codex/visualizations/2026/10/28/01a1827c-4d9e-7d23-b0c3-a7ddb931c0d3/strategy-runtime-view-001`。Appa26/runtime-006为普通新venv、24公有+5私有发行，完整4731条hashed RECORD、wheel payload与自身site逐项核实，pip check通过；原A SDK0.15/corea8/V1a6/nativea1保持。当前root uv.lock归A，默认locked构建资格另验。

B值来源为`build/ms-retained-cta-001/values-001/FIRST.json`，仅为B自有桥显式Context替身的冻结结果，C fixture逐字复制。实际安装App→原C观察方法/读池/HTTP→生产SPA的ui-004通过1440×1000与390×844、LA时区、目标0/理论200/券商700可卖300口径区分，真实文件损坏503保留、空发布清除、原文件恢复、内部字段不入DOM及关闭。此链显式替代生命周期，无B原生执行Job，不授实时执行或真实账户资格。Browser plugin not available，使用已有Playwright/Edge；console仅一次主动503，warning0；HTTP线程、读池和App均关闭。

142后端回归（执行App/唯一策略）和62前端回归通过，覆盖ready错pid、原截止、停止竞争、坏字段/读回冲突、未知与完整空券商、缓存恢复及紧凑总览。保留anyio已导入rewrite和Starlette/httpx三条QA警告；Vite未来原生configLoader警告独立于应用运行。

## A真实分析窗口主链

消费A `build/qmt-native-adjustment-module-001/main004/ANALYSIS-WINDOW.json`，SHA `5158a15ae9b7ccb5c85cbaef1dcadfdff89c7d1b977ab6c483d109acc144908a`。八证券401共同日期/3208 raw及3208分析行、2025-03-05至2026-10-28。原source/factor revision和实际2026-10-29接收时点保持；辅助事实缺失、历史首次可知与修订unknown。声明最终批次/上海15:00历史模型，使用实际正式六参数及预算来源SHA120e9bf8…a7，明确模拟本金120000和费用reserve20，原生flat开始；不解释为真实券商资金或当前持仓接管。

`build/retained-real-analysis-002/main-001`普通Appa26安装→正式StrategyHost/runner→原WtBtPorter已完成400条日末：98预热、77初始化、10买入、16卖出、199收敛。原Host elapsed137577ms、exit0、nonforced、pid_reaped/pipes_joined=true，12原生输出身份已核；真实订单/来源业务请求0。价格/前复权/历史来自A真实冻结数据，撮合及资金沿显式历史模拟。实际HTTP启动/报告/生产SPA、同核RT/实际周期/隔离委托撤单及完整M1继续。

## 尝试与剩余

早期QA源包导入次序、C盘临时根不满足原E盘部署约束、缺少pytest父目录、重复文本定位、默认3.14缺离线wheel及脚本沿旧编号替换路径均保留失败原件；后继使用精确路径、3.12原安装解释器和新独占根。真实输入001在预检成功后误将A日期计数当列表，未启动回测；002保留A原计数并独立成功。失败均沿原native Job关闭，关闭状态/errors/owner分别保留，不修改产品准入绕过。

当前尚未生产部署、真实下撤单、QMT界面或新增WT行为。模块剩余为A/B正式RT/实际周期/隔离交易整链、统一安装与升级回退和完整操作材料；本切片独立审查和精确交付继续。

## 最终A数据、实际HTTP及共享缓存修正

A最终交付为main006/ANALYSIS-WINDOW.json，SHA `a38386d74bda91da91cc9669ffde734cb69ba50f4d06427fe27038e0ff857859`。与main004相比raw/分析bar/单位/两revision/范围逐值相同，仅实际known_at/received_at及输入摘要更新。使用最终资料的新SESSION位于`build/retained-real-analysis-003`。real-ui-002由当前生产SPA实际点击HTTP启动，正式原DLL400条完成、八页日末及末日详情已打开；后续QA错误读取顶层日期（实际record.trading_date）中止，原归档和正常关闭保留。real-read-003复用该完成档，两代新App真实HTTP/生产SPA读回400绩效、原费用、末日及390px页面，零新增回测；页面无内部标识、无溢出，console/warning为0。原件路径同外部根。

001双轴full独立核出共享HPR状态组件刷新中/失败提前return的问题，影响系统状态页；同根旧Operations数据选择也按相同根因修正。各原React Query成功data保持渲染及原observed_at，局部错误分开解释，成功状态按当前返回更新。63前端及TypeScript通过；spa-005/ui-005已沿真实安装HTTP逐一验证HPR/来源/执行/系统状态四路503保留及恢复，与策略结果损坏503合计五条主动资源错误，warning0，所有App/HTTP线程/读池关闭。

安装006与001冻结共享树存在一项B-owned差额：execution_configured.py在wheel及实装中为`dddcdbe026903b4e1b48562d07521bcd11310bfe1942864100eae297b860ac90`，B持续开发后的源码为`ccd20b2188e9cecabba46bf721cd31d32dff34e7f1f40bda07eaa20bbfed103a`。差额只在RetainedStrategy新增现金执行配置准入，C消费的_restore_quantity_state已由作者及独审分别确认AST相同。C保持B最新源码，安装候选按自身B字节绑定；最新B实时组合仍待其最终交付后重新集成。002审查镜像会显式采用安装候选B依赖，并分别记录共享树后继，避免将全部工作树当作当前安装。

最终spa-005的real-read-004再次沿同一完成档通过两代HTTP/页面，未新增回测。11次失败QA均已按原关闭收据核九项boolean全true、errors为空、无保留owner；汇总FAILED-QA-CLOSURES.json。独立001规格full为gap/共享HPR一项P2，修正后的002 delta继续；001原报告保持。

## 最终限定交付

双轴002复审均complete，原共享HPR/系统状态缓存P2关闭；001 gap和全部失败原件保留。120份审查源码、158份原件由REVIEW-INPUTS-002锁定，新增开发包/搬迁属于单列补件。开发ZIP SHA `921c7f019a8f8b17774c9bcfc829eb5600924d833b3ba790e795abced232debc`，28成员；新根安装29发行4726 hashed RECORD/139私wheel成员与自身site通过。主安装4731与搬迁4726的计数差为五个direct_url附加记录，启动器及uv_cache位置相关字节分别保留；产品wheel payload相同。最终DELIVERY与续接位于build/strategy-runtime-view-001，原件在外部strategy-runtime-view-001根。

A已将apps/guanheng/uv.lock更新至Appa26/五本地发行并完成offline check，依据[依赖锁证据](2026-10-29-latest-dependency-lock.md)；该资格与本轮独立pin安装分别保留，完整统一安装/升级回退仍待A组合。当前B最新运行源继续由B交付，不以C候选旧B字节授其实时资格。整个模块goal active，下一步将最终B原生同核/实际周期和隔离订单撤单接入同一真实A资料与页面。
