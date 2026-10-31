# 统一可安装行情运行候选

类型：功能最终规格。状态：accepted。前缀MRC。范围：交付计划A-07/M3的模块A组件装配；App继续拥有进程生命周期，全系统M3、实盘与发布分别验收。

## MRC-R1 来源与职责

新增`scripts/package-market-runtime.py`及纯装配实现`scripts/native_support/market_runtime.py`，专用QA为`tests/integration/market_runtime_candidate/`；本规格、专用证据及build/market-runtime-candidate-001归本模块。原组件代码、DLL、格式、默认值、状态、线程和恢复协议保持。共享App/SDK/WT/Common/索引/CMake/NOW/CURRENT只读。

六项输入必须显式给出路径和SHA，缺项或身份不符拒绝装配：RS14 package005的160成员历史服务安装；SDK216的0.15 wheel；HPR product002的candidate-e安装；collection-relocated005的app原生12文件及原许可证；NMR candidate002；显式ParserQMTHostV6最终安装。来源版本及实际SHA存入输入锁和总manifest，组件内原INSTALLATION/MANIFEST与许可证逐字保存。采集app本身无INSTALLATION，沿原INSTALLED清单核所选原生子集，保存原清单及明确native-app-only范围，装配收据只登记所带子集，不授旧整包资格。

原RS14候选精确来源固定如下；工具中的ORIGINS与此一致。MRC-R5登记的CNH后继由输入清单明确选择，原候选及其他组件保持原身份；其他未登记版本拒绝装配。

| component/版本 | 原身份SHA256 |
|---|---|
| history / RS14-package005 | 48e907ccfca84d6eb65eb07cdaacb1ee876dc19fdb80a4380228735826ddaf73 |
| sdk / 0.15.0 wheel | 34579862be4dc777bf2f10cceff64d0df2a242a7ee78f368c06e9a4c744287ab |
| hpr / HPR-e | 5c3e3ffb082f09c2965c70336664f81b1816b951c8c676d58d397c35d4623ad3 |
| collection / collection005-native原来源清单 | 11cfb6725e327285b26be85c84ab201ae7c39dbd0e00550605738256e056e2a9 |
| minute_reader / NMR001 candidate002 | aee1e7c6615172e82a62dd8ef56d96fc05da03d7a07fa9f35735cce467b1f5fe |
| parser_v6 / v6-001 MANIFEST | b0a105513e0ea2f6aaec9d3c6d68c8548ec4d6eaa4274a0072cb482b2cf250ea |

复用既有native_support.artifact.normal_path、原逐文件安装职责及ZIP标准库；装配器补六种已冻结安装形状的共同目录/消费映射，不重建业务模块。不包真实数据根、凭证、账户、真实策略正文、日志、通信Journal、运行控制文件或历史数据；仅带原组件许可范围内源码/二进制及脱敏例。输入清单具有明确文件集合，禁止任意目录打包。

## MRC-R2 目录与消费

总目录含`components/{history,sdk,hpr,collection,minute_reader,parser_v6}`、`examples/`、装配工具及`MARKET-RUNTIME.json`。组件独立目录避免同名DLL覆盖。总manifest登记schema、Windows x64、组件版本/来源清单SHA/原生关键SHA、完整成员SHA/字节数、消费字段及资格边界。不得从不同组件挑选同名库覆盖原文件。

消费字段只使用规范相对成员路径并包含SHA：Parser module/library及原例；NMR library/module及minute_native显式开关；history service entry/原Reader/Helper；collection service entry（沿history冻结源码）及原DataKit/Storage/Lifecycle/Helper；HPR pythonw/python/agent/app_adapter/原CLI；SDK wheel/version。resolve命令在核总manifest及全部成员后，仅把这些成员路径渲染为该实际安装根的绝对路径；输出公开路径/摘要，不读用户运行配置，不自动启动或写App配置。

manifest的consumers字段精确列原module、App owner、入口引用及原schema：history服务guanheng.source-market-service.v1，HPR进程qmt.history-preparation-process.v1，采集服务qmt.quote-collector.v1；不把不同层级的service/process配置互换。

