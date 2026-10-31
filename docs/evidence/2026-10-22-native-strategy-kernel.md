# 策略业务核与原生接缝开发验证

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：开发验证与能力取证。状态：完整configured 1.2.0纯核已迁入候选；独立审查仍有待修正项，原生同核接线、用户入口和生产未完成。要求见[NSK](../specs/native-strategy-kernel.md)与[NSQ](../specs/native-strategy-quantity.md)。全部开发、解释器环境、测试和制品在本仓库；旧QMT只作静态来源参考。

## 当前实际结果

纯包位于`apps/guanheng/strategy_core`，保留八角色特征、连续EMA、完整信号记忆、退出规则、分配、signal/execution映射及当前全量零/非零目标；完整前缀、配置、因果数据和知晓截止形成确定性身份。它不持有柜台账户、订单、旧通用worker或行情数据库。首次包与后继包原件分别保存在`build/guanheng-workspace/strategy-core-001/`及各round，尚未授最终候选资格。

| 范围 | 已发生验证 | 当前限制 |
|---|---|---|
| 普通算法与记忆 | 首次80项；独立320组信号、320组状态/恢复及36组完整公开结果对照通过 | 首核仅configured 1.2.0；其余策略/版本仍在最终范围 |
| a2根因回归 | 隔离安装143项、Ruff、原反例重放及32768行容量通过 | 开发者结果不能替代独立审查；下列F2/F3保持开放 |
| 全部文本预算 | 独立8Mi字符ASCII/非BMP及32768行通过，超限在计算/编码前拒绝 | 非BMP场景峰值工作集约204MiB，按实测输入登记 |
| 原生ABI | 固定头MSVC实际探针：Bar88/align8、CtxHandler4、指针8、bool1；RT6/BT7回调参数分别绑定 | 本次Windows x64，其他平台另验 |
| 固定原BT构建 | 原WtBtPorter target 173/173通过，108导出 | RT DLL编译/链接通过，原target停于默认ParserUDP部署复制，不能标成完整RT构建通过 |

首次full为gap；a2的独立delta（外部历史/待归仓路径：`../../build/guanheng-workspace/reviews/strategy-core-delta-001.md`）已冻结：F1来源元数据可变性及100MB文本绕过关闭；F2混合有限int/float求和裸溢出、正数极小均值下溢错误灰灯仍开放；F3标准时区时间转换到UTC超出表示范围时哈希裸异常为新增发现。报告SHA-256 `cbc44fd69c3176abd86ce5db45ea1a3345f4014e861a4f83538738a809ee3039`，输入39项前后零漂移。a3在原owner修正与回归，原a1/a2轮子及审查资料保留。

## 原生同步回调与生命周期

001实际探针（外部历史/待归仓路径：`../../build/guanheng-workspace/strategy-native-probe-001/REPORT.md`）用固定原WtBtPorter与合成m1完成7次bar/7次calculate，预热2、后继完整闭合前缀3→9，未来一条未见；feed返回后覆盖调用者数组，原生后继字段仍相等。callback借用块在回调内复制；on_bar只复制，get_bars放在calculate，避免清除closed标志影响调度。hook=false实际calc_done=0，完成由calculate出口和run返回登记。

父端CREATE_SUSPENDED后先归入KILL_ON_JOB_CLOSE Job再恢复线程。正常退出、父绝对截止，以及DLL加载前和原生init后两阶段父死亡均已通过实际子进程句柄验证回收。强制回收可出现exit0，完成判定同时使用forced/incomplete和结果身份。实验异常清理仍有备用3秒等待未覆盖，不授完整产品单截止资格；产品并发、多块、RT、异步及通道排空待验。

## 日线、ETF理论数量及资金的真实能力

002实际探针（外部历史/待归仓路径：`../../build/guanheng-workspace/strategy-native-probe-002/REPORT.md`）五场景各14次双ETF bar、7次calculate，两个证券预热2、完整前缀3→9，未来日期未见。全部completion完整、forced=false、进程wait回收，耗时291–367ms。9份关键原生源码与固定Git `08b230dd05facf6d650d949bfe51054115a2ecb1`逐字节相等，DLL SHA-256为`4726fdb9c48d32ec46fe0793eabb23d120aec8a536dc8dc140b57b636b533b2e`；收尾回执SHA为`7918be64bf0a07d294fc895120435fd0858834490213f7b62cc06b9083718e1a`。

