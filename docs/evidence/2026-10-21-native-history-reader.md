# 2026-10-21 原生历史 Reader 与同实例 CTA 验收

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：实现及隔离整链验收。状态：源码、模块测试、原生宿主、独立 full 审查、完整流水线和搬迁包验收通过。要求见 [NHR-R1–R6](../specs/native-history-reader.md)，运行方式见[操作手册](../runbooks/native-history-reader.md)。

## 实现与原因

原历史 reader 的缓存可在同一实例继续返回旧历史；策略按需补齐、追加及同条数修订需要新读取看到当前合格数据。自有 `GuanhengHistoryReader` 通过原 `IDataReader` 接口接入：原 CTA → WtDtMgr(force_cache=false,times=1) → reader DLL → 独立 HTTP 服务 → StrategyMarket → 原行情服务与 NativeHistoryStore。日历、来源合并和补齐继续由既有统一模块负责。

SDK 0.7.0新增 `tail_history_1m`，按权威分钟计划倒查最近N根，不以现存稀疏记录跳过缺口。每次成功读取返回拥有独立数组的切片；内存按持有切片计费。分钟轮次先取得合格结果，再完整投递原宿主回调批；恢复分钟只更新历史可见性，当前分钟才形成策略事件。回调期间释放读取所需的锁，stop停止新准入并完成在途批次，异常结果未知则隔离并保留指针。

本轮只新增或修改自有适配、测试、构建接线及文档。12个冻结上游文件摘要与既有基线全部一致。当前开发制品仍包含已冻结差异，不授其生产保留资格。

## 实际验证

| 验证 | 结果及覆盖 |
|---|---|
| SDK | 52项单测；另独立100组跨窗/end/count组合，日历未知、空窗口、缺口、预算及来源边界通过 |
| 原生插件 | 9项测试通过：同实例补齐/追加/修订、旧切片与容量、身份变化、并发读、pool重入、stop等待、异常批次与单init |
| WinHTTP | 5组测试通过：严格字段与身份、数值、重复键、容量、认证、慢body截止、重定向等负向 |
| 独立reader服务 | 12项测试通过，含真实回环HTTP→原SDK→market HTTP→native Store；缺口恢复、上游不可用后缓存回读、来源谱系与总预算 |
| 原宿主 | 原WtDtMgr与CtaStraContext，同一实例，poolsize=0和2通过；实际HTTP与DSB存储、同条数修订、旧切片保持、current/recovered、重复分钟及回调读/stop |

宿主收据（外部历史/待归仓路径：`native-history-reader-2026-10-21/host-acceptance.json`）记录pool0的5次事件与pool2的4次事件，每次回调均重新读取两根历史。差别来自pool0另验证首次Pending后由分钟事件完成基线恢复；pool2先成功读取建立基线。09:34和延迟处理的09:36作为恢复历史，不伪装当前事件。reader对象销毁后，旧切片仍与最初内容逐字段一致。

宿主首次构造漏传原WTSHotMgr，使首次成功读取的原 `WtEngine::sub_tick` 无法访问必需依赖；补齐隔离宿主初始化后整链通过。没有修改上游方法。测试使用原核心类并显式触发分钟，未运行完整生产WtRunner行情ticker/交易进程。

## 独立审查

full报告（外部历史/待归仓路径：`native-history-reader-2026-10-21/full-review.md`）、审查输入（外部历史/待归仓路径：`native-history-reader-2026-10-21/review-inputs.json`）及独立执行（外部历史/待归仓路径：`native-history-reader-2026-10-21/review-validation.json`）保留源码与制品身份。开放发现0。发现的NHR-F1 P2生命周期文档缺项已关闭：stop仅等待在途调用；reader对象、旧切片和DLL加载引用分别管理，DLL及依赖在最后切片release之后才可卸载。规格、模块和手册已同步。

## 完整开发制品

完整运行 `python -B scripts/native.py all --offline --qmt-source D:/workspace/qmt --calendar-owner-source E:/workspace/qmt-worktrees/wondertrader-service-adapters` 退出0，21阶段全部passed。71项启用CTest全部通过，1项既有全天时段用例Disabled；32项流水线测试通过。完整收据（外部历史/待归仓路径：`native-history-reader-2026-10-21/receipt.json`）和CTest结果（外部历史/待归仓路径：`native-history-reader-2026-10-21/ctest.xml`）冻结本次输入身份。

新开发包 `build/native/packages/dev-20261021T101256Z-3bd82988.zip` 的SHA256为 `c042f985180b6d44757a8c87aed1f3489545ddb897b635d79eb83123a7cc493e`。包内SDK为0.7.0，wheel SHA256为 `ce2407b167f9f635113dd1f49f4330ce077920fa1f6c6f8186f3c506a8f56d49`。解压目录中的reader DLL、服务、SDK、原CTA宿主重新完成pool0/2同实例链，搬迁收据（外部历史/待归仓路径：`native-history-reader-2026-10-21/package-host-acceptance.json`）为passed；原策略、分钟业务消费者、worker与跨仓日历搬迁回归亦通过。独立full审查23项最终输入摘要全部匹配，12个冻结框架文件摘要全部保持。

## 限制与后续

本记录来源均为合成隔离fixture。真实428根QMT数据的资格沿[先前来源验收](2026-10-21-real-qmt-native-history.md)，当前reader整链不能将其覆盖或精度提升。生产分钟日历接口及证券排除仍见[现场核实](2026-10-21-live-minute-calendar.md)。

原宿主基础m1读取已验；WtPorter强制缓存、重采样、多个策略同时修改原宿主订阅容器、完整WtRunner ticker和生产退出编排另验。原WtDtMgr不释放其reader加载引用；本测试证明reader对象销毁后切片存活，实际DLL卸载安全须由受管宿主单独证明。生产仍使用保守poolsize=0配置，pool2的单上下文隔离通过不扩大原容器并发契约。

本轮没有部署、重启终端、下载全市场、委托或撤单。整体适配目标保持active。