entries.hpr_agent是可校验的包`__init__.py`文件锚；原HistoryPreparationProcess配置installed_agent取该锚的parent目录。hpr_app_adapter是源码文件锚，导入根取其parent.parent；collection_session的parent为原采集native.directory。hpr_cli供模块身份核验，实际配对仍用hpr_python沿原`-m guanheng_qmt_shm.history_preparation_cli`入口。

原HTTP Reader默认、未启用HPR/采集/服务的默认行为保持。Parser v6必须由调用者显式选择原module；包存在不授权连源。HPR源配对/Journal/状态及历史数据目录由调用者在包外显式提供，App使用现有Managed owner。source service内部冻结SDK载荷与独立SDK0.15 wheel相同；调用者SDK沿普通pip安装wheel，不解包覆盖依赖。

HPR原venv是已验Windows x64安装，pyvenv.cfg及INSTALLATION保留原Python runtime_anchor；移动本候选目录保持字节身份，不宣称把系统Python运行时搬到任意机器。消费者必须核本机所需外部Python运行时/基础资料/私有配对/数据根；缺失时保持未启动并报告对应缺项。源端3.6.8解释器仅QA外部输入，终端不入包。

路径约束沿组件唯一实现：原生NMR按实际数据根+证券构造核RT256/日志512字节（含结尾零）；其他入口继续原配置路径/读字节/身份验证。resolve只渲染安装成员，不接受外部数据根插值或伪造原生路径资格。安装根及全成员拒绝符号链接、junction、所有reparse point和硬链接，规范路径拒绝Windows别名/大小写冲突/穿越。

## MRC-R3 有界装配与搬迁

create先有界读取显式来源清单，再从第一遍枚举开始限制文件/目录总量，逐项核清单SHA并消费同一次受限快照。每文件不超过64MiB、所有载荷不超过256MiB、枚举/ZIP成员不超过4096；清单不超过2MiB。只创建新输出目录，不覆盖已有候选。所有原生关键入口必须在清单内且SHA匹配。

总manifest严格字段/schema/路径/字节/SHA/组件集合校验；文件集合必须精确相等。verify同时核内外清单身份，未知成员/重复大小写/错误组件及损坏拒绝。extract要求外部固定ZIP SHA，先核完整成员集合、大小、压缩类型和所有字节摘要，再写新目录并重新verify；ZIP绝对路径、穿越、重复/链接/超额拒绝。失败不产生成功收据，不以局部目录作为有效安装。

ZIP在创建ZipFile前先逐记录核central directory不超过4096项/8MiB，拒绝多卷及Zip64目录，避免其构造期先无界加载成员。输出目录及ZIP不得位于任一原组件来源根内。

## MRC-R4 组合验收

主链顺序：create新目录→ZIP全成员验证→extract新搬迁根→resolve消费字段→普通安装SDK0.15并核模块身份→安装历史服务1m+d1及原Reader逐字段→安装NMR对上午真实只读样本及原通知/stop/持有切片→显式v6 Parser沿同候选HPR正式Host/认证SHM/实际3.6.8完整内存正文SDK替身取得三证券→原owner正常关闭。所有真实QMT请求、下载、账户与交易为零。

采集原生组件按关键文件及同原证据输入核复用；对新的装配路径核原库加载。历史组件所带collection_status与旧采集Python集合的字节不同，新增同候选原采集service→真实SHM/SDK替身→原005 Writer→原Helper回读及实际App采集owner关闭，防止以旧原生证据代替新Python组合资格。原模块异常/完整资源证据在输入相同时复用，组合变化重新核真实路径/导入/加载身份。主链后覆盖缺输入、漂移、额外成员、路径链接、超额/损坏ZIP、已有目标与搬迁解析；独立full按standards/spec读最终源码，运行资格分别登记。

交付HANDOFF/DELIVERY固定源码、组件、manifest/ZIP及结果SHA，列实际消费字段、复现及边界。下午自然策略调度、完整B/C用户链、跨机器Python安装、真实源授权/单位、真实下载、全市场容量与全系统M3不由此装配授予。

