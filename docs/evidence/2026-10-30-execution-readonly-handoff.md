# 独立WT执行结果只读交接

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：开发验证与接口交接。状态：生产端主链已验证，消费端及完整模块pending-verification。对应[NRT-R20](../specs/native-realtime-strategy.md#nrt-r20-独立运行结果的只读定位交接)、[WRI](../specs/independent-wt-runtime.md)及[模块B](../migration/module-b-delivery.md)。本片新增WT框架行为及真实券商委托均为0。

## 实际结果与范围

`build/ms-execution-observation-001/main-005`从普通安装的`guanheng_wt_runtime`真实CLI启动，未安装观衡、FastAPI、Starlette或Uvicorn。唯一正式1.1.2策略沿原Factory、CTA调度、NSQ、股票执行单元、TraderAdapter和WinSHM运输，向SDK替身卖出510050.SH的200份；后继调度收敛，来源剩余510300.SH的200份。实际13次查询、1次替身委托，真实券商调用0。

WRI公开status携带原execution的`business_observation`，原ready、v2结果和reference的control_id/CTA配置SHA/实际策略PID一致。只读校验取得P revision2、资金revision1、可用资金82000元及剩余持仓/可卖各200份；读取前后SDK调用均为1。P与资金各自的原接收时间和结果发布时间保持。此结果证明B生产端交接，观衡HTTP/页面消费由C完成并另验。

本次正常停止成功：WRI的closed记录`components_closed=true`，执行父监督者发布closed.v2（exit_code=0、resources_closed=true、recovery_ready=true）及同代clean.v2。物理外层收据分别核Job树0、进程reap、reader join、EOF和句柄关闭。`POSTFLIGHT.json`的Host、源、HTTP与代理关闭均为true。该单次结果没有覆盖正常两代及原股票组件的稳定退出资格。

## 固定输入与身份

全部路径相对仓库根，所有新增文件、TEMP/TMP及安装缓存位于E盘独占根。

| 原件 | 身份及用途 |
|---|---|
| `build/ms-execution-observation-001/INSTALLATION-001.json` | SHA `6ac7506a4f3a411f0dc118e088aa03d5c087da60f9b7cbe6141eadc37a95915c`；六发行、720带摘要RECORD核验，uv离线copy安装 |
| 同根`source/`与`wheels/` | 冻结完整独立运行源码及六wheel；执行requirements逐一锁版本，不以基础两包安装代替执行闭包 |
| `build/ms-retained-runtime-001/native-005/BUILD.json` | SHA `0a37f6f9e9fcd60aa42b9733d2f187906901a733e33d5773ce632d1273c77e7d`；本片复用原native005，WtExeFact仍为原工厂 |
| 同根`installation/app/GuanhengCtaRuntime.dll` | SHA `ec7e363283bce510735bebe3bb2d245cb31b4e5a03fef8273f2da00db1f8de38` |
| `build/ms-execution-observation-001/MAIN-INPUTS-005.json` | 实际安装、native BUILD及七项QA源码SHA；对应QA原字节保存在同根`qa-main-005/` |
| 同根`main-005/OBSERVATION-HANDOFF-001.json` | 实际CLI、WRI配置定位、原ready/reference/v2全值及读取前后SDK调用数 |
| 同根`main-005/RESULT.json`、`POSTFLIGHT.json` | 业务结果、源调用、退出及各资源事实；实际金融观察来自明确SDK替身 |
| 同根`MAIN-OUTER-CLOSE-005.json`及main内`.outer.json` | 两层native.run包装进程和整树回收；包装进程退出码不冒称各内部PID的独立OS退出码 |

main005最外层driver PID44948；WRI启动包装进程PID13052；WRI公开PID38376；实际策略子进程PID56244。外层包装分别exit0及Job树0，WRI自己发布成功closed，策略退出由其原父监督者确认并发布closed.v2。四种身份分别保存，不能把包装PID或退出码替换为策略PID的独立OS采样。

实际命令、预算与完整输出在同根`main-005.log`及`.tmp/ms-observation-main5.py`。目标入口为安装解释器`-I -B -m guanheng_wt_runtime`；WRI startup20/stop8秒，QA调用startup25/stop10秒，整次170秒原截止和175秒外层预算。查询排队5000ms、执行1000ms、代理/Trader HTTP8000ms均为显式隔离配置。

## 给C的准确输入

main005交接文件中的`runtime_observation_configuration`可直接对应C既有WRI只读配置模型：path为实际root的status.json，另含root control_id、instance_id、configuration_sha256。root的配置SHA与内层CTA的config_sha256分别核对。

消费链为：已有WRI只读读取器→`components.execution.business_observation`→原ready和strategies.json的共享快照读取→核reference/ready/v2三项身份→原strategies交既有project_strategy与账户DTO。v2固定顶层为schema、control_id、config_sha256、pid、strategies；旧v1投影器可在身份核验后只包装原strategies继续复用。消费者保持只读，沿原请求截止处理文件替换，不构造执行owner。

`broker_observation.positions_known/account_known`分别控制已知性，已知空集合表示空仓；P与A分别展示接收时刻和修订。`broker_position_qualified=false`属于交易资格，已有P/资金仍可展示。原投影尚未提供委托/成交明细，C应分别显示对应组不可用；已有账户数据持续可见。停止或故障后reference仍指向最后完整结果，运行状态与原数据时间同时展示。

完整六发行版本为runtime0.1.0a1、market-client0.15.0、strategy-core0.1.0a8、strategy-native0.1.0a1、strategy-v1 **0.1.0a6**及tzdata2026.3。C当前后继策略包须重新锁定组合并验收；相同开发版本号下的wheel以INSTALLATION所载SHA区分，不能只比版本号。

## 失败原件与剩余工作

main001是QA将Path传给要求str的RuntimeConfig入口，启动前失败；main002是QA把尚未发布的新券商P与理论收敛直接比较，断言失败，其执行正常关闭；main003等到后继P revision2后取得交接，随后股票关闭exit2。main004改为实际CLI后，QA普通read_bytes在Windows文件替换期间共享失败；QA统一复用SDK共享快照读取后main005通过。以上失败分别保留，不归为同一个WT问题。

后继main006尝试正常两代，首代已发布selling并调用一次替身委托，随后在等待后继P时实际运行包装exit2，未进入第二代。该次无源/proxy首错、无最终成功closed/clean，外层及源资源完整回收；根因缺少同次异常现场，保持unknown。QA新增后继行情序号推进以避免观察补发后第二代重播旧分钟，main006未走到该分支，尚未授予行为资格。

main007沿同一实际CLI再次执行并只附加本代策略PID32788，完成selling→converged及v2交接；关闭期间捕获c0000005、访问类型8，dump SHA `489c6638f1883eb4ee9a7f0502bb0629a232e2260279ec24219abc936b908dc9`。附加/分离/join成功，errors及controlled_schedule均为空。原`.tmp/ms-standalone-dump-read.py`对同次转储作静态读取，slot0候选仍为WtExeFact.dll+0x1baff；报告明确为stack_candidates_only。完整关闭失败、二代未运行，成功closed/clean均未发布，资源回收齐备。该次证据不反推main006根因；股票商品引用配对的独立诊断与[按配置分流的具体提案](../migration/native-stock-metadata-ownership-proposal.md)对应。

独立REVIEW-001及REVIEW-002分别审查生产接口和实际CLI增量，开放P1/P2为0。REVIEW-002 SHA `7429b88950dac1d73667f0e23a60db4485094495e999834004748f66c9b92b0d`；main005七项QA冻结原件与安装720记录相符。后继main006/007及其QA输入分别保留，尚未纳入main005已通过资格。

R20-C1生产端交接已验证；C2独立观衡消费、C3错误身份/替换与消费者启停仍待C接线。正常两代、完整真实新周期、全周期BT/RT、资金/T+1全矩阵、实际券商写验真及统一候选完整组合继续。股票组件具体修改仅形成按配置分流的提案，批准前相关框架源码只读。

## 本片开发交付

DELIVERY-001（外部历史/待归仓路径：`../../build/ms-execution-observation-001/DELIVERY-001.json`） SHA `29630a370db04d66a6555e2d05c4f7e3f9a5cfa726be3c60f31bbd1b7e0db91b`及PACKAGE-001（外部历史/待归仓路径：`../../build/ms-execution-observation-001/PACKAGE-001.json`）固定116成员ZIP，包含六wheel、原native005、源码/QA及实跑证据。ZIP SHA为`754195f8457079d13fc2ce053a84bc7cad04a9860e6e408ccdd15e1990cac1d9`，大小3225215字节。封装后独立审查逐项核115 payload的字节数/摘要及六wheel、原工厂身份，结果见提案审查附带包装核验（外部历史/待归仓路径：`../../build/ms-stock-reference-proposal-002/REVIEW-001.json`）。包内文档和提案为封装时快照，当前准确候选与模块状态沿仓库唯一正文；候选框架修改没有进入该ZIP。

本片`CHECKS-001.json`核普通安装720摘要记录及single-link、五个B模块当前/冻结/安装字节一致、QA语法及project文档导航；全部通过。该类静态检查与main005实际业务资格分别记录，归档搬迁后重新安装运行继续待验。