这些场景只设置合成引擎的0/100/200份理论目标，没有Trader、执行器或真实通道。固定输入与原trades/funds/closes逐笔核对得到：

- `get_all_position`优先显示pending目标。首次新证券的`get_position`也可能回显pending；已存在position记录时它显示实际理论量。first/last entry描述当前持仓明细，首次pending为0，实际入场后非0，全部平仓后归0。
- T+1场景实际200、可卖100时，清零setter被拒，目标枚举保持200；次日可卖恢复后再次提交才接纳，后续bar才实际平完。void setter需要完整目标读回确认。
- actual100、pending200后再次set100会早退，pending200仍生效并在下个bar成交。公开接口的通用pending撤销能力在本场景有缺口，当前适配按NSQ明确隔离/阻断，不修改框架来绕过取证。
- fund flag0逐次等于已实现盈亏加浮盈亏减费用，不含初始本金。显式C0加flag0只授无现金流理论NAV，现金/购买力另有估值要求。T0最低费场景最终原生PnL90，T1场景PnL265，逐笔与每日原输出相符。
- 原fees已支持费率、按量及minfee；最低费作用于每条fill，200份平仓拆为两条100份时各收5。lotstick/minlots虽由资料装载，CTA setter/撮合未用其校验，整手约束在数量边界明确验证。

原生回放在下条日线模拟tick撮合，观测价格等于下一日open，原trades时间写该日15:00。该时间是模型口径，不能授真实柜台成交时刻。固定向量探针没有执行完整NSQ先卖后买算法，也没有调用本次configured纯核。

根任务另按收尾清单独立重算177份脚本/输入/输出/源码与DLL身份，逐个核五个实际completion、forced状态、进程回收和管道结束。直接从原CSV重新计算每场景trade费用总和、close已实现盈亏总和及最终`realized+dynamic-fees`，与funds全部一致；根回核记录（外部历史/待归仓路径：`../../build/guanheng-workspace/strategy-native-root-001/probe-002-verification.json`）保留实际值。此回核只授上述实验身份与算术范围。

## 后续接线与资格

经济代际沿稳定配置/policy及原allocation日期与完整权重向量，保留卖出完成后重新冻结买量、手续费跨整手残余卖出、T+1等待和整组现金资格；旧独立回测的每日重平衡退出新默认。纯转换模块和原生执行事实分别承担职责。

下一步关闭纯核F2/F3，完成NSQ与实际原生同核回放，再贯通独立HTTP/页面及来源明确的真实输入。已下载分钟样本的[真实来源链](2026-10-22-qmt-downloaded-cache.md)独立记录；本页合成实验不授ETF数据覆盖、真实账户/审批/委托、策略收益或生产资格，五策略与完整观衡范围保持。

## 后继：a4、纯数量与真实完整交易日

纯核a3关闭F1/F2a/F2b/F3后，独立delta-002另复现非零次正规均值舍入跨越量比阈值F2c；报告原件SHA为`1d20e96489d13c025c47a5b24147548b678b87035951b49bd46bb6a23965d97b`。a4以共享精度资格处理均值、比率、EMA、止损及分配，wheel SHA为`6bb9782301a865cec3b9be4f86743ea6269b4103a18d2cb82b877d1303fa052a`，开发隔离215项通过。a4独立delta进行中，已取得旧反例关闭及普通结果相符证据，同时实测发现长窗口精确路径的内部时间检查缺口：合法4096日/32768行、窗口256、默认5秒预算约25秒后才返回超时。该项保持开放，不能以宿主强制终止替代纯核预算修正。

