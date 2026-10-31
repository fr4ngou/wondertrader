# 账户与市场观察的可读结果和局部降级

类型：模块C展示切片证据。状态：候选005主路径、边界及独立双轴审查通过；完整模块继续in-progress。依据[只读可用性](../product/brief.md#只读查看与可用性)、[NAC-R7](../specs/native-account-console.md#nac-r7-中文用户入口)、[QAR](../specs/qmt-shm-account-read.md)及[OBI](../specs/independent-market-observation.md)。

## 根因与实现

AccountWorkspace在读取中、失败或能力提示关闭时清空展示；ObservationShell把目录、定义、序列、历史导航的任一失败传播到整个看板，原图及期货/期权也共同清空。账户GroupSource将内部运输绑定、路由、摘要、会话及请求编号当作日常内容。修正各自展示层，原后端DTO、来源查询和交易授权保持。

账户沿一个React Query内存值分开保存当前轮原DTO与至多四类成功批。每类新成功批（含空）替换同类，失败批明确显示上次成功结果及原查询时间；全部读取失败保留原值及刷新原因。已知来源身份改变后清除跨来源回退；不合并行、资金统计、原scan_id、订单责任或真实账户事实。未配置时保持自动读取关闭，明确刷新仍沿原API；能力提示变化保留已读结果。账户/交易记录/总览共用此实现。日常来源只显示掩码账户、实际环境和北京时间，内部技术身份留在原DTO。

观察沿既有按快照/指标/日期/参数隔离的Query缓存展示，刷新状态单独提示；序列自带定义可以绘图，历史导航缺失仅停止导航，主图和原始表保持。四品种的期货/期权各自读取与降级；原图、对照数据、说明、回执和目录保留各自成功值，成功空替换为空。运行更新失败明确本次状态不可用，上次心跳/回执的时间保留，缓存不授当前存活。新增ReadNotice统一刷新/失败/上次读取时间和手动重试。

## 主链与验证

外部原件根`C:/Users/frangou/.codex/visualizations/2026/10/28/01a1827c-4d9e-7d23-b0c3-a7ddb931c0d3/read-only-business-001`。全部QA沿原`native.run(private_console=True)`有限Job、输出和截止执行，原件按代际命名。

- 157前端定向回归通过，覆盖账户正常、完整空、partial、HTTP失败/繁忙/恢复、能力提示停用、分页/标签、私有字段拒绝、来源改变，以及观察目录/指标/定义/历史导航/原图/期货期权/回执的正常、失败、恢复、查询切换及成功空。TypeScript、正式SPA003和分块检查通过。
- 当前源码App及正式SPA003通过原HTTP读取既有观察发布根`build/observation-provider-completion-001/main-003/data`，固定原snapshot和沪深PB指标；首次历史导航503仍绘制真实序列，恢复导航后，序列刷新503保留图、表和日期，成功空清空当前图。浏览器账户响应用仓库公开DTO2合成材料，在真实Query/API边界验证读取中保留、失败保留、局部更新、来源改变、成功空及恢复。账户本轮不授真实券商或新B原生主链资格。
- Browser plugin not available，复用既有Playwright/Edge。页面身份、非空、无框架覆盖、1440×1000/390×844、LA浏览器时区、零页面横向溢出、内部身份不渲染均通过；console仅受控503，warning为0。所有请求为GET；没有账户/行情采集、交易或生产动作。App正常shutdown、线程join、端口关闭和原Job/tree/EOF/join均完成。

## 尝试及资格

001/002失败由旧“隐藏旧值”断言、时间标签和提示预期引起，另001类型检查发现JSON fixture类型需沿实际校验边界准入；修正测试使用当前需求和validateAccountOverview后003全通过。失败收据九项回收状态全部true、errors为空、无保留owner；原日志未覆盖。

本轮展示缓存为有限可重建值投影，涉及金融事实的来源隔离，送独立规格/规范两轴审查。独立App新整包安装、真实B账户浏览器后继、数据资产其他子页的同类缓存、唯一策略完整M1及统一升级回滚继续；当前未部署生产，未操作QMT界面或真实下撤单。

## 独审修正候选005

原003 full发现来源JSON键重排误清缓存、外层capabilities失败卸载整个Routes、两处观察详情残留快照前缀，以及旧DTO1超安全整数代际经JSON解码合并。原003冻结源/原件/SPA及full gap保留。新实现按已验证来源字段的固定元组取身份，旧代际准入改为安全整数；IndependentApp将能力说明与只读路由分开，首次能力读取失败也能进入账户页主动读取，后台能力失败保留已读页面；观察详情只显示发布时间。

修正产品005的162定向前端回归（验证006）、类型检查、正式SPA通过，覆盖原触发、实际换源、键重排、两相邻超域代际、外层首次/后台失败及恢复。验证005最初两条路由断言仍假定连接信息先于页面完成，006改为分别等待页面和元数据，未改产品逻辑；原失败及关闭保留。当前App/正式SPA005的Edge主链重新通过，包含真实归档图/表、历史导航独立失败、序列刷新失败、真空展示、无快照摘要、能力首次/后台失败仍可读账户，以及相同来源键重排的partial保留和真实换源清除。账户依然为明确合成DTO，所有请求GET，只有受控503资源错误，零warning；App/线程/端口和原native Job完整关闭。005独立delta继续，不提升完整App安装、真实B链或整个M1资格。

A后续市场范围候选已由C只读核验：`build/qmt-market-history-scope-001/DELIVERY.json` SHA `611a29a9d6637f5cfb4005b1b1f6694d7cb095746ac91a7ad11b2e5c02769e4d`、`unified/relocated-001/MARKET-RUNTIME.json` SHA `2f417ae0f96ee2ef01dad0326e0c22cffa8eb7a62989f851d4a1cd4a8ae2f65e`。沿其已安装工具verify/resolve核1161个清单文件及受控路径，两次原native Job正常关闭，原件`build/retained-resonance-kernel-001/A-CURRENT-VERIFIED.json`。该元数据核验步骤只读取公开安装资料，组件启动与页面消费按下条实际主链授资格。

后继实际消费已在`market-current`完成：复用原普通35发行Appa19/SDK0.15，SourceMarketProcess沿原source-collected配置直接装入A新统一安装内history组件，配当前SPA005。三证券各2000根及当日240根与原件逐字段一致，两代App、390/1440、真实源停止/HTTP503保留、成功空和重试恢复均通过；主链40秒量级正常结束，App/来源/线程/端口及原Job关闭。源配置只读已有归档，QMT业务请求/真实下撤单为0。该条授新A历史组件消费与当前行情页面资格；新版HPR实时补齐、唯一策略前复权/周期及新完整App发行仍待后继组合，旧私有配对未读取。

## 最终绑定与剩余工作

005两轴delta均complete、无新增P级问题，原full gap及复核原件保留。规格报告SHA `bf7405fc46113ec87fb06f30319fdb2684bf66f8ae885a4f2e0840e72ab09613`，规范报告SHA `a82bb910d94aa13fdbd514d03fc9e652be9a97bc9f2a4920eb3e97eb874fad01`。REVIEW-INPUTS-005 SHA `52fe30987b318da2f99ab1280cf1f78c23e0767fc4e0ef1aec47f6c421f8c5cc`固定26源/26原件/18SPA，当前源与冻结副本及全部SPA再核一致。正式ZIP的18成员逐字节对应，SHA `66d0670cddaaaac9604cafa9e0b80a35ba8e1162941f16ae9f66321b9a9eb2fd`。

外部根`DELIVERY-005.json` SHA `ecd4f475be68bdcb278e583f9294925e43ea26d99f86193da406ff9f764aac1f`同时绑定双轴、源码、原件、SPA及新A历史组件两代消费；delivery5-005原Job正常结束。只授本切片资格：数据资产及其余只读工作区状态、完整新App发行/安装、真实B账户后继、RR112真实前复权/周期、原生BT/RT与隔离委托撤单页面整链、统一升级回滚仍待完成。旧QMT只读，真实下撤单/QMT界面操作/生产切换均为0，完整goal active。