实现及固定候选验证见[2026-10-29组件装配证据](../evidence/2026-10-29-market-runtime-candidate.md)；代码审查与实际运行资格分别登记。

## MRC-R5 采集归档查询后继

CNH最终组件具备原RS14能力及source-collected，允许history显式绑定CNH-package002：原INSTALLATION SHA 225791a042473d5aa669bf8f56aa09a3ed2d3e06cb3d8864db4270e102167903、161文件。原RS14-package005及其160文件仍可装配和核验；SDK/HPR/采集原生/NMR/Parser身份不变，配置默认关闭和manifest schema保持。装配工具集中登记组件清单SHA与版本的唯一映射，create按输入原SHA选择，verify按实际清单SHA及匹配版本核验；不通过修改版本文字放行任意新清单。其他字段、总字节/成员上界、原生关键入口、许可证和精确文件集合校验继续。

先组装新候选、ZIP核验/新根搬迁/resolve，核五个其他组件与原005逐字节相同、CNH原161文件相同。用该搬迁根接真实旧历史与今日归档的SDK/App接口，原四条安装组合按受影响路径复验；真实来源业务请求及交易为零。之后验证旧候选兼容、未知history原SHA及版本/清单错配拒绝、普通安装与关闭，独立审查登记源码与运行各自范围。完整页面和系统M3、长期运行、真实交易/生产资格另验。

收盘后运行新候选组合时，NMR明确选择snapshot回放范围：仅读原上午212冻结副本，验证新安装路径的原Reader/通知/切片/stop与默认HTTP，不读取已完成归档的137现场来冒充上午窗口。snapshot-and-live默认保留原现场验证路径及资格；回放结果不读取旧LIVE.json冒充当前连接。新组合记录minute_scope，真实现场读取及全天采集分别沿原有效证据和自然归档主链证明。


## MRC-R6 来源市场范围补齐后继

状态：accepted / in-progress。沿HPR2的limits.v2和RS15把正式补齐范围改为来源支持的沪深市场，统一候选同时提供新版history和HPR；原schema、消费入口及默认关闭保持。history原清单199c3eb662d135b6866a5bc21b19d98393fdeb8cf720194e98597042af24542e登记为CNH-market-scope001，HPR原清单819ae7497b765f4005afc230f3d6bc46d5c58c70d47fcb615173d4c62af45ba1登记为HPR-market-scope001。旧RS14/CNH/HPR-e候选继续原映射，其他四组件保持原件。

新目录装配、ZIP搬迁、resolve后，用新两个组件完成省略逐只证券配置的SDK→原Host/WinSHM/3.6.8正文→原Helper/Reader补齐和重复/重连主链，核旧候选与新入口身份及全部资源关闭。实际QMT新正文安装及真实下载、完整App和系统M3继续分别验收；该候选不自动切换运行实例。


## MRC-R7 原生报价插件与来源范围组合

状态：accepted / in-progress。来源已采用HPR2 limits.v2时，统一候选显式提供兼容该合同的Parser后继。登记parser_v6原MANIFEST SHA 348508d29f0928a49cbfba38b9f1439685ae7b4f5c0aa1eeab5f984d5031f93a，版本v6-market-scope001；DLL SHA 31bf05de7c2f4ee14363dee5a02aed7850c673055d724be78ad7c51ff3b1346b。原v6-001及所有既有映射继续可验，其他五组件沿R6当前输入保持原件。新增准入限自有BoundCore的profile_v6分支，支持明确v1/v2形状，WT框架、插件工厂和默认行为保持。

装配和搬迁后，复验四条现有安装组合；真实来源通过当前已运行的limits.v2配对取得三证券标准SPI，再正常stop/delete/Host关闭。Host进程ready与QMT已认证连接分别核实；初始化调用者先在其原启动截止内取得认证read-binding，再调用Parser的connect。等待只读取连接状态，不派发SDK或增加证券权限。原失败回执保留，超时按当前启动失败处理，沿原生命周期关闭。源价格单位及盘后时效沿来源原资格，此组合不授策略整链、长期全市场运行或真实交易。