NSQ独立full（外部历史/待归仓路径：`../../build/guanheng-workspace/reviews/strategy-quantities-full-001.md`）已冻结为complete，仅授纯数量模块资格，0开放发现。实际安装42项、1000组整数参考、100组Decimal陷阱环境及完整阶段/JSON恢复通过，20项输入无漂移；报告SHA为`9885d9e76fbabaa9a81d2ba2a54ec293414cd040971ed57ad6c0c764515c7e35`，对应wheel SHA为`e75e80bd04c4c7088e2bfafef40e6c9de4d3fb772948b0f721eda159dda45310`。真实原生事实采集、提交/撤销、宿主恢复、CTA/BT、HTTP/页面与生产仍分别待验。

真实分钟004（外部历史/待归仓路径：`../../build/guanheng-workspace/strategy-native-real-minute-004/REPORT.md`）消费独立两日1435条QMT冻结样本。固定原WtBtPorter在2026-10-21 09:30–15:00运行，init每证券取得前日最后2条；09:31首calculate至15:00共240次，当日bar共718条，723次历史前缀检查全部符合来源及截止。辅线缺14:59时保留14:58末条，没有补零。全流程1151ms/20秒，非forced、exit0、进程wait及管道结束；没有setter、通道或执行器，原生交易输出为空。该结果与003的09:33起点/237次观察分别保留。

根任务独立回核（外部历史/待归仓路径：`../../build/guanheng-workspace/strategy-native-root-002/real-minute-004-verification.json`）核86项实际文件身份，并从原始market-data用独立`struct`编码重新构造88字节bar：1435条来源、723次前缀、718次bar及240次原生时钟全部相符；收尾清单SHA为`483909a0bb8de1f70ca06eab8b76bb1f1e5e1131d93e8f1c9f05ca06e5d8615e`。此证据授真实冻结分钟到原CTA完整当日读取；量额开发profile、coverage unknown及非configured/非实时/非生产限制保持。

后继薄BacktestPorter产品正接入原C ABI。读取白名单是signal/execution并集，完整提交仅覆盖execution集合；八角色映射589680→589000实际需要9只读取证券。此边界按NSK分别准入，不把信号专用代码加入清仓向量。下一步修正纯核内部截止、完成薄绑定独审及同核/数量/原生组合，再接业务HTTP与实际页面。

## 后继：完整业务核、数量与原生撮合首次组合

组合实验原件（外部历史/待归仓路径：`../../build/guanheng-workspace/strategy-configured-native-001/runs/3c8640531d2b440c82dca57c1d9449e8/completion.json`）使用冻结a4 wheel、独审NSQ a1 wheel、薄Porter候选及相同固定原WtBtPorter实际执行。输入为完整八角色合成闭合日线与辅助事实；9证券读取、8execution提交，589680仅产生信号、589000为对应执行代码。样本明确指定初始资本100000 CNY、raw价格10 CNY/份、费用0及T0合成品种资料，均属于本次输入，不成为业务默认。

2024-01-04..09实际4次calculate/36次bar；每次原生日线前缀逐日期及OHLC/volume/amount与冻结来源相等，附回对应行的因果辅助后，整个公开核结果与独立纯前缀计算逐日一致。quantity只调用NSQ；新经济代际前先用当次capture核旧代actual收敛，未跳过旧pending。

| 决策日 | NSQ阶段 | 完整向量内CSI300目标 | 当次原生实际量 | 原生后继成交 |
|---|---|---:|---:|---|
| 01-04 | buying | 900 | 0 | 01-05开900 |
| 01-05 | 旧代converged，再新代buying | 1400 | 900 | 01-08开500 |
| 01-08 | converged | 无重复提交 | 1400 | 无 |
| 01-09 | converged | 无重复提交 | 1400 | 无 |

两次提交均完整覆盖8execution，7只零目标明确保留，signal专用589680没有进入向量。原生trades实际两条900/500，positions为900→1400→1400，funds所有损益及费用为0；同次cash由显式资本加原flag0减原actual市值派生，原始捕获与逐笔CSV重算一致，没有新增持仓或现金账本。capture前后枚举相同且同owner，无跨线程setter；entry区分仅授固定、初始flat、单上下文、绝对目标setter的本现金多头模型。

原生子进程391ms退出0，nonforced、wait及有限管道收口。20秒期限从合成输入准备完成计至子进程回收，本实验不授包括文件准入的全流程期限或完整父死亡/故障矩阵。根任务`close.py`重核58项冻结文件、原生逐笔CSV、capture actual与现金；收尾身份（外部历史/待归仓路径：`../../build/guanheng-workspace/strategy-configured-native-001/closing-identity.json`）SHA为`74ebdbf92969be7c3610e57627094fe8398c543eba89c250eba72ea1027d81b6`。

薄Porter候选SHA为`c06d7b7b5f5af8f7b188a7d37a47782bef09ca4e312ae7093431dc2c66ddf06d`；15个原DLL场景包括pending覆盖、T+1拒绝、回调异常、线程/重入、空数据、ABI拒绝及9/8、16/8、只读集合。根任务冻结364项输入/原件于root-freeze-001（外部历史/待归仓路径：`../../build/guanheng-workspace/strategy-porter-001/root-freeze-001.json`），SHA为`e1d8de927b53b25d582b68e9bcf5461e248f61b597ec5160102f9166b7e20460`。独立full另在进行，不以这些开发结果代替独审。

产品会话依[NSB](../specs/native-strategy-backtest-session.md)实施，后继须覆盖非恒价/费用/卖出/T+1/未知与恢复、独立安装及用户入口。本次小样本组合仍消费a4，F4不因小样本通过关闭；a5截止修正候选已冻结为新wheel，资格由后继独立delta决定。真实ETF历史/辅助、RT、柜台及生产均未授，整体移植继续。

## 后继：纯核a5与薄Porter独立验收

a5独立delta-004（外部历史/待归仓路径：`../../build/guanheng-workspace/reviews/strategy-core-delta-004.md`）结论complete，仅授冻结纯核。254项安装测试、676组普通语义对照、原数值/元数据/UTC反例及内部期限传播通过，56/56输入无漂移。原256及2048窗口配方约5秒稳定返回`calculation_timeout`，F4关闭；5秒是协作期限，调度与单步抖动明确保留，未承诺所有合法输入必在期限内成功。新wheel SHA为`5397695ccf208cac7c3e8fcd2a44ee36ce613a3ee59f7423201fa2d51ff6886c`，报告SHA为`2ba706273d14ab2ef4650a4a0a6677694dddc50e5ce90a18f61f20c69cd67a23`，128项独审manifest SHA为`78b3697d3cc4332b47dc2f2782c5de83f24d0456a4497e37089a5d3049d6e65c`。a4实验资格和原件保持当时边界。

薄Porter独立full-002（外部历史/待归仓路径：`../../build/guanheng-workspace/reviews/strategy-porter-full-002.md`）结论complete，开放产品发现0。15个原场景与28个新增独立反例共43个实际原DLL/准入子进程通过，全部Job预绑定、nonforced、exit0及回收。独立覆盖多块count/isLast/身份/空指针、借用缓冲返回后擦除、线程/重入、非法loader/枚举、数值/标识、提交前中后故障、异常诊断及run顺序；产品SHA保持`c06d7b7b5f5af8f7b188a7d37a47782bef09ca4e312ae7093431dc2c66ddf06d`。报告SHA为`8977e63c712c705c90d9e62aba9880c60de5cba90436f3a4236d25071a667da7`，1111项独审manifest SHA为`3188901f6aa26ea62c1a168b69a2609e1f19fba418237d79132e0d97cb625ec9`。

根任务逐项回核（外部历史/待归仓路径：`../../build/guanheng-workspace/strategy-native-root-002/core-and-porter-review-verification.json`）确认上述128及1111项实际文件身份相符；复用资格限对应纯核与薄ABI边界。NSB会话候选已另行实际消费a5、NSQ及薄Porter，包含动态价格/费用、T+1、未知费、预热和失败隔离，独立full进行中；较长回测结果保留容量也纳入审查。正式父宿主按[NSH](../specs/native-strategy-host.md)实施，启动/回收/完整结果资格不由薄Porter或单个实验代替。没有新增框架修改、真实委托或生产切换。

## 后继：会话独立full发现与修正范围

NSB full-001正式报告（外部历史/待归仓路径：`../../build/guanheng-workspace/reviews/strategy-session-full-001.md`）结论gap，开放2项P2；源码冻结SHA为`4f905702e5ad2da2190c22f6aa7440ea2aec12dcbea7e86c0a615ac7ab5d663d`。报告SHA为`83ba2304a42e869f0f287599fd21d6332563de751c0681b2ffd471e385d118de`，manifest SHA为`1cff26e3147577b222295cec82890bc4e2b75fe316f3d5b7fa73205264177079`，根任务已重新计算两份摘要相符；1157项原件的全量回核未在本次重复执行。独立32项测试、12个原生子进程及59次capture核对见正式报告，不能抵消已复现发现。

F1：每日保留整个累计核结果造成二次增长。默认窗口100、1250日的实际原DLL回测于第335个输入日达到8MiB，失败隔离正确，但正常多年回测无法完成。F2：资金转换只固定精度仍继承Decimal指数和陷阱，同一合法本金在Emax=2下令真实回调锁存Overflow。两项归自有session层，无新增WonderTrader框架修改需求。

最终NSB规格已明确共享完整历史、逐日紧凑快照及完整前缀精确重建，保留线性计量和setter前容量准入；数值转换完全独立调用者上下文。原产品owner解除开发冻结，在新轮次修正并覆盖原触发、普通费用/T+1和异常隔离，完成后再独立审查。旧候选、报告和原件保持；当前修复尚未取得完成资格。NSH正式结果接线依新版本协议重新验收，既有父宿主实验仅授所测边界。

后继应用发行元数据已升`guanheng-app==0.1.0a2`，显式依赖`guanheng-strategy-core==0.1.0a5`与`guanheng-strategy-native==0.1.0a1`；本仓库私有包来源写入uv配置，锁文件共28包。根任务使用本仓库Python3.12和E盘缓存完成`uv lock`，随后`uv lock --check --offline`及文档导航检查通过。此项只确认发行依赖及锁文件，独立安装、NSB/NSH修正、用户入口和最新整包资格仍待对应验证。QMT终端HTTP按用户最新决定仅用于今晚前临时流程，停止优化和新部署；新SHM接入须等待另一对话开发完成且今晚实测通过确认，不影响本轮离线原生回测。

## 2026-10-22 后继：NSH、NSB与NBC独立修正

NSH创建窗口修正已通过独立delta-002（外部历史/待归仓路径：`../../build/guanheng-workspace/reviews/strategy-host-delta-002.md`），报告SHA `f5144bd86a9987b8b7bc29fde988616ca8f9820785dbde316698e0bfa4e43e6e`。新版72场景通过，原版9项对照保留；真实API成功前后异常保持PID/句柄/wait，句柄净增0。2640原件清单根任务逐项回核一致。原 full 的P2关闭。

NSB v2后继F3是公开重建入口可绕过同版校验。现由唯一validator返回深不可变ValidatedSessionReport，普通构造、两个公开重建入口及单记录入口均准入；raw dict每次校验，重复扫描复用已验证值。独立delta-003（外部历史/待归仓路径：`../../build/guanheng-workspace/reviews/strategy-session-delta-003.md`）complete，报告SHA `0da32fb315366982020a412ed1d1df088f56135ee219abfaa9516e975b755111`；97组反例、8check路径、96测试通过，1249全部前缀SHA保值，7点独立语义仅按原资格SHA绑定复用。根任务回核1273原件一致；不重复或扩大既有569秒长原生回测资格。

新Session SHA `380aa6d8bc1878c709dda7a4c82e32a082ab3ffee1149120abc0821f1d7ddf0a`，新Job SHA `26e814798b895a8aa6e693b611dd1964c9df6983b09b430868de52d3fb2c4c01`。NSH delta固定旧Session，NSB delta固定各自实验，组合新应用由[NBW后继](2026-10-22-native-backtest-workspace.md)另做正式安装/实际链，不能按单组件通过推导整包完成。
